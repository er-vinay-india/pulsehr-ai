"""HighView Presentation Studio — PPT-L6 PPTX Compiler.

Compiles a validated ResolvedDeckLayout into an editable PowerPoint (.pptx) presentation:
- Standard 16:9 widescreen layout (13.333 in x 7.5 in).
- Exact 1:1 mapping from ResolvedSlideLayout to physical PowerPoint slide.
- Slide creation invariant: len(prs.slides) == len(resolved_deck.slides). (0 physical slides created).
- Zero content dropped: every object layout is compiled onto the slide.
- Assigns shape.name = object_name for Selection Pane navigation.
- PowerPoint internal shape.shape_id remains distinct from semantic object_id.
- Emits an immutable RenderManifest with full audit records and semantic fingerprints.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import pptx
from pptx.util import Inches

from app.core import config
from app.services.presentation.content_models import PresentationContentPackage
from app.services.presentation.layer_zone_models import (
    LayeredDeckStructureSpec,
    SlideObjectSpec,
)
from app.services.presentation.layout_models import ResolvedDeckLayout
from app.services.presentation.render_models import (
    RenderManifest,
    RenderStatus,
    RenderedObjectRecord,
    RenderedSlideRecord,
    compute_render_manifest_fingerprint,
    compute_rendered_slide_fingerprint,
)
from app.services.presentation.renderer_adapters import (
    RendererAdapterRegistry,
)

logger = logging.getLogger(__name__)


class PPTXCompiler:
    """Compiles resolved presentation layouts into native PowerPoint DrawingML files."""

    def __init__(self, registry: Optional[RendererAdapterRegistry] = None) -> None:
        self.registry = registry or RendererAdapterRegistry()

    def compile_deck(
        self,
        resolved_deck: ResolvedDeckLayout,
        deck_structure: LayeredDeckStructureSpec,
        content_package: PresentationContentPackage,
        output_path: Optional[Path] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> tuple[RenderManifest, Path]:
        """Compiles a ResolvedDeckLayout into a PowerPoint file and returns the RenderManifest."""
        prs = pptx.Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)

        slide_w_emu = int(prs.slide_width)
        slide_h_emu = int(prs.slide_height)

        # Build fast lookup maps for content items and object specs
        content_map = {item.content_id: item for item in content_package.items}
        for kpi in content_package.global_kpis:
            content_map[kpi.content_id] = kpi
        structure_slide_map = {s.physical_slide_id: s for s in deck_structure.slides}

        # Resolve theme palette if available in metadata
        theme_input = (metadata or {}).get("theme") or (metadata or {}).get("theme_id")
        if not theme_input and metadata and isinstance(metadata.get("scope"), dict):
            theme_input = metadata["scope"].get("theme") or metadata["scope"].get("theme_id")

        theme_palette: Optional[dict[str, Any]] = None
        if theme_input:
            try:
                from app.services.presentation.theme_engine import ThemeEngine
                theme_palette = ThemeEngine.get_semantic_resolver(theme_input).resolve_asset_palette()
            except Exception as e:
                logger.debug("Could not resolve theme palette in PPTXCompiler: %s", e)

        rendered_slides: list[RenderedSlideRecord] = []
        total_objects = 0
        total_editable = 0
        total_fallbacks = 0

        # Physical slide creation: exactly 1 slide per ResolvedSlideLayout
        for slide_idx, res_slide in enumerate(resolved_deck.slides):
            prs_slide = prs.slides.add_slide(prs.slide_layouts[6])  # Blank layout
            slide_spec = structure_slide_map.get(res_slide.physical_slide_id)
            if not slide_spec:
                # Fallback to matching by index if IDs diverge (safety)
                if slide_idx < len(deck_structure.slides):
                    slide_spec = deck_structure.slides[slide_idx]

            # Fast lookup for slide object specs
            obj_spec_map: dict[str, SlideObjectSpec] = {}
            if slide_spec:
                for zone in slide_spec.zones:
                    for obj in zone.objects:
                        obj_spec_map[obj.object_id] = obj

            rendered_objects: list[RenderedObjectRecord] = []

            for obj_layout in res_slide.object_layouts:
                if theme_palette and "theme_palette" not in obj_layout.metadata:
                    obj_layout.metadata["theme_palette"] = theme_palette
                content_item = content_map.get(obj_layout.content_id)
                obj_spec = obj_spec_map.get(obj_layout.object_id)

                adapter = self.registry.get_adapter(obj_layout.kind, obj_layout.editability)
                shape, obj_record = adapter.render(
                    slide=prs_slide,
                    obj_layout=obj_layout,
                    slide_spec=slide_spec,
                    content_item=content_item,
                    slide_w_emu=slide_w_emu,
                    slide_h_emu=slide_h_emu,
                    obj_spec=obj_spec,
                )

                # Selection Pane contract: shape.name MUST match object_name
                shape.name = obj_layout.object_name
                obj_record.shape_id = int(shape.shape_id)

                rendered_objects.append(obj_record)
                total_objects += 1
                if obj_record.is_native_editable:
                    total_editable += 1
                if obj_record.fallback_applied:
                    total_fallbacks += 1

            # Populate speaker notes with presenter briefing and technical provenance (T31/T33 Lineage)
            try:
                notes_slide = prs_slide.notes_slide
                tf = notes_slide.notes_text_frame
                notes_lines: list[str] = []
                if slide_spec and slide_spec.headline:
                    notes_lines.append(f"Slide: {slide_spec.headline}")

                slide_items = [content_map.get(ol.content_id) for ol in res_slide.object_layouts if ol.content_id in content_map]
                slide_takeaways = [it.narrative_takeaway or it.takeaway for it in slide_items if it and (it.narrative_takeaway or it.takeaway)]
                if slide_takeaways:
                    notes_lines.append("\nKey Takeaways:")
                    for t in dict.fromkeys(slide_takeaways):
                        notes_lines.append(f"- {t}")

                # Technical lineage and audit provenance strictly in speaker notes frame
                prov_topics = [it.visual_id for it in slide_items if it and it.visual_id]
                prov_evids = [eid for it in slide_items if it for eid in (it.evidence_ids or [])]
                prov_facts = [it.fact_id for it in slide_items if it and it.fact_id]

                notes_lines.append("\n--- Technical Lineage & Audit Provenance ---")
                notes_lines.append(f"Physical Slide ID: {res_slide.physical_slide_id}")
                notes_lines.append(f"Logical Slide ID: {res_slide.logical_slide_id}")
                if slide_spec:
                    notes_lines.append(f"Semantic Topic: {slide_spec.semantic_topic}")
                    role_val = slide_spec.structural_role.value if hasattr(slide_spec.structural_role, "value") else str(slide_spec.structural_role)
                    notes_lines.append(f"Structural Role: {role_val}")
                if prov_topics:
                    notes_lines.append(f"Topic IDs: {', '.join(sorted(set(prov_topics)))}")
                if prov_evids:
                    notes_lines.append(f"Evidence IDs: {', '.join(sorted(set(prov_evids)))}")
                if prov_facts:
                    notes_lines.append(f"Fact IDs: {', '.join(sorted(set(prov_facts)))}")

                tf.text = "\n".join(notes_lines)
            except Exception as note_exc:
                logger.warning("Could not set speaker notes on slide %d: %s", slide_idx, note_exc)

            slide_record = RenderedSlideRecord(
                physical_slide_id=res_slide.physical_slide_id,
                logical_slide_id=res_slide.logical_slide_id,
                slide_index=slide_idx,
                objects=rendered_objects,
                render_status=RenderStatus.SUCCESS if not any(o.fallback_applied for o in rendered_objects) else RenderStatus.FALLBACK_APPLIED,
                slide_fingerprint="",
                metadata={
                    "total_objects": len(rendered_objects),
                },
            )
            slide_record.slide_fingerprint = compute_rendered_slide_fingerprint(slide_record)
            rendered_slides.append(slide_record)

        # Invariant check: slide count in presentation == slide count in resolved_deck
        if len(prs.slides) != len(resolved_deck.slides):
            raise ValueError(
                f"Slide count invariant violated: presentation has {len(prs.slides)}, expected {len(resolved_deck.slides)}"
            )

        # Resolve destination path
        if output_path is None:
            out_dir = config.EXPORTS_DIR
            out_dir.mkdir(parents=True, exist_ok=True)
            output_path = out_dir / f"presentation_{resolved_deck.deck_id}.pptx"
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)

        prs.save(str(output_path))
        logger.info("Saved compiled presentation to %s (%d slides, %d objects)", output_path, len(prs.slides), total_objects)

        manifest_id = f"RMAN-{resolved_deck.deck_id}"
        semantic_fingerprint = compute_render_manifest_fingerprint(
            manifest_id=manifest_id,
            deck_id=resolved_deck.deck_id,
            slides=rendered_slides,
        )

        manifest_metadata = dict(metadata or {})
        try:
            from app.services.presentation.typography import TypographyResolver
            manifest_metadata["typography_manifest"] = TypographyResolver.get_current_manifest().model_dump()
        except Exception:
            pass

        manifest = RenderManifest(
            manifest_id=manifest_id,
            deck_id=resolved_deck.deck_id,
            pptx_path=str(output_path),
            slides=rendered_slides,
            total_slides=len(rendered_slides),
            total_objects_rendered=total_objects,
            total_native_editable=total_editable,
            total_fallbacks=total_fallbacks,
            semantic_render_fingerprint=semantic_fingerprint,
            replan_required=False,
            metadata=manifest_metadata,
        )

        return manifest, output_path
