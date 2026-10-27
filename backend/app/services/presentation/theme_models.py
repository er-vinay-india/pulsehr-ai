"""HighView Presentation Studio — PPT-L7 Theme & Style Models.

Defines the central, typed ThemeDefinition, design tokens, style outcomes,
and StyleManifest. Strictly separates styling from geometry, layout, and content.
"""

from __future__ import annotations

from enum import Enum
import hashlib
import json
from typing import Any, Optional
from pydantic import BaseModel, Field


class ThemeMode(str, Enum):
    """Supported theme color realization modes."""
    LIGHT = "LIGHT"
    DARK = "DARK"
    HIGH_CONTRAST = "HIGH_CONTRAST"
    PRINT = "PRINT"
    CUSTOM = "CUSTOM"


class FontRole(str, Enum):
    """Semantic font typography roles."""
    DISPLAY = "DISPLAY"
    HEADING = "HEADING"
    BODY = "BODY"
    NUMERIC = "NUMERIC"
    MONO = "MONO"
    CAPTION = "CAPTION"


class SemanticTokenRole(str, Enum):
    """Central semantic color token keys."""
    BACKGROUND_PRIMARY = "BACKGROUND_PRIMARY"
    BACKGROUND_SECONDARY = "BACKGROUND_SECONDARY"
    SURFACE_PRIMARY = "SURFACE_PRIMARY"
    SURFACE_ELEVATED = "SURFACE_ELEVATED"
    SURFACE_ALT = "SURFACE_ALT"
    TEXT_PRIMARY = "TEXT_PRIMARY"
    TEXT_SECONDARY = "TEXT_SECONDARY"
    TEXT_MUTED = "TEXT_MUTED"
    TEXT_ON_DARK = "TEXT_ON_DARK"
    TEXT_ON_LIGHT = "TEXT_ON_LIGHT"
    BRAND_PRIMARY = "BRAND_PRIMARY"
    ACCENT_PRIMARY = "ACCENT_PRIMARY"
    ACCENT_SECONDARY = "ACCENT_SECONDARY"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    DANGER = "DANGER"
    INFO = "INFO"
    BORDER_SUBTLE = "BORDER_SUBTLE"
    BORDER_STRONG = "BORDER_STRONG"
    GRID_LINE = "GRID_LINE"


class SemanticColorRole(str, Enum):
    """Semantic color roles distinguishing data fidelity vs presentation chrome."""
    # Presentation / Chrome — Text & Labels (Target: WCAG AAA, 7.0:1 normal / 4.5:1 large)
    TITLE = "TITLE"
    SUBTITLE = "SUBTITLE"
    BODY = "BODY"
    AXIS_TEXT = "AXIS_TEXT"
    AXIS_TITLE = "AXIS_TITLE"
    TICK_TEXT = "TICK_TEXT"
    LEGEND_TEXT = "LEGEND_TEXT"
    DATA_LABEL = "DATA_LABEL"
    TABLE_HEADER_TEXT = "TABLE_HEADER_TEXT"
    TABLE_CELL_TEXT = "TABLE_CELL_TEXT"
    ANNOTATION_TEXT = "ANNOTATION_TEXT"
    KPI_LABEL = "KPI_LABEL"
    KPI_VALUE = "KPI_VALUE"

    # Presentation / Chrome — Essential Graphical Boundaries (Target: non-text >= 3.0:1)
    CARD_BORDER = "CARD_BORDER"
    AXIS_LINE = "AXIS_LINE"
    TABLE_BORDER = "TABLE_BORDER"

    # Presentation / Chrome — Decorative / Subtle Lines (Target: 1.2:1 to 2.5:1, subtle not harsh)
    GRID_LINE = "GRID_LINE"
    REFERENCE_LINE_SUBTLE = "REFERENCE_LINE_SUBTLE"

    # Presentation / Chrome — Surfaces
    SLIDE_BACKGROUND = "SLIDE_BACKGROUND"
    CARD_SURFACE = "CARD_SURFACE"
    CHART_PLOT_SURFACE = "CHART_PLOT_SURFACE"
    TABLE_HEADER_SURFACE = "TABLE_HEADER_SURFACE"
    TABLE_ROW_ALT_SURFACE = "TABLE_ROW_ALT_SURFACE"

    # Data / Semantic — Preserved (Target: preserve hue; check legibility >= 2.5:1 against plot area)
    DATA_SERIES = "DATA_SERIES"
    STATUS_POSITIVE = "STATUS_POSITIVE"
    STATUS_NEGATIVE = "STATUS_NEGATIVE"
    STATUS_WARNING = "STATUS_WARNING"
    STATUS_NEUTRAL = "STATUS_NEUTRAL"


