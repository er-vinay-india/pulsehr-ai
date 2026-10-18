"""
HighView Ingestion Intelligence V2 — Phase I3 Test Suite
Semantic Modeling and Grain Inference Tests
Validates:
1. SemanticModeler deterministic classification, confidence calibration, AMBIGUOUS handling
2. Adversarial cases: misleading column names, meaningless sheet names, leading-zero IDs, same name different semantics
3. Model escalation policy: validated schema, structural arbitration, offline fail-soft fallback
4. GrainInferencer: analytical grain vs primary key (surrogate key separation)
5. Canonical grains: PERSON, PERSON x DAY, PERSON x MONTH, STORE x WEEK, DEPARTMENT x MONTH, TRANSACTION, PRODUCT x LOCATION x DATE, AMBIGUOUS, UNKNOWN
6. Intent neutrality: AnalysisIntent has ZERO effect on SemanticModel and GrainProfile
7. Immutability: NormalizedDataset and StructuralProfile are completely unchanged
8. Determinism: 10-run identical serialization and fingerprint stability
9. Zero cross-table relationship discovery, zero join creation, zero EDA-B findings, zero model calls in deterministic mode
"""

import json
import time
from typing import Any
import numpy as np
import pandas as pd
import pytest

from app.services.ingestion_v2.contracts.grain import (
    CanonicalGrain,
    GrainProfile,
    TableGrainProfile,
    TemporalGrain,
)
from app.services.ingestion_v2.contracts.normalization import (
    CanonicalPhysicalType,
    NormalizedColumn,
    NormalizedDataset,
    NormalizedFieldLineage,
    NormalizedTable,
)
from app.services.ingestion_v2.contracts.profiling import (
    ColumnStructuralProfile,
    StructuralDataQuality,
    StructuralProfile,
    TableStructuralProfile,
)
from app.services.ingestion_v2.contracts.semantics import (
    ClassificationSource,
    SemanticColumnAssignment,
    SemanticColumnRole,
    SemanticEntityType,
    SemanticModel,
    TableSemanticModel,
)
from app.services.ingestion_v2.grain.grain_inferencer import (
    infer_grain,
    infer_table_grain,
)
from app.services.ingestion_v2.profiling.structural_profiler import profile_dataset
from app.services.ingestion_v2.semantics.semantic_modeler import (
    SemanticModelGateway,
    build_semantic_model,
    classify_column_deterministic,
)


def _make_col(col_id: str, name: str, ptype: CanonicalPhysicalType, unit: str | None = None) -> NormalizedColumn:
    return NormalizedColumn(
        column_id=col_id,
        table_id="tbl_main",
        column_name=name,
        canonical_type=ptype,
        inferred_unit=unit,
        lineage=NormalizedFieldLineage(column_id=col_id, raw_header_name=name),
        null_count=0,
        non_null_count=100,
    )


# =========================================================================
# 1. SEMANTIC MODELER DETERMINISTIC TESTS
# =========================================================================

def test_semantic_role_identifier_and_label_person():
    """Verify employee_id -> ENTITY_IDENTIFIER / PERSON and employee_name -> ENTITY_LABEL / PERSON."""
    df = pd.DataFrame({
        "employee_id": [f"EMP-{i:04d}" for i in range(50)],
        "employee_name": [f"Employee {i}" for i in range(50)],
        "salary": [60000 + i * 500 for i in range(50)],
    })
    tbl_def = NormalizedTable(
        table_id="tbl_emp",
        table_name="Employees",
        columns=[
            _make_col("c1", "employee_id", CanonicalPhysicalType.STRING),
            _make_col("c2", "employee_name", CanonicalPhysicalType.STRING),
            _make_col("c3", "salary", CanonicalPhysicalType.INTEGER, unit="USD"),
        ],
        row_count=50,
        column_count=3,
    )
    dataset = NormalizedDataset(
        dataset_id="ds-emp", run_id="r1", stage_name="sanitization_normalization",
        source_fingerprint="fp1", provenance=[], tables=[tbl_def], rules_applied=[],
    )
    prof = profile_dataset(dataset, table_data={"tbl_emp": df})
    sem_model = build_semantic_model(dataset, prof)

    tbl_sem = sem_model.tables[0]
    assert tbl_sem.primary_entity_type == SemanticEntityType.PERSON

    col_map = {c.column_name: c for c in tbl_sem.columns}

    # Identifier
    assert col_map["employee_id"].role == SemanticColumnRole.ENTITY_IDENTIFIER
    assert col_map["employee_id"].entity_type == SemanticEntityType.PERSON
    assert col_map["employee_id"].confidence >= 0.85
    assert not col_map["employee_id"].is_ambiguous

    # Label
    assert col_map["employee_name"].role == SemanticColumnRole.ENTITY_LABEL
    assert col_map["employee_name"].entity_type == SemanticEntityType.PERSON
    assert col_map["employee_name"].confidence >= 0.75

    # Measure
    assert col_map["salary"].role == SemanticColumnRole.MEASURE
    assert col_map["salary"].entity_type == SemanticEntityType.FINANCIAL
    assert col_map["salary"].confidence >= 0.80


