"""
Feature Synthesis Adapter wrapping Featuretools for automated Deep Feature Synthesis (DFS)
within semantic groups and bounded computational limits.
Includes compatibility bridge for pandas 3.0+ and Woodwork accessor persistence.
"""

from typing import List, Dict, Any, Optional, Tuple
import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Ensure Woodwork handles pandas 3.0 accessor recreation
_woodwork_patched = False

def _ensure_woodwork_compat():
    global _woodwork_patched
    if _woodwork_patched:
        return
    try:
        from woodwork.table_accessor import WoodworkTableAccessor
        from woodwork.column_accessor import WoodworkColumnAccessor

        # Table accessor patch
        orig_table_init = WoodworkTableAccessor.__init__
        def new_table_init(self, dataframe):
            orig_table_init(self, dataframe)
            if hasattr(dataframe, '_ww_schema'):
                self._schema = dataframe._ww_schema
        WoodworkTableAccessor.__init__ = new_table_init

        orig_table_init_partial = WoodworkTableAccessor.init_with_partial_schema
        def new_table_init_partial(self, *args, **kwargs):
            orig_table_init_partial(self, *args, **kwargs)
            self._dataframe._ww_schema = self._schema
        WoodworkTableAccessor.init_with_partial_schema = new_table_init_partial

        # Column accessor patch
        orig_col_init = WoodworkColumnAccessor.__init__
        def new_col_init(self, series):
            orig_col_init(self, series)
            if hasattr(series, '_ww_schema'):
                self._schema = series._ww_schema
        WoodworkColumnAccessor.__init__ = new_col_init

        orig_col_init_method = WoodworkColumnAccessor.init
        def new_col_init_method(self, *args, **kwargs):
            orig_col_init_method(self, *args, **kwargs)
            self._series._ww_schema = self._schema
        WoodworkColumnAccessor.init = new_col_init_method

        # Patch __getattr__ for dynamic DataFrame calls
        if hasattr(WoodworkTableAccessor.__getattr__, '__wrapped__'):
            orig_getattr = WoodworkTableAccessor.__getattr__.__wrapped__
            def new_getattr(self, attr):
                if self._schema is None:
                    self.init(validate=False)
                return orig_getattr(self, attr)
            WoodworkTableAccessor.__getattr__ = new_getattr

        _woodwork_patched = True
        logger.debug("Woodwork compatibility bridge for pandas 3+ applied successfully")
    except Exception as e:
        logger.warning("Could not apply woodwork compatibility bridge: %s", e)


class FeatureSynthesisAdapter:
    """
    Adapter providing automated feature derivation using Featuretools DFS.
    Constrained by semantic column boundaries and strict budget quotas.
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        if self.enabled:
            _ensure_woodwork_compat()

    def synthesize_features_for_group(
        self,
        df: pd.DataFrame,
        group_columns: List[str],
        max_features: int = 20,
        max_depth: int = 1
    ) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
        """
        Runs Featuretools DFS over a subset of semantically related numeric columns.
        Returns (derived_df, feature_metadata_list).
        """
        if not self.enabled:
            return pd.DataFrame(index=df.index), []

        # Filter available numeric columns in group
        valid_cols = [
            c for c in group_columns
            if c in df.columns and pd.api.types.is_numeric_dtype(df[c])
        ]
        if len(valid_cols) < 2:
            return pd.DataFrame(index=df.index), []

        try:
            import featuretools as ft

            sub_df = df[valid_cols].copy()
            # If no unique index column, create synthetic index
            synth_idx = "__ft_id__"
            sub_df[synth_idx] = np.arange(len(sub_df))

            # Initialize woodwork schema
            sub_df.ww.init(index=synth_idx, name="group_entity")

            # Build EntitySet
            es = ft.EntitySet(id="group_entity_set")
            es = es.add_dataframe(dataframe=sub_df)

            # Restrict trans_primitives to standard safe operations
            trans_primitives = ["add_numeric", "subtract_numeric", "multiply_numeric", "divide_numeric"]

            # Run DFS
            feature_matrix, _ = ft.dfs(
                entityset=es,
                target_dataframe_name="group_entity",
                trans_primitives=trans_primitives,
                max_depth=max_depth,
                max_features=max_features + len(valid_cols) + 1,
                verbose=False
            )

            # Drop original columns and synthetic index
            cols_to_drop = [c for c in valid_cols if c in feature_matrix.columns]
            if synth_idx in feature_matrix.columns:
                cols_to_drop.append(synth_idx)

            derived_matrix = feature_matrix.drop(columns=cols_to_drop, errors="ignore")

            # Slice to budget
            if derived_matrix.shape[1] > max_features:
                derived_matrix = derived_matrix.iloc[:, :max_features]

            # Construct lineage metadata
            feature_metadata = []
            for col in derived_matrix.columns:
                feature_metadata.append({
                    "column_name": str(col),
                    "generator": "featuretools_dfs",
                    "primitive": "dfs_composite",
                    "source_columns": valid_cols,
                    "depth": max_depth
                })

            # Replace inf/-inf with NaN
            derived_matrix = derived_matrix.replace([np.inf, -np.inf], np.nan)
            derived_matrix.index = df.index

            return derived_matrix, feature_metadata

        except Exception as e:
            logger.warning("Featuretools synthesis error: %s", e)
            return pd.DataFrame(index=df.index), []
