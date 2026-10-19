"""
Unit Tests for SDR-4G GEO-1 Geographic Semantic Resolver.
Tests canonical country, state, and city resolution, aliases, ISO codes,
ambiguity abstention, hierarchy conflicts, cache correctness, and non-geo protection.
"""

import pytest
from app.services.sdr.contracts.profiles import (
    DeterministicColumnFeatures,
    PrivacyClassification,
    ProfilingAmbiguityState,
    SemanticColumnProfile,
    SemanticColumnRole,
    SemanticConcept,
    SemanticDtype,
    SourceCoordinateRef,
)
from app.services.sdr.geo.contracts import (
    GeoLevel,
    GeoMatchMethod,
    GeoResolutionStatus,
)
from app.services.sdr.geo.geo_provider import GeoEnrichmentProvider
from app.services.sdr.geo.normalizer import is_ambiguous_short_code, normalize_for_lookup
from app.services.sdr.geo.reference_store import GeoReferenceStore
from app.services.sdr.geo.resolver import GeoResolutionEngine


def _make_geo_profile(col_id: str, col_name: str, role: SemanticColumnRole = SemanticColumnRole.LOCATION) -> SemanticColumnProfile:
    features = DeterministicColumnFeatures(
        row_count=10,
        null_count=0,
        null_ratio=0.0,
        distinct_count=10,
        distinct_ratio=1.0,
        sample_values=["sample"],
    )
    return SemanticColumnProfile(
        dataset_id="ds_geo",
        sheet_id="sheet1",
        column_id=col_id,
        source_name=col_name,
        canonical_name=col_name.lower(),
        physical_dtype="VARCHAR",
        semantic_dtype=SemanticDtype.GEOGRAPHIC_LOCATION,
        semantic_role=role,
        semantic_concept=SemanticConcept.LOCATION_ATTRIBUTE,
        confidence=0.95,
        ambiguity_state=ProfilingAmbiguityState.CLEAR,
        features=features,
        source_lineage=SourceCoordinateRef(
            dataset_id="ds_geo",
            sheet_id="sheet1",
            column_ids=[col_id],
            source_file_hash="hash_geo",
        ),
        profile_id=f"prof_{col_id}",
        artifact_fingerprint=f"fp_{col_id}",
    )


def test_canonical_country_and_iso_code_resolution():
    """Valid country names and ISO alpha-2/3 codes resolve with 0 ambiguity."""
    engine = GeoResolutionEngine()

    # Canonical name
    res_in = engine.resolve_country("India")
    assert res_in.resolution_status == GeoResolutionStatus.RESOLVED
    assert res_in.resolved_entity_id == "GEO-CTRY-IN"
    assert res_in.confidence == 1.0

    # ISO-2
    res_in_code = engine.resolve_country("IN")
    assert res_in_code.resolution_status == GeoResolutionStatus.RESOLVED
    assert res_in_code.resolved_entity_id == "GEO-CTRY-IN"
    assert res_in_code.match_method == GeoMatchMethod.ISO_CODE

    # ISO-3
    res_in_alpha3 = engine.resolve_country("IND")
    assert res_in_alpha3.resolution_status == GeoResolutionStatus.RESOLVED
    assert res_in_alpha3.resolved_entity_id == "GEO-CTRY-IN"

    # US canonical and codes
    for token in ["United States", "USA", "US", "United States of America"]:
        res_us = engine.resolve_country(token)
        assert res_us.resolution_status == GeoResolutionStatus.RESOLVED
        assert res_us.resolved_entity_id == "GEO-CTRY-US"

    # UK canonical and codes
    for token in ["United Kingdom", "UK", "GBR", "GB"]:
        res_gb = engine.resolve_country(token)
        assert res_gb.resolution_status == GeoResolutionStatus.RESOLVED
        assert res_gb.resolved_entity_id == "GEO-CTRY-GB"


def test_city_resolution_with_aliases():
    """Historical and common city aliases resolve to single canonical entity."""
    engine = GeoResolutionEngine()

    # Bangalore -> Bengaluru
    res_blr1 = engine.resolve_token("Bengaluru")
    res_blr2 = engine.resolve_token("Bangalore")
    assert res_blr1.resolution_status == GeoResolutionStatus.RESOLVED
    assert res_blr2.resolution_status == GeoResolutionStatus.RESOLVED
    assert res_blr1.resolved_entity_id == "GEO-CITY-IN-BLR"
    assert res_blr2.resolved_entity_id == "GEO-CITY-IN-BLR"
    assert res_blr2.match_method == GeoMatchMethod.EXACT_ALIAS

    # Bombay -> Mumbai
    res_bom = engine.resolve_token("Bombay")
    assert res_bom.resolution_status == GeoResolutionStatus.RESOLVED
    assert res_bom.resolved_entity_id == "GEO-CITY-IN-BOM"

    # Calcutta -> Kolkata
    res_ccu = engine.resolve_token("Calcutta")
    assert res_ccu.resolution_status == GeoResolutionStatus.RESOLVED
    assert res_ccu.resolved_entity_id == "GEO-CITY-IN-CCU"


