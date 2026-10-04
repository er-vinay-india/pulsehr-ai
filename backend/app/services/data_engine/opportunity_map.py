"""Analysis Opportunity Map Engine for PulseHR AI.

Given an arbitrary SemanticDatasetProfile, identifies all mathematically and
statistically admissible analytical paths without executing them:
- Period Trend Analysis (Temporal × Measure)
- Segment Variance & Cohort Comparison (Categorical × Measure)
- Entity Concentration / Pareto Analysis (Entity × Measure)
- Bivariate Association & Correlation (Measure × Measure)
- Subgroup Rate Disparity (Dimension × Percentage Rate)
- Categorical Cross-Tabulation (Dimension × Dimension)
- Target Association & Outcome Risk (Target × Measure / Dimension)
"""

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

from .semantic_classifier import SemanticDatasetProfile, SemanticRole


class OpportunityType(str, Enum):
    PERIOD_TREND = "period_trend"                     # DateTime + Measure
    SEGMENT_COMPARISON = "segment_comparison"         # Dimension + Measure
    ENTITY_CONCENTRATION = "entity_concentration"     # High-cardinality entity + Measure (Pareto)
    MEASURE_RELATIONSHIP = "measure_relationship"     # Measure + Measure (Correlation / Tradeoff)
    SUBGROUP_RATE_DISPARITY = "subgroup_rate"         # Dimension + Percentage Rate
    CATEGORICAL_CROSS_TAB = "categorical_cross_tab"   # Dimension + Dimension
    TARGET_ASSOCIATION = "target_association"         # Possible Target + Dimension / Measure
    TARGET_COMPLIANCE = "target_compliance"           # Explicit Business Rule / Threshold Compliance
    MULTI_FACTOR_SEGMENT_DISPARITY = "multi_factor_segment_disparity"  # Dimension A × Dimension B × Measure


class AnalysisOpportunity(BaseModel):
    """A single admissible analytical pathway."""
    opportunity_id: str
    opportunity_type: OpportunityType
    primary_column: str
    secondary_column: str | None = None
    title: str
    rationale: str
    mathematical_method: str
    feasibility_score: float = 1.0  # 0.0 to 1.0 based on null rates, cardinality, and signal quality
    is_user_priority: bool = False
    priority_reason: str | None = None
    priority_question: str | None = None
    target_rule: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def type(self) -> OpportunityType:
        return self.opportunity_type


class AnalysisOpportunityMap(BaseModel):
    """Complete collection of admissible analytical opportunities for a dataset."""
    dataset_name: str
    total_opportunities: int
    by_type_count: dict[str, int] = Field(default_factory=dict)
    opportunities: list[AnalysisOpportunity] = Field(default_factory=list)


def _clean_name(name: str | None) -> str:
    """Sanitizes raw column names and tokens into clean business English."""
    if not name:
        return ""
    s = str(name).strip()
    for prefix in [
        "interact_mean_", "interact_ratio_", "interact_sum_", "interact_count_", "interact_",
        "mean_", "sum_", "ratio_", "log_", "std_", "diff_", "pct_"
    ]:
        if s.lower().startswith(prefix):
            s = s[len(prefix):]
    s = s.replace("_", " ").strip()
    acronyms = {"hr", "fte", "kpi", "id", "us", "uk", "cpi", "ols", "usd", "eur", "gbp", "inr", "roi", "ai", "qa"}
    words = s.split()
    capitalized = []
    for idx, w in enumerate(words):
        lower = w.lower()
        if lower in acronyms:
            capitalized.append(lower.upper())
        elif idx > 0 and lower in {"by", "vs", "and", "of", "in", "on", "at", "to", "for", "with", "over", "across"}:
            capitalized.append(lower)
        else:
            capitalized.append(w.capitalize())
    return " ".join(capitalized)


