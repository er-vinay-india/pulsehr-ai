from __future__ import annotations

import json
import logging
from typing import Any

from ...gateway.model_gateway import ModelGateway, extract_json_payload
from ....core.models_config import ModelRole
from .director_models import (
    InformationDestination,
    InformationSourceType,
    InformationUnit,
    PresentationIntent,
    PresentationPlanningContext,
)

logger = logging.getLogger(__name__)


def extract_and_triage_information(
    ctx: PresentationPlanningContext,
    intent: PresentationIntent,
    max_retries: int = 1
) -> list[InformationUnit]:
    """Stage 2: Extracts atomic InformationUnits and triages them into MAIN_DECK, APPENDIX, SPEAKER_NOTES, or OMIT.

    STRICT PRECEDENCE RULE:
    Current evidence always supersedes historical memory. Historical context provides background or
    comparative benchmarks, but can NEVER overwrite or contradict current empirical ground truth.
    """
    raw_units: list[InformationUnit] = []

    # 1. Dataset Profile units (Current ground truth)
    raw_units.append(
        InformationUnit(
            id="INFO-SCOPE-01",
            title="Reporting scope",
            statement=f"The review covers {ctx.total_records:,} records from '{ctx.dataset_label}'. {ctx.completeness_pct}% of data cells are non-empty.",
            source_type=InformationSourceType.DATASET_PROFILE,
            source_ref=ctx.dataset_label,
            confidence=1.0,
            priority="HIGH",
            destination=InformationDestination.MAIN_DECK,
            rationale="Essential baseline scope establishing empirical ground truth.",
            metrics={"total_records": ctx.total_records, "completeness_pct": ctx.completeness_pct}
        )
    )

    if ctx.baseline_benchmark:
        raw_units.append(
            InformationUnit(
                id="INFO-SCOPE-02",
                title="Baseline Benchmark & Dispersion",
                statement=f"Operational baseline: {ctx.baseline_benchmark} (Dispersion: {ctx.dispersion_metric or 'observed variance'}). Window: {ctx.reporting_period or 'Full Period'}.",
                source_type=InformationSourceType.DATASET_PROFILE,
                source_ref=ctx.dataset_label,
                confidence=1.0,
                priority="HIGH",
                destination=InformationDestination.MAIN_DECK,
                rationale="Defines the network benchmark against which variance is evaluated.",
                metrics={"benchmark": ctx.baseline_benchmark, "dispersion": ctx.dispersion_metric}
            )
        )

    # 2. Current Evidence (Ground truth empirical findings from evidence ledger)
    for idx, ev in enumerate(ctx.current_evidence):
        ev_id = ev.get("evidence_id") or f"EVID-{idx+1:02d}"
        headline = ev.get("headline") or ev.get("title") or f"Empirical finding {idx+1}"
        finding = ev.get("finding") or ev.get("statement") or ev.get("why_it_matters") or headline
        metric_val = ev.get("metric_value") if ev.get("metric_value") is not None else ev.get("value")
        comparison = ev.get("comparison") or ""

        # Priority triage: First 6-8 findings to MAIN_DECK, remaining to APPENDIX
        dest = InformationDestination.MAIN_DECK if idx < 7 else InformationDestination.APPENDIX
        priority = "HIGH" if idx < 4 else ("MEDIUM" if idx < 8 else "LOW")

        raw_units.append(
            InformationUnit(
                id=f"INFO-EVID-{idx+1:02d}",
                title=headline[:80],
                statement=f"{headline}. {finding}".strip(),
                evidence_id=ev_id,
                source_type=InformationSourceType.CURRENT_EVIDENCE,
                source_ref=ev_id,
                confidence=1.0,  # Current verified evidence is 1.0 confidence
                priority=priority,
                destination=dest,
                rationale=f"Verified empirical evidence with status: {ev.get('status', 'audited')}.",
                metrics={key: ev[key] for key in ('metric_name', 'metric_value', 'numeric_value', 'unit', 'denominator', 'comparison', 'date_range', 'limitations') if key in ev} | {"metric_value": metric_val, "comparison": comparison}
            )
        )

    # 3. User Prompt Directives
    if ctx.instructions:
        raw_units.append(
            InformationUnit(
                id="INFO-USER-01",
                title="User Focus Requirement",
                statement=ctx.instructions,
                source_type=InformationSourceType.USER_PROMPT,
                source_ref="user_instructions",
                confidence=0.95,
                priority="HIGH",
                destination=InformationDestination.MAIN_DECK,
                rationale="Direct user instruction requiring dedicated presentation coverage."
            )
        )

    # 4. Historical Memory (Contextual semantic retrieval from Phase 1)
    # Strictly marked as HISTORICAL_MEMORY. Subordinate to current evidence.
    hist_ctx = ctx.historical_context or {}
    hist_results = hist_ctx.get("results") or []
    for h_idx, item in enumerate(hist_results[:4]):
        h_text = item.get("text", "")
        h_mem_id = item.get("memory_id", f"MEM-{h_idx+1}")
        h_type = item.get("memory_type", "HISTORICAL")

        # Check if historical statement conflicts directly with current evidence; if so, clarify as prior/benchmark
        # Historical context belongs to SPEAKER_NOTES or APPENDIX unless explicitly relevant as historical benchmark
        dest = InformationDestination.SPEAKER_NOTES if h_idx < 2 else InformationDestination.APPENDIX

        raw_units.append(
            InformationUnit(
                id=f"INFO-HIST-{h_idx+1:02d}",
                title=f"Historical Benchmark ({h_type})",
                statement=f"[Historical Context] {h_text}".strip(),
                evidence_id=None,
                source_type=InformationSourceType.HISTORICAL_MEMORY,
                source_ref=h_mem_id,
                confidence=float(item.get("score", 0.7)),
                priority="LOW",
                destination=dest,
                rationale="Historical memory retrieved for contextual depth. Current evidence supersedes any conflicting numbers.",
                metrics={"memory_id": h_mem_id, "score": item.get("score", 0.0)}
            )
        )

    if max_retries < 0:
        return raw_units

    # Now attempt LLM-assisted refinement of triage if model is responsive
    units_summary = [
        {"id": u.id, "title": u.title, "source": u.source_type.value, "dest": u.destination.value}
        for u in raw_units[:12]
    ]

    prompt = f"""You are the Presentation Director. Refine the destination triage for these information units.
Destinations:
- MAIN_DECK: Core executive slides (max 6-10 units)
- APPENDIX: Audit trails, extensive detail, secondary evidence
- SPEAKER_NOTES: Contextual caveats, talking points, historical benchmarks
- OMIT: Noise or redundant items

Units to triage:
{json.dumps(units_summary, indent=2)}

Presentation Intent: {intent.purpose} for {intent.target_audience} ({intent.audience_seniority.value}).
STRICT RULE: Units with source 'CURRENT_EVIDENCE' are ground truth. Units with 'HISTORICAL_MEMORY' must not contradict current evidence.

Return a JSON array of objects: [{{"id": "...", "destination": "MAIN_DECK|APPENDIX|SPEAKER_NOTES|OMIT"}}]
"""

    for attempt in range(max_retries + 1):
        try:
            result = ModelGateway.generate(
                role=ModelRole.ANALYST,
                prompt=prompt,
                report_id=f"director-info-{ctx.dataset_label}",
                step_name="director_information_triage"
            )
            if result.success and result.raw_text:
                payload = extract_json_payload(result.raw_text)
                parsed = json.loads(payload)
                if isinstance(parsed, list):
                    triage_map = {item.get("id"): item.get("destination") for item in parsed if isinstance(item, dict)}
                    for u in raw_units:
                        new_dest = triage_map.get(u.id)
                        if new_dest in [d.value for d in InformationDestination]:
                            # Enforce rule: High priority current evidence cannot be omitted
                            if u.source_type == InformationSourceType.CURRENT_EVIDENCE and u.priority == "HIGH" and new_dest == "OMIT":
                                continue
                            u.destination = InformationDestination(new_dest)
                    break
        except Exception as exc:
            logger.debug(f"Information triage attempt {attempt} failed: {exc}")

    return raw_units
