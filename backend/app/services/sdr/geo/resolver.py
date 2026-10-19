"""
HighView Semantic Data Refinery — Phase SDR-4G
Governed Geographic Semantic Resolver (GEO-1)

Core Engine resolving observed strings into canonical geographic entities.
Preserves ambiguity instead of guessing.
Implements bounded deterministic caching, value deduplication, and context-aware disambiguation.
"""

from __future__ import annotations

from typing import Any, Sequence
from app.services.sdr.contracts.profiles import (
    SemanticColumnProfile,
    SemanticColumnRole,
    SemanticDtype,
)
from app.services.sdr.geo.contracts import (
    CanonicalGeoEntity,
    GeoLevel,
    GeoMatchMethod,
    GeoResolutionCandidate,
    GeoResolutionStatus,
    compute_geo_resolution_fingerprint,
)
from app.services.sdr.geo.hierarchy_validator import GeoHierarchyValidator
from app.services.sdr.geo.normalizer import (
    is_ambiguous_short_code,
    normalize_for_lookup,
    normalize_geo_text,
)
from app.services.sdr.geo.reference_store import GeoReferenceStore


# Non-geographic false positive terms that require explicit location column context
NON_GEO_FALSE_POSITIVE_TERMS = {
    "georgia", "jordan", "turkey", "chad", "washington",
    "reading", "mobile", "bath", "orange", "gary",
}


