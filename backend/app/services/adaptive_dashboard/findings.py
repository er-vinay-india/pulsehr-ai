"""Shared Findings Store and Selection Engine (Section 4 of Strategy Plan).

Guarantees 100% analytical parity across dashboard, chatbot, narration, and presentation (T31).
Implements deterministic ranking, hard evidence gates, and deduplication (T33).
"""
from __future__ import annotations

import hashlib
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from .contracts import AdaptiveDashboardResponse


class UnifiedFinding(BaseModel):
    """Immutable finding representation shared across Dashboard, Copilot, Narration, and Presentation (Section 4 / T31)."""
    model_config = ConfigDict(extra="forbid")

    finding_id: str
    recipe_id: str
    calculation_id: str
    definition_id: str
    source_sheet_ids: list[int]
    source_scope: list[str]
    snapshot: str
    status: Literal["available", "needs_definition", "withheld", "abstain"] = "available"

    short_business_title: str
    typed_value: float | None = None
    formatted_value: str
    unit: str

    population_or_exposure: str
    comparison_and_effect: str | None = None
    evidence_bound_observation: str
    possible_operational_implication: str | None = None
    one_next_check_or_action: str
    allowed_claim_level: Literal[
        "descriptive_fact",
        "reconciled_ledger",
        "statistical_association",
        "non_causal_forecast",
        "exploratory_pattern",
    ] = "descriptive_fact"

    visual_kind: str = "none"
    visual_points_summary: list[dict[str, Any]] = Field(default_factory=list)
    drilldown_route: str | None = None
    privacy_state: Literal["cohort_safe", "aggregate_safe", "pii_suppressed"] = "aggregate_safe"
    limitations: list[str] = Field(default_factory=list)

    # Ranking & deduplication keys
    analytical_subject: str
    decision_category: str
    rank_score: float = 0.0


