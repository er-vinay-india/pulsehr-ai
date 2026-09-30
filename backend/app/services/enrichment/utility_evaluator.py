"""Utility Evaluation, Redundancy Pruning, and Bounded Selection Engine (Stage 11).

Evaluates information gain, statistical variance, missingness penalties, and collinearity.
Prunes redundant or low-confidence features down to the exact configurable hard column ceiling.
"""

from __future__ import annotations

import logging
from typing import Any
import numpy as np
import pandas as pd

from .config import EnrichmentConfig
from .models import DerivedFeature

logger = logging.getLogger(__name__)


class FeatureUtilityEvaluator:
    """Evaluates and prunes candidate derived features to maximize information density."""

    @classmethod
    def evaluate_and_prune(
        cls,
        original_df: pd.DataFrame,
        enriched_df: pd.DataFrame,
        derived_features: list[DerivedFeature],
        config: EnrichmentConfig
    ) -> tuple[pd.DataFrame, list[DerivedFeature]]:
        if not derived_features:
            return enriched_df, []

        orig_cols = list(original_df.columns)
        candidate_cols = [f.name for f in derived_features if f.name in enriched_df.columns]
        feature_map = {f.name: f for f in derived_features}

        evaluated_features: list[DerivedFeature] = []

        for col_name in candidate_cols:
            feat = feature_map[col_name]
            series = enriched_df[col_name]

            # 1. Minimum confidence filter
            if feat.confidence < config.min_feature_confidence:
                continue

            # 2. Null penalty
            null_ratio = series.isna().sum() / max(1, len(series))
            if null_ratio > 0.6:
                continue

            # 3. Variance / Constant Check
            if pd.api.types.is_numeric_dtype(series):
                std = series.std()
                if np.isnan(std) or std <= 1e-6:
                    continue
                # Base utility score factoring variance and completeness
                base_utility = feat.utility_score * (1.0 - 0.4 * null_ratio)
            else:
                nunique = series.nunique()
                if nunique <= 1 or nunique == len(series):
                    continue
                base_utility = feat.utility_score * (1.0 - 0.3 * null_ratio)

            feat.utility_score = round(base_utility, 4)
            evaluated_features.append(feat)

        # 4. Collinearity / Redundancy Pruning among numeric features
        evaluated_features.sort(key=lambda f: f.utility_score, reverse=True)
        retained_features: list[DerivedFeature] = []
        retained_numeric_series: list[pd.Series] = []

        for feat in evaluated_features:
            series = enriched_df[feat.name]
            if pd.api.types.is_numeric_dtype(series):
                is_redundant = False
                clean_s = pd.to_numeric(series, errors='coerce').fillna(0)
                for existing_s in retained_numeric_series:
                    corr = np.corrcoef(clean_s, existing_s)[0, 1]
                    if not np.isnan(corr) and abs(corr) >= 0.98:
                        is_redundant = True
                        break
                if not is_redundant:
                    retained_features.append(feat)
                    retained_numeric_series.append(clean_s)
            else:
                retained_features.append(feat)

        # 5. Enforce Hard Column Ceiling (max_derived_columns)
        if len(retained_features) > config.max_derived_columns:
            logger.info(
                f"Pruning derived features from {len(retained_features)} down to hard ceiling {config.max_derived_columns}."
            )
            retained_features = retained_features[:config.max_derived_columns]

        # Assemble final pruned DataFrame
        final_cols = orig_cols + [f.name for f in retained_features if f.name not in orig_cols]
        final_df = enriched_df[final_cols].copy()

        return final_df, retained_features
