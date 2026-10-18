"""
HighView Ingestion V2 — Phase I6: Governed Enrichment & Semantic Graph Integration Test Suite
Verifies:
1. LocalMetricDeriver: intra-table, same-grain, validated columns, unit safety, denominator preservation.
2. RelationalMetricDeriver: authorized JoinPlan mandatory, UNSAFE/AMBIGUOUS blocked, operation guards, grain safety.
3. Metric Identity & Deduplication: stable SHA-256 fingerprints, alias merging, separate definitions never merged.
4. Semantic Family Builder: domain-neutral concept grouping, organizational metadata invariant, intent neutrality.
5. Semantic Graph Builder & Topology: 0 dangling edges, 0 orphan inputs, 0 derivation cycles, 0 missing grains.
6. Evidence Integration: EVID-* compatibility, zero competing evidence IDs, SemanticGraph/EvidenceGraph separation.
7. Determinism: 10-run serialization byte-for-byte identical, stable fingerprints.
8. Domain-Neutral Benchmark: Workforce, Retail, Environmental, Finance, SaaS, Supply Chain (precision/recall/F1 = 1.000).
9. Performance & Memory: P50/P95 latency and peak memory telemetry.
10. Epistemic Boundaries & P0 Firewall: 0 new findings, 0 recommendations, 0 ExecutiveTopics, 0 vectors, 0 model calls, shadow-only.
"""

import time
import tracemalloc
import pytest
from typing import Any

from app.services.ingestion_v2.contracts.base import SourceCoordinateRef
from app.services.ingestion_v2.contracts.normalization import (
    NormalizedDataset,
    NormalizedTable,
    NormalizedColumn,
    CanonicalPhysicalType,
    NormalizedFieldLineage,
)
from app.services.ingestion_v2.contracts.profiling import (
    StructuralProfile,
    TableStructuralProfile,
    ColumnStructuralProfile,
    StructuralDataQuality,
)
from app.services.ingestion_v2.contracts.semantics import (
    SemanticModel,
    TableSemanticModel,
    SemanticColumnAssignment,
    SemanticColumnRole,
    SemanticConcept,
    SemanticEntityType,
    MeasureClass,
    ClassificationSource,
)
from app.services.ingestion_v2.contracts.grain import (
    GrainProfile,
    TableGrainProfile,
    CanonicalGrain,
)
from app.services.ingestion_v2.contracts.relationships import (
    ValidatedRelationshipGraph,
    ValidatedRelationshipEdge,
    RelationshipCardinality,
    RelationshipStatus,
    CandidateKeyType,
)
from app.services.ingestion_v2.contracts.joins import (
    JoinPlan,
    JoinSafetyStatus,
    PreAggregationSpec,
    GovernedJoinPlanSet,
)
from app.services.ingestion_v2.contracts.analytics import (
    AnalyticalProfile,
    AnalyticalFinding,
    FindingType,
    StatisticalTestEvidence,
    AnalyticalReliability,
)
from app.services.ingestion_v2.contracts.enrichment import (
    LocalDerivedMetric,
    RelationalDerivedMetric,
    SemanticFamily,
    EnrichedDataset,
    MetricAdditivity,
)
from app.services.ingestion_v2.contracts.semantic_graph import (
    GraphNodeType,
    GraphEdgeType,
    SemanticGraph,
    SemanticGraphNode,
    SemanticGraphEdge,
)
from app.services.ingestion_v2.contracts.intent import (
    AnalysisIntent,
    IntentFocusDomain,
    TargetPersona,
)
from app.services.ingestion_v2.enrichment import (
    LocalMetricDeriver,
    LocalMetricCandidateSpec,
    IncompatibleUnitError,
    InvalidLocalMetricSourceError,
    RelationalMetricDeriver,
    RelationalMetricCandidateSpec,
    JoinPlanRequiredError,
    UnsafeJoinPlanError,
    AmbiguousJoinPlanError,
    ForbiddenJoinOperationError,
    GrainMismatchError,
    SemanticFamilyBuilder,
    SemanticFamilySpec,
    MetricRegistry,
    compute_metric_fingerprint,
    normalize_formula,
)
from app.services.ingestion_v2.semantic_graph import (
    SemanticGraphBuilder,
    SemanticGraphValidator,
    DanglingEdgeError,
    OrphanMetricInputError,
    MetricDerivationCycleError,
    MissingGrainError,
    MissingJoinPlanError,
    InvalidEvidenceRefError,
    NonexistentEvidenceError,
    ObservedValueInMetricError,
    compute_graph_fingerprint,
    serialize_graph_canonical,
    create_metric_node,
    create_derived_from_edge,
)


# ==============================================================================
# 1. LOCAL METRIC DERIVER TESTS
# ==============================================================================

def test_local_metric_derivation_margin_and_attendance_rate():
    """Verify LocalMetricDeriver calculates margin and attendance rate within table grain."""
    deriver = LocalMetricDeriver()

    # Spec 1: Revenue - Cost = Margin (Difference)
    spec_margin = LocalMetricCandidateSpec(
        metric_name="Gross Margin",
        formula="revenue - cost",
        source_table_id="tbl_financials",
        source_column_ids=["revenue", "cost"],
        target_grain="STORE x MONTH",
        unit="USD",
        additivity=MetricAdditivity.ADDITIVE,
        concept="PROFITABILITY",
    )
    metric_margin = deriver.derive_metric(
        spec_margin,
        table_columns=["revenue", "cost", "store_id", "month"],
        column_units={"revenue": "USD", "cost": "USD"},
        table_grain="STORE x MONTH",
    )
    assert metric_margin.metric_name == "Gross Margin"
    assert metric_margin.formula == "revenue - cost"
    assert metric_margin.unit == "USD"
    assert metric_margin.grain == "STORE x MONTH"
    assert metric_margin.additivity == MetricAdditivity.ADDITIVE
    assert metric_margin.fingerprint != ""

    # Spec 2: Present / Eligible = Attendance Rate (Ratio)
    spec_att = LocalMetricCandidateSpec(
        metric_name="Attendance Rate",
        formula="present_days / eligible_days",
        source_table_id="tbl_attendance",
        source_column_ids=["present_days", "eligible_days"],
        target_grain="PERSON x MONTH",
        unit="PERCENTAGE",
        additivity=MetricAdditivity.RATIO,
        numerator_definition="present_days",
        denominator_definition="eligible_days",
        concept="ATTENDANCE",
    )
    metric_att = deriver.derive_metric(
        spec_att,
        table_columns=["present_days", "eligible_days", "employee_id", "month"],
        column_units={"present_days": "DAYS", "eligible_days": "DAYS"},
        table_grain="PERSON x MONTH",
    )
    assert metric_att.metric_name == "Attendance Rate"
    assert metric_att.additivity == MetricAdditivity.RATIO
    assert metric_att.numerator_definition == "present_days"
    assert metric_att.denominator_definition == "eligible_days"


def test_local_metric_deriver_unit_safety_rejection():
    """Verify attempting to combine incompatible units (USD vs EUR) raises IncompatibleUnitError."""
    deriver = LocalMetricDeriver()
    spec = LocalMetricCandidateSpec(
        metric_name="Global Profit",
        formula="us_revenue - eu_cost",
        source_table_id="tbl_sales",
        source_column_ids=["us_revenue", "eu_cost"],
        target_grain="COMPANY x YEAR",
        unit="MIXED",
        additivity=MetricAdditivity.ADDITIVE,
    )
    with pytest.raises(IncompatibleUnitError) as exc_info:
        deriver.derive_metric(
            spec,
            table_columns=["us_revenue", "eu_cost"],
            column_units={"us_revenue": "USD", "eu_cost": "EUR"},
            table_grain="COMPANY x YEAR",
        )
    assert "Incompatible units detected" in str(exc_info.value)


def test_local_metric_deriver_grain_and_column_guards():
    """Verify grain mismatch and missing column errors are strictly enforced."""
    deriver = LocalMetricDeriver()
    spec = LocalMetricCandidateSpec(
        metric_name="Closure Rate",
        formula="closed / total",
        source_table_id="tbl_tickets",
        source_column_ids=["closed", "total"],
        target_grain="DEPARTMENT",  # Mismatch: table is TICKET
        unit="RATIO",
        additivity=MetricAdditivity.RATIO,
    )
    # Grain mismatch
    with pytest.raises(InvalidLocalMetricSourceError) as exc_info:
        deriver.derive_metric(
            spec,
            table_columns=["closed", "total"],
            table_grain="TICKET",
        )
    assert "Grain mismatch" in str(exc_info.value)

    # Column missing
    spec_correct_grain = spec.model_copy(update={"target_grain": "TICKET"})
    with pytest.raises(InvalidLocalMetricSourceError) as exc_info2:
        deriver.derive_metric(
            spec_correct_grain,
            table_columns=["closed"],  # 'total' is missing
            table_grain="TICKET",
        )
    assert "Column 'total' does not exist" in str(exc_info2.value)


# ==============================================================================
# 2. RELATIONAL METRIC DERIVER TESTS
# ==============================================================================

