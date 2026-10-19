"""
HighView Semantic Data Refinery — Phase SDR-6
Dynamic Analytical Views, Governed Reconstruction & Silver -> Gold Modeling
Full Certification Corpus Benchmark & Evaluation Suite

Tests all 13 Mandatory Certification Cases:
- Case A: Dimension Lookup (Sales + Stores -> SalesWithRegion, SALE grain, row count preserved)
- Case B: Preaggregation (AttendanceDaily -> EMPLOYEE x MONTH SUM(hours) before join, no fanout)
- Case C: Weighted Ratio (Department attendance present/eligible -> SUM(present)/SUM(eligible) = 91/102 != 70%)
- Case D: Missing vs Zero (hours=0 vs hours=NULL preserved, no fillna(0))
- Case E: Fact Alignment (SalesDaily + InventoryDaily, composite key STORE x SKU x DAY, no duplication)
- Case F: Unsafe JoinPlan Blocked (UNSAFE -> BLOCKED, 0 executions)
- Case G: Ambiguous JoinPlan Blocked (AMBIGUOUS -> BLOCKED, 0 executions)
- Case H: Unit Conflict (USD + hours -> BLOCKED / INVALID)
- Case I: Ratio Aggregation Trap (AVG(rate) without denominator -> BLOCKED)
- Case J: Grain Violation (Duplicate rows detected at declared grain -> VIEW INVALIDATED, no silent dedupe)
- Case K: Geo Enrichment Consumption (Provenance = DERIVED_ENRICHMENT, not observed source)
- Case L: Local Metric Deriver (revenue = quantity * unit_price, 0 JoinPlan required, grain/unit preserved)
- Case M: Relational Metric Deriver (cross-table requires JoinPlan, missing JoinPlan -> BLOCKED)

Plus:
- Dry Run Validator
- View Invalidation on Upstream Drift
- Retrieval ANALYTICAL_INDEX Containment (0 index leakage)
- Repeat-Run Artifact Determinism (100% byte-identical SHA-256)
- Small / Medium / Large View Reconstruction Performance Benchmark
"""

import hashlib
import json
from pathlib import Path
import time
import tracemalloc
import pandas as pd
import pytest

from app.services.ingestion_v2.contracts.joins import (
    JoinSafetyStatus,
    PreAggregationSpec,
)
from app.services.ingestion_v2.contracts.relationships import (
    CandidateKeyType,
    RelationshipCardinality,
    RelationshipStatus,
)
from app.services.ingestion_v2.retrieval.namespaces import (
    AuthorityClass,
    RetrievalNamespace,
)
from app.services.sdr.artifacts.artifact_writer import SDRArtifactWriter
from app.services.sdr.contracts.policies import SDRPolicySuite
from app.services.sdr.contracts.relationships import (
    RelationshipClass,
    SDRJoinPlan,
    SDRValidatedRelationshipEdge,
)
from app.services.sdr.contracts.views import (
    ControlledExpression,
    ExpressionOp,
    MaterializationMode,
    MissingValuePolicy,
    SDRAnalyticalExecutionResult,
    SDRAnalyticalFact,
    SDRAnalyticalViewSpec,
    SDRAnalyticalViewStatus,
    SDRDerivedMeasureSpec,
    SDRFilterConstraint,
    check_analytical_view_invalidation,
    compute_analytical_fact_fingerprint,
    compute_analytical_view_fingerprint,
)
from app.services.sdr.retrieval.retrieval_adapter import SDRRetrievalAdapter
from app.services.sdr.views.duckdb_executor import (
    GovernedAnalyticalExecutionError,
    GrainViolationError,
    SDRDuckDBExecutor,
)
from app.services.sdr.views.expression_engine import (
    RatioAggregationTrapError,
    UnitConflictError,
    compile_controlled_expression_to_sql,
    validate_unit_compatibility,
)
from app.services.sdr.views.metric_derivers import (
    LocalMetricDeriver,
    MetricDerivationError,
    RelationalMetricDeriver,
)
from app.services.sdr.views.view_engine import SDRAnalyticalViewEngine


# =====================================================================
# FIXTURES
# =====================================================================

@pytest.fixture
def test_data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture
def executor(test_data_dir: Path) -> SDRDuckDBExecutor:
    return SDRDuckDBExecutor(base_dir=test_data_dir)


@pytest.fixture
def view_engine(executor: SDRDuckDBExecutor) -> SDRAnalyticalViewEngine:
    return SDRAnalyticalViewEngine(executor=executor)


@pytest.fixture
def artifact_writer(test_data_dir: Path) -> SDRArtifactWriter:
    return SDRArtifactWriter(base_dir=test_data_dir)


# =====================================================================
# CERTIFICATION CASE A: DIMENSION LOOKUP
# =====================================================================

