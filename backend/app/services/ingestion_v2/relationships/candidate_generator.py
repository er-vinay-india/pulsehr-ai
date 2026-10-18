"""
HighView Ingestion V2 — Phase I4: Relationship Candidate Generator
Stage 6: Relationship Discovery

Generates plausible cross-table structural relationship candidates.
Optimizes for high recall using multi-signal blocking while strictly preventing pairwise explosion.
Zero model / LLM calls. Fully deterministic.
"""

from __future__ import annotations

import itertools
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
)
from app.services.ingestion_v2.contracts.semantics import (
    SemanticColumnAssignment,
    SemanticColumnRole,
    SemanticEntityType,
    SemanticModel,
    TableSemanticModel,
)
from app.services.ingestion_v2.relationships.candidate_rules import (
    MAX_PAIRWISE_CANDIDATE_LIMIT,
    compute_entity_type_compatibility,
    compute_name_similarity,
    compute_physical_type_compatibility,
    compute_semantic_role_compatibility,
)
from app.services.ingestion_v2.relationships.candidate_signals import evaluate_candidate_signals


class CandidateGenerationStats:
    def __init__(self):
        self.raw_possible_pairs: int = 0
        self.pruned_candidate_pairs: int = 0
        self.validation_pairs: int = 0


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


def generate_candidates(
    normalized_dataset: NormalizedDataset,
    structural_profile: StructuralProfile,
    semantic_model: SemanticModel,
    grain_profile: GrainProfile,
    table_data: dict[str, pd.DataFrame] | None = None,
    stats_out: CandidateGenerationStats | None = None,
) -> RelationshipCandidateSet:
    """
    Stage 6 Entry Point: Generate relationship candidates across tables.

    Rules:
    - Scoped strictly to the same dataset/workspace.
    - Zero cross-dataset leakage.
    - High recall: validation stage will prune false positives.
    - Blocking heuristics prevent pairwise explosion on wide tables.
    """
    stats = stats_out or CandidateGenerationStats()
    candidates: list[RelationshipCandidate] = []

    # Map tables, profiles, and semantic assignments for quick lookups
    tbl_map: dict[str, NormalizedTable] = {t.table_id: t for t in normalized_dataset.tables}
    prof_map: dict[str, TableStructuralProfile] = {t.table_id: t for t in structural_profile.tables}
    sem_map: dict[str, TableSemanticModel] = {t.table_id: t for t in semantic_model.tables}
    grain_map = {t.table_id: t for t in (getattr(grain_profile, "table_grains", None) or getattr(grain_profile, "tables", []))}

    table_ids = [t.table_id for t in normalized_dataset.tables]
    table_pairs = list(itertools.combinations(table_ids, 2))

    for source_tid, target_tid in table_pairs:
        source_tbl = tbl_map[source_tid]
        target_tbl = tbl_map[target_tid]
        source_prof = prof_map.get(source_tid)
        target_prof = prof_map.get(target_tid)
        source_sem = sem_map.get(source_tid)
        target_sem = sem_map.get(target_tid)

        if not source_prof or not target_prof or not source_sem or not target_sem:
            continue

        source_col_profs = {c.column_name: c for c in source_prof.columns}
        target_col_profs = {c.column_name: c for c in target_prof.columns}
        s_sem_cols = getattr(source_sem, "columns", None) or getattr(source_sem, "column_assignments", [])
        t_sem_cols = getattr(target_sem, "columns", None) or getattr(target_sem, "column_assignments", [])
        source_col_sems = {c.column_name: c for c in s_sem_cols}
        target_col_sems = {c.column_name: c for c in t_sem_cols}

        # 1. Single Column Candidate Evaluation
        for s_col in source_tbl.columns:
            s_p = source_col_profs.get(s_col.column_name)
            s_s = source_col_sems.get(s_col.column_name)
            if not s_p or not s_s:
                continue

            s_role = getattr(s_s, "role", getattr(s_s, "semantic_role", None))

            # Blocking: Skip constant, all-null, free-text, or technical metadata columns
            if s_p.is_constant or s_p.null_ratio >= 0.99:
                continue
            if s_role in (SemanticColumnRole.FREE_TEXT, SemanticColumnRole.TECHNICAL_METADATA):
                continue

            for t_col in target_tbl.columns:
                stats.raw_possible_pairs += 1
                t_p = target_col_profs.get(t_col.column_name)
                t_s = target_col_sems.get(t_col.column_name)
                if not t_p or not t_s:
                    continue

                t_role = getattr(t_s, "role", getattr(t_s, "semantic_role", None))

                if t_p.is_constant or t_p.null_ratio >= 0.99:
                    stats.pruned_candidate_pairs += 1
                    continue
                if t_role in (SemanticColumnRole.FREE_TEXT, SemanticColumnRole.TECHNICAL_METADATA):
                    stats.pruned_candidate_pairs += 1
                    continue

                # Blocking: MEASURE paired with IDENTIFIER or DIMENSION is strictly blocked
                if (s_role == SemanticColumnRole.MEASURE and t_role != SemanticColumnRole.MEASURE) or \
                   (t_role == SemanticColumnRole.MEASURE and s_role != SemanticColumnRole.MEASURE):
                    stats.pruned_candidate_pairs += 1
                    continue

                # Blocking: Incompatible physical types
                type_compat = compute_physical_type_compatibility(s_p.physical_type, t_p.physical_type)
                if type_compat <= 0.0:
                    stats.pruned_candidate_pairs += 1
                    continue

                # Evaluate candidate signals
                sem_role_score = compute_semantic_role_compatibility(s_role, t_role)
                if sem_role_score <= 0.0:
                    stats.pruned_candidate_pairs += 1
                    continue

                entity_type_score = compute_entity_type_compatibility(s_s.entity_type, t_s.entity_type)
                if entity_type_score <= 0.0:
                    stats.pruned_candidate_pairs += 1
                    continue

                lexical_score = compute_name_similarity(s_col.column_name, t_col.column_name)

                # Candidate Confidence Score (Optimized for broad recall)
                candidate_confidence = round(
                    0.35 * lexical_score +
                    0.25 * sem_role_score +
                    0.25 * entity_type_score +
                    0.15 * type_compat,
                    4
                )

                # Broad acceptance filter: if >= 0.35 or high lexical or same entity identifier
                has_key_affinity = (
                    s_role == SemanticColumnRole.ENTITY_IDENTIFIER or
                    t_role == SemanticColumnRole.ENTITY_IDENTIFIER or
                    lexical_score >= 0.70
                )

                if candidate_confidence >= 0.35 and has_key_affinity:
                    cand_id = f"cand_{source_tid}_{s_col.column_id}__{target_tid}_{t_col.column_id}"
                    candidates.append(
                        RelationshipCandidate(
                            candidate_id=cand_id,
                            source_table_id=source_tid,
                            source_column_ids=[s_col.column_id],
                            target_table_id=target_tid,
                            target_column_ids=[t_col.column_id],
                            key_type=CandidateKeyType.SINGLE,
                            discovery_method="MULTI_SIGNAL_HEURISTIC",
                            confidence_score=candidate_confidence,
                        )
                    )
                    stats.validation_pairs += 1
                else:
                    stats.pruned_candidate_pairs += 1

                if len(candidates) >= MAX_PAIRWISE_CANDIDATE_LIMIT:
                    break

        # 2. Composite Key Candidate Evaluation
        # Inspect candidate composite keys from structural profiler or grain key columns
        source_composites = getattr(source_prof, "candidate_composite_keys", []) or []
        target_composites = getattr(target_prof, "candidate_composite_keys", []) or []

        # Also inspect grain profile composite key columns
        s_grain = grain_map.get(source_tid)
        t_grain = grain_map.get(target_tid)
        if s_grain and len(s_grain.key_columns) > 1:
            source_composites = list(source_composites) + [{"column_names": s_grain.key_columns}]
        if t_grain and len(t_grain.key_columns) > 1:
            target_composites = list(target_composites) + [{"column_names": t_grain.key_columns}]

        for s_comp in source_composites:
            s_names = s_comp.get("column_names") or []
            if len(s_names) < 2 or len(s_names) > 3:
                continue
            for t_comp in target_composites:
                t_names = t_comp.get("column_names") or []
                if len(t_names) != len(s_names):
                    continue

                # Check if columns can align pairwise
                aligned_pairs = []
                for s_name in s_names:
                    best_match = None
                    best_score = 0.0
                    for t_name in t_names:
                        sim = compute_name_similarity(s_name, t_name)
                        if sim > best_score and sim >= 0.70:
                            best_score = sim
                            best_match = t_name
                    if best_match:
                        aligned_pairs.append((s_name, best_match, best_score))

                if len(aligned_pairs) == len(s_names):
                    # Successfully aligned composite key!
                    s_cids = [source_tbl.columns[[c.column_name for c in source_tbl.columns].index(p[0])].column_id for p in aligned_pairs]
                    t_cids = [target_tbl.columns[[c.column_name for c in target_tbl.columns].index(p[1])].column_id for p in aligned_pairs]
                    avg_sim = round(sum(p[2] for p in aligned_pairs) / len(aligned_pairs), 4)

                    cand_id = f"cand_comp_{source_tid}__{target_tid}__{len(candidates)}"
                    candidates.append(
                        RelationshipCandidate(
                            candidate_id=cand_id,
                            source_table_id=source_tid,
                            source_column_ids=s_cids,
                            target_table_id=target_tid,
                            target_column_ids=t_cids,
                            key_type=CandidateKeyType.COMPOSITE,
                            discovery_method="COMPOSITE_GRAIN_ALIGNMENT",
                            confidence_score=avg_sim,
                        )
                    )
                    stats.validation_pairs += 1

    # Deterministic stage fingerprint
    cand_dicts = [c.model_dump() for c in candidates]
    stage_fp = compute_stage_fingerprint({
        "dataset_id": normalized_dataset.dataset_id,
        "candidates": cand_dicts,
    })

    return RelationshipCandidateSet(
        dataset_id=normalized_dataset.dataset_id,
        run_id=normalized_dataset.run_id,
        stage_name="relationship_discovery",
        source_fingerprint=stage_fp,
        provenance=list(normalized_dataset.provenance),
        candidates=candidates,
    )
