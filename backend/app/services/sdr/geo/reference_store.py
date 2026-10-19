"""
HighView Semantic Data Refinery — Phase SDR-4G
Local Offline Geographic Reference Store (GEO-1)

Loads versioned, offline reference datasets (GeoNames, Natural Earth, geoBoundaries)
and builds deterministic in-memory indexes.
Zero external network calls during runtime.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.services.sdr.geo.contracts import (
    CanonicalGeoEntity,
    GeoLevel,
    compute_canonical_geo_entity_fingerprint,
)


DEFAULT_REFERENCE_PATH = Path(__file__).parent / "reference" / "geo_reference_data.json"


class GeoReferenceStore:
    """
    Offline local store managing indexed canonical geographic entities.
    Completely decoupled from primary application database (pulsehr.sqlite3).
    """

    def __init__(self, reference_data: dict[str, Any] | None = None, reference_path: Path | None = None):
        self.reference_path = reference_path or DEFAULT_REFERENCE_PATH
        if reference_data is not None:
            self.data = reference_data
        else:
            with open(self.reference_path, "r", encoding="utf-8") as f:
                self.data = json.load(f)

        self.metadata = self.data.get("metadata", {})
        self.reference_version = self.metadata.get("reference_version", "2026.1")

        # Core in-memory storage
        self.entities_by_id: dict[str, CanonicalGeoEntity] = {}
        self.entities_by_level: dict[GeoLevel, list[CanonicalGeoEntity]] = {lvl: [] for lvl in GeoLevel}

        # Multi-index structures for deterministic resolution
        self.countries_by_code: dict[str, CanonicalGeoEntity] = {}
        self.entities_by_canonical_name: dict[str, list[CanonicalGeoEntity]] = {}
        self.entities_by_alias: dict[str, list[CanonicalGeoEntity]] = {}
        self.phone_calling_codes: dict[str, str] = self.data.get("phone_calling_codes", {})

        self._build_indexes()
        self.store_fingerprint = self._compute_store_fingerprint()

    def _build_indexes(self) -> None:
        """Parses JSON data into CanonicalGeoEntity instances and builds search indexes."""
        # 1. Countries
        for item in self.data.get("countries", []):
            aliases = list(set(item.get("aliases", []) + [item["canonical_name"], item["country_code"], item["country_code_alpha3"]]))
            entity = CanonicalGeoEntity(
                geo_entity_id=item["geo_entity_id"],
                level=GeoLevel.COUNTRY,
                canonical_name=item["canonical_name"],
                display_name=item["display_name"],
                country_code=item["country_code"].upper(),
                country_code_alpha3=item.get("country_code_alpha3", "").upper(),
                latitude=item.get("latitude"),
                longitude=item.get("longitude"),
                timezone=item.get("timezone"),
                reference_source="NaturalEarth+GeoNames",
                reference_version=self.reference_version,
                aliases=aliases,
                confidence=1.0,
            )
            fp = compute_canonical_geo_entity_fingerprint(entity)
            entity = entity.model_copy(update={"artifact_fingerprint": fp})
            self._register_entity(entity)
            self.countries_by_code[entity.country_code] = entity
            if entity.country_code_alpha3:
                self.countries_by_code[entity.country_code_alpha3] = entity

        # 2. States / Admin1
        for item in self.data.get("states", []):
            aliases = list(set(item.get("aliases", []) + [item["canonical_name"]] + ([item["admin1_code"]] if item.get("admin1_code") else [])))
            entity = CanonicalGeoEntity(
                geo_entity_id=item["geo_entity_id"],
                level=GeoLevel.ADMIN1,
                canonical_name=item["canonical_name"],
                display_name=item["display_name"],
                country_code=item["country_code"].upper(),
                admin1_code=item.get("admin1_code"),
                parent_geo_entity_id=item.get("parent_geo_entity_id"),
                latitude=item.get("latitude"),
                longitude=item.get("longitude"),
                timezone=item.get("timezone"),
                reference_source="GeoNames+geoBoundaries",
                reference_version=self.reference_version,
                aliases=aliases,
                confidence=1.0,
            )
            fp = compute_canonical_geo_entity_fingerprint(entity)
            entity = entity.model_copy(update={"artifact_fingerprint": fp})
            self._register_entity(entity)

        # 3. Cities
        for item in self.data.get("cities", []):
            aliases = list(set(item.get("aliases", []) + [item["canonical_name"]]))
            entity = CanonicalGeoEntity(
                geo_entity_id=item["geo_entity_id"],
                level=GeoLevel.CITY,
                canonical_name=item["canonical_name"],
                display_name=item["display_name"],
                country_code=item["country_code"].upper(),
                admin1_code=item.get("admin1_code"),
                parent_geo_entity_id=item.get("parent_geo_entity_id"),
                latitude=item.get("latitude"),
                longitude=item.get("longitude"),
                timezone=item.get("timezone"),
                reference_source="GeoNames",
                reference_version=self.reference_version,
                aliases=aliases,
                confidence=1.0,
            )
            fp = compute_canonical_geo_entity_fingerprint(entity)
            entity = entity.model_copy(update={"artifact_fingerprint": fp})
            self._register_entity(entity)

    def _register_entity(self, entity: CanonicalGeoEntity) -> None:
        self.entities_by_id[entity.geo_entity_id] = entity
        self.entities_by_level[entity.level].append(entity)

        norm_canon = entity.canonical_name.strip().lower()
        self.entities_by_canonical_name.setdefault(norm_canon, []).append(entity)

        for alias in entity.aliases:
            norm_alias = alias.strip().lower()
            self.entities_by_alias.setdefault(norm_alias, []).append(entity)

    def _compute_store_fingerprint(self) -> str:
        """Deterministic fingerprint of entire reference dataset."""
        sorted_ids = sorted(self.entities_by_id.keys())
        payload = [self.entities_by_id[eid].artifact_fingerprint for eid in sorted_ids]
        raw = f"{self.reference_version}::" + "::".join(payload)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get_entity(self, geo_entity_id: str) -> CanonicalGeoEntity | None:
        return self.entities_by_id.get(geo_entity_id)

    def get_parent_entity(self, entity: CanonicalGeoEntity) -> CanonicalGeoEntity | None:
        if not entity.parent_geo_entity_id:
            return None
        return self.entities_by_id.get(entity.parent_geo_entity_id)

    def get_full_hierarchy(self, entity: CanonicalGeoEntity) -> list[CanonicalGeoEntity]:
        """Returns ascending hierarchy list: [entity, parent, grandparent, ...]"""
        chain = [entity]
        curr = entity
        while curr.parent_geo_entity_id and curr.parent_geo_entity_id in self.entities_by_id:
            parent = self.entities_by_id[curr.parent_geo_entity_id]
            chain.append(parent)
            curr = parent
        return chain

    def get_country_for_code(self, code: str) -> CanonicalGeoEntity | None:
        return self.countries_by_code.get(code.strip().upper())

    def find_entities_by_alias(self, normalized_name: str) -> list[CanonicalGeoEntity]:
        """Looks up entities matching a normalized name or alias."""
        return self.entities_by_alias.get(normalized_name.strip().lower(), [])