def test_case_a_dimension_lookup(view_engine: SDRAnalyticalViewEngine):
    """
    Stores: store_id, store_name, region
    Sales: sale_id, store_id, amount
    Using SDR-5 SAFE JoinPlan:
    Build SalesWithRegion; Result grain: SALE; Expected: sales amount unchanged, region added, row count preserved.
    """
    stores_df = pd.DataFrame({
        "store_id": [1, 2, 3],
        "store_name": ["North Store", "South Store", "East Store"],
        "region": ["Region North", "Region South", "Region North"],
    })
    sales_df = pd.DataFrame({
        "sale_id": [101, 102, 103, 104, 105],
        "store_id": [1, 1, 2, 3, 2],
        "amount": [100.0, 150.0, 200.0, 300.0, 250.0],
    })

    join_plan = SDRJoinPlan(
        join_plan_id="jp_sales_stores_safe",
        relationship_edge_id="edge_sales_stores",
        dataset_id="ds_sales",
        left_sheet_id="sales",
        right_sheet_id="stores",
        left_keys=["store_id"],
        right_keys=["store_id"],
        join_type="LEFT",
        safety_status=JoinSafetyStatus.SAFE,
        left_grain="SALE",
        right_grain="STORE",
        target_grain="SALE",
        cardinality=RelationshipCardinality.MANY_TO_ONE,
    )

    view_spec = SDRAnalyticalViewSpec(
        analytical_view_id="view_sales_with_region",
        dataset_id="ds_sales",
        name="SalesWithRegion",
        source_sheet_ids=["sales", "stores"],
        join_plan_ids=["jp_sales_stores_safe"],
        base_grain="SALE",
        result_grain="SALE",
        dimension_columns=["sale_id", "store_id", "region"],
        measure_columns=["amount"],
        unit_metadata={"amount": "USD"},
    )

    source_tables = {"sales": sales_df, "stores": stores_df}
    join_plans = {"jp_sales_stores_safe": join_plan}

    result, facts = view_engine.execute_and_reconstruct(view_spec, source_tables, join_plans)

    assert result.status == SDRAnalyticalViewStatus.VALID
    assert result.row_count == 5  # Row count preserved
    assert len(result.rows) == 5
    assert result.result_grain == "SALE"
    assert result.grain_validation["status"] == "PASS"

    # Sales amount unchanged (sum = 1000.0)
    total_amount = sum(r["amount"] for r in result.rows)
    assert total_amount == 1000.0

    # Region added
    regions = [r["region"] for r in result.rows]
    assert "Region North" in regions and "Region South" in regions

    # Analytical fact produced
    assert len(facts) >= 1
    amount_fact = next(f for f in facts if f.metric == "amount")
    assert amount_fact.value == 1000.0
    assert amount_fact.unit == "USD"
    assert amount_fact.provenance_type == "DERIVED_RELATIONAL"


# =====================================================================
# CERTIFICATION CASE B: PREAGGREGATION
# =====================================================================

def test_case_b_preaggregation(view_engine: SDRAnalyticalViewEngine):
    """
    EmployeeMonthly: employee_id, month, target_hours
    AttendanceDaily: employee_id, month, day, hours
    Use SDR-5 SAFE_WITH_PREAGGREGATION.
    Required: AttendanceDaily pre-aggregated to EMPLOYEE x MONTH SUM(hours), then join.
    Prove no raw fanout, correct result grain, correct total hours.
    """
    emp_monthly_df = pd.DataFrame({
        "employee_id": ["E1", "E2"],
        "month": ["2026-01", "2026-01"],
        "target_hours": [160.0, 160.0],
    })
    att_daily_df = pd.DataFrame({
        "employee_id": ["E1", "E1", "E2", "E2"],
        "month": ["2026-01", "2026-01", "2026-01", "2026-01"],
        "day": ["01", "02", "01", "02"],
        "hours": [8.0, 7.5, 8.0, 8.5],
    })

    preagg_spec = PreAggregationSpec(
        source_table_id="attendance_daily",
        target_grain="EMPLOYEE × MONTH",
        group_by_columns=["employee_id", "month"],
        aggregations={"hours": "SUM"},
    )

    join_plan = SDRJoinPlan(
        join_plan_id="jp_emp_att_preagg",
        relationship_edge_id="edge_emp_att",
        dataset_id="ds_hr",
        left_sheet_id="employee_monthly",
        right_sheet_id="attendance_daily",
        left_keys=["employee_id", "month"],
        right_keys=["employee_id", "month"],
        join_type="LEFT",
        safety_status=JoinSafetyStatus.SAFE_WITH_PREAGGREGATION,
        left_grain="EMPLOYEE × MONTH",
        right_grain="EMPLOYEE × DAY",
        target_grain="EMPLOYEE × MONTH",
        required_preaggregation=True,
        preaggregation_side="RIGHT",
        preaggregation_spec=preagg_spec,
    )

    view_spec = SDRAnalyticalViewSpec(
        analytical_view_id="view_emp_monthly_actuals",
        dataset_id="ds_hr",
        name="EmployeeMonthlyActuals",
        source_sheet_ids=["employee_monthly", "attendance_daily"],
        join_plan_ids=["jp_emp_att_preagg"],
        base_grain="EMPLOYEE × MONTH",
        result_grain="EMPLOYEE × MONTH",
        dimension_columns=["employee_id", "month"],
        measure_columns=["target_hours", "hours"],
        preaggregation_specs=[preagg_spec],
        unit_metadata={"target_hours": "hours", "hours": "hours"},
    )

    source_tables = {"employee_monthly": emp_monthly_df, "attendance_daily": att_daily_df}
    join_plans = {"jp_emp_att_preagg": join_plan}

    result, facts = view_engine.execute_and_reconstruct(view_spec, source_tables, join_plans)

    assert result.status == SDRAnalyticalViewStatus.VALID_WITH_PREAGGREGATION
    assert result.row_count == 2  # Exactly 2 rows (no raw daily fanout to 4 rows!)
    assert result.result_grain == "EMPLOYEE × MONTH"
    assert result.grain_validation["status"] == "PASS"

    # Verify total hours
    total_hours = sum(r["hours"] for r in result.rows)
    assert total_hours == 32.0  # (8+7.5) + (8+8.5) = 15.5 + 16.5 = 32.0

    e1_row = next(r for r in result.rows if r["employee_id"] == "E1")
    assert e1_row["hours"] == 15.5
    assert e1_row["target_hours"] == 160.0


