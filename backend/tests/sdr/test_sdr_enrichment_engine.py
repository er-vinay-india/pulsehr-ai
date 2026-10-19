"""
HighView Semantic Data Refinery — Phase SDR-4
Tests: Controlled Enrichment Engine, Hard Governance Gates, and Decision Evaluation
"""

import pytest

from app.services.ingestion_v2.contracts.grain import (
    CanonicalGrain,
    TemporalGrain,
)
from app.services.ingestion_v2.contracts.provenance import SourceCoordinateRef
from app.services.ingestion_v2.contracts.semantics import (
    SemanticColumnRole,
    SemanticConcept,
    SemanticEntityType,
)
from app.services.ingestion_v2.retrieval.namespaces import (
    AuthorityClass,
    RetrievalNamespace,
)
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
from app.services.sdr.retrieval.retrieval_adapter import SDRRetrievalAdapter


def _make_profile(
    column_id: str,
    source_name: str,
    role: SemanticColumnRole,
    dtype: SemanticDtype,
    concept: SemanticConcept = SemanticConcept.DESCRIPTOR,
    entity_type: SemanticEntityType = SemanticEntityType.UNKNOWN,
    privacy: PrivacyClassification = PrivacyClassification.GENERAL_ATTRIBUTE,
    ambiguity: ProfilingAmbiguityState = ProfilingAmbiguityState.CLEAR,
    row_count: int = 5,
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
        dataset_id="ds_test",
        sheet_id="sheet1",
        column_id=column_id,
        source_name=source_name,
        canonical_name=source_name.lower(),
        physical_dtype="VARCHAR",
        semantic_dtype=dtype,
        semantic_role=role,
        semantic_concept=concept,
        entity_type_hypothesis=entity_type,
        privacy_classification=privacy,
        confidence=0.95,
        ambiguity_state=ambiguity,
        features=features,
        source_lineage=SourceCoordinateRef(
            dataset_id="ds_test",
            sheet_id="sheet1",
            column_ids=[column_id],
            source_file_hash="dummy_source_hash",
        ),
        profile_id=f"prof_{column_id}",
        artifact_fingerprint=f"fp_{column_id}",
    )


def test_deterministic_date_part_enrichment():
    """Date column produces accepted year, month, and standard quarter derivations."""
    hire_date = _make_profile(
        "col_date", "hire_date",
        SemanticColumnRole.TIME, SemanticDtype.DATE, SemanticConcept.TIME_SPAN
    )
    engine = SDREnrichmentEngine()
    result = engine.analyze_enrichments(
        dataset_id="ds_test",
        sheet_id="sheet1",
        profiles=[hire_date],
        column_data={"col_date": ["2026-01-15", "2026-04-20", "2026-10-19"]},
    )

    validated = result.validated_enrichments
    assert len(validated) == 3
    names = {v.output_name for v in validated}
    assert "hire_date_year" in names
    assert "hire_date_month" in names
    assert "hire_date_quarter" in names

    for v in validated:
        assert v.authority == "DERIVED_ENRICHMENT"
        assert v.enrichment_id.startswith("ENRICH-")
        assert v.is_valid is True
        assert v.deterministic_projection_expression is not None


def test_code_label_enrichment():
    """Department code produces standard text label expansion via local reference dictionary."""
    dept_code = _make_profile(
        "col_dept", "dept_code",
        SemanticColumnRole.DIMENSION, SemanticDtype.CATEGORICAL_CODE, SemanticConcept.CATEGORICAL
    )
    engine = SDREnrichmentEngine()
    result = engine.analyze_enrichments(
        dataset_id="ds_test",
        sheet_id="sheet1",
        profiles=[dept_code],
        column_data={"col_dept": ["ENG", "SAL", "HR"]},
    )

    validated = result.validated_enrichments
    assert len(validated) == 1
    assert validated[0].output_name == "dept_code_name"
    assert validated[0].output_semantic_type == SemanticDtype.NATURAL_LANGUAGE_TEXT
    assert validated[0].confidence >= 0.95


def test_low_utility_rejection():
    """Trivial character count metric is evaluated and rejected/deferred due to low information gain."""
    text_col = _make_profile(
        "col_text", "comments",
        SemanticColumnRole.FREE_TEXT, SemanticDtype.NATURAL_LANGUAGE_TEXT, SemanticConcept.FREE_TEXT
    )
    reg = EnrichmentProviderRegistry()
    reg.register_provider(MockLowUtilityProvider())
    engine = SDREnrichmentEngine(registry=reg)

    result = engine.analyze_enrichments(
        dataset_id="ds_test",
        sheet_id="sheet1",
        profiles=[text_col],
    )

    assert len(result.validated_enrichments) == 0
    assert len(result.decisions) == 1
    dec = result.decisions[0]
    assert dec.decision in (EnrichmentDecisionType.REJECT, EnrichmentDecisionType.DEFER)
    assert dec.analytical_utility < 0.60
    assert "low" in dec.rationale.lower()