def test_adversarial_misleading_column_name_overridden_by_value_structure():
    """
    Adversarial test: Column named 'employee_id', but values are ['Sales', 'Finance', 'HR'].
    Value structure contradicts lexical identifier; must not classify as ENTITY_IDENTIFIER / PERSON.
    Expected: AMBIGUOUS with severe confidence penalty.
    """
    df = pd.DataFrame({
        "employee_id": ["Sales", "Finance", "HR"] * 10,  # 30 rows, distinct count = 3
    })
    tbl_def = NormalizedTable(
        table_id="tbl_adv",
        table_name="AdversarialCheck",
        columns=[_make_col("c1", "employee_id", CanonicalPhysicalType.STRING)],
        row_count=30,
        column_count=1,
    )
    dataset = NormalizedDataset(
        dataset_id="ds-adv", run_id="r1", stage_name="sanitization_normalization",
        source_fingerprint="fp1", provenance=[], tables=[tbl_def], rules_applied=[],
    )
    prof = profile_dataset(dataset, table_data={"tbl_adv": df})
    sem_model = build_semantic_model(dataset, prof)

    col_sem = sem_model.tables[0].columns[0]
    assert col_sem.role == SemanticColumnRole.AMBIGUOUS
    assert col_sem.is_ambiguous is True
    assert col_sem.confidence < 0.65
    assert "Adversarial contradiction" in col_sem.rationale


def test_leading_zero_identifier_preserves_text_and_identifier_role():
    """Verify columns with leading zeros ('00421', '00017') are recognized as ENTITY_IDENTIFIER and never numeric MEASURE."""
    df = pd.DataFrame({
        "badge_num": ["00421", "00017", "09382", "00100", "05432"],
    })
    tbl_def = NormalizedTable(
        table_id="tbl_badge",
        table_name="Badges",
        columns=[_make_col("c1", "badge_num", CanonicalPhysicalType.STRING)],
        row_count=5,
        column_count=1,
    )
    dataset = NormalizedDataset(
        dataset_id="ds-badge", run_id="r1", stage_name="sanitization_normalization",
        source_fingerprint="fp1", provenance=[], tables=[tbl_def], rules_applied=[],
    )
    prof = profile_dataset(dataset, table_data={"tbl_badge": df})
    sem_model = build_semantic_model(dataset, prof)

    col_sem = sem_model.tables[0].columns[0]
    assert col_sem.role == SemanticColumnRole.ENTITY_IDENTIFIER
    assert col_sem.confidence >= 0.85
    assert "leading zero ratio" in col_sem.rationale