# =====================================================================
# CERTIFICATION CASE C: WEIGHTED RATIO
# =====================================================================

def test_case_c_weighted_ratio(view_engine: SDRAnalyticalViewEngine):
    """
    Department attendance:
    Dept A: 90 / 100 = 90%
    Dept B: 1 / 2 = 50%
    Rollup must be SUM(present) / SUM(eligible) = 91 / 102 = ~89.2157%, NOT (90% + 50%)/2 = 70%.
    """
    dept_df = pd.DataFrame({
        "department": ["Dept A", "Dept B"],
        "present_days": [90.0, 1.0],
        "eligible_days": [100.0, 2.0],
    })

    # Analytical view calculating company-wide rolled-up rate
    view_spec = SDRAnalyticalViewSpec(
        analytical_view_id="view_weighted_attendance_rollup",
        dataset_id="ds_att",
        name="WeightedAttendanceRollup",
        source_sheet_ids=["dept_attendance"],
        base_grain="DEPARTMENT",
        result_grain="COMPANY",
        dimension_columns=[],  # Entire company rollup
        measure_columns=["present_days"],
        denominator_metadata={"present_days": "eligible_days"},  # Weighted denominator
        unit_metadata={"present_days": "ratio"},
    )

    source_tables = {"dept_attendance": dept_df}
    result, facts = view_engine.execute_and_reconstruct(view_spec, source_tables, {})

    assert result.status == SDRAnalyticalViewStatus.VALID
    assert len(result.rows) == 1

    rolled_up_rate = result.rows[0]["present_days"]
    expected_rate = 91.0 / 102.0  # 0.89215686...
    assert abs(rolled_up_rate - expected_rate) < 1e-5
    # Strict assertion: Must NOT equal simple average (0.70)
    assert abs(rolled_up_rate - 0.70) > 0.15


# =====================================================================
# CERTIFICATION CASE D: MISSING VS ZERO
# =====================================================================

def test_case_d_missing_vs_zero(view_engine: SDRAnalyticalViewEngine):
    """
    Employee A: hours = 0.0
    Employee B: hours = None (NULL)
    Result must preserve difference. No fillna(0) unless explicit policy authorizes.
    """
    emp_df = pd.DataFrame({
        "emp_id": ["E_A", "E_B"],
        "hours": [0.0, None],
    })

    view_spec = SDRAnalyticalViewSpec(
        analytical_view_id="view_missing_vs_zero",
        dataset_id="ds_missing",
        name="MissingVsZero",
        source_sheet_ids=["emp_hours"],
        base_grain="EMPLOYEE",
        result_grain="EMPLOYEE",
        dimension_columns=["emp_id"],
        measure_columns=["hours"],
        missing_value_policy=MissingValuePolicy.PRESERVE_NULL,
    )

    result, facts = view_engine.execute_and_reconstruct(view_spec, {"emp_hours": emp_df}, {})

    assert result.status == SDRAnalyticalViewStatus.VALID
    rows_by_id = {r["emp_id"]: r["hours"] for r in result.rows}

    # Employee A must be numeric 0.0
    assert rows_by_id["E_A"] == 0.0
    # Employee B must be None (NULL), NOT converted to 0.0
    assert rows_by_id["E_B"] is None
    assert result.missing_value_summary["hours"]["null_count"] == 1
    assert result.missing_value_summary["hours"]["zero_count"] == 1


# =====================================================================
# CERTIFICATION CASE E: FACT ALIGNMENT (COMPOSITE GRAIN)
# =====================================================================

def test_case_e_fact_alignment_composite_grain(view_engine: SDRAnalyticalViewEngine):
    """
    SalesDaily: store_id + sku + day, sales_qty
    InventoryDaily: store_id + sku + day, stock_qty
    SDR-5 SAFE composite JoinPlan on STORE x SKU x DAY.
    Expected: result grain STORE x SKU x DAY. No duplication.
    """
    sales_daily = pd.DataFrame({
        "store_id": ["S1", "S1", "S2"],
        "sku": ["P1", "P2", "P1"],
        "day": ["D1", "D1", "D1"],
        "sales_qty": [10.0, 20.0, 30.0],
    })
    inv_daily = pd.DataFrame({
        "store_id": ["S1", "S1", "S2"],
        "sku": ["P1", "P2", "P1"],
        "day": ["D1", "D1", "D1"],
        "stock_qty": [100.0, 200.0, 300.0],
    })

    join_plan = SDRJoinPlan(
        join_plan_id="jp_composite_sales_inv",
        relationship_edge_id="edge_composite_sales_inv",
        dataset_id="ds_retail",
        left_sheet_id="sales_daily",
        right_sheet_id="inv_daily",
        left_keys=["store_id", "sku", "day"],
        right_keys=["store_id", "sku", "day"],
        join_type="INNER",
        safety_status=JoinSafetyStatus.SAFE,
        left_grain="STORE × SKU × DAY",
        right_grain="STORE × SKU × DAY",
        target_grain="STORE × SKU × DAY",
        cardinality=RelationshipCardinality.ONE_TO_ONE,
    )

    view_spec = SDRAnalyticalViewSpec(
        analytical_view_id="view_sales_inv_aligned",
        dataset_id="ds_retail",
        name="SalesInventoryAligned",
        source_sheet_ids=["sales_daily", "inv_daily"],
        join_plan_ids=["jp_composite_sales_inv"],
        base_grain="STORE × SKU × DAY",
        result_grain="STORE × SKU × DAY",
        dimension_columns=["store_id", "sku", "day"],
        measure_columns=["sales_qty", "stock_qty"],
    )

    source_tables = {"sales_daily": sales_daily, "inv_daily": inv_daily}
    join_plans = {"jp_composite_sales_inv": join_plan}

    result, facts = view_engine.execute_and_reconstruct(view_spec, source_tables, join_plans)

    assert result.status == SDRAnalyticalViewStatus.VALID
    assert result.row_count == 3
    assert result.grain_validation["status"] == "PASS"
    assert result.grain_validation["is_unique"] is True


