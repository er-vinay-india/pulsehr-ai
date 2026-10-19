"""
HighView Semantic Data Refinery — Phase SDR-4G / GEO-1
Governed Geographic Semantic Resolver & Offline Enrichment Provider
Full Certification Corpus Benchmark & Evaluation Suite
"""

import hashlib
import json
from pathlib import Path
import time
import tracemalloc
import pytest

from app.services.sdr.artifacts.artifact_writer import SDRArtifactWriter
from app.services.sdr.contracts.enrichment import (
    EnrichmentDecisionType,
    EnrichmentMaterialization,
    EnrichmentStatus,
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
    SemanticColumnRole,
    SemanticConcept,
    SemanticDtype,
    SemanticEntityType,
    SourceCoordinateRef,
)
from app.services.sdr.enrichment.enrichment_engine import SDREnrichmentEngine
from app.services.sdr.enrichment.provider import EnrichmentProviderRegistry
from app.services.sdr.geo.contracts import (
    GeoLevel,
    GeoMatchMethod,
    GeoResolutionStatus,
)
from app.services.sdr.geo.geo_provider import GeoEnrichmentProvider
from app.services.sdr.geo.hierarchy_validator import GeoHierarchyValidator
from app.services.sdr.geo.normalizer import is_ambiguous_short_code, normalize_for_lookup
from app.services.sdr.geo.reference_store import GeoReferenceStore
from app.services.sdr.geo.resolver import GeoResolutionEngine
from app.services.sdr.retrieval.retrieval_adapter import SDRRetrievalAdapter

P0_EXPECTED_SHA = "1561d64eeae26f4d30926371740d6ca9dc41eb6ea7c537281763b7d5aabd9496"
P0_EXPECTED_SIZE = 70385664


def _create_geo_profile(
    dataset_id: str,
    sheet_id: str,
    column_id: str,
    source_name: str,
    role: SemanticColumnRole = SemanticColumnRole.LOCATION,
    dtype: SemanticDtype = SemanticDtype.GEOGRAPHIC_LOCATION,
    concept: SemanticConcept = SemanticConcept.LOCATION_ATTRIBUTE,
    privacy: PrivacyClassification = PrivacyClassification.GENERAL_ATTRIBUTE,
    sample_values: list[str] | None = None,
) -> SemanticColumnProfile:
    samples = sample_values or ["Bengaluru", "Mumbai"]
    features = DeterministicColumnFeatures(
        row_count=len(samples),
        null_count=0,
        null_ratio=0.0,
        distinct_count=len(set(samples)),
        distinct_ratio=len(set(samples)) / max(len(samples), 1),
        sample_values=samples[:5],
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
        entity_type_hypothesis=SemanticEntityType.LOCATION,
        privacy_classification=privacy,
        confidence=0.95,
        ambiguity_state=ProfilingAmbiguityState.CLEAR,
        features=features,
        source_lineage=SourceCoordinateRef(
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            column_ids=[column_id],
            source_file_hash="hash_geo_cert",
        ),
        profile_id=f"prof_{column_id}",
        artifact_fingerprint=f"fp_{column_id}",
    )


# =========================================================================
# 1. CANONICAL RESOLUTION CERTIFICATION
# =========================================================================

