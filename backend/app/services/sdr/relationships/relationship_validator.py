"""
HighView Semantic Data Refinery — Phase SDR-5
Relationship Validator Engine

Deterministically verifies referential integrity, bidirectional coverage, cardinality, and null safety.
Zero LLM / model calls. Fully deterministic.
"""

from __future__ import annotations

from typing import Any, Sequence
import pandas as pd

from app.services.ingestion_v2.contracts.relationships import (
    CandidateKeyType,
    RelationshipCardinality,
    RelationshipStatus,
)
from app.services.sdr.contracts.policies import SDRPolicySuite
from app.services.sdr.contracts.profiles import SemanticColumnProfile
from app.services.sdr.contracts.relationships import (
    RelationshipClass,
    SDRRelationshipCandidate,
    SDRValidatedRelationshipEdge,
    compute_validated_edge_fingerprint,
)


class RelationshipValidatorEngine:
    """
    Offline deterministic referee that validates relationship candidates.
    Distinguishes high-precision referential integrity from coincidental overlap.
    """

    def __init__(
        self,
        min_coverage: float = 0.50,
        min_confidence: float = 0.65,
        policy_suite: SDRPolicySuite | None = None,
    ):
        self.min_coverage = min_coverage
        self.min_confidence = min_confidence
        self.policy_suite = policy_suite or SDRPolicySuite()
        self.policy_fingerprint = self.policy_suite.compute_policy_fingerprint()

    def validate_candidate(
        self,
        candidate: SDRRelationshipCandidate,
        df_left: pd.DataFrame | None = None,
        df_right: pd.DataFrame | None = None,
        left_profiles: dict[str, SemanticColumnProfile] | None = None,
        right_profiles: dict[str, SemanticColumnProfile] | None = None,
    ) -> SDRValidatedRelationshipEdge:
        """
        Mathematically verifies a candidate relationship.
        Evaluates referential coverage, unmatched keys, nulls, cardinality, and grain preservation.
        """
        l_cols = candidate.left_column_ids
        r_cols = candidate.right_column_ids
        is_composite = len(l_cols) > 1
        key_type = CandidateKeyType.COMPOSITE if is_composite else CandidateKeyType.SINGLE

        # 1. Non-structural/Entity relationship class guard
        if candidate.relationship_class in (
            RelationshipClass.SEMANTIC_RELATIONSHIP,
            RelationshipClass.ANALYTICAL_RELATIONSHIP,
            RelationshipClass.RETRIEVAL_SIMILARITY,
        ):
            return self._build_rejected_edge(
                candidate=candidate,
                key_type=key_type,
                reason=f"Relationship class {candidate.relationship_class.value} is not eligible for structural validation.",
            )

        # 2. Detailed Data Verification (if DataFrames provided)
        if df_left is not None and df_right is not None:
            # Drop null keys separately (NULL == NULL is strictly forbidden)
            left_valid = df_left[l_cols].dropna()
            right_valid = df_right[r_cols].dropna()

            left_null_count = len(df_left) - len(left_valid)
            right_null_count = len(df_right) - len(right_valid)

            if len(left_valid) == 0 or len(right_valid) == 0:
                return self._build_rejected_edge(
                    candidate=candidate,
                    key_type=key_type,
                    reason="One or both sides contain zero non-null key values.",
                )

            if not is_composite:
                s_l = left_valid[l_cols[0]].astype(str).str.strip().str.lower()
                s_r = right_valid[r_cols[0]].astype(str).str.strip().str.lower()
                keys_l = set(s_l.unique())
                keys_r = set(s_r.unique())
                freqs_l = s_l.value_counts()
                freqs_r = s_r.value_counts()
            else:
                t_l = pd.Series(list(zip(*(left_valid[c].astype(str).str.strip().str.lower() for c in l_cols))))
                t_r = pd.Series(list(zip(*(right_valid[c].astype(str).str.strip().str.lower() for c in r_cols))))
                keys_l = set(t_l.unique())
                keys_r = set(t_r.unique())
                freqs_l = t_l.value_counts()
                freqs_r = t_r.value_counts()

            matched_keys = keys_l.intersection(keys_r)
            unmatched_l = len(keys_l) - len(matched_keys)
            unmatched_r = len(keys_r) - len(matched_keys)

            left_cov = len(matched_keys) / max(len(keys_l), 1)
            right_cov = len(matched_keys) / max(len(keys_r), 1)
            ref_cov = len(matched_keys) / max(len(keys_l.union(keys_r)), 1)

            max_freq_l = int(freqs_l.max()) if len(freqs_l) > 0 else 1
            max_freq_r = int(freqs_r.max()) if len(freqs_r) > 0 else 1

            # Exact matched pairs: For each matched key k: pairs(k) = count_left(k) * count_right(k)
            matched_pairs = sum(int(freqs_l.get(k, 0)) * int(freqs_r.get(k, 0)) for k in matched_keys)
            left_total_rows = len(df_left) if df_left is not None else len(keys_l)
            right_total_rows = len(df_right) if df_right is not None else len(keys_r)

            unmatched_left_rows = sum(int(freqs_l.get(k, 0)) for k in (keys_l - matched_keys)) + left_null_count
            unmatched_right_rows = sum(int(freqs_r.get(k, 0)) for k in (keys_r - matched_keys)) + right_null_count

            # Estimated result rows for standard LEFT join: matched pairs + unmatched left rows
            estimated_result_rows = matched_pairs + unmatched_left_rows
            expansion_ratio = round(estimated_result_rows / max(left_total_rows, 1), 4)
            max_freq_bound = max_freq_l * max_freq_r

            # Deterministic observed cardinality
            if max_freq_l == 1 and max_freq_r == 1:
                cardinality = RelationshipCardinality.ONE_TO_ONE
                multiplier = 1.0
            elif max_freq_l > 1 and max_freq_r == 1:
                cardinality = RelationshipCardinality.MANY_TO_ONE
                multiplier = float(max_freq_l)
            elif max_freq_l == 1 and max_freq_r > 1:
                cardinality = RelationshipCardinality.ONE_TO_MANY
                multiplier = float(max_freq_r)
            else:
                cardinality = RelationshipCardinality.MANY_TO_MANY
                multiplier = float(max(max_freq_l, max_freq_r))

            evidence: dict[str, Any] = {
                "left_rows": left_total_rows,
                "right_rows": right_total_rows,
                "matched_distinct_keys": len(matched_keys),
                "matched_pairs": matched_pairs,
                "unmatched_left_rows": unmatched_left_rows,
                "unmatched_right_rows": unmatched_right_rows,
                "estimated_result_rows": estimated_result_rows,
                "expansion_ratio": expansion_ratio,
                "max_frequency_bound": max_freq_bound,
                "matched_keys_count": len(matched_keys),
                "unmatched_left": unmatched_l,
                "unmatched_right": unmatched_r,
                "left_unique_keys": len(keys_l),
                "right_unique_keys": len(keys_r),
                "max_left_frequency": max_freq_l,
                "max_right_frequency": max_freq_r,
                "left_null_count": left_null_count,
                "right_null_count": right_null_count,
            }
        else:
            # Fallback to candidate pre-computed metrics
            left_cov = candidate.left_coverage
            right_cov = candidate.right_coverage
            ref_cov = candidate.referential_overlap
            cardinality = candidate.candidate_cardinality
            multiplier = 1.0 if cardinality == RelationshipCardinality.ONE_TO_ONE else 2.0
            unmatched_l = int((1.0 - left_cov) * 100)
            unmatched_r = int((1.0 - right_cov) * 100)
            left_null_count = 0
            right_null_count = 0
            left_total_rows = 100
            right_total_rows = 100
            matched_pairs = int(left_cov * 100)
            unmatched_left_rows = int((1.0 - left_cov) * 100)
            unmatched_right_rows = int((1.0 - right_cov) * 100)
            estimated_result_rows = matched_pairs + unmatched_left_rows
            expansion_ratio = round(estimated_result_rows / max(left_total_rows, 1), 4)
            max_freq_bound = 1 if cardinality == RelationshipCardinality.ONE_TO_ONE else 2
            evidence = dict(candidate.evidence)
            evidence.update({
                "left_rows": left_total_rows,
                "right_rows": right_total_rows,
                "matched_distinct_keys": int(left_cov * 100),
                "matched_pairs": matched_pairs,
                "unmatched_left_rows": unmatched_left_rows,
                "unmatched_right_rows": unmatched_right_rows,
                "estimated_result_rows": estimated_result_rows,
                "expansion_ratio": expansion_ratio,
                "max_frequency_bound": max_freq_bound,
            })

        # 3. Coverage and Ambiguity Hard Gates
        # If referential overlap is exceptionally low (< 0.20), it is REJECTED or AMBIGUOUS
        if ref_cov < 0.20 or (left_cov < 0.25 and right_cov < 0.25):
            status = RelationshipStatus.AMBIGUOUS if ref_cov >= 0.10 else RelationshipStatus.REJECTED
            reason = f"Insufficient referential coverage: overlap={ref_cov:.2f}, left={left_cov:.2f}, right={right_cov:.2f}."
            return self._build_edge(
                candidate=candidate,
                key_type=key_type,
                cardinality=cardinality,
                status=status,
                ref_cov=ref_cov,
                left_cov=left_cov,
                right_cov=right_cov,
                unmatched_l=unmatched_l,
                unmatched_r=unmatched_r,
                left_null_count=left_null_count,
                right_null_count=right_null_count,
                multiplier=multiplier,
                confidence=min(candidate.confidence, 0.40),
                rejection_reason=reason,
                evidence=evidence,
            )

        # 4. Same-name false positive guard
        # If confidence is below minimum threshold
        confidence = round(
            0.40 * ref_cov +
            0.30 * min(left_cov, right_cov) +
            0.20 * candidate.semantic_compatibility +
            0.10 * (1.0 - min(candidate.left_null_ratio, candidate.right_null_ratio)),
            4
        )

        if confidence < self.min_confidence:
            return self._build_edge(
                candidate=candidate,
                key_type=key_type,
                cardinality=cardinality,
                status=RelationshipStatus.AMBIGUOUS,
                ref_cov=ref_cov,
                left_cov=left_cov,
                right_cov=right_cov,
                unmatched_l=unmatched_l,
                unmatched_r=unmatched_r,
                left_null_count=left_null_count,
                right_null_count=right_null_count,
                multiplier=multiplier,
                confidence=confidence,
                rejection_reason="Confidence below acceptance threshold.",
                evidence=evidence,
            )

        # 5. Acceptance
        is_grain_preserving = (cardinality in (RelationshipCardinality.ONE_TO_ONE, RelationshipCardinality.MANY_TO_ONE))
        duplication_risk = (cardinality in (RelationshipCardinality.ONE_TO_MANY, RelationshipCardinality.MANY_TO_MANY))

        return self._build_edge(
            candidate=candidate,
            key_type=key_type,
            cardinality=cardinality,
            status=RelationshipStatus.VALIDATED,
            ref_cov=ref_cov,
            left_cov=left_cov,
            right_cov=right_cov,
            unmatched_l=unmatched_l,
            unmatched_r=unmatched_r,
            left_null_count=left_null_count,
            right_null_count=right_null_count,
            multiplier=multiplier,
            confidence=confidence,
            rejection_reason=None,
            is_grain_preserving=is_grain_preserving,
            duplication_risk_flag=duplication_risk,
            evidence=evidence,
        )

    def validate_candidates(
        self,
        candidates: Sequence[SDRRelationshipCandidate],
        table_data: dict[str, pd.DataFrame] | None = None,
        profiles_by_sheet: dict[str, Sequence[SemanticColumnProfile]] | None = None,
    ) -> list[SDRValidatedRelationshipEdge]:
        """Validates a batch of candidates."""
        validated_edges: list[SDRValidatedRelationshipEdge] = []
        for cand in candidates:
            df_l = table_data.get(cand.left_sheet_id) if table_data else None
            df_r = table_data.get(cand.right_sheet_id) if table_data else None
            edge = self.validate_candidate(cand, df_left=df_l, df_right=df_r)
            validated_edges.append(edge)
        return validated_edges

    def _build_edge(
        self,
        candidate: SDRRelationshipCandidate,
        key_type: CandidateKeyType,
        cardinality: RelationshipCardinality,
        status: RelationshipStatus,
        ref_cov: float,
        left_cov: float,
        right_cov: float,
        unmatched_l: int,
        unmatched_r: int,
        left_null_count: int,
        right_null_count: int,
        multiplier: float,
        confidence: float,
        rejection_reason: str | None = None,
        is_grain_preserving: bool = True,
        duplication_risk_flag: bool = False,
        evidence: dict[str, Any] | None = None,
    ) -> SDRValidatedRelationshipEdge:
        edge_id = f"edge_{candidate.left_sheet_id}_{'_'.join(candidate.left_column_ids)}_to_{candidate.right_sheet_id}_{'_'.join(candidate.right_column_ids)}"
        evidence_dict = evidence or {}
        key_fps: list[str] = []
        if candidate.left_key_candidate_id:
            key_fps.append(candidate.left_key_candidate_id)
        if candidate.right_key_candidate_id:
            key_fps.append(candidate.right_key_candidate_id)
        grain_fps: list[str] = [candidate.left_grain, candidate.right_grain]

        fp = compute_validated_edge_fingerprint(
            edge_id=edge_id,
            candidate_id=candidate.candidate_id,
            dataset_id=candidate.dataset_id,
            left_sheet_id=candidate.left_sheet_id,
            right_sheet_id=candidate.right_sheet_id,
            left_column_ids=candidate.left_column_ids,
            right_column_ids=candidate.right_column_ids,
            cardinality=cardinality,
            status=status,
            dataset_version=candidate.dataset_version,
            policy_fingerprint=self.policy_fingerprint,
            key_fingerprints=key_fps,
            grain_fingerprints=grain_fps,
        )

        return SDRValidatedRelationshipEdge(
            edge_id=edge_id,
            candidate_id=candidate.candidate_id,
            dataset_id=candidate.dataset_id,
            left_sheet_id=candidate.left_sheet_id,
            right_sheet_id=candidate.right_sheet_id,
            left_column_ids=candidate.left_column_ids,
            right_column_ids=candidate.right_column_ids,
            key_type=key_type,
            cardinality=cardinality,
            status=status,
            relationship_class=candidate.relationship_class,
            referential_coverage=round(ref_cov, 4),
            left_coverage=round(left_cov, 4),
            right_coverage=round(right_cov, 4),
            unmatched_left_count=unmatched_l,
            unmatched_right_count=unmatched_r,
            left_null_count=left_null_count,
            right_null_count=right_null_count,
            confidence=round(confidence, 4),
            estimated_row_multiplier=round(multiplier, 2),
            left_grain=candidate.left_grain,
            right_grain=candidate.right_grain,
            is_grain_preserving=is_grain_preserving,
            duplication_risk_flag=duplication_risk_flag,
            left_rows=evidence_dict.get("left_rows", 0),
            right_rows=evidence_dict.get("right_rows", 0),
            matched_distinct_keys=evidence_dict.get("matched_distinct_keys", 0),
            matched_pairs=evidence_dict.get("matched_pairs", 0),
            unmatched_left_rows=evidence_dict.get("unmatched_left_rows", 0),
            unmatched_right_rows=evidence_dict.get("unmatched_right_rows", 0),
            estimated_result_rows=evidence_dict.get("estimated_result_rows", 0),
            expansion_ratio=evidence_dict.get("expansion_ratio", 1.0),
            max_frequency_bound=evidence_dict.get("max_frequency_bound", int(multiplier)),
            key_fingerprints=key_fps,
            grain_fingerprints=grain_fps,
            policy_fingerprint=self.policy_fingerprint,
            rejection_reason=rejection_reason,
            validation_evidence=evidence_dict,
            dataset_version=candidate.dataset_version,
            artifact_fingerprint=fp,
        )

    def _build_rejected_edge(
        self,
        candidate: SDRRelationshipCandidate,
        key_type: CandidateKeyType,
        reason: str,
    ) -> SDRValidatedRelationshipEdge:
        return self._build_edge(
            candidate=candidate,
            key_type=key_type,
            cardinality=candidate.candidate_cardinality,
            status=RelationshipStatus.REJECTED,
            ref_cov=0.0,
            left_cov=0.0,
            right_cov=0.0,
            unmatched_l=0,
            unmatched_r=0,
            left_null_count=0,
            right_null_count=0,
            multiplier=1.0,
            confidence=0.0,
            rejection_reason=reason,
            is_grain_preserving=False,
            duplication_risk_flag=False,
            evidence={"rejection_reason": reason},
        )