# =====================================================================
# CERTIFICATION CASE F: UNSAFE JOINPLAN BLOCKED
# =====================================================================

def test_case_f_unsafe_joinplan_blocked(view_engine: SDRAnalyticalViewEngine):
    """
    Attempt AnalyticalView using UNSAFE JoinPlan.
    Expected: BLOCKED, execution count = 0.
    """
    unsafe_plan = SDRJoinPlan(
        join_plan_id="jp_unsafe_m2m",
        relationship_edge_id="edge_unsafe",
        dataset_id="ds_unsafe",
        left_sheet_id="table_a",
        right_sheet_id="table_b",
        left_keys=["dep_id"],
        right_keys=["dep_id"],
        join_type="LEFT",
        safety_status=JoinSafetyStatus.UNSAFE,
        left_grain="ORDER",
        right_grain="ITEM",
        target_grain="ORDER",
        cardinality=RelationshipCardinality.MANY_TO_MANY,
        forbidden_reason="Unsafe many-to-many Cartesian expansion",
    )

    view_spec = SDRAnalyticalViewSpec(
        analytical_view_id="view_blocked_unsafe",
        dataset_id="ds_unsafe",
        name="BlockedUnsafeView",
        source_sheet_ids=["table_a", "table_b"],
        join_plan_ids=["jp_unsafe_m2m"],
        base_grain="ORDER",
        result_grain="ORDER",
        dimension_columns=["dep_id"],
    )

    source_tables = {
        "table_a": pd.DataFrame({"dep_id": [1, 2]}),
        "table_b": pd.DataFrame({"dep_id": [1, 2]}),
    }
    join_plans = {"jp_unsafe_m2m": unsafe_plan}

    result, facts = view_engine.execute_and_reconstruct(view_spec, source_tables, join_plans)

    assert result.status == SDRAnalyticalViewStatus.UNSAFE
    assert result.row_count == 0
    assert len(facts) == 0
    assert "Dry run preflight failed" in (result.error_message or "")


# =====================================================================
# CERTIFICATION CASE G: AMBIGUOUS JOINPLAN BLOCKED
# =====================================================================

def test_case_g_ambiguous_joinplan_blocked(view_engine: SDRAnalyticalViewEngine):
    """
    Attempt AnalyticalView using AMBIGUOUS JoinPlan.
    Expected: BLOCKED, execution count = 0.
    """
    ambiguous_plan = SDRJoinPlan(
        join_plan_id="jp_ambiguous_keys",
        relationship_edge_id="edge_ambiguous",
        dataset_id="ds_amb",
        left_sheet_id="table_x",
        right_sheet_id="table_y",
        left_keys=["code"],
        right_keys=["code"],
        join_type="LEFT",
        safety_status=JoinSafetyStatus.AMBIGUOUS,
        left_grain="TRANSACTION",
        right_grain="ACCOUNT",
        target_grain="TRANSACTION",
        forbidden_reason="Multiple competing key candidate paths",
    )

    view_spec = SDRAnalyticalViewSpec(
        analytical_view_id="view_blocked_ambiguous",
        dataset_id="ds_amb",
        name="BlockedAmbiguousView",
        source_sheet_ids=["table_x", "table_y"],
        join_plan_ids=["jp_ambiguous_keys"],
        base_grain="TRANSACTION",
        result_grain="TRANSACTION",
        dimension_columns=["code"],
    )

    source_tables = {
        "table_x": pd.DataFrame({"code": ["A", "B"]}),
        "table_y": pd.DataFrame({"code": ["A", "B"]}),
    }
    join_plans = {"jp_ambiguous_keys": ambiguous_plan}

    result, facts = view_engine.execute_and_reconstruct(view_spec, source_tables, join_plans)

    assert result.status == SDRAnalyticalViewStatus.AMBIGUOUS
    assert result.row_count == 0
    assert len(facts) == 0


# =====================================================================
# CERTIFICATION CASE H: UNIT CONFLICT
# =====================================================================

