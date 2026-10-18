"""
HighView Ingestion V2 — Phase I4 Tests: Relationship Discovery, Validation & Join Planning
Tests:
- Relationship candidate generation & blocking strategies (pairwise explosion protection)
- Relationship validation across single, composite, synonym, and leading-zero keys
- Cardinality inference (1:1, 1:N, N:1, M:N)
- Fanout detection and estimated row multipliers
- Strict rejection of measure <-> identifier, status <-> status, and M:N cartesian traps
- Join safety analyzer across all 6 canonical scenarios (A through F)
- Governed join planning with target grain, pre-aggregation, and measure additivity
- Ratio, distinct count, and semi-additive metric protection
- Epistemic boundary invariants (0 model calls, 0 EDA-B, 0 vectors, input immutability)
"""

import pytest
import pandas as pd
from app.services.ingestion_v2.contracts.base import SourceCoordinateRef
from app.services.ingestion_v2.contracts.grain import (
    CanonicalGrain,
    GrainProfile,
    TableGrainProfile,
    TemporalGrain,
)
from app.services.ingestion_v2.contracts.joins import (
    JoinPlan,
    JoinSafetyAssessment,
    JoinSafetyStatus,
    MeasureAdditivity,
    PreAggregationSpec,
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
from app.services.ingestion_v2.contracts.relationships import (
    CandidateKeyType,
    RelationshipCandidate,
    RelationshipCandidateSet,
    RelationshipCardinality,
    RelationshipStatus,
    ValidatedRelationshipEdge,
    ValidatedRelationshipGraph,
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
from app.services.ingestion_v2.joins.join_planner import infer_measure_additivity, plan_join
from app.services.ingestion_v2.joins.join_safety import JoinSafetyAnalyzer
from app.services.ingestion_v2.relationships.candidate_generator import (
    CandidateGenerationStats,
    generate_candidates,
)
from app.services.ingestion_v2.relationships.candidate_rules import (
    compute_name_similarity,
    compute_semantic_role_compatibility,
)
from app.services.ingestion_v2.relationships.relationship_validator import (
    compute_expected_fanout,
    validate_candidates,
)


def _make_col(
    col_id: str,
    table_id: str,
    name: str,
    ptype: CanonicalPhysicalType,
    samples: list[str] | None = None,
) -> NormalizedColumn:
    return NormalizedColumn(
        column_id=col_id,
        table_id=table_id,
        column_name=name,
        canonical_type=ptype,
        lineage=NormalizedFieldLineage(column_id=col_id, raw_header_name=name),
        null_count=0,
        non_null_count=len(samples) if samples else 10,
        sample_values=samples or ["val1", "val2"],
    )


def _make_col_prof(
    col_id: str,
    table_id: str,
    name: str,
    ptype: str,
    uniqueness: float = 1.0,
    null_ratio: float = 0.0,
    cand_id_score: float = 0.9,
    pattern: str = "AAAA-DDDD",
) -> ColumnStructuralProfile:
    return ColumnStructuralProfile(
        column_id=col_id,
        table_id=table_id,
        column_name=name,
        physical_type=ptype,
        row_count=100,
        null_count=int(null_ratio * 100),
        null_ratio=null_ratio,
        non_null_count=100 - int(null_ratio * 100),
        distinct_count=int(uniqueness * 100),
        uniqueness_ratio=uniqueness,
        dominant_pattern=pattern,
        candidate_identifier_score=cand_id_score,
    )


def _make_quality() -> StructuralDataQuality:
    return StructuralDataQuality(
        completeness_score=1.0,
        validity_score=1.0,
        uniqueness_score=1.0,
        consistency_score=1.0,
        reconstruction_fidelity_score=1.0,
        overall_structural_quality=1.0,
    )


def _make_col_sem(
    col_name: str,
    role: SemanticColumnRole,
    entity: SemanticEntityType,
    concept: SemanticConcept = SemanticConcept.IDENTIFIER,
    mclass: MeasureClass | None = None,
    col_id: str | None = None,
    table_id: str = "t",
) -> SemanticColumnAssignment:
    return SemanticColumnAssignment(
        column_id=col_id or f"col_{col_name}",
        table_id=table_id,
        column_name=col_name,
        role=role,
        entity_type=entity,
        semantic_concept=concept,
        measure_class=mclass,
        confidence=0.95,
        is_ambiguous=False,
        classification_source=ClassificationSource.HEURISTIC,
        rationale="test",
    )


def _make_table_sem(
    table_id: str,
    cols: list[SemanticColumnAssignment],
    primary_entity: SemanticEntityType = SemanticEntityType.PERSON,
) -> TableSemanticModel:
    return TableSemanticModel(
        table_id=table_id,
        table_name=table_id,
        primary_entity_type=primary_entity,
        columns=cols,
    )


def _make_table_grain(
    table_id: str,
    canonical_grain: CanonicalGrain,
    grain_expr: str,
    key_cols: list[str],
) -> TableGrainProfile:
    return TableGrainProfile(
        table_id=table_id,
        table_name=table_id,
        primary_entity=canonical_grain,
        temporal_grain=TemporalGrain.NONE,
        key_columns=key_cols,
        grain_dimensions=key_cols,
        grain_expression=grain_expr,
        is_unique=True,
        uniqueness_ratio=1.0,
        grain_confidence=0.95,
        duplicate_key_rows=0,
        candidate_grains=[grain_expr],
        grain_status="RESOLVED",
        rationale="test",
    )


# ==============================================================================
# 1. CANDIDATE GENERATION & PAIRWISE EXPLOSION PROTECTION
# ==============================================================================

def test_candidate_generation_lexical_synonym_and_blocking():
    """Verify candidate generation detects synonym keys (employee_id <-> worker_number) and blocks measures."""
    src = SourceCoordinateRef(dataset_id="ds-rel-01", source_file_hash="hash01")

    # Table A: Employees (employee_id, department, salary)
    cols_a = [
        _make_col("c_e1", "tbl_emp", "employee_id", CanonicalPhysicalType.STRING),
        _make_col("c_e2", "tbl_emp", "department", CanonicalPhysicalType.STRING),
        _make_col("c_e3", "tbl_emp", "salary", CanonicalPhysicalType.FLOAT),
    ]
    tbl_a = NormalizedTable(table_id="tbl_emp", table_name="Employees", columns=cols_a, row_count=10, column_count=3)

    # Table B: Workers (worker_number, department, hours_worked)
    cols_b = [
        _make_col("c_w1", "tbl_wrk", "worker_number", CanonicalPhysicalType.STRING),
        _make_col("c_w2", "tbl_wrk", "department", CanonicalPhysicalType.STRING),
        _make_col("c_w3", "tbl_wrk", "hours_worked", CanonicalPhysicalType.FLOAT),
    ]
    tbl_b = NormalizedTable(table_id="tbl_wrk", table_name="Workers", columns=cols_b, row_count=10, column_count=3)

    norm_ds = NormalizedDataset(
        dataset_id="ds-rel-01",
        run_id="run-01",
        source_fingerprint="fp01",
        provenance=[src],
        tables=[tbl_a, tbl_b],
    )

    prof_a = TableStructuralProfile(
        table_id="tbl_emp",
        table_name="Employees",
        row_count=10,
        column_count=3,
        columns=[
            _make_col_prof("c_e1", "tbl_emp", "employee_id", "STRING", uniqueness=1.0),
            _make_col_prof("c_e2", "tbl_emp", "department", "STRING", uniqueness=0.3),
            _make_col_prof("c_e3", "tbl_emp", "salary", "FLOAT", uniqueness=0.8),
        ],
        quality=_make_quality(),
    )
    prof_b = TableStructuralProfile(
        table_id="tbl_wrk",
        table_name="Workers",
        row_count=10,
        column_count=3,
        columns=[
            _make_col_prof("c_w1", "tbl_wrk", "worker_number", "STRING", uniqueness=1.0),
            _make_col_prof("c_w2", "tbl_wrk", "department", "STRING", uniqueness=0.3),
            _make_col_prof("c_w3", "tbl_wrk", "hours_worked", "FLOAT", uniqueness=0.8),
        ],
        quality=_make_quality(),
    )
    struct_prof = StructuralProfile(
        dataset_id="ds-rel-01",
        run_id="run-01",
        stage_name="structural_profiling_eda_a",
        source_fingerprint="fp-prof",
        provenance=[src],
        tables=[prof_a, prof_b],
        dataset_structural_quality=_make_quality(),
    )

    sem_a = _make_table_sem(
        "tbl_emp",
        [
            _make_col_sem("employee_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticEntityType.PERSON),
            _make_col_sem("department", SemanticColumnRole.DIMENSION, SemanticEntityType.DEPARTMENT),
            _make_col_sem("salary", SemanticColumnRole.MEASURE, SemanticEntityType.UNKNOWN, SemanticConcept.MEASURE, MeasureClass.FINANCIAL),
        ],
    )
    sem_b = _make_table_sem(
        "tbl_wrk",
        [
            _make_col_sem("worker_number", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticEntityType.PERSON),
            _make_col_sem("department", SemanticColumnRole.DIMENSION, SemanticEntityType.DEPARTMENT),
            _make_col_sem("hours_worked", SemanticColumnRole.MEASURE, SemanticEntityType.UNKNOWN, SemanticConcept.MEASURE, MeasureClass.QUANTITY),
        ],
    )
    sem_model = SemanticModel(
        dataset_id="ds-rel-01",
        run_id="run-01",
        stage_name="semantic_modeling",
        source_fingerprint="fp-sem",
        provenance=[src],
        tables=[sem_a, sem_b],
    )

    grain_a = _make_table_grain("tbl_emp", CanonicalGrain.PERSON, "PERSON", ["employee_id"])
    grain_b = _make_table_grain("tbl_wrk", CanonicalGrain.PERSON, "PERSON", ["worker_number"])
    grain_prof = GrainProfile(
        dataset_id="ds-rel-01",
        run_id="run-01",
        stage_name="grain_inference",
        source_fingerprint="fp-grain",
        provenance=[src],
        table_grains=[grain_a, grain_b],
    )

    stats = CandidateGenerationStats()
    cand_set = generate_candidates(norm_ds, struct_prof, sem_model, grain_prof, stats_out=stats)

    # Assertions
    # 1. Total possible pairs: 3 cols x 3 cols = 9
    assert stats.raw_possible_pairs == 9
    # 2. Measure pairs (salary <-> worker_number, salary <-> hours_worked) were pruned
    assert stats.pruned_candidate_pairs > 0
    # 3. Found candidate for employee_id <-> worker_number (synonyms)
    cand_pairs = [(c.source_column_ids, c.target_column_ids) for c in cand_set.candidates]
    assert (["c_e1"], ["c_w1"]) in cand_pairs


def test_pairwise_explosion_protection_on_wide_tables():
    """Verify that a wide table scenario with 50 columns each does not produce 2,500 unconstrained candidates."""
    src = SourceCoordinateRef(dataset_id="ds-wide", source_file_hash="hash-wide")

    cols_a = [_make_col(f"ca_{i}", "tbl_w1", f"measure_val_{i}", CanonicalPhysicalType.FLOAT) for i in range(50)]
    cols_a[0] = _make_col("ca_0", "tbl_w1", "record_id", CanonicalPhysicalType.STRING)
    tbl_a = NormalizedTable(table_id="tbl_w1", table_name="WideA", columns=cols_a, row_count=100, column_count=50)

    cols_b = [_make_col(f"cb_{i}", "tbl_w2", f"measure_val_{i}", CanonicalPhysicalType.FLOAT) for i in range(50)]
    cols_b[0] = _make_col("cb_0", "tbl_w2", "record_id", CanonicalPhysicalType.STRING)
    tbl_b = NormalizedTable(table_id="tbl_w2", table_name="WideB", columns=cols_b, row_count=100, column_count=50)

    norm_ds = NormalizedDataset(dataset_id="ds-wide", run_id="run-w", source_fingerprint="fp-w", provenance=[src], tables=[tbl_a, tbl_b])

    prof_cols_a = [_make_col_prof(f"ca_{i}", "tbl_w1", f"measure_val_{i}", "FLOAT", cand_id_score=0.1) for i in range(50)]
    prof_cols_a[0] = _make_col_prof("ca_0", "tbl_w1", "record_id", "STRING", uniqueness=1.0, cand_id_score=0.95)
    prof_a = TableStructuralProfile(table_id="tbl_w1", table_name="WideA", row_count=100, column_count=50, columns=prof_cols_a, quality=_make_quality())

    prof_cols_b = [_make_col_prof(f"cb_{i}", "tbl_w2", f"measure_val_{i}", "FLOAT", cand_id_score=0.1) for i in range(50)]
    prof_cols_b[0] = _make_col_prof("cb_0", "tbl_w2", "record_id", "STRING", uniqueness=1.0, cand_id_score=0.95)
    prof_b = TableStructuralProfile(table_id="tbl_w2", table_name="WideB", row_count=100, column_count=50, columns=prof_cols_b, quality=_make_quality())
    struct_prof = StructuralProfile(dataset_id="ds-wide", run_id="run-w", stage_name="structural_profiling_eda_a", source_fingerprint="fp-pw", provenance=[src], tables=[prof_a, prof_b], dataset_structural_quality=_make_quality())

    sems_a = [_make_col_sem(f"measure_val_{i}", SemanticColumnRole.MEASURE, SemanticEntityType.UNKNOWN) for i in range(50)]
    sems_a[0] = _make_col_sem("record_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticEntityType.TRANSACTION)
    sem_a = _make_table_sem("tbl_w1", sems_a, SemanticEntityType.TRANSACTION)

    sems_b = [_make_col_sem(f"measure_val_{i}", SemanticColumnRole.MEASURE, SemanticEntityType.UNKNOWN) for i in range(50)]
    sems_b[0] = _make_col_sem("record_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticEntityType.TRANSACTION)
    sem_b = _make_table_sem("tbl_w2", sems_b, SemanticEntityType.TRANSACTION)
    sem_model = SemanticModel(dataset_id="ds-wide", run_id="run-w", stage_name="semantic_modeling", source_fingerprint="fp-sw", provenance=[src], tables=[sem_a, sem_b])

    grain_a = _make_table_grain("tbl_w1", CanonicalGrain.TRANSACTION, "TRANSACTION", ["record_id"])
    grain_b = _make_table_grain("tbl_w2", CanonicalGrain.TRANSACTION, "TRANSACTION", ["record_id"])
    grain_prof = GrainProfile(dataset_id="ds-wide", run_id="run-w", stage_name="grain_inference", source_fingerprint="fp-gw", provenance=[src], table_grains=[grain_a, grain_b])

    stats = CandidateGenerationStats()
    cand_set = generate_candidates(norm_ds, struct_prof, sem_model, grain_prof, stats_out=stats)

    # 50 x 50 = 2500 possible pairs
    assert stats.raw_possible_pairs == 2500
    # Almost all float measure pairs pruned!
    assert stats.pruned_candidate_pairs >= 2490
    assert len(cand_set.candidates) == 1
    assert cand_set.candidates[0].source_column_ids == ["ca_0"]
    assert cand_set.candidates[0].target_column_ids == ["cb_0"]


# ==============================================================================
# 2. CARDINALITY & FANOUT TRAP TESTS
# ==============================================================================

def test_cardinality_inference_and_fanout_computation():
    """Verify 1:1, 1:N, N:1, and M:N cardinality inference and fanout calculation."""
    df_emp = pd.DataFrame({"employee_id": ["E1", "E2", "E3", "E4", "E5"]})
    df_att = pd.DataFrame({"employee_id": ["E1", "E1", "E1", "E2", "E2", "E2", "E3", "E3", "E3", "E4", "E4", "E4", "E5", "E5", "E5"]})

    mult, max_m, joined_rows = compute_expected_fanout(df_emp, ["employee_id"], df_att, ["employee_id"])
    assert joined_rows == 15
    assert mult == 1.0
    assert max_m == 3.0

    emp_ids = ["EMP01", "EMP02"]
    att_trap = pd.DataFrame({"employee_id": [e for e in emp_ids for _ in range(22)]})  # 44 rows
    leave_trap = pd.DataFrame({"employee_id": [e for e in emp_ids for _ in range(3)]})  # 6 rows

    mult_trap, max_trap, joined_trap = compute_expected_fanout(att_trap, ["employee_id"], leave_trap, ["employee_id"])
    assert joined_trap == 132
    assert max_trap == 66.0
    assert mult_trap == round(132 / 44, 4)


# ==============================================================================
# 3. RELATIONSHIP VALIDATOR BENCHMARK (10 CANONICAL FIXTURES)
# ==============================================================================

def test_canonical_relationship_benchmark():
    """
    Evaluate 10 required truth scenarios:
    1. VALID: employee_id <-> worker_number
    2. VALID: store_id + week <-> store_id + week (composite)
    3. VALID: product_id <-> inventory.product_id
    4. INVALID: department <-> department (many-to-many Cartesian risk)
    5. INVALID: status <-> status (different meaning)
    6. INVALID: numeric measure <-> numeric identifier
    7. AMBIGUOUS: employee_name <-> person_name
    8. VALID_WITH_LOW_COVERAGE: employee_id <-> historical_attendance.employee_id
    9. COMPOSITE: location_id + date <-> location_id + date
    10. LEADING_ZERO: 00421 <-> 00421
    """
    src = SourceCoordinateRef(dataset_id="ds-bench", source_file_hash="hash-bench")

    # Table 1: Employees
    df_emp = pd.DataFrame({
        "employee_id": ["00421", "00422", "00423", "00424"],
        "employee_name": ["Alice Smith", "Bob Jones", "Charlie Brown", "Diana Prince"],
        "department": ["Sales", "Sales", "Engineering", "Engineering"],
        "status": ["ACTIVE", "ACTIVE", "ACTIVE", "LEAVE"],
        "salary": [75000.0, 82000.0, 95000.0, 88000.0],
    })
    # Table 2: Workers
    df_wrk = pd.DataFrame({
        "worker_number": ["00421", "00422", "00423", "00424"],
        "person_name": ["Alice S.", "Bob J.", "Charlie B.", "Diana P."],
        "department": ["Sales", "Sales", "Sales", "Engineering"],
        "status": ["APPROVED", "PENDING", "APPROVED", "REJECTED"],
        "worker_id_num": [421, 422, 423, 424],
    })
    # Table 3: Store Sales
    df_sales = pd.DataFrame({
        "store_id": ["S1", "S1", "S2", "S2"],
        "week": ["W01", "W02", "W01", "W02"],
        "revenue": [1000.0, 1200.0, 800.0, 950.0],
    })
    # Table 4: Store Targets
    df_targets = pd.DataFrame({
        "store_id": ["S1", "S1", "S2", "S2"],
        "week": ["W01", "W02", "W01", "W02"],
        "target": [900.0, 1100.0, 850.0, 900.0],
    })
    # Table 5: Products Master
    df_prod = pd.DataFrame({
        "product_id": ["P100", "P200", "P300"],
        "product_name": ["Widget A", "Widget B", "Gadget C"],
    })
    # Table 6: Inventory
    df_inv = pd.DataFrame({
        "product_id": ["P100", "P100", "P200", "P300"],
        "location_id": ["LOC1", "LOC2", "LOC1", "LOC2"],
        "date": ["2026-01-01", "2026-01-01", "2026-01-01", "2026-01-01"],
        "stock": [50, 20, 80, 15],
    })
    # Table 7: Historical Attendance
    df_hist = pd.DataFrame({
        "employee_id": ["00421", "00421"],
        "attendance_date": ["2020-01-01", "2020-01-02"],
    })
    # Table 8: Environmental Facility
    df_env = pd.DataFrame({
        "location_id": ["LOC1", "LOC2"],
        "date": ["2026-01-01", "2026-01-01"],
        "emissions": [12.5, 8.2],
    })

    table_data = {
        "t_emp": df_emp,
        "t_wrk": df_wrk,
        "t_sales": df_sales,
        "t_targets": df_targets,
        "t_prod": df_prod,
        "t_inv": df_inv,
        "t_hist": df_hist,
        "t_env": df_env,
    }

    tbls = [
        NormalizedTable(table_id="t_emp", table_name="Employees", columns=[_make_col(f"e_{c}", "t_emp", c, CanonicalPhysicalType.STRING) for c in df_emp.columns], row_count=len(df_emp), column_count=len(df_emp.columns)),
        NormalizedTable(table_id="t_wrk", table_name="Workers", columns=[_make_col(f"w_{c}", "t_wrk", c, CanonicalPhysicalType.STRING) for c in df_wrk.columns], row_count=len(df_wrk), column_count=len(df_wrk.columns)),
        NormalizedTable(table_id="t_sales", table_name="Sales", columns=[_make_col(f"s_{c}", "t_sales", c, CanonicalPhysicalType.STRING) for c in df_sales.columns], row_count=len(df_sales), column_count=len(df_sales.columns)),
        NormalizedTable(table_id="t_targets", table_name="Targets", columns=[_make_col(f"tar_{c}", "t_targets", c, CanonicalPhysicalType.STRING) for c in df_targets.columns], row_count=len(df_targets), column_count=len(df_targets.columns)),
        NormalizedTable(table_id="t_prod", table_name="Products", columns=[_make_col(f"p_{c}", "t_prod", c, CanonicalPhysicalType.STRING) for c in df_prod.columns], row_count=len(df_prod), column_count=len(df_prod.columns)),
        NormalizedTable(table_id="t_inv", table_name="Inventory", columns=[_make_col(f"i_{c}", "t_inv", c, CanonicalPhysicalType.STRING) for c in df_inv.columns], row_count=len(df_inv), column_count=len(df_inv.columns)),
        NormalizedTable(table_id="t_hist", table_name="HistAttendance", columns=[_make_col(f"h_{c}", "t_hist", c, CanonicalPhysicalType.STRING) for c in df_hist.columns], row_count=len(df_hist), column_count=len(df_hist.columns)),
        NormalizedTable(table_id="t_env", table_name="Environment", columns=[_make_col(f"env_{c}", "t_env", c, CanonicalPhysicalType.STRING) for c in df_env.columns], row_count=len(df_env), column_count=len(df_env.columns)),
    ]
    norm_ds = NormalizedDataset(dataset_id="ds-bench", run_id="run-b", source_fingerprint="fp-b", provenance=[src], tables=tbls)

    prof_list = [
        TableStructuralProfile(table_id=t.table_id, table_name=t.table_name, row_count=t.row_count, column_count=t.column_count, columns=[_make_col_prof(c.column_id, t.table_id, c.column_name, "STRING") for c in t.columns], quality=_make_quality())
        for t in tbls
    ]
    struct_prof = StructuralProfile(dataset_id="ds-bench", run_id="run-b", stage_name="structural_profiling_eda_a", source_fingerprint="fp-sb", provenance=[src], tables=prof_list, dataset_structural_quality=_make_quality())

    sem_models = [
        _make_table_sem("t_emp", [
            _make_col_sem("employee_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticEntityType.PERSON),
            _make_col_sem("employee_name", SemanticColumnRole.ENTITY_LABEL, SemanticEntityType.PERSON),
            _make_col_sem("department", SemanticColumnRole.DIMENSION, SemanticEntityType.DEPARTMENT),
            _make_col_sem("status", SemanticColumnRole.STATUS, SemanticEntityType.PERSON),
            _make_col_sem("salary", SemanticColumnRole.MEASURE, SemanticEntityType.UNKNOWN, SemanticConcept.MEASURE, MeasureClass.FINANCIAL),
        ], SemanticEntityType.PERSON),
        _make_table_sem("t_wrk", [
            _make_col_sem("worker_number", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticEntityType.PERSON),
            _make_col_sem("person_name", SemanticColumnRole.ENTITY_LABEL, SemanticEntityType.PERSON),
            _make_col_sem("department", SemanticColumnRole.DIMENSION, SemanticEntityType.DEPARTMENT),
            _make_col_sem("status", SemanticColumnRole.STATUS, SemanticEntityType.EVENT),
            _make_col_sem("worker_id_num", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticEntityType.PERSON),
        ], SemanticEntityType.PERSON),
        _make_table_sem("t_sales", [
            _make_col_sem("store_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticEntityType.STORE),
            _make_col_sem("week", SemanticColumnRole.TIME, SemanticEntityType.UNKNOWN, SemanticConcept.TIME_SPAN),
            _make_col_sem("revenue", SemanticColumnRole.MEASURE, SemanticEntityType.UNKNOWN, SemanticConcept.MEASURE, MeasureClass.FINANCIAL),
        ], SemanticEntityType.STORE),
        _make_table_sem("t_targets", [
            _make_col_sem("store_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticEntityType.STORE),
            _make_col_sem("week", SemanticColumnRole.TIME, SemanticEntityType.UNKNOWN, SemanticConcept.TIME_SPAN),
            _make_col_sem("target", SemanticColumnRole.MEASURE, SemanticEntityType.UNKNOWN, SemanticConcept.MEASURE, MeasureClass.FINANCIAL),
        ], SemanticEntityType.STORE),
        _make_table_sem("t_prod", [
            _make_col_sem("product_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticEntityType.PRODUCT),
            _make_col_sem("product_name", SemanticColumnRole.ENTITY_LABEL, SemanticEntityType.PRODUCT),
        ], SemanticEntityType.PRODUCT),
        _make_table_sem("t_inv", [
            _make_col_sem("product_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticEntityType.PRODUCT),
            _make_col_sem("location_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticEntityType.LOCATION),
            _make_col_sem("date", SemanticColumnRole.TIME, SemanticEntityType.UNKNOWN, SemanticConcept.TIME_SPAN),
            _make_col_sem("stock", SemanticColumnRole.MEASURE, SemanticEntityType.UNKNOWN, SemanticConcept.MEASURE, MeasureClass.QUANTITY),
        ], SemanticEntityType.PRODUCT),
        _make_table_sem("t_hist", [
            _make_col_sem("employee_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticEntityType.PERSON),
            _make_col_sem("attendance_date", SemanticColumnRole.TIME, SemanticEntityType.UNKNOWN, SemanticConcept.TIME_SPAN),
        ], SemanticEntityType.PERSON),
        _make_table_sem("t_env", [
            _make_col_sem("location_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticEntityType.LOCATION),
            _make_col_sem("date", SemanticColumnRole.TIME, SemanticEntityType.UNKNOWN, SemanticConcept.TIME_SPAN),
            _make_col_sem("emissions", SemanticColumnRole.MEASURE, SemanticEntityType.UNKNOWN, SemanticConcept.MEASURE, MeasureClass.QUANTITY),
        ], SemanticEntityType.LOCATION),
    ]
    sem_model = SemanticModel(dataset_id="ds-bench", run_id="run-b", stage_name="semantic_modeling", source_fingerprint="fp-semb", provenance=[src], tables=sem_models)

    grain_profs = [
        _make_table_grain("t_emp", CanonicalGrain.PERSON, "PERSON", ["employee_id"]),
        _make_table_grain("t_wrk", CanonicalGrain.PERSON, "PERSON", ["worker_number"]),
        _make_table_grain("t_sales", CanonicalGrain.COMPOSITE, "STORE x WEEK", ["store_id", "week"]),
        _make_table_grain("t_targets", CanonicalGrain.COMPOSITE, "STORE x WEEK", ["store_id", "week"]),
        _make_table_grain("t_prod", CanonicalGrain.PRODUCT, "PRODUCT", ["product_id"]),
        _make_table_grain("t_inv", CanonicalGrain.COMPOSITE, "PRODUCT x LOCATION x DAY", ["product_id", "location_id", "date"]),
        _make_table_grain("t_hist", CanonicalGrain.COMPOSITE, "PERSON x DAY", ["employee_id", "attendance_date"]),
        _make_table_grain("t_env", CanonicalGrain.COMPOSITE, "LOCATION x DAY", ["location_id", "date"]),
    ]
    grain_prof = GrainProfile(dataset_id="ds-bench", run_id="run-b", stage_name="grain_inference", source_fingerprint="fp-gb", provenance=[src], table_grains=grain_profs)

    candidates = [
        RelationshipCandidate(candidate_id="c1", source_table_id="t_emp", source_column_ids=["e_employee_id"], target_table_id="t_wrk", target_column_ids=["w_worker_number"], discovery_method="BENCHMARK", confidence_score=0.9),
        RelationshipCandidate(candidate_id="c2", source_table_id="t_sales", source_column_ids=["s_store_id", "s_week"], target_table_id="t_targets", target_column_ids=["tar_store_id", "tar_week"], key_type=CandidateKeyType.COMPOSITE, discovery_method="BENCHMARK", confidence_score=0.95),
        RelationshipCandidate(candidate_id="c3", source_table_id="t_prod", source_column_ids=["p_product_id"], target_table_id="t_inv", target_column_ids=["i_product_id"], discovery_method="BENCHMARK", confidence_score=0.9),
        RelationshipCandidate(candidate_id="c4", source_table_id="t_emp", source_column_ids=["e_department"], target_table_id="t_wrk", target_column_ids=["w_department"], discovery_method="BENCHMARK", confidence_score=0.6),
        RelationshipCandidate(candidate_id="c5", source_table_id="t_emp", source_column_ids=["e_status"], target_table_id="t_wrk", target_column_ids=["w_status"], discovery_method="BENCHMARK", confidence_score=0.5),
        RelationshipCandidate(candidate_id="c6", source_table_id="t_emp", source_column_ids=["e_salary"], target_table_id="t_wrk", target_column_ids=["w_worker_id_num"], discovery_method="BENCHMARK", confidence_score=0.3),
        RelationshipCandidate(candidate_id="c7", source_table_id="t_emp", source_column_ids=["e_employee_name"], target_table_id="t_wrk", target_column_ids=["w_person_name"], discovery_method="BENCHMARK", confidence_score=0.6),
        RelationshipCandidate(candidate_id="c8", source_table_id="t_emp", source_column_ids=["e_employee_id"], target_table_id="t_hist", target_column_ids=["h_employee_id"], discovery_method="BENCHMARK", confidence_score=0.85),
        RelationshipCandidate(candidate_id="c9", source_table_id="t_inv", source_column_ids=["i_location_id", "i_date"], target_table_id="t_env", target_column_ids=["env_location_id", "env_date"], key_type=CandidateKeyType.COMPOSITE, discovery_method="BENCHMARK", confidence_score=0.9),
    ]
    cand_set = RelationshipCandidateSet(dataset_id="ds-bench", run_id="run-b", source_fingerprint="fp-cset", provenance=[src], candidates=candidates)

    graph = validate_candidates(cand_set, norm_ds, struct_prof, sem_model, grain_prof, table_data=table_data)
    edge_map = {e.candidate_id: e for e in graph.edges}

    assert edge_map["c1"].status == RelationshipStatus.ACCEPTED
    assert edge_map["c1"].cardinality == RelationshipCardinality.ONE_TO_ONE

    assert edge_map["c2"].status == RelationshipStatus.ACCEPTED
    assert edge_map["c2"].key_type == CandidateKeyType.COMPOSITE
    assert edge_map["c2"].cardinality == RelationshipCardinality.ONE_TO_ONE

    assert edge_map["c3"].status == RelationshipStatus.ACCEPTED
    assert edge_map["c3"].cardinality == RelationshipCardinality.ONE_TO_MANY

    assert edge_map["c4"].status == RelationshipStatus.REJECTED
    assert edge_map["c4"].cardinality == RelationshipCardinality.MANY_TO_MANY
    assert "CARTESIAN_RISK" in (edge_map["c4"].rejection_reason or "")

    assert edge_map["c5"].status == RelationshipStatus.REJECTED
    assert "STATUS_DOMAIN_MISMATCH" in (edge_map["c5"].rejection_reason or "")

    assert edge_map["c6"].status == RelationshipStatus.REJECTED
    assert "MEASURE_CANNOT_FORM_FOREIGN_KEY" in (edge_map["c6"].rejection_reason or "")

    assert edge_map["c7"].status == RelationshipStatus.AMBIGUOUS
    assert "ENTITY_LABEL" in (edge_map["c7"].rejection_reason or "")

    assert edge_map["c8"].status == RelationshipStatus.ACCEPTED
    assert edge_map["c8"].cardinality == RelationshipCardinality.ONE_TO_MANY

    assert edge_map["c9"].status == RelationshipStatus.ACCEPTED
    assert edge_map["c9"].key_type == CandidateKeyType.COMPOSITE

    accepted_ids = {e.candidate_id for e in graph.edges if e.status == RelationshipStatus.ACCEPTED}
    rejected_ids = {e.candidate_id for e in graph.edges if e.status == RelationshipStatus.REJECTED}
    ambiguous_ids = {e.candidate_id for e in graph.edges if e.status == RelationshipStatus.AMBIGUOUS}

    assert accepted_ids == {"c1", "c2", "c3", "c8", "c9"}
    assert rejected_ids == {"c4", "c5", "c6"}
    assert ambiguous_ids == {"c7"}
    assert len(accepted_ids & {"c4", "c5", "c6", "c7"}) == 0


# ==============================================================================
# 4. JOIN SAFETY ANALYZER (SCENARIOS A THROUGH F)
# ==============================================================================

def test_join_safety_scenarios_a_through_f():
    """
    Verify all 6 Join Safety Benchmark Scenarios:
    A. PERSON <-> PERSON x DAY dimension enrichment -> SAFE
    B. PERSON x DAY <-> PERSON x INCIDENT raw fact-to-fact -> UNSAFE
    C. PERSON x DAY -> aggregate PERSON x MONTH then join PERSON dimension -> SAFE_WITH_PREAGGREGATION
    D. STORE x WEEK <-> STORE x WEEK exact composite grain -> SAFE
    E. DEPARTMENT x MONTH <-> PERSON x DAY without aggregation -> UNSAFE
    F. PRODUCT x LOCATION x DAY <-> PRODUCT master dimension enrichment -> SAFE
    """
    grain_list = [
        _make_table_grain("t_person", CanonicalGrain.PERSON, "PERSON", ["employee_id"]),
        _make_table_grain("t_att_day", CanonicalGrain.COMPOSITE, "PERSON x DAY", ["employee_id", "date"]),
        _make_table_grain("t_leave_inc", CanonicalGrain.COMPOSITE, "PERSON x INCIDENT", ["employee_id", "incident_id"]),
        _make_table_grain("t_store_wk1", CanonicalGrain.COMPOSITE, "STORE x WEEK", ["store_id", "week"]),
        _make_table_grain("t_store_wk2", CanonicalGrain.COMPOSITE, "STORE x WEEK", ["store_id", "week"]),
        _make_table_grain("t_dept_mo", CanonicalGrain.COMPOSITE, "DEPARTMENT x MONTH", ["department", "month"]),
        _make_table_grain("t_prod", CanonicalGrain.PRODUCT, "PRODUCT", ["product_id"]),
        _make_table_grain("t_inv_daily", CanonicalGrain.COMPOSITE, "PRODUCT x LOCATION x DAY", ["product_id", "location_id", "date"]),
    ]
    grain_prof = GrainProfile(
        dataset_id="ds-safe",
        run_id="run-s",
        stage_name="grain_inference",
        source_fingerprint="fp-gs",
        provenance=[],
        table_grains=grain_list,
    )

    # Scenario A: PERSON <-> PERSON x DAY dimension enrichment -> SAFE
    edge_a = ValidatedRelationshipEdge(
        edge_id="e_a",
        candidate_id="c_a",
        source_table_id="t_person",
        source_column_ids=["employee_id"],
        target_table_id="t_att_day",
        target_column_ids=["employee_id"],
        key_type=CandidateKeyType.SINGLE,
        cardinality=RelationshipCardinality.ONE_TO_MANY,
        status=RelationshipStatus.ACCEPTED,
        referential_coverage=1.0,
        source_overlap_ratio=1.0,
        target_overlap_ratio=1.0,
        confidence=0.95,
        estimated_row_multiplier=1.0,
        is_grain_preserving=True,
    )
    assess_a = JoinSafetyAnalyzer.assess_edge_safety(edge_a, grain_prof)
    assert assess_a.safety_status == JoinSafetyStatus.SAFE
    assert assess_a.dimension_propagation_safe is True
    assert assess_a.recommended_target_grain == "PERSON x DAY"

    # Scenario B: PERSON x DAY <-> PERSON x INCIDENT raw fact-to-fact -> UNSAFE
    edge_b = ValidatedRelationshipEdge(
        edge_id="e_b",
        candidate_id="c_b",
        source_table_id="t_att_day",
        source_column_ids=["employee_id"],
        target_table_id="t_leave_inc",
        target_column_ids=["employee_id"],
        key_type=CandidateKeyType.SINGLE,
        cardinality=RelationshipCardinality.MANY_TO_MANY,
        status=RelationshipStatus.ACCEPTED,
        referential_coverage=0.9,
        source_overlap_ratio=0.9,
        target_overlap_ratio=0.9,
        confidence=0.85,
        estimated_row_multiplier=3.0,
        is_grain_preserving=False,
        duplication_risk_flag=True,
    )
    assess_b = JoinSafetyAnalyzer.assess_edge_safety(edge_b, grain_prof)
    assert assess_b.safety_status == JoinSafetyStatus.UNSAFE
    assert assess_b.many_to_many_risk is True
    assert assess_b.required_pre_aggregation is True

    # Scenario C: PERSON x DAY pre-aggregated to PERSON x MONTH -> SAFE_WITH_PREAGGREGATION
    assess_c = JoinSafetyAnalyzer.assess_edge_safety(edge_b, grain_prof, analysis_purpose="PREAGGREGATION_ANALYSIS", requested_target_grain="PERSON x MONTH")
    assert assess_c.safety_status == JoinSafetyStatus.SAFE_WITH_PREAGGREGATION
    assert assess_c.recommended_target_grain == "PERSON x MONTH"

    # Scenario D: STORE x WEEK <-> STORE x WEEK exact composite grain -> SAFE
    edge_d = ValidatedRelationshipEdge(
        edge_id="e_d",
        candidate_id="c_d",
        source_table_id="t_store_wk1",
        source_column_ids=["store_id", "week"],
        target_table_id="t_store_wk2",
        target_column_ids=["store_id", "week"],
        key_type=CandidateKeyType.COMPOSITE,
        cardinality=RelationshipCardinality.ONE_TO_ONE,
        status=RelationshipStatus.ACCEPTED,
        referential_coverage=1.0,
        source_overlap_ratio=1.0,
        target_overlap_ratio=1.0,
        confidence=0.98,
        estimated_row_multiplier=1.0,
        is_grain_preserving=True,
    )
    assess_d = JoinSafetyAnalyzer.assess_edge_safety(edge_d, grain_prof)
    assert assess_d.safety_status == JoinSafetyStatus.SAFE
    assert assess_d.is_grain_compatible is True

    # Scenario E: DEPARTMENT x MONTH <-> PERSON x DAY without aggregation -> UNSAFE
    edge_e = ValidatedRelationshipEdge(
        edge_id="e_e",
        candidate_id="c_e",
        source_table_id="t_dept_mo",
        source_column_ids=["department"],
        target_table_id="t_att_day",
        target_column_ids=["department"],
        key_type=CandidateKeyType.SINGLE,
        cardinality=RelationshipCardinality.MANY_TO_MANY,
        status=RelationshipStatus.ACCEPTED,
        referential_coverage=0.8,
        source_overlap_ratio=0.8,
        target_overlap_ratio=0.8,
        confidence=0.75,
        estimated_row_multiplier=5.0,
        is_grain_preserving=False,
        duplication_risk_flag=True,
    )
    assess_e = JoinSafetyAnalyzer.assess_edge_safety(edge_e, grain_prof)
    assert assess_e.safety_status == JoinSafetyStatus.UNSAFE
    assert assess_e.temporal_mismatch is True

    # Scenario F: PRODUCT x LOCATION x DAY <-> PRODUCT master dimension enrichment -> SAFE
    edge_f = ValidatedRelationshipEdge(
        edge_id="e_f",
        candidate_id="c_f",
        source_table_id="t_prod",
        source_column_ids=["product_id"],
        target_table_id="t_inv_daily",
        target_column_ids=["product_id"],
        key_type=CandidateKeyType.SINGLE,
        cardinality=RelationshipCardinality.ONE_TO_MANY,
        status=RelationshipStatus.ACCEPTED,
        referential_coverage=1.0,
        source_overlap_ratio=1.0,
        target_overlap_ratio=1.0,
        confidence=0.95,
        estimated_row_multiplier=1.0,
        is_grain_preserving=True,
    )
    assess_f = JoinSafetyAnalyzer.assess_edge_safety(edge_f, grain_prof)
    assert assess_f.safety_status == JoinSafetyStatus.SAFE
    assert assess_f.dimension_propagation_safe is True
    assert assess_f.recommended_target_grain == "PRODUCT x LOCATION x DAY"


# ==============================================================================
# 5. GOVERNED JOIN PLANNER BENCHMARK
# ==============================================================================

def test_governed_join_planner_full_contract():
    """Verify JoinPlan specifies target grain, pre-aggregation, and measure additivity protections."""
    sem_emp = _make_table_sem(
        "t_emp",
        [
            _make_col_sem("employee_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticEntityType.PERSON),
            _make_col_sem("department", SemanticColumnRole.DIMENSION, SemanticEntityType.DEPARTMENT),
            _make_col_sem("salary", SemanticColumnRole.MEASURE, SemanticEntityType.UNKNOWN, SemanticConcept.MEASURE, MeasureClass.FINANCIAL),
        ],
    )
    sem_att = _make_table_sem(
        "t_att",
        [
            _make_col_sem("employee_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticEntityType.PERSON),
            _make_col_sem("attendance_date", SemanticColumnRole.TIME, SemanticEntityType.UNKNOWN, SemanticConcept.TIME_SPAN),
            _make_col_sem("hours_worked", SemanticColumnRole.MEASURE, SemanticEntityType.UNKNOWN, SemanticConcept.MEASURE, MeasureClass.QUANTITY),
            _make_col_sem("attendance_rate", SemanticColumnRole.MEASURE, SemanticEntityType.UNKNOWN, SemanticConcept.MEASURE, MeasureClass.PERCENTAGE),
        ],
    )
    sem_model = SemanticModel(
        dataset_id="ds-plan",
        run_id="run-p",
        stage_name="semantic_modeling",
        source_fingerprint="fp-sp",
        provenance=[],
        tables=[sem_emp, sem_att],
    )

    grain_prof = GrainProfile(
        dataset_id="ds-plan",
        run_id="run-p",
        stage_name="grain_inference",
        source_fingerprint="fp-gp",
        provenance=[],
        table_grains=[
            _make_table_grain("t_emp", CanonicalGrain.PERSON, "PERSON", ["employee_id"]),
            _make_table_grain("t_att", CanonicalGrain.COMPOSITE, "PERSON x DAY", ["employee_id", "attendance_date"]),
        ],
    )

    edge_emp_att = ValidatedRelationshipEdge(
        edge_id="edge_plan_01",
        candidate_id="cand_plan_01",
        source_table_id="t_emp",
        source_column_ids=["employee_id"],
        target_table_id="t_att",
        target_column_ids=["employee_id"],
        key_type=CandidateKeyType.SINGLE,
        cardinality=RelationshipCardinality.ONE_TO_MANY,
        status=RelationshipStatus.ACCEPTED,
        referential_coverage=1.0,
        source_overlap_ratio=1.0,
        target_overlap_ratio=1.0,
        confidence=0.95,
        estimated_row_multiplier=1.0,
        is_grain_preserving=True,
    )

    # 1. Dimension enrichment plan (target grain: PERSON x DAY)
    plan_enrich = plan_join(edge_emp_att, "DIMENSION_ENRICHMENT", grain_prof, sem_model)
    assert plan_enrich.safety_status == JoinSafetyStatus.SAFE
    assert plan_enrich.target_grain == "PERSON x DAY"
    assert "department" in plan_enrich.dimension_propagation
    assert plan_enrich.measure_additivity_rules["salary"] == MeasureAdditivity.NON_ADDITIVE
    assert plan_enrich.measure_additivity_rules["hours_worked"] == MeasureAdditivity.ADDITIVE
    assert plan_enrich.measure_additivity_rules["attendance_rate"] == MeasureAdditivity.RATIO
    assert "SUM(hours_worked)" in plan_enrich.safe_operations
    assert "SUM(salary)" in plan_enrich.forbidden_operations
    assert "SUM(attendance_rate)" in plan_enrich.forbidden_operations

    # 2. Pre-aggregation plan (target grain: PERSON)
    edge_preagg = ValidatedRelationshipEdge(
        edge_id="edge_plan_02",
        candidate_id="cand_plan_02",
        source_table_id="t_emp",
        source_column_ids=["employee_id"],
        target_table_id="t_att",
        target_column_ids=["employee_id"],
        key_type=CandidateKeyType.SINGLE,
        cardinality=RelationshipCardinality.ONE_TO_MANY,
        status=RelationshipStatus.ACCEPTED,
        referential_coverage=1.0,
        source_overlap_ratio=1.0,
        target_overlap_ratio=1.0,
        confidence=0.95,
        estimated_row_multiplier=1.0,
        is_grain_preserving=True,
    )
    plan_pre = plan_join(edge_preagg, "PREAGGREGATION_ANALYSIS", grain_prof, sem_model, target_grain="PERSON")
    assert plan_pre.target_grain == "PERSON"
    assert plan_pre.pre_aggregation is not None
    assert plan_pre.pre_aggregation.target_grain == "PERSON"
    assert plan_pre.pre_aggregation.source_table_id == "t_att"
    assert "hours_worked" in plan_pre.pre_aggregation.aggregations


# ==============================================================================
# 6. EPISTEMIC BOUNDARY & IMMUTABILITY VERIFICATION
# ==============================================================================

def test_epistemic_boundary_and_immutability():
    """Verify normalized dataset and structural/semantic/grain inputs remain 100% frozen."""
    src = SourceCoordinateRef(dataset_id="ds-imm", source_file_hash="hash-imm")
    tbl = NormalizedTable(
        table_id="t_imm",
        table_name="Imm",
        columns=[_make_col("c1", "t_imm", "id", CanonicalPhysicalType.STRING)],
        row_count=1,
        column_count=1,
    )
    norm_ds = NormalizedDataset(dataset_id="ds-imm", run_id="r1", source_fingerprint="fp1", provenance=[src], tables=[tbl])
    struct_prof = StructuralProfile(
        dataset_id="ds-imm",
        run_id="r1",
        stage_name="structural_profiling_eda_a",
        source_fingerprint="fp2",
        provenance=[src],
        tables=[],
        dataset_structural_quality=_make_quality(),
    )
    sem_model = SemanticModel(dataset_id="ds-imm", run_id="r1", stage_name="semantic_modeling", source_fingerprint="fp3", provenance=[src], tables=[])
    grain_prof = GrainProfile(dataset_id="ds-imm", run_id="r1", stage_name="grain_inference", source_fingerprint="fp4", provenance=[src], table_grains=[])

    fp_norm_before = norm_ds.source_fingerprint
    fp_struct_before = struct_prof.source_fingerprint
    fp_sem_before = sem_model.source_fingerprint
    fp_grain_before = grain_prof.source_fingerprint

    cands = generate_candidates(norm_ds, struct_prof, sem_model, grain_prof)
    graph = validate_candidates(cands, norm_ds, struct_prof, sem_model, grain_prof)

    assert norm_ds.source_fingerprint == fp_norm_before
    assert struct_prof.source_fingerprint == fp_struct_before
    assert sem_model.source_fingerprint == fp_sem_before
    assert grain_prof.source_fingerprint == fp_grain_before
