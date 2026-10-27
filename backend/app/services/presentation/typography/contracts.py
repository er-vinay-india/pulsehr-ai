"""Typography Intent and Resolution Contracts.

Strict Architectural Invariants:
- AI determines semantic intent (importance, hierarchy, emphasis, density risk, reflow preference, color role).
- Engineering / Deterministic Engine owns exact font sizes in pt, coordinates (x, y, w, h),
  contrast validation, line breaking, and renderer-specific XML/HTML output.
- CONDENSE is strictly forbidden from the ReflowPreference enum.
- WCAG AAA contrast (>= 7.0:1 for normal text, >= 4.5:1 for large text) is a MANDATORY HARD INVARIANT.
- Minimum readability point size floors are strictly enforced across all textual roles.
"""
from __future__ import annotations

import enum
import time
from typing import Any
from pydantic import BaseModel, Field, field_validator, model_validator


class SemanticTypographyRole(str, enum.Enum):
    """Semantic role of a textual block on a slide."""
    DECK_TITLE = "DECK_TITLE"
    SLIDE_TITLE = "SLIDE_TITLE"
    TITLE = "TITLE"
    SUBTITLE = "SUBTITLE"
    KPI = "KPI"
    KPI_VALUE = "KPI_VALUE"
    KPI_LABEL = "KPI_LABEL"
    PRIMARY_INSIGHT = "PRIMARY_INSIGHT"
    BODY = "BODY"
    BULLET = "BULLET"
    CHART = "CHART"
    CHART_TITLE = "CHART_TITLE"
    DATA_LABEL = "DATA_LABEL"
    AXIS_TITLE = "AXIS_TITLE"
    AXIS_LABEL = "AXIS_LABEL"
    LEGEND = "LEGEND"
    TABLE = "TABLE"
    TABLE_HEADER = "TABLE_HEADER"
    TABLE_BODY = "TABLE_BODY"
    TABLE_CELL = "TABLE_CELL"
    CAPTION = "CAPTION"
    SOURCE = "SOURCE"
    FOOTNOTE = "FOOTNOTE"
    CALLOUT = "CALLOUT"
    BADGE = "BADGE"


def normalize_semantic_role(role: Any) -> SemanticTypographyRole:
    """Normalizes arbitrary string or enum representations to standard SemanticTypographyRole."""
    if isinstance(role, SemanticTypographyRole):
        return role
    s = str(role or "").strip().upper()
    if s in ("DECK_TITLE", "PRESENTATION_TITLE"):
        return SemanticTypographyRole.DECK_TITLE
    if s in ("SLIDE_TITLE", "SLD_TITLE"):
        return SemanticTypographyRole.SLIDE_TITLE
    if s in ("TITLE", "HEADLINE"):
        return SemanticTypographyRole.TITLE
    if s in ("SUBTITLE", "DECK_SUBTITLE"):
        return SemanticTypographyRole.SUBTITLE
    if s in ("KPI", "KPI_METRIC", "METRIC"):
        return SemanticTypographyRole.KPI
    if s in ("KPI_VALUE", "METRIC_VALUE"):
        return SemanticTypographyRole.KPI_VALUE
    if s in ("KPI_LABEL", "METRIC_LABEL"):
        return SemanticTypographyRole.KPI_LABEL
    if s in ("PRIMARY_INSIGHT", "INSIGHT", "TAKEAWAY", "KEY_TAKEAWAY", "NARRATIVE_TAKEAWAY"):
        return SemanticTypographyRole.PRIMARY_INSIGHT
    if s in ("BULLET", "SUPPORTING_BULLET"):
        return SemanticTypographyRole.BULLET
    if s in ("SOURCE", "CITATION"):
        return SemanticTypographyRole.SOURCE
    if s in ("FOOTNOTE", "DISCLAIMER"):
        return SemanticTypographyRole.FOOTNOTE
    if s in ("CAPTION",):
        return SemanticTypographyRole.CAPTION
    if s in ("CALLOUT", "QUOTE"):
        return SemanticTypographyRole.CALLOUT
    if s in ("CHART", "CHART_CONTAINER", "VISUAL"):
        return SemanticTypographyRole.CHART
    if s in ("CHART_TITLE", "VISUAL_TITLE"):
        return SemanticTypographyRole.CHART_TITLE
    if s in ("DATA_LABEL",):
        return SemanticTypographyRole.DATA_LABEL
    if s in ("AXIS_TITLE",):
        return SemanticTypographyRole.AXIS_TITLE
    if s in ("AXIS_LABEL",):
        return SemanticTypographyRole.AXIS_LABEL
    if s in ("LEGEND",):
        return SemanticTypographyRole.LEGEND
    if s in ("TABLE", "DATA_TABLE"):
        return SemanticTypographyRole.TABLE
    if s in ("TABLE_HEADER", "TH"):
        return SemanticTypographyRole.TABLE_HEADER
    if s in ("TABLE_BODY",):
        return SemanticTypographyRole.TABLE_BODY
    if s in ("TABLE_CELL", "TD"):
        return SemanticTypographyRole.TABLE_CELL
    if s in ("BODY", "NARRATIVE", "TEXT"):
        return SemanticTypographyRole.BODY
    try:
        return SemanticTypographyRole(s)
    except ValueError:
        return SemanticTypographyRole.BODY


