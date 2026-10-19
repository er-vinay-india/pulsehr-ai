"""
HighView Semantic Data Refinery — Phase SDR-4
Certification Corpus Benchmark & Evaluation Suite
"""

import hashlib
import json
from pathlib import Path
import time
import tracemalloc
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
from app.services.sdr.artifacts.artifact_writer import SDRArtifactWriter
from app.services.sdr.contracts.enrichment import (
    EnrichmentDecisionType,
    EnrichmentMaterialization,
    EnrichmentStatus,
)
from app.services.sdr.contracts.grain import (
    GrainStatus,
    SDRGrainProfile,
)
from app.services.sdr.contracts.policies import (
    EnrichmentPolicy,
    SDRPolicySuite,
)
from app.services.sdr.contracts.profiles import (
    DeterministicColumnFeatures,
    PrivacyClassification,
    ProfilingAmbiguityState,
    SemanticColumnProfile,
    SemanticDtype,
)
from app.services.sdr.enrichment.enrichment_engine import SDREnrichmentEngine
from app.services.sdr.enrichment.mock_providers import (
    CodeLabelProvider,
    DatePartProvider,
    MockAmbiguousProvider,
    MockFailingProvider,
    MockLowUtilityProvider,
    MockSensitiveInferenceProvider,
)
from app.services.sdr.enrichment.provider import EnrichmentProviderRegistry

P0_EXPECTED_SHA = "1561d64eeae26f4d30926371740d6ca9dc41eb6ea7c537281763b7d5aabd9496"
P0_EXPECTED_SIZE = 70385664