def test_canonical_city_state_country_and_aliases():
    """Certify primary global benchmark locations resolve deterministically with canonical & historical aliases."""
    engine = GeoResolutionEngine()

    test_matrix = [
        # (input_city, state_ctx, country_ctx, expected_id, expected_canonical, expected_country, expected_admin1)
        ("Bengaluru", "KA", "IN", "GEO-CITY-IN-BLR", "Bengaluru", "IN", "KA"),
        ("Bangalore", None, "India", "GEO-CITY-IN-BLR", "Bengaluru", "IN", "KA"),
        ("Mumbai", None, "India", "GEO-CITY-IN-BOM", "Mumbai", "IN", "MH"),
        ("Bombay", None, "IN", "GEO-CITY-IN-BOM", "Mumbai", "IN", "MH"),
        ("Kolkata", None, "India", "GEO-CITY-IN-CCU", "Kolkata", "IN", "WB"),
        ("Calcutta", None, "India", "GEO-CITY-IN-CCU", "Kolkata", "IN", "WB"),
        ("London", None, "United Kingdom", "GEO-CITY-GB-LON", "London", "GB", "ENG"),
        ("Paris", None, "France", "GEO-CITY-FR-PAR", "Paris", "FR", "IDF"),
        ("Austin", "TX", "United States", "GEO-CITY-US-AUS", "Austin", "US", "TX"),
        ("Sydney", "NSW", "Australia", "GEO-CITY-AU-SYD", "Sydney", "AU", "NSW"),
        ("Singapore", None, "Singapore", "GEO-CITY-SG-SIN", "Singapore", "SG", None),
        ("Tokyo", None, "Japan", "GEO-CITY-JP-TYO", "Tokyo", "JP", "13"),
    ]

    for city_in, state_in, ctry_in, exp_id, exp_canon, exp_ctry, exp_adm1 in test_matrix:
        cand = engine.resolve_city(city_in, state_context=state_in, country_context=ctry_in)
        assert cand.resolution_status == GeoResolutionStatus.RESOLVED, f"Failed for {city_in}: status={cand.resolution_status}"
        assert cand.resolved_entity_id == exp_id, f"Failed for {city_in}: got {cand.resolved_entity_id}, expected {exp_id}"
        assert cand.confidence >= 0.90

        ent = engine.store.get_entity(cand.resolved_entity_id)
        assert ent is not None
        assert ent.canonical_name == exp_canon
        assert ent.country_code == exp_ctry
        assert ent.admin1_code == exp_adm1


def test_iso_code_coverage_and_invariance():
    """Certify ISO-2 and ISO-3 resolution invariance across major global jurisdictions."""
    engine = GeoResolutionEngine()
    iso_pairs = [
        ("IN", "IND", "GEO-CTRY-IN", "India"),
        ("US", "USA", "GEO-CTRY-US", "United States"),
        ("GB", "GBR", "GEO-CTRY-GB", "United Kingdom"),
        ("FR", "FRA", "GEO-CTRY-FR", "France"),
        ("DE", "DEU", "GEO-CTRY-DE", "Germany"),
        ("AU", "AUS", "GEO-CTRY-AU", "Australia"),
        ("SG", "SGP", "GEO-CTRY-SG", "Singapore"),
        ("JP", "JPN", "GEO-CTRY-JP", "Japan"),
    ]

    for alpha2, alpha3, exp_id, exp_name in iso_pairs:
        res2 = engine.resolve_country(alpha2)
        res3 = engine.resolve_country(alpha3)
        res_name = engine.resolve_country(exp_name)

        assert res2.resolution_status == GeoResolutionStatus.RESOLVED
        assert res3.resolution_status == GeoResolutionStatus.RESOLVED
        assert res_name.resolution_status == GeoResolutionStatus.RESOLVED

        assert res2.resolved_entity_id == exp_id
        assert res3.resolved_entity_id == exp_id
        assert res_name.resolved_entity_id == exp_id

        assert res2.match_method == GeoMatchMethod.ISO_CODE
        assert res3.match_method == GeoMatchMethod.ISO_CODE


# =========================================================================
# 2. AMBIGUITY ABSTENTION & FALSE POSITIVE PROTECTION
# =========================================================================

def test_ambiguity_abstention_corpus():
    """Springfield, Georgia, Washington, Cambridge without context MUST abstain with AMBIGUOUS status."""
    engine = GeoResolutionEngine()

    # 1. Springfield (alone)
    res_sp = engine.resolve_token("Springfield")
    assert res_sp.resolution_status == GeoResolutionStatus.AMBIGUOUS
    assert res_sp.candidate_count >= 2
    assert res_sp.resolved_entity_id is None

    # Springfield disambiguated with Illinois
    res_sp_il = engine.resolve_token("Springfield", state_context="Illinois", country_context="United States")
    assert res_sp_il.resolution_status == GeoResolutionStatus.RESOLVED
    assert res_sp_il.resolved_entity_id == "GEO-CITY-US-SPRINGFIELD-IL"

    # 2. Georgia (alone)
    res_ga = engine.resolve_token("Georgia")
    assert res_ga.resolution_status == GeoResolutionStatus.AMBIGUOUS
    assert res_ga.candidate_count >= 2
    assert res_ga.resolved_entity_id is None

    # Georgia disambiguated with country context United States -> State Georgia
    res_ga_us = engine.resolve_token("Georgia", country_context="United States")
    assert res_ga_us.resolution_status == GeoResolutionStatus.RESOLVED
    assert res_ga_us.resolved_entity_id == "GEO-ADM1-US-GA"

    # 3. Washington (alone)
    res_wa = engine.resolve_token("Washington")
    assert res_wa.resolution_status == GeoResolutionStatus.AMBIGUOUS
    assert res_wa.candidate_count >= 2

    # 4. Cambridge (alone)
    res_cam = engine.resolve_token("Cambridge")
    assert res_cam.resolution_status == GeoResolutionStatus.AMBIGUOUS
    assert res_cam.candidate_count >= 2

    # Cambridge disambiguated with UK
    res_cam_uk = engine.resolve_token("Cambridge", country_context="United Kingdom")
    assert res_cam_uk.resolution_status == GeoResolutionStatus.RESOLVED
    assert res_cam_uk.resolved_entity_id == "GEO-CITY-GB-CAM"


