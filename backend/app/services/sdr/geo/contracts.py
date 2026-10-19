"""
HighView Semantic Data Refinery — Phase SDR-4G
Geographic Semantic Contracts (GEO-1)

EPISTEMIC RULE:
OBSERVED GEOGRAPHY != RESOLVED GEOGRAPHY != DERIVED GEOGRAPHY
Never overwrite observed source values.
"""

from __future__ import annotations

from enum import Enum
import hashlib
import json
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class GeoLevel(str, Enum):
    """
    Geographic administrative hierarchy level.
    Strictly decoupled from storage representations.
    """
    COUNTRY = "COUNTRY"               # Nation / Sovereign State (Admin 0)
    ADMIN1 = "ADMIN1"                 # State / Province / Region (Admin 1)
    ADMIN2 = "ADMIN2"                 # County / District / Prefecture (Admin 2)
    CITY = "CITY"                     # Municipality / Urban agglomeration / Populated place
    POSTAL_CODE = "POSTAL_CODE"       # Postal code / ZIP code
    LATITUDE = "LATITUDE"             # Derived centroid latitude
    LONGITUDE = "LONGITUDE"           # Derived centroid longitude
    REGION = "REGION"                 # Continental / Supranational region
    TIMEZONE = "TIMEZONE"             # IANA Timezone ID
    UNKNOWN = "UNKNOWN"


class GeoResolutionStatus(str, Enum):
    """Lifecycle status of a geographic resolution candidate."""
    RESOLVED = "RESOLVED"       # Deterministically resolved to exactly one canonical geo entity
    AMBIGUOUS = "AMBIGUOUS"     # Multiple plausible candidate entities exist without disambiguating context
    UNRESOLVED = "UNRESOLVED"   # Value does not match reference data
    INVALID = "INVALID"         # Hierarchical conflict (e.g. City in Country A paired with Country B)


class GeoMatchMethod(str, Enum):
    """Method used to resolve the source token against reference evidence."""
    EXACT_CANONICAL = "EXACT_CANONICAL"
    EXACT_ALIAS = "EXACT_ALIAS"
    ISO_CODE = "ISO_CODE"
    HIERARCHICAL_CONTEXT = "HIERARCHICAL_CONTEXT"
    PHONE_PREFIX_HINT = "PHONE_PREFIX_HINT"
    FUZZY = "FUZZY"
    NONE = "NONE"


class CanonicalGeoEntity(BaseModel):
    """
    Authoritative reference entity representing a ground-truth geographic entity.
    Originates from versioned local reference stores (GeoNames / Natural Earth / geoBoundaries).
    """
    model_config = ConfigDict(frozen=True)

    geo_entity_id: str
    level: GeoLevel
    canonical_name: str
    display_name: str
    country_code: str                          # ISO 3166-1 alpha-2 (e.g. 'IN', 'US', 'GB')
    country_code_alpha3: str = ""              # ISO 3166-1 alpha-3 (e.g. 'IND', 'USA', 'GBR')
    admin1_code: str | None = None             # State/Province code (e.g. 'KA', 'TX', 'ENG')
    admin2_code: str | None = None
    parent_geo_entity_id: str | None = None    # Direct hierarchical parent (e.g. State -> Country)
    latitude: float | None = None              # CITY_REFERENCE_POINT or country/state centroid
    longitude: float | None = None
    timezone: str | None = None                # IANA Timezone (e.g. 'Asia/Kolkata', 'America/Chicago')
    reference_source: str = "GeoNames+NaturalEarth"
    reference_version: str = "2026.1"
    aliases: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    artifact_fingerprint: str = ""


class GeoResolutionCandidate(BaseModel):
    """
    Record of geographic resolution attempting to ground an observed value in reference geography.
    Preserves observed value verbatim and captures disambiguation evidence.
    """
    model_config = ConfigDict(frozen=True)

    source_value: str
    normalized_input: str
    candidate_geo_entity_ids: list[str] = Field(default_factory=list)
    resolved_entity_id: str | None = None
    candidate_count: int = 0
    resolution_status: GeoResolutionStatus = GeoResolutionStatus.UNRESOLVED
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    match_method: GeoMatchMethod = GeoMatchMethod.NONE
    disambiguation_evidence: list[str] = Field(default_factory=list)
    source_column_id: str = ""
    source_coordinate_refs: list[str] = Field(default_factory=list)
    provider_version: str = "1.0.0"
    reference_data_version: str = "2026.1"
    artifact_fingerprint: str = ""


def compute_canonical_geo_entity_fingerprint(entity: CanonicalGeoEntity) -> str:
    """Computes deterministic SHA-256 fingerprint for a canonical geo entity."""
    payload = {
        "geo_entity_id": entity.geo_entity_id,
        "level": entity.level.value,
        "canonical_name": entity.canonical_name,
        "country_code": entity.country_code,
        "admin1_code": entity.admin1_code,
        "parent_geo_entity_id": entity.parent_geo_entity_id,
        "latitude": round(entity.latitude, 4) if entity.latitude is not None else None,
        "longitude": round(entity.longitude, 4) if entity.longitude is not None else None,
        "reference_source": entity.reference_source,
        "reference_version": entity.reference_version,
        "aliases": sorted(entity.aliases),
    }
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def compute_geo_resolution_fingerprint(
    source_value: str,
    normalized_input: str,
    resolution_status: GeoResolutionStatus,
    resolved_entity_id: str | None,
    candidate_ids: list[str],
    provider_version: str,
    reference_data_version: str,
    policy_fingerprint: str = "",
) -> str:
    """Computes deterministic SHA-256 fingerprint for a geographic resolution candidate."""
    payload = {
        "source_value": source_value,
        "normalized_input": normalized_input,
        "resolution_status": resolution_status.value,
        "resolved_entity_id": resolved_entity_id,
        "candidate_ids": sorted(candidate_ids),
        "provider_version": provider_version,
        "reference_data_version": reference_data_version,
        "policy_fingerprint": policy_fingerprint,
    }
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