def test_state_resolution_with_country_context():
    """State/province names and codes resolve safely when country context is provided."""
    engine = GeoResolutionEngine()

    # Karnataka in India
    res_ka = engine.resolve_token("Karnataka", country_context="India")
    assert res_ka.resolution_status == GeoResolutionStatus.RESOLVED
    assert res_ka.resolved_entity_id == "GEO-ADM1-IN-KA"

    # Texas in United States
    res_tx = engine.resolve_token("Texas", country_context="United States")
    assert res_tx.resolution_status == GeoResolutionStatus.RESOLVED
    assert res_tx.resolved_entity_id == "GEO-ADM1-US-TX"

    # CA with United States context -> California
    res_ca_us = engine.resolve_token("CA", country_context="United States")
    assert res_ca_us.resolution_status == GeoResolutionStatus.RESOLVED
    assert res_ca_us.resolved_entity_id == "GEO-ADM1-US-CA"

    # CA without context -> Ambiguous (could be Canada or California)
    res_ca_raw = engine.resolve_token("CA")
    assert res_ca_raw.resolution_status == GeoResolutionStatus.AMBIGUOUS


def test_ambiguity_abstention_springfield():
    """Springfield without state/country context must abstain with AMBIGUOUS status."""
    engine = GeoResolutionEngine()

    # Springfield alone -> AMBIGUOUS
    res_raw = engine.resolve_token("Springfield")
    assert res_raw.resolution_status == GeoResolutionStatus.AMBIGUOUS
    assert res_raw.candidate_count >= 2
    assert res_raw.resolved_entity_id is None

    # Springfield with Illinois context -> RESOLVED
    res_il = engine.resolve_token("Springfield", state_context="Illinois", country_context="United States")
    assert res_il.resolution_status == GeoResolutionStatus.RESOLVED
    assert res_il.resolved_entity_id == "GEO-CITY-US-SPRINGFIELD-IL"

    # Springfield with Missouri context -> RESOLVED
    res_mo = engine.resolve_token("Springfield", state_context="Missouri", country_context="United States")
    assert res_mo.resolution_status == GeoResolutionStatus.RESOLVED
    assert res_mo.resolved_entity_id == "GEO-CITY-US-SPRINGFIELD-MO"


def test_ambiguity_abstention_georgia_and_washington():
    """Georgia (Country vs State) and Washington (State vs DC) must abstain without context."""
    engine = GeoResolutionEngine()

    # Georgia without context -> AMBIGUOUS
    res_georgia = engine.resolve_token("Georgia")
    assert res_georgia.resolution_status == GeoResolutionStatus.AMBIGUOUS
    assert res_georgia.candidate_count >= 2

    # Georgia with country context US -> US State Georgia
    res_georgia_us = engine.resolve_token("Georgia", country_context="United States")
    assert res_georgia_us.resolution_status == GeoResolutionStatus.RESOLVED
    assert res_georgia_us.resolved_entity_id == "GEO-ADM1-US-GA"

    # Washington without context -> AMBIGUOUS
    res_wash = engine.resolve_token("Washington")
    assert res_wash.resolution_status == GeoResolutionStatus.AMBIGUOUS


def test_non_geographic_false_positive_protection():
    """Non-geographic words (Georgia, Jordan, Turkey, Chad) are rejected in non-location columns."""
    engine = GeoResolutionEngine()

    non_geo_prof = _make_profile("col_text", "description", role=SemanticColumnRole.FREE_TEXT)

    for word in ["Georgia", "Jordan", "Turkey", "Chad"]:
        res = engine.resolve_token(word, column_profile=non_geo_prof)
        assert res.resolution_status == GeoResolutionStatus.UNRESOLVED
        assert res.resolved_entity_id is None
        assert "Non-geographic false positive guard" in res.disambiguation_evidence[0]


