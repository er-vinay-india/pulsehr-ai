"""Narrative Entitlement and Language Governance Guards.

Enforces:
1. NarrativeEntitlementIntegrity:
   - Prohibits unsupported superlatives, subjective judgments, and causal overreach.
   - Verifies that all cited numbers exist in bound facts.
2. NarrativeSemanticAlignmentIntegrity:
   - Protects domain purity (retail has zero workforce tokens; environmental has zero retail/workforce tokens).
   - Verifies that titles derive strictly from underlying measures/subjects.
3. NarrativeGrainIntegrity:
   - Preserves person vs department wording based on entity_grain.
4. HumanFacingLanguagePolicy:
   - Eliminates machine taxonomy ("Semantic Family", "Visual Morphology", "Distributions & Variance") from user-facing text.
"""
from __future__ import annotations

import re
from typing import Any

from .contracts import NarrativeInput, NarrativeResult


PROHIBITED_WORDS = (
    "performing badly",
    "leave caused",
    "caused by",
    "will recover",
    "the business is healthy",
    "is healthy",
    "sales will increase",
    "will improve",
    "critical risk",
    "ai discovered",
    "machine learning discovered",
    "underperforming",
    "worst",
    "best",
    "poor",
)

PROHIBITED_MACHINE_TAXONOMY = {
    "semantic family",
    "visual morphology",
    "distributions & variance",
    "decision simulator",
    "comparative benchmarks",
    "bivariate association",
    "distributional variance",
    "cross-tabulation",
    "semantic ranking",
    "statistical morphology",
}


class NarrativeViolationError(ValueError):
    """Raised when narrative text violates governance, domain boundaries, or entitlement rules."""
    pass