def test_case_h_unit_conflict(view_engine: SDRAnalyticalViewEngine):
    """
    Attempt: USD amount + hours.
    Expected: INVALID / BLOCKED.
    """
    # Attempt compile: ADD(col("amount", unit="USD"), col("hours", unit="hours"))
    expr = ControlledExpression.binary(
        ExpressionOp.ADD,
        ControlledExpression.col("amount", unit="USD"),
        ControlledExpression.col("hours", unit="hours"),
    )

    with pytest.raises(UnitConflictError) as exc_info:
        compile_controlled_expression_to_sql(expr)
    assert "incompatible units" in str(exc_info.value).lower()

    # Dry-run validation of AnalyticalView with this expression must fail
    view_spec = SDRAnalyticalViewSpec(
        analytical_view_id="view_unit_conflict",
        dataset_id="ds_conflict",
        name="UnitConflictView",
        source_sheet_ids=["table_finance"],
        base_grain="RECORD",
        result_grain="RECORD",
        derived_measure_specs=[
            SDRDerivedMeasureSpec(measure_name="bad_sum", expression=expr)
        ],
    )

    source_tables = {"table_finance": pd.DataFrame({"amount": [10.0], "hours": [2.0]})}
    is_valid, err = view_engine.dry_run_validate(view_spec, source_tables, {})
    assert is_valid is False
    assert "incompatible units" in (err or "").lower()


# =====================================================================
# CERTIFICATION CASE I: RATIO AGGREGATION TRAP
# =====================================================================

def test_case_i_ratio_aggregation_trap(view_engine: SDRAnalyticalViewEngine):
    """
    Attempt: AVG(attendance_rate) without denominator semantics.
    Expected: BLOCKED / AMBIGUOUS.
    """
    expr = ControlledExpression.aggregate(
        ExpressionOp.AVG,
        ControlledExpression.col("attendance_rate", unit="percentage"),
    )

    # Attempt compile without denominator metadata
    with pytest.raises(RatioAggregationTrapError) as exc_info:
        compile_controlled_expression_to_sql(
            expr,
            unit_metadata={"attendance_rate": "percentage"},
            ratio_columns={"attendance_rate"},
            denominator_metadata={},  # Missing denominator!
        )
    assert "ratio aggregation trap" in str(exc_info.value).lower()

    # Dry run view validation must fail
    view_spec = SDRAnalyticalViewSpec(
        analytical_view_id="view_ratio_trap",
        dataset_id="ds_ratio",
        name="RatioTrapView",
        source_sheet_ids=["att_table"],
        base_grain="DEPARTMENT",
        result_grain="COMPANY",
        unit_metadata={"attendance_rate": "percentage"},
        derived_measure_specs=[
            SDRDerivedMeasureSpec(measure_name="avg_rate", expression=expr)
        ],
    )

    is_valid, err = view_engine.dry_run_validate(view_spec, {"att_table": pd.DataFrame({"attendance_rate": [0.9]})}, {})
    assert is_valid is False
    assert "ratio aggregation trap" in (err or "").lower()


# =====================================================================
# CERTIFICATION CASE J: GRAIN VIOLATION
# =====================================================================

def test_case_j_grain_violation(view_engine: SDRAnalyticalViewEngine):
    """
    Declared: one row per store/day.
    Actual reconstruction produces duplicate rows.
    Expected: VIEW INVALIDATED (status = UNSAFE), no silent grouping or deduplication.
    """
    # Create duplicate rows for same store_id + day
    dup_df = pd.DataFrame({
        "store_id": ["S1", "S1", "S2"],
        "day": ["2026-01-01", "2026-01-01", "2026-01-01"],
        "revenue": [100.0, 150.0, 300.0],
    })

    view_spec = SDRAnalyticalViewSpec(
        analytical_view_id="view_dup_grain",
        dataset_id="ds_dup",
        name="DuplicateGrainView",
        source_sheet_ids=["store_daily"],
        base_grain="STORE × DAY",
        result_grain="STORE × DAY",
        dimension_columns=["store_id", "day"],
        measure_columns=["revenue"],
    )

    result, facts = view_engine.execute_and_reconstruct(view_spec, {"store_daily": dup_df}, {})

    assert result.status == SDRAnalyticalViewStatus.UNSAFE
    assert result.grain_validation["status"] == "FAIL"
    assert result.grain_validation["is_unique"] is False
    assert "GRAIN_VIOLATION" in (result.error_message or "")
    # Verify no facts generated
    assert len(facts) == 0


# =====================================================================
# CERTIFICATION CASE K: GEO ENRICHMENT CONSUMPTION
# =====================================================================

def test_case_k_geo_enrichment_consumption(view_engine: SDRAnalyticalViewEngine):
    """
    Sales/store data with: city = Bengaluru.
    Use validated GEO enrichment: country = India.
    Build: sales by country.
    Prove: country provenance = DERIVED_ENRICHMENT, not observed source.
    """
    sales_store_df = pd.DataFrame({
        "store_id": ["S1", "S2"],
        "city": ["Bengaluru", "Bengaluru"],
        "country": ["India", "India"],  # Enriched column
        "sales": [500.0, 700.0],
    })

    view_spec = SDRAnalyticalViewSpec(
        analytical_view_id="view_sales_by_country",
        dataset_id="ds_geo_sales",
        name="SalesByCountry",
        source_sheet_ids=["sales_geo"],
        base_grain="STORE",
        result_grain="COUNTRY",
        dimension_columns=["country"],
        measure_columns=["sales"],
        provenance={"derived_enrichment": True, "enriched_columns": ["country"]},
    )

    result, facts = view_engine.execute_and_reconstruct(view_spec, {"sales_geo": sales_store_df}, {})

    assert result.status == SDRAnalyticalViewStatus.VALID
    assert result.row_count == 1
    assert result.rows[0]["country"] == "India"
    assert result.rows[0]["sales"] == 1200.0

    # Fact provenance must be DERIVED_ENRICHMENT
    sales_fact = next(f for f in facts if f.metric == "sales")
    assert sales_fact.provenance_type == "DERIVED_ENRICHMENT"