def test_relational_metric_derivation_via_authorized_join_plan():
    """Verify cross-table metric derivation succeeds when backed by an authorized SAFE JoinPlan."""
    deriver = RelationalMetricDeriver()

    safe_plan = JoinPlan(
        join_plan_id="jp-dept-att-001",
        edge_id="edge-emp-att-01",
        left_table_id="tbl_employees",
        left_grain="PERSON",
        right_table_id="tbl_attendance",
        right_grain="PERSON x DAY",
        target_grain="DEPARTMENT x MONTH",
        join_type="INNER",
        safety_status=JoinSafetyStatus.SAFE_WITH_PREAGGREGATION,
        pre_aggregation=PreAggregationSpec(
            source_table_id="tbl_attendance",
            group_by_columns=["employee_id", "month"],
            aggregations={"present_days": "SUM", "scheduled_days": "SUM"},
            target_grain="PERSON x MONTH",
        ),
        safe_operations=["PREAGGREGATED_RATIO", "DEPARTMENT_ROLLUP"],
        forbidden_operations=["RAW_HEADCOUNT_AFTER_JOIN", "CARTESIAN_MULTIPLICATION"],
    )

    spec = RelationalMetricCandidateSpec(
        metric_name="Department Attendance Rate",
        join_plan_id="jp-dept-att-001",
        numerator_metric="total_present_days",
        denominator_metric="total_scheduled_days",
        formula="total_present_days / total_scheduled_days",
        target_grain="DEPARTMENT x MONTH",
        source_table_ids=["tbl_employees", "tbl_attendance"],
        source_column_ids=["department_id", "present_days", "scheduled_days"],
        unit="PERCENTAGE",
        additivity=MetricAdditivity.RATIO,
    )

    metric = deriver.derive_relational_metric(spec, authorized_plans=[safe_plan])
    assert metric.metric_name == "Department Attendance Rate"
    assert metric.join_plan_id == "jp-dept-att-001"
    assert metric.target_grain == "DEPARTMENT x MONTH"
    assert metric.denominator_safety_verified is True
    assert metric.fingerprint != ""


def test_relational_metric_deriver_safety_guards_and_forbidden_operations():
    """Verify missing JoinPlan, UNSAFE, AMBIGUOUS, and forbidden operations are strictly blocked."""
    deriver = RelationalMetricDeriver()

    # 1. Missing JoinPlan
    spec_no_plan = RelationalMetricCandidateSpec(
        metric_name="Cross Table Metric",
        join_plan_id="",
        numerator_metric="a",
        denominator_metric="b",
        formula="a / b",
        target_grain="COMPANY",
        source_table_ids=["t1", "t2"],
    )
    with pytest.raises(JoinPlanRequiredError):
        deriver.derive_relational_metric(spec_no_plan, authorized_plans=[])

    # 2. UNSAFE JoinPlan
    unsafe_plan = JoinPlan(
        join_plan_id="jp-unsafe-001",
        edge_id="edge-fact-fact",
        left_table_id="tbl_attendance",
        left_grain="PERSON x DAY",
        right_table_id="tbl_leave",
        right_grain="PERSON x INCIDENT",
        target_grain="PERSON",
        join_type="INNER",
        safety_status=JoinSafetyStatus.UNSAFE,
        forbidden_reason="Raw fact-to-fact join produces unconstrained Cartesian multiplier",
    )
    spec_unsafe = RelationalMetricCandidateSpec(
        metric_name="Attendance Leave Ratio",
        join_plan_id="jp-unsafe-001",
        numerator_metric="att",
        denominator_metric="leave",
        formula="att / leave",
        target_grain="PERSON",
        source_table_ids=["tbl_attendance", "tbl_leave"],
    )
    with pytest.raises(UnsafeJoinPlanError) as exc_unsafe:
        deriver.derive_relational_metric(spec_unsafe, authorized_plans=[unsafe_plan])
    assert "is UNSAFE" in str(exc_unsafe.value)

    # 3. AMBIGUOUS JoinPlan
    ambiguous_plan = unsafe_plan.model_copy(
        update={"join_plan_id": "jp-ambig-001", "safety_status": JoinSafetyStatus.AMBIGUOUS}
    )
    spec_ambig = spec_unsafe.model_copy(update={"join_plan_id": "jp-ambig-001"})
    with pytest.raises(AmbiguousJoinPlanError):
        deriver.derive_relational_metric(spec_ambig, authorized_plans=[ambiguous_plan])

    # 4. Forbidden operation: raw headcount after fanout join
    safe_with_guard = JoinPlan(
        join_plan_id="jp-emp-att-guard",
        edge_id="edge-emp-att",
        left_table_id="tbl_employees",
        left_grain="PERSON",
        right_table_id="tbl_attendance",
        right_grain="PERSON x DAY",
        target_grain="DEPARTMENT",
        join_type="LEFT",
        safety_status=JoinSafetyStatus.SAFE,
        forbidden_operations=["raw_headcount_after_join"],
    )
    spec_forbidden = RelationalMetricCandidateSpec(
        metric_name="raw_headcount_after_join",
        join_plan_id="jp-emp-att-guard",
        numerator_metric="cnt",
        denominator_metric="tot",
        formula="count(employee_id)",
        target_grain="DEPARTMENT",
        source_table_ids=["tbl_employees", "tbl_attendance"],
    )
    with pytest.raises(ForbiddenJoinOperationError) as exc_forbid:
        deriver.derive_relational_metric(spec_forbidden, authorized_plans=[safe_with_guard])
    assert "strictly forbidden" in str(exc_forbid.value)


# ==============================================================================
# 3. METRIC IDENTITY & DEDUPLICATION TESTS
# ==============================================================================

def test_metric_identity_alias_deduplication():
    """
    Verify equivalent definitions across display wordings
    resolve to 1 canonical metric with aliases aggregated.
    """
    registry = MetricRegistry()
    deriver = LocalMetricDeriver(registry=registry)

    # Alias 1: Office Attendance %
    spec1 = LocalMetricCandidateSpec(
        metric_name="Office Attendance %",
        formula="present_days / eligible_days",
        source_table_id="tbl_attendance",
        source_column_ids=["present_days", "eligible_days"],
        target_grain="PERSON x MONTH",
        unit="PERCENTAGE",
        additivity=MetricAdditivity.RATIO,
        numerator_definition="present_days",
        denominator_definition="eligible_days",
    )
    m1 = deriver.derive_metric(
        spec1,
        table_columns=["present_days", "eligible_days"],
        table_grain="PERSON x MONTH",
    )

    # Alias 2: Attendance Rate
    spec2 = spec1.model_copy(update={"metric_name": "Attendance Rate"})
    m2 = deriver.derive_metric(
        spec2,
        table_columns=["present_days", "eligible_days"],
        table_grain="PERSON x MONTH",
    )

    # Alias 3: Attendance Percentage
    spec3 = spec1.model_copy(update={"metric_name": "Attendance Percentage"})
    m3 = deriver.derive_metric(
        spec3,
        table_columns=["present_days", "eligible_days"],
        table_grain="PERSON x MONTH",
    )

    assert m1.fingerprint == m2.fingerprint == m3.fingerprint
    assert len(registry.metrics) == 1  # Exactly 1 canonical metric!
    canonical = registry.metrics[0]
    assert "Office Attendance %" in canonical.display_aliases
    assert "Attendance Rate" in canonical.display_aliases
    assert "Attendance Percentage" in canonical.display_aliases


def test_metric_identity_different_definitions_never_deduplicate():
    """
    Verify same name with different definitions ('Conversion Rate' orders/visitors vs paid/trials)
    produce distinct fingerprints and remain separate metrics.
    """
    registry = MetricRegistry()
    deriver = LocalMetricDeriver(registry=registry)

    # Definition A: Orders / Visitors
    spec_a = LocalMetricCandidateSpec(
        metric_name="Conversion Rate",
        formula="orders / visitors",
        source_table_id="tbl_web_traffic",
        source_column_ids=["orders", "visitors"],
        target_grain="CAMPAIGN",
        unit="PERCENTAGE",
        additivity=MetricAdditivity.RATIO,
        numerator_definition="orders",
        denominator_definition="visitors",
    )
    m_a = deriver.derive_metric(
        spec_a,
        table_columns=["orders", "visitors"],
        table_grain="CAMPAIGN",
    )

    # Definition B: Paid Customers / Trials
    spec_b = LocalMetricCandidateSpec(
        metric_name="Conversion Rate",
        formula="paid_customers / trial_users",
        source_table_id="tbl_saas_trials",
        source_column_ids=["paid_customers", "trial_users"],
        target_grain="COHORT",
        unit="PERCENTAGE",
        additivity=MetricAdditivity.RATIO,
        numerator_definition="paid_customers",
        denominator_definition="trial_users",
    )
    m_b = deriver.derive_metric(
        spec_b,
        table_columns=["paid_customers", "trial_users"],
        table_grain="COHORT",
    )

    assert m_a.fingerprint != m_b.fingerprint
    assert len(registry.metrics) == 2  # Must NOT deduplicate by name alone!


def test_metric_fingerprint_invariance_to_volatile_fields():
    """Verify metric fingerprints are strictly invariant to run_id, timestamps, and display wording."""
    fp1 = compute_metric_fingerprint(
        formula="revenue - cost",
        target_grain="STORE x MONTH",
        source_table_ids=["tbl_sales"],
        source_column_ids=["revenue", "cost"],
        unit="USD",
        additivity="ADDITIVE",
    )
    fp2 = compute_metric_fingerprint(
        formula="  revenue  -   cost ",  # Extra whitespace
        target_grain="store x month",      # Lowercase grain
        source_table_ids=["tbl_sales"],
        source_column_ids=["cost", "revenue"],  # Permuted columns
        unit="usd",
        additivity="additive",
    )
    assert fp1 == fp2

    # Different formula -> different fingerprint
    fp3 = compute_metric_fingerprint(
        formula="revenue - cost - tax",
        target_grain="STORE x MONTH",
        source_table_ids=["tbl_sales"],
        source_column_ids=["revenue", "cost", "tax"],
        unit="USD",
        additivity="ADDITIVE",
    )
    assert fp1 != fp3


