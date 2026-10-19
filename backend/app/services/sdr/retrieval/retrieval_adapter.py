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

