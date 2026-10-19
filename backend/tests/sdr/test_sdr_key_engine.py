"""
HighView Semantic Data Refinery — Phase SDR-3
Tests: Key Intelligence Engine, Candidate Key Discovery, Minimality, and FD Discovery
"""

import hashlib
import json
from pathlib import Path
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
from app.services.ingestion_v2.retrieval.namespaces import (
    AuthorityClass,
    RetrievalNamespace,
)
from app.services.sdr.contracts.grain import (
    GrainCandidate,
    GrainStatus,
    SDRGrainProfile,
)
from app.services.sdr.contracts.keys import (
    KeyAuthority,
    KeyCandidateStatus,
    KeyCandidateType,
    ObservedFunctionalDependency,
    SDRKeyCandidate,
)
from app.services.sdr.contracts.policies import KeyConfidencePolicy, SDRPolicySuite
from app.services.sdr.contracts.profiles import (
    DeterministicColumnFeatures,
    PrivacyClassification,
    ProfilingAmbiguityState,
    SemanticColumnProfile,
    SemanticDtype,
)
from app.services.sdr.keys.candidate_evaluator import SDRKeyCandidateEvaluator
from app.services.sdr.keys.fd_engine import SDRFunctionalDependencyEngine
from app.services.sdr.keys.key_engine import SDRKeyIntelligenceEngine
from app.services.sdr.retrieval.retrieval_adapter import SDRRetrievalAdapter


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
    sample_values: list | None = None,
) -> SemanticColumnProfile:
    dc = row_count if distinct_count is None else min(distinct_count, row_count)
    features = DeterministicColumnFeatures(
        row_count=row_count,
        null_count=int(row_count * null_ratio),
        null_ratio=null_ratio,
        distinct_count=dc,
        distinct_ratio=dc / float(row_count) if row_count > 0 else 0.0,
        sample_values=sample_values or [f"val_{i}" for i in range(min(5, dc))],
    )
    return SemanticColumnProfile(
        dataset_id="ds_test",
        sheet_id="sheet1",
        column_id=column_id,
        source_name=source_name,
        canonical_name=source_name.lower(),
        physical_dtype="VARCHAR",
        semantic_dtype=dtype,
        semantic_role=role,
        semantic_concept=concept,
        measure_class=measure_class,
        entity_type_hypothesis=entity_hypothesis,
        privacy_classification=PrivacyClassification.PUBLIC,
        confidence=0.95,
        ambiguity_state=ProfilingAmbiguityState.CLEAR,
        features=features,
        source_lineage=SourceCoordinateRef(dataset_id="ds_test", sheet_id="sheet1", column_ids=[column_id], source_file_hash="dummy_hash"),
        profile_id=f"prof_{column_id}",
        artifact_fingerprint=f"fp_{column_id}",
    )


def test_atomic_clean_key_candidate():
    """Clean atomic identifier with 100% uniqueness and 0 nulls yields HIGH_CONFIDENCE_CANDIDATE_KEY."""
    emp_id = _make_profile(
        "col_emp_id",
        "employee_id",
        SemanticColumnRole.IDENTIFIER,
        SemanticDtype.ID,
        entity_hypothesis=SemanticEntityType.PERSON,
        row_count=5,
        distinct_count=5,
        null_ratio=0.0,
    )
    name = _make_profile(
        "col_name",
        "employee_name",
        SemanticColumnRole.ATTRIBUTE,
        SemanticDtype.TEXT,
        row_count=5,
        distinct_count=5,
    )
    rows = [
        {"employee_id": "E101", "employee_name": "Alice"},
        {"employee_id": "E102", "employee_name": "Bob"},
        {"employee_id": "E103", "employee_name": "Charlie"},
        {"employee_id": "E104", "employee_name": "David"},
        {"employee_id": "E105", "employee_name": "Eve"},
    ]

    engine = SDRKeyIntelligenceEngine()
    result = engine.analyze_keys(
        dataset_id="ds_test",
        sheet_id="sheet1",
        profiles=[emp_id, name],
        rows=rows,
    )

    candidates = result["candidates"]
    emp_candidates = [c for c in candidates if set(c.column_names) == {"employee_id"}]
    assert len(emp_candidates) == 1
    cand = emp_candidates[0]
    assert cand.key_type == KeyCandidateType.ATOMIC_NATURAL_KEY
    assert cand.status == KeyCandidateStatus.HIGH_CONFIDENCE_CANDIDATE_KEY
    assert cand.uniqueness_ratio == 1.0
    assert cand.null_ratio == 0.0
    assert cand.is_minimal is True
    # Epistemic law: Statistical uniqueness alone NEVER yields PRIMARY_KEY_CONFIRMED
    assert cand.status != KeyCandidateStatus.PRIMARY_KEY_CONFIRMED
    assert cand.authority == KeyAuthority.STATISTICALLY_INFERRED


