"""
HighView Semantic Data Refinery — Phase SDR-8
Shadow Telemetry Ledger & Isolated File-Based Storage

Enforces:
1. P0 Database Isolation: ZERO writes to pulsehr.sqlite3 database.
2. Independent per-consumer telemetry (HRIDAY, Dashboard, Presentation).
3. Complete failure isolation: errors in telemetry capture never impact user response.
4. Aggregates metrics:
   - Requests, SDR available/unavailable/stale/blocked counts
   - Comparison classes: UNCHANGED, EXPECTED_IMPROVEMENT, EXPECTED_DIFFERENCE, REGRESSION, UNRESOLVED
   - Latencies (V2, SDR shadow, comparison)
   - Zero invariants: V2 failures caused by SDR (0), user-visible substitutions (0)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.core import config
from app.services.sdr.shadow.contracts import (
    ComparisonClass,
    DisagreementType,
    SDRShadowEvaluation,
    ShadowConsumerType,
    ShadowTelemetrySummary,
)

logger = logging.getLogger(__name__)


class ShadowTelemetryLedger:
    """
    Manages in-memory and file-based shadow telemetry outside of P0.
    """

    def __init__(self, base_data_dir: Path | str | None = None):
        if base_data_dir is not None:
            self.base_dir = Path(base_data_dir)
        else:
            self.base_dir = getattr(config, "DATA_DIR", Path("data"))

        self._summaries: dict[ShadowConsumerType, ShadowTelemetrySummary] = {
            ShadowConsumerType.HRIDAY: ShadowTelemetrySummary(consumer=ShadowConsumerType.HRIDAY),
            ShadowConsumerType.DASHBOARD: ShadowTelemetrySummary(consumer=ShadowConsumerType.DASHBOARD),
            ShadowConsumerType.PRESENTATION: ShadowTelemetrySummary(consumer=ShadowConsumerType.PRESENTATION),
        }
        self._evaluations: list[SDRShadowEvaluation] = []

    def record_evaluation(self, evaluation: SDRShadowEvaluation) -> None:
        """Records an evaluation and updates in-memory counters and filesystem store."""
        self._evaluations.append(evaluation)
        summary = self._summaries[evaluation.consumer]
        summary.total_requests += 1

        if evaluation.sdr_status == "AVAILABLE":
            summary.sdr_available_count += 1
        elif evaluation.sdr_status == "STALE":
            summary.sdr_stale_count += 1
            summary.sdr_unavailable_count += 1
        elif evaluation.sdr_status == "UNSAFE_BLOCKED":
            summary.unsafe_blocked_count += 1
            summary.sdr_unavailable_count += 1
        elif evaluation.sdr_status == "AMBIGUOUS_BLOCKED":
            summary.ambiguous_blocked_count += 1
            summary.sdr_unavailable_count += 1
        else:
            summary.sdr_unavailable_count += 1

        # Class counts
        if evaluation.comparison_class == ComparisonClass.UNCHANGED:
            summary.unchanged_count += 1
        elif evaluation.comparison_class == ComparisonClass.EXPECTED_IMPROVEMENT:
            summary.expected_improvement_count += 1
        elif evaluation.comparison_class == ComparisonClass.EXPECTED_DIFFERENCE:
            summary.expected_difference_count += 1

        # Difference type counts
        if evaluation.difference_type == DisagreementType.REGRESSION:
            summary.regression_count += 1
        elif evaluation.difference_type == DisagreementType.UNRESOLVED:
            summary.unresolved_count += 1

        # Latency samples
        if "v2_latency_ms" in evaluation.latency:
            summary.v2_latency_samples.append(evaluation.latency["v2_latency_ms"])
        if "sdr_latency_ms" in evaluation.latency:
            summary.sdr_latency_samples.append(evaluation.latency["sdr_latency_ms"])
        if "comparison_latency_ms" in evaluation.latency:
            summary.comparison_latency_samples.append(evaluation.latency["comparison_latency_ms"])

        # Persist to dataset SDR directory (Outside P0)
        try:
            self._persist_evaluation_to_disk(evaluation)
        except Exception as exc:
            logger.warning("Failed to persist shadow evaluation to disk: %s", exc)

    def _persist_evaluation_to_disk(self, evaluation: SDRShadowEvaluation) -> None:
        """Saves evaluation in dataset sdr directory outside P0 SQLite."""
        target_dir = Path(self.base_dir) / "datasets" / str(evaluation.dataset_id) / "sdr"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / "shadow_telemetry.jsonl"
        with open(target_file, "a", encoding="utf-8") as f:
            f.write(evaluation.model_dump_json() + "\n")

    def get_summary(self, consumer: ShadowConsumerType) -> ShadowTelemetrySummary:
        return self._summaries[consumer]

    def get_all_summaries(self) -> dict[str, Any]:
        result = {}
        for c, s in self._summaries.items():
            v2_l = s.v2_latency_samples
            sdr_l = s.sdr_latency_samples
            cmp_l = s.comparison_latency_samples

            result[c.value] = {
                "total_requests": s.total_requests,
                "sdr_available": s.sdr_available_count,
                "sdr_unavailable": s.sdr_unavailable_count,
                "sdr_stale": s.sdr_stale_count,
                "unsafe_blocked": s.unsafe_blocked_count,
                "ambiguous_blocked": s.ambiguous_blocked_count,
                "UNCHANGED": s.unchanged_count,
                "EXPECTED_IMPROVEMENT": s.expected_improvement_count,
                "EXPECTED_DIFFERENCE": s.expected_difference_count,
                "REGRESSION": s.regression_count,
                "UNRESOLVED": s.unresolved_count,
                "v2_failures_caused_by_sdr": s.v2_failures_caused_by_sdr,
                "user_visible_substitutions": s.user_visible_substitutions,
                "latencies_ms": {
                    "v2_p50": round(sorted(v2_l)[len(v2_l) // 2], 2) if v2_l else 0.0,
                    "sdr_p50": round(sorted(sdr_l)[len(sdr_l) // 2], 2) if sdr_l else 0.0,
                    "comparison_p50": round(sorted(cmp_l)[len(cmp_l) // 2], 2) if cmp_l else 0.0,
                },
            }
        return result

    def reset(self) -> None:
        """Resets in-memory counters (for hermetic testing)."""
        self._summaries = {
            ShadowConsumerType.HRIDAY: ShadowTelemetrySummary(consumer=ShadowConsumerType.HRIDAY),
            ShadowConsumerType.DASHBOARD: ShadowTelemetrySummary(consumer=ShadowConsumerType.DASHBOARD),
            ShadowConsumerType.PRESENTATION: ShadowTelemetrySummary(consumer=ShadowConsumerType.PRESENTATION),
        }
        self._evaluations.clear()


_shared_telemetry_ledger: ShadowTelemetryLedger | None = None


def get_shadow_telemetry_ledger() -> ShadowTelemetryLedger:
    global _shared_telemetry_ledger
    if _shared_telemetry_ledger is None:
        _shared_telemetry_ledger = ShadowTelemetryLedger()
    return _shared_telemetry_ledger