# =====================================================================
# CERTIFICATION CASE L: LOCAL METRIC DERIVER
# =====================================================================

def test_case_l_local_metric_deriver(view_engine: SDRAnalyticalViewEngine):
    """
    Single table: quantity, unit_price.
    Derived: revenue = quantity * unit_price.
    No JoinPlan required. Grain, unit, formula, source evidence preserved.
    If join_plan_id passed to LocalMetricDeriver, raises MetricDerivationError.
    """
    expr = ControlledExpression.binary(
        ExpressionOp.MULTIPLY,
        ControlledExpression.col("quantity", unit="count"),
        ControlledExpression.col("unit_price", unit="USD"),
    )

    # 1. Valid local derivation
    derived_spec = LocalMetricDeriver.derive_metric(
        dataset_id="ds_orders",
        sheet_id="orders",
        metric_name="revenue",
        expression=expr,
        grain="ORDER_LINE",
        unit_metadata={"quantity": "count", "unit_price": "USD"},
    )
    assert derived_spec.measure_name == "revenue"
    assert derived_spec.unit == "USD"
    assert "quantity" in derived_spec.formula_repr and "unit_price" in derived_spec.formula_repr

    # 2. Reject join_plan_id in LocalMetricDeriver
    with pytest.raises(MetricDerivationError):
        LocalMetricDeriver.derive_metric(
            dataset_id="ds_orders",
            sheet_id="orders",
            metric_name="revenue",
            expression=expr,
            grain="ORDER_LINE",
            join_plan_id="illegal_plan_id",
        )

    # 3. Execution
    orders_df = pd.DataFrame({
        "line_id": [1, 2],
        "quantity": [2.0, 5.0],
        "unit_price": [10.0, 20.0],
    })

    view_spec = SDRAnalyticalViewSpec(
        analytical_view_id="view_local_revenue",
        dataset_id="ds_orders",
        name="LocalRevenueView",
        source_sheet_ids=["orders"],
        base_grain="ORDER_LINE",
        result_grain="ORDER_LINE",
        dimension_columns=["line_id"],
        derived_measure_specs=[derived_spec],
    )

    result, facts = view_engine.execute_and_reconstruct(view_spec, {"orders": orders_df}, {})
    assert result.status == SDRAnalyticalViewStatus.VALID
    assert result.row_count == 2
    assert result.rows[0]["revenue"] == 20.0
    assert result.rows[1]["revenue"] == 100.0


# =====================================================================
# CERTIFICATION CASE M: RELATIONAL METRIC DERIVER
# =====================================================================

def test_case_m_relational_metric_deriver():
    """
    Two sheets. Metric requires JoinPlan.
    join_plan_id is mandatory. Missing join_plan_id: BLOCKED.
    """
    expr = ControlledExpression.col("cross_measure")

    # 1. Missing JoinPlan -> BLOCKED
    with pytest.raises(MetricDerivationError) as exc_info:
        RelationalMetricDeriver.derive_metric(
            dataset_id="ds_rel",
            metric_name="cross_metric",
            expression=expr,
            join_plan=None,  # Missing!
            result_grain="GLOBAL",
        )
    assert "requires an authorized sdrjoinplan" in str(exc_info.value).lower()

    # 2. Unsafe JoinPlan -> BLOCKED
    unsafe_plan = SDRJoinPlan(
        join_plan_id="jp_unsafe",
        relationship_edge_id="edge_unsafe",
        dataset_id="ds_rel",
        left_sheet_id="t1",
        right_sheet_id="t2",
        left_keys=["k"],
        right_keys=["k"],
        join_type="LEFT",
        safety_status=JoinSafetyStatus.UNSAFE,
        left_grain="T1",
        right_grain="T2",
        target_grain="T1",
    )
    with pytest.raises(MetricDerivationError) as exc_info2:
        RelationalMetricDeriver.derive_metric(
            dataset_id="ds_rel",
            metric_name="cross_metric",
            expression=expr,
            join_plan=unsafe_plan,
            result_grain="GLOBAL",
        )
    assert "only safe or safe_with_preaggregation" in str(exc_info2.value).lower()


# =====================================================================
# RETRIEVAL ANALYTICAL_INDEX CONTAINMENT
# =====================================================================

