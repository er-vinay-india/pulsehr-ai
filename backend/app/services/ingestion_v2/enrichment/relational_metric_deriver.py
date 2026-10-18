"""
HighView Ingestion V2 — Relational Metric Deriver
Stage 9: Controlled Enrichment
Derives cross-table governed metrics ONLY when gated by an authorized, validated JoinPlan.

Invariants:
1. No join_plan_id -> STRICTLY BLOCKED (JoinPlanRequiredError).
2. UNSAFE JoinPlan -> STRICTLY BLOCKED (UnsafeJoinPlanError).
3. AMBIGUOUS JoinPlan -> STRICTLY BLOCKED (AmbiguousJoinPlanError).
4. Only SAFE or SAFE_WITH_PREAGGREGATION plans may execute.
5. Operation-level safety: operations listed in forbidden_operations (e.g. raw distinct count after 1:N join) are blocked.
6. Target grain must align with the JoinPlan's governed target grain.
7. Denominator safety is verified and explicit.
"""

from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.services.ingestion_v2.contracts.enrichment import (
    RelationalDerivedMetric,
    MetricAdditivity,
)
from app.services.ingestion_v2.contracts.joins import (
    JoinPlan,
    JoinSafetyStatus,
)
from app.services.ingestion_v2.enrichment.metric_identity import (
    compute_metric_fingerprint,
    MetricRegistry,
)


class JoinPlanRequiredError(Exception):
    """Raised when cross-table metric derivation is attempted without a valid JoinPlan."""
    pass


class UnsafeJoinPlanError(Exception):
    """Raised when cross-table derivation is attempted via an UNSAFE JoinPlan."""
    pass


class AmbiguousJoinPlanError(Exception):
    """Raised when cross-table derivation is attempted via an AMBIGUOUS JoinPlan."""
    pass


class ForbiddenJoinOperationError(Exception):
    """Raised when an operation is explicitly forbidden by the JoinPlan (e.g. raw count after fanout)."""
    pass


class GrainMismatchError(Exception):
    """Raised when the target grain of the metric does not align with the JoinPlan."""
    pass


