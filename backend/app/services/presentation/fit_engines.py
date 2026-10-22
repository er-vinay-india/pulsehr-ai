"""HighView Presentation Studio — PPT-L5 Fit Engines & Sizing Policies.

Implements deterministic content fit measurement without AI, without text summarization,
and without image distortion:
1. TextFitEngine: Word-wrap measurement, typography floor enforcement, line counts.
2. ImageFitEngine: Strict aspect ratio preservation, CONTAIN/COVER crop boxes, quality checks.
3. TableFitEngine: Data-aware column width allocation, row height budget, continuation detection.
4. ChartFitPolicy: Minimum viable area per visual family, map protection, label/legend pressure.

Architectural Invariants:
1. SPLIT BEFORE SHRINK: Readability floors are never breached.
2. ZERO content dropped, ZERO content rewritten, ZERO numbers stripped.
3. ZERO image distortion (aspect ratio is 100% preserved).
4. Primary visuals are NEVER hidden.
5. AI calls = 0.
"""

from __future__ import annotations

import logging
import math
import re
from typing import Any, Optional

from .content_models import ContentKind
from .layout_config import CentralLayoutConfig, DEFAULT_LAYOUT_CONFIG, TypographyPolicy
from .layout_models import (
    Box2D,
    ImageFitMode,
    ImageQualityWarning,
    ObjectFitStatus,
    TextRole,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# TEXT FIT ENGINE
# ==============================================================================

class TextFitEngine:
    """Measures and resolves typography fit deterministically within a bounding box."""

    def __init__(self, config: CentralLayoutConfig | None = None) -> None:
        self.config = config or DEFAULT_LAYOUT_CONFIG

    @classmethod
    def clean_text(cls, text: str) -> str:
        """Removes Markdown bold/italic markup while preserving exact content."""
        if not text:
            return ""
        # Remove bold/italic markdown
        clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", str(text))
        clean = re.sub(r"\*([^*]+)\*", r"\1", clean)
        return clean.strip()

    @classmethod
    def estimate_lines_for_paragraph(
        cls,
        paragraph: str,
        available_width_pt: float,
        font_size_pt: float,
        scale: float = 0.52,
    ) -> int:
        """Estimates line count for a single paragraph given width and font size."""
        clean = cls.clean_text(paragraph)
        if not clean:
            return 0
        char_capacity = max(1, math.floor(available_width_pt / max(font_size_pt * scale, 1.0)))
        words = clean.split()
        if not words:
            return 1
        lines = 1
        current_line_chars = 0
        for word in words:
            w_len = len(word)
            if current_line_chars == 0:
                current_line_chars = w_len
            elif current_line_chars + 1 + w_len <= char_capacity:
                current_line_chars += 1 + w_len
            else:
                lines += 1
                current_line_chars = w_len
        return lines

    def fit_text(
        self,
        text: str,
        available_box: Box2D,
        role: TextRole = TextRole.BODY,
        bullet_count: int = 0,
        paragraph_gap_fraction: float = 0.01,
    ) -> tuple[float, int, ObjectFitStatus, list[str]]:
        """Fits text into available_box respecting typography policy and floors.
        
        Returns:
            (resolved_font_size_pt, line_count, fit_status, warnings)
        """
        clean = self.clean_text(text)
        policy = self.config.get_typography(role)
        warnings: list[str] = []

        if not clean and bullet_count == 0:
            return policy.default_size_pt, 0, ObjectFitStatus.FIT, []

        w_pt = available_box.width * self.config.logical_width_pt
        h_pt = available_box.height * self.config.logical_height_pt

        paragraphs = clean.split("\n") if clean else [""]
        paragraphs = [p.strip() for p in paragraphs if p.strip()] or [""]

        # Step font size down from default to floor
        current_size = policy.default_size_pt
        floor_size = policy.floor_size_pt
        best_size = floor_size
        best_lines = 1
        fits = False

        size_step = 0.5
        while current_size >= floor_size - 1e-6:
            line_height_pt = current_size * policy.line_height_ratio
            total_lines = 0
            for p in paragraphs:
                p_lines = self.estimate_lines_for_paragraph(
                    p, w_pt, current_size, scale=policy.chars_per_line_scale
                )
                total_lines += max(1, p_lines)

            # Account for extra vertical gap between paragraphs/bullets
            num_gaps = max(0, len(paragraphs) - 1 + bullet_count)
            gap_height_pt = num_gaps * (paragraph_gap_fraction * self.config.logical_height_pt)
            required_height_pt = (total_lines * line_height_pt) + gap_height_pt

            if required_height_pt <= h_pt:
                best_size = current_size
                best_lines = total_lines
                fits = True
                break

            best_size = current_size
            best_lines = total_lines
            current_size -= size_step

        if fits:
            if best_size == policy.default_size_pt:
                status = ObjectFitStatus.FIT
            elif best_size <= floor_size + 0.5:
                status = ObjectFitStatus.AT_MINIMUM_SIZE
                warnings.append(f"{role.value} text scaled to minimum font floor {best_size:.1f}pt")
            else:
                status = ObjectFitStatus.FIT_WITH_ADJUSTMENT
            return best_size, best_lines, status, warnings

        # Does not fit even at floor size
        warnings.append(
            f"{role.value} text overflows available vertical capacity at floor size {floor_size:.1f}pt "
            f"({best_lines} lines require {best_lines * floor_size * policy.line_height_ratio:.1f}pt, "
            f"available: {h_pt:.1f}pt)"
        )
        return floor_size, best_lines, ObjectFitStatus.OVERFLOW, warnings


# ==============================================================================
# IMAGE FIT ENGINE
# ==============================================================================

class ImageFitEngine:
    """Calculates deterministic image bounding boxes, crop windows, and quality warnings."""

    def __init__(self, config: CentralLayoutConfig | None = None) -> None:
        self.config = config or DEFAULT_LAYOUT_CONFIG

    def fit_image(
        self,
        source_width_px: int,
        source_height_px: int,
        available_box: Box2D,
        mode: ImageFitMode = ImageFitMode.CONTAIN,
    ) -> tuple[Box2D, Optional[Box2D], ImageQualityWarning, list[str]]:
        """Fits an image into available_box while strictly preserving source aspect ratio.
        
        Returns:
            (resolved_bounds, crop_box, quality_warning, warnings)
        """
        warnings: list[str] = []
        quality_warning = ImageQualityWarning.NONE

        if source_width_px <= 0 or source_height_px <= 0:
            source_width_px = 800
            source_height_px = 600

        source_aspect = float(source_width_px) / float(source_height_px)
        canvas_aspect = self.config.canvas_aspect_ratio

        # Available box aspect in physical presentation space
        # box_w_pt = available_box.width * 960, box_h_pt = available_box.height * 540
        box_w_physical = available_box.width * canvas_aspect
        box_h_physical = available_box.height * 1.0
        target_aspect = box_w_physical / max(box_h_physical, 1e-6)

        # Quality estimation
        rendered_w_px = available_box.width * 1920.0
        rendered_h_px = available_box.height * 1080.0
        if source_width_px < 300 or source_height_px < 200:
            quality_warning = ImageQualityWarning.LOW_RESOLUTION
            warnings.append(
                f"Source image resolution ({source_width_px}x{source_height_px}) is below recommended 300x200 floor"
            )
        elif rendered_w_px > source_width_px * 2.2 or rendered_h_px > source_height_px * 2.2:
            quality_warning = ImageQualityWarning.UPSCALE_RISK
            warnings.append(
                f"Image requires upscaling ({source_width_px}x{source_height_px} -> ~{int(rendered_w_px)}x{int(rendered_h_px)})"
            )

        crop_box: Optional[Box2D] = None

        if mode == ImageFitMode.CONTAIN:
            # Fit inside available_box without cropping, preserving source aspect
            if source_aspect > target_aspect:
                # Constrained by width
                fit_w = available_box.width
                fit_h = (fit_w * canvas_aspect) / (source_aspect * 1.0)
                fit_left = available_box.left
                fit_top = available_box.top + ((available_box.height - fit_h) / 2.0)
            else:
                # Constrained by height
                fit_h = available_box.height
                fit_w = (fit_h * source_aspect) / canvas_aspect
                fit_top = available_box.top
                fit_left = available_box.left + ((available_box.width - fit_w) / 2.0)

            resolved_bounds = Box2D(
                left=round(fit_left, 5),
                top=round(fit_top, 5),
                width=round(fit_w, 5),
                height=round(fit_h, 5),
            )
            return resolved_bounds, None, quality_warning, warnings

        elif mode == ImageFitMode.COVER:
            # Fills entire available_box, calculate deterministic centered crop window
            resolved_bounds = Box2D(
                left=round(available_box.left, 5),
                top=round(available_box.top, 5),
                width=round(available_box.width, 5),
                height=round(available_box.height, 5),
            )
            # Crop box normalized within source image [0.0, 1.0]
            if source_aspect > target_aspect:
                # Source is wider than target: crop left & right
                visible_w_frac = target_aspect / source_aspect
                crop_left = (1.0 - visible_w_frac) / 2.0
                crop_box = Box2D(
                    left=round(crop_left, 4),
                    top=0.0,
                    width=round(visible_w_frac, 4),
                    height=1.0,
                )
            else:
                # Source is taller than target: crop top & bottom
                visible_h_frac = source_aspect / target_aspect
                crop_top = (1.0 - visible_h_frac) / 2.0
                crop_box = Box2D(
                    left=0.0,
                    top=round(crop_top, 4),
                    width=1.0,
                    height=round(visible_h_frac, 4),
                )
            return resolved_bounds, crop_box, quality_warning, warnings

        elif mode == ImageFitMode.FIT_WIDTH:
            fit_w = available_box.width
            fit_h = min(available_box.height, (fit_w * canvas_aspect) / source_aspect)
            resolved_bounds = Box2D(
                left=round(available_box.left, 5),
                top=round(available_box.top, 5),
                width=round(fit_w, 5),
                height=round(fit_h, 5),
            )
            return resolved_bounds, None, quality_warning, warnings

        else:  # FIT_HEIGHT
            fit_h = available_box.height
            fit_w = min(available_box.width, (fit_h * source_aspect) / canvas_aspect)
            resolved_bounds = Box2D(
                left=round(available_box.left, 5),
                top=round(available_box.top, 5),
                width=round(fit_w, 5),
                height=round(fit_h, 5),
            )
            return resolved_bounds, None, quality_warning, warnings


# ==============================================================================
# TABLE FIT ENGINE
# ==============================================================================

class TableFitEngine:
    """Calculates data-aware table column widths, row heights, and continuation triggers."""

    def __init__(self, config: CentralLayoutConfig | None = None) -> None:
        self.config = config or DEFAULT_LAYOUT_CONFIG

    def fit_table(
        self,
        headers: list[str],
        row_count: int,
        sample_rows: list[list[Any]] | None = None,
        available_box: Box2D | None = None,
    ) -> tuple[list[float], list[float], float, ObjectFitStatus, Optional[dict[str, Any]], list[str]]:
        """Allocates column widths and estimates row heights.
        
        Returns:
            (column_width_fractions, row_height_fractions, resolved_font_size, fit_status, split_hint, warnings)
        """
        warnings: list[str] = []
        box = available_box or Box2D(left=0.05, top=0.17, width=0.90, height=0.74)
        col_count = max(1, len(headers))
        policy = self.config.get_typography(TextRole.TABLE)

        # 1. Data-aware column weighting
        col_weights = []
        for c_idx in range(col_count):
            h_text = headers[c_idx] if c_idx < len(headers) else f"Col {c_idx + 1}"
            sample_lens = [len(str(r[c_idx])) for r in (sample_rows or []) if c_idx < len(r)]
            avg_len = sum(sample_lens) / max(1, len(sample_lens)) if sample_lens else len(h_text)
            max_len = max(sample_lens + [len(h_text)]) if sample_lens else len(h_text)

            # Detect numeric / currency columns
            is_numeric = False
            if sample_rows:
                num_count = sum(
                    1 for r in sample_rows
                    if c_idx < len(r) and re.match(r"^[\$€£]?\s*[-+]?[0.0-9,]+%?$", str(r[c_idx]).strip())
                )
                if num_count >= max(1, len(sample_rows) // 2):
                    is_numeric = True

            if is_numeric:
                weight = max(1.0, math.sqrt(max_len) * 0.8)
            elif "id" in h_text.lower() or "code" in h_text.lower() or max_len <= 6:
                weight = 1.0
            elif "desc" in h_text.lower() or "name" in h_text.lower() or avg_len > 25:
                weight = 2.5
            else:
                weight = max(1.2, min(2.0, avg_len / 10.0))
            col_weights.append(weight)

        total_weight = sum(col_weights)
        col_fractions = [round(w / total_weight, 4) for w in col_weights]

        # Ensure minimum column width
        min_w = self.config.table_min_col_width
        for idx in range(len(col_fractions)):
            if col_fractions[idx] < min_w:
                col_fractions[idx] = min_w
        # Re-normalize
        total_f = sum(col_fractions)
        col_fractions = [round(f / total_f, 4) for f in col_fractions]

        # 2. Row height and font sizing
        row_h_default = self.config.table_row_height_default
        row_h_min = self.config.table_row_height_min
        header_h = row_h_default * 1.25

        available_h = box.height
        needed_h = header_h + (row_count * row_h_default)

        split_hint: Optional[dict[str, Any]] = None

        if needed_h <= available_h:
            # Fits comfortably at default size
            row_heights = [round(header_h, 4)] + [round(row_h_default, 4)] * row_count
            return col_fractions, row_heights, policy.default_size_pt, ObjectFitStatus.FIT, None, []

        # Try minimum row height
        needed_min_h = header_h + (row_count * row_h_min)
        if needed_min_h <= available_h:
            compressed_h = (available_h - header_h) / max(1, row_count)
            row_heights = [round(header_h, 4)] + [round(compressed_h, 4)] * row_count
            font_size = max(policy.floor_size_pt, policy.default_size_pt - 2.0)
            warnings.append(f"Table row heights compressed to fit ({row_count} rows)")
            return col_fractions, row_heights, font_size, ObjectFitStatus.FIT_WITH_ADJUSTMENT, None, warnings

        # Overflow: Exceeds vertical capacity even at minimum row height
        # Calculate maximum safe rows that can fit
        max_safe_rows = max(1, int((available_h - header_h) // row_h_min))
        split_hint = {
            "reason": "TABLE_OVERFLOW",
            "total_rows": row_count,
            "max_rows_per_slide": max_safe_rows,
            "split_row_index": max_safe_rows,
            "recommended_continuation_slides": math.ceil(row_count / max_safe_rows),
        }
        warnings.append(
            f"Table overflow: {row_count} rows exceed vertical capacity (max safe: {max_safe_rows} rows). "
            f"LATE_SPLIT_REQUIRED."
        )
        row_heights = [round(header_h, 4)] + [round(row_h_min, 4)] * row_count
        return col_fractions, row_heights, policy.floor_size_pt, ObjectFitStatus.OVERFLOW, split_hint, warnings


# ==============================================================================
# CHART FIT POLICY
# ==============================================================================

class ChartFitPolicy:
    """Enforces minimum viable geometry and evaluates label/legend pressure for charts and maps."""

    def __init__(self, config: CentralLayoutConfig | None = None) -> None:
        self.config = config or DEFAULT_LAYOUT_CONFIG

    def evaluate_chart_fit(
        self,
        available_box: Box2D,
        kind: ContentKind,
        is_primary: bool = True,
        category_count: int = 0,
        series_count: int = 1,
        is_map: bool = False,
    ) -> tuple[ObjectFitStatus, list[str]]:
        """Validates chart allocation against architectural constraints.
        
        Returns:
            (fit_status, warnings)
        """
        warnings: list[str] = []

        # 1. Map Area Protection
        if is_map or kind == ContentKind.MAP:
            min_w = self.config.min_map_width
            min_h = self.config.min_map_height
            if available_box.width < min_w or available_box.height < min_h:
                warnings.append(
                    f"Map visual allocated insufficient area ({available_box.width:.2f}x{available_box.height:.2f} < "
                    f"minimum {min_w:.2f}x{min_h:.2f}). Geographic clarity compromised."
                )
                return ObjectFitStatus.OVERFLOW, warnings
            return ObjectFitStatus.FIT, []

        # 2. Primary Chart Minimum Viable Area
        min_w = self.config.min_chart_width
        min_h = self.config.min_chart_height
        if available_box.width < min_w or available_box.height < min_h:
            warnings.append(
                f"Chart allocated area ({available_box.width:.2f}x{available_box.height:.2f}) is below "
                f"minimum viable size ({min_w:.2f}x{min_h:.2f})."
            )
            return ObjectFitStatus.OVERFLOW, warnings

        # 3. Label Pressure Assessment
        if category_count > 8:
            warnings.append(
                f"High category count ({category_count} categories) creates axis label collision pressure."
            )

        # 4. Legend Pressure Assessment
        if series_count > 5:
            warnings.append(
                f"High series count ({series_count} series) creates legend reservation pressure."
            )

        status = ObjectFitStatus.FIT if not warnings else ObjectFitStatus.FIT_WITH_ADJUSTMENT
        return status, warnings