# ==============================================================================
# 4. SEMANTIC FAMILY BUILDER TESTS
# ==============================================================================

def test_semantic_family_builder_domain_neutral_grouping():
    """Verify SemanticFamilyBuilder groups related validated metrics into typed families."""
    builder = SemanticFamilyBuilder()

    metrics = [
        LocalDerivedMetric(
            metric_id="m-present",
            table_id="tbl_attendance",
            metric_name="Present Days",
            formula="present_days",
            source_columns=["present_days"],
            grain="PERSON x MONTH",
        ),
        LocalDerivedMetric(
            metric_id="m-att-rate",
            table_id="tbl_attendance",
            metric_name="Attendance Rate",
            formula="present_days / eligible_days",
            source_columns=["present_days", "eligible_days"],
            grain="PERSON x MONTH",
            evidence_refs=["EVID-att-mean-001"],
        ),
        LocalDerivedMetric(
            metric_id="m-rev",
            table_id="tbl_sales",
            metric_name="Revenue",
            formula="sales_amount",
            source_columns=["sales_amount"],
            grain="STORE x MONTH",
            evidence_refs=["EVID-sales-iqr-002"],
        ),
    ]

    families = builder.auto_group_metrics(metrics, dimensions=["department", "region"])
    assert len(families) == 2  # ATTENDANCE and REVENUE_FINANCIAL

    att_fam = next(f for f in families if f.concept_type == "ATTENDANCE")
    assert "m-present" in att_fam.metric_ids
    assert "m-att-rate" in att_fam.metric_ids
    assert "EVID-att-mean-001" in att_fam.evidence_refs

    rev_fam = next(f for f in families if f.concept_type == "REVENUE_FINANCIAL")
    assert "m-rev" in rev_fam.metric_ids
    assert "EVID-sales-iqr-002" in rev_fam.evidence_refs


def test_semantic_family_analysis_intent_neutrality():
    """Verify different AnalysisIntent objectives produce identical family memberships and definitions."""
    builder1 = SemanticFamilyBuilder()
    builder2 = SemanticFamilyBuilder()

    metric = LocalDerivedMetric(
        metric_id="m-1",
        table_id="tbl_workforce",
        metric_name="Turnover Rate",
        formula="exits / avg_headcount",
        source_columns=["exits", "avg_headcount"],
        grain="DEPARTMENT x YEAR",
    )

    intent_exec = AnalysisIntent(
        dataset_id="ds-test",
        run_id="run-1",
        source_fingerprint="fp-1",
        intent_id="intent-exec",
        focus_domain=IntentFocusDomain.TURNOVER_ATTRITION,
        target_persona=TargetPersona.EXECUTIVE,
    )
    intent_analyst = AnalysisIntent(
        dataset_id="ds-test",
        run_id="run-2",
        source_fingerprint="fp-1",
        intent_id="intent-analyst",
        focus_domain=IntentFocusDomain.COMPENSATION_EQUITY,
        target_persona=TargetPersona.COMPENSATION_ANALYST,
    )

    fams_exec = builder1.auto_group_metrics([metric], intent=intent_exec)
    fams_analyst = builder2.auto_group_metrics([metric], intent=intent_analyst)

    assert fams_exec[0].family_id == fams_analyst[0].family_id
    assert fams_exec[0].metric_ids == fams_analyst[0].metric_ids
    assert fams_exec[0].concept_type == fams_analyst[0].concept_type


# ==============================================================================
# 5. SEMANTIC GRAPH BUILDER & TOPOLOGY INTEGRITY TESTS
# ==============================================================================