def test_short_code_and_non_geo_false_positive_protection():
    """
    Ensure non-geographic columns and short 2-letter tokens never cause false geographic matches.
    """
    engine = GeoResolutionEngine()

    # Non-geographic column profiles
    name_col = _create_geo_profile(
        dataset_id="ds_test",
        sheet_id="sheet1",
        column_id="col_name",
        source_name="first_name",
        role=SemanticColumnRole.FREE_TEXT,
        dtype=SemanticDtype.NATURAL_LANGUAGE_TEXT,
        concept=SemanticConcept.DESCRIPTOR,
    )
    prod_col = _create_geo_profile(
        dataset_id="ds_test",
        sheet_id="sheet1",
        column_id="col_prod",
        source_name="product_category",
        role=SemanticColumnRole.DIMENSION,
        dtype=SemanticDtype.CATEGORICAL_CODE,
        concept=SemanticConcept.DESCRIPTOR,
    )

    false_positive_cases = [
        ("Jordan", name_col),
        ("Turkey", prod_col),
        ("Georgia", name_col),
        ("Reading", prod_col),
        ("Mobile", prod_col),
        ("Bath", prod_col),
        ("Orange", prod_col),
        ("Gary", name_col),
    ]

    for token, profile in false_positive_cases:
        res = engine.resolve_token(token, column_profile=profile)
        assert res.resolution_status == GeoResolutionStatus.UNRESOLVED
        assert res.confidence == 0.0
        assert res.resolved_entity_id is None
        assert "Non-geographic false positive guard" in res.disambiguation_evidence[0]

    # Unknown tokens
    res_atl = engine.resolve_token("Atlantis")
    assert res_atl.resolution_status == GeoResolutionStatus.UNRESOLVED
    assert res_atl.confidence == 0.0


# =========================================================================
# 3. HIERARCHICAL CONFLICT REJECTION
# =========================================================================

def test_hierarchical_conflict_validation():
    """Cross-column topological conflict (e.g. Bengaluru, California, India) must be rejected with INVALID status."""
    engine = GeoResolutionEngine()
    validator = GeoHierarchyValidator(engine.store)

    # Valid hierarchy
    valid_res = validator.validate_hierarchy(city="Bengaluru", state="Karnataka", country="India")
    assert valid_res.is_valid is True
    assert valid_res.status == GeoResolutionStatus.RESOLVED
    assert len(valid_res.conflicts) == 0

    # Conflicting hierarchy A: City in India, State in US
    invalid_a = validator.validate_hierarchy(city="Bengaluru", state="California", country="India")
    assert invalid_a.is_valid is False
    assert invalid_a.status == GeoResolutionStatus.INVALID
    assert len(invalid_a.conflicts) >= 1
    assert any("Hierarchy conflict" in c for c in invalid_a.conflicts)

    # Conflicting hierarchy B: City in US, State in India
    invalid_b = validator.validate_hierarchy(city="Austin", state="Karnataka", country="United States")
    assert invalid_b.is_valid is False
    assert invalid_b.status == GeoResolutionStatus.INVALID
    assert len(invalid_b.conflicts) >= 1


# =========================================================================
# 4. GOVERNED ENRICHMENT PROVIDER & POLICY ENGINE INTEGRATION
# =========================================================================

