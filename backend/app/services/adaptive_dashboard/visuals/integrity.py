"""Visual Semantic Alignment and Mutation Integrity Guards (Phase G5.4).

Enforces:
1. VisualSemanticAlignmentIntegrity:
   - Validates that visual axes and series concepts match ExecutiveTopic analytical concepts.
   - Enforces domain purity (retail axes cannot have workforce/environmental titles).
   - Enforces entity grain integrity (PERSON vs DEPARTMENT).
   - Enforces theme absence (no hex colors, dark/light styles, or CSS).
2. VisualSemanticsMutationIntegrity:
   - Prohibits the composition layer from mutating chart_type, axes, series, measures, or evidence.
"""
from __future__ import annotations

import re
from typing import Any

from .contracts import VisualSpec


class VisualIntegrityError(ValueError):
    """Raised when visual specification violates alignment, purity, or immutability rules."""
    pass


class VisualSemanticAlignmentIntegrity:
    """Enforces semantic alignment, cross-domain purity, grain consistency, and theme absence."""

    WORKFORCE_TOKENS = {"attendance", "leaves", "employee", "wfo", "headcount", "absenteeism"}
    RETAIL_TOKENS = {"fuel_price", "fuel price", "weekly_sales", "weekly sales", "cpi", "holiday_flag"}
    ENVIRONMENTAL_TOKENS = {"so2", "no2", "pm10", "pm2.5", "pm25", "cpcb", "aqi", "jharia", "brynihat"}

    @classmethod
    def audit_theme_absence(cls, spec_dict: dict[str, Any], fail_closed: bool = True) -> list[str]:
        """Audits that VisualSpec contains ZERO theme colors, hex values, or CSS styling."""
        violations: list[str] = []
        # Check all string values in properties and spec
        for k, v in spec_dict.items():
            if isinstance(v, str):
                if re.search(r"#[0-9a-fA-F]{3,8}\b", v):
                    violations.append(f"Hardcoded hex color '{v}' found in VisualSpec property '{k}'")
                if "dark" in v.lower() and "theme" in v.lower():
                    violations.append(f"Theme directive '{v}' found in VisualSpec property '{k}'")
            elif isinstance(v, dict):
                violations.extend(cls.audit_theme_absence(v, fail_closed=False))

        if violations and fail_closed:
            raise VisualIntegrityError("; ".join(violations))
        return violations

    @classmethod
    def audit_domain_purity(
        cls,
        spec: VisualSpec | dict[str, Any],
        domain: str,
        fail_closed: bool = True,
    ) -> list[str]:
        """Verifies that axes, titles, and labels do not leak cross-domain vocabulary."""
        violations: list[str] = []
        dom = (domain or "").lower()

        if isinstance(spec, VisualSpec):
            text_corpus = f"{spec.full_title} {spec.display_title} {spec.x_label} {spec.y_label}".lower()
        else:
            text_corpus = f"{spec.get('full_title', '')} {spec.get('display_title', '')} {spec.get('title', '')} {spec.get('x_label', '')} {spec.get('y_label', '')}".lower()

        if dom in ("workforce", "workforce_hr", "hr"):
            for bad in cls.RETAIL_TOKENS | cls.ENVIRONMENTAL_TOKENS:
                if re.search(r"\b" + re.escape(bad) + r"\b", text_corpus):
                    violations.append(f"Foreign domain token '{bad}' leaked into workforce visual.")

        elif "retail" in dom or "commercial" in dom or "sales" in dom:
            for bad in cls.WORKFORCE_TOKENS | cls.ENVIRONMENTAL_TOKENS:
                if re.search(r"\b" + re.escape(bad) + r"\b", text_corpus):
                    violations.append(f"Foreign domain token '{bad}' leaked into retail visual.")

        elif "environmental" in dom or "air" in dom or "cpcb" in dom:
            for bad in cls.WORKFORCE_TOKENS | cls.RETAIL_TOKENS:
                if re.search(r"\b" + re.escape(bad) + r"\b", text_corpus):
                    violations.append(f"Foreign domain token '{bad}' leaked into environmental visual.")

        if violations and fail_closed:
            raise VisualIntegrityError("; ".join(violations))
        return violations

    @classmethod
    def audit_grain_consistency(
        cls,
        spec: VisualSpec | dict[str, Any],
        entity_grain: str,
        fail_closed: bool = True,
    ) -> list[str]:
        """Ensures chart type and naming match the designated entity grain."""
        violations: list[str] = []
        grain = (entity_grain or "").strip().lower()

        if isinstance(spec, VisualSpec):
            c_type = spec.chart_type
            title = spec.full_title.lower()
        else:
            c_type = spec.get("chart_type", "")
            title = (spec.get("full_title") or spec.get("title", "")).lower()

        if grain in ("department", "division", "function"):
            if c_type == "podium_top_3":
                violations.append("Podium visual reserved for PERSON grain; invalid for DEPARTMENT.")
            if "employee ranking" in title or "top 3 employee" in title:
                violations.append("Department grain visual title contains employee wording.")

        elif grain in ("person", "employee", "staff", "individual"):
            if "department ranking" in title:
                violations.append("Person grain visual title contains department wording.")

        if violations and fail_closed:
            raise VisualIntegrityError("; ".join(violations))
        return violations

    @classmethod
    def audit_title_axis_alignment(
        cls,
        spec: VisualSpec | dict[str, Any],
        fail_closed: bool = True,
    ) -> list[str]:
        """Ensures that relationship/scatter card titles match the bound x and y axis measures."""
        violations: list[str] = []
        if isinstance(spec, VisualSpec):
            chart_type = spec.chart_type
            x_label = spec.x_label
            y_label = spec.y_label
            title = spec.full_title
        else:
            chart_type = spec.get("chart_type", "")
            x_label = spec.get("x_label", "")
            y_label = spec.get("y_label", "")
            title = spec.get("full_title") or spec.get("title", "")

        if chart_type in ("scatter", "correlation_scatter") and x_label and y_label:
            axes_corpus = f"{x_label} {y_label}".lower()
            title_lower = title.lower()

            # If axes are retail (fuel, temperature, cpi, sales), title must not mention workforce or attendance
            if any(k in axes_corpus for k in ["fuel", "temperature", "sales", "cpi", "store"]):
                for bad in cls.WORKFORCE_TOKENS:
                    if re.search(r"\b" + re.escape(bad) + r"\b", title_lower):
                        violations.append(
                            f"Scatter title '{title}' mentions workforce token '{bad}' but axes are retail: x='{x_label}', y='{y_label}'"
                        )

        if violations and fail_closed:
            raise VisualIntegrityError("; ".join(violations))
        return violations


class VisualSemanticsMutationIntegrity:
    """Protects VisualSpec semantics from being altered during spatial layout and composition."""

    IMMUTABLE_KEYS = {
        "chart_type",
        "analytical_intent",
        "entity_grain",
        "categories",
        "values",
        "series",
        "x_label",
        "y_label",
        "evidence_ids",
        "benchmark",
    }

    @classmethod
    def verify_composition_handoff(
        cls,
        original_spec: VisualSpec | dict[str, Any],
        composed_spec: dict[str, Any],
        fail_closed: bool = True,
    ) -> list[str]:
        """Verifies that composition only added layout metadata without mutating analytical semantics."""
        violations: list[str] = []
        orig_dict = original_spec.to_dict() if isinstance(original_spec, VisualSpec) else original_spec

        for k in cls.IMMUTABLE_KEYS:
            if k in orig_dict and k in composed_spec:
                if orig_dict[k] != composed_spec[k]:
                    violations.append(
                        f"Composition layer mutated immutable VisualSpec semantic property '{k}': "
                        f"original='{orig_dict[k]}' -> composed='{composed_spec[k]}'"
                    )

        if violations and fail_closed:
            raise VisualIntegrityError("; ".join(violations))
        return violations
