"""
Statistical Adapter wrapping SciPy and Scikit-Learn for advanced moment analysis,
nonlinear dependence detection, and robust statistical profiling.
"""

from typing import Dict, Any, Optional, Tuple
import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

class StatisticalAdapter:
    """
    Adapter providing statistical calculations using scipy.stats and scikit-learn.
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def compute_moments(self, series: pd.Series) -> Dict[str, Any]:
        """
        Computes mean, variance, skewness, kurtosis, and IQR.
        """
        clean = series.dropna()
        if len(clean) < 3:
            return {
                "skewness": 0.0,
                "kurtosis": 0.0,
                "iqr": 0.0,
                "std": 0.0
            }

        try:
            from scipy import stats
            vals = clean.to_numpy(dtype=float)
            skew_val = float(stats.skew(vals, nan_policy='omit'))
            kurt_val = float(stats.kurtosis(vals, nan_policy='omit'))
            iqr_val = float(stats.iqr(vals, nan_policy='omit'))
            std_val = float(np.std(vals))
            return {
                "skewness": skew_val if not np.isnan(skew_val) else 0.0,
                "kurtosis": kurt_val if not np.isnan(kurt_val) else 0.0,
                "iqr": iqr_val if not np.isnan(iqr_val) else 0.0,
                "std": std_val if not np.isnan(std_val) else 0.0
            }
        except Exception as e:
            logger.debug("Scipy moments computation fallback: %s", e)
            return {
                "skewness": float(clean.skew()) if hasattr(clean, 'skew') else 0.0,
                "kurtosis": float(clean.kurt()) if hasattr(clean, 'kurt') else 0.0,
                "iqr": float(clean.quantile(0.75) - clean.quantile(0.25)),
                "std": float(clean.std())
            }

    def compute_correlations(
        self,
        s1: pd.Series,
        s2: pd.Series
    ) -> Dict[str, float]:
        """
        Computes Pearson, Spearman, and Kendall Tau correlations between two numerical series.
        """
        df = pd.DataFrame({"a": s1, "b": s2}).dropna()
        if len(df) < 5 or df["a"].nunique() <= 1 or df["b"].nunique() <= 1:
            return {"pearson": 0.0, "spearman": 0.0, "kendall": 0.0}

        results = {}
        try:
            from scipy import stats
            p_val, _ = stats.pearsonr(df["a"], df["b"])
            s_val, _ = stats.spearmanr(df["a"], df["b"])
            k_val, _ = stats.kendalltau(df["a"], df["b"])
            results["pearson"] = float(p_val) if not np.isnan(p_val) else 0.0
            results["spearman"] = float(s_val) if not np.isnan(s_val) else 0.0
            results["kendall"] = float(k_val) if not np.isnan(k_val) else 0.0
        except Exception as e:
            logger.debug("Scipy correlation computation fallback: %s", e)
            results["pearson"] = float(df["a"].corr(df["b"]))
            results["spearman"] = float(df["a"].corr(df["b"], method="spearman"))
            results["kendall"] = 0.0

        return results

    def compute_mutual_information(
        self,
        s_target: pd.Series,
        s_feature: pd.Series
    ) -> float:
        """
        Computes mutual information between two numerical variables using scikit-learn.
        Captures non-linear dependencies.
        """
        df = pd.DataFrame({"y": s_target, "x": s_feature}).dropna()
        if len(df) < 10 or df["x"].nunique() <= 1 or df["y"].nunique() <= 1:
            return 0.0

        try:
            from sklearn.feature_selection import mutual_info_regression
            X = df[["x"]].to_numpy()
            y = df["y"].to_numpy()
            # Subsample if dataset is large to prevent slow processing
            if len(X) > 1000:
                indices = np.random.choice(len(X), size=1000, replace=False)
                X = X[indices]
                y = y[indices]

            mi = mutual_info_regression(X, y, random_state=42)
            val = float(mi[0])
            return val if not np.isnan(val) and val >= 0 else 0.0
        except Exception as e:
            logger.debug("Mutual information computation error: %s", e)
            return 0.0