class TypographyImportance(str, enum.Enum):
    """Semantic importance level governing visual dominance."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    SUPPORTING = "SUPPORTING"


class TypographyRelativeScale(str, enum.Enum):
    """Relative abstract scale. Converted to concrete pt values deterministically by spatial engine."""
    HERO = "HERO"      # Slide titles, focal hero KPIs
    XL = "XL"          # Large metrics, primary section headers
    LARGE = "LARGE"    # Card headings, key callouts, primary insights
    BASE = "BASE"      # Body paragraphs, table cells, chart labels
    SMALL = "SMALL"    # Supporting context, secondary metrics, legends
    XS = "XS"          # Footnotes, methodology, disclaimers, citations


class TypographyPreferredWeight(str, enum.Enum):
    """Relative typographic weight preference."""
    BOLD = "BOLD"
    SEMIBOLD = "SEMIBOLD"
    MEDIUM = "MEDIUM"
    REGULAR = "REGULAR"


class TypographyColorRole(str, enum.Enum):
    """Semantic color intent. Converted to exact contrast-safe hex tokens by Theme Resolver."""
    TEXT_PRIMARY = "TEXT_PRIMARY"
    TEXT_SECONDARY = "TEXT_SECONDARY"
    TEXT_MUTED = "TEXT_MUTED"
    TEXT_ON_ACCENT = "TEXT_ON_ACCENT"
    TEXT_POSITIVE = "TEXT_POSITIVE"
    TEXT_NEGATIVE = "TEXT_NEGATIVE"
    TEXT_WARNING = "TEXT_WARNING"


class DensityRisk(str, enum.Enum):
    """Assessed density pressure on the container."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ReflowPreference(str, enum.Enum):
    """Structural reflow preference. CONDENSE is strictly prohibited."""
    NONE = "NONE"
    WRAP = "WRAP"
    SPLIT = "SPLIT"


class ImportantTextRun(BaseModel):
    """Entity or metric span receiving inline typographic emphasis."""
    text_span: str
    semantic_role: str = "ENTITY"  # ENTITY, PRIMARY_METRIC, COMPARISON_BENCHMARK, SURROUNDING_TEXT
    emphasis: str = "NORMAL"       # HERO, STRONG, NORMAL, SUBDUED


# ---------------------------------------------------------------------------
# WCAG 2.1 AAA Contrast & Readability Floor Calculations
# ---------------------------------------------------------------------------

