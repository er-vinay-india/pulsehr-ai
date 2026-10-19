"""
HighView Semantic Data Refinery — Phase SDR-3
Observed Local Functional Dependency Engine
"""

from __future__ import annotations

from collections import defaultdict
import itertools
from typing import Any, Mapping, Sequence

from app.services.ingestion_v2.contracts.semantics import SemanticColumnRole
from app.services.sdr.contracts.keys import (
    KeyCandidateStatus,
    ObservedFunctionalDependency,
    SDRKeyCandidate,
    compute_fd_fingerprint,
)
from app.services.sdr.contracts.policies import KeyConfidencePolicy
from app.services.sdr.contracts.profiles import (
    SemanticColumnProfile,
)
from app.services.sdr.keys.candidate_evaluator import (
    is_eligible_key_column,
)


class SDRFunctionalDependencyEngine:
    """
    Discovers deterministic local functional dependencies (X -> Y) within a sheet.
    Prunes combinatorial search by prioritizing candidate keys and dimensions,
    excluding continuous measures and free text as determinants.
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

    def discover_functional_dependencies(
        self,
        dataset_id: str,
        sheet_id: str,
        profiles: Sequence[SemanticColumnProfile],
        column_data: Mapping[str, Sequence[Any]] | None = None,
        rows: Sequence[Mapping[str, Any]] | None = None,
        row_count: int | None = None,
        key_candidates: Sequence[SDRKeyCandidate] | None = None,
        candidates: Sequence[SDRKeyCandidate] | None = None,
        policy_fingerprint: str = "",
    ) -> list[ObservedFunctionalDependency]:
        """
        Discovers local functional dependencies supported by the current dataset evidence.
        """
        # Normalize rows to column_data if provided
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

        if row_count == 0 or len(profiles) < 2:
            return []

        prof_map = {p.column_id: p for p in profiles}
        name_to_id = {p.source_name.lower(): p.column_id for p in profiles}
        name_to_id.update({p.column_id.lower(): p.column_id for p in profiles})

        # 1. Determinant candidate filtering:
        # Determinants must be eligible key columns or dimensions (no measures, no free text)
        determinant_candidates: list[tuple[str, ...]] = []

        all_candidates = list(candidates if candidates is not None else (key_candidates or []))

        # High priority determinants: from top key candidates
        for kc in all_candidates:
            if kc.is_minimal and kc.status not in (KeyCandidateStatus.REJECTED, KeyCandidateStatus.NON_KEY):
                col_ids = []
                if hasattr(kc, "column_ids") and kc.column_ids:
                    col_ids = list(kc.column_ids)
                elif hasattr(kc, "column_names") and kc.column_names:
                    col_ids = [name_to_id.get(c.lower(), c) for c in kc.column_names]
                if col_ids and len(col_ids) <= self.policy.fd_max_determinant_width:
                    t = tuple(col_ids)
                    if t not in determinant_candidates:
                        determinant_candidates.append(t)

        # Secondary determinants: individual identifier/dimension columns
        for p in profiles:
            if is_eligible_key_column(p):
                single = (p.column_id,)
                if single not in determinant_candidates:
                    determinant_candidates.append(single)

        # Cap determinant pool to avoid Cartesian explosion
        determinant_candidates = determinant_candidates[:15]

        # Dependent candidates: all other columns
        dependencies: list[ObservedFunctionalDependency] = []

        for det_col_ids in determinant_candidates:
            det_names = [prof_map[cid].source_name for cid in det_col_ids if cid in prof_map]
            if not det_names:
                continue

            for dep_p in profiles:
                if dep_p.column_id in det_col_ids:
                    continue  # Trivial dependency X -> X

                # Evaluate X -> Y
                support, violations = self._evaluate_dependency(
                    det_col_ids=det_col_ids,
                    dep_col_id=dep_p.column_id,
                    prof_map=prof_map,
                    column_data=column_data,
                    row_count=row_count,
                )

                if support >= self.policy.fd_min_support:
                    fd_id = f"fd_{sheet_id}_{'_'.join(det_col_ids)}_to_{dep_p.column_id}"
                    fp = compute_fd_fingerprint(
                        dataset_id=dataset_id,
                        sheet_id=sheet_id,
                        determinant_column_ids=list(det_col_ids),
                        dependent_column_ids=[dep_p.column_id],
                        support_ratio=support,
                        violation_count=violations,
                        policy_fingerprint=policy_fingerprint,
                    )

                    rationale = (
                        f"Observed local functional dependency: ({', '.join(det_names)}) -> {dep_p.source_name} "
                        f"with {support:.2%} support and {violations} violations across {row_count} rows."
                    )

                    fd = ObservedFunctionalDependency(
                        fd_id=fd_id,
                        dataset_id=dataset_id,
                        sheet_id=sheet_id,
                        determinant_column_ids=list(det_col_ids),
                        determinant_column_names=det_names,
                        dependent_column_ids=[dep_p.column_id],
                        dependent_column_names=[dep_p.source_name],
                        support_ratio=support,
                        violation_count=violations,
                        scope="CURRENT_DATASET",
                        confidence=round(support, 4),
                        rationale=rationale,
                        artifact_fingerprint=fp,
                    )
                    dependencies.append(fd)

        # Sort dependencies by support descending, violation_count ascending
        dependencies.sort(key=lambda d: (d.support_ratio, -d.violation_count), reverse=True)
        return dependencies[:30]

    def _evaluate_dependency(
        self,
        det_col_ids: tuple[str, ...],
        dep_col_id: str,
        prof_map: Mapping[str, SemanticColumnProfile],
        column_data: Mapping[str, Sequence[Any]],
        row_count: int,
    ) -> tuple[float, int]:
        """
        Computes support ratio and violation count for X -> Y.
        Support ratio = (distinct determinant values with exactly 1 dependent value) / (total distinct determinant values).
        """
        det_cols = [list(self._get_column_values(column_data, prof_map[cid])) for cid in det_col_ids if cid in prof_map]
        if len(det_cols) != len(det_col_ids) or dep_col_id not in prof_map:
            return 0.0, 0

        dep_col = list(self._get_column_values(column_data, prof_map[dep_col_id]))

        limit = min(row_count, self.policy.fd_sample_size)
        mapping: dict[tuple[Any, ...], set[Any]] = defaultdict(set)

        for i in range(limit):
            det_val = tuple(det_cols[c_idx][i] if i < len(det_cols[c_idx]) else None for c_idx in range(len(det_col_ids)))
            dep_val = dep_col[i] if i < len(dep_col) else None
            # Skip if any determinant value is null
            if any(v is None for v in det_val):
                continue
            mapping[det_val].add(dep_val)

        if not mapping:
            return 0.0, 0

        consistent_groups = sum(1 for det_v, dep_vals in mapping.items() if len(dep_vals) == 1)
        violation_groups = sum(1 for det_v, dep_vals in mapping.items() if len(dep_vals) > 1)
        support = consistent_groups / float(len(mapping))

        return support, violation_groups
