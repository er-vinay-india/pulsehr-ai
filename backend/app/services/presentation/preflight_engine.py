"""HighView Presentation Studio — PPT-L3 Presentation Preflight Engine.

Inspects DeckStoryPlan and source PresentationContentPackage BEFORE physical slide expansion.
Evaluates content pressure, structural role capacity, table dimensions, multi-visual density,
and target deck length constraints.

Architectural Principles:
1. Logical topic first, physical page second.
2. Content-type-aware capacity model (tables, visuals, KPIs, narratives).
3. Split-over-shrink: flags when content exceeds capacity so expansion engine splits rather than shrinks.
4. Target length is guidance, not truth. Never drops critical primary content to satisfy a target length.
5. ZERO geometry, coordinates, typography sizing, or rendering logic.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .content_models import ContentKind, PresentationContentItem, PresentationContentPackage
from .manifest_models import (
    ContentDensity,
    DeckLengthPolicy,
    ExpansionReason,
    LogicalTopicPreflightResult,
    PreflightStatus,
    PresentationPreflightResult,
    TargetLengthStatus,
)
from .story_models import DeckStoryPlan, LogicalSlidePlan, StructuralRole

logger = logging.getLogger(__name__)

# Semantic density and capacity thresholds (independent of pixel coordinates)
MAX_SAFE_TABLE_ROWS_PER_SLIDE = 6
MAX_SAFE_INITIATIVES_PER_SLIDE = 3
MAX_SAFE_PRIMARY_VISUALS_PER_SLIDE = 1
MAX_SAFE_TOTAL_VISUALS_PER_SLIDE = 2
MAX_SAFE_CHARACTERS_PER_SLIDE = 450


class PresentationPreflightEngine:
    """Preflight engine evaluating slide capacity and expansion feasibility before physical layout."""

    def __init__(self, max_slides_per_topic: int = 3, max_total_slides: int = 30):
        self.max_slides_per_topic = max_slides_per_topic
        self.max_total_slides = max_total_slides

    def preflight(
        self,
        story_plan: DeckStoryPlan,
        content_pkg: PresentationContentPackage,
        target_slide_count: Optional[int] = None,
        length_policy: DeckLengthPolicy = DeckLengthPolicy.STANDARD,
        metadata: Optional[dict[str, Any]] = None
    ) -> PresentationPreflightResult:
        """Executes preflight evaluation across all logical slides in the story plan.
        
        Args:
            story_plan: Validated DeckStoryPlan from PPT-L2.
            content_pkg: Source PresentationContentPackage from PPT-L1.
            target_slide_count: Optional user-requested deck slide count guidance.
            length_policy: Deck length policy (EXECUTIVE_SHORT, STANDARD, DETAILED, etc.).
            metadata: Optional execution metadata.
            
        Returns:
            PresentationPreflightResult with detailed per-topic capacity assessments.
        """
        all_pkg_items = {it.content_id: it for it in content_pkg.items}
        all_pkg_kpis = {k.content_id: k for k in content_pkg.global_kpis}
        all_items_lookup: dict[str, PresentationContentItem] = {**all_pkg_items, **all_pkg_kpis}

        topic_results: list[LogicalTopicPreflightResult] = []
        warnings: list[str] = []
        errors: list[str] = []
        total_estimated_physical = 0

        for l_slide in story_plan.logical_slides:
            res = self._evaluate_logical_slide(l_slide, all_items_lookup)
            topic_results.append(res)
            total_estimated_physical += res.recommended_physical_slides

            if res.warnings:
                warnings.extend(res.warnings)

        # Check total expansion limit guard
        if total_estimated_physical > self.max_total_slides:
            msg = f"Estimated physical slides ({total_estimated_physical}) exceeds bounded maximum ({self.max_total_slides})"
            errors.append(msg)
            logger.warning(msg)

        # Target length policy evaluation
        target_status, target_warnings = self._evaluate_target_length(
            estimated_count=total_estimated_physical,
            target_count=target_slide_count,
            policy=length_policy
        )
        warnings.extend(target_warnings)

        overall_status = PreflightStatus.FAIL if errors else (
            PreflightStatus.PASS_WITH_WARNINGS if warnings else PreflightStatus.PASS
        )

        return PresentationPreflightResult(
            status=overall_status,
            deck_story_plan_id=story_plan.plan_id,
            logical_topic_results=topic_results,
            estimated_physical_slide_count=total_estimated_physical,
            target_length_guidance=target_slide_count,
            target_length_policy=length_policy,
            target_length_status=target_status,
            warnings=warnings,
            errors=errors,
            metadata=metadata or {}
        )

    def _evaluate_logical_slide(
        self,
        l_slide: LogicalSlidePlan,
        items_lookup: dict[str, PresentationContentItem]
    ) -> LogicalTopicPreflightResult:
        """Evaluates capacity, density, and expansion needs for a single logical slide."""
        # 1. Structural role immutable constraints
        if l_slide.structural_role in (StructuralRole.TITLE, StructuralRole.CLOSING):
            return LogicalTopicPreflightResult(
                logical_slide_id=l_slide.logical_slide_id,
                semantic_topic=l_slide.semantic_topic,
                structural_role=l_slide.structural_role,
                estimated_density=ContentDensity.LOW,
                recommended_physical_slides=1,
                expansion_reason=ExpansionReason.NONE,
                primary_bindings_count=len(l_slide.content_bindings),
                notes=f"{l_slide.structural_role.value} slide is strictly single-page by architectural invariant"
            )

        # 2. Collect bound items
        bound_items: list[PresentationContentItem] = []
        for b in l_slide.content_bindings:
            it = items_lookup.get(b.content_id)
            if it is not None:
                bound_items.append(it)

        primary_count = sum(1 for b in l_slide.content_bindings if b.binding_role.value == "PRIMARY")
        supporting_count = sum(1 for b in l_slide.content_bindings if b.binding_role.value == "SUPPORTING")
        optional_count = sum(1 for b in l_slide.content_bindings if b.binding_role.value == "OPTIONAL")

        # 3. Analyze content kinds
        tables = [it for it in bound_items if it.kind == ContentKind.TABLE]
        visuals = [it for it in bound_items if it.kind in (ContentKind.MAP, ContentKind.CHART)]

        # 4. Table dimension check
        table_split_recommended = False
        table_rows_max = 0
        for tbl in tables:
            r_count = self._estimate_table_rows(tbl)
            if r_count > table_rows_max:
                table_rows_max = r_count

        if table_rows_max > MAX_SAFE_TABLE_ROWS_PER_SLIDE:
            table_split_recommended = True

        # 5. Multi-visual check
        # If there are 2+ major visuals (or a map/chart + a supporting table), split is recommended
        multi_visual_split_recommended = False
        if len(visuals) >= 2 or (len(visuals) >= 1 and len(tables) >= 1):
            multi_visual_split_recommended = True

        # 6. Text volume calculation
        text_volume = len(l_slide.headline or "") + len(l_slide.takeaway or "")
        for it in bound_items:
            text_volume += len(it.title or "") + len(it.narrative_takeaway or "")

        # 7. Density grading
        density = self._grade_density(
            table_rows_max=table_rows_max,
            visuals_count=len(visuals),
            text_volume=text_volume,
            primary_count=primary_count,
            structural_role=l_slide.structural_role
        )

        # 8. Expansion determination (Split-over-Shrink)
        recommended_slides = 1
        reason = ExpansionReason.NONE
        warnings: list[str] = []

        if not l_slide.allow_split:
            # Splitting explicitly prohibited on this logical slide
            recommended_slides = 1
            if density in (ContentDensity.HIGH, ContentDensity.VERY_HIGH):
                warnings.append(
                    f"Slide '{l_slide.logical_slide_id}' has {density.value} density but allow_split is False."
                )
        elif table_split_recommended:
            recommended_slides = min(self.max_slides_per_topic, 2 if table_rows_max <= 12 else 3)
            reason = ExpansionReason.TABLE_LENGTH
        elif multi_visual_split_recommended:
            recommended_slides = min(self.max_slides_per_topic, 2)
            reason = ExpansionReason.MULTI_VISUAL
        elif density == ContentDensity.VERY_HIGH:
            recommended_slides = min(self.max_slides_per_topic, 2)
            reason = ExpansionReason.CONTENT_DENSITY
        elif l_slide.structural_role == StructuralRole.ACTION_PLAN and primary_count > MAX_SAFE_INITIATIVES_PER_SLIDE:
            recommended_slides = min(self.max_slides_per_topic, 2)
            reason = ExpansionReason.NARRATIVE_SEPARATION

        return LogicalTopicPreflightResult(
            logical_slide_id=l_slide.logical_slide_id,
            semantic_topic=l_slide.semantic_topic,
            structural_role=l_slide.structural_role,
            estimated_density=density,
            recommended_physical_slides=recommended_slides,
            expansion_reason=reason,
            primary_bindings_count=primary_count,
            supporting_bindings_count=supporting_count,
            optional_bindings_count=optional_count,
            table_split_recommended=table_split_recommended,
            multi_visual_split_recommended=multi_visual_split_recommended,
            warnings=warnings,
            notes=f"Table rows max: {table_rows_max}, visuals: {len(visuals)}, text volume: {text_volume} chars"
        )

    def _estimate_table_rows(self, item: PresentationContentItem) -> int:
        """Estimates the row count of a table content item from its table_data or visual_spec."""
        if item.table_data and isinstance(item.table_data, list):
            return len(item.table_data)
        if item.visual_spec and isinstance(item.visual_spec, dict):
            t_data = item.visual_spec.get("table_data")
            if isinstance(t_data, dict):
                rows = t_data.get("rows")
                if isinstance(rows, list):
                    return len(rows)
            elif isinstance(t_data, list):
                return len(t_data)
        return 8 if "detail" in (item.title or "").lower() or "breakdown" in (item.title or "").lower() else 5

    def _grade_density(
        self,
        table_rows_max: int,
        visuals_count: int,
        text_volume: int,
        primary_count: int,
        structural_role: StructuralRole
    ) -> ContentDensity:
        """Grades content density based on multifaceted content pressure indicators."""
        if structural_role in (StructuralRole.TITLE, StructuralRole.CLOSING):
            return ContentDensity.LOW

        score = 0
        if table_rows_max > 10:
            score += 3
        elif table_rows_max > 6:
            score += 2

        if visuals_count >= 2:
            score += 3
        elif visuals_count == 1:
            score += 1

        if text_volume > 450:
            score += 3
        elif text_volume > 250:
            score += 1

        if primary_count >= 3:
            score += 2

        if score >= 6:
            return ContentDensity.VERY_HIGH
        elif score >= 4:
            return ContentDensity.HIGH
        elif score >= 2:
            return ContentDensity.MEDIUM
        return ContentDensity.LOW

    def _evaluate_target_length(
        self,
        estimated_count: int,
        target_count: Optional[int],
        policy: DeckLengthPolicy
    ) -> tuple[TargetLengthStatus, list[str]]:
        """Evaluates whether the estimated physical slide count aligns with target guidance."""
        warnings: list[str] = []

        if target_count is None:
            # Policy range evaluation
            if policy == DeckLengthPolicy.EXECUTIVE_SHORT and estimated_count > 8:
                warnings.append(
                    f"Estimated deck length ({estimated_count}) exceeds EXECUTIVE_SHORT policy range (5-7 slides)."
                )
                return TargetLengthStatus.ACCEPTABLE, warnings
            return TargetLengthStatus.UNCONSTRAINED, warnings

        # Explicit target count evaluation
        if target_count < estimated_count:
            # Target is shorter than feasible capacity without dropping primary content
            msg = (
                f"TARGET_LENGTH_CONFLICT: Requested target of {target_count} slides conflicts with minimum "
                f"feasible capacity of {estimated_count} slides. Primary content is protected and will not "
                f"be silently truncated."
            )
            warnings.append(msg)
            logger.info(msg)
            return TargetLengthStatus.TARGET_LENGTH_CONFLICT, warnings

        if target_count == estimated_count:
            return TargetLengthStatus.OPTIMAL, warnings

        # Target is larger than estimated
        if target_count > estimated_count + 4:
            warnings.append(
                f"Target slide count ({target_count}) exceeds natural story capacity ({estimated_count}). "
                f"Sparse story will not generate artificial filler slides."
            )
        return TargetLengthStatus.ACCEPTABLE, warnings
