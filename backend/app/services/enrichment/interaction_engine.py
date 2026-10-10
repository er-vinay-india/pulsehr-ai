"""Interaction Feature Derivation Engine (Stage 9).

Generates bounded cross-feature combinations, ratios, categorical aggregations (group means),
and interaction terms while enforcing strict derivation recursion depth and budget bounds.
"""

from __future__ import annotations

import itertools
import logging
from typing import Any
import numpy as np
import pandas as pd

from .config import BudgetGuard, EnrichmentConfig
from .models import DerivedFeature, EnrichmentColumnProfile, SemanticRole
from ..display_formatters import format_display_label

logger = logging.getLogger(__name__)


class InteractionFeatureEngine:
    """Generates cross-dimensional feature interactions, ratios, and categorical aggregations."""

    @classmethod
    def derive_interactions(
        cls,
        df: pd.DataFrame,
        profiles: dict[str, EnrichmentColumnProfile],
        budget_guard: BudgetGuard,
        config: EnrichmentConfig
    ) -> tuple[pd.DataFrame, list[DerivedFeature]]:
        enriched_df = df.copy()
        interaction_features: list[DerivedFeature] = []

        if config.max_derivation_depth < 2:
            return enriched_df, interaction_features

        # Identify numeric measures and categorical dimensions
        numeric_cols = [
            c for c in enriched_df.columns
            if pd.api.types.is_numeric_dtype(enriched_df[c])
            and enriched_df[c].nunique() > 2
            and not c.endswith("_id")
            and not c.endswith("_year")
            and not c.endswith("_day")
            and not (
                profiles.get(c) and (
                    SemanticRole.IDENTIFIER in profiles[c].roles
                    or SemanticRole.ORDINAL in profiles[c].roles
                    or profiles[c].semantic_type == "identifier"
                )
            )
        ]

        total_rows = len(enriched_df)
        categorical_cols: list[str] = []
        for c in enriched_df.columns:
            if c.endswith("_id") or c.endswith("_uuid"):
                continue
            prof = profiles.get(c)
            if prof and (SemanticRole.IDENTIFIER in prof.roles or prof.semantic_type == "identifier"):
                continue

            nunique = enriched_df[c].nunique()
            if nunique < 2:
                continue

            cardinality_ratio = nunique / max(1, total_rows)
            # Dynamic cardinality: genuine categories don't have unique ratio >= 0.70
            is_cat_dtype = (
                isinstance(enriched_df[c].dtype, pd.CategoricalDtype)
                or pd.api.types.is_object_dtype(enriched_df[c])
                or pd.api.types.is_string_dtype(enriched_df[c])
                or pd.api.types.is_bool_dtype(enriched_df[c])
            )
            has_cat_role = prof and (SemanticRole.CATEGORY in prof.roles or SemanticRole.ORDINAL in prof.roles or SemanticRole.DIMENSION in prof.roles)

            if has_cat_role or (is_cat_dtype and cardinality_ratio < 0.70) or (nunique <= 50 and cardinality_ratio < 0.50):
                categorical_cols.append(c)

        # 1. Group-Level Categorical Aggregation Features (e.g. Mean(Sales) by Department)
        for cat_col in categorical_cols[:6]:
            for num_col in numeric_cols[:5]:
                if not budget_guard.can_derive_column():
                    break

                feat_name = f"interact_mean_{num_col}_by_{cat_col}"
                if feat_name in enriched_df.columns:
                    continue

                # For high cardinality (> 20 distinct), bin infrequent categories to top 15 + other
                cat_nunique = enriched_df[cat_col].nunique()
                if cat_nunique > 20:
                    top_cats = set(enriched_df[cat_col].value_counts().nlargest(15).index)
                    binned_cat = enriched_df[cat_col].apply(lambda v: v if v in top_cats else "__other__")
                    group_means = enriched_df.groupby(binned_cat)[num_col].transform("mean")
                else:
                    group_means = enriched_df.groupby(cat_col)[num_col].transform("mean")
                if group_means.std() > 0:
                    enriched_df[feat_name] = np.round(group_means, 4)
                    budget_guard.record_derived_columns(1)
                    disp_name = f"Mean {format_display_label(num_col)} by {format_display_label(cat_col)}"
                    interaction_features.append(
                        DerivedFeature(
                            name=feat_name,
                            display_name=disp_name,
                            is_synthetic=True,
                            source_columns=[num_col, cat_col],
                            derivation_type="interaction_group_mean",
                            expression=f"mean({num_col}) grouped_by {cat_col}",
                            depth=2,
                            confidence=0.92,
                            utility_score=0.88,
                            unit="mean_aggregate",
                            roles=[SemanticRole.MEASURE, SemanticRole.QUANTITY]
                        )
                    )

        # 2. Pairwise Metric Ratio / Difference Interactions (bounded to top correlated pairs)
        if len(numeric_cols) >= 2 and budget_guard.can_derive_column():
            pairs = list(itertools.combinations(numeric_cols[:10], 2))
            for c1, c2 in pairs:
                if not budget_guard.can_derive_column():
                    break

                s1 = pd.to_numeric(enriched_df[c1], errors='coerce')
                s2 = pd.to_numeric(enriched_df[c2], errors='coerce')

                # Bounded Ratio c1 / c2 if c2 is strictly non-zero positive
                if (s2 > 0).sum() / max(1, len(enriched_df)) >= 0.7:
                    ratio_name = f"interact_ratio_{c1}_over_{c2}"
                    if ratio_name not in enriched_df.columns:
                        ratio_val = (s1 / s2).where(s2 > 0).round(4)
                        res = pd.Series(ratio_val.to_numpy(dtype=float, na_value=np.nan), index=enriched_df.index, dtype="float64")

                        # Verify standard deviation > 0
                        if res.std() > 0:
                            enriched_df[ratio_name] = res
                            budget_guard.record_derived_columns(1)
                            disp_name = f"Ratio of {format_display_label(c1)} to {format_display_label(c2)}"
                            interaction_features.append(
                                DerivedFeature(
                                    name=ratio_name,
                                    display_name=disp_name,
                                    is_synthetic=True,
                                    source_columns=[c1, c2],
                                    derivation_type="interaction_ratio",
                                    expression=f"{c1} / {c2}",
                                    depth=2,
                                    confidence=0.85,
                                    utility_score=0.82,
                                    unit="ratio",
                                    roles=[SemanticRole.MEASURE, SemanticRole.QUANTITY]
                                )
                            )

        return enriched_df, interaction_features
