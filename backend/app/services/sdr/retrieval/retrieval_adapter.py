"""
HighView Semantic Data Refinery — Phase SDR-1
Retrieval Adapter for Frozen I7 Namespaces
"""

from __future__ import annotations

from typing import Any, Sequence

from app.services.ingestion_v2.retrieval.documents import RetrievalDocument
from app.services.ingestion_v2.retrieval.namespaces import (
    AuthorityClass,
    RetrievalNamespace,
)
from app.services.sdr.contracts.decomposition import SemanticDecompositionCandidate
from app.services.sdr.contracts.enrichment import (
    EnrichmentCandidate,
    ValidatedEnrichment,
)
from app.services.sdr.contracts.keys import (
    ObservedFunctionalDependency,
    SDRKeyCandidate,
)
from app.services.sdr.contracts.profiles import SemanticColumnProfile
from app.services.sdr.contracts.relationships import (
    SDRJoinPlan,
    SDRRelationshipCandidate,
    SDRValidatedRelationshipEdge,
)
from app.services.sdr.contracts.views import (
    SDRAnalyticalFact,
    SDRAnalyticalViewSpec,
)
from app.services.sdr.geo.contracts import CanonicalGeoEntity, GeoResolutionCandidate


class SDRRetrievalAdapter:
    """
    Builds retrieval documents for SDR-1 artifacts strictly adhering to the
    frozen 4-namespace taxonomy.
    Emits exclusively to RAW_SCHEMA (physical profiles) and SEMANTIC (semantic profiles & decomposition).
    NEVER writes to RELATIONSHIP or ANALYTICAL namespaces.
    """

    @staticmethod
    def build_raw_schema_document(
        profile: SemanticColumnProfile,
        dataset_version: str = "v1",
        source_fingerprint: str = "source_hash",
    ) -> RetrievalDocument:
        """Emits a physical column profile document to RAW_SCHEMA_INDEX."""
        doc_id = f"raw_schema_{profile.dataset_id}_{profile.sheet_id}_{profile.column_id}"
        text = (
            f"Table {profile.sheet_id} Column {profile.source_name} "
            f"PhysicalType {profile.physical_dtype} "
            f"RowCount {profile.features.row_count} NullRatio {profile.features.null_ratio} "
            f"DistinctRatio {profile.features.distinct_ratio}"
        )
        metadata = {
            "dataset_id": profile.dataset_id,
            "sheet_id": profile.sheet_id,
            "column_id": profile.column_id,
            "physical_dtype": profile.physical_dtype,
            "null_ratio": profile.features.null_ratio,
            "distinct_ratio": profile.features.distinct_ratio,
            "avg_length": profile.features.avg_value_length,
            "sample_values": profile.features.sample_values[:5],
        }

        return RetrievalDocument.create(
            document_id=doc_id,
            namespace=RetrievalNamespace.RAW_SCHEMA,
            authority_class=AuthorityClass.STRUCTURAL,
            dataset_id=profile.dataset_id,
            dataset_version=dataset_version,
            source_fingerprint=source_fingerprint,
            artifact_type="RawColumnProfileDoc",
            artifact_id=profile.profile_id,
            text_for_retrieval=text,
            structured_metadata=metadata,
        )

    @staticmethod
    def build_semantic_profile_document(
        profile: SemanticColumnProfile,
        dataset_version: str = "v1",
        source_fingerprint: str = "source_hash",
    ) -> RetrievalDocument:
        """Emits a semantic column profile document to SEMANTIC_INDEX."""
        doc_id = f"semantic_{profile.dataset_id}_{profile.sheet_id}_{profile.column_id}"
        text = (
            f"Column {profile.canonical_name} ({profile.source_name}) "
            f"Role {profile.semantic_role.value} Concept {profile.semantic_concept.value} "
            f"SemanticDtype {profile.semantic_dtype.value} "
            f"Privacy {profile.privacy_classification.value} "
            f"Confidence {profile.confidence}"
        )
        metadata = {
            "dataset_id": profile.dataset_id,
            "sheet_id": profile.sheet_id,
            "column_id": profile.column_id,
            "canonical_name": profile.canonical_name,
            "semantic_role": profile.semantic_role.value,
            "semantic_concept": profile.semantic_concept.value,
            "semantic_dtype": profile.semantic_dtype.value,
            "measure_class": profile.measure_class.value if profile.measure_class else None,
            "privacy_classification": profile.privacy_classification.value,
            "confidence": profile.confidence,
            "ambiguity_state": profile.ambiguity_state.value,
            "is_composite_candidate": profile.is_composite_candidate,
            "profile_fingerprint": profile.artifact_fingerprint,
        }

        return RetrievalDocument.create(
            document_id=doc_id,
            namespace=RetrievalNamespace.SEMANTIC,
            authority_class=AuthorityClass.SEMANTIC,
            dataset_id=profile.dataset_id,
            dataset_version=dataset_version,
            source_fingerprint=source_fingerprint,
            artifact_type="SemanticColumnDoc",
            artifact_id=profile.profile_id,
            text_for_retrieval=text,
            structured_metadata=metadata,
        )

    @staticmethod
    def build_decomposition_candidate_document(
        candidate: SemanticDecompositionCandidate,
        dataset_version: str = "v1",
        source_fingerprint: str = "source_hash",
    ) -> RetrievalDocument:
        """Emits a decomposition candidate document to SEMANTIC_INDEX."""
        doc_id = f"decomp_{candidate.dataset_id}_{candidate.sheet_id}_{candidate.source_column_id}"
        comp_names = [c.candidate_name for c in candidate.components]
        text = (
            f"Decomposition Candidate for {candidate.source_column_name} "
            f"Pattern {candidate.pattern_type.value} "
            f"Components {', '.join(comp_names)} "
            f"Status {candidate.validation_status.value}"
        )
        metadata = {
            "candidate_id": candidate.candidate_id,
            "dataset_id": candidate.dataset_id,
            "sheet_id": candidate.sheet_id,
            "source_column_id": candidate.source_column_id,
            "pattern_type": candidate.pattern_type.value,
            "validation_status": candidate.validation_status.value,
            "confidence": candidate.confidence,
            "components": [
                {
                    "position": c.position,
                    "name": c.candidate_name,
                    "role": c.proposed_semantic_role.value,
                    "dtype": c.proposed_semantic_dtype.value,
                }
                for c in candidate.components
            ],
            "is_destructive": candidate.is_destructive,
            "candidate_fingerprint": candidate.candidate_fingerprint,
        }

        return RetrievalDocument.create(
            document_id=doc_id,
            namespace=RetrievalNamespace.SEMANTIC,
            authority_class=AuthorityClass.SEMANTIC,
            dataset_id=candidate.dataset_id,
            dataset_version=dataset_version,
            source_fingerprint=source_fingerprint,
            artifact_type="DecompositionCandidateDoc",
            artifact_id=candidate.candidate_id,
            text_for_retrieval=text,
            structured_metadata=metadata,
        )

    @staticmethod
    def build_entity_hypothesis_document(
        hypothesis: Any,
        dataset_version: str = "v1",
        source_fingerprint: str = "source_hash",
    ) -> RetrievalDocument:
        """Emits an entity hypothesis document to SEMANTIC_INDEX."""
        doc_id = f"ent_hyp_{hypothesis.dataset_id}_{hypothesis.sheet_id}_{hypothesis.canonical_name.lower()}"
        text = (
            f"Table {hypothesis.sheet_id} Entity Hypothesis {hypothesis.canonical_name} "
            f"Type {hypothesis.entity_type.value} Confidence {hypothesis.entity_confidence} "
            f"Status {hypothesis.state.value} SupportingColumns {', '.join(hypothesis.supporting_column_ids)}"
        )
        metadata = {
            "hypothesis_id": hypothesis.entity_hypothesis_id,
            "dataset_id": hypothesis.dataset_id,
            "sheet_id": hypothesis.sheet_id,
            "canonical_name": hypothesis.canonical_name,
            "entity_type": hypothesis.entity_type.value,
            "entity_confidence": hypothesis.entity_confidence,
            "state": hypothesis.state.value,
            "supporting_column_ids": hypothesis.supporting_column_ids,
            "identifier_column_ids": hypothesis.identifier_like_column_ids,
            "evidence": hypothesis.evidence,
        }

        return RetrievalDocument.create(
            document_id=doc_id,
            namespace=RetrievalNamespace.SEMANTIC,
            authority_class=AuthorityClass.SEMANTIC,
            dataset_id=hypothesis.dataset_id,
            dataset_version=dataset_version,
            source_fingerprint=source_fingerprint,
            artifact_type="EntityHypothesisDoc",
            artifact_id=hypothesis.entity_hypothesis_id,
            text_for_retrieval=text,
            structured_metadata=metadata,
        )

    @staticmethod
    def build_grain_profile_document(
        grain_profile: Any,
        dataset_version: str = "v1",
        source_fingerprint: str = "source_hash",
    ) -> RetrievalDocument:
        """Emits a governed table grain document to SEMANTIC_INDEX."""
        doc_id = f"grain_sem_{grain_profile.dataset_id}_{grain_profile.sheet_id}"
        text = (
            f"Table {grain_profile.sheet_id} Observational Grain {grain_profile.resolved_grain_expression} "
            f"PrimaryEntity {grain_profile.primary_entity.value} Temporal {grain_profile.temporal_grain.value} "
            f"Status {grain_profile.grain_status.value} Confidence {grain_profile.grain_confidence}"
        )
        metadata = {
            "profile_id": grain_profile.profile_id,
            "dataset_id": grain_profile.dataset_id,
            "sheet_id": grain_profile.sheet_id,
            "primary_entity": grain_profile.primary_entity.value,
            "temporal_grain": grain_profile.temporal_grain.value,
            "resolved_grain_expression": grain_profile.resolved_grain_expression,
            "grain_status": grain_profile.grain_status.value,
            "grain_confidence": grain_profile.grain_confidence,
            "is_unique": grain_profile.is_unique,
            "rationale": grain_profile.rationale,
        }

        return RetrievalDocument.create(
            document_id=doc_id,
            namespace=RetrievalNamespace.SEMANTIC,
            authority_class=AuthorityClass.SEMANTIC,
            dataset_id=grain_profile.dataset_id,
            dataset_version=dataset_version,
            source_fingerprint=source_fingerprint,
            artifact_type="GrainProfileDoc",
            artifact_id=grain_profile.profile_id,
            text_for_retrieval=text,
            structured_metadata=metadata,
        )

    @staticmethod
    def build_raw_grain_observation_document(
        grain_profile: Any,
        dataset_version: str = "v1",
        source_fingerprint: str = "source_hash",
    ) -> RetrievalDocument:
        """Emits structural grain candidate observations to RAW_SCHEMA_INDEX."""
        doc_id = f"grain_raw_{grain_profile.dataset_id}_{grain_profile.sheet_id}"
        best_cand = grain_profile.best_candidate
        text = (
            f"Table {grain_profile.sheet_id} Candidate Determinants "
            f"{', '.join(best_cand.determinant_column_names) if best_cand else 'NONE'} "
            f"Uniqueness {best_cand.uniqueness_ratio if best_cand else 0.0} "
            f"Duplicates {best_cand.duplicate_row_count if best_cand else 0}"
        )
        metadata = {
            "dataset_id": grain_profile.dataset_id,
            "sheet_id": grain_profile.sheet_id,
            "determinant_columns": best_cand.determinant_column_names if best_cand else [],
            "uniqueness_ratio": best_cand.uniqueness_ratio if best_cand else 0.0,
            "duplicate_rows": best_cand.duplicate_row_count if best_cand else 0,
            "null_involvement_ratio": best_cand.null_involvement_ratio if best_cand else 0.0,
        }

        return RetrievalDocument.create(
            document_id=doc_id,
            namespace=RetrievalNamespace.RAW_SCHEMA,
            authority_class=AuthorityClass.STRUCTURAL,
            dataset_id=grain_profile.dataset_id,
            dataset_version=dataset_version,
            source_fingerprint=source_fingerprint,
            artifact_type="RawGrainObservationDoc",
            artifact_id=grain_profile.profile_id,
            text_for_retrieval=text,
            structured_metadata=metadata,
        )

    @staticmethod
    def build_raw_key_candidate_document(
        candidate: SDRKeyCandidate,
        dataset_version: str = "v1",
        source_fingerprint: str = "source_hash",
    ) -> RetrievalDocument:
        """Emits physical key candidate observations to RAW_SCHEMA_INDEX."""
        doc_id = f"raw_key_{candidate.dataset_id}_{candidate.sheet_id}_{'_'.join(candidate.column_names)}"
        text = (
            f"Table {candidate.sheet_id} Key Columns {', '.join(candidate.column_names)} "
            f"Uniqueness {candidate.uniqueness_ratio} NullRatio {candidate.null_ratio} "
            f"Duplicates {candidate.duplicate_row_count} Minimal {candidate.is_minimal}"
        )
        metadata = {
            "candidate_id": candidate.candidate_id,
            "dataset_id": candidate.dataset_id,
            "sheet_id": candidate.sheet_id,
            "column_names": list(candidate.column_names),
            "composite_width": candidate.width,
            "uniqueness_ratio": candidate.uniqueness_ratio,
            "null_ratio": candidate.null_ratio,
            "duplicate_count": candidate.duplicate_row_count,
            "is_minimal": candidate.is_minimal,
            "status": candidate.status.value,
        }

        return RetrievalDocument.create(
            document_id=doc_id,
            namespace=RetrievalNamespace.RAW_SCHEMA,
            authority_class=AuthorityClass.STRUCTURAL,
            dataset_id=candidate.dataset_id,
            dataset_version=dataset_version,
            source_fingerprint=source_fingerprint,
            artifact_type="RawKeyCandidateDoc",
            artifact_id=candidate.candidate_id,
            text_for_retrieval=text,
            structured_metadata=metadata,
        )

    @staticmethod
    def build_key_candidate_document(
        candidate: SDRKeyCandidate,
        dataset_version: str = "v1",
        source_fingerprint: str = "source_hash",
    ) -> RetrievalDocument:
        """Emits a semantic key candidate document to SEMANTIC_INDEX."""
        doc_id = f"semantic_key_{candidate.dataset_id}_{candidate.sheet_id}_{'_'.join(candidate.column_names)}"
        text = (
            f"Table {candidate.sheet_id} CandidateKey {', '.join(candidate.column_names)} "
            f"Type {candidate.candidate_type.value} Status {candidate.status.value} "
            f"Confidence {candidate.key_confidence} Authority {candidate.authority.value} "
            f"EntityRef {candidate.entity_type.value}"
        )
        metadata = {
            "candidate_id": candidate.candidate_id,
            "dataset_id": candidate.dataset_id,
            "sheet_id": candidate.sheet_id,
            "column_names": list(candidate.column_names),
            "key_type": candidate.candidate_type.value,
            "status": candidate.status.value,
            "authority": candidate.authority.value,
            "confidence": candidate.key_confidence,
            "entity_reference": candidate.entity_type.value,
            "is_minimal": candidate.is_minimal,
            "quality_notes": candidate.evidence,
            "candidate_fingerprint": candidate.artifact_fingerprint,
        }

        return RetrievalDocument.create(
            document_id=doc_id,
            namespace=RetrievalNamespace.SEMANTIC,
            authority_class=AuthorityClass.SEMANTIC,
            dataset_id=candidate.dataset_id,
            dataset_version=dataset_version,
            source_fingerprint=source_fingerprint,
            artifact_type="SemanticKeyCandidateDoc",
            artifact_id=candidate.candidate_id,
            text_for_retrieval=text,
            structured_metadata=metadata,
        )

    @staticmethod
    def build_functional_dependency_document(
        fd: ObservedFunctionalDependency,
        dataset_version: str = "v1",
        source_fingerprint: str = "source_hash",
    ) -> RetrievalDocument:
        """Emits an observed functional dependency document to SEMANTIC_INDEX."""
        doc_id = f"fd_{fd.dataset_id}_{fd.sheet_id}_{'_'.join(fd.determinant_column_names)}_to_{'_'.join(fd.dependent_column_names)}"
        text = (
            f"Table {fd.sheet_id} FD {', '.join(fd.determinant_column_names)} -> {', '.join(fd.dependent_column_names)} "
            f"Support {fd.support_ratio} Confidence {fd.confidence} Scope {fd.scope}"
        )
        metadata = {
            "fd_id": fd.fd_id,
            "dataset_id": fd.dataset_id,
            "sheet_id": fd.sheet_id,
            "determinant_columns": list(fd.determinant_column_names),
            "dependent_columns": list(fd.dependent_column_names),
            "support": fd.support_ratio,
            "confidence": fd.confidence,
            "exception_count": fd.violation_count,
            "scope": fd.scope,
            "rationale": fd.rationale,
            "fd_fingerprint": fd.artifact_fingerprint,
        }

        return RetrievalDocument.create(
            document_id=doc_id,
            namespace=RetrievalNamespace.SEMANTIC,
            authority_class=AuthorityClass.SEMANTIC,
            dataset_id=fd.dataset_id,
            dataset_version=dataset_version,
            source_fingerprint=source_fingerprint,
            artifact_type="FunctionalDependencyDoc",
            artifact_id=fd.fd_id,
            text_for_retrieval=text,
            structured_metadata=metadata,
        )

    @staticmethod
    def build_enrichment_candidate_document(
        candidate: EnrichmentCandidate,
        dataset_version: str = "v1",
        source_fingerprint: str = "source_hash",
    ) -> RetrievalDocument:
        """Emits an enrichment candidate opportunity to SEMANTIC_INDEX."""
        doc_id = f"enrich_cand_{candidate.dataset_id}_{candidate.sheet_id}_{candidate.candidate_id}"
        text = (
            f"Table {candidate.sheet_id} Column {', '.join(candidate.source_column_names)} "
            f"EnrichmentOpportunity {candidate.proposed_enrichment_type} "
            f"Output {candidate.proposed_output_name} Type {candidate.proposed_output_semantic_type.value} "
            f"Provider {candidate.provider_id} Confidence {candidate.confidence}"
        )
        metadata = {
            "candidate_id": candidate.candidate_id,
            "dataset_id": candidate.dataset_id,
            "sheet_id": candidate.sheet_id,
            "source_columns": list(candidate.source_column_names),
            "enrichment_type": candidate.proposed_enrichment_type,
            "output_name": candidate.proposed_output_name,
            "output_type": candidate.proposed_output_semantic_type.value,
            "provider_id": candidate.provider_id,
            "confidence": candidate.confidence,
            "validation_status": candidate.validation_status.value,
            "candidate_fingerprint": candidate.artifact_fingerprint,
        }

        return RetrievalDocument.create(
            document_id=doc_id,
            namespace=RetrievalNamespace.SEMANTIC,
            authority_class=AuthorityClass.SEMANTIC,
            dataset_id=candidate.dataset_id,
            dataset_version=dataset_version,
            source_fingerprint=source_fingerprint,
            artifact_type="EnrichmentCandidateDoc",
            artifact_id=candidate.candidate_id,
            text_for_retrieval=text,
            structured_metadata=metadata,
        )

    @staticmethod
    def build_validated_enrichment_document(
        enrichment: ValidatedEnrichment,
        dataset_version: str = "v1",
        source_fingerprint: str = "source_hash",
    ) -> RetrievalDocument:
        """Emits an authorized validated enrichment definition to SEMANTIC_INDEX."""
        doc_id = f"val_enrich_{enrichment.dataset_id}_{enrichment.sheet_id}_{enrichment.enrichment_id}"
        text = (
            f"Table {enrichment.sheet_id} DerivedEnrichment {enrichment.output_name} "
            f"SourceColumns {', '.join(enrichment.source_column_names)} "
            f"Type {enrichment.output_semantic_type.value} Authority {enrichment.authority} "
            f"Materialization {enrichment.materialization.value} Confidence {enrichment.confidence} "
            f"Provider {enrichment.provider_id} v{enrichment.provider_version}"
        )
        metadata = {
            "enrichment_id": enrichment.enrichment_id,
            "dataset_id": enrichment.dataset_id,
            "sheet_id": enrichment.sheet_id,
            "source_columns": list(enrichment.source_column_names),
            "output_name": enrichment.output_name,
            "output_type": enrichment.output_semantic_type.value,
            "materialization": enrichment.materialization.value,
            "authority": enrichment.authority,
            "confidence": enrichment.confidence,
            "provider_id": enrichment.provider_id,
            "provider_version": enrichment.provider_version,
            "reference_version": enrichment.reference_data_version,
            "is_valid": enrichment.is_valid,
            "enrichment_fingerprint": enrichment.artifact_fingerprint,
        }

        return RetrievalDocument.create(
            document_id=doc_id,
            namespace=RetrievalNamespace.SEMANTIC,
            authority_class=AuthorityClass.SEMANTIC,
            dataset_id=enrichment.dataset_id,
            dataset_version=dataset_version,
            source_fingerprint=source_fingerprint,
            artifact_type="ValidatedEnrichmentDoc",
            artifact_id=enrichment.enrichment_id,
            text_for_retrieval=text,
            structured_metadata=metadata,
        )

    @staticmethod
    def build_geo_resolution_document(
        candidate: GeoResolutionCandidate,
        dataset_id: str = "dataset_geo",
        sheet_id: str = "sheet_geo",
        dataset_version: str = "v1",
        source_fingerprint: str = "source_hash",
    ) -> RetrievalDocument:
        """Emits a geographic resolution candidate to SEMANTIC_INDEX."""
        doc_id = f"geo_res_{dataset_id}_{sheet_id}_{candidate.source_column_id}_{candidate.normalized_input}"
        text = (
            f"Table {sheet_id} Column {candidate.source_column_id} GeoResolution "
            f"Observed '{candidate.source_value}' Normalized '{candidate.normalized_input}' "
            f"Status {candidate.resolution_status.value} ResolvedEntity {candidate.resolved_entity_id or 'NONE'} "
            f"Method {candidate.match_method.value} Confidence {candidate.confidence}"
        )
        metadata = {
            "source_value": candidate.source_value,
            "normalized_input": candidate.normalized_input,
            "resolution_status": candidate.resolution_status.value,
            "resolved_entity_id": candidate.resolved_entity_id,
            "candidate_ids": candidate.candidate_geo_entity_ids,
            "confidence": candidate.confidence,
            "match_method": candidate.match_method.value,
            "source_column_id": candidate.source_column_id,
            "geo_fingerprint": candidate.artifact_fingerprint,
        }

        return RetrievalDocument.create(
            document_id=doc_id,
            namespace=RetrievalNamespace.SEMANTIC,
            authority_class=AuthorityClass.SEMANTIC,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            source_fingerprint=source_fingerprint,
            artifact_type="GeoResolutionDoc",
            artifact_id=doc_id,
            text_for_retrieval=text,
            structured_metadata=metadata,
        )

    @staticmethod
    def build_canonical_geo_document(
        entity: CanonicalGeoEntity,
        dataset_id: str = "dataset_geo",
        dataset_version: str = "v1",
        source_fingerprint: str = "source_hash",
    ) -> RetrievalDocument:
        """Emits a canonical reference entity to SEMANTIC_INDEX."""
        doc_id = f"canon_geo_{entity.geo_entity_id}"
        text = (
            f"CanonicalGeoEntity {entity.geo_entity_id} Level {entity.level.value} "
            f"Name '{entity.canonical_name}' Display '{entity.display_name}' Country {entity.country_code} "
            f"Parent {entity.parent_geo_entity_id or 'NONE'} Timezone {entity.timezone or 'UNKNOWN'}"
        )
        metadata = {
            "geo_entity_id": entity.geo_entity_id,
            "level": entity.level.value,
            "canonical_name": entity.canonical_name,
            "display_name": entity.display_name,
            "country_code": entity.country_code,
            "parent_id": entity.parent_geo_entity_id,
            "latitude": entity.latitude,
            "longitude": entity.longitude,
            "timezone": entity.timezone,
            "reference_version": entity.reference_version,
            "entity_fingerprint": entity.artifact_fingerprint,
        }

        return RetrievalDocument.create(
            document_id=doc_id,
            namespace=RetrievalNamespace.SEMANTIC,
            authority_class=AuthorityClass.SEMANTIC,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            source_fingerprint=source_fingerprint,
            artifact_type="CanonicalGeoDoc",
            artifact_id=entity.geo_entity_id,
            text_for_retrieval=text,
            structured_metadata=metadata,
        )

    @staticmethod
    def build_relationship_candidate_document(
        candidate: SDRRelationshipCandidate,
        dataset_version: str = "v1",
        source_fingerprint: str = "source_hash",
    ) -> RetrievalDocument:
        """Emits a candidate relationship document to RELATIONSHIP_INDEX (provisional authority)."""
        doc_id = f"rel_cand_{candidate.dataset_id}_{candidate.candidate_id}"
        l_cols = ",".join(candidate.left_column_ids)
        r_cols = ",".join(candidate.right_column_ids)
        text = (
            f"Candidate relationship between {candidate.left_sheet_id}.{l_cols} and {candidate.right_sheet_id}.{r_cols}. "
            f"Class: {candidate.relationship_class.value}. Candidate cardinality: {candidate.candidate_cardinality.value}. "
            f"Confidence: {candidate.confidence}. Referential overlap: {candidate.referential_overlap}."
        )
        metadata = {
            "candidate_id": candidate.candidate_id,
            "dataset_id": candidate.dataset_id,
            "left_sheet_id": candidate.left_sheet_id,
            "right_sheet_id": candidate.right_sheet_id,
            "left_column_ids": candidate.left_column_ids,
            "right_column_ids": candidate.right_column_ids,
            "relationship_class": candidate.relationship_class.value,
            "candidate_cardinality": candidate.candidate_cardinality.value,
            "confidence": candidate.confidence,
            "referential_overlap": candidate.referential_overlap,
            "left_coverage": candidate.left_coverage,
            "right_coverage": candidate.right_coverage,
            "artifact_fingerprint": candidate.artifact_fingerprint,
            "target_index": "RELATIONSHIP_INDEX",
        }

        return RetrievalDocument.create(
            document_id=doc_id,
            namespace=RetrievalNamespace.RELATIONSHIP,
            authority_class=AuthorityClass.RELATIONSHIP,
            dataset_id=candidate.dataset_id,
            dataset_version=dataset_version,
            source_fingerprint=source_fingerprint,
            artifact_type="RelationshipCandidateDoc",
            artifact_id=candidate.candidate_id,
            text_for_retrieval=text,
            structured_metadata=metadata,
        )

    @staticmethod
    def build_validated_relationship_edge_document(
        edge: SDRValidatedRelationshipEdge,
        dataset_version: str = "v1",
        source_fingerprint: str = "source_hash",
    ) -> RetrievalDocument:
        """Emits a validated relationship edge document to RELATIONSHIP_INDEX (governed relationship authority)."""
        doc_id = f"rel_edge_{edge.dataset_id}_{edge.edge_id}"
        l_cols = ",".join(edge.left_column_ids)
        r_cols = ",".join(edge.right_column_ids)
        text = (
            f"Validated relationship between {edge.left_sheet_id}.{l_cols} and {edge.right_sheet_id}.{r_cols}. "
            f"Cardinality: {edge.cardinality.value}. Status: {edge.status.value}. Class: {edge.relationship_class.value}. "
            f"Coverage: {edge.referential_coverage}. Grain preserving: {edge.is_grain_preserving}."
        )
        metadata = {
            "edge_id": edge.edge_id,
            "candidate_id": edge.candidate_id,
            "dataset_id": edge.dataset_id,
            "left_sheet_id": edge.left_sheet_id,
            "right_sheet_id": edge.right_sheet_id,
            "left_column_ids": edge.left_column_ids,
            "right_column_ids": edge.right_column_ids,
            "cardinality": edge.cardinality.value,
            "status": edge.status.value,
            "relationship_class": edge.relationship_class.value,
            "referential_coverage": edge.referential_coverage,
            "left_coverage": edge.left_coverage,
            "right_coverage": edge.right_coverage,
            "unmatched_left": edge.unmatched_left_count,
            "unmatched_right": edge.unmatched_right_count,
            "confidence": edge.confidence,
            "is_grain_preserving": edge.is_grain_preserving,
            "duplication_risk_flag": edge.duplication_risk_flag,
            "artifact_fingerprint": edge.artifact_fingerprint,
            "target_index": "RELATIONSHIP_INDEX",
        }

        return RetrievalDocument.create(
            document_id=doc_id,
            namespace=RetrievalNamespace.RELATIONSHIP,
            authority_class=AuthorityClass.RELATIONSHIP,
            dataset_id=edge.dataset_id,
            dataset_version=dataset_version,
            source_fingerprint=source_fingerprint,
            artifact_type="ValidatedRelationshipDoc",
            artifact_id=edge.edge_id,
            text_for_retrieval=text,
            structured_metadata=metadata,
        )

    @staticmethod
    def build_join_plan_document(
        plan: SDRJoinPlan,
        dataset_version: str = "v1",
        source_fingerprint: str = "source_hash",
    ) -> RetrievalDocument:
        """Emits a governed JoinPlan document to RELATIONSHIP_INDEX (governed executable metadata)."""
        doc_id = f"join_plan_{plan.dataset_id}_{plan.join_plan_id}"
        l_keys = ",".join(plan.left_keys)
        r_keys = ",".join(plan.right_keys)
        safe_ops = ", ".join(plan.safe_operations)
        forb_ops = ", ".join(plan.forbidden_operations)
        text = (
            f"JoinPlan {plan.join_plan_id} joining {plan.left_sheet_id}.{l_keys} and {plan.right_sheet_id}.{r_keys}. "
            f"JoinType: {plan.join_type}. Safety: {plan.safety_status.value}. Target grain: {plan.target_grain}. "
            f"Preaggregation required: {plan.required_preaggregation}. "
            f"Safe operations: [{safe_ops}]. Forbidden operations: [{forb_ops}]."
        )
        metadata = {
            "join_plan_id": plan.join_plan_id,
            "relationship_edge_id": plan.relationship_edge_id,
            "dataset_id": plan.dataset_id,
            "left_sheet_id": plan.left_sheet_id,
            "right_sheet_id": plan.right_sheet_id,
            "left_keys": plan.left_keys,
            "right_keys": plan.right_keys,
            "join_type": plan.join_type,
            "safety_status": plan.safety_status.value,
            "left_grain": plan.left_grain,
            "right_grain": plan.right_grain,
            "target_grain": plan.target_grain,
            "required_preaggregation": plan.required_preaggregation,
            "preaggregation_side": plan.preaggregation_side,
            "expansion_ratio": plan.expansion_ratio,
            "risk_flags": plan.risk_flags,
            "safe_operations": plan.safe_operations,
            "forbidden_operations": plan.forbidden_operations,
            "artifact_fingerprint": plan.artifact_fingerprint,
            "target_index": "RELATIONSHIP_INDEX",
        }

        return RetrievalDocument.create(
            document_id=doc_id,
            namespace=RetrievalNamespace.RELATIONSHIP,
            authority_class=AuthorityClass.RELATIONSHIP,
            dataset_id=plan.dataset_id,
            dataset_version=dataset_version,
            source_fingerprint=source_fingerprint,
            artifact_type="JoinPlanDoc",
            artifact_id=plan.join_plan_id,
            text_for_retrieval=text,
            structured_metadata=metadata,
        )

    @staticmethod
    def build_analytical_view_document(
        view: SDRAnalyticalViewSpec,
        dataset_version: str = "v1",
        source_fingerprint: str = "source_hash",
    ) -> RetrievalDocument:
        """Emits an analytical view metadata document strictly to ANALYTICAL_INDEX."""
        doc_id = f"analytical_view_{view.dataset_id}_{view.analytical_view_id}"
        dims = ", ".join(view.dimension_columns)
        measures = ", ".join(view.measure_columns + [d.measure_name for d in view.derived_measure_specs])
        text = (
            f"AnalyticalView {view.analytical_view_id} ({view.name}) over sheets [{', '.join(view.source_sheet_ids)}]. "
            f"Result grain: {view.result_grain}. Dimensions: [{dims}]. Measures: [{measures}]. "
            f"Materialization: {view.materialization_mode.value}. Status: {view.status.value}."
        )
        metadata = {
            "analytical_view_id": view.analytical_view_id,
            "dataset_id": view.dataset_id,
            "name": view.name,
            "source_sheet_ids": view.source_sheet_ids,
            "join_plan_ids": view.join_plan_ids,
            "base_grain": view.base_grain,
            "result_grain": view.result_grain,
            "dimension_columns": view.dimension_columns,
            "measure_columns": view.measure_columns,
            "materialization_mode": view.materialization_mode.value,
            "status": view.status.value,
            "artifact_fingerprint": view.artifact_fingerprint,
            "target_index": "ANALYTICAL_INDEX",
        }

        return RetrievalDocument.create(
            document_id=doc_id,
            namespace=RetrievalNamespace.ANALYTICAL,
            authority_class=AuthorityClass.ANALYTICAL_EVIDENCE,
            dataset_id=view.dataset_id,
            dataset_version=dataset_version,
            source_fingerprint=source_fingerprint,
            artifact_type="AnalyticalViewDoc",
            artifact_id=view.analytical_view_id,
            text_for_retrieval=text,
            structured_metadata=metadata,
        )

    @staticmethod
    def build_analytical_fact_document(
        fact: SDRAnalyticalFact,
        dataset_version: str = "v1",
        source_fingerprint: str = "source_hash",
    ) -> RetrievalDocument:
        """Emits an analytical fact document strictly to ANALYTICAL_INDEX."""
        doc_id = f"analytical_fact_{fact.dataset_id}_{fact.fact_id}"
        text = (
            f"AnalyticalFact {fact.fact_id}: metric '{fact.metric}' = {fact.formatted_value} "
            f"at grain '{fact.grain}'. Provenance: {fact.provenance_type}. "
            f"View: {fact.analytical_view_id}."
        )
        metadata = {
            "fact_id": fact.fact_id,
            "metric": fact.metric,
            "value": fact.value,
            "formatted_value": fact.formatted_value,
            "unit": fact.unit,
            "grain": fact.grain,
            "denominator_value": fact.denominator_value,
            "dataset_id": fact.dataset_id,
            "analytical_view_id": fact.analytical_view_id,
            "join_plan_ids": fact.join_plan_ids,
            "provenance_type": fact.provenance_type,
            "artifact_fingerprint": fact.artifact_fingerprint,
            "target_index": "ANALYTICAL_INDEX",
        }

        return RetrievalDocument.create(
            document_id=doc_id,
            namespace=RetrievalNamespace.ANALYTICAL,
            authority_class=AuthorityClass.ANALYTICAL_EVIDENCE,
            dataset_id=fact.dataset_id,
            dataset_version=dataset_version,
            source_fingerprint=source_fingerprint,
            artifact_type="AnalyticalFactDoc",
            artifact_id=fact.fact_id,
            text_for_retrieval=text,
            structured_metadata=metadata,
        )


