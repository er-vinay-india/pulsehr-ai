"""
HighView Semantic Data Refinery — Phase SDR-3
Certification Corpus Benchmark & Evaluation Suite
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
from app.services.ingestion_v2.retrieval.namespaces import RetrievalNamespace
from app.services.sdr.artifacts.artifact_writer import SDRArtifactWriter
from app.services.sdr.contracts.grain import (
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
from app.services.sdr.contracts.policies import SDRPolicySuite
from app.services.sdr.contracts.profiles import (
    DeterministicColumnFeatures,
    PrivacyClassification,
    ProfilingAmbiguityState,
    SemanticColumnProfile,
    SemanticDtype,
)
from app.services.sdr.keys.key_engine import SDRKeyIntelligenceEngine
from app.services.sdr.retrieval.retrieval_adapter import SDRRetrievalAdapter

P0_EXPECTED_SHA = "1561d64eeae26f4d30926371740d6ca9dc41eb6ea7c537281763b7d5aabd9496"
P0_EXPECTED_SIZE = 70385664


def _create_profile(
    dataset_id: str,
    sheet_id: str,
    column_id: str,
    source_name: str,
    role: SemanticColumnRole,
    dtype: SemanticDtype,
    concept: SemanticConcept,
    entity_type: SemanticEntityType = SemanticEntityType.UNKNOWN,
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
    return SemanticColumnProfile(
        dataset_id=dataset_id,
        sheet_id=sheet_id,
        column_id=column_id,
        source_name=source_name,
        canonical_name=source_name.lower(),
        physical_dtype="VARCHAR",
        semantic_dtype=dtype,
        semantic_role=role,
        semantic_concept=concept,
        measure_class=measure_class,
        entity_type_hypothesis=entity_type,
        privacy_classification=PrivacyClassification.PUBLIC,
        confidence=0.95,
        ambiguity_state=ProfilingAmbiguityState.CLEAR,
        features=features,
        source_lineage=SourceCoordinateRef(dataset_id=dataset_id, sheet_id=sheet_id, column_ids=[column_id], source_file_hash="dummy_hash"),
        profile_id=f"prof_{column_id}",
        artifact_fingerprint=f"fp_{column_id}",
    )


def test_p0_database_isolation_guard():
    """Verify primary application database is bit-identical to frozen baseline."""
    p0_path = Path("backend/data/db/pulsehr.sqlite3")
    if p0_path.exists():
        hasher = hashlib.sha256()
        with open(p0_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        assert hasher.hexdigest() == P0_EXPECTED_SHA
        assert p0_path.stat().st_size == P0_EXPECTED_SIZE


def test_corpus_hr_directory():
    """Target 1: HR Directory (Atomic Key, Excluded Measure & Free Text, Minimal Key)."""
    dataset_id = "ds_hr"
    sheet_id = "employees"
    row_count = 6

    emp_id = _create_profile(
        dataset_id, sheet_id, "col_emp", "employee_id",
        SemanticColumnRole.IDENTIFIER, SemanticDtype.ID, SemanticConcept.IDENTIFIER,
        row_count=row_count, distinct_count=row_count,
    )
    name = _create_profile(
        dataset_id, sheet_id, "col_name", "full_name",
        SemanticColumnRole.ATTRIBUTE, SemanticDtype.TEXT, SemanticConcept.DESCRIPTOR,
        row_count=row_count, distinct_count=row_count,
    )
    dept = _create_profile(
        dataset_id, sheet_id, "col_dept", "department",
        SemanticColumnRole.ATTRIBUTE, SemanticDtype.CATEGORICAL, SemanticConcept.CATEGORICAL,
        row_count=row_count, distinct_count=2,
    )
    salary = _create_profile(
        dataset_id, sheet_id, "col_sal", "annual_salary",
        SemanticColumnRole.MEASURE, SemanticDtype.DECIMAL, SemanticConcept.MEASURE,
        measure_class=MeasureClass.FINANCIAL, row_count=row_count, distinct_count=row_count,
    )
    notes = _create_profile(
        dataset_id, sheet_id, "col_notes", "hr_notes",
        SemanticColumnRole.ATTRIBUTE, SemanticDtype.TEXT, SemanticConcept.FREE_TEXT,
        row_count=row_count, distinct_count=row_count,
    )

    rows = [
        {"employee_id": f"E{i}", "full_name": f"Name {i}", "department": "Eng" if i % 2 == 0 else "Sales",
         "annual_salary": 100000.0 + i * 5000, "hr_notes": f"Note for employee {i}"}
        for i in range(1, row_count + 1)
    ]

    engine = SDRKeyIntelligenceEngine()
    result = engine.analyze_keys(
        dataset_id=dataset_id,
        sheet_id=sheet_id,
        profiles=[emp_id, name, dept, salary, notes],
        rows=rows,
    )

    candidates = result["candidates"]
    fds = result["functional_dependencies"]

    # 1. employee_id is high-confidence candidate key
    emp_cand = next(c for c in candidates if set(c.column_names) == {"employee_id"})
    assert emp_cand.status == KeyCandidateStatus.HIGH_CONFIDENCE_CANDIDATE_KEY
    assert emp_cand.is_minimal is True
    # Epistemic law: NEVER confirmed primary key without source declaration
    assert emp_cand.status != KeyCandidateStatus.PRIMARY_KEY_CONFIRMED

    # 2. Composite (employee_id, department) is rejected due to minimality violation
    comp_cand = next((c for c in candidates if set(c.column_names) == {"employee_id", "department"}), None)
    if comp_cand:
        assert comp_cand.is_minimal is False
        assert comp_cand.status == KeyCandidateStatus.REJECTED

    # 3. Measures and Free Text NEVER become valid candidate keys
    bad_cands = [
        c for c in candidates
        if any(col in ("annual_salary", "hr_notes") for col in c.column_names)
        and c.status in (KeyCandidateStatus.HIGH_CONFIDENCE_CANDIDATE_KEY, KeyCandidateStatus.PLAUSIBLE_CANDIDATE_KEY)
    ]
    assert len(bad_cands) == 0

    # 4. FD discovery: employee_id -> full_name, employee_id -> department
    emp_fds = [fd for fd in fds if fd.determinant_columns == ("employee_id",)]
    assert len(emp_fds) >= 1
    for fd in emp_fds:
        assert fd.scope == "CURRENT_DATASET"


def test_corpus_attendance_snapshot():
    """Target 2: Monthly Attendance Snapshot (Composite Key emp_id + snapshot_month)."""
    dataset_id = "ds_snap"
    sheet_id = "attendance"
    row_count = 4

    emp_id = _create_profile(
        dataset_id, sheet_id, "col_emp", "employee_id",
        SemanticColumnRole.IDENTIFIER, SemanticDtype.ID, SemanticConcept.IDENTIFIER,
        row_count=row_count, distinct_count=2,
    )
    month = _create_profile(
        dataset_id, sheet_id, "col_month", "snapshot_month",
        SemanticColumnRole.DIMENSION, SemanticDtype.DATE, SemanticConcept.TIME_SPAN,
        row_count=row_count, distinct_count=2,
    )
    hours = _create_profile(
        dataset_id, sheet_id, "col_hours", "hours_logged",
        SemanticColumnRole.MEASURE, SemanticDtype.DECIMAL, SemanticConcept.MEASURE,
        measure_class=MeasureClass.QUANTITY, row_count=row_count, distinct_count=4,
    )

    rows = [
        {"employee_id": "E1", "snapshot_month": "2026-01", "hours_logged": 160.0},
        {"employee_id": "E1", "snapshot_month": "2026-02", "hours_logged": 155.0},
        {"employee_id": "E2", "snapshot_month": "2026-01", "hours_logged": 168.0},
        {"employee_id": "E2", "snapshot_month": "2026-02", "hours_logged": 172.0},
    ]

    grain_profile = SDRGrainProfile(
        dataset_id=dataset_id,
        sheet_id=sheet_id,
        primary_entity=CanonicalGrain.PERSON,
        temporal_grain=TemporalGrain.MONTHLY,
        resolved_grain_expression="EMPLOYEE × MONTH",
        grain_status=GrainStatus.CONFIRMED,
        grain_confidence=0.98,
        is_unique=True,
        rationale="Monthly snapshot",
        profile_id="grain_snap",
        artifact_fingerprint="fp_grain_snap",
    )

    engine = SDRKeyIntelligenceEngine()
    result = engine.analyze_keys(
        dataset_id=dataset_id,
        sheet_id=sheet_id,
        profiles=[emp_id, month, hours],
        rows=rows,
        grain_profile=grain_profile,
    )

    candidates = result["candidates"]

    # Composite candidate (employee_id, snapshot_month) is high-confidence
    composite_cand = next(
        (c for c in candidates if set(c.column_names) == {"employee_id", "snapshot_month"}),
        None,
    )
    assert composite_cand is not None
    assert composite_cand.key_type == KeyCandidateType.COMPOSITE_NATURAL_KEY
    assert composite_cand.status == KeyCandidateStatus.HIGH_CONFIDENCE_CANDIDATE_KEY
    assert composite_cand.composite_width == 2
    assert composite_cand.uniqueness_ratio == 1.0


def test_corpus_event_stream_abstention():
    """Target 3: Transaction / Event Log with no natural business key."""
    dataset_id = "ds_events"
    sheet_id = "audit_log"
    row_count = 5

    ts = _create_profile(
        dataset_id, sheet_id, "col_ts", "timestamp",
        SemanticColumnRole.DIMENSION, SemanticDtype.TIMESTAMP, SemanticConcept.TIME_SPAN,
        row_count=row_count, distinct_count=row_count,
    )
    action = _create_profile(
        dataset_id, sheet_id, "col_action", "action",
        SemanticColumnRole.DIMENSION, SemanticDtype.CATEGORICAL, SemanticConcept.CATEGORICAL,
        row_count=row_count, distinct_count=3,
    )
    val = _create_profile(
        dataset_id, sheet_id, "col_latency", "latency_ms",
        SemanticColumnRole.MEASURE, SemanticDtype.DECIMAL, SemanticConcept.MEASURE,
        measure_class=MeasureClass.QUANTITY, row_count=row_count, distinct_count=row_count,
    )

    rows = [
        {"timestamp": f"2026-10-19T10:0{i}:00", "action": "LOGIN", "latency_ms": 10.0 + i}
        for i in range(row_count)
    ]

    grain_profile = SDRGrainProfile(
        dataset_id=dataset_id,
        sheet_id=sheet_id,
        primary_entity=CanonicalGrain.EVENT,
        temporal_grain=TemporalGrain.DATETIME_EVENT,
        resolved_grain_expression="EVENT_OCCURRENCE",
        grain_status=GrainStatus.CONFIRMED,
        grain_confidence=0.95,
        is_unique=True,
        rationale="Audit event stream",
        profile_id="grain_events",
        artifact_fingerprint="fp_events",
    )

    engine = SDRKeyIntelligenceEngine()
    result = engine.analyze_keys(
        dataset_id=dataset_id,
        sheet_id=sheet_id,
        profiles=[ts, action, val],
        rows=rows,
        grain_profile=grain_profile,
    )

    candidates = result["candidates"]
    high_conf = [
        c for c in candidates
        if c.status == KeyCandidateStatus.HIGH_CONFIDENCE_CANDIDATE_KEY
        and c.key_type in (KeyCandidateType.ATOMIC_NATURAL_KEY, KeyCandidateType.COMPOSITE_NATURAL_KEY)
    ]
    assert len(high_conf) == 0


def test_corpus_artifact_persistence_and_determinism(tmp_path):
    """Target 4: SDR-3 Artifact writing & determinism across runs."""
    dataset_id = "ds_det"
    sheet_id = "test_sheet"

    emp_id = _create_profile(
        dataset_id, sheet_id, "col_emp", "employee_id",
        SemanticColumnRole.IDENTIFIER, SemanticDtype.ID, SemanticConcept.IDENTIFIER,
        row_count=3, distinct_count=3,
    )
    name = _create_profile(
        dataset_id, sheet_id, "col_name", "full_name",
        SemanticColumnRole.ATTRIBUTE, SemanticDtype.TEXT, SemanticConcept.DESCRIPTOR,
        row_count=3, distinct_count=3,
    )
    rows = [
        {"employee_id": "E1", "full_name": "Alice"},
        {"employee_id": "E2", "full_name": "Bob"},
        {"employee_id": "E3", "full_name": "Charlie"},
    ]

    engine = SDRKeyIntelligenceEngine()
    run1 = engine.analyze_keys(dataset_id=dataset_id, sheet_id=sheet_id, profiles=[emp_id, name], rows=rows)
    run2 = engine.analyze_keys(dataset_id=dataset_id, sheet_id=sheet_id, profiles=[emp_id, name], rows=rows)

    # Determinism across runs
    assert len(run1["candidates"]) == len(run2["candidates"])
    for c1, c2 in zip(run1["candidates"], run2["candidates"]):
        assert c1.candidate_id == c2.candidate_id
        assert c1.candidate_fingerprint == c2.candidate_fingerprint
        assert c1.status == c2.status

    assert len(run1["functional_dependencies"]) == len(run2["functional_dependencies"])
    for f1, f2 in zip(run1["functional_dependencies"], run2["functional_dependencies"]):
        assert f1.fd_id == f2.fd_id
        assert f1.fd_fingerprint == f2.fd_fingerprint

    # Artifact Writing
    writer = SDRArtifactWriter(base_dir=tmp_path)
    paths = writer.write_sdr3_artifacts(
        dataset_id=dataset_id,
        sheet_id=sheet_id,
        candidates=run1["candidates"],
        dependencies=run1["functional_dependencies"],
        manifest=run1["manifest"],
    )

    for artifact_name, path_str in paths.items():
        if artifact_name == "manifest_fingerprint":
            continue
        p = Path(path_str)
        assert p.exists()
        assert p.stat().st_size > 0
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data is not None


def test_final_p0_integrity_check():
    """Verify primary application database remains completely untouched after all corpus tests."""
    p0_path = Path("backend/data/db/pulsehr.sqlite3")
    if p0_path.exists():
        hasher = hashlib.sha256()
        with open(p0_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        assert hasher.hexdigest() == P0_EXPECTED_SHA
        assert p0_path.stat().st_size == P0_EXPECTED_SIZE
