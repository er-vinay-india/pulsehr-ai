"""
Symbolic Relationship Adapter wrapping PySR for symbolic formula discovery.
Protected by strict feature flags and graceful fallbacks when Julia is not available.
"""

from typing import List, Dict, Any, Optional
import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

class SymbolicRelationshipAdapter:
    """
    Adapter providing symbolic equation discovery using PySR.
    Operates within strict time limits and semantic group boundaries.
    """

    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self._pysr_available = False
        if self.enabled:
            self._check_availability()

    def _check_availability(self):
        try:
            import pysr
            self._pysr_available = True
        except Exception as e:
            logger.info("PySR not initialized or unavailable: %s", e)
            self._pysr_available = False

    def is_available(self) -> bool:
        return self.enabled and self._pysr_available

    def discover_symbolic_relationship(
        self,
        df: pd.DataFrame,
        feature_cols: List[str],
        target_col: str,
        max_time_seconds: int = 15
    ) -> Optional[Dict[str, Any]]:
        """
        Runs PySR symbolic regression to discover functional relationships between
        features and a target variable within a semantic group.
        """
        if not self.is_available():
            return None

        # Ensure features and target exist in dataframe
        if target_col not in df.columns or not any(c in df.columns for c in feature_cols):
            return None

        valid_features = [c for c in feature_cols if c in df.columns and c != target_col]
        if not valid_features:
            return None

        try:
            from pysr import PySRRegressor

            # Prepare data
            sub_df = df[valid_features + [target_col]].dropna()
            if len(sub_df) < 15:
                return None

            # Subsample for speed if dataset is large
            if len(sub_df) > 300:
                sub_df = sub_df.sample(n=300, random_state=42)

            X = sub_df[valid_features].to_numpy()
            y = sub_df[target_col].to_numpy()

            # Ensure variance exists
            if np.std(y) < 1e-6 or any(np.std(X[:, i]) < 1e-6 for i in range(X.shape[1])):
                return None

            model = PySRRegressor(
                niterations=15,
                timeout_in_seconds=max_time_seconds,
                binary_operators=["+", "-", "*", "/"],
                unary_operators=["sqrt", "square", "log"],
                maxsize=15,
                verbosity=0,
                progress=False,
                random_state=42
            )

            model.fit(X, y, variable_names=valid_features)

            best_equation = model.get_best()
            if best_equation is None or (hasattr(best_equation, "empty") and best_equation.empty):
                return None

            sympy_expr = str(model.sympy())
            loss = float(best_equation.get("loss", 1.0))
            score = float(best_equation.get("score", 0.0))

            return {
                "target_column": target_col,
                "input_columns": valid_features,
                "expression": sympy_expr,
                "loss": loss,
                "score": score,
                "complexity": int(best_equation.get("complexity", 1)),
                "generator": "pysr_symbolic_regression"
            }

        except Exception as e:
            logger.warning("Symbolic relationship discovery encountered error: %s", e)
            return None