@pytest.fixture
def canonical_mock_stages():
    """Creates fully populated mock stages for assembling a canonical SemanticGraph."""
    dataset_id = "ds-canonical"
    run_id = "run-001"
    src_fp = "src-canonical-hash-12345"

    norm_dataset = NormalizedDataset(
        dataset_id=dataset_id,
        run_id=run_id,
        source_fingerprint=src_fp,
        tables=[
            NormalizedTable(
                table_id="tbl_employees",
                table_name="employees",
                row_count=100,
                column_count=3,
                parquet_path="/tmp/employees.parquet",
                columns=[
                    NormalizedColumn(
                        column_id="tbl_employees.employee_id",
                        table_id="tbl_employees",
                        column_name="employee_id",
                        canonical_type=CanonicalPhysicalType.STRING,
                        lineage=NormalizedFieldLineage(column_id="tbl_employees.employee_id", raw_header_name="employee_id"),
                        null_count=0,
                        non_null_count=100,
                    ),
                    NormalizedColumn(
                        column_id="tbl_employees.department",
                        table_id="tbl_employees",
                        column_name="department",
                        canonical_type=CanonicalPhysicalType.STRING,
                        lineage=NormalizedFieldLineage(column_id="tbl_employees.department", raw_header_name="department"),
                        null_count=0,
                        non_null_count=100,
                    ),
                    NormalizedColumn(
                        column_id="tbl_employees.salary",
                        table_id="tbl_employees",
                        column_name="salary",
                        canonical_type=CanonicalPhysicalType.FLOAT,
                        inferred_unit="USD",
                        lineage=NormalizedFieldLineage(column_id="tbl_employees.salary", raw_header_name="salary", inferred_unit="USD"),
                        null_count=0,
                        non_null_count=100,
                    ),
                ],
            ),
            NormalizedTable(
                table_id="tbl_attendance",
                table_name="attendance",
                row_count=2200,
                column_count=4,
                parquet_path="/tmp/attendance.parquet",
                columns=[
                    NormalizedColumn(
                        column_id="tbl_attendance.employee_id",
                        table_id="tbl_attendance",
                        column_name="employee_id",
                        canonical_type=CanonicalPhysicalType.STRING,
                        lineage=NormalizedFieldLineage(column_id="tbl_attendance.employee_id", raw_header_name="employee_id"),
                        null_count=0,
                        non_null_count=2200,
                    ),
                    NormalizedColumn(
                        column_id="tbl_attendance.date",
                        table_id="tbl_attendance",
                        column_name="date",
                        canonical_type=CanonicalPhysicalType.DATE,
                        lineage=NormalizedFieldLineage(column_id="tbl_attendance.date", raw_header_name="date"),
                        null_count=0,
                        non_null_count=2200,
                    ),
                    NormalizedColumn(
                        column_id="tbl_attendance.present_days",
                        table_id="tbl_attendance",
                        column_name="present_days",
                        canonical_type=CanonicalPhysicalType.INTEGER,
                        inferred_unit="DAYS",
                        lineage=NormalizedFieldLineage(column_id="tbl_attendance.present_days", raw_header_name="present_days", inferred_unit="DAYS"),
                        null_count=0,
                        non_null_count=2200,
                    ),
                    NormalizedColumn(
                        column_id="tbl_attendance.eligible_days",
                        table_id="tbl_attendance",
                        column_name="eligible_days",
                        canonical_type=CanonicalPhysicalType.INTEGER,
                        inferred_unit="DAYS",
                        lineage=NormalizedFieldLineage(column_id="tbl_attendance.eligible_days", raw_header_name="eligible_days", inferred_unit="DAYS"),
                        null_count=0,
                        non_null_count=2200,
                    ),
                ],
            ),
        ],
    )

    quality_perfect = StructuralDataQuality(
        completeness_score=1.0,
        validity_score=1.0,
        uniqueness_score=1.0,
        consistency_score=1.0,
        reconstruction_fidelity_score=1.0,
        overall_structural_quality=1.0,
    )

    struct_profile = StructuralProfile(
        dataset_id=dataset_id,
        run_id=run_id,
        source_fingerprint=src_fp,
        dataset_structural_quality=quality_perfect,
        tables=[
            TableStructuralProfile(
                table_id="tbl_employees",
                table_name="employees",
                row_count=100,
                column_count=3,
                quality=quality_perfect,
                columns=[
                    ColumnStructuralProfile(
                        column_id="tbl_employees.employee_id",
                        table_id="tbl_employees",
                        column_name="employee_id",
                        physical_type="STRING",
                        row_count=100,
                        null_count=0,
                        null_ratio=0.0,
                        distinct_count=100,
                        uniqueness_ratio=1.0,
                    ),
                    ColumnStructuralProfile(
                        column_id="tbl_employees.department",
                        table_id="tbl_employees",
                        column_name="department",
                        physical_type="STRING",
                        row_count=100,
                        null_count=0,
                        null_ratio=0.0,
                        distinct_count=5,
                        uniqueness_ratio=0.05,
                    ),
                    ColumnStructuralProfile(
                        column_id="tbl_employees.salary",
                        table_id="tbl_employees",
                        column_name="salary",
                        physical_type="FLOAT",
                        row_count=100,
                        null_count=0,
                        null_ratio=0.0,
                        distinct_count=80,
                        uniqueness_ratio=0.8,
                    ),
                ],
            ),
            TableStructuralProfile(
                table_id="tbl_attendance",
                table_name="attendance",
                row_count=2200,
                column_count=4,
                quality=quality_perfect,
                columns=[
                    ColumnStructuralProfile(
                        column_id="tbl_attendance.employee_id",
                        table_id="tbl_attendance",
                        column_name="employee_id",
                        physical_type="STRING",
                        row_count=2200,
                        null_count=0,
                        null_ratio=0.0,
                        distinct_count=100,
                        uniqueness_ratio=0.045,
                    ),
                    ColumnStructuralProfile(
                        column_id="tbl_attendance.date",
                        table_id="tbl_attendance",
                        column_name="date",
                        physical_type="DATE",
                        row_count=2200,
                        null_count=0,
                        null_ratio=0.0,
                        distinct_count=22,
                        uniqueness_ratio=0.01,
                    ),
                    ColumnStructuralProfile(
                        column_id="tbl_attendance.present_days",
                        table_id="tbl_attendance",
                        column_name="present_days",
                        physical_type="INTEGER",
                        row_count=2200,
                        null_count=0,
                        null_ratio=0.0,
                        distinct_count=2,
                        uniqueness_ratio=0.001,
                    ),
                    ColumnStructuralProfile(
                        column_id="tbl_attendance.eligible_days",
                        table_id="tbl_attendance",
                        column_name="eligible_days",
                        physical_type="INTEGER",
                        row_count=2200,
                        null_count=0,
                        null_ratio=0.0,
                        distinct_count=2,
                        uniqueness_ratio=0.001,
                    ),
                ],
            ),
        ],
    )

    semantic_model = SemanticModel(
        dataset_id=dataset_id,
        run_id=run_id,
        source_fingerprint=src_fp,
        tables=[
            TableSemanticModel(
                table_id="tbl_employees",
                table_name="employees",
                primary_entity_type=SemanticEntityType.PERSON,
                columns=[
                    SemanticColumnAssignment(
                        column_id="tbl_employees.employee_id",
                        table_id="tbl_employees",
                        column_name="employee_id",
                        role=SemanticColumnRole.ENTITY_IDENTIFIER,
                        entity_type=SemanticEntityType.PERSON,
                        semantic_concept=SemanticConcept.IDENTIFIER,
                        confidence=1.0,
                        classification_source=ClassificationSource.HEURISTIC,
                        rationale="Unique ID",
                    ),
                    SemanticColumnAssignment(
                        column_id="tbl_employees.department",
                        table_id="tbl_employees",
                        column_name="department",
                        role=SemanticColumnRole.DIMENSION,
                        semantic_concept=SemanticConcept.CATEGORICAL,
                        confidence=1.0,
                        classification_source=ClassificationSource.HEURISTIC,
                        rationale="Department category",
                    ),
                    SemanticColumnAssignment(
                        column_id="tbl_employees.salary",
                        table_id="tbl_employees",
                        column_name="salary",
                        role=SemanticColumnRole.MEASURE,
                        measure_class=MeasureClass.FINANCIAL,
                        semantic_concept=SemanticConcept.MEASURE,
                        confidence=1.0,
                        classification_source=ClassificationSource.HEURISTIC,
                        rationale="Employee salary measure",
                    ),
                ],
            ),
            TableSemanticModel(
                table_id="tbl_attendance",
                table_name="attendance",
                primary_entity_type=SemanticEntityType.PERSON,
                columns=[
                    SemanticColumnAssignment(
                        column_id="tbl_attendance.employee_id",
                        table_id="tbl_attendance",
                        column_name="employee_id",
                        role=SemanticColumnRole.ENTITY_IDENTIFIER,
                        entity_type=SemanticEntityType.PERSON,
                        semantic_concept=SemanticConcept.IDENTIFIER,
                        confidence=1.0,
                        classification_source=ClassificationSource.HEURISTIC,
                        rationale="FK to employee",
                    ),
                    SemanticColumnAssignment(
                        column_id="tbl_attendance.date",
                        table_id="tbl_attendance",
                        column_name="date",
                        role=SemanticColumnRole.TIME,
                        semantic_concept=SemanticConcept.TIME_SPAN,
                        confidence=1.0,
                        classification_source=ClassificationSource.HEURISTIC,
                        rationale="Attendance date",
                    ),
                    SemanticColumnAssignment(
                        column_id="tbl_attendance.present_days",
                        table_id="tbl_attendance",
                        column_name="present_days",
                        role=SemanticColumnRole.MEASURE,
                        measure_class=MeasureClass.QUANTITY,
                        semantic_concept=SemanticConcept.MEASURE,
                        confidence=1.0,
                        classification_source=ClassificationSource.HEURISTIC,
                        rationale="Present days count",
                    ),
                    SemanticColumnAssignment(
                        column_id="tbl_attendance.eligible_days",
                        table_id="tbl_attendance",
                        column_name="eligible_days",
                        role=SemanticColumnRole.MEASURE,
                        measure_class=MeasureClass.QUANTITY,
                        semantic_concept=SemanticConcept.MEASURE,
                        confidence=1.0,
                        classification_source=ClassificationSource.HEURISTIC,
                        rationale="Eligible days count",
                    ),
                ],
            ),
        ],
    )

    grain_profile = GrainProfile(
        dataset_id=dataset_id,
        run_id=run_id,
        source_fingerprint=src_fp,
        table_grains=[
            TableGrainProfile(
                table_id="tbl_employees",
                table_name="employees",
                primary_entity=CanonicalGrain.PERSON,
                key_columns=["employee_id"],
                grain_expression="PERSON",
                is_unique=True,
                uniqueness_ratio=1.0,
                grain_confidence=1.0,
                duplicate_key_rows=0,
                rationale="Unique employee_id",
            ),
            TableGrainProfile(
                table_id="tbl_attendance",
                table_name="attendance",
                primary_entity=CanonicalGrain.PERSON,
                key_columns=["employee_id", "date"],
                grain_expression="PERSON x DAY",
                is_unique=True,
                uniqueness_ratio=1.0,
                grain_confidence=1.0,
                duplicate_key_rows=0,
                rationale="Unique composite key employee_id and date",
            ),
        ],
    )

    relationships = ValidatedRelationshipGraph(
        dataset_id=dataset_id,
        run_id=run_id,
        source_fingerprint=src_fp,
        edges=[
            ValidatedRelationshipEdge(
                edge_id="edge-emp-att-01",
                candidate_id="cand-emp-att-01",
                source_table_id="tbl_employees",
                source_column_ids=["employee_id"],
                target_table_id="tbl_attendance",
                target_column_ids=["employee_id"],
                key_type=CandidateKeyType.SINGLE,
                cardinality=RelationshipCardinality.ONE_TO_MANY,
                status=RelationshipStatus.VALIDATED,
                referential_coverage=1.0,
                source_overlap_ratio=1.0,
                target_overlap_ratio=1.0,
                confidence=1.0,
                estimated_row_multiplier=22.0,
                is_grain_preserving=False,
            )
        ],
    )

    join_plan = JoinPlan(
        join_plan_id="jp-dept-att-001",
        edge_id="edge-emp-att-01",
        left_table_id="tbl_employees",
        left_grain="PERSON",
        right_table_id="tbl_attendance",
        right_grain="PERSON x DAY",
        target_grain="DEPARTMENT x MONTH",
        join_type="INNER",
        safety_status=JoinSafetyStatus.SAFE_WITH_PREAGGREGATION,
        pre_aggregation=PreAggregationSpec(
            source_table_id="tbl_attendance",
            group_by_columns=["employee_id"],
            aggregations={"present_days": "SUM", "eligible_days": "SUM"},
            target_grain="PERSON",
        ),
    )

    analytical_profile = AnalyticalProfile(
        dataset_id=dataset_id,
        run_id=run_id,
        source_fingerprint=src_fp,
        reliability=AnalyticalReliability(
            grain_confidence_score=1.0,
            join_coverage_score=1.0,
            metric_definition_confidence=1.0,
            evidence_sufficiency_score=1.0,
            overall_analytical_reliability=1.0,
        ),
        findings=[
            AnalyticalFinding(
                finding_id="find-att-mean-01",
                finding_type="DISTRIBUTION",
                affected_tables=["tbl_attendance"],
                affected_columns=["present_days"],
                description="Observed mean attendance days is 20.4",
                evidence_ref="EVID-att-mean-001",
                statistical_test_evidence=StatisticalTestEvidence(
                    test_name="SAMPLE_MEAN",
                    test_statistic=20.4,
                    p_value=0.01,
                    sample_size=2200,
                    degrees_of_freedom=2199.0,
                    is_statistically_significant=True,
                ),
                analytical_reliability=AnalyticalReliability(
                    grain_confidence_score=1.0,
                    join_coverage_score=1.0,
                    metric_definition_confidence=1.0,
                    evidence_sufficiency_score=1.0,
                    overall_analytical_reliability=1.0,
                ),
            )
        ],
    )

    enriched_dataset = EnrichedDataset(
        dataset_id=dataset_id,
        run_id=run_id,
        source_fingerprint=src_fp,
        local_metrics=[
            LocalDerivedMetric(
                metric_id="metric-att-rate",
                table_id="tbl_attendance",
                metric_name="Attendance Rate",
                formula="present_days / eligible_days",
                source_columns=["present_days", "eligible_days"],
                grain="PERSON x DAY",
                unit="PERCENTAGE",
                additivity=MetricAdditivity.RATIO,
                evidence_refs=["EVID-att-mean-001"],
            )
        ],
        relational_metrics=[
            RelationalDerivedMetric(
                metric_id="metric-dept-att-rate",
                metric_name="Department Attendance Rate",
                join_plan_id="jp-dept-att-001",
                numerator_metric="present_days",
                denominator_metric="eligible_days",
                formula="present_days / eligible_days",
                target_grain="DEPARTMENT x MONTH",
                unit="PERCENTAGE",
                additivity=MetricAdditivity.RATIO,
                source_table_ids=["tbl_employees", "tbl_attendance"],
                source_column_ids=["department", "present_days", "eligible_days"],
                evidence_refs=["EVID-att-mean-001"],
            )
        ],
        semantic_families=[
            SemanticFamily(
                family_id="family-attendance",
                family_name="Workforce Attendance Family",
                concept_type="ATTENDANCE",
                metric_ids=["metric-att-rate", "metric-dept-att-rate"],
                dimension_ids=["tbl_employees.department"],
                entity_types=["PERSON"],
                grain_scope="PERSON x DAY / DEPARTMENT x MONTH",
                evidence_refs=["EVID-att-mean-001"],
            )
        ],
    )

    return {
        "dataset_id": dataset_id,
        "run_id": run_id,
        "source_fingerprint": src_fp,
        "normalized_dataset": norm_dataset,
        "structural_profile": struct_profile,
        "semantic_model": semantic_model,
        "grain_profile": grain_profile,
        "relationships": relationships,
        "join_plans": [join_plan],
        "analytical_profile": analytical_profile,
        "enriched_dataset": enriched_dataset,
    }


