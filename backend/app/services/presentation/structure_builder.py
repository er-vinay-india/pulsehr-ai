"""HighView Presentation Studio — PPT-L4 Layered Slide Structure Builder.

Implements the deterministic LayeredSlideStructureBuilder that transforms
a validated PhysicalSlideManifest (PPT-L3) into a LayeredDeckStructureSpec (PPT-L4).

Architectural Invariants:
1. PPT-L4 owns structure and identity, NOT position or geometry.
2. ZERO layout coordinates (x/y/w/h, left_pct, etc.), ZERO EMUs, ZERO font sizes, ZERO colors.
3. SlideExpansionEngine is the SOLE owner of physical slide creation (physical slide creations = 0).
4. Content allocated to a physical slide stays strictly on that slide (zero cross-slide movement).
5. If structure cannot accommodate content, returns STRUCTURE_REPLAN_REQUIRED rather than
   silently moving or creating slides.
6. Deterministic, stable object IDs that survive regeneration, layout, and theme changes.
7. Truthful editability policy: raster/composite maps are NEVER marked NATIVE_EDITABLE.
8. Zero governance leakage in business presentations; accurate preservation in technical decks.
9. AI structure calls = 0 (fully deterministic).
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from .content_models import ContentKind, PresentationContentItem, PresentationContentPackage
from .story_models import ContentBinding, ContentBindingRole
from .layer_zone_models import (
    CoordinateSpace,
    EditabilityPolicy,
    FrameInheritancePolicy,
    LayeredDeckStructureSpec,
    LayeredSlideSpec,
    LayeredSlideStructureValidator,
    LayerRole,
    SafeAreaSpec,
    SlideObjectSpec,
    StructureStatus,
    StructureValidationError,
    ZoneSpec,
    ZoneType,
)
from .manifest_models import PhysicalSlideInstance, PhysicalSlideManifest

logger = logging.getLogger(__name__)


class LayeredSlideStructureBuilder:
    """Constructs layered zone specifications and stable object identities from a PhysicalSlideManifest."""

    MAX_VISUALS_PER_SLIDE = 2
    MAX_TABLE_ROWS_PER_SLIDE = 25

    def __init__(self) -> None:
        self._used_object_names: set[str] = set()

    def _build_selection_pane_name(
        self,
        physical_slide_id: str,
        descriptor: str,
        discriminator: str = "",
    ) -> str:
        """Constructs a deterministic, unique PowerPoint Selection-Pane friendly object name.
        
        Format: HV_{CLEAN_SLIDE_ID}_{CLEAN_DESCRIPTOR}[_{CLEAN_DISCRIMINATOR}]
        Strictly unique across the entire deck and distinct from HighView semantic object_id.
        """
        clean_slide = re.sub(r"[^A-Za-z0-9]+", "_", physical_slide_id).strip("_").upper()
        clean_desc = re.sub(r"[^A-Za-z0-9]+", "_", descriptor).strip("_").upper()
        parts = ["HV", clean_slide, clean_desc]
        if discriminator:
            clean_disc = re.sub(r"[^A-Za-z0-9]+", "_", discriminator).strip("_").upper()
            if clean_disc:
                parts.append(clean_disc)

        base_name = "_".join(parts)
        candidate = base_name
        counter = 2
        while candidate in self._used_object_names:
            candidate = f"{base_name}_{counter:02d}"
            counter += 1

        self._used_object_names.add(candidate)
        return candidate

    def build_structure(
        self,
        manifest: PhysicalSlideManifest,
        content_pkg: PresentationContentPackage,
        is_technical_deck: bool = False,
        metadata: Optional[dict[str, Any]] = None,
    ) -> LayeredDeckStructureSpec:
        """Transforms a PhysicalSlideManifest into an authoritative LayeredDeckStructureSpec.
        
        Args:
            manifest: The validated PhysicalSlideManifest from PPT-L3.
            content_pkg: The source PresentationContentPackage from PPT-L1.
            is_technical_deck: If True, preserves governance and technical tokens verbatim.
            metadata: Optional execution metadata.
            
        Returns:
            LayeredDeckStructureSpec adhering to all PPT-L4 contracts.
        """
        self._used_object_names = set()
        item_lookup: dict[str, PresentationContentItem] = {
            item.content_id: item for item in content_pkg.items
        }
        for kpi in content_pkg.global_kpis:
            item_lookup[kpi.content_id] = kpi

        deck_slides: list[LayeredSlideSpec] = []
        global_registry: dict[str, SlideObjectSpec] = {}
        deck_replan_required = False
        deck_replan_reasons: list[str] = []

        for m_slide in manifest.slides:
            slide_spec, slide_objects, replan_reason = self._build_slide_spec(
                m_slide=m_slide,
                item_lookup=item_lookup,
                is_technical_deck=is_technical_deck,
            )

            if replan_reason:
                deck_replan_required = True
                deck_replan_reasons.append(replan_reason)

            deck_slides.append(slide_spec)
            for obj in slide_objects:
                global_registry[obj.object_id] = obj

        deck_structure = LayeredDeckStructureSpec(
            manifest_id=manifest.manifest_id,
            manifest_version=manifest.manifest_version,
            slides=deck_slides,
            object_registry=global_registry,
            replan_required=deck_replan_required,
            replan_reasons=deck_replan_reasons,
            metadata=metadata or {},
        )

        deck_structure.structure_fingerprint = deck_structure.compute_structure_fingerprint()

        # Validate structure invariants unless a replan is explicitly signaled
        if not deck_structure.replan_required:
            LayeredSlideStructureValidator.validate(
                deck_structure=deck_structure,
                manifest=manifest,
                content_pkg=content_pkg,
                is_technical_deck=is_technical_deck,
            )

        logger.info(
            "LayeredSlideStructureBuilder built structure for manifest %s: %d slides, %d objects, replan_required=%s",
            manifest.manifest_id,
            len(deck_structure.slides),
            len(deck_structure.object_registry),
            deck_structure.replan_required,
        )

        return deck_structure

    def _build_slide_spec(
        self,
        m_slide: PhysicalSlideInstance,
        item_lookup: dict[str, PresentationContentItem],
        is_technical_deck: bool,
    ) -> tuple[LayeredSlideSpec, list[SlideObjectSpec], Optional[str]]:
        """Assembles zones and slide objects for a single physical slide."""
        clean_headline = self._cleanse_text(m_slide.headline, is_technical_deck)
        zones: list[ZoneSpec] = []
        all_slide_objects: list[SlideObjectSpec] = []
        replan_reason: Optional[str] = None

        # 1. Title Zone (Master chrome / Body title)
        title_obj = SlideObjectSpec(
            object_id=f"{m_slide.physical_slide_id}__OBJ_TITLE",
            object_name=self._build_selection_pane_name(m_slide.physical_slide_id, "TITLE"),
            name="Slide Title",
            content_id=f"{m_slide.physical_slide_id}__TITLE",
            binding_role=ContentBindingRole.PRIMARY,
            kind=ContentKind.NARRATIVE_INSIGHT,
            semantic_topic=m_slide.semantic_topic,
            editability=EditabilityPolicy.NATIVE_REQUIRED,
            inheritance_policy=FrameInheritancePolicy.PER_SLIDE,
            headline=clean_headline,
            narrative_text="",
            data_summary={},
            source_traceability={"physical_slide_id": m_slide.physical_slide_id},
        )
        title_zone = ZoneSpec(
            zone_id=f"{m_slide.physical_slide_id}__ZONE_TITLE",
            zone_type=ZoneType.TITLE,
            layer_role=LayerRole.BODY,
            coordinate_space=CoordinateSpace.BODY_SPACE,
            inheritance_policy=FrameInheritancePolicy.PER_SLIDE,
            objects=[title_obj],
            allowed_kinds=[ContentKind.NARRATIVE_INSIGHT],
            z_index=1,
        )
        zones.append(title_zone)
        all_slide_objects.append(title_obj)

        # 2. Categorize content bindings on this physical slide
        visual_bindings: list[tuple[ContentBinding, PresentationContentItem]] = []
        table_bindings: list[tuple[ContentBinding, PresentationContentItem]] = []
        kpi_bindings: list[tuple[ContentBinding, PresentationContentItem]] = []
        narrative_bindings: list[tuple[ContentBinding, PresentationContentItem]] = []

        for binding in m_slide.content_bindings:
            pkg_item = item_lookup.get(binding.content_id)
            if not pkg_item:
                # Synthesize fallback item if item was not found in package
                pkg_item = PresentationContentItem(
                    content_id=binding.content_id,
                    kind=getattr(binding, "kind_hint", None) or ContentKind.NARRATIVE_INSIGHT,
                    role=ContentRole.KEY_FINDING,
                    topic_category=m_slide.semantic_topic,
                    title=binding.content_id,
                    narrative_takeaway=binding.content_id,
                )

            if pkg_item.kind in (ContentKind.CHART, ContentKind.MAP):
                visual_bindings.append((binding, pkg_item))
            elif pkg_item.kind == ContentKind.TABLE:
                table_bindings.append((binding, pkg_item))
            elif pkg_item.kind == ContentKind.KPI_METRIC:
                kpi_bindings.append((binding, pkg_item))
            else:
                narrative_bindings.append((binding, pkg_item))

        # Check physical capacity feasibility
        if len(visual_bindings) > self.MAX_VISUALS_PER_SLIDE:
            replan_reason = (
                f"Slide '{m_slide.physical_slide_id}' has {len(visual_bindings)} visual items, "
                f"exceeding maximum zone capacity of {self.MAX_VISUALS_PER_SLIDE}."
            )
        for _, tbl in table_bindings:
            if tbl.table_data and len(tbl.table_data) > self.MAX_TABLE_ROWS_PER_SLIDE:
                replan_reason = (
                    f"Slide '{m_slide.physical_slide_id}' has data table '{tbl.content_id}' with "
                    f"{len(tbl.table_data)} rows, exceeding maximum readable row capacity ({self.MAX_TABLE_ROWS_PER_SLIDE})."
                )

        # 3. Build Visual Zones (PRIMARY_VISUAL, SECONDARY_VISUAL)
        for idx, (b, item) in enumerate(visual_bindings):
            obj = self._create_slide_object(
                m_slide=m_slide,
                binding=b,
                item=item,
                is_technical_deck=is_technical_deck,
            )
            zone_type = ZoneType.PRIMARY_VISUAL if idx == 0 else ZoneType.SECONDARY_VISUAL
            zone_id = f"{m_slide.physical_slide_id}__ZONE_{zone_type.value}"
            v_zone = ZoneSpec(
                zone_id=zone_id,
                zone_type=zone_type,
                layer_role=LayerRole.BODY,
                coordinate_space=CoordinateSpace.BODY_SPACE,
                objects=[obj],
                allowed_kinds=[ContentKind.CHART, ContentKind.MAP],
                z_index=2 + idx,
            )
            zones.append(v_zone)
            all_slide_objects.append(obj)

        # 4. Build Data Table Zone
        if table_bindings:
            table_objs = [
                self._create_slide_object(
                    m_slide=m_slide,
                    binding=b,
                    item=item,
                    is_technical_deck=is_technical_deck,
                )
                for b, item in table_bindings
            ]
            t_zone = ZoneSpec(
                zone_id=f"{m_slide.physical_slide_id}__ZONE_DATA_TABLE",
                zone_type=ZoneType.DATA_TABLE,
                layer_role=LayerRole.BODY,
                coordinate_space=CoordinateSpace.BODY_SPACE,
                objects=table_objs,
                allowed_kinds=[ContentKind.TABLE],
                z_index=4,
            )
            zones.append(t_zone)
            all_slide_objects.extend(table_objs)

        # 5. Build KPI Strip Zone
        if kpi_bindings:
            kpi_objs = [
                self._create_slide_object(
                    m_slide=m_slide,
                    binding=b,
                    item=item,
                    is_technical_deck=is_technical_deck,
                )
                for b, item in kpi_bindings
            ]
            k_zone = ZoneSpec(
                zone_id=f"{m_slide.physical_slide_id}__ZONE_KPI_STRIP",
                zone_type=ZoneType.KPI_STRIP,
                layer_role=LayerRole.BODY,
                coordinate_space=CoordinateSpace.BODY_SPACE,
                objects=kpi_objs,
                allowed_kinds=[ContentKind.KPI_METRIC],
                z_index=5,
            )
            zones.append(k_zone)
            all_slide_objects.extend(kpi_objs)

        # 6. Build Narrative / Bullet Zone
        if narrative_bindings:
            narrative_objs = [
                self._create_slide_object(
                    m_slide=m_slide,
                    binding=b,
                    item=item,
                    is_technical_deck=is_technical_deck,
                )
                for b, item in narrative_bindings
            ]
            n_zone = ZoneSpec(
                zone_id=f"{m_slide.physical_slide_id}__ZONE_INSIGHT_NARRATIVE",
                zone_type=ZoneType.INSIGHT_NARRATIVE,
                layer_role=LayerRole.BODY,
                coordinate_space=CoordinateSpace.BODY_SPACE,
                objects=narrative_objs,
                allowed_kinds=[ContentKind.NARRATIVE_INSIGHT],
                z_index=6,
            )
            zones.append(n_zone)
            all_slide_objects.extend(narrative_objs)

        # 7. Build Footnote / Source Citation Zone
        footnote_sources = set()
        for _, item in visual_bindings + table_bindings + kpi_bindings + narrative_bindings:
            if item.source_dataset_id or item.source_sheet_name:
                src = str(item.source_sheet_name or item.source_dataset_id)
                footnote_sources.add(src)
        
        footnote_text = f"Source: {', '.join(sorted(footnote_sources))}" if footnote_sources else "Source: Internal HR Analytics"
        clean_footnote = self._cleanse_text(footnote_text, is_technical_deck)

        footnote_obj = SlideObjectSpec(
            object_id=f"{m_slide.physical_slide_id}__OBJ_FOOTNOTE",
            object_name=self._build_selection_pane_name(m_slide.physical_slide_id, "FOOTNOTE"),
            name="Slide Footnote",
            content_id=f"{m_slide.physical_slide_id}__FOOTNOTE",
            binding_role=ContentBindingRole.SUPPORTING,
            kind=ContentKind.NARRATIVE_INSIGHT,
            semantic_topic=m_slide.semantic_topic,
            editability=EditabilityPolicy.NATIVE_REQUIRED,
            inheritance_policy=FrameInheritancePolicy.MASTER_PREFERRED,
            headline="",
            narrative_text=clean_footnote,
            data_summary={},
            source_traceability={"sources": sorted(footnote_sources)},
        )
        footnote_zone = ZoneSpec(
            zone_id=f"{m_slide.physical_slide_id}__ZONE_FOOTNOTE",
            zone_type=ZoneType.FOOTNOTE,
            layer_role=LayerRole.MASTER_FRAME,
            coordinate_space=CoordinateSpace.MASTER_FRAME_SPACE,
            inheritance_policy=FrameInheritancePolicy.MASTER_PREFERRED,
            objects=[footnote_obj],
            allowed_kinds=[ContentKind.NARRATIVE_INSIGHT],
            z_index=7,
        )
        zones.append(footnote_zone)
        all_slide_objects.append(footnote_obj)

        slide_status = StructureStatus.STRUCTURE_REPLAN_REQUIRED if replan_reason else StructureStatus.STRUCTURE_VALIDATED

        slide_spec = LayeredSlideSpec(
            physical_slide_id=m_slide.physical_slide_id,
            logical_slide_id=m_slide.logical_slide_id,
            semantic_topic=m_slide.semantic_topic,
            structural_role=m_slide.structural_role,
            sequence_index=m_slide.sequence_index,
            continuation_index=m_slide.continuation_index,
            is_continuation=m_slide.is_continuation,
            headline=clean_headline,
            section_name=m_slide.section_name,
            zones=zones,
            safe_area=SafeAreaSpec(),
            structure_status=slide_status,
            replan_reason=replan_reason,
            metadata=dict(m_slide.metadata),
        )

        return slide_spec, all_slide_objects, replan_reason

    def _create_slide_object(
        self,
        m_slide: PhysicalSlideInstance,
        binding: ContentBinding,
        item: PresentationContentItem,
        is_technical_deck: bool,
    ) -> SlideObjectSpec:
        """Instantiates a stable, truthful SlideObjectSpec from a PresentationContentItem."""
        # Truthful editability policy: defines renderer expectations, not actual rendering outcome
        if item.kind == ContentKind.MAP:
            # Maps are raster/composite geographic representations in PowerPoint
            editability = EditabilityPolicy.RASTER_ALLOWED
        elif item.kind == ContentKind.IMAGE:
            editability = EditabilityPolicy.RASTER_ALLOWED
        elif item.kind == ContentKind.VIDEO:
            editability = EditabilityPolicy.MEDIA_REFERENCE
        elif item.kind == ContentKind.CHART:
            editability = EditabilityPolicy.NATIVE_PREFERRED
        elif item.kind in (ContentKind.TABLE, ContentKind.KPI_METRIC, ContentKind.NARRATIVE_INSIGHT):
            editability = EditabilityPolicy.NATIVE_REQUIRED
        else:
            editability = EditabilityPolicy.NATIVE_REQUIRED

        # Deterministic HighView semantic object ID
        object_id = f"{m_slide.physical_slide_id}__OBJ_{item.kind.value.upper()}_{item.content_id}"

        # Deterministic, unique Selection-Pane friendly object name
        desc = f"{item.kind.value}_{item.content_id}"
        object_name = self._build_selection_pane_name(m_slide.physical_slide_id, desc)

        clean_headline = self._cleanse_text(item.narrative_takeaway or item.metric_label or item.content_id, is_technical_deck)
        bullets_text = "\n".join(item.supporting_bullets) if item.supporting_bullets else ""
        clean_narrative = self._cleanse_text(bullets_text, is_technical_deck)

        # Audited lineage traceability
        source_traceability: dict[str, Any] = {}
        if item.fact_id:
            source_traceability["fact_id"] = item.fact_id
        if item.source_dataset_id:
            source_traceability["source_dataset_id"] = item.source_dataset_id
        if item.source_sheet_name:
            source_traceability["source_sheet_name"] = item.source_sheet_name
        if item.dimension_name:
            source_traceability["dimension_name"] = item.dimension_name
        if item.metric_name:
            source_traceability["metric_name"] = item.metric_name
        if item.unit:
            source_traceability["unit"] = item.unit
        if item.grain:
            source_traceability["grain"] = item.grain
        if item.evidence_ids:
            source_traceability["evidence_ids"] = list(item.evidence_ids)

        # Data summary
        data_summary: dict[str, Any] = {}
        if item.metric_value:
            data_summary["metric_value"] = item.metric_value
        if item.metric_label:
            data_summary["metric_label"] = item.metric_label
        if item.table_data:
            data_summary["row_count"] = len(item.table_data)
            data_summary["columns"] = list(item.table_data[0].keys()) if item.table_data else []
        if item.visual_spec:
            data_summary["chart_type"] = item.visual_spec.get("chart_type")

        return SlideObjectSpec(
            object_id=object_id,
            object_name=object_name,
            name=f"{item.kind.value.capitalize()} Object ({item.content_id})",
            content_id=item.content_id,
            binding_role=binding.binding_role,
            kind=item.kind,
            semantic_topic=m_slide.semantic_topic,
            editability=editability,
            inheritance_policy=FrameInheritancePolicy.PER_SLIDE,
            headline=clean_headline,
            narrative_text=clean_narrative,
            data_summary=data_summary,
            source_traceability=source_traceability,
            metadata=dict(getattr(item, "metadata", None) or {}),
        )

    @classmethod
    def _cleanse_text(cls, text: str, is_technical_deck: bool) -> str:
        """Sanitizes user-visible text to prevent governance leakage in business presentations."""
        if not text or is_technical_deck:
            return text or ""
        cleaned = re.sub(r"\bSDR(-\d+)?\b", "Dataset", text, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bJoin(Plan|Graph)\b", "Data Integration", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bEVID-[A-Za-z0-9_\-]+\b", "Audited Evidence", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b[a-f0-9]{32,64}\b", "", cleaned)
        cleaned = re.sub(r"\bcontrol\s+plane\b", "core system", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\borchestrator\s+task\b", "pipeline process", cleaned, flags=re.IGNORECASE)
        return cleaned.strip()