class SemanticEmphasis(str, Enum):
    """Semantic visual emphasis hierarchy."""
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    WARNING = "WARNING"
    NEUTRAL = "NEUTRAL"
    HIGHLIGHT = "HIGHLIGHT"


class StyleRole(str, Enum):
    """Component-level styling role."""
    TITLE = "TITLE"
    SUBTITLE = "SUBTITLE"
    BODY = "BODY"
    BULLET = "BULLET"
    KPI_VALUE = "KPI_VALUE"
    KPI_UNIT = "KPI_UNIT"
    KPI_LABEL = "KPI_LABEL"
    TABLE_HEADER = "TABLE_HEADER"
    TABLE_BODY = "TABLE_BODY"
    TABLE_TOTAL = "TABLE_TOTAL"
    CHART_SERIES = "CHART_SERIES"
    CHART_AXIS = "CHART_AXIS"
    CHART_GRID = "CHART_GRID"
    CHART_LABEL = "CHART_LABEL"
    CHART_LEGEND = "CHART_LEGEND"
    CAPTION = "CAPTION"
    FOOTNOTE = "FOOTNOTE"
    CALLOUT = "CALLOUT"
    PAGE_NUMBER = "PAGE_NUMBER"
    CARD_SURFACE = "CARD_SURFACE"
    SLIDE_BACKGROUND = "SLIDE_BACKGROUND"


class PaletteTokens(BaseModel):
    """Primary color palette hex values."""
    background: str
    surface: str
    surface_alt: str
    surface_elevated: str
    primary_text: str
    secondary_text: str
    muted_text: str
    brand: str
    accent: str
    positive: str
    negative: str
    warning: str
    border_subtle: str
    border_strong: str
    grid: str


class TypographyTokens(BaseModel):
    """Typography family mappings per role."""
    display_family: str
    heading_family: str
    body_family: str
    numeric_family: str
    mono_family: str
    caption_family: str
    fallback_family: str = "Arial, sans-serif"


class ChartPaletteTokens(BaseModel):
    """Categorical, sequential, diverging, and status chart palettes."""
    categorical: list[str] = Field(default_factory=list)
    sequential: list[str] = Field(default_factory=list)
    diverging: list[str] = Field(default_factory=list)
    status: dict[str, str] = Field(default_factory=dict)


class TableTokens(BaseModel):
    """Table styling design tokens."""
    header_fill: str
    header_text: str
    body_text: str
    alt_row_fill: str | None = None
    border: str


class SurfaceTokens(BaseModel):
    """Surface styling design tokens."""
    primary: str
    elevated: str
    alt: str
    radius: str = "12px"
    shadow: str = "0 10px 25px -5px rgba(0, 0, 0, 0.3)"


class BorderTokens(BaseModel):
    """Border styling tokens."""
    subtle: str
    strong: str
    accent: str


class EmphasisTokens(BaseModel):
    """Emphasis color mappings."""
    primary: str
    secondary: str
    positive: str
    negative: str
    warning: str
    neutral: str
    highlight: str


class AccessibilityPolicy(BaseModel):
    """Deterministic accessibility and contrast thresholds."""
    min_normal_contrast: float = 4.5
    min_large_contrast: float = 3.0
    target_normal_contrast: float = 7.0
    auto_contrast_resolution: bool = True


class ThemeDefinition(BaseModel):
    """Central typed definition of a HighView presentation theme.

    Owns visual styles, colors, typography families, and chart palettes.
    Does NOT contain geometry, coordinates, box dimensions, or font sizes.
    """
    theme_id: str
    name: str
    version: str = "1.0.0"
    mode: ThemeMode
    is_dark: bool
    palette: PaletteTokens
    typography: TypographyTokens
    chart_palette: ChartPaletteTokens
    table_tokens: TableTokens
    surface_tokens: SurfaceTokens
    border_tokens: BorderTokens
    emphasis_tokens: EmphasisTokens
    accessibility_policy: AccessibilityPolicy = Field(default_factory=AccessibilityPolicy)
    theme_fingerprint: str = ""

    def get_token_hex(self, token_name: str | SemanticTokenRole) -> str:
        """Resolve a semantic color token name to its hex value."""
        key = token_name.value if isinstance(token_name, SemanticTokenRole) else str(token_name)
        mapping = {
            "BACKGROUND_PRIMARY": self.palette.background,
            "BACKGROUND_SECONDARY": self.palette.surface_alt,
            "SURFACE_PRIMARY": self.palette.surface,
            "SURFACE_ELEVATED": self.palette.surface_elevated,
            "SURFACE_ALT": self.palette.surface_alt,
            "TEXT_PRIMARY": self.palette.primary_text,
            "TEXT_SECONDARY": self.palette.secondary_text,
            "TEXT_MUTED": self.palette.muted_text,
            "TEXT_ON_DARK": "#FFFFFF",
            "TEXT_ON_LIGHT": "#0F172A",
            "BRAND_PRIMARY": self.palette.brand,
            "ACCENT_PRIMARY": self.palette.accent,
            "ACCENT_SECONDARY": self.emphasis_tokens.highlight,
            "SUCCESS": self.palette.positive,
            "WARNING": self.palette.warning,
            "DANGER": self.palette.negative,
            "INFO": self.palette.brand,
            "BORDER_SUBTLE": self.palette.border_subtle,
            "BORDER_STRONG": self.palette.border_strong,
            "GRID_LINE": self.palette.grid,
        }
        if key in mapping:
            return mapping[key]
        raise ValueError(f"Unknown theme token '{key}' in ThemeDefinition '{self.theme_id}'")


