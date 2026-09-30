"""Hybrid Column Relationship Discovery Engine (Stage 3).

Calculates multi-faceted relationship scores combining semantic name similarity,
statistical dependencies (Pearson, Spearman, Cramér's V, Correlation Ratio),
structural compatibility, domain relationships, and physical unit compatibility.
"""

from __future__ import annotations

import itertools
import math
import re
from typing import Any
import numpy as np
import pandas as pd

from .config import EnrichmentConfig
from .models import ColumnRelationship, EnrichmentColumnProfile, SemanticRole

# Domain clusters for semantic affinity
DOMAIN_KEYWORDS = {
    "motion_transportation": {"distance", "time", "speed", "velocity", "duration", "fuel", "trip", "travel", "mileage", "vehicle", "route", "km", "miles", "hours"},
    "physical_properties": {"mass", "volume", "density", "weight", "material", "area", "length", "width", "height", "temperature", "pressure", "kg", "grams", "liters"},
    "financial_economics": {"price", "cost", "revenue", "sales", "margin", "profit", "discount", "tax", "budget", "spend", "currency", "amount", "fee"},
    "workforce_operations": {"headcount", "hours", "overtime", "absent", "tenure", "salary", "rating", "performance", "shift", "department", "employee", "leave"},
    "temporal_lifecycle": {"start", "end", "date", "created", "updated", "year", "quarter", "month", "duration", "latency", "cycle"}
}


def compute_string_similarity(s1: str, s2: str) -> float:
    """Computes normalized token overlap and substring similarity between column names."""
    tokens1 = set(re.findall(r'[a-zA-Z0-9]+', s1.lower()))
    tokens2 = set(re.findall(r'[a-zA-Z0-9]+', s2.lower()))
    if not tokens1 or not tokens2:
        return 0.0
    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)
    jaccard = intersection / max(1, union)
    
    # Substring bonus
    sub_bonus = 0.3 if (s1.lower() in s2.lower() or s2.lower() in s1.lower()) and s1 != s2 else 0.0
    return min(1.0, jaccard + sub_bonus)


def compute_cramers_v(cat1: list[Any], cat2: list[Any]) -> float:
    """Computes Cramér's V statistic for categorical-categorical association."""
    try:
        s1 = pd.Series(cat1).dropna()
        s2 = pd.Series(cat2).dropna()
        if len(s1) < 4 or len(s2) < 4:
            return 0.0
        contingency = pd.crosstab(s1, s2).values
        if contingency.shape[0] < 2 or contingency.shape[1] < 2:
            return 0.0
        n = contingency.sum()
        if n == 0:
            return 0.0
        row_sums = contingency.sum(axis=1, keepdims=True)
        col_sums = contingency.sum(axis=0, keepdims=True)
        expected = np.dot(row_sums, col_sums) / n
        with np.errstate(divide='ignore', invalid='ignore'):
            chi2_terms = np.where(expected > 0, ((contingency - expected) ** 2) / expected, 0.0)
        chi2 = float(np.sum(chi2_terms))
        phi2 = chi2 / n
        r, k = contingency.shape
        phi2corr = max(0, phi2 - ((k - 1) * (r - 1)) / max(1, n - 1))
        rcorr = r - ((r - 1) ** 2) / max(1, n - 1)
        kcorr = k - ((k - 1) ** 2) / max(1, n - 1)
        denom = min((kcorr - 1), (rcorr - 1))
        if denom <= 0:
            return 0.0
        return round(float(np.sqrt(phi2corr / denom)), 4)
    except Exception:
        return 0.0


def compute_correlation_ratio(categories: list[Any], measurements: list[float]) -> float:
    """Computes correlation ratio (eta) between a categorical and a continuous variable."""
    try:
        df = pd.DataFrame({"cat": categories, "val": measurements}).dropna()
        if len(df) < 5 or df["cat"].nunique() < 2:
            return 0.0
        total_variance = df["val"].var()
        if total_variance == 0 or np.isnan(total_variance):
            return 0.0
        grouped_means = df.groupby("cat")["val"].mean()
        grouped_counts = df.groupby("cat")["val"].count()
        overall_mean = df["val"].mean()
        weighted_ss = sum(grouped_counts[c] * (grouped_means[c] - overall_mean) ** 2 for c in grouped_means.index)
        eta2 = weighted_ss / ((len(df) - 1) * total_variance)
        return round(float(np.sqrt(max(0.0, min(1.0, eta2)))), 4)
    except Exception:
        return 0.0


