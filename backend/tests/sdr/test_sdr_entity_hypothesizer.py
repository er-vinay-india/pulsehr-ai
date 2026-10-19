"""
HighView Semantic Data Refinery — Phase SDR-2
Tests: Entity Hypothesis Engine & Dirty Key Decoupling
"""

import pytest

from app.services.ingestion_v2.contracts.semantics import (
    SemanticColumnRole,
    SemanticConcept,
    SemanticEntityType,
)
from app.services.sdr.contracts.entity import (
    EntityHypothesisState,
    SemanticEntityHypothesis,
)
from app.services.ingestion_v2.contracts.provenance import SourceCoordinateRef
from app.services.sdr.contracts.policies import SDRPolicySuite
from app.services.sdr.contracts.profiles import (
    DeterministicColumnFeatures,
    PrivacyClassification,
    ProfilingAmbiguityState,
    SemanticColumnProfile,
    SemanticDtype,
)
from app.services.sdr.entity.entity_hypothesizer import SDREntityHypothesisEngine


def _make_dummy_profile(
    column_id: str,
    source_name: str,
    role: SemanticColumnRole,
    dtype: SemanticDtype,
    entity_hypothesis: SemanticEntityType = SemanticEntityType.UNKNOWN,
    distinct_count: int = 10,
    null_ratio: float = 0.0,
) -> SemanticColumnProfile:
    features = DeterministicColumnFeatures(
        row_count=10,
        null_count=int(10 * null_ratio),
        null_ratio=null_ratio,
        distinct_count=distinct_count,
        distinct_ratio=distinct_count / 10.0,
        sample_values=["val1", "val2"],
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
        semantic_concept=SemanticConcept.DESCRIPTOR,
        entity_type_hypothesis=entity_hypothesis,
        confidence=0.90,
        ambiguity_state=ProfilingAmbiguityState.CLEAR,
        privacy_classification=PrivacyClassification.GENERAL_ATTRIBUTE,
        features=features,
        source_lineage=lineage,
        artifact_fingerprint=f"fp_{column_id}",
    )


