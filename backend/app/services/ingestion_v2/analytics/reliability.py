"""
HighView Ingestion V2 — Analytical Reliability Model
Stage 8: Analytical EDA-B
Evaluates the inferential and evidentiary reliability of findings and profiles.
Strictly decoupled from StructuralDataQuality (EDA-A).
"""

from __future__ import annotations

from app.services.ingestion_v2.contracts.analytics import AnalyticalReliability
from app.services.ingestion_v2.contracts.grain import GrainProfile
from app.services.ingestion_v2.contracts.joins import JoinPlan
from app.services.ingestion_v2.contracts.relationships import ValidatedRelationshipGraph


def calculate_analytical_reliability(
    grain_profile: GrainProfile | None = None,
    relationship_graph: ValidatedRelationshipGraph | None = None,
    join_plans: list[JoinPlan] | None = None,
    findings_count: int = 0,
    min_sample_size: int = 10,
    has_small_sample_groups: bool = False,
    missingness_ratio: float = 0.0,
) -> AnalyticalReliability:
    """
    Compute structured AnalyticalReliability score and level.

    Weights:
    - Grain confidence: 0.30
    - Join coverage & safety: 0.25
    - Metric definition confidence: 0.15
    - Sample sufficiency: 0.20
    - Missingness / completeness: 0.10
    """
    # 1. Grain confidence
    if grain_profile and (getattr(grain_profile, "table_grains", None) or getattr(grain_profile, "tables", [])):
        tg_list = getattr(grain_profile, "table_grains", None) or getattr(grain_profile, "tables", [])
        grain_conf = sum(t.grain_confidence for t in tg_list) / max(1, len(tg_list))
    else:
        grain_conf = 0.85

    # 2. Join coverage & safety
    if join_plans and len(join_plans) > 0:
        safe_count = sum(1 for jp in join_plans if jp.safety_status.value in ("SAFE", "SAFE_WITH_PREAGGREGATION"))
        join_coverage = safe_count / len(join_plans)
    elif relationship_graph and len(relationship_graph.edges) > 0:
        accepted_count = sum(1 for e in relationship_graph.edges if e.status.value == "ACCEPTED")
        join_coverage = accepted_count / len(relationship_graph.edges)
    else:
        join_coverage = 1.0  # Single table dataset has perfect join coverage

    # 3. Metric definition confidence
    metric_def_conf = 0.95

    # 4. Sample sufficiency
    if min_sample_size < 5:
        sample_suff = 0.35
    elif has_small_sample_groups:
        sample_suff = 0.70
    elif min_sample_size < 20:
        sample_suff = 0.85
    else:
        sample_suff = 0.98

    # 5. Evidence sufficiency
    evid_suff = min(1.0, 0.40 + (0.05 * min(12, findings_count)))

    # Missingness penalty
    missingness_factor = max(0.0, 1.0 - missingness_ratio)

    # Overall weighted score
    overall = (
        (0.30 * grain_conf) +
        (0.25 * join_coverage) +
        (0.15 * metric_def_conf) +
        (0.20 * sample_suff) +
        (0.10 * missingness_factor)
    )
    overall = round(max(0.0, min(1.0, overall)), 3)

    # Reliability level
    if overall >= 0.80 and sample_suff >= 0.70 and join_coverage >= 0.80:
        level = "HIGH"
    elif overall >= 0.50:
        level = "MEDIUM"
    else:
        level = "LOW"

    rationale_parts = []
    if grain_conf < 0.80:
        rationale_parts.append("Low grain confidence")
    if join_coverage < 0.80:
        rationale_parts.append("Partial join coverage or unsafe join plans")
    if sample_suff < 0.70:
        rationale_parts.append("Small sample size or tiny groups present")
    if missingness_ratio > 0.20:
        rationale_parts.append("Elevated missingness")

    rationale = "; ".join(rationale_parts) if rationale_parts else "Strong grain, join safety, and sample support"

    return AnalyticalReliability(
        grain_confidence_score=round(grain_conf, 3),
        join_coverage_score=round(join_coverage, 3),
        metric_definition_confidence=round(metric_def_conf, 3),
        evidence_sufficiency_score=round(evid_suff, 3),
        overall_analytical_reliability=overall,
        reliability_level=level,
        sample_sufficiency_score=round(sample_suff, 3),
        statistical_support_score=round(min(1.0, sample_suff * evid_suff), 3),
        rationale=rationale,
    )