def compute_wcag_luminance(hex_str: str) -> float:
    """Computes WCAG 2.1 relative luminance for a hex color string."""
    hex_clean = hex_str.lstrip("#").strip()
    if len(hex_clean) == 3:
        hex_clean = "".join(c * 2 for c in hex_clean)
    if len(hex_clean) != 6:
        return 0.0
    r = int(hex_clean[0:2], 16) / 255.0
    g = int(hex_clean[2:4], 16) / 255.0
    b = int(hex_clean[4:6], 16) / 255.0

    def to_linear(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * to_linear(r) + 0.7152 * to_linear(g) + 0.0722 * to_linear(b)


def compute_contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    """Computes WCAG 2.1 contrast ratio between foreground and background colors."""
    l1 = compute_wcag_luminance(fg_hex)
    l2 = compute_wcag_luminance(bg_hex)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return round((lighter + 0.05) / (darker + 0.05), 2)


def get_aaa_contrast_threshold(font_size_pt: float, font_weight: str) -> float:
    """Returns the mandatory WCAG AAA contrast threshold.
    
    - Normal text (< 18.0pt or < 14.0pt bold): 7.0:1
    - Large text (>= 18.0pt regular or >= 14.0pt bold): 4.5:1
    - Stricter threshold (7.0:1) applied whenever uncertain.
    """
    is_bold = str(font_weight).lower() in ("bold", "700", "800", "900", "600")
    if font_size_pt >= 18.0 or (font_size_pt >= 14.0 and is_bold):
        return 4.5
    return 7.0


# Minimum point size floors per semantic role
ROLE_READABILITY_FLOORS: dict[SemanticTypographyRole, float] = {
    SemanticTypographyRole.DECK_TITLE: 28.0,
    SemanticTypographyRole.SLIDE_TITLE: 24.0,
    SemanticTypographyRole.TITLE: 24.0,
    SemanticTypographyRole.SUBTITLE: 14.0,
    SemanticTypographyRole.KPI_VALUE: 24.0,
    SemanticTypographyRole.KPI: 24.0,
    SemanticTypographyRole.KPI_LABEL: 10.5,
    SemanticTypographyRole.PRIMARY_INSIGHT: 13.0,
    SemanticTypographyRole.BODY: 11.5,
    SemanticTypographyRole.BULLET: 11.5,
    SemanticTypographyRole.CHART_TITLE: 13.0,
    SemanticTypographyRole.CHART: 10.5,
    SemanticTypographyRole.DATA_LABEL: 9.5,
    SemanticTypographyRole.AXIS_TITLE: 10.5,
    SemanticTypographyRole.AXIS_LABEL: 9.0,
    SemanticTypographyRole.LEGEND: 9.0,
    SemanticTypographyRole.TABLE: 10.5,
    SemanticTypographyRole.TABLE_HEADER: 11.5,
    SemanticTypographyRole.TABLE_BODY: 10.5,
    SemanticTypographyRole.TABLE_CELL: 10.5,
    SemanticTypographyRole.CAPTION: 9.5,
    SemanticTypographyRole.SOURCE: 9.0,
    SemanticTypographyRole.FOOTNOTE: 9.0,
    SemanticTypographyRole.CALLOUT: 11.0,
    SemanticTypographyRole.BADGE: 9.5,
}


class TypographyIntent(BaseModel):
    """AI output contract for presentation typography intent.
    
    Contains strictly relative and semantic properties.
    Must never contain point sizes, pixel values, geometric coordinates, or raw hex colors.
    """
    block_id: str = ""
    semantic_role: SemanticTypographyRole = SemanticTypographyRole.BODY
    importance: TypographyImportance = TypographyImportance.MEDIUM
    emphasis_level: str = "NORMAL"
    preferred_weight: TypographyPreferredWeight = TypographyPreferredWeight.REGULAR
    relative_scale: TypographyRelativeScale = TypographyRelativeScale.BASE
    color_role: TypographyColorRole = TypographyColorRole.TEXT_PRIMARY
    density_risk: DensityRisk = DensityRisk.LOW
    reflow_preference: ReflowPreference = ReflowPreference.NONE
    important_runs: list[ImportantTextRun] = Field(default_factory=list)
    confidence: float = 1.0
    rationale: str = ""

    @field_validator("reflow_preference", mode="before")
    @classmethod
    def validate_no_condense(cls, v: Any) -> Any:
        if isinstance(v, str) and "condense" in v.lower():
            raise ValueError("CONDENSE is prohibited. Safe typography requires WRAP or SPLIT.")
        return v

    @model_validator(mode="before")
    @classmethod
    def reject_rendering_leaks(cls, data: Any) -> Any:
        if isinstance(data, dict):
            forbidden = {"font_size", "font_size_pt", "x", "y", "width", "height", "color", "hex"}
            leaks = forbidden.intersection(data.keys())
            if leaks:
                raise ValueError(f"TypographyIntent rejected rendering properties: {leaks}")
        return data


class TypographyBlockProvenance(BaseModel):
    """Telemetry recording exact provenance of how typography was resolved for a block."""
    typography_source: str = "PHI_LORA"  # "PHI_LORA" or "DETERMINISTIC_FALLBACK"
    base_model: str = "mlx-community/Phi-4-mini-instruct-mlx-4Bit"
    adapter_loaded: bool = True
    adapter_version: str = "phi4_mini_lora_v1"
    fallback_used: bool = False
    fallback_reason: str | None = None
    latency_ms: float = 0.0
    # WCAG AAA & Readability Telemetry
    foreground_hex: str = "#0F172A"
    background_hex: str = "#FFFFFF"
    contrast_ratio: float = 17.85
    aaa_threshold: float = 7.0
    aaa_pass: bool = True
    color_repaired: bool = False
    readability_floor_pt: float = 11.5
    readability_pass: bool = True


class ResolvedTypographySpec(BaseModel):
    """Deterministic engineering specification resolved from TypographyIntent and Theme.
    
    This is what the PPTX, HTML, and future PDF renderers consume.
    Guaranteed to satisfy WCAG AAA contrast (aaa_pass=True) and readability floor (readability_pass=True).
    """
    block_id: str
    semantic_role: SemanticTypographyRole
    font_family: str
    font_size_pt: float
    font_weight: str  # bold, normal, 600, etc.
    color_hex: str
    line_height_multiplier: float
    max_lines: int | None = None
    reflow_action: ReflowPreference = ReflowPreference.NONE
    important_runs: list[ImportantTextRun] = Field(default_factory=list)
    # Contrast & accessibility fields
    foreground_hex: str = "#0F172A"
    background_hex: str = "#FFFFFF"
    contrast_ratio: float = 17.85
    aaa_threshold: float = 7.0
    aaa_pass: bool = True
    color_repaired: bool = False
    readability_floor_pt: float = 11.5
    readability_pass: bool = True
    has_backing_plate: bool = False
    backing_plate_hex: str | None = None
    provenance: TypographyBlockProvenance = Field(default_factory=TypographyBlockProvenance)
    intent: TypographyIntent | None = None


class TypographyManifest(BaseModel):
    """Manifest recording typography telemetry, WCAG AAA accessibility, and execution provenance."""
    manifest_id: str = Field(default_factory=lambda: f"typo-man-{int(time.time()*1000)}")
    typography_source: str = "PHI_LORA"
    base_model: str = "mlx-community/Phi-4-mini-instruct-mlx-4Bit"
    adapter_loaded: bool = True
    adapter_version: str = "phi4_mini_lora_v1"
    fallback_used: bool = False
    fallback_reason: str | None = None
    total_blocks_resolved: int = 0
    total_ai_inferences: int = 0
    total_fallback_inferences: int = 0
    avg_latency_ms: float = 0.0
    # Accessibility totals
    total_aaa_checks: int = 0
    total_aaa_passes: int = 0
    total_aaa_failures: int = 0
    total_color_repairs_applied: int = 0
    total_readability_passes: int = 0
    total_readability_failures: int = 0
    blocks: list[dict[str, Any]] = Field(default_factory=list)
