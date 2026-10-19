"""
HighView Semantic Data Refinery — Phase SDR-1
Retrieval Adapter for Frozen I7 Namespaces
"""

from __future__ import annotations

from typing import Sequence

from app.services.ingestion_v2.retrieval.documents import RetrievalDocument
from app.services.ingestion_v2.retrieval.namespaces import (
    AuthorityClass,
    RetrievalNamespace,
)
from app.services.sdr.contracts.decomposition import SemanticDecompositionCandidate
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