class GeoResolutionEngine:
    """
    Offline deterministic geographic semantic resolver.
    """

    def __init__(
        self,
        reference_store: GeoReferenceStore | None = None,
        provider_version: str = "1.0.0",
        min_confidence: float = 0.85,
    ):
        self.store = reference_store or GeoReferenceStore()
        self.hierarchy_validator = GeoHierarchyValidator(self.store)
        self.provider_version = provider_version
        self.reference_data_version = self.store.reference_version
        self.min_confidence = min_confidence

        # Bounded deterministic resolution cache: key -> GeoResolutionCandidate
        self._cache: dict[str, GeoResolutionCandidate] = {}
        self._cache_hits = 0
        self._cache_misses = 0

    def _make_cache_key(
        self,
        norm_val: str,
        country_context: str | None,
        state_context: str | None,
        column_role: SemanticColumnRole | None,
    ) -> str:
        c_code = country_context.upper() if country_context else ""
        s_code = state_context.upper() if state_context else ""
        role_str = column_role.value if column_role else ""
        return f"{norm_val}::{c_code}::{s_code}::{role_str}::{self.provider_version}::{self.reference_data_version}"

    def resolve_token(
        self,
        raw_value: Any,
        column_profile: SemanticColumnProfile | None = None,
        country_context: str | None = None,
        state_context: str | None = None,
        phone_hint: str | None = None,
        expected_level: GeoLevel | None = None,
    ) -> GeoResolutionCandidate:
        """
        Resolves a single geographic string token against local reference evidence.
        """
        if raw_value is None:
            return GeoResolutionCandidate(
                source_value="",
                normalized_input="",
                resolution_status=GeoResolutionStatus.UNRESOLVED,
                provider_version=self.provider_version,
                reference_data_version=self.reference_data_version,
            )

        str_val = str(raw_value).strip()
        if not str_val:
            return GeoResolutionCandidate(
                source_value=str_val,
                normalized_input="",
                resolution_status=GeoResolutionStatus.UNRESOLVED,
                provider_version=self.provider_version,
                reference_data_version=self.reference_data_version,
            )

        norm_input = normalize_for_lookup(str_val)
        col_role = column_profile.semantic_role if column_profile else None
        col_id = column_profile.column_id if column_profile else ""

        # 1. Non-geographic False Positive Guard
        # If the column is NOT a location/geo column and token is in non-geo false positive list
        is_geo_col = (
            col_role == SemanticColumnRole.LOCATION
            or (column_profile and column_profile.semantic_dtype == SemanticDtype.GEOGRAPHIC_LOCATION)
            or (column_profile and any(k in column_profile.source_name.lower() for k in ("city", "state", "country", "location", "geo", "region", "address")))
        )

        if norm_input in NON_GEO_FALSE_POSITIVE_TERMS and (column_profile is not None and not is_geo_col):
            # Reject resolving non-geographic concepts (e.g. Jordan as name, Turkey as food, Georgia as font)
            return GeoResolutionCandidate(
                source_value=str_val,
                normalized_input=norm_input,
                resolution_status=GeoResolutionStatus.UNRESOLVED,
                confidence=0.0,
                match_method=GeoMatchMethod.NONE,
                disambiguation_evidence=["Non-geographic false positive guard: Column is not identified as geographic context."],
                source_column_id=col_id,
                provider_version=self.provider_version,
                reference_data_version=self.reference_data_version,
            )

        # 2. Check Bounded Cache
        cache_key = self._make_cache_key(norm_input, country_context, state_context, col_role)
        if cache_key in self._cache:
            self._cache_hits += 1
            cached = self._cache[cache_key]
            return cached.model_copy(update={"source_value": str_val, "source_column_id": col_id})

        self._cache_misses += 1

        # 3. Disambiguation context synthesis
        resolved_country_code: str | None = None
        if country_context:
            c_cand = self.resolve_country(country_context)
            if c_cand.resolution_status == GeoResolutionStatus.RESOLVED and c_cand.resolved_entity_id:
                c_ent = self.store.get_entity(c_cand.resolved_entity_id)
                if c_ent:
                    resolved_country_code = c_ent.country_code

        # Supporting phone hint
        if not resolved_country_code and phone_hint:
            clean_phone = phone_hint.strip()
            for prefix, c_code in self.store.phone_calling_codes.items():
                if clean_phone.startswith(prefix):
                    resolved_country_code = c_code
                    break

        # 4. Search Reference Store
        matching_entities = self.store.find_entities_by_alias(norm_input)

        # 4A. If short abbreviation (e.g. 'IN', 'OR', 'ME', 'GA', 'CA')
        if len(str_val) == 2 and is_ambiguous_short_code(str_val) and not is_geo_col and not resolved_country_code:
            res = GeoResolutionCandidate(
                source_value=str_val,
                normalized_input=norm_input,
                resolution_status=GeoResolutionStatus.AMBIGUOUS,
                candidate_geo_entity_ids=[e.geo_entity_id for e in matching_entities],
                candidate_count=len(matching_entities),
                confidence=0.20,
                disambiguation_evidence=["Ambiguous 2-letter token without verified geographic column context."],
                source_column_id=col_id,
                provider_version=self.provider_version,
                reference_data_version=self.reference_data_version,
            )
            self._cache[cache_key] = res
            return res

        # 5. Evaluate Matches
        if not matching_entities:
            # Unresolved location
            res = GeoResolutionCandidate(
                source_value=str_val,
                normalized_input=norm_input,
                resolution_status=GeoResolutionStatus.UNRESOLVED,
                candidate_geo_entity_ids=[],
                candidate_count=0,
                confidence=0.0,
                match_method=GeoMatchMethod.NONE,
                disambiguation_evidence=["No matching geographic entity in local reference data."],
                source_column_id=col_id,
                provider_version=self.provider_version,
                reference_data_version=self.reference_data_version,
            )
            self._cache[cache_key] = res
            return res

        # 6. Apply Context Disambiguation
        filtered_entities = matching_entities
        disambiguation_notes: list[str] = []

        if expected_level and len(filtered_entities) > 1:
            level_matched = [e for e in filtered_entities if e.level == expected_level]
            if level_matched:
                filtered_entities = level_matched
                disambiguation_notes.append(f"Filtered by expected level '{expected_level.value}'.")

        if resolved_country_code:
            country_matched = [e for e in filtered_entities if e.country_code == resolved_country_code]
            if country_matched:
                filtered_entities = country_matched
                disambiguation_notes.append(f"Filtered by country context '{resolved_country_code}'.")

        if state_context and len(filtered_entities) > 1:
            norm_state = normalize_for_lookup(state_context)
            matched_state_ents = self.store.find_entities_by_alias(norm_state)
            matched_state_ids = {s.geo_entity_id for s in matched_state_ents if s.level == GeoLevel.ADMIN1}
            matched_state_codes = {s.admin1_code.lower() for s in matched_state_ents if s.admin1_code}
            matched_state_codes.add(norm_state)

            state_matched = [
                e for e in filtered_entities
                if (e.admin1_code and e.admin1_code.lower() in matched_state_codes)
                or (e.parent_geo_entity_id and e.parent_geo_entity_id in matched_state_ids)
                or (e.parent_geo_entity_id and norm_state in e.parent_geo_entity_id.lower())
            ]
            if state_matched:
                filtered_entities = state_matched
                disambiguation_notes.append(f"Filtered by state context '{state_context}'.")

        # 7. Disambiguation Outcome
        if len(filtered_entities) == 1:
            target = filtered_entities[0]
            # Exact match method
            method = GeoMatchMethod.EXACT_CANONICAL
            if norm_input == target.country_code.lower() or norm_input == target.country_code_alpha3.lower():
                method = GeoMatchMethod.ISO_CODE
            elif norm_input != target.canonical_name.lower():
                method = GeoMatchMethod.EXACT_ALIAS

            if disambiguation_notes:
                method = GeoMatchMethod.HIERARCHICAL_CONTEXT

            fp = compute_geo_resolution_fingerprint(
                source_value=str_val,
                normalized_input=norm_input,
                resolution_status=GeoResolutionStatus.RESOLVED,
                resolved_entity_id=target.geo_entity_id,
                candidate_ids=[target.geo_entity_id],
                provider_version=self.provider_version,
                reference_data_version=self.reference_data_version,
            )

            res = GeoResolutionCandidate(
                source_value=str_val,
                normalized_input=norm_input,
                candidate_geo_entity_ids=[target.geo_entity_id],
                resolved_entity_id=target.geo_entity_id,
                candidate_count=1,
                resolution_status=GeoResolutionStatus.RESOLVED,
                confidence=1.0 if not disambiguation_notes else 0.95,
                match_method=method,
                disambiguation_evidence=disambiguation_notes or ["Deterministic exact reference match."],
                source_column_id=col_id,
                provider_version=self.provider_version,
                reference_data_version=self.reference_data_version,
                artifact_fingerprint=fp,
            )
            self._cache[cache_key] = res
            return res

        # Multiple entities remain -> AMBIGUOUS
        fp = compute_geo_resolution_fingerprint(
            source_value=str_val,
            normalized_input=norm_input,
            resolution_status=GeoResolutionStatus.AMBIGUOUS,
            resolved_entity_id=None,
            candidate_ids=[e.geo_entity_id for e in filtered_entities],
            provider_version=self.provider_version,
            reference_data_version=self.reference_data_version,
        )
        res = GeoResolutionCandidate(
            source_value=str_val,
            normalized_input=norm_input,
            candidate_geo_entity_ids=[e.geo_entity_id for e in filtered_entities],
            resolved_entity_id=None,
            candidate_count=len(filtered_entities),
            resolution_status=GeoResolutionStatus.AMBIGUOUS,
            confidence=0.40,
            match_method=GeoMatchMethod.NONE,
            disambiguation_evidence=[
                f"Multiple plausible candidate entities exist ({len(filtered_entities)} matches). Withholding resolution without explicit context."
            ],
            source_column_id=col_id,
            provider_version=self.provider_version,
            reference_data_version=self.reference_data_version,
            artifact_fingerprint=fp,
        )
        self._cache[cache_key] = res
        return res

    def resolve_country(self, raw_value: Any) -> GeoResolutionCandidate:
        """Dedicated country resolver with 0 ambiguity for valid ISO codes and canonical names."""
        if raw_value is None:
            return GeoResolutionCandidate(source_value="", normalized_input="", resolution_status=GeoResolutionStatus.UNRESOLVED)

        s = str(raw_value).strip()
        norm = normalize_for_lookup(s)

        # 1. Direct ISO code lookup
        if len(s) in (2, 3):
            c_entity = self.store.get_country_for_code(s)
            if c_entity:
                return GeoResolutionCandidate(
                    source_value=s,
                    normalized_input=norm,
                    candidate_geo_entity_ids=[c_entity.geo_entity_id],
                    resolved_entity_id=c_entity.geo_entity_id,
                    candidate_count=1,
                    resolution_status=GeoResolutionStatus.RESOLVED,
                    confidence=1.0,
                    match_method=GeoMatchMethod.ISO_CODE,
                    disambiguation_evidence=[f"Standard ISO 3166 code '{s.upper()}'."],
                    provider_version=self.provider_version,
                    reference_data_version=self.reference_data_version,
                )

        # 2. General search filtered to COUNTRY level
        matches = [e for e in self.store.find_entities_by_alias(norm) if e.level == GeoLevel.COUNTRY]
        if len(matches) == 1:
            c_ent = matches[0]
            return GeoResolutionCandidate(
                source_value=s,
                normalized_input=norm,
                candidate_geo_entity_ids=[c_ent.geo_entity_id],
                resolved_entity_id=c_ent.geo_entity_id,
                candidate_count=1,
                resolution_status=GeoResolutionStatus.RESOLVED,
                confidence=1.0,
                match_method=GeoMatchMethod.EXACT_CANONICAL if norm == c_ent.canonical_name.lower() else GeoMatchMethod.EXACT_ALIAS,
                disambiguation_evidence=["Exact canonical country match."],
                provider_version=self.provider_version,
                reference_data_version=self.reference_data_version,
            )
        elif len(matches) > 1:
            return GeoResolutionCandidate(
                source_value=s,
                normalized_input=norm,
                candidate_geo_entity_ids=[e.geo_entity_id for e in matches],
                candidate_count=len(matches),
                resolution_status=GeoResolutionStatus.AMBIGUOUS,
                confidence=0.50,
                disambiguation_evidence=["Multiple country matches."],
                provider_version=self.provider_version,
                reference_data_version=self.reference_data_version,
            )

        return GeoResolutionCandidate(
            source_value=s,
            normalized_input=norm,
            resolution_status=GeoResolutionStatus.UNRESOLVED,
            candidate_count=0,
            confidence=0.0,
            provider_version=self.provider_version,
            reference_data_version=self.reference_data_version,
        )

    def resolve_city(
        self,
        raw_value: Any,
        state_context: str | None = None,
        country_context: str | None = None,
        column_profile: SemanticColumnProfile | None = None,
    ) -> GeoResolutionCandidate:
        """Dedicated city resolver with level filtering to GeoLevel.CITY."""
        return self.resolve_token(
            raw_value=raw_value,
            column_profile=column_profile,
            country_context=country_context,
            state_context=state_context,
            expected_level=GeoLevel.CITY,
        )

    def resolve_composite_hierarchy(
        self,
        raw_composite: str,
        delimiter: str = " - ",
    ) -> Tuple[GeoResolutionStatus, list[GeoResolutionCandidate], list[str]]:
        """
        Decomposes and hierarchically validates a multi-tier geographic string.
        Example: 'Bengaluru - Karnataka - India' -> [City, State, Country]
        Example: 'Bengaluru - California - India' -> INVALID / CONFLICT
        """
        parts = [p.strip() for p in raw_composite.split(delimiter) if p.strip()]
        if len(parts) == 0:
            return GeoResolutionStatus.UNRESOLVED, [], ["Empty composite location string."]

        if len(parts) == 3:
            # City, State, Country
            city_str, state_str, country_str = parts
            c_cand = self.resolve_country(country_str)
            s_cand = self.resolve_token(state_str, country_context=country_str)
            city_cand = self.resolve_token(city_str, country_context=country_str, state_context=state_str)

            # Check individual resolution
            if any(c.resolution_status != GeoResolutionStatus.RESOLVED for c in (city_cand, s_cand, c_cand)):
                # If any part failed or is ambiguous
                if any(c.resolution_status == GeoResolutionStatus.AMBIGUOUS for c in (city_cand, s_cand, c_cand)):
                    return GeoResolutionStatus.AMBIGUOUS, [city_cand, s_cand, c_cand], ["One or more components are ambiguous."]
                return GeoResolutionStatus.UNRESOLVED, [city_cand, s_cand, c_cand], ["One or more components unresolved."]

            # Retrieve canonical entities for topological check
            city_ent = self.store.get_entity(city_cand.resolved_entity_id) if city_cand.resolved_entity_id else None
            state_ent = self.store.get_entity(s_cand.resolved_entity_id) if s_cand.resolved_entity_id else None
            country_ent = self.store.get_entity(c_cand.resolved_entity_id) if c_cand.resolved_entity_id else None

            is_valid, reasons = self.hierarchy_validator.validate_hierarchy_consistency(
                city=city_ent, state=state_ent, country=country_ent
            )
            if not is_valid:
                # Topologically inconsistent
                conflict_cand = city_cand.model_copy(
                    update={
                        "resolution_status": GeoResolutionStatus.INVALID,
                        "disambiguation_evidence": reasons,
                    }
                )
                return GeoResolutionStatus.INVALID, [conflict_cand, s_cand, c_cand], reasons

            return GeoResolutionStatus.RESOLVED, [city_cand, s_cand, c_cand], ["Hierarchically consistent geographic location."]

        elif len(parts) == 2:
            # City/Region, Country
            city_str, country_str = parts
            c_cand = self.resolve_country(country_str)
            city_cand = self.resolve_token(city_str, country_context=country_str)

            if city_cand.resolution_status == GeoResolutionStatus.RESOLVED and c_cand.resolution_status == GeoResolutionStatus.RESOLVED:
                city_ent = self.store.get_entity(city_cand.resolved_entity_id) if city_cand.resolved_entity_id else None
                country_ent = self.store.get_entity(c_cand.resolved_entity_id) if c_cand.resolved_entity_id else None
                is_valid, reasons = self.hierarchy_validator.validate_hierarchy_consistency(
                    city=city_ent, country=country_ent
                )
                if not is_valid:
                    return GeoResolutionStatus.INVALID, [city_cand, c_cand], reasons
                return GeoResolutionStatus.RESOLVED, [city_cand, c_cand], ["Hierarchically consistent location."]

            if city_cand.resolution_status == GeoResolutionStatus.AMBIGUOUS or c_cand.resolution_status == GeoResolutionStatus.AMBIGUOUS:
                return GeoResolutionStatus.AMBIGUOUS, [city_cand, c_cand], ["Ambiguous component in composite string."]

            return GeoResolutionStatus.UNRESOLVED, [city_cand, c_cand], ["Unresolved composite string."]

        return GeoResolutionStatus.UNRESOLVED, [], ["Unsupported composite part count."]

    def get_cache_stats(self) -> dict[str, int]:
        return {
            "cache_entries": len(self._cache),
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
        }
