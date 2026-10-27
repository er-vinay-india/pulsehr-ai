"""HighView Presentation Studio — PPT-L7 Theme Engine.

Implements ThemeDefinition factory, StyleTokenResolver, FontResolver,
TextStyleResolver, TableStyleResolver, ChartStyleResolver, and ObjectStyleResolver.
Enforces deterministic theme styling and WCAG contrast safety.
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Optional

from app.services.presentation.theme_models import (
    AccessibilityAuditResult,
    AccessibilityPolicy,
    BorderTokens,
    ChartPaletteTokens,
    EmphasisTokens,
    FontRole,
    ObjectStyleOutcome,
    PaletteTokens,
    SemanticColorRole,
    SemanticEmphasis,
    SemanticTokenRole,
    StyleRole,
    SurfaceTokens,
    TableTokens,
    ThemeDefinition,
    ThemeMode,
    TypographyTokens,
    compute_theme_fingerprint,
)
from app.services.presentation.visual.design_tokens import SLIDE_THEME_PRESETS, SLIDE_THEME_ALIASES
from app.services.presentation.visual.visual_validator import (
    calculate_contrast_ratio,
    parse_hex_color,
)

logger = logging.getLogger(__name__)


# Standard Office-safe font fallback stacks
OFFICE_SAFE_FONTS = {
    FontRole.DISPLAY: ["Trebuchet MS", "Arial", "Calibri", "Segoe UI"],
    FontRole.HEADING: ["Arial", "Calibri", "Trebuchet MS", "Segoe UI"],
    FontRole.BODY: ["Calibri", "Arial", "Segoe UI", "Tahoma"],
    FontRole.NUMERIC: ["Calibri", "Arial", "Trebuchet MS"],
    FontRole.MONO: ["Consolas", "Courier New", "Lucida Console"],
    FontRole.CAPTION: ["Calibri", "Arial", "Segoe UI"],
}


class FontResolver:
    """Resolves typography families to PowerPoint and Office-safe font names.

    Detects potential reflow risks when substituting display web fonts with
    standard desktop fonts. Never modifies font size or layout bounds.
    """

    @classmethod
    def resolve_font(
        cls,
        theme: ThemeDefinition,
        role: FontRole,
        available_fonts: Optional[set[str]] = None,
    ) -> tuple[str, list[str]]:
        """Resolves font family for role, returning (resolved_family_name, warnings)."""
        warnings = []
        raw_font = cls._get_raw_font(theme, role)
        # Parse font-family CSS string into candidates
        candidates = [c.strip().strip("'\"") for c in raw_font.split(",") if c.strip()]
        
        # Office-safe fallbacks for this role
        office_fallbacks = OFFICE_SAFE_FONTS.get(role, ["Arial", "Calibri"])
        all_candidates = candidates + office_fallbacks

        if available_fonts is not None:
            for font in all_candidates:
                if font in available_fonts:
                    if font != candidates[0]:
                        warnings.append(
                            f"STYLE_REFLOW_RISK: Preferred font '{candidates[0]}' unavailable for role '{role.value}', substituted with '{font}'."
                        )
                    return font, warnings

        # In default environment without font probing, select the primary Office-safe font
        # from candidates or fallbacks.
        chosen = office_fallbacks[0]
        for c in candidates:
            # If candidate is already an office-safe font, use it directly
            for safe in office_fallbacks:
                if c.lower() == safe.lower():
                    return safe, warnings

        # If primary candidate is a custom web font (e.g. Space Grotesk), flag reflow risk
        warnings.append(
            f"STYLE_REFLOW_RISK: Selected font fallback '{chosen}' for primary web font '{candidates[0]}'."
        )
        return chosen, warnings

    @staticmethod
    def _get_raw_font(theme: ThemeDefinition, role: FontRole) -> str:
        if role == FontRole.DISPLAY:
            return theme.typography.display_family
        elif role == FontRole.HEADING:
            return theme.typography.heading_family
        elif role == FontRole.BODY:
            return theme.typography.body_family
        elif role == FontRole.NUMERIC:
            return theme.typography.numeric_family
        elif role == FontRole.MONO:
            return theme.typography.mono_family
        elif role == FontRole.CAPTION:
            return theme.typography.caption_family
        return theme.typography.body_family


class StyleTokenResolver:
    """Resolves semantic tokens and enforces deterministic contrast compliance."""

    def __init__(self, theme: ThemeDefinition):
        self.theme = theme
        self.policy = theme.accessibility_policy

    def resolve_color(self, token: SemanticTokenRole | str) -> str:
        """Resolve semantic color token to hex."""
        return self.theme.get_token_hex(token)

    def check_and_resolve_contrast(
        self,
        fg_hex: str,
        bg_hex: str,
        target_id: str,
        target_type: str,
        is_large_text: bool = False,
    ) -> tuple[str, AccessibilityAuditResult]:
        """Validates contrast ratio and applies auto-contrast resolution if necessary."""
        ratio = calculate_contrast_ratio(fg_hex, bg_hex)
        threshold = self.policy.min_large_contrast if is_large_text else self.policy.min_normal_contrast

        if ratio >= threshold:
            audit = AccessibilityAuditResult(
                target_id=target_id,
                target_type=target_type,
                foreground_hex=fg_hex,
                background_hex=bg_hex,
                contrast_ratio=ratio,
                threshold=threshold,
                passed=True,
                auto_resolved=False,
            )
            return fg_hex, audit

        # Auto-contrast resolution
        if self.policy.auto_contrast_resolution:
            # Test high-contrast alternatives
            alt_dark = self.theme.get_token_hex(SemanticTokenRole.TEXT_ON_DARK)
            alt_light = self.theme.get_token_hex(SemanticTokenRole.TEXT_ON_LIGHT)
            
            ratio_dark = calculate_contrast_ratio(alt_dark, bg_hex)
            ratio_light = calculate_contrast_ratio(alt_light, bg_hex)

            if ratio_dark >= ratio_light:
                chosen_hex = alt_dark
                chosen_token = "TEXT_ON_DARK"
                chosen_ratio = ratio_dark
            else:
                chosen_hex = alt_light
                chosen_token = "TEXT_ON_LIGHT"
                chosen_ratio = ratio_light

            passed = chosen_ratio >= threshold
            audit = AccessibilityAuditResult(
                target_id=target_id,
                target_type=target_type,
                foreground_hex=chosen_hex,
                background_hex=bg_hex,
                contrast_ratio=chosen_ratio,
                threshold=threshold,
                passed=passed,
                auto_resolved=True,
                resolution_token=chosen_token,
            )
            return chosen_hex, audit

        audit = AccessibilityAuditResult(
            target_id=target_id,
            target_type=target_type,
            foreground_hex=fg_hex,
            background_hex=bg_hex,
            contrast_ratio=ratio,
            threshold=threshold,
            passed=False,
            auto_resolved=False,
        )
        return fg_hex, audit


class TextStyleResolver:
    """Resolves typography styling for text frames and runs."""

    def __init__(self, token_resolver: StyleTokenResolver):
        self.token_resolver = token_resolver
        self.theme = token_resolver.theme

    def resolve_text_style(
        self,
        style_role: StyleRole,
        bg_hex: str,
        target_id: str,
        emphasis: Optional[SemanticEmphasis] = None,
        is_title_slide: bool = False,
    ) -> tuple[dict[str, Any], list[AccessibilityAuditResult], list[str]]:
        """Resolves font family, bold, color, and contrast audit for a text role."""
        warnings: list[str] = []
        audits: list[AccessibilityAuditResult] = []

        is_large = style_role in (StyleRole.TITLE, StyleRole.KPI_VALUE)

        # 1. Determine font role
        if style_role == StyleRole.TITLE:
            font_role = FontRole.DISPLAY if is_title_slide else FontRole.HEADING
        elif style_role in (StyleRole.SUBTITLE, StyleRole.TABLE_HEADER):
            font_role = FontRole.HEADING
        elif style_role == StyleRole.KPI_VALUE:
            font_role = FontRole.NUMERIC
        elif style_role in (StyleRole.CAPTION, StyleRole.FOOTNOTE, StyleRole.PAGE_NUMBER):
            font_role = FontRole.CAPTION
        else:
            font_role = FontRole.BODY

        family, font_warnings = FontResolver.resolve_font(self.theme, font_role)
        warnings.extend(font_warnings)

        # 2. Determine base color token
        if emphasis == SemanticEmphasis.POSITIVE:
            base_color = self.token_resolver.resolve_color(SemanticTokenRole.SUCCESS)
        elif emphasis == SemanticEmphasis.NEGATIVE:
            base_color = self.token_resolver.resolve_color(SemanticTokenRole.DANGER)
        elif emphasis == SemanticEmphasis.WARNING:
            base_color = self.token_resolver.resolve_color(SemanticTokenRole.WARNING)
        elif style_role == StyleRole.TITLE:
            base_color = self.token_resolver.resolve_color(SemanticTokenRole.TEXT_PRIMARY)
        elif style_role == StyleRole.SUBTITLE:
            base_color = self.token_resolver.resolve_color(SemanticTokenRole.TEXT_SECONDARY)
        elif style_role in (StyleRole.KPI_LABEL, StyleRole.CAPTION, StyleRole.FOOTNOTE, StyleRole.PAGE_NUMBER):
            base_color = self.token_resolver.resolve_color(SemanticTokenRole.TEXT_MUTED)
        elif style_role == StyleRole.KPI_VALUE:
            base_color = self.token_resolver.resolve_color(SemanticTokenRole.ACCENT_PRIMARY)
        elif style_role == StyleRole.TABLE_HEADER:
            base_color = self.theme.table_tokens.header_text
        else:
            base_color = self.token_resolver.resolve_color(SemanticTokenRole.TEXT_PRIMARY)

        # 3. Contrast check
        resolved_color, audit = self.token_resolver.check_and_resolve_contrast(
            fg_hex=base_color,
            bg_hex=bg_hex,
            target_id=target_id,
            target_type=style_role.value,
            is_large_text=is_large,
        )
        audits.append(audit)

        # 4. Font weight
        is_bold = style_role in (StyleRole.TITLE, StyleRole.KPI_VALUE, StyleRole.TABLE_HEADER)
        is_italic = style_role in (StyleRole.FOOTNOTE, StyleRole.CAPTION)

        result = {
            "font_family": family,
            "font_color_hex": resolved_color,
            "bold": is_bold,
            "italic": is_italic,
            "style_role": style_role,
        }
        return result, audits, warnings


class SemanticColorResolver:
    """Central authoritative resolver for visual presentation colors and contrast.

    Enforces the semantic split:
    - DATA / SEMANTIC: Preserves categorical identity, status meaning, and analytical fidelity.
    - PRESENTATION / CHROME: Adapts to theme template with role-specific contrast thresholds:
        * Text & Essential Labels: WCAG AAA (>= 7.0:1 normal, >= 4.5:1 large/bold)
        * Essential Boundaries: Non-text contrast (>= 3.0:1)
        * Decorative Gridlines: Subtly perceptible (1.2:1 to 2.5:1 against local surface)
    """

    def __init__(self, theme: ThemeDefinition):
        self.theme = theme
        self.policy = theme.accessibility_policy
        self.token_resolver = StyleTokenResolver(theme)
        self._series_color_cache: dict[str, str] = {}

    def resolve_color(
        self,
        role: SemanticColorRole | str,
        surface_hex: Optional[str] = None,
        is_large_text: bool = False,
        target_id: str = "",
    ) -> tuple[str, AccessibilityAuditResult]:
        """Resolves color for a semantic role against its immediate surface with deterministic repair."""
        if isinstance(role, str):
            try:
                role_enum = SemanticColorRole(role.upper())
            except ValueError:
                role_enum = SemanticColorRole.BODY
        else:
            role_enum = role

        # Local surface selection: default to card surface for visuals, slide bg for framing
        if surface_hex:
            local_surface = surface_hex
        elif role_enum in (
            SemanticColorRole.SLIDE_BACKGROUND,
            SemanticColorRole.TITLE,
            SemanticColorRole.SUBTITLE,
        ):
            local_surface = self.theme.palette.background
        else:
            local_surface = self.theme.palette.surface

        # 1. Surfaces
        if role_enum == SemanticColorRole.SLIDE_BACKGROUND:
            return self.theme.palette.background, self._audit(target_id or "SLIDE_BG", "SURFACE", self.theme.palette.background, self.theme.palette.background, 1.0, 1.0, True)
        if role_enum == SemanticColorRole.CARD_SURFACE:
            return self.theme.palette.surface, self._audit(target_id or "CARD_BG", "SURFACE", self.theme.palette.surface, self.theme.palette.background, 1.0, 1.0, True)
        if role_enum == SemanticColorRole.CHART_PLOT_SURFACE:
            return self.theme.palette.surface, self._audit(target_id or "CHART_PLOT_BG", "SURFACE", self.theme.palette.surface, self.theme.palette.surface, 1.0, 1.0, True)
        if role_enum == SemanticColorRole.TABLE_HEADER_SURFACE:
            return self.theme.table_tokens.header_fill, self._audit(target_id or "TABLE_HEADER_BG", "SURFACE", self.theme.table_tokens.header_fill, local_surface, 1.0, 1.0, True)
        if role_enum == SemanticColorRole.TABLE_ROW_ALT_SURFACE:
            alt = self.theme.table_tokens.alt_row_fill or local_surface
            return alt, self._audit(target_id or "TABLE_ROW_ALT_BG", "SURFACE", alt, local_surface, 1.0, 1.0, True)

        # 2. Decorative Gridlines (Target: 1.2:1 to 2.5:1, subtle not harsh)
        if role_enum in (SemanticColorRole.GRID_LINE, SemanticColorRole.REFERENCE_LINE_SUBTLE):
            raw_grid = self.theme.get_token_hex(SemanticTokenRole.GRID_LINE)
            ratio = calculate_contrast_ratio(raw_grid, local_surface)
            chosen_grid = raw_grid
            if ratio < 1.2:
                muted = self.theme.get_token_hex(SemanticTokenRole.TEXT_MUTED)
                if calculate_contrast_ratio(muted, local_surface) >= 1.2:
                    chosen_grid = muted
            return chosen_grid, self._audit(target_id or "GRID_LINE", "DECORATIVE_LINE", chosen_grid, local_surface, ratio, 1.2, ratio >= 1.2)

        # 3. Essential Graphical Boundaries (Target: non-text contrast >= 3.0:1)
        if role_enum in (SemanticColorRole.CARD_BORDER, SemanticColorRole.AXIS_LINE, SemanticColorRole.TABLE_BORDER):
            if role_enum == SemanticColorRole.AXIS_LINE:
                candidate = self.theme.get_token_hex(SemanticTokenRole.TEXT_MUTED)
            elif role_enum == SemanticColorRole.TABLE_BORDER:
                candidate = self.theme.table_tokens.border
            else:
                candidate = self.theme.border_tokens.subtle

            ratio = calculate_contrast_ratio(candidate, local_surface)
            if ratio >= 3.0:
                return candidate, self._audit(target_id or role_enum.value, "BOUNDARY", candidate, local_surface, ratio, 3.0, True)

            strong_border = self.theme.border_tokens.strong
            r_strong = calculate_contrast_ratio(strong_border, local_surface)
            if r_strong >= 3.0:
                return strong_border, self._audit(target_id or role_enum.value, "BOUNDARY", strong_border, local_surface, r_strong, 3.0, True, True, "BORDER_STRONG")

            alt = self.theme.get_token_hex(SemanticTokenRole.TEXT_SECONDARY)
            r_alt = calculate_contrast_ratio(alt, local_surface)
            return alt, self._audit(target_id or role_enum.value, "BOUNDARY", alt, local_surface, r_alt, 3.0, r_alt >= 3.0, True, "TEXT_SECONDARY")

        # 4. Data / Semantic Status (Preserve meaning; check legibility >= 2.5:1)
        if role_enum == SemanticColorRole.STATUS_POSITIVE:
            c = self.theme.get_token_hex(SemanticTokenRole.SUCCESS)
            r = calculate_contrast_ratio(c, local_surface)
            return c, self._audit(target_id or "STATUS_POSITIVE", "SEMANTIC_DATA", c, local_surface, r, 2.5, r >= 2.5)
        if role_enum == SemanticColorRole.STATUS_NEGATIVE:
            c = self.theme.get_token_hex(SemanticTokenRole.DANGER)
            r = calculate_contrast_ratio(c, local_surface)
            return c, self._audit(target_id or "STATUS_NEGATIVE", "SEMANTIC_DATA", c, local_surface, r, 2.5, r >= 2.5)
        if role_enum == SemanticColorRole.STATUS_WARNING:
            c = self.theme.get_token_hex(SemanticTokenRole.WARNING)
            r = calculate_contrast_ratio(c, local_surface)
            return c, self._audit(target_id or "STATUS_WARNING", "SEMANTIC_DATA", c, local_surface, r, 2.5, r >= 2.5)
        if role_enum == SemanticColorRole.STATUS_NEUTRAL:
            c = self.theme.get_token_hex(SemanticTokenRole.TEXT_MUTED)
            r = calculate_contrast_ratio(c, local_surface)
            return c, self._audit(target_id or "STATUS_NEUTRAL", "SEMANTIC_DATA", c, local_surface, r, 2.5, r >= 2.5)

        # 5. Text & Essential Labels (WCAG AAA Target: >= 7.0:1 normal, >= 4.5:1 large/bold)
        threshold = 4.5 if is_large_text else 7.0
        if role_enum in (SemanticColorRole.TITLE, SemanticColorRole.KPI_VALUE):
            candidate = self.theme.get_token_hex(SemanticTokenRole.TEXT_PRIMARY)
        elif role_enum in (SemanticColorRole.SUBTITLE, SemanticColorRole.AXIS_TITLE, SemanticColorRole.TABLE_HEADER_TEXT):
            candidate = self.theme.get_token_hex(SemanticTokenRole.TEXT_SECONDARY)
        elif role_enum in (
            SemanticColorRole.AXIS_TEXT,
            SemanticColorRole.TICK_TEXT,
            SemanticColorRole.LEGEND_TEXT,
            SemanticColorRole.DATA_LABEL,
            SemanticColorRole.ANNOTATION_TEXT,
            SemanticColorRole.KPI_LABEL,
        ):
            candidate = self.theme.get_token_hex(SemanticTokenRole.TEXT_SECONDARY)
        elif role_enum == SemanticColorRole.TABLE_CELL_TEXT:
            candidate = self.theme.table_tokens.body_text
        else:
            candidate = self.theme.get_token_hex(SemanticTokenRole.TEXT_PRIMARY)

        ratio = calculate_contrast_ratio(candidate, local_surface)
        if ratio >= threshold:
            return candidate, self._audit(target_id or role_enum.value, "TEXT", candidate, local_surface, ratio, threshold, True)

        # Deterministic Color Repair for text/labels
        alt_dark = self.theme.get_token_hex(SemanticTokenRole.TEXT_ON_DARK)
        alt_light = self.theme.get_token_hex(SemanticTokenRole.TEXT_ON_LIGHT)
        r_dark = calculate_contrast_ratio(alt_dark, local_surface)
        r_light = calculate_contrast_ratio(alt_light, local_surface)

        best_token = "TEXT_ON_DARK" if r_dark >= r_light else "TEXT_ON_LIGHT"
        best_candidate = alt_dark if r_dark >= r_light else alt_light
        best_ratio = max(r_dark, r_light)

        return best_candidate, self._audit(target_id or role_enum.value, "TEXT", best_candidate, local_surface, best_ratio, threshold, best_ratio >= threshold, True, best_token)

    def resolve_series_color(
        self,
        series_name: str,
        series_index: int,
        status_intent: Optional[str] = None,
    ) -> str:
        """Deterministically assigns series color while maintaining deck-wide consistency."""
        clean_name = series_name.strip().lower()
        if clean_name in self._series_color_cache:
            return self._series_color_cache[clean_name]

        if status_intent and status_intent in self.theme.chart_palette.status:
            chosen = self.theme.chart_palette.status[status_intent]
            self._series_color_cache[clean_name] = chosen
            return chosen

        palette = self.theme.chart_palette.categorical
        if not palette:
            palette = [self.theme.palette.brand, self.theme.palette.accent]
        chosen = palette[series_index % len(palette)]
        self._series_color_cache[clean_name] = chosen
        return chosen

    def resolve_chart_chrome(
        self,
        surface_hex: Optional[str] = None,
    ) -> tuple[dict[str, Any], list[AccessibilityAuditResult]]:
        """Resolves complete visual chart chrome with local surface AAA contrast."""
        audits: list[AccessibilityAuditResult] = []
        plot_bg = surface_hex or self.theme.palette.surface

        axis_line, a_audit = self.resolve_color(SemanticColorRole.AXIS_LINE, plot_bg, target_id="CHART_AXIS_LINE")
        audits.append(a_audit)

        grid_line, g_audit = self.resolve_color(SemanticColorRole.GRID_LINE, plot_bg, target_id="CHART_GRID_LINE")
        audits.append(g_audit)

        tick_text, t_audit = self.resolve_color(SemanticColorRole.TICK_TEXT, plot_bg, is_large_text=False, target_id="CHART_TICK_TEXT")
        audits.append(t_audit)

        axis_title, at_audit = self.resolve_color(SemanticColorRole.AXIS_TITLE, plot_bg, is_large_text=False, target_id="CHART_AXIS_TITLE")
        audits.append(at_audit)

        legend_text, l_audit = self.resolve_color(SemanticColorRole.LEGEND_TEXT, plot_bg, is_large_text=False, target_id="CHART_LEGEND_TEXT")
        audits.append(l_audit)

        data_label, dl_audit = self.resolve_color(SemanticColorRole.DATA_LABEL, plot_bg, is_large_text=False, target_id="CHART_DATA_LABEL")
        audits.append(dl_audit)

        font_family, _ = FontResolver.resolve_font(self.theme, FontRole.CAPTION)

        return {
            "plot_bg_hex": plot_bg,
            "axis_line_color_hex": axis_line,
            "grid_color_hex": grid_line,
            "tick_text_color_hex": tick_text,
            "axis_title_color_hex": axis_title,
            "legend_text_color_hex": legend_text,
            "data_label_color_hex": data_label,
            "font_family": font_family,
            # Backward-compatibility aliases
            "axis_color_hex": axis_line,
            "label_color_hex": tick_text,
        }, audits

    def resolve_table_chrome(
        self,
        surface_hex: Optional[str] = None,
        table_object_id: str = "TABLE",
    ) -> tuple[dict[str, Any], list[AccessibilityAuditResult], list[str]]:
        """Resolves complete table styling with local surface contrast."""
        audits: list[AccessibilityAuditResult] = []
        warnings: list[str] = []
        card_bg = surface_hex or self.theme.palette.surface

        header_fill = self.theme.table_tokens.header_fill
        header_text, h_audit = self.resolve_color(SemanticColorRole.TABLE_HEADER_TEXT, header_fill, target_id=f"{table_object_id}__HEADER")
        audits.append(h_audit)

        body_text, b_audit = self.resolve_color(SemanticColorRole.TABLE_CELL_TEXT, card_bg, target_id=f"{table_object_id}__BODY")
        audits.append(b_audit)

        border_color, brd_audit = self.resolve_color(SemanticColorRole.TABLE_BORDER, card_bg, target_id=f"{table_object_id}__BORDER")
        audits.append(brd_audit)

        alt_fill = self.theme.table_tokens.alt_row_fill or card_bg

        font_family, f_warnings = FontResolver.resolve_font(self.theme, FontRole.BODY)
        warnings.extend(f_warnings)

        return {
            "header_fill_hex": header_fill,
            "header_text_hex": header_text,
            "body_text_hex": body_text,
            "alt_row_fill_hex": alt_fill,
            "border_color_hex": border_color,
            "font_family": font_family,
            "header_contrast": h_audit.contrast_ratio,
            "body_contrast": b_audit.contrast_ratio,
        }, audits, warnings

    def resolve_asset_palette(
        self,
        surface_hex: Optional[str] = None,
    ) -> dict[str, Any]:
        """Resolves full typed RGB/RGBA palette for Pillow and SVG visual rendering."""
        card_bg = surface_hex or self.theme.palette.surface
        is_dark = self.theme.is_dark

        card_border, _ = self.resolve_color(SemanticColorRole.CARD_BORDER, card_bg)
        title_text, _ = self.resolve_color(SemanticColorRole.TITLE, card_bg, is_large_text=True)
        body_text, _ = self.resolve_color(SemanticColorRole.BODY, card_bg)
        muted_text, _ = self.resolve_color(SemanticColorRole.TICK_TEXT, card_bg)
        grid_line, _ = self.resolve_color(SemanticColorRole.GRID_LINE, card_bg)
        axis_line, _ = self.resolve_color(SemanticColorRole.AXIS_LINE, card_bg)

        success_val = self.theme.get_token_hex(SemanticTokenRole.SUCCESS)
        danger_val = self.theme.get_token_hex(SemanticTokenRole.DANGER)
        neutral_val = self.theme.get_token_hex(SemanticTokenRole.TEXT_MUTED)

        def _rgba(hex_str: str, alpha: int = 255) -> tuple[int, int, int, int]:
            r, g, b = parse_hex_color(hex_str)
            return (r, g, b, alpha)

        return {
            "is_dark": is_dark,
            "card_bg_hex": card_bg,
            "card_bg_rgba": _rgba(card_bg),
            "card_border_rgba": _rgba(card_border),
            "title_text_rgba": _rgba(title_text),
            "body_text_rgba": _rgba(body_text),
            "muted_text_rgba": _rgba(muted_text),
            "grid_line_rgba": _rgba(grid_line),
            "axis_line_rgba": _rgba(axis_line),
            "status_success": {
                "bg_rgba": _rgba(card_bg),
                "border_rgba": _rgba(success_val, 160),
                "val_rgba": _rgba(success_val),
            },
            "status_danger": {
                "bg_rgba": _rgba(card_bg),
                "border_rgba": _rgba(danger_val, 160),
                "val_rgba": _rgba(danger_val),
            },
            "status_neutral": {
                "bg_rgba": _rgba(card_bg),
                "border_rgba": _rgba(card_border),
                "val_rgba": _rgba(neutral_val),
            },
        }

    def _audit(
        self,
        target_id: str,
        target_type: str,
        fg_hex: str,
        bg_hex: str,
        ratio: float,
        threshold: float,
        passed: bool,
        auto_resolved: bool = False,
        resolution_token: Optional[str] = None,
    ) -> AccessibilityAuditResult:
        return AccessibilityAuditResult(
            target_id=target_id,
            target_type=target_type,
            foreground_hex=fg_hex,
            background_hex=bg_hex,
            contrast_ratio=round(ratio, 2),
            threshold=threshold,
            passed=passed,
            auto_resolved=auto_resolved,
            resolution_token=resolution_token,
        )


class TableStyleResolver:
    """Resolves colors and borders for native DrawingML tables."""

    def __init__(self, token_resolver: StyleTokenResolver):
        self.token_resolver = token_resolver
        self.theme = token_resolver.theme
        self.semantic_resolver = SemanticColorResolver(self.theme)

    def resolve_table_style(
        self,
        table_object_id: str,
        slide_bg_hex: str,
    ) -> tuple[dict[str, Any], list[AccessibilityAuditResult], list[str]]:
        """Resolves header fill, header text, body text, alternate row fill, and borders."""
        return self.semantic_resolver.resolve_table_chrome(
            surface_hex=slide_bg_hex,
            table_object_id=table_object_id,
        )


class ChartStyleResolver:
    """Resolves deterministic color palettes for chart series and axes."""

    def __init__(self, token_resolver: StyleTokenResolver):
        self.token_resolver = token_resolver
        self.theme = token_resolver.theme
        self.semantic_resolver = SemanticColorResolver(self.theme)

    def resolve_series_color(
        self,
        series_name: str,
        series_index: int,
        status_intent: Optional[str] = None,
    ) -> str:
        """Deterministically assigns series color while maintaining deck-wide consistency."""
        return self.semantic_resolver.resolve_series_color(
            series_name=series_name,
            series_index=series_index,
            status_intent=status_intent,
        )

    def resolve_chart_chrome(
        self,
        slide_bg_hex: str,
    ) -> tuple[dict[str, Any], list[AccessibilityAuditResult]]:
        """Resolves axis line, gridline, and label styling with contrast checking."""
        return self.semantic_resolver.resolve_chart_chrome(surface_hex=slide_bg_hex)


class ThemeEngine:
    """HighView Central Presentation Theme Engine.

    Builds, registers, and serves typed ThemeDefinition instances.
    Provides factory methods and style resolvers for PPT-L7.
    """

    _registry: dict[str, ThemeDefinition] = {}

    @classmethod
    def get_theme(cls, theme_input: Any = None) -> ThemeDefinition:
        """Retrieves or builds a canonical ThemeDefinition by id or dict."""
        cls._ensure_registry_loaded()

        raw_id = (
            theme_input
            if isinstance(theme_input, str)
            else (theme_input or {}).get("id") or (theme_input or {}).get("theme_id")
        )
        key = str(raw_id or "executive_dark").strip().lower().replace("-", "_")
        normalized_key = SLIDE_THEME_ALIASES.get(key, key)

        if normalized_key in cls._registry:
            return cls._registry[normalized_key]

        return cls._registry.get("executive_dark") or next(iter(cls._registry.values()))

    @classmethod
    def get_semantic_resolver(cls, theme_input: Any = None) -> SemanticColorResolver:
        """Retrieves or builds a SemanticColorResolver for the resolved theme."""
        theme = cls.get_theme(theme_input)
        return SemanticColorResolver(theme)

    @classmethod
    def _ensure_registry_loaded(cls) -> None:
        if cls._registry:
            return

        for preset_id, preset_data in SLIDE_THEME_PRESETS.items():
            theme_def = cls._build_theme_definition(preset_id, preset_data)
            cls._registry[preset_id] = theme_def

        for alias, target in SLIDE_THEME_ALIASES.items():
            if target in cls._registry:
                aliased = copy.deepcopy(cls._registry[target])
                aliased.theme_id = alias
                aliased.theme_fingerprint = compute_theme_fingerprint(aliased)
                cls._registry[alias] = aliased

    @classmethod
    def _build_theme_definition(cls, preset_id: str, data: dict[str, Any]) -> ThemeDefinition:
        is_dark = data.get("is_dark", True)
        mode = ThemeMode.DARK if is_dark else ThemeMode.LIGHT

        bg = data.get("bg_color", "#08111F")
        card_bg = data.get("card_bg", "#0F1B2D")
        surface_alt = data.get("surface_alt", "#141820")
        primary_text = data.get("primary_text", "#F8FAFC")
        secondary_text = data.get("secondary_text", "#CBD5E1")
        muted_text = data.get("muted_text", "#94A3B8")
        brand = data.get("brand_color", "#7AB4FB")
        accent = data.get("accent_color", "#5EEAD4")
        positive = data.get("success_color", "#A3E635")
        negative = data.get("danger_color", "#FA9494")
        warning = data.get("warning_color", "#FBBF24")
        border = data.get("card_border", "#5C6A7A")

        palette = PaletteTokens(
            background=bg,
            surface=card_bg,
            surface_alt=surface_alt,
            surface_elevated=card_bg,
            primary_text=primary_text,
            secondary_text=secondary_text,
            muted_text=muted_text,
            brand=brand,
            accent=accent,
            positive=positive,
            negative=negative,
            warning=warning,
            border_subtle=border,
            border_strong=brand,
            grid=border,
        )

        display_font = data.get("font_display", "'Space Grotesk', system-ui, sans-serif")
        body_font = data.get("font_body", "'Plus Jakarta Sans', system-ui, sans-serif")
        mono_font = data.get("font_mono", "'Space Mono', monospace")

        typography = TypographyTokens(
            display_family=display_font,
            heading_family=display_font,
            body_family=body_font,
            numeric_family=display_font,
            mono_family=mono_font,
            caption_family=body_font,
            fallback_family="Arial, Calibri, sans-serif",
        )

        chart_palette_list = list(data.get("chart_palette", [accent, brand, positive, warning, negative]))
        chart_palettes = ChartPaletteTokens(
            categorical=chart_palette_list,
            sequential=[bg, brand, accent, primary_text],
            diverging=[positive, warning, negative],
            status={
                "positive": positive,
                "warning": warning,
                "negative": negative,
                "info": brand,
                "neutral": secondary_text,
            },
        )

        table_tokens = TableTokens(
            header_fill=card_bg if is_dark else surface_alt,
            header_text=primary_text,
            body_text=secondary_text,
            alt_row_fill=surface_alt,
            border=border,
        )

        surface_tokens = SurfaceTokens(
            primary=card_bg,
            elevated=card_bg,
            alt=surface_alt,
            radius="12px",
            shadow="0 10px 25px -5px rgba(0, 0, 0, 0.3)",
        )

        border_tokens = BorderTokens(
            subtle=border,
            strong=brand,
            accent=accent,
        )

        emphasis_tokens = EmphasisTokens(
            primary=brand,
            secondary=accent,
            positive=positive,
            negative=negative,
            warning=warning,
            neutral=muted_text,
            highlight=accent,
        )

        theme_def = ThemeDefinition(
            theme_id=preset_id,
            name=data.get("name", preset_id.replace("_", " ").title()),
            version="1.0.0",
            mode=mode,
            is_dark=is_dark,
            palette=palette,
            typography=typography,
            chart_palette=chart_palettes,
            table_tokens=table_tokens,
            surface_tokens=surface_tokens,
            border_tokens=border_tokens,
            emphasis_tokens=emphasis_tokens,
            accessibility_policy=AccessibilityPolicy(
                min_normal_contrast=4.5,
                min_large_contrast=3.0,
                target_normal_contrast=7.0,
                auto_contrast_resolution=True,
            ),
        )
        theme_def.theme_fingerprint = compute_theme_fingerprint(theme_def)
        return theme_def