def test_sensitive_inference_hard_block():
    """Probabilistic health risk inference is strictly BLOCKED by hard gate; zero execution."""
    emp_id = _make_profile(
        "col_emp", "employee_id",
        SemanticColumnRole.IDENTIFIER, SemanticDtype.IDENTIFIER_CODE, SemanticConcept.IDENTIFIER
    )
    reg = EnrichmentProviderRegistry()
    reg.register_provider(MockSensitiveInferenceProvider())
    engine = SDREnrichmentEngine(registry=reg)

    result = engine.analyze_enrichments(
        dataset_id="ds_test",
        sheet_id="sheet1",
        profiles=[emp_id],
    )

    assert len(result.validated_enrichments) == 0
    assert len(result.decisions) == 1
    dec = result.decisions[0]
    assert dec.decision == EnrichmentDecisionType.REJECT
    assert dec.hard_gate_passed is False
    assert any("sensitive" in f.lower() for f in dec.hard_gate_failures)


def test_ambiguity_abstention():
    """Ambiguous candidate signal is marked AMBIGUOUS; resolution is withheld without guessing."""
    ambig_col = _make_profile(
        "col_loc", "location_tag",
        SemanticColumnRole.DIMENSION, SemanticDtype.CATEGORICAL_CODE, SemanticConcept.CATEGORICAL,
        ambiguity=ProfilingAmbiguityState.AMBIGUOUS_TYPE
    )
    reg = EnrichmentProviderRegistry()
    reg.register_provider(MockAmbiguousProvider())
    engine = SDREnrichmentEngine(registry=reg)

    result = engine.analyze_enrichments(
        dataset_id="ds_test",
        sheet_id="sheet1",
        profiles=[ambig_col],
    )

    assert len(result.validated_enrichments) == 0
    assert len(result.decisions) == 1
    dec = result.decisions[0]
    assert dec.decision == EnrichmentDecisionType.AMBIGUOUS
    assert dec.hard_gate_passed is False


def test_provider_failure_graceful_degradation():
    """Provider failure or timeout degrades gracefully without disrupting source or other enrichments."""
    date_col = _make_profile("col_date", "event_date", SemanticColumnRole.TIME, SemanticDtype.DATE)
    text_col = _make_profile("col_text", "notes", SemanticColumnRole.FREE_TEXT, SemanticDtype.NATURAL_LANGUAGE_TEXT)

    reg = EnrichmentProviderRegistry()
    reg.register_provider(DatePartProvider())
    reg.register_provider(MockFailingProvider())
    engine = SDREnrichmentEngine(registry=reg)

    result = engine.analyze_enrichments(
        dataset_id="ds_test",
        sheet_id="sheet1",
        profiles=[date_col, text_col],
    )

    # Date parts succeeded despite failing provider on text_col
    assert len(result.validated_enrichments) == 3
    assert result.manifest["validated_enrichments_count"] == 3


def test_source_change_invalidation():
    """Changing source column values or fingerprint invalidates dependent enrichments; preserves unrelated."""
    hire_date = _make_profile("col_hire", "hire_date", SemanticColumnRole.TIME, SemanticDtype.DATE)
    dept_code = _make_profile("col_dept", "dept_code", SemanticColumnRole.DIMENSION, SemanticDtype.CATEGORICAL_CODE)

    engine = SDREnrichmentEngine()
    result = engine.analyze_enrichments(
        dataset_id="ds_test",
        sheet_id="sheet1",
        profiles=[hire_date, dept_code],
    )

    validated = result.validated_enrichments
    assert len(validated) == 4
    for v in validated:
        assert v.is_valid is True

    # Mutate col_hire
    updated = engine.invalidate_by_source_change(validated, changed_column_ids=["col_hire"])
    hire_enrichments = [e for e in updated if "hire_date" in e.output_name]
    dept_enrichments = [e for e in updated if "dept_code" in e.output_name]

    for e in hire_enrichments:
        assert e.is_valid is False
        assert "Source column" in str(e.invalidation_reason)

    for e in dept_enrichments:
        assert e.is_valid is True  # Preserved!


