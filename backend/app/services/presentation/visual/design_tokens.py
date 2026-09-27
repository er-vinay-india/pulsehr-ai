"""Slide Design Tokens and Theme Normalization Contract for Phase 4.

Normalizes presentation slide themes into canonical, renderer-neutral design tokens
consumed by React, standalone HTML, and native PPTX exports.
Guarantees 100% isolation from the web application shell theme.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class SlideDesignTokens(BaseModel):
    """Canonical design tokens governing the visual appearance of presentation slides."""
    theme_id: str
    name: str
    is_dark: bool = True
    background: str = "#0F172A"
    surface: str = "#1E293B"
    surface_alt: str = "#141F32"
    primary_text: str = "#F8FAFC"
    secondary_text: str = "#94A3B8"
    muted_text: str = "#64748B"
    brand: str = "#38BDF8"
    accent: str = "#FF8A62"
    positive: str = "#10B981"
    negative: str = "#EF4444"
    warning: str = "#F59E0B"
    border: str = "rgba(255, 255, 255, 0.08)"
    grid: str = "rgba(255, 255, 255, 0.04)"
    chart_palette: list[str] = Field(
        default_factory=lambda: [
            "#38BDF8", "#FF8A62", "#10B981", "#A78BFA", "#FBBF24", "#F43F5E", "#34D399", "#60A5FA"
        ]
    )
    font_heading: str = "'Space Grotesk', system-ui, sans-serif"
    font_body: str = "'Plus Jakarta Sans', system-ui, sans-serif"
    font_mono: str = "'Space Mono', monospace"
    radius: str = "12px"
    shadow: str = "0 20px 40px -15px rgba(0, 0, 0, 0.5)"
    spacing: str = "16px"
    headline_scale: float = 1.0
    body_scale: float = 1.0

    @property
    def accent_primary(self) -> str:
        return self.accent

    @property
    def slide_padding(self) -> str:
        return "28px 36px"

    @property
    def card_gap(self) -> str:
        return self.spacing

    @property
    def card_border_radius(self) -> str:
        return self.radius

    @property
    def card_shadow(self) -> str:
        return self.shadow

    @property
    def font_size_headline(self) -> str:
        return f"{int(28 * self.headline_scale)}px"

    @property
    def font_size_subtitle(self) -> str:
        return "15px"

    @property
    def font_size_body(self) -> str:
        return f"{int(14 * self.body_scale)}px"

    @property
    def font_size_caption(self) -> str:
        return "12px"

    @property
    def font_size_kpi(self) -> str:
        return "32px"

    def to_scoped_css_variables(self) -> dict[str, str]:
        """Emits CSS custom properties for inclusion ONLY inside .presentation-runtime."""
        return {
            "--slide-bg": self.background,
            "--card-bg": self.surface,
            "--card-bg-alt": self.surface_alt,
            "--text-primary": self.primary_text,
            "--text-secondary": self.secondary_text,
            "--text-muted": self.muted_text,
            "--brand-color": self.brand,
            "--accent-color": self.accent,
            "--success-color": self.positive,
            "--danger-color": self.negative,
            "--warning-color": self.warning,
            "--card-border": self.border,
            "--grid-border": self.grid,
            "--font-display": self.font_heading,
            "--font-body": self.font_body,
            "--font-mono": self.font_mono,
            "--slide-radius": self.radius,
            "--slide-shadow": self.shadow,
        }


# Canonical Normalized Presentation Slide Themes (Preserving all existing themes)
DEFAULT_SLIDE_THEMES: dict[str, SlideDesignTokens] = {
    "bold_signal": SlideDesignTokens(
        theme_id="bold_signal",
        name="Bold Signal",
        is_dark=True,
        background="#131418",
        surface="#1C1E24",
        surface_alt="#17191E",
        primary_text="#FFFFFF",
        secondary_text="#94A3B8",
        muted_text="#64748B",
        brand="#FF5722",
        accent="#FF8A65",
        positive="#10B981",
        negative="#EF4444",
        warning="#F59E0B",
        border="rgba(255, 255, 255, 0.08)",
        grid="rgba(255, 255, 255, 0.04)",
        chart_palette=["#FF5722", "#FF8A65", "#00B4D8", "#90E0EF", "#FFD166", "#06D6A0"],
        font_heading="'Archivo Black', 'Space Grotesk', sans-serif",
        font_body="'Space Grotesk', system-ui, sans-serif"
    ),
    "electric_studio": SlideDesignTokens(
        theme_id="electric_studio",
        name="Electric Studio",
        is_dark=True,
        background="#0A0C10",
        surface="#141820",
        surface_alt="#0F1218",
        primary_text="#FFFFFF",
        secondary_text="#A1A1AA",
        muted_text="#71717A",
        brand="#4361EE",
        accent="#4CC9F0",
        positive="#10B981",
        negative="#F72585",
        warning="#FFB703",
        border="rgba(67, 97, 238, 0.25)",
        grid="rgba(67, 97, 238, 0.08)",
        chart_palette=["#4361EE", "#4CC9F0", "#7209B7", "#F72585", "#4895EF", "#560BAD"],
        font_heading="'Manrope', system-ui, sans-serif",
        font_body="'Manrope', system-ui, sans-serif"
    ),
    "creative_voltage": SlideDesignTokens(
        theme_id="creative_voltage",
        name="Creative Voltage",
        is_dark=True,
        background="#090914",
        surface="#111126",
        surface_alt="#0D0D1D",
        primary_text="#F8FAFC",
        secondary_text="#94A3B8",
        muted_text="#64748B",
        brand="#00F0FF",
        accent="#0055FF",
        positive="#00F5D4",
        negative="#FF0055",
        warning="#FEE440",
        border="rgba(0, 240, 255, 0.2)",
        grid="rgba(0, 240, 255, 0.05)",
        chart_palette=["#00F0FF", "#0055FF", "#7B2CBF", "#FF0055", "#00F5D4", "#FEE440"],
        font_heading="'Syne', system-ui, sans-serif",
        font_body="'Plus Jakarta Sans', system-ui, sans-serif"
    ),
    "executive_dark": SlideDesignTokens(
        theme_id="executive_dark",
        name="Executive Dark",
        is_dark=True,
        background="#0F172A",
        surface="#1E293B",
        surface_alt="#162032",
        primary_text="#F8FAFC",
        secondary_text="#94A3B8",
        muted_text="#64748B",
        brand="#38BDF8",
        accent="#FF8A62",
        positive="#10B981",
        negative="#EF4444",
        warning="#F59E0B",
        border="rgba(255, 255, 255, 0.08)",
        grid="rgba(255, 255, 255, 0.04)",
        chart_palette=["#38BDF8", "#FF8A62", "#10B981", "#A78BFA", "#FBBF24", "#F43F5E"],
        font_heading="'Space Grotesk', system-ui, sans-serif",
        font_body="'Plus Jakarta Sans', system-ui, sans-serif"
    ),
    "minimal_stark": SlideDesignTokens(
        theme_id="minimal_stark",
        name="Minimal Stark (Light)",
        is_dark=False,
        background="#F8FAFC",
        surface="#FFFFFF",
        surface_alt="#F1F5F9",
        primary_text="#0F172A",
        secondary_text="#475569",
        muted_text="#94A3B8",
        brand="#0F172A",
        accent="#2563EB",
        positive="#059669",
        negative="#DC2626",
        warning="#D97706",
        border="#E2E8F0",
        grid="#F1F5F9",
        chart_palette=["#0F172A", "#2563EB", "#059669", "#7C3AED", "#D97706", "#DC2626"],
        font_heading="'Space Grotesk', system-ui, sans-serif",
        font_body="'Plus Jakarta Sans', system-ui, sans-serif"
    ),
    "corporate_navy": SlideDesignTokens(
        theme_id="corporate_navy",
        name="Corporate Navy",
        is_dark=True,
        background="#0B192C",
        surface="#1E3E62",
        surface_alt="#152B44",
        primary_text="#FFFFFF",
        secondary_text="#CBD5E1",
        muted_text="#94A3B8",
        brand="#008DDA",
        accent="#41C9E2",
        positive="#10B981",
        negative="#EF4444",
        warning="#F59E0B",
        border="rgba(255, 255, 255, 0.12)",
        grid="rgba(255, 255, 255, 0.05)",
        chart_palette=["#008DDA", "#41C9E2", "#ACE2E1", "#F7EEDD", "#38BDF8", "#818CF8"],
        font_heading="'Plus Jakarta Sans', system-ui, sans-serif",
        font_body="'Plus Jakarta Sans', system-ui, sans-serif"
    ),
}


def normalize_slide_theme(theme_input: dict[str, Any] | str | None) -> SlideDesignTokens:
    """Safely normalizes raw theme dictionaries or ID strings into canonical SlideDesignTokens."""
    if isinstance(theme_input, str):
        clean_id = theme_input.strip().lower()
        if clean_id in DEFAULT_SLIDE_THEMES:
            return DEFAULT_SLIDE_THEMES[clean_id]
        clean_id = clean_id.replace("-", "_")
        if clean_id in DEFAULT_SLIDE_THEMES:
            return DEFAULT_SLIDE_THEMES[clean_id]
        return DEFAULT_SLIDE_THEMES["executive_dark"]

    if isinstance(theme_input, dict):
        t_id = theme_input.get("id") or theme_input.get("name") or "executive_dark"
        if t_id in DEFAULT_SLIDE_THEMES:
            base = DEFAULT_SLIDE_THEMES[t_id]
            # Override with any explicit custom values if provided
            data = base.model_dump()
            if "bg_color" in theme_input:
                data["background"] = theme_input["bg_color"]
            if "background" in theme_input:
                data["background"] = theme_input["background"]
            if "card_bg" in theme_input:
                data["surface"] = theme_input["card_bg"]
            if "primary_text" in theme_input:
                data["primary_text"] = theme_input["primary_text"]
            if "secondary_text" in theme_input:
                data["secondary_text"] = theme_input["secondary_text"]
            if "accent_color" in theme_input:
                data["accent"] = theme_input["accent_color"]
            if "brand_color" in theme_input:
                data["brand"] = theme_input["brand_color"]
            if "chart_palette" in theme_input:
                data["chart_palette"] = theme_input["chart_palette"]
            return SlideDesignTokens(**data)

    return DEFAULT_SLIDE_THEMES["executive_dark"]
