"""
HighView Semantic Data Refinery — Phase SDR-2
Tests: Governed Grain Discovery Engine & Strict Negative Gates
"""

import pytest

from app.services.ingestion_v2.contracts.grain import (
    CanonicalGrain,
    TemporalGrain,
)
from app.services.ingestion_v2.contracts.provenance import SourceCoordinateRef
from app.services.ingestion_v2.contracts.semantics import (
    MeasureClass,
    SemanticColumnRole,
    SemanticConcept,
    SemanticEntityType,
)
from app.services.sdr.contracts.grain import (
    GrainCandidate,
    GrainStatus,
    SDRGrainProfile,
)
from app.services.sdr.contracts.policies import GrainConfidencePolicy, SDRPolicySuite
from app.services.sdr.contracts.profiles import (
    DeterministicColumnFeatures,
    PrivacyClassification,
    ProfilingAmbiguityState,
    SemanticColumnProfile,
    SemanticDtype,
)
from app.services.sdr.grain.candidate_pruner import (
    is_measure_column,
    is_system_row_identifier,
    prune_grain_candidates,
)
from app.services.sdr.grain.grain_engine import SDRGrainDiscoveryEngine


def _make_profile(
    column_id: str,
    source_name: str,
    role: SemanticColumnRole,
    dtype: SemanticDtype,
    concept: SemanticConcept = SemanticConcept.DESCRIPTOR,
    entity_hypothesis: SemanticEntityType = SemanticEntityType.UNKNOWN,
    measure_class: MeasureClass | None = None,
    distinct_count: int | None = None,
    null_ratio: float = 0.0,
    row_count: int = 10,
) -> SemanticColumnProfile:
    dc = row_count if distinct_count is None else min(distinct_count, row_count)
    features = DeterministicColumnFeatures(
        row_count=row_count,
        null_count=int(row_count * null_ratio),
        null_ratio=null_ratio,
        distinct_count=dc,
        distinct_ratio=dc / float(row_count) if row_count > 0 else 0.0,
        sample_values=["v1", "v2"],
    )
    lineage = SourceCoordinateRef(
        dataset_id="ds_test",
        sheet_id="sheet1",
        column_ids=[column_id],
        source_file_hash="dummy_hash",
    )
    return SemanticColumnProfile(
        profile_id=f"prof_{column_id}",
        dataset_id="ds_test",
        sheet_id="sheet1",
        column_id=column_id,
        source_name=source_name,
        canonical_name=source_name.lower(),
        physical_dtype="string",
        semantic_dtype=dtype,
        semantic_role=role,
        semantic_concept=concept,
        entity_type_hypothesis=entity_hypothesis,
        measure_class=measure_class,
        confidence=0.90,
        ambiguity_state=ProfilingAmbiguityState.CLEAR,
        privacy_classification=PrivacyClassification.GENERAL_ATTRIBUTE,
        features=features,
        source_lineage=lineage,
        artifact_fingerprint=f"fp_{column_id}",
    )