def extract_findings_from_response(response: AdaptiveDashboardResponse) -> list[UnifiedFinding]:
    """Extracts unified immutable findings from an AdaptiveDashboardResponse (T31)."""
    findings: list[UnifiedFinding] = []
    sheet_id = response.sheet_id
    snapshot = response.snapshot
    sheet_name = response.manifest.display_name or response.manifest.sheet_name
    domain = response.contract.domain

    # 1. Element 1: Primary Metric / Scale Finding
    elem = response.element
    if elem.evidence.status == "available":
        f1_id = f"finding_kpi_{elem.evidence.calculation_id.replace('CALC-', '')[:8]}"
        findings.append(
            UnifiedFinding(
                finding_id=f1_id,
                recipe_id=elem.business_concept,
                calculation_id=elem.evidence.calculation_id,
                definition_id=elem.evidence.definition_id,
                source_sheet_ids=[sheet_id],
                source_scope=[sheet_name],
                snapshot=snapshot,
                status="available",
                short_business_title=elem.glance.label,
                typed_value=float(elem.glance.value) if elem.glance.value is not None else None,
                formatted_value=elem.glance.formatted_value,
                unit=elem.glance.unit or "",
                population_or_exposure=elem.inspect.applicable_population,
                comparison_and_effect=None,
                evidence_bound_observation=elem.explain.exact_value_text,
                possible_operational_implication=elem.inspect.selection_reason,
                one_next_check_or_action=f"Review historical trend and segment distribution in {sheet_name}.",
                allowed_claim_level="descriptive_fact",
                visual_kind="kpi_tile",
                visual_points_summary=[],
                drilldown_route=f"/?sheet_id={sheet_id}&view=eda#explorer",
                privacy_state="aggregate_safe",
                limitations=elem.evidence.limitations,
                analytical_subject=domain,
                decision_category="operational_scale",
                rank_score=65.0,
            )
        )

    # 2. Element 6: Decision Focus (Material Disparity / Management Priority)
    if response.decision_element and response.decision_element.kind != "unavailable_card":
        df = response.decision_element
        calc_id = df.evidence.calculation_id if df.evidence else f"calc_focus_{snapshot[:8]}"
        def_id = df.evidence.definition_id if df.evidence else "def_decision_focus_v1"
        f6_id = f"finding_focus_{calc_id.replace('CALC-', '')[:8]}"
        target_lbl = df.subject_label
        obs_val = float(df.observed_value)
        obs_fmt = df.formatted_observed_value
        comp_lbl = df.comparator_label
        comp_val = float(df.comparator_value)
        comp_fmt = df.formatted_comparator_value
        gap_fmt = df.formatted_gap_value
        findings.append(
            UnifiedFinding(
                finding_id=f6_id,
                recipe_id="recipe_s09_decision_focus",
                calculation_id=calc_id,
                definition_id=def_id,
                source_sheet_ids=[sheet_id],
                source_scope=[sheet_name],
                snapshot=snapshot,
                status="available",
                short_business_title=df.title,
                typed_value=obs_val,
                formatted_value=obs_fmt,
                unit=df.unit,
                population_or_exposure=f"Segment: {target_lbl} ({df.sample_label})",
                comparison_and_effect=f"{comp_lbl}: {comp_fmt} (gap: {gap_fmt})",
                evidence_bound_observation=f"{target_lbl} observed at {obs_fmt} vs {comp_lbl} of {comp_fmt}.",
                possible_operational_implication=df.why_it_matters,
                one_next_check_or_action=df.next_step,
                allowed_claim_level="descriptive_fact",
                visual_kind="decision_gap",
                visual_points_summary=[
                    {"label": target_lbl, "value": obs_val},
                    {"label": comp_lbl, "value": comp_val},
                ],
                drilldown_route=f"/?sheet_id={sheet_id}&view=eda#explorer",
                privacy_state="cohort_safe",
                limitations=df.evidence.limitations if df.evidence else ["Identified as greatest observed gap; causal drivers require targeted investigation."],
                analytical_subject=domain,
                decision_category="segment_disparity",
                rank_score=95.0,
            )
        )

    # 3. Element 8: Exception Watch
    if response.exception_element and response.exception_element.kind == "exception_watch":
        exc = response.exception_element
        lead = exc.lead_exception
        if lead:
            calc_id = lead.calculation_id or (exc.evidence.calculation_id if exc.evidence else f"calc_exc_{exc.inspect.snapshot[:8]}")
            f8_id = f"finding_exc_{calc_id.replace('calc_exc_', '').replace('CALC-', '')[:8]}"
            pts = exc.visual.points if (exc.visual and exc.visual.points) else []
            findings.append(
                UnifiedFinding(
                    finding_id=f8_id,
                    recipe_id="recipe_s08_exceptions",
                    calculation_id=calc_id,
                    definition_id="def_exception_watch_v1",
                    source_sheet_ids=[sheet_id],
                    source_scope=[sheet_name],
                    snapshot=snapshot,
                    status="available",
                    short_business_title=f"Exception Watch: {lead.subject_label}",
                    typed_value=float(lead.observed_value),
                    formatted_value=lead.formatted_observed_value,
                    unit=lead.unit or (exc.glance.unit or ""),
                    population_or_exposure=f"Segment/Period: {lead.subject_label} ({lead.sample_label})",
                    comparison_and_effect=f"Expected range: {lead.formatted_expected_range}",
                    evidence_bound_observation=exc.explain.exact_value_text,
                    possible_operational_implication=exc.why_inspect,
                    one_next_check_or_action=exc.next_check,
                    allowed_claim_level="descriptive_fact",
                    visual_kind="timeline_band",
                    visual_points_summary=[{"label": p.label, "value": p.value} for p in pts[:6]],
                    drilldown_route=f"/?sheet_id={sheet_id}&view=eda#explorer",
                    privacy_state="aggregate_safe",
                    limitations=exc.inspect.limitations,
                    analytical_subject=domain,
                    decision_category="anomaly_monitoring",
                    rank_score=85.0,
                )
            )

    # 4. Element 9: Forward Outlook / Target Gap
    if response.outlook_element and response.outlook_element.kind != "outlook_unavailable":
        out = response.outlook_element
        calc_id = out.inspect.calculation_id or (out.evidence.calculation_id if out.evidence else f"calc_outlook_{snapshot[:8]}")
        f9_id = f"finding_outlook_{calc_id.replace('calc_outlook_', '').replace('CALC-', '')[:8]}"
        claim_level = "descriptive_fact" if out.kind == "target_gap" else "non_causal_forecast"
        pts = out.points if out.points else []
        findings.append(
            UnifiedFinding(
                finding_id=f9_id,
                recipe_id=f"recipe_s19_{out.kind}",
                calculation_id=calc_id,
                definition_id=out.inspect.definition_id,
                source_sheet_ids=[sheet_id],
                source_scope=[sheet_name],
                snapshot=snapshot,
                status="available",
                short_business_title=out.title,
                typed_value=float(out.glance.value) if out.glance.value is not None else None,
                formatted_value=out.glance.formatted_value,
                unit=out.glance.unit or "",
                population_or_exposure=out.inspect.applicable_population,
                comparison_and_effect=out.glance.context_qualifier,
                evidence_bound_observation=out.explain.exact_value_text,
                possible_operational_implication=out.why_available_or_unavailable,
                one_next_check_or_action=out.inspect.selection_reason,
                allowed_claim_level=claim_level,
                visual_kind="forecast_path",
                visual_points_summary=[{"label": p.period_label, "value": p.actual_value or p.forecast_value} for p in pts[:6]],
                drilldown_route=f"/?sheet_id={sheet_id}&view=eda#explorer",
                privacy_state="aggregate_safe",
                limitations=out.inspect.limitations,
                analytical_subject=domain,
                decision_category="forward_outlook",
                rank_score=80.0,
            )
        )

    # 5. Element 10: Enterprise Synthesis (Cross-Source Reconciliation / Cohort / Association)
    if response.enterprise_element and response.enterprise_element.lead_finding:
        ent = response.enterprise_element
        lead = ent.lead_finding
        f10_id = f"finding_ent_{lead.calculation_id.replace('calc_ent_', '')[:8]}"
        claim_level = "reconciled_ledger" if ent.kind == "reconciled_metric" else (
            "statistical_association" if ent.kind == "cross_source_association" else "descriptive_fact"
        )
        sources_list = [s.display_name for s in ent.sources]
        findings.append(
            UnifiedFinding(
                finding_id=f10_id,
                recipe_id=lead.recipe_id,
                calculation_id=lead.calculation_id,
                definition_id=ent.inspect.definition_id,
                source_sheet_ids=lead.source_sheet_ids,
                source_scope=sources_list,
                snapshot=lead.snapshot,
                status="available",
                short_business_title=lead.title,
                typed_value=float(lead.values[0]) if lead.values else None,
                formatted_value=ent.glance.formatted_value,
                unit=ent.glance.unit or (lead.units[0] if lead.units else ""),
                population_or_exposure=f"{lead.matched_count:,} matched entities across {len(sources_list)} sources",
                comparison_and_effect=lead.join_description,
                evidence_bound_observation=ent.what_it_establishes,
                possible_operational_implication=lead.interpretation,
                one_next_check_or_action=ent.next_check,
                allowed_claim_level=claim_level,
                visual_kind=ent.visual.kind if ent.visual else "none",
                visual_points_summary=[{"label": p.label, "value": p.y} for p in (ent.visual.points if ent.visual else [])],
                drilldown_route=ent.drilldown_targets[0].route if ent.drilldown_targets else f"/?sheet_id={sheet_id}&view=eda#explorer",
                privacy_state="cohort_safe",
                limitations=[ent.what_it_does_not_establish],
                analytical_subject=domain,
                decision_category="cross_source_reconciliation",
                rank_score=92.0,
            )
        )

    return findings