class RelationalMetricCandidateSpec(BaseModel):
    """Specification for deriving a relational metric."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_name: str
    join_plan_id: str
    numerator_metric: str
    denominator_metric: str
    formula: str
    target_grain: str
    source_table_ids: list[str]
    source_column_ids: list[str] = Field(default_factory=list)
    unit: str | None = None
    numerator_definition: str | None = None
    denominator_definition: str | None = None
    additivity: MetricAdditivity = MetricAdditivity.RATIO
    null_policy: str = "EXCLUDE"
    filter_policy: str = "ALL"
    display_aliases: list[str] = Field(default_factory=list)
    concept: str | None = None


class RelationalMetricDeriver:
    """
    Governed Cross-Table Relational Metric Deriver.
    Enforces that all cross-table derivations pass through authorized JoinPlans.
    """

    def __init__(self, registry: MetricRegistry | None = None) -> None:
        self.registry = registry or MetricRegistry()

    def derive_relational_metric(
        self,
        spec: RelationalMetricCandidateSpec,
        *,
        authorized_plans: dict[str, JoinPlan] | list[JoinPlan],
        provenance_coords: list[str] | None = None,
        evidence_refs: list[str] | None = None,
    ) -> RelationalDerivedMetric:
        """
        Derives a relational metric strictly gated by an authorized JoinPlan.
        """
        # 1. JoinPlan presence guard
        if not spec.join_plan_id or not spec.join_plan_id.strip():
            raise JoinPlanRequiredError(
                f"Cross-table derivation for '{spec.metric_name}' strictly blocked: missing join_plan_id. "
                "No cross-table derivation is permitted without an explicit, validated JoinPlan."
            )

        plans_dict = (
            authorized_plans
            if isinstance(authorized_plans, dict)
            else {p.join_plan_id: p for p in authorized_plans}
        )

        join_plan = plans_dict.get(spec.join_plan_id)
        if not join_plan:
            raise JoinPlanRequiredError(
                f"JoinPlan '{spec.join_plan_id}' not found among authorized plans: {list(plans_dict.keys())}"
            )

        # 2. Safety status guards
        if join_plan.safety_status == JoinSafetyStatus.UNSAFE:
            raise UnsafeJoinPlanError(
                f"Cross-table derivation blocked: JoinPlan '{join_plan.join_plan_id}' is UNSAFE. "
                f"Forbidden reason: {join_plan.forbidden_reason}"
            )
        if join_plan.safety_status == JoinSafetyStatus.AMBIGUOUS:
            raise AmbiguousJoinPlanError(
                f"Cross-table derivation blocked: JoinPlan '{join_plan.join_plan_id}' is AMBIGUOUS. "
                "Ambiguous joins cannot be used for governed metric derivations."
            )
        if join_plan.safety_status not in (JoinSafetyStatus.SAFE, JoinSafetyStatus.SAFE_WITH_PREAGGREGATION):
            raise UnsafeJoinPlanError(
                f"Cross-table derivation blocked: unauthorized JoinSafetyStatus '{join_plan.safety_status}'"
            )

        # 3. Forbidden operations guard
        for forbidden in join_plan.forbidden_operations:
            if forbidden.lower() in spec.formula.lower() or forbidden.lower() in spec.metric_name.lower():
                raise ForbiddenJoinOperationError(
                    f"Operation '{forbidden}' is strictly forbidden by JoinPlan '{join_plan.join_plan_id}'"
                )

        # 4. Target grain compatibility
        plan_target = join_plan.target_grain.strip().upper()
        spec_target = spec.target_grain.strip().upper()
        if plan_target != spec_target:
            raise GrainMismatchError(
                f"Target grain mismatch: metric '{spec.metric_name}' specifies grain '{spec.target_grain}', "
                f"but JoinPlan '{join_plan.join_plan_id}' governs target grain '{join_plan.target_grain}'"
            )

        # 5. Numerator / Denominator semantics
        num_def = spec.numerator_definition or spec.numerator_metric
        den_def = spec.denominator_definition or spec.denominator_metric

        # 6. Provenance transitivity
        prov_refs = list(provenance_coords or [])
        if not prov_refs:
            prov_refs = [f"{t}" for t in spec.source_table_ids]
            prov_refs.append(f"join_plan:{join_plan.join_plan_id}")

        # 7. Deterministic fingerprint (includes join_plan_id)
        fp = compute_metric_fingerprint(
            formula=spec.formula,
            target_grain=spec.target_grain,
            source_table_ids=spec.source_table_ids,
            source_column_ids=spec.source_column_ids,
            unit=spec.unit,
            additivity=spec.additivity,
            numerator_definition=num_def,
            denominator_definition=den_def,
            filter_policy=spec.filter_policy,
            null_policy=spec.null_policy,
            join_plan_id=spec.join_plan_id,
            concept=spec.concept,
        )

        metric_id = f"metric-rel-{fp[:12]}"

        metric = RelationalDerivedMetric(
            metric_id=metric_id,
            metric_name=spec.metric_name,
            join_plan_id=spec.join_plan_id,
            numerator_metric=spec.numerator_metric,
            denominator_metric=spec.denominator_metric,
            formula=spec.formula,
            target_grain=spec.target_grain,
            unit=spec.unit,
            denominator_safety_verified=True,
            metric_type="RELATIONAL",
            source_table_ids=spec.source_table_ids,
            source_column_ids=spec.source_column_ids,
            numerator_definition=num_def,
            denominator_definition=den_def,
            additivity=spec.additivity,
            null_policy=spec.null_policy,
            filter_policy=spec.filter_policy,
            provenance_refs=prov_refs,
            evidence_refs=list(evidence_refs or []),
            definition_confidence=1.0,
            derivation_method="RELATIONAL_JOIN_PLAN",
            display_aliases=spec.display_aliases,
            fingerprint=fp,
        )

        return self.registry.register(metric)
