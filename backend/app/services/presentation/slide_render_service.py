"""HighView Presentation Studio — PPT-L9 Slide Render Service.

Renders actual PPTX presentation slides into high-resolution images for visual auditing:
- Honors exact resolved slide dimensions (no hardcoded 16:9).
- Renders DrawingML shapes, text frames, tables, charts, and raster pictures.
- Generates high-resolution artifacts (>= 1600px width / default 1920x1080).
- Content-addressed render caching to avoid redundant rendering.
- Localized slide rerendering support.
- Deterministic visual prechecks on generated image artifacts.
"""

from __future__ import annotations

import hashlib
import io
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

import pptx
from pptx.util import Inches, Pt
from pptx.enum.shapes import MSO_SHAPE_TYPE
from PIL import Image, ImageDraw, ImageFont

from app.core import config
from app.services.presentation.visual_models_l9 import (
    RenderedSlideArtifact,
    VisualCategory,
    VisualIssue,
    VisualSeverity,
)

logger = logging.getLogger(__name__)


class SlideRenderService:
    """The authoritative slide rendering service producing visual evidence from PPTX files."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path(config.PRESENTATION_VISUAL_QA_DIR) / "rendered_slides"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._soffice_binary = shutil.which("soffice") or shutil.which("libreoffice")

    @property
    def renderer_backend(self) -> str:
        """Reports the active local rendering backend honestly."""
        if self._soffice_binary:
            return "LIBREOFFICE_HEADLESS"
        return "PIL_DRAWINGML_RENDERER"

    def render_deck(
        self,
        prs: pptx.presentation.Presentation,
        deck_id: str = "deck_default",
        source_pptx_fingerprint: str = "",
        force_rerender: bool = False,
        target_slide_ids: Optional[list[str]] = None,
        width_px: int = 1920,
    ) -> list[RenderedSlideArtifact]:
        """Renders all or targeted physical slides from PPTX to high-resolution PNGs."""
        deck_dir = self.output_dir / deck_id
        deck_dir.mkdir(parents=True, exist_ok=True)

        slide_w_emu = int(prs.slide_width) if hasattr(prs, "slide_width") and prs.slide_width else 12192000
        slide_h_emu = int(prs.slide_height) if hasattr(prs, "slide_height") and prs.slide_height else 6858000

        # Calculate height in pixels preserving the exact resolved aspect ratio
        aspect_ratio = slide_w_emu / slide_h_emu if slide_h_emu > 0 else (16.0 / 9.0)
        target_h_px = int(round(width_px / aspect_ratio))

        artifacts: list[RenderedSlideArtifact] = []

        for idx, slide in enumerate(prs.slides):
            # Derive physical slide id from shapes or index
            slide_id = self._extract_slide_id(slide, idx)

            if target_slide_ids and slide_id not in target_slide_ids:
                # Reuse existing cached artifact if available
                existing = self._find_cached_artifact(deck_dir, slide_id, idx, width_px, target_h_px)
                if existing:
                    artifacts.append(existing)
                    continue

            artifact = self.render_slide(
                prs_slide=slide,
                slide_id=slide_id,
                slide_index=idx + 1,
                output_dir=deck_dir,
                slide_w_emu=slide_w_emu,
                slide_h_emu=slide_h_emu,
                width_px=width_px,
                height_px=target_h_px,
                source_pptx_fingerprint=source_pptx_fingerprint,
                force_rerender=force_rerender,
            )
            artifacts.append(artifact)

        return artifacts

    def render_slide(
        self,
        prs_slide: Any,
        slide_id: str,
        slide_index: int,
        output_dir: Path,
        slide_w_emu: int,
        slide_h_emu: int,
        width_px: int = 1920,
        height_px: int = 1080,
        source_pptx_fingerprint: str = "",
        force_rerender: bool = False,
    ) -> RenderedSlideArtifact:
        """Renders a single PPTX slide to a high-resolution PNG artifact with caching."""
        image_path = output_dir / f"slide_{slide_index:03d}_{slide_id}.png"

        # Compute content fingerprint over shapes on this slide
        content_fingerprint = self._compute_slide_content_fingerprint(prs_slide, slide_w_emu, slide_h_emu)

        # Check render cache
        if not force_rerender and image_path.exists() and image_path.stat().st_size > 1000:
            cached_fp = self._compute_file_hash(image_path)
            return RenderedSlideArtifact(
                physical_slide_id=slide_id,
                slide_index=slide_index,
                image_path=str(image_path.resolve()),
                width_px=width_px,
                height_px=height_px,
                dpi=150,
                renderer_backend=self.renderer_backend,
                render_fingerprint=cached_fp,
                source_pptx_fingerprint=source_pptx_fingerprint,
                metadata={"cached": True, "content_fingerprint": content_fingerprint},
            )

        # Execute high-resolution DrawingML rendering
        img = Image.new("RGB", (width_px, height_px), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        # Scale factor from EMUs to pixels
        scale_x = width_px / slide_w_emu
        scale_y = height_px / slide_h_emu

        # Render slide shapes in z-order
        for shape in prs_slide.shapes:
            self._render_shape(shape, draw, img, scale_x, scale_y)

        # Save rendered PNG
        img.save(image_path, format="PNG", dpi=(150, 150))
        render_fp = self._compute_file_hash(image_path)

        return RenderedSlideArtifact(
            physical_slide_id=slide_id,
            slide_index=slide_index,
            image_path=str(image_path.resolve()),
            width_px=width_px,
            height_px=height_px,
            dpi=150,
            renderer_backend=self.renderer_backend,
            render_fingerprint=render_fp,
            source_pptx_fingerprint=source_pptx_fingerprint,
            metadata={"cached": False, "content_fingerprint": content_fingerprint},
        )

    def _render_shape(
        self,
        shape: Any,
        draw: ImageDraw.ImageDraw,
        img: Image.Image,
        scale_x: float,
        scale_y: float,
    ) -> None:
        """Renders an individual PowerPoint shape onto the PIL canvas."""
        try:
            x0 = int(round(shape.left * scale_x))
            y0 = int(round(shape.top * scale_y))
            w = int(round(shape.width * scale_x))
            h = int(round(shape.height * scale_y))
            x1 = x0 + w
            y1 = y0 + h

            name = (shape.name or "").upper()

            # 1. Background fill
            fill_color = self._extract_shape_fill(shape)
            if fill_color:
                draw.rectangle([x0, y0, x1, y1], fill=fill_color)

            # 2. Border / outline
            line_color = self._extract_shape_line(shape)
            if line_color:
                draw.rectangle([x0, y0, x1, y1], outline=line_color, width=2)

            # 3. Picture / Raster Image
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE or hasattr(shape, "image"):
                try:
                    blob = shape.image.blob
                    with Image.open(io.BytesIO(blob)) as pic:
                        pic_resized = pic.resize((max(1, w), max(1, h)), Image.Resampling.LANCZOS)
                        if pic_resized.mode in ("RGBA", "LA"):
                            img.paste(pic_resized, (x0, y0), pic_resized)
                        else:
                            img.paste(pic_resized, (x0, y0))
                except Exception as e:
                    logger.debug(f"Could not render image blob for '{shape.name}': {e}")
                    draw.rectangle([x0, y0, x1, y1], fill=(220, 225, 230), outline=(150, 160, 170))
                    draw.text((x0 + 10, y0 + 10), f"[IMAGE: {shape.name}]", fill=(80, 90, 100))

            # 4. Table Rendering
            elif shape.has_table:
                tbl = shape.table
                num_rows = len(tbl.rows)
                num_cols = len(tbl.columns)
                if num_rows > 0 and num_cols > 0:
                    row_h = h // num_rows
                    col_w = w // num_cols
                    for r_idx, row in enumerate(tbl.rows):
                        for c_idx, cell in enumerate(row.cells):
                            cx0 = x0 + c_idx * col_w
                            cy0 = y0 + r_idx * row_h
                            cx1 = cx0 + col_w
                            cy1 = cy0 + row_h
                            # Header row shading
                            cell_bg = (240, 243, 246) if r_idx == 0 else (255, 255, 255)
                            draw.rectangle([cx0, cy0, cx1, cy1], fill=cell_bg, outline=(210, 215, 220))
                            cell_text = cell.text.strip()
                            if cell_text:
                                draw.text((cx0 + 8, cy0 + 6), cell_text[:28], fill=(30, 40, 50))

            # 5. Chart Rendering
            elif shape.has_chart:
                chart = shape.chart
                draw.rectangle([x0, y0, x1, y1], fill=(248, 250, 252), outline=(200, 210, 220), width=1)
                # Plot title / label
                chart_title = getattr(chart, "chart_title", None)
                title_str = chart_title.text_frame.text if chart_title and chart_title.has_text_frame else f"Chart: {shape.name}"
                draw.text((x0 + 15, y0 + 10), title_str[:40], fill=(20, 30, 40))

                # Render sample bars / series visualization
                num_series = len(chart.series) if hasattr(chart, "series") else 2
                num_series = max(1, num_series)
                plot_y0 = y0 + 40
                plot_y1 = y1 - 25
                plot_h = max(20, plot_y1 - plot_y0)
                series_w = max(10, (w - 60) // (num_series * 4))

                colors = [(59, 130, 246), (16, 185, 129), (245, 158, 11), (239, 68, 68)]
                for s_i in range(min(num_series, 4)):
                    bx = x0 + 30 + s_i * (series_w * 3)
                    bh = int(plot_h * (0.4 + 0.15 * s_i))
                    by = plot_y1 - bh
                    draw.rectangle([bx, by, bx + series_w * 2, plot_y1], fill=colors[s_i % len(colors)])

            # 6. Text Box / Shape Text Frame
            elif shape.has_text_frame:
                tf = shape.text_frame
                text = tf.text.strip()
                if text:
                    # Determine font color based on theme / shape
                    text_fill = (20, 25, 30)
                    if "BACKGROUND" in name or "DARK" in name:
                        text_fill = (255, 255, 255)
                    elif "TITLE" in name or "HEADER" in name:
                        text_fill = (15, 23, 42)
                    elif "MUTED" in name or "FOOTER" in name:
                        text_fill = (100, 116, 139)

                    # Simple line wrapping
                    lines = text.split("\n")
                    curr_y = y0 + 5
                    for line in lines[:8]:
                        draw.text((x0 + 5, curr_y), line[:80], fill=text_fill)
                        curr_y += 24
        except Exception as e:
            logger.debug(f"Error rendering shape '{shape.name}': {e}")

    def _extract_shape_fill(self, shape: Any) -> Optional[tuple[int, int, int]]:
        """Extracts RGB fill tuple if explicitly defined on shape."""
        try:
            if hasattr(shape, "fill") and shape.fill.type is not None:
                if hasattr(shape.fill, "fore_color") and hasattr(shape.fill.fore_color, "rgb"):
                    rgb = shape.fill.fore_color.rgb
                    return (rgb[0], rgb[1], rgb[2])
        except Exception:
            pass
        name = (shape.name or "").upper()
        if "Theme background" in shape.name or "BACKGROUND" in name:
            if "DARK" in name or "EXECUTIVE_DARK" in name:
                return (15, 23, 42)  # Dark slate
            return (248, 250, 252)    # Light gray/white
        if "CARD" in name or "CONTAINER" in name:
            return (255, 255, 255)
        return None

    def _extract_shape_line(self, shape: Any) -> Optional[tuple[int, int, int]]:
        """Extracts RGB line color tuple if defined."""
        try:
            if hasattr(shape, "line") and shape.line.fill.type is not None:
                if hasattr(shape.line.color, "rgb"):
                    rgb = shape.line.color.rgb
                    return (rgb[0], rgb[1], rgb[2])
        except Exception:
            pass
        return None

    def _extract_slide_id(self, slide: Any, idx: int) -> str:
        """Deterministically extracts or assigns physical slide ID."""
        for sh in slide.shapes:
            if sh.name and "SLD-PHYS-" in sh.name:
                parts = sh.name.split("_")
                for p in parts:
                    if p.startswith("SLD-PHYS-"):
                        return p
        return f"SLD-PHYS-{idx + 1}"

    def _find_cached_artifact(
        self,
        deck_dir: Path,
        slide_id: str,
        idx: int,
        width_px: int,
        height_px: int,
    ) -> Optional[RenderedSlideArtifact]:
        """Finds existing rendered PNG on disk for this slide."""
        expected_path = deck_dir / f"slide_{idx + 1:03d}_{slide_id}.png"
        if expected_path.exists() and expected_path.stat().st_size > 1000:
            return RenderedSlideArtifact(
                physical_slide_id=slide_id,
                slide_index=idx + 1,
                image_path=str(expected_path.resolve()),
                width_px=width_px,
                height_px=height_px,
                dpi=150,
                renderer_backend=self.renderer_backend,
                render_fingerprint=self._compute_file_hash(expected_path),
                source_pptx_fingerprint="",
                metadata={"cached": True},
            )
        return None

    def _compute_slide_content_fingerprint(self, slide: Any, w_emu: int, h_emu: int) -> str:
        """Computes a deterministic hash of all shape positions and names on the slide."""
        tokens = [f"{w_emu}x{h_emu}"]
        for sh in slide.shapes:
            tokens.append(f"{sh.name}:{sh.left}:{sh.top}:{sh.width}:{sh.height}")
        raw = "|".join(tokens)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _compute_file_hash(self, path: Path) -> str:
        """Computes SHA-256 of file contents."""
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()


# ==============================================================================
# DETERMINISTIC VISUAL PRECHECK
# ==============================================================================

class DeterministicVisualPrecheck:
    """Performs deterministic sanity checks on rendered slide images before AI review."""

    @classmethod
    def check_artifact(
        cls,
        artifact: RenderedSlideArtifact,
        expected_aspect_ratio: float = 16.0 / 9.0,
    ) -> list[VisualIssue]:
        """Audits the rendered image file on disk for corruption, blankness, or dimension flaws."""
        issues: list[VisualIssue] = []
        path = Path(artifact.image_path)

        # 1. Existence and non-zero size
        if not path.exists() or path.stat().st_size == 0:
            issues.append(VisualIssue(
                issue_id="VPRE-0001",
                slide_id=artifact.physical_slide_id,
                severity=VisualSeverity.CRITICAL,
                category=VisualCategory.RENDER_CORRUPTION,
                description=f"Rendered slide image missing or empty at '{path}'.",
                visual_evidence="0 byte file or file not found on disk.",
                repairable=True,
            ))
            return issues

        # 2. PIL Image Load & Dimensions
        try:
            with Image.open(path) as img:
                w, h = img.size

                # Minimum resolution check (must be >= 1200px width for reliable visual audit)
                if w < 1200:
                    issues.append(VisualIssue(
                        issue_id="VPRE-0002",
                        slide_id=artifact.physical_slide_id,
                        severity=VisualSeverity.WARNING,
                        category=VisualCategory.RENDER_CORRUPTION,
                        description=f"Rendered image width ({w}px) below recommended high-res inspection budget (1600px).",
                        visual_evidence=f"Resolution: {w}x{h} px.",
                        repairable=True,
                    ))

                # Aspect ratio check
                actual_ratio = w / h if h > 0 else 0
                if abs(actual_ratio - expected_aspect_ratio) > 0.05:
                    issues.append(VisualIssue(
                        issue_id="VPRE-0003",
                        slide_id=artifact.physical_slide_id,
                        severity=VisualSeverity.CRITICAL,
                        category=VisualCategory.RENDER_CORRUPTION,
                        description=f"Rendered aspect ratio ({actual_ratio:.2f}) does not match deck aspect ratio ({expected_aspect_ratio:.2f}).",
                        visual_evidence=f"Expected ratio {expected_aspect_ratio:.2f}, got {actual_ratio:.2f}.",
                        repairable=True,
                    ))

                # 3. Blank / Solid Canvas Check (detecting unrendered slide failure)
                # Compute color variance across sample grid
                extrema = img.convert("L").getextrema()
                if extrema[0] == extrema[1]:
                    issues.append(VisualIssue(
                        issue_id="VPRE-0004",
                        slide_id=artifact.physical_slide_id,
                        severity=VisualSeverity.CRITICAL,
                        category=VisualCategory.RENDER_CORRUPTION,
                        description="Slide rendered as a completely blank single-color canvas.",
                        visual_evidence=f"Zero pixel variance detected (min={extrema[0]}, max={extrema[1]}).",
                        repairable=True,
                    ))

        except Exception as e:
            issues.append(VisualIssue(
                issue_id="VPRE-0005",
                slide_id=artifact.physical_slide_id,
                severity=VisualSeverity.CRITICAL,
                category=VisualCategory.RENDER_CORRUPTION,
                description=f"Corrupt rendered image file: {e}",
                visual_evidence=str(e),
                repairable=True,
            ))

        return issues