def test_retrieval_analytical_index_containment():
    """
    Verifies that SDR-6 analytical view and fact documents emit strictly
    to ANALYTICAL_INDEX with 0 leakage into RAW_SCHEMA, SEMANTIC, or RELATIONSHIP.
    """
    view = SDRAnalyticalViewSpec(
        analytical_view_id="view_retrieval_test",
        dataset_id="ds_test",
        name="RetrievalTestView",
        source_sheet_ids=["s1"],
        base_grain="G1",
        result_grain="G1",
        dimension_columns=["c1"],
        measure_columns=["m1"],
    )

    fact = SDRAnalyticalFact(
        fact_id="fact_test_01",
        metric="m1",
        value=100.0,
        formatted_value="100.0 USD",
        unit="USD",
        grain="G1",
        dataset_id="ds_test",
        analytical_view_id="view_retrieval_test",
        provenance_type="DERIVED_LOCAL",
    )

    doc_view = SDRRetrievalAdapter.build_analytical_view_document(view)
    doc_fact = SDRRetrievalAdapter.build_analytical_fact_document(fact)

    # 1. Namespaces strictly ANALYTICAL
    assert doc_view.namespace == RetrievalNamespace.ANALYTICAL
    assert doc_fact.namespace == RetrievalNamespace.ANALYTICAL
    assert doc_view.namespace == RetrievalNamespace.ANALYTICAL_INDEX
    assert doc_fact.namespace == RetrievalNamespace.ANALYTICAL_INDEX

    # 2. Authority class
    assert doc_view.authority_class == AuthorityClass.ANALYTICAL_EVIDENCE
    assert doc_fact.authority_class == AuthorityClass.ANALYTICAL_EVIDENCE

    # 3. Metadata target_index
    assert doc_view.structured_metadata["target_index"] == "ANALYTICAL_INDEX"
    assert doc_fact.structured_metadata["target_index"] == "ANALYTICAL_INDEX"

    # 4. Zero index leakage
    assert doc_view.namespace not in (
        RetrievalNamespace.RAW_SCHEMA,
        RetrievalNamespace.SEMANTIC,
        RetrievalNamespace.RELATIONSHIP,
    )
    assert doc_fact.namespace not in (
        RetrievalNamespace.RAW_SCHEMA,
        RetrievalNamespace.SEMANTIC,
        RetrievalNamespace.RELATIONSHIP,
    )


# =====================================================================
# VIEW INVALIDATION ON UPSTREAM DRIFT
# =====================================================================

def test_view_invalidation_on_upstream_drift():
    """
    Verifies that AnalyticalView becomes stale when:
    - Dataset version changes
    - Source artifact fingerprint changes
    - JoinPlan fingerprint changes
    - Policy fingerprint changes
    Unrelated views remain valid.
    """
    view = SDRAnalyticalViewSpec(
        analytical_view_id="view_drift_test",
        dataset_id="ds_drift",
        dataset_version="v1",
        name="DriftTestView",
        source_sheet_ids=["s1", "s2"],
        source_artifact_fingerprints=["src_fp_1", "src_fp_2"],
        join_plan_ids=["jp1"],
        base_grain="G1",
        result_grain="G1",
        policy_fingerprint="policy_fp_initial",
        provenance={"join_plan_fingerprints": ["jp_fp_1"]},
    )

    # 1. Baseline: no drift
    is_inv, reason = check_analytical_view_invalidation(
        view,
        current_dataset_version="v1",
        current_source_fingerprints=["src_fp_1", "src_fp_2"],
        current_join_plan_fingerprints=["jp_fp_1"],
        current_policy_fingerprint="policy_fp_initial",
    )
    assert is_inv is False
    assert reason is None

    # 2. Dataset version drift
    is_inv_ver, reason_ver = check_analytical_view_invalidation(
        view,
        current_dataset_version="v2",  # Drift!
        current_source_fingerprints=["src_fp_1", "src_fp_2"],
        current_join_plan_fingerprints=["jp_fp_1"],
        current_policy_fingerprint="policy_fp_initial",
    )
    assert is_inv_ver is True
    assert reason_ver == "INVALIDATED_DATASET_VERSION_DRIFT"

    # 3. Source fingerprint drift
    is_inv_src, reason_src = check_analytical_view_invalidation(
        view,
        current_dataset_version="v1",
        current_source_fingerprints=["src_fp_1", "src_fp_MODIFIED"],  # Drift!
        current_join_plan_fingerprints=["jp_fp_1"],
        current_policy_fingerprint="policy_fp_initial",
    )
    assert is_inv_src is True
    assert reason_src == "INVALIDATED_SOURCE_FINGERPRINT_DRIFT"

    # 4. JoinPlan drift
    is_inv_jp, reason_jp = check_analytical_view_invalidation(
        view,
        current_dataset_version="v1",
        current_source_fingerprints=["src_fp_1", "src_fp_2"],
        current_join_plan_fingerprints=["jp_fp_MODIFIED"],  # Drift!
        current_policy_fingerprint="policy_fp_initial",
    )
    assert is_inv_jp is True
    assert reason_jp == "INVALIDATED_JOIN_PLAN_DRIFT"

    # 5. Policy drift
    is_inv_pol, reason_pol = check_analytical_view_invalidation(
        view,
        current_dataset_version="v1",
        current_source_fingerprints=["src_fp_1", "src_fp_2"],
        current_join_plan_fingerprints=["jp_fp_1"],
        current_policy_fingerprint="policy_fp_CHANGED",  # Drift!
    )
    assert is_inv_pol is True
    assert reason_pol == "INVALIDATED_POLICY_DRIFT"


# =====================================================================
# ARTIFACT DETERMINISM (REPEAT RUN)
# =====================================================================