def test_source_declared_primary_key():
    """Source-declared PK receives PRIMARY_KEY_CONFIRMED status with SOURCE_DECLARED authority."""
    emp_id = _make_profile(
        "col_emp_id",
        "employee_id",
        SemanticColumnRole.IDENTIFIER,
        SemanticDtype.ID,
        row_count=3,
        distinct_count=3,
    )
    rows = [
        {"employee_id": "E1"},
        {"employee_id": "E2"},
        {"employee_id": "E3"},
    ]

    engine = SDRKeyIntelligenceEngine()
    result = engine.analyze_keys(
        dataset_id="ds_test",
        sheet_id="sheet1",
        profiles=[emp_id],
        rows=rows,
        source_declared_pk=("employee_id",),
    )

    candidates = result["candidates"]
    cand = candidates[0]
    assert cand.authority == KeyAuthority.SOURCE_DECLARED
    assert cand.status == KeyCandidateStatus.PRIMARY_KEY_CONFIRMED


def test_candidate_minimality_enforcement():
    """A composite candidate whose proper subset is already unique is non-minimal and demoted."""
    emp_id = _make_profile(
        "col_emp_id",
        "employee_id",
        SemanticColumnRole.IDENTIFIER,
        SemanticDtype.ID,
        row_count=3,
        distinct_count=3,
    )
    dept = _make_profile(
        "col_dept",
        "department",
        SemanticColumnRole.ATTRIBUTE,
        SemanticDtype.CATEGORICAL,
        row_count=3,
        distinct_count=2,
    )
    rows = [
        {"employee_id": "E1", "department": "Eng"},
        {"employee_id": "E2", "department": "Sales"},
        {"employee_id": "E3", "department": "Eng"},
    ]

    evaluator = SDRKeyCandidateEvaluator(policy=KeyConfidencePolicy(max_composite_width=2))
    candidates = evaluator.evaluate_key_candidates(
        dataset_id="ds_test",
        sheet_id="sheet1",
        profiles=[emp_id, dept],
        rows=rows,
    )

    # emp_id is minimal
    emp_cand = next(c for c in candidates if set(c.column_names) == {"employee_id"})
    assert emp_cand.is_minimal is True
    assert emp_cand.status == KeyCandidateStatus.HIGH_CONFIDENCE_CANDIDATE_KEY

    # composite (department, employee_id) has proper subset employee_id that is unique
    composite_cands = [c for c in candidates if set(c.column_names) == {"department", "employee_id"}]
    assert len(composite_cands) == 1
    comp = composite_cands[0]
    assert comp.is_minimal is False
    assert comp.status == KeyCandidateStatus.REJECTED
    assert "proper subset" in comp.quality_notes.lower()


def test_strict_negative_gate_measures():
    """Continuous measures (salary, revenue, temperature) NEVER become candidate keys."""
    salary = _make_profile(
        "col_sal",
        "salary",
        SemanticColumnRole.MEASURE,
        SemanticDtype.DECIMAL,
        concept=SemanticConcept.MEASURE,
        measure_class=MeasureClass.FINANCIAL,
        row_count=5,
        distinct_count=5,  # 100% unique values!
    )
    rows = [
        {"salary": 100000.0},
        {"salary": 105000.0},
        {"salary": 110000.0},
        {"salary": 115000.0},
        {"salary": 120000.0},
    ]

    engine = SDRKeyIntelligenceEngine()
    result = engine.analyze_keys(
        dataset_id="ds_test",
        sheet_id="sheet1",
        profiles=[salary],
        rows=rows,
    )
    candidates = result["candidates"]
    # salary should not be accepted as candidate key
    valid_cands = [c for c in candidates if c.status in (
        KeyCandidateStatus.HIGH_CONFIDENCE_CANDIDATE_KEY,
        KeyCandidateStatus.PLAUSIBLE_CANDIDATE_KEY,
    )]
    assert len(valid_cands) == 0


