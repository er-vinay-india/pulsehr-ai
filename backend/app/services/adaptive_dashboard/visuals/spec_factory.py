"""Visual Specification Factory (Phase G5.4).

Constructs theme-agnostic semantic VisualSpecs from verified VisualInput.
Guarantees:
- Inherits topic identity, dataset, domain, and entity grain.
- Answers: 'How should this already-understood analytical story be shown?'
- Zero narrative generation (never writes findings or takeaways).
- Zero evidence generation (never mints EVID/CTX/SCEN identifiers).
- Zero raw database/DuckDB access.
- Zero theme styling (no hex colors, dark/light styles).
- Enforces title-axis alignment and grain integrity.
"""
from __future__ import annotations

import re
from typing import Any

from ..formatting.presentation_labels import clean_metric_name, safe_title
from .capability_registry import VisualCapabilityRegistry
from .contracts import VisualInput, VisualSpec
from .integrity import (
    VisualIntegrityError,
    VisualSemanticAlignmentIntegrity,
)


class VisualSpecFactory:
    """Factory creating theme-agnostic, evidence-bound visual specifications."""

    @classmethod
    def create_visual_spec(cls, visual_input: VisualInput) -> VisualSpec:
        """Constructs and validates a semantic VisualSpec."""
        # 1. Determine chart archetype
        if visual_input.chart_type and VisualCapabilityRegistry.is_supported(visual_input.chart_type):
            chart_type = visual_input.chart_type
        else:
            cand_count = len(visual_input.categories) or len(visual_input.values) or len(visual_input.bound_facts)
            chart_type = VisualCapabilityRegistry.select_archetype(
                intent=visual_input.analytical_intent,
                entity_grain=visual_input.entity_grain,
                count=cand_count,
            )

        morphology = VisualCapabilityRegistry.get_morphology(chart_type).value

        # 2. Derive canonical full title and display title
        full_title = visual_input.full_title or visual_input.narrative_title or "Executive Overview"
        display_title = visual_input.display_title or safe_title(full_title)

        # 3. Resolve categories and values from bound facts if not supplied directly
        categories = list(visual_input.categories)
        values = list(visual_input.values)
        evidence_ids = list(visual_input.evidence_ids)

        if not categories and visual_input.bound_facts:
            for bf in visual_input.bound_facts:
                f = bf.fact
                cat_name = getattr(f, "dimension", None) or getattr(f, "entity_name", None) or getattr(f, "subject", "")
                if cat_name and cat_name not in categories:
                    categories.append(str(cat_name))
                if f.value is not None:
                    try:
                        values.append(float(f.value))
                    except (ValueError, TypeError):
                        pass
                eid = getattr(bf, "evidence_id", None) or (
                    bf.evidence.evidence_id if hasattr(bf, "evidence") and hasattr(bf.evidence, "evidence_id") else None
                )
                if eid and eid not in evidence_ids:
                    evidence_ids.append(eid)

        # 4. Resolve axes labels cleanly without underscore leaks
        x_label = clean_metric_name(visual_input.x_label) if visual_input.x_label else ""
        y_label = clean_metric_name(visual_input.y_label) if visual_input.y_label else ""

        # 5. Build VisualSpec
        spec = VisualSpec(
            topic_id=visual_input.topic_id,
            dataset_id=visual_input.dataset_id,
            dataset_version=visual_input.dataset_version,
            domain=visual_input.domain,
            entity_grain=visual_input.entity_grain,
            chart_type=chart_type,
            full_title=full_title,
            display_title=display_title,
            analytical_intent=visual_input.analytical_intent,
            visual_morphology=morphology,
            categories=categories,
            values=values,
            series=visual_input.series,
            x_label=x_label,
            y_label=y_label,
            benchmark=visual_input.benchmark,
            benchmark_label=visual_input.benchmark_label,
            unit=visual_input.unit,
            evidence_ids=evidence_ids,
            layout_hint=visual_input.layout_hint,
            properties=visual_input.tokens,
        )

        # 6. Audit alignment, theme absence, grain, and domain purity
        VisualSemanticAlignmentIntegrity.audit_theme_absence(spec.to_dict(), fail_closed=True)
        VisualSemanticAlignmentIntegrity.audit_domain_purity(spec, visual_input.domain, fail_closed=True)
        VisualSemanticAlignmentIntegrity.audit_grain_consistency(spec, visual_input.entity_grain, fail_closed=True)
        VisualSemanticAlignmentIntegrity.audit_title_axis_alignment(spec, fail_closed=True)

        return spec
