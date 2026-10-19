"""
HighView Semantic Data Refinery — Phase SDR-3
Candidate Key Evaluator & Minimality Engine
"""

from __future__ import annotations

from collections import Counter
import itertools
from typing import Any, Mapping, Sequence

from app.services.ingestion_v2.contracts.grain import TemporalGrain
from app.services.ingestion_v2.contracts.semantics import (
    SemanticColumnRole,
    SemanticConcept,
    SemanticEntityType,
)
from app.services.sdr.contracts.grain import SDRGrainProfile
from app.services.sdr.contracts.keys import (
    KeyAuthority,
    KeyCandidateStatus,
    KeyCandidateType,
    SDRKeyCandidate,
    compute_key_candidate_fingerprint,
)
from app.services.sdr.contracts.policies import KeyConfidencePolicy
from app.services.sdr.contracts.profiles import (
    SemanticColumnProfile,
    SemanticDtype,
)
from app.services.sdr.grain.candidate_pruner import (
    is_measure_column,
    is_system_row_identifier,
)

FREE_TEXT_NAME_PATTERNS = {
    "note", "notes", "description", "desc", "comment", "comments",
    "user_agent", "useragent", "narrative", "text", "summary", "remark", "remarks",
}


def is_free_text_column(profile: SemanticColumnProfile) -> bool:
    """Detects narrative or unconstrained free-text columns unsuitable for key candidacy."""
    if profile.semantic_role == SemanticColumnRole.FREE_TEXT:
        return True
    if profile.semantic_dtype == SemanticDtype.NATURAL_LANGUAGE_TEXT:
        name_lower = profile.source_name.lower().replace(" ", "_")
        if any(pat in name_lower for pat in FREE_TEXT_NAME_PATTERNS):
            return True
        if profile.semantic_concept not in (SemanticConcept.IDENTIFIER, SemanticConcept.DESCRIPTOR):
            return True
        # If average string length is high (> 40 chars)
        if profile.features.sample_values:
            avg_len = sum(len(str(v)) for v in profile.features.sample_values) / len(profile.features.sample_values)
            if avg_len > 40:
                return True
    return False


def is_eligible_key_column(profile: SemanticColumnProfile) -> bool:
    """Determines if a column is eligible for business candidate key evaluation."""
    if is_measure_column(profile):
        return False
    if is_free_text_column(profile):
        return False
    return True


