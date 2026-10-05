"""Global Insight Candidate Pool, Multi-Factor Scoring, Redundancy Suppression & Capacity Budget.

Shifts prioritization from per-sheet quotas to a dataset-wide meritocratic candidate pool:
1. Global Candidate Scoring (0.25 Impact + 0.20 Stat + 0.15 Action + 0.15 Confidence + 0.10 Novelty + 0.10 CrossSheetValue + 0.05 Recency).
2. Meaningful Cross-Sheet Boost (relationship confidence, coverage %, information gain).
3. Redundancy Suppression (prevents 4 cards saying essentially the same thing).
4. Hard-governed Slot Budget (Hero: 1, Strategic: 3, Diagnostic: 2, Risk/Foresight: 2, Action: 1; max 9).
5. Domain Coverage Awareness (flags domain imbalance as an auditable sanity check).
"""
from __future__ import annotations

import collections
import logging
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from .evidence_graph import EvidenceGraph, EvidenceItem

logger = logging.getLogger(__name__)


class InsightCandidate(BaseModel):
    """Governed analytical insight competing in the global dataset pool."""
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    title: str
    scope: Literal["SINGLE_SHEET", "CROSS_SHEET"] = "SINGLE_SHEET"
    evidence_ids: list[str] = Field(default_factory=list)
    source_sheet_ids: list[int] = Field(default_factory=list)
    relationship_ids: list[str] = Field(default_factory=list)
    slot_type: Literal["hero", "strategic", "diagnostic", "risk_foresight", "action_scenario"] = "strategic"
    domain: str = "general"
    metric_name: str
    dimension_name: str
    population: int = 0
    effect_size: float = 0.5
    confidence: float = 1.0
    novelty: float = 0.5
    actionability: float = 0.7
    business_impact: float = 0.8
    cross_sheet_value: float = 0.0
    recency: float = 0.9
    composite_score: float = 0.0
    redundancy_group: str
    is_suppressed: bool = False
    suppression_reason: str | None = None


class DashboardSlotBudget(BaseModel):
    """Hard-governed slot allocation envelope for executive reporting."""
    model_config = ConfigDict(extra="forbid")

    max_hero: int = 1
    max_strategic: int = 3
    max_diagnostic: int = 2
    max_risk_foresight: int = 2
    max_action_scenario: int = 1
    total_max: int = 9


class GlobalInsightScorer:
    """Computes global meritocratic scores across all candidate findings."""

    @classmethod
    def score_candidate(cls, c: InsightCandidate) -> float:
        """Calculates dataset-wide multi-factor score."""
        score = (
            0.25 * c.business_impact
            + 0.20 * c.effect_size
            + 0.15 * c.actionability
            + 0.15 * c.confidence
            + 0.10 * c.novelty
            + 0.10 * c.cross_sheet_value
            + 0.05 * c.recency
        )
        return round(score, 4)


class InsightRedundancyResolver:
    """Eliminates repetitive insights across related metrics and segments."""

    @classmethod
    def resolve_redundancies(cls, candidates: list[InsightCandidate]) -> list[InsightCandidate]:
        """Suppresses lower-scoring candidates within the same redundancy group."""
        # Group by redundancy_group
        groups: dict[str, list[InsightCandidate]] = collections.defaultdict(list)
        for c in candidates:
            groups[c.redundancy_group].append(c)

        resolved: list[InsightCandidate] = []
        for group_key, items in groups.items():
            # Sort descending by composite score
            items.sort(key=lambda x: x.composite_score, reverse=True)
            # Winner takes the slot
            primary = items[0]
            resolved.append(primary)

            # Suppress remaining variants
            for duplicate in items[1:]:
                duplicate.is_suppressed = True
                duplicate.suppression_reason = (
                    f"Redundancy suppression: Outranked by primary finding '{primary.title}' "
                    f"in analytical group '{group_key}'."
                )
                resolved.append(duplicate)

        return resolved


