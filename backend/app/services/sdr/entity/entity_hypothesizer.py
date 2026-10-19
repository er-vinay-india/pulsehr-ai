"""
HighView Semantic Data Refinery — Phase SDR-2
Entity Hypothesis Engine
"""

from __future__ import annotations

from typing import Sequence

from app.services.ingestion_v2.contracts.semantics import (
    SemanticColumnRole,
    SemanticEntityType,
)
from app.services.sdr.contracts.entity import (
    EntityHypothesisState,
    SemanticEntityHypothesis,
    compute_entity_hypothesis_fingerprint,
)
from app.services.sdr.contracts.profiles import (
    SemanticColumnProfile,
    SemanticDtype,
)

# Canonical Entity Display Names
ENTITY_CANONICAL_NAMES: dict[SemanticEntityType, str] = {
    SemanticEntityType.PERSON: "EMPLOYEE",
    SemanticEntityType.ORGANIZATION: "ORGANIZATION",
    SemanticEntityType.DEPARTMENT: "DEPARTMENT",
    SemanticEntityType.TEAM: "TEAM",
    SemanticEntityType.STORE: "STORE",
    SemanticEntityType.PRODUCT: "PRODUCT",
    SemanticEntityType.LOCATION: "LOCATION",
    SemanticEntityType.REGION: "REGION",
    SemanticEntityType.TRANSACTION: "TRANSACTION",
    SemanticEntityType.ACCOUNT: "ACCOUNT",
    SemanticEntityType.FACILITY: "FACILITY",
    SemanticEntityType.DEVICE: "DEVICE",
    SemanticEntityType.EVENT: "EVENT",
    SemanticEntityType.UNKNOWN: "UNKNOWN",
    SemanticEntityType.AMBIGUOUS: "AMBIGUOUS",
}


