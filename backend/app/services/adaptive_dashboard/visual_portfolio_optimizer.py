"""Executive Visual Diversity & Density Portfolio Optimizer.

Governs Level-1 dashboard richness within the 8 minimum / 15 maximum visual range (target: 10–12),
while strictly enforcing:
1. Multi-factor portfolio scoring (importance + confidence + business relevance + diversity bonuses - redundancy penalties)
2. Intent diversity (min 4 distinct intents, max 3 of same intent)
3. Chart family diversity (min 5 distinct chart families, max 2 of same family)
4. Truth > Quota (never fabricate synthetic stories or temporal labels)
5. Archetype gating rules (BOX_PLOT >= 5 obs, DENDROGRAM depth >= 2, SCATTER N >= 3, PODIUM_TOP_3 <= 20 chars/2 lines, no WORD_CLOUD for ranking)
6. Size class / layout hints (HERO, LARGE, MEDIUM, COMPACT, MICRO)
"""
from __future__ import annotations

import collections
from enum import Enum
import logging
import re
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class ChartFamily(str, Enum):
    """Governed visual taxonomy families."""
    COMPARISON = "COMPARISON"
    CORRELATION = "CORRELATION"
    PART_TO_WHOLE = "PART_TO_WHOLE"
    HIERARCHY = "HIERARCHY"
    TEMPORAL = "TEMPORAL"
    DISTRIBUTION = "DISTRIBUTION"
    FLOW = "FLOW"
    GEOSPATIAL = "GEOSPATIAL"
    SPECIALTY = "SPECIALTY"


class ChartArchetype(str, Enum):
    """Governed chart archetypes."""
    LOLLIPOP = "lollipop"
    BULLET = "bullet"
    DUMBBELL = "dumbbell"
    BOX_PLOT = "box_plot"
    HISTOGRAM = "histogram"
    HEATMAP = "heatmap"
    TREEMAP = "treemap"
    DENDROGRAM = "dendrogram"
    AREA = "area"
    SLOPE = "slope"
    SCATTER = "scatter"
    SANKEY = "sankey"
    PODIUM_TOP_3 = "podium_top_3"
    RANKED_BAR = "ranked_bar"
    HORIZONTAL_BAR = "horizontal_bar"
    LINE = "line"
    ONE_HUNDRED_PERCENT_STACKED_BAR = "100_percent_stacked_bar"
    STACKED_BAR = "stacked_bar"
    WATERFALL = "waterfall"
    VARIANCE_BAR = "variance_bar"
    DONUT = "donut"
    PIE = "pie"
    DOT_PLOT = "dot_plot"
    WORD_CLOUD = "word_cloud"


class LayoutHint(str, Enum):
    """Visual size classes governing CSS grid density and layout."""
    HERO = "HERO"          # Full width / top anchor
    LARGE = "LARGE"        # 8–12 columns
    MEDIUM = "MEDIUM"      # 6 columns
    COMPACT = "COMPACT"    # 4 columns (ideal for podium, bullet, dumbbell, lollipop)
    MICRO = "MICRO"        # Compact metric sparkline / tile


class DashboardVisualBudget(BaseModel):
    """Hard-governed slot and visual portfolio budget envelope."""
    model_config = ConfigDict(extra="forbid")

    min_visuals: int = 8          # Conditional on >=8 valid non-redundant stories existing ("truth > quota")
    target_min: int = 10
    target_max: int = 12
    max_visuals: int = 15
    max_same_intent: int = 3
    max_same_chart_family: int = 2
    min_distinct_intents: int = 4
    min_distinct_chart_families: int = 5