def test_governed_enrichment_provider_with_sdr_policy_engine():
    """
    Certify GeoEnrichmentProvider integrates with SDR-4 policy engine:
    1. Pre-enrichment hard gates prevent sensitive inferences.
    2. Derived enrichments strictly use ENRICH-GEO-* prefixes.
    3. Source values remain 100% immutable (OBSERVED != RESOLVED != DERIVED).
    4. Accepted enrichments default to VIRTUAL_ENRICHMENT materialization.
    """
    registry = EnrichmentProviderRegistry()
    geo_provider = GeoEnrichmentProvider()
    registry.register_provider(geo_provider)

    policy_suite = SDRPolicySuite(
        enrichment=EnrichmentPolicy(
            max_candidates_per_column=5,
            max_enrichments_per_column=5,
            max_enrichment_depth=2,
            min_utility_score=0.40,
        )
    )

    sdr_engine = SDREnrichmentEngine(registry=registry, policy=policy_suite.enrichment)

    dataset_id = "ds_geo_hr"
    sheet_id = "employees"
    city_col = _create_geo_profile(
        dataset_id=dataset_id,
        sheet_id=sheet_id,
        column_id="col_city",
        source_name="work_city",
        sample_values=["Bengaluru", "Mumbai", "London", "Austin", "Paris"],
    )

    result = sdr_engine.analyze_enrichments(
        dataset_id=dataset_id,
        sheet_id=sheet_id,
        profiles=[city_col],
        policy_suite=policy_suite,
    )

    # Verify candidate generation
    assert len(result.candidates) >= 4
    for cand in result.candidates:
        assert cand.proposed_enrichment_type.startswith("CITY_TO_")
        assert cand.provider_id == "provider_geo_resolver"

    # Verify validation and decisions
    assert len(result.validated_enrichments) >= 4
    for val in result.validated_enrichments:
        assert val.output_name.startswith("ENRICH-GEO-")
        assert val.materialization == EnrichmentMaterialization.VIRTUAL_ENRICHMENT
        assert val.confidence >= 0.80
        assert val.is_valid is True

    for dec in result.decisions:
        assert dec.decision == EnrichmentDecisionType.ACCEPT
        assert dec.analytical_utility >= 0.40
        assert dec.net_information_gain > 0.0

    # Confirm source column was NOT modified
    assert city_col.source_name == "work_city"
    assert city_col.column_id == "col_city"

    # Test resolution execution through provider
    city_to_state_cand = [c for c in result.candidates if c.proposed_enrichment_type == "CITY_TO_STATE"][0]
    resolved_states = geo_provider.resolve(city_to_state_cand, values=["Bengaluru", "London", "Paris", "Austin"])
    assert resolved_states == ["Karnataka", "England", "Île-de-France", "Texas"]


# =========================================================================
# 5. HIGH-SCALE DEDUPLICATION & PERFORMANCE BENCHMARK
# =========================================================================

def test_deduplication_and_cache_efficiency():
    """
    Certify value deduplication:
    Resolving 10,000 rows containing 5 distinct cities executes in < 100ms.
    Also verifies underlying resolution cache hit ratio on repeated token calls.
    """
    provider = GeoEnrichmentProvider()
    city_prof = _create_geo_profile("ds", "sh", "col_c", "office_city")
    candidates = provider.generate_candidates("ds", "sh", city_prof, sample_values=["Bengaluru", "London"])
    cand = [c for c in candidates if c.proposed_enrichment_type == "CITY_TO_COUNTRY"][0]

    # Generate 10,000 rows with 5 unique cities
    distinct_cities = ["Bengaluru", "London", "Paris", "Austin", "Tokyo"]
    large_dataset = [distinct_cities[i % len(distinct_cities)] for i in range(10000)]

    tracemalloc.start()
    start_time = time.perf_counter()

    resolved = provider.resolve(cand, large_dataset)

    duration_ms = (time.perf_counter() - start_time) * 1000
    _, peak_memory = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert len(resolved) == 10000
    assert resolved[0] == "India"
    assert resolved[1] == "United Kingdom"
    assert resolved[2] == "France"
    assert resolved[3] == "United States"
    assert resolved[4] == "Japan"

    # Performance assertions
    assert duration_ms < 100.0, f"Deduplicated resolution took {duration_ms:.2f}ms (expected < 100ms)"
    assert peak_memory < 15 * 1024 * 1024, f"Peak memory {peak_memory / 1024 / 1024:.2f}MB exceeded 15MB limit"

    # Test engine cache hits on direct repeated lookups
    engine = GeoResolutionEngine()
    for city in large_dataset:
        engine.resolve_token(city, expected_level=GeoLevel.CITY)

    assert engine._cache_misses == 5
    assert engine._cache_hits == 9995


