"""Controlled Semantic Data Enrichment & Scientific Feature Discovery Pipeline Orchestrator.

Executes all 11 stages deterministically within configurable resource limits:
1. Data Profiling
2. Semantic Typing
3. Column Relationship Discovery
4. Semantic Column Grouping (G1...Gf)
5. Normalization
6. Primitive Feature Derivation
7. Formula Discovery & Domain Reasoning
8. Scientific Features
9. Interaction Features
10. Analytical Tables
11. Utility Evaluation & Pruning
"""

from __future__ import annotations

import logging
from typing import Any
import pandas as pd

from .config import BudgetGuard, EnrichmentConfig
from .models import EnrichedDatasetPackage
from .profiler import (
    EnrichmentProfiler,
    PERCENTAGE_PATTERN,
    CURRENCY_PATTERN,
    DISTANCE_PATTERN,
    MASS_PATTERN,
    VOLUME_PATTERN,
    SPEED_PATTERN,
    TIME_DURATION_PATTERN,
    TEMPERATURE_PATTERN,
    DATE_PATTERN,
)
from .relationship_engine import ColumnRelationshipEngine
from .column_grouping import ColumnGroupingEngine
from .primitive_deriver import PrimitiveFeatureDeriver
from .formula_engine import ScientificFormulaEngine
from .interaction_engine import InteractionFeatureEngine
from .table_synthesizer import AnalyticalTableSynthesizer
from .utility_evaluator import FeatureUtilityEvaluator

logger = logging.getLogger(__name__)


class ControlledEnrichmentPipeline:
    """Master orchestrator executing the 11-stage controlled semantic enrichment pipeline."""

    @classmethod
    def enrich_dataset(
        cls,
        df: pd.DataFrame,
        dataset_id: str = "dataset_s1",
        config: EnrichmentConfig | None = None
    ) -> tuple[pd.DataFrame, EnrichedDatasetPackage]:
        cfg = config or EnrichmentConfig()
        budget = BudgetGuard(cfg)

        orig_rows, orig_cols = df.shape
        logger.info(f"Starting Controlled Semantic Enrichment for {dataset_id} ({orig_rows} rows x {orig_cols} cols).")

        # Stage 0: Safe Automatic Type Coercion for String-encoded Numerics
        # Preserve text columns, dates, and measurement strings with physical units
        cleaned_df = df.copy()
        for col in cleaned_df.columns:
            if not pd.api.types.is_numeric_dtype(cleaned_df[col]):
                non_null_series = cleaned_df[col].dropna().astype(str).str.strip()
                if len(non_null_series) == 0:
                    continue
                sample_vals = non_null_series.iloc[:30].tolist()
                has_unit_or_date = any(
                    PERCENTAGE_PATTERN.match(v) or CURRENCY_PATTERN.match(v) or
                    DISTANCE_PATTERN.match(v) or MASS_PATTERN.match(v) or
                    VOLUME_PATTERN.match(v) or SPEED_PATTERN.match(v) or
                    TIME_DURATION_PATTERN.match(v) or TEMPERATURE_PATTERN.match(v) or
                    DATE_PATTERN.match(v)
                    for v in sample_vals
                )
                if not has_unit_or_date:
                    converted = pd.to_numeric(cleaned_df[col].astype(str).str.replace(',', ''), errors='coerce')
                    valid_ratio = converted.notna().sum() / max(1, len(non_null_series))
                    if valid_ratio >= 0.8:
                        cleaned_df[col] = converted

        # Stage 1 & 2: Data Profiling & Multi-Role Semantic Typing
        profiles = EnrichmentProfiler.profile_dataset(cleaned_df)

        # Stage 3: Column Relationship Discovery
        relationships = ColumnRelationshipEngine.discover_relationships(cleaned_df, profiles, cfg)

        # Stage 4: Semantic Column Grouping (G1...Gf)
        groups = ColumnGroupingEngine.group_columns(list(cleaned_df.columns), relationships, profiles, cfg.min_relationship_score)

        # Stage 5 & 6: Morphological Normalization & Primitive Feature Derivation
        df_primitives, primitive_features = PrimitiveFeatureDeriver.derive_primitives(cleaned_df, profiles, budget)

        # Update profiles for newly derived columns to allow formula & interaction discovery
        all_profiles = dict(profiles)
        for feat in primitive_features:
            if feat.name in df_primitives.columns:
                all_profiles[feat.name] = EnrichmentProfiler.profile_column(feat.name, df_primitives[feat.name].tolist())

        # Stage 7 & 8: Scientific Formula Discovery & Domain Reasoning
        df_formulas, formula_features = ScientificFormulaEngine.discover_formulas(
            df_primitives, groups, all_profiles, budget, cfg
        )

        for feat in formula_features:
            if feat.name in df_formulas.columns:
                all_profiles[feat.name] = EnrichmentProfiler.profile_column(feat.name, df_formulas[feat.name].tolist())

        # Stage 9: Interaction Features (Ratios, Group Means, Cross-features)
        df_interactions, interaction_features = InteractionFeatureEngine.derive_interactions(
            df_formulas, all_profiles, budget, cfg
        )

        # Combine all derived features before final pruning
        all_derived_features = primitive_features + formula_features + interaction_features

        # Stage 10: Analytical Tables Synthesis
        analytical_tables = AnalyticalTableSynthesizer.synthesize_tables(
            df_interactions, all_profiles, budget, cfg
        )

        # Stage 11: Utility Evaluation & Hard Ceiling Pruning
        final_df, retained_features = FeatureUtilityEvaluator.evaluate_and_prune(
            original_df=cleaned_df,
            enriched_df=df_interactions,
            derived_features=all_derived_features,
            config=cfg
        )

        final_rows, final_cols = final_df.shape
        budget_summary = budget.get_summary()

        logger.info(
            f"Completed Controlled Semantic Enrichment for {dataset_id}: "
            f"Expanded from {orig_cols} to {final_cols} columns (+{len(retained_features)} derived), "
            f"{len(analytical_tables)} analytical tables materialized in {budget_summary['elapsed_seconds']}s."
        )

        pkg = EnrichedDatasetPackage(
            dataset_id=dataset_id,
            original_row_count=orig_rows,
            original_col_count=orig_cols,
            enriched_row_count=final_rows,
            enriched_col_count=final_cols,
            column_profiles=profiles,
            relationships=relationships,
            semantic_groups=groups,
            derived_features=retained_features,
            analytical_tables=analytical_tables,
            budget_summary=budget_summary
        )

        return final_df, pkg
