"""Slide Design Tokens and Theme Normalization Contract for Phase 4.

Normalizes presentation slide themes into canonical, renderer-neutral design tokens
consumed by React, standalone HTML, and native PPTX exports.
Guarantees 100% isolation from the web application shell theme.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field


SLIDE_THEME_PRESETS = json.loads((Path(__file__).parent.parent / "templates" / "themes.json").read_text())
_DEFAULT = SLIDE_THEME_PRESETS["executive_dark"]


class SlideDesignTokens(BaseModel):
    """Canonical design tokens governing the visual appearance of presentation slides."""
    theme_id: str
    name: str
    is_dark: bool = True
    background: str = _DEFAULT["bg_color"]
    surface: str = _DEFAULT["card_bg"]
    surface_alt: str = _DEFAULT["surface_alt"]
    primary_text: str = _DEFAULT["primary_text"]
    secondary_text: str = _DEFAULT["secondary_text"]
    muted_text: str = _DEFAULT["muted_text"]
    brand: str = _DEFAULT["brand_color"]
    accent: str = _DEFAULT["accent_color"]
    positive: str = _DEFAULT["success_color"]
    negative: str = _DEFAULT["danger_color"]
    warning: str = _DEFAULT["warning_color"]
    border: str = _DEFAULT["card_border"]
    grid: str = _DEFAULT["card_border"]
    chart_palette: list[str] = Field(default_factory=lambda: list(_DEFAULT["chart_palette"]))
    font_heading: str = _DEFAULT["font_display"]
    font_body: str = _DEFAULT["font_body"]
    font_mono: str = _DEFAULT["font_mono"]
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


# The same preset source generates the React/SCSS and HTML export tokens.
SLIDE_THEME_ALIASES = {"executive_studio": "executive_dark", "minimal_stark": "clean_light"}
DEFAULT_SLIDE_THEMES = {
    key: SlideDesignTokens(
        theme_id=key, name=t["name"], is_dark=t["is_dark"],
        background=t["bg_color"], surface=t["card_bg"], surface_alt=t["surface_alt"],
        primary_text=t["primary_text"], secondary_text=t["secondary_text"], muted_text=t["muted_text"],
        brand=t["brand_color"], accent=t["accent_color"], positive=t["success_color"],
        negative=t["danger_color"], warning=t["warning_color"], border=t["card_border"], grid=t["card_border"],
        chart_palette=t["chart_palette"], font_heading=t["font_display"], font_body=t["font_body"], font_mono=t["font_mono"]
    ) for key, t in SLIDE_THEME_PRESETS.items()
}
for alias, key in SLIDE_THEME_ALIASES.items():
    DEFAULT_SLIDE_THEMES[alias] = DEFAULT_SLIDE_THEMES[key].model_copy(update={"theme_id": alias})


def slide_theme_preset(theme_input: dict[str, Any] | str | None) -> dict:
    """Upgrade saved built-in palettes on read; a deck does not need regeneration."""
    raw_id = theme_input if isinstance(theme_input, str) else (theme_input or {}).get("id") or (theme_input or {}).get("theme_id")
    key = str(raw_id or "executive_dark").strip().lower().replace("-", "_")
    return dict(SLIDE_THEME_PRESETS.get(SLIDE_THEME_ALIASES.get(key, key), SLIDE_THEME_PRESETS["executive_dark"]))


def normalize_slide_theme(theme_input: dict[str, Any] | str | None) -> SlideDesignTokens:
    raw_id = theme_input if isinstance(theme_input, str) else (theme_input or {}).get("id") or (theme_input or {}).get("theme_id")
    key = str(raw_id or "executive_dark").strip().lower().replace("-", "_")
    return DEFAULT_SLIDE_THEMES.get(key, DEFAULT_SLIDE_THEMES["executive_dark"]).model_copy(deep=True)