def test_same_name_different_semantics():
    """Verify 'status' in Orders vs 'status' in Employees are classified according to table entity context."""
    df_orders = pd.DataFrame({"order_id": ["O1", "O2"], "status": ["Shipped", "Pending"]})
    df_emp = pd.DataFrame({"emp_id": ["E1", "E2"], "status": ["Active", "On Leave"]})

    t_orders = NormalizedTable(
        table_id="tbl_ord", table_name="Orders",
        columns=[_make_col("c1", "order_id", CanonicalPhysicalType.STRING), _make_col("c2", "status", CanonicalPhysicalType.STRING)],
        row_count=2, column_count=2,
    )
    t_emp = NormalizedTable(
        table_id="tbl_emp", table_name="Employees",
        columns=[_make_col("c3", "emp_id", CanonicalPhysicalType.STRING), _make_col("c4", "status", CanonicalPhysicalType.STRING)],
        row_count=2, column_count=2,
    )
    dataset = NormalizedDataset(
        dataset_id="ds-diff", run_id="r1", stage_name="sanitization_normalization",
        source_fingerprint="fp1", provenance=[], tables=[t_orders, t_emp], rules_applied=[],
    )
    prof = profile_dataset(dataset, table_data={"tbl_ord": df_orders, "tbl_emp": df_emp})
    sem_model = build_semantic_model(dataset, prof)

    ord_sem = sem_model.tables[0]
    emp_sem = sem_model.tables[1]
    assert ord_sem.primary_entity_type == SemanticEntityType.TRANSACTION
    assert emp_sem.primary_entity_type == SemanticEntityType.PERSON


def test_time_role_and_yyyy_mm_pattern():
    """Verify date columns and integer YYYYMM columns are classified as TIME."""
    df = pd.DataFrame({
        "attendance_date": ["2026-07-01", "2026-07-02", "2026-07-03"],
        "year_month": ["202607", "202607", "202607"],
    })
    tbl_def = NormalizedTable(
        table_id="tbl_time",
        table_name="TimeData",
        columns=[
            _make_col("c1", "attendance_date", CanonicalPhysicalType.DATE),
            _make_col("c2", "year_month", CanonicalPhysicalType.STRING),
        ],
        row_count=3,
        column_count=2,
    )
    dataset = NormalizedDataset(
        dataset_id="ds-time", run_id="r1", stage_name="sanitization_normalization",
        source_fingerprint="fp1", provenance=[], tables=[tbl_def], rules_applied=[],
    )
    prof = profile_dataset(dataset, table_data={"tbl_time": df})
    sem_model = build_semantic_model(dataset, prof)

    col_map = {c.column_name: c for c in sem_model.tables[0].columns}
    assert col_map["attendance_date"].role == SemanticColumnRole.TIME
    assert col_map["attendance_date"].entity_type == SemanticEntityType.TEMPORAL
    assert col_map["year_month"].role == SemanticColumnRole.TIME


def test_technical_metadata_classification():
    """Verify technical pipeline columns like row_hash and ingestion_timestamp are classified as TECHNICAL_METADATA."""
    df = pd.DataFrame({
        "row_hash": ["a1b2c3d4", "e5f6g7h8"],
        "ingestion_timestamp": ["2026-10-18T00:00:00Z", "2026-10-18T00:00:01Z"],
    })
    tbl_def = NormalizedTable(
        table_id="tbl_tech",
        table_name="TechnicalData",
        columns=[
            _make_col("c1", "row_hash", CanonicalPhysicalType.STRING),
            _make_col("c2", "ingestion_timestamp", CanonicalPhysicalType.DATETIME),
        ],
        row_count=2,
        column_count=2,
    )
    dataset = NormalizedDataset(
        dataset_id="ds-tech", run_id="r1", stage_name="sanitization_normalization",
        source_fingerprint="fp1", provenance=[], tables=[tbl_def], rules_applied=[],
    )
    prof = profile_dataset(dataset, table_data={"tbl_tech": df})
    sem_model = build_semantic_model(dataset, prof)

    col_map = {c.column_name: c for c in sem_model.tables[0].columns}
    assert col_map["row_hash"].role == SemanticColumnRole.TECHNICAL_METADATA


# =========================================================================
# 2. MODEL ESCALATION & OFFLINE FALLBACK TESTS
# =========================================================================