class OpportunityMapGenerator:
    """Discovers mathematically viable analytical paths from a SemanticDatasetProfile."""

    @classmethod
    def generate(
        cls,
        profile: SemanticDatasetProfile,
        max_opportunities: int = 25,
        context: Any | None = None
    ) -> AnalysisOpportunityMap:
        opportunities: list[AnalysisOpportunity] = []
        opp_idx = 1

        dates = profile.temporal_dimensions
        measures = list(set(profile.numeric_measures + profile.monetary_measures + profile.percentage_rates))
        categories = profile.categorical_dimensions
        rates = profile.percentage_rates
        targets = profile.possible_targets or profile.boolean_flags
        identifiers = profile.identifiers

        # 0. User-Explicit Business Rule Compliance Opportunities
        if context and getattr(context, "business_rules", None):
            for rule in context.business_rules:
                dims = getattr(context, "important_dimensions", []) or categories[:2]
                for dim in dims[:2]:
                    clean_dim = _clean_name(dim)
                    opportunities.append(AnalysisOpportunity(
                        opportunity_id=f"OPP-{opp_idx:03d}",
                        opportunity_type=OpportunityType.TARGET_COMPLIANCE,
                        primary_column=dim,
                        secondary_column=rule.metric,
                        title=f"Target Compliance: {clean_dim} adherence to {rule.description or (rule.metric + ' ' + rule.operator + ' ' + str(rule.threshold))}",
                        rationale=f"Evaluates compliance percentage against explicit user business rule ({rule.source}).",
                        mathematical_method="threshold_compliance_rate_by_group",
                        feasibility_score=1.0,
                        is_user_priority=True,
                        priority_reason=f"Directly addresses user rule '{rule.metric} {rule.operator} {rule.threshold}'",
                        target_rule=rule.model_dump()
                    ))
                    opp_idx += 1

        # 1. Period Trend Opportunities (Date x Measure)
        for dt_col in dates[:2]:
            for m_col in measures[:4]:
                p_col = profile.columns.get(m_col)
                feasibility = 1.0 - ((profile.columns.get(dt_col).null_percentage if dt_col in profile.columns else 0) / 100.0)
                m_label = _clean_name(p_col.display_name if p_col and p_col.display_name else m_col)
                dt_label = _clean_name(dt_col)
                opportunities.append(AnalysisOpportunity(
                    opportunity_id=f"OPP-{opp_idx:03d}",
                    opportunity_type=OpportunityType.PERIOD_TREND,
                    primary_column=dt_col,
                    secondary_column=m_col,
                    title=f"Chronological Trend Analysis: {m_label} over {dt_label}",
                    rationale=f"Evaluates trajectory, momentum, and period-over-period changes in {m_label}.",
                    mathematical_method="temporal_aggregation_and_slope",
                    feasibility_score=round(max(0.2, feasibility), 2)
                ))
                opp_idx += 1

        # 2. Segment Comparison Opportunities (Dimension x Measure)
        for dim_col in categories[:3]:
            dim_prof = profile.columns.get(dim_col)
            card = dim_prof.unique_count if dim_prof else 5
            if 2 <= card <= 40:
                for m_col in measures[:4]:
                    m_prof = profile.columns.get(m_col)
                    m_label = _clean_name(m_prof.display_name if m_prof and m_prof.display_name else m_col)
                    dim_label = _clean_name(dim_prof.display_name if dim_prof and dim_prof.display_name else dim_col)
                    opportunities.append(AnalysisOpportunity(
                        opportunity_id=f"OPP-{opp_idx:03d}",
                        opportunity_type=OpportunityType.SEGMENT_COMPARISON,
                        primary_column=dim_col,
                        secondary_column=m_col,
                        title=f"Segment Comparison: {m_label} across {dim_label}",
                        rationale=f"Discovers cohort disparities and identifies outperformer vs underperformer segments.",
                        mathematical_method="group_distribution_and_variance",
                        feasibility_score=0.95
                    ))
                    opp_idx += 1

        # 3. Subgroup Rate Disparity (Dimension x Percentage Rate)
        for dim_col in categories[:2]:
            for r_col in rates[:2]:
                r_prof = profile.columns.get(r_col)
                r_label = _clean_name(r_prof.display_name if r_prof and r_prof.display_name else r_col)
                dim_label = _clean_name(dim_col)
                opportunities.append(AnalysisOpportunity(
                    opportunity_id=f"OPP-{opp_idx:03d}",
                    opportunity_type=OpportunityType.SUBGROUP_RATE_DISPARITY,
                    primary_column=dim_col,
                    secondary_column=r_col,
                    title=f"Rate Disparity Analysis: {r_label} by {dim_label}",
                    rationale=f"Audits percentage spread and structural divergence across groups for {r_label}.",
                    mathematical_method="proportional_variance_and_effect_size",
                    feasibility_score=0.90
                ))
                opp_idx += 1

        # 4. Measure Relationship & Tradeoff (Measure x Measure)
        if len(measures) >= 2:
            for i in range(min(3, len(measures))):
                for j in range(i + 1, min(4, len(measures))):
                    m1, m2 = measures[i], measures[j]
                    clean_m1 = _clean_name(m1)
                    clean_m2 = _clean_name(m2)
                    opportunities.append(AnalysisOpportunity(
                        opportunity_id=f"OPP-{opp_idx:03d}",
                        opportunity_type=OpportunityType.MEASURE_RELATIONSHIP,
                        primary_column=m1,
                        secondary_column=m2,
                        title=f"Bivariate Association: {clean_m1} vs {clean_m2}",
                        rationale=f"Tests statistical correlation, trade-offs, and empirical dependency between {clean_m1} and {clean_m2}.",
                        mathematical_method="pearson_spearman_correlation_matrix",
                        feasibility_score=0.85
                    ))
                    opp_idx += 1

        # 5. Entity Concentration / Pareto Analysis (Identifier/High-Card Dimension x Volume/Money Measure)
        high_card_entities = [c for c in (identifiers + categories) if profile.columns.get(c) and profile.columns[c].unique_count > 15]
        vol_measures = profile.monetary_measures or measures[:2]
        if high_card_entities and vol_measures:
            ent = high_card_entities[0]
            meas = vol_measures[0]
            clean_meas = _clean_name(meas)
            clean_ent = _clean_name(ent)
            opportunities.append(AnalysisOpportunity(
                opportunity_id=f"OPP-{opp_idx:03d}",
                opportunity_type=OpportunityType.ENTITY_CONCENTRATION,
                primary_column=ent,
                secondary_column=meas,
                title=f"Concentration & Pareto Analysis: {clean_meas} by {clean_ent}",
                rationale=f"Determines whether the top 20% of {clean_ent} entities drive the majority of {clean_meas}.",
                mathematical_method="cumulative_sum_and_gini_coefficient",
                feasibility_score=0.90
            ))
            opp_idx += 1

        # 6. Target Association (Target Flag x Measure / Dimension)
        if targets:
            tgt = targets[0]
            clean_tgt = _clean_name(tgt)
            for m_col in measures[:2]:
                clean_m = _clean_name(m_col)
                opportunities.append(AnalysisOpportunity(
                    opportunity_id=f"OPP-{opp_idx:03d}",
                    opportunity_type=OpportunityType.TARGET_ASSOCIATION,
                    primary_column=tgt,
                    secondary_column=m_col,
                    title=f"Outcome Driver Analysis: {clean_m} impact on {clean_tgt}",
                    rationale=f"Analyzes how metric variance correlates with the target state ({clean_tgt}).",
                    mathematical_method="logistic_odds_ratio_or_group_split",
                    feasibility_score=0.88
                ))
                opp_idx += 1

        # 7. Categorical Cross-Tabulation (Dimension x Dimension)
        if len(categories) >= 2:
            c1, c2 = categories[0], categories[1]
            clean_c1 = _clean_name(c1)
            clean_c2 = _clean_name(c2)
            opportunities.append(AnalysisOpportunity(
                opportunity_id=f"OPP-{opp_idx:03d}",
                opportunity_type=OpportunityType.CATEGORICAL_CROSS_TAB,
                primary_column=c1,
                secondary_column=c2,
                title=f"Cross-Tabulation Matrix: {clean_c1} × {clean_c2}",
                rationale=f"Evaluates cohort volume co-occurrence and segment distribution across {clean_c1} and {clean_c2}.",
                mathematical_method="contingency_table_chi_squared",
                feasibility_score=0.85
            ))
            opp_idx += 1

        # 8. Multi-Factor Segment Disparity (Dimension A × Dimension B × Measure)
        if len(categories) >= 2 and measures:
            viable_dims = []
            for cat in categories:
                col_meta = profile.columns.get(cat)
                dist_cnt = col_meta.unique_count if col_meta and getattr(col_meta, "unique_count", None) is not None else 5
                if 2 <= dist_cnt <= 15:
                    viable_dims.append(cat)

            if len(viable_dims) >= 2:
                c1, c2 = viable_dims[0], viable_dims[1]
                clean_c1 = _clean_name(c1)
                clean_c2 = _clean_name(c2)
                for m_col in measures[:2]:
                    clean_m = _clean_name(m_col)
                    opportunities.append(AnalysisOpportunity(
                        opportunity_id=f"OPP-{opp_idx:03d}",
                        opportunity_type=OpportunityType.MULTI_FACTOR_SEGMENT_DISPARITY,
                        primary_column=f"{c1}__x__{c2}",
                        secondary_column=m_col,
                        title=f"Multi-Factor Deep Segment Disparity: {clean_m} across {clean_c1} × {clean_c2}",
                        rationale=f"Evaluates non-linear cross-segment disparities and compound outlier cohorts across {clean_c1} and {clean_c2}.",
                        mathematical_method="bivariate_group_aggregation_and_pareto_concentration",
                        feasibility_score=0.92,
                        metadata={"dim1": c1, "dim2": c2, "measure": m_col}
                    ))
                    opp_idx += 1

        # 9. User-Priority Tagging & Reordering
        if context and getattr(context, "has_user_intent", False):
            user_questions_text = " ".join(getattr(context, "questions_to_answer", [])).lower()
            user_obj_text = (getattr(context, "user_objective", "") or "").lower()
            user_terms = user_questions_text + " " + user_obj_text
            imp_dims = [d.lower() for d in getattr(context, "important_dimensions", [])]
            imp_metrics = [m.lower() for m in getattr(context, "important_metrics", [])]

            for opp in opportunities:
                p_lower = opp.primary_column.lower()
                s_lower = (opp.secondary_column or "").lower()
                matched_reason = []
                if p_lower in imp_dims or (p_lower in user_terms and len(p_lower) >= 3):
                    matched_reason.append(f"dimension '{opp.primary_column}'")
                if s_lower and (s_lower in imp_metrics or (s_lower in user_terms and len(s_lower) >= 3)):
                    matched_reason.append(f"metric '{opp.secondary_column}'")
                if matched_reason:
                    opp.is_user_priority = True
                    opp.priority_reason = f"Directly addresses user-requested {', '.join(matched_reason)}"

            # Re-order: user-priority opportunities strictly first
            opportunities.sort(key=lambda o: 0 if o.is_user_priority else 1)

        # Group counts by type
        by_type: dict[str, int] = {}
        for opp in opportunities:
            t = opp.opportunity_type.value
            by_type[t] = by_type.get(t, 0) + 1

        return AnalysisOpportunityMap(
            dataset_name=profile.dataset_name,
            total_opportunities=len(opportunities),
            by_type_count=by_type,
            opportunities=opportunities[:max_opportunities]
        )
