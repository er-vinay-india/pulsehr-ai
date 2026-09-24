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
    metadata: dict[str, Any] = Field(default_factory=dict)


class AnalysisOpportunityMap(BaseModel):
    """Complete collection of admissible analytical opportunities for a dataset."""
    dataset_name: str
    total_opportunities: int
    by_type_count: dict[str, int] = Field(default_factory=dict)
    opportunities: list[AnalysisOpportunity] = Field(default_factory=list)


class OpportunityMapGenerator:
    """Discovers mathematically viable analytical paths from a SemanticDatasetProfile."""

    @classmethod
    def generate(cls, profile: SemanticDatasetProfile, max_opportunities: int = 25) -> AnalysisOpportunityMap:
        opportunities: list[AnalysisOpportunity] = []
        opp_idx = 1

        dates = profile.temporal_dimensions
        measures = list(set(profile.numeric_measures + profile.monetary_measures + profile.percentage_rates))
        categories = profile.categorical_dimensions
        rates = profile.percentage_rates
        targets = profile.possible_targets or profile.boolean_flags
        identifiers = profile.identifiers

        # 1. Period Trend Opportunities (Date x Measure)
        for dt_col in dates[:2]:
            for m_col in measures[:4]:
                p_col = profile.columns.get(m_col)
                feasibility = 1.0 - ((profile.columns.get(dt_col).null_percentage if dt_col in profile.columns else 0) / 100.0)
                opportunities.append(AnalysisOpportunity(
                    opportunity_id=f"OPP-{opp_idx:03d}",
                    opportunity_type=OpportunityType.PERIOD_TREND,
                    primary_column=dt_col,
                    secondary_column=m_col,
                    title=f"Chronological Trend Analysis: {p_col.display_name if p_col else m_col} over {dt_col}",
                    rationale=f"Evaluates trajectory, momentum, and period-over-period changes in {m_col}.",
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
                    opportunities.append(AnalysisOpportunity(
                        opportunity_id=f"OPP-{opp_idx:03d}",
                        opportunity_type=OpportunityType.SEGMENT_COMPARISON,
                        primary_column=dim_col,
                        secondary_column=m_col,
                        title=f"Segment Comparison: {m_prof.display_name if m_prof else m_col} across {dim_prof.display_name if dim_prof else dim_col}",
                        rationale=f"Discovers cohort disparities and identifies outperformer vs underperformer segments.",
                        mathematical_method="group_distribution_and_variance",
                        feasibility_score=0.95
                    ))
                    opp_idx += 1

        # 3. Subgroup Rate Disparity (Dimension x Percentage Rate)
        for dim_col in categories[:2]:
            for r_col in rates[:2]:
                r_prof = profile.columns.get(r_col)
                opportunities.append(AnalysisOpportunity(
                    opportunity_id=f"OPP-{opp_idx:03d}",
                    opportunity_type=OpportunityType.SUBGROUP_RATE_DISPARITY,
                    primary_column=dim_col,
                    secondary_column=r_col,
                    title=f"Rate Disparity Analysis: {r_prof.display_name if r_prof else r_col} by {dim_col}",
                    rationale=f"Audits percentage spread and structural divergence across groups for {r_col}.",
                    mathematical_method="proportional_variance_and_effect_size",
                    feasibility_score=0.90
                ))
                opp_idx += 1

        # 4. Measure Relationship & Tradeoff (Measure x Measure)
        if len(measures) >= 2:
            for i in range(min(3, len(measures))):
                for j in range(i + 1, min(4, len(measures))):
                    m1, m2 = measures[i], measures[j]
                    opportunities.append(AnalysisOpportunity(
                        opportunity_id=f"OPP-{opp_idx:03d}",
                        opportunity_type=OpportunityType.MEASURE_RELATIONSHIP,
                        primary_column=m1,
                        secondary_column=m2,
                        title=f"Bivariate Association: {m1} vs {m2}",
                        rationale=f"Tests statistical correlation, trade-offs, and empirical dependency between {m1} and {m2}.",
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
            opportunities.append(AnalysisOpportunity(
                opportunity_id=f"OPP-{opp_idx:03d}",
                opportunity_type=OpportunityType.ENTITY_CONCENTRATION,
                primary_column=ent,
                secondary_column=meas,
                title=f"Concentration & Pareto Analysis: {meas} by {ent}",
                rationale=f"Determines whether the top 20% of {ent} entities drive the majority of {meas}.",
                mathematical_method="cumulative_sum_and_gini_coefficient",
                feasibility_score=0.90
            ))
            opp_idx += 1

        # 6. Target Association (Target Flag x Measure / Dimension)
        if targets:
            tgt = targets[0]
            for m_col in measures[:2]:
                opportunities.append(AnalysisOpportunity(
                    opportunity_id=f"OPP-{opp_idx:03d}",
                    opportunity_type=OpportunityType.TARGET_ASSOCIATION,
                    primary_column=tgt,
                    secondary_column=m_col,
                    title=f"Outcome Driver Analysis: {m_col} impact on {tgt}",
                    rationale=f"Analyzes how metric variance correlates with the target state ({tgt}).",
                    mathematical_method="logistic_odds_ratio_or_group_split",
                    feasibility_score=0.88
                ))
                opp_idx += 1

        # 7. Categorical Cross-Tabulation (Dimension x Dimension)
        if len(categories) >= 2:
            c1, c2 = categories[0], categories[1]
            opportunities.append(AnalysisOpportunity(
                opportunity_id=f"OPP-{opp_idx:03d}",
                opportunity_type=OpportunityType.CATEGORICAL_CROSS_TAB,
                primary_column=c1,
                secondary_column=c2,
                title=f"Cross-Tabulation Matrix: {c1} × {c2}",
                rationale=f"Evaluates cohort volume co-occurrence and segment distribution across {c1} and {c2}.",
                mathematical_method="contingency_table_chi_squared",
                feasibility_score=0.85
            ))
            opp_idx += 1

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
