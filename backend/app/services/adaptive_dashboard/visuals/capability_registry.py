"""Visual Capability Registry and Archetype Catalog (Phase G5.4).

Governs supported chart types, their visual families, and morphologies.
Provides deterministic archetype selection answering:
"How should this already-understood analytical story be shown?"
"""
from __future__ import annotations

from .contracts import ChartFamily, VisualMorphology


class VisualCapabilityRegistry:
    """Governed catalog of chart archetypes, families, and visual morphologies."""

    ARCHETYPE_TO_FAMILY: dict[str, ChartFamily] = {
        "podium_top_3": ChartFamily.COMPARISON,
        "podium": ChartFamily.COMPARISON,
        "ranked_bar": ChartFamily.COMPARISON,
        "horizontal_bar": ChartFamily.COMPARISON,
        "lollipop": ChartFamily.COMPARISON,
        "bullet": ChartFamily.COMPARISON,
        "bullet_bar": ChartFamily.COMPARISON,
        "dumbbell": ChartFamily.COMPARISON,
        "variance_bar": ChartFamily.COMPARISON,
        "scatter": ChartFamily.CORRELATION,
        "correlation_scatter": ChartFamily.CORRELATION,
        "bubble": ChartFamily.CORRELATION,
        "100_percent_stacked_bar": ChartFamily.PART_TO_WHOLE,
        "stacked_bar": ChartFamily.PART_TO_WHOLE,
        "donut": ChartFamily.PART_TO_WHOLE,
        "pie": ChartFamily.PART_TO_WHOLE,
        "line": ChartFamily.TEMPORAL,
        "trend_line": ChartFamily.TEMPORAL,
        "area": ChartFamily.TEMPORAL,
        "slope": ChartFamily.TEMPORAL,
        "box_plot": ChartFamily.DISTRIBUTION,
        "boxplot": ChartFamily.DISTRIBUTION,
        "histogram": ChartFamily.DISTRIBUTION,
        "dot_plot": ChartFamily.DISTRIBUTION,
        "heatmap": ChartFamily.SPECIALTY,
        "waterfall": ChartFamily.FLOW,
        "map": ChartFamily.GEOSPATIAL,
        "choropleth": ChartFamily.GEOSPATIAL,
        "bubble_map": ChartFamily.GEOSPATIAL,
        "point_map": ChartFamily.GEOSPATIAL,
    }

    ARCHETYPE_TO_MORPHOLOGY: dict[str, VisualMorphology] = {
        "podium_top_3": VisualMorphology.LENGTH,
        "podium": VisualMorphology.LENGTH,
        "ranked_bar": VisualMorphology.LENGTH,
        "horizontal_bar": VisualMorphology.LENGTH,
        "bullet": VisualMorphology.LENGTH,
        "bullet_bar": VisualMorphology.LENGTH,
        "variance_bar": VisualMorphology.LENGTH,
        "waterfall": VisualMorphology.LENGTH,
        "dot_plot": VisualMorphology.POINT,
        "lollipop": VisualMorphology.POINT,
        "scatter": VisualMorphology.POINT,
        "correlation_scatter": VisualMorphology.POINT,
        "bubble": VisualMorphology.POINT,
        "dumbbell": VisualMorphology.RANGE,
        "box_plot": VisualMorphology.RANGE,
        "boxplot": VisualMorphology.RANGE,
        "histogram": VisualMorphology.RANGE,
        "100_percent_stacked_bar": VisualMorphology.AREA,
        "stacked_bar": VisualMorphology.AREA,
        "donut": VisualMorphology.AREA,
        "pie": VisualMorphology.AREA,
        "line": VisualMorphology.TEMPORAL_PATH,
        "trend_line": VisualMorphology.TEMPORAL_PATH,
        "area": VisualMorphology.TEMPORAL_PATH,
        "slope": VisualMorphology.TEMPORAL_PATH,
        "heatmap": VisualMorphology.MATRIX,
        "map": VisualMorphology.GEOSPATIAL,
        "choropleth": VisualMorphology.GEOSPATIAL,
        "bubble_map": VisualMorphology.GEOSPATIAL,
        "point_map": VisualMorphology.GEOSPATIAL,
    }

    @classmethod
    def get_family(cls, chart_type: str) -> ChartFamily:
        """Returns the governed ChartFamily for a chart archetype."""
        return cls.ARCHETYPE_TO_FAMILY.get(chart_type.lower(), ChartFamily.COMPARISON)

    @classmethod
    def get_morphology(cls, chart_type: str) -> VisualMorphology:
        """Returns the governed VisualMorphology for a chart archetype."""
        return cls.ARCHETYPE_TO_MORPHOLOGY.get(chart_type.lower(), VisualMorphology.LENGTH)

    @classmethod
    def is_supported(cls, chart_type: str) -> bool:
        """Verifies if a chart archetype is governed and supported."""
        return chart_type.lower() in cls.ARCHETYPE_TO_FAMILY

    @classmethod
    def select_archetype(
        cls,
        intent: str,
        entity_grain: str = "aggregate",
        count: int = 1,
        has_temporal: bool = False,
    ) -> str:
        """Deterministically selects the optimal chart archetype from analytical intent and grain.
        
        Answers: 'How should this already-understood analytical story be shown?'
        Never interprets dataset meaning.
        """
        int_norm = (intent or "RANKING").upper()
        grain_norm = (entity_grain or "aggregate").strip().lower()

        if int_norm == "RANKING":
            if grain_norm in ("person", "employee", "staff", "individual") and count <= 3:
                return "podium_top_3"
            return "ranked_bar"

        if int_norm == "TREND":
            return "line"

        if int_norm == "RELATIONSHIP":
            return "scatter"

        if int_norm == "COMPOSITION":
            return "100_percent_stacked_bar"

        if int_norm in ("GEOSPATIAL", "GEO", "MAP"):
            return "choropleth"

        if int_norm == "DISTRIBUTION":
            return "box_plot"

        if int_norm == "ANOMALY":
            return "variance_bar"

        if int_norm == "COMPARISON":
            return "ranked_bar"

        return "ranked_bar"
