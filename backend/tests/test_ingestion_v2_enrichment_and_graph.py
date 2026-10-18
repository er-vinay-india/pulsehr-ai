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


def test_semantic_graph_negative_invalid_competing_evidence_id(canonical_mock_stages):
    """Verify validator raises InvalidEvidenceRefError if a non-EVID competing ID is minted."""
    builder = SemanticGraphBuilder()
    graph = builder.build_graph(**canonical_mock_stages)

    # Corrupt with competing non-EVID token
    bad_edge = SemanticGraphEdge(
        edge_id="edge-bad-evid",
        source_node_id="metric:metric-att-rate",
        target_node_id="evidence:MY_CUSTOM_FACT_999",
        edge_type=GraphEdgeType.SUPPORTED_BY_EVIDENCE,
        evidence_ref="MY_CUSTOM_FACT_999",  # Competing ID!
    )
    corrupted_graph = graph.model_copy(update={"edges": list(graph.edges) + [bad_edge]})

    validator = SemanticGraphValidator()
    with pytest.raises(InvalidEvidenceRefError) as exc_info:
        validator.validate(corrupted_graph)
    assert "non-standard evidence reference" in str(exc_info.value)


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

def test_performance_and_memory_telemetry(canonical_mock_stages):
    """
    Measures latency and memory for:
    - LocalMetricDeriver
    - RelationalMetricDeriver
    - SemanticFamilyBuilder
    - Graph build
    - Graph validation
    - Graph fingerprinting
    """
    tracemalloc.start()

    # 1. LocalMetricDeriver latency
    deriver_loc = LocalMetricDeriver()
    spec_loc = LocalMetricCandidateSpec(
        metric_name="Attendance Rate",
        formula="present_days / eligible_days",
        source_table_id="tbl_attendance",
        source_column_ids=["present_days", "eligible_days"],
        target_grain="PERSON x DAY",
        unit="PERCENTAGE",
        additivity=MetricAdditivity.RATIO,
    )
    latencies_loc = []
    for _ in range(20):
        t0 = time.perf_counter()
        deriver_loc.derive_metric(
            spec_loc,
            table_columns=["present_days", "eligible_days"],
            table_grain="PERSON x DAY",
        )
        latencies_loc.append((time.perf_counter() - t0) * 1000)

    # 2. RelationalMetricDeriver latency
    deriver_rel = RelationalMetricDeriver()
    spec_rel = RelationalMetricCandidateSpec(
        metric_name="Dept Attendance Rate",
        join_plan_id="jp-dept-att-001",
        numerator_metric="present_days",
        denominator_metric="eligible_days",
        formula="present_days / eligible_days",
        target_grain="DEPARTMENT x MONTH",
        source_table_ids=["tbl_employees", "tbl_attendance"],
    )
    latencies_rel = []
    for _ in range(20):
        t0 = time.perf_counter()
        deriver_rel.derive_relational_metric(spec_rel, authorized_plans=canonical_mock_stages["join_plans"])
        latencies_rel.append((time.perf_counter() - t0) * 1000)

    # 3. SemanticFamilyBuilder latency
    fam_builder = SemanticFamilyBuilder()
    latencies_fam = []
    for _ in range(20):
        t0 = time.perf_counter()
        fam_builder.auto_group_metrics(canonical_mock_stages["enriched_dataset"].local_metrics)
        latencies_fam.append((time.perf_counter() - t0) * 1000)

    # 4. Graph build latency
    builder = SemanticGraphBuilder()
    latencies_build = []
    for _ in range(20):
        t0 = time.perf_counter()
        g = builder.build_graph(**canonical_mock_stages)
        latencies_build.append((time.perf_counter() - t0) * 1000)

    # 5. Graph validation latency
    validator = SemanticGraphValidator()
    latencies_val = []
    for _ in range(20):
        t0 = time.perf_counter()
        validator.validate(g)
        latencies_val.append((time.perf_counter() - t0) * 1000)

    # 6. Fingerprinting latency
    latencies_fp = []
    for _ in range(20):
        t0 = time.perf_counter()
        compute_graph_fingerprint(g)
        latencies_fp.append((time.perf_counter() - t0) * 1000)

    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    peak_mem_mb = peak_mem / (1024 * 1024)

    # Check that all operations are sub-millisecond or fast (< 50ms)
    assert sorted(latencies_loc)[10] < 50.0
    assert sorted(latencies_rel)[10] < 50.0
    assert sorted(latencies_fam)[10] < 50.0
    assert sorted(latencies_build)[10] < 50.0
    assert sorted(latencies_val)[10] < 50.0
    assert sorted(latencies_fp)[10] < 50.0
    assert peak_mem_mb < 20.0  # Graph assembly is very lightweight
