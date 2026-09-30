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
        ]

        categorical_cols = [
            c for c in enriched_df.columns
            if 2 <= enriched_df[c].nunique() <= 30
            and not c.endswith("_id")
        ]

        # 1. Group-Level Categorical Aggregation Features (e.g. Mean(Sales) by Department)
        for cat_col in categorical_cols[:5]:
            for num_col in numeric_cols[:5]:
                if not budget_guard.can_derive_column():
                    break

                feat_name = f"interact_mean_{num_col}_by_{cat_col}"
                if feat_name in enriched_df.columns:
                    continue

                group_means = enriched_df.groupby(cat_col)[num_col].transform("mean")
                if group_means.std() > 0:
                    enriched_df[feat_name] = np.round(group_means, 4)
                    budget_guard.record_derived_columns(1)
                    interaction_features.append(
                        DerivedFeature(
                            name=feat_name,
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
                        valid_mask = s2 > 0
                        res = pd.Series(np.nan, index=enriched_df.index, dtype=float)
                        res.loc[valid_mask] = np.round(s1.loc[valid_mask] / s2.loc[valid_mask], 4)

                        # Verify standard deviation > 0
                        if res.std() > 0:
                            enriched_df[ratio_name] = res
                            budget_guard.record_derived_columns(1)
                            interaction_features.append(
                                DerivedFeature(
                                    name=ratio_name,
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
