"""
Profiling Adapter combining Visions type detection, statistical distribution analysis,
and robust column characterization.
"""

from typing import Dict, Any, List, Optional
import logging
import pandas as pd
import numpy as np
from .statistical_adapter import StatisticalAdapter

logger = logging.getLogger(__name__)

class ProfilingAdapter:
    """
    Adapter providing advanced profiling and type discovery using Visions and SciPy.
    """

    def __init__(self, visions_enabled: bool = True):
        self.visions_enabled = visions_enabled
        self.stat_adapter = StatisticalAdapter(enabled=True)
        self._typeset = None
        if self.visions_enabled:
            self._init_visions()

    def _init_visions(self):
        try:
            import visions
            self._typeset = visions.StandardSet()
        except Exception as e:
            logger.debug("Visions initialization notice: %s", e)
            self._typeset = None

    def infer_visions_type(self, series: pd.Series) -> Optional[str]:
        """Infers semantic/physical type using Visions type rules."""
        if not self._typeset or series.dropna().empty:
            return None
        try:
            # Detect type via visions
            v_type = self._typeset.detect_type(series)
            return str(v_type)
        except Exception as e:
            logger.debug("Visions type inference error for %s: %s", series.name, e)
            return None

    def profile_series(self, series: pd.Series) -> Dict[str, Any]:
        """
        Calculates comprehensive statistical and structural metrics for a column.
        """
        clean = series.dropna()
        n_total = len(series)
        n_missing = n_total - len(clean)
        null_ratio = float(n_missing / n_total) if n_total > 0 else 0.0
        unique_cnt = int(series.nunique())

        is_num = pd.api.types.is_numeric_dtype(series)

        profile: Dict[str, Any] = {
            "name": str(series.name),
            "total_count": n_total,
            "null_count": n_missing,
            "null_ratio": round(null_ratio, 4),
            "unique_count": unique_cnt,
            "unique_ratio": round(unique_cnt / n_total, 4) if n_total > 0 else 0.0,
            "is_numeric": bool(is_num),
            "dtype": str(series.dtype),
        }

        # Visions type
        v_type = self.infer_visions_type(series)
        if v_type:
            profile["visions_type"] = v_type

        if is_num and len(clean) > 0:
            numeric_vals = clean.to_numpy(dtype=float)
            profile["min"] = float(np.min(numeric_vals))
            profile["max"] = float(np.max(numeric_vals))
            profile["mean"] = float(np.mean(numeric_vals))
            profile["median"] = float(np.median(numeric_vals))
            profile["zeros_count"] = int(np.sum(numeric_vals == 0))
            profile["negatives_count"] = int(np.sum(numeric_vals < 0))

            # Advanced moments via SciPy
            moments = self.stat_adapter.compute_moments(clean)
            profile.update(moments)
        else:
            profile["min"] = None
            profile["max"] = None
            profile["mean"] = None
            profile["median"] = None
            profile["skewness"] = 0.0
            profile["kurtosis"] = 0.0
            profile["iqr"] = 0.0

        return profile
