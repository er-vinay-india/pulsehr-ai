"""
HighView Semantic Data Refinery — Phase SDR-4G
Offline Geographic Enrichment Provider (GEO-1)

Conforms to SDR-4 EnrichmentProvider protocol.
Derives governed geographic hierarchy attributes (city -> state, city -> country, country -> ISO code, coordinates, timezone).
Defaults to VIRTUAL_ENRICHMENT; 100% offline; preserves observed source verbatim.
"""

from __future__ import annotations

from typing import Any, Sequence
from app.services.sdr.contracts.enrichment import (
    EnrichmentCandidate,
    EnrichmentMaterialization,
    EnrichmentProviderMetadata,
    EnrichmentProviderType,
    EnrichmentStatus,
    compute_enrichment_candidate_fingerprint,
)
from app.services.sdr.contracts.profiles import (
    PrivacyClassification,
    ProfilingAmbiguityState,
    SemanticColumnProfile,
    SemanticColumnRole,
    SemanticDtype,
)
from app.services.sdr.enrichment.provider import EnrichmentProvider
from app.services.sdr.geo.contracts import (
    CanonicalGeoEntity,
    GeoLevel,
    GeoResolutionStatus,
)
from app.services.sdr.geo.normalizer import normalize_for_lookup
from app.services.sdr.geo.reference_store import GeoReferenceStore
from app.services.sdr.geo.resolver import GeoResolutionEngine


