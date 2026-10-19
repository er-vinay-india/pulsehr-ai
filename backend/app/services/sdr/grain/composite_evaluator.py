"""
HighView Semantic Data Refinery — Phase SDR-2
Bounded Composite Combination Evaluator
"""

from __future__ import annotations

from collections import Counter
import itertools
from typing import Any, Mapping, Sequence

from app.services.ingestion_v2.contracts.grain import TemporalGrain
from app.services.ingestion_v2.contracts.semantics import SemanticColumnRole
from app.services.sdr.contracts.grain import GrainCandidate
from app.services.sdr.contracts.policies import GrainConfidencePolicy
from app.services.sdr.contracts.profiles import (
    SemanticColumnProfile,
    SemanticDtype,
)


def map_temporal_frequency_from_profile(profile: SemanticColumnProfile) -> TemporalGrain:
    """Maps a temporal column profile to its temporal grain."""
    name_lower = profile.source_name.lower()
    if "month" in name_lower or "mon" in name_lower:
        return TemporalGrain.MONTH
    if "week" in name_lower or "wk" in name_lower:
        return TemporalGrain.WEEK
    if "quarter" in name_lower or "qtr" in name_lower or profile.features.sample_values and any("q" in s.lower() for s in profile.features.sample_values):
        return TemporalGrain.QUARTER
    if "year" in name_lower or "annual" in name_lower:
        return TemporalGrain.YEAR
    if profile.semantic_dtype == SemanticDtype.DATE:
        return TemporalGrain.DAY
    if profile.semantic_dtype == SemanticDtype.DATETIME:
        return TemporalGrain.DATETIME_EVENT
    return TemporalGrain.DAY


def synthesize_candidate_expression(profiles: Sequence[SemanticColumnProfile]) -> str:
    """Synthesizes human-readable grain expression, e.g. EMPLOYEE x MONTH."""
    parts: list[str] = []
    for p in profiles:
        if p.semantic_role == SemanticColumnRole.TIME:
            tg = map_temporal_frequency_from_profile(p)
            parts.append(tg.value)
        elif p.semantic_role == SemanticColumnRole.ENTITY_IDENTIFIER:
            parts.append(p.canonical_name.upper())
        elif p.entity_type_hypothesis.value != "UNKNOWN":
            parts.append(p.entity_type_hypothesis.value)
        else:
            parts.append(p.canonical_name.upper())

    return " x ".join(parts) if parts else "UNKNOWN"


