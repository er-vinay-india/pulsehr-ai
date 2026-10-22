"""HighView Presentation Studio — PPT-L5 Central Layout Configuration & Typography Policy.

Central source of truth for:
1. Canonical normalized coordinate constants [0.0, 1.0].
2. Safe-area geometry and frame reservations.
3. Minimum dimension constraints for charts, tables, images, and text.
4. Role-based typography policies and strict readability floors.
5. Grid and spacing tokens.

Architectural Invariants:
1. ZERO scattered magic numbers across layout engines.
2. ZERO brand colors, palette definitions, or font family choices (deferred to PPT-L7).
3. SPLIT BEFORE SHRINK: Readability floors are strictly respected.
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field

from .layout_models import TextRole


class TypographyPolicy(BaseModel):
    """Typography rules and strict readability floors per semantic text role."""
    role: TextRole
    default_size_pt: float = Field(..., ge=6.0, le=72.0)
    floor_size_pt: float = Field(..., ge=6.0, le=48.0)
    line_height_ratio: float = Field(default=1.25, ge=1.0, le=2.0)
    max_lines: int = Field(default=4, ge=1)
    min_lines: int = Field(default=1, ge=1)
    chars_per_line_scale: float = Field(
        default=0.52,
        description="Average character width fraction of font size (0.52 standard proportional)"
    )


class CentralLayoutConfig(BaseModel):
    """Authoritative layout configuration for standard 16:9 presentation canvas."""

    # Canvas dimensions
    canvas_aspect_ratio_str: str = "16:9"
    canvas_aspect_ratio: float = 16.0 / 9.0  # 1.7778
    logical_width_pt: float = 960.0
    logical_height_pt: float = 540.0

    # Margins and Frame Reservations (normalized [0.0, 1.0])
    margin_left: float = 0.05       # 48pt / 960pt = 0.05
    margin_right: float = 0.05      # 48pt / 960pt = 0.05
    margin_top: float = 0.04        # ~22pt / 540pt
    margin_bottom: float = 0.04     # ~22pt / 540pt

    # Frame reservations
    frame_header_top: float = 0.04
    frame_header_height: float = 0.12  # Header area for category & title (approx 65pt)
    frame_footer_bottom: float = 0.96
    frame_footer_height: float = 0.04  # Footer area for source, notes, page number (0.92 -> 0.96)

    # Body area derived from margins and frame
    body_top: float = 0.17          # Top of body zone
    body_bottom: float = 0.91       # Bottom of body zone
    body_height: float = 0.74       # Total usable vertical content budget (0.91 - 0.17)
    body_left: float = 0.05
    body_width: float = 0.90

    # Spacing tokens (normalized [0.0, 1.0])
    zone_gap_h: float = 0.025       # Horizontal gap between zones (24pt / 960pt)
    zone_gap_v: float = 0.020       # Vertical gap between zones (11pt / 540pt)
    object_gap_h: float = 0.015     # Horizontal gap between objects within a zone
    object_gap_v: float = 0.012     # Vertical gap between objects within a zone
    min_element_gap: float = 0.008  # Absolute minimum separation to avoid touching

    # Minimum viable dimensions (normalized [0.0, 1.0])
    min_chart_width: float = 0.28   # 268pt / 960pt
    min_chart_height: float = 0.32  # 172pt / 540pt
    min_map_width: float = 0.40     # Maps need prominent area for geographic clarity
    min_map_height: float = 0.40
    min_table_width: float = 0.32
    min_table_height: float = 0.22
    min_image_width: float = 0.15
    min_image_height: float = 0.15
    min_text_width: float = 0.20
    min_text_height: float = 0.08

    # Table constraints
    table_row_height_default: float = 0.045  # ~24pt / 540pt
    table_row_height_min: float = 0.035      # ~19pt / 540pt
    table_max_rows_per_slide: int = 12       # Beyond this, late split is required
    table_min_col_width: float = 0.08

    # Bullet constraints
    max_bullets_per_slide: int = 5
    max_bullets_with_visual: int = 4

    # Grid system (12-column logical grid)
    grid_columns: int = 12

    # Role-based typography policies
    typography_policies: dict[TextRole, TypographyPolicy] = Field(
        default_factory=lambda: {
            TextRole.TITLE: TypographyPolicy(
                role=TextRole.TITLE,
                default_size_pt=28.0,
                floor_size_pt=20.0,
                line_height_ratio=1.22,
                max_lines=3,
                min_lines=1,
            ),
            TextRole.SUBTITLE: TypographyPolicy(
                role=TextRole.SUBTITLE,
                default_size_pt=16.0,
                floor_size_pt=13.0,
                line_height_ratio=1.20,
                max_lines=3,
                min_lines=1,
            ),
            TextRole.BODY: TypographyPolicy(
                role=TextRole.BODY,
                default_size_pt=15.0,
                floor_size_pt=11.5,
                line_height_ratio=1.25,
                max_lines=6,
                min_lines=1,
            ),
            TextRole.BULLET: TypographyPolicy(
                role=TextRole.BULLET,
                default_size_pt=14.0,
                floor_size_pt=11.0,
                line_height_ratio=1.25,
                max_lines=4,
                min_lines=1,
            ),
            TextRole.KPI_VALUE: TypographyPolicy(
                role=TextRole.KPI_VALUE,
                default_size_pt=34.0,
                floor_size_pt=22.0,
                line_height_ratio=1.10,
                max_lines=1,
                min_lines=1,
            ),
            TextRole.KPI_LABEL: TypographyPolicy(
                role=TextRole.KPI_LABEL,
                default_size_pt=13.0,
                floor_size_pt=10.0,
                line_height_ratio=1.15,
                max_lines=2,
                min_lines=1,
            ),
            TextRole.TABLE: TypographyPolicy(
                role=TextRole.TABLE,
                default_size_pt=13.0,
                floor_size_pt=10.0,
                line_height_ratio=1.18,
                max_lines=3,
                min_lines=1,
            ),
            TextRole.FOOTNOTE: TypographyPolicy(
                role=TextRole.FOOTNOTE,
                default_size_pt=10.0,
                floor_size_pt=8.5,
                line_height_ratio=1.15,
                max_lines=2,
                min_lines=1,
            ),
            TextRole.CAPTION: TypographyPolicy(
                role=TextRole.CAPTION,
                default_size_pt=11.0,
                floor_size_pt=9.0,
                line_height_ratio=1.15,
                max_lines=2,
                min_lines=1,
            ),
        }
    )

    def get_typography(self, role: TextRole) -> TypographyPolicy:
        """Retrieves typography policy for a text role."""
        return self.typography_policies.get(
            role,
            TypographyPolicy(
                role=role,
                default_size_pt=14.0,
                floor_size_pt=11.0,
                line_height_ratio=1.25,
            )
        )


# Global default configuration instance
DEFAULT_LAYOUT_CONFIG = CentralLayoutConfig()