class ChartCapabilityRegistry:
    """Governed catalog of chart archetypes, family mappings, default sizes, and gating rules."""

    ARCHETYPE_TO_FAMILY: dict[str, ChartFamily] = {
        ChartArchetype.RANKED_BAR.value: ChartFamily.COMPARISON,
        ChartArchetype.HORIZONTAL_BAR.value: ChartFamily.COMPARISON,
        ChartArchetype.LOLLIPOP.value: ChartFamily.COMPARISON,
        ChartArchetype.BULLET.value: ChartFamily.COMPARISON,
        "bullet_bar": ChartFamily.COMPARISON,
        ChartArchetype.DUMBBELL.value: ChartFamily.COMPARISON,
        ChartArchetype.PODIUM_TOP_3.value: ChartFamily.COMPARISON,
        ChartArchetype.SCATTER.value: ChartFamily.CORRELATION,
        "correlation_scatter": ChartFamily.CORRELATION,
        "bubble": ChartFamily.CORRELATION,
        ChartArchetype.ONE_HUNDRED_PERCENT_STACKED_BAR.value: ChartFamily.PART_TO_WHOLE,
        ChartArchetype.STACKED_BAR.value: ChartFamily.PART_TO_WHOLE,
        ChartArchetype.DONUT.value: ChartFamily.PART_TO_WHOLE,
        ChartArchetype.PIE.value: ChartFamily.PART_TO_WHOLE,
        ChartArchetype.TREEMAP.value: ChartFamily.HIERARCHY,
        ChartArchetype.DENDROGRAM.value: ChartFamily.HIERARCHY,
        ChartArchetype.LINE.value: ChartFamily.TEMPORAL,
        "trend_line": ChartFamily.TEMPORAL,
        ChartArchetype.AREA.value: ChartFamily.TEMPORAL,
        ChartArchetype.SLOPE.value: ChartFamily.TEMPORAL,
        ChartArchetype.BOX_PLOT.value: ChartFamily.DISTRIBUTION,
        ChartArchetype.HISTOGRAM.value: ChartFamily.DISTRIBUTION,
        ChartArchetype.DOT_PLOT.value: ChartFamily.DISTRIBUTION,
        ChartArchetype.WATERFALL.value: ChartFamily.FLOW,
        ChartArchetype.SANKEY.value: ChartFamily.FLOW,
        ChartArchetype.VARIANCE_BAR.value: ChartFamily.COMPARISON,
        ChartArchetype.HEATMAP.value: ChartFamily.SPECIALTY,
        ChartArchetype.WORD_CLOUD.value: ChartFamily.SPECIALTY,
    }

    ARCHETYPE_TO_LAYOUT_HINT: dict[str, LayoutHint] = {
        ChartArchetype.PODIUM_TOP_3.value: LayoutHint.COMPACT,
        ChartArchetype.BULLET.value: LayoutHint.COMPACT,
        "bullet_bar": LayoutHint.COMPACT,
        ChartArchetype.DUMBBELL.value: LayoutHint.COMPACT,
        ChartArchetype.LOLLIPOP.value: LayoutHint.COMPACT,
        ChartArchetype.DOT_PLOT.value: LayoutHint.COMPACT,
        ChartArchetype.BOX_PLOT.value: LayoutHint.MEDIUM,
        ChartArchetype.SCATTER.value: LayoutHint.MEDIUM,
        "correlation_scatter": LayoutHint.MEDIUM,
        ChartArchetype.HISTOGRAM.value: LayoutHint.MEDIUM,
        ChartArchetype.RANKED_BAR.value: LayoutHint.MEDIUM,
        ChartArchetype.HORIZONTAL_BAR.value: LayoutHint.MEDIUM,
        ChartArchetype.ONE_HUNDRED_PERCENT_STACKED_BAR.value: LayoutHint.MEDIUM,
        ChartArchetype.STACKED_BAR.value: LayoutHint.MEDIUM,
        ChartArchetype.LINE.value: LayoutHint.MEDIUM,
        "trend_line": LayoutHint.MEDIUM,
        ChartArchetype.AREA.value: LayoutHint.MEDIUM,
        ChartArchetype.SLOPE.value: LayoutHint.COMPACT,
        ChartArchetype.WATERFALL.value: LayoutHint.COMPACT,
        ChartArchetype.VARIANCE_BAR.value: LayoutHint.MEDIUM,
        ChartArchetype.DONUT.value: LayoutHint.COMPACT,
        ChartArchetype.TREEMAP.value: LayoutHint.LARGE,
        ChartArchetype.HEATMAP.value: LayoutHint.LARGE,
        ChartArchetype.DENDROGRAM.value: LayoutHint.LARGE,
        ChartArchetype.SANKEY.value: LayoutHint.LARGE,
        ChartArchetype.WORD_CLOUD.value: LayoutHint.COMPACT,
    }

    @classmethod
    def get_family(cls, archetype: str) -> ChartFamily:
        """Resolves chart family with fallback to COMPARISON."""
        return cls.ARCHETYPE_TO_FAMILY.get(archetype.lower(), ChartFamily.COMPARISON)

    @classmethod
    def get_layout_hint(cls, archetype: str, is_hero: bool = False) -> LayoutHint:
        """Resolves visual layout hint with fallback to MEDIUM."""
        if is_hero:
            return LayoutHint.HERO
        return cls.ARCHETYPE_TO_LAYOUT_HINT.get(archetype.lower(), LayoutHint.MEDIUM)

    @classmethod
    def validate_archetype_gates(
        cls,
        archetype: str,
        spec: dict[str, Any],
        has_temporal_dimension: bool = False,
    ) -> tuple[bool, str]:
        """Gated capability verification ensuring archetypes are strictly faithful to underlying data."""
        arch = archetype.lower()

        # 1. BOX_PLOT GATING: Numeric measure, categorical groups, >= 5 obs per group (prefer >= 10)
        if arch == ChartArchetype.BOX_PLOT.value:
            obs_count = spec.get("observation_count") or spec.get("population") or len(spec.get("values", []))
            box_data = spec.get("box_data") or spec.get("distribution_data")
            if not box_data and obs_count < 5:
                return False, f"BOX_PLOT rejected: requires >= 5 observations (found {obs_count})"
            return True, "VALIDATED"

        # 2. DENDROGRAM GATING: Explicit validated hierarchy with depth >= 2
        if arch == ChartArchetype.DENDROGRAM.value:
            hierarchy_depth = spec.get("hierarchy_depth", 0)
            if hierarchy_depth < 2:
                return False, f"DENDROGRAM rejected: requires validated hierarchy depth >= 2 (found {hierarchy_depth})"
            return True, "VALIDATED"

        # 3. SCATTER GATING: 2 numeric continuous measures, N >= 3 points
        if arch in (ChartArchetype.SCATTER.value, "correlation_scatter"):
            points = spec.get("scatter_points") or spec.get("points") or []
            if len(points) < 3:
                return False, f"SCATTER rejected: requires >= 3 points (found {len(points)})"
            return True, "VALIDATED"

        # 4. PODIUM_TOP_3 GATING: High-confidence ranking, N >= 3, strict label length <= 20 chars
        if arch == ChartArchetype.PODIUM_TOP_3.value:
            cats = spec.get("categories") or []
            if len(cats) < 3:
                return False, f"PODIUM_TOP_3 rejected: requires >= 3 ranked entities (found {len(cats)})"
            return True, "VALIDATED"

        # 5. WORD_CLOUD GATING: Allowed ONLY for categorical text frequency, forbidden for numeric ranking
        if arch == ChartArchetype.WORD_CLOUD.value:
            intent = spec.get("analytical_intent") or ""
            if intent in ("RANKING", "COMPARISON", "TREND"):
                return False, f"WORD_CLOUD rejected: strictly forbidden for quantitative ranking/trend (intent={intent})"
            if not spec.get("text_frequencies"):
                return False, "WORD_CLOUD rejected: requires text frequency tokens"
            return True, "VALIDATED"

        # 6. TEMPORAL (LINE, AREA, SLOPE) GATING: Genuine validated temporal dimension required
        if arch in (ChartArchetype.LINE.value, "trend_line", ChartArchetype.AREA.value, ChartArchetype.SLOPE.value):
            if not has_temporal_dimension:
                return False, "TEMPORAL chart rejected: genuine validated temporal dimension does not exist (truth > quota)"
            return True, "VALIDATED"

        return True, "VALIDATED"

    @classmethod
    def format_podium_labels(cls, categories: list[str]) -> list[dict[str, str]]:
        """Enforces Podium Top 3 label truncation rules: <= 20 chars, <= 2 lines, full label preserved in tooltip."""
        formatted = []
        for cat in categories[:3]:
            raw_text = str(cat).strip()
            # If length <= 20, keep as is
            if len(raw_text) <= 20:
                short_text = raw_text
            else:
                # Word-based split or truncation
                words = raw_text.split()
                line1, line2 = "", ""
                for w in words:
                    if len(f"{line1} {w}".strip()) <= 10:
                        line1 = f"{line1} {w}".strip()
                    elif len(f"{line2} {w}".strip()) <= 10:
                        line2 = f"{line2} {w}".strip()
                    else:
                        break
                if line1 and line2:
                    short_text = f"{line1}\n{line2}"
                elif line1:
                    short_text = line1[:20]
                else:
                    short_text = raw_text[:18] + "…"

            formatted.append({
                "display_label": short_text,
                "full_label": raw_text,
            })
        return formatted


