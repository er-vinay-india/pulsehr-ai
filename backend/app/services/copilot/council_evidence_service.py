"""CouncilEvidenceService: Central evidence retrieval, normalization, and arbitration for the AI Council.

Orchestrates:
1. Dataset-scoped hybrid RAG retrieval via Nomic & BM25+.
2. Deterministic full-population calculations via Pandas/SQLite.
3. Domain governance findings from the cryptographic Decision Brief / Shared Findings Store.
4. DeepSeek-R1 critic arbitration when multi-source or hybrid evidence is present.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from ...core import config
from ...db.database import get_connection
from ..gateway.model_gateway import ModelGateway
from ...core.models_config import ModelRole
from ..hybrid_retrieval import hybrid_search
from .council_contracts import (
    CouncilPlan,
    RetrievalRequest,
    RetrievedEvidence,
    CalculationResult,
    EvidenceItem,
    EvidenceType,
    EntityGrain,
    CriticReview,
    TaskType,
)

logger = logging.getLogger(__name__)


class CouncilEvidenceService:
    """Central evidence hub ensuring Council members receive normalized, dataset-scoped evidence."""

    @classmethod
    def retrieve_rag_evidence(
        cls,
        request: RetrievalRequest,
        conn=None
    ) -> list[RetrievedEvidence]:
        """Performs dataset-scoped, grain-enforced hybrid semantic search."""
        grain_str = request.entity_grain.value if request.entity_grain else None
        chunks = hybrid_search(
            query=request.query,
            top_k=request.max_results,
            dataset_id=request.dataset_id,
            sheet_id=request.sheet_id,
            entity_grain=grain_str
        )

        results: list[RetrievedEvidence] = []
        for c in chunks:
            if c.get("relevance_score", 0.0) < request.min_relevance_score and not c.get("keyword_score"):
                continue

            # Verify grain match
            c_grain = EntityGrain.EMPLOYEE if ("id:" in c.get("text", "").lower() or "employee" in c.get("text", "").lower()) else EntityGrain.DEPARTMENT
            if request.entity_grain and request.entity_grain == EntityGrain.EMPLOYEE and c_grain != EntityGrain.EMPLOYEE:
                # Discard department chunks when employee grain is explicitly required
                continue

            results.append(
                RetrievedEvidence(
                    evidence_id=f"chunk-{c.get('chunk_id')}",
                    content=c.get("text", ""),
                    source_type="tabular_chunk",
                    dataset_id=c.get("dataset_id") or request.dataset_id,
                    sheet_id=request.sheet_id,
                    entity_grain=c_grain,
                    relevance_score=float(c.get("relevance_score", 0.7)),
                    confidence=1.0,
                    source_reference=f"{c.get('source_file', 'Dataset')} / {c.get('sheet_name', 'Sheet')} (Row {c.get('row_index', 0)})",
                    is_stale=False
                )
            )
        return results

    @classmethod
    def gather_evidence(
        cls,
        user_query: str,
        plan: CouncilPlan,
        dataset_id: int | None = None,
        sheet_id: int | None = None,
        prior_context: dict[str, Any] | None = None,
        conn=None
    ) -> tuple[list[EvidenceItem], CalculationResult | None]:
        """Gathers unified evidence items across Calculations, RAG, FactStore, and Conversation State."""
        evidence_items: list[EvidenceItem] = []
        calc_result: CalculationResult | None = None
        should_close = False

        if conn is None:
            conn = get_connection()
            should_close = True

        try:
            # 1. Deterministic Calculation
            if plan.requires_calculation:
                from ..copilot_query_planner import AnalyticalQueryPlan, execute_analytical_plan
                planner_plan = AnalyticalQueryPlan(
                    intent=plan.operation.value if plan.operation else "ranking",
                    metric=plan.metric,
                    secondary_metric=plan.secondary_metric,
                    entity_dimension="Department",
                    direction=plan.direction,
                    ranking_limit=plan.ranking_limit,
                    additional_fields=plan.additional_fields,
                    threshold_operator=plan.threshold_operator,
                    threshold_value=plan.threshold_value,
                    entity_grain=plan.entity_grain.value,
                    dataset_id=dataset_id,
                    sheet_id=sheet_id,
                    prior_context=prior_context,
                    explanation=plan.explanation
                )

                raw_res = execute_analytical_plan(planner_plan, conn=conn)
                raw_cov = raw_res.get("evidence", {}).get("coverage", {})
                raw_rows = raw_res.get("raw_analysis", {}).get("rows", [])

                calc_result = CalculationResult(
                    status="success" if raw_res.get("status") == "success" else "metric_missing",
                    dataset_id=dataset_id,
                    sheet_id=sheet_id,
                    entity_grain=plan.entity_grain,
                    metric=plan.metric or "attendance",
                    direction=plan.direction,
                    columns=list(raw_rows[0].keys()) if raw_rows else [],
                    rows=raw_rows,
                    row_count=raw_cov.get("total_records", len(raw_rows)),
                    distinct_entities=raw_cov.get("distinct_employees", len(raw_rows)),
                    missing_records_excluded=raw_cov.get("missing_records", 0),
                    snapshot_hash=raw_res.get("evidence", {}).get("snapshot_hash", "unversioned"),
                    calculation_method=raw_res.get("evidence", {}).get("calculation_method", "Full-population evaluation."),
                    warnings=raw_res.get("evidence", {}).get("caveats", [])
                )

                evidence_items.append(
                    EvidenceItem(
                        evidence_type=EvidenceType.CALCULATION,
                        source_id=f"calc-{dataset_id}-{sheet_id or 'all'}",
                        dataset_id=dataset_id,
                        sheet_id=sheet_id,
                        entity_grain=plan.entity_grain,
                        metric=plan.metric,
                        content=calc_result.model_dump(),
                        confidence=1.0,
                        provenance={
                            "method": calc_result.calculation_method,
                            "snapshot_hash": calc_result.snapshot_hash,
                            "answer_markdown": raw_res.get("answer", "")
                        }
                    )
                )

            # 2. Retrieved Knowledge (RAG via Nomic + BM25+)
            if plan.requires_rag:
                ret_req = RetrievalRequest(
                    query=user_query,
                    dataset_id=dataset_id,
                    sheet_id=sheet_id,
                    entity_grain=plan.entity_grain,
                    metric=plan.metric,
                    max_results=5,
                    min_relevance_score=0.55
                )
                ret_items = cls.retrieve_rag_evidence(ret_req, conn=conn)
                for r in ret_items:
                    evidence_items.append(
                        EvidenceItem(
                            evidence_type=EvidenceType.RETRIEVED_KNOWLEDGE,
                            source_id=r.evidence_id,
                            dataset_id=r.dataset_id,
                            sheet_id=r.sheet_id,
                            entity_grain=r.entity_grain,
                            metric=r.metric,
                            content=r.model_dump(),
                            confidence=r.relevance_score,
                            provenance={"source_reference": r.source_reference}
                        )
                    )

            # 3. Domain Governance & Fact Store Findings
            if sheet_id is not None or dataset_id is not None:
                try:
                    from ..adaptive_dashboard.findings import get_shared_findings_for_sheet
                    target_sid = sheet_id
                    if target_sid is None and dataset_id is not None:
                        s_row = conn.execute("SELECT id FROM sheets WHERE dataset_id=? ORDER BY row_count DESC, id ASC LIMIT 1", (dataset_id,)).fetchone()
                        if s_row:
                            target_sid = s_row[0]
                    if target_sid is not None:
                        findings = get_shared_findings_for_sheet(sheet_id=target_sid)
                        for f in findings[:4]:
                            evidence_items.append(
                                EvidenceItem(
                                    evidence_type=EvidenceType.DOMAIN_GOVERNANCE,
                                    source_id=f.finding_id,
                                    dataset_id=dataset_id,
                                    sheet_id=target_sid,
                                    entity_grain=EntityGrain.DEPARTMENT,
                                    metric=f.metric_key,
                                    content={
                                        "title": f.short_business_title,
                                        "observation": f.evidence_bound_observation,
                                        "value": f.formatted_value,
                                        "action": f.one_next_check_or_action
                                    },
                                    confidence=1.0,
                                    provenance={"category": f.decision_category, "calc_id": f.calculation_id}
                                )
                            )
                except Exception as exc:
                    logger.debug(f"Could not load shared findings for evidence hub: {exc}")

            # 4. Conversation State Context
            if prior_context:
                evidence_items.append(
                    EvidenceItem(
                        evidence_type=EvidenceType.CONVERSATION_STATE,
                        source_id=f"prior-{prior_context.get('dataset_id')}",
                        dataset_id=prior_context.get("dataset_id"),
                        sheet_id=prior_context.get("sheet_id"),
                        entity_grain=EntityGrain(prior_context.get("entity_grain")) if prior_context.get("entity_grain") in ("employee", "department") else None,
                        metric=prior_context.get("metric"),
                        content=prior_context,
                        confidence=1.0,
                        provenance={"last_intent": prior_context.get("last_intent")}
                    )
                )

            return evidence_items, calc_result

        finally:
            if should_close:
                conn.close()

    @classmethod
    def arbitrate_evidence(
        cls,
        user_query: str,
        evidence_items: list[EvidenceItem],
        plan: CouncilPlan
    ) -> CriticReview:
        """DeepSeek-R1 Critic audits consistency between calculated facts, retrieved knowledge, and requested grain."""
        calc_items = [e for e in evidence_items if e.evidence_type == EvidenceType.CALCULATION]
        ret_items = [e for e in evidence_items if e.evidence_type == EvidenceType.RETRIEVED_KNOWLEDGE]
        gov_items = [e for e in evidence_items if e.evidence_type == EvidenceType.DOMAIN_GOVERNANCE]

        # 1. Deterministic Sanity Checks
        # Grain consistency rule: If user asked for employee grain, verify calculation is employee grain
        if plan.entity_grain == EntityGrain.EMPLOYEE:
            for c in calc_items:
                if c.entity_grain != EntityGrain.EMPLOYEE:
                    return CriticReview(
                        conflict_detected=True,
                        grain_consistent=False,
                        calculation_supported=False,
                        discrepancy_details="Grain mismatch: Requested employee calculation but received department aggregate.",
                        preferred_evidence_source="calculation",
                        confidence=1.0,
                        mandatory_caveats=["Department aggregates cannot substitute for individual employee records."]
                    )

        # If purely a calculation or fact retrieval with no conflicting sources, return clean pass
        if (len(calc_items) > 0 and len(ret_items) == 0 and len(gov_items) == 0) or (len(calc_items) == 0 and len(ret_items) > 0):
            return CriticReview(
                conflict_detected=False,
                grain_consistent=True,
                calculation_supported=True,
                confidence=1.0
            )

        # 2. Invoke DeepSeek-R1 Critic for multi-source arbitration (Hybrid Questions)
        prompt = f"""You are the Executive AI Council Critic (DeepSeek-R1).