class SDREntityHypothesisEngine:
    """
    Infers business entity hypotheses for a sheet from SDR-1 Semantic Column Profiles.

    CORE EPISTEMIC LAW:
    EntityConfidence != KeyConfidence.
    A table with dirty or duplicate employee IDs still represents an EMPLOYEE entity.
    """

    def generate_hypotheses(
        self,
        dataset_id: str,
        sheet_id: str,
        profiles: Sequence[SemanticColumnProfile],
        policy_fingerprint: str = "default_policy",
    ) -> list[SemanticEntityHypothesis]:
        """
        Analyzes column semantics and clusters columns into candidate business entity hypotheses.
        """
        if not profiles:
            return []

        # 1. Bucket columns by entity type hypotheses and roles
        entity_buckets: dict[SemanticEntityType, list[SemanticColumnProfile]] = {}
        unassigned_profiles: list[SemanticColumnProfile] = []

        for p in profiles:
            ent = p.entity_type_hypothesis
            if ent not in (SemanticEntityType.UNKNOWN, SemanticEntityType.AMBIGUOUS):
                entity_buckets.setdefault(ent, []).append(p)
            else:
                unassigned_profiles.append(p)

        # Fallback: if no explicit entity type but role is TRANSACTION or EVENT
        for p in unassigned_profiles:
            if any(t in p.source_name.lower() for t in ("order", "txn", "transaction", "invoice")):
                entity_buckets.setdefault(SemanticEntityType.TRANSACTION, []).append(p)
            elif any(t in p.source_name.lower() for t in ("event", "log", "incident")):
                entity_buckets.setdefault(SemanticEntityType.EVENT, []).append(p)

        # 2. Build hypothesis for each detected entity type
        hypotheses: list[SemanticEntityHypothesis] = []

        for ent_type, ent_profiles in entity_buckets.items():
            col_ids = [p.column_id for p in ent_profiles]
            id_cols = [
                p.column_id
                for p in ent_profiles
                if p.semantic_role == SemanticColumnRole.ENTITY_IDENTIFIER
                or p.semantic_dtype == SemanticDtype.IDENTIFIER_CODE
            ]
            desc_cols = [
                p.column_id
                for p in ent_profiles
                if p.semantic_role in (
                    SemanticColumnRole.DIMENSION,
                    SemanticColumnRole.ENTITY_LABEL,
                    SemanticColumnRole.ATTRIBUTE,
                    SemanticColumnRole.CATEGORY,
                    SemanticColumnRole.FREE_TEXT,
                )
            ]
            meas_cols = [p.column_id for p in profiles if p.semantic_role == SemanticColumnRole.MEASURE]
            time_cols = [p.column_id for p in profiles if p.semantic_role == SemanticColumnRole.TIME]

            # Calculate EntityConfidence:
            # High if has identifier-like column OR multiple descriptive columns.
            # INVARIANT: Does NOT penalize for nulls or duplicates in keys!
            base_conf = 0.70
            if id_cols:
                base_conf += 0.20
            if desc_cols:
                base_conf += 0.10
            conf = min(0.95, base_conf)

            canonical_name = ENTITY_CANONICAL_NAMES.get(ent_type, ent_type.value)
            state = EntityHypothesisState.CONFIRMED if conf >= 0.80 else EntityHypothesisState.PROVISIONAL

            evidence = (
                f"Entity hypothesis {canonical_name} supported by {len(col_ids)} column(s) "
                f"(IDs: {id_cols or 'none'}, Descriptors: {desc_cols or 'none'})."
            )

            h_id = f"ent_hyp_{dataset_id}_{sheet_id}_{ent_type.value.lower()}"
            fps = [p.artifact_fingerprint for p in ent_profiles]

            artifact_fp = compute_entity_hypothesis_fingerprint(
                dataset_id=dataset_id,
                sheet_id=sheet_id,
                entity_type=ent_type,
                canonical_name=canonical_name,
                supporting_column_ids=col_ids,
                source_profile_fingerprints=fps,
                policy_fingerprint=policy_fingerprint,
            )

            hypotheses.append(
                SemanticEntityHypothesis(
                    entity_hypothesis_id=h_id,
                    dataset_id=dataset_id,
                    sheet_id=sheet_id,
                    entity_type=ent_type,
                    canonical_name=canonical_name,
                    supporting_column_ids=col_ids,
                    identifier_like_column_ids=id_cols,
                    descriptor_column_ids=desc_cols,
                    measure_column_ids=meas_cols,
                    temporal_column_ids=time_cols,
                    entity_confidence=conf,
                    evidence=evidence,
                    state=state,
                    authority="DETERMINISTIC_HEURISTIC",
                    source_profile_fingerprints=fps,
                    artifact_fingerprint=artifact_fp,
                )
            )

        # If absolutely no entity recognized, create a fallback UNKNOWN hypothesis
        if not hypotheses:
            h_id = f"ent_hyp_{dataset_id}_{sheet_id}_unknown"
            artifact_fp = compute_entity_hypothesis_fingerprint(
                dataset_id=dataset_id,
                sheet_id=sheet_id,
                entity_type=SemanticEntityType.UNKNOWN,
                canonical_name="UNKNOWN",
                supporting_column_ids=[],
                source_profile_fingerprints=[p.artifact_fingerprint for p in profiles],
                policy_fingerprint=policy_fingerprint,
            )
            hypotheses.append(
                SemanticEntityHypothesis(
                    entity_hypothesis_id=h_id,
                    dataset_id=dataset_id,
                    sheet_id=sheet_id,
                    entity_type=SemanticEntityType.UNKNOWN,
                    canonical_name="UNKNOWN",
                    supporting_column_ids=[],
                    identifier_like_column_ids=[],
                    descriptor_column_ids=[],
                    measure_column_ids=[p.column_id for p in profiles if p.semantic_role == SemanticColumnRole.MEASURE],
                    temporal_column_ids=[p.column_id for p in profiles if p.semantic_role == SemanticColumnRole.TIME],
                    entity_confidence=0.30,
                    evidence="No strong business entity tokens or semantic roles discovered.",
                    state=EntityHypothesisState.AMBIGUOUS,
                    authority="DETERMINISTIC_HEURISTIC",
                    source_profile_fingerprints=[p.artifact_fingerprint for p in profiles],
                    artifact_fingerprint=artifact_fp,
                )
            )

        # Sort deterministically by confidence desc then canonical name
        return sorted(hypotheses, key=lambda h: (-h.entity_confidence, h.canonical_name))
