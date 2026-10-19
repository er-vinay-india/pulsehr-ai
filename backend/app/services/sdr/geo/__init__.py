"""
HighView Semantic Data Refinery — Phase SDR-4G
Geographic Semantic Resolver & Offline Enrichment Package (GEO-1)
"""

from app.services.sdr.geo.contracts import (
    CanonicalGeoEntity,
    GeoLevel,
    GeoMatchMethod,
    GeoResolutionCandidate,
    GeoResolutionStatus,
    compute_canonical_geo_entity_fingerprint,
    compute_geo_resolution_fingerprint,
)
from app.services.sdr.geo.geo_provider import GeoEnrichmentProvider
from app.services.sdr.geo.hierarchy_validator import GeoHierarchyValidator
from app.services.sdr.geo.normalizer import (
    is_ambiguous_short_code,
    normalize_for_lookup,
    normalize_geo_text,
)
from app.services.sdr.geo.reference_store import GeoReferenceStore
from app.services.sdr.geo.resolver import GeoResolutionEngine

__all__ = [
    "CanonicalGeoEntity",
    "GeoLevel",
    "GeoMatchMethod",
    "GeoResolutionCandidate",
    "GeoResolutionStatus",
    "compute_canonical_geo_entity_fingerprint",
    "compute_geo_resolution_fingerprint",
    "GeoEnrichmentProvider",
    "GeoHierarchyValidator",
    "is_ambiguous_short_code",
    "normalize_for_lookup",
    "normalize_geo_text",
    "GeoReferenceStore",
    "GeoResolutionEngine",
]