class SDRCandidateKeyEvaluator:
    """
    Evaluates atomic and composite candidate keys.
    Computes exact structural uniqueness, null/duplicate quality,
    candidate minimality, grain compatibility, and stability.
    """

    def __init__(self, policy: KeyConfidencePolicy | None = None):
        self.policy = policy or KeyConfidencePolicy()

    @staticmethod
    def _get_column_values(column_data: Mapping[str, Sequence[Any]], profile: SemanticColumnProfile) -> Sequence[Any]:
        """Resolves column values from mapping whether keyed by column_id, source_name, or canonical_name."""
        if profile.column_id in column_data:
            return column_data[profile.column_id]
        if profile.source_name in column_data:
            return column_data[profile.source_name]
        if profile.canonical_name in column_data:
            return column_data[profile.canonical_name]
        return []

    def evaluate_key_candidates(
        self,
        dataset_id: str,
        sheet_id: str,
        profiles: Sequence[SemanticColumnProfile],
        grain_profile: SDRGrainProfile | None = None,
        column_data: Mapping[str, Sequence[Any]] | None = None,
        rows: Sequence[Mapping[str, Any]] | None = None,
        row_count: int | None = None,
        policy_fingerprint: str = "",
        source_declared_pk_columns: Sequence[str] | None = None,
    ) -> list[SDRKeyCandidate]:
        """Convenience entry point supporting row dictionaries and optional grain profile."""
        if rows is not None:
            norm_col_data: dict[str, list[Any]] = {}
            for p in profiles:
                vals = [r.get(p.source_name, r.get(p.column_id, r.get(p.canonical_name))) for r in rows]
                norm_col_data[p.column_id] = vals
                norm_col_data[p.source_name] = vals
                norm_col_data[p.canonical_name] = vals
            column_data = norm_col_data
            row_count = len(rows)
        elif column_data is not None:
            norm_col_data = dict(column_data)
            for p in profiles:
                if p.source_name in norm_col_data and p.column_id not in norm_col_data:
                    norm_col_data[p.column_id] = norm_col_data[p.source_name]
                elif p.column_id in norm_col_data and p.source_name not in norm_col_data:
                    norm_col_data[p.source_name] = norm_col_data[p.column_id]
            column_data = norm_col_data
            if row_count is None:
                row_count = max((len(v) for v in column_data.values()), default=0)
        else:
            column_data = {}
            row_count = 0

        if grain_profile is None:
            from app.services.ingestion_v2.contracts.grain import CanonicalGrain, TemporalGrain
            from app.services.sdr.contracts.grain import GrainStatus
            grain_profile = SDRGrainProfile(
                dataset_id=dataset_id,
                sheet_id=sheet_id,
                primary_entity=CanonicalGrain.UNKNOWN,
                temporal_grain=TemporalGrain.NONE,
                resolved_grain_expression="UNKNOWN",
                grain_status=GrainStatus.PROVISIONAL,
                grain_confidence=0.5,
                is_unique=False,
                rationale="Default inferred grain profile",
                profile_id=f"grain_{dataset_id}_{sheet_id}",
                artifact_fingerprint="fp_default_grain",
            )

        return self.evaluate_all_candidates(
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            profiles=profiles,
            grain_profile=grain_profile,
            column_data=column_data,
            row_count=row_count,
            policy_fingerprint=policy_fingerprint,
            source_declared_pk_columns=source_declared_pk_columns,
        )

    def evaluate_all_candidates(
        self,
        dataset_id: str,
        sheet_id: str,
        profiles: Sequence[SemanticColumnProfile],
        grain_profile: SDRGrainProfile,
        column_data: Mapping[str, Sequence[Any]],
        row_count: int,
        policy_fingerprint: str = "",
        source_declared_pk_columns: Sequence[str] | None = None,
    ) -> list[SDRKeyCandidate]:
        """
        Discovers, evaluates, and ranks candidate keys for a sheet.
        """
        if row_count == 0 or not profiles:
            return []

        prof_map = {p.column_id: p for p in profiles}
        name_map = {p.source_name.lower(): p for p in profiles}
        source_pk_set = set(c.lower() for c in (source_declared_pk_columns or []))

        # 1. Classify System Row IDs & Non-Key columns
        system_id_candidates = self._evaluate_system_row_ids(dataset_id, sheet_id, profiles, column_data, row_count, grain_profile, policy_fingerprint)

        # 2. Filter eligible columns for natural/composite business keys
        eligible_profiles = [p for p in profiles if is_eligible_key_column(p) and not is_system_row_identifier(p)]

        # 3. Evaluate single-column (atomic) candidates
        atomic_candidates = self._evaluate_atomic_candidates(
            dataset_id, sheet_id, eligible_profiles, column_data, row_count, grain_profile, policy_fingerprint, source_pk_set
        )

        # 4. Evaluate composite candidates (width 2 to max_composite_width)
        composite_candidates: list[SDRKeyCandidate] = []
        if self.policy.max_composite_width >= 2 and len(eligible_profiles) >= 2:
            composite_candidates = self._evaluate_composite_candidates(
                dataset_id, sheet_id, eligible_profiles, column_data, row_count, grain_profile, policy_fingerprint, atomic_candidates
            )

        # 5. Evaluate candidate minimality:
        # If a strict subset of candidate K already achieves equivalent uniqueness with <= nulls, K is non-minimal.
        all_eval_candidates = atomic_candidates + composite_candidates
        all_eval_candidates = self._enforce_minimality(all_eval_candidates, prof_map)

        # 6. Evaluate foreign-key-like candidate columns
        fk_candidates = self._evaluate_foreign_key_candidates(
            dataset_id, sheet_id, eligible_profiles, grain_profile, policy_fingerprint, source_pk_set, atomic_candidates
        )

        # Combine all candidates and rank
        combined = all_eval_candidates + system_id_candidates + fk_candidates

        # Rank candidates by status priority, key_confidence descending, width ascending, null_ratio ascending
        status_rank = {
            KeyCandidateStatus.PRIMARY_KEY_CONFIRMED: 5,
            KeyCandidateStatus.HIGH_CONFIDENCE: 4,
            KeyCandidateStatus.CANDIDATE: 3,
            KeyCandidateStatus.AMBIGUOUS: 2,
            KeyCandidateStatus.REJECTED: 1,
            KeyCandidateStatus.UNKNOWN: 0,
            KeyCandidateStatus.NON_KEY: 0,
        }

        ranked = sorted(
            combined,
            key=lambda c: (
                status_rank.get(c.status, 0),
                c.is_minimal,
                c.key_confidence,
                -c.width,
                -c.null_ratio,
            ),
            reverse=True,
        )

        # Gate on ambiguous top candidates
        self._tag_ambiguous_candidates(ranked)

        return ranked[:self.policy.max_candidates]

    def _evaluate_system_row_ids(
        self,
        dataset_id: str,
        sheet_id: str,
        profiles: Sequence[SemanticColumnProfile],
        column_data: Mapping[str, Sequence[Any]],
        row_count: int,
        grain_profile: SDRGrainProfile,
        policy_fingerprint: str,
    ) -> list[SDRKeyCandidate]:
        """Identifies and models technical system sequence columns as SYSTEM_ROW_ID."""
        results: list[SDRKeyCandidate] = []
        for p in profiles:
            if not is_system_row_identifier(p):
                continue

            vals = list(self._get_column_values(column_data, p))
            distinct_cnt = len(set(vals))
            uniq_ratio = distinct_cnt / float(row_count) if row_count > 0 else 0.0

            cand_id = f"key_{sheet_id}_{p.column_id}"
            fp = compute_key_candidate_fingerprint(
                dataset_id=dataset_id,
                sheet_id=sheet_id,
                column_ids=[p.column_id],
                candidate_type=KeyCandidateType.SYSTEM_ROW_ID,
                grain_expression=p.canonical_name.upper(),
                uniqueness_ratio=uniq_ratio,
                key_confidence=0.40,
                status=KeyCandidateStatus.REJECTED,
                grain_artifact_fingerprint=grain_profile.artifact_fingerprint,
                policy_fingerprint=policy_fingerprint,
            )

            cand = SDRKeyCandidate(
                candidate_id=cand_id,
                dataset_id=dataset_id,
                sheet_id=sheet_id,
                column_ids=[p.column_id],
                column_names=[p.source_name],
                candidate_type=KeyCandidateType.SYSTEM_ROW_ID,
                entity_type=SemanticEntityType.UNKNOWN,
                grain_expression=p.canonical_name.upper(),
                width=1,
                row_count=row_count,
                unique_combination_count=distinct_cnt,
                uniqueness_ratio=uniq_ratio,
                null_count=p.features.null_count,
                null_ratio=p.features.null_ratio,
                duplicate_combination_count=0,
                duplicate_row_count=0,
                semantic_support_score=0.10,
                grain_support_score=0.20,
                stability_score=1.0,
                minimality_score=1.0,
                is_minimal=True,
                key_confidence=0.40,
                authority=KeyAuthority.INFERRED,
                status=KeyCandidateStatus.REJECTED,
                evidence="System-assigned row counter or technical index; excluded from natural business key candidacy.",
                source_profile_fingerprints=[p.artifact_fingerprint],
                grain_artifact_fingerprint=grain_profile.artifact_fingerprint,
                artifact_fingerprint=fp,
            )
            results.append(cand)
        return results

    def _evaluate_atomic_candidates(
        self,
        dataset_id: str,
        sheet_id: str,
        eligible_profiles: Sequence[SemanticColumnProfile],
        column_data: Mapping[str, Sequence[Any]],
        row_count: int,
        grain_profile: SDRGrainProfile,
        policy_fingerprint: str,
        source_pk_set: set[str],
    ) -> list[SDRKeyCandidate]:
        """Evaluates single-column natural business key candidates."""
        candidates: list[SDRKeyCandidate] = []

        for p in eligible_profiles:
            vals = list(self._get_column_values(column_data, p))
            null_count = sum(1 for v in vals if v is None or (isinstance(v, str) and not v.strip()))
            null_ratio = null_count / float(row_count) if row_count > 0 else 0.0

            non_null_vals = [v for v in vals if v is not None and not (isinstance(v, str) and not v.strip())]
            counts = Counter(non_null_vals)
            unique_cnt = len(counts)
            dup_groups = sum(1 for _, c in counts.items() if c > 1)
            dup_rows = sum(c for _, c in counts.items() if c > 1)
            uniqueness_ratio = unique_cnt / float(row_count) if row_count > 0 else 0.0

            # Compute sample duplicate coordinates
            sample_dups: list[str] = []
            if dup_groups > 0:
                dup_sample_keys = [k for k, c in counts.items() if c > 1][:3]
                for k in dup_sample_keys:
                    row_idxs = [idx + 1 for idx, v in enumerate(vals) if v == k][:2]
                    sample_dups.append(f"('{k}',)")
                    sample_dups.append(f"value='{k}' (rows: {row_idxs})")

            # Semantic Support Score
            sem_score = 0.50
            if p.semantic_role == SemanticColumnRole.ENTITY_IDENTIFIER:
                sem_score = 0.95
            elif p.semantic_dtype == SemanticDtype.IDENTIFIER_CODE:
                sem_score = 0.85
            elif p.semantic_concept == SemanticConcept.IDENTIFIER:
                sem_score = 0.80
            elif p.semantic_role == SemanticColumnRole.ENTITY_LABEL:
                sem_score = 0.65
            elif p.semantic_role == SemanticColumnRole.DIMENSION:
                sem_score = 0.55

            # Grain Compatibility Score
            grain_support = 1.0
            grain_det_ids = grain_profile.best_candidate.determinant_column_ids if grain_profile.best_candidate else []
            if grain_profile.best_candidate and grain_profile.best_candidate.width > 1:
                # Single column only partially covers composite grain
                if p.column_id in grain_det_ids:
                    grain_support = 0.50  # necessary but insufficient alone
                else:
                    grain_support = 0.20
            elif grain_profile.best_candidate and grain_profile.best_candidate.width == 1:
                if p.column_id in grain_det_ids:
                    grain_support = 1.0
                else:
                    grain_support = 0.60

            # Stability Score (within current dataset evidence)
            stability = 1.0
            if null_ratio > self.policy.max_null_ratio:
                stability -= (null_ratio * 0.5)
            stability = max(0.20, min(1.0, stability))

            # Source declared check
            is_source_declared = (
                p.source_name.lower() in source_pk_set
                or p.canonical_name.lower() in source_pk_set
                or p.column_id.lower() in source_pk_set
            )
            authority = KeyAuthority.SOURCE_DECLARED if is_source_declared else KeyAuthority.INFERRED

            # Composite Key Confidence formula
            key_conf = (
                uniqueness_ratio * 0.40
                + sem_score * 0.25
                + grain_support * 0.25
                + stability * 0.10
            )
            # Severe penalty for nulls
            if null_ratio > self.policy.max_null_ratio:
                key_conf *= (1.0 - null_ratio)

            # Determine candidate type and status
            cand_type = KeyCandidateType.CANDIDATE_KEY
            status = KeyCandidateStatus.CANDIDATE

            if is_source_declared:
                cand_type = KeyCandidateType.CANDIDATE_KEY
                status = KeyCandidateStatus.PRIMARY_KEY_CONFIRMED
                evidence = f"Source-declared primary key '{p.source_name}'; confirmed per authoritative upstream metadata."
            elif uniqueness_ratio >= self.policy.min_uniqueness_for_high_confidence and null_ratio == 0.0 and grain_support >= 0.80 and sem_score >= 0.75:
                cand_type = KeyCandidateType.CANDIDATE_KEY
                status = KeyCandidateStatus.HIGH_CONFIDENCE
                evidence = f"Dominant atomic candidate key with {uniqueness_ratio:.2%} uniqueness and 0 nulls, aligned with grain '{grain_profile.resolved_grain_expression}'."
            elif grain_support < 0.60 and grain_profile.best_candidate and grain_profile.best_candidate.width > 1:
                cand_type = KeyCandidateType.CANDIDATE_KEY
                status = KeyCandidateStatus.REJECTED
                evidence = f"Semantically valid identifier, but insufficient alone to identify a row at composite grain '{grain_profile.resolved_grain_expression}'."
                key_conf = min(key_conf, 0.55)
            elif uniqueness_ratio >= self.policy.min_uniqueness_for_candidate:
                cand_type = KeyCandidateType.CANDIDATE_KEY
                status = KeyCandidateStatus.CANDIDATE
                evidence = f"Candidate key with {uniqueness_ratio:.2%} uniqueness and {dup_rows} duplicate rows across {dup_groups} duplicate groups."
            else:
                cand_type = KeyCandidateType.NON_KEY
                status = KeyCandidateStatus.NON_KEY
                evidence = f"Low uniqueness ({uniqueness_ratio:.2%}); insufficient discriminative power to identify individual rows."
                key_conf = min(key_conf, 0.40)

            cand_id = f"key_{sheet_id}_{p.column_id}"
            fp = compute_key_candidate_fingerprint(
                dataset_id=dataset_id,
                sheet_id=sheet_id,
                column_ids=[p.column_id],
                candidate_type=cand_type,
                grain_expression=p.canonical_name.upper(),
                uniqueness_ratio=uniqueness_ratio,
                key_confidence=key_conf,
                status=status,
                grain_artifact_fingerprint=grain_profile.artifact_fingerprint,
                policy_fingerprint=policy_fingerprint,
            )

            cand = SDRKeyCandidate(
                candidate_id=cand_id,
                dataset_id=dataset_id,
                sheet_id=sheet_id,
                column_ids=[p.column_id],
                column_names=[p.source_name],
                candidate_type=cand_type,
                entity_type=p.entity_type_hypothesis,
                grain_expression=p.canonical_name.upper(),
                width=1,
                row_count=row_count,
                unique_combination_count=unique_cnt,
                uniqueness_ratio=uniqueness_ratio,
                null_count=null_count,
                null_ratio=null_ratio,
                duplicate_combination_count=dup_groups,
                duplicate_row_count=dup_rows,
                semantic_support_score=sem_score,
                grain_support_score=grain_support,
                stability_score=stability,
                minimality_score=1.0,
                is_minimal=True,
                key_confidence=key_conf,
                authority=authority,
                status=status,
                evidence=evidence,
                sample_duplicate_coordinates=sample_dups,
                source_profile_fingerprints=[p.artifact_fingerprint],
                grain_artifact_fingerprint=grain_profile.artifact_fingerprint,
                artifact_fingerprint=fp,
            )
            candidates.append(cand)

        return candidates

    def _evaluate_composite_candidates(
        self,
        dataset_id: str,
        sheet_id: str,
        eligible_profiles: Sequence[SemanticColumnProfile],
        column_data: Mapping[str, Sequence[Any]],
        row_count: int,
        grain_profile: SDRGrainProfile,
        policy_fingerprint: str,
        atomic_candidates: list[SDRKeyCandidate],
    ) -> list[SDRKeyCandidate]:
        """
        Evaluates bounded composite combinations up to max_composite_width (<= 3).
        Only combinations aligned with grain or semantic pairings are screened.
        """
        prof_map = {p.column_id: p for p in eligible_profiles}
        composite_candidates: list[SDRKeyCandidate] = []

        # Find grain determinant column IDs to prioritize
        grain_det_ids = set(grain_profile.best_candidate.determinant_column_ids) if grain_profile.best_candidate else set()

        # Generate candidate combinations of width 2 and width 3
        combos: list[tuple[str, ...]] = []

        # Priority 1: Exact grain determinant combination if width >= 2
        if len(grain_det_ids) >= 2 and len(grain_det_ids) <= self.policy.max_composite_width:
            if all(cid in prof_map for cid in grain_det_ids):
                combos.append(tuple(sorted(grain_det_ids)))

        # Priority 2: Pairings involving at least 1 identifier/entity or 1 temporal column
        for w in range(2, min(self.policy.max_composite_width + 1, len(eligible_profiles) + 1)):
            for comb in itertools.combinations(eligible_profiles, w):
                col_ids = tuple(sorted(p.column_id for p in comb))
                if col_ids in combos:
                    continue
                # Prune pairs with 2 temporal columns
                time_cnt = sum(1 for p in comb if p.semantic_role == SemanticColumnRole.TIME)
                if time_cnt > 1:
                    continue
                # Must contain at least 1 entity/identifier or dimension
                has_entity_or_id = any(
                    p.semantic_role in (SemanticColumnRole.ENTITY_IDENTIFIER, SemanticColumnRole.DIMENSION)
                    or p.semantic_dtype == SemanticDtype.IDENTIFIER_CODE
                    for p in comb
                )
                if not has_entity_or_id:
                    continue
                combos.append(col_ids)
                if len(combos) >= 20:  # Bounded search cap
                    break
            if len(combos) >= 20:
                break

        for col_ids in combos:
            selected_profs = [prof_map[cid] for cid in col_ids]
            col_names = [p.source_name for p in selected_profs]
            grain_expr = " x ".join(p.canonical_name.upper() for p in selected_profs)

            # Evaluate composite uniqueness
            tuples = []
            cols_vals = [list(self._get_column_values(column_data, prof_map[cid])) for cid in col_ids]
            null_count = 0
            for row_i in range(row_count):
                row_tuple = tuple(cols_vals[c_i][row_i] if row_i < len(cols_vals[c_i]) else None for c_i in range(len(col_ids)))
                if any(v is None or (isinstance(v, str) and not v.strip()) for v in row_tuple):
                    null_count += 1
                else:
                    tuples.append(row_tuple)

            null_ratio = null_count / float(row_count) if row_count > 0 else 0.0
            counts = Counter(tuples)
            unique_cnt = len(counts)
            dup_groups = sum(1 for _, c in counts.items() if c > 1)
            dup_rows = sum(c for _, c in counts.items() if c > 1)
            uniqueness_ratio = unique_cnt / float(row_count) if row_count > 0 else 0.0

            # Semantic Support Score
            sem_score = sum(
                0.90 if p.semantic_role == SemanticColumnRole.ENTITY_IDENTIFIER
                else 0.80 if p.semantic_role == SemanticColumnRole.TIME
                else 0.60
                for p in selected_profs
            ) / float(len(selected_profs))

            # Grain Support Score
            is_matching_temporal_grain = (
                not grain_det_ids
                and grain_profile.temporal_grain != TemporalGrain.NONE
                and any(
                    p.semantic_role in (SemanticColumnRole.TIME, SemanticColumnRole.TIMESTAMP)
                    or p.semantic_concept == SemanticConcept.TIME_SPAN
                    for p in selected_profs
                )
                and any(
                    p.semantic_role in (SemanticColumnRole.ENTITY_IDENTIFIER, SemanticColumnRole.IDENTIFIER, SemanticColumnRole.DIMENSION)
                    or p.semantic_concept == SemanticConcept.IDENTIFIER
                    for p in selected_profs
                )
            )
            is_exact_grain = (set(col_ids) == grain_det_ids) or is_matching_temporal_grain
            is_superset_of_grain = grain_det_ids.issubset(set(col_ids)) and len(col_ids) > len(grain_det_ids) if grain_det_ids else False
            if is_exact_grain:
                grain_support = 1.0
            elif is_superset_of_grain:
                grain_support = 0.70  # Contains grain but redundant
            else:
                grain_support = 0.60

            stability = max(0.20, 1.0 - (null_ratio * 0.5))

            key_conf = (
                uniqueness_ratio * 0.45
                + sem_score * 0.25
                + grain_support * 0.20
                + stability * 0.10
            )
            if null_ratio > self.policy.max_null_ratio:
                key_conf *= (1.0 - null_ratio)

            status = KeyCandidateStatus.CANDIDATE
            cand_type = KeyCandidateType.COMPOSITE_CANDIDATE_KEY
            if uniqueness_ratio >= self.policy.min_uniqueness_for_high_confidence and null_ratio == 0.0 and is_exact_grain:
                status = KeyCandidateStatus.HIGH_CONFIDENCE
                cand_type = KeyCandidateType.COMPOSITE_NATURAL_KEY
                evidence = f"High-confidence composite candidate key ({', '.join(col_names)}) with {uniqueness_ratio:.2%} uniqueness, strictly matching table grain."
            elif uniqueness_ratio >= self.policy.min_uniqueness_for_candidate:
                status = KeyCandidateStatus.CANDIDATE
                evidence = f"Composite candidate key ({', '.join(col_names)}) with {uniqueness_ratio:.2%} uniqueness and {dup_rows} duplicate rows."
            else:
                status = KeyCandidateStatus.UNKNOWN
                evidence = f"Composite combination ({', '.join(col_names)}) has low uniqueness ({uniqueness_ratio:.2%})."
                key_conf = min(key_conf, 0.40)

            cand_id = f"key_{sheet_id}_{'_'.join(col_ids)}"
            fps = [prof_map[cid].artifact_fingerprint for cid in col_ids]
            fp = compute_key_candidate_fingerprint(
                dataset_id=dataset_id,
                sheet_id=sheet_id,
                column_ids=list(col_ids),
                candidate_type=KeyCandidateType.COMPOSITE_CANDIDATE_KEY,
                grain_expression=grain_expr,
                uniqueness_ratio=uniqueness_ratio,
                key_confidence=key_conf,
                status=status,
                grain_artifact_fingerprint=grain_profile.artifact_fingerprint,
                policy_fingerprint=policy_fingerprint,
            )

            cand = SDRKeyCandidate(
                candidate_id=cand_id,
                dataset_id=dataset_id,
                sheet_id=sheet_id,
                column_ids=list(col_ids),
                column_names=col_names,
                candidate_type=KeyCandidateType.COMPOSITE_CANDIDATE_KEY,
                entity_type=SemanticEntityType.UNKNOWN,
                grain_expression=grain_expr,
                width=len(col_ids),
                row_count=row_count,
                unique_combination_count=unique_cnt,
                uniqueness_ratio=uniqueness_ratio,
                null_count=null_count,
                null_ratio=null_ratio,
                duplicate_combination_count=dup_groups,
                duplicate_row_count=dup_rows,
                semantic_support_score=sem_score,
                grain_support_score=grain_support,
                stability_score=stability,
                minimality_score=1.0,
                is_minimal=True,
                key_confidence=key_conf,
                authority=KeyAuthority.INFERRED,
                status=status,
                evidence=evidence,
                sample_duplicate_coordinates=[],
                source_profile_fingerprints=fps,
                grain_artifact_fingerprint=grain_profile.artifact_fingerprint,
                artifact_fingerprint=fp,
            )
            composite_candidates.append(cand)

        return composite_candidates

    def _enforce_minimality(
        self,
        candidates: list[SDRKeyCandidate],
        prof_map: Mapping[str, SemanticColumnProfile],
    ) -> list[SDRKeyCandidate]:
        """
        CRITICAL MINIMALITY REQUIREMENT:
        For candidate set K: if a strict subset S of K has equivalent identity quality
        (uniqueness(S) >= uniqueness(K) - tolerance and null_ratio(S) <= null_ratio(K)),
        then K is non-minimal and must be rejected or demoted.
        """
        refined: list[SDRKeyCandidate] = []

        # Map candidate sets
        cand_by_cols = {frozenset(c.column_ids): c for c in candidates}

        for cand in candidates:
            cand_cols = frozenset(cand.column_ids)
            if cand.width == 1:
                refined.append(cand)
                continue

            # Check if any strict proper subset S of cand_cols exists that is already unique
            is_minimal = True
            violating_subset_names = []

            for other in candidates:
                if other.candidate_id == cand.candidate_id:
                    continue
                other_cols = frozenset(other.column_ids)
                if other_cols.issubset(cand_cols) and len(other_cols) < len(cand_cols):
                    # other is a strict proper subset!
                    if other.uniqueness_ratio >= (cand.uniqueness_ratio - self.policy.minimality_tolerance) and other.null_ratio <= cand.null_ratio:
                        is_minimal = False
                        violating_subset_names.append(", ".join(other.column_names))

            if not is_minimal:
                # Demote non-minimal candidate
                demoted_evidence = (
                    f"Non-minimal composite candidate: strictly proper subset ({', '.join(violating_subset_names)}) "
                    f"already achieves equivalent uniqueness ({cand.uniqueness_ratio:.2%}). Redundant determinant columns rejected."
                )
                demoted_cand = cand.model_copy(
                    update={
                        "is_minimal": False,
                        "minimality_score": 0.20,
                        "status": KeyCandidateStatus.REJECTED,
                        "key_confidence": min(cand.key_confidence, 0.45),
                        "evidence": demoted_evidence,
                    }
                )
                refined.append(demoted_cand)
            else:
                refined.append(cand)

        return refined

    def _evaluate_foreign_key_candidates(
        self,
        dataset_id: str,
        sheet_id: str,
        eligible_profiles: Sequence[SemanticColumnProfile],
        grain_profile: SDRGrainProfile,
        policy_fingerprint: str,
        source_pk_set: set[str] | None = None,
        atomic_candidates: list[SDRKeyCandidate] | None = None,
    ) -> list[SDRKeyCandidate]:
        """
        Tags foreign-key-like candidate columns as local semantic hypotheses.
        STRICT BOUNDARY: Does NOT assert cross-table relationship or referential validity.
        """
        if len(eligible_profiles) <= 1:
            return []

        fk_candidates: list[SDRKeyCandidate] = []
        grain_det_ids = set(grain_profile.best_candidate.determinant_column_ids) if grain_profile.best_candidate else set()
        pk_set = source_pk_set or set()
        dominant_cand_cols = {
            c.column_ids[0] for c in (atomic_candidates or [])
            if len(c.column_ids) == 1 and c.status in (KeyCandidateStatus.PRIMARY_KEY_CONFIRMED, KeyCandidateStatus.HIGH_CONFIDENCE)
        }

        for p in eligible_profiles:
            # Exclude source-declared or dominant candidate keys of this sheet
            if (
                p.source_name.lower() in pk_set
                or p.canonical_name.lower() in pk_set
                or p.column_id.lower() in pk_set
                or p.column_id in dominant_cand_cols
            ):
                continue

            # Check if column looks like a reference identifier to an external domain
            is_fk_like = False
            name_lower = p.source_name.lower()
            if (
                p.semantic_role in (SemanticColumnRole.ENTITY_IDENTIFIER, SemanticColumnRole.DIMENSION)
                or p.semantic_dtype == SemanticDtype.IDENTIFIER_CODE
            ):
                if p.column_id not in grain_det_ids and ("_id" in name_lower or "id_" in name_lower or "_code" in name_lower):
                    is_fk_like = True

            if is_fk_like:
                cand_id = f"fk_{sheet_id}_{p.column_id}"
                fp = compute_key_candidate_fingerprint(
                    dataset_id=dataset_id,
                    sheet_id=sheet_id,
                    column_ids=[p.column_id],
                    candidate_type=KeyCandidateType.FOREIGN_KEY_CANDIDATE,
                    grain_expression=p.canonical_name.upper(),
                    uniqueness_ratio=p.features.distinct_ratio,
                    key_confidence=0.70,
                    status=KeyCandidateStatus.CANDIDATE,
                    grain_artifact_fingerprint=grain_profile.artifact_fingerprint,
                    policy_fingerprint=policy_fingerprint,
                )

                cand = SDRKeyCandidate(
                    candidate_id=cand_id,
                    dataset_id=dataset_id,
                    sheet_id=sheet_id,
                    column_ids=[p.column_id],
                    column_names=[p.source_name],
                    candidate_type=KeyCandidateType.FOREIGN_KEY_CANDIDATE,
                    entity_type=p.entity_type_hypothesis,
                    grain_expression=p.canonical_name.upper(),
                    width=1,
                    row_count=p.features.row_count,
                    unique_combination_count=p.features.distinct_count,
                    uniqueness_ratio=p.features.distinct_ratio,
                    null_count=p.features.null_count,
                    null_ratio=p.features.null_ratio,
                    duplicate_combination_count=0,
                    duplicate_row_count=0,
                    semantic_support_score=0.75,
                    grain_support_score=0.50,
                    stability_score=1.0,
                    minimality_score=1.0,
                    is_minimal=True,
                    key_confidence=0.70,
                    authority=KeyAuthority.INFERRED,
                    status=KeyCandidateStatus.CANDIDATE,
                    evidence="Local reference identifier hypothesis; cross-table referential validation deferred to SDR-5.",
                    sample_duplicate_coordinates=[],
                    source_profile_fingerprints=[p.artifact_fingerprint],
                    grain_artifact_fingerprint=grain_profile.artifact_fingerprint,
                    artifact_fingerprint=fp,
                )
                fk_candidates.append(cand)

        return fk_candidates

    def _tag_ambiguous_candidates(self, ranked: list[SDRKeyCandidate]) -> None:
        """
        Tags top competing candidate keys as AMBIGUOUS if their confidence and uniqueness
        are within ambiguity_margin.
        """
        valid_candidates = [c for c in ranked if c.status in (KeyCandidateStatus.HIGH_CONFIDENCE, KeyCandidateStatus.CANDIDATE) and c.candidate_type != KeyCandidateType.FOREIGN_KEY_CANDIDATE]
        if len(valid_candidates) >= 2:
            first = valid_candidates[0]
            second = valid_candidates[1]
            if first.status == KeyCandidateStatus.HIGH_CONFIDENCE and second.status == KeyCandidateStatus.HIGH_CONFIDENCE:
                # Both are valid clean candidate keys; preserve HIGH_CONFIDENCE
                return
            if (
                abs(first.key_confidence - second.key_confidence) <= self.policy.ambiguity_margin
                and abs(first.uniqueness_ratio - second.uniqueness_ratio) <= self.policy.ambiguity_margin
                and set(first.column_ids) != set(second.column_ids)
            ):
                # Tag both as AMBIGUOUS
                for i, c in enumerate(ranked):
                    if c.candidate_id in (first.candidate_id, second.candidate_id):
                        ranked[i] = c.model_copy(
                            update={
                                "status": KeyCandidateStatus.AMBIGUOUS,
                                "evidence": (
                                    f"Competing candidate key: '{', '.join(c.column_names)}' has equivalent discriminative power "
                                    f"to alternative candidate key; withholds single primary key presumption."
                                ),
                            }
                        )


SDRKeyCandidateEvaluator = SDRCandidateKeyEvaluator