class ColumnRelationshipEngine:
    """Discovers hybrid pairwise relationships across columns respecting hard candidate budgets."""

    @classmethod
    def discover_relationships(
        cls,
        df: pd.DataFrame,
        profiles: dict[str, EnrichmentColumnProfile],
        config: EnrichmentConfig
    ) -> list[ColumnRelationship]:
        columns = list(df.columns)
        num_cols = len(columns)
        if num_cols < 2:
            return []

        # Generate candidate pairs
        all_pairs = list(itertools.combinations(columns, 2))
        
        # Enforce max_pairwise_candidates
        if len(all_pairs) > config.max_pairwise_candidates:
            # Prioritize pairs with shared tokens, common roles, or numeric pairs
            def pair_priority(p: tuple[str, str]) -> float:
                c1, c2 = p
                prof1, prof2 = profiles.get(c1), profiles.get(c2)
                sim = compute_string_similarity(c1, c2)
                type_boost = 0.5 if prof1 and prof2 and prof1.physical_type == prof2.physical_type else 0.0
                return sim + type_boost

            all_pairs = sorted(all_pairs, key=pair_priority, reverse=True)[:config.max_pairwise_candidates]

        relationships: list[ColumnRelationship] = []

        for col1, col2 in all_pairs:
            prof1 = profiles.get(col1)
            prof2 = profiles.get(col2)
            if not prof1 or not prof2:
                continue

            rel = cls.evaluate_pair(df[col1], df[col2], prof1, prof2)
            if rel.relationship_score >= config.min_relationship_score:
                relationships.append(rel)

        # Sort by relationship score descending
        relationships.sort(key=lambda r: r.relationship_score, reverse=True)
        return relationships

    @classmethod
    def evaluate_pair(
        cls,
        s1: pd.Series,
        s2: pd.Series,
        prof1: EnrichmentColumnProfile,
        prof2: EnrichmentColumnProfile
    ) -> ColumnRelationship:
        col1, col2 = prof1.column, prof2.column
        reasons: list[str] = []

        # 1. Semantic Name Similarity
        semantic_sim = compute_string_similarity(col1, col2)
        if semantic_sim > 0.4:
            reasons.append(f"Name token similarity: {semantic_sim:.2f}")

        # 2. Statistical Dependency
        stat_dep = 0.0
        is_num1 = SemanticRole.MEASURE in prof1.roles or prof1.physical_type in ("float", "int", "string_with_unit")
        is_num2 = SemanticRole.MEASURE in prof2.roles or prof2.physical_type in ("float", "int", "string_with_unit")

        # Convert to numeric arrays if applicable
        num_s1 = pd.to_numeric(s1.astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce')
        num_s2 = pd.to_numeric(s2.astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce')

        valid_nums1 = num_s1.notna().sum() / max(1, len(s1)) >= 0.7
        valid_nums2 = num_s2.notna().sum() / max(1, len(s2)) >= 0.7

        if valid_nums1 and valid_nums2:
            # Pearson & Spearman correlation via pandas and rank (zero scipy dependency)
            aligned = pd.DataFrame({"v1": num_s1, "v2": num_s2}).dropna()
            if len(aligned) >= 5 and aligned["v1"].std() > 0 and aligned["v2"].std() > 0:
                p_corr = aligned["v1"].corr(aligned["v2"])
                s_corr = aligned["v1"].rank().corr(aligned["v2"].rank())
                p_val = abs(p_corr) if not np.isnan(p_corr) else 0.0
                s_val = abs(s_corr) if not np.isnan(s_corr) else 0.0
                stat_dep = max(p_val, s_val)
                if stat_dep > 0.5:
                    reasons.append(f"Strong quantitative correlation: {stat_dep:.2f} (Pearson={p_val:.2f}, Spearman={s_val:.2f})")
        elif (valid_nums1 and not valid_nums2) or (valid_nums2 and not valid_nums1):
            # Correlation Ratio (continuous vs categorical)
            cat_s = s2 if valid_nums1 else s1
            num_s = num_s1 if valid_nums1 else num_s2
            stat_dep = compute_correlation_ratio(cat_s.tolist(), num_s.tolist())
            if stat_dep > 0.4:
                reasons.append(f"Categorical-continuous correlation ratio: {stat_dep:.2f}")
        else:
            # Cramér's V (categorical vs categorical)
            stat_dep = compute_cramers_v(s1.tolist(), s2.tolist())
            if stat_dep > 0.4:
                reasons.append(f"Categorical Cramér's V association: {stat_dep:.2f}")

        # 3. Structural Compatibility (Functional dependency / null alignment)
        struct_compat = 0.0
        if len(s1) > 0:
            null_overlap = (s1.isna() == s2.isna()).sum() / len(s1)
            struct_compat += 0.3 * null_overlap

            # Functional dependency check (if A groups cleanly with B)
            if prof1.cardinality > 0 and prof2.cardinality > 0:
                card_ratio = min(prof1.cardinality, prof2.cardinality) / max(prof1.cardinality, prof2.cardinality)
                struct_compat += 0.4 * card_ratio
                if card_ratio > 0.8:
                    reasons.append("Aligned cardinality hierarchy")

        # 4. Domain Relationship
        domain_rel = 0.0
        words1 = set(col1.lower().split("_"))
        words2 = set(col2.lower().split("_"))
        for d_name, d_words in DOMAIN_KEYWORDS.items():
            if (words1 & d_words) and (words2 & d_words):
                domain_rel = 1.0
                reasons.append(f"Co-occurring domain affinity: {d_name.replace('_', ' ').title()}")
                break

        # 5. Unit Compatibility & Known Physical Formulations
        unit_compat = 0.0
        u1 = (prof1.detected_unit or "").lower()
        u2 = (prof2.detected_unit or "").lower()
        if u1 and u2:
            try:
                from .adapters.unit_adapter import UnitSystemAdapter
                u_adapter = UnitSystemAdapter(enabled=True)
                if u1 == u2 or u_adapter.are_compatible(u1, u2):
                    unit_compat = 0.9
                    reasons.append(f"Dimensionally compatible units: {u1} and {u2}")
                else:
                    # Check ratio or product compatibility
                    valid_ratio, _, _ = u_adapter.validate_operation("/", u1, u2)
                    valid_prod, _, _ = u_adapter.validate_operation("*", u1, u2)
                    if valid_ratio or valid_prod:
                        unit_compat = 0.8
                        reasons.append(f"Complementary physical dimensions: {u1} and {u2}")
            except Exception:
                if u1 == u2:
                    unit_compat = 0.9
                elif (u1 in ("km", "m", "miles") and u2 in ("hours", "s", "min")) or (u2 in ("km", "m", "miles") and u1 in ("hours", "s", "min")):
                    unit_compat = 1.0
                    reasons.append("Complementary distance/time units for velocity derivation")
                elif (u1 in ("kg", "g", "lb") and u2 in ("l", "ml", "m3")) or (u2 in ("kg", "g", "lb") and u1 in ("l", "ml", "m3")):
                    unit_compat = 1.0
                    reasons.append("Complementary mass/volume units for density derivation")

        # Composite Score
        composite_score = (
            0.20 * semantic_sim
            + 0.40 * stat_dep
            + 0.15 * struct_compat
            + 0.15 * domain_rel
            + 0.10 * unit_compat
        )
        composite_score = round(min(1.0, max(0.0, composite_score)), 4)

        rel_type = "general_dependency"
        if stat_dep >= 0.85:
            rel_type = "collinear"
        elif unit_compat >= 0.8:
            rel_type = "dimensional_complement"
        elif domain_rel >= 0.8:
            rel_type = "domain_affinity"
        elif stat_dep >= 0.5:
            rel_type = "statistical_association"

        return ColumnRelationship(
            left_column=col1,
            right_column=col2,
            relationship_score=composite_score,
            semantic_similarity=round(semantic_sim, 4),
            statistical_dependency=round(stat_dep, 4),
            structural_compatibility=round(struct_compat, 4),
            domain_relationship=round(domain_rel, 4),
            unit_compatibility=round(unit_compat, 4),
            relationship_type=rel_type,
            reasons=reasons
        )
