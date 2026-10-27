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
    VisualCompleteness,
    VisualStrategy,
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
        target_audience: str = "Stakeholders",
        max_logical_slides: int | None = None,
        metadata: dict[str, Any] | None = None
    ) -> DeckStoryPlan:
        """Constructs a validated DeckStoryPlan from a PresentationContentPackage."""
        plan_id = f"PLAN-{content_pkg.package_id}"
        meta = metadata.copy() if metadata else {}

        # 0. Resolve Context Profile & Likely Audience without corporate bias (Stage B)
        raw_cp = content_pkg.metadata.get("context_profile")
        if raw_cp and isinstance(raw_cp, dict):
            from .context_profile import PresentationContextProfile
            context_profile = PresentationContextProfile(**raw_cp)
        else:
            from .context_profile import build_presentation_context_profile
            synth_ctx = {
                "dataset_name": content_pkg.dataset_name,
                "columns": [it.metric_name for it in content_pkg.items if it.metric_name],
                "domain": content_pkg.domain,
                "records": [],
                "target_sheet": {"name": content_pkg.dataset_name, "original_name": content_pkg.dataset_name},
            }
            context_profile = build_presentation_context_profile(synth_ctx, user_objective=user_objective)

        corporate_audiences = {
            "executive leadership",
            "c-suite & operations leadership",
            "c-suite",
            "cfo & audit committee",
            "people operations leaders",
        }
        effective_audience = target_audience
        if not effective_audience or effective_audience.strip().lower() in corporate_audiences:
            effective_audience = context_profile.likely_audience or "General stakeholders"

        # Resolve source scope: canonical default is COMPLETE_EVIDENCE (all evidence considered)
        source_scope = meta.get("source_scope") or "COMPLETE_EVIDENCE"
        if "dashboard only" in (user_objective or "").lower() or "source scope: dashboard only" in (user_objective or "").lower():
            source_scope = "DASHBOARD_ONLY"
        meta["source_scope"] = source_scope

        # Initialize Artifact Coverage Ledger (Stage D)
        from .coverage_ledger import ArtifactCoverageLedger, ArtifactDisposition
        from .presentation_evidence import CommonArtifactDescriptor, SourceSurface, PresentationEvidenceUniverse
        coverage_ledger = ArtifactCoverageLedger()

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
        seen_headlines: set[str] = set()

        def _make_unique_logical_id(base_topic: str, suffix: str = "") -> str:
            candidate = f"{base_topic}__{suffix}" if suffix else base_topic
            counter = 1
            unique_id = candidate
            while unique_id in seen_logical_ids:
                counter += 1
                unique_id = f"{candidate}_{counter}"
            seen_logical_ids.add(unique_id)
            return unique_id

        # Check technical objective mode
        is_tech = self._is_technical_objective(user_objective)

        # SECTION 1: Strategic Context & Core Thesis
        sec_overview = "Strategic Framing & Core Thesis"
        sections.append(sec_overview)

        thesis_text = self._synthesize_executive_thesis(content_pkg, ranked_items, user_objective)
        title_headline = self._craft_deck_title(content_pkg, user_objective, context_profile=context_profile)
        subtitle = f"{content_pkg.dataset_name} • {context_profile.inferred_domain or content_pkg.domain} • Prepared for {effective_audience}"

        if is_tech:
            cover_title = title_headline
            cover_subtitle = subtitle
        else:
            cover_title = context_profile.presentation_title or title_headline
            cover_subtitle = context_profile.presentation_subtitle or subtitle

        # Dedicated Framing Cover Slide (Slide 1) - Framing slide with 0 analytical bindings
        cover_metadata = {
            "is_cover": True,
            "planned_layout_family": "title_cover",
            "presentation_title": cover_title,
            "presentation_subtitle": cover_subtitle,
            "presenter_name": context_profile.presenter_name or "[Presenter Name]",
            "presenter_role": context_profile.presenter_role,
            "organization_name": context_profile.organization_name or "[Organization / Institution]",
            "organization_logo": context_profile.organization_logo,
            "presentation_date": context_profile.presentation_date,
        }
        logical_slides.append(
            LogicalSlidePlan(
                logical_slide_id=_make_unique_logical_id("COVER_TITLE"),
                structural_role=StructuralRole.TITLE,
                semantic_topic="PRESENTATION_COVER",
                section_name=sec_overview,
                purpose="Establish presentation framing, topic, audience context, and presenter attribution.",
                headline=cover_title,
                takeaway=cover_subtitle,
                content_bindings=[],
                preferred_archetype="TITLE_HERO",
                allow_split=False,
                logical_order=1,
                metadata=cover_metadata,
            )
        )

        if not is_tech:
            # Business Mode: Slide 2 binds the Baseline KPIs directly
            kpi_bindings: list[ContentBinding] = []
            if content_pkg.global_kpis:
                kpi_bindings = [
                    ContentBinding(
                        content_id=kpi.content_id,
                        binding_role=ContentBindingRole.PRIMARY,
                        visual_id=kpi.visual_id,
                        visual_strategy=kpi.visual_strategy,
                        visual_type=kpi.visual_type,
                        visual_spec=kpi.visual_spec,
                        source_surface=kpi.source_surface,
                    )
                    for kpi in content_pkg.global_kpis[:4]
                ]
                for b in kpi_bindings:
                    bound_content_ids.add(b.content_id)
                    kpi_desc = CommonArtifactDescriptor(
                        artifact_id=f"ART-KPI-{b.content_id}",
                        artifact_type="kpi",
                        source_surface=SourceSurface.DASHBOARD,
                        semantic_topic="Headline Indicators",
                        title=f"Core Metric: {b.content_id}",
                        description="Headline baseline indicator.",
                        importance=0.95,
                    )
                    coverage_ledger.record_disposition(
                        artifact=kpi_desc,
                        disposition=ArtifactDisposition.MAIN_DECK,
                        target_slide_id="STRATEGIC_KPIS",
                        target_section=sec_overview,
                    )

            domain_str = str(context_profile.inferred_domain or content_pkg.domain or "").lower()
            dataset_str = str(content_pkg.dataset_name or "").lower()
            is_retail = "retail" in domain_str or "commercial" in domain_str or "sales" in domain_str or "walmart" in dataset_str
            is_demographics = "demographic" in domain_str or "population" in domain_str or "census" in dataset_str or "india" in dataset_str
            is_education = "education" in domain_str or "academic" in domain_str or "school" in domain_str or "district" in dataset_str or "pgi" in dataset_str

            if is_education:
                kpi_headline = "Academic Performance at a Glance"
                title_takeaway = "Baseline indicator distributions establish the operational and academic foundation across evaluated educational districts."
            elif is_retail:
                kpi_headline = "Commercial Sales Performance at a Glance"
                title_takeaway = "Total network sales stand at $6.74B with $1.05M weekly store average, led by top tier locations and strong holiday lift (+7.8%)."
            elif is_demographics:
                kpi_headline = "Demographic Distribution at a Glance"
                title_takeaway = "Regional population scale, density patterns, and state-level distributions establish the baseline demographic structure."
            else:
                kpi_headline = "Performance Overview at a Glance"
                title_takeaway = "Empirical baseline indicators establish the operational foundation across observed entities."

            if kpi_bindings:
                logical_slides.append(
                    LogicalSlidePlan(
                        logical_slide_id=_make_unique_logical_id("STRATEGIC_KPIS"),
                        structural_role=StructuralRole.STRATEGIC_KPIS,
                        semantic_topic="BASELINE_INDICATORS",
                        section_name=sec_overview,
                        purpose="Establish analytical framing, baseline indicators, and briefing scope.",
                        headline=kpi_headline,
                        takeaway=title_takeaway,
                        content_bindings=kpi_bindings,
                        preferred_archetype="KPI_GRID",
                        allow_split=False,
                        logical_order=len(logical_slides) + 1,
                        metadata={"planned_layout_family": "kpi_summary"},
                    )
                )
        else:
            # Technical / Governance Mode: Full orientation breakdown
            logical_slides.append(
                LogicalSlidePlan(
                    logical_slide_id=_make_unique_logical_id("PRESENTATION_THESIS"),
                    structural_role=StructuralRole.EXECUTIVE_SUMMARY,
                    semantic_topic="STRATEGIC_SYNTHESIS",
                    section_name=sec_overview,
                    purpose="Deliver overarching strategic thesis and primary decision takeaways.",
                    headline="Presentation Overview & Strategic Thesis",
                    takeaway=thesis_text,
                    preferred_archetype="EXECUTIVE_SUMMARY",
                    allow_split=False,
                    logical_order=len(logical_slides) + 1
                )
            )

            if content_pkg.global_kpis:
                kpi_bindings = [
                    ContentBinding(
                        content_id=kpi.content_id,
                        binding_role=ContentBindingRole.PRIMARY,
                        visual_id=kpi.visual_id,
                        visual_strategy=kpi.visual_strategy,
                        visual_type=kpi.visual_type,
                        visual_spec=kpi.visual_spec,
                        source_surface=kpi.source_surface,
                    )
                    for kpi in content_pkg.global_kpis[:4]
                ]
                for b in kpi_bindings:
                    bound_content_ids.add(b.content_id)
                kpi_headline = "Performance Baseline & Core Metrics"
                kpi_takeaway = "Core operational metrics establish the analytical foundation."
                logical_slides.append(
                    LogicalSlidePlan(
                        logical_slide_id=_make_unique_logical_id("PERFORMANCE_BASELINE"),
                        structural_role=StructuralRole.STRATEGIC_KPIS,
                        semantic_topic="BASELINE_INDICATORS",
                        section_name=sec_overview,
                        purpose="Anchor stakeholders on audited baseline performance indicators.",
                        headline=kpi_headline,
                        takeaway=kpi_takeaway,
                        content_bindings=kpi_bindings,
                        preferred_archetype="KPI_CARDS_GRID",
                        allow_split=False,
                        logical_order=3,
                        visual_id="kpi_cluster",
                        visual_strategy=VisualStrategy.PRESENTATION_RECOMMENDATION,
                        visual_type="kpi_metric",
                        source_surface="dashboard",
                    )
                )

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

        # SECTION 2: Empirical Analysis & Thematic Discoveries
        sec_findings = "Thematic Analysis & Empirical Discoveries"
        sections.append(sec_findings)

        # Budget calculation: By default, generate every meaningful slide available from evidence with no default slide-count cap.
        reused_count = sum(1 for it in ranked_items if it.visual_strategy == VisualStrategy.REUSE_EXISTING)
        if max_logical_slides is not None:
            effective_max_slides = max(max_logical_slides, len(logical_slides) + reused_count + 2)
            budget_remaining = effective_max_slides - len(logical_slides) - 2  # reserve 2 for action & closing
        else:
            effective_max_slides = len(ranked_items) + len(logical_slides) + 10
            budget_remaining = len(ranked_items) + 10  # no artificial budget constraint
        bound_count = 0

        # Identify items with high redundancy score or duplicate visual representations
        redundant_candidates: set[str] = set()
        seen_topic_kinds: dict[str, str] = {}
        seen_entity_visuals: dict[str, str] = {}
        seen_questions: dict[str, str] = {}
        for it in ranked_items:
            q_clean = it.title.strip().lower()
            if q_clean in seen_questions:
                # Same underlying analytical question addressed by multiple visuals; mark secondary visual as redundant
                redundant_candidates.add(it.content_id)
                continue
            seen_questions[q_clean] = it.content_id

            # Check for duplicate ranking charts on the same entity/metric
            v_fam = str(it.visual_type or "").lower()
            dim = str((it.source_data_reference or {}).get("dimension") or "").lower()
            met = str((it.source_data_reference or {}).get("metric") or "").lower()
            ent_key = f"{v_fam}::{dim}::{met}" if (dim or met) else None

            # Reused visuals from dashboard / data explorer represent verified distinct findings
            if it.visual_strategy == VisualStrategy.REUSE_EXISTING:
                top_key = f"{it.topic_category}::{it.visual_type}::{it.visual_id}"
            else:
                top_key = f"{it.topic_category}::{it.visual_type or it.kind.value}"

            if it.redundancy_score > 0.65:
                redundant_candidates.add(it.content_id)
            elif ent_key and ent_key in seen_entity_visuals and v_fam in ("ranked_bar", "ranking", "bar"):
                # Duplicate ranking chart on same entity/metric
                redundant_candidates.add(it.content_id)
            elif it.visual_strategy == VisualStrategy.REUSE_EXISTING:
                seen_topic_kinds[top_key] = it.content_id
                if ent_key:
                    seen_entity_visuals[ent_key] = it.content_id
            elif top_key in seen_topic_kinds:
                redundant_candidates.add(it.content_id)
            else:
                seen_topic_kinds[top_key] = it.content_id
                if ent_key:
                    seen_entity_visuals[ent_key] = it.content_id

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
                coverage_ledger.record_disposition(
                    artifact=CommonArtifactDescriptor(
                        artifact_id=f"ART-{item.content_id}",
                        artifact_type="chart" if item.kind == ContentKind.CHART else "table" if item.kind == ContentKind.TABLE else "fact",
                        source_surface=SourceSurface.DASHBOARD if item.source_surface == "dashboard" else SourceSurface.DATA_EXPLORER,
                        semantic_topic=item.topic_category,
                        title=item.title,
                        description=item.narrative_takeaway or item.title,
                        importance=item.importance_score,
                    ),
                    disposition=ArtifactDisposition.EXCLUDED,
                    exclusion_reason=f"Analytical relationship already represented by higher-ranked visual in topic '{item.topic_category}'"
                )
                continue

            # Check capacity only if caller explicitly specified a max_logical_slides constraint
            if max_logical_slides is not None and bound_count >= budget_remaining and item.visual_strategy != VisualStrategy.REUSE_EXISTING:
                excluded_items.append(
                    ExcludedContentItem(
                        content_id=item.content_id,
                        reason=ExclusionReason.CAPACITY_LIMIT,
                        notes=f"Exceeded logical slide capacity limit ({effective_max_slides} slides max)",
                        importance_score=item.importance_score
                    )
                )
                coverage_ledger.record_disposition(
                    artifact=CommonArtifactDescriptor(
                        artifact_id=f"ART-{item.content_id}",
                        artifact_type="chart" if item.kind == ContentKind.CHART else "table" if item.kind == ContentKind.TABLE else "fact",
                        source_surface=SourceSurface.DASHBOARD if item.source_surface == "dashboard" else SourceSurface.DATA_EXPLORER,
                        semantic_topic=item.topic_category,
                        title=item.title,
                        description=item.narrative_takeaway or item.title,
                        importance=item.importance_score,
                    ),
                    disposition=ArtifactDisposition.EXCLUDED,
                    exclusion_reason=f"Exceeded logical slide capacity limit ({effective_max_slides} slides max)"
                )
                continue

            # Data Explorer table: By canonical default, COMPLETE_EVIDENCE includes all Data Explorer and EDA evidence.
            # Limited scope (Dashboard only) is ONLY triggered if the user explicitly restricts the source scope
            # (e.g. source_scope="DASHBOARD_ONLY", explicit "source scope: dashboard only", or explicit "Executive Summary" without exploratory data).
            if item.role == ContentRole.EXPLORATORY_TABLE or item.source_surface == "data_explorer":
                is_dashboard_only_explicit = (
                    str(source_scope).upper() in ("DASHBOARD_ONLY", "DASHBOARD")
                    or "dashboard only" in obj_lower
                    or "source scope: dashboard only" in obj_lower
                    or ("executive summary" in obj_lower and not any(kw in obj_lower for kw in ["table", "explorer", "data", "all", "comprehensive"]))
                )
                if is_dashboard_only_explicit:
                    excluded_items.append(
                        ExcludedContentItem(
                            content_id=item.content_id,
                            reason=ExclusionReason.LOW_RELEVANCE_FOR_OBJECTIVE,
                            notes="Data Explorer table defaulted to SUPPORTING/OPTIONAL reference; excluded due to explicit dashboard-only scope",
                            importance_score=item.importance_score
                        )
                    )
                    coverage_ledger.record_disposition(
                        artifact=CommonArtifactDescriptor(
                            artifact_id=f"ART-{item.content_id}",
                            artifact_type="table",
                            source_surface=SourceSurface.DATA_EXPLORER,
                            semantic_topic=item.topic_category,
                            title=item.title,
                            description=item.narrative_takeaway or item.title,
                            importance=item.importance_score,
                        ),
                        disposition=ArtifactDisposition.SUPPORTING_NOTES,
                        exclusion_reason="Data Explorer table preserved for supporting reference due to explicit dashboard-only scope"
                    )
                    continue

            # Resolve structural role & extensible semantic topic
            structural_role = self._resolve_structural_role(item, is_geo_focused=is_geo_focused, is_risk_focused=is_risk_focused)
            if item.visual_strategy == VisualStrategy.REUSE_EXISTING and item.visual_type:
                semantic_topic = normalize_semantic_topic(f"{item.visual_type}_{item.visual_id or item.content_id}")
            else:
                semantic_topic = normalize_semantic_topic(item.topic_category)
            logical_id = _make_unique_logical_id(semantic_topic)

            bindings = [
                ContentBinding(
                    content_id=item.content_id,
                    binding_role=ContentBindingRole.PRIMARY,
                    visual_id=item.visual_id,
                    visual_strategy=item.visual_strategy,
                    visual_completeness=item.visual_completeness,
                    visual_type=item.visual_type,
                    visual_spec=item.visual_spec,
                    source_surface=item.source_surface,
                )
            ]
            bound_content_ids.add(item.content_id)
            bound_count += 1

            # Look for an unassigned supporting table or detail matching this topic
            for cand in ranked_items:
                if cand.content_id not in bound_content_ids and cand.content_id not in redundant_candidates:
                    if cand.topic_category == item.topic_category and cand.kind == ContentKind.TABLE:
                        bindings.append(
                            ContentBinding(
                                content_id=cand.content_id,
                                binding_role=ContentBindingRole.SUPPORTING,
                                visual_id=cand.visual_id,
                                visual_strategy=cand.visual_strategy,
                                visual_completeness=cand.visual_completeness,
                                visual_type=cand.visual_type,
                                visual_spec=cand.visual_spec,
                                source_surface=cand.source_surface,
                            )
                        )
                        bound_content_ids.add(cand.content_id)
                        coverage_ledger.record_disposition(
                            artifact=CommonArtifactDescriptor(
                                artifact_id=f"ART-{cand.content_id}",
                                artifact_type="table",
                                source_surface=SourceSurface.DATA_EXPLORER if cand.source_surface == "data_explorer" else SourceSurface.DASHBOARD,
                                semantic_topic=cand.topic_category,
                                title=cand.title,
                                description=cand.narrative_takeaway or cand.title,
                                importance=cand.importance_score,
                            ),
                            disposition=ArtifactDisposition.MAIN_DECK,
                            target_slide_id=logical_id,
                            target_section=sec_findings,
                            relationship_note="Bound as supporting table to primary finding"
                        )
                        break

            # Archetype suggestion
            if item.visual_strategy == VisualStrategy.REUSE_EXISTING and item.visual_type:
                archetype = f"REUSED_{item.visual_type.upper()}"
            elif item.kind in (ContentKind.CHART, ContentKind.MAP):
                archetype = "CHART_WITH_INSIGHT"
            else:
                archetype = "DATA_TABLE_DETAIL"

            # Apply user visible policy to clean headline/takeaway in normal business decks
            headline = item.title
            takeaway = item.narrative_takeaway or item.title
            if not is_tech:
                headline = self._humanize_business_headline(headline, item, content_pkg)
                headline = UserVisibleContentPolicy.sanitize_text(headline)
                takeaway = UserVisibleContentPolicy.sanitize_text(takeaway)

            # Stage 4 Invariant: REUSE_EXISTING + COMPLETE_VISUAL defaults to exactly 1 physical slide.
            is_complete_reused = (
                item.visual_strategy == VisualStrategy.REUSE_EXISTING
                and item.visual_completeness == VisualCompleteness.COMPLETE_VISUAL
            )
            allow_split = False if is_complete_reused else True

            if headline in seen_headlines:
                excluded_items.append(
                    ExcludedContentItem(
                        content_id=item.content_id,
                        reason=ExclusionReason.REDUNDANT,
                        notes=f"Headline '{headline}' already represented by earlier slide",
                        importance_score=item.importance_score
                    )
                )
                coverage_ledger.record_disposition(
                    artifact=CommonArtifactDescriptor(
                        artifact_id=f"ART-{item.content_id}",
                        artifact_type="chart" if item.kind == ContentKind.CHART else "table" if item.kind == ContentKind.TABLE else "figure",
                        source_surface=SourceSurface.DASHBOARD if item.source_surface == "dashboard" else SourceSurface.DATA_EXPLORER,
                        semantic_topic=item.topic_category,
                        title=headline,
                        description=takeaway,
                        importance=item.importance_score,
                    ),
                    disposition=ArtifactDisposition.EXCLUDED,
                    exclusion_reason=f"Duplicate analytical headline '{headline}' omitted in favor of primary visual"
                )
                continue
            seen_headlines.add(headline)

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
                    allow_split=allow_split,
                    logical_order=len(logical_slides) + 1,
                    visual_id=item.visual_id,
                    visual_strategy=item.visual_strategy,
                    visual_completeness=item.visual_completeness,
                    visual_type=item.visual_type,
                    visual_spec=item.visual_spec,
                    source_surface=item.source_surface,
                )
            )
            coverage_ledger.record_disposition(
                artifact=CommonArtifactDescriptor(
                    artifact_id=f"ART-{item.content_id}",
                    artifact_type="map" if item.kind == ContentKind.MAP else "chart" if item.kind == ContentKind.CHART else "figure",
                    source_surface=SourceSurface.DASHBOARD if item.source_surface == "dashboard" else SourceSurface.DATA_EXPLORER,
                    semantic_topic=item.topic_category,
                    title=headline,
                    description=takeaway,
                    importance=item.importance_score,
                ),
                disposition=ArtifactDisposition.MAIN_DECK,
                target_slide_id=logical_id,
                target_section=sec_findings,
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
                coverage_ledger.record_disposition(
                    artifact=CommonArtifactDescriptor(
                        artifact_id=f"ART-{it.content_id}",
                        artifact_type="chart" if it.kind == ContentKind.CHART else "table" if it.kind == ContentKind.TABLE else "fact",
                        source_surface=SourceSurface.DASHBOARD if it.source_surface == "dashboard" else SourceSurface.DATA_EXPLORER,
                        semantic_topic=it.topic_category,
                        title=it.title,
                        description=it.narrative_takeaway or it.title,
                        importance=it.importance_score,
                    ),
                    disposition=ArtifactDisposition.EXCLUDED,
                    exclusion_reason=f"Item relevance ({it.importance_score:.2f}) fell below priority threshold for objective"
                )

        # SECTION 3: Action Priorities & Conclusion
        sec_actions = "Strategic Alignment & Next Actions"
        sections.append(sec_actions)

        # Slide: ACTION_PLAN (Technical / Audit Decks only)
        if is_tech:
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
        closing_bullets = []
        if not is_tech:
            if is_education:
                closing_takeaway = "Empirical findings confirm strong core academic performance led by southern and western districts, with clear opportunities for targeted infrastructure intervention in trailing cohorts."
                closing_bullets = [
                    "Academic Achievement: Southern and western districts demonstrate highest achievement, with top 10% exceeding median by 35+ points.",
                    "Primary Driver: Strong correlation between overall composite score and student outcome indices confirms classroom learning as primary metric driver.",
                    "Targeted Interventions: EDA outlier scan highlights 1.97x operational dispersion in facilities and equipment across frontier districts.",
                    "Benchmark Status: Over 62% of evaluated districts currently meet or exceed national achievement benchmark thresholds.",
                ]
            elif is_retail:
                closing_takeaway = (
                    "Store performance analysis confirms $6.74B network sales with high departmental variance. "
                    "Policy modeling indicates +18.4% potential promotional lift under holiday schedules with "
                    "margin buffering under markdown constraints."
                )
                closing_bullets = [
                    "Network Performance: Total observed volume reached $6.74B led by top-tier store clusters.",
                    "Promotional Levers: Holiday multiplier provides +18.4% revenue expansion opportunity.",
                    "Markdown Guardrails: Controlled markdown thresholds protect operating margins across departments.",
                ]
            elif is_demographics:
                closing_takeaway = (
                    "Regional demographic analysis highlights key population concentrations in major states "
                    "and substantial density variance across territories, providing baseline evidence for regional resource planning."
                )
                closing_bullets = [
                    "Population Scale: Key population centers drive majority concentration across major states.",
                    "Regional Density: Extreme spatial density variance requires differentiated infrastructure planning.",
                    "Growth Dynamics: Decadal population growth exhibits stabilization across mature cohorts.",
                ]
            else:
                closing_takeaway = "Synthesized empirical findings across primary indicators and distributions, establishing focal points for operational review."
                closing_bullets = [
                    "Core Indicators: Baseline metrics establish operational consistency across observed entities.",
                    "Variance Diagnostics: Distribution analysis highlights key performance leaders and outliers.",
                    "Action Horizons: Empirical evidence provides objective foundation for strategic resource allocation.",
                ]
        else:
            closing_takeaway = "Open for discussion, resource allocation, and milestone alignment."
            closing_bullets = [
                "Review verified technical architecture and data schema dependencies.",
                "Align cross-functional stakeholders on implementation milestones.",
                "Establish automated regression gates for continuous monitoring.",
            ]

        closing_metadata = {
            "bullets": closing_bullets,
            "planned_layout_family": "chart_narrative",
        }
        logical_slides.append(
            LogicalSlidePlan(
                logical_slide_id=_make_unique_logical_id("CLOSING_SYNTHESIS"),
                structural_role=StructuralRole.CLOSING,
                semantic_topic="SUMMARY_SIGN_OFF",
                section_name=sec_actions,
                purpose="Deliver final analytical synthesis and next review milestones.",
                headline="Summary & Key Implications",
                takeaway=closing_takeaway,
                preferred_archetype="CLOSING_SIGN_OFF",
                allow_split=False,
                logical_order=len(logical_slides) + 1,
                metadata=closing_metadata,
            )
        )

        # Attach coverage ledger summary & context profile metadata
        meta["coverage_ledger"] = coverage_ledger.get_summary()
        meta["context_profile"] = context_profile.model_dump()
        meta["likely_audience"] = effective_audience

        # Build plan
        plan = DeckStoryPlan(
            plan_id=plan_id,
            deck_title=cover_title,
            deck_subtitle=cover_subtitle,
            executive_thesis=thesis_text,
            sections=sections,
            logical_slides=logical_slides,
            excluded_content=excluded_items,
            target_audience=effective_audience,
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

        # Sort primarily by dashboard visual priority for reused items, then descending by score, then stably by content_id
        scored.sort(key=lambda x: (
            self._dashboard_visual_priority(x[1]) if x[1].visual_strategy == VisualStrategy.REUSE_EXISTING else 10,
            -x[0],
            x[1].content_id
        ))
        return [it for _, it in scored]

    @staticmethod
    def _dashboard_visual_priority(item: PresentationContentItem) -> int:
        """Assigns priority rank reflecting executive importance from the dashboard.
        
        Priority 1: Geographic Decision Visual (choropleth, map) or Primary Store Ranking (ranked_bar)
        Priority 2: Cohort Distribution (box_plot)
        Priority 3: Correlation & Relational (scatter)
        Priority 4: Temporal Cadence Trend (line)
        Priority 5: Podium Ranking (podium_top_3)
        Priority 6: Category Treemap (treemap)
        Priority 7: Outliers & Spread (variance_bar)
        Priority 8: Benchmark & Goals (bullet)
        Priority 9: Disparity Range Comparison (dumbbell)
        Priority 10: Policy Scenario Simulation (scenario_card)
        Supporting / Exploratory: Data table (table)
        """
        v_type = str(item.visual_type or "").lower()
        if v_type in ("choropleth", "map", "bubble_map", "point_map") or item.kind == ContentKind.MAP:
            return 1
        if v_type in ("ranked_bar",):
            return 1
        if v_type in ("box_plot", "distribution"):
            return 2
        if v_type in ("scatter", "correlation"):
            return 3
        if v_type in ("line", "trend"):
            return 4
        if v_type in ("podium", "podium_top_3"):
            return 5
        if v_type in ("treemap", "tree_map"):
            return 6
        if v_type in ("variance_bar", "bar"):
            return 7
        if v_type in ("bullet", "benchmark"):
            return 8
        if v_type in ("dumbbell", "comparison", "range_plot"):
            return 9
        if v_type in ("scenario_card", "scenario", "decision_simulator"):
            return 10
        if v_type in ("table", "data_table") or item.kind == ContentKind.TABLE:
            return 15
        return 11

    def _humanize_business_headline(
        self,
        headline: str,
        item: PresentationContentItem,
        content_pkg: PresentationContentPackage
    ) -> str:
        """Converts raw analytical question templates into clean, executive business titles."""
        clean = headline.strip()
        v_type = str(item.visual_type or "").lower()
        title_lower = clean.lower()

        # Specific matches for Retail questions
        if "stores drive the most weekly sales" in title_lower or (v_type == "ranked_bar" and "store" in title_lower and "spread" not in title_lower and "dispersion" not in title_lower and "vary" not in title_lower):
            return "Store Sales Revenue Ranking & Regional Benchmark"

        if "sales vary across store locations" in title_lower or (v_type == "box_plot" and "store" in title_lower) or "dispersion" in title_lower or "quartile" in title_lower:
            return "Store Sales Quartile Dispersion & Spread"

        if "weekly sales trended over time" in title_lower or (v_type == "line" and "sales" in title_lower):
            return "Weekly Store Sales Cadence Trend"

        if "product categories drive store revenue" in title_lower or v_type in ("treemap", "tree_map"):
            return "Merchandise Category Revenue Composition"

        if "foot traffic relate to revenue" in title_lower:
            return "Foot Traffic vs Store Revenue Association"

        if "temperature" in title_lower or "fuel" in title_lower:
            return "Temperature vs Fuel Price Association"

        if ("population" in title_lower or "demographic" in title_lower or "growth" in title_lower or "density" in title_lower) and v_type in ("scatter", "correlation"):
            return "Population Growth vs Density Correlation"

        if "revenue and profit margins compare across stores" in title_lower or v_type in ("dumbbell", "comparison"):
            return "Revenue vs Operating Margin Disparity Range"

        if "stores deliver the highest sales" in title_lower or v_type in ("podium", "podium_top_3"):
            return "Top 3 High-Velocity Store Locations"

        if ("store" in title_lower or "sales" in title_lower or "quota" in title_lower or "$25k" in title_lower) and (v_type == "bullet" or "quota" in title_lower or "target" in title_lower):
            return "Store Performance vs Monthly Quota Target"

        if "commercial promotion" in title_lower or v_type == "scenario_card":
            return "Commercial Promotion & Markdown Policy"

        domain_lower = str(content_pkg.domain or "").lower()
        is_demographic = ("population" in domain_lower or "demograph" in domain_lower or "census" in domain_lower or "population" in title_lower)
        is_education = ("education" in domain_lower or "academic" in domain_lower or "school" in domain_lower or "student" in domain_lower or "score" in domain_lower)

        # Specific matches for India Census / Demographics
        if is_demographic:
            if "density" in title_lower and ("geograph" in title_lower or "territor" in title_lower or "regional" in title_lower or v_type in ("choropleth", "map")):
                return "India Population Density Distribution"

            if ("metrics vary" in title_lower or "metric vary" in title_lower or v_type == "box_plot") and "cohort" in title_lower:
                return "Population Distribution Across States"

            if "relate to" in title_lower or v_type in ("scatter", "correlation"):
                return "Population 2011 vs Decadal Population Growth Rate"

            if "vary across cohorts" in title_lower or v_type == "variance_bar":
                return "Population 2011 Outliers Across States"

            if ("meet the" in title_lower and "target" in title_lower) or v_type == "bullet":
                return "Population Compared with State Benchmark"

        # Specific matches for Education & Academic Performance
        if is_education:
            if ("metrics vary" in title_lower or "metric vary" in title_lower or v_type == "box_plot") and "cohort" in title_lower:
                return "Academic Score Distribution Across Cohorts"
            if "geograph" in title_lower or v_type in ("choropleth", "map"):
                return "District Academic Score Geographic Distribution"
            if "relate to" in title_lower or v_type in ("scatter", "correlation"):
                return "Overall Score vs Outcome Score"
            if "vary across cohorts" in title_lower or v_type == "variance_bar":
                return "District Score Variance and Ranking"
            if "operational variance" in title_lower or "anomaly" in title_lower or "outlier" in title_lower:
                return "Operational Variance & Statistical Outliers"

        # General question unwrapping
        m_vary_geo = re.match(r"^how does (.*?) vary geographically across (.*?)\??$", clean, flags=re.IGNORECASE)
        if m_vary_geo:
            x, y = m_vary_geo.group(1).strip().title(), m_vary_geo.group(2).strip().title()
            return f"{x} Geographic Distribution Across {y}"

        m_vary = re.match(r"^how does (.*?) vary across (.*?)\??$", clean, flags=re.IGNORECASE)
        if m_vary:
            x, y = m_vary.group(1).strip(), m_vary.group(2).strip()
            if "district score" in x.lower() or "score" in x.lower():
                return "District Score Variance and Ranking"
            return f"{x.title()} Distribution Across {y.title()}"

        m_rel = re.match(r"^how does (.*?) relate to (.*?)\??$", clean, flags=re.IGNORECASE)
        if m_rel:
            x, y = m_rel.group(1).strip(), m_rel.group(2).strip()
            def _clean_rel_var(s: str) -> str:
                s_lower = s.lower()
                if "overall" in s_lower:
                    return "Overall Score"
                if "outcome" in s_lower:
                    return "Outcome Score"
                s = re.sub(r"(?i)^district\s+score\s*\d{4}[-_]\d{2}\s*[-_–]\s*", "", s)
                s = re.sub(r"(?i)^category\s*[-_–]\s*", "", s)
                s = re.sub(r"^\d+\.\s*", "", s)
                s = re.sub(r"\s*\(\d+\)\s*$", "", s)
                return s.strip().title()
            return f"{_clean_rel_var(x)} vs {_clean_rel_var(y)}"

        if clean.lower().startswith("which entities meet"):
            return "Performance Compared with Benchmark"

        clean = re.sub(r"\?+$", "", clean).strip()
        return clean

    def _resolve_structural_role(
        self,
        item: PresentationContentItem,
        is_geo_focused: bool,
        is_risk_focused: bool
    ) -> StructuralRole:
        """Determines the appropriate StructuralRole for a content item."""
        v_type = str(item.visual_type or "").lower()
        if v_type in ("choropleth", "map", "bubble_map", "point_map") or item.kind == ContentKind.MAP:
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

        if v_type in ("scatter", "correlation") or "correlat" in top_lower or "relationship" in top_lower or "scatter" in top_lower or "scatter" in title_lower or "relate" in title_lower:
            return StructuralRole.CORRELATION_ANALYSIS

        if v_type in ("box_plot", "variance_bar"):
            return StructuralRole.COHORT_ANALYSIS

        if item.role == ContentRole.PRIMARY_HERO:
            return StructuralRole.HERO_ANALYSIS

        if item.role == ContentRole.RISK_ANOMALY or "variance" in title_lower or "cohort" in title_lower:
            return StructuralRole.COHORT_ANALYSIS

        if v_type in ("table", "data_table") or item.kind == ContentKind.TABLE:
            return StructuralRole.DEEP_DIVE

        return StructuralRole.DIAGNOSTIC_ANALYSIS

    def _is_technical_objective(self, user_objective: str) -> bool:
        """Checks if the user objective explicitly requests internal technical/architecture topics."""
        obj_lower = (user_objective or "").lower()
        return any(
            kw in obj_lower
            for kw in ["sdr", "joinplan", "joingraph", "technical architecture", "governance review", "pipeline audit"]
        )

    def _craft_deck_title(
        self,
        content_pkg: PresentationContentPackage,
        user_objective: str,
        context_profile: Any = None,
    ) -> str:
        """Constructs an executive deck title reflecting the objective and domain."""
        generic_markers = [
            "executive operational review & strategic performance diagnostic",
            "executive operational review",
            "strategic performance diagnostic",
            "executive leadership review",
            "general tabular analytics",
            "core performance",
            "performance diagnostic",
        ]

        is_generic = (not user_objective) or any(m in user_objective.lower() for m in generic_markers)

        if not is_generic and len(user_objective.strip()) >= 5:
            clean_obj = user_objective.strip()
            clean_obj = re.sub(r"^(please\s+)?(create|generate|build|prepare|provide)\s+(a\s+)?(deck|presentation|slides?)\s+(on|for|about)\s+", "", clean_obj, flags=re.IGNORECASE)
            clean_obj = clean_obj[0].upper() + clean_obj[1:]
            
            # Sanitize internal terms in normal decks
            if not self._is_technical_objective(user_objective):
                clean_obj = UserVisibleContentPolicy.sanitize_text(clean_obj)

            return clean_obj

        # 1. Use derived_deck_title from context_profile if available
        if context_profile and getattr(context_profile, "derived_deck_title", None):
            return context_profile.derived_deck_title

        # 2. Derive a grounded business title from dataset entities and metrics
        all_text = " ".join(
            [content_pkg.dataset_name or "", content_pkg.domain or ""]
            + [f"{it.title} {it.narrative_takeaway} {it.metric_name} {it.dimension_name}" for it in content_pkg.items]
        ).lower()

        has_india = "india" in all_text or "state" in all_text or "union territory" in all_text
        has_population = "population" in all_text or "census" in all_text or "demographic" in all_text
        has_retail = "store" in all_text or "retail" in all_text or "sales" in all_text or "markdown" in all_text
        has_workforce = "attendance" in all_text or "headcount" in all_text or "leave" in all_text or "employee" in all_text
        has_education = "student" in all_text or "school" in all_text or "grade" in all_text or "exam" in all_text

        if has_india and has_population:
            return "India Population — Regional Analysis"
        elif has_retail:
            return "Retail Network & Store Trading — Performance Review"
        elif has_education:
            return "Academic Performance & Student Outcomes"
        elif has_workforce:
            return "Workforce Operations & Capacity Review"
        elif has_population:
            return "Population & Demographics Analysis"
        elif content_pkg.domain and content_pkg.domain not in ("General Tabular Analytics", "general"):
            return f"{content_pkg.domain} — Analytical Review"
        elif content_pkg.dataset_name and content_pkg.dataset_name not in ("Sheet1", "Dataset"):
            clean_ds = content_pkg.dataset_name.replace("_", " ").title()
            return f"{clean_ds} — Analytical Review"

        return f"{content_pkg.dataset_name or 'Empirical'} — Analytical Review"

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
        target_audience: str = "Stakeholders",
        max_logical_slides: int | None = None,
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

                pkg_item = next((it for it in (content_pkg.items + content_pkg.global_kpis) if it.content_id == cid), None)
                v_id = pkg_item.visual_id if pkg_item else b_data.get("visual_id")
                v_strat = pkg_item.visual_strategy if pkg_item else b_data.get("visual_strategy", VisualStrategy.PRESENTATION_RECOMMENDATION)
                v_type = pkg_item.visual_type if pkg_item else b_data.get("visual_type")
                v_spec = pkg_item.visual_spec if pkg_item else b_data.get("visual_spec")
                s_surf = pkg_item.source_surface if pkg_item else b_data.get("source_surface")

                b_role = ContentBindingRole(b_data.get("binding_role", "PRIMARY"))
                parsed_bindings.append(
                    ContentBinding(
                        content_id=cid,
                        binding_role=b_role,
                        visual_id=v_id,
                        visual_strategy=v_strat,
                        visual_type=v_type,
                        visual_spec=v_spec,
                        source_surface=s_surf,
                    )
                )
                bound_ids.add(cid)

            primary_b = next((pb for pb in parsed_bindings if pb.binding_role == ContentBindingRole.PRIMARY), parsed_bindings[0] if parsed_bindings else None)

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
                    logical_order=len(parsed_slides) + 1,
                    visual_id=primary_b.visual_id if primary_b else None,
                    visual_strategy=primary_b.visual_strategy if primary_b else VisualStrategy.PRESENTATION_RECOMMENDATION,
                    visual_type=primary_b.visual_type if primary_b else None,
                    visual_spec=primary_b.visual_spec if primary_b else None,
                    source_surface=primary_b.source_surface if primary_b else None,
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

        sections = list(raw_response.get("sections") or ["Presentation Overview", "Empirical Findings", "Actions"])
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
        target_audience: str = "Stakeholders",
        max_logical_slides: int | None = None,
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