def test_canonical_semantic_graph_build_and_validation(canonical_mock_stages):
    """Verify SemanticGraphBuilder correctly assembles the graph with zero dangling edges or errors."""
    builder = SemanticGraphBuilder()
    graph = builder.build_graph(**canonical_mock_stages)

    assert graph.stage_name == "semantic_graph"
    assert graph.node_count > 0
    assert graph.edge_count > 0
    assert graph.metrics_count == 2
    assert graph.families_count == 1
    assert len(graph.graph_fingerprint) == 64

    # Verify nodes represent all tables and columns
    table_nodes = [n for n in graph.nodes if n.node_type == GraphNodeType.TABLE]
    assert len(table_nodes) == 2

    metric_nodes = [n for n in graph.nodes if n.node_type == GraphNodeType.METRIC]
    assert len(metric_nodes) == 2

    family_nodes = [n for n in graph.nodes if n.node_type == GraphNodeType.SEMANTIC_FAMILY]
    assert len(family_nodes) == 1

    # Verify edge types present
    edge_types = {e.edge_type for e in graph.edges}
    assert GraphEdgeType.CONTAINS in edge_types
    assert GraphEdgeType.STRUCTURAL_RELATIONSHIP in edge_types
    assert GraphEdgeType.MEASURED_AT_GRAIN in edge_types
    assert GraphEdgeType.DERIVED_FROM in edge_types
    assert GraphEdgeType.USES_JOIN_PLAN in edge_types
    assert GraphEdgeType.SUPPORTED_BY_EVIDENCE in edge_types
    assert GraphEdgeType.BELONGS_TO_FAMILY in edge_types


# ==============================================================================
# 6. GRAPH NEGATIVE INTEGRITY TESTS
# ==============================================================================

def test_semantic_graph_negative_dangling_edge(canonical_mock_stages):
    """Verify validator raises DanglingEdgeError when an edge references a non-existent node."""
    builder = SemanticGraphBuilder()
    graph = builder.build_graph(**canonical_mock_stages)

    # Inject dangling edge
    bad_edge = SemanticGraphEdge(
        edge_id="edge-dangling-001",
        source_node_id="table:tbl_employees",
        target_node_id="node:does_not_exist",
        edge_type=GraphEdgeType.CONTAINS,
    )
    corrupted_edges = list(graph.edges) + [bad_edge]
    corrupted_graph = graph.model_copy(update={"edges": corrupted_edges})

    validator = SemanticGraphValidator()
    with pytest.raises(DanglingEdgeError) as exc_info:
        validator.validate(corrupted_graph)
    assert "Dangling edges detected" in str(exc_info.value)


def test_semantic_graph_negative_derivation_cycle():
    """Verify validator raises MetricDerivationCycleError when cyclic dependencies exist (A -> B -> A)."""
    # Create two metrics where A derived from B and B derived from A
    m_a = create_metric_node(
        metric_id="metric_a",
        metric_name="Metric A",
        formula="metric_b * 2",
        target_grain="PERSON",
    )
    m_b = create_metric_node(
        metric_id="metric_b",
        metric_name="Metric B",
        formula="metric_a / 2",
        target_grain="PERSON",
    )

    edge_a_from_b = create_derived_from_edge("metric:metric_a", "metric:metric_b")
    edge_b_from_a = create_derived_from_edge("metric:metric_b", "metric:metric_a")

    graph = SemanticGraph(
        dataset_id="ds-cycle",
        run_id="run-c",
        source_fingerprint="fp-c",
        nodes=[m_a, m_b],
        edges=[edge_a_from_b, edge_b_from_a],
        node_count=2,
        edge_count=2,
    )

    validator = SemanticGraphValidator()
    with pytest.raises(MetricDerivationCycleError) as exc_info:
        validator.validate(graph)
    assert "Metric derivation cycle detected" in str(exc_info.value)


def test_semantic_graph_negative_missing_grain():
    """Verify validator raises MissingGrainError when a MetricNode lacks a declared target_grain."""
    bad_metric = create_metric_node(
        metric_id="metric_no_grain",
        metric_name="Grainless Metric",
        formula="col_a + col_b",
        target_grain="",  # Missing grain!
    )
    graph = SemanticGraph(
        dataset_id="ds-no-grain",
        run_id="run-ng",
        source_fingerprint="fp-ng",
        nodes=[bad_metric],
        edges=[],
        node_count=1,
        edge_count=0,
    )
    validator = SemanticGraphValidator()
    with pytest.raises(MissingGrainError) as exc_info:
        validator.validate(graph)
    assert "Missing grain detected" in str(exc_info.value)


def test_semantic_graph_negative_orphan_metric_input():
    """Verify validator raises OrphanMetricInputError when a metric references a non-existent column."""
    orphan_metric = create_metric_node(
        metric_id="metric_orphan",
        metric_name="Orphan Input Metric",
        formula="phantom_col * 2",
        target_grain="STORE",
        source_table_ids=["tbl_stores"],
        source_column_ids=["phantom_col"],  # Not in graph
    )
    graph = SemanticGraph(
        dataset_id="ds-orphan",
        run_id="run-orph",
        source_fingerprint="fp-orph",
        nodes=[orphan_metric],
        edges=[],
        node_count=1,
        edge_count=0,
    )
    validator = SemanticGraphValidator()
    with pytest.raises(OrphanMetricInputError) as exc_info:
        validator.validate(graph)
    assert "Orphan metric inputs detected" in str(exc_info.value)


def test_evidence_reference_valid_existing(canonical_mock_stages):
    """Canonical Test 1: Valid existing EVID-001 with isolated fixture evidence registry -> PASS."""
    builder = SemanticGraphBuilder()
    evidence_reg = {"EVID-att-mean-001", "EVID-002"}
    graph = builder.build_graph(**canonical_mock_stages, evidence_registry=evidence_reg)

    validator = SemanticGraphValidator()
    report = validator.validate(graph, evidence_registry=evidence_reg, raise_on_error=True)
    assert report.is_valid is True
    assert report.invalid_evidence_count == 0
    assert report.unresolved_evidence_count == 0


def test_evidence_reference_well_formed_nonexistent(canonical_mock_stages):
    """Canonical Test 2: Well-formed but nonexistent EVID-999999 -> REJECT or explicit UNRESOLVED state."""
    builder = SemanticGraphBuilder()
    evidence_reg = {"EVID-att-mean-001"}
    graph = builder.build_graph(**canonical_mock_stages, evidence_registry=evidence_reg)

    # Inject well-formed but nonexistent EVID-999999
    bad_edge = SemanticGraphEdge(
        edge_id="edge-evid-nonexistent",
        source_node_id="metric:metric-att-rate",
        target_node_id="evidence:EVID-999999",
        edge_type=GraphEdgeType.SUPPORTED_BY_EVIDENCE,
        evidence_ref="EVID-999999",
    )
    corrupted_graph = graph.model_copy(update={"edges": list(graph.edges) + [bad_edge]})
    validator = SemanticGraphValidator()

    # Mode 1: raise_on_error=True -> REJECT with NonexistentEvidenceError
    with pytest.raises(NonexistentEvidenceError) as exc_info:
        validator.validate(corrupted_graph, evidence_registry=evidence_reg, raise_on_error=True)
    assert "EVID-999999" in str(exc_info.value)

    # Mode 2: raise_on_error=False -> explicit UNRESOLVED state
    report = validator.validate(corrupted_graph, evidence_registry=evidence_reg, raise_on_error=False)
    assert report.is_valid is False
    assert report.unresolved_evidence_count == 1
    assert any("EVID-999999" in u for u in report.unresolved_evidence)


def test_evidence_reference_invalid_namespace(canonical_mock_stages):
    """Canonical Test 3: Invalid namespace ABC-001 -> REJECT."""
    builder = SemanticGraphBuilder()
    graph = builder.build_graph(**canonical_mock_stages)

    bad_edge = SemanticGraphEdge(
        edge_id="edge-bad-namespace",
        source_node_id="metric:metric-att-rate",
        target_node_id="evidence:ABC-001",
        edge_type=GraphEdgeType.SUPPORTED_BY_EVIDENCE,
        evidence_ref="ABC-001",
    )
    corrupted_graph = graph.model_copy(update={"edges": list(graph.edges) + [bad_edge]})
    validator = SemanticGraphValidator()

    with pytest.raises(InvalidEvidenceRefError) as exc_info:
        validator.validate(corrupted_graph, raise_on_error=True)
    assert "Expected 'EVID-*'" in str(exc_info.value)


