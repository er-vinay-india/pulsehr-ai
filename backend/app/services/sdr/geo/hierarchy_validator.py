"""
HighView Semantic Data Refinery — Phase SDR-4G
Geographic Hierarchy Validator (GEO-1)

Ensures resolved geographic entities across levels (City, State, Country)
are strictly consistent with reference parent-child relationships.
Rejects contradictory hierarchies (e.g. Bengaluru, California, India).
"""

from __future__ import annotations

from typing import Tuple
from pydantic import BaseModel
from app.services.sdr.geo.contracts import CanonicalGeoEntity, GeoLevel, GeoResolutionStatus
from app.services.sdr.geo.reference_store import GeoReferenceStore


class GeoHierarchyValidationResult(BaseModel):
    """Result of hierarchical topological consistency validation."""
    is_valid: bool
    status: GeoResolutionStatus
    conflicts: list[str]


class GeoHierarchyValidator:
    """
    Validates topological consistency across multiple geographic components.
    """

    def __init__(self, store: GeoReferenceStore):
        self.store = store

    def validate_hierarchy(
        self,
        city: str | CanonicalGeoEntity | None = None,
        state: str | CanonicalGeoEntity | None = None,
        country: str | CanonicalGeoEntity | None = None,
    ) -> GeoHierarchyValidationResult:
        """
        Validates cross-column hierarchy given string tokens or CanonicalGeoEntities.
        """
        city_ent = city if isinstance(city, CanonicalGeoEntity) else None
        state_ent = state if isinstance(state, CanonicalGeoEntity) else None
        country_ent = country if isinstance(country, CanonicalGeoEntity) else None

        if isinstance(country, str) and country.strip():
            country_norm = country.strip().lower()
            c_matches = self.store.find_entities_by_alias(country_norm)
            c_country = [c for c in c_matches if c.level == GeoLevel.COUNTRY]
            if c_country:
                country_ent = c_country[0]

        if isinstance(state, str) and state.strip():
            state_norm = state.strip().lower()
            s_matches = self.store.find_entities_by_alias(state_norm)
            s_state = [s for s in s_matches if s.level == GeoLevel.ADMIN1]
            if s_state:
                state_ent = s_state[0]

        if isinstance(city, str) and city.strip():
            city_norm = city.strip().lower()
            c_matches = self.store.find_entities_by_alias(city_norm)
            c_city = [c for c in c_matches if c.level == GeoLevel.CITY]
            if c_city:
                if country_ent:
                    filtered = [c for c in c_city if c.country_code == country_ent.country_code]
                    city_ent = filtered[0] if filtered else c_city[0]
                else:
                    city_ent = c_city[0]

        is_valid, conflicts = self.validate_hierarchy_consistency(
            city=city_ent,
            state=state_ent,
            country=country_ent,
        )
        status = GeoResolutionStatus.RESOLVED if is_valid else GeoResolutionStatus.INVALID
        return GeoHierarchyValidationResult(
            is_valid=is_valid,
            status=status,
            conflicts=conflicts,
        )

    def validate_hierarchy_consistency(
        self,
        city: CanonicalGeoEntity | None = None,
        state: CanonicalGeoEntity | None = None,
        country: CanonicalGeoEntity | None = None,
    ) -> Tuple[bool, list[str]]:
        """
        Validates that city, state, and country belong to the same authoritative hierarchy.
        Returns: (is_consistent: bool, failure_reasons: list[str])
        """
        reasons: list[str] = []

        # 1. State <-> Country validation
        if state and country:
            if state.country_code != country.country_code:
                reasons.append(
                    f"Hierarchy conflict: State '{state.canonical_name}' (Country {state.country_code}) "
                    f"does not belong to Country '{country.canonical_name}' ({country.country_code})."
                )

        # 2. City <-> Country validation
        if city and country:
            if city.country_code != country.country_code:
                reasons.append(
                    f"Hierarchy conflict: City '{city.canonical_name}' (Country {city.country_code}) "
                    f"does not belong to Country '{country.canonical_name}' ({country.country_code})."
                )

        # 3. City <-> State validation
        if city and state:
            # Check admin1 code match or parent entity match
            if city.admin1_code and state.admin1_code:
                if city.admin1_code != state.admin1_code or city.country_code != state.country_code:
                    reasons.append(
                        f"Hierarchy conflict: City '{city.canonical_name}' ({city.admin1_code}) "
                        f"does not belong to State '{state.canonical_name}' ({state.admin1_code})."
                    )
            elif city.parent_geo_entity_id and city.parent_geo_entity_id != state.geo_entity_id:
                parent = self.store.get_entity(city.parent_geo_entity_id)
                if parent and parent.level == GeoLevel.ADMIN1 and parent.geo_entity_id != state.geo_entity_id:
                    reasons.append(
                        f"Hierarchy conflict: City '{city.canonical_name}' parent '{parent.canonical_name}' "
                        f"differs from declared State '{state.canonical_name}'."
                    )

        if reasons:
            return False, reasons
        return True, []