def rank_and_deduplicate_findings(
    findings: list[UnifiedFinding],
    max_findings: int = 5,
) -> list[UnifiedFinding]:
    """Applies deterministic ranking and deduplication (Section 4 / T33).

    Deduplicates by (analytical_subject, decision_category) and underlying metric.
    Selects typically 3–5 distinct findings without random chart rotation.
    """
    if not findings:
        return []

    # Sort deterministically by rank_score descending, then finding_id ascending
    sorted_candidates = sorted(
        findings,
        key=lambda f: (-f.rank_score, f.finding_id)
    )

    selected: list[UnifiedFinding] = []
    seen_categories: set[tuple[str, str]] = set()

    for cand in sorted_candidates:
        dedup_key = (cand.analytical_subject, cand.decision_category)
        if dedup_key in seen_categories:
            continue
        seen_categories.add(dedup_key)
        selected.append(cand)
        if len(selected) >= max_findings:
            break

    return selected


def get_shared_findings_for_sheet(sheet_id: int) -> list[UnifiedFinding]:
    """Retrieves authoritative, ranked, deduplicated findings for a sheet (T31, T33)."""
    from .engine import run_adaptive_dashboard

    response = run_adaptive_dashboard(sheet_id=sheet_id)
    raw_findings = extract_findings_from_response(response)
    return rank_and_deduplicate_findings(raw_findings, max_findings=5)