def compute_theme_fingerprint(theme: ThemeDefinition) -> str:
    """Computes deterministic SHA-256 fingerprint for a ThemeDefinition."""
    payload = {
        "theme_id": theme.theme_id,
        "version": theme.version,
        "mode": theme.mode.value,
        "is_dark": theme.is_dark,
        "palette": theme.palette.model_dump(),
        "typography": theme.typography.model_dump(),
        "chart_palette": theme.chart_palette.model_dump(),
        "table_tokens": theme.table_tokens.model_dump(),
        "surface_tokens": theme.surface_tokens.model_dump(),
        "border_tokens": theme.border_tokens.model_dump(),
        "emphasis_tokens": theme.emphasis_tokens.model_dump(),
    }
    dumped = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


# --- Style Manifest & Outcomes ---

class ObjectStyleOutcome(BaseModel):
    """Style applied to an individual PowerPoint shape object."""
    object_id: str
    object_name: str
    style_role: StyleRole
    font_family: Optional[str] = None
    font_weight: Optional[str] = None
    font_color_hex: Optional[str] = None
    fill_color_hex: Optional[str] = None
    stroke_color_hex: Optional[str] = None
    contrast_ratio: Optional[float] = None
    resolved_tokens: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class ChartSeriesStyleOutcome(BaseModel):
    """Style applied to a chart series."""
    series_index: int
    series_name: str
    color_hex: str
    token_used: str


class TableStyleOutcome(BaseModel):
    """Style applied to a native table."""
    object_id: str
    header_fill_hex: str
    header_text_hex: str
    body_text_hex: str
    alt_row_fill_hex: Optional[str] = None
    border_color_hex: Optional[str] = None
    header_contrast: float
    body_contrast: float


class SlideStyleOutcome(BaseModel):
    """Style summary for a physical slide."""
    slide_index: int
    physical_slide_id: str
    background_fill_hex: str
    background_mode: str
    styled_object_count: int


class AccessibilityAuditResult(BaseModel):
    """Record of contrast verification for styled text or element."""
    target_id: str
    target_type: str
    foreground_hex: str
    background_hex: str
    contrast_ratio: float
    threshold: float
    passed: bool
    auto_resolved: bool = False
    resolution_token: Optional[str] = None


class StyleManifest(BaseModel):
    """Full deterministic manifest of PPT-L7 styling outcomes."""
    theme_id: str
    theme_version: str
    mode: ThemeMode
    slide_styles: list[SlideStyleOutcome] = Field(default_factory=list)
    object_styles: list[ObjectStyleOutcome] = Field(default_factory=list)
    chart_series_styles: list[ChartSeriesStyleOutcome] = Field(default_factory=list)
    table_styles: list[TableStyleOutcome] = Field(default_factory=list)
    accessibility_results: list[AccessibilityAuditResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    stats: dict[str, Any] = Field(default_factory=dict)
    style_fingerprint: str = ""


def compute_style_manifest_fingerprint(manifest: StyleManifest) -> str:
    """Computes deterministic SHA-256 fingerprint for a StyleManifest."""
    payload = {
        "theme_id": manifest.theme_id,
        "theme_version": manifest.theme_version,
        "mode": manifest.mode.value,
        "slide_styles": [s.model_dump() for s in manifest.slide_styles],
        "object_styles": [
            {
                "object_id": o.object_id,
                "object_name": o.object_name,
                "style_role": o.style_role.value,
                "font_family": o.font_family,
                "font_weight": o.font_weight,
                "font_color_hex": o.font_color_hex,
                "fill_color_hex": o.fill_color_hex,
                "stroke_color_hex": o.stroke_color_hex,
                "contrast_ratio": o.contrast_ratio,
                "resolved_tokens": o.resolved_tokens,
            }
            for o in manifest.object_styles
        ],
        "chart_series_styles": [c.model_dump() for c in manifest.chart_series_styles],
        "table_styles": [t.model_dump() for t in manifest.table_styles],
    }
    dumped = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()