# =========================================================================
# 6. REPEAT-RUN DETERMINISM PROOF
# =========================================================================

def test_repeat_run_artifact_determinism(tmp_path: Path):
    """
    Prove that independent runs across separate output directories generate 100% byte-identical artifacts.
    """
    run1_dir = tmp_path / "run1"
    run2_dir = tmp_path / "run2"

    provider = GeoEnrichmentProvider()
    city_prof = _create_geo_profile("ds_cert", "sheet1", "col_city", "city")
    candidates = provider.generate_candidates("ds_cert", "sheet1", city_prof, sample_values=["Bengaluru", "Mumbai"])

    # Generate resolutions
    resolutions = [
        provider.resolver.resolve_token("Bengaluru"),
        provider.resolver.resolve_token("Mumbai"),
        provider.resolver.resolve_token("Springfield"),
    ]
    canonical_entities = [provider.resolver.store.get_entity(r.resolved_entity_id) for r in resolutions if r.resolved_entity_id]

    writer1 = SDRArtifactWriter(base_dir=run1_dir)
    paths1 = writer1.write_sdr4g_artifacts(
        dataset_id="ds_cert",
        sheet_id="sheet1",
        resolutions=resolutions,
        canonical_entities=canonical_entities,
    )

    writer2 = SDRArtifactWriter(base_dir=run2_dir)
    paths2 = writer2.write_sdr4g_artifacts(
        dataset_id="ds_cert",
        sheet_id="sheet1",
        resolutions=resolutions,
        canonical_entities=canonical_entities,
    )

    def file_sha256(p: Path) -> str:
        h = hashlib.sha256()
        with open(p, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    for key in ("geo_resolutions", "canonical_geo_entities", "geo_manifest"):
        sha1 = file_sha256(paths1[key])
        sha2 = file_sha256(paths2[key])
        assert sha1 == sha2, f"Artifact {key} SHA mismatch: {sha1} != {sha2}"


# =========================================================================
# 7. RETRIEVAL INDEX CONTAINMENT PROOF
# =========================================================================

def test_retrieval_index_containment():
    """Prove SDR-4G documents emit strictly into SEMANTIC_INDEX, with 0 docs in other indexes."""
    adapter = SDRRetrievalAdapter()
    engine = GeoResolutionEngine()

    cand = engine.resolve_city("Bengaluru", country_context="India")
    ent = engine.store.get_entity(cand.resolved_entity_id)

    res_doc = adapter.build_geo_resolution_document(cand, dataset_id="ds_cert", sheet_id="sheet1")
    ent_doc = adapter.build_canonical_geo_document(ent, dataset_id="ds_cert")

    # Both documents must target SEMANTIC namespace exclusively
    from app.services.ingestion_v2.retrieval.namespaces import RetrievalNamespace
    assert res_doc.namespace == RetrievalNamespace.SEMANTIC
    assert ent_doc.namespace == RetrievalNamespace.SEMANTIC

    # Confirm no relationship, analytical, or raw schema indexes are targeted
    for doc in (res_doc, ent_doc):
        assert doc.namespace not in (
            RetrievalNamespace.RELATIONSHIP,
            RetrievalNamespace.ANALYTICAL,
            RetrievalNamespace.RAW_SCHEMA,
        )


# =========================================================================
# 8. P0 ISOLATION CHECK
# =========================================================================

def test_p0_database_isolation():
    """Verify primary application database pulsehr.sqlite3 remains 100% byte-identical."""
    p0_path = Path("backend/data/db/pulsehr.sqlite3")
    if p0_path.exists():
        hasher = hashlib.sha256()
        with open(p0_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        assert hasher.hexdigest() == P0_EXPECTED_SHA
        assert p0_path.stat().st_size == P0_EXPECTED_SIZE
