"""HighView Presentation Studio — PPT-L6 Renderer Validator.

Performs strict, programmatic validation of compiled PowerPoint presentations:
1. Package integrity: valid zip archive, valid OOXML [Content_Types].xml, opens cleanly in python-pptx.
2. Slide count invariant: len(prs.slides) == len(manifest.slides) == len(resolved_deck.slides). (0 physical slide creation).
3. Zero content dropped: len(prs.shapes) == len(slide.object_layouts) for every slide.
4. Selection Pane names: shape.name exactly matches object_name.
5. ID separation: PowerPoint internal shape.shape_id is an integer distinct from HighView object_id.
6. Native DrawingML editability:
   - Text boxes satisfy shape.has_text_frame == True.
   - Tables satisfy shape.has_table == True.
   - Charts satisfy shape.has_chart == True.
7. Zero silent downgrades: NATIVE_REQUIRED objects must never degrade to raster.
8. Truthful non-native rendering: MAP objects use RASTER_ALLOWED and is_native_editable == False.
9. Geometry preservation: applied bounds match resolved bounds.
"""

from __future__ import annotations

import logging
import os
import zipfile
from pathlib import Path
from typing import Optional

import pptx

from app.services.presentation.content_models import ContentKind
from app.services.presentation.layer_zone_models import (
    EditabilityPolicy,
    LayeredDeckStructureSpec,
)
from app.services.presentation.layout_models import ResolvedDeckLayout
from app.services.presentation.render_models import (
    RenderManifest,
    ShapeType,
)

logger = logging.getLogger(__name__)


class RendererValidationError(Exception):
    """Raised when presentation package or audit manifest violates PPT-L6 invariants."""
    pass