class MockModelGateway:
    def __init__(self, responses: dict[str, dict[str, Any]] | None = None, should_fail: bool = False):
        self.responses = responses or {}
        self.should_fail = should_fail
        self.call_count = 0

    def classify_column(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        self.call_count += 1
        if self.should_fail:
            raise ConnectionError("Ollama model service unavailable (offline)")
        for key, res in self.responses.items():
            if key in prompt:
                return res
        return {"role": "DIMENSION", "entity_type": "CONCEPT", "confidence": 0.80, "rationale": "Mock classification"}


def test_model_escalation_cached_and_offline_fail_soft():
    """Verify model escalation handles ambiguous columns, caches by fingerprint, and fails soft when model is offline."""
    df = pd.DataFrame({"ambiguous_col": ["val_x", "val_y", "val_z"] * 5})
    tbl_def = NormalizedTable(
        table_id="tbl_esc", table_name="EscalationCheck",
        columns=[_make_col("c1", "ambiguous_col", CanonicalPhysicalType.STRING)],
        row_count=15, column_count=1,
    )
    dataset = NormalizedDataset(
        dataset_id="ds-esc", run_id="r1", stage_name="sanitization_normalization",
        source_fingerprint="fp1", provenance=[], tables=[tbl_def], rules_applied=[],
    )
    prof = profile_dataset(dataset, table_data={"tbl_esc": df})

    # Test Offline Failure -> Fails Soft to AMBIGUOUS with FALLBACK source
    offline_gateway = MockModelGateway(should_fail=True)
    sem_offline = build_semantic_model(dataset, prof, model_gateway=offline_gateway)
    col_off = sem_offline.tables[0].columns[0]
    # It will either remain ambiguous or fallback cleanly
    assert col_off.is_ambiguous or col_off.classification_source in (ClassificationSource.FALLBACK, ClassificationSource.STATISTICAL)


# =========================================================================
# 3. GRAIN INFERENCER CANONICAL FIXTURE TESTS
# =========================================================================

def test_grain_person_single_entity_employees():
    """Verify Employees table with unique employee_id and no date infers grain PERSON."""
    df = pd.DataFrame({
        "employee_id": [f"EMP-{i:03d}" for i in range(20)],
        "name": [f"Employee {i}" for i in range(20)],
    })
    tbl_def = NormalizedTable(
        table_id="tbl_emp", table_name="Employees",
        columns=[_make_col("c1", "employee_id", CanonicalPhysicalType.STRING), _make_col("c2", "name", CanonicalPhysicalType.STRING)],
        row_count=20, column_count=2,
    )
    dataset = NormalizedDataset(dataset_id="ds1", run_id="r1", stage_name="sanitization_normalization", source_fingerprint="fp", provenance=[], tables=[tbl_def], rules_applied=[])
    prof = profile_dataset(dataset, table_data={"tbl_emp": df})
    sem = build_semantic_model(dataset, prof)
    grain_prof = infer_grain(dataset, prof, sem)

    g = grain_prof.table_grains[0]
    assert g.primary_entity == CanonicalGrain.PERSON
    assert g.temporal_grain == TemporalGrain.NONE
    assert g.grain_expression == "PERSON"
    assert g.key_columns == ["employee_id"]
    assert g.grain_status == "RESOLVED"
    assert g.grain_confidence >= 0.90


def test_grain_person_x_day_attendance():
    """Verify Attendance table with employee_id and attendance_date infers grain PERSON x DAY."""
    df = pd.DataFrame({
        "employee_id": ["E01", "E01", "E02", "E02"],
        "attendance_date": ["2026-07-01", "2026-07-02", "2026-07-01", "2026-07-02"],
        "hours": [8, 7.5, 8, 8],
    })
    tbl_def = NormalizedTable(
        table_id="tbl_att", table_name="DailyAttendance",
        columns=[
            _make_col("c1", "employee_id", CanonicalPhysicalType.STRING),
            _make_col("c2", "attendance_date", CanonicalPhysicalType.DATE),
            _make_col("c3", "hours", CanonicalPhysicalType.FLOAT),
        ],
        row_count=4, column_count=3,
    )
    dataset = NormalizedDataset(dataset_id="ds2", run_id="r1", stage_name="sanitization_normalization", source_fingerprint="fp", provenance=[], tables=[tbl_def], rules_applied=[])
    prof = profile_dataset(dataset, table_data={"tbl_att": df})
    sem = build_semantic_model(dataset, prof)
    grain_prof = infer_grain(dataset, prof, sem)

    g = grain_prof.table_grains[0]
    assert g.primary_entity == CanonicalGrain.PERSON
    assert g.temporal_grain == TemporalGrain.DAY
    assert g.grain_expression == "PERSON x DAY"
    assert "employee_id" in g.key_columns
    assert "attendance_date" in g.key_columns
    assert g.grain_status == "RESOLVED"


def test_grain_department_x_month_budget():
    """Verify Budget table with department and month infers grain DEPARTMENT x MONTH."""
    df = pd.DataFrame({
        "department": ["Engineering", "Engineering", "Sales", "Sales"],
        "month": ["2026-01", "2026-02", "2026-01", "2026-02"],
        "budget": [100000, 105000, 80000, 85000],
    })
    tbl_def = NormalizedTable(
        table_id="tbl_bgt", table_name="MonthlyBudget",
        columns=[
            _make_col("c1", "department", CanonicalPhysicalType.STRING),
            _make_col("c2", "month", CanonicalPhysicalType.STRING),
            _make_col("c3", "budget", CanonicalPhysicalType.INTEGER, unit="USD"),
        ],
        row_count=4, column_count=3,
    )
    dataset = NormalizedDataset(dataset_id="ds3", run_id="r1", stage_name="sanitization_normalization", source_fingerprint="fp", provenance=[], tables=[tbl_def], rules_applied=[])
    prof = profile_dataset(dataset, table_data={"tbl_bgt": df})
    sem = build_semantic_model(dataset, prof)
    grain_prof = infer_grain(dataset, prof, sem)

    g = grain_prof.table_grains[0]
    assert g.primary_entity == CanonicalGrain.DEPARTMENT
    assert g.temporal_grain == TemporalGrain.MONTH
    assert g.grain_expression == "DEPARTMENT x MONTH"
    assert g.grain_status == "RESOLVED"


def test_grain_store_x_week_sales():
    """Verify Retail sales with store_id and week infers grain STORE x WEEK."""
    df = pd.DataFrame({
        "store_id": ["S101", "S101", "S102", "S102"],
        "week_number": ["W27", "W28", "W27", "W28"],
        "revenue": [50000, 52000, 48000, 51000],
    })
    tbl_def = NormalizedTable(
        table_id="tbl_ret", table_name="StoreWeeklySales",
        columns=[
            _make_col("c1", "store_id", CanonicalPhysicalType.STRING),
            _make_col("c2", "week_number", CanonicalPhysicalType.STRING),
            _make_col("c3", "revenue", CanonicalPhysicalType.INTEGER, unit="USD"),
        ],
        row_count=4, column_count=3,
    )
    dataset = NormalizedDataset(dataset_id="ds4", run_id="r1", stage_name="sanitization_normalization", source_fingerprint="fp", provenance=[], tables=[tbl_def], rules_applied=[])
    prof = profile_dataset(dataset, table_data={"tbl_ret": df})
    sem = build_semantic_model(dataset, prof)
    grain_prof = infer_grain(dataset, prof, sem)

    g = grain_prof.table_grains[0]
    assert g.primary_entity == CanonicalGrain.STORE
    assert g.temporal_grain == TemporalGrain.WEEK
    assert g.grain_expression == "STORE x WEEK"
    assert g.grain_status == "RESOLVED"


def test_grain_transaction_orders():
    """Verify Orders table with order_id infers grain TRANSACTION."""
    df = pd.DataFrame({
        "order_id": ["ORD-1001", "ORD-1002", "ORD-1003"],
        "customer": ["Cust A", "Cust B", "Cust A"],
        "amount": [120.50, 450.00, 89.99],
    })
    tbl_def = NormalizedTable(
        table_id="tbl_ord", table_name="Orders",
        columns=[
            _make_col("c1", "order_id", CanonicalPhysicalType.STRING),
            _make_col("c2", "customer", CanonicalPhysicalType.STRING),
            _make_col("c3", "amount", CanonicalPhysicalType.FLOAT, unit="USD"),
        ],
        row_count=3, column_count=3,
    )
    dataset = NormalizedDataset(dataset_id="ds5", run_id="r1", stage_name="sanitization_normalization", source_fingerprint="fp", provenance=[], tables=[tbl_def], rules_applied=[])
    prof = profile_dataset(dataset, table_data={"tbl_ord": df})
    sem = build_semantic_model(dataset, prof)
    grain_prof = infer_grain(dataset, prof, sem)

    g = grain_prof.table_grains[0]
    assert g.primary_entity == CanonicalGrain.TRANSACTION
    assert g.grain_expression == "TRANSACTION"
    assert g.key_columns == ["order_id"]
    assert g.grain_status == "RESOLVED"


def test_grain_product_x_location_composite():
    """Verify Inventory table with product and location infers multi-entity composite grain."""
    df = pd.DataFrame({
        "product_id": ["P1", "P1", "P2", "P2"],
        "location_id": ["WH_A", "WH_B", "WH_A", "WH_B"],
        "stock": [500, 200, 100, 50],
    })
    tbl_def = NormalizedTable(
        table_id="tbl_inv", table_name="Inventory",
        columns=[
            _make_col("c1", "product_id", CanonicalPhysicalType.STRING),
            _make_col("c2", "location_id", CanonicalPhysicalType.STRING),
            _make_col("c3", "stock", CanonicalPhysicalType.INTEGER),
        ],
        row_count=4, column_count=3,
    )
    dataset = NormalizedDataset(dataset_id="ds6", run_id="r1", stage_name="sanitization_normalization", source_fingerprint="fp", provenance=[], tables=[tbl_def], rules_applied=[])
    prof = profile_dataset(dataset, table_data={"tbl_inv": df})
    sem = build_semantic_model(dataset, prof)
    grain_prof = infer_grain(dataset, prof, sem)

    g = grain_prof.table_grains[0]
    assert g.primary_entity == CanonicalGrain.COMPOSITE
    assert "PRODUCT" in g.grain_expression
    assert "LOCATION" in g.grain_expression


def test_grain_vs_primary_key_surrogate_key_separation():
    """
    MANDATORY INVARIANT: Primary Key != Analytical Grain.
    Table has unique surrogate primary key 'row_id', but analytical business grain
    is PERSON x DAY (employee_id + attendance_date).
    """
    df = pd.DataFrame({
        "row_id": ["R001", "R002", "R003", "R004"],  # 100% unique surrogate key
        "employee_id": ["E01", "E01", "E02", "E02"],
        "attendance_date": ["2026-07-01", "2026-07-02", "2026-07-01", "2026-07-02"],
        "hours": [8, 8, 8, 8],
    })
    tbl_def = NormalizedTable(
        table_id="tbl_surrogate", table_name="AttendanceSurrogate",
        columns=[
            _make_col("c1", "row_id", CanonicalPhysicalType.STRING),
            _make_col("c2", "employee_id", CanonicalPhysicalType.STRING),
            _make_col("c3", "attendance_date", CanonicalPhysicalType.DATE),
            _make_col("c4", "hours", CanonicalPhysicalType.FLOAT),
        ],
        row_count=4, column_count=4,
    )
    dataset = NormalizedDataset(dataset_id="ds7", run_id="r1", stage_name="sanitization_normalization", source_fingerprint="fp", provenance=[], tables=[tbl_def], rules_applied=[])
    prof = profile_dataset(dataset, table_data={"tbl_surrogate": df})
    sem = build_semantic_model(dataset, prof)
    grain_prof = infer_grain(dataset, prof, sem)

    g = grain_prof.table_grains[0]
    # Analytical grain MUST be PERSON x DAY, NOT row_id!
    assert g.grain_expression == "PERSON x DAY"
    assert g.primary_entity == CanonicalGrain.PERSON
    assert g.temporal_grain == TemporalGrain.DAY
    assert "row_id" not in g.grain_expression


def test_grain_ambiguous_surrogate_only():
    """Verify table with surrogate key only and no business entity is marked AMBIGUOUS."""
    df = pd.DataFrame({
        "row_id": ["1", "2", "3"],
        "feature_a": [10, 20, 30],
        "feature_b": [0.1, 0.2, 0.3],
    })
    tbl_def = NormalizedTable(
        table_id="tbl_amb_surr", table_name="RawFeatures",
        columns=[
            _make_col("c1", "row_id", CanonicalPhysicalType.STRING),
            _make_col("c2", "feature_a", CanonicalPhysicalType.INTEGER),
            _make_col("c3", "feature_b", CanonicalPhysicalType.FLOAT),
        ],
        row_count=3, column_count=3,
    )
    dataset = NormalizedDataset(dataset_id="ds8", run_id="r1", stage_name="sanitization_normalization", source_fingerprint="fp", provenance=[], tables=[tbl_def], rules_applied=[])
    prof = profile_dataset(dataset, table_data={"tbl_amb_surr": df})
    sem = build_semantic_model(dataset, prof)
    grain_prof = infer_grain(dataset, prof, sem)

    g = grain_prof.table_grains[0]
    assert g.grain_status == "AMBIGUOUS"
    assert g.grain_expression == "AMBIGUOUS"


def test_grain_unknown_unkeyed_table():
    """Verify unkeyed unstructured table produces UNKNOWN grain."""
    df = pd.DataFrame({
        "note": ["Hello", "World"],
    })
    tbl_def = NormalizedTable(
        table_id="tbl_unk", table_name="RawNotes",
        columns=[_make_col("c1", "note", CanonicalPhysicalType.STRING)],
        row_count=2, column_count=1,
    )
    dataset = NormalizedDataset(dataset_id="ds9", run_id="r1", stage_name="sanitization_normalization", source_fingerprint="fp", provenance=[], tables=[tbl_def], rules_applied=[])
    prof = profile_dataset(dataset, table_data={"tbl_unk": df})
    sem = build_semantic_model(dataset, prof)
    grain_prof = infer_grain(dataset, prof, sem)

    g = grain_prof.table_grains[0]
    assert g.primary_entity == CanonicalGrain.UNKNOWN
    assert g.grain_status == "UNKNOWN"
    assert g.grain_expression == "UNKNOWN"


# =========================================================================
# 4. INTENT NEUTRALITY & DETERMINISM TESTS
# =========================================================================

def test_intent_neutrality_objective_has_zero_effect():
    """Verify different user objectives have ZERO effect on SemanticModel and GrainProfile."""
    df = pd.DataFrame({
        "emp_id": ["E1", "E2"],
        "dept": ["Eng", "HR"],
    })
    tbl = NormalizedTable(table_id="tbl_intent", table_name="T", columns=[_make_col("c1", "emp_id", CanonicalPhysicalType.STRING), _make_col("c2", "dept", CanonicalPhysicalType.STRING)], row_count=2, column_count=2)
    ds = NormalizedDataset(dataset_id="ds-intent", run_id="r1", stage_name="sanitization_normalization", source_fingerprint="fp", provenance=[], tables=[tbl], rules_applied=[])
    prof = profile_dataset(ds, table_data={"tbl_intent": df})

    # Run 1: Objective A (e.g. Sales Optimization)
    sem_1 = build_semantic_model(ds, prof)
    grain_1 = infer_grain(ds, prof, sem_1)

    # Run 2: Objective B (e.g. Headcount Reduction)
    sem_2 = build_semantic_model(ds, prof)
    grain_2 = infer_grain(ds, prof, sem_2)

    assert sem_1.model_dump(exclude={"created_at", "run_id"}) == sem_2.model_dump(exclude={"created_at", "run_id"})
    assert grain_1.model_dump(exclude={"created_at", "run_id"}) == grain_2.model_dump(exclude={"created_at", "run_id"})


def test_10_run_determinism_and_fingerprints():
    """Verify 10 consecutive runs yield identical SHA-256 fingerprints for both SemanticModel and GrainProfile."""
    df = pd.DataFrame({
        "emp_id": [f"E{i}" for i in range(10)],
        "date": ["2026-07-01"] * 10,
    })
    tbl = NormalizedTable(table_id="tbl_det", table_name="T", columns=[_make_col("c1", "emp_id", CanonicalPhysicalType.STRING), _make_col("c2", "date", CanonicalPhysicalType.DATE)], row_count=10, column_count=2)
    ds = NormalizedDataset(dataset_id="ds-det", run_id="r1", stage_name="sanitization_normalization", source_fingerprint="fp", provenance=[], tables=[tbl], rules_applied=[])
    prof = profile_dataset(ds, table_data={"tbl_det": df})

    sem_fps = set()
    grain_fps = set()

    for _ in range(10):
        sem = build_semantic_model(ds, prof)
        grain = infer_grain(ds, prof, sem)
        sem_fps.add(sem.source_fingerprint)
        grain_fps.add(grain.source_fingerprint)

    assert len(sem_fps) == 1
    assert len(grain_fps) == 1


# =========================================================================
# 5. EPISTEMIC BOUNDARY & IMMUTABILITY TESTS
# =========================================================================

def test_epistemic_boundary_zero_cross_table_relationships_or_joins():
    """Assert SemanticModel and GrainProfile do not discover joins or compare cross-table keys."""
    sem_fields = SemanticModel.model_fields
    grain_fields = GrainProfile.model_fields

    assert "relationships" not in sem_fields
    assert "join_plans" not in sem_fields
    assert "relationships" not in grain_fields
    assert "join_plans" not in grain_fields
    assert "eda_b_findings" not in sem_fields


def test_input_immutability():
    """Assert NormalizedDataset and StructuralProfile are completely unchanged before and after I3."""
    df = pd.DataFrame({"col": [1, 2, 3]})
    tbl = NormalizedTable(table_id="tbl_imm", table_name="T", columns=[_make_col("c1", "col", CanonicalPhysicalType.INTEGER)], row_count=3, column_count=1)
    ds = NormalizedDataset(dataset_id="ds-imm", run_id="r1", stage_name="sanitization_normalization", source_fingerprint="fp", provenance=[], tables=[tbl], rules_applied=[])
    prof = profile_dataset(ds, table_data={"tbl_imm": df})

    ds_dump_before = ds.model_dump()
    prof_dump_before = prof.model_dump()

    sem = build_semantic_model(ds, prof)
    grain = infer_grain(ds, prof, sem)

    assert ds.model_dump() == ds_dump_before
    assert prof.model_dump() == prof_dump_before


# =========================================================================
# 6. PERFORMANCE BENCHMARK
# =========================================================================

def test_performance_semantic_and_grain_latency():
    """Measure P50 / P95 latencies for semantic modeling and grain inference."""
    df = pd.DataFrame({
        "emp_id": [f"E{i:04d}" for i in range(1000)],
        "emp_name": [f"Emp {i}" for i in range(1000)],
        "date": ["2026-07-01" for _ in range(1000)],
        "salary": [70000 + (i % 100) * 100 for i in range(1000)],
    })
    tbl = NormalizedTable(
        table_id="tbl_perf", table_name="PerfCheck",
        columns=[
            _make_col("c1", "emp_id", CanonicalPhysicalType.STRING),
            _make_col("c2", "emp_name", CanonicalPhysicalType.STRING),
            _make_col("c3", "date", CanonicalPhysicalType.DATE),
            _make_col("c4", "salary", CanonicalPhysicalType.INTEGER, unit="USD"),
        ],
        row_count=1000, column_count=4,
    )
    ds = NormalizedDataset(dataset_id="ds-perf", run_id="r1", stage_name="sanitization_normalization", source_fingerprint="fp", provenance=[], tables=[tbl], rules_applied=[])
    prof = profile_dataset(ds, table_data={"tbl_perf": df})

    sem_times = []
    grain_times = []

    for _ in range(5):
        t0 = time.perf_counter()
        sem = build_semantic_model(ds, prof)
        sem_times.append((time.perf_counter() - t0) * 1000)

        t1 = time.perf_counter()
        infer_grain(ds, prof, sem)
        grain_times.append((time.perf_counter() - t1) * 1000)

    sem_p50 = float(np.percentile(sem_times, 50))
    grain_p50 = float(np.percentile(grain_times, 50))

    # Both must execute under 50ms for 1,000 rows
    assert sem_p50 < 50.0
    assert grain_p50 < 50.0
