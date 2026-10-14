"""Composition Candidate Builder (Phase G5.6).

Extracts structural, graphical, and legibility metadata from topics and visual specifications.
Guarantees:
- Semantically blind: strictly zero domain or analytical interpretation.
- Evaluates only visual archetypes, content density, and readability envelopes.
"""
from __future__ import annotations

from typing import Any
from .contracts import (
    ARCHETYPE_PROFILES,
    DEFAULT_PROFILE,
    CompositionCandidate,
    ContentDensityMetrics,
    VisualHeightClass,
    VisualLegibilityProfile,
)


def get_legibility_profile(chart_type: str) -> VisualLegibilityProfile:
    """Retrieves governed visual legibility profile for a chart archetype."""
    normalized = (chart_type or "").lower().replace("-", "_").replace(" ", "_")
    return ARCHETYPE_PROFILES.get(normalized, DEFAULT_PROFILE)


get_spatial_profile = get_legibility_profile


def analyze_content_density(topic: Any, profile: VisualLegibilityProfile) -> ContentDensityMetrics:
    """Computes content density, label length metrics, and effective required spans for a card."""
    spec = getattr(topic, "visual_spec", {}) or {}
    if not isinstance(spec, dict):
        spec = {}

    # 1. Extract categories / entity labels
    categories: list[str] = []
    if "categories" in spec and isinstance(spec["categories"], list):
        categories.extend(str(c) for c in spec["categories"])
    elif "x_categories" in spec and isinstance(spec["x_categories"], list):
        categories.extend(str(c) for c in spec["x_categories"])
    elif "podium_categories" in spec and isinstance(spec["podium_categories"], list):
        categories.extend(str(c) for c in spec["podium_categories"])

    # 2. Extract series and marks
    series = spec.get("series", [])
    series_count = len(series) if isinstance(series, list) else 1

    marks_count = len(categories)
    if "scatter_points" in spec and isinstance(spec["scatter_points"], list):
        marks_count = len(spec["scatter_points"])
    elif "heatmap_data" in spec and isinstance(spec["heatmap_data"], list):
        marks_count = len(spec["heatmap_data"])

    longest_label = max((len(c) for c in categories), default=0)
    avg_label = (sum(len(c) for c in categories) / len(categories)) if categories else 0.0

    # 3. Compute label density adjustment
    adjustment = 0
    arch = profile.chart_archetype

    # Horizontal bars and rankings with long labels require at least 8 columns
    if arch in ("ranked_bar", "ranking", "horizontal_bar", "diverging_bar"):
        if longest_label >= 20 or avg_label >= 14:
            adjustment = 1
    elif arch in ("dumbbell", "variance_bar"):
        if longest_label >= 28 or avg_label >= 18:
            adjustment = 1

    # Effective min span bounded by profile envelopes
    eff_min = max(profile.min_readable_span + adjustment, profile.min_readable_span)
    if arch in ("ranked_bar", "ranking", "horizontal_bar"):
        eff_min = min(eff_min, 8)
    else:
        eff_min = min(eff_min, profile.max_useful_span)
    eff_pref = max(profile.preferred_span, eff_min)

    # Normalized density scores
    label_density_score = min(1.0, (longest_label / 40.0) * 0.7 + (avg_label / 25.0) * 0.3)
    info_density_score = min(1.0, (marks_count / 20.0) * 0.6 + (series_count / 4.0) * 0.4)

    return ContentDensityMetrics(
        longest_label_length=longest_label,
        average_label_length=round(avg_label, 1),
        number_of_categories=len(categories),
        series_count=series_count,
        axis_label_count=len(categories),
        marks_count=marks_count,
        label_density_score=round(label_density_score, 3),
        information_density_score=round(info_density_score, 3),
        label_density_adjustment=adjustment,
        effective_min_span=eff_min,
        effective_preferred_span=eff_pref,
    )


class CompositionCandidateBuilder:
    """Builds semantically blind CompositionCandidate instances from topic and visual metadata."""

    @classmethod
    def build_candidate(cls, topic: Any) -> CompositionCandidate:
        tid = str(getattr(topic, "topic_id", "") or id(topic))
        title = str(getattr(topic, "title", ""))
        slot_type = str(getattr(topic, "slot_type", "supporting"))
        intent = str(getattr(topic, "analytical_intent", "general"))
        priority = int(getattr(topic, "priority", 1) or 1)
        importance = float(getattr(topic, "priority_score", 0.5) or 0.5)

        spec = getattr(topic, "visual_spec", {}) or {}
        chart_type = getattr(topic, "recommended_visual", "") or spec.get("chart_type", "ranked_bar")
        profile = get_legibility_profile(chart_type)
        density = analyze_content_density(topic, profile)

        is_hero = (slot_type == "hero")

        return CompositionCandidate(
            topic_id=tid,
            visual_family=chart_type,
            chart_archetype=chart_type,
            morphology=chart_type,
            importance=importance,
            priority=priority,
            readability_constraints={
                "min_readable_span": density.effective_min_span,
                "preferred_span": density.effective_preferred_span,
                "max_useful_span": profile.max_useful_span,
                "min_height": profile.min_height,
            },
            content_density=density,
            preferred_span=density.effective_preferred_span,
            minimum_span=density.effective_min_span,
            maximum_span=profile.max_useful_span,
            height_class=profile.preferred_height.value,
            slot_type=slot_type,
            analytical_intent=intent,
            is_hero=is_hero,
            title=title,
        )
