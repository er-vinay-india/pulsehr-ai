"""
HighView Semantic Data Refinery — Phase SDR-5
Relationship Candidate Discovery Engine

Discovers cross-sheet relationship candidates with early semantic and key pruning (bounded search).
Adheres strictly to the Core Law:
  SIMILAR COLUMNS != RELATIONSHIP
  RELATIONSHIP != SAFE JOIN
  SAFE JOIN != SAFE ANALYTICAL AGGREGATION
"""

from __future__ import annotations

import itertools
from typing import Any, Sequence
import pandas as pd

from app.services.ingestion_v2.contracts.relationships import (
    CandidateKeyType,
    RelationshipCardinality,
)
from app.services.ingestion_v2.contracts.semantics import (
    SemanticColumnRole,
    SemanticEntityType,
)
from app.services.sdr.contracts.grain import SDRGrainProfile
from app.services.sdr.contracts.keys import KeyCandidateStatus, SDRKeyCandidate
from app.services.sdr.contracts.policies import SDRPolicySuite
from app.services.sdr.contracts.profiles import (
    SemanticColumnProfile,
    SemanticConcept,
    SemanticDtype,
)
from app.services.sdr.contracts.relationships import (
    RelationshipClass,
    SDRRelationshipCandidate,
    compute_relationship_candidate_fingerprint,
)


class CandidateDiscoveryStats:
    """Telemetry tracking bounded search and pruning efficiency."""

    def __init__(self):
        self.sheets_count: int = 0
        self.columns_count: int = 0
        self.candidate_column_pairs_considered: int = 0
        self.pairs_pruned_semantically: int = 0
        self.key_compatible_pairs: int = 0
        self.relationship_candidates_evaluated: int = 0