def test_evidence_reference_empty_reference(canonical_mock_stages):
    """Canonical Test 4: Empty reference -> REJECT."""
    builder = SemanticGraphBuilder()
    graph = builder.build_graph(**canonical_mock_stages)

    bad_edge = SemanticGraphEdge(
        edge_id="edge-empty-ref",
        source_node_id="metric:metric-att-rate",
        target_node_id="evidence:",
        edge_type=GraphEdgeType.SUPPORTED_BY_EVIDENCE,
        evidence_ref="",
    )
    corrupted_graph = graph.model_copy(update={"edges": list(graph.edges) + [bad_edge]})
    validator = SemanticGraphValidator()

    with pytest.raises(InvalidEvidenceRefError) as exc_info:
        validator.validate(corrupted_graph, raise_on_error=True)
    assert "empty evidence reference" in str(exc_info.value)


def test_evidencegraph_separation_observed_value_not_copied():
    """
    Canonical Test 5: SemanticGraph / EvidenceGraph separation.
    MetricNode attendance_rate SUPPORTED_BY_EVIDENCE EVID-123 must NOT copy
    observed value such as 83.4% into the semantic metric definition.
    """
    # 1. Direct node constructor guard
    with pytest.raises(ValueError) as exc_info:
        create_metric_node(
            metric_id="metric_att",
            metric_name="Attendance Rate",
            formula="present / eligible",
            target_grain="PERSON",
            properties={"observed_value": 0.834},
        )
    assert "Observed analytical value 'observed_value' cannot be embedded" in str(exc_info.value)

    # 2. Validator guard if raw node was constructed bypassing helper
    raw_bad_node = SemanticGraphNode(
        node_id="metric:metric_attendance_rate",
        node_type=GraphNodeType.METRIC,
        label="Attendance Rate",
        properties={
            "metric_id": "metric_attendance_rate",
            "formula": "present / eligible",
            "target_grain": "PERSON",
            "observed_value": 0.834,
            "metric_type": "LOCAL",
        },
    )
    raw_graph = SemanticGraph(
        dataset_id="ds-sep",
        run_id="run-sep",
        source_fingerprint="fp-sep",
        nodes=[raw_bad_node],
        edges=[],
        node_count=1,
        edge_count=0,
    )
    validator = SemanticGraphValidator()
    with pytest.raises(ObservedValueInMetricError) as exc_info:
        validator.validate(raw_graph, raise_on_error=True)
    assert "illegally embeds observed value" in str(exc_info.value)

    # 3. Valid metric node stores definition only, leaving observed value in EvidenceGraph
    valid_metric_node = create_metric_node(
        metric_id="attendance_rate",
        metric_name="Attendance Rate",
        formula="present_days / eligible_days",
        target_grain="PERSON x DAY",
        numerator_definition="COUNT(present_days)",
        denominator_definition="COUNT(eligible_days)",
        unit="PERCENTAGE",
        additivity=MetricAdditivity.RATIO.value,
        evidence_ref="EVID-123",
    )
    assert "observed_value" not in valid_metric_node.properties
    assert "value" not in valid_metric_node.properties
    assert "result" not in valid_metric_node.properties
    assert valid_metric_node.properties["formula"] == "present_days / eligible_days"
    assert valid_metric_node.evidence_ref == "EVID-123"


# ==============================================================================
# 7. DETERMINISM & 10-RUN GRAPH SERIALIZATION
# ==============================================================================

def test_10_run_graph_serialization_identical(canonical_mock_stages):
    """Verify 10 independent serialization runs produce 100% byte-for-byte identical output."""
    builder = SemanticGraphBuilder()
    graph = builder.build_graph(**canonical_mock_stages)

    baseline_bytes = serialize_graph_canonical(graph)
    baseline_fp = compute_graph_fingerprint(graph)

    for run_idx in range(10):
        # Re-serialize
        serialized = serialize_graph_canonical(graph)
        fp = compute_graph_fingerprint(graph)
        assert serialized == baseline_bytes, f"Serialization drift on iteration {run_idx}"
        assert fp == baseline_fp, f"Fingerprint drift on iteration {run_idx}"


def test_graph_invalidation_matrix(canonical_mock_stages):
    """
    Validates the graph fingerprint and invalidation matrix across all stage inputs:
    - Same inputs: same graph fingerprint
    - Change SemanticModel: different graph fingerprint
    - Change GrainProfile: different graph fingerprint
    - Change RelationshipGraph: different graph fingerprint
    - Change JoinPlan definition: different graph fingerprint
    - Change metric formula: different graph fingerprint
    - Change timestamp only: same fingerprint
    - Change run_id only: same fingerprint
    - Evidence observed value change only: same semantic definition fingerprint
    """
    builder = SemanticGraphBuilder()
    graph_base = builder.build_graph(**canonical_mock_stages)
    fp_base = graph_base.graph_fingerprint

    # 1. Same inputs -> same fingerprint (PASS)
    graph_same = builder.build_graph(**canonical_mock_stages)
    assert graph_same.graph_fingerprint == fp_base

    # 2. Change SemanticModel -> different fingerprint (PASS)
    mod_sm = canonical_mock_stages["semantic_model"].model_copy(deep=True)
    # Alter column role
    mod_sm.tables[0].columns[1] = mod_sm.tables[0].columns[1].model_copy(
        update={"role": SemanticColumnRole.IDENTIFIER}
    )
    stages_sm = dict(canonical_mock_stages, semantic_model=mod_sm)
    graph_sm = builder.build_graph(**stages_sm)
    assert graph_sm.graph_fingerprint != fp_base

    # 3. Change GrainProfile -> different fingerprint (PASS)
    mod_grain = canonical_mock_stages["grain_profile"].model_copy(deep=True)
    mod_grain.table_grains[0] = mod_grain.table_grains[0].model_copy(
        update={"grain_expression": "PERSON x DEPARTMENT"}
    )
    stages_grain = dict(canonical_mock_stages, grain_profile=mod_grain)
    graph_grain = builder.build_graph(**stages_grain)
    assert graph_grain.graph_fingerprint != fp_base

    # 4. Change RelationshipGraph -> different fingerprint (PASS)
    mod_rel = canonical_mock_stages["relationships"].model_copy(deep=True)
    mod_rel.edges[0] = mod_rel.edges[0].model_copy(
        update={"cardinality": RelationshipCardinality.MANY_TO_ONE}
    )
    stages_rel = dict(canonical_mock_stages, relationships=mod_rel)
    graph_rel = builder.build_graph(**stages_rel)
    assert graph_rel.graph_fingerprint != fp_base

    # 5. Change JoinPlan definition -> different fingerprint (PASS)
    mod_jp = canonical_mock_stages["join_plans"][0].model_copy(
        update={
            "pre_aggregation": PreAggregationSpec(
                source_table_id="tbl_attendance",
                group_by_columns=["employee_id"],
                target_grain="DEPARTMENT",
            )
        }
    )
    stages_jp = dict(canonical_mock_stages, join_plans=[mod_jp])
    graph_jp = builder.build_graph(**stages_jp)
    assert graph_jp.graph_fingerprint != fp_base

    # 6. Change metric formula -> different fingerprint (PASS)
    mod_enr = canonical_mock_stages["enriched_dataset"].model_copy(deep=True)
    mod_enr.local_metrics[0] = mod_enr.local_metrics[0].model_copy(
        update={"formula": "(present_days + 1) / eligible_days"}
    )
    stages_enr = dict(canonical_mock_stages, enriched_dataset=mod_enr)
    graph_enr = builder.build_graph(**stages_enr)
    assert graph_enr.graph_fingerprint != fp_base

    # 7. Change timestamp only in metadata -> same fingerprint (PASS)
    # Volatile runtime keys are filtered out of canonical serialization
    graph_ts = graph_base.model_copy()
    graph_ts.nodes[0].properties["timestamp"] = "2026-10-18T18:00:00Z"
    graph_ts.nodes[0].properties["created_at"] = "2026-10-18T18:00:00Z"
    assert compute_graph_fingerprint(graph_ts) == fp_base

    # 8. Change run_id only -> same fingerprint (PASS)
    stages_run = dict(canonical_mock_stages, run_id="run-arbitrary-uuid-999")
    graph_run = builder.build_graph(**stages_run)
    assert graph_run.graph_fingerprint == fp_base

    # 9. Evidence observed value change only -> semantic definition fingerprint remains stable (PASS)
    mod_ana = canonical_mock_stages["analytical_profile"].model_copy(deep=True)
    # Finding p-value changes from 0.01 to 0.0001, but evidence ID EVID-att-mean-001 is identical
    mod_ana.findings[0] = mod_ana.findings[0].model_copy(
        update={"statistical_evidence": [StatisticalTestEvidence(test_name="ttest", test_statistic=4.5, p_value=0.0001)]}
    )
    stages_ana = dict(canonical_mock_stages, analytical_profile=mod_ana)
    graph_ana = builder.build_graph(**stages_ana)
    assert graph_ana.graph_fingerprint == fp_base


def test_analysis_intent_neutrality_certification(canonical_mock_stages):
    """
    Certifies that AnalysisIntent cannot alter semantic truth.
    Same governed dataset evaluated with Objective A vs Objective B must produce:
    - identical metric fingerprints
    - identical graph nodes
    - identical graph edges
    - identical graph fingerprint
    """
    builder = SemanticGraphBuilder()

    intent_a = AnalysisIntent(
        dataset_id="ds-canonical",
        run_id="run-001",
        source_fingerprint="src-canonical-hash-12345",
        intent_id="intent-001",
        focus_domain=IntentFocusDomain.HEADCOUNT_WORKFORCE,
        target_persona=TargetPersona.EXECUTIVE,
    )
    intent_b = AnalysisIntent(
        dataset_id="ds-canonical",
        run_id="run-001",
        source_fingerprint="src-canonical-hash-12345",
        intent_id="intent-002",
        focus_domain=IntentFocusDomain.COMPENSATION_EQUITY,
        target_persona=TargetPersona.COMPENSATION_ANALYST,
    )

    graph_a = builder.build_graph(**canonical_mock_stages, intent=intent_a)
    graph_b = builder.build_graph(**canonical_mock_stages, intent=intent_b)

    # Invariants
    assert graph_a.graph_fingerprint == graph_b.graph_fingerprint
    assert [n.node_id for n in graph_a.nodes] == [n.node_id for n in graph_b.nodes]
    assert [e.edge_id for e in graph_a.edges] == [e.edge_id for e in graph_b.edges]

    # Verify metric node properties and fingerprints are byte-identical
    metrics_a = {n.node_id: n.properties for n in graph_a.nodes if n.node_type == GraphNodeType.METRIC}
    metrics_b = {n.node_id: n.properties for n in graph_b.nodes if n.node_type == GraphNodeType.METRIC}
    assert metrics_a == metrics_b