def test_strict_negative_gate_free_text():
    """Long free text / notes columns NEVER become candidate keys despite uniqueness."""
    notes = _make_profile(
        "col_notes",
        "performance_notes",
        SemanticColumnRole.ATTRIBUTE,
        SemanticDtype.TEXT,
        concept=SemanticConcept.FREE_TEXT,
        row_count=3,
        distinct_count=3,
    )
    rows = [
        {"performance_notes": "Exceeded all quarterly performance metrics."},
        {"performance_notes": "Demonstrated exceptional engineering craftsmanship."},
        {"performance_notes": "Solid team leadership across sprint deliverables."},
    ]

    engine = SDRKeyIntelligenceEngine()
    result = engine.analyze_keys(
        dataset_id="ds_test",
        sheet_id="sheet1",
        profiles=[notes],
        rows=rows,
    )
    candidates = result["candidates"]
    valid_cands = [c for c in candidates if c.status in (
        KeyCandidateStatus.HIGH_CONFIDENCE_CANDIDATE_KEY,
        KeyCandidateStatus.PLAUSIBLE_CANDIDATE_KEY,
    )]
    assert len(valid_cands) == 0


def test_system_row_id_isolation():
    """Technical row identifiers (row_number, __row_id) are tagged SYSTEM_ROW_ID and not business keys."""
    row_num = _make_profile(
        "col_rownum",
        "row_number",
        SemanticColumnRole.IDENTIFIER,
        SemanticDtype.INTEGER,
        row_count=5,
        distinct_count=5,
    )
    rows = [{"row_number": i} for i in range(1, 6)]

    engine = SDRKeyIntelligenceEngine()
    result = engine.analyze_keys(
        dataset_id="ds_test",
        sheet_id="sheet1",
        profiles=[row_num],
        rows=rows,
    )
    candidates = result["candidates"]
    cand = next(c for c in candidates if set(c.column_names) == {"row_number"})
    assert cand.key_type == KeyCandidateType.SYSTEM_ROW_ID
    assert cand.status == KeyCandidateStatus.REJECTED


def test_composite_key_discovery_for_multigrain_table():
    """Snapshot table (emp_id + month) where neither column is individually unique yields composite candidate."""
    emp_id = _make_profile(
        "col_emp_id",
        "employee_id",
        SemanticColumnRole.IDENTIFIER,
        SemanticDtype.ID,
        row_count=4,
        distinct_count=2,  # 2 distinct employees
    )
    month = _make_profile(
        "col_month",
        "snapshot_month",
        SemanticColumnRole.DIMENSION,
        SemanticDtype.DATE,
        concept=SemanticConcept.TIME_SPAN,
        row_count=4,
        distinct_count=2,  # 2 distinct months
    )
    hours = _make_profile(
        "col_hours",
        "hours_worked",
        SemanticColumnRole.MEASURE,
        SemanticDtype.DECIMAL,
        measure_class=MeasureClass.QUANTITY,
        row_count=4,
        distinct_count=4,
    )
    rows = [
        {"employee_id": "E1", "snapshot_month": "2026-01", "hours_worked": 160},
        {"employee_id": "E1", "snapshot_month": "2026-02", "hours_worked": 150},
        {"employee_id": "E2", "snapshot_month": "2026-01", "hours_worked": 165},
        {"employee_id": "E2", "snapshot_month": "2026-02", "hours_worked": 170},
    ]

    grain_profile = SDRGrainProfile(
        dataset_id="ds_test",
        sheet_id="sheet1",
        primary_entity=CanonicalGrain.PERSON,
        temporal_grain=TemporalGrain.MONTHLY,
        resolved_grain_expression="EMPLOYEE × MONTH",
        grain_status=GrainStatus.CONFIRMED,
        grain_confidence=0.98,
        is_unique=True,
        rationale="Monthly employee attendance",
        profile_id="grain_test",
        artifact_fingerprint="fp_grain",
    )

    engine = SDRKeyIntelligenceEngine()
    result = engine.analyze_keys(
        dataset_id="ds_test",
        sheet_id="sheet1",
        profiles=[emp_id, month, hours],
        rows=rows,
        grain_profile=grain_profile,
    )

    candidates = result["candidates"]
    composite_cands = [
        c for c in candidates
        if set(c.column_names) == {"employee_id", "snapshot_month"}
        and c.status == KeyCandidateStatus.HIGH_CONFIDENCE_CANDIDATE_KEY
    ]
    assert len(composite_cands) == 1
    cand = composite_cands[0]
    assert cand.key_type == KeyCandidateType.COMPOSITE_NATURAL_KEY
    assert cand.composite_width == 2
    assert cand.uniqueness_ratio == 1.0
    assert cand.is_minimal is True