def test_provider_version_upgrade_invalidation():
    """Upgrading provider version invalidates dependent enrichments."""
    hire_date = _make_profile("col_hire", "hire_date", SemanticColumnRole.TIME, SemanticDtype.DATE)
    engine = SDREnrichmentEngine()
    result = engine.analyze_enrichments(
        dataset_id="ds_test",
        sheet_id="sheet1",
        profiles=[hire_date],
    )

    validated = result.validated_enrichments
    assert len(validated) == 3

    # Upgrade provider_date_part from 1.0.0 to 2.0.0
    updated = engine.invalidate_by_provider_version(validated, provider_id="provider_date_part", new_version="2.0.0")
    for e in updated:
        assert e.is_valid is False
        assert "2.0.0" in str(e.invalidation_reason)


def test_virtual_vs_materialized_distinction():
    """Virtual enrichments store logical expressions; materialized enrichments reference persisted storage."""
    hire_date = _make_profile("col_hire", "hire_date", SemanticColumnRole.TIME, SemanticDtype.DATE)
    engine = SDREnrichmentEngine()

    # Default: virtual projections
    res_virtual = engine.analyze_enrichments(
        dataset_id="ds_test", sheet_id="sheet1", profiles=[hire_date], materialize_all=False
    )
    for v in res_virtual.validated_enrichments:
        assert v.materialization == EnrichmentMaterialization.VIRTUAL_ENRICHMENT
        assert v.deterministic_projection_expression is not None

    # Explicit: materialized
    res_mat = engine.analyze_enrichments(
        dataset_id="ds_test", sheet_id="sheet1", profiles=[hire_date], materialize_all=True
    )
    for v in res_mat.validated_enrichments:
        assert v.materialization == EnrichmentMaterialization.MATERIALIZED_ENRICHMENT
        assert v.output_values_reference is not None
        assert "silver_store://" in v.output_values_reference


def test_depth_and_budget_limits():
    """Enrichment policy limits column budget and prevents uncontrolled depth explosion."""
    hire_date = _make_profile("col_hire", "hire_date", SemanticColumnRole.TIME, SemanticDtype.DATE)
    policy = EnrichmentPolicy(max_enrichments_per_column=2, max_enrichment_depth=1)
    engine = SDREnrichmentEngine(policy=policy)

    result = engine.analyze_enrichments(
        dataset_id="ds_test",
        sheet_id="sheet1",
        profiles=[hire_date],
    )

    # hire_date has 3 candidate parts (year, month, quarter), but column cap is 2!
    assert len(result.validated_enrichments) == 2
    assert result.manifest["deferred_count"] == 1


def test_retrieval_namespace_strictness():
    """Enrichment retrieval documents emit strictly to SEMANTIC_INDEX; forbidden to RELATIONSHIP/ANALYTICAL."""
    hire_date = _make_profile("col_hire", "hire_date", SemanticColumnRole.TIME, SemanticDtype.DATE)
    engine = SDREnrichmentEngine()
    result = engine.analyze_enrichments(
        dataset_id="ds_test",
        sheet_id="sheet1",
        profiles=[hire_date],
    )

    cand = result.candidates[0]
    val = result.validated_enrichments[0]

    cand_doc = SDRRetrievalAdapter.build_enrichment_candidate_document(cand)
    val_doc = SDRRetrievalAdapter.build_validated_enrichment_document(val)

    assert cand_doc.namespace == RetrievalNamespace.SEMANTIC
    assert cand_doc.authority_class == AuthorityClass.SEMANTIC
    assert val_doc.namespace == RetrievalNamespace.SEMANTIC
    assert val_doc.authority_class == AuthorityClass.SEMANTIC

    forbidden = {RetrievalNamespace.RELATIONSHIP, RetrievalNamespace.ANALYTICAL}
    assert cand_doc.namespace not in forbidden
    assert val_doc.namespace not in forbidden


def test_governance_invariants_unviolated():
    """Strict verification of zero sensitive acceptance, zero relationship edges, zero JoinPlans."""
    emp_id = _make_profile("col_emp", "employee_id", SemanticColumnRole.IDENTIFIER, SemanticDtype.IDENTIFIER_CODE)
    engine = SDREnrichmentEngine()
    result = engine.analyze_enrichments(
        dataset_id="ds_test",
        sheet_id="sheet1",
        profiles=[emp_id],
    )

    # Zero sensitive inferred attributes accepted
    for v in result.validated_enrichments:
        assert v.output_semantic_type != SemanticDtype.UNKNOWN
        assert "health" not in v.output_name.lower()

    # Zero relationship edges or JoinPlans
    assert "relationship_edges" not in result
    assert "join_plans" not in result
    assert "gold_metrics" not in result
