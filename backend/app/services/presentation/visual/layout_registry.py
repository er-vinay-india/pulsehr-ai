"""Canonical Layout Registry and Legacy Compatibility Layer for Phase 4.

Defines the single source of truth for all presentation slide layouts,
enforcing layout families, specific variants, layout-aware content budgets,
and deterministic mappings for legacy presentation and dashboard layouts.
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class LayoutFamily(str, Enum):
    """The 21 canonical presentation layout families."""
    TITLE_HERO = "TITLE_HERO"
    SECTION_DIVIDER = "SECTION_DIVIDER"
    EXECUTIVE_SUMMARY = "EXECUTIVE_SUMMARY"
    KPI_GRID = "KPI_GRID"
    CHART_INSIGHT = "CHART_INSIGHT"
    CHART_FULL = "CHART_FULL"
    DUAL_CHART = "DUAL_CHART"
    COMPARISON = "COMPARISON"
    TABLE = "TABLE"
    TIMELINE = "TIMELINE"
    PROCESS = "PROCESS"
    ROADMAP = "ROADMAP"
    MATRIX = "MATRIX"
    RISK_MATRIX = "RISK_MATRIX"
    ARCHITECTURE = "ARCHITECTURE"
    IMAGE_STORY = "IMAGE_STORY"
    QUOTE = "QUOTE"
    ACTION_PLAN = "ACTION_PLAN"
    DASHBOARD = "DASHBOARD"
    BEFORE_AFTER = "BEFORE_AFTER"
    SUMMARY_CLOSE = "SUMMARY_CLOSE"


class ContentBudget(BaseModel):
    """Layout-aware capacity budgets preventing spatial overflow on 16:9 canvas."""
    max_headline_lines: int = 2
    max_headline_chars: int = 80
    max_subtitle_chars: int = 140
    max_insights: int = 3
    max_body_words: int = 120
    max_table_rows: int = 8
    max_kpis: int = 4
    chart_area_pct: int = 65


class LayoutDefinition(BaseModel):
    """Complete structural contract for a layout family and its variants."""
    family: LayoutFamily
    default_variant: str
    supported_variants: list[str] = Field(default_factory=list)
    description: str
    content_budget: ContentBudget = Field(default_factory=ContentBudget)
    grid_columns: int = 12


class LayoutSpec(BaseModel):
    """Canonical layout specification governing spatial composition."""
    family: LayoutFamily
    variant: str
    grid_columns: int = 12
    content_budget: ContentBudget = Field(default_factory=ContentBudget)



# Mapping from historical / fragmented slide layout strings to canonical families
LEGACY_LAYOUT_MAP: dict[str, tuple[LayoutFamily, str]] = {
    "title_hero": (LayoutFamily.TITLE_HERO, "hero_centered"),
    "title_cover": (LayoutFamily.TITLE_HERO, "title_cover"),
    "kpi_summary": (LayoutFamily.KPI_GRID, "quad_kpi"),
    "chart_narrative": (LayoutFamily.CHART_INSIGHT, "chart_left_insight_right"),
    "full_chart_takeaway": (LayoutFamily.CHART_FULL, "full_bleed_takeaway_top"),
    "two_charts": (LayoutFamily.DUAL_CHART, "side_by_side"),
    "comparison_split": (LayoutFamily.COMPARISON, "two_column_split"),
    "action_plan": (LayoutFamily.ACTION_PLAN, "initiative_proposals"),
    "table_detail": (LayoutFamily.TABLE, "bounded_financial_table"),
}

# Mapping from dashboard view layouts to canonical families
DASHBOARD_LAYOUT_MAP: dict[str, tuple[LayoutFamily, str]] = {
    "split_kpi_chart": (LayoutFamily.CHART_INSIGHT, "split_kpi_chart"),
    "chart_focus": (LayoutFamily.CHART_FULL, "chart_focus"),
    "callout_alert": (LayoutFamily.EXECUTIVE_SUMMARY, "callout_alert"),
    "audit_quad": (LayoutFamily.MATRIX, "audit_quad"),
    "roadmap_quad": (LayoutFamily.ROADMAP, "roadmap_quad"),
}


class LayoutRegistry:
    """Canonical registry governing all layout families, variants, and content budgets."""

    def __init__(self):
        self._registry: dict[LayoutFamily, LayoutDefinition] = {}
        self._initialize_canonical_registry()

    def _initialize_canonical_registry(self):
        # 1. TITLE_HERO
        self.register(LayoutDefinition(
            family=LayoutFamily.TITLE_HERO,
            default_variant="hero_centered",
            supported_variants=["hero_centered", "title_cover", "hero_left_aligned"],
            description="Hero presentation title, domain badge, and primary thesis",
            content_budget=ContentBudget(max_headline_lines=3, max_headline_chars=90, max_body_words=50, chart_area_pct=0)
        ))

        # 2. SECTION_DIVIDER
        self.register(LayoutDefinition(
            family=LayoutFamily.SECTION_DIVIDER,
            default_variant="minimal_centered",
            supported_variants=["minimal_centered", "split_color", "big_number_stage"],
            description="Chapter and narrative milestone divider",
            content_budget=ContentBudget(max_headline_lines=2, max_body_words=40, chart_area_pct=0)
        ))

        # 3. EXECUTIVE_SUMMARY
        self.register(LayoutDefinition(
            family=LayoutFamily.EXECUTIVE_SUMMARY,
            default_variant="cards_and_callout",
            supported_variants=["cards_and_callout", "callout_alert", "three_takeaways"],
            description="High-density executive takeaway with primary conclusions",
            content_budget=ContentBudget(max_insights=4, max_body_words=160, max_kpis=3, chart_area_pct=30)
        ))

        # 4. KPI_GRID
        self.register(LayoutDefinition(
            family=LayoutFamily.KPI_GRID,
            default_variant="quad_kpi",
            supported_variants=["quad_kpi", "three_col_kpi", "hero_kpi_plus_duo"],
            description="Metric dashboard displaying 3-6 critical quantitative anchors",
            content_budget=ContentBudget(max_kpis=6, max_body_words=80, chart_area_pct=0)
        ))

        # 5. CHART_INSIGHT
        self.register(LayoutDefinition(
            family=LayoutFamily.CHART_INSIGHT,
            default_variant="chart_left_insight_right",
            supported_variants=[
                "chart_left_insight_right",
                "insight_left_chart_right",
                "chart_top_takeaway_bottom",
                "split_kpi_chart"
            ],
            description="Primary data visualization paired with structured executive takeaways",
            content_budget=ContentBudget(chart_area_pct=65, max_insights=3, max_body_words=110)
        ))

        # 6. CHART_FULL
        self.register(LayoutDefinition(
            family=LayoutFamily.CHART_FULL,
            default_variant="full_bleed_takeaway_top",
            supported_variants=["full_bleed_takeaway_top", "chart_focus", "hero_visual"],
            description="Expansive full-slide visualization with prominent banner takeaway",
            content_budget=ContentBudget(chart_area_pct=85, max_insights=1, max_body_words=45)
        ))

        # 7. DUAL_CHART
        self.register(LayoutDefinition(
            family=LayoutFamily.DUAL_CHART,
            default_variant="side_by_side",
            supported_variants=["side_by_side", "stacked_pair", "macro_micro_split"],
            description="Two complementary visualizations showing correlated trends or distributions",
            content_budget=ContentBudget(chart_area_pct=75, max_insights=2, max_body_words=80)
        ))

        # 8. COMPARISON
        self.register(LayoutDefinition(
            family=LayoutFamily.COMPARISON,
            default_variant="two_column_split",
            supported_variants=["two_column_split", "three_column_cards", "leader_vs_laggard"],
            description="Comparative analysis between cohorts, periods, or benchmarks",
            content_budget=ContentBudget(chart_area_pct=40, max_insights=4, max_body_words=140)
        ))

        # 9. TABLE
        self.register(LayoutDefinition(
            family=LayoutFamily.TABLE,
            default_variant="bounded_financial_table",
            supported_variants=["bounded_financial_table", "raci_matrix", "evidence_ledger_table"],
            description="Structured tabular dataset with highlighted critical values",
            content_budget=ContentBudget(max_table_rows=8, max_body_words=60, chart_area_pct=70)
        ))

        # 10. TIMELINE
        self.register(LayoutDefinition(
            family=LayoutFamily.TIMELINE,
            default_variant="horizontal_milestones",
            supported_variants=["horizontal_milestones", "vertical_stepper", "phased_horizon"],
            description="Chronological milestones and retrospective sequence",
            content_budget=ContentBudget(max_insights=5, max_body_words=120, chart_area_pct=50)
        ))

        # 11. PROCESS
        self.register(LayoutDefinition(
            family=LayoutFamily.PROCESS,
            default_variant="linear_chevron_flow",
            supported_variants=["linear_chevron_flow", "cyclical_loop", "funnel_stages"],
            description="Standard operating procedure and workflow progression",
            content_budget=ContentBudget(max_insights=5, max_body_words=110, chart_area_pct=60)
        ))

        # 12. ROADMAP
        self.register(LayoutDefinition(
            family=LayoutFamily.ROADMAP,
            default_variant="quarterly_swimlanes",
            supported_variants=["quarterly_swimlanes", "roadmap_quad", "now_next_later"],
            description="Strategic execution roadmap across time horizons and workstreams",
            content_budget=ContentBudget(max_insights=4, max_body_words=130, chart_area_pct=60)
        ))

        # 13. MATRIX
        self.register(LayoutDefinition(
            family=LayoutFamily.MATRIX,
            default_variant="talent_9box",
            supported_variants=["talent_9box", "two_by_two", "priority_matrix", "audit_quad"],
            description="Two-axis spatial matrix categorizing entities by orthogonal dimensions",
            content_budget=ContentBudget(chart_area_pct=65, max_insights=3, max_body_words=100)
        ))

        # 14. RISK_MATRIX
        self.register(LayoutDefinition(
            family=LayoutFamily.RISK_MATRIX,
            default_variant="impact_vs_likelihood",
            supported_variants=["impact_vs_likelihood", "burnout_strain_grid"],
            description="Risk categorization matrix mapping severity against probability",
            content_budget=ContentBudget(chart_area_pct=65, max_insights=3, max_body_words=100)
        ))

        # 15. ARCHITECTURE
        self.register(LayoutDefinition(
            family=LayoutFamily.ARCHITECTURE,
            default_variant="layered_system_stack",
            supported_variants=["layered_system_stack", "component_diagram", "hub_and_spoke"],
            description="System topology, integration layers, and infrastructure mapping",
            content_budget=ContentBudget(chart_area_pct=70, max_body_words=90)
        ))

        # 16. IMAGE_STORY
        self.register(LayoutDefinition(
            family=LayoutFamily.IMAGE_STORY,
            default_variant="hero_image_narrative_side",
            supported_variants=["hero_image_narrative_side", "gallery_trio"],
            description="High-impact photographic or illustrative focal point",
            content_budget=ContentBudget(chart_area_pct=50, max_body_words=100)
        ))

        # 17. QUOTE
        self.register(LayoutDefinition(
            family=LayoutFamily.QUOTE,
            default_variant="executive_testimony",
            supported_variants=["executive_testimony", "stakeholder_pull_quote"],
            description="Authoritative quotation, customer voice, or regulatory citation",
            content_budget=ContentBudget(max_body_words=80, chart_area_pct=0)
        ))

        # 18. ACTION_PLAN
        self.register(LayoutDefinition(
            family=LayoutFamily.ACTION_PLAN,
            default_variant="initiative_proposals",
            supported_variants=["initiative_proposals", "owner_matrix", "okr_grid"],
            description="Concrete strategic commitments, owners, milestones, and success metrics",
            content_budget=ContentBudget(max_insights=3, max_body_words=150, chart_area_pct=30)
        ))

        # 19. DASHBOARD
        self.register(LayoutDefinition(
            family=LayoutFamily.DASHBOARD,
            default_variant="multi_widget_quad",
            supported_variants=["multi_widget_quad", "cockpit_summary"],
            description="Compact multi-widget analytical control panel",
            content_budget=ContentBudget(max_kpis=4, chart_area_pct=60, max_body_words=90)
        ))

        # 20. BEFORE_AFTER
        self.register(LayoutDefinition(
            family=LayoutFamily.BEFORE_AFTER,
            default_variant="split_transformation",
            supported_variants=["split_transformation", "baseline_vs_target"],
            description="Direct comparison between prior state and target operational state",
            content_budget=ContentBudget(chart_area_pct=50, max_insights=4, max_body_words=120)
        ))

        # 21. SUMMARY_CLOSE
        self.register(LayoutDefinition(
            family=LayoutFamily.SUMMARY_CLOSE,
            default_variant="next_steps_and_qa",
            supported_variants=["next_steps_and_qa", "closing_commitments"],
            description="Concluding discussion prompts, Q&A framing, and decisive next steps",
            content_budget=ContentBudget(max_insights=3, max_body_words=80, chart_area_pct=0)
        ))

    def register(self, definition: LayoutDefinition):
        self._registry[definition.family] = definition

    def get_layout(self, family: LayoutFamily | str) -> LayoutDefinition | None:
        if isinstance(family, str):
            try:
                family = LayoutFamily(family.upper())
            except ValueError:
                # Try legacy mapping
                resolved = self.map_legacy_layout(family)
                return self._registry.get(resolved[0])
        return self._registry.get(family)

    def get_all_families(self) -> list[LayoutFamily]:
        return list(self._registry.keys())

    def map_legacy_layout(self, raw_layout: str) -> tuple[LayoutFamily, str]:
        """Resolves any legacy slide layout or dashboard identifier into a canonical family and variant."""
        clean = (raw_layout or "").strip().lower()
        if clean in LEGACY_LAYOUT_MAP:
            return LEGACY_LAYOUT_MAP[clean]
        if clean in DASHBOARD_LAYOUT_MAP:
            return DASHBOARD_LAYOUT_MAP[clean]

        # Check if already a canonical family name
        for fam in LayoutFamily:
            if fam.value.lower() == clean:
                defn = self._registry.get(fam)
                return (fam, defn.default_variant if defn else "standard")

        # Default fallback
        return (LayoutFamily.CHART_INSIGHT, "chart_left_insight_right")

    @classmethod
    def get_canonical_layout(cls, raw_layout: str | LayoutFamily) -> LayoutSpec:
        """Returns a canonical LayoutSpec for any layout string or family."""
        if isinstance(raw_layout, LayoutFamily):
            fam = raw_layout
            defn = layout_registry._registry.get(fam)
            variant = defn.default_variant if defn else "standard"
            budget = defn.content_budget if defn else ContentBudget()
            return LayoutSpec(family=fam, variant=variant, content_budget=budget)
        fam, variant = layout_registry.map_legacy_layout(str(raw_layout))
        defn = layout_registry._registry.get(fam)
        budget = defn.content_budget if defn else ContentBudget()
        return LayoutSpec(family=fam, variant=variant, content_budget=budget)

    @classmethod
    def get_budget(cls, family: LayoutFamily | str) -> ContentBudget:
        """Retrieves layout-aware content budget."""
        defn = layout_registry.get_layout(family)
        return defn.content_budget if defn else ContentBudget()


# Global canonical layout registry instance
layout_registry = LayoutRegistry()
