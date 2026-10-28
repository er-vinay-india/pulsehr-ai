"""Visual Selection Intelligence Service.

Coordinates data profiling, candidate generation, deterministic selection,
and canonical PresentationVisualSpec synthesis between ContentHub and StoryPlanner.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from ..content_models import ContentKind, PresentationContentItem, PresentationContentPackage
from ..presentation_visual_spec import PresentationVisualSpec, VisualFamily
from .candidate_generator import VisualCandidateGenerator
from .normalization import normalize_to_visual_family
from .selection_models import DataShapeProfile, VisualSelectionDecision
from .selection_provider import DeterministicVisualSelectionProvider
from .spec_builder import PresentationVisualSpecBuilder

logger = logging.getLogger(__name__)


class VisualSelectionIntelligence:
    """The central Visual Selection Intelligence engine for the active layered pipeline."""

    def __init__(
        self,
        candidate_generator: Optional[VisualCandidateGenerator] = None,
        selection_provider: Optional[DeterministicVisualSelectionProvider] = None,
        spec_builder: Optional[PresentationVisualSpecBuilder] = None,
    ) -> None:
        self.candidate_generator = candidate_generator or VisualCandidateGenerator()
        self.selection_provider = selection_provider or DeterministicVisualSelectionProvider()
        self.spec_builder = spec_builder or PresentationVisualSpecBuilder()

    def profile_content_item(self, item: PresentationContentItem) -> DataShapeProfile:
        """Deterministically inspects an empirical content item to construct a DataShapeProfile."""
        text_corpus = f"{item.title} {item.subtitle or ''} {item.takeaway or ''} {item.topic_category}".lower()

        # 1. Scenario detection
        is_scenario = (
            str(item.visual_id or "").upper().startswith("SCEN")
            or "scenario" in text_corpus
            or "counterfactual" in text_corpus
            or "policy simulation" in text_corpus
        )

        # 2. Geographic detection
        is_geographic = (
            any(k in text_corpus for k in ["district", "state", "region", "territory", "province", "country", "geographic", "geo ", "heatmap", "choropleth"])
            or item.kind == ContentKind.MAP
            or str(item.visual_type or "").lower() in ("map", "choropleth", "bubble_map", "point_map")
        )

        # 3. Temporal detection
        temporal_markers = ["week", "month", "quarter", "year", "trend", "timeseries", "trajectory", "historical", "202", "daily", "timeline"]
        is_temporal = any(k in text_corpus for k in temporal_markers)

        # 4. Distribution / Dispersion detection
        dist_markers = ["dispersion", "quartile", "outlier", "distribution", "skew", "variance", "spread", "box_plot", "boxplot"]
        is_distribution = any(k in text_corpus for k in dist_markers)

        # 5. Ranking detection
        rank_markers = ["rank", "top ", "bottom ", "leading", "lagging", "highest", "lowest", "standing"]
        is_ranked = any(k in text_corpus for k in rank_markers)

        # 6. Tabular / Record detail detection
        is_record_detail = (
            item.kind == ContentKind.TABLE
            or bool(item.table_data and len(item.table_data) > 0)
            or "matrix" in text_corpus
            or "detail" in text_corpus
        )

        # 7. Dimension and metric counts
        raw_vspec = item.visual_spec if isinstance(item.visual_spec, dict) else {}
        categories = raw_vspec.get("categories") or []
        series = raw_vspec.get("series") or []
        cat_count = len(categories)

        col_count = len(item.table_data[0].keys()) if item.table_data and len(item.table_data) > 0 else 0
        row_count = len(item.table_data) if item.table_data else cat_count

        max_lbl_len = max([len(str(c)) for c in categories]) if categories else 0

        # Existing visual asset
        has_existing = bool(
            item.visual_spec
            or (item.source_surface in ("dashboard", "data_explorer") and item.visual_id and not item.visual_id.startswith("tmp"))
        )

        # Metric & continuous dimension estimation
        metric_count = len(series) if series else (1 if item.metric_value or item.metric_name else 0)
        continuous_dims = 2 if ("scatter" in text_corpus or "correlation" in text_corpus or (series and len(series) >= 2 and not is_temporal)) else 1

        has_bm = bool(raw_vspec.get("benchmark") or raw_vspec.get("reference_line") or "benchmark" in text_corpus or "target" in text_corpus)
        has_ba = "before" in text_corpus and "after" in text_corpus
        has_at = "actual" in text_corpus and "target" in text_corpus

        return DataShapeProfile(
            content_id=item.content_id,
            is_temporal=is_temporal,
            is_geographic=is_geographic,
            is_scenario=is_scenario,
            is_ranked=is_ranked,
            is_distribution=is_distribution,
            is_record_detail=is_record_detail,
            categorical_dimension_count=1 if cat_count > 0 else 0,
            continuous_dimension_count=continuous_dims,
            metric_count=max(metric_count, 1),
            category_count=cat_count,
            row_count=row_count,
            column_count=col_count,
            has_benchmark=has_bm,
            has_before_after=has_ba,
            has_actual_target=has_at,
            has_existing_visual=has_existing,
            existing_visual_type=item.visual_type,
            existing_visual_id=item.visual_id,
            source_surface=item.source_surface,
            max_label_length=max_lbl_len,
        )

    def select_visual_for_item(
        self,
        item: PresentationContentItem
    ) -> tuple[PresentationVisualSpec, VisualSelectionDecision]:
        """Runs the complete Visual Selection Intelligence pipeline for a single content item."""
        profile = self.profile_content_item(item)
        candidates = self.candidate_generator.generate_candidates(profile, analytical_intent=item.topic_category)
        decision = self.selection_provider.select_visual(
            content_id=item.content_id,
            profile=profile,
            candidates=candidates,
            analytical_intent=item.topic_category,
        )
        spec = self.spec_builder.build_spec(item=item, decision=decision, profile=profile)
        return spec, decision

    def process_content_package(
        self,
        pkg: PresentationContentPackage
    ) -> PresentationContentPackage:
        """Processes an entire PresentationContentPackage, enriching all items with canonical PresentationVisualSpecs."""
        enriched_items: list[PresentationContentItem] = []
        for it in pkg.items:
            spec, decision = self.select_visual_for_item(it)
            it.presentation_visual_spec = spec
            it.visual_type = spec.family.value
            it.visual_strategy = decision.reuse_strategy
            it.visual_completeness = decision.visual_completeness
            # Keep dictionary representation synchronized for downstream backwards compatibility
            if not it.visual_spec:
                it.visual_spec = {
                    "chart_type": spec.family.value,
                    "title": spec.title,
                    "categories": spec.categories,
                    "series": [{"name": s.name, "values": s.values} for s in spec.series],
                }
            enriched_items.append(it)

        enriched_kpis: list[PresentationContentItem] = []
        for kpi in pkg.global_kpis:
            spec, decision = self.select_visual_for_item(kpi)
            kpi.presentation_visual_spec = spec
            kpi.visual_type = spec.family.value
            kpi.visual_strategy = decision.reuse_strategy
            kpi.visual_completeness = decision.visual_completeness
            enriched_kpis.append(kpi)

        pkg.items = enriched_items
        pkg.global_kpis = enriched_kpis
        logger.info(
            "VisualSelectionIntelligence processed package with %d items and %d global KPIs into canonical PresentationVisualSpecs.",
            len(pkg.items),
            len(pkg.global_kpis)
        )
        return pkg
