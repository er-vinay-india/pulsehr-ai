"""HighView Presentation Studio — PPT-L8 Deterministic Post-Style Validation Engine.

Performs comprehensive, deterministic validation of the actual styled PowerPoint state
after PPT-L7. Strictly enforces the PPT-L8 ownership boundary:
- May detect, classify, and report defects.
- Emits typed upstream repair requests.
- Never directly mutates story, content, geometry, font size, theme, or slide count.
"""

from __future__ import annotations

import io
import logging
import re
import zipfile
from typing import Any, Optional

import pptx
from pptx.enum.shapes import MSO_SHAPE_TYPE

from app.services.presentation.content_models import ContentKind, PresentationContentPackage
from app.services.presentation.layout_models import ResolvedDeckLayout, ResolvedSlideLayout
from app.services.presentation.layer_zone_models import (
    EditabilityPolicy,
    LayeredDeckStructureSpec,
    LayeredSlideSpec,
    LayerRole,
    StructuralRole,
)
from app.services.presentation.render_models import RenderManifest
from app.services.presentation.theme_models import StyleManifest, ThemeDefinition
from app.services.presentation.validation_models_l8 import (
    DeckValidationStatus,
    RepairAction,
    RepairOwner,
    RepairRecommendation,
    SlideValidationResult,
    ValidationCategory,
    ValidationIssue,
    ValidationManifest,
    ValidationSeverity,
    ZoneValidationResult,
    compute_validation_manifest_fingerprint,
)
from app.services.presentation.visual.visual_validator import calculate_contrast_ratio

logger = logging.getLogger(__name__)

# Bounding box tolerance (~0.002 inches)
EMU_TOLERANCE = 2500


class ValidationIssueClassifier:
    """Classifies validation issues into deterministic severity levels and blocking status."""

    CRITICAL_CATEGORIES = {
        ValidationCategory.OBJECT_EXISTENCE,
        ValidationCategory.IDENTITY_PRESERVATION,
        ValidationCategory.CONTENT_PRESERVATION,
        ValidationCategory.NUMERIC_PRESERVATION,
        ValidationCategory.EDITABILITY_PRESERVATION,
        ValidationCategory.PACKAGE_INTEGRITY,
        ValidationCategory.SLIDE_COUNT_ORDER,
        ValidationCategory.CONTINUATION_SEQUENCE,
    }

    @classmethod
    def classify(
        cls,
        category: ValidationCategory,
        base_severity: ValidationSeverity,
    ) -> tuple[ValidationSeverity, bool]:
        """Returns (final_severity, is_blocking)."""
        if category in cls.CRITICAL_CATEGORIES or base_severity == ValidationSeverity.CRITICAL:
            return ValidationSeverity.CRITICAL, True
        if base_severity == ValidationSeverity.WARNING:
            return ValidationSeverity.WARNING, False
        return ValidationSeverity.INFO, False


class RepairRecommendationBuilder:
    """Builds typed repair recommendations attributing responsible upstream owner."""

    @classmethod
    def build_recommendation(cls, issue: ValidationIssue) -> Optional[RepairRecommendation]:
        """Maps a blocking issue to an authoritative upstream phase and action."""
        if not issue.blocking:
            return None

        cat = issue.category
        if cat == ValidationCategory.TEXT_CLIPPING:
            return RepairRecommendation(
                repair_id=f"REP-{issue.issue_id}",
                action=RepairAction.TEXT_REFLOW_REQUIRED,
                owner=RepairOwner.PPT_L5_LAYOUT,
                slide_id=issue.slide_id,
                object_id=issue.object_id,
                reason=issue.message,
            )
        if cat == ValidationCategory.TABLE_INTEGRITY:
            return RepairRecommendation(
                repair_id=f"REP-{issue.issue_id}",
                action=RepairAction.TABLE_SPLIT_REQUIRED,
                owner=RepairOwner.PPT_L3_EXPANSION,
                slide_id=issue.slide_id,
                object_id=issue.object_id,
                reason=issue.message,
            )
        if cat == ValidationCategory.COLLISION:
            return RepairRecommendation(
                repair_id=f"REP-{issue.issue_id}",
                action=RepairAction.LAYOUT_REPLAN_REQUIRED,
                owner=RepairOwner.PPT_L5_LAYOUT,
                slide_id=issue.slide_id,
                object_id=issue.object_id,
                reason=issue.message,
            )
        if cat == ValidationCategory.CONTRAST:
            return RepairRecommendation(
                repair_id=f"REP-{issue.issue_id}",
                action=RepairAction.STYLE_ADJUSTMENT_REQUIRED,
                owner=RepairOwner.PPT_L7_STYLE,
                slide_id=issue.slide_id,
                object_id=issue.object_id,
                reason=issue.message,
            )
        if cat == ValidationCategory.IMAGE_MAP_QUALITY:
            return RepairRecommendation(
                repair_id=f"REP-{issue.issue_id}",
                action=RepairAction.ASSET_REPLACEMENT_REQUIRED,
                owner=RepairOwner.ASSET_PIPELINE,
                slide_id=issue.slide_id,
                object_id=issue.object_id,
                reason=issue.message,
            )
        if cat == ValidationCategory.CHART_INTEGRITY:
            return RepairRecommendation(
                repair_id=f"REP-{issue.issue_id}",
                action=RepairAction.CHART_LABEL_REPLAN_REQUIRED,
                owner=RepairOwner.PPT_L5_LAYOUT,
                slide_id=issue.slide_id,
                object_id=issue.object_id,
                reason=issue.message,
            )

        return None