class GlobalCandidatePoolEngine:
    """Orchestrates candidate scoring, deduplication, and slot-budget allocation."""

    @classmethod
    def build_candidates_from_evidence(
        cls,
        graph: EvidenceGraph,
        sheet_domain_map: dict[int, str] | None = None,
    ) -> list[InsightCandidate]:
        """Converts evidence graph nodes into scored InsightCandidates."""
        sheet_domain_map = sheet_domain_map or {}
        candidates: list[InsightCandidate] = []

        for idx, node in enumerate(graph.nodes, start=1):
            cand_id = f"INS-{idx:03d}"
            is_cross = len(node.tokens.get("source_sheet_ids", [])) > 1 or "cross" in node.metric.lower()
            scope: Literal["SINGLE_SHEET", "CROSS_SHEET"] = "CROSS_SHEET" if is_cross else "SINGLE_SHEET"

            # Determine slot type based on claim type
            slot_type: Literal["hero", "strategic", "diagnostic", "risk_foresight", "action_scenario"] = "strategic"
            if node.claim_type in ("capacity_gap", "backlog_aging"):
                slot_type = "risk_foresight"
            elif node.claim_type == "segment_difference":
                slot_type = "strategic"
            elif node.claim_type == "trend_change":
                slot_type = "diagnostic"
            elif node.causal_classification == "HYPOTHESIS":
                slot_type = "action_scenario"

            # Cross-sheet value booster
            cross_val = 0.85 if is_cross else 0.0
            impact = 0.90 if node.claim_type in ("capacity_gap", "target_gap") else 0.75
            effect = min(1.0, max(0.4, (node.difference_pct or 20.0) / 50.0))
            conf = 1.0 if node.confidence == "HIGH" else (0.75 if node.confidence == "MEDIUM" else 0.4)

            # Derive redundancy group
            metric_base = node.metric.replace("recipe_", "").split("_")[0]
            redundancy_group = f"{metric_base}_{node.subject.lower()}"

            cand = InsightCandidate(
                candidate_id=cand_id,
                title=f"{node.subject}: {node.formatted_value}",
                scope=scope,
                evidence_ids=[node.evidence_id],
                source_sheet_ids=node.tokens.get("source_sheet_ids", [graph.sheet_id]),
                slot_type=slot_type,
                domain=sheet_domain_map.get(graph.sheet_id, "general"),
                metric_name=node.metric,
                dimension_name=node.subject,
                population=node.population,
                effect_size=round(effect, 2),
                confidence=conf,
                novelty=0.7 if is_cross else 0.5,
                actionability=0.8 if node.claim_type == "capacity_gap" else 0.6,
                business_impact=impact,
                cross_sheet_value=cross_val,
                recency=0.9,
                redundancy_group=redundancy_group,
            )
            cand.composite_score = GlobalInsightScorer.score_candidate(cand)
            candidates.append(cand)

        return candidates

    @classmethod
    def select_dashboard_insights(
        cls,
        candidates: list[InsightCandidate],
        budget: DashboardSlotBudget | None = None,
    ) -> tuple[list[InsightCandidate], list[str]]:
        """Selects up to total_max insights adhering strictly to slot limits and domain awareness."""
        budget = budget or DashboardSlotBudget()

        # Step 1: Suppress redundancies
        deduped = InsightRedundancyResolver.resolve_redundancies(candidates)
        active_candidates = [c for c in deduped if not c.is_suppressed]

        # Step 2: Sort by score descending
        active_candidates.sort(key=lambda x: x.composite_score, reverse=True)

        # Step 3: Slot capacity allocation
        selected: list[InsightCandidate] = []
        counts = {
            "hero": 0,
            "strategic": 0,
            "diagnostic": 0,
            "risk_foresight": 0,
            "action_scenario": 0,
        }

        # Promote top candidate to hero slot
        if active_candidates:
            hero_cand = active_candidates[0]
            hero_cand.slot_type = "hero"
            selected.append(hero_cand)
            counts["hero"] += 1

        for c in active_candidates[1:]:
            if len(selected) >= budget.total_max:
                break

            st = c.slot_type
            max_limit = getattr(budget, f"max_{st}", 2)
            if counts.get(st, 0) < max_limit:
                selected.append(c)
                counts[st] = counts.get(st, 0) + 1

        # Step 4: Coverage sanity check
        warnings: list[str] = []
        if selected:
            domains = [c.domain for c in selected if c.domain != "general"]
            if domains and len(set(domains)) == 1 and len(selected) >= 4:
                warnings.append(
                    f"CoverageWarning: All {len(selected)} selected insights originate from the single analytical domain '{domains[0]}'."
                )

        return selected, warnings
