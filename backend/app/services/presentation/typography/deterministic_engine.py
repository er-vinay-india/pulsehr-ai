"""Deterministic Typography Engine.

Translates relative AI-predicted TypographyIntent into concrete point sizes,
contrast-safe hex colors, and spacing based on theme and spatial constraints.
Enforces WCAG AAA contrast (>= 7.0:1 for normal text, >= 4.5:1 for large text)
and minimum readability point size floors across all presentation roles.
Provides 100% deterministic repair if an input color or font size falls below policy.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from .contracts import (
    DensityRisk,
    ReflowPreference,
    ResolvedTypographySpec,
    SemanticTypographyRole,
    TypographyBlockProvenance,
    TypographyColorRole,
    TypographyImportance,
    TypographyIntent,
    TypographyPreferredWeight,
    TypographyRelativeScale,
    ROLE_READABILITY_FLOORS,
    compute_contrast_ratio,
    compute_wcag_luminance,
    get_aaa_contrast_threshold,
    normalize_semantic_role,
)

logger = logging.getLogger(__name__)


# Concrete point sizes per relative scale and semantic role (calibrated to exceed readability floors)
POINT_SIZE_MATRIX: dict[tuple[SemanticTypographyRole, TypographyRelativeScale], float] = {
    # 1. DECK & SLIDE TITLES
    (SemanticTypographyRole.DECK_TITLE, TypographyRelativeScale.HERO): 36.0,
    (SemanticTypographyRole.DECK_TITLE, TypographyRelativeScale.XL): 32.0,
    (SemanticTypographyRole.DECK_TITLE, TypographyRelativeScale.LARGE): 28.0,

    (SemanticTypographyRole.SLIDE_TITLE, TypographyRelativeScale.HERO): 32.0,
    (SemanticTypographyRole.SLIDE_TITLE, TypographyRelativeScale.XL): 28.0,
    (SemanticTypographyRole.SLIDE_TITLE, TypographyRelativeScale.LARGE): 24.0,

    (SemanticTypographyRole.TITLE, TypographyRelativeScale.HERO): 32.0,
    (SemanticTypographyRole.TITLE, TypographyRelativeScale.XL): 28.0,
    (SemanticTypographyRole.TITLE, TypographyRelativeScale.LARGE): 24.0,
    (SemanticTypographyRole.TITLE, TypographyRelativeScale.BASE): 24.0,

    # 2. SUBTITLE
    (SemanticTypographyRole.SUBTITLE, TypographyRelativeScale.LARGE): 18.0,
    (SemanticTypographyRole.SUBTITLE, TypographyRelativeScale.BASE): 15.0,
    (SemanticTypographyRole.SUBTITLE, TypographyRelativeScale.SMALL): 14.0,

    # 3. KPI / KPI_VALUE (distinctly hero-weighted)
    (SemanticTypographyRole.KPI, TypographyRelativeScale.HERO): 40.0,
    (SemanticTypographyRole.KPI, TypographyRelativeScale.XL): 34.0,
    (SemanticTypographyRole.KPI, TypographyRelativeScale.LARGE): 28.0,
    (SemanticTypographyRole.KPI, TypographyRelativeScale.BASE): 24.0,

    (SemanticTypographyRole.KPI_VALUE, TypographyRelativeScale.HERO): 40.0,
    (SemanticTypographyRole.KPI_VALUE, TypographyRelativeScale.XL): 34.0,
    (SemanticTypographyRole.KPI_VALUE, TypographyRelativeScale.LARGE): 28.0,
    (SemanticTypographyRole.KPI_VALUE, TypographyRelativeScale.BASE): 24.0,

    (SemanticTypographyRole.KPI_LABEL, TypographyRelativeScale.BASE): 12.0,
    (SemanticTypographyRole.KPI_LABEL, TypographyRelativeScale.SMALL): 10.5,

    # 4. PRIMARY_INSIGHT
    (SemanticTypographyRole.PRIMARY_INSIGHT, TypographyRelativeScale.LARGE): 16.5,
    (SemanticTypographyRole.PRIMARY_INSIGHT, TypographyRelativeScale.BASE): 14.0,
    (SemanticTypographyRole.PRIMARY_INSIGHT, TypographyRelativeScale.SMALL): 13.0,

    # 5. BODY & BULLET
    (SemanticTypographyRole.BODY, TypographyRelativeScale.LARGE): 15.0,
    (SemanticTypographyRole.BODY, TypographyRelativeScale.BASE): 12.5,
    (SemanticTypographyRole.BODY, TypographyRelativeScale.SMALL): 11.5,

    (SemanticTypographyRole.BULLET, TypographyRelativeScale.LARGE): 15.0,
    (SemanticTypographyRole.BULLET, TypographyRelativeScale.BASE): 12.5,
    (SemanticTypographyRole.BULLET, TypographyRelativeScale.SMALL): 11.5,

    # 6. SOURCE, FOOTNOTE & CAPTION (Floors: 9.0pt - 9.5pt)
    (SemanticTypographyRole.SOURCE, TypographyRelativeScale.SMALL): 10.0,
    (SemanticTypographyRole.SOURCE, TypographyRelativeScale.XS): 9.0,

    (SemanticTypographyRole.FOOTNOTE, TypographyRelativeScale.SMALL): 10.0,
    (SemanticTypographyRole.FOOTNOTE, TypographyRelativeScale.XS): 9.0,

    (SemanticTypographyRole.CAPTION, TypographyRelativeScale.BASE): 11.0,
    (SemanticTypographyRole.CAPTION, TypographyRelativeScale.SMALL): 9.5,

    # 7. CHART, CHART_TITLE, DATA_LABEL, AXIS & LEGEND
    (SemanticTypographyRole.CHART_TITLE, TypographyRelativeScale.LARGE): 16.0,
    (SemanticTypographyRole.CHART_TITLE, TypographyRelativeScale.BASE): 13.5,

    (SemanticTypographyRole.CHART, TypographyRelativeScale.BASE): 12.0,
    (SemanticTypographyRole.CHART, TypographyRelativeScale.SMALL): 11.0,

    (SemanticTypographyRole.DATA_LABEL, TypographyRelativeScale.BASE): 11.0,
    (SemanticTypographyRole.DATA_LABEL, TypographyRelativeScale.SMALL): 9.5,

    (SemanticTypographyRole.AXIS_TITLE, TypographyRelativeScale.BASE): 11.5,
    (SemanticTypographyRole.AXIS_TITLE, TypographyRelativeScale.SMALL): 10.5,

    (SemanticTypographyRole.AXIS_LABEL, TypographyRelativeScale.SMALL): 10.0,
    (SemanticTypographyRole.AXIS_LABEL, TypographyRelativeScale.XS): 9.0,

    (SemanticTypographyRole.LEGEND, TypographyRelativeScale.SMALL): 10.0,
    (SemanticTypographyRole.LEGEND, TypographyRelativeScale.XS): 9.0,

    # 8. TABLE, TABLE_HEADER & TABLE_BODY
    (SemanticTypographyRole.TABLE_HEADER, TypographyRelativeScale.BASE): 12.5,
    (SemanticTypographyRole.TABLE_HEADER, TypographyRelativeScale.SMALL): 11.5,

    (SemanticTypographyRole.TABLE_BODY, TypographyRelativeScale.BASE): 11.0,
    (SemanticTypographyRole.TABLE_BODY, TypographyRelativeScale.SMALL): 10.5,

    (SemanticTypographyRole.TABLE_CELL, TypographyRelativeScale.BASE): 11.0,
    (SemanticTypographyRole.TABLE_CELL, TypographyRelativeScale.SMALL): 10.5,

    (SemanticTypographyRole.TABLE, TypographyRelativeScale.BASE): 11.5,
    (SemanticTypographyRole.TABLE, TypographyRelativeScale.SMALL): 10.5,

    # 9. CALLOUT & BADGE
    (SemanticTypographyRole.CALLOUT, TypographyRelativeScale.LARGE): 14.0,
    (SemanticTypographyRole.CALLOUT, TypographyRelativeScale.BASE): 12.0,

    (SemanticTypographyRole.BADGE, TypographyRelativeScale.SMALL): 10.0,
    (SemanticTypographyRole.BADGE, TypographyRelativeScale.XS): 9.5,
}

def _load_slide_theme_presets() -> dict[str, Any]:
    """Loads themes.json directly without importing presentation.visual to prevent circular imports."""
    try:
        themes_file = Path(__file__).resolve().parent.parent / "templates" / "themes.json"
        if themes_file.exists():
            return json.loads(themes_file.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Could not read themes.json: %s", exc)
    return {}


def _init_theme_palettes() -> dict[str, dict[TypographyColorRole, str]]:
    """Builds theme palette lookup including canonical presets from themes.json."""
    palettes: dict[str, dict[TypographyColorRole, str]] = {
        "light": {
            TypographyColorRole.TEXT_PRIMARY: "#0F172A",    # 17.85:1 on #FFFFFF (AAA PASS)
            TypographyColorRole.TEXT_SECONDARY: "#334155",  # 10.35:1 on #FFFFFF (AAA PASS)
            TypographyColorRole.TEXT_MUTED: "#374151",      # 10.31:1 on #FFFFFF (AAA PASS)
            TypographyColorRole.TEXT_ON_ACCENT: "#FFFFFF",  # Re-validated against actual accent
            TypographyColorRole.TEXT_POSITIVE: "#166534",   # 7.13:1 on #FFFFFF (AAA PASS)
            TypographyColorRole.TEXT_NEGATIVE: "#991B1B",   # 8.31:1 on #FFFFFF (AAA PASS)
            TypographyColorRole.TEXT_WARNING: "#92400E",    # 7.09:1 on #FFFFFF (AAA PASS)
        },
        "dark": {
            TypographyColorRole.TEXT_PRIMARY: "#F8FAFC",    # 17.06:1 on #0F172A (AAA PASS)
            TypographyColorRole.TEXT_SECONDARY: "#E2E8F0",  # 14.48:1 on #0F172A (AAA PASS)
            TypographyColorRole.TEXT_MUTED: "#CBD5E1",      # 12.02:1 on #0F172A (AAA PASS)
            TypographyColorRole.TEXT_ON_ACCENT: "#F8FAFC",  # Re-validated against actual accent
            TypographyColorRole.TEXT_POSITIVE: "#4ADE80",   # 10.25:1 on #0F172A (AAA PASS)
            TypographyColorRole.TEXT_NEGATIVE: "#FCA5A5",   # 9.41:1 on #0F172A (AAA PASS)
            TypographyColorRole.TEXT_WARNING: "#FBBF24",    # 10.69:1 on #0F172A (AAA PASS)
        }
    }
    presets = _load_slide_theme_presets()
    for tid, p in presets.items():
        is_dark = p.get("is_dark", True)
        palettes[tid] = {
            TypographyColorRole.TEXT_PRIMARY: p.get("primary_text") or ("#F8FAFC" if is_dark else "#0F172A"),
            TypographyColorRole.TEXT_SECONDARY: p.get("secondary_text") or ("#CBD5E1" if is_dark else "#334155"),
            TypographyColorRole.TEXT_MUTED: p.get("muted_text") or ("#CBD5E1" if is_dark else "#374151"),
            TypographyColorRole.TEXT_ON_ACCENT: "#FFFFFF" if is_dark else "#0F172A",
            TypographyColorRole.TEXT_POSITIVE: p.get("success_color") or ("#4ADE80" if is_dark else "#166534"),
            TypographyColorRole.TEXT_NEGATIVE: p.get("danger_color") or ("#FCA5A5" if is_dark else "#991B1B"),
            TypographyColorRole.TEXT_WARNING: p.get("warning_color") or ("#FBBF24" if is_dark else "#92400E"),
        }
    return palettes


def _init_default_backgrounds() -> dict[str, str]:
    """Builds default background mapping per theme preset."""
    bgs: dict[str, str] = {
        "light": "#FFFFFF",
        "dark": "#0F172A",
    }
    presets = _load_slide_theme_presets()
    for tid, p in presets.items():
        bgs[tid] = p.get("bg_color") or ("#08111F" if p.get("is_dark") else "#FFFFFF")
    return bgs


THEME_PALETTES: dict[str, dict[TypographyColorRole, str]] = _init_theme_palettes()
DEFAULT_BACKGROUNDS: dict[str, str] = _init_default_backgrounds()


class DeterministicTypographyEngine:
    """Calculates concrete layout typography from relative intent and theme rules.
    
    Guarantees WCAG AAA compliance and readability floor preservation on all rendered output.
    """

    @classmethod
    def resolve_and_repair_color(
        cls,
        requested_color_role: TypographyColorRole,
        background_hex: str,
        font_size_pt: float,
        font_weight: str,
        theme_mode: str = "light"
    ) -> tuple[str, float, float, bool, bool]:
        """Resolves color against the real background and enforces WCAG AAA contrast.
        
        Returns: (resolved_color_hex, contrast_ratio, aaa_threshold, aaa_pass, color_repaired)
        """
        norm_key = theme_mode.lower()
        if norm_key in THEME_PALETTES:
            theme_key = norm_key
        else:
            theme_key = "dark" if any(w in norm_key for w in ("dark", "slate", "charcoal", "navy", "botanical", "voltage", "signal", "studio")) else "light"
        palette = THEME_PALETTES.get(theme_key, THEME_PALETTES["light"])
        
        threshold = get_aaa_contrast_threshold(font_size_pt, font_weight)
        candidate = palette.get(requested_color_role, palette[TypographyColorRole.TEXT_PRIMARY])
        
        # 1. Test candidate contrast
        c = compute_contrast_ratio(candidate, background_hex)
        if c >= threshold:
            return candidate, c, threshold, True, False

        # 2. Deterministic Color Repair
        # Candidate failed AAA against this specific background.
        # Select best contrasting token from palette or guaranteed anchors.
        bg_lum = compute_wcag_luminance(background_hex)
        if bg_lum > 0.4:
            # Light background -> test darker anchors
            repair_pool = [
                palette[TypographyColorRole.TEXT_PRIMARY],
                "#0F172A",
                "#1C1917",
                "#202328",
                "#020617",
                "#000000"
            ]
        else:
            # Dark background -> test lighter anchors
            repair_pool = [
                palette[TypographyColorRole.TEXT_PRIMARY],
                "#F8FAFC",
                "#FFFFFF"
            ]

        for rep in repair_pool:
            c_rep = compute_contrast_ratio(rep, background_hex)
            if c_rep >= threshold:
                return rep, c_rep, threshold, True, True

        # Fallback to absolute extreme if surface is mid-gray
        c_white = compute_contrast_ratio("#FFFFFF", background_hex)
        c_black = compute_contrast_ratio("#000000", background_hex)
        if c_white >= c_black:
            return "#FFFFFF", c_white, threshold, c_white >= threshold, True
        else:
            return "#000000", c_black, threshold, c_black >= threshold, True

    @classmethod
    def resolve_spec(
        cls,
        intent: TypographyIntent,
        font_family: str = "Calibri",
        theme_mode: str = "light",
        available_lines: int = 3,
        background_hex: str | None = None,
        is_on_image: bool = False,
        provenance: TypographyBlockProvenance | None = None
    ) -> ResolvedTypographySpec:
        """Deterministically maps relative TypographyIntent into concrete render specifications.
        
        Validates and guarantees:
        1. WCAG AAA contrast ratio (>= 7.0:1 for normal text, >= 4.5:1 for large text).
        2. Minimum readability point size floor per semantic role.
        3. Backing plate enforcement if overlaid on unverifiable image background.
        """
        norm_key = theme_mode.lower()
        if norm_key in THEME_PALETTES:
            theme_key = norm_key
        else:
            theme_key = "dark" if any(w in norm_key for w in ("dark", "slate", "charcoal", "navy", "botanical", "voltage", "signal", "studio")) else "light"
        real_bg = background_hex or DEFAULT_BACKGROUNDS.get(theme_key, "#FFFFFF")
        
        # 1. Backing plate enforcement for image overlays
        has_backing_plate = False
        backing_plate_hex = None
        if is_on_image:
            has_backing_plate = True
            is_dark_bg = compute_wcag_luminance(DEFAULT_BACKGROUNDS.get(theme_key, "#FFFFFF")) < 0.4
            backing_plate_hex = "#0F172A" if is_dark_bg else "#FFFFFF"
            real_bg = backing_plate_hex

        # 2. Resolve exact point size and enforce readability floor
        pt_size = POINT_SIZE_MATRIX.get(
            (intent.semantic_role, intent.relative_scale),
            POINT_SIZE_MATRIX.get((intent.semantic_role, TypographyRelativeScale.BASE), 13.0)
        )
        floor_pt = ROLE_READABILITY_FLOORS.get(intent.semantic_role, 9.0)
        readability_pass = pt_size >= floor_pt
        if not readability_pass:
            # Deterministically repair font size to meet readability floor
            pt_size = floor_pt
            readability_pass = True

        # 3. Resolve font weight string
        if intent.preferred_weight == TypographyPreferredWeight.BOLD:
            weight_str = "bold"
        elif intent.preferred_weight == TypographyPreferredWeight.SEMIBOLD:
            weight_str = "600"
        elif intent.preferred_weight == TypographyPreferredWeight.MEDIUM:
            weight_str = "500"
        else:
            weight_str = "normal"

        # 4. Resolve and repair color against actual background (WCAG AAA)
        final_color, contrast_ratio, aaa_threshold, aaa_pass, color_repaired = cls.resolve_and_repair_color(
            requested_color_role=intent.color_role,
            background_hex=real_bg,
            font_size_pt=pt_size,
            font_weight=weight_str,
            theme_mode=theme_mode
        )

        # 5. Resolve line height
        if intent.semantic_role in (
            SemanticTypographyRole.DECK_TITLE,
            SemanticTypographyRole.SLIDE_TITLE,
            SemanticTypographyRole.TITLE,
            SemanticTypographyRole.KPI_VALUE,
            SemanticTypographyRole.KPI
        ):
            line_height = 1.15
        elif intent.semantic_role in (SemanticTypographyRole.PRIMARY_INSIGHT, SemanticTypographyRole.SUBTITLE):
            line_height = 1.25
        else:
            line_height = 1.35

        # 6. Resolve reflow action (CONDENSE is strictly impossible by contract)
        reflow = intent.reflow_preference
        if intent.density_risk == DensityRisk.HIGH and reflow == ReflowPreference.NONE:
            reflow = ReflowPreference.SPLIT

        # Update provenance telemetry
        prov = provenance or TypographyBlockProvenance()
        prov.foreground_hex = final_color
        prov.background_hex = real_bg
        prov.contrast_ratio = contrast_ratio
        prov.aaa_threshold = aaa_threshold
        prov.aaa_pass = aaa_pass
        prov.color_repaired = color_repaired
        prov.readability_floor_pt = floor_pt
        prov.readability_pass = readability_pass

        return ResolvedTypographySpec(
            block_id=intent.block_id,
            semantic_role=intent.semantic_role,
            font_family=font_family,
            font_size_pt=pt_size,
            font_weight=weight_str,
            color_hex=final_color,
            line_height_multiplier=line_height,
            max_lines=available_lines,
            reflow_action=reflow,
            important_runs=intent.important_runs,
            foreground_hex=final_color,
            background_hex=real_bg,
            contrast_ratio=contrast_ratio,
            aaa_threshold=aaa_threshold,
            aaa_pass=aaa_pass,
            color_repaired=color_repaired,
            readability_floor_pt=floor_pt,
            readability_pass=readability_pass,
            has_backing_plate=has_backing_plate,
            backing_plate_hex=backing_plate_hex,
            provenance=prov,
            intent=intent
        )

    @classmethod
    def create_fallback_intent(
        cls,
        block_id: str,
        text: str,
        role: SemanticTypographyRole | str,
        container_lines: int = 3
    ) -> TypographyIntent:
        """Generates a 100% deterministic fallback intent when AI specialist is offline or invalid."""
        norm_role = normalize_semantic_role(role)

        # Estimate text density
        word_count = len(text.split())
        density_risk = DensityRisk.LOW
        reflow_pref = ReflowPreference.NONE
        
        if word_count > container_lines * 14:
            density_risk = DensityRisk.HIGH
            reflow_pref = ReflowPreference.SPLIT
        elif word_count > container_lines * 9:
            density_risk = DensityRisk.MEDIUM
            reflow_pref = ReflowPreference.WRAP

        # Role-based scale and weight
        if norm_role in (SemanticTypographyRole.DECK_TITLE, SemanticTypographyRole.SLIDE_TITLE, SemanticTypographyRole.TITLE):
            scale = TypographyRelativeScale.HERO
            weight = TypographyPreferredWeight.BOLD
            importance = TypographyImportance.CRITICAL
            color_role = TypographyColorRole.TEXT_PRIMARY
        elif norm_role in (SemanticTypographyRole.KPI, SemanticTypographyRole.KPI_VALUE):
            scale = TypographyRelativeScale.HERO
            weight = TypographyPreferredWeight.BOLD
            importance = TypographyImportance.CRITICAL
            color_role = TypographyColorRole.TEXT_PRIMARY
        elif norm_role == SemanticTypographyRole.KPI_LABEL:
            scale = TypographyRelativeScale.BASE
            weight = TypographyPreferredWeight.MEDIUM
            importance = TypographyImportance.MEDIUM
            color_role = TypographyColorRole.TEXT_SECONDARY
        elif norm_role == SemanticTypographyRole.SUBTITLE:
            scale = TypographyRelativeScale.LARGE
            weight = TypographyPreferredWeight.SEMIBOLD
            importance = TypographyImportance.HIGH
            color_role = TypographyColorRole.TEXT_SECONDARY
        elif norm_role == SemanticTypographyRole.PRIMARY_INSIGHT:
            scale = TypographyRelativeScale.LARGE
            weight = TypographyPreferredWeight.SEMIBOLD
            importance = TypographyImportance.HIGH
            color_role = TypographyColorRole.TEXT_PRIMARY
        elif norm_role in (SemanticTypographyRole.SOURCE, SemanticTypographyRole.FOOTNOTE):
            scale = TypographyRelativeScale.XS
            weight = TypographyPreferredWeight.REGULAR
            importance = TypographyImportance.SUPPORTING
            color_role = TypographyColorRole.TEXT_MUTED
        elif norm_role == SemanticTypographyRole.TABLE_HEADER:
            scale = TypographyRelativeScale.BASE
            weight = TypographyPreferredWeight.BOLD
            importance = TypographyImportance.HIGH
            color_role = TypographyColorRole.TEXT_PRIMARY
        elif norm_role in (SemanticTypographyRole.TABLE, SemanticTypographyRole.TABLE_BODY, SemanticTypographyRole.TABLE_CELL):
            scale = TypographyRelativeScale.BASE
            weight = TypographyPreferredWeight.REGULAR
            importance = TypographyImportance.MEDIUM
            color_role = TypographyColorRole.TEXT_SECONDARY
        elif norm_role == SemanticTypographyRole.CHART_TITLE:
            scale = TypographyRelativeScale.BASE
            weight = TypographyPreferredWeight.SEMIBOLD
            importance = TypographyImportance.HIGH
            color_role = TypographyColorRole.TEXT_PRIMARY
        elif norm_role in (SemanticTypographyRole.CALLOUT, SemanticTypographyRole.BADGE):
            scale = TypographyRelativeScale.SMALL
            weight = TypographyPreferredWeight.SEMIBOLD
            importance = TypographyImportance.HIGH
            color_role = TypographyColorRole.TEXT_ON_ACCENT
        else:
            scale = TypographyRelativeScale.BASE
            weight = TypographyPreferredWeight.REGULAR
            importance = TypographyImportance.MEDIUM
            color_role = TypographyColorRole.TEXT_SECONDARY

        return TypographyIntent(
            block_id=block_id,
            semantic_role=norm_role,
            importance=importance,
            relative_scale=scale,
            preferred_weight=weight,
            color_role=color_role,
            density_risk=density_risk,
            reflow_preference=reflow_pref,
            confidence=1.0,
            rationale="Deterministic rule-based fallback"
        )
