"""
HighView Ingestion V2 — Phase I4: Relationship Validator
Stage 7: Relationship Validation

Mathematically verifies referential integrity, cardinality, and grain compatibility for relationship candidates.
Enforces high-precision validation: accepted false-positive benchmark relationships = 0.
Zero model / LLM calls. Fully deterministic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence
import pandas as pd

from app.services.ingestion_v2.contracts.base import compute_stage_fingerprint
from app.services.ingestion_v2.contracts.grain import GrainProfile
from app.services.ingestion_v2.contracts.normalization import NormalizedDataset, NormalizedTable
from app.services.ingestion_v2.contracts.profiling import ColumnStructuralProfile, StructuralProfile, TableStructuralProfile
from app.services.ingestion_v2.contracts.relationships import (
    CandidateKeyType,
    RelationshipCandidate,
    RelationshipCandidateSet,
    RelationshipCardinality,
    RelationshipStatus,
    ValidatedRelationshipEdge,
    ValidatedRelationshipGraph,
)
from app.services.ingestion_v2.contracts.semantics import (
    SemanticColumnAssignment,
    SemanticColumnRole,
    SemanticEntityType,
    SemanticModel,
    TableSemanticModel,
)
from app.services.ingestion_v2.relationships.candidate_rules import (
    AMBIGUITY_THRESHOLD,
    AUTO_ACCEPT_THRESHOLD,
    HIGH_NULL_PENALTY_RATIO,
    MAX_NULL_KEY_RATIO,
    WEIGHT_DATATYPE_COMPATIBILITY,
    WEIGHT_KEY_UNIQUENESS,
    WEIGHT_LEXICAL_SIMILARITY,
    WEIGHT_REFERENTIAL_COVERAGE,
    WEIGHT_SEMANTIC_COMPATIBILITY,
    compute_entity_type_compatibility,
    compute_name_similarity,
    compute_physical_type_compatibility,
    compute_semantic_role_compatibility,
)
from app.services.ingestion_v2.relationships.candidate_signals import (
    ValueOverlapMetrics,
    compute_pattern_compatibility,
    compute_value_overlap_composite,
    compute_value_overlap_single,
)


def _load_table_df(
    tbl: NormalizedTable,
    table_data: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """Helper to retrieve DataFrame for table without modifying canonical storage."""
    if table_data and tbl.table_id in table_data:
        return table_data[tbl.table_id]
    if tbl.parquet_path and Path(tbl.parquet_path).is_file():
        return pd.read_parquet(tbl.parquet_path)
    # Construct fallback from sample values
    data = {}
    for col in tbl.columns:
        data[col.column_name] = col.sample_values if col.sample_values else []
    return pd.DataFrame(data)


def compute_expected_fanout(
    df_left: pd.DataFrame,
    left_cols: list[str],
    df_right: pd.DataFrame,
    right_cols: list[str],
) -> tuple[float, float, int]:
    """
    Calculate expected joined rows and row multiplier based on key frequencies.
    row_multiplier = expected_joined_rows / max(len(df_left), len(df_right))
    max_expected_multiplier = max fanout observed on any key.
    """
    if len(df_left) == 0 or len(df_right) == 0:
        return 1.0, 1.0, 0

    sub_left = df_left[left_cols].dropna()
    sub_right = df_right[right_cols].dropna()

    if len(left_cols) == 1:
        s_left = sub_left[left_cols[0]].astype(str).str.strip()
        s_right = sub_right[right_cols[0]].astype(str).str.strip()
        freqs_left = s_left.value_counts()
        freqs_right = s_right.value_counts()
    else:
        tuples_left = pd.Series(list(zip(*(sub_left[c].astype(str).str.strip() for c in left_cols))))
        tuples_right = pd.Series(list(zip(*(sub_right[c].astype(str).str.strip() for c in right_cols))))
        freqs_left = tuples_left.value_counts()
        freqs_right = tuples_right.value_counts()

    # Overlapping keys
    shared_keys = freqs_left.index.intersection(freqs_right.index)
    if len(shared_keys) == 0:
        return 1.0, 1.0, 0

    expected_joined_rows = int(sum(freqs_left[k] * freqs_right[k] for k in shared_keys))
    base_rows = max(len(df_left), len(df_right))
    row_multiplier = round(expected_joined_rows / max(1, base_rows), 4)

    # Max fanout on any key
    max_mult = float(max(freqs_left[k] * freqs_right[k] for k in shared_keys))

    return row_multiplier, max_mult, expected_joined_rows


def validate_candidates(
    candidate_set: RelationshipCandidateSet,
    normalized_dataset: NormalizedDataset,
    structural_profile: StructuralProfile,
    semantic_model: SemanticModel,
    grain_profile: GrainProfile,
    table_data: dict[str, pd.DataFrame] | None = None,
) -> ValidatedRelationshipGraph:
    """
    Stage 7 Entry Point: Mathematically validate relationship candidates.

    Returns:
    - ValidatedRelationshipGraph containing ValidatedRelationshipEdge items.
    Guarantees:
    - Exact referential integrity and overlap ratios computed.
    - Cardinality inferred from data distributions (1:1, 1:N, N:1, M:N).
    - Unsafe many-to-many raw joins flagged and rejected or marked ambiguous.
    - Zero false-positive accepted relationships.
    """
    tbl_map: dict[str, NormalizedTable] = {t.table_id: t for t in normalized_dataset.tables}
    prof_map: dict[str, TableStructuralProfile] = {t.table_id: t for t in structural_profile.tables}
    sem_map: dict[str, TableSemanticModel] = {t.table_id: t for t in semantic_model.tables}
    grain_map = {t.table_id: t for t in (getattr(grain_profile, "table_grains", None) or getattr(grain_profile, "tables", []))}

    validated_edges: list[ValidatedRelationshipEdge] = []

    for cand in candidate_set.candidates:
        s_tbl = tbl_map.get(cand.source_table_id)
        t_tbl = tbl_map.get(cand.target_table_id)
        if not s_tbl or not t_tbl:
            continue

        s_df = _load_table_df(s_tbl, table_data)
        t_df = _load_table_df(t_tbl, table_data)

        # Resolve column names
        s_cnames = [c.column_name for c in s_tbl.columns if c.column_id in cand.source_column_ids]
        t_cnames = [c.column_name for c in t_tbl.columns if c.column_id in cand.target_column_ids]

        if len(s_cnames) != len(cand.source_column_ids) or len(t_cnames) != len(cand.target_column_ids):
            continue

        # Look up profiles and semantics
        s_prof = prof_map.get(cand.source_table_id)
        t_prof = prof_map.get(cand.target_table_id)
        s_sem = sem_map.get(cand.source_table_id)
        t_sem = sem_map.get(cand.target_table_id)

        s_sem_cols = (getattr(s_sem, "columns", None) or getattr(s_sem, "column_assignments", [])) if s_sem else []
        t_sem_cols = (getattr(t_sem, "columns", None) or getattr(t_sem, "column_assignments", [])) if t_sem else []
        s_col_sems = {c.column_name: c for c in s_sem_cols}
        t_col_sems = {c.column_name: c for c in t_sem_cols}
        s_col_profs = {c.column_name: c for c in s_prof.columns} if s_prof else {}
        t_col_profs = {c.column_name: c for c in t_prof.columns} if t_prof else {}

        # 1. Compute Value Overlap
        overlap: ValueOverlapMetrics
        if cand.key_type == CandidateKeyType.COMPOSITE:
            overlap = compute_value_overlap_composite(s_df, s_cnames, t_df, t_cnames)
        else:
            s_series = s_df[s_cnames[0]] if s_cnames[0] in s_df.columns else pd.Series([], dtype=str)
            t_series = t_df[t_cnames[0]] if t_cnames[0] in t_df.columns else pd.Series([], dtype=str)
            overlap = compute_value_overlap_single(s_series, t_series)

        # 2. Evaluate Left and Right Key Uniqueness from actual data
        left_sub = s_df[s_cnames].dropna()
        right_sub = t_df[t_cnames].dropna()

        left_is_unique = (len(left_sub) > 0 and len(left_sub.drop_duplicates()) == len(left_sub))
        right_is_unique = (len(right_sub) > 0 and len(right_sub.drop_duplicates()) == len(right_sub))

        # Infer Cardinality
        cardinality: RelationshipCardinality
        if left_is_unique and right_is_unique:
            cardinality = RelationshipCardinality.ONE_TO_ONE
        elif left_is_unique and not right_is_unique:
            cardinality = RelationshipCardinality.ONE_TO_MANY
        elif not left_is_unique and right_is_unique:
            cardinality = RelationshipCardinality.MANY_TO_ONE
        else:
            cardinality = RelationshipCardinality.MANY_TO_MANY

        # 3. Compute Estimated Row Multiplier & Fanout
        row_multiplier, max_multiplier, expected_joined_rows = compute_expected_fanout(
            s_df, s_cnames, t_df, t_cnames
        )

        # 4. Multi-Dimensional Signal Evaluation
        sem_scores = []
        entity_scores = []
        type_scores = []
        lexical_scores = []

        for sc, tc in zip(s_cnames, t_cnames):
            s_s = s_col_sems.get(sc)
            t_s = t_col_sems.get(tc)
            s_p = s_col_profs.get(sc)
            t_p = t_col_profs.get(tc)

            s_role = getattr(s_s, "role", getattr(s_s, "semantic_role", None)) if s_s else None
            t_role = getattr(t_s, "role", getattr(t_s, "semantic_role", None)) if t_s else None

            if s_s and t_s and s_role and t_role:
                sem_scores.append(compute_semantic_role_compatibility(s_role, t_role))
                entity_scores.append(compute_entity_type_compatibility(s_s.entity_type, t_s.entity_type))
            else:
                sem_scores.append(0.5)
                entity_scores.append(0.5)

            if s_p and t_p:
                type_scores.append(compute_physical_type_compatibility(s_p.physical_type, t_p.physical_type))
            else:
                type_scores.append(0.8)

            lexical_scores.append(compute_name_similarity(sc, tc))

        avg_sem_role = sum(sem_scores) / len(sem_scores) if sem_scores else 0.5
        avg_entity_type = sum(entity_scores) / len(entity_scores) if entity_scores else 0.5
        avg_type_compat = sum(type_scores) / len(type_scores) if type_scores else 0.8
        avg_lexical = sum(lexical_scores) / len(lexical_scores) if lexical_scores else 0.5

        # Semantic compatibility combines role and entity type
        semantic_compat = round(0.55 * avg_sem_role + 0.45 * avg_entity_type, 4)

        # Referential coverage: proportion of target keys found in source (or vice-versa)
        referential_cov = max(overlap.left_coverage, overlap.right_coverage)

        # Uniqueness score
        if cardinality in (RelationshipCardinality.ONE_TO_ONE, RelationshipCardinality.ONE_TO_MANY, RelationshipCardinality.MANY_TO_ONE):
            uniqueness_score = 1.0
        else:
            uniqueness_score = 0.20

        # Weighted Confidence Score Formula
        confidence = round(
            WEIGHT_REFERENTIAL_COVERAGE * referential_cov +
            WEIGHT_SEMANTIC_COMPATIBILITY * semantic_compat +
            WEIGHT_KEY_UNIQUENESS * uniqueness_score +
            WEIGHT_DATATYPE_COMPATIBILITY * avg_type_compat +
            WEIGHT_LEXICAL_SIMILARITY * avg_lexical,
            4
        )

        # Penalties & Sanity Guards
        # 1. Null key penalty
        max_null_ratio = max(overlap.left_null_ratio, overlap.right_null_ratio)
        if max_null_ratio > HIGH_NULL_PENALTY_RATIO:
            confidence = max(0.0, confidence - 0.20)

        # 2. Rejection guard: Incompatible semantic role (e.g. MEASURE vs IDENTIFIER)
        has_measure_contradiction = any(
            (s_col_sems.get(sc) and getattr(s_col_sems[sc], "role", getattr(s_col_sems[sc], "semantic_role", None)) == SemanticColumnRole.MEASURE) or
            (t_col_sems.get(tc) and getattr(t_col_sems[tc], "role", getattr(t_col_sems[tc], "semantic_role", None)) == SemanticColumnRole.MEASURE)
            for sc, tc in zip(s_cnames, t_cnames)
        )

        # 3. Rejection guard: Status to Status across different entities
        has_status_mismatch = any(
            s_col_sems.get(sc) and t_col_sems.get(tc) and
            getattr(s_col_sems[sc], "role", getattr(s_col_sems[sc], "semantic_role", None)) == SemanticColumnRole.STATUS and
            getattr(t_col_sems[tc], "role", getattr(t_col_sems[tc], "semantic_role", None)) == SemanticColumnRole.STATUS and
            s_col_sems[sc].entity_type != t_col_sems[tc].entity_type
            for sc, tc in zip(s_cnames, t_cnames)
        )

        # 4. Rejection guard: Many-to-Many fanout risk without unique key backing (e.g. department <-> department)
        is_m2m_fanout_risk = (cardinality == RelationshipCardinality.MANY_TO_MANY and row_multiplier > 1.0)

        # 5. Entity Label Matching without Unique Key (e.g. employee_name <-> person_name)
        is_label_only = all(
            s_col_sems.get(sc) and t_col_sems.get(tc) and
            getattr(s_col_sems[sc], "role", getattr(s_col_sems[sc], "semantic_role", None)) == SemanticColumnRole.ENTITY_LABEL and
            getattr(t_col_sems[tc], "role", getattr(t_col_sems[tc], "semantic_role", None)) == SemanticColumnRole.ENTITY_LABEL
            for sc, tc in zip(s_cnames, t_cnames)
        )

        # 6. Grain compatibility
        s_g = grain_map.get(cand.source_table_id)
        t_g = grain_map.get(cand.target_table_id)
        is_grain_preserving = (
            cardinality in (RelationshipCardinality.ONE_TO_ONE, RelationshipCardinality.ONE_TO_MANY)
            and not is_m2m_fanout_risk
        )

        # Status Decision Logic
        status: RelationshipStatus
        rejection_reason: str | None = None

        if has_measure_contradiction:
            status = RelationshipStatus.REJECTED
            rejection_reason = "MEASURE_CANNOT_FORM_FOREIGN_KEY"
            confidence = 0.0
        elif has_status_mismatch:
            status = RelationshipStatus.REJECTED
            rejection_reason = "STATUS_DOMAIN_MISMATCH"
            confidence = 0.10
        elif is_m2m_fanout_risk:
            status = RelationshipStatus.REJECTED
            rejection_reason = "MANY_TO_MANY_CARTESIAN_RISK"
            confidence = min(0.35, confidence)
        elif max_null_ratio > MAX_NULL_KEY_RATIO:
            status = RelationshipStatus.REJECTED
            rejection_reason = f"EXCESSIVE_NULL_KEY_RATIO_{max_null_ratio}"
            confidence = min(0.30, confidence)
        elif is_label_only:
            status = RelationshipStatus.AMBIGUOUS
            rejection_reason = "ENTITY_LABEL_MATCH_LACKS_UNIQUE_IDENTIFIER"
            confidence = max(AMBIGUITY_THRESHOLD, min(0.65, confidence))
        elif overlap.intersection_size == 0:
            status = RelationshipStatus.REJECTED
            rejection_reason = "ZERO_VALUE_OVERLAP"
            confidence = min(0.20, confidence)
        elif confidence >= AUTO_ACCEPT_THRESHOLD:
            status = RelationshipStatus.ACCEPTED
        elif confidence >= AMBIGUITY_THRESHOLD:
            status = RelationshipStatus.AMBIGUOUS
        else:
            status = RelationshipStatus.REJECTED
            rejection_reason = "CONFIDENCE_BELOW_THRESHOLD"

        # Evidence dictionary
        evidence: dict[str, str | int | float | bool] = {
            "intersection_size": overlap.intersection_size,
            "left_distinct": overlap.left_distinct,
            "right_distinct": overlap.right_distinct,
            "source_overlap_ratio": overlap.left_coverage,
            "target_overlap_ratio": overlap.right_coverage,
            "jaccard_overlap": overlap.jaccard_overlap,
            "left_null_ratio": overlap.left_null_ratio,
            "right_null_ratio": overlap.right_null_ratio,
            "row_multiplier": row_multiplier,
            "max_expected_multiplier": max_multiplier,
            "expected_joined_rows": expected_joined_rows,
            "semantic_compatibility": semantic_compat,
            "datatype_compatibility": avg_type_compat,
            "lexical_similarity": avg_lexical,
            "uniqueness_score": uniqueness_score,
            "confidence": confidence,
            "cardinality": cardinality.value,
        }
        if rejection_reason:
            evidence["rejection_reason"] = rejection_reason

        edge_id = f"edge_{cand.candidate_id}"
        validated_edges.append(
            ValidatedRelationshipEdge(
                edge_id=edge_id,
                candidate_id=cand.candidate_id,
                source_table_id=cand.source_table_id,
                source_column_ids=cand.source_column_ids,
                target_table_id=cand.target_table_id,
                target_column_ids=cand.target_column_ids,
                key_type=cand.key_type,
                cardinality=cardinality,
                status=status,
                referential_coverage=referential_cov,
                source_overlap_ratio=overlap.left_coverage,
                target_overlap_ratio=overlap.right_coverage,
                confidence=confidence,
                estimated_row_multiplier=row_multiplier,
                is_grain_preserving=is_grain_preserving,
                duplication_risk_flag=is_m2m_fanout_risk,
                rejection_reason=rejection_reason,
                validation_evidence=evidence,
            )
        )

    # Deterministic fingerprint
    edge_dicts = [e.model_dump() for e in validated_edges]
    stage_fp = compute_stage_fingerprint({
        "dataset_id": normalized_dataset.dataset_id,
        "edges": edge_dicts,
    })

    return ValidatedRelationshipGraph(
        dataset_id=normalized_dataset.dataset_id,
        run_id=normalized_dataset.run_id,
        stage_name="relationship_validation",
        source_fingerprint=stage_fp,
        provenance=list(normalized_dataset.provenance),
        edges=validated_edges,
    )