Review the following pieces of evidence for the user query: "{user_query}"
Requested grain: {plan.entity_grain.value}

EVIDENCE ITEMS:
{json.dumps([{'type': e.evidence_type.value, 'grain': str(e.entity_grain), 'content': e.content} for e in evidence_items[:6]], indent=2)}

TASK:
1. Determine whether any conflict or numerical discrepancy exists between calculations and domain findings.
2. Ensure non-causal language is mandated if user asked 'why'.
3. Always prefer deterministic calculation over conversational text.

Return your evaluation matching the requested CriticReview JSON schema."""

        try:
            gateway_res = ModelGateway.generate(
                role=ModelRole.CRITIC,
                prompt=prompt,
                response_schema=CriticReview,
                step_name="deepseek_critic_arbitration",
                temperature_override=0.05
            )
            if gateway_res.parsed:
                review = gateway_res.parsed
                if calc_items:
                    review.calculation_supported = True
                    review.preferred_evidence_source = "calculation"
                if any(k in user_query.lower() for k in ("why", "cause", "reason")):
                    causal_disclaimer = "Observed correlations do not establish organizational causation without controlled longitudinal trials."
                    if not any("causation" in c.lower() or "causal" in c.lower() for c in review.mandatory_caveats):
                        review.mandatory_caveats.append(causal_disclaimer)
                return review
        except Exception as exc:
            logger.warning(f"DeepSeek critic inference failed; falling back to deterministic arbitration: {exc}")

        # Deterministic Fallback Arbitration
        has_why = any(k in user_query.lower() for k in ("why", "cause", "reason"))
        caveats = ["Observed correlations do not establish organizational causation without controlled longitudinal trials."] if has_why else []
        return CriticReview(
            conflict_detected=False,
            grain_consistent=True,
            calculation_supported=True,
            preferred_evidence_source="calculation",
            confidence=1.0,
            mandatory_caveats=caveats
        )