def test_event_table_no_natural_key_abstention():
    """Event table with no natural business key safely abstains without guessing."""
    ts = _make_profile(
        "col_ts",
        "event_timestamp",
        SemanticColumnRole.DIMENSION,
        SemanticDtype.TIMESTAMP,
        concept=SemanticConcept.TIME_SPAN,
        row_count=4,
        distinct_count=4,
    )
    event_type = _make_profile(
        "col_ev",
        "event_type",
        SemanticColumnRole.DIMENSION,
        SemanticDtype.CATEGORICAL,
        row_count=4,
        distinct_count=2,
    )
    metric = _make_profile(
        "col_val",
        "duration_ms",
        SemanticColumnRole.MEASURE,
        SemanticDtype.DECIMAL,
        measure_class=MeasureClass.QUANTITY,
        row_count=4,
        distinct_count=4,
    )
    rows = [
        {"event_timestamp": "2026-10-19T10:00:00", "event_type": "CLICK", "duration_ms": 12.0},
        {"event_timestamp": "2026-10-19T10:00:01", "event_type": "PAGE_VIEW", "duration_ms": 45.0},
        {"event_timestamp": "2026-10-19T10:00:02", "event_type": "CLICK", "duration_ms": 18.0},
        {"event_timestamp": "2026-10-19T10:00:03", "event_type": "LOGOUT", "duration_ms": 5.0},
    ]

    grain_profile = SDRGrainProfile(
        dataset_id="ds_test",
        sheet_id="events",
        primary_entity=CanonicalGrain.EVENT,
        temporal_grain=TemporalGrain.DATETIME_EVENT,
        resolved_grain_expression="EVENT_OCCURRENCE",
        grain_status=GrainStatus.CONFIRMED,
        grain_confidence=0.95,
        is_unique=True,
        rationale="Event log",
        profile_id="grain_events",
        artifact_fingerprint="fp_events",
    )

    engine = SDRKeyIntelligenceEngine()
    result = engine.analyze_keys(
        dataset_id="ds_test",
        sheet_id="events",
        profiles=[ts, event_type, metric],
        rows=rows,
        grain_profile=grain_profile,
    )

    candidates = result["candidates"]
    # Must NOT designate any high confidence natural primary key
    high_conf_natural_keys = [
        c for c in candidates
        if c.status == KeyCandidateStatus.HIGH_CONFIDENCE_CANDIDATE_KEY
        and c.key_type in (KeyCandidateType.ATOMIC_NATURAL_KEY, KeyCandidateType.COMPOSITE_NATURAL_KEY)
    ]
    assert len(high_conf_natural_keys) == 0


def test_dirty_duplicate_key_tracking():
    """Duplicate coordinates are captured and uniqueness_ratio demotes candidate."""
    emp_id = _make_profile(
        "col_emp_id",
        "employee_id",
        SemanticColumnRole.IDENTIFIER,
        SemanticDtype.ID,
        row_count=5,
        distinct_count=4,
    )
    rows = [
        {"employee_id": "E101"},
        {"employee_id": "E102"},
        {"employee_id": "E103"},
        {"employee_id": "E101"},  # duplicate
        {"employee_id": "E104"},
    ]

    evaluator = SDRKeyCandidateEvaluator()
    candidates = evaluator.evaluate_key_candidates(
        dataset_id="ds_test",
        sheet_id="sheet1",
        profiles=[emp_id],
        rows=rows,
    )

    cand = candidates[0]
    assert cand.uniqueness_ratio == 0.8
    assert cand.duplicate_count == 1
    assert "('E101',)" in cand.duplicate_coordinates
    assert cand.status == KeyCandidateStatus.NON_KEY


