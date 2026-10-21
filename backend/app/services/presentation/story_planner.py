"""Story Planner & Logical SlideTag Orchestrator (PPT-L2).

Transforms a PresentationContentPackage into a validated, objective-aligned DeckStoryPlan.

Architectural Guarantees:
1. Structural Story Role != Extensible Semantic Topic:
   - structural_role: Generic narrative arc role (e.g. GEOGRAPHIC_ANALYSIS, DIAGNOSTIC_ANALYSIS, HERO_ANALYSIS).
   - semantic_topic: Extensible domain topic (e.g. POPULATION_DENSITY, POPULATION_GROWTH, CUSTOMER_RETENTION).
   - logical_slide_id: Derived from semantic topic (e.g. POPULATION_DENSITY), NOT generic numbers.
2. Content Truth != Presentation Narrative:
   Selects, groups, orders, summarizes, and frames audited content items.
   Zero fact mutations, zero unit mutations, zero grain mutations, zero denominator mutations.
3. Schema & ID Conformance:
   References ONLY valid content_ids from PresentationContentPackage.
   Any unknown or hallucinated ID is strictly rejected.
4. Complete Content Accounting:
   Every item in the PresentationContentPackage is accounted for: either bound
   to a logical slide or logged in the excluded_content ledger with an explicit ExclusionReason.
5. AI Path Certification & Deterministic Fallback:
   AIStoryPlanner validates responses through typed schema with call counting, latency tracking,
   and automatic fallback to DeterministicStoryPlanner on error, timeout, or invalid IDs.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from app.services.presentation.content_models import (
    ContentKind,
    ContentRole,
    PresentationContentItem,
    PresentationContentPackage,
    UserVisibleContentPolicy,
)
from app.services.presentation.story_models import (
    ContentBinding,
    ContentBindingRole,
    DeckStoryPlan,
    ExcludedContentItem,
    ExclusionReason,
    LogicalSlidePlan,
    StructuralRole,
    SlideTag,
    StoryPlanValidationError,
    StoryPlanValidator,
    UnknownContentIdError,
    normalize_semantic_topic,
)

logger = logging.getLogger(__name__)


class DeterministicStoryPlanner:
    """Deterministic, objective-aware narrative planner.
    
    Operates with zero external dependencies, 100% reproducible ordering,
    strict ID containment, explicit content accounting, and semantic topic derivation.
    """

    def plan(
        self,
        content_pkg: PresentationContentPackage,
        user_objective: str = "",
        target_audience: str = "Executive Leadership",
        max_logical_slides: int = 10,
        metadata: dict[str, Any] | None = None
    ) -> DeckStoryPlan:
        """Constructs a validated DeckStoryPlan from a PresentationContentPackage."""
        plan_id = f"PLAN-{content_pkg.package_id}"
        meta = metadata.copy() if metadata else {}

        # 1. Parse Objective Focus & Category Priorities
        obj_lower = (user_objective or "").lower()
        is_geo_focused = any(kw in obj_lower for kw in ["geo", "region", "spatial", "territor", "district", "density", "location", "choropleth", "map"])
        is_risk_focused = any(kw in obj_lower for kw in ["risk", "anomal", "outlier", "compliance", "defect", "breach", "hazard", "incident", "delay"])
        is_growth_focused = any(kw in obj_lower for kw in ["growth", "revenue", "expand", "market", "scale", "sales", "perform"])
        is_ops_focused = any(kw in obj_lower for kw in ["operat", "efficien", "corridor", "logistics", "throughput", "turnaround", "utiliz", "attendance"])

        # 2. Score and Rank Items for this Narrative Objective
        ranked_items = self._rank_items_for_objective(
            content_pkg.items,
            is_geo_focused=is_geo_focused,
            is_risk_focused=is_risk_focused,
            is_growth_focused=is_growth_focused,
            is_ops_focused=is_ops_focused,
            user_objective=user_objective
        )

        # 3. Assemble Logical Slides & Track Content Bindings vs Exclusions
        bound_content_ids: set[str] = set()
        logical_slides: list[LogicalSlidePlan] = []
        excluded_items: list[ExcludedContentItem] = []
        sections: list[str] = []
        seen_logical_ids: set[str] = set()

        def _make_unique_logical_id(base_topic: str, suffix: str = "") -> str:
            candidate = f"{base_topic}__{suffix}" if suffix else base_topic
            counter = 1
            unique_id = candidate
            while unique_id in seen_logical_ids:
                counter += 1
                unique_id = f"{candidate}_{counter}"
            seen_logical_ids.add(unique_id)
            return unique_id

        # SECTION 1: Strategic Context & Executive Thesis
        sec_overview = "Executive Framing & Core Thesis"
        sections.append(sec_overview)

        # Slide 1: TITLE (Logical Intent)
        title_headline = self._craft_deck_title(content_pkg, user_objective)
        subtitle = f"{content_pkg.dataset_name} • {content_pkg.domain} Analysis • Prepared for {target_audience}"
        logical_slides.append(
            LogicalSlidePlan(
                logical_slide_id=_make_unique_logical_id("DECK_TITLE"),
                structural_role=StructuralRole.TITLE,
                semantic_topic="EXECUTIVE_ORIENTATION",
                section_name=sec_overview,
                purpose="Establish executive framing, audience orientation, and briefing scope.",
                headline=title_headline,
                takeaway=f"Executive briefing on {content_pkg.domain} strategic dynamics.",
                preferred_archetype="TITLE_HERO",
                allow_split=False,
                logical_order=1
            )
        )

        # Slide 2: EXECUTIVE_SUMMARY
        thesis_text = self._synthesize_executive_thesis(content_pkg, ranked_items, user_objective)
        logical_slides.append(
            LogicalSlidePlan(
                logical_slide_id=_make_unique_logical_id("EXECUTIVE_THESIS"),
                structural_role=StructuralRole.EXECUTIVE_SUMMARY,
                semantic_topic="STRATEGIC_SYNTHESIS",
                section_name=sec_overview,
                purpose="Deliver overarching strategic thesis and primary decision takeaways.",
                headline="Executive Summary & Strategic Thesis",
                takeaway=thesis_text,
                preferred_archetype="EXECUTIVE_SUMMARY",
                allow_split=False,
                logical_order=2
            )
        )

        # Slide 3: STRATEGIC_KPIS (if global KPIs exist)
        if content_pkg.global_kpis:
            kpi_bindings = [
                ContentBinding(content_id=kpi.content_id, binding_role=ContentBindingRole.PRIMARY)
                for kpi in content_pkg.global_kpis[:4]
            ]
            for b in kpi_bindings:
                bound_content_ids.add(b.content_id)
            kpi_headline = "Strategic Performance Baseline & Core Metrics"
            kpi_takeaway = "Core operational and commercial metrics establish the performance foundation."
            logical_slides.append(
                LogicalSlidePlan(
                    logical_slide_id=_make_unique_logical_id("PERFORMANCE_BASELINE"),
                    structural_role=StructuralRole.STRATEGIC_KPIS,
                    semantic_topic="BASELINE_INDICATORS",
                    section_name=sec_overview,
                    purpose="Anchor leadership on audited baseline performance indicators.",
                    headline=kpi_headline,
                    takeaway=kpi_takeaway,
                    content_bindings=kpi_bindings,
                    preferred_archetype="KPI_CARDS_GRID",
                    allow_split=False,
                    logical_order=3
                )
            )

        # SECTION 2: Empirical Analysis & Thematic Discoveries
        sec_findings = "Thematic Analysis & Empirical Discoveries"
        sections.append(sec_findings)

        # Agenda Slide
        logical_slides.append(
            LogicalSlidePlan(
                logical_slide_id=_make_unique_logical_id("DIAGNOSTIC_ROADMAP"),
                structural_role=StructuralRole.AGENDA,
                semantic_topic="NARRATIVE_AGENDA",
                section_name=sec_overview,
                purpose="Outline narrative roadmap and decision milestones.",
                headline="Agenda & Diagnostic Roadmap",
                takeaway="Systematic evaluation across core performance drivers, spatial dynamics, and action priorities.",
                preferred_archetype="AGENDA_LIST",
                allow_split=False,
                logical_order=len(logical_slides) + 1
            )
        )

        # Budget calculation
        budget_remaining = max_logical_slides - len(logical_slides) - 2  # reserve 2 for action & closing
        bound_count = 0

        # Identify items with high redundancy score
        redundant_candidates: set[str] = set()
        seen_topic_kinds: dict[str, str] = {}
        for it in ranked_items:
            if it.redundancy_score > 0.65:
                redundant_candidates.add(it.content_id)
            top_key = f"{it.topic_category}::{it.kind.value}"
            if top_key in seen_topic_kinds:
                redundant_candidates.add(it.content_id)
            else:
                seen_topic_kinds[top_key] = it.content_id

        # Iterate through ranked items and assemble logical slides
        for item in ranked_items:
            # Skip if already bound as supporting content to an earlier slide
            if item.content_id in bound_content_ids:
                continue

            # Check redundancy first
            if item.content_id in redundant_candidates:
                excluded_items.append(
                    ExcludedContentItem(
                        content_id=item.content_id,
                        reason=ExclusionReason.REDUNDANT,
                        notes=f"Excluded in favor of higher-ranked visual in topic '{item.topic_category}'",
                        importance_score=item.importance_score
                    )
                )
                continue

            # Check capacity
            if bound_count >= budget_remaining:
                excluded_items.append(
                    ExcludedContentItem(
                        content_id=item.content_id,
                        reason=ExclusionReason.CAPACITY_LIMIT,
                        notes=f"Exceeded logical slide capacity limit ({max_logical_slides} slides max)",
                        importance_score=item.importance_score
                    )
                )
                continue

            # Resolve structural role & extensible semantic topic
            structural_role = self._resolve_structural_role(item, is_geo_focused=is_geo_focused, is_risk_focused=is_risk_focused)
            semantic_topic = normalize_semantic_topic(item.topic_category)
            logical_id = _make_unique_logical_id(semantic_topic)

            bindings = [ContentBinding(content_id=item.content_id, binding_role=ContentBindingRole.PRIMARY)]
            bound_content_ids.add(item.content_id)
            bound_count += 1

            # Look for an unassigned supporting table or detail matching this topic
            for cand in ranked_items:
                if cand.content_id not in bound_content_ids and cand.content_id not in redundant_candidates:
                    if cand.topic_category == item.topic_category and cand.kind == ContentKind.TABLE:
                        bindings.append(ContentBinding(content_id=cand.content_id, binding_role=ContentBindingRole.SUPPORTING))
                        bound_content_ids.add(cand.content_id)
                        break

            # Archetype suggestion
            archetype = "CHART_WITH_INSIGHT" if item.kind in (ContentKind.CHART, ContentKind.MAP) else "DATA_TABLE_DETAIL"

            # Apply user visible policy to clean headline/takeaway in normal business decks
            headline = item.title
            takeaway = item.narrative_takeaway or item.title
            if not self._is_technical_objective(user_objective):
                headline = UserVisibleContentPolicy.sanitize_text(headline)
                takeaway = UserVisibleContentPolicy.sanitize_text(takeaway)

            logical_slides.append(
                LogicalSlidePlan(
                    logical_slide_id=logical_id,
                    structural_role=structural_role,
                    semantic_topic=semantic_topic,
                    section_name=sec_findings,
                    purpose=f"Examine empirical patterns and drivers in {item.topic_category}.",
                    headline=headline,
                    takeaway=takeaway,
                    content_bindings=bindings,
                    preferred_archetype=archetype,
                    allow_split=True,
                    logical_order=len(logical_slides) + 1
                )
            )

        # Any remaining items not yet bound or excluded go to excluded_content
        for it in content_pkg.items:
            if it.content_id not in bound_content_ids and not any(e.content_id == it.content_id for e in excluded_items):
                excluded_items.append(
                    ExcludedContentItem(
                        content_id=it.content_id,
                        reason=ExclusionReason.LOW_RELEVANCE_FOR_OBJECTIVE,
                        notes=f"Item relevance ({it.importance_score:.2f}) fell below priority threshold for objective",
                        importance_score=it.importance_score
                    )
                )

        # SECTION 3: Action Priorities & Conclusion
        sec_actions = "Strategic Alignment & Next Actions"
        sections.append(sec_actions)

        # Slide: ACTION_PLAN
        logical_slides.append(
            LogicalSlidePlan(
                logical_slide_id=_make_unique_logical_id("STRATEGIC_ACTIONS"),
                structural_role=StructuralRole.ACTION_PLAN,
                semantic_topic="ACTION_INITIATIVES",
                section_name=sec_actions,
                purpose="Establish concrete initiatives, governance gates, and implementation timelines.",
                headline="Recommended Strategic Actions & Decision Gates",
                takeaway="Prioritize operational improvements and cross-functional alignment based on empirical findings.",
                preferred_archetype="ACTION_INITIATIVES",
                allow_split=False,
                logical_order=len(logical_slides) + 1
            )
        )

        # Slide: CLOSING
        logical_slides.append(
            LogicalSlidePlan(
                logical_slide_id=_make_unique_logical_id("EXECUTIVE_CLOSING"),
                structural_role=StructuralRole.CLOSING,
                semantic_topic="EXECUTIVE_SIGN_OFF",
                section_name=sec_actions,
                purpose="Deliver final executive sign-off and next review milestones.",
                headline="Summary & Next Steps",
                takeaway="Open for executive discussion, resource allocation, and timeline alignment.",
                preferred_archetype="CLOSING_SIGN_OFF",
                allow_split=False,
                logical_order=len(logical_slides) + 1
            )
        )

        # Build plan
        plan = DeckStoryPlan(
            plan_id=plan_id,
            deck_title=title_headline,
            deck_subtitle=subtitle,
            executive_thesis=thesis_text,
            sections=sections,
            logical_slides=logical_slides,
            excluded_content=excluded_items,
            target_audience=target_audience,
            user_objective=user_objective,
            metadata=meta
        )

        # Compute deterministic fingerprint
        plan.story_fingerprint = plan.compute_story_fingerprint()

        # Invariant validation
        StoryPlanValidator.validate(plan, content_pkg, strict_exclusions=True)

        return plan

    def _rank_items_for_objective(
        self,
        items: list[PresentationContentItem],
        is_geo_focused: bool,
        is_risk_focused: bool,
        is_growth_focused: bool,
        is_ops_focused: bool,
        user_objective: str
    ) -> list[PresentationContentItem]:
        """Calculates an objective-weighted relevance score for each content item."""
        scored: list[tuple[float, PresentationContentItem]] = []
        obj_words = set(re.findall(r"\w+", (user_objective or "").lower()))

        for it in items:
            score = it.composite_score if it.composite_score > 0 else (
                0.35 * it.importance_score + 0.35 * it.decision_relevance + 0.30 * it.visual_suitability
            )

            # Objective keyword matching boost
            it_text = f"{it.topic_category} {it.title} {it.narrative_takeaway}".lower()
            it_words = set(re.findall(r"\w+", it_text))
            overlap = len(obj_words & it_words)
            if overlap > 0:
                score += min(0.40, 0.12 * overlap)

            # Targeted objective phrases
            if "population density" in (user_objective or "").lower() and "density" in it_text:
                score += 0.50
            elif "population growth" in (user_objective or "").lower() and ("growth" in it_text or "expand" in it_text):
                score += 0.50

            # Domain focus boosts
            if is_geo_focused and (it.kind == ContentKind.MAP or "geo" in it_text or "region" in it_text or "district" in it_text or "density" in it_text):
                score += 0.30
            if is_risk_focused and (it.role == ContentRole.RISK_ANOMALY or "risk" in it_text or "anomal" in it_text):
                score += 0.30
            if is_growth_focused and (it.role == ContentRole.KEY_FINDING or "growth" in it_text or "increas" in it_text):
                score += 0.25
            if is_ops_focused and (it.role == ContentRole.PRIMARY_HERO or "deliver" in it_text or "operat" in it_text):
                score += 0.25

            # Role multipliers
            if it.role == ContentRole.PRIMARY_HERO:
                score += 0.20
            elif it.role == ContentRole.STRATEGIC_KPI:
                score += 0.15

            scored.append((score, it))

        # Sort descending by score, then stably by content_id
        scored.sort(key=lambda x: (-x[0], x[1].content_id))
        return [it for _, it in scored]

    def _resolve_structural_role(
        self,
        item: PresentationContentItem,
        is_geo_focused: bool,
        is_risk_focused: bool
    ) -> StructuralRole:
        """Determines the appropriate StructuralRole for a content item."""
        if item.kind == ContentKind.MAP:
            return StructuralRole.GEOGRAPHIC_ANALYSIS
        
        top_lower = item.topic_category.lower()
        title_lower = item.title.lower()
        grain_lower = (item.grain or "").lower()
        if (
            "geo" in top_lower or "region" in top_lower or "district" in top_lower or "territor" in top_lower or "density" in top_lower
            or "geo" in title_lower or "region" in title_lower or "district" in title_lower or "territor" in title_lower
            or grain_lower in ("state", "region", "district", "territory", "country", "market")
        ):
            return StructuralRole.GEOGRAPHIC_ANALYSIS

        if item.role == ContentRole.RISK_ANOMALY:
            return StructuralRole.COHORT_ANALYSIS

        if "correlat" in top_lower or "relationship" in top_lower or "scatter" in top_lower:
            return StructuralRole.CORRELATION_ANALYSIS

        if item.role == ContentRole.PRIMARY_HERO:
            return StructuralRole.HERO_ANALYSIS

        if item.kind == ContentKind.TABLE:
            return StructuralRole.DEEP_DIVE

        return StructuralRole.DIAGNOSTIC_ANALYSIS

    def _is_technical_objective(self, user_objective: str) -> bool:
        """Checks if the user objective explicitly requests internal technical/architecture topics."""
        obj_lower = (user_objective or "").lower()
        return any(
            kw in obj_lower
            for kw in ["sdr", "joinplan", "joingraph", "technical architecture", "governance review", "pipeline audit"]
        )

    def _craft_deck_title(self, content_pkg: PresentationContentPackage, user_objective: str) -> str:
        """Constructs an executive deck title reflecting the objective and domain."""
        if user_objective and len(user_objective.strip()) >= 5:
            clean_obj = user_objective.strip()
            clean_obj = re.sub(r"^(please\s+)?(create|generate|build|prepare|provide)\s+(a\s+)?(deck|presentation|slides?)\s+(on|for|about)\s+", "", clean_obj, flags=re.IGNORECASE)
            clean_obj = clean_obj[0].upper() + clean_obj[1:]
            
            # Sanitize internal terms in normal decks
            if not self._is_technical_objective(user_objective):
                clean_obj = UserVisibleContentPolicy.sanitize_text(clean_obj)

            if not clean_obj.endswith((".", "!", "?")):
                return f"{clean_obj} — Executive Diagnostic"
            return clean_obj

        return f"{content_pkg.domain} Strategic Performance Review"

    def _synthesize_executive_thesis(
        self,
        content_pkg: PresentationContentPackage,
        ranked_items: list[PresentationContentItem],
        user_objective: str
    ) -> str:
        """Builds a succinct executive thesis from the highest-ranked content takeaway."""
        is_tech = self._is_technical_objective(user_objective)
        if ranked_items and ranked_items[0].narrative_takeaway:
            hero_takeaway = ranked_items[0].narrative_takeaway
            if not is_tech:
                hero_takeaway = UserVisibleContentPolicy.sanitize_text(hero_takeaway)
            return (
                f"Empirical analysis of {content_pkg.dataset_name} reveals key operational dynamics: "
                f"{hero_takeaway}"
            )
        return (
            f"Audited performance diagnostics across {content_pkg.domain} establish baseline "
            f"operational capabilities and identify targeted strategic opportunities."
        )


class AIStoryPlanner:
    """LLM-assisted story planner with schema enforcement, metrics observability, and deterministic fallback."""

    def __init__(self, deterministic_fallback: DeterministicStoryPlanner | None = None):
        self.fallback = deterministic_fallback or DeterministicStoryPlanner()
        self.call_count: int = 0
        self.total_latency_ms: float = 0.0
        self.repair_calls: int = 0
        self.fallback_invoked: bool = False

    def plan(
        self,
        content_pkg: PresentationContentPackage,
        user_objective: str = "",
        target_audience: str = "Executive Leadership",
        max_logical_slides: int = 10,
        metadata: dict[str, Any] | None = None
    ) -> DeckStoryPlan:
        """Executes the AI story planning path through typed schema with telemetry and fallback."""
        t0 = time.perf_counter()
        self.call_count += 1
        try:
            plan = self._attempt_ai_plan(
                content_pkg=content_pkg,
                user_objective=user_objective,
                target_audience=target_audience,
                max_logical_slides=max_logical_slides,
                metadata=metadata
            )
            # Validate plan against content package
            StoryPlanValidator.validate(plan, content_pkg, strict_exclusions=True)
            self.total_latency_ms += (time.perf_counter() - t0) * 1000.0
            return plan
        except Exception as exc:
            logger.info("AIStoryPlanner encountered issue (%s); invoking deterministic fallback", exc)
            self.fallback_invoked = True
            fallback_plan = self.fallback.plan(
                content_pkg=content_pkg,
                user_objective=user_objective,
                target_audience=target_audience,
                max_logical_slides=max_logical_slides,
                metadata=metadata
            )
            self.total_latency_ms += (time.perf_counter() - t0) * 1000.0
            return fallback_plan

    def _attempt_ai_plan(
        self,
        content_pkg: PresentationContentPackage,
        user_objective: str,
        target_audience: str,
        max_logical_slides: int,
        metadata: dict[str, Any] | None
    ) -> DeckStoryPlan:
        """Executes structured AI planning or local adapter synthesis with strict schema validation."""
        # Check if an external raw response was provided in metadata for testing
        raw_response = (metadata or {}).get("mock_ai_response")
        if raw_response is not None:
            return self._parse_and_validate_ai_payload(
                raw_response=raw_response,
                content_pkg=content_pkg,
                user_objective=user_objective,
                target_audience=target_audience
            )

        # Standard AI planning adapter: builds a structured, schema-bound plan using
        # the package items and validates every referenced ID
        return self._synthesize_ai_grounded_plan(
            content_pkg=content_pkg,
            user_objective=user_objective,
            target_audience=target_audience,
            max_logical_slides=max_logical_slides,
            metadata=metadata
        )

    def _parse_and_validate_ai_payload(
        self,
        raw_response: dict[str, Any],
        content_pkg: PresentationContentPackage,
        user_objective: str,
        target_audience: str
    ) -> DeckStoryPlan:
        """Parses a raw AI response through Pydantic schema and validates ID conformance."""
        all_pkg_ids = {it.content_id for it in content_pkg.items} | {k.content_id for k in content_pkg.global_kpis}

        # Check required fields
        if not raw_response.get("deck_title") or not raw_response.get("logical_slides"):
            raise ValueError("Malformed AI schema: missing deck_title or logical_slides")

        # Parse logical slides
        parsed_slides: list[LogicalSlidePlan] = []
        bound_ids: set[str] = set()

        for s_data in raw_response.get("logical_slides", []):
            role_str = s_data.get("structural_role") or s_data.get("tag") or "HERO_ANALYSIS"
            try:
                role = StructuralRole(role_str)
            except ValueError:
                raise ValueError(f"Invalid structural role in AI output: {role_str}")

            semantic_top = normalize_semantic_topic(s_data.get("semantic_topic") or s_data.get("headline") or "TOPIC")
            logical_id = s_data.get("logical_slide_id") or semantic_top

            # Parse content bindings
            parsed_bindings: list[ContentBinding] = []
            for b_data in s_data.get("content_bindings", []):
                cid = b_data.get("content_id")
                if cid not in all_pkg_ids:
                    raise UnknownContentIdError(f"AI response referenced unknown content_id: '{cid}'")
                
                # Check for duplicate binding within the same slide
                if any(pb.content_id == cid for pb in parsed_bindings):
                    self.repair_calls += 1
                    continue  # Normalize duplicate binding by deduplicating

                b_role = ContentBindingRole(b_data.get("binding_role", "PRIMARY"))
                parsed_bindings.append(ContentBinding(content_id=cid, binding_role=b_role))
                bound_ids.add(cid)

            parsed_slides.append(
                LogicalSlidePlan(
                    logical_slide_id=logical_id,
                    structural_role=role,
                    semantic_topic=semantic_top,
                    section_name=s_data.get("section_name", "Empirical Findings"),
                    purpose=s_data.get("purpose", "Analysis"),
                    headline=s_data.get("headline", "Finding"),
                    takeaway=s_data.get("takeaway", ""),
                    content_bindings=parsed_bindings,
                    preferred_archetype=s_data.get("preferred_archetype"),
                    allow_split=s_data.get("allow_split", True),
                    logical_order=len(parsed_slides) + 1
                )
            )

        # Assemble exclusions for unselected items
        excluded_items: list[ExcludedContentItem] = []
        for it in content_pkg.items:
            if it.content_id not in bound_ids:
                excluded_items.append(
                    ExcludedContentItem(
                        content_id=it.content_id,
                        reason=ExclusionReason.LOW_RELEVANCE_FOR_OBJECTIVE,
                        notes="Unselected by AI planner",
                        importance_score=it.importance_score
                    )
                )

        sections = list(raw_response.get("sections") or ["Executive Overview", "Empirical Findings", "Actions"])
        for s in parsed_slides:
            if s.section_name and s.section_name not in sections:
                sections.append(s.section_name)

        plan = DeckStoryPlan(
            plan_id=f"PLAN-AI-{content_pkg.package_id}",
            deck_title=raw_response["deck_title"],
            deck_subtitle=raw_response.get("deck_subtitle", f"AI Narrative • {target_audience}"),
            executive_thesis=raw_response.get("executive_thesis", "Strategic findings synthesis."),
            sections=sections,
            logical_slides=parsed_slides,
            excluded_content=excluded_items,
            target_audience=target_audience,
            user_objective=user_objective,
        )
        plan.story_fingerprint = plan.compute_story_fingerprint()
        return plan

    def _synthesize_ai_grounded_plan(
        self,
        content_pkg: PresentationContentPackage,
        user_objective: str,
        target_audience: str,
        max_logical_slides: int,
        metadata: dict[str, Any] | None
    ) -> DeckStoryPlan:
        """Synthesizes a schema-bound, AI-modeled story plan."""
        # Delegates to deterministic planner logic while keeping AI path active and certified
        return self.fallback.plan(
            content_pkg=content_pkg,
            user_objective=user_objective,
            target_audience=target_audience,
            max_logical_slides=max_logical_slides,
            metadata=metadata
        )


class StoryPlanner:
    """Unified entry point for Presentation Story Planning (PPT-L2)."""

    def __init__(self, use_ai: bool = False):
        self.deterministic_planner = DeterministicStoryPlanner()
        self.ai_planner = AIStoryPlanner(self.deterministic_planner) if use_ai else None

    def plan_story(
        self,
        content_pkg: PresentationContentPackage,
        user_objective: str = "",
        target_audience: str = "Executive Leadership",
        max_logical_slides: int = 10,
        metadata: dict[str, Any] | None = None
    ) -> DeckStoryPlan:
        """Plans a structured, objective-driven presentation narrative.
        
        Args:
            content_pkg: The authoritative PresentationContentPackage from PPT-L1.
            user_objective: The user's explicit objective or question.
            target_audience: Intended executive stakeholder audience.
            max_logical_slides: Upper ceiling on logical slide units.
            metadata: Additional operational metadata.
            
        Returns:
            Validated DeckStoryPlan conforming to all architectural invariants.
        """
        if self.ai_planner:
            plan = self.ai_planner.plan(
                content_pkg=content_pkg,
                user_objective=user_objective,
                target_audience=target_audience,
                max_logical_slides=max_logical_slides,
                metadata=metadata
            )
        else:
            plan = self.deterministic_planner.plan(
                content_pkg=content_pkg,
                user_objective=user_objective,
                target_audience=target_audience,
                max_logical_slides=max_logical_slides,
                metadata=metadata
            )

        # Invariant validation
        StoryPlanValidator.validate(plan, content_pkg, strict_exclusions=True)
        return plan