class SDRCompositeEvaluator:
    """
    Evaluates candidate determinant combinations up to bounded width (max <= 3).
    Computes exact structural uniqueness, duplicate patterns, and null involvement.
    """

    def __init__(self, policy: GrainConfidencePolicy | None = None):
        self.policy = policy or GrainConfidencePolicy()

    def evaluate_combinations(
        self,
        eligible_profiles: Sequence[SemanticColumnProfile],
        column_data: Mapping[str, Sequence[Any]],
        row_count: int,
    ) -> list[GrainCandidate]:
        """
        Generates and scores grain candidates up to max_composite_width.
        """
        if row_count == 0 or not eligible_profiles:
            return []

        prof_map = {p.column_id: p for p in eligible_profiles}
        candidates: list[GrainCandidate] = []

        # Generate combinations for width 1 to max_composite_width
        all_combinations: list[tuple[str, ...]] = []

        # Width 1: All eligible single columns
        for p in eligible_profiles:
            all_combinations.append((p.column_id,))

        # Width 2: Pairs
        if self.policy.max_composite_width >= 2 and len(eligible_profiles) >= 2:
            for c1, c2 in itertools.combinations(eligible_profiles, 2):
                # Prune invalid pairings (e.g. 2 time columns)
                if c1.semantic_role == SemanticColumnRole.TIME and c2.semantic_role == SemanticColumnRole.TIME:
                    continue
                all_combinations.append((c1.column_id, c2.column_id))

        # Width 3: Triples
        if self.policy.max_composite_width >= 3 and len(eligible_profiles) >= 3:
            for c1, c2, c3 in itertools.combinations(eligible_profiles, 3):
                # Must have at least 1 temporal or 2 entity columns
                time_count = sum(1 for c in (c1, c2, c3) if c.semantic_role == SemanticColumnRole.TIME)
                if time_count > 1:
                    continue  # Prune multiple time dimensions
                all_combinations.append((c1.column_id, c2.column_id, c3.column_id))

        # Cap total combinations evaluated to prevent combinatorial cost
        evaluated_combos = all_combinations[: self.policy.max_composite_candidates_eval]

        for combo in evaluated_combos:
            combo_profiles = [prof_map[cid] for cid in combo]
            cand = self._evaluate_single_combination(combo, combo_profiles, column_data, row_count)
            if cand:
                candidates.append(cand)

        # Sort candidates deterministically:
        # Highest confidence first, then lowest width (parsimony), then highest uniqueness
        return sorted(
            candidates,
            key=lambda c: (-c.confidence, c.width, -c.uniqueness_ratio, c.candidate_id),
        )

    def _evaluate_single_combination(
        self,
        combo: tuple[str, ...],
        profiles: list[SemanticColumnProfile],
        column_data: Mapping[str, Sequence[Any]],
        row_count: int,
    ) -> GrainCandidate | None:
        """Evaluates tuple uniqueness and duplicates for a specific column combination."""
        # Check all column data available
        for cid in combo:
            if cid not in column_data or len(column_data[cid]) < row_count:
                return None

        # Build row tuples and detect null involvement
        row_tuples: list[tuple[Any, ...]] = []
        null_rows = 0

        for r in range(row_count):
            vals: list[Any] = []
            has_null = False
            for cid in combo:
                v = column_data[cid][r]
                if v is None or str(v).strip() in ("", "None", "null", "NaN", "N/A"):
                    has_null = True
                vals.append(v)
            if has_null:
                null_rows += 1
            row_tuples.append(tuple(vals))

        counts = Counter(row_tuples)
        unique_combinations = len(counts)
        uniqueness_ratio = round(unique_combinations / row_count, 4) if row_count > 0 else 0.0
        null_involvement_ratio = round(null_rows / row_count, 4) if row_count > 0 else 0.0

        # Duplicate statistics
        dup_combos = sum(1 for t, c in counts.items() if c > 1)
        dup_rows = sum(c for t, c in counts.items() if c > 1)

        # Synthesize grain expression
        expr = synthesize_candidate_expression(profiles)
        col_names = [p.source_name for p in profiles]
        width = len(combo)

        # Calculate Confidence Score
        confidence = self._score_combination_confidence(profiles, uniqueness_ratio, null_involvement_ratio, width)

        cid = f"cand_{'_'.join(combo)}"
        rationale = (
            f"Evaluated {expr} ({', '.join(col_names)}): {unique_combinations}/{row_count} unique ({uniqueness_ratio:.2%}), "
            f"{dup_combos} duplicate combination(s), {dup_rows} duplicate row(s)."
        )

        return GrainCandidate(
            candidate_id=cid,
            determinant_column_ids=list(combo),
            determinant_column_names=col_names,
            grain_expression=expr,
            width=width,
            row_count=row_count,
            unique_combination_count=unique_combinations,
            uniqueness_ratio=uniqueness_ratio,
            duplicate_combination_count=dup_combos,
            duplicate_row_count=dup_rows,
            null_involvement_ratio=null_involvement_ratio,
            confidence=round(confidence, 4),
            rationale=rationale,
        )

    def _score_combination_confidence(
        self,
        profiles: list[SemanticColumnProfile],
        uniqueness_ratio: float,
        null_involvement_ratio: float,
        width: int,
    ) -> float:
        """
        Deterministic confidence calculation:
        Combines uniqueness, semantic role alignment, null penalties, and parsimony.
        """
        score = uniqueness_ratio * 0.70

        # Semantic Role Backing Boost
        has_id = any(p.semantic_role == SemanticColumnRole.ENTITY_IDENTIFIER for p in profiles)
        has_time = any(p.semantic_role == SemanticColumnRole.TIME for p in profiles)
        id_or_dim_count = sum(
            1 for p in profiles
            if p.semantic_role in (
                SemanticColumnRole.ENTITY_IDENTIFIER,
                SemanticColumnRole.DIMENSION,
                SemanticColumnRole.CATEGORY,
            )
        )

        semantic_boost = 0.0
        if has_id and not has_time and width == 1:
            semantic_boost = 0.25  # Natural single entity grain
        elif id_or_dim_count >= 1 and has_time and width == 2:
            semantic_boost = 0.25  # Natural periodic snapshot grain (e.g. Employee x Month)
        elif id_or_dim_count >= 2 and has_time and width == 3:
            semantic_boost = 0.25  # Natural multi-entity periodic grain (e.g. Store x SKU x Day)
        elif id_or_dim_count >= 1 and not has_time and width == 1:
            semantic_boost = 0.10

        # Scale semantic boost by uniqueness ratio so non-unique candidates cannot outrank unique ones
        score += semantic_boost * uniqueness_ratio

        # Parsimony adjustment (prefer smaller width when uniqueness is equivalent)
        parsimony_penalty = (width - 1) * 0.04
        score -= parsimony_penalty

        # Null involvement penalty
        if null_involvement_ratio > 0.0:
            score -= null_involvement_ratio * 0.30

        return max(0.10, min(0.98, score))
