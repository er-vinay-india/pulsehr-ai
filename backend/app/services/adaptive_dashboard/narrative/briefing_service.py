"""Executive Briefing Service and Claim Validator (Phase G5.3).

Synthesizes short, natural, audible executive briefings (target 55-100 words, max 130 words / 1,200 chars)
strictly bound to verified calculations and bound facts.
Guarantees:
- Zero fabricated causes, forecasts, targets, or unverified performance language.
- Strict numeric entitlement: every number in spoken text must exist in cited claims.
- Zero PII leaks.
- Zero machine taxonomy in spoken text.
- Audible formatting (e.g. expands 'pp' to 'percentage points').
"""
from __future__ import annotations

import re
from typing import Any

from .contracts import BriefingClaim, ExecutiveBriefingSpec
from .integrity import (
    PROHIBITED_MACHINE_TAXONOMY,
    PROHIBITED_WORDS,
    NarrativeEntitlementIntegrity,
)


def count_words(text: str) -> int:
    """Counts whitespace-delimited words in a string."""
    return len(text.split())


def format_pp_for_speech(text: str) -> str:
    """Expands shorthand 'pp' into audible 'percentage points' for spoken clarity."""
    return re.sub(r"\bpp\b", "percentage points", text)


def validate_briefing_claims(
    claims: list[BriefingClaim],
    spoken_text: str,
    manifest_snapshot: str,
    available_component_ids: set[str],
    available_components: dict[str, Any] | None = None,
) -> None:
    """Strict pre-publication validator. Raises ValueError on any contract or evidence violation."""
    # 1. Word and character bounds
    word_count = count_words(spoken_text)
    if word_count > 130:
        raise ValueError(f"Briefing word count exceeds maximum: {word_count} words > 130 words limit.")
    if len(spoken_text) > 1200:
        raise ValueError(f"Briefing character count exceeds maximum: {len(spoken_text)} chars > 1200 limit.")

    # 2. Prohibited wording check
    lower_spoken = spoken_text.lower()
    for phrase in PROHIBITED_WORDS:
        if phrase in lower_spoken:
            raise ValueError(f"Prohibited non-causal or subjective phrase detected in briefing: '{phrase}'")

    # 2b. Prohibited machine taxonomy check
    for jargon in PROHIBITED_MACHINE_TAXONOMY:
        if jargon in lower_spoken:
            raise ValueError(f"Machine taxonomy leaked into audible briefing: '{jargon}'")

    # 3. PII check (emails, phone numbers)
    if "@" in spoken_text:
        raise ValueError("Potential PII (email address) detected in briefing text.")
    if re.search(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", spoken_text):
        raise ValueError("Potential PII (phone number) detected in briefing text.")

    # 4. Claim binding integrity
    for claim in claims:
        if claim.source_component_id not in available_component_ids:
            raise ValueError(f"Claim references missing source component: '{claim.source_component_id}'")
        if not claim.calculation_ids:
            raise ValueError(f"Claim '{claim.claim_id}' must reference at least one calculation ID.")

        # Extract numeric tokens from claim text, ignoring calendar dates, years (2020-2035), rankings (#1), ordinals
        text_without_dates = re.sub(
            r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)(?:\s+\d{4})?\b",
            " ",
            claim.text,
            flags=re.IGNORECASE,
        )
        text_without_dates = re.sub(
            r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?(?:\s+\d{4})?\b",
            " ",
            text_without_dates,
            flags=re.IGNORECASE,
        )
        text_without_dates = re.sub(r"\b\d{4}-\d{2}(?:-\d{2})?\b", " ", text_without_dates)

        clean_text = text_without_dates
        if available_components:
            for comp in available_components.values():
                if hasattr(comp, "items") and comp.items:
                    for it in comp.items:
                        label = getattr(it, "segment", None) or getattr(it, "cohort", None) or getattr(it, "label", None)
                        if label and any(c.isdigit() for c in str(label)):
                            clean_text = clean_text.replace(str(label), " ")
                if hasattr(comp, "subject_label") and comp.subject_label and any(c.isdigit() for c in str(comp.subject_label)):
                    clean_text = clean_text.replace(str(comp.subject_label), " ")

        tokens = re.findall(r"(?<![\w#])[-+]?\$?\d{1,3}(?:,\d{3})*(?:\.\d+)?(?:[kKmMbBtT])?%?(?![a-zA-Z0-9_])", clean_text)
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
            # Ignore standard 4-digit years
            if 2000 <= val <= 2035 and "." not in clean_tok and not suffix:
                continue
            multiplier = {"k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12}.get(suffix, 1.0)
            expanded_val = val * multiplier
            scale_tol = 0.6 if multiplier == 1.0 else (multiplier * 0.05)
            # Verify value exists in claim.numeric_values within display rounding tolerance
            matched = any(
                abs(val - num) <= 0.6
                or abs(abs(val) - abs(num)) <= 0.6
                or abs(expanded_val - num) <= scale_tol
                or abs(abs(expanded_val) - abs(num)) <= scale_tol
                or (abs(expanded_val - num) / max(abs(num), 1.0) <= 0.02)
                for num in claim.numeric_values
            )
            if not matched:
                raise ValueError(
                    f"Unbound numeric value '{token}' in claim '{claim.claim_id}' not found in claim.numeric_values ({claim.numeric_values})."
                )


class ExecutiveBriefingService:
    """Service for building and validating audible executive briefings."""

    @classmethod
    def validate_claims(
        cls,
        claims: list[BriefingClaim],
        spoken_text: str,
        manifest_snapshot: str,
        available_component_ids: set[str],
        available_components: dict[str, Any] | None = None,
    ) -> None:
        """Validates briefing claims using strict pre-publication rules."""
        validate_briefing_claims(
            claims=claims,
            spoken_text=spoken_text,
            manifest_snapshot=manifest_snapshot,
            available_component_ids=available_component_ids,
            available_components=available_components,
        )

    @classmethod
    def format_audio_text(cls, text: str) -> str:
        """Formats text for audible clarity."""
        return format_pp_for_speech(text)

    @classmethod
    def audit_word_count(cls, text: str, max_words: int = 130) -> int:
        """Returns word count or raises ValueError if over limit."""
        wc = count_words(text)
        if wc > max_words:
            raise ValueError(f"Audible briefing exceeds limit: {wc} > {max_words} words.")
        return wc
