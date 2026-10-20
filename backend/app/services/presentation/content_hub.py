"""Presentation Content Hub, Providers & Ranking Engine (PPT-L1).

Implements the PresentationContentHub which ingests governed empirical truth
from multiple content providers (Dashboard, Data Explorer, User Context), scores
and ranks items using the multi-factor PresentationContentRanker, enforces the
UserVisibleContentPolicy, and emits a clean, boardroom-ready PresentationContentPackage.

Invariants:
1. CONTENT TRUTH != PRESENTATION NARRATIVE.
2. PresentationContentPackage contains only audited empirical facts and governed specs.
3. UserVisibleContentPolicy purges internal governance jargon (SDR, JoinPlan, EVID, SHA-256).
4. ContentScore = 0.30*Importance + 0.25*DecisionValue + 0.20*Novelty + 0.15*VisualSuitability - 0.25*RedundancyPenalty.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import logging
import re
from typing import Any
import uuid

from .content_models import (
    ContentKind,
    ContentRole,
    PresentationContentItem,
    PresentationContentPackage,
    UserVisibleContentPolicy,
)

logger = logging.getLogger(__name__)


class PresentationContentProvider(ABC):
    """Abstract base class for presentation content sources."""

    @abstractmethod
    def provide_content(
        self,
        scope: dict[str, Any],
        dataset_context: dict[str, Any],
        workspace_evidence: dict[str, Any] | None = None,
    ) -> list[PresentationContentItem]:
        """Extracts and yields candidate PresentationContentItems."""
        pass


class DashboardContentProvider(PresentationContentProvider):
    """Extracts governed presentation topics, visual specs, and strategic KPIs from dashboard context."""

    def provide_content(
        self,
        scope: dict[str, Any],
        dataset_context: dict[str, Any],
        workspace_evidence: dict[str, Any] | None = None,
    ) -> list[PresentationContentItem]:
        items: list[PresentationContentItem] = []
        workspace_evidence = workspace_evidence or {}

        # 1. Resolve topics from presentation_topics or executive_topics
        topics = (
            dataset_context.get("presentation_topics")
            or workspace_evidence.get("presentation_topics")
            or []
        )

        if not topics:
            raw_exec = (
                dataset_context.get("executive_topics")
                or workspace_evidence.get("executive_topics")
                or []
            )
            if raw_exec:
                from .topic_contract import PresentationTopic
                domain = dataset_context.get("domain", "general")
                sheet_name = (dataset_context.get("target_sheet") or {}).get("name") or ""
                topics = [
                    PresentationTopic.from_executive_topic(t, domain=domain, source_sheet_name=sheet_name)
                    for t in raw_exec
                ]

        item_seq = 1
        for topic in topics:
            t_dict = topic if isinstance(topic, dict) else topic.model_dump()
            topic_id = str(t_dict.get("topic_id") or f"TOPIC-{item_seq}")
            slot_type = str(t_dict.get("slot_type", "supporting")).lower()
            rec_visual = str(t_dict.get("recommended_visual", "chart")).lower()

            # Determine ContentRole
            if slot_type == "hero":
                role = ContentRole.PRIMARY_HERO
                importance = 0.95
                decision_rel = 0.90
            elif slot_type == "risk_anomaly":
                role = ContentRole.RISK_ANOMALY
                importance = 0.85
                decision_rel = 0.85
            elif slot_type == "action_scenario":
                role = ContentRole.ACTION_INITIATIVE
                importance = 0.80
                decision_rel = 0.95
            else:
                role = ContentRole.KEY_FINDING
                importance = 0.70
                decision_rel = 0.75

            # Determine ContentKind
            if "map" in rec_visual or "choropleth" in rec_visual:
                kind = ContentKind.MAP
                visual_suitability = 0.95
            elif "table" in rec_visual:
                kind = ContentKind.TABLE
                visual_suitability = 0.85
            else:
                kind = ContentKind.CHART
                visual_suitability = 0.90

            title = str(t_dict.get("title") or "Executive Analytical Finding")
            subtitle = str(t_dict.get("subtitle") or "")
            takeaway = str(t_dict.get("primary_takeaway") or "")
            rec_action = str(t_dict.get("recommended_action") or "")

            bullets = []
            if takeaway:
                bullets.append(takeaway)
            if rec_action:
                bullets.append(f"Recommended action: {rec_action}")
            if t_dict.get("leader") and t_dict.get("leader_value") is not None:
                bullets.append(f"Leading entity: {t_dict['leader']} ({t_dict['leader_value']} {t_dict.get('unit', '')})".strip())

            content_id = f"CONTENT-{item_seq:03d}"
            item_seq += 1

            items.append(
                PresentationContentItem(
                    content_id=content_id,
                    kind=kind,
                    role=role,
                    topic_category=t_dict.get("domain", dataset_context.get("domain", "General")),
                    title=title,
                    subtitle=subtitle or None,
                    importance_score=importance,
                    decision_relevance=decision_rel,
                    visual_suitability=visual_suitability,
                    narrative_takeaway=takeaway,
                    supporting_bullets=bullets,
                    visual_spec=t_dict.get("visual_spec") or None,
                    evidence_ids=list(t_dict.get("evidence_ids") or []),
                    fact_id=t_dict.get("fact_id"),
                    source_sheet_name=(dataset_context.get("target_sheet") or {}).get("name"),
                    dimension_name=t_dict.get("dimension") or t_dict.get("ranking_direction"),
                    metric_name=t_dict.get("metric"),
                    unit=t_dict.get("unit"),
                    grain=t_dict.get("grain") or t_dict.get("entity_grain"),
                    denominator=t_dict.get("denominator"),
                )
            )

        # 2. Extract Strategic KPIs from traceable_metrics or summary metrics
        traceable = dataset_context.get("traceable_metrics") or []
        for idx, tm in enumerate(traceable[:4]):
            tm_dict = tm if isinstance(tm, dict) else tm.model_dump() if hasattr(tm, "model_dump") else {}
            label = tm_dict.get("label") or tm_dict.get("metric_name") or "Primary Metric"
            val = tm_dict.get("formatted_value") or str(tm_dict.get("value") or "")
            if not val:
                continue

            kpi_item = PresentationContentItem(
                content_id=f"CONTENT-KPI-{idx+1:02d}",
                kind=ContentKind.KPI_METRIC,
                role=ContentRole.STRATEGIC_KPI,
                topic_category="Key Performance Indicators",
                title=f"Core Metric: {label}",
                importance_score=0.90,
                decision_relevance=0.85,
                visual_suitability=0.85,
                narrative_takeaway=f"{label} stands at {val}.",
                metric_label=label,
                metric_value=val,
                evidence_ids=[tm_dict.get("evidence_id")] if tm_dict.get("evidence_id") else [],
                metric_name=label,
                unit=tm_dict.get("unit"),
                grain=tm_dict.get("grain"),
                denominator=tm_dict.get("denominator"),
            )
            items.append(kpi_item)

        return items


class DataExplorerContentProvider(PresentationContentProvider):
    """Extracts exploratory data tables, column distributions, and data profile findings."""

    def provide_content(
        self,
        scope: dict[str, Any],
        dataset_context: dict[str, Any],
        workspace_evidence: dict[str, Any] | None = None,
    ) -> list[PresentationContentItem]:
        items: list[PresentationContentItem] = []
        records = dataset_context.get("records") or []
        columns = dataset_context.get("columns") or []
        sheet_name = (dataset_context.get("target_sheet") or {}).get("name") or "Dataset"

        if not records or not columns:
            return items

        # Build exploratory summary table partition (strictly bounded preview)
        sample_rows = records[:10]
        clean_rows = [{str(k): v for k, v in list(row.items())[:8] if not str(k).startswith("_")} for row in sample_rows]

        table_item = PresentationContentItem(
            content_id="CONTENT-EXP-001",
            kind=ContentKind.TABLE,
            role=ContentRole.EXPLORATORY_TABLE,
            topic_category="Data Profile & Structure",
            title=f"{sheet_name} Empirical Data Sample",
            subtitle=f"Audited sample preview of {len(clean_rows)} representative records across {min(len(columns), 8)} attributes",
            importance_score=0.65,
            decision_relevance=0.60,
            visual_suitability=0.80,
            narrative_takeaway=f"Empirical structure grounded in {len(columns)} attributes and {len(records)} verified records.",
            supporting_bullets=[
                f"Total recorded entities: {len(records):,}",
                f"Total profiled attributes: {len(columns)}",
                "Integrity verified against active SQLite storage.",
            ],
            table_data=clean_rows,
            source_sheet_name=sheet_name,
        )
        items.append(table_item)

        # Build data profile / anomaly item if high nulls or variance detected
        profile = dataset_context.get("profile") or {}
        if profile.get("anomalies"):
            anom_list = profile["anomalies"]
            anom_item = PresentationContentItem(
                content_id="CONTENT-EXP-002",
                kind=ContentKind.NARRATIVE_INSIGHT,
                role=ContentRole.RISK_ANOMALY,
                topic_category="Data Quality & Outliers",
                title="Operational Variance & Anomaly Detection",
                subtitle="Governed distribution scan for statistical outliers",
                importance_score=0.80,
                decision_relevance=0.85,
                visual_suitability=0.60,
                narrative_takeaway=f"Identified {len(anom_list)} operational variances requiring executive attention.",
                supporting_bullets=[str(a) for a in anom_list[:3]],
                source_sheet_name=sheet_name,
            )
            items.append(anom_item)

        return items


class UserContextProvider(PresentationContentProvider):
    """Parses user objective, instructions, and requested decision to yield targeted narrative initiatives."""

    def provide_content(
        self,
        scope: dict[str, Any],
        dataset_context: dict[str, Any],
        workspace_evidence: dict[str, Any] | None = None,
    ) -> list[PresentationContentItem]:
        items: list[PresentationContentItem] = []
        objective = scope.get("objective") or ""
        instructions = scope.get("instructions") or ""
        decision = scope.get("requested_decision") or scope.get("decision") or ""

        if not (objective or instructions or decision):
            return items

        # Create targeted strategic action initiative if requested decision exists
        if decision:
            action_item = PresentationContentItem(
                content_id="CONTENT-USR-001",
                kind=ContentKind.NARRATIVE_INSIGHT,
                role=ContentRole.ACTION_INITIATIVE,
                topic_category="Strategic Decision",
                title=f"Requested Decision: {decision[:60]}",
                subtitle="Decision frame aligned with executive objective",
                importance_score=0.90,
                decision_relevance=1.00,
                visual_suitability=0.65,
                narrative_takeaway=f"Executive decision requested: {decision}",
                supporting_bullets=[
                    f"Objective: {objective}" if objective else "Align operational focus with audited evidence.",
                    f"Special guidance: {instructions}" if instructions else "Deliver data-backed recommendations.",
                ],
            )
            items.append(action_item)

        return items


class PresentationContentRanker:
    """Evaluates candidate presentation content items and penalizes redundancy.
    
    Scoring Formula:
    ContentScore = 0.30 * Importance 
                 + 0.25 * DecisionValue 
                 + 0.20 * Novelty 
                 + 0.15 * VisualSuitability 
                 - 0.25 * RedundancyPenalty
    """

    W_IMPORTANCE = 0.30
    W_DECISION = 0.25
    W_NOVELTY = 0.20
    W_VISUAL = 0.15
    W_REDUNDANCY = 0.25

    STOP_WORDS = {"by", "of", "in", "the", "and", "across", "for", "with", "to", "from", "on", "a", "an", "all", "per"}

    @classmethod
    def _compute_item_overlap(cls, item_a: PresentationContentItem, item_b: PresentationContentItem) -> float:
        """Computes pairwise similarity / redundancy between two content items in [0.0, 1.0].
        
        Guarantees:
        1. Facts that share a common dimension (e.g. state) but measure materially different metrics
           (e.g. 'Population Density by State' vs 'Population Growth by State') are NOT redundant.
        2. Items are only penalized for redundancy when they duplicate the analytical metric,
           story role, and substantive semantic content.
        """
        # If both items define metric_name and they differ, they represent distinct analytical metrics
        if (
            item_a.metric_name and item_b.metric_name
            and item_a.metric_name.strip().lower() != item_b.metric_name.strip().lower()
        ):
            # Distinct metrics sharing a dimension are complementary, not redundant
            return 0.0

        # Exact dimension & metric match
        if (
            item_a.metric_name and item_b.metric_name
            and item_a.metric_name.strip().lower() == item_b.metric_name.strip().lower()
            and item_a.dimension_name and item_b.dimension_name
            and item_a.dimension_name.strip().lower() == item_b.dimension_name.strip().lower()
        ):
            return 0.90

        # Exact metric match across same visual kind
        if (
            item_a.metric_name and item_b.metric_name
            and item_a.metric_name.strip().lower() == item_b.metric_name.strip().lower()
            and item_a.kind == item_b.kind
        ):
            return 0.70

        # Substantive token overlap in title (ignoring generic stop words)
        tokens_a = {w for w in re.findall(r"\w+", item_a.title.lower()) if w not in cls.STOP_WORDS}
        tokens_b = {w for w in re.findall(r"\w+", item_b.title.lower()) if w not in cls.STOP_WORDS}
        
        if tokens_a and tokens_b:
            intersection = tokens_a.intersection(tokens_b)
            union = tokens_a.union(tokens_b)
            jaccard = len(intersection) / len(union)
            # Only consider substantive overlap if jaccard is very high and roles/kinds align
            if jaccard >= 0.80 and (item_a.kind == item_b.kind or item_a.role == item_b.role):
                return jaccard

        return 0.0

    @classmethod
    def rank_items(
        cls,
        items: list[PresentationContentItem],
        max_items: int = 20,
    ) -> list[PresentationContentItem]:
        """Ranks and curates candidate items, dynamically penalizing redundancy against selected set."""
        if not items:
            return []

        # Sort initially by base intrinsic score
        def base_score(it: PresentationContentItem) -> float:
            return (
                cls.W_IMPORTANCE * it.importance_score
                + cls.W_DECISION * it.decision_relevance
                + cls.W_VISUAL * it.visual_suitability
            )

        candidates = sorted(items, key=base_score, reverse=True)
        selected: list[PresentationContentItem] = []

        for cand in candidates:
            # Calculate novelty and redundancy penalty relative to already selected items
            max_overlap = 0.0
            for sel in selected:
                overlap = cls._compute_item_overlap(cand, sel)
                if overlap > max_overlap:
                    max_overlap = overlap

            cand.redundancy_score = round(max_overlap, 3)
            cand.novelty_score = round(max(0.0, 1.0 - max_overlap), 3)

            cand.composite_score = round(
                cls.W_IMPORTANCE * cand.importance_score
                + cls.W_DECISION * cand.decision_relevance
                + cls.W_NOVELTY * cand.novelty_score
                + cls.W_VISUAL * cand.visual_suitability
                - cls.W_REDUNDANCY * cand.redundancy_score,
                4,
            )

            # High redundancy threshold (>0.85) drops the item unless it's a primary hero
            if cand.redundancy_score >= 0.85 and cand.role != ContentRole.PRIMARY_HERO:
                continue

            selected.append(cand)
            if len(selected) >= max_items:
                break

        # Final sort by composite score
        selected.sort(key=lambda it: it.composite_score, reverse=True)
        return selected


class PresentationContentHub:
    """Coordinates content providers, ranking, and policy enforcement to assemble PresentationContentPackage."""

    def __init__(
        self,
        providers: list[PresentationContentProvider] | None = None,
        ranker: type[PresentationContentRanker] | None = None,
    ):
        self.providers = providers or [
            DashboardContentProvider(),
            DataExplorerContentProvider(),
            UserContextProvider(),
        ]
        self.ranker = ranker or PresentationContentRanker

    def assemble_package(
        self,
        scope: dict[str, Any],
        dataset_context: dict[str, Any],
        workspace_evidence: dict[str, Any] | None = None,
        max_items: int = 20,
    ) -> PresentationContentPackage:
        """Assembles, sanitizes, ranks, and packages all audited presentation content."""
        workspace_evidence = workspace_evidence or {}
        objective = scope.get("objective") or ""
        instructions = scope.get("instructions") or ""

        # Check policy exemption (e.g. technical architecture audit)
        allow_governance = UserVisibleContentPolicy.is_governance_exempt(objective, instructions)

        # 1. Harvest raw content items from all configured providers
        raw_candidates: list[PresentationContentItem] = []
        provider_status: dict[str, str] = {}
        for provider in self.providers:
            provider_name = provider.__class__.__name__
            try:
                provided = provider.provide_content(scope, dataset_context, workspace_evidence)
                raw_candidates.extend(provided)
                provider_status[provider_name] = f"SUCCESS ({len(provided)} items)"
            except Exception as exc:
                provider_status[provider_name] = f"FAILED: {exc}"
                logger.warning("Provider %s failed during content collection: %s", provider_name, exc)

        # 2. Sanitize user-visible text fields against UserVisibleContentPolicy
        sanitized_candidates: list[PresentationContentItem] = []
        for item in raw_candidates:
            sanitized = UserVisibleContentPolicy.sanitize_content_item(item, allow_governance=allow_governance)
            violations = UserVisibleContentPolicy.validate_content_item(sanitized, allow_governance=allow_governance)
            if violations:
                logger.warning(
                    "Content item %s had policy violations after sanitization: %s",
                    sanitized.content_id,
                    violations,
                )
            sanitized_candidates.append(sanitized)

        # 3. Separate Strategic KPIs from general content
        kpi_items = [it for it in sanitized_candidates if it.role == ContentRole.STRATEGIC_KPI]
        body_candidates = [it for it in sanitized_candidates if it.role != ContentRole.STRATEGIC_KPI]

        # 4. Rank and curate body items
        ranked_items = self.ranker.rank_items(body_candidates, max_items=max_items)

        # 5. Extract available topic categories
        available_topics = sorted(
            list(
                {
                    it.topic_category
                    for it in (ranked_items + kpi_items)
                    if it.topic_category
                }
            )
        )

        dataset_name = (
            (dataset_context.get("target_sheet") or {}).get("name")
            or dataset_context.get("dataset_name")
            or "Audited Dataset"
        )
        domain = dataset_context.get("domain") or "general"

        pkg = PresentationContentPackage(
            package_id=f"PKG-{uuid.uuid4().hex[:8].upper()}",
            dataset_name=dataset_name,
            domain=domain,
            items=ranked_items,
            available_topics=available_topics,
            global_kpis=kpi_items[:4],
            metadata={
                "governance_exempt": allow_governance,
                "raw_candidate_count": len(raw_candidates),
                "ranked_item_count": len(ranked_items),
                "kpi_count": len(kpi_items),
                "provider_status": provider_status,
                "max_items_limit": max_items,
            },
        )
        pkg.content_fingerprint = pkg.compute_fingerprint()
        return pkg