class GeoEnrichmentProvider(EnrichmentProvider):
    """
    Governed Offline Geographic Enrichment Provider (GEO-1).
    Derives canonical geographic attributes from observed source columns.
    """

    def __init__(
        self,
        version: str = "1.0.0",
        reference_version: str = "2026.1",
        reference_store: GeoReferenceStore | None = None,
    ):
        self.store = reference_store or GeoReferenceStore()
        # If custom reference_version was requested, override
        if reference_version != self.store.reference_version:
            self.store.reference_version = reference_version

        metadata = EnrichmentProviderMetadata(
            provider_id="provider_geo_resolver",
            provider_name="HighView Offline Geographic Semantic Resolver",
            provider_version=version,
            provider_type=EnrichmentProviderType.LOCAL_REFERENCE,
            supported_input_semantics=[
                SemanticDtype.GEOGRAPHIC_LOCATION,
                SemanticDtype.NATURAL_LANGUAGE_TEXT,
                SemanticDtype.CATEGORICAL_CODE,
                SemanticDtype.COMPOSITE_TEXT,
            ],
            supported_output_semantics=[
                SemanticDtype.GEOGRAPHIC_LOCATION,
                SemanticDtype.CATEGORICAL_CODE,
                SemanticDtype.DECIMAL_NUMBER,
                SemanticDtype.NATURAL_LANGUAGE_TEXT,
            ],
            is_offline=True,
            is_deterministic=True,
            reference_data_version=self.store.reference_version,
            license_or_provenance="GeoNames (CC BY 4.0) + Natural Earth (Public Domain) + geoBoundaries (CC BY 4.0)",
        )
        super().__init__(metadata)
        self.resolver = GeoResolutionEngine(
            reference_store=self.store,
            provider_version=self.provider_version,
        )

    def can_handle(self, profile: SemanticColumnProfile) -> bool:
        """Determines if column is a valid candidate for geographic resolution."""
        # Must be classified as GEOGRAPHIC_LOCATION or have LOCATION semantic role or explicit location tokens
        if profile.semantic_dtype == SemanticDtype.GEOGRAPHIC_LOCATION:
            return True
        if profile.semantic_role == SemanticColumnRole.LOCATION:
            return True

        col_name = profile.source_name.lower()
        geo_tokens = ("city", "state", "country", "province", "region", "location", "territory", "place")
        if any(t in col_name for t in geo_tokens):
            return True

        return False

    def generate_candidates(
        self,
        dataset_id: str,
        sheet_id: str,
        profile: SemanticColumnProfile,
        sample_values: Sequence[Any] | None = None,
        policy_fingerprint: str = "",
        depth: int = 1,
        parent_enrichment_id: str | None = None,
    ) -> list[EnrichmentCandidate]:
        """Proposes governed geographic enrichments based on detected column level."""
        col_name = profile.source_name.lower()
        val_fp = profile.artifact_fingerprint
        candidates: list[EnrichmentCandidate] = []

        # Analyze sample values to detect level (Country, State, City, or Composite)
        is_country_col = "country" in col_name or "nation" in col_name
        is_state_col = ("state" in col_name or "province" in col_name) and not is_country_col
        is_city_col = ("city" in col_name or "town" in col_name or "office" in col_name or "headquarters" in col_name) and not is_country_col and not is_state_col

        # Default to city if location general
        if not (is_country_col or is_state_col or is_city_col):
            is_city_col = True

        # Check sample values for ambiguity or unknown
        ambiguity_state = ProfilingAmbiguityState.CLEAR
        if sample_values:
            for v in sample_values:
                res = self.resolver.resolve_token(v, column_profile=profile)
                if res.resolution_status == GeoResolutionStatus.AMBIGUOUS:
                    ambiguity_state = ProfilingAmbiguityState.AMBIGUOUS_TYPE
                    break

        # 1. Country column -> Propose ISO2 and ISO3 codes
        if is_country_col:
            specs = [
                ("iso2", "COUNTRY_TO_ISO2", SemanticDtype.CATEGORICAL_CODE, 0.98, "ISO 3166-1 alpha-2 standard country code", 0.85),
                ("iso3", "COUNTRY_TO_ISO3", SemanticDtype.CATEGORICAL_CODE, 0.98, "ISO 3166-1 alpha-3 standard country code", 0.85),
            ]
            for suffix, enrich_type, out_dtype, conf, desc, util in specs:
                cand_id = f"cand_geo_{sheet_id}_{profile.column_id}_{suffix}"
                out_name = f"ENRICH-GEO-{profile.source_name}_{suffix}"
                fp = compute_enrichment_candidate_fingerprint(
                    dataset_id=dataset_id,
                    sheet_id=sheet_id,
                    source_column_ids=[profile.column_id],
                    source_values_fingerprint=val_fp,
                    proposed_output_name=out_name,
                    proposed_output_semantic_type=out_dtype,
                    provider_id=self.provider_id,
                    provider_version=self.provider_version,
                    reference_data_version=self.reference_data_version,
                    policy_fingerprint=policy_fingerprint,
                )
                candidates.append(
                    EnrichmentCandidate(
                        candidate_id=cand_id,
                        dataset_id=dataset_id,
                        sheet_id=sheet_id,
                        source_column_ids=[profile.column_id],
                        source_column_names=[profile.source_name],
                        source_semantic_type=profile.semantic_dtype,
                        source_values_fingerprint=val_fp,
                        proposed_enrichment_type=enrich_type,
                        proposed_output_name=out_name,
                        proposed_output_semantic_type=out_dtype,
                        provider_id=self.provider_id,
                        provider_version=self.provider_version,
                        reference_data_version=self.reference_data_version,
                        confidence=conf,
                        ambiguity_state=ambiguity_state,
                        information_gain_record={"description": desc, "base_utility": util, "expected_reuse": 1},
                        privacy_classification=PrivacyClassification.GENERAL_ATTRIBUTE,
                        validation_status=EnrichmentStatus.CANDIDATE if ambiguity_state == ProfilingAmbiguityState.CLEAR else EnrichmentStatus.AMBIGUOUS,
                        depth=depth,
                        parent_enrichment_id=parent_enrichment_id,
                        provenance=profile.source_lineage,
                        artifact_fingerprint=fp,
                    )
                )

        # 2. City column -> Propose State, Country, Reference Coordinates, Timezone
        if is_city_col:
            specs = [
                ("state", "CITY_TO_STATE", SemanticDtype.GEOGRAPHIC_LOCATION, 0.95, "Parent state/province derived from canonical city", 0.85),
                ("country", "CITY_TO_COUNTRY", SemanticDtype.GEOGRAPHIC_LOCATION, 0.98, "Parent country derived from canonical city", 0.90),
                ("ref_latitude", "CITY_TO_REF_LATITUDE", SemanticDtype.DECIMAL_NUMBER, 0.90, "City centroid reference latitude (CITY_REFERENCE_POINT)", 0.70),
                ("ref_longitude", "CITY_TO_REF_LONGITUDE", SemanticDtype.DECIMAL_NUMBER, 0.90, "City centroid reference longitude (CITY_REFERENCE_POINT)", 0.70),
                ("timezone", "CITY_TO_TIMEZONE", SemanticDtype.NATURAL_LANGUAGE_TEXT, 0.92, "Standard IANA Timezone ID derived from city", 0.75),
            ]
            for suffix, enrich_type, out_dtype, conf, desc, util in specs:
                cand_id = f"cand_geo_{sheet_id}_{profile.column_id}_{suffix}"
                out_name = f"ENRICH-GEO-{profile.source_name}_{suffix}"
                fp = compute_enrichment_candidate_fingerprint(
                    dataset_id=dataset_id,
                    sheet_id=sheet_id,
                    source_column_ids=[profile.column_id],
                    source_values_fingerprint=val_fp,
                    proposed_output_name=out_name,
                    proposed_output_semantic_type=out_dtype,
                    provider_id=self.provider_id,
                    provider_version=self.provider_version,
                    reference_data_version=self.reference_data_version,
                    policy_fingerprint=policy_fingerprint,
                )
                candidates.append(
                    EnrichmentCandidate(
                        candidate_id=cand_id,
                        dataset_id=dataset_id,
                        sheet_id=sheet_id,
                        source_column_ids=[profile.column_id],
                        source_column_names=[profile.source_name],
                        source_semantic_type=profile.semantic_dtype,
                        source_values_fingerprint=val_fp,
                        proposed_enrichment_type=enrich_type,
                        proposed_output_name=out_name,
                        proposed_output_semantic_type=out_dtype,
                        provider_id=self.provider_id,
                        provider_version=self.provider_version,
                        reference_data_version=self.reference_data_version,
                        confidence=conf,
                        ambiguity_state=ambiguity_state,
                        information_gain_record={"description": desc, "base_utility": util, "expected_reuse": 1},
                        privacy_classification=PrivacyClassification.GENERAL_ATTRIBUTE,
                        validation_status=EnrichmentStatus.CANDIDATE if ambiguity_state == ProfilingAmbiguityState.CLEAR else EnrichmentStatus.AMBIGUOUS,
                        depth=depth,
                        parent_enrichment_id=parent_enrichment_id,
                        provenance=profile.source_lineage,
                        artifact_fingerprint=fp,
                    )
                )

        # 3. State column -> Propose Country
        if is_state_col:
            specs = [
                ("country", "STATE_TO_COUNTRY", SemanticDtype.GEOGRAPHIC_LOCATION, 0.95, "Parent country derived from state/province", 0.88),
            ]
            for suffix, enrich_type, out_dtype, conf, desc, util in specs:
                cand_id = f"cand_geo_{sheet_id}_{profile.column_id}_{suffix}"
                out_name = f"ENRICH-GEO-{profile.source_name}_{suffix}"
                fp = compute_enrichment_candidate_fingerprint(
                    dataset_id=dataset_id,
                    sheet_id=sheet_id,
                    source_column_ids=[profile.column_id],
                    source_values_fingerprint=val_fp,
                    proposed_output_name=out_name,
                    proposed_output_semantic_type=out_dtype,
                    provider_id=self.provider_id,
                    provider_version=self.provider_version,
                    reference_data_version=self.reference_data_version,
                    policy_fingerprint=policy_fingerprint,
                )
                candidates.append(
                    EnrichmentCandidate(
                        candidate_id=cand_id,
                        dataset_id=dataset_id,
                        sheet_id=sheet_id,
                        source_column_ids=[profile.column_id],
                        source_column_names=[profile.source_name],
                        source_semantic_type=profile.semantic_dtype,
                        source_values_fingerprint=val_fp,
                        proposed_enrichment_type=enrich_type,
                        proposed_output_name=out_name,
                        proposed_output_semantic_type=out_dtype,
                        provider_id=self.provider_id,
                        provider_version=self.provider_version,
                        reference_data_version=self.reference_data_version,
                        confidence=conf,
                        ambiguity_state=ambiguity_state,
                        information_gain_record={"description": desc, "base_utility": util, "expected_reuse": 1},
                        privacy_classification=PrivacyClassification.GENERAL_ATTRIBUTE,
                        validation_status=EnrichmentStatus.CANDIDATE if ambiguity_state == ProfilingAmbiguityState.CLEAR else EnrichmentStatus.AMBIGUOUS,
                        depth=depth,
                        parent_enrichment_id=parent_enrichment_id,
                        provenance=profile.source_lineage,
                        artifact_fingerprint=fp,
                    )
                )

        return candidates

    def resolve(self, candidate: EnrichmentCandidate, values: Sequence[Any] | None = None) -> Any:
        """
        Executes deterministic resolution of candidate values or returns logical expression.
        Uses value deduplication to resolve unique inputs once.
        """
        col = candidate.source_column_names[0]
        enrich_type = candidate.proposed_enrichment_type

        # Logical expression for virtual execution
        logical_expr = f"GEO_LOOKUP({col}, '{enrich_type}')"
        if values is None:
            return logical_expr

        # Value deduplication: resolve unique values once
        unique_vals = list({v for v in values if v is not None})
        val_map: dict[Any, Any] = {}

        for uv in unique_vals:
            # Check if composite or single token
            str_uv = str(uv)
            if " - " in str_uv:
                status, parts, _ = self.resolver.resolve_composite_hierarchy(str_uv)
                if status == GeoResolutionStatus.RESOLVED and parts:
                    city_ent = self.store.get_entity(parts[0].resolved_entity_id) if parts[0].resolved_entity_id else None
                    if city_ent:
                        val_map[uv] = self._extract_attr(city_ent, enrich_type)
                    else:
                        val_map[uv] = None
                else:
                    val_map[uv] = None
            else:
                level_hint = GeoLevel.CITY if enrich_type.startswith("CITY_TO_") else (GeoLevel.ADMIN1 if enrich_type.startswith("STATE_TO_") else (GeoLevel.COUNTRY if enrich_type.startswith("COUNTRY_TO_") else None))
                res = self.resolver.resolve_token(uv, expected_level=level_hint)
                if res.resolution_status == GeoResolutionStatus.RESOLVED and res.resolved_entity_id:
                    ent = self.store.get_entity(res.resolved_entity_id)
                    val_map[uv] = self._extract_attr(ent, enrich_type) if ent else None
                else:
                    val_map[uv] = None

        return [val_map.get(v) if v is not None else None for v in values]

    def _extract_attr(self, entity: CanonicalGeoEntity, enrich_type: str) -> Any:
        if "ISO2" in enrich_type:
            return entity.country_code
        elif "ISO3" in enrich_type:
            return entity.country_code_alpha3
        elif "COUNTRY" in enrich_type:
            if entity.level == GeoLevel.COUNTRY:
                return entity.canonical_name
            # Traverse to parent country
            hierarchy = self.store.get_full_hierarchy(entity)
            for h in hierarchy:
                if h.level == GeoLevel.COUNTRY:
                    return h.canonical_name
            c_ent = self.store.get_country_for_code(entity.country_code)
            return c_ent.canonical_name if c_ent else entity.country_code
        elif "STATE" in enrich_type:
            if entity.level == GeoLevel.ADMIN1:
                return entity.canonical_name
            # Check direct parent
            if entity.parent_geo_entity_id:
                p = self.store.get_entity(entity.parent_geo_entity_id)
                if p and p.level == GeoLevel.ADMIN1:
                    return p.canonical_name
            return None
        elif "LATITUDE" in enrich_type:
            return entity.latitude
        elif "LONGITUDE" in enrich_type:
            return entity.longitude
        elif "TIMEZONE" in enrich_type:
            return entity.timezone
        return None