def test_ambiguous_competing_candidates():
    """When two candidates have equal uniqueness, both remain candidates; neither is arbitrarily confirmed."""
    nat_id = _make_profile(
        "col_nat",
        "national_id",
        SemanticColumnRole.IDENTIFIER,
        SemanticDtype.ID,
        row_count=3,
        distinct_count=3,
    )
    passport = _make_profile(
        "col_pass",
        "passport_number",
        SemanticColumnRole.IDENTIFIER,
        SemanticDtype.ID,
        row_count=3,
        distinct_count=3,
    )
    rows = [
        {"national_id": "N1", "passport_number": "P1"},
        {"national_id": "N2", "passport_number": "P2"},
        {"national_id": "N3", "passport_number": "P3"},
    ]

    engine = SDRKeyIntelligenceEngine()
    result = engine.analyze_keys(
        dataset_id="ds_test",
        sheet_id="sheet1",
        profiles=[nat_id, passport],
        rows=rows,
    )

    candidates = result["candidates"]
    nat_cands = [c for c in candidates if set(c.column_names) == {"national_id"}]
    pass_cands = [c for c in candidates if set(c.column_names) == {"passport_number"}]

    assert len(nat_cands) == 1
    assert len(pass_cands) == 1
    # Both are HIGH_CONFIDENCE_CANDIDATE_KEY, neither is PRIMARY_KEY_CONFIRMED
    assert nat_cands[0].status == KeyCandidateStatus.HIGH_CONFIDENCE_CANDIDATE_KEY
    assert pass_cands[0].status == KeyCandidateStatus.HIGH_CONFIDENCE_CANDIDATE_KEY
    assert nat_cands[0].status != KeyCandidateStatus.PRIMARY_KEY_CONFIRMED
    assert pass_cands[0].status != KeyCandidateStatus.PRIMARY_KEY_CONFIRMED


def test_functional_dependency_discovery():
    """Local functional dependencies (X -> Y) discovered with scope CURRENT_DATASET."""
    emp_id = _make_profile(
        "col_emp_id",
        "employee_id",
        SemanticColumnRole.IDENTIFIER,
        SemanticDtype.ID,
        row_count=4,
        distinct_count=2,
    )
    name = _make_profile(
        "col_name",
        "employee_name",
        SemanticColumnRole.ATTRIBUTE,
        SemanticDtype.TEXT,
        row_count=4,
        distinct_count=2,
    )
    dept = _make_profile(
        "col_dept",
        "department",
        SemanticColumnRole.ATTRIBUTE,
        SemanticDtype.CATEGORICAL,
        row_count=4,
        distinct_count=2,
    )
    rows = [
        {"employee_id": "E1", "employee_name": "Alice", "department": "Eng"},
        {"employee_id": "E1", "employee_name": "Alice", "department": "Eng"},
        {"employee_id": "E2", "employee_name": "Bob", "department": "Sales"},
        {"employee_id": "E2", "employee_name": "Bob", "department": "Sales"},
    ]

    fd_engine = SDRFunctionalDependencyEngine()
    candidate = SDRKeyCandidate(
        candidate_id="cand_emp",
        dataset_id="ds_test",
        sheet_id="sheet1",
        column_ids=["col_emp_id"],
        column_names=["employee_id"],
        candidate_type=KeyCandidateType.CANDIDATE_KEY,
        entity_type=SemanticEntityType.PERSON,
        grain_expression="EMPLOYEE",
        width=1,
        row_count=4,
        unique_combination_count=2,
        uniqueness_ratio=0.5,
        null_count=0,
        null_ratio=0.0,
        duplicate_combination_count=2,
        duplicate_row_count=2,
        semantic_support_score=0.9,
        grain_support_score=0.5,
        stability_score=1.0,
        minimality_score=1.0,
        is_minimal=True,
        key_confidence=0.90,
        authority=KeyAuthority.INFERRED,
        status=KeyCandidateStatus.CANDIDATE,
        evidence="Candidate employee_id",
        artifact_fingerprint="fp_emp",
    )

    dependencies = fd_engine.discover_functional_dependencies(
        dataset_id="ds_test",
        sheet_id="sheet1",
        profiles=[emp_id, name, dept],
        candidates=[candidate],
        rows=rows,
    )

    assert len(dependencies) >= 1
    emp_to_name = next(
        (fd for fd in dependencies if fd.determinant_columns == ("employee_id",) and fd.dependent_columns == ("employee_name",)),
        None,
    )
    assert emp_to_name is not None
    assert emp_to_name.confidence == 1.0
    assert emp_to_name.support == 1.0
    assert emp_to_name.exception_count == 0
    assert emp_to_name.scope == "CURRENT_DATASET"


