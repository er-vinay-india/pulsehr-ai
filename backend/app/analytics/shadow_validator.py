"""
Dual-Path Shadow Validator for Phase G3 Analytical Plane.
Compares legacy SQLite-JSON calculations against DuckDB Parquet calculations
with strict numerical and categorical tolerance.
"""
from __future__ import annotations

import logging
import math
from typing import Any, Sequence

logger = logging.getLogger(__name__)


class NumericalEquivalenceTolerance:
    """Enforces strict tolerance rules between legacy and columnar calculations."""

    FLOAT_REL_TOL = 1e-5
    FLOAT_ABS_TOL = 1e-7

    @classmethod
    def is_close(cls, a: Any, b: Any) -> bool:
        """Evaluates numerical equality with domain-appropriate tolerances."""
        if a is None and b is None:
            return True
        if a is None or b is None:
            return False

        # Attempt float conversion
        try:
            fa = float(a)
            fb = float(b)
            if math.isnan(fa) and math.isnan(fb):
                return True
            return math.isclose(fa, fb, rel_tol=cls.FLOAT_REL_TOL, abs_tol=cls.FLOAT_ABS_TOL)
        except (ValueError, TypeError):
            # Categorical string comparison
            return str(a).strip() == str(b).strip()

    @classmethod
    def compare_record_lists(
        cls,
        legacy_records: Sequence[dict[str, Any]],
        duckdb_records: Sequence[dict[str, Any]],
        key_fields: Sequence[str] = (),
        metric_fields: Sequence[str] = (),
    ) -> tuple[bool, list[str]]:
        """Compares two record lists and returns (is_equivalent, list_of_discrepancies)."""
        discrepancies: list[str] = []

        if len(legacy_records) != len(duckdb_records):
            discrepancies.append(
                f"Row count mismatch: legacy={len(legacy_records)} vs duckdb={len(duckdb_records)}"
            )
            return False, discrepancies

        # Compare row by row or key by key
        for idx, (leg, ddb) in enumerate(zip(legacy_records, duckdb_records)):
            # Check key fields
            for k in key_fields:
                val_leg = leg.get(k)
                val_ddb = ddb.get(k)
                if not cls.is_close(val_leg, val_ddb):
                    discrepancies.append(
                        f"Row {idx} key '{k}' mismatch: legacy={val_leg} vs duckdb={val_ddb}"
                    )

            # Check metric fields
            for m in metric_fields:
                val_leg = leg.get(m)
                val_ddb = ddb.get(m)
                if not cls.is_close(val_leg, val_ddb):
                    discrepancies.append(
                        f"Row {idx} metric '{m}' mismatch: legacy={val_leg} vs duckdb={val_ddb}"
                    )

        is_equiv = len(discrepancies) == 0
        return is_equiv, discrepancies


class ShadowValidator:
    """Orchestrates shadow execution and telemetry recording."""

    discrepancy_log: list[dict[str, Any]] = []

    @classmethod
    def record_comparison(
        cls,
        operation: str,
        dataset_id: int,
        is_equivalent: bool,
        discrepancies: list[str],
        legacy_ms: float,
        duckdb_ms: float,
    ) -> None:
        entry = {
            "operation": operation,
            "dataset_id": dataset_id,
            "is_equivalent": is_equivalent,
            "discrepancies": discrepancies,
            "legacy_ms": legacy_ms,
            "duckdb_ms": duckdb_ms,
            "speedup": f"{(legacy_ms / max(0.001, duckdb_ms)):.1f}x",
        }
        cls.discrepancy_log.append(entry)
        if not is_equivalent:
            logger.warning(
                "Shadow discrepancy in %s for dataset %s: %s",
                operation,
                dataset_id,
                discrepancies[:3],
            )
        else:
            logger.debug(
                "Shadow equivalence confirmed for %s (%s speedup)",
                operation,
                entry["speedup"],
            )

    @classmethod
    def get_discrepancy_count(cls) -> int:
        return sum(1 for e in cls.discrepancy_log if not e["is_equivalent"])

    @classmethod
    def reset(cls) -> None:
        cls.discrepancy_log.clear()
