"""PresentationVisualSpec Builder.

Constructs and enriches the authoritative canonical PresentationVisualSpec contract
from a validated VisualSelectionDecision and grounded PresentationContentItem data.
"""
from __future__ import annotations

import logging
from typing import Any
from ..presentation_visual_spec import (
    CHART_CAPABILITY_REGISTRY,
    PresentationAxisSpec,
    PresentationLegendSpec,
    PresentationVisualSeries,
    PresentationVisualSpec,
    VisualFamily,
    compute_visual_semantic_fingerprint,
)
from ..content_models import PresentationContentItem
from .selection_models import DataShapeProfile, VisualSelectionDecision

logger = logging.getLogger(__name__)


class PresentationVisualSpecBuilder:
    """Builds authoritative PresentationVisualSpec instances from grounded evidence and decisions."""

    @classmethod
    def build_spec(
        cls,
        item: PresentationContentItem,
        decision: VisualSelectionDecision,
        profile: DataShapeProfile
    ) -> PresentationVisualSpec:
        """Constructs canonical PresentationVisualSpec enforcing data integrity and capability bounds."""
        family = decision.selected_visual_family
        capability = CHART_CAPABILITY_REGISTRY.get(family)
        native_editable = capability.native_editable if capability else True

        # Extract categories & series from existing visual_spec if available
        raw_vspec = item.visual_spec if isinstance(item.visual_spec, dict) else {}
        categories: list[str] = [str(c) for c in (raw_vspec.get("categories") or [])]
        raw_series = raw_vspec.get("series") or []

        built_series: list[PresentationVisualSeries] = []
        if raw_series and isinstance(raw_series, list):
            for s in raw_series:
                if isinstance(s, dict):
                    s_name = str(s.get("name") or item.metric_name or "Series")
                    vals = s.get("values") if s.get("values") is not None else s.get("data") or []
                    built_series.append(PresentationVisualSeries(name=s_name, values=vals))
        elif raw_vspec.get("values"):
            built_series.append(PresentationVisualSeries(
                name=item.metric_name or "Value",
                values=raw_vspec.get("values") or []
            ))
        elif item.table_data and not built_series:
            # Build categories from first column of table_data if suitable
            first_col_key = list(item.table_data[0].keys())[0] if item.table_data else None
            if first_col_key:
                categories = [str(row.get(first_col_key, "")) for row in item.table_data[:10]]

        # Fallback category labels if empty
        if not categories and built_series and built_series[0].values:
            categories = [f"Item {i+1}" for i in range(len(built_series[0].values))]

        # Stable visual identifier
        visual_id = (
            decision.source_visual_id
            or item.visual_id
            or f"VIS-{item.content_id}"
        )

        topic_id = item.topic_id or item.content_id
        sem_hash = item.semantic_hash
        if not sem_hash:
            try:
                sem_hash = compute_visual_semantic_fingerprint({
                    "morphology": family.value,
                    "analytical_intent": family.value.upper(),
                    "metric": item.metric_name or "",
                    "unit": item.unit or "",
                    "grain": item.grain or "",
                    "dimension": item.dimension_name or "",
                    "categories": categories,
                    "series": [{"name": s.name, "values": s.values} for s in built_series],
                    "data_binding": item.fact_id or item.content_id,
                })
            except Exception:
                sem_hash = f"hash-{visual_id}"

        # Source reference metadata
        src_ref = item.source_data_reference if isinstance(item.source_data_reference, dict) else None

        return PresentationVisualSpec(
            visual_id=visual_id,
            topic_id=topic_id,
            fact_id=item.fact_id,
            evidence_ids=list(item.evidence_ids),
            semantic_hash=sem_hash,
            family=family,
            analytical_intent=family.value.upper(),
            title=item.title,
            subtitle=item.subtitle or "",
            metric=item.metric_name or "",
            unit=item.unit or "",
            grain=item.grain or "",
            dimension=item.dimension_name or "",
            categories=categories,
            series=built_series,
            category_axis=PresentationAxisSpec(title=item.dimension_name or "Category"),
            value_axis=PresentationAxisSpec(title=item.metric_name or "Value", unit=item.unit or ""),
            legend=PresentationLegendSpec(visible=len(built_series) > 1),
            native_editable=native_editable,
            source_visual_type=profile.existing_visual_type or family.value,
            source_visual_family=family.value,
            is_legacy_fallback=False,
            # Governance fields
            visual_variant=decision.selected_visual_variant,
            reuse_strategy=decision.reuse_strategy.value,
            visual_completeness=decision.visual_completeness.value,
            is_scenario=profile.is_scenario,
            table_data=item.table_data,
            reason_codes=decision.reason_codes,
            confidence=decision.confidence,
            source_surface=item.source_surface,
            source_data_reference=src_ref,
        )