def test_entity_hypothesis_clustering_employee_table():
    """Verify clustering of columns into an EMPLOYEE entity hypothesis."""
    profiles = [
        _make_dummy_profile("c1", "emp_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticDtype.IDENTIFIER_CODE, SemanticEntityType.PERSON),
        _make_dummy_profile("c2", "full_name", SemanticColumnRole.ENTITY_LABEL, SemanticDtype.NATURAL_LANGUAGE_TEXT, SemanticEntityType.PERSON),
        _make_dummy_profile("c3", "department", SemanticColumnRole.DIMENSION, SemanticDtype.CATEGORICAL_CODE, SemanticEntityType.DEPARTMENT),
        _make_dummy_profile("c4", "hire_date", SemanticColumnRole.TIME, SemanticDtype.DATE, SemanticEntityType.UNKNOWN),
        _make_dummy_profile("c5", "annual_salary", SemanticColumnRole.MEASURE, SemanticDtype.CURRENCY_AMOUNT, SemanticEntityType.UNKNOWN),
    ]

    engine = SDREntityHypothesisEngine()
    hypotheses = engine.generate_hypotheses("ds_test", "sheet1", profiles)

    assert len(hypotheses) >= 1
    # Primary hypothesis should be EMPLOYEE (PERSON)
    primary = hypotheses[0]
    assert primary.entity_type == SemanticEntityType.PERSON
    assert primary.canonical_name == "EMPLOYEE"
    assert "c1" in primary.identifier_like_column_ids
    assert "c2" in primary.descriptor_column_ids
    assert primary.entity_confidence >= 0.85
    assert primary.state == EntityHypothesisState.CONFIRMED


def test_dirty_key_decoupling_preserves_entity_confidence():
    """
    CRITICAL EPISTEMIC LAW:
    EntityConfidence != KeyConfidence.
    A table with dirty or duplicate employee IDs still represents an EMPLOYEE entity.
    Dirty keys must NOT erase clear entities.
    """
    # Simulate a dirty key column: 50% duplicate rows, 20% nulls
    dirty_emp_id = _make_dummy_profile(
        column_id="c_id",
        source_name="employee_id",
        role=SemanticColumnRole.ENTITY_IDENTIFIER,
        dtype=SemanticDtype.IDENTIFIER_CODE,
        entity_hypothesis=SemanticEntityType.PERSON,
        distinct_count=5,  # Only 5 distinct in 10 rows
        null_ratio=0.20,
    )
    emp_name = _make_dummy_profile(
        column_id="c_name",
        source_name="employee_name",
        role=SemanticColumnRole.ENTITY_LABEL,
        dtype=SemanticDtype.NATURAL_LANGUAGE_TEXT,
        entity_hypothesis=SemanticEntityType.PERSON,
    )
    job_title = _make_dummy_profile(
        column_id="c_title",
        source_name="job_title",
        role=SemanticColumnRole.DIMENSION,
        dtype=SemanticDtype.CATEGORICAL_CODE,
        entity_hypothesis=SemanticEntityType.PERSON,
    )

    engine = SDREntityHypothesisEngine()
    hypotheses = engine.generate_hypotheses("ds_test", "sheet_dirty", [dirty_emp_id, emp_name, job_title])

    assert len(hypotheses) == 1
    emp_hyp = hypotheses[0]
    assert emp_hyp.canonical_name == "EMPLOYEE"
    # Invariant: EntityConfidence remains high despite dirty key
    assert emp_hyp.entity_confidence >= 0.85
    assert emp_hyp.state == EntityHypothesisState.CONFIRMED
    assert "c_id" in emp_hyp.identifier_like_column_ids


def test_entity_clustering_store_and_product():
    """Verify distinct clustering for store and product columns in retail data."""
    profiles = [
        _make_dummy_profile("s1", "store_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticDtype.IDENTIFIER_CODE, SemanticEntityType.STORE),
        _make_dummy_profile("s2", "store_city", SemanticColumnRole.LOCATION, SemanticDtype.GEOGRAPHIC_LOCATION, SemanticEntityType.STORE),
        _make_dummy_profile("p1", "sku_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticDtype.IDENTIFIER_CODE, SemanticEntityType.PRODUCT),
        _make_dummy_profile("p2", "product_category", SemanticColumnRole.CATEGORY, SemanticDtype.CATEGORICAL_CODE, SemanticEntityType.PRODUCT),
    ]

    engine = SDREntityHypothesisEngine()
    hypotheses = engine.generate_hypotheses("ds_test", "sheet_retail", profiles)

    # Should detect both STORE and PRODUCT
    entity_names = {h.canonical_name for h in hypotheses}
    assert "STORE" in entity_names
    assert "PRODUCT" in entity_names


def test_unknown_fallback_on_unstructured_data():
    """Verify fallback to UNKNOWN hypothesis when no entity clues are present."""
    profiles = [
        _make_dummy_profile("u1", "generic_val1", SemanticColumnRole.DIMENSION, SemanticDtype.NATURAL_LANGUAGE_TEXT, SemanticEntityType.UNKNOWN),
        _make_dummy_profile("u2", "generic_val2", SemanticColumnRole.DIMENSION, SemanticDtype.NATURAL_LANGUAGE_TEXT, SemanticEntityType.UNKNOWN),
    ]

    engine = SDREntityHypothesisEngine()
    hypotheses = engine.generate_hypotheses("ds_test", "sheet_generic", profiles)

    assert len(hypotheses) == 1
    h = hypotheses[0]
    assert h.entity_type == SemanticEntityType.UNKNOWN
    assert h.canonical_name == "UNKNOWN"
    assert h.entity_confidence <= 0.50
    assert h.state == EntityHypothesisState.AMBIGUOUS


def test_entity_hypothesis_deterministic_fingerprint():
    """Verify determinism of entity hypothesis fingerprints."""
    profiles = [
        _make_dummy_profile("c1", "emp_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticDtype.IDENTIFIER_CODE, SemanticEntityType.PERSON),
        _make_dummy_profile("c2", "full_name", SemanticColumnRole.ENTITY_LABEL, SemanticDtype.NATURAL_LANGUAGE_TEXT, SemanticEntityType.PERSON),
    ]

    engine = SDREntityHypothesisEngine()
    h1 = engine.generate_hypotheses("ds_test", "sheet1", profiles, policy_fingerprint="pol_v1")[0]
    h2 = engine.generate_hypotheses("ds_test", "sheet1", profiles, policy_fingerprint="pol_v1")[0]

    assert h1.artifact_fingerprint == h2.artifact_fingerprint
    assert len(h1.artifact_fingerprint) == 64  # SHA-256