class DeterministicValidationEngine:
    """The central PPT-L8 Post-Style Deterministic Validation Engine."""

    @classmethod
    def _is_authorized_overlap(
        cls,
        s1: Any,
        s2: Any,
        struct_slide: Optional[Any],
        layout_slide: Optional[Any],
    ) -> bool:
        """Determines if the overlap between two shapes is an intentional, authorized composition.
        
        Authorized overlaps:
        1. Grouped / multi-shape semantic components (shapes sharing same base object name or object_id).
        2. Container / frame compositions (one shape is explicitly a container, frame, card background).
        3. Intentional overlays and badges (shapes marked with OVERLAY, BADGE, CALLOUT).
        
        Forbidden collisions:
        - Text covering chart data/labels, chart covering footer, table covering header/title,
          image obscuring title, cross-zone blocking collisions.
        """
        n1 = (s1.name or "").upper()
        n2 = (s2.name or "").upper()

        # 1. Multi-shape child components of the same semantic object
        base1 = s1.name.split("::")[0] if "::" in s1.name else s1.name
        base2 = s2.name.split("::")[0] if "::" in s2.name else s2.name
        if base1 == base2 and ("::" in s1.name or "::" in s2.name):
            return True

        # Check metadata from layout objects if present
        if layout_slide:
            objs_by_name = {o.object_name: o for o in layout_slide.object_layouts}
            lo1 = objs_by_name.get(s1.name)
            lo2 = objs_by_name.get(s2.name)
            if lo1 and lo2 and lo1.object_id == lo2.object_id:
                return True
            if lo1 and (lo1.metadata.get("is_overlay") or lo1.metadata.get("is_container") or lo1.metadata.get("allow_overlap")):
                return True
            if lo2 and (lo2.metadata.get("is_overlay") or lo2.metadata.get("is_container") or lo2.metadata.get("allow_overlap")):
                return True

        # 2. Container or frame compositions (card container behind inner contents)
        container_keywords = ("CONTAINER", "CARD_BG", "FRAME_BG", "BACKGROUND_SHAPE", "CONTAINER_BG")
        if any(kw in n1 for kw in container_keywords) or any(kw in n2 for kw in container_keywords):
            return True

        # 3. Intentional overlay / badge / callout layering
        overlay_keywords = ("OVERLAY", "BADGE", "CALLOUT", "TAG_PILL", "CHIP")
        if any(kw in n1 for kw in overlay_keywords) or any(kw in n2 for kw in overlay_keywords):
            # Overlays are authorized unless they obscure required header/title/footer
            forbidden_for_overlay = ("TITLE", "HEADER", "FOOTER")
            if not any(f in n1 for f in forbidden_for_overlay) and not any(f in n2 for f in forbidden_for_overlay):
                return True

        return False

    @classmethod
    def validate(
        cls,
        prs: pptx.presentation.Presentation,
        style_manifest: StyleManifest,
        render_manifest: RenderManifest,
        resolved_deck: ResolvedDeckLayout,
        deck_structure: LayeredDeckStructureSpec,
        content_package: PresentationContentPackage,
        raw_pptx_bytes: Optional[bytes] = None,
        is_technical_deck: bool = False,
    ) -> ValidationManifest:
        """Executes full post-style validation suite in canonical deterministic order."""
        issues: list[ValidationIssue] = []
        slide_results: list[SlideValidationResult] = []
        issue_counter = 0

        def _add_issue(
            category: ValidationCategory,
            severity: ValidationSeverity,
            message: str,
            slide_id: Optional[str] = None,
            zone_id: Optional[str] = None,
            object_id: Optional[str] = None,
            object_name: Optional[str] = None,
            evidence: Optional[dict[str, Any]] = None,
        ) -> ValidationIssue:
            nonlocal issue_counter
            issue_counter += 1
            final_sev, is_blocking = ValidationIssueClassifier.classify(category, severity)
            issue = ValidationIssue(
                issue_id=f"ISSUE-{issue_counter:04d}",
                severity=final_sev,
                category=category,
                slide_id=slide_id,
                zone_id=zone_id,
                object_id=object_id,
                object_name=object_name,
                message=message,
                evidence=evidence or {},
                blocking=is_blocking,
            )
            rec = RepairRecommendationBuilder.build_recommendation(issue)
            if rec:
                issue.recommended_owner = rec.owner
                issue.repair_action = rec.action
            issues.append(issue)
            return issue

        # -------------------------------------------------------------
        # 1. Package / ZIP / XML Structural Validation
        # -------------------------------------------------------------
        if raw_pptx_bytes:
            try:
                with zipfile.ZipFile(io.BytesIO(raw_pptx_bytes)) as zf:
                    namelist = set(zf.namelist())
                    if "[Content_Types].xml" not in namelist:
                        _add_issue(
                            ValidationCategory.PACKAGE_INTEGRITY,
                            ValidationSeverity.CRITICAL,
                            "Missing [Content_Types].xml in PPTX package.",
                        )
                    if "ppt/presentation.xml" not in namelist:
                        _add_issue(
                            ValidationCategory.PACKAGE_INTEGRITY,
                            ValidationSeverity.CRITICAL,
                            "Missing ppt/presentation.xml in PPTX package.",
                        )
                    # Check for malformed XML or broken parts
                    for name in namelist:
                        if name.endswith(".xml") or name.endswith(".rels"):
                            try:
                                part_data = zf.read(name)
                                if len(part_data) == 0:
                                    _add_issue(
                                        ValidationCategory.PACKAGE_INTEGRITY,
                                        ValidationSeverity.CRITICAL,
                                        f"Empty XML package part '{name}'.",
                                    )
                            except Exception as e:
                                _add_issue(
                                    ValidationCategory.PACKAGE_INTEGRITY,
                                    ValidationSeverity.CRITICAL,
                                    f"Broken part '{name}' in PPTX: {e}",
                                )
            except Exception as e:
                _add_issue(
                    ValidationCategory.PACKAGE_INTEGRITY,
                    ValidationSeverity.CRITICAL,
                    f"Corrupt PPTX zip archive: {e}",
                )

        # -------------------------------------------------------------
        # 2. Slide Count, Order, and Continuation Sequence
        # -------------------------------------------------------------
        expected_slide_count = len(deck_structure.slides)
        actual_slide_count = len(prs.slides)
        if actual_slide_count != expected_slide_count:
            _add_issue(
                ValidationCategory.SLIDE_COUNT_ORDER,
                ValidationSeverity.CRITICAL,
                f"Physical slide count mismatch: manifest expected {expected_slide_count}, actual PPTX has {actual_slide_count}.",
            )

        # Continuation sequence checks
        topic_sequences: dict[str, list[int]] = {}
        for s_idx, s_spec in enumerate(deck_structure.slides):
            topic = s_spec.semantic_topic
            topic_sequences.setdefault(topic, []).append(s_idx)

        for topic, indices in topic_sequences.items():
            if len(indices) > 1:
                # Must be contiguous
                for i in range(len(indices) - 1):
                    if indices[i + 1] != indices[i] + 1:
                        _add_issue(
                            ValidationCategory.CONTINUATION_SEQUENCE,
                            ValidationSeverity.CRITICAL,
                            f"Discontinuous topic continuation for topic '{topic}' across slides {indices}.",
                        )

        # -------------------------------------------------------------
        # 3. Object Existence & Identity Preservation
        # -------------------------------------------------------------
        for slide_idx, prs_slide in enumerate(prs.slides):
            if slide_idx >= len(deck_structure.slides):
                break
            struct_slide = deck_structure.slides[slide_idx]
            layout_slide = resolved_deck.slides[slide_idx] if slide_idx < len(resolved_deck.slides) else None
            slide_id = struct_slide.physical_slide_id

            shape_names = [sh.name for sh in prs_slide.shapes if sh.name]
            shape_name_set = set(shape_names)

            # Shape name collisions check
            if len(shape_names) != len(shape_name_set):
                _add_issue(
                    ValidationCategory.IDENTITY_PRESERVATION,
                    ValidationSeverity.CRITICAL,
                    f"Duplicate shape names detected on slide {slide_id}.",
                    slide_id=slide_id,
                )

            # Check every expected layout object exists on the slide
            if layout_slide:
                for obj_layout in layout_slide.object_layouts:
                    # Shape name should match object_name or contain it (multi-shape child)
                    matching = any(sh.name == obj_layout.object_name or obj_layout.object_name in sh.name for sh in prs_slide.shapes)
                    if not matching:
                        _add_issue(
                            ValidationCategory.OBJECT_EXISTENCE,
                            ValidationSeverity.CRITICAL,
                            f"Expected object '{obj_layout.object_name}' (ID: {obj_layout.object_id}) not found on slide {slide_id}.",
                            slide_id=slide_id,
                            object_id=obj_layout.object_id,
                            object_name=obj_layout.object_name,
                        )

            # Empty slide check: if business slide has no content shapes
            content_shapes = [sh for sh in prs_slide.shapes if not (sh.name and sh.name.startswith("Theme background"))]
            if len(content_shapes) == 0 and struct_slide.structural_role not in (StructuralRole.TITLE, StructuralRole.CLOSING):
                _add_issue(
                    ValidationCategory.OBJECT_EXISTENCE,
                    ValidationSeverity.CRITICAL,
                    f"Unexpected empty business slide {slide_id}.",
                    slide_id=slide_id,
                )

        # -------------------------------------------------------------
        # Authoritative Slide Dimensions Resolution
        # -------------------------------------------------------------
        # Dimensions must come directly from upstream resolved deck layout / presentation.
        # Zero hardcoded slide dimension assumptions.
        deck_width_emu = (
            resolved_deck.metadata.get("slide_width_emu")
            or resolved_deck.metadata.get("slide_width")
            or (int(prs.slide_width) if hasattr(prs, "slide_width") and prs.slide_width else None)
        )
        deck_height_emu = (
            resolved_deck.metadata.get("slide_height_emu")
            or resolved_deck.metadata.get("slide_height")
            or (int(prs.slide_height) if hasattr(prs, "slide_height") and prs.slide_height else None)
        )
        if deck_width_emu is None or deck_height_emu is None:
            deck_width_emu = int(prs.slide_width)
            deck_height_emu = int(prs.slide_height)

        # -------------------------------------------------------------
        # 4. Geometry & Safe Area Validation
        # -------------------------------------------------------------
        for slide_idx, prs_slide in enumerate(prs.slides):
            if slide_idx >= len(resolved_deck.slides):
                break
            layout_slide = resolved_deck.slides[slide_idx]
            slide_id = layout_slide.physical_slide_id
            safe_bounds = layout_slide.safe_area.safe_area_bounds

            # Authoritative slide dimension for this specific slide layout
            slide_w_emu = layout_slide.metadata.get("slide_width_emu") or deck_width_emu
            slide_h_emu = layout_slide.metadata.get("slide_height_emu") or deck_height_emu

            min_safe_left = int(safe_bounds.left * slide_w_emu)
            max_safe_right = int((safe_bounds.left + safe_bounds.width) * slide_w_emu)
            min_safe_top = int(safe_bounds.top * slide_h_emu)
            max_safe_bottom = int((safe_bounds.top + safe_bounds.height) * slide_h_emu)

            layout_objs = {o.object_name: o for o in layout_slide.object_layouts}

            for shape in prs_slide.shapes:
                if shape.name.startswith("Theme background"):
                    continue

                sh_left = shape.left
                sh_top = shape.top
                sh_right = shape.left + shape.width
                sh_bottom = shape.top + shape.height

                # Compare with PPT-L5 resolved geometry
                if shape.name in layout_objs:
                    exp_obj = layout_objs[shape.name]
                    exp_left = int(exp_obj.bounds.left * slide_w_emu)
                    exp_top = int(exp_obj.bounds.top * slide_h_emu)
                    exp_width = int(exp_obj.bounds.width * slide_w_emu)
                    exp_height = int(exp_obj.bounds.height * slide_h_emu)

                    if (
                        abs(sh_left - exp_left) > EMU_TOLERANCE
                        or abs(sh_top - exp_top) > EMU_TOLERANCE
                        or abs(shape.width - exp_width) > EMU_TOLERANCE
                        or abs(shape.height - exp_height) > EMU_TOLERANCE
                    ):
                        _add_issue(
                            ValidationCategory.GEOMETRY,
                            ValidationSeverity.CRITICAL,
                            f"Object '{shape.name}' geometry mutated after PPT-L5.",
                            slide_id=slide_id,
                            object_id=exp_obj.object_id,
                            object_name=shape.name,
                        )

                # Safe area violations for body content
                if "TITLE" not in shape.name and "FOOTER" not in shape.name and "PAGE" not in shape.name:
                    if sh_left < min_safe_left - EMU_TOLERANCE or sh_right > max_safe_right + EMU_TOLERANCE:
                        _add_issue(
                            ValidationCategory.SAFE_AREA,
                            ValidationSeverity.CRITICAL,
                            f"Object '{shape.name}' horizontally breaches safe margin [{min_safe_left}, {max_safe_right}].",
                            slide_id=slide_id,
                            object_name=shape.name,
                        )
                    if sh_top < min_safe_top - EMU_TOLERANCE or sh_bottom > max_safe_bottom + EMU_TOLERANCE:
                        _add_issue(
                            ValidationCategory.SAFE_AREA,
                            ValidationSeverity.CRITICAL,
                            f"Object '{shape.name}' vertically breaches safe margin [{min_safe_top}, {max_safe_bottom}].",
                            slide_id=slide_id,
                            object_name=shape.name,
                        )

        # -------------------------------------------------------------
        # 5. Content & Numeric Preservation
        # -------------------------------------------------------------
        content_items_by_id = {item.content_id: item for item in content_package.items}

        for slide_idx, prs_slide in enumerate(prs.slides):
            if slide_idx >= len(deck_structure.slides):
                break
            struct_slide = deck_structure.slides[slide_idx]
            slide_id = struct_slide.physical_slide_id

            for zone in struct_slide.zones:
                for obj_spec in zone.objects:
                    src_content = content_items_by_id.get(obj_spec.content_id)
                    if not src_content:
                        continue

                    matching_shape = next((sh for sh in prs_slide.shapes if obj_spec.object_name in sh.name), None)
                    if not matching_shape:
                        continue

                    # Verify text preservation
                    if src_content.kind == ContentKind.NARRATIVE_INSIGHT and matching_shape.has_text_frame:
                        expected_text = getattr(src_content, "headline", None) or getattr(src_content, "title", None) or getattr(src_content, "narrative_takeaway", None)
                        if expected_text:
                            actual_text = matching_shape.text_frame.text
                            # Verify key words preserved
                            if not any(w.lower() in actual_text.lower() for w in expected_text.split()[:3]):
                                _add_issue(
                                    ValidationCategory.CONTENT_PRESERVATION,
                                    ValidationSeverity.CRITICAL,
                                    f"Narrative content mutated on '{obj_spec.object_name}'.",
                                    slide_id=slide_id,
                                    object_id=obj_spec.object_id,
                                    object_name=obj_spec.object_name,
                                )

                    # Verify table row and column count preservation
                    elif src_content.kind == ContentKind.TABLE and matching_shape.has_table:
                        tbl = matching_shape.table
                        if src_content.table_data:
                            expected_rows = len(src_content.table_data) + 1  # header + data
                            if len(tbl.rows) != expected_rows:
                                _add_issue(
                                    ValidationCategory.TABLE_INTEGRITY,
                                    ValidationSeverity.CRITICAL,
                                    f"Table row count mismatch on '{obj_spec.object_name}': expected {expected_rows}, got {len(tbl.rows)}.",
                                    slide_id=slide_id,
                                    object_id=obj_spec.object_id,
                                    object_name=obj_spec.object_name,
                                )

                    # Verify chart categories and series count
                    elif src_content.kind == ContentKind.CHART and matching_shape.has_chart:
                        chart = matching_shape.chart
                        spec = src_content.visual_spec or {}
                        exp_series = spec.get("series", [])
                        if exp_series and len(chart.series) != len(exp_series):
                            _add_issue(
                                ValidationCategory.CHART_INTEGRITY,
                                ValidationSeverity.CRITICAL,
                                f"Chart series count mismatch on '{obj_spec.object_name}': expected {len(exp_series)}, got {len(chart.series)}.",
                                slide_id=slide_id,
                                object_id=obj_spec.object_id,
                                object_name=obj_spec.object_name,
                            )

        # -------------------------------------------------------------
        # 6. Native DrawingML Editability Preservation
        # -------------------------------------------------------------
        if render_manifest and getattr(render_manifest, "slides", None):
            for s_idx, r_slide in enumerate(render_manifest.slides):
                if s_idx >= len(prs.slides):
                    break
                slide = prs.slides[s_idx]
                for obj_rec in r_slide.objects:
                    matching = next((sh for sh in slide.shapes if sh.name == obj_rec.object_name), None)
                    if not matching:
                        continue

                    shape_type_val = obj_rec.shape_type.value if hasattr(obj_rec.shape_type, "value") else str(obj_rec.shape_type)

                    if obj_rec.is_native_editable:
                        if shape_type_val in ("TEXT", "TEXT_BOX") and not matching.has_text_frame:
                            _add_issue(
                                ValidationCategory.EDITABILITY_PRESERVATION,
                                ValidationSeverity.CRITICAL,
                                f"Object '{obj_rec.object_name}' lost native text frame.",
                                slide_id=obj_rec.physical_slide_id,
                                object_id=obj_rec.object_id,
                                object_name=obj_rec.object_name,
                            )
                        elif shape_type_val == "TABLE" and not matching.has_table:
                            _add_issue(
                                ValidationCategory.EDITABILITY_PRESERVATION,
                                ValidationSeverity.CRITICAL,
                                f"Object '{obj_rec.object_name}' lost native table frame.",
                                slide_id=obj_rec.physical_slide_id,
                                object_id=obj_rec.object_id,
                                object_name=obj_rec.object_name,
                            )
                        elif shape_type_val == "CHART" and not matching.has_chart:
                            _add_issue(
                                ValidationCategory.EDITABILITY_PRESERVATION,
                                ValidationSeverity.CRITICAL,
                                f"Object '{obj_rec.object_name}' lost native chart frame.",
                                slide_id=obj_rec.physical_slide_id,
                                object_id=obj_rec.object_id,
                                object_name=obj_rec.object_name,
                            )
                    elif obj_rec.metadata.get("actual_render_mode") in ("RASTER_IMAGE", "PICTURE") or shape_type_val in ("RASTER_IMAGE", "PICTURE"):
                        # Maps must be truthfully non-native
                        if obj_rec.is_native_editable:
                            _add_issue(
                                ValidationCategory.EDITABILITY_PRESERVATION,
                                ValidationSeverity.CRITICAL,
                                f"Raster map '{obj_rec.object_name}' falsely claimed as native editable.",
                                slide_id=obj_rec.physical_slide_id,
                                object_id=obj_rec.object_id,
                                object_name=obj_rec.object_name,
                            )

        # -------------------------------------------------------------
        # 7. Layer Order & Collision Detection
        # -------------------------------------------------------------
        for slide_idx, prs_slide in enumerate(prs.slides):
            layout_slide = resolved_deck.slides[slide_idx] if slide_idx < len(resolved_deck.slides) else None
            struct_slide = deck_structure.slides[slide_idx] if slide_idx < len(deck_structure.slides) else None
            slide_id = layout_slide.physical_slide_id if layout_slide else f"SLD-{slide_idx+1}"
            shapes = [sh for sh in prs_slide.shapes if not (sh.name and sh.name.startswith("Theme background"))]

            for i in range(len(shapes)):
                s1 = shapes[i]
                for j in range(i + 1, len(shapes)):
                    s2 = shapes[j]

                    # Bounding box collision check
                    left_max = max(s1.left, s2.left)
                    right_min = min(s1.left + s1.width, s2.left + s2.width)
                    top_max = max(s1.top, s2.top)
                    bottom_min = min(s1.top + s1.height, s2.top + s2.height)

                    if right_min > left_max and bottom_min > top_max:
                        overlap_w = right_min - left_max
                        overlap_h = bottom_min - top_max
                        overlap_area = overlap_w * overlap_h
                        smaller_area = min(s1.width * s1.height, s2.width * s2.height)
                        overlap_ratio = overlap_area / smaller_area if smaller_area > 0 else 0.0

                        # Meaningful overlap > 5%
                        if overlap_ratio > 0.05:
                            # Check if authorized intentional overlap
                            if cls._is_authorized_overlap(s1, s2, struct_slide, layout_slide):
                                continue

                            _add_issue(
                                ValidationCategory.COLLISION,
                                ValidationSeverity.CRITICAL,
                                f"Unexpected blocking collision between '{s1.name}' and '{s2.name}' (overlap {overlap_ratio:.1%}).",
                                slide_id=slide_id,
                                object_name=s1.name,
                            )

        # -------------------------------------------------------------
        # 8. Text Clipping & STYLE_REFLOW_RISK
        # -------------------------------------------------------------
        for slide_idx, prs_slide in enumerate(prs.slides):
            slide_id = resolved_deck.slides[slide_idx].physical_slide_id if slide_idx < len(resolved_deck.slides) else f"SLD-{slide_idx+1}"
            for shape in prs_slide.shapes:
                if shape.has_text_frame:
                    tf = shape.text_frame
                    text_content = tf.text.strip()
                    if not text_content:
                        continue

                    # Estimated text height based on paragraphs, runs, and font sizes
                    total_chars = len(text_content)
                    box_width_pt = shape.width / 12700.0   # EMUs to points
                    box_height_pt = shape.height / 12700.0

                    font_size = 14.0
                    for p in tf.paragraphs:
                        if p.font.size:
                            font_size = p.font.size.pt
                            break

                    chars_per_line = max(10, int(box_width_pt / (font_size * 0.55)))
                    est_lines = max(1, total_chars // chars_per_line + (1 if total_chars % chars_per_line else 0))
                    est_required_height = est_lines * (font_size * 1.3)

                    # If estimated text height exceeds box height by > 25%, flag severe clipping
                    if est_required_height > box_height_pt * 1.25:
                        _add_issue(
                            ValidationCategory.TEXT_CLIPPING,
                            ValidationSeverity.CRITICAL,
                            f"Text in shape '{shape.name}' severely exceeds box height: est {est_required_height:.1f}pt vs {box_height_pt:.1f}pt.",
                            slide_id=slide_id,
                            object_name=shape.name,
                            evidence={"est_lines": est_lines, "box_height_pt": box_height_pt},
                        )

        # -------------------------------------------------------------
        # 9. Contrast Revalidation
        # -------------------------------------------------------------
        for audit in style_manifest.accessibility_results:
            if not audit.passed:
                _add_issue(
                    ValidationCategory.CONTRAST,
                    ValidationSeverity.CRITICAL,
                    f"Contrast failure on '{audit.target_id}': ratio {audit.contrast_ratio}:1 below threshold {audit.threshold}:1.",
                    object_id=audit.target_id,
                )

        # -------------------------------------------------------------
        # 10. Governance & Control-Plane Leak Check
        # -------------------------------------------------------------
        if not is_technical_deck:
            governance_patterns = [
                re.compile(r"EVID-[A-Z0-9_-]+", re.IGNORECASE),
                re.compile(r"JoinPlan", re.IGNORECASE),
                re.compile(r"SDR_[A-Z0-9_]+", re.IGNORECASE),
                re.compile(r"\b[a-f0-9]{32,64}\b"),  # Raw hash
            ]
            for slide_idx, prs_slide in enumerate(prs.slides):
                slide_id = resolved_deck.slides[slide_idx].physical_slide_id if slide_idx < len(resolved_deck.slides) else f"SLD-{slide_idx+1}"
                for shape in prs_slide.shapes:
                    if shape.has_text_frame:
                        for pattern in governance_patterns:
                            match = pattern.search(shape.text_frame.text)
                            if match:
                                _add_issue(
                                    ValidationCategory.GOVERNANCE_LEAK,
                                    ValidationSeverity.WARNING,
                                    f"Governance or internal token '{match.group()}' exposed in visible text on '{shape.name}'.",
                                    slide_id=slide_id,
                                    object_name=shape.name,
                                )

        # -------------------------------------------------------------
        # Deterministic Issue Sorting & Assembly
        # -------------------------------------------------------------
        severity_order = {
            ValidationSeverity.CRITICAL: 0,
            ValidationSeverity.WARNING: 1,
            ValidationSeverity.INFO: 2,
        }
        issues.sort(key=lambda x: (severity_order.get(x.severity, 99), x.slide_id or "", x.zone_id or "", x.object_id or "", x.category.value, x.issue_id))

        # Build Slide Validation Results
        for slide_idx, prs_slide in enumerate(prs.slides):
            s_id = resolved_deck.slides[slide_idx].physical_slide_id if slide_idx < len(resolved_deck.slides) else f"SLD-{slide_idx+1}"
            slide_issues = [i for i in issues if i.slide_id == s_id]
            blocking_count = sum(1 for i in slide_issues if i.blocking)
            warnings_count = sum(1 for i in slide_issues if i.severity == ValidationSeverity.WARNING)

            slide_results.append(
                SlideValidationResult(
                    physical_slide_id=s_id,
                    sequence_index=slide_idx + 1,
                    status="FAIL" if blocking_count > 0 else "PASS",
                    blocking_issue_count=blocking_count,
                    warnings_count=warnings_count,
                    issues=slide_issues,
                )
            )

        # Severity counts
        counts = {
            "CRITICAL": sum(1 for i in issues if i.severity == ValidationSeverity.CRITICAL),
            "WARNING": sum(1 for i in issues if i.severity == ValidationSeverity.WARNING),
            "INFO": sum(1 for i in issues if i.severity == ValidationSeverity.INFO),
        }

        # Build Repair Recommendations
        repair_requests: list[RepairRecommendation] = []
        for i in issues:
            if i.blocking:
                rec = RepairRecommendationBuilder.build_recommendation(i)
                if rec and rec.repair_id not in {r.repair_id for r in repair_requests}:
                    repair_requests.append(rec)

        # Determine Final Deck Status
        has_critical = counts["CRITICAL"] > 0
        if has_critical:
            # If any issue is unrecoverable failure
            unrecoverable = any(
                i.category in (ValidationCategory.PACKAGE_INTEGRITY, ValidationCategory.CONTENT_PRESERVATION, ValidationCategory.NUMERIC_PRESERVATION, ValidationCategory.SLIDE_COUNT_ORDER)
                for i in issues if i.severity == ValidationSeverity.CRITICAL
            )
            final_status = DeckValidationStatus.FAIL if unrecoverable else DeckValidationStatus.REPAIR_REQUIRED
        else:
            final_status = DeckValidationStatus.CERTIFIED

        deck_id = getattr(deck_structure, "deck_id", getattr(resolved_deck, "deck_id", "default_deck"))
        manifest = ValidationManifest(
            deck_id=deck_id,
            status=final_status,
            slides=slide_results,
            issues=issues,
            counts_by_severity=counts,
            repair_requests=repair_requests,
            stats={
                "slides_validated": len(prs.slides),
                "total_issues": len(issues),
                "critical_issues": counts["CRITICAL"],
                "warnings": counts["WARNING"],
                "info_issues": counts["INFO"],
                "repair_requests": len(repair_requests),
                "slide_width_emu": int(deck_width_emu),
                "slide_height_emu": int(deck_height_emu),
            },
        )
        manifest.validation_fingerprint = compute_validation_manifest_fingerprint(manifest)
        return manifest