class RelationshipDiscoveryEngine:
    """
    Offline deterministic engine for discovering cross-sheet relationship candidates.
    Applies multi-stage pruning to guarantee bounded pairwise search across large workbooks.
    """

    def __init__(self, policy_suite: SDRPolicySuite | None = None):
        self.policy_suite = policy_suite or SDRPolicySuite()
        self.policy_fingerprint = self.policy_suite.compute_policy_fingerprint()

    def discover_candidates(
        self,
        dataset_id: str,
        profiles_by_sheet: dict[str, Sequence[SemanticColumnProfile]],
        key_candidates_by_sheet: dict[str, Sequence[SDRKeyCandidate]] | None = None,
        grain_profiles_by_sheet: dict[str, SDRGrainProfile] | None = None,
        table_data: dict[str, pd.DataFrame] | None = None,
        dataset_version: str = "v1",
        stats_out: CandidateDiscoveryStats | None = None,
    ) -> tuple[list[SDRRelationshipCandidate], CandidateDiscoveryStats]:
        """
        Discovers candidate relationships across sheets in the same dataset.
        Zero cross-dataset leakage.
        """
        stats = stats_out or CandidateDiscoveryStats()
        sheet_ids = list(profiles_by_sheet.keys())
        stats.sheets_count = len(sheet_ids)
        stats.columns_count = sum(len(profs) for profs in profiles_by_sheet.values())

        candidates: list[SDRRelationshipCandidate] = []
        keys_by_sheet = key_candidates_by_sheet or {}
        grains_by_sheet = grain_profiles_by_sheet or {}

        # Pairwise sheet evaluation: combinations of 2 sheets
        sheet_pairs = list(itertools.combinations(sheet_ids, 2))

        for left_sheet, right_sheet in sheet_pairs:
            left_profs = {getattr(p, "source_name", getattr(p, "column_name", p.column_id)): p for p in profiles_by_sheet[left_sheet]}
            right_profs = {getattr(p, "source_name", getattr(p, "column_name", p.column_id)): p for p in profiles_by_sheet[right_sheet]}

            left_keys = keys_by_sheet.get(left_sheet, [])
            right_keys = keys_by_sheet.get(right_sheet, [])

            left_grain = grains_by_sheet.get(left_sheet)
            right_grain = grains_by_sheet.get(right_sheet)
            left_grain_expr = getattr(left_grain, "resolved_grain_expression", getattr(left_grain, "grain_expression", "UNKNOWN"))
            right_grain_expr = getattr(right_grain, "resolved_grain_expression", getattr(right_grain, "grain_expression", "UNKNOWN"))

            df_left = table_data.get(left_sheet) if table_data else None
            df_right = table_data.get(right_sheet) if table_data else None

            # Track which column pairs we have already evaluated as composite candidates
            composite_paired_cols: set[tuple[str, str]] = set()

            # -------------------------------------------------------------
            # Stage A: Composite Key Candidate Pairing from SDR-3 Keys
            # -------------------------------------------------------------
            composite_left_keys = [k for k in left_keys if k.width > 1 and k.status in (
                KeyCandidateStatus.HIGH_CONFIDENCE,
                KeyCandidateStatus.CANDIDATE,
                KeyCandidateStatus.HIGH_CONFIDENCE_CANDIDATE_KEY,
                KeyCandidateStatus.PLAUSIBLE_CANDIDATE_KEY,
            )]
            composite_right_keys = [k for k in right_keys if k.width > 1 and k.status in (
                KeyCandidateStatus.HIGH_CONFIDENCE,
                KeyCandidateStatus.CANDIDATE,
                KeyCandidateStatus.HIGH_CONFIDENCE_CANDIDATE_KEY,
                KeyCandidateStatus.PLAUSIBLE_CANDIDATE_KEY,
            )]

            # Check composite-to-composite or composite-to-matching columns
            for l_comp in composite_left_keys:
                l_col_names = sorted(l_comp.column_names)
                # Check if right sheet has exact matching names or matching composite key
                r_matching_cols = [c for c in l_col_names if c in right_profs]
                if len(r_matching_cols) == len(l_col_names):
                    # Canonical ordered column pairing
                    l_cols = l_col_names
                    r_cols = l_col_names  # Deterministic 1:1 mapping by name
                    cand = self._evaluate_candidate_pair(
                        dataset_id=dataset_id,
                        left_sheet=left_sheet,
                        right_sheet=right_sheet,
                        left_col_names=l_cols,
                        right_col_names=r_cols,
                        left_profs=left_profs,
                        right_profs=right_profs,
                        left_grain_expr=left_grain_expr,
                        right_grain_expr=right_grain_expr,
                        left_key_id=l_comp.candidate_id,
                        right_key_id=None,
                        df_left=df_left,
                        df_right=df_right,
                        dataset_version=dataset_version,
                        is_composite=True,
                    )
                    if cand:
                        candidates.append(cand)
                        stats.relationship_candidates_evaluated += 1
                        for lc, rc in zip(l_cols, r_cols):
                            composite_paired_cols.add((lc, rc))

            # -------------------------------------------------------------
            # Stage B: Single Column Candidate Search with Bounded Pruning
            # -------------------------------------------------------------
            for l_col_name, l_prof in left_profs.items():
                l_role = l_prof.semantic_role
                l_concept = l_prof.semantic_concept

                # Early Pruning Rule 1: Exclude non-joinable column types
                if l_role in (SemanticColumnRole.FREE_TEXT, SemanticColumnRole.TECHNICAL_METADATA):
                    continue
                if l_concept == SemanticConcept.FREE_TEXT:
                    continue
                if l_prof.features.distinct_count <= 1 and l_prof.features.row_count > 1:
                    continue  # Constant column

                for r_col_name, r_prof in right_profs.items():
                    stats.candidate_column_pairs_considered += 1

                    # Skip if already part of a valid composite relationship
                    if (l_col_name, r_col_name) in composite_paired_cols:
                        continue

                    r_role = r_prof.semantic_role
                    r_concept = r_prof.semantic_concept

                    if r_role in (SemanticColumnRole.FREE_TEXT, SemanticColumnRole.TECHNICAL_METADATA):
                        stats.pairs_pruned_semantically += 1
                        continue
                    if r_concept == SemanticConcept.FREE_TEXT:
                        stats.pairs_pruned_semantically += 1
                        continue
                    if r_prof.features.distinct_count <= 1 and r_prof.features.row_count > 1:
                        stats.pairs_pruned_semantically += 1
                        continue

                    # Early Pruning Rule 2: Strict measure exclusion
                    # (Measure to measure, or measure to dimension/identifier: NEVER a relationship)
                    if l_role == SemanticColumnRole.MEASURE or r_role == SemanticColumnRole.MEASURE:
                        stats.pairs_pruned_semantically += 1
                        continue
                    if l_concept == SemanticConcept.MEASURE or r_concept == SemanticConcept.MEASURE:
                        stats.pairs_pruned_semantically += 1
                        continue

                    # Early Pruning Rule 3: Incompatible physical & semantic dtypes
                    if not self._are_dtypes_compatible(l_prof, r_prof):
                        stats.pairs_pruned_semantically += 1
                        continue

                    # Early Pruning Rule 4: Key Affinity / Identifier Requirement
                    # At least one side must be an ENTITY_IDENTIFIER or high-uniqueness identifier/dimension
                    l_is_key_affinity = (
                        l_role in (SemanticColumnRole.ENTITY_IDENTIFIER, SemanticColumnRole.IDENTIFIER)
                        or l_concept == SemanticConcept.IDENTIFIER
                        or any(l_col_name in k.column_names for k in left_keys)
                    )
                    r_is_key_affinity = (
                        r_role in (SemanticColumnRole.ENTITY_IDENTIFIER, SemanticColumnRole.IDENTIFIER)
                        or r_concept == SemanticConcept.IDENTIFIER
                        or any(r_col_name in k.column_names for k in right_keys)
                    )

                    if not (l_is_key_affinity or r_is_key_affinity):
                        # Both sides are generic status/category/dimension columns without key affinity
                        # Same-name false match guard (e.g. status == status)
                        stats.pairs_pruned_semantically += 1
                        continue

                    stats.key_compatible_pairs += 1

                    # Evaluate candidate pair
                    l_key_id = next((k.candidate_id for k in left_keys if l_col_name in k.column_names), None)
                    r_key_id = next((k.candidate_id for k in right_keys if r_col_name in k.column_names), None)

                    cand = self._evaluate_candidate_pair(
                        dataset_id=dataset_id,
                        left_sheet=left_sheet,
                        right_sheet=right_sheet,
                        left_col_names=[l_col_name],
                        right_col_names=[r_col_name],
                        left_profs=left_profs,
                        right_profs=right_profs,
                        left_grain_expr=left_grain_expr,
                        right_grain_expr=right_grain_expr,
                        left_key_id=l_key_id,
                        right_key_id=r_key_id,
                        df_left=df_left,
                        df_right=df_right,
                        dataset_version=dataset_version,
                        is_composite=False,
                    )
                    if cand:
                        candidates.append(cand)
                        stats.relationship_candidates_evaluated += 1

        return candidates, stats

    def _are_dtypes_compatible(
        self,
        left_prof: SemanticColumnProfile,
        right_prof: SemanticColumnProfile,
    ) -> bool:
        """Determines if physical and semantic data types can plausibly participate in referential join."""
        l_phy = left_prof.physical_dtype.upper()
        r_phy = right_prof.physical_dtype.upper()

        # Both text-like
        l_is_str = any(t in l_phy for t in ["VARCHAR", "TEXT", "STRING", "CHAR", "OBJECT"])
        r_is_str = any(t in r_phy for t in ["VARCHAR", "TEXT", "STRING", "CHAR", "OBJECT"])
        if l_is_str and r_is_str:
            return True

        # Both integer/numeric
        l_is_num = any(t in l_phy for t in ["INT", "BIGINT", "SMALLINT", "FLOAT", "DOUBLE", "NUMERIC", "DECIMAL"])
        r_is_num = any(t in r_phy for t in ["INT", "BIGINT", "SMALLINT", "FLOAT", "DOUBLE", "NUMERIC", "DECIMAL"])
        if l_is_num and r_is_num:
            return True

        # Identifier codes that may be stored as numeric on one side and string on the other (e.g. 101 vs "101")
        if (l_is_str and r_is_num) or (l_is_num and r_is_str):
            if (
                left_prof.semantic_role in (SemanticColumnRole.ENTITY_IDENTIFIER, SemanticColumnRole.IDENTIFIER)
                or right_prof.semantic_role in (SemanticColumnRole.ENTITY_IDENTIFIER, SemanticColumnRole.IDENTIFIER)
            ):
                return True

        # Both date/time
        l_is_date = "DATE" in l_phy or "TIME" in l_phy or left_prof.semantic_dtype in (SemanticDtype.DATE, SemanticDtype.TIMESTAMP)
        r_is_date = "DATE" in r_phy or "TIME" in r_phy or right_prof.semantic_dtype in (SemanticDtype.DATE, SemanticDtype.TIMESTAMP)
        if l_is_date and r_is_date:
            return True

        return False

    def _evaluate_candidate_pair(
        self,
        dataset_id: str,
        left_sheet: str,
        right_sheet: str,
        left_col_names: list[str],
        right_col_names: list[str],
        left_profs: dict[str, SemanticColumnProfile],
        right_profs: dict[str, SemanticColumnProfile],
        left_grain_expr: str,
        right_grain_expr: str,
        left_key_id: str | None,
        right_key_id: str | None,
        df_left: pd.DataFrame | None,
        df_right: pd.DataFrame | None,
        dataset_version: str,
        is_composite: bool,
    ) -> SDRRelationshipCandidate | None:
        """Evaluates compatibility, calculates coverage/overlap, and constructs SDRRelationshipCandidate."""
        l_p = left_profs[left_col_names[0]]
        r_p = right_profs[right_col_names[0]]

        # Semantic compatibility score
        sem_compat = 0.5
        if l_p.semantic_role == r_p.semantic_role:
            sem_compat += 0.25
        if l_p.entity_type_hypothesis == r_p.entity_type_hypothesis and l_p.entity_type_hypothesis != SemanticEntityType.UNKNOWN:
            sem_compat += 0.25
        sem_compat = min(sem_compat, 1.0)

        # Name lexical score
        lex_scores = []
        for lc, rc in zip(left_col_names, right_col_names):
            ln, rn = lc.lower(), rc.lower()
            if ln == rn:
                lex_scores.append(1.0)
            elif ln in rn or rn in ln:
                lex_scores.append(0.8)
            else:
                lex_scores.append(0.3)
        avg_lex = sum(lex_scores) / len(lex_scores)

        # Referential coverage calculation
        left_cov = 0.0
        right_cov = 0.0
        ref_overlap = 0.0
        left_null_ratio = float(l_p.features.null_ratio)
        right_null_ratio = float(r_p.features.null_ratio)
        left_dup_ratio = max(0.0, 1.0 - float(l_p.features.distinct_ratio))
        right_dup_ratio = max(0.0, 1.0 - float(r_p.features.distinct_ratio))
        candidate_card = RelationshipCardinality.MANY_TO_ONE

        evidence: dict[str, Any] = {
            "is_composite": is_composite,
            "lexical_similarity": avg_lex,
            "left_columns": left_col_names,
            "right_columns": right_col_names,
        }

        if df_left is not None and df_right is not None:
            # Drop null keys separately (NULL == NULL is strictly forbidden)
            sub_l = df_left[left_col_names].dropna()
            sub_r = df_right[right_col_names].dropna()

            if len(sub_l) > 0 and len(sub_r) > 0:
                if len(left_col_names) == 1:
                    s_l = sub_l[left_col_names[0]].astype(str).str.strip().str.lower()
                    s_r = sub_r[right_col_names[0]].astype(str).str.strip().str.lower()
                    set_l = set(s_l.unique())
                    set_r = set(s_r.unique())
                    counts_l = s_l.value_counts()
                    counts_r = s_r.value_counts()
                else:
                    t_l = pd.Series(list(zip(*(sub_l[c].astype(str).str.strip().str.lower() for c in left_col_names))))
                    t_r = pd.Series(list(zip(*(sub_r[c].astype(str).str.strip().str.lower() for c in right_col_names))))
                    set_l = set(t_l.unique())
                    set_r = set(t_r.unique())
                    counts_l = t_l.value_counts()
                    counts_r = t_r.value_counts()

                intersection = set_l.intersection(set_r)
                if len(intersection) == 0:
                    return None

                union = set_l.union(set_r)
                ref_overlap = len(intersection) / max(len(union), 1)
                left_cov = len(intersection) / max(len(set_l), 1)
                right_cov = len(intersection) / max(len(set_r), 1)

                # Observed uniqueness
                max_freq_l = int(counts_l.max()) if len(counts_l) > 0 else 1
                max_freq_r = int(counts_r.max()) if len(counts_r) > 0 else 1

                if max_freq_l == 1 and max_freq_r == 1:
                    candidate_card = RelationshipCardinality.ONE_TO_ONE
                elif max_freq_l > 1 and max_freq_r == 1:
                    candidate_card = RelationshipCardinality.MANY_TO_ONE
                elif max_freq_l == 1 and max_freq_r > 1:
                    candidate_card = RelationshipCardinality.ONE_TO_MANY
                else:
                    candidate_card = RelationshipCardinality.MANY_TO_MANY

                evidence["matched_keys_count"] = len(intersection)
                evidence["left_unique_keys"] = len(set_l)
                evidence["right_unique_keys"] = len(set_r)
                evidence["max_left_frequency"] = max_freq_l
                evidence["max_right_frequency"] = max_freq_r
        else:
            # Fallback estimation from features
            if avg_lex < 0.6:
                return None
            ref_overlap = avg_lex
            left_cov = avg_lex
            right_cov = avg_lex
            if l_p.features.distinct_ratio >= 0.99 and r_p.features.distinct_ratio >= 0.99:
                candidate_card = RelationshipCardinality.ONE_TO_ONE
            elif l_p.features.distinct_ratio < 0.99 and r_p.features.distinct_ratio >= 0.99:
                candidate_card = RelationshipCardinality.MANY_TO_ONE
            elif l_p.features.distinct_ratio >= 0.99 and r_p.features.distinct_ratio < 0.99:
                candidate_card = RelationshipCardinality.ONE_TO_MANY
            else:
                candidate_card = RelationshipCardinality.MANY_TO_MANY

        # Confidence computation
        confidence = round(
            0.35 * avg_lex +
            0.25 * sem_compat +
            0.30 * ref_overlap +
            0.10 * (1.0 - max(left_null_ratio, right_null_ratio)),
            4
        )

        cand_id = f"cand_{left_sheet}_{'_'.join(left_col_names)}_to_{right_sheet}_{'_'.join(right_col_names)}"

        fp = compute_relationship_candidate_fingerprint(
            dataset_id=dataset_id,
            left_sheet_id=left_sheet,
            right_sheet_id=right_sheet,
            left_column_ids=left_col_names,
            right_column_ids=right_col_names,
            candidate_cardinality=candidate_card,
            dataset_version=dataset_version,
            policy_fingerprint=self.policy_fingerprint,
        )

        rel_class = RelationshipClass.STRUCTURAL_RELATIONSHIP
        if is_composite:
            rel_class = RelationshipClass.STRUCTURAL_RELATIONSHIP
        elif l_p.semantic_role in (SemanticColumnRole.LOCATION, SemanticColumnRole.ATTRIBUTE):
            rel_class = RelationshipClass.ENTITY_RELATIONSHIP

        return SDRRelationshipCandidate(
            candidate_id=cand_id,
            dataset_id=dataset_id,
            left_sheet_id=left_sheet,
            right_sheet_id=right_sheet,
            left_column_ids=left_col_names,
            right_column_ids=right_col_names,
            left_key_candidate_id=left_key_id,
            right_key_candidate_id=right_key_id,
            left_grain=left_grain_expr,
            right_grain=right_grain_expr,
            relationship_class=rel_class,
            semantic_compatibility=sem_compat,
            dtype_compatibility=1.0,
            normalized_value_compatibility=round(ref_overlap, 4),
            referential_overlap=round(ref_overlap, 4),
            left_coverage=round(left_cov, 4),
            right_coverage=round(right_cov, 4),
            left_null_ratio=round(left_null_ratio, 4),
            right_null_ratio=round(right_null_ratio, 4),
            left_duplicate_ratio=round(left_dup_ratio, 4),
            right_duplicate_ratio=round(right_dup_ratio, 4),
            candidate_cardinality=candidate_card,
            confidence=confidence,
            evidence=evidence,
            dataset_version=dataset_version,
            artifact_fingerprint=fp,
        )