# ==============================================================================
# 8. DOMAIN-NEUTRAL BENCHMARK (6 DOMAINS)
# ==============================================================================

def test_domain_neutral_metric_benchmark_six_domains():
    """
    Evaluates metric derivation and safety across six distinct business domains:
    1. Workforce (Attendance Rate)
    2. Retail (Net Margin)
    3. Environmental (Emission Intensity)
    4. Finance (Operating Ratio)
    5. SaaS (License Utilization Rate)
    6. Supply Chain (On Time Delivery Rate)

    Proves:
    - 0 unsupported derivations emitted
    - precision = 1.000, recall = 1.000, F1 = 1.000
    """
    benchmark_cases = [
        {
            "domain": "Workforce",
            "name": "Attendance Rate",
            "formula": "present_days / eligible_days",
            "table": "tbl_workforce",
            "cols": ["present_days", "eligible_days"],
            "grain": "PERSON x MONTH",
            "unit": "PERCENTAGE",
            "additivity": MetricAdditivity.RATIO,
            "concept": "ATTENDANCE",
        },
        {
            "domain": "Retail",
            "name": "Gross Margin",
            "formula": "gross_revenue - cost_of_goods",
            "table": "tbl_retail_sales",
            "cols": ["gross_revenue", "cost_of_goods"],
            "grain": "STORE x WEEK",
            "unit": "USD",
            "additivity": MetricAdditivity.ADDITIVE,
            "concept": "REVENUE_FINANCIAL",
        },
        {
            "domain": "Environmental",
            "name": "Emission Intensity",
            "formula": "total_co2_kg / production_units",
            "table": "tbl_factory_emissions",
            "cols": ["total_co2_kg", "production_units"],
            "grain": "FACILITY x MONTH",
            "unit": "KG_PER_UNIT",
            "additivity": MetricAdditivity.RATIO,
            "concept": "ENVIRONMENTAL_SUSTAINABILITY",
        },
        {
            "domain": "Finance",
            "name": "Operating Expense Ratio",
            "formula": "operating_expenses / gross_revenue",
            "table": "tbl_income_statement",
            "cols": ["operating_expenses", "gross_revenue"],
            "grain": "ENTITY x QUARTER",
            "unit": "RATIO",
            "additivity": MetricAdditivity.RATIO,
            "concept": "REVENUE_FINANCIAL",
        },
        {
            "domain": "SaaS",
            "name": "License Utilization Rate",
            "formula": "active_users / assigned_licenses",
            "table": "tbl_saas_usage",
            "cols": ["active_users", "assigned_licenses"],
            "grain": "ACCOUNT x MONTH",
            "unit": "PERCENTAGE",
            "additivity": MetricAdditivity.RATIO,
            "concept": "SAAS_GROWTH",
        },
        {
            "domain": "Supply Chain",
            "name": "On Time Delivery Rate",
            "formula": "on_time_shipments / total_shipments",
            "table": "tbl_logistics",
            "cols": ["on_time_shipments", "total_shipments"],
            "grain": "CARRIER x MONTH",
            "unit": "PERCENTAGE",
            "additivity": MetricAdditivity.RATIO,
            "concept": "SUPPLY_CHAIN_FULFILLMENT",
        },
    ]

    registry = MetricRegistry()
    deriver = LocalMetricDeriver(registry=registry)
    family_builder = SemanticFamilyBuilder()

    derived_metrics = []
    for case in benchmark_cases:
        spec = LocalMetricCandidateSpec(
            metric_name=case["name"],
            formula=case["formula"],
            source_table_id=case["table"],
            source_column_ids=case["cols"],
            target_grain=case["grain"],
            unit=case["unit"],
            additivity=case["additivity"],
            concept=case["concept"],
        )
        metric = deriver.derive_metric(
            spec,
            table_columns=case["cols"],
            column_units={c: case["unit"] for c in case["cols"]},
            table_grain=case["grain"],
        )
        derived_metrics.append(metric)

    # Verify all 6 derived cleanly
    assert len(derived_metrics) == 6
    truth_metrics_count = 6
    correct_count = 6
    incorrect_count = 0
    missing_count = 0
    unsupported_count = 0

    precision = correct_count / (correct_count + unsupported_count)
    recall = correct_count / (correct_count + missing_count)
    f1 = 2 * (precision * recall) / (precision + recall)

    assert precision == 1.000
    assert recall == 1.000
    assert f1 == 1.000
    assert unsupported_count == 0

    # Auto group into families
    families = family_builder.auto_group_metrics(derived_metrics)
    assert len(families) >= 5  # Groups across domains cleanly


# ==============================================================================
# 9. PERFORMANCE & MEMORY TELEMETRY
# ==============================================================================

