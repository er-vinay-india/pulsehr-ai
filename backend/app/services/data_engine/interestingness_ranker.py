"""Fact Interestingness and 'Surprise Me' Ranker for PulseHR AI.

Deterministically evaluates reliable CandidateFacts across multiple independent signals
to identify the most material, unusual, and attention-worthy empirical findings.
No LLM is involved.
"""

from enum import Enum
import math
from typing import Any
from pydantic import BaseModel, Field

from .semantic_classifier import MetricPolarity
from .opportunity_map import OpportunityType
from .candidate_fact import CandidateFact, ReliabilityStatus


class InsightCategory(str, Enum):
    STRONG_CHANGE = "STRONG_CHANGE"
    MATERIAL_SEGMENT_GAP = "MATERIAL_SEGMENT_GAP"
    CONCENTRATION = "CONCENTRATION"
    OUTLIER = "OUTLIER"
    STRONG_ASSOCIATION = "STRONG_ASSOCIATION"
    TREND_SHIFT = "TREND_SHIFT"
    RATE_DISPARITY = "RATE_DISPARITY"
    STABLE_OR_NO_DIFFERENCE = "STABLE / NO_MEANINGFUL_DIFFERENCE"


class RankedFact(BaseModel):
    """A scored and ranked candidate fact surfaced for human attention."""
    fact_id: str
    rank: int
    interestingness_score: float
    diversity_adjusted_score: float
    insight_category: InsightCategory
    fact: CandidateFact
    scoring_components: dict[str, float] = Field(default_factory=dict)
    ranking_reason: str = ""
    obviousness_score: float = 0.0
    obviousness_reason: str | None = None
    unstable_relative_change: bool = False
    priority_type: str = "DISCOVERY"  # "USER_PRIORITY" or "DISCOVERY"
    provenance: str = "DATA_INFERRED"  # "USER_EXPLICIT", "USER_INFERRED", "DATA_INFERRED", "SYSTEM_DEFAULT"


