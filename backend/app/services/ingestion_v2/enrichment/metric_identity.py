"""
HighView Ingestion V2 — Metric Identity & Fingerprinting
Stage 9: Controlled Enrichment
Provides deterministic SHA-256 fingerprinting and alias deduplication for governed metrics.

Invariants:
1. Fingerprints are stable and deterministic: excluded from timestamps, run_ids, and wording aliases.
2. Equivalent definitions across different alias names resolve to ONE canonical metric with aliases preserved.
3. Identical names with different formulas/grains/denominators produce DISTINCT fingerprints and remain separate.
"""

import hashlib
import json
import re
from typing import Any, TypeVar, Union
from app.services.ingestion_v2.contracts.enrichment import (
    LocalDerivedMetric,
    RelationalDerivedMetric,
    MetricAdditivity,
)

TMetric = TypeVar("TMetric", LocalDerivedMetric, RelationalDerivedMetric)


def normalize_formula(formula: str) -> str:
    """Normalize formula string: trim, collapse spaces, normalize operators."""
    if not formula:
        return ""
    # Collapse multiple whitespace characters into a single space
    s = re.sub(r"\s+", " ", formula.strip().lower())
    # Normalize common operators
    s = s.replace(" / ", "/").replace(" * ", "*").replace(" + ", "+").replace(" - ", "-")
    return s


def compute_metric_fingerprint(
    *,
    formula: str,
    target_grain: str,
    source_table_ids: list[str],
    source_column_ids: list[str],
    unit: str | None = None,
    additivity: Union[MetricAdditivity, str] = MetricAdditivity.NON_ADDITIVE,
    numerator_definition: str | None = None,
    denominator_definition: str | None = None,
    filter_policy: str = "ALL",
    null_policy: str = "EXCLUDE",
    join_plan_id: str | None = None,
    concept: str | None = None,
) -> str:
    """
    Computes a canonical SHA-256 fingerprint for a derived metric.
    Includes only semantic identity fields. Strictly excludes display labels,
    timestamps, and runtime identifiers.
    """
    additivity_str = additivity.value if isinstance(additivity, MetricAdditivity) else str(additivity)

    payload = {
        "formula": normalize_formula(formula),
        "target_grain": (target_grain or "").strip().upper(),
        "source_tables": sorted(list(set(source_table_ids))),
        "source_columns": sorted(list(set(source_column_ids))),
        "unit": (unit or "").strip().lower() if unit else None,
        "additivity": additivity_str.upper(),
        "numerator": normalize_formula(numerator_definition) if numerator_definition else None,
        "denominator": normalize_formula(denominator_definition) if denominator_definition else None,
        "filter_policy": (filter_policy or "").strip().upper(),
        "null_policy": (null_policy or "").strip().upper(),
        "join_plan_id": (join_plan_id or "").strip() if join_plan_id else None,
        "concept": (concept or "").strip().upper() if concept else None,
    }
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class MetricRegistry:
    """
    Governed deduplication and canonical metric registry.
    Resolves duplicate aliases with identical fingerprints into 1 canonical metric.
    Prevents colliding metrics with the same name but different definitions from overwriting.
    """

    def __init__(self) -> None:
        self._metrics_by_fp: dict[str, Union[LocalDerivedMetric, RelationalDerivedMetric]] = {}
        self._metrics_by_id: dict[str, Union[LocalDerivedMetric, RelationalDerivedMetric]] = {}

    @property
    def metrics(self) -> list[Union[LocalDerivedMetric, RelationalDerivedMetric]]:
        return list(self._metrics_by_fp.values())

    def get_by_fingerprint(self, fp: str) -> Union[LocalDerivedMetric, RelationalDerivedMetric, None]:
        return self._metrics_by_fp.get(fp)

    def get_by_id(self, metric_id: str) -> Union[LocalDerivedMetric, RelationalDerivedMetric, None]:
        return self._metrics_by_id.get(metric_id)

    def register(self, metric: TMetric) -> TMetric:
        """
        Registers a derived metric.
        If an identical metric already exists (by fingerprint):
        - merges display aliases
        - returns the existing canonical metric
        If the metric is novel:
        - registers and returns it
        """
        fp = metric.fingerprint
        if not fp:
            # Compute if not pre-populated
            if isinstance(metric, LocalDerivedMetric):
                fp = compute_metric_fingerprint(
                    formula=metric.formula,
                    target_grain=metric.target_grain or metric.grain,
                    source_table_ids=[metric.source_table_id or metric.table_id],
                    source_column_ids=metric.source_column_ids or metric.source_columns,
                    unit=metric.unit,
                    additivity=metric.additivity,
                    numerator_definition=metric.numerator_definition,
                    denominator_definition=metric.denominator_definition,
                    filter_policy=metric.filter_policy,
                    null_policy=metric.null_policy,
                )
            else:
                fp = compute_metric_fingerprint(
                    formula=metric.formula,
                    target_grain=metric.target_grain,
                    source_table_ids=metric.source_table_ids,
                    source_column_ids=metric.source_column_ids,
                    unit=metric.unit,
                    additivity=metric.additivity,
                    numerator_definition=metric.numerator_definition,
                    denominator_definition=metric.denominator_definition,
                    filter_policy=metric.filter_policy,
                    null_policy=metric.null_policy,
                    join_plan_id=metric.join_plan_id,
                )
            # Reconstruct with fingerprint
            metric = metric.model_copy(update={"fingerprint": fp})

        if fp in self._metrics_by_fp:
            # Canonical match found: merge display aliases
            existing = self._metrics_by_fp[fp]
            existing_aliases = set(existing.display_aliases)
            existing_aliases.add(metric.metric_name)
            for alias in metric.display_aliases:
                existing_aliases.add(alias)
            # Sort aliases deterministically
            updated_existing = existing.model_copy(
                update={"display_aliases": sorted(list(existing_aliases))}
            )
            self._metrics_by_fp[fp] = updated_existing
            self._metrics_by_id[updated_existing.metric_id] = updated_existing
            return updated_existing  # type: ignore

        # Novel metric
        aliases = set(metric.display_aliases)
        aliases.add(metric.metric_name)
        final_metric = metric.model_copy(
            update={
                "fingerprint": fp,
                "display_aliases": sorted(list(aliases)),
            }
        )
        self._metrics_by_fp[fp] = final_metric
        self._metrics_by_id[final_metric.metric_id] = final_metric
        return final_metric  # type: ignore