def test_retrieval_namespace_strictness():
    """Key candidate and FD retrieval documents emit exclusively to RAW_SCHEMA and SEMANTIC namespaces."""
    cand = SDRKeyCandidate(
        candidate_id="cand_test",
        dataset_id="ds_test",
        sheet_id="sheet1",
        column_ids=["col1"],
        column_names=["id_col"],
        candidate_type=KeyCandidateType.HIGH_CONFIDENCE_CANDIDATE_KEY,
        entity_type=SemanticEntityType.UNKNOWN,
        grain_expression="ID_COL",
        width=1,
        row_count=10,
        unique_combination_count=10,
        uniqueness_ratio=1.0,
        null_count=0,
        null_ratio=0.0,
        duplicate_combination_count=0,
        duplicate_row_count=0,
        semantic_support_score=0.9,
        grain_support_score=1.0,
        stability_score=1.0,
        minimality_score=1.0,
        is_minimal=True,
        key_confidence=0.99,
        authority=KeyAuthority.INFERRED,
        status=KeyCandidateStatus.HIGH_CONFIDENCE,
        evidence="Dominant atomic candidate key",
        artifact_fingerprint="fp_cand",
    )
    fd = ObservedFunctionalDependency(
        fd_id="fd_test",
        dataset_id="ds_test",
        sheet_id="sheet1",
        determinant_column_ids=["col1"],
        determinant_column_names=["id_col"],
        dependent_column_ids=["col2"],
        dependent_column_names=["name_col"],
        support_ratio=1.0,
        violation_count=0,
        scope="CURRENT_DATASET",
        confidence=1.0,
        rationale="Local FD",
        artifact_fingerprint="fp_fd",
    )

    raw_doc = SDRRetrievalAdapter.build_raw_key_candidate_document(cand)
    sem_doc = SDRRetrievalAdapter.build_key_candidate_document(cand)
    fd_doc = SDRRetrievalAdapter.build_functional_dependency_document(fd)

    assert raw_doc.namespace == RetrievalNamespace.RAW_SCHEMA
    assert raw_doc.authority_class == AuthorityClass.STRUCTURAL

    assert sem_doc.namespace == RetrievalNamespace.SEMANTIC
    assert sem_doc.authority_class == AuthorityClass.SEMANTIC

    assert fd_doc.namespace == RetrievalNamespace.SEMANTIC
    assert fd_doc.authority_class == AuthorityClass.SEMANTIC

    # STRICT GOVERNANCE: Must NEVER emit to RELATIONSHIP or ANALYTICAL
    forbidden_namespaces = {RetrievalNamespace.RELATIONSHIP, RetrievalNamespace.ANALYTICAL}
    assert raw_doc.namespace not in forbidden_namespaces
    assert sem_doc.namespace not in forbidden_namespaces
    assert fd_doc.namespace not in forbidden_namespaces


def test_governance_contracts_unviolated():
    """Strict verification of zero PK authorization, zero FK validation, zero JoinPlans."""
    emp_id = _make_profile(
        "col_emp_id",
        "employee_id",
        SemanticColumnRole.IDENTIFIER,
        SemanticDtype.ID,
        row_count=3,
        distinct_count=3,
    )
    rows = [{"employee_id": "E1"}, {"employee_id": "E2"}, {"employee_id": "E3"}]

    engine = SDRKeyIntelligenceEngine()
    result = engine.analyze_keys(
        dataset_id="ds_test",
        sheet_id="sheet1",
        profiles=[emp_id],
        rows=rows,
    )

    candidates = result["candidates"]
    manifest = result["manifest"]

    # 1. Zero confirmed primary keys from statistical inference
    assert manifest["primary_keys_confirmed"] == 0

    # 2. Zero authorized foreign keys between sheets
    assert "foreign_keys_authorized" not in manifest or manifest.get("foreign_keys_authorized", 0) == 0

    # 3. Zero JoinPlans
    assert "join_plans" not in result
    assert "validated_relationships" not in result