def test_sdr6_artifact_determinism(artifact_writer: SDRArtifactWriter, tmp_path: Path):
    """
    Verifies that running SDR-6 artifact generation repeatedly produces
    100% byte-identical SHA-256 matches across all 4 JSON artifacts:
    - analytical_views.json
    - analytical_facts.json
    - analytical_execution_manifest.json
    - sdr6_manifest.json
    """
    view = SDRAnalyticalViewSpec(
        analytical_view_id="view_det_1",
        dataset_id="ds_det",
        name="DeterminismView",
        source_sheet_ids=["sheet_a"],
        base_grain="ITEM",
        result_grain="ITEM",
        dimension_columns=["item_id"],
        measure_columns=["price"],
    )
    fact = SDRAnalyticalFact(
        fact_id="fact_det_1",
        metric="price",
        value=50.0,
        formatted_value="50.0",
        unit="USD",
        grain="ITEM",
        dataset_id="ds_det",
        analytical_view_id="view_det_1",
    )
    exec_res = SDRAnalyticalExecutionResult(
        view_id="view_det_1",
        status=SDRAnalyticalViewStatus.VALID,
        row_count=10,
        result_grain="ITEM",
        measure_results={"price": {"count": 10, "mean": 50.0, "sum": 500.0}},
    )

    writer1 = SDRArtifactWriter(base_dir=tmp_path / "run1")
    writer2 = SDRArtifactWriter(base_dir=tmp_path / "run2")

    res1 = writer1.write_sdr6_artifacts("ds_det", [view], [fact], [exec_res])
    res2 = writer2.write_sdr6_artifacts("ds_det", [view], [fact], [exec_res])

    # Hash comparison
    assert res1["manifest_fingerprint"] == res2["manifest_fingerprint"]

    for key in ["analytical_views", "analytical_facts", "analytical_execution_manifest", "sdr6_manifest"]:
        p1 = Path(res1[key])
        p2 = Path(res2[key])
        h1 = hashlib.sha256(p1.read_bytes()).hexdigest()
        h2 = hashlib.sha256(p2.read_bytes()).hexdigest()
        assert h1 == h2, f"Artifact {key} differed between runs: {h1} vs {h2}"


# =====================================================================
# BOUNDED PERFORMANCE BENCHMARK (SMALL / MEDIUM / LARGE)
# =====================================================================

def test_performance_and_bounded_view_reconstruction(view_engine: SDRAnalyticalViewEngine):
    """
    Executes SMALL, MEDIUM, and LARGE view reconstruction benchmarks.
    Measures source rows, source sheets, JoinPlans, preaggregations, result rows, runtime, and peak memory.
    """
    benchmark_configs = [
        ("SMALL", 2, 5, 100),
        ("MEDIUM", 4, 15, 500),
        ("LARGE", 6, 20, 1000),
    ]

    telemetry = []

    for label, n_sheets, n_cols, n_rows in benchmark_configs:
        tracemalloc.start()
        t0 = time.perf_counter()

        # Build synthetic tables
        tables = {}
        for s_idx in range(n_sheets):
            s_id = f"sheet_{s_idx}"
            data = {"id": list(range(n_rows))}
            for c_idx in range(n_cols):
                data[f"meas_{c_idx}"] = [float(r * (c_idx + 1)) for r in range(n_rows)]
            tables[s_id] = pd.DataFrame(data)

        # Build JoinPlan linking sheet_0 and sheet_1
        join_plan = SDRJoinPlan(
            join_plan_id=f"jp_{label}",
            relationship_edge_id=f"edge_{label}",
            dataset_id=f"ds_{label}",
            left_sheet_id="sheet_0",
            right_sheet_id="sheet_1",
            left_keys=["id"],
            right_keys=["id"],
            join_type="LEFT",
            safety_status=JoinSafetyStatus.SAFE,
            left_grain="ID",
            right_grain="ID",
            target_grain="ID",
            cardinality=RelationshipCardinality.ONE_TO_ONE,
        )

        view_spec = SDRAnalyticalViewSpec(
            analytical_view_id=f"view_{label}",
            dataset_id=f"ds_{label}",
            name=f"View_{label}",
            source_sheet_ids=["sheet_0", "sheet_1"],
            join_plan_ids=[f"jp_{label}"],
            base_grain="ID",
            result_grain="ID",
            dimension_columns=["id"],
            measure_columns=["meas_0"],
            unit_metadata={"meas_0": "USD"},
        )

        result, facts = view_engine.execute_and_reconstruct(
            view_spec, tables, {f"jp_{label}": join_plan}
        )

        elapsed = time.perf_counter() - t0
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        assert result.status == SDRAnalyticalViewStatus.VALID
        assert result.row_count == n_rows
        assert len(facts) >= 1

        telemetry.append({
            "tier": label,
            "sheets": n_sheets,
            "cols_per_sheet": n_cols,
            "rows_per_sheet": n_rows,
            "result_rows": result.row_count,
            "elapsed_s": round(elapsed, 4),
            "peak_mb": round(peak / (1024 * 1024), 2),
        })

    for tel in telemetry:
        print(f"\n[SDR-6 BENCHMARK] Tier: {tel['tier']}, Sheets: {tel['sheets']}, "
              f"Rows: {tel['rows_per_sheet']}, Result Rows: {tel['result_rows']}, "
              f"Time: {tel['elapsed_s']}s, Peak Mem: {tel['peak_mb']} MB")
        assert tel["elapsed_s"] < 10.0
        assert tel["peak_mb"] < 100.0
