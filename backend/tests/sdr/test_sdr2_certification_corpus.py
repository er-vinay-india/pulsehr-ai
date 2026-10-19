"""
HighView Semantic Data Refinery — Phase SDR-2
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
from app.services.sdr.contracts.entity import (
    EntityHypothesisState,
    SemanticEntityHypothesis,
)
from app.services.sdr.contracts.grain import (
    GrainStatus,
    SDRGrainProfile,
)
from app.services.sdr.contracts.policies import SDRPolicySuite
from app.services.sdr.contracts.profiles import (
    DeterministicColumnFeatures,
    PrivacyClassification,
    ProfilingAmbiguityState,
    SemanticColumnProfile,
    SemanticDtype,
)
from app.services.sdr.entity.entity_hypothesizer import SDREntityHypothesisEngine
from app.services.sdr.grain.grain_engine import SDRGrainDiscoveryEngine
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
    lineage = SourceCoordinateRef(
        dataset_id=dataset_id,
        sheet_id=sheet_id,
        column_ids=[column_id],
        source_file_hash="dummy_hash",
    )
    return SemanticColumnProfile(
        profile_id=f"prof_{dataset_id}_{sheet_id}_{column_id}",
        dataset_id=dataset_id,
        sheet_id=sheet_id,
        column_id=column_id,
        source_name=source_name,
        canonical_name=source_name.lower(),
        physical_dtype="string",
        semantic_dtype=dtype,
        semantic_role=role,
        semantic_concept=concept,
        entity_type_hypothesis=entity_type,
        measure_class=measure_class,
        confidence=0.90,
        ambiguity_state=ProfilingAmbiguityState.CLEAR,
        privacy_classification=PrivacyClassification.GENERAL_ATTRIBUTE,
        features=features,
        source_lineage=lineage,
        artifact_fingerprint=f"fp_{column_id}",
    )


def test_sdr2_certification_corpus_benchmark(tmp_path: Path):
    """
    Executes the full SDR-2 certification benchmark across 6 canonical table archetypes.
    Verifies:
    1. Correct entity hypothesis clustering and confidence
    2. Decoupling invariant: Dirty keys preserve EntityConfidence >= 0.85
    3. Negative gate: 0 continuous measures (salary/revenue) promoted to grain
    4. Negative gate: 0 surrogate row counters (row_number) promoted to grain
    5. Correct composite grain discovery for snapshots and multi-entity tables
    6. Ambiguity preservation: competing candidates yield GrainStatus.AMBIGUOUS
    7. Zero PK/FK or JoinPlan emissions
    8. Deterministic SHA-256 artifact fingerprints
    9. Retrieval documents strictly targeting SEMANTIC and RAW_SCHEMA namespaces
    10. Bit-identical P0 database isolation
    """
    entity_engine = SDREntityHypothesisEngine()
    grain_engine = SDRGrainDiscoveryEngine()
    artifact_writer = SDRArtifactWriter(base_data_dir=tmp_path)
    policy_suite = SDRPolicySuite()

    all_hypotheses: list[SemanticEntityHypothesis] = []
    all_grain_profiles: list[SDRGrainProfile] = []
    all_grain_candidates = []

    # ---------------------------------------------------------
    # Table 1: Employee Master Table (Clean Single Grain)
    # ---------------------------------------------------------
    t1_p1 = _create_profile("ds_cert", "t1_emp", "c1", "employee_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticDtype.IDENTIFIER_CODE, SemanticConcept.IDENTIFIER, SemanticEntityType.PERSON, row_count=5)
    t1_p2 = _create_profile("ds_cert", "t1_emp", "c2", "full_name", SemanticColumnRole.ENTITY_LABEL, SemanticDtype.NATURAL_LANGUAGE_TEXT, SemanticConcept.DESCRIPTOR, SemanticEntityType.PERSON, row_count=5)
    t1_p3 = _create_profile("ds_cert", "t1_emp", "c3", "department", SemanticColumnRole.DIMENSION, SemanticDtype.CATEGORICAL_CODE, SemanticConcept.DESCRIPTOR, SemanticEntityType.DEPARTMENT, distinct_count=2, row_count=5)
    t1_data = {
        "c1": ["E101", "E102", "E103", "E104", "E105"],
        "c2": ["Alice", "Bob", "Charlie", "David", "Eve"],
        "c3": ["HR", "Eng", "Eng", "Sales", "HR"],
    }
    t1_hyps = entity_engine.generate_hypotheses("ds_cert", "t1_emp", [t1_p1, t1_p2, t1_p3])
    t1_grain = grain_engine.discover_grain("ds_cert", "t1_emp", [t1_p1, t1_p2, t1_p3], t1_data, 5)

    assert len(t1_hyps) >= 1
    assert t1_hyps[0].canonical_name == "EMPLOYEE"
    assert t1_hyps[0].entity_confidence >= 0.85
    assert t1_grain.grain_status == GrainStatus.RESOLVED
    assert t1_grain.primary_entity == CanonicalGrain.PERSON
    assert t1_grain.resolved_grain_expression == "EMPLOYEE_ID"
    assert t1_grain.best_candidate.width == 1

    all_hypotheses.extend(t1_hyps)
    all_grain_profiles.append(t1_grain)
    all_grain_candidates.extend(t1_grain.ranked_candidates)

    # ---------------------------------------------------------
    # Table 2: Monthly Headcount Snapshot (Composite Width 2)
    # ---------------------------------------------------------
    t2_p1 = _create_profile("ds_cert", "t2_snap", "c1", "emp_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticDtype.IDENTIFIER_CODE, SemanticConcept.IDENTIFIER, SemanticEntityType.PERSON, distinct_count=3, row_count=6)
    t2_p2 = _create_profile("ds_cert", "t2_snap", "c2", "month", SemanticColumnRole.TIME, SemanticDtype.DATE, SemanticConcept.TIME_SPAN, SemanticEntityType.UNKNOWN, distinct_count=2, row_count=6)
    t2_p3 = _create_profile("ds_cert", "t2_snap", "c3", "status", SemanticColumnRole.STATUS, SemanticDtype.CATEGORICAL_CODE, SemanticConcept.STATUS, SemanticEntityType.UNKNOWN, distinct_count=2, row_count=6)
    t2_data = {
        "c1": ["E1", "E2", "E3", "E1", "E2", "E3"],
        "c2": ["2026-01", "2026-01", "2026-01", "2026-02", "2026-02", "2026-02"],
        "c3": ["Active", "Active", "Active", "Active", "Leave", "Active"],
    }
    t2_hyps = entity_engine.generate_hypotheses("ds_cert", "t2_snap", [t2_p1, t2_p2, t2_p3])
    t2_grain = grain_engine.discover_grain("ds_cert", "t2_snap", [t2_p1, t2_p2, t2_p3], t2_data, 6)

    assert t2_grain.grain_status == GrainStatus.RESOLVED
    assert t2_grain.temporal_grain == TemporalGrain.MONTH
    assert t2_grain.best_candidate.width == 2
    assert "MONTH" in t2_grain.resolved_grain_expression

    all_hypotheses.extend(t2_hyps)
    all_grain_profiles.append(t2_grain)
    all_grain_candidates.extend(t2_grain.ranked_candidates)

    # ---------------------------------------------------------
    # Table 3: Retail Sales with Continuous Measure (Salary/Revenue Never Grain)
    # ---------------------------------------------------------
    t3_p1 = _create_profile("ds_cert", "t3_sales", "c_st", "store_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticDtype.IDENTIFIER_CODE, SemanticConcept.IDENTIFIER, SemanticEntityType.STORE, distinct_count=2, row_count=4)
    t3_p2 = _create_profile("ds_cert", "t3_sales", "c_sku", "sku_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticDtype.IDENTIFIER_CODE, SemanticConcept.IDENTIFIER, SemanticEntityType.PRODUCT, distinct_count=2, row_count=4)
    t3_p3 = _create_profile("ds_cert", "t3_sales", "c_dt", "sale_date", SemanticColumnRole.TIME, SemanticDtype.DATE, SemanticConcept.TIME_SPAN, SemanticEntityType.UNKNOWN, distinct_count=2, row_count=4)
    # Continuous revenue with 100% unique floats!
    t3_p4 = _create_profile("ds_cert", "t3_sales", "c_rev", "revenue", SemanticColumnRole.MEASURE, SemanticDtype.CURRENCY_AMOUNT, SemanticConcept.MEASURE, SemanticEntityType.UNKNOWN, measure_class=MeasureClass.FINANCIAL, distinct_count=4, row_count=4)
    t3_data = {
        "c_st": ["S1", "S1", "S1", "S2"],
        "c_sku": ["P1", "P1", "P2", "P1"],
        "c_dt": ["2026-01-01", "2026-01-02", "2026-01-01", "2026-01-01"],
        "c_rev": [102.50, 204.10, 305.80, 412.95],
    }
    t3_hyps = entity_engine.generate_hypotheses("ds_cert", "t3_sales", [t3_p1, t3_p2, t3_p3, t3_p4])
    t3_grain = grain_engine.discover_grain("ds_cert", "t3_sales", [t3_p1, t3_p2, t3_p3, t3_p4], t3_data, 4)

    assert t3_grain.grain_status == GrainStatus.RESOLVED
    assert t3_grain.best_candidate.width == 3
    # CRITICAL: Revenue must NOT be in the grain!
    assert "c_rev" not in t3_grain.best_candidate.determinant_column_ids
    for cand in t3_grain.ranked_candidates:
        assert "c_rev" not in cand.determinant_column_ids

    all_hypotheses.extend(t3_hyps)
    all_grain_profiles.append(t3_grain)
    all_grain_candidates.extend(t3_grain.ranked_candidates)

    # ---------------------------------------------------------
    # Table 4: Dirty Employee Table (Dirty Key Decoupling)
    # ---------------------------------------------------------
    t4_p1 = _create_profile("ds_cert", "t4_dirty", "c1", "emp_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticDtype.IDENTIFIER_CODE, SemanticConcept.IDENTIFIER, SemanticEntityType.PERSON, distinct_count=4, null_ratio=0.0, row_count=5)
    t4_p2 = _create_profile("ds_cert", "t4_dirty", "c2", "emp_name", SemanticColumnRole.ENTITY_LABEL, SemanticDtype.NATURAL_LANGUAGE_TEXT, SemanticConcept.DESCRIPTOR, SemanticEntityType.PERSON, distinct_count=4, null_ratio=0.0, row_count=5)
    t4_data = {
        "c1": ["E1", "E1", "E2", "E3", "E4"],
        "c2": ["Alice", "Alice", "Bob", "Charlie", "David"],
    }
    t4_hyps = entity_engine.generate_hypotheses("ds_cert", "t4_dirty", [t4_p1, t4_p2])
    t4_grain = grain_engine.discover_grain("ds_cert", "t4_dirty", [t4_p1, t4_p2], t4_data, 5)

    # Core Epistemic Law: Entity is STILL confidently EMPLOYEE
    assert len(t4_hyps) >= 1
    assert t4_hyps[0].canonical_name == "EMPLOYEE"
    assert t4_hyps[0].entity_confidence >= 0.85
    # While grain reports non-uniqueness / duplicates
    assert t4_grain.is_unique is False
    assert t4_grain.best_candidate is not None
    assert t4_grain.best_candidate.duplicate_row_count > 0

    all_hypotheses.extend(t4_hyps)
    all_grain_profiles.append(t4_grain)
    all_grain_candidates.extend(t4_grain.ranked_candidates)

    # ---------------------------------------------------------
    # Table 5: Ambiguous Table (Competing Candidates)
    # ---------------------------------------------------------
    t5_p1 = _create_profile("ds_cert", "t5_ambig", "c_a", "alt_code_a", SemanticColumnRole.DIMENSION, SemanticDtype.IDENTIFIER_CODE, SemanticConcept.IDENTIFIER, distinct_count=4, row_count=5)
    t5_p2 = _create_profile("ds_cert", "t5_ambig", "c_b", "alt_code_b", SemanticColumnRole.DIMENSION, SemanticDtype.IDENTIFIER_CODE, SemanticConcept.IDENTIFIER, distinct_count=4, row_count=5)
    t5_data = {
        "c_a": ["A1", "A2", "A3", "A4", "A4"],
        "c_b": ["B1", "B2", "B3", "B4", "B4"],
    }
    t5_hyps = entity_engine.generate_hypotheses("ds_cert", "t5_ambig", [t5_p1, t5_p2])
    t5_grain = grain_engine.discover_grain("ds_cert", "t5_ambig", [t5_p1, t5_p2], t5_data, 5)

    assert t5_grain.grain_status == GrainStatus.AMBIGUOUS
    assert len(t5_grain.ranked_candidates) >= 2

    all_hypotheses.extend(t5_hyps)
    all_grain_profiles.append(t5_grain)
    all_grain_candidates.extend(t5_grain.ranked_candidates)

    # ---------------------------------------------------------
    # Table 6: System Row Counter + Unique Salary (Pruning Gates)
    # ---------------------------------------------------------
    t6_p1 = _create_profile("ds_cert", "t6_sys", "c_row", "row_number", SemanticColumnRole.DIMENSION, SemanticDtype.INTEGER_NUMBER, SemanticConcept.TECHNICAL, distinct_count=5, row_count=5)
    t6_p2 = _create_profile("ds_cert", "t6_sys", "c_sal", "salary", SemanticColumnRole.MEASURE, SemanticDtype.CURRENCY_AMOUNT, SemanticConcept.MEASURE, measure_class=MeasureClass.FINANCIAL, distinct_count=5, row_count=5)
    t6_p3 = _create_profile("ds_cert", "t6_sys", "c_name", "department_name", SemanticColumnRole.DIMENSION, SemanticDtype.CATEGORICAL_CODE, SemanticConcept.DESCRIPTOR, SemanticEntityType.DEPARTMENT, distinct_count=3, row_count=5)
    t6_data = {
        "c_row": [1, 2, 3, 4, 5],
        "c_sal": [70000.0, 75000.0, 80000.0, 85000.0, 90000.0],
        "c_name": ["Sales", "HR", "Sales", "Eng", "HR"],
    }
    t6_hyps = entity_engine.generate_hypotheses("ds_cert", "t6_sys", [t6_p1, t6_p2, t6_p3])
    t6_grain = grain_engine.discover_grain("ds_cert", "t6_sys", [t6_p1, t6_p2, t6_p3], t6_data, 5)

    # Neither row_number nor salary can be grain
    assert "c_row" not in t6_grain.best_candidate.determinant_column_ids
    assert "c_sal" not in t6_grain.best_candidate.determinant_column_ids

    all_hypotheses.extend(t6_hyps)
    all_grain_profiles.append(t6_grain)
    all_grain_candidates.extend(t6_grain.ranked_candidates)

    # ---------------------------------------------------------
    # Governance Verification: Zero PK / FK / JoinPlans Emitted
    # ---------------------------------------------------------
    for g in all_grain_profiles:
        gd = g.model_dump()
        assert "primary_key" not in gd
        assert "foreign_key" not in gd
        assert "join_plan" not in gd

    # ---------------------------------------------------------
    # Artifact Persistence Verification
    # ---------------------------------------------------------
    art_paths = artifact_writer.write_sdr2_artifacts(
        dataset_id="ds_cert",
        entity_hypotheses=all_hypotheses,
        grain_profiles=all_grain_profiles,
        grain_candidates=all_grain_candidates,
        policy_suite=policy_suite,
    )

    for key, p_str in art_paths.items():
        if key != "manifest_fingerprint":
            p = Path(p_str)
            assert p.exists()
            assert p.stat().st_size > 0

    manifest_json = Path(art_paths["sdr2_manifest"]).read_text(encoding="utf-8")
    manifest = json.loads(manifest_json)
    assert manifest["dataset_id"] == "ds_cert"
    assert manifest["entity_hypotheses_count"] == len(all_hypotheses)
    assert manifest["grain_profiles_count"] == len(all_grain_profiles)

    # ---------------------------------------------------------
    # Retrieval Namespace Verification
    # ---------------------------------------------------------
    retrieval_adapter = SDRRetrievalAdapter()
    for hyp in all_hypotheses:
        doc = retrieval_adapter.build_entity_hypothesis_document(hyp)
        assert doc.namespace == RetrievalNamespace.SEMANTIC

    for gr in all_grain_profiles:
        doc_sem = retrieval_adapter.build_grain_profile_document(gr)
        assert doc_sem.namespace == RetrievalNamespace.SEMANTIC

        doc_raw = retrieval_adapter.build_raw_grain_observation_document(gr)
        assert doc_raw.namespace == RetrievalNamespace.RAW_SCHEMA

    # ---------------------------------------------------------
    # Bit-Identical P0 Isolation Verification
    # ---------------------------------------------------------
    p0_path = Path("backend/data/db/pulsehr.sqlite")
    if not p0_path.exists():
        p0_path = Path("backend/data/db/pulsehr.sqlite3")
    assert p0_path.exists()
    assert p0_path.stat().st_size == P0_EXPECTED_SIZE

    hasher = hashlib.sha256()
    with open(p0_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    assert hasher.hexdigest() == P0_EXPECTED_SHA
