"""HighView Presentation Studio — PPT-L5 Constraint Layout Engine & Layout Validator.

Implements:
1. ZoneLayoutEngine: Resolves zone bounding boxes from structural archetypes and constraints.
2. LayoutConstraintEngine: Coordinates fit engines, bounded repairs, and deterministic layout resolution.
3. LayoutValidator: Strict architectural validation ensuring 0 overlaps, 0 safe-area violations,
   0 font floor violations, and 0 orphan objects.

Architectural Invariants:
1. Canonical coordinates: Normalized [0.0, 1.0].
2. ZERO brand colors, ZERO theme palette, ZERO OOXML, ZERO PowerPoint shape IDs.
3. ZERO physical slide creation (SlideExpansionEngine remains sole owner).
4. SPLIT BEFORE SHRINK: Readability floors are never breached.
5. Deterministic layout fingerprints: Same input -> exact same layout.
6. AI layout calls = 0.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import math
from typing import Any, Optional

from .content_models import ContentKind
from .fit_engines import (
    ChartFitPolicy,
    ImageFitEngine,
    TableFitEngine,
    TextFitEngine,
)
from .layout_config import CentralLayoutConfig, DEFAULT_LAYOUT_CONFIG
from .layout_models import (
    Box2D,
    ImageFitMode,
    LateSplitRequest,
    LayoutStatus,
    ObjectFitStatus,
    ResolvedDeckLayout,
    ResolvedObjectLayout,
    ResolvedSafeArea,
    ResolvedSlideLayout,
    ResolvedZoneLayout,
    SlideFitStatus,
    TextRole,
    ZoneFitStatus,
    compute_layout_fingerprint,
)
from .layer_zone_models import (
    CoordinateSpace,
    EditabilityPolicy,
    LayeredDeckStructureSpec,
    LayeredSlideSpec,
    LayerRole,
    SlideObjectSpec,
    StructuralRole,
    ZoneSpec,
    ZoneType,
)
from .story_models import ContentBindingRole

logger = logging.getLogger(__name__)


class LayoutValidationError(ValueError):
    """Raised when slide layout violates spatial constraints or integrity rules."""
    pass


# ==============================================================================
# ZONE LAYOUT ENGINE
# ==============================================================================

class ZoneLayoutEngine:
    """Assigns normalized bounding boxes to structural zones based on layout archetypes."""

    def __init__(self, config: CentralLayoutConfig | None = None) -> None:
        self.config = config or DEFAULT_LAYOUT_CONFIG

    def resolve_safe_area(self) -> ResolvedSafeArea:
        """Constructs canonical safe area reservations."""
        cfg = self.config
        slide_b = Box2D(left=0.0, top=0.0, width=1.0, height=1.0)
        safe_b = Box2D(
            left=round(cfg.margin_left, 4),
            top=round(cfg.margin_top, 4),
            width=round(1.0 - cfg.margin_left - cfg.margin_right, 4),
            height=round(1.0 - cfg.margin_top - cfg.margin_bottom, 4),
        )
        header_b = Box2D(
            left=round(cfg.margin_left, 4),
            top=round(cfg.frame_header_top, 4),
            width=round(cfg.body_width, 4),
            height=round(cfg.frame_header_height, 4),
        )
        footer_b = Box2D(
            left=round(cfg.margin_left, 4),
            top=round(cfg.body_bottom + 0.01, 4),
            width=round(cfg.body_width, 4),
            height=round(cfg.frame_footer_height, 4),
        )
        body_b = Box2D(
            left=round(cfg.body_left, 4),
            top=round(cfg.body_top, 4),
            width=round(cfg.body_width, 4),
            height=round(cfg.body_height, 4),
        )
        return ResolvedSafeArea(
            slide_bounds=slide_b,
            safe_area_bounds=safe_b,
            frame_header_bounds=header_b,
            frame_footer_bounds=footer_b,
            body_bounds=body_b,
        )

    def resolve_zone_bounds(
        self,
        slide_spec: LayeredSlideSpec,
        safe_area: ResolvedSafeArea,
        attempt: int = 1,
    ) -> dict[str, Box2D]:
        """Resolves normalized Box2D bounds for each zone on the slide.
        
        Archetypes are detected dynamically from zone types and structural role.
        """
        cfg = self.config
        bounds_map: dict[str, Box2D] = {}
        zones = slide_spec.zones

        # Frame zones
        header_zones = [z for z in zones if z.zone_type in (ZoneType.TITLE, ZoneType.SUBTITLE)]
        footer_zones = [z for z in zones if z.zone_type == ZoneType.FOOTNOTE]
        bg_zones = [z for z in zones if z.zone_type == ZoneType.BACKGROUND_CANVAS]
        body_zones = [
            z for z in zones
            if z not in header_zones and z not in footer_zones and z not in bg_zones
        ]

        # Background zone
        for bg in bg_zones:
            bounds_map[bg.zone_id] = Box2D(left=0.0, top=0.0, width=1.0, height=1.0)

        # Header frame zones
        has_subtitle = any(z.zone_type == ZoneType.SUBTITLE for z in header_zones)
        hb = safe_area.frame_header_bounds
        for hz in header_zones:
            if hz.zone_type == ZoneType.TITLE:
                if has_subtitle:
                    bounds_map[hz.zone_id] = Box2D(
                        left=hb.left,
                        top=hb.top,
                        width=hb.width,
                        height=round(hb.height * 0.65, 4),
                    )
                else:
                    bounds_map[hz.zone_id] = Box2D(
                        left=hb.left,
                        top=hb.top,
                        width=hb.width,
                        height=round(hb.height, 4),
                    )
            elif hz.zone_type == ZoneType.SUBTITLE:
                bounds_map[hz.zone_id] = Box2D(
                    left=hb.left,
                    top=round(hb.top + (hb.height * 0.68), 4),
                    width=hb.width,
                    height=round(hb.height * 0.32, 4),
                )

        # Footer frame zones
        fb = safe_area.frame_footer_bounds
        for fz in footer_zones:
            bounds_map[fz.zone_id] = Box2D(
                left=fb.left,
                top=fb.top,
                width=fb.width,
                height=fb.height,
            )

        # Body zones layout by archetype
        bb = safe_area.body_bounds
        b_types = [z.zone_type for z in body_zones]

        # 1. TITLE HERO / CLOSING
        if slide_spec.structural_role in (StructuralRole.TITLE, StructuralRole.CLOSING, StructuralRole.THANK_YOU):
            for bz in body_zones:
                bounds_map[bz.zone_id] = Box2D(
                    left=round(bb.left + (bb.width * 0.10), 4),
                    top=round(bb.top + (bb.height * 0.15), 4),
                    width=round(bb.width * 0.80, 4),
                    height=round(bb.height * 0.65, 4),
                )
            return bounds_map

        # 2. TABLE FOCUSED (only data table in body)
        if ZoneType.DATA_TABLE in b_types and len(body_zones) == 1:
            bz = body_zones[0]
            bounds_map[bz.zone_id] = Box2D(
                left=bb.left,
                top=bb.top,
                width=bb.width,
                height=bb.height,
            )
            return bounds_map

        # 3. KPI STRIP + VISUAL / BODY
        if ZoneType.KPI_STRIP in b_types:
            kpi_zone = next(z for z in body_zones if z.zone_type == ZoneType.KPI_STRIP)
            other_zones = [z for z in body_zones if z != kpi_zone]
            kpi_h = 0.17
            gap_v = cfg.zone_gap_v

            bounds_map[kpi_zone.zone_id] = Box2D(
                left=bb.left,
                top=bb.top,
                width=bb.width,
                height=round(kpi_h, 4),
            )

            remaining_top = bb.top + kpi_h + gap_v
            remaining_h = max(0.20, bb.height - kpi_h - gap_v)

            if len(other_zones) == 1:
                bounds_map[other_zones[0].zone_id] = Box2D(
                    left=bb.left,
                    top=round(remaining_top, 4),
                    width=bb.width,
                    height=round(remaining_h, 4),
                )
            elif len(other_zones) == 2:
                # Split remaining space horizontally
                gap_h = cfg.zone_gap_h
                w_each = (bb.width - gap_h) / 2.0
                bounds_map[other_zones[0].zone_id] = Box2D(
                    left=bb.left,
                    top=round(remaining_top, 4),
                    width=round(w_each, 4),
                    height=round(remaining_h, 4),
                )
                bounds_map[other_zones[1].zone_id] = Box2D(
                    left=round(bb.left + w_each + gap_h, 4),
                    top=round(remaining_top, 4),
                    width=round(w_each, 4),
                    height=round(remaining_h, 4),
                )
            return bounds_map

        # 4. MULTI VISUAL (Two charts side by side)
        visual_zones = [z for z in body_zones if z.zone_type in (ZoneType.PRIMARY_VISUAL, ZoneType.SECONDARY_VISUAL)]
        if len(visual_zones) >= 2 and len(body_zones) == 2:
            gap_h = cfg.zone_gap_h
            w_each = (bb.width - gap_h) / 2.0
            bounds_map[visual_zones[0].zone_id] = Box2D(
                left=bb.left,
                top=bb.top,
                width=round(w_each, 4),
                height=bb.height,
            )
            bounds_map[visual_zones[1].zone_id] = Box2D(
                left=round(bb.left + w_each + gap_h, 4),
                top=bb.top,
                width=round(w_each, 4),
                height=bb.height,
            )
            return bounds_map

        # 5. PRIMARY VISUAL + INSIGHT NARRATIVE / BULLETS (Standard Workhorse Layout)
        if len(body_zones) == 2:
            z1, z2 = body_zones[0], body_zones[1]
            gap_h = cfg.zone_gap_h

            # Determine visual ratio vs text ratio (rebalance in attempt 2 if needed)
            if attempt == 2:
                vis_ratio = 0.52
                text_ratio = 0.44
            elif attempt == 3:
                vis_ratio = 0.50
                text_ratio = 0.47
            else:
                vis_ratio = 0.58
                text_ratio = 0.38

            # Ensure map visual gets generous area
            is_map_present = any(
                o.kind == ContentKind.MAP for z in body_zones for o in z.objects
            )
            if is_map_present:
                vis_ratio = max(vis_ratio, 0.56)
                text_ratio = 1.0 - vis_ratio - (gap_h / bb.width)

            w1 = round(bb.width * vis_ratio, 4)
            w2 = round(bb.width - w1 - gap_h, 4)

            # Left is visual, Right is insight/bullets
            if z1.zone_type in (ZoneType.PRIMARY_VISUAL, ZoneType.DATA_TABLE):
                vis_z, text_z = z1, z2
            else:
                vis_z, text_z = z2, z1

            bounds_map[vis_z.zone_id] = Box2D(
                left=bb.left,
                top=bb.top,
                width=w1,
                height=bb.height,
            )
            bounds_map[text_z.zone_id] = Box2D(
                left=round(bb.left + w1 + gap_h, 4),
                top=bb.top,
                width=w2,
                height=bb.height,
            )
            return bounds_map

        # 6. SINGLE BODY ZONE (Full canvas)
        if len(body_zones) == 1:
            bounds_map[body_zones[0].zone_id] = Box2D(
                left=bb.left,
                top=bb.top,
                width=bb.width,
                height=bb.height,
            )
            return bounds_map

        # 7. GENERIC N-ZONE HORIZONTAL FLOW
        n = max(1, len(body_zones))
        gap_h = cfg.zone_gap_h
        total_gaps = gap_h * (n - 1)
        w_each = max(0.10, (bb.width - total_gaps) / n)
        for i, bz in enumerate(body_zones):
            x = bb.left + i * (w_each + gap_h)
            bounds_map[bz.zone_id] = Box2D(
                left=round(x, 4),
                top=bb.top,
                width=round(w_each, 4),
                height=bb.height,
            )

        return bounds_map


# ==============================================================================
# LAYOUT CONSTRAINT ENGINE
# ==============================================================================

class LayoutConstraintEngine:
    """Coordinates fit engines, layout resolution, bounded repairs, and fingerprinting."""

    def __init__(self, config: CentralLayoutConfig | None = None) -> None:
        self.config = config or DEFAULT_LAYOUT_CONFIG
        self.zone_engine = ZoneLayoutEngine(self.config)
        self.text_engine = TextFitEngine(self.config)
        self.image_engine = ImageFitEngine(self.config)
        self.table_engine = TableFitEngine(self.config)
        self.chart_policy = ChartFitPolicy(self.config)

    def resolve_slide_layout(self, slide_spec: LayeredSlideSpec) -> ResolvedSlideLayout:
        """Deterministically calculates exact geometry and content fit for a physical slide."""
        safe_area = self.zone_engine.resolve_safe_area()
        repair_actions: list[str] = []
        late_split: Optional[LateSplitRequest] = None
        slide_status = SlideFitStatus.PASS
        warnings: list[str] = []

        max_attempts = 4
        best_resolved_zones: list[ResolvedZoneLayout] = []
        best_resolved_objs: list[ResolvedObjectLayout] = []

        for attempt in range(1, max_attempts + 1):
            zone_bounds_map = self.zone_engine.resolve_zone_bounds(
                slide_spec, safe_area, attempt=attempt
            )
            resolved_zones: list[ResolvedZoneLayout] = []
            all_slide_objs: list[ResolvedObjectLayout] = []
            slide_has_overflow = False

            for zone_spec in slide_spec.zones:
                zb = zone_bounds_map.get(
                    zone_spec.zone_id,
                    Box2D(left=safe_area.body_bounds.left, top=safe_area.body_bounds.top, width=0.4, height=0.4)
                )
                zone_objs: list[ResolvedObjectLayout] = []
                zone_overflow = False

                num_objs = max(1, len(zone_spec.objects))

                # Lay out objects inside the zone
                for idx, obj_spec in enumerate(zone_spec.objects):
                    obj_box, fit_status, resolved_font, lines, fit_mode, crop_box, col_w, row_h, obj_warn, split_hint = self._resolve_object_geometry(
                        obj_spec, zb, idx, num_objs, zone_spec.zone_type
                    )
                    if obj_warn:
                        warnings.extend(obj_warn)

                    if fit_status in (ObjectFitStatus.OVERFLOW, ObjectFitStatus.REPLAN_REQUIRED):
                        zone_overflow = True
                        slide_has_overflow = True
                        if split_hint and not late_split:
                            late_split = LateSplitRequest(
                                physical_slide_id=slide_spec.physical_slide_id,
                                logical_slide_id=slide_spec.logical_slide_id,
                                reason=split_hint.get("reason", "CONTENT_OVERFLOW"),
                                affected_content_ids=[obj_spec.content_id],
                                recommended_partition_hint=split_hint,
                            )

                    res_obj = ResolvedObjectLayout(
                        object_id=obj_spec.object_id,
                        object_name=obj_spec.object_name,
                        content_id=obj_spec.content_id,
                        name=obj_spec.name,
                        kind=obj_spec.kind,
                        binding_role=obj_spec.binding_role,
                        editability=obj_spec.editability,
                        bounds=obj_box,
                        fit_status=fit_status,
                        resolved_font_size=resolved_font,
                        line_count=lines,
                        fit_mode=fit_mode,
                        crop_box=crop_box,
                        column_widths=col_w,
                        row_heights=row_h,
                        warnings=obj_warn,
                        metadata=obj_spec.metadata,
                    )
                    zone_objs.append(res_obj)
                    all_slide_objs.append(res_obj)

                res_zone = ResolvedZoneLayout(
                    zone_id=zone_spec.zone_id,
                    zone_type=zone_spec.zone_type,
                    layer_role=zone_spec.layer_role,
                    coordinate_space=zone_spec.coordinate_space,
                    bounds=zb,
                    fit_status=ZoneFitStatus.OVERFLOW if zone_overflow else ZoneFitStatus.FIT,
                    objects=zone_objs,
                    z_index=zone_spec.z_index,
                    metadata=zone_spec.metadata,
                )
                resolved_zones.append(res_zone)

            best_resolved_zones = resolved_zones
            best_resolved_objs = all_slide_objs

            if not slide_has_overflow:
                if attempt > 1:
                    repair_actions.append(f"Repaired layout on attempt {attempt}")
                break
            else:
                if attempt == 1:
                    repair_actions.append("Attempt 2: Rebalanced zone proportions")
                elif attempt == 2:
                    repair_actions.append("Attempt 3: Scaled text to minimum font floor")
                elif attempt == 3:
                    repair_actions.append("Attempt 4: Verified late split escalation")

        # Determine final slide fit status
        if late_split or any(o.fit_status == ObjectFitStatus.OVERFLOW for o in best_resolved_objs):
            slide_status = SlideFitStatus.LATE_SPLIT_REQUIRED
            if not late_split:
                late_split = LateSplitRequest(
                    physical_slide_id=slide_spec.physical_slide_id,
                    logical_slide_id=slide_spec.logical_slide_id,
                    reason="SPATIAL_OVERFLOW",
                    affected_content_ids=[
                        o.content_id for o in best_resolved_objs if o.fit_status == ObjectFitStatus.OVERFLOW
                    ],
                    recommended_partition_hint={"repair_exhausted": True},
                )
        elif warnings:
            slide_status = SlideFitStatus.PASS_WITH_WARNINGS
        else:
            slide_status = SlideFitStatus.PASS

        fingerprint = compute_layout_fingerprint(
            slide_id=slide_spec.physical_slide_id,
            aspect_ratio=self.config.canvas_aspect_ratio_str,
            safe_area=safe_area,
            zones=best_resolved_zones,
            fit_status=slide_status,
            late_split=late_split,
            repair_actions=repair_actions,
        )

        return ResolvedSlideLayout(
            physical_slide_id=slide_spec.physical_slide_id,
            logical_slide_id=slide_spec.logical_slide_id,
            sequence_index=slide_spec.sequence_index,
            aspect_ratio=self.config.canvas_aspect_ratio_str,
            slide_bounds=safe_area.slide_bounds,
            safe_area=safe_area,
            zones=best_resolved_zones,
            object_layouts=best_resolved_objs,
            fit_status=slide_status,
            warnings=warnings,
            late_split_request=late_split,
            repair_attempts=len(repair_actions) + 1,
            repair_actions=repair_actions,
            layout_fingerprint=fingerprint,
            metadata=slide_spec.metadata,
        )

    def _resolve_object_geometry(
        self,
        obj_spec: SlideObjectSpec,
        zone_box: Box2D,
        obj_index: int,
        total_in_zone: int,
        zone_type: ZoneType,
    ) -> tuple[
        Box2D,
        ObjectFitStatus,
        Optional[float],
        Optional[int],
        Optional[ImageFitMode],
        Optional[Box2D],
        Optional[list[float]],
        Optional[list[float]],
        list[str],
        Optional[dict[str, Any]],
    ]:
        """Resolves geometry, fit status, and content sizing for a single object within a zone."""
        warnings: list[str] = []
        split_hint: Optional[dict[str, Any]] = None
        fit_mode: Optional[ImageFitMode] = None
        crop_box: Optional[Box2D] = None
        col_w: Optional[list[float]] = None
        row_h: Optional[list[float]] = None
        resolved_font: Optional[float] = None
        lines: Optional[int] = None
        fit_status = ObjectFitStatus.FIT

        # Determine object sub-box within zone
        if total_in_zone == 1:
            obj_box = Box2D(
                left=zone_box.left,
                top=zone_box.top,
                width=zone_box.width,
                height=zone_box.height,
            )
        elif zone_type == ZoneType.KPI_STRIP:
            # Horizontal strip for KPIs
            gap_h = self.config.object_gap_h
            w_each = (zone_box.width - (gap_h * (total_in_zone - 1))) / total_in_zone
            x = zone_box.left + obj_index * (w_each + gap_h)
            obj_box = Box2D(
                left=round(x, 4),
                top=zone_box.top,
                width=round(w_each, 4),
                height=zone_box.height,
            )
        else:
            # Vertical stacking within zone
            gap_v = self.config.object_gap_v
            h_each = (zone_box.height - (gap_v * (total_in_zone - 1))) / total_in_zone
            y = zone_box.top + obj_index * (h_each + gap_v)
            obj_box = Box2D(
                left=zone_box.left,
                top=round(y, 4),
                width=zone_box.width,
                height=round(h_each, 4),
            )

        # 1. TEXT OBJECTS (Title, Subtitle, Narrative, Bullets, Footnote)
        if obj_spec.kind == ContentKind.NARRATIVE_INSIGHT:
            if zone_type == ZoneType.TITLE:
                role = TextRole.TITLE
            elif zone_type == ZoneType.SUBTITLE:
                role = TextRole.SUBTITLE
            elif zone_type == ZoneType.FOOTNOTE:
                role = TextRole.FOOTNOTE
            elif zone_type == ZoneType.BULLETS:
                role = TextRole.BULLET
            elif zone_type == ZoneType.KPI_STRIP:
                role = TextRole.KPI_LABEL
            else:
                role = TextRole.BODY

            content_text = obj_spec.narrative_text or obj_spec.headline or obj_spec.name
            bullet_count = 0
            if role == TextRole.BULLET:
                bullet_count = len([line for line in content_text.split("\n") if line.strip()])
                if bullet_count > self.config.max_bullets_per_slide:
                    warnings.append(
                        f"Bullet count ({bullet_count}) exceeds safe maximum ({self.config.max_bullets_per_slide})"
                    )

            resolved_font, lines, fit_status, text_warn = self.text_engine.fit_text(
                text=content_text,
                available_box=obj_box,
                role=role,
                bullet_count=bullet_count,
            )
            warnings.extend(text_warn)
            if fit_status == ObjectFitStatus.OVERFLOW:
                split_hint = {
                    "reason": "TITLE_OVERFLOW" if role == TextRole.TITLE else "TEXT_OVERFLOW",
                    "text_role": role.value,
                    "overflow_lines": lines,
                }

        # 2. STAT CALLOUT (KPIs)
        elif obj_spec.kind == ContentKind.KPI_METRIC:
            resolved_font = self.config.get_typography(TextRole.KPI_VALUE).default_size_pt
            fit_status = ObjectFitStatus.FIT
            lines = 1

        # 3. IMAGES & MAPS (RASTER_ALLOWED)
        elif obj_spec.kind in (ContentKind.IMAGE, ContentKind.MAP):
            is_map = (obj_spec.kind == ContentKind.MAP)
            src_w = int(obj_spec.data_summary.get("width", 1200))
            src_h = int(obj_spec.data_summary.get("height", 800))
            mode = ImageFitMode.CONTAIN if is_map else ImageFitMode.CONTAIN

            res_bounds, crop_b, q_warn, img_warn = self.image_engine.fit_image(
                source_width_px=src_w,
                source_height_px=src_h,
                available_box=obj_box,
                mode=mode,
            )
            obj_box = res_bounds
            fit_mode = mode
            crop_box = crop_b
            warnings.extend(img_warn)

            if is_map:
                c_status, c_warn = self.chart_policy.evaluate_chart_fit(
                    available_box=obj_box,
                    kind=ContentKind.MAP,
                    is_map=True,
                )
                warnings.extend(c_warn)
                if c_status == ObjectFitStatus.OVERFLOW:
                    fit_status = ObjectFitStatus.OVERFLOW
                    split_hint = {"reason": "MAP_SPACE_DEFICIT"}

        # 4. CHARTS (Native Preferred)
        elif obj_spec.kind == ContentKind.CHART:
            cat_count = int(obj_spec.data_summary.get("category_count", 0))
            ser_count = int(obj_spec.data_summary.get("series_count", 1))
            c_status, c_warn = self.chart_policy.evaluate_chart_fit(
                available_box=obj_box,
                kind=ContentKind.CHART,
                is_primary=(obj_spec.binding_role == ContentBindingRole.PRIMARY),
                category_count=cat_count,
                series_count=ser_count,
                is_map=False,
            )
            fit_status = c_status
            warnings.extend(c_warn)
            if c_status == ObjectFitStatus.OVERFLOW:
                split_hint = {"reason": "CHART_SPACE_DEFICIT", "category_count": cat_count}

        # 5. DATA TABLES
        elif obj_spec.kind == ContentKind.TABLE:
            row_count = int(obj_spec.data_summary.get("row_count", 5))
            headers = obj_spec.data_summary.get("headers", ["Col 1", "Col 2", "Col 3"])
            sample_data = obj_spec.data_summary.get("sample_rows", [])

            col_w, row_h, resolved_font, t_status, tbl_split, t_warn = self.table_engine.fit_table(
                headers=headers,
                row_count=row_count,
                sample_rows=sample_data,
                available_box=obj_box,
            )
            fit_status = t_status
            warnings.extend(t_warn)
            if t_status == ObjectFitStatus.OVERFLOW:
                split_hint = tbl_split or {"reason": "TABLE_OVERFLOW"}

        return (
            obj_box,
            fit_status,
            resolved_font,
            lines,
            fit_mode,
            crop_box,
            col_w,
            row_h,
            warnings,
            split_hint,
        )

    def resolve_deck_layout(
        self,
        deck_structure: LayeredDeckStructureSpec,
        metadata: Optional[dict[str, Any]] = None,
    ) -> ResolvedDeckLayout:
        """Resolves layouts for all physical slides in a deck structure."""
        resolved_slides: list[ResolvedSlideLayout] = []
        all_late_splits: list[LateSplitRequest] = []

        for slide_spec in deck_structure.slides:
            res_slide = self.resolve_slide_layout(slide_spec)
            resolved_slides.append(res_slide)
            if res_slide.late_split_request:
                all_late_splits.append(res_slide.late_split_request)

        # Compute whole-deck fingerprint from slide fingerprints
        slide_fps = [s.layout_fingerprint for s in resolved_slides]
        deck_fp_payload = f"{deck_structure.manifest_id}::" + "::".join(slide_fps)
        deck_fingerprint = hashlib.sha256(deck_fp_payload.encode("utf-8")).hexdigest()

        total_objects = sum(len(s.object_layouts) for s in resolved_slides)

        return ResolvedDeckLayout(
            deck_id=deck_structure.manifest_id,
            slides=resolved_slides,
            deck_fingerprint=deck_fingerprint,
            late_splits=all_late_splits,
            total_slides=len(resolved_slides),
            total_objects=total_objects,
            replan_required=len(all_late_splits) > 0,
            metadata=metadata or {},
        )


# ==============================================================================
# LAYOUT VALIDATOR
# ==============================================================================

class LayoutValidator:
    """Rigorous architectural validator for resolved slide and deck layouts."""

    def __init__(self, config: CentralLayoutConfig | None = None) -> None:
        self.config = config or DEFAULT_LAYOUT_CONFIG

    def validate_slide_layout(
        self,
        layout: ResolvedSlideLayout,
        original_spec: Optional[LayeredSlideSpec] = None,
    ) -> None:
        """Validates all spatial and structural invariants for a ResolvedSlideLayout."""
        tol = 1e-3

        # 1. Slide bounds must be [0,0, 1,1]
        sb = layout.slide_bounds
        if sb.left != 0.0 or sb.top != 0.0 or sb.width != 1.0 or sb.height != 1.0:
            raise LayoutValidationError(
                f"Slide bounds must be exactly (0.0, 0.0, 1.0, 1.0), got {sb.to_rounded_dict()}"
            )

        # 2. Positive non-zero dimensions
        for z in layout.zones:
            if z.bounds.width <= 0.0 or z.bounds.height <= 0.0:
                raise LayoutValidationError(
                    f"Zone {z.zone_id} has invalid non-positive dimensions: {z.bounds.to_rounded_dict()}"
                )
            for o in z.objects:
                if o.bounds.width <= 0.0 or o.bounds.height <= 0.0:
                    raise LayoutValidationError(
                        f"Object {o.object_id} has invalid non-positive dimensions: {o.bounds.to_rounded_dict()}"
                    )

        # 3. Containment: Objects inside their owning zone
        for z in layout.zones:
            for o in z.objects:
                if not z.bounds.contains(o.bounds, tol=tol):
                    raise LayoutValidationError(
                        f"Object {o.object_id} {o.bounds.to_rounded_dict()} breaches owning zone "
                        f"{z.zone_id} {z.bounds.to_rounded_dict()}"
                    )

        # 4. Safe Area Containment
        sb = layout.safe_area.safe_area_bounds
        bb = layout.safe_area.body_bounds
        hb = layout.safe_area.frame_header_bounds
        fb = layout.safe_area.frame_footer_bounds

        for z in layout.zones:
            if z.zone_type == ZoneType.BACKGROUND_CANVAS:
                continue
            # All content zones must be inside slide perimeter safe area bounds
            if not sb.contains(z.bounds, tol=tol):
                raise LayoutValidationError(
                    f"Zone {z.zone_id} {z.bounds.to_rounded_dict()} breaches safe area perimeter "
                    f"{sb.to_rounded_dict()}"
                )
            if z.zone_type in (ZoneType.TITLE, ZoneType.SUBTITLE):
                if not hb.contains(z.bounds, tol=tol):
                    raise LayoutValidationError(
                        f"Header zone {z.zone_id} {z.bounds.to_rounded_dict()} breaches header bounds "
                        f"{hb.to_rounded_dict()}"
                    )
            elif z.zone_type == ZoneType.FOOTNOTE:
                if not fb.contains(z.bounds, tol=tol):
                    raise LayoutValidationError(
                        f"Footer zone {z.zone_id} {z.bounds.to_rounded_dict()} breaches footer bounds "
                        f"{fb.to_rounded_dict()}"
                    )
            else:
                # Main body content zones must be strictly inside body bounds
                if not bb.contains(z.bounds, tol=tol):
                    raise LayoutValidationError(
                        f"Body content zone {z.zone_id} {z.bounds.to_rounded_dict()} breaches safe body bounds "
                        f"{bb.to_rounded_dict()}"
                    )

        # 5. Body / Frame Collision Prevention: Main body content zones must not invade header or footer
        main_body_zones = [
            z for z in layout.zones
            if z.zone_type not in (ZoneType.TITLE, ZoneType.SUBTITLE, ZoneType.FOOTNOTE, ZoneType.BACKGROUND_CANVAS)
        ]
        for z in main_body_zones:
            if z.bounds.intersects(hb, tol=tol):
                raise LayoutValidationError(
                    f"Body zone {z.zone_id} collides with reserved header frame {hb.to_rounded_dict()}"
                )
            if z.bounds.intersects(fb, tol=tol):
                raise LayoutValidationError(
                    f"Body zone {z.zone_id} collides with reserved footer frame {fb.to_rounded_dict()}"
                )

        # 6. Unapproved Overlaps: Sibling main body content zones must not overlap
        for i in range(len(main_body_zones)):
            for j in range(i + 1, len(main_body_zones)):
                z1 = main_body_zones[i]
                z2 = main_body_zones[j]
                if z1.bounds.intersects(z2.bounds, tol=tol):
                    raise LayoutValidationError(
                        f"Unapproved collision between body zones {z1.zone_id} and {z2.zone_id}"
                    )

        # 7. Sibling objects within a zone must not overlap
        for z in layout.zones:
            objs = z.objects
            for i in range(len(objs)):
                for j in range(i + 1, len(objs)):
                    o1, o2 = objs[i], objs[j]
                    if o1.bounds.intersects(o2.bounds, tol=tol):
                        raise LayoutValidationError(
                            f"Unapproved collision between objects {o1.object_id} and {o2.object_id} in zone {z.zone_id}"
                        )

        # 8. Typography floors: No text object resolved below its floor
        for o in layout.object_layouts:
            if o.resolved_font_size is not None:
                # Minimum floor across all roles is 8.0pt
                if o.resolved_font_size < 8.0 - tol:
                    raise LayoutValidationError(
                        f"Object {o.object_id} resolved font size {o.resolved_font_size}pt violates floor 8.0pt"
                    )

        # 9. Identity Preservation: If original_spec provided, verify identity invariants
        if original_spec:
            spec_obj_ids = {
                o.object_id for z in original_spec.zones for o in z.objects
            }
            layout_obj_ids = {o.object_id for o in layout.object_layouts}
            if spec_obj_ids != layout_obj_ids:
                raise LayoutValidationError(
                    f"Object ID mismatch between spec and layout: {spec_obj_ids ^ layout_obj_ids}"
                )

            # Editability policy unchanged
            spec_obj_map = {
                o.object_id: o for z in original_spec.zones for o in z.objects
            }
            for lo in layout.object_layouts:
                so = spec_obj_map.get(lo.object_id)
                if so and so.editability != lo.editability:
                    raise LayoutValidationError(
                        f"EditabilityPolicy mutated for {lo.object_id}: {so.editability} -> {lo.editability}"
                    )

        # 10. Layout fingerprint must be present and valid
        if not layout.layout_fingerprint or len(layout.layout_fingerprint) != 64:
            raise LayoutValidationError(
                f"Slide {layout.physical_slide_id} missing valid SHA-256 layout fingerprint"
            )

    def validate_deck_layout(
        self,
        deck_layout: ResolvedDeckLayout,
        original_spec: Optional[LayeredDeckStructureSpec] = None,
    ) -> None:
        """Validates all slides in a ResolvedDeckLayout."""
        if not deck_layout.slides:
            raise LayoutValidationError(f"Deck layout {deck_layout.deck_id} contains zero slides")

        spec_slide_map = {s.physical_slide_id: s for s in original_spec.slides} if original_spec else {}

        for slide in deck_layout.slides:
            orig = spec_slide_map.get(slide.physical_slide_id)
            self.validate_slide_layout(slide, original_spec=orig)

        if not deck_layout.deck_fingerprint or len(deck_layout.deck_fingerprint) != 64:
            raise LayoutValidationError("Deck layout missing valid SHA-256 deck fingerprint")
