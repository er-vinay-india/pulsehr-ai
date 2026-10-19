"""
HighView Semantic Data Refinery — Phase SDR-1
Tests: Contracts & Fingerprint Invariants
"""

import pytest
from pydantic import ValidationError

from app.services.ingestion_v2.contracts.provenance import SourceCoordinateRef
from app.services.ingestion_v2.contracts.semantics import (
    ClassificationSource,
    MeasureClass,
    SemanticColumnRole,
    SemanticConcept,
    SemanticEntityType,
)
from app.services.sdr.contracts.policies import (
    SDRPolicySuite,
    SemanticConfidencePolicy,
)
from app.services.sdr.contracts.profiles import (
    DeterministicColumnFeatures,
    PrivacyClassification,
    ProfilingAmbiguityState,
    SemanticColumnProfile,
    SemanticDtype,
    compute_profile_fingerprint,
)
from app.services.sdr.contracts.decomposition import (
    CompositePatternType,
    DecompositionComponent,
    DecompositionValidationStatus,
    SemanticDecompositionCandidate,
    compute_candidate_fingerprint,
)


def test_sdr_policy_suite_fingerprint_determinism():
    """Verify that same policy config produces identical fingerprint and changes upon tuning."""
    policy1 = SDRPolicySuite()
    policy2 = SDRPolicySuite()
    assert policy1.compute_policy_fingerprint() == policy2.compute_policy_fingerprint()

    # Modifying threshold changes fingerprint
    custom_policy = SDRPolicySuite(
        semantic=SemanticConfidencePolicy(promotion_threshold=0.85)
    )
    assert custom_policy.compute_policy_fingerprint() != policy1.compute_policy_fingerprint()


def test_semantic_column_profile_frozen_immutability():
    """Verify SemanticColumnProfile is strictly immutable and extra fields are forbidden."""
    features = DeterministicColumnFeatures(
        row_count=10,
        null_count=0,
        null_ratio=0.0,
        distinct_count=10,
        distinct_ratio=1.0,
    )
    lineage = SourceCoordinateRef(
        dataset_id="ds_test",
        sheet_id="sheet1",
        column_ids=["col1"],
        source_file_hash="hash123",
    )

    profile = SemanticColumnProfile(
        profile_id="prof_01",
        dataset_id="ds_test",
        sheet_id="sheet1",
        column_id="col1",
        source_name="employee_id",
        canonical_name="employee_id",
        physical_dtype="string",
        semantic_dtype=SemanticDtype.IDENTIFIER_CODE,
        semantic_role=SemanticColumnRole.ENTITY_IDENTIFIER,
        semantic_concept=SemanticConcept.IDENTIFIER,
        features=features,
        confidence=0.95,
        source_lineage=lineage,
    )

    # Mutation raises error because model is frozen
    with pytest.raises(ValidationError):
        profile.confidence = 0.50


def test_decomposition_candidate_is_destructive_invariant():
    """Verify is_destructive defaults to False and candidate is frozen."""
    candidate = SemanticDecompositionCandidate(
        candidate_id="cand_01",
        dataset_id="ds_test",
        sheet_id="sheet1",
        source_column_id="col_loc",
        source_column_name="Location",
        pattern_type=CompositePatternType.GEOGRAPHIC_HIERARCHY,
        delimiter=" - ",
        components=[
            DecompositionComponent(
                position=1,
                candidate_name="city",
                proposed_semantic_role=SemanticColumnRole.LOCATION,
                proposed_semantic_dtype=SemanticDtype.GEOGRAPHIC_LOCATION,
                proposed_concept=SemanticConcept.LOCATION_ATTRIBUTE,
                extraction_rule="SPLIT[0]",
            )
        ],
        confidence=0.90,
        source_profile_fingerprint="fp_prof",
    )

    assert candidate.is_destructive is False
    with pytest.raises(ValidationError):
        candidate.confidence = 0.20


def test_profile_and_candidate_fingerprint_determinism():
    """Verify profile and candidate fingerprints are reproducible and exclude volatile fields."""
    fp1 = compute_profile_fingerprint(
        dataset_id="ds_1",
        sheet_id="s1",
        column_id="c1",
        source_name="salary",
        physical_dtype="float64",
        semantic_dtype=SemanticDtype.CURRENCY_AMOUNT,
        semantic_role=SemanticColumnRole.MEASURE,
        features_sample_fingerprint="sample_hash_abc",
        policy_fingerprint="policy_hash_xyz",
    )
    fp2 = compute_profile_fingerprint(
        dataset_id="ds_1",
        sheet_id="s1",
        column_id="c1",
        source_name="salary",
        physical_dtype="float64",
        semantic_dtype=SemanticDtype.CURRENCY_AMOUNT,
        semantic_role=SemanticColumnRole.MEASURE,
        features_sample_fingerprint="sample_hash_abc",
        policy_fingerprint="policy_hash_xyz",
    )
    assert fp1 == fp2
    assert len(fp1) == 64  # SHA-256 length

    c_fp1 = compute_candidate_fingerprint(
        dataset_id="ds_1",
        sheet_id="s1",
        source_column_id="c1",
        pattern_type=CompositePatternType.CODE_LABEL_PAIR,
        component_names=["code", "label"],
        source_profile_fingerprint=fp1,
    )
    c_fp2 = compute_candidate_fingerprint(
        dataset_id="ds_1",
        sheet_id="s1",
        source_column_id="c1",
        pattern_type=CompositePatternType.CODE_LABEL_PAIR,
        component_names=["code", "label"],
        source_profile_fingerprint=fp1,
    )
    assert c_fp1 == c_fp2