def test_single_entity_grain_discovery():
    """Verify single-column natural business grain (e.g. employee master)."""
    p_id = _make_profile("c1", "employee_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticDtype.IDENTIFIER_CODE, SemanticConcept.IDENTIFIER, SemanticEntityType.PERSON, distinct_count=5, row_count=5)
    p_name = _make_profile("c2", "full_name", SemanticColumnRole.ENTITY_LABEL, SemanticDtype.NATURAL_LANGUAGE_TEXT, SemanticConcept.DESCRIPTOR, SemanticEntityType.PERSON, distinct_count=5, row_count=5)
    p_dept = _make_profile("c3", "department", SemanticColumnRole.DIMENSION, SemanticDtype.CATEGORICAL_CODE, SemanticConcept.DESCRIPTOR, SemanticEntityType.DEPARTMENT, distinct_count=2, row_count=5)

    data = {
        "c1": ["E101", "E102", "E103", "E104", "E105"],
        "c2": ["Alice", "Bob", "Charlie", "David", "Eve"],
        "c3": ["HR", "Eng", "Eng", "Sales", "HR"],
    }

    engine = SDRGrainDiscoveryEngine()
    profile = engine.discover_grain("ds_test", "sheet_emp", [p_id, p_name, p_dept], data, 5)

    assert profile.grain_status == GrainStatus.RESOLVED
    assert profile.primary_entity == CanonicalGrain.PERSON
    assert profile.temporal_grain == TemporalGrain.NONE
    assert profile.best_candidate is not None
    assert profile.best_candidate.determinant_column_ids == ["c1"]
    assert profile.best_candidate.width == 1
    assert profile.best_candidate.uniqueness_ratio == 1.0
    assert profile.is_unique is True


def test_snapshot_composite_grain_discovery():
    """Verify 2-column composite snapshot grain (e.g. Employee x Month)."""
    # 6 rows: 3 employees x 2 months
    p_id = _make_profile("c_id", "emp_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticDtype.IDENTIFIER_CODE, SemanticConcept.IDENTIFIER, SemanticEntityType.PERSON, distinct_count=3, row_count=6)
    p_month = _make_profile("c_mo", "reporting_month", SemanticColumnRole.TIME, SemanticDtype.DATE, SemanticConcept.TIME_SPAN, SemanticEntityType.UNKNOWN, distinct_count=2, row_count=6)
    p_status = _make_profile("c_st", "status", SemanticColumnRole.STATUS, SemanticDtype.CATEGORICAL_CODE, SemanticConcept.STATUS, SemanticEntityType.UNKNOWN, distinct_count=2, row_count=6)

    data = {
        "c_id": ["E1", "E2", "E3", "E1", "E2", "E3"],
        "c_mo": ["2026-01", "2026-01", "2026-01", "2026-02", "2026-02", "2026-02"],
        "c_st": ["Active", "Active", "Active", "Active", "Leave", "Active"],
    }

    engine = SDRGrainDiscoveryEngine()
    profile = engine.discover_grain("ds_test", "sheet_snap", [p_id, p_month, p_status], data, 6)

    assert profile.grain_status == GrainStatus.RESOLVED
    assert profile.primary_entity == CanonicalGrain.PERSON
    assert profile.temporal_grain == TemporalGrain.MONTH
    assert profile.best_candidate is not None
    assert set(profile.best_candidate.determinant_column_ids) == {"c_id", "c_mo"}
    assert profile.best_candidate.width == 2
    assert profile.best_candidate.uniqueness_ratio == 1.0
    assert "MONTH" in profile.resolved_grain_expression


def test_three_column_composite_grain_discovery():
    """Verify 3-column composite grain (e.g. Store x SKU x Day)."""
    # 4 rows: Store x SKU x Day, where no 2-column pair is unique
    p_store = _make_profile("c_st", "store_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticDtype.IDENTIFIER_CODE, SemanticConcept.IDENTIFIER, SemanticEntityType.STORE, distinct_count=2, row_count=4)
    p_sku = _make_profile("c_sku", "sku_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticDtype.IDENTIFIER_CODE, SemanticConcept.IDENTIFIER, SemanticEntityType.PRODUCT, distinct_count=2, row_count=4)
    p_date = _make_profile("c_dt", "transaction_date", SemanticColumnRole.TIME, SemanticDtype.DATE, SemanticConcept.TIME_SPAN, SemanticEntityType.UNKNOWN, distinct_count=2, row_count=4)

    # (S1, P1) sold on Day 1 AND Day 2 -> (store, sku) is NOT unique
    # (S1, Day 1) has P1 and P2 -> (store, date) is NOT unique
    # (P1, Day 1) has S1 and S2 -> (sku, date) is NOT unique
    data = {
        "c_st": ["S1", "S1", "S1", "S2"],
        "c_sku": ["P1", "P1", "P2", "P1"],
        "c_dt": ["2026-01-01", "2026-01-02", "2026-01-01", "2026-01-01"],
    }

    engine = SDRGrainDiscoveryEngine()
    profile = engine.discover_grain("ds_test", "sheet_retail", [p_store, p_sku, p_date], data, 4)

    assert profile.grain_status == GrainStatus.RESOLVED
    assert profile.best_candidate is not None
    assert profile.best_candidate.width == 3
    assert profile.best_candidate.uniqueness_ratio == 1.0
    assert set(profile.best_candidate.determinant_column_ids) == {"c_st", "c_sku", "c_dt"}


def test_critical_negative_unique_salary_never_promoted():
    """
    CRITICAL NEGATIVE GATE:
    A salary column with 100% unique float values must NEVER become grain or part of grain candidates.
    Uniqueness is evidence, not meaning.
    """
    p_id = _make_profile("c_id", "emp_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticDtype.IDENTIFIER_CODE, SemanticConcept.IDENTIFIER, SemanticEntityType.PERSON, distinct_count=5, row_count=5)
    # Salary has 100% unique floats!
    p_sal = _make_profile("c_sal", "annual_salary", SemanticColumnRole.MEASURE, SemanticDtype.CURRENCY_AMOUNT, SemanticConcept.MEASURE, SemanticEntityType.UNKNOWN, measure_class=MeasureClass.FINANCIAL, distinct_count=5, row_count=5)

    assert is_measure_column(p_sal) is True

    policy = GrainConfidencePolicy()
    eligible = prune_grain_candidates([p_id, p_sal], policy)
    assert p_sal not in eligible
    assert eligible == [p_id]

    data = {
        "c_id": ["E1", "E2", "E3", "E4", "E5"],
        "c_sal": [75000.12, 82500.45, 93000.80, 110000.00, 125000.50],
    }

    engine = SDRGrainDiscoveryEngine()
    profile = engine.discover_grain("ds_test", "sheet_sal", [p_id, p_sal], data, 5)

    assert profile.best_candidate is not None
    assert "c_sal" not in profile.best_candidate.determinant_column_ids
    for cand in profile.ranked_candidates:
        assert "c_sal" not in cand.determinant_column_ids


def test_critical_negative_unique_revenue_never_promoted():
    """Verify continuous revenue measure is unconditionally excluded from grain."""
    p_rev = _make_profile("c_rev", "total_revenue", SemanticColumnRole.MEASURE, SemanticDtype.CURRENCY_AMOUNT, SemanticConcept.MEASURE, measure_class=MeasureClass.FINANCIAL, distinct_count=10, row_count=10)
    assert is_measure_column(p_rev) is True

    policy = GrainConfidencePolicy()
    eligible = prune_grain_candidates([p_rev], policy)
    assert len(eligible) == 0


def test_critical_negative_row_number_never_promoted():
    """
    CRITICAL NEGATIVE GATE:
    System sequence numbers or row IDs (row_number, seq, idx) must NEVER define business grain.
    """
    p_seq = _make_profile("c_seq", "row_number", SemanticColumnRole.DIMENSION, SemanticDtype.INTEGER_NUMBER, SemanticConcept.TECHNICAL, distinct_count=10, row_count=10)
    p_id = _make_profile("c_id", "emp_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticDtype.IDENTIFIER_CODE, SemanticConcept.IDENTIFIER, SemanticEntityType.PERSON, distinct_count=10, row_count=10)

    assert is_system_row_identifier(p_seq) is True

    policy = GrainConfidencePolicy()
    eligible = prune_grain_candidates([p_seq, p_id], policy)
    assert p_seq not in eligible
    assert eligible == [p_id]


def test_duplicate_keys_preserve_entity_hypothesis_while_reporting_grain_duplicates():
    """
    CRITICAL EPISTEMIC LAW:
    EntityConfidence != GrainConfidence != KeyConfidence.
    When employee_id has duplicate rows, the entity hypothesis remains EMPLOYEE,
    while grain profile detects duplicate rows and records ambiguity/duplicates.
    """
    p_id = _make_profile("c_id", "employee_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticDtype.IDENTIFIER_CODE, SemanticConcept.IDENTIFIER, SemanticEntityType.PERSON, distinct_count=4, row_count=6)
    p_name = _make_profile("c_name", "employee_name", SemanticColumnRole.ENTITY_LABEL, SemanticDtype.NATURAL_LANGUAGE_TEXT, SemanticConcept.DESCRIPTOR, SemanticEntityType.PERSON, distinct_count=4, row_count=6)

    # 6 rows, but E1 and E2 repeat without a time column!
    data = {
        "c_id": ["E1", "E1", "E2", "E2", "E3", "E4"],
        "c_name": ["Alice", "Alice", "Bob", "Bob", "Charlie", "David"],
    }

    engine = SDRGrainDiscoveryEngine()
    profile = engine.discover_grain("ds_test", "sheet_dirty_keys", [p_id, p_name], data, 6)

    # Grain confidence reflects duplicate rows
    assert profile.is_unique is False
    assert profile.best_candidate is not None
    assert profile.best_candidate.duplicate_row_count > 0
    assert profile.best_candidate.uniqueness_ratio < 1.0
    # Entity grain remains PERSON
    assert profile.primary_entity == CanonicalGrain.PERSON


def test_ambiguity_gate_on_competing_candidates():
    """
    Verify ambiguity gate: when two distinct candidate combinations have virtually identical uniqueness,
    engine returns GrainStatus.AMBIGUOUS rather than guessing.
    """
    p_code_a = _make_profile("c_a", "alt_code_a", SemanticColumnRole.DIMENSION, SemanticDtype.IDENTIFIER_CODE, SemanticConcept.IDENTIFIER, distinct_count=4, row_count=5)
    p_code_b = _make_profile("c_b", "alt_code_b", SemanticColumnRole.DIMENSION, SemanticDtype.IDENTIFIER_CODE, SemanticConcept.IDENTIFIER, distinct_count=4, row_count=5)

    data = {
        "c_a": ["A1", "A2", "A3", "A4", "A4"],
        "c_b": ["B1", "B2", "B3", "B4", "B4"],
    }

    engine = SDRGrainDiscoveryEngine()
    profile = engine.discover_grain("ds_test", "sheet_ambig", [p_code_a, p_code_b], data, 5)

    assert profile.grain_status == GrainStatus.AMBIGUOUS
    assert len(profile.ranked_candidates) >= 2


def test_governance_zero_primary_or_foreign_keys_or_joinplans():
    """
    CRITICAL GOVERNANCE INVARIANT:
    SDR-2 MUST NOT authorize PRIMARY_KEY or FOREIGN_KEY, and MUST NOT emit JoinPlans.
    Those are deferred to SDR-3 and SDR-5.
    """
    p_id = _make_profile("c1", "employee_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticDtype.IDENTIFIER_CODE, SemanticConcept.IDENTIFIER, SemanticEntityType.PERSON, distinct_count=5, row_count=5)
    data = {"c1": ["E1", "E2", "E3", "E4", "E5"]}

    engine = SDRGrainDiscoveryEngine()
    profile = engine.discover_grain("ds_test", "sheet1", [p_id], data, 5)

    # Check contracts do not have PK/FK/JoinPlan attributes
    profile_dict = profile.model_dump()
    assert "primary_key" not in profile_dict
    assert "foreign_key" not in profile_dict
    assert "join_plan" not in profile_dict
    assert "join_authorization" not in profile_dict

    if profile.best_candidate:
        cand_dict = profile.best_candidate.model_dump()
        assert "is_primary_key" not in cand_dict
        assert "foreign_key" not in cand_dict


def test_width_cap_and_dual_temporal_pruning():
    """Verify that combinations of width > 3 are never formed and dual temporal columns are pruned."""
    policy = GrainConfidencePolicy(max_composite_width=3)
    p_t1 = _make_profile("t1", "event_date", SemanticColumnRole.TIME, SemanticDtype.DATE, SemanticConcept.TIME_SPAN, row_count=5)
    p_t2 = _make_profile("t2", "fiscal_month", SemanticColumnRole.TIME, SemanticDtype.DATE, SemanticConcept.TIME_SPAN, row_count=5)
    p_d1 = _make_profile("d1", "dim_1", SemanticColumnRole.DIMENSION, SemanticDtype.CATEGORICAL_CODE, row_count=5)
    p_d2 = _make_profile("d2", "dim_2", SemanticColumnRole.DIMENSION, SemanticDtype.CATEGORICAL_CODE, row_count=5)
    p_d3 = _make_profile("d3", "dim_3", SemanticColumnRole.DIMENSION, SemanticDtype.CATEGORICAL_CODE, row_count=5)

    from app.services.sdr.grain.composite_evaluator import SDRCompositeEvaluator
    evaluator = SDRCompositeEvaluator(policy)

    data = {
        "t1": ["2026-01-01"] * 5,
        "t2": ["2026-01"] * 5,
        "d1": ["A", "B", "C", "D", "E"],
        "d2": ["1", "2", "3", "4", "5"],
        "d3": ["X", "Y", "Z", "W", "V"],
    }

    candidates = evaluator.evaluate_combinations([p_t1, p_t2, p_d1, p_d2, p_d3], data, 5)

    # 1. No combination width > 3
    for cand in candidates:
        assert cand.width <= 3

    # 2. No combination contains both t1 and t2
    for cand in candidates:
        has_t1 = "t1" in cand.determinant_column_ids
        has_t2 = "t2" in cand.determinant_column_ids
        assert not (has_t1 and has_t2), f"Candidate {cand.candidate_id} contains dual temporal columns!"