def test_hierarchy_consistency_and_conflict_rejection():
    """Hierarchically consistent locations pass; contradictory hierarchies are strictly rejected."""
    engine = GeoResolutionEngine()

    # Consistent: Bengaluru - Karnataka - India
    status_ok, parts_ok, _ = engine.resolve_composite_hierarchy("Bengaluru - Karnataka - India")
    assert status_ok == GeoResolutionStatus.RESOLVED
    assert len(parts_ok) == 3

    # Conflicting: Bengaluru - California - India
    status_bad, parts_bad, reasons = engine.resolve_composite_hierarchy("Bengaluru - California - India")
    assert status_bad == GeoResolutionStatus.INVALID
    assert len(reasons) >= 1
    assert any("does not belong" in r or "conflict" in r.lower() for r in reasons)


def test_unknown_location_abstention():
    """Completely synthetic or non-existent geographic locations yield UNRESOLVED."""
    engine = GeoResolutionEngine()

    res = engine.resolve_token("Xylophonia Atlantis City")
    assert res.resolution_status == GeoResolutionStatus.UNRESOLVED
    assert res.resolved_entity_id is None
    assert res.confidence == 0.0


def test_value_deduplication_and_cache_correctness():
    """Resolving repeated rows queries the cache and increments cache hits."""
    engine = GeoResolutionEngine()

    res1 = engine.resolve_token("Bengaluru")
    res2 = engine.resolve_token("Bengaluru")
    res3 = engine.resolve_token("Bengaluru")

    assert res1.resolved_entity_id == res2.resolved_entity_id == res3.resolved_entity_id
    stats = engine.get_cache_stats()
    assert stats["cache_entries"] >= 1
    assert stats["cache_hits"] >= 2


def test_geo_enrichment_provider_integration():
    """GeoEnrichmentProvider integrates with SDR-4 enrichment contracts."""
    provider = GeoEnrichmentProvider()
    city_prof = _make_geo_profile("col_city", "office_city")

    candidates = provider.generate_candidates(
        dataset_id="ds_test",
        sheet_id="sheet1",
        profile=city_prof,
        sample_values=["Bengaluru", "Mumbai", "London"],
    )

    assert len(candidates) >= 3
    types = {c.proposed_enrichment_type for c in candidates}
    assert "CITY_TO_STATE" in types
    assert "CITY_TO_COUNTRY" in types
    assert "CITY_TO_REF_LATITUDE" in types
    assert "CITY_TO_TIMEZONE" in types

    # Resolve values with deduplication
    city_to_country_cand = [c for c in candidates if c.proposed_enrichment_type == "CITY_TO_COUNTRY"][0]
    resolved_vals = provider.resolve(city_to_country_cand, values=["Bengaluru", "London", "Bengaluru", "Mumbai"])
    assert resolved_vals == ["India", "United Kingdom", "India", "India"]


def test_reference_coordinates_and_timezone_governance():
    """Centroid coordinates are reference points, not precise personal locations."""
    provider = GeoEnrichmentProvider()
    city_prof = _make_geo_profile("col_city", "city")

    candidates = provider.generate_candidates(
        dataset_id="ds_test",
        sheet_id="sheet1",
        profile=city_prof,
        sample_values=["Austin"],
    )

    lat_cand = [c for c in candidates if c.proposed_enrichment_type == "CITY_TO_REF_LATITUDE"][0]
    resolved_lat = provider.resolve(lat_cand, values=["Austin"])[0]
    assert resolved_lat == pytest.approx(30.2672, abs=0.01)

    tz_cand = [c for c in candidates if c.proposed_enrichment_type == "CITY_TO_TIMEZONE"][0]
    resolved_tz = provider.resolve(tz_cand, values=["Austin"])[0]
    assert resolved_tz == "America/Chicago"


def _make_profile(col_id: str, col_name: str, role: SemanticColumnRole, dtype: SemanticDtype = SemanticDtype.NATURAL_LANGUAGE_TEXT) -> SemanticColumnProfile:
    features = DeterministicColumnFeatures(
        row_count=10, null_count=0, null_ratio=0.0, distinct_count=10, distinct_ratio=1.0, sample_values=["v"]
    )
    return SemanticColumnProfile(
        dataset_id="ds_test", sheet_id="sheet1", column_id=col_id, source_name=col_name,
        canonical_name=col_name.lower(), physical_dtype="VARCHAR", semantic_dtype=dtype,
        semantic_role=role, semantic_concept=SemanticConcept.DESCRIPTOR,
        confidence=0.95, features=features,
        source_lineage=SourceCoordinateRef(dataset_id="ds_test", sheet_id="sheet1", column_ids=[col_id], source_file_hash="h"),
        profile_id=f"prof_{col_id}", artifact_fingerprint=f"fp_{col_id}",
    )