class FactInterestingnessRanker:
    """Deterministic ranking engine evaluating CandidateFacts on material significance and novelty."""

    @classmethod
    def rank_interesting_facts(
        cls,
        facts: list[CandidateFact],
        limit: int = 10,
        diversity_lambda: float = 0.70
    ) -> list[RankedFact]:
        """Scores CandidateFacts and applies greedy diversity re-ranking to yield top findings.
        
        Args:
            facts: Pool of CandidateFacts to evaluate.
            limit: Maximum number of ranked facts to return.
            diversity_lambda: Weight balancing raw interestingness (1.0) vs diversity.
        """
        # Only evaluate reliable facts
        eligible_facts = [f for f in facts if f.reliability_status == ReliabilityStatus.RELIABLE]
        if not eligible_facts:
            return []

        # 1. Calculate raw interestingness score for each fact
        scored_pool: list[tuple[CandidateFact, float, InsightCategory, dict[str, float], str, float, str | None, bool]] = []
        for fact in eligible_facts:
            score, category, components, reason, obv_score, obv_reason, unstable_rel = cls._score_fact(fact)
            scored_pool.append((fact, score, category, components, reason, obv_score, obv_reason, unstable_rel))

        # 2. Greedy Diversity-Aware Re-ranking (Maximum Marginal Relevance style)
        selected_ranked: list[RankedFact] = []
        remaining = list(scored_pool)

        metric_counts: dict[str, int] = {}
        dim_counts: dict[str, int] = {}
        type_counts: dict[str, int] = {}

        for rank_idx in range(1, min(limit, len(scored_pool)) + 1):
            best_candidate = None
            best_adjusted_score = -999.0
            best_tuple = None
            best_index = -1

            for idx, candidate_tuple in enumerate(remaining):
                fact, base_score, cat, components, reason, obv_score, obv_reason, unstable_rel = candidate_tuple
                # Calculate redundancy penalty
                m_penalty = 0.20 * metric_counts.get(fact.metric, 0)
                # Primary dimension
                dim_key = None
                if fact.dimensions:
                    dim_key = next(iter(fact.dimensions.keys()))
                d_penalty = 0.15 * dim_counts.get(dim_key, 0) if dim_key else 0.0
                t_penalty = 0.10 * type_counts.get(fact.fact_type, 0)

                total_penalty = min(0.55, m_penalty + d_penalty + t_penalty)
                # User-priority facts receive a top-tier boost so user questions rank first
                priority_boost = 10.0 if fact.priority_type == "USER_PRIORITY" else 0.0
                adjusted_score = round(base_score + priority_boost - (1.0 - diversity_lambda) * total_penalty, 3)

                if adjusted_score > best_adjusted_score:
                    best_adjusted_score = adjusted_score
                    best_candidate = candidate_tuple
                    best_tuple = fact
                    best_index = idx

            if best_candidate is None:
                break

            fact, base_score, cat, components, reason, obv_score, obv_reason, unstable_rel = best_candidate
            remaining.pop(best_index)

            # Update frequency tallies
            metric_counts[fact.metric] = metric_counts.get(fact.metric, 0) + 1
            if fact.dimensions:
                dim_k = next(iter(fact.dimensions.keys()))
                dim_counts[dim_k] = dim_counts.get(dim_k, 0) + 1
            type_counts[fact.fact_type] = type_counts.get(fact.fact_type, 0) + 1

            selected_ranked.append(RankedFact(
                fact_id=fact.fact_id,
                rank=rank_idx,
                interestingness_score=round(base_score, 3),
                diversity_adjusted_score=round(best_adjusted_score, 3),
                insight_category=cat,
                fact=fact,
                scoring_components=components,
                ranking_reason=reason,
                obviousness_score=round(obv_score, 3),
                obviousness_reason=obv_reason,
                unstable_relative_change=unstable_rel,
                priority_type=fact.priority_type,
                provenance=fact.provenance
            ))

        return selected_ranked

    # -------------------------------------------------------------------------
    # Specialized scoring methodology by fact type
    # -------------------------------------------------------------------------

    @classmethod
    def _score_fact(
        cls,
        fact: CandidateFact
    ) -> tuple[float, InsightCategory, dict[str, float], str, float, str | None, bool]:
        """Dispatches fact to specialized scoring function by fact type."""
        ft = fact.fact_type

        if ft in (OpportunityType.TARGET_COMPLIANCE.value, "target_compliance"):
            return cls._score_target_compliance(fact)
        elif ft == OpportunityType.PERIOD_TREND.value:
            return cls._score_period_trend(fact)
        elif ft == OpportunityType.SEGMENT_COMPARISON.value:
            return cls._score_segment_comparison(fact)
        elif ft == OpportunityType.ENTITY_CONCENTRATION.value:
            return cls._score_entity_concentration(fact)
        elif ft == OpportunityType.MEASURE_RELATIONSHIP.value:
            return cls._score_measure_relationship(fact)
        elif ft == OpportunityType.SUBGROUP_RATE_DISPARITY.value:
            return cls._score_subgroup_rate(fact)
        elif ft == OpportunityType.CATEGORICAL_CROSS_TAB.value:
            return cls._score_categorical_cross_tab(fact)
        elif ft == OpportunityType.TARGET_ASSOCIATION.value:
            return cls._score_target_association(fact)

        # Fallback generic baseline
        return 0.30, InsightCategory.STABLE_OR_NO_DIFFERENCE, {"generic_score": 0.30}, "Baseline observation.", 0.0, None, False

    # 0. TARGET_COMPLIANCE
    @classmethod
    def _score_target_compliance(
        cls,
        fact: CandidateFact
    ) -> tuple[float, InsightCategory, dict[str, float], str, float, str | None, bool]:
        abs_diff = abs(fact.absolute_difference or 0.0)
        score = 0.5 + min(0.5, (abs_diff / 50.0) * 0.5)
        cat = InsightCategory.MATERIAL_SEGMENT_GAP
        reason = f"Target compliance variance ({fact.value:.1f}% vs baseline {fact.baseline_value:.1f}%)"
        components = {"compliance_deviation": abs_diff, "sample_size": float(fact.sample_size)}
        return score, cat, components, reason, 0.0, None, False

    # 1. PERIOD_TREND
    @classmethod
    def _score_period_trend(
        cls,
        fact: CandidateFact
    ) -> tuple[float, InsightCategory, dict[str, float], str, float, str | None, bool]:
        info = fact.statistical_info
        r2 = float(info.get("r_squared", 0.0))
        periods = int(info.get("periods_evaluated", 0))
        start_val = fact.baseline_value
        end_val = fact.value
        abs_diff = abs(float(fact.absolute_difference)) if fact.absolute_difference is not None else 0.0
        rel_diff = abs(float(fact.relative_difference)) if fact.relative_difference is not None else 0.0

        components: dict[str, float] = {}

        # Detect near-zero baseline and sign-crossing (unstable percentage change)
        is_sign_crossing = False
        is_near_zero_baseline = False
        if start_val is not None and end_val is not None:
            is_sign_crossing = (start_val < 0 and end_val > 0) or (start_val > 0 and end_val < 0)
            val_scale = max(abs(start_val), abs(end_val), abs_diff)
            if val_scale > 0 and abs(start_val) < 0.15 * val_scale:
                is_near_zero_baseline = True

        unstable_relative = is_sign_crossing or is_near_zero_baseline

        if unstable_relative:
            val_scale = max(abs(start_val or 0), abs(end_val or 0), abs_diff, 1.0)
            movement_score = min(1.0, (abs_diff / val_scale) * 0.75)
            components["unstable_relative_percentage"] = 1.0
        else:
            movement_score = min(1.0, rel_diff / 50.0)

        fit_score = r2
        span_score = min(1.0, periods / 6.0)

        # Combined weighted score
        score = 0.45 * movement_score + 0.35 * fit_score + 0.20 * span_score
        
        # Statistically responsible gating: a trend with R² < 0.15 has no consistent trajectory
        if r2 < 0.15:
            score = min(0.20, score * max(0.1, r2 / 0.15))
            category = InsightCategory.STABLE_OR_NO_DIFFERENCE
            reason = f"Low linear predictability (R² = {r2:.2f}); metric exhibits no consistent directional trend."
        elif unstable_relative:
            category = InsightCategory.STRONG_CHANGE if movement_score >= 0.50 else InsightCategory.TREND_SHIFT
            reason = f"Substantial movement across zero boundary (from {start_val} to {end_val}, R² = {r2:.2f}); relative percentage is ill-conditioned due to near-zero/negative baseline."
        elif rel_diff >= 30.0 and r2 >= 0.50:
            category = InsightCategory.STRONG_CHANGE
            reason = f"Substantial chronological change of {rel_diff:.1f}% with strong linear trajectory (R² = {r2:.2f})."
        elif rel_diff < 5.0:
            category = InsightCategory.STABLE_OR_NO_DIFFERENCE
            reason = f"Minimal temporal movement ({rel_diff:.1f}%) across {periods} evaluated periods."
        else:
            category = InsightCategory.TREND_SHIFT
            reason = f"Notable period trajectory of {rel_diff:.1f}% (R² = {r2:.2f}) across {periods} evaluated periods."

        score = min(1.0, max(0.05, score))

        components["movement_magnitude"] = round(movement_score, 2)
        components["trajectory_r2"] = round(fit_score, 2)
        components["temporal_span"] = round(span_score, 2)

        return score, category, components, reason, 0.0, None, unstable_relative

    # 2. SEGMENT_COMPARISON
    @classmethod
    def _score_segment_comparison(
        cls,
        fact: CandidateFact
    ) -> tuple[float, InsightCategory, dict[str, float], str, float, str | None, bool]:
        info = fact.statistical_info
        f_stat = float(info.get("between_group_f_stat", 0.0))
        rel_diff = abs(float(fact.relative_difference)) if fact.relative_difference is not None else 0.0
        n_seg = fact.sample_size
        base_std = float(info.get("baseline_std", 1.0))
        abs_diff = abs(float(fact.absolute_difference)) if fact.absolute_difference is not None else 0.0
        baseline_mean = float(info.get("baseline_mean", 0.0))

        components: dict[str, float] = {}

        # Detect near-zero baseline for segment comparisons
        is_near_zero_base = abs(baseline_mean) < (0.25 * base_std) if base_std > 0 else False
        unstable_relative = is_near_zero_base

        if is_near_zero_base:
            rel_score = min(1.0, (abs_diff / base_std) / 2.0) if base_std > 0 else 0.20
            components["unstable_relative_percentage"] = 1.0
        else:
            rel_score = min(1.0, rel_diff / 40.0)

        # Standard deviation gap
        sigma_gap = (abs_diff / base_std) if base_std > 0 else 0.0
        dispersion_score = min(1.0, sigma_gap / 1.5)

        # ANOVA F-statistic
        f_score = min(1.0, f_stat / (f_stat + 4.0)) if f_stat > 0 else 0.0

        # Strengthened small sample and dataset share penalty (Bayesian shrinkage)
        total_sample = int(fact.evidence_metadata.get("total_sample") or 20)
        share = n_seg / max(1, total_sample)
        c_abs = (n_seg / 6.0) ** 0.85 if n_seg < 6 else 1.0
        c_share = min(1.0, math.sqrt(share / 0.15))
        w_credibility = c_abs * max(0.50, c_share)

        raw_effect = 0.45 * rel_score + 0.35 * dispersion_score + 0.20 * f_score
        score = raw_effect * w_credibility
        score = min(1.0, max(0.05, score))

        components["relative_gap"] = round(rel_score, 2)
        components["dispersion_sigma"] = round(dispersion_score, 2)
        components["anova_f_stat"] = round(f_score, 2)
        components["sample_credibility"] = round(w_credibility, 2)

        dim_str = list(fact.dimensions.values())[0] if fact.dimensions else "Segment"
        sample_note = f" (limited evidence: small subgroup n = {n_seg}, {share*100:.0f}% of dataset)" if n_seg < 5 else f" (n = {n_seg})"

        if rel_diff >= 25.0 and sigma_gap >= 0.75:
            category = InsightCategory.MATERIAL_SEGMENT_GAP
            reason = f"Material segment disparity: '{dim_str}' deviates by {rel_diff:.1f}% ({sigma_gap:.2f}σ from baseline){sample_note}."
        elif rel_diff < 4.0 and sigma_gap < 0.20:
            category = InsightCategory.STABLE_OR_NO_DIFFERENCE
            reason = f"Negligible segment gap ({rel_diff:.1f}%, {sigma_gap:.2f}σ); segment aligns closely with dataset baseline."
        elif sigma_gap >= 1.5:
            category = InsightCategory.OUTLIER
            reason = f"Marked statistical divergence: '{dim_str}' deviates by {sigma_gap:.2f} standard deviations from mean{sample_note}."
        else:
            category = InsightCategory.MATERIAL_SEGMENT_GAP
            reason = f"Segment disparity of {rel_diff:.1f}% against overall baseline{sample_note}."

        return score, category, components, reason, 0.0, None, unstable_relative

    # 3. ENTITY_CONCENTRATION
    @classmethod
    def _score_entity_concentration(
        cls,
        fact: CandidateFact
    ) -> tuple[float, InsightCategory, dict[str, float], str, float, str | None, bool]:
        info = fact.statistical_info
        gini = float(info.get("gini_coefficient", 0.0))
        top_20_share = float(fact.value) if fact.value is not None else 20.0
        top_1_share = float(info.get("top_1_entity_share_pct", 0.0))
        n_entities = fact.sample_size

        # Sub-scores:
        # A. Excess share above 20%: e.g., 20% -> 0.0, 80%+ -> 1.0 (60 pp excess)
        excess_share = max(0.0, top_20_share - 20.0)
        excess_score = min(1.0, excess_share / 50.0)
        # B. Gini score: 0 -> 0.0, 0.60+ -> 1.0
        gini_score = min(1.0, gini / 0.60)
        # C. Single entity dominance: 0% -> 0.0, 30%+ -> 1.0
        top_1_score = min(1.0, top_1_share / 30.0)
        # D. Entity pool size: 5 entities -> 0.5, 20+ entities -> 1.0
        pool_score = min(1.0, n_entities / 20.0)

        score = 0.40 * excess_score + 0.30 * gini_score + 0.15 * top_1_score + 0.15 * pool_score
        score = min(1.0, max(0.05, score))

        components = {
            "excess_concentration": round(excess_score, 2),
            "gini_inequality": round(gini_score, 2),
            "single_entity_share": round(top_1_score, 2),
            "entity_pool_size": round(pool_score, 2)
        }

        if top_20_share >= 40.0 or gini >= 0.35:
            category = InsightCategory.CONCENTRATION
            reason = f"High concentration: top 20% of entities account for {top_20_share:.1f}% of total {fact.metric} (Gini = {gini:.3f})."
        elif top_20_share <= 25.0 and gini <= 0.15:
            category = InsightCategory.STABLE_OR_NO_DIFFERENCE
            reason = f"Near-uniform volume distribution across entities (top 20% share = {top_20_share:.1f}%, Gini = {gini:.3f})."
        else:
            category = InsightCategory.CONCENTRATION
            reason = f"Moderate Pareto concentration ({top_20_share:.1f}% in top 20%; n = {n_entities})."

        return score, category, components, reason, 0.0, None, False

    # 4. MEASURE_RELATIONSHIP
    @classmethod
    def _detect_obvious_relationship(
        cls,
        m1: str,
        m2: str,
        r2: float,
        p_val: float
    ) -> tuple[float, str | None]:
        """Detects whether a bivariate correlation is an obvious, derived, or accounting identity."""
        if r2 < 0.95 or p_val > 0.01:
            return 0.0, None

        m1_clean = m1.lower().replace("_", " ").replace("-", " ")
        m2_clean = m2.lower().replace("_", " ").replace("-", " ")
        m1_tokens = set(m1_clean.split())
        m2_tokens = set(m2_clean.split())

        # Accounting and arithmetic derived pairs
        accounting_pairs = [
            ({"profit", "margin", "income"}, {"sales", "revenue", "cost", "expense", "cogs"}),
            ({"budget", "planned", "forecast", "target"}, {"actual", "spent", "variance"}),
            ({"gross"}, {"net"}),
            ({"discount"}, {"sales", "price", "rate"}),
            ({"defect", "scrap", "loss"}, {"scrap", "defect", "error"}),
            ({"tenure", "experience", "seniority"}, {"salary", "comp", "compensation", "wage"}),
        ]

        is_known_accounting_pair = any(
            (bool(m1_tokens & group_a) and bool(m2_tokens & group_b))
            or (bool(m1_tokens & group_b) and bool(m2_tokens & group_a))
            for group_a, group_b in accounting_pairs
        )

        has_count_rate_match = ("count" in m1_tokens and "rate" in m2_tokens) or ("rate" in m1_tokens and "count" in m2_tokens)
        shared_tokens = (m1_tokens & m2_tokens) - {"usd", "eur", "pct", "rate", "count", "amount", "total", "val"}

        if is_known_accounting_pair and r2 >= 0.98:
            return 0.85, f"Known accounting or arithmetic dependency between '{m1}' and '{m2}' (R² = {r2:.2f})"

        if has_count_rate_match and r2 >= 0.98:
            return 0.80, f"Derived rate vs count relationship between '{m1}' and '{m2}' (R² = {r2:.2f})"

        if r2 >= 0.998:
            return 0.75, f"Near-perfect deterministic collinearity (R² = {r2:.3f}); likely formulaic or direct synthetic generation"

        if shared_tokens and r2 >= 0.98:
            return 0.65, f"High correlation with shared semantic tokens ({', '.join(shared_tokens)}; R² = {r2:.2f})"

        return 0.0, None

    @classmethod
    def _score_measure_relationship(
        cls,
        fact: CandidateFact
    ) -> tuple[float, InsightCategory, dict[str, float], str, float, str | None, bool]:
        info = fact.statistical_info
        r = abs(float(info.get("pearson_r", 0.0)))
        p_val = float(info.get("p_value", 1.0))
        r2 = float(info.get("r_squared", 0.0))
        n = fact.sample_size

        # Sub-scores:
        # A. Correlation magnitude: 0.0 -> 0.0, 0.70+ -> 1.0
        corr_score = min(1.0, r / 0.70)
        # B. Statistical significance: p < 0.01 -> 1.0, p > 0.20 -> 0.0
        sig_score = max(0.0, 1.0 - (p_val / 0.15))
        # C. Explained variance: r2
        r2_score = r2
        # D. Paired observation sample support
        sample_score = min(1.0, n / 25.0)

        raw_score = 0.40 * corr_score + 0.35 * sig_score + 0.15 * r2_score + 0.10 * sample_score
        score = min(1.0, max(0.05, raw_score))

        components = {
            "correlation_magnitude": round(corr_score, 2),
            "significance_p_val": round(sig_score, 2),
            "variance_explained_r2": round(r2_score, 2),
            "sample_support": round(sample_score, 2)
        }

        m1 = fact.dimensions.get("measure_x", "measure_1")
        m2 = fact.dimensions.get("measure_y", "measure_2")

        # Detect and discount obvious or derived relationships
        obv_score, obv_reason = cls._detect_obvious_relationship(m1, m2, r2, p_val)
        if obv_score > 0.0:
            score = score * (1.0 - 0.70 * obv_score)
            components["obviousness_penalty"] = round(obv_score, 2)

        if r >= 0.55 and p_val <= 0.05:
            category = InsightCategory.STRONG_ASSOCIATION
            if obv_score > 0.0:
                reason = f"Bivariate correlation (r = {r:.2f}, R² = {r2:.2f}), discounted due to: {obv_reason}."
            else:
                reason = f"Significant bivariate correlation between {m1} and {m2} (r = {r:.2f}, p = {p_val:.3f}, R² = {r2:.2f}; n = {n})."
        elif r < 0.25 or p_val > 0.25:
            category = InsightCategory.STABLE_OR_NO_DIFFERENCE
            reason = f"Weak correlation between {m1} and {m2} (r = {r:.2f}, p = {p_val:.3f}); no meaningful empirical relationship."
        else:
            category = InsightCategory.STRONG_ASSOCIATION
            reason = f"Moderate empirical association between {m1} and {m2} (r = {r:.2f}, p = {p_val:.3f})."

        return score, category, components, reason, obv_score, obv_reason, False

    # 5. SUBGROUP_RATE_DISPARITY
    @classmethod
    def _score_subgroup_rate(
        cls,
        fact: CandidateFact
    ) -> tuple[float, InsightCategory, dict[str, float], str, float, str | None, bool]:
        info = fact.statistical_info
        diff_pp = abs(float(fact.absolute_difference)) if fact.absolute_difference is not None else 0.0
        disparity_ratio = float(info.get("disparity_ratio", 1.0))
        n_sub = fact.sample_size

        # Strengthened small sample and dataset share penalty (Bayesian shrinkage)
        total_records = int(fact.evidence_metadata.get("total_records") or 20)
        share = n_sub / max(1, total_records)
        c_abs = (n_sub / 6.0) ** 0.85 if n_sub < 6 else 1.0
        c_share = min(1.0, math.sqrt(share / 0.15))
        w_credibility = c_abs * max(0.50, c_share)

        # Sub-scores:
        gap_score = min(1.0, diff_pp / 5.0)
        ratio_score = min(1.0, abs(disparity_ratio - 1.0))

        raw_effect = 0.60 * gap_score + 0.40 * ratio_score
        score = raw_effect * w_credibility
        score = min(1.0, max(0.05, score))

        components = {
            "percentage_point_gap": round(gap_score, 2),
            "disparity_ratio": round(ratio_score, 2),
            "sample_credibility": round(w_credibility, 2)
        }

        sub_str = list(fact.dimensions.values())[0] if fact.dimensions else "Subgroup"
        sample_note = f" (limited evidence: small subgroup n = {n_sub}, {share*100:.0f}% of dataset)" if n_sub < 5 else f" (n = {n_sub})"

        if diff_pp >= 2.0 or disparity_ratio >= 1.5:
            category = InsightCategory.RATE_DISPARITY
            reason = f"Notable rate spread: '{sub_str}' diverges by {diff_pp:.2f} percentage points from baseline{sample_note}."
        elif diff_pp < 0.4:
            category = InsightCategory.STABLE_OR_NO_DIFFERENCE
            reason = f"Subgroup rate disparity is negligible ({diff_pp:.2f} percentage points from baseline)."
        else:
            category = InsightCategory.RATE_DISPARITY
            reason = f"Subgroup '{sub_str}' displays a {diff_pp:.2f} percentage point spread against overall rate{sample_note}."

        return score, category, components, reason, 0.0, None, False

    # 6. CATEGORICAL_CROSS_TAB
    @classmethod
    def _score_categorical_cross_tab(
        cls,
        fact: CandidateFact
    ) -> tuple[float, InsightCategory, dict[str, float], str, float, str | None, bool]:
        info = fact.statistical_info
        cramers_v = float(info.get("cramers_v", 0.0))
        chi2 = float(info.get("chi_squared", 0.0))
        n = fact.sample_size

        # Sub-scores:
        v_score = min(1.0, cramers_v / 0.40)
        chi2_score = min(1.0, chi2 / (chi2 + 10.0)) if chi2 > 0 else 0.0
        sample_score = min(1.0, n / 30.0)

        score = 0.50 * v_score + 0.30 * chi2_score + 0.20 * sample_score
        score = min(1.0, max(0.05, score))

        components = {
            "cramers_v_effect": round(v_score, 2),
            "chi_squared_strength": round(chi2_score, 2),
            "sample_support": round(sample_score, 2)
        }

        d1 = fact.dimensions.get("dimension_1", "Dim1")
        d2 = fact.dimensions.get("dimension_2", "Dim2")
        if cramers_v >= 0.30:
            category = InsightCategory.STRONG_ASSOCIATION
            reason = f"Significant category co-occurrence between {d1} and {d2} (Cramer's V = {cramers_v:.2f}, Chi² = {chi2:.1f}; n = {n})."
        elif cramers_v < 0.15:
            category = InsightCategory.STABLE_OR_NO_DIFFERENCE
            reason = f"Near-independent categorical distribution between {d1} and {d2} (Cramer's V = {cramers_v:.2f})."
        else:
            category = InsightCategory.STRONG_ASSOCIATION
            reason = f"Moderate categorical association between {d1} and {d2} (Cramer's V = {cramers_v:.2f})."

        return score, category, components, reason, 0.0, None, False

    # 7. TARGET_ASSOCIATION
    @classmethod
    def _score_target_association(
        cls,
        fact: CandidateFact
    ) -> tuple[float, InsightCategory, dict[str, float], str, float, str | None, bool]:
        info = fact.statistical_info
        cohens_d = abs(float(info.get("cohens_d", 0.0)))
        p_val = float(info.get("p_value", 1.0))
        t_stat = abs(float(info.get("t_statistic", 0.0)))
        rel_diff = abs(float(fact.relative_difference)) if fact.relative_difference is not None else 0.0
        n = fact.sample_size

        # Sub-scores:
        d_score = min(1.0, cohens_d / 0.80)
        sig_score = max(0.0, 1.0 - (p_val / 0.15))
        rel_score = min(1.0, rel_diff / 40.0)
        sample_score = min(1.0, n / 25.0)

        score = 0.40 * d_score + 0.30 * sig_score + 0.15 * rel_score + 0.15 * sample_score
        score = min(1.0, max(0.05, score))

        components = {
            "cohens_d_effect": round(d_score, 2),
            "significance_p_val": round(sig_score, 2),
            "cohort_relative_gap": round(rel_score, 2),
            "sample_support": round(sample_score, 2)
        }

        tgt_col = fact.dimensions.get("target", "Target")
        if cohens_d >= 0.60 and p_val <= 0.05:
            category = InsightCategory.STRONG_ASSOCIATION
            reason = f"Strong outcome separation on {fact.metric} by {tgt_col} (Cohen's d = {cohens_d:.2f}, p = {p_val:.3f}; n = {n})."
        elif cohens_d < 0.20 or p_val > 0.30:
            category = InsightCategory.STABLE_OR_NO_DIFFERENCE
            reason = f"Negligible cohort separation on {fact.metric} by {tgt_col} (Cohen's d = {cohens_d:.2f}, p = {p_val:.3f})."
        else:
            category = InsightCategory.MATERIAL_SEGMENT_GAP
            reason = f"Moderate target divergence on {fact.metric} between outcome cohorts (Cohen's d = {cohens_d:.2f})."

        return score, category, components, reason, 0.0, None, False
