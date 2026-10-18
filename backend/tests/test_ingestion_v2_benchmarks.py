"""
HighView Ingestion Intelligence V2 — Phase I3 Labeled Truth Benchmarks
Covers:
1. Labeled Semantic Benchmark across 6 domains (Workforce, Retail, Environmental, Finance synthetic, SaaS synthetic, Supply Chain synthetic)
2. Adversarial examples and strict HIGH_CONFIDENCE_FALSE_POSITIVE = 0 guarantee
3. Model Escalation Policy: Validated schema, structural arbitration, offline fail-soft
4. Labeled Grain Benchmark across 14 canonical fixtures with FALSE_CONFIDENT_GRAIN = 0 guarantee
"""

from dataclasses import dataclass
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
    StructuralProfile,
)
from app.services.ingestion_v2.contracts.semantics import (
    ClassificationSource,
    MeasureClass,
    SemanticColumnAssignment,
    SemanticColumnRole,
    SemanticConcept,
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


def _make_col(
    table_id: str,
    column_id: str,
    column_name: str,
    canonical_type: CanonicalPhysicalType,
    inferred_unit: str | None = None,
) -> NormalizedColumn:
    return NormalizedColumn(
        column_id=column_id,
        table_id=table_id,
        column_name=column_name,
        canonical_type=canonical_type,
        inferred_unit=inferred_unit,
        lineage=NormalizedFieldLineage(column_id=column_id, raw_header_name=column_name),
        null_count=0,
        non_null_count=100,
    )


# =========================================================================
# 1. LABELED SEMANTIC BENCHMARK TRUTH DEFINITIONS
# =========================================================================

@dataclass(frozen=True)
class SemanticTruthRecord:
    dataset: str
    table: str
    column: str
    expected_role: SemanticColumnRole
    expected_entity_type: SemanticEntityType
    expected_measure_class: MeasureClass | None = None
    allowed_ambiguity: bool = False
    minimum_confidence_band: str = "MEDIUM"


# Comprehensive 6-domain labeled corpus with 48 distinct benchmark columns
SEMANTIC_BENCHMARK_TRUTH: list[SemanticTruthRecord] = [
    # Domain 1: Workforce
    SemanticTruthRecord("workforce", "employees", "employee_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticEntityType.PERSON, None, False, "HIGH"),
    SemanticTruthRecord("workforce", "employees", "employee_name", SemanticColumnRole.ENTITY_LABEL, SemanticEntityType.PERSON, None, False, "MEDIUM"),
    SemanticTruthRecord("workforce", "employees", "department", SemanticColumnRole.DIMENSION, SemanticEntityType.DEPARTMENT, None, False, "MEDIUM"),
    SemanticTruthRecord("workforce", "employees", "salary", SemanticColumnRole.MEASURE, SemanticEntityType.UNKNOWN, MeasureClass.FINANCIAL, False, "MEDIUM"),
    SemanticTruthRecord("workforce", "employees", "hire_date", SemanticColumnRole.TIME, SemanticEntityType.UNKNOWN, None, False, "HIGH"),
    SemanticTruthRecord("workforce", "employees", "is_active", SemanticColumnRole.BOOLEAN, SemanticEntityType.UNKNOWN, None, False, "HIGH"),
    SemanticTruthRecord("workforce", "employees", "employment_status", SemanticColumnRole.STATUS, SemanticEntityType.UNKNOWN, None, False, "MEDIUM"),
    SemanticTruthRecord("workforce", "employees", "hr_notes", SemanticColumnRole.FREE_TEXT, SemanticEntityType.UNKNOWN, None, False, "MEDIUM"),
    SemanticTruthRecord("workforce", "employees", "row_hash", SemanticColumnRole.TECHNICAL_METADATA, SemanticEntityType.UNKNOWN, None, False, "HIGH"),
    # Adversarial Workforce: same name different sheet meaning, leading zero, different names same meaning
    SemanticTruthRecord("workforce", "staff", "associate_code", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticEntityType.PERSON, None, False, "HIGH"),
    SemanticTruthRecord("workforce", "staff", "badge_number", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticEntityType.UNKNOWN, None, False, "MEDIUM"),
    SemanticTruthRecord("workforce", "adversarial", "fake_id_categories", SemanticColumnRole.AMBIGUOUS, SemanticEntityType.UNKNOWN, None, True, "LOW"),

    # Domain 2: Retail
    SemanticTruthRecord("retail", "stores", "store_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticEntityType.STORE, None, False, "HIGH"),
    SemanticTruthRecord("retail", "stores", "store_name", SemanticColumnRole.ENTITY_LABEL, SemanticEntityType.STORE, None, False, "MEDIUM"),
    SemanticTruthRecord("retail", "stores", "store_location", SemanticColumnRole.DIMENSION, SemanticEntityType.LOCATION, None, False, "MEDIUM"),
    SemanticTruthRecord("retail", "sales", "revenue", SemanticColumnRole.MEASURE, SemanticEntityType.UNKNOWN, MeasureClass.FINANCIAL, False, "MEDIUM"),
    SemanticTruthRecord("retail", "sales", "units_sold", SemanticColumnRole.MEASURE, SemanticEntityType.UNKNOWN, MeasureClass.QUANTITY, False, "MEDIUM"),
    SemanticTruthRecord("retail", "sales", "week_number", SemanticColumnRole.TIME, SemanticEntityType.UNKNOWN, None, False, "HIGH"),
    SemanticTruthRecord("retail", "sales", "discount_pct", SemanticColumnRole.MEASURE, SemanticEntityType.UNKNOWN, MeasureClass.PERCENTAGE, False, "MEDIUM"),

    # Domain 3: Environmental
    SemanticTruthRecord("environmental", "emissions", "facility_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticEntityType.FACILITY, None, False, "HIGH"),
    SemanticTruthRecord("environmental", "emissions", "facility_name", SemanticColumnRole.ENTITY_LABEL, SemanticEntityType.FACILITY, None, False, "MEDIUM"),
    SemanticTruthRecord("environmental", "emissions", "scope_category", SemanticColumnRole.DIMENSION, SemanticEntityType.UNKNOWN, None, False, "MEDIUM"),
    SemanticTruthRecord("environmental", "emissions", "co2_emissions_mt", SemanticColumnRole.MEASURE, SemanticEntityType.UNKNOWN, MeasureClass.QUANTITY, False, "MEDIUM"),
    SemanticTruthRecord("environmental", "emissions", "reporting_year", SemanticColumnRole.TIME, SemanticEntityType.UNKNOWN, None, False, "HIGH"),
    SemanticTruthRecord("environmental", "emissions", "audit_status", SemanticColumnRole.STATUS, SemanticEntityType.UNKNOWN, None, False, "MEDIUM"),

    # Domain 4: Finance Synthetic
    SemanticTruthRecord("finance", "ledger", "account_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticEntityType.ACCOUNT, None, False, "HIGH"),
    SemanticTruthRecord("finance", "ledger", "account_name", SemanticColumnRole.ENTITY_LABEL, SemanticEntityType.ACCOUNT, None, False, "MEDIUM"),
    SemanticTruthRecord("finance", "ledger", "budget_amount", SemanticColumnRole.MEASURE, SemanticEntityType.UNKNOWN, MeasureClass.FINANCIAL, False, "HIGH"),
    SemanticTruthRecord("finance", "ledger", "actual_cost", SemanticColumnRole.MEASURE, SemanticEntityType.UNKNOWN, MeasureClass.FINANCIAL, False, "HIGH"),
    SemanticTruthRecord("finance", "ledger", "fiscal_period", SemanticColumnRole.TIME, SemanticEntityType.UNKNOWN, None, False, "HIGH"),
    SemanticTruthRecord("finance", "ledger", "variance_pct", SemanticColumnRole.MEASURE, SemanticEntityType.UNKNOWN, MeasureClass.PERCENTAGE, False, "MEDIUM"),

    # Domain 5: SaaS Synthetic
    SemanticTruthRecord("saas", "subscriptions", "user_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticEntityType.PERSON, None, False, "HIGH"),
    SemanticTruthRecord("saas", "subscriptions", "plan_tier", SemanticColumnRole.DIMENSION, SemanticEntityType.UNKNOWN, None, False, "MEDIUM"),
    SemanticTruthRecord("saas", "subscriptions", "monthly_recurring_revenue", SemanticColumnRole.MEASURE, SemanticEntityType.UNKNOWN, MeasureClass.FINANCIAL, False, "HIGH"),
    SemanticTruthRecord("saas", "subscriptions", "is_churned", SemanticColumnRole.BOOLEAN, SemanticEntityType.UNKNOWN, None, False, "HIGH"),
    SemanticTruthRecord("saas", "subscriptions", "signup_timestamp", SemanticColumnRole.TIME, SemanticEntityType.UNKNOWN, None, False, "HIGH"),
    SemanticTruthRecord("saas", "subscriptions", "device_type", SemanticColumnRole.DIMENSION, SemanticEntityType.DEVICE, None, False, "MEDIUM"),
    SemanticTruthRecord("saas", "subscriptions", "nps_score", SemanticColumnRole.MEASURE, SemanticEntityType.UNKNOWN, MeasureClass.SCORE, False, "MEDIUM"),

    # Domain 6: Supply Chain Synthetic
    SemanticTruthRecord("supply_chain", "inventory", "product_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticEntityType.PRODUCT, None, False, "HIGH"),
    SemanticTruthRecord("supply_chain", "inventory", "product_title", SemanticColumnRole.ENTITY_LABEL, SemanticEntityType.PRODUCT, None, False, "MEDIUM"),
    SemanticTruthRecord("supply_chain", "inventory", "warehouse_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticEntityType.FACILITY, None, False, "HIGH"),
    SemanticTruthRecord("supply_chain", "inventory", "stock_quantity", SemanticColumnRole.MEASURE, SemanticEntityType.UNKNOWN, MeasureClass.QUANTITY, False, "MEDIUM"),
    SemanticTruthRecord("supply_chain", "orders", "order_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticEntityType.TRANSACTION, None, False, "HIGH"),
    SemanticTruthRecord("supply_chain", "orders", "order_date", SemanticColumnRole.TIME, SemanticEntityType.UNKNOWN, None, False, "HIGH"),
    SemanticTruthRecord("supply_chain", "orders", "shipping_address", SemanticColumnRole.DIMENSION, SemanticEntityType.LOCATION, None, False, "MEDIUM"),

    # Edge & Null Cases
    SemanticTruthRecord("edge", "null_table", "all_empty_notes", SemanticColumnRole.UNKNOWN, SemanticEntityType.UNKNOWN, None, False, "HIGH"),
    SemanticTruthRecord("edge", "ambig_table", "ambiguous_code_xyz", SemanticColumnRole.AMBIGUOUS, SemanticEntityType.UNKNOWN, None, True, "LOW"),
    SemanticTruthRecord("edge", "text_table", "general_memo_text", SemanticColumnRole.FREE_TEXT, SemanticEntityType.UNKNOWN, None, False, "MEDIUM"),
]


def _build_benchmark_synthetic_data(record: SemanticTruthRecord) -> tuple[pd.Series, CanonicalPhysicalType, str | None]:
    """Generates realistic synthetic data matching each benchmark record."""
    name = record.column
    r = record.expected_role

    if r == SemanticColumnRole.ENTITY_IDENTIFIER:
        if "lead" in name or name == "associate_code":
            data = [f"00{i:03d}" for i in range(100)]
            return pd.Series(data), CanonicalPhysicalType.STRING, None
        data = [f"ID-{i:05d}" for i in range(100)]
        return pd.Series(data), CanonicalPhysicalType.STRING, None

    if r == SemanticColumnRole.ENTITY_LABEL:
        data = [f"Entity Label {i}" for i in range(100)]
        return pd.Series(data), CanonicalPhysicalType.STRING, None

    if r == SemanticColumnRole.MEASURE:
        unit = "$" if record.expected_measure_class == MeasureClass.FINANCIAL else ("%" if record.expected_measure_class == MeasureClass.PERCENTAGE else None)
        data = [float(1000 + i * 25) for i in range(100)]
        return pd.Series(data), CanonicalPhysicalType.FLOAT, unit

    if r == SemanticColumnRole.TIME:
        data = pd.date_range("2024-01-01", periods=100, freq="D").astype(str).tolist()
        return pd.Series(data), CanonicalPhysicalType.DATE, None

    if r == SemanticColumnRole.BOOLEAN:
        data = [True if i % 2 == 0 else False for i in range(100)]
        return pd.Series(data), CanonicalPhysicalType.BOOLEAN, None

    if r == SemanticColumnRole.STATUS:
        states = ["ACTIVE", "PENDING", "COMPLETED", "SUSPENDED"]
        data = [states[i % len(states)] for i in range(100)]
        return pd.Series(data), CanonicalPhysicalType.STRING, None

    if r == SemanticColumnRole.FREE_TEXT:
        data = [f"Unstructured notes commentary message remark {i}" for i in range(100)]
        return pd.Series(data), CanonicalPhysicalType.STRING, None

    if r == SemanticColumnRole.TECHNICAL_METADATA:
        data = [f"hash_{i}_{time.time()}" for i in range(100)]
        return pd.Series(data), CanonicalPhysicalType.STRING, None

    if r == SemanticColumnRole.DIMENSION:
        cats = ["Tier_A", "Tier_B", "Tier_C", "Tier_D"]
        data = [cats[i % len(cats)] for i in range(100)]
        return pd.Series(data), CanonicalPhysicalType.STRING, None

    if r == SemanticColumnRole.UNKNOWN:
        data = [None] * 100
        return pd.Series(data), CanonicalPhysicalType.STRING, None

    if record.column == "fake_id_categories":
        # Adversarial: named id, but 3 values
        data = ["Dept_X", "Dept_Y", "Dept_Z"] * 33 + ["Dept_X"]
        return pd.Series(data), CanonicalPhysicalType.STRING, None

    # Default fallback
    data = [f"val_{i % 5}" for i in range(100)]
    return pd.Series(data), CanonicalPhysicalType.STRING, None


# =========================================================================
# 2. RUN LABELED SEMANTIC BENCHMARK & METRICS
# =========================================================================

def test_labeled_semantic_benchmark_full_corpus():
    """
    Executes the SemanticModeler over the 48-column benchmark corpus.
    Evaluates Precision, Recall, F1, High-Confidence False Positives (must be 0),
    Ambiguity and Unknown counts.
    """
    y_true_roles = []
    y_pred_roles = []
    y_true_entities = []
    y_pred_entities = []

    high_confidence_false_positives = 0
    high_confidence_false_negatives = 0
    ambiguous_count = 0
    unknown_count = 0
    deterministic_count = 0

    results = []

    for idx, rec in enumerate(SEMANTIC_BENCHMARK_TRUTH):
        series, ptype, unit = _build_benchmark_synthetic_data(rec)
        col_id = f"col_{idx}"
        tbl_id = f"tbl_{rec.table}"

        col_norm = _make_col(tbl_id, col_id, rec.column, ptype, unit)
        tbl_def = NormalizedTable(
            table_id=tbl_id,
            table_name=rec.table,
            columns=[col_norm],
            row_count=len(series),
            column_count=1,
        )
        dataset = NormalizedDataset(
            dataset_id=f"ds_{rec.dataset}",
            run_id="r_bench",
            stage_name="normalization",
            source_fingerprint=f"fp_{rec.dataset}_{idx}",
            provenance=[],
            tables=[tbl_def],
            rules_applied=[],
        )

        df = pd.DataFrame({rec.column: series})
        prof = profile_dataset(dataset, table_data={tbl_id: df})
        sem_model = build_semantic_model(dataset, prof)
        assignment = sem_model.tables[0].columns[0]

        deterministic_count += 1
        if assignment.role == SemanticColumnRole.AMBIGUOUS:
            ambiguous_count += 1
        if assignment.role == SemanticColumnRole.UNKNOWN:
            unknown_count += 1

        pred_role = assignment.role
        pred_ent = assignment.entity_type
        conf = assignment.confidence

        is_match = False
        if pred_role == rec.expected_role:
            is_match = True
        elif rec.allowed_ambiguity and pred_role == SemanticColumnRole.AMBIGUOUS:
            is_match = True

        # Check High Confidence False Positive
        # False Positive: Model predicts a specific business role with confidence >= 0.85, but true role was different
        if not is_match and conf >= 0.85:
            high_confidence_false_positives += 1

        # High Confidence False Negative: True role is high-confidence, but model failed to assign it or went ambiguous
        if not is_match and rec.minimum_confidence_band == "HIGH":
            high_confidence_false_negatives += 1

        y_true_roles.append(rec.expected_role.value)
        y_pred_roles.append(pred_role.value)

        results.append({
            "column": rec.column,
            "expected_role": rec.expected_role.value,
            "predicted_role": pred_role.value,
            "expected_entity": rec.expected_entity_type.value,
            "predicted_entity": pred_ent.value,
            "confidence": conf,
            "is_match": is_match,
        })

    total_columns = len(SEMANTIC_BENCHMARK_TRUTH)
    matches = sum(1 for r in results if r["is_match"])
    precision = matches / total_columns
    recall = matches / total_columns
    f1 = 2 * (precision * recall) / (precision + recall)

    print("\n" + "=" * 60)
    print(f"SEMANTIC BENCHMARK RESULTS ({total_columns} columns)")
    print(f"Accuracy / Precision: {precision:.4f} ({matches}/{total_columns})")
    print(f"Recall:               {recall:.4f}")
    print(f"F1 Score:             {f1:.4f}")
    print(f"High-Conf False Pos:  {high_confidence_false_positives}")
    print(f"High-Conf False Neg:  {high_confidence_false_negatives}")
    print(f"Ambiguous Count:      {ambiguous_count}")
    print(f"Unknown Count:        {unknown_count}")
    print("=" * 60)

    # Absolute Requirements
    assert high_confidence_false_positives == 0, f"Expected 0 high-confidence false positives, found {high_confidence_false_positives}"
    assert precision >= 0.95, f"Expected precision >= 0.95, got {precision:.4f}"
    assert f1 >= 0.95, f"Expected F1 >= 0.95, got {f1:.4f}"


# =========================================================================
# 3. TEST MODEL ESCALATION PATH (MOCKED / DETERMINISTIC)
# =========================================================================

class MockFrozenModelGateway:
    """Mock gateway that simulates model responses without network or live dependencies."""
    def __init__(self, mode: str = "valid"):
        self.mode = mode
        self.call_count = 0

    def classify_column(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        self.call_count += 1
        if self.mode == "offline":
            raise ConnectionError("Connection refused to local model daemon.")
        if self.mode == "contradictory":
            # Proposes ENTITY_IDENTIFIER for a low-cardinality column (structural guard must reject)
            return {
                "role": "ENTITY_IDENTIFIER",
                "entity_type": "PERSON",
                "confidence": 0.90,
                "rationale": "Model hallucinations claiming low-cardinality column is an ID.",
            }
        # Valid resolution
        return {
            "role": "DIMENSION",
            "entity_type": "DEPARTMENT",
            "confidence": 0.82,
            "rationale": "Model assistance successfully recognized department code dimension.",
        }


def test_model_escalation_path_complete_matrix():
    """
    Tests all 3 required model escalation scenarios:
    1. Weak deterministic evidence -> model suggests valid role -> accepted by structural guard
    2. Contradictory model response -> structural arbitration rejects model suggestion -> falls back to safe AMBIGUOUS
    3. Model offline / unavailable -> fail-soft fallback -> AMBIGUOUS without pipeline failure
    """
    # Case 1: Valid escalation
    df_weak = pd.DataFrame({"ambig_field_x": [f"code_{i % 60}" for i in range(100)]})
    tbl_def_1 = NormalizedTable(
        table_id="tbl_esc1", table_name="EscTable",
        columns=[_make_col("tbl_esc1", "c1", "ambig_field_x", CanonicalPhysicalType.STRING)],
        row_count=100, column_count=1,
    )
    dataset_1 = NormalizedDataset(
        dataset_id="ds_esc1", run_id="r1", stage_name="norm", source_fingerprint="fp1",
        provenance=[], tables=[tbl_def_1], rules_applied=[],
    )
    prof_1 = profile_dataset(dataset_1, table_data={"tbl_esc1": df_weak})

    gw_valid = MockFrozenModelGateway(mode="valid")
    sem_1 = build_semantic_model(dataset_1, prof_1, model_gateway=gw_valid)
    col_1 = sem_1.tables[0].columns[0]

    assert col_1.role == SemanticColumnRole.DIMENSION
    assert col_1.entity_type == SemanticEntityType.DEPARTMENT
    assert col_1.classification_source == ClassificationSource.MODEL_ASSISTED
    assert col_1.confidence >= 0.80
    assert gw_valid.call_count == 1

    # Case 2: Contradictory model response rejected by structural arbitration
    df_contra = pd.DataFrame({"ambig_field_y": [f"val_{i % 60}" for i in range(100)]})
    tbl_def_2 = NormalizedTable(
        table_id="tbl_esc2", table_name="EscTable2",
        columns=[_make_col("tbl_esc2", "c2", "ambig_field_y", CanonicalPhysicalType.STRING)],
        row_count=100, column_count=1,
    )
    dataset_2 = NormalizedDataset(
        dataset_id="ds_esc2", run_id="r2", stage_name="norm", source_fingerprint="fp2",
        provenance=[], tables=[tbl_def_2], rules_applied=[],
    )
    prof_2 = profile_dataset(dataset_2, table_data={"tbl_esc2": df_contra})

    gw_contra = MockFrozenModelGateway(mode="contradictory")
    sem_2 = build_semantic_model(dataset_2, prof_2, model_gateway=gw_contra)
    col_2 = sem_2.tables[0].columns[0]

    # Model tried to claim it is an ENTITY_IDENTIFIER, but uniqueness < 0.75 -> rejected
    assert col_2.role != SemanticColumnRole.ENTITY_IDENTIFIER
    assert col_2.role == SemanticColumnRole.AMBIGUOUS

    # Case 3: Offline fail-soft (uses distinct column to avoid cache)
    df_offline = pd.DataFrame({"ambig_field_z": [f"val_off_{i % 60}" for i in range(100)]})
    tbl_def_3 = NormalizedTable(
        table_id="tbl_esc3", table_name="EscTable3",
        columns=[_make_col("tbl_esc3", "c3", "ambig_field_z", CanonicalPhysicalType.STRING)],
        row_count=100, column_count=1,
    )
    dataset_3 = NormalizedDataset(
        dataset_id="ds_esc3", run_id="r3", stage_name="norm", source_fingerprint="fp3",
        provenance=[], tables=[tbl_def_3], rules_applied=[],
    )
    prof_3 = profile_dataset(dataset_3, table_data={"tbl_esc3": df_offline})

    gw_offline = MockFrozenModelGateway(mode="offline")
    sem_3 = build_semantic_model(dataset_3, prof_3, model_gateway=gw_offline)
    col_3 = sem_3.tables[0].columns[0]
    assert col_3.classification_source == ClassificationSource.FALLBACK
    assert col_3.role == SemanticColumnRole.AMBIGUOUS
    assert "Model assistance unavailable" in col_3.rationale


# =========================================================================
# 4. LABELED GRAIN BENCHMARK (14 FIXTURES)
# =========================================================================

@dataclass(frozen=True)
class GrainTruthFixture:
    fixture_id: str
    description: str
    table_name: str
    columns: list[tuple[str, CanonicalPhysicalType, str | None]]  # (name, ptype, unit)
    data_generator: Any
    expected_primary_entity: CanonicalGrain
    expected_temporal_grain: TemporalGrain
    expected_grain_expression: str
    expected_status: str  # "RESOLVED", "AMBIGUOUS", "UNKNOWN"


def _gen_person():
    return pd.DataFrame({"employee_id": [f"EMP-{i:03d}" for i in range(50)], "name": [f"Person {i}" for i in range(50)]})

def _gen_person_x_day():
    return pd.DataFrame({
        "employee_id": ["E1", "E1", "E2", "E2"],
        "attendance_date": ["2026-01-01", "2026-01-02", "2026-01-01", "2026-01-02"],
        "hours": [8.0, 8.0, 7.5, 8.0],
    })

def _gen_person_x_month():
    return pd.DataFrame({
        "employee_id": ["E101", "E101", "E102", "E102"],
        "payroll_month": ["2026-01", "2026-02", "2026-01", "2026-02"],
        "net_pay": [5000, 5000, 5200, 5200],
    })

def _gen_store_x_week():
    return pd.DataFrame({
        "store_id": ["S1", "S1", "S2", "S2"],
        "week_number": ["W01", "W02", "W01", "W02"],
        "sales": [10000, 12000, 9000, 11000],
    })

def _gen_dept_x_month():
    return pd.DataFrame({
        "dept_code": ["ENG", "ENG", "MKT", "MKT"],
        "budget_month": ["2026-01", "2026-02", "2026-01", "2026-02"],
        "budget": [100000, 105000, 50000, 52000],
    })

def _gen_transaction():
    return pd.DataFrame({"order_id": [f"ORD-{i:04d}" for i in range(50)], "amount": [i * 10.0 for i in range(50)]})

def _gen_event():
    return pd.DataFrame({"event_id": [f"EVT-{i:04d}" for i in range(50)], "log_message": [f"Event {i}" for i in range(50)]})

def _gen_product_x_location():
    return pd.DataFrame({
        "product_id": ["P1", "P1", "P2", "P2"],
        "location_id": ["LOC_A", "LOC_B", "LOC_A", "LOC_B"],
        "inventory": [100, 200, 150, 250],
    })

def _gen_product_x_location_x_date():
    return pd.DataFrame({
        "product_id": ["P1", "P1", "P2", "P2"],
        "location_id": ["LOC_A", "LOC_B", "LOC_A", "LOC_B"],
        "snapshot_date": ["2026-01-01", "2026-01-01", "2026-01-01", "2026-01-01"],
        "stock": [50, 75, 120, 90],
    })

def _gen_surrogate_only():
    return pd.DataFrame({
        "row_id": [1, 2, 3, 4],
        "feature_1": [10.5, 20.3, 15.2, 22.1],
        "feature_2": [100, 200, 150, 300],
    })

def _gen_ambiguous_grain():
    return pd.DataFrame({
        "attr_a": ["Alpha", "Beta", "Gamma", "Alpha"],
        "attr_b": ["Red", "Blue", "Red", "Blue"],
        "metric_val": [10, 20, 30, 40],
    })

def _gen_unknown_grain():
    return pd.DataFrame({
        "unstructured_memo": ["Note 1", "Note 2", "Note 3", "Note 4"],
        "comment": ["Comm A", "Comm B", "Comm C", "Comm D"],
    })

def _gen_compound_grain():
    return pd.DataFrame({
        "store_id": ["S1", "S1", "S2", "S2"],
        "product_id": ["P10", "P20", "P10", "P20"],
        "units": [5, 10, 15, 20],
    })

def _gen_misleading_row_id():
    # Technical row_id + true business person x day
    return pd.DataFrame({
        "row_id": [1, 2, 3, 4],  # Unique surrogate key
        "employee_id": ["E1", "E1", "E2", "E2"],  # Domain entity
        "timesheet_date": ["2026-01-01", "2026-01-02", "2026-01-01", "2026-01-02"],  # Temporal dimension
        "hours": [8.0, 8.5, 8.0, 7.5],
    })


GRAIN_BENCHMARK_FIXTURES: list[GrainTruthFixture] = [
    GrainTruthFixture("g01", "Single Entity Person", "Employees", [("employee_id", CanonicalPhysicalType.STRING, None), ("name", CanonicalPhysicalType.STRING, None)], _gen_person, CanonicalGrain.PERSON, TemporalGrain.NONE, "PERSON", "RESOLVED"),
    GrainTruthFixture("g02", "Periodic Snapshot Person x Day", "Attendance", [("employee_id", CanonicalPhysicalType.STRING, None), ("attendance_date", CanonicalPhysicalType.DATE, None), ("hours", CanonicalPhysicalType.FLOAT, "hours")], _gen_person_x_day, CanonicalGrain.PERSON, TemporalGrain.DAY, "PERSON x DAY", "RESOLVED"),
    GrainTruthFixture("g03", "Periodic Snapshot Person x Month", "Payroll", [("employee_id", CanonicalPhysicalType.STRING, None), ("payroll_month", CanonicalPhysicalType.DATE, None), ("net_pay", CanonicalPhysicalType.INTEGER, "USD")], _gen_person_x_month, CanonicalGrain.PERSON, TemporalGrain.MONTH, "PERSON x MONTH", "RESOLVED"),
    GrainTruthFixture("g04", "Periodic Snapshot Store x Week", "StoreWeeklySales", [("store_id", CanonicalPhysicalType.STRING, None), ("week_number", CanonicalPhysicalType.STRING, None), ("sales", CanonicalPhysicalType.INTEGER, "USD")], _gen_store_x_week, CanonicalGrain.STORE, TemporalGrain.WEEK, "STORE x WEEK", "RESOLVED"),
    GrainTruthFixture("g05", "Periodic Snapshot Dept x Month", "DeptMonthlyBudget", [("dept_code", CanonicalPhysicalType.STRING, None), ("budget_month", CanonicalPhysicalType.DATE, None), ("budget", CanonicalPhysicalType.INTEGER, "USD")], _gen_dept_x_month, CanonicalGrain.DEPARTMENT, TemporalGrain.MONTH, "DEPARTMENT x MONTH", "RESOLVED"),
    GrainTruthFixture("g06", "Event/Transaction Grain", "Orders", [("order_id", CanonicalPhysicalType.STRING, None), ("amount", CanonicalPhysicalType.FLOAT, "USD")], _gen_transaction, CanonicalGrain.TRANSACTION, TemporalGrain.NONE, "TRANSACTION", "RESOLVED"),
    GrainTruthFixture("g07", "Audit Event Grain", "SystemEvents", [("event_id", CanonicalPhysicalType.STRING, None), ("log_message", CanonicalPhysicalType.STRING, None)], _gen_event, CanonicalGrain.EVENT, TemporalGrain.NONE, "EVENT", "RESOLVED"),
    GrainTruthFixture("g08", "Multi-Entity Composite", "ProductLocationInventory", [("product_id", CanonicalPhysicalType.STRING, None), ("location_id", CanonicalPhysicalType.STRING, None), ("inventory", CanonicalPhysicalType.INTEGER, None)], _gen_product_x_location, CanonicalGrain.COMPOSITE, TemporalGrain.NONE, "PRODUCT x LOCATION", "RESOLVED"),
    GrainTruthFixture("g09", "Multi-Entity Periodic Snapshot", "InventorySnapshots", [("product_id", CanonicalPhysicalType.STRING, None), ("location_id", CanonicalPhysicalType.STRING, None), ("snapshot_date", CanonicalPhysicalType.DATE, None), ("stock", CanonicalPhysicalType.INTEGER, None)], _gen_product_x_location_x_date, CanonicalGrain.COMPOSITE, TemporalGrain.DAY, "PRODUCT x LOCATION x DAY", "RESOLVED"),
    GrainTruthFixture("g10", "Surrogate Key Only Table", "RawFeatures", [("row_id", CanonicalPhysicalType.INTEGER, None), ("feature_1", CanonicalPhysicalType.FLOAT, None), ("feature_2", CanonicalPhysicalType.INTEGER, None)], _gen_surrogate_only, CanonicalGrain.AMBIGUOUS, TemporalGrain.NONE, "AMBIGUOUS", "AMBIGUOUS"),
    GrainTruthFixture("g11", "Ambiguous Multi-Attribute Table", "AmbiguousTable", [("attr_a", CanonicalPhysicalType.STRING, None), ("attr_b", CanonicalPhysicalType.STRING, None), ("metric_val", CanonicalPhysicalType.INTEGER, None)], _gen_ambiguous_grain, CanonicalGrain.AMBIGUOUS, TemporalGrain.NONE, "AMBIGUOUS", "AMBIGUOUS"),
    GrainTruthFixture("g12", "Unknown Unkeyed Table", "UnkeyedMemos", [("unstructured_memo", CanonicalPhysicalType.STRING, None), ("comment", CanonicalPhysicalType.STRING, None)], _gen_unknown_grain, CanonicalGrain.UNKNOWN, TemporalGrain.NONE, "UNKNOWN", "UNKNOWN"),
    GrainTruthFixture("g13", "Compound Entity Grain", "StoreProductCatalog", [("store_id", CanonicalPhysicalType.STRING, None), ("product_id", CanonicalPhysicalType.STRING, None), ("units", CanonicalPhysicalType.INTEGER, None)], _gen_compound_grain, CanonicalGrain.COMPOSITE, TemporalGrain.NONE, "STORE x PRODUCT", "RESOLVED"),
    GrainTruthFixture("g14", "Misleading Surrogate row_id Table", "WorkTimesheets", [("row_id", CanonicalPhysicalType.INTEGER, None), ("employee_id", CanonicalPhysicalType.STRING, None), ("timesheet_date", CanonicalPhysicalType.DATE, None), ("hours", CanonicalPhysicalType.FLOAT, "hours")], _gen_misleading_row_id, CanonicalGrain.PERSON, TemporalGrain.DAY, "PERSON x DAY", "RESOLVED"),
]


def test_labeled_grain_benchmark_full_corpus():
    """
    Executes GrainInferencer over the 14-fixture canonical corpus.
    Evaluates Exact Grain Accuracy, Component Accuracy, and guarantees FALSE_CONFIDENT_GRAIN = 0.
    """
    exact_matches = 0
    component_matches = 0
    false_confident_grains = 0
    ambiguous_correctly_withheld = 0
    total_ambiguous_fixtures = 0
    unknown_correctly_withheld = 0
    total_unknown_fixtures = 0

    results = []

    for fix in GRAIN_BENCHMARK_FIXTURES:
        df = fix.data_generator()
        tbl_id = f"tbl_{fix.fixture_id}"
        cols = [_make_col(tbl_id, f"c{i}", name, ptype, unit) for i, (name, ptype, unit) in enumerate(fix.columns)]

        tbl_def = NormalizedTable(
            table_id=tbl_id,
            table_name=fix.table_name,
            columns=cols,
            row_count=len(df),
            column_count=len(cols),
        )
        dataset = NormalizedDataset(
            dataset_id=f"ds_{fix.fixture_id}",
            run_id="r_grain",
            stage_name="normalization",
            source_fingerprint=f"fp_grain_{fix.fixture_id}",
            provenance=[],
            tables=[tbl_def],
            rules_applied=[],
        )

        prof = profile_dataset(dataset, table_data={tbl_id: df})
        sem = build_semantic_model(dataset, prof)
        grain_prof = infer_grain(dataset, prof, sem)
        g = grain_prof.table_grains[0]

        is_exact = (g.primary_entity == fix.expected_primary_entity and g.temporal_grain == fix.expected_temporal_grain)
        if fix.expected_status in ("AMBIGUOUS", "UNKNOWN"):
            is_exact = (g.primary_entity == fix.expected_primary_entity)

        if is_exact:
            exact_matches += 1

        # Component accuracy (checks if expected components appear in expression or key)
        is_comp = False
        if is_exact or (fix.expected_primary_entity.value in g.grain_expression):
            is_comp = True
            component_matches += 1

        # False confident check: Fixture is truly ambiguous/unknown, but inferencer claimed RESOLVED with high confidence
        if fix.expected_status in ("AMBIGUOUS", "UNKNOWN"):
            if fix.expected_status == "AMBIGUOUS":
                total_ambiguous_fixtures += 1
                if g.primary_entity == CanonicalGrain.AMBIGUOUS:
                    ambiguous_correctly_withheld += 1
                else:
                    false_confident_grains += 1
            elif fix.expected_status == "UNKNOWN":
                total_unknown_fixtures += 1
                if g.primary_entity == CanonicalGrain.UNKNOWN:
                    unknown_correctly_withheld += 1
                else:
                    false_confident_grains += 1

        results.append({
            "fixture": fix.fixture_id,
            "description": fix.description,
            "expected_expr": fix.expected_grain_expression,
            "actual_expr": g.grain_expression,
            "expected_entity": fix.expected_primary_entity.value,
            "actual_entity": g.primary_entity.value,
            "expected_status": fix.expected_status,
            "actual_status": g.grain_status,
            "confidence": g.grain_confidence,
            "is_exact": is_exact,
        })

    total_fixtures = len(GRAIN_BENCHMARK_FIXTURES)
    exact_accuracy = exact_matches / total_fixtures
    component_accuracy = component_matches / total_fixtures

    print("\n" + "=" * 60)
    print(f"GRAIN BENCHMARK RESULTS ({total_fixtures} fixtures)")
    print(f"Exact Grain Accuracy:       {exact_accuracy:.4f} ({exact_matches}/{total_fixtures})")
    print(f"Component Accuracy:         {component_accuracy:.4f} ({component_matches}/{total_fixtures})")
    print(f"False Confident Grains:     {false_confident_grains}")
    print(f"Ambiguous Withheld:         {ambiguous_correctly_withheld}/{total_ambiguous_fixtures}")
    print(f"Unknown Withheld:           {unknown_correctly_withheld}/{total_unknown_fixtures}")
    print("=" * 60)

    # Absolute Requirements
    assert false_confident_grains == 0, f"Expected 0 false confident grains, found {false_confident_grains}"
    assert exact_accuracy == 1.0, f"Expected 1.0 exact accuracy, got {exact_accuracy:.4f}"
    assert component_accuracy == 1.0, f"Expected 1.0 component accuracy, got {component_accuracy:.4f}"
    assert ambiguous_correctly_withheld == total_ambiguous_fixtures
    assert unknown_correctly_withheld == total_unknown_fixtures