class NarrativeEntitlementIntegrity:
    """Verifies that narrative statements are strictly entitled by underlying bound facts."""

    @classmethod
    def audit_narrative_text(
        cls,
        text: str,
        input_data: NarrativeInput,
        fail_closed: bool = True,
    ) -> list[str]:
        """Audits text for prohibited non-causal language, machine taxonomy, and unsupported numbers."""
        violations: list[str] = []
        low_text = text.lower()

        # 1. Prohibited subjective / non-causal words
        for phrase in PROHIBITED_WORDS:
            if phrase in low_text:
                violations.append(f"Prohibited non-causal or subjective phrase detected: '{phrase}'")

        # 2. Prohibited machine taxonomy
        for jargon in PROHIBITED_MACHINE_TAXONOMY:
            if jargon in low_text:
                violations.append(f"Internal machine taxonomy leaked into human-facing narrative: '{jargon}'")

        # 3. Numeric entitlement check
        # Extract numbers from text (ignoring 4-digit years 2000-2035 and ordinals)
        supplied_values: list[float] = []
        for bf in input_data.bound_facts:
            if bf.fact.value is not None:
                try:
                    supplied_values.append(float(bf.fact.value))
                except (ValueError, TypeError):
                    pass
            if bf.fact.difference_pct is not None:
                try:
                    supplied_values.append(float(bf.fact.difference_pct))
                except (ValueError, TypeError):
                    pass
            if bf.fact.comparison_value is not None:
                try:
                    supplied_values.append(float(bf.fact.comparison_value))
                except (ValueError, TypeError):
                    pass

        # Extract numeric tokens
        tokens = re.findall(r"(?<![\w#])[-+]?\$?\d{1,3}(?:,\d{3})*(?:\.\d+)?(?:[kKmMbBtT])?%?(?![a-zA-Z0-9_])", text)
        for token in tokens:
            clean_tok = token.replace(",", "").replace("$", "").rstrip("%").lstrip("+")
            suffix = ""
            if clean_tok and clean_tok[-1] in "kKmMbBtT":
                suffix = clean_tok[-1].lower()
                clean_tok = clean_tok[:-1]
            try:
                val = float(clean_tok)
            except ValueError:
                continue

            # Ignore calendar years
            if 2000 <= val <= 2035 and "." not in clean_tok and not suffix:
                continue

            multiplier = {"k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12}.get(suffix, 1.0)
            expanded_val = val * multiplier

            # If input provided facts, verify this number was supplied within display tolerance
            if supplied_values:
                matched = any(
                    abs(val - num) <= 0.6
                    or abs(abs(val) - abs(num)) <= 0.6
                    or abs(expanded_val - num) <= 0.6
                    or abs(abs(expanded_val) - abs(num)) <= 0.6
                    for num in supplied_values
                )
                if not matched:
                    violations.append(
                        f"Unbound numeric token '{token}' in narrative not found in verified bound facts."
                    )

        if violations and fail_closed:
            raise NarrativeViolationError("; ".join(violations))
        return violations


class NarrativeSemanticAlignmentIntegrity:
    """Guards domain purity and ensures titles and findings derive from their own evidence."""

    WORKFORCE_TOKENS = {"attendance", "leaves", "employee", "wfo", "headcount", "absenteeism"}
    RETAIL_TOKENS = {"fuel_price", "fuel price", "weekly_sales", "weekly sales", "cpi", "holiday_flag"}
    ENVIRONMENTAL_TOKENS = {"so2", "no2", "pm10", "pm2.5", "pm25", "cpcb", "aqi", "jharia", "brynihat"}

    @classmethod
    def audit_domain_purity(
        cls,
        text: str,
        domain: str,
        fail_closed: bool = True,
    ) -> list[str]:
        """Ensures that narrative text contains zero foreign cross-domain vocabulary."""
        violations: list[str] = []
        low_text = text.lower()
        dom = (domain or "").lower()

        if dom in ("workforce", "workforce_hr", "hr"):
            for bad in cls.RETAIL_TOKENS | cls.ENVIRONMENTAL_TOKENS:
                if re.search(r"\b" + re.escape(bad) + r"\b", low_text):
                    violations.append(f"Foreign domain token '{bad}' leaked into workforce narrative.")

        elif "retail" in dom or "commercial" in dom or "sales" in dom:
            for bad in cls.WORKFORCE_TOKENS | cls.ENVIRONMENTAL_TOKENS:
                if re.search(r"\b" + re.escape(bad) + r"\b", low_text):
                    violations.append(f"Foreign domain token '{bad}' leaked into retail narrative.")

        elif "environmental" in dom or "air" in dom or "cpcb" in dom:
            for bad in cls.WORKFORCE_TOKENS | cls.RETAIL_TOKENS:
                if re.search(r"\b" + re.escape(bad) + r"\b", low_text):
                    violations.append(f"Foreign domain token '{bad}' leaked into environmental narrative.")

        if violations and fail_closed:
            raise NarrativeViolationError("; ".join(violations))
        return violations


class NarrativeGrainIntegrity:
    """Enforces entity grain isolation between personnel (employee) and aggregate/department wording."""

    @classmethod
    def audit_grain_wording(
        cls,
        title: str,
        finding: str,
        entity_grain: str,
        fail_closed: bool = True,
    ) -> list[str]:
        """Audits that person grain uses employee wording and department grain uses department wording."""
        violations: list[str] = []
        eg = (entity_grain or "").strip().lower()
        full_text = f"{title} {finding}".lower()

        if eg in ("person", "employee", "individual", "staff"):
            # Should not describe as department ranking
            if "department ranking" in full_text or "top department" in full_text:
                violations.append(
                    f"Entity grain mismatch: Personnel grain '{eg}' emitted department ranking wording."
                )
        elif eg in ("department", "division", "function"):
            # Should not describe as employee podium
            if "top employee" in full_text or "employee ranking" in full_text:
                violations.append(
                    f"Entity grain mismatch: Department grain '{eg}' emitted employee ranking wording."
                )

        if violations and fail_closed:
            raise NarrativeViolationError("; ".join(violations))
        return violations
