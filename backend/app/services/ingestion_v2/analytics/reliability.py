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
    # Optional direct calibration parameters for explicit benchmark fixtures
    grain_confidence_override: float | None = None,
    relationship_confidence_override: float | None = None,
    join_plan_confidence_override: float | None = None,
    source_coverage_override: float | None = None,
    metric_definition_override: float | None = None,
    sample_sufficiency_override: float | None = None,
    missingness_support_override: float | None = None,
) -> AnalyticalReliability:
    """
    Compute structured AnalyticalReliability score and level.

    Component Scores:
    - grain_confidence: Grain confidence across tables
    - relationship_confidence: Status of candidate relationship edges
    - join_plan_confidence: Authorized vs rejected join plans
    - source_coverage: Fraction of source tables / entities covered safely
    - metric_definition_confidence: Explicitness of metric definitions
    - sample_sufficiency: Sample size sufficiency
    - missingness_support: Completeness factor (1.0 - missingness)
    - statistical_support: Combined power of findings and sample sizes
    """
    # 1. Grain confidence
    if grain_confidence_override is not None:
        grain_conf = grain_confidence_override
    elif grain_profile and (getattr(grain_profile, "table_grains", None) or getattr(grain_profile, "tables", [])):
        tg_list = getattr(grain_profile, "table_grains", None) or getattr(grain_profile, "tables", [])
        grain_conf = sum(t.grain_confidence for t in tg_list) / max(1, len(tg_list))
    else:
        grain_conf = 0.85

    # 2. Relationship confidence
    if relationship_confidence_override is not None:
        rel_conf = relationship_confidence_override
    elif relationship_graph and len(relationship_graph.edges) > 0:
        accepted_count = sum(1 for e in relationship_graph.edges if getattr(e.status, "value", str(e.status)) == "ACCEPTED")
        rel_conf = accepted_count / len(relationship_graph.edges)
    else:
        rel_conf = 1.0

    # 3. Join plan confidence & coverage
    if join_plan_confidence_override is not None:
        join_plan_conf = join_plan_confidence_override
    elif join_plans and len(join_plans) > 0:
        safe_count = sum(
            1 for jp in join_plans
            if getattr(jp.safety_status, "value", str(jp.safety_status)) in ("SAFE", "SAFE_WITH_PREAGGREGATION")
        )
        join_plan_conf = safe_count / len(join_plans)
    else:
        join_plan_conf = 1.0

    # 4. Source coverage
    if source_coverage_override is not None:
        source_cov = source_coverage_override
    else:
        source_cov = min(rel_conf, join_plan_conf)

    # 5. Metric definition confidence
    metric_def_conf = metric_definition_override if metric_definition_override is not None else 0.95

    # 6. Sample sufficiency
    if sample_sufficiency_override is not None:
        sample_suff = sample_sufficiency_override
    elif min_sample_size < 5:
        sample_suff = 0.35
    elif has_small_sample_groups:
        sample_suff = 0.70
    elif min_sample_size < 20:
        sample_suff = 0.85
    else:
        sample_suff = 0.98

    # 7. Missingness support
    if missingness_support_override is not None:
        missingness_factor = missingness_support_override
    else:
        missingness_factor = max(0.0, 1.0 - missingness_ratio)

    # 8. Evidence & Statistical sufficiency
    evid_suff = min(1.0, 0.40 + (0.05 * min(12, findings_count)))
    stat_support = round(min(1.0, sample_suff * evid_suff), 3)

    # Overall weighted score
    overall = (
        (0.20 * grain_conf) +
        (0.15 * rel_conf) +
        (0.15 * join_plan_conf) +
        (0.10 * source_cov) +
        (0.10 * metric_def_conf) +
        (0.15 * sample_suff) +
        (0.15 * missingness_factor)
    )
    overall = round(max(0.0, min(1.0, overall)), 3)

    # Reliability level
    if overall >= 0.80 and sample_suff >= 0.70 and join_plan_conf >= 0.75:
        level = "HIGH"
    elif overall >= 0.50:
        level = "MEDIUM"
    else:
        level = "LOW"

    rationale_parts = []
    if grain_conf < 0.80:
        rationale_parts.append("Low grain confidence")
    if join_plan_conf < 0.80:
        rationale_parts.append("Partial join coverage or unsafe join plans")
    if sample_suff < 0.70:
        rationale_parts.append("Small sample size or tiny groups present")
    if missingness_factor < 0.80:
        rationale_parts.append("Elevated missingness")
    if metric_def_conf < 0.80:
        rationale_parts.append("Ambiguous metric definitions")

    rationale = "; ".join(rationale_parts) if rationale_parts else "Strong grain, join safety, and sample support"

    return AnalyticalReliability(
        grain_confidence_score=round(grain_conf, 3),
        relationship_confidence_score=round(rel_conf, 3),
        join_plan_confidence_score=round(join_plan_conf, 3),
        join_coverage_score=round(join_plan_conf, 3),
        source_coverage_score=round(source_cov, 3),
        metric_definition_confidence=round(metric_def_conf, 3),
        sample_sufficiency_score=round(sample_suff, 3),
        missingness_support_score=round(missingness_factor, 3),
        evidence_sufficiency_score=round(evid_suff, 3),
        statistical_support_score=stat_support,
        overall_analytical_reliability=overall,
        reliability_level=level,
        rationale=rationale,
    )