class RendererValidator:
    """Architectural validator for PPT-L6 compiled PowerPoint presentations."""

    def validate_manifest_and_package(
        self,
        manifest: RenderManifest,
        resolved_deck: ResolvedDeckLayout,
        deck_structure: LayeredDeckStructureSpec,
    ) -> None:
        """Runs the complete suite of programmatic PPTX and manifest integrity checks."""
        pptx_path = Path(manifest.pptx_path)

        # 1. Package existence and size
        if not pptx_path.exists() or not pptx_path.is_file():
            raise RendererValidationError(f"Generated PPTX file not found at: {pptx_path}")

        file_size = pptx_path.stat().st_size
        if file_size <= 0:
            raise RendererValidationError(f"Generated PPTX file is empty (0 bytes): {pptx_path}")

        # 2. Structural zip inspection
        try:
            with zipfile.ZipFile(pptx_path, "r") as z:
                namelist = z.namelist()
                if "[Content_Types].xml" not in namelist:
                    raise RendererValidationError("PPTX package is missing '[Content_Types].xml'")
                if "ppt/presentation.xml" not in namelist:
                    raise RendererValidationError("PPTX package is missing 'ppt/presentation.xml'")
                for idx in range(1, len(resolved_deck.slides) + 1):
                    slide_part = f"ppt/slides/slide{idx}.xml"
                    if slide_part not in namelist:
                        raise RendererValidationError(f"PPTX package is missing expected slide part: {slide_part}")
        except zipfile.BadZipFile as bzf:
            raise RendererValidationError(f"Generated PPTX is not a valid zip archive: {bzf}") from bzf

        # 3. Programmatic presentation load
        try:
            prs = pptx.Presentation(str(pptx_path))
        except Exception as exc:
            raise RendererValidationError(f"Generated PPTX failed programmatic presentation load: {exc}") from exc

        # 4. Slide count invariant (Zero physical slide creation in PPT-L6)
        expected_slide_count = len(resolved_deck.slides)
        if len(prs.slides) != expected_slide_count:
            raise RendererValidationError(
                f"Slide count mismatch: PPTX has {len(prs.slides)} slides, expected {expected_slide_count}"
            )
        if len(manifest.slides) != expected_slide_count:
            raise RendererValidationError(
                f"Manifest slide count mismatch: manifest has {len(manifest.slides)}, expected {expected_slide_count}"
            )
        if len(deck_structure.slides) != expected_slide_count:
            raise RendererValidationError(
                f"Structure slide count mismatch: structure has {len(deck_structure.slides)}, expected {expected_slide_count}"
            )

        # 5. Object count and content integrity
        if manifest.total_objects_rendered != resolved_deck.total_objects:
            raise RendererValidationError(
                f"Total object count mismatch: manifest has {manifest.total_objects_rendered}, "
                f"resolved layout has {resolved_deck.total_objects}"
            )

        # 6. Per-slide and per-shape inspections
        for slide_idx, prs_slide in enumerate(prs.slides):
            res_slide = resolved_deck.slides[slide_idx]
            manifest_slide = manifest.slides[slide_idx]

            if len(prs_slide.shapes) != len(res_slide.object_layouts):
                raise RendererValidationError(
                    f"Slide {slide_idx + 1} shape count mismatch: PPTX has {len(prs_slide.shapes)}, "
                    f"expected {len(res_slide.object_layouts)}"
                )

            # Map shapes by shape.name
            shape_by_name = {s.name: s for s in prs_slide.shapes}

            for obj_idx, obj_layout in enumerate(res_slide.object_layouts):
                obj_record = manifest_slide.objects[obj_idx]

                # Selection Pane contract: shape.name == object_name
                if obj_layout.object_name not in shape_by_name:
                    raise RendererValidationError(
                        f"Slide {slide_idx + 1}: Shape name '{obj_layout.object_name}' not found in PPTX shapes"
                    )

                shape = shape_by_name[obj_layout.object_name]

                # ID separation: shape.shape_id is an integer, distinct from HighView object_id
                if not isinstance(shape.shape_id, int):
                    raise RendererValidationError(
                        f"Shape ID for '{shape.name}' must be an integer, got: {type(shape.shape_id)}"
                    )
                if str(shape.shape_id) == obj_layout.object_id:
                    raise RendererValidationError(
                        f"Shape ID for '{shape.name}' unexpectedly equals semantic object_id '{obj_layout.object_id}'"
                    )

                # DrawingML native editability checks
                if obj_record.is_native_editable:
                    if obj_record.shape_type == ShapeType.TEXT_BOX:
                        if not getattr(shape, "has_text_frame", False):
                            raise RendererValidationError(
                                f"Object '{obj_layout.object_id}' declared native editable TEXT_BOX but lacks has_text_frame"
                            )
                    elif obj_record.shape_type == ShapeType.TABLE:
                        if not getattr(shape, "has_table", False):
                            raise RendererValidationError(
                                f"Object '{obj_layout.object_id}' declared native editable TABLE but lacks has_table"
                            )
                    elif obj_record.shape_type == ShapeType.CHART:
                        if not getattr(shape, "has_chart", False):
                            raise RendererValidationError(
                                f"Object '{obj_layout.object_id}' declared native editable CHART but lacks has_chart"
                            )

                # Zero silent downgrades check
                if obj_layout.editability == EditabilityPolicy.NATIVE_REQUIRED:
                    if obj_record.fallback_applied:
                        raise RendererValidationError(
                            f"Object '{obj_layout.object_id}' has NATIVE_REQUIRED policy but fallback was applied: {obj_record.fallback_reason}"
                        )
                    if not obj_record.is_native_editable:
                        raise RendererValidationError(
                            f"Object '{obj_layout.object_id}' has NATIVE_REQUIRED policy but was rendered non-editable"
                        )

                # Truthful non-native map check
                if obj_layout.kind == ContentKind.MAP:
                    if obj_layout.editability != EditabilityPolicy.RASTER_ALLOWED:
                        raise RendererValidationError(
                            f"Map object '{obj_layout.object_id}' must use RASTER_ALLOWED, got {obj_layout.editability}"
                        )
                    if obj_record.is_native_editable:
                        raise RendererValidationError(
                            f"Map object '{obj_layout.object_id}' must truthfully be non-native editable"
                        )
                    if obj_record.shape_type != ShapeType.PICTURE:
                        raise RendererValidationError(
                            f"Map object '{obj_layout.object_id}' must render as PICTURE, got {obj_record.shape_type}"
                        )

                # Applied bounds check
                tol = 1e-4
                b1 = obj_record.applied_bounds
                b2 = obj_layout.bounds
                if (
                    abs(b1.left - b2.left) > tol
                    or abs(b1.top - b2.top) > tol
                    or abs(b1.width - b2.width) > tol
                    or abs(b1.height - b2.height) > tol
                ):
                    raise RendererValidationError(
                        f"Geometry mismatch for object '{obj_layout.object_id}': layout bounds {b2} != applied bounds {b1}"
                    )

        logger.info("Programmatic validation PASSED for presentation: %s (%d slides)", pptx_path.name, expected_slide_count)