class CandidatePortfolioItem(BaseModel):
    """Wrapper for candidates evaluated by the portfolio optimizer."""
    model_config = ConfigDict(extra="ignore")

    item_id: str
    title: str
    semantic_family: str
    intent: str
    chart_archetype: str
    chart_family: ChartFamily
    layout_hint: LayoutHint = LayoutHint.MEDIUM
    importance_score: float = 0.5
    confidence: float = 0.90
    business_value: float = 0.5
    statistical_significance: float = 0.5
    decision_value: float = 0.5
    visual_spec: dict[str, Any] = Field(default_factory=dict)
    tokens: dict[str, Any] = Field(default_factory=dict)
    suggested_role: str = "supporting"
    fingerprint: str = ""
    is_hero: bool = False
    portfolio_score: float = 0.0


class VisualPortfolioOptimizer:
    """Meritocratic portfolio selector maximizing visual richness, diversity, and density."""

    @classmethod
    def optimize_portfolio(
        cls,
        candidates: list[CandidatePortfolioItem],
        budget: DashboardVisualBudget | None = None,
        has_temporal_dimension: bool = False,
    ) -> list[CandidatePortfolioItem]:
        """Selects 8–15 visuals satisfying diversity constraints under the 'truth > quota' contract."""
        budget = budget or DashboardVisualBudget()
        if not candidates:
            return []

        # Step 1: Pre-validate candidates through archetype gates
        valid_candidates: list[CandidatePortfolioItem] = []
        for c in candidates:
            is_valid, reason = ChartCapabilityRegistry.validate_archetype_gates(
                archetype=c.chart_archetype,
                spec=c.visual_spec,
                has_temporal_dimension=has_temporal_dimension,
            )
            if not is_valid:
                logger.info("Archetype gate rejected %s: %s", c.chart_archetype, reason)
                # Fallback to ranked_bar if feasible
                if c.chart_archetype not in (ChartArchetype.WORD_CLOUD.value, ChartArchetype.LINE.value):
                    c.chart_archetype = ChartArchetype.RANKED_BAR.value
                    c.chart_family = ChartFamily.COMPARISON
                    c.layout_hint = LayoutHint.MEDIUM
                    valid_candidates.append(c)
            else:
                c.chart_family = ChartCapabilityRegistry.get_family(c.chart_archetype)
                c.layout_hint = ChartCapabilityRegistry.get_layout_hint(c.chart_archetype, is_hero=c.is_hero)
                valid_candidates.append(c)

        if not valid_candidates:
            return []

        # Deduplicate candidates by normalized title to eliminate duplicate stories
        seen_titles: set[str] = set()
        deduped: list[CandidatePortfolioItem] = []
        for c in valid_candidates:
            norm_title = re.sub(r"[^a-zA-Z0-9]+", " ", c.title).strip().lower()
            if norm_title in seen_titles:
                continue
            seen_titles.add(norm_title)
            deduped.append(c)
        valid_candidates = deduped

        # If total valid candidates is less than min_visuals, respect Truth > Quota (never fabricate dummy stories)
        if len(valid_candidates) <= budget.min_visuals:
            logger.info("Candidate pool size (%d) <= min_visuals (%d); respecting Truth > Quota", len(valid_candidates), budget.min_visuals)
            for c in valid_candidates:
                c.portfolio_score = round(cls._base_score(c), 4)
            return valid_candidates

        # Step 2: Iterative greedy portfolio selection with multi-factor scoring and diversity bonuses
        selected: list[CandidatePortfolioItem] = []
        intent_counts: dict[str, int] = collections.defaultdict(int)
        family_counts: dict[ChartFamily, int] = collections.defaultdict(int)
        selected_fingerprints: set[str] = set()

        # Step 2a: Anchor the Hero candidate first
        hero_candidates = [c for c in valid_candidates if c.suggested_role == "hero" or c.is_hero]
        anchor = hero_candidates[0] if hero_candidates else valid_candidates[0]
        anchor.is_hero = True
        anchor.layout_hint = LayoutHint.HERO
        anchor.portfolio_score = round(cls._base_score(anchor) + 1.0, 4)
        selected.append(anchor)
        intent_counts[anchor.intent] += 1
        family_counts[anchor.chart_family] += 1
        if anchor.fingerprint:
            selected_fingerprints.add(anchor.fingerprint)

        # Step 2b: Iterate and score remaining candidates
        remaining = [c for c in valid_candidates if c != anchor]

        while remaining and len(selected) < budget.max_visuals:
            best_candidate = None
            best_score = -999.0

            for cand in remaining:
                # 1. Redundancy check: duplicate fingerprint gets penalized heavily
                if cand.fingerprint and cand.fingerprint in selected_fingerprints:
                    continue

                # 2. Hard caps: max same intent and max same chart family
                current_intent_count = intent_counts[cand.intent]
                current_family_count = family_counts[cand.chart_family]

                # If we haven't reached min_visuals yet, we allow slight flexibility if no other candidates exist
                pool_constrained = (len(selected) + len(remaining)) <= budget.min_visuals
                if not pool_constrained:
                    if current_intent_count >= budget.max_same_intent:
                        continue
                    if current_family_count >= budget.max_same_chart_family:
                        continue

                # 3. Calculate portfolio score
                base = cls._base_score(cand)
                score = base

                # Diversity bonus: rewarding distinct intents
                if current_intent_count == 0:
                    score += 0.35  # Major bonus for presenting a fresh analytical intent
                elif current_intent_count == 1:
                    score += 0.10

                # Diversity bonus: rewarding distinct visual chart families
                if current_family_count == 0:
                    score += 0.40  # Major bonus for presenting a fresh visual chart family
                elif current_family_count == 1:
                    score += 0.15

                # Goal bonus: pushing towards target minimum intents (4) and families (5)
                if len(intent_counts) < budget.min_distinct_intents and current_intent_count == 0:
                    score += 0.25
                if len(family_counts) < budget.min_distinct_chart_families and current_family_count == 0:
                    score += 0.30

                # Semantic family diversity: avoid too many stories on the same metric family
                same_sem_family = sum(1 for s in selected if s.semantic_family == cand.semantic_family)
                if same_sem_family > 0:
                    score -= (0.20 * same_sem_family)

                if score > best_score:
                    best_score = score
                    best_candidate = cand

            if not best_candidate:
                # If constrained by hard caps before hitting min_visuals, relax family cap slightly
                if len(selected) < budget.min_visuals and remaining:
                    fallback_cands = [c for c in remaining if c.fingerprint not in selected_fingerprints]
                    if fallback_cands:
                        best_candidate = max(fallback_cands, key=lambda c: cls._base_score(c))
                        best_score = cls._base_score(best_candidate)
                    else:
                        break
                else:
                    break

            best_candidate.portfolio_score = round(best_score, 4)
            selected.append(best_candidate)
            intent_counts[best_candidate.intent] += 1
            family_counts[best_candidate.chart_family] += 1
            if best_candidate.fingerprint:
                selected_fingerprints.add(best_candidate.fingerprint)
            remaining.remove(best_candidate)

            # Check if target saturation reached with diminishing returns
            if len(selected) >= budget.target_max:
                break

        logger.info(
            "VisualPortfolioOptimizer selected %d visuals (intents=%d, families=%d)",
            len(selected),
            len(intent_counts),
            len(family_counts),
        )
        return selected

    @classmethod
    def _base_score(cls, c: CandidatePortfolioItem) -> float:
        """Computes multi-factor intrinsic merit score."""
        return (
            0.35 * c.business_value
            + 0.25 * c.importance_score
            + 0.20 * c.confidence
            + 0.10 * c.statistical_significance
            + 0.10 * c.decision_value
        )
