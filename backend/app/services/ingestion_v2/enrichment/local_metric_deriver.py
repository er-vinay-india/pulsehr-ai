"""
HighView Ingestion V2 — Local Metric Deriver
Stage 9: Controlled Enrichment
Derives intra-table governed metrics strictly within the same logical table and governed grain.

Invariants:
1. Same logical table only. Zero cross-table reads.
2. Same governed grain only.
3. Existing validated columns only.
4. Unit compatibility verified. Incompatible units (e.g. USD vs EUR, kg vs tonnes) strictly blocked.
5. Preserves full denominator semantics for ratios and entity semantics for counts.
6. Transitive provenance: traces metric -> columns -> table -> normalized storage coordinates.
7. Evidence links: references upstream EVID-* findings without duplicating analytical numbers into definitions.
"""

from typing import Any, Sequence
from pydantic import BaseModel, ConfigDict, Field

from app.services.ingestion_v2.contracts.enrichment import (
    LocalDerivedMetric,
    MetricAdditivity,
)
from app.services.ingestion_v2.enrichment.metric_identity import (
    compute_metric_fingerprint,
    MetricRegistry,
)


class LocalMetricCandidateSpec(BaseModel):
    """Specification for deriving a local metric."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_name: str
    formula: str
    source_table_id: str
    source_column_ids: list[str]
    target_grain: str
    unit: str | None = None
    numerator_definition: str | None = None
    denominator_definition: str | None = None
    additivity: MetricAdditivity = MetricAdditivity.NON_ADDITIVE
    null_policy: str = "EXCLUDE"
    filter_policy: str = "ALL"
    display_aliases: list[str] = Field(default_factory=list)
    concept: str | None = None


class IncompatibleUnitError(Exception):
    """Raised when attempting to derive a metric from columns with incompatible units."""
    pass


class InvalidLocalMetricSourceError(Exception):
    """Raised when source columns do not exist in the specified table or grain does not match."""
    pass


class LocalMetricDeriver:
    """
    Governed Intra-Table Metric Deriver.
    Enforces strict grain, unit, and single-table boundaries.
    """

    def __init__(self, registry: MetricRegistry | None = None) -> None:
        self.registry = registry or MetricRegistry()

    def derive_metric(
        self,
        spec: LocalMetricCandidateSpec,
        *,
        table_columns: Sequence[str] | dict[str, Any],
        column_units: dict[str, str | None] | None = None,
        table_grain: str,
        provenance_coords: list[str] | None = None,
        evidence_refs: list[str] | None = None,
    ) -> LocalDerivedMetric:
        """
        Derives a single local metric after validating table, grain, column existence, and units.
        """
        # 1. Grain alignment check
        if spec.target_grain.strip().upper() != table_grain.strip().upper():
            raise InvalidLocalMetricSourceError(
                f"Grain mismatch: candidate grain '{spec.target_grain}' != table grain '{table_grain}'"
            )

        # 2. Column existence check
        existing_cols = set(table_columns.keys() if isinstance(table_columns, dict) else table_columns)
        for col in spec.source_column_ids:
            if col not in existing_cols:
                raise InvalidLocalMetricSourceError(
                    f"Column '{col}' does not exist in table '{spec.source_table_id}'. Valid columns: {sorted(list(existing_cols))}"
                )

        # 3. Unit safety check
        units = column_units or {}
        if len(spec.source_column_ids) >= 2:
            # Check unit compatibility for additive / subtractive formulas
            if spec.additivity in (MetricAdditivity.ADDITIVE, MetricAdditivity.SEMI_ADDITIVE, MetricAdditivity.NON_ADDITIVE):
                col_u = [units.get(c) for c in spec.source_column_ids if units.get(c)]
                if len(col_u) >= 2 and len(set(col_u)) > 1:
                    raise IncompatibleUnitError(
                        f"Incompatible units detected across source columns {spec.source_column_ids}: {col_u}. "
                        "Cannot derive metric across differing units without explicit conversion."
                    )

        # 4. Numerator & Denominator semantic preservation for ratios
        num_def = spec.numerator_definition
        den_def = spec.denominator_definition
        if spec.additivity == MetricAdditivity.RATIO:
            if not num_def and len(spec.source_column_ids) >= 1:
                num_def = spec.source_column_ids[0]
            if not den_def and len(spec.source_column_ids) >= 2:
                den_def = spec.source_column_ids[1]

        # 5. Provenance transitivity
        prov_refs = list(provenance_coords or [])
        if not prov_refs:
            prov_refs = [f"{spec.source_table_id}.{c}" for c in spec.source_column_ids]

        # 6. Deterministic fingerprint
        fp = compute_metric_fingerprint(
            formula=spec.formula,
            target_grain=spec.target_grain,
            source_table_ids=[spec.source_table_id],
            source_column_ids=spec.source_column_ids,
            unit=spec.unit,
            additivity=spec.additivity,
            numerator_definition=num_def,
            denominator_definition=den_def,
            filter_policy=spec.filter_policy,
            null_policy=spec.null_policy,
            concept=spec.concept,
        )

        metric_id = f"metric-loc-{fp[:12]}"

        metric = LocalDerivedMetric(
            metric_id=metric_id,
            table_id=spec.source_table_id,
            source_table_id=spec.source_table_id,
            metric_name=spec.metric_name,
            formula=spec.formula,
            source_columns=spec.source_column_ids,
            source_column_ids=spec.source_column_ids,
            unit=spec.unit,
            grain=spec.target_grain,
            target_grain=spec.target_grain,
            numerator_definition=num_def,
            denominator_definition=den_def,
            additivity=spec.additivity,
            null_policy=spec.null_policy,
            filter_policy=spec.filter_policy,
            provenance_refs=prov_refs,
            evidence_refs=list(evidence_refs or []),
            definition_confidence=1.0,
            derivation_method="DETERMINISTIC",
            display_aliases=spec.display_aliases,
            fingerprint=fp,
        )

        return self.registry.register(metric)