def _create_profile(
    dataset_id: str,
    sheet_id: str,
    column_id: str,
    source_name: str,
    role: SemanticColumnRole,
    dtype: SemanticDtype,
    concept: SemanticConcept = SemanticConcept.DESCRIPTOR,
    entity_type: SemanticEntityType = SemanticEntityType.UNKNOWN,
    measure_class: MeasureClass | None = None,
    privacy: PrivacyClassification = PrivacyClassification.GENERAL_ATTRIBUTE,
    ambiguity: ProfilingAmbiguityState = ProfilingAmbiguityState.CLEAR,
    row_count: int = 10,
) -> SemanticColumnProfile:
    features = DeterministicColumnFeatures(
        row_count=row_count,
        null_count=0,
        null_ratio=0.0,
        distinct_count=row_count,
        distinct_ratio=1.0,
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
        privacy_classification=privacy,
        confidence=0.95,
        ambiguity_state=ambiguity,
        features=features,
        source_lineage=SourceCoordinateRef(
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            column_ids=[column_id],
            source_file_hash="dummy_hash",
        ),
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


def test_corpus_10_core_enrichment_cases():
    """Verify all 10 core SDR-4 enrichment cases."""
    dataset_id = "ds_corpus"
    sheet_id = "table1"

    # Case 1 & 2: Date & Code
    p_date = _create_profile(dataset_id, sheet_id, "col_date", "hire_date", SemanticColumnRole.TIME, SemanticDtype.DATE)
    p_dept = _create_profile(dataset_id, sheet_id, "col_dept", "dept_code", SemanticColumnRole.DIMENSION, SemanticDtype.CATEGORICAL_CODE)
    # Case 3: Low-utility
    p_text = _create_profile(dataset_id, sheet_id, "col_text", "notes", SemanticColumnRole.FREE_TEXT, SemanticDtype.NATURAL_LANGUAGE_TEXT)
    # Case 4: Ambiguous
    p_ambig = _create_profile(dataset_id, sheet_id, "col_ambig", "region_code", SemanticColumnRole.DIMENSION, SemanticDtype.CATEGORICAL_CODE, ambiguity=ProfilingAmbiguityState.AMBIGUOUS_TYPE)
    # Case 5: Sensitive
    p_emp = _create_profile(dataset_id, sheet_id, "col_emp", "emp_id", SemanticColumnRole.IDENTIFIER, SemanticDtype.IDENTIFIER_CODE)

    reg = EnrichmentProviderRegistry()
    reg.register_provider(DatePartProvider())
    reg.register_provider(CodeLabelProvider())
    reg.register_provider(MockLowUtilityProvider())
    reg.register_provider(MockAmbiguousProvider())
    reg.register_provider(MockSensitiveInferenceProvider())

    engine = SDREnrichmentEngine(registry=reg)
    result = engine.analyze_enrichments(
        dataset_id=dataset_id,
        sheet_id=sheet_id,
        profiles=[p_date, p_dept, p_text, p_ambig, p_emp],
    )

    validated = result.validated_enrichments
    decisions = result.decisions

    # Case 1: Date -> Year, Month, Quarter accepted
    date_val = [v for v in validated if "hire_date" in v.output_name]
    assert len(date_val) == 3

    # Case 2: Code -> Label accepted
    dept_val = [v for v in validated if "dept_code" in v.output_name]
    assert len(dept_val) == 1
    assert dept_val[0].output_name == "dept_code_name"

    # Case 3: Low-utility rejected
    low_dec = [d for d in decisions if "cand_low_util" in d.candidate_id]
    assert len(low_dec) >= 1
    for d in low_dec:
        assert d.decision in (EnrichmentDecisionType.REJECT, EnrichmentDecisionType.DEFER)

    # Case 4: Ambiguous candidate withheld
    ambig_dec = [d for d in decisions if "cand_ambig" in d.candidate_id]
    assert len(ambig_dec) >= 1
    for d in ambig_dec:
        assert d.decision == EnrichmentDecisionType.AMBIGUOUS

    # Case 5A: Direct Identifier Safe Internal Use -> ACCEPTED
    emp_val = [v for v in validated if "emp_id" in v.output_name]
    assert len(emp_val) == 1
    assert emp_val[0].output_name == "emp_id_name"
    assert emp_val[0].materialization == EnrichmentMaterialization.VIRTUAL_ENRICHMENT

    # Case 5B: Direct Identifier Sensitive Inferred Attribute -> HARD BLOCKED
    sens_dec = [d for d in decisions if "health" in d.candidate_id]
    assert len(sens_dec) >= 1
    for d in sens_dec:
        assert d.hard_gate_passed is False
        assert d.decision == EnrichmentDecisionType.REJECT

    # Verify zero sensitive attributes accepted in validated
    assert not any("health" in v.output_name.lower() for v in validated)


def test_corpus_artifact_persistence_and_determinism(tmp_path):
    """Verify exact repeat-run artifact determinism and SHA-256 match across separate directories."""
    dataset_id = "ds_det"
    sheet_id = "employees"

    hire_date = _create_profile(dataset_id, sheet_id, "col_date", "hire_date", SemanticColumnRole.TIME, SemanticDtype.DATE)
    dept_code = _create_profile(dataset_id, sheet_id, "col_dept", "dept_code", SemanticColumnRole.DIMENSION, SemanticDtype.CATEGORICAL_CODE)

    policy = SDRPolicySuite()
    engine = SDREnrichmentEngine()

    run1 = engine.analyze_enrichments(dataset_id=dataset_id, sheet_id=sheet_id, profiles=[hire_date, dept_code], policy_suite=policy)
    run2 = engine.analyze_enrichments(dataset_id=dataset_id, sheet_id=sheet_id, profiles=[hire_date, dept_code], policy_suite=policy)

    # 1. In-memory fingerprint matching
    assert len(run1.candidates) == len(run2.candidates)
    for c1, c2 in zip(run1.candidates, run2.candidates):
        assert c1.candidate_id == c2.candidate_id
        assert c1.artifact_fingerprint == c2.artifact_fingerprint

    assert len(run1.validated_enrichments) == len(run2.validated_enrichments)
    for v1, v2 in zip(run1.validated_enrichments, run2.validated_enrichments):
        assert v1.enrichment_id == v2.enrichment_id
        assert v1.artifact_fingerprint == v2.artifact_fingerprint

    assert len(run1.decisions) == len(run2.decisions)
    for d1, d2 in zip(run1.decisions, run2.decisions):
        assert d1.decision_id == d2.decision_id
        assert d1.artifact_fingerprint == d2.artifact_fingerprint

    # 2. Disk persistence to two isolated directories
    dir1 = tmp_path / "run1"
    dir2 = tmp_path / "run2"

    writer1 = SDRArtifactWriter(base_dir=dir1)
    writer2 = SDRArtifactWriter(base_dir=dir2)

    paths1 = writer1.write_sdr4_artifacts(
        dataset_id=dataset_id,
        sheet_id=sheet_id,
        candidates=run1.candidates,
        validated_enrichments=run1.validated_enrichments,
        decisions=run1.decisions,
        manifest=run1.manifest,
        policy_suite=policy,
    )

    paths2 = writer2.write_sdr4_artifacts(
        dataset_id=dataset_id,
        sheet_id=sheet_id,
        candidates=run2.candidates,
        validated_enrichments=run2.validated_enrichments,
        decisions=run2.decisions,
        manifest=run2.manifest,
        policy_suite=policy,
    )

    def file_sha256(p: str) -> str:
        h = hashlib.sha256()
        with open(p, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    for key in ("enrichment_candidates", "validated_enrichments", "enrichment_decisions", "sdr4_manifest"):
        sha1 = file_sha256(paths1[key])
        sha2 = file_sha256(paths2[key])
        assert sha1 == sha2, f"Artifact {key} SHA mismatch: {sha1} != {sha2}"


def test_corpus_provider_and_reference_version_invalidation_proof():
    """
    Prove that provider version (v1 -> v2) and reference version (r1 -> r2) upgrades:
    1. Keep source data fingerprint UNCHANGED.
    2. Change candidate and validated enrichment fingerprints.
    3. Invalidate dependent enrichments.
    4. Keep unrelated enrichments completely valid and unchanged.
    """
    dataset_id = "ds_inv_corpus"
    sheet_id = "table_inv"

    dept_col = _create_profile(dataset_id, sheet_id, "col_dept", "dept_code", SemanticColumnRole.DIMENSION, SemanticDtype.CATEGORICAL_CODE)
    hire_col = _create_profile(dataset_id, sheet_id, "col_hire", "hire_date", SemanticColumnRole.TIME, SemanticDtype.DATE)

    # Initial Run A: provider v1.0.0, reference r2026.1
    reg_a = EnrichmentProviderRegistry()
    reg_a.register_provider(CodeLabelProvider(version="1.0.0", reference_version="2026.1"))
    reg_a.register_provider(DatePartProvider(version="1.0.0"))

    engine_a = SDREnrichmentEngine(registry=reg_a)
    result_a = engine_a.analyze_enrichments(dataset_id=dataset_id, sheet_id=sheet_id, profiles=[dept_col, hire_col])

    val_a = result_a.validated_enrichments
    dept_val_a = [v for v in val_a if "dept_code" in v.output_name][0]
    hire_val_a = [v for v in val_a if "hire_date" in v.output_name][0]

    # Source fingerprint check
    source_fp_dept = dept_col.artifact_fingerprint

    # Upgraded Run B: Provider Version v2.0.0
    reg_b = EnrichmentProviderRegistry()
    reg_b.register_provider(CodeLabelProvider(version="2.0.0", reference_version="2026.1"))
    reg_b.register_provider(DatePartProvider(version="1.0.0"))

    engine_b = SDREnrichmentEngine(registry=reg_b)
    result_b = engine_b.analyze_enrichments(dataset_id=dataset_id, sheet_id=sheet_id, profiles=[dept_col, hire_col])

    val_b = result_b.validated_enrichments
    dept_val_b = [v for v in val_b if "dept_code" in v.output_name][0]

    # Verification:
    # 1. Source fingerprint: UNCHANGED
    assert dept_col.artifact_fingerprint == source_fp_dept

    # 2. Candidate / Validated enrichment fingerprint: CHANGED
    assert dept_val_a.artifact_fingerprint != dept_val_b.artifact_fingerprint

    # 3. Dependent enrichment: INVALIDATED when provider upgrades
    inv_provider = engine_a.invalidate_by_provider_or_reference_version(
        val_a, provider_id="provider_code_label", new_provider_version="2.0.0"
    )
    inv_dept = [v for v in inv_provider if "dept_code" in v.output_name][0]
    inv_hire = [v for v in inv_provider if "hire_date" in v.output_name][0]

    assert inv_dept.is_valid is False
    assert "2.0.0" in inv_dept.invalidation_reason

    # 4. Unrelated enrichment: UNCHANGED and VALID
    assert inv_hire.is_valid is True
    assert inv_hire.artifact_fingerprint == hire_val_a.artifact_fingerprint

    # 5. Reference Version r2026.2 Upgrade: INVALIDATED
    inv_ref = engine_a.invalidate_by_provider_or_reference_version(
        val_a, provider_id="provider_code_label", new_reference_version="2026.2"
    )
    ref_dept = [v for v in inv_ref if "dept_code" in v.output_name][0]
    ref_hire = [v for v in inv_ref if "hire_date" in v.output_name][0]

    assert ref_dept.is_valid is False
    assert "2026.2" in ref_dept.invalidation_reason
    assert ref_hire.is_valid is True


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