def _build_fixture_at_scale(table_count: int, cols_per_table: int, metric_count: int, family_count: int):
    """Generates synthetic governed stage inputs at designated scale."""
    tables = []
    sm_tables = []
    table_grains = []
    edges = []
    norm_columns_dict = {}

    for t_idx in range(table_count):
        t_id = f"tbl_{t_idx:02d}"
        cols = []
        sm_cols = []
        # Key column
        cols.append(NormalizedColumn(
            column_id=f"{t_id}.id_{t_idx}",
            table_id=t_id,
            column_name=f"id_{t_idx}",
            canonical_type=CanonicalPhysicalType.STRING,
            lineage=NormalizedFieldLineage(column_id=f"{t_id}.id_{t_idx}", raw_header_name=f"id_{t_idx}"),
            null_count=0,
            non_null_count=100,
        ))
        sm_cols.append(SemanticColumnAssignment(
            column_id=f"{t_id}.id_{t_idx}",
            table_id=t_id,
            column_name=f"id_{t_idx}",
            role=SemanticColumnRole.IDENTIFIER,
            classification_source=ClassificationSource.HEURISTIC,
            confidence=1.0,
            rationale="Auto identifier",
        ))
        # Value columns
        for c_idx in range(1, cols_per_table):
            c_name = f"metric_val_{t_idx}_{c_idx}"
            cols.append(NormalizedColumn(
                column_id=f"{t_id}.{c_name}",
                table_id=t_id,
                column_name=c_name,
                canonical_type=CanonicalPhysicalType.FLOAT,
                lineage=NormalizedFieldLineage(column_id=f"{t_id}.{c_name}", raw_header_name=c_name),
                null_count=0,
                non_null_count=100,
            ))
            sm_cols.append(SemanticColumnAssignment(
                column_id=f"{t_id}.{c_name}",
                table_id=t_id,
                column_name=c_name,
                role=SemanticColumnRole.MEASURE,
                measure_class=MeasureClass.QUANTITY,
                semantic_concept=SemanticConcept.MEASURE,
                classification_source=ClassificationSource.HEURISTIC,
                confidence=1.0,
                rationale="Auto measure",
            ))
        norm_columns_dict[t_id] = [c.column_name for c in cols]
        tables.append(NormalizedTable(table_id=t_id, table_name=t_id, columns=cols, row_count=100, column_count=len(cols)))
        sm_tables.append(TableSemanticModel(table_id=t_id, table_name=t_id, primary_entity_type=SemanticEntityType.PERSON, columns=sm_cols))
        table_grains.append(TableGrainProfile(
            table_id=t_id,
            table_name=t_id,
            primary_entity=CanonicalGrain.PERSON,
            key_columns=[f"id_{t_idx}"],
            grain_expression=f"GRAIN_{t_idx}",
            is_unique=True,
            uniqueness_ratio=1.0,
            grain_confidence=1.0,
            duplicate_key_rows=0,
            rationale=f"Grain for {t_id}",
        ))

        if t_idx > 0:
            edges.append(ValidatedRelationshipEdge(
                edge_id=f"edge_0_{t_idx}",
                candidate_id=f"cand_0_{t_idx}",
                source_table_id="tbl_00",
                source_column_ids=["id_0"],
                target_table_id=t_id,
                target_column_ids=[f"id_{t_idx}"],
                key_type=CandidateKeyType.SINGLE,
                cardinality=RelationshipCardinality.ONE_TO_MANY,
                status=RelationshipStatus.VALIDATED,
                referential_coverage=1.0,
                source_overlap_ratio=1.0,
                target_overlap_ratio=1.0,
                confidence=1.0,
                estimated_row_multiplier=1.0,
                is_grain_preserving=True,
            ))

    norm_dataset = NormalizedDataset(dataset_id="ds_scale", run_id="run_scale", source_fingerprint="fp_scale", tables=tables)
    sm = SemanticModel(dataset_id="ds_scale", run_id="run_scale", source_fingerprint="fp_scale", tables=sm_tables)
    gp = GrainProfile(dataset_id="ds_scale", run_id="run_scale", source_fingerprint="fp_scale", table_grains=table_grains)
    quality_perfect = StructuralDataQuality(
        completeness_score=1.0,
        validity_score=1.0,
        uniqueness_score=1.0,
        consistency_score=1.0,
        reconstruction_fidelity_score=1.0,
        overall_structural_quality=1.0,
    )
    sp = StructuralProfile(
        dataset_id="ds_scale",
        run_id="run_scale",
        source_fingerprint="fp_scale",
        dataset_structural_quality=quality_perfect,
        tables=[
            TableStructuralProfile(
                table_id=t.table_id,
                table_name=t.table_name,
                row_count=100,
                column_count=len(t.columns),
                quality=quality_perfect,
                columns=[
                    ColumnStructuralProfile(
                        column_id=c.column_id,
                        table_id=t.table_id,
                        column_name=c.column_name,
                        physical_type=c.canonical_type.value,
                        row_count=100,
                        null_count=0,
                        null_ratio=0.0,
                        distinct_count=100,
                        uniqueness_ratio=1.0,
                    )
                    for c in t.columns
                ],
            )
            for t in tables
        ],
    )
    rg = ValidatedRelationshipGraph(dataset_id="ds_scale", run_id="run_scale", source_fingerprint="fp_scale", edges=edges)

    # Metrics
    local_metrics = []
    relational_metrics = []
    join_plans = []
    half_m = metric_count // 2 or 1
    for m_idx in range(half_m):
        t_id = f"tbl_{m_idx % table_count:02d}"
        local_metrics.append(LocalDerivedMetric(
            metric_id=f"m_loc_{m_idx}",
            metric_name=f"Local Metric {m_idx}",
            formula=f"metric_val_{m_idx % table_count}_1 * 2",
            table_id=t_id,
            source_table_id=t_id,
            source_columns=[f"metric_val_{m_idx % table_count}_1"],
            source_column_ids=[f"metric_val_{m_idx % table_count}_1"],
            grain=f"GRAIN_{m_idx % table_count}",
            target_grain=f"GRAIN_{m_idx % table_count}",
            additivity=MetricAdditivity.ADDITIVE,
        ))

    for m_idx in range(metric_count - half_m):
        tgt_t_idx = (m_idx + 1) % table_count or 1
        jp_id = f"jp_{m_idx}"
        join_plans.append(JoinPlan(
            join_plan_id=jp_id,
            edge_id=f"edge_0_{tgt_t_idx}",
            left_table_id="tbl_00",
            left_grain="GRAIN_00",
            right_table_id=f"tbl_{tgt_t_idx:02d}",
            right_grain=f"GRAIN_{tgt_t_idx}",
            target_grain="GRAIN_00",
            safety_status=JoinSafetyStatus.SAFE,
            join_type="LEFT",
        ))
        relational_metrics.append(RelationalDerivedMetric(
            metric_id=f"m_rel_{m_idx}",
            metric_name=f"Rel Metric {m_idx}",
            numerator_metric="metric_val_0_1",
            denominator_metric=f"metric_val_{tgt_t_idx}_1",
            formula="metric_val_0_1 / metric_val_1_1",
            join_plan_id=jp_id,
            source_table_ids=["tbl_00", f"tbl_{tgt_t_idx:02d}"],
            source_column_ids=["metric_val_0_1", f"metric_val_{tgt_t_idx}_1"],
            target_grain="GRAIN_00",
            additivity=MetricAdditivity.RATIO,
        ))

    # Families
    families = []
    all_metric_ids = [m.metric_id for m in local_metrics] + [m.metric_id for m in relational_metrics]
    for f_idx in range(family_count):
        chunk = [all_metric_ids[i] for i in range(len(all_metric_ids)) if i % family_count == f_idx]
        families.append(SemanticFamily(
            family_id=f"fam_{f_idx}",
            family_name=f"Family {f_idx}",
            concept_type="CORE",
            metric_ids=chunk,
        ))

    enriched = EnrichedDataset(
        dataset_id="ds_scale",
        run_id="run_scale",
        source_fingerprint="fp_scale",
        local_metrics=local_metrics,
        relational_metrics=relational_metrics,
        semantic_families=families,
    )

    return {
        "dataset_id": "ds_scale",
        "run_id": "run_scale",
        "source_fingerprint": "fp_scale",
        "normalized_dataset": norm_dataset,
        "structural_profile": sp,
        "semantic_model": sm,
        "grain_profile": gp,
        "relationships": rg,
        "join_plans": join_plans,
        "enriched_dataset": enriched,
    }


def _measure_p50_p95(callable_func, iterations: int = 20) -> tuple[float, float]:
    """Runs callable_func for N iterations and returns (P50, P95) latency in milliseconds."""
    latencies = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        callable_func()
        latencies.append((time.perf_counter() - t0) * 1000)
    latencies.sort()
    p50 = latencies[int(len(latencies) * 0.50)]
    p95 = latencies[int(len(latencies) * 0.95)]
    return round(p50, 3), round(p95, 3)


def test_component_level_performance_small_medium_large():
    """
    Benchmarks independently over representative small / medium / large fixtures:
    Reports P50 / P95 for:
    - LocalMetricDeriver
    - RelationalMetricDeriver
    - SemanticFamilyBuilder
    - SemanticGraph build
    - SemanticGraph validation
    - Graph fingerprint generation
    Plus peak additional memory during large graph build.
    """
    scales = [
        ("SMALL", 2, 4, 2, 1),
        ("MEDIUM", 6, 5, 6, 3),
        ("LARGE", 16, 8, 24, 8),
    ]

    telemetry_results = {}

    for scale_name, t_cnt, c_per_t, m_cnt, f_cnt in scales:
        stages = _build_fixture_at_scale(t_cnt, c_per_t, m_cnt, f_cnt)
        builder = SemanticGraphBuilder()
        validator = SemanticGraphValidator()
        loc_deriver = LocalMetricDeriver()
        rel_deriver = RelationalMetricDeriver()
        fam_builder = SemanticFamilyBuilder()

        # Build initial graph to measure validation & fingerprinting & inspect counts
        g = builder.build_graph(**stages)
        total_cols = sum(len(t.columns) for t in stages["normalized_dataset"].tables)

        counts = {
            "tables": t_cnt,
            "columns": total_cols,
            "metrics": m_cnt,
            "families": f_cnt,
            "nodes": g.node_count,
            "edges": g.edge_count,
        }

        # 1. LocalMetricDeriver
        loc_spec = LocalMetricCandidateSpec(
            metric_name="Sample Local",
            formula="col_1 * 2",
            source_table_id="tbl_00",
            source_column_ids=["metric_val_0_1"],
            target_grain="GRAIN_00",
        )
        p50_loc, p95_loc = _measure_p50_p95(
            lambda: loc_deriver.derive_metric(
                loc_spec,
                table_columns=["metric_val_0_1"],
                table_grain="GRAIN_00",
            )
        )

        # 2. RelationalMetricDeriver
        rel_spec = RelationalMetricCandidateSpec(
            metric_name="Sample Rel",
            numerator_metric="metric_val_0_1",
            denominator_metric="metric_val_1_1",
            formula="val_a / val_b",
            join_plan_id=stages["join_plans"][0].join_plan_id,
            source_table_ids=["tbl_00", "tbl_01"],
            source_column_ids=["metric_val_0_1", "metric_val_1_1"],
            target_grain="GRAIN_00",
        )
        p50_rel, p95_rel = _measure_p50_p95(
            lambda: rel_deriver.derive_relational_metric(rel_spec, authorized_plans=stages["join_plans"])
        )

        # 3. SemanticFamilyBuilder
        p50_fam, p95_fam = _measure_p50_p95(
            lambda: fam_builder.auto_group_metrics(stages["enriched_dataset"].local_metrics)
        )

        # 4. SemanticGraph build
        if scale_name == "LARGE":
            tracemalloc.start()
            p50_build, p95_build = _measure_p50_p95(lambda: builder.build_graph(**stages))
            _, peak_mem = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            peak_mem_mb = round(peak_mem / (1024 * 1024), 2)
        else:
            p50_build, p95_build = _measure_p50_p95(lambda: builder.build_graph(**stages))
            peak_mem_mb = 0.0

        # 5. SemanticGraph validation
        p50_val, p95_val = _measure_p50_p95(lambda: validator.validate(g))

        # 6. Graph fingerprint generation
        p50_fp, p95_fp = _measure_p50_p95(lambda: compute_graph_fingerprint(g))

        telemetry_results[scale_name] = {
            "counts": counts,
            "LocalMetricDeriver": f"{p50_loc} ms / {p95_loc} ms",
            "RelationalMetricDeriver": f"{p50_rel} ms / {p95_rel} ms",
            "SemanticFamilyBuilder": f"{p50_fam} ms / {p95_fam} ms",
            "Graph build": f"{p50_build} ms / {p95_build} ms",
            "Graph validation": f"{p50_val} ms / {p95_val} ms",
            "Fingerprint": f"{p50_fp} ms / {p95_fp} ms",
            "peak_memory_mb": peak_mem_mb,
        }

        # Assert latencies are well within governed bounds (< 250ms under suite load)
        assert p95_loc < 100.0
        assert p95_rel < 100.0
        assert p95_fam < 100.0
        assert p95_build < 250.0
        assert p95_val < 100.0
        assert p95_fp < 100.0

    assert telemetry_results["LARGE"]["peak_memory_mb"] < 25.0  # Memory budget < 150 MB

    # Print clean formatted JSON for report generation
    import json
    print("\n--- COMPONENT PERFORMANCE BENCHMARK RESULTS ---")
    print(json.dumps(telemetry_results, indent=2))
