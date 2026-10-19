"""
HighView Semantic Data Refinery — Phase SDR-2
SDR Grain Discovery Engine
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.services.ingestion_v2.contracts.grain import (
    CanonicalGrain,
    TemporalGrain,
)
from app.services.ingestion_v2.contracts.semantics import (
    SemanticColumnRole,
    SemanticEntityType,
)
from app.services.sdr.contracts.grain import (
    GrainCandidate,
    GrainStatus,
    SDRGrainProfile,
    compute_grain_profile_fingerprint,
)
from app.services.sdr.contracts.policies import GrainConfidencePolicy
from app.services.sdr.contracts.profiles import (
    SemanticColumnProfile,
    SemanticDtype,
)
from app.services.sdr.grain.candidate_pruner import prune_grain_candidates
from app.services.sdr.grain.composite_evaluator import (
    SDRCompositeEvaluator,
    map_temporal_frequency_from_profile,
)

ENTITY_TO_CANONICAL_GRAIN: dict[SemanticEntityType, CanonicalGrain] = {
    SemanticEntityType.PERSON: CanonicalGrain.PERSON,
    SemanticEntityType.DEPARTMENT: CanonicalGrain.DEPARTMENT,
    SemanticEntityType.STORE: CanonicalGrain.STORE,
    SemanticEntityType.PRODUCT: CanonicalGrain.PRODUCT,
    SemanticEntityType.LOCATION: CanonicalGrain.LOCATION,
    SemanticEntityType.ORGANIZATION: CanonicalGrain.ORGANIZATION,
    SemanticEntityType.TRANSACTION: CanonicalGrain.TRANSACTION,
    SemanticEntityType.EVENT: CanonicalGrain.EVENT,
    SemanticEntityType.UNKNOWN: CanonicalGrain.UNKNOWN,
    SemanticEntityType.AMBIGUOUS: CanonicalGrain.AMBIGUOUS,
}


class SDRGrainDiscoveryEngine:
    """
    Discovers and governs row-level observational grain for a sheet.
    Adheres strictly to the core principle: UNIQUENESS IS EVIDENCE, NOT MEANING.
    """

    def __init__(self, policy: GrainConfidencePolicy | None = None):
        self.policy = policy or GrainConfidencePolicy()
        self.evaluator = SDRCompositeEvaluator(policy=self.policy)

    def discover_grain(
        self,
        dataset_id: str,
        sheet_id: str,
        profiles: Sequence[SemanticColumnProfile],
        column_data: Mapping[str, Sequence[Any]],
        row_count: int,
        policy_fingerprint: str = "default_policy",
    ) -> SDRGrainProfile:
        """
        Discovers table observational grain through bounded combination evaluation and strict pruning.
        """
        if row_count == 0 or not profiles:
            return SDRGrainProfile(
                profile_id=f"grain_{dataset_id}_{sheet_id}",
                dataset_id=dataset_id,
                sheet_id=sheet_id,
                primary_entity=CanonicalGrain.UNKNOWN,
                temporal_grain=TemporalGrain.NONE,
                resolved_grain_expression="UNKNOWN",
                grain_status=GrainStatus.UNKNOWN,
                best_candidate=None,
                ranked_candidates=[],
                is_unique=False,
                grain_confidence=0.0,
                rationale="Empty sheet or no column profiles available; grain cannot be determined.",
            )

        prof_map = {p.column_id: p for p in profiles}

        # Step 1: Candidate Pruning (Measures and system row counters strictly excluded)
        eligible_profiles = prune_grain_candidates(profiles, self.policy)

        # Step 2: Bounded Composite Combination Evaluation
        ranked_candidates = self.evaluator.evaluate_combinations(
            eligible_profiles=eligible_profiles,
            column_data=column_data,
            row_count=row_count,
        )

        if not ranked_candidates:
            # Check if this is an event/unstructured log without key
            has_time = any(p.semantic_role == SemanticColumnRole.TIME for p in profiles)
            primary_ent = CanonicalGrain.EVENT if has_time else CanonicalGrain.UNKNOWN
            expr = "EVENT" if has_time else "UNKNOWN"
            return SDRGrainProfile(
                profile_id=f"grain_{dataset_id}_{sheet_id}",
                dataset_id=dataset_id,
                sheet_id=sheet_id,
                primary_entity=primary_ent,
                temporal_grain=TemporalGrain.DATETIME_EVENT if has_time else TemporalGrain.NONE,
                resolved_grain_expression=expr,
                grain_status=GrainStatus.PROVISIONAL if has_time else GrainStatus.UNKNOWN,
                best_candidate=None,
                ranked_candidates=[],
                is_unique=False,
                grain_confidence=0.50 if has_time else 0.20,
                rationale="No viable candidate combinations passed uniqueness thresholds. Classifying as event/unstructured grain.",
            )

        best_cand = ranked_candidates[0]

        # Step 3: Primary Entity & Temporal Grain Synthesis
        primary_entity = self._derive_primary_entity(best_cand, prof_map)
        temporal_grain = self._derive_temporal_grain(best_cand, prof_map)

        is_event_table = (
            primary_entity == CanonicalGrain.EVENT
            or any(p.entity_type_hypothesis == SemanticEntityType.EVENT for p in profiles)
            or any("event" in p.source_name.lower() for p in profiles)
            or any(p.semantic_dtype == SemanticDtype.DATETIME for p in profiles)
        )
        has_natural_key = (
            best_cand.uniqueness_ratio >= self.policy.min_uniqueness_for_single_grain
            and best_cand.confidence >= 0.75
        )

        # Step 4: Ambiguity Gate
        # If top 2 candidates are very close in confidence but express different grains -> AMBIGUOUS
        is_ambiguous = False
        if len(ranked_candidates) >= 2:
            second_cand = ranked_candidates[1]
            conf_diff = best_cand.confidence - second_cand.confidence
            if conf_diff < self.policy.ambiguity_margin and best_cand.grain_expression != second_cand.grain_expression:
                is_ambiguous = True

        # Step 5: Status Determination
        if is_event_table and not has_natural_key:
            primary_entity = CanonicalGrain.EVENT
            if temporal_grain == TemporalGrain.NONE:
                temporal_grain = TemporalGrain.DATETIME_EVENT
            status = GrainStatus.PROVISIONAL
            conf = max(0.65, best_cand.confidence)
            resolved_expr = "EVENT_OCCURRENCE"
            rationale = (
                "Event table with no natural business key. 1 row represents an individual "
                f"event occurrence (observed candidate combinations non-unique, max uniqueness {best_cand.uniqueness_ratio:.2%}; "
                "lineage relies on immutable row coordinates)."
            )
        elif is_ambiguous:
            status = GrainStatus.AMBIGUOUS
            conf = min(0.60, best_cand.confidence)
            resolved_expr = best_cand.grain_expression
            rationale = (
                f"Competing grain hypotheses detected: '{best_cand.grain_expression}' ({best_cand.confidence:.2f}) "
                f"vs '{ranked_candidates[1].grain_expression}' ({ranked_candidates[1].confidence:.2f}). "
                "Withholding confirmed grain promotion."
            )
        elif has_natural_key:
            status = GrainStatus.RESOLVED
            conf = best_cand.confidence
            resolved_expr = best_cand.grain_expression
            rationale = (
                f"Resolved dominant grain: 1 row represents '{best_cand.grain_expression}' "
                f"keyed by ({', '.join(best_cand.determinant_column_names)}) with {best_cand.uniqueness_ratio:.2%} uniqueness."
            )
        elif best_cand.uniqueness_ratio >= 0.70:
            status = GrainStatus.PROVISIONAL
            conf = best_cand.confidence
            resolved_expr = best_cand.grain_expression
            rationale = (
                f"Provisional grain candidate: '{best_cand.grain_expression}' keyed by "
                f"({', '.join(best_cand.determinant_column_names)}) with {best_cand.uniqueness_ratio:.2%} uniqueness and {best_cand.duplicate_row_count} duplicate rows."
            )
        else:
            status = GrainStatus.UNKNOWN
            conf = 0.30
            resolved_expr = "UNKNOWN"
            rationale = "Candidate uniqueness too low to establish confirmed row grain."

        profile_id = f"grain_{dataset_id}_{sheet_id}"
        source_fps = [prof_map[cid].artifact_fingerprint for cid in best_cand.determinant_column_ids if cid in prof_map]

        artifact_fp = compute_grain_profile_fingerprint(
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            primary_entity=primary_entity,
            temporal_grain=temporal_grain,
            resolved_grain_expression=resolved_expr,
            best_candidate_ids=best_cand.determinant_column_ids,
            grain_status=status,
            policy_fingerprint=policy_fingerprint,
        )

        return SDRGrainProfile(
            profile_id=profile_id,
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            primary_entity=primary_entity,
            temporal_grain=temporal_grain,
            resolved_grain_expression=resolved_expr,
            grain_status=status,
            best_candidate=best_cand,
            ranked_candidates=ranked_candidates[:5],
            is_unique=best_cand.uniqueness_ratio >= 0.99,
            grain_confidence=conf,
            rationale=rationale,
            source_profile_fingerprints=source_fps,
            artifact_fingerprint=artifact_fp,
        )

    def _derive_primary_entity(
        self,
        candidate: GrainCandidate,
        prof_map: Mapping[str, SemanticColumnProfile],
    ) -> CanonicalGrain:
        """Determines primary canonical grain entity from candidate determinants."""
        for cid in candidate.determinant_column_ids:
            p = prof_map.get(cid)
            if not p:
                continue
            if p.entity_type_hypothesis in ENTITY_TO_CANONICAL_GRAIN:
                eg = ENTITY_TO_CANONICAL_GRAIN[p.entity_type_hypothesis]
                if eg not in (CanonicalGrain.UNKNOWN, CanonicalGrain.AMBIGUOUS):
                    return eg
            if p.semantic_role == SemanticColumnRole.ENTITY_IDENTIFIER:
                return CanonicalGrain.PERSON  # default entity fallback

        # If width > 1 with time and dimensions
        if candidate.width >= 2:
            return CanonicalGrain.COMPOSITE

        return CanonicalGrain.UNKNOWN

    def _derive_temporal_grain(
        self,
        candidate: GrainCandidate,
        prof_map: Mapping[str, SemanticColumnProfile],
    ) -> TemporalGrain:
        """Determines temporal grain participation from candidate determinants."""
        for cid in candidate.determinant_column_ids:
            p = prof_map.get(cid)
            if p and p.semantic_role == SemanticColumnRole.TIME:
                return map_temporal_frequency_from_profile(p)
        return TemporalGrain.NONE
