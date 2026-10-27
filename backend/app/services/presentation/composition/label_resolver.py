"""Slide Composition Intelligence — Governed Display Label Resolver.

Resolves human-readable display labels from LabelSimplificationIntents while preserving
empirical data truth, source identifiers, and analytical lineage.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from .composition_models import LabelSimplificationIntent

logger = logging.getLogger(__name__)


class GovernedLabelResolver:
    """Governed resolver converting technical labels to display labels while preserving source truth."""

    @classmethod
    def resolve_label(
        cls,
        source_label: str,
        label_intents: Optional[list[LabelSimplificationIntent]] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> tuple[str, bool]:
        """Resolves a display label from label intents.
        
        Returns:
            tuple[display_label, was_simplified]
            - display_label: Safe, human-friendly display label (or source_label if untransformed)
            - was_simplified: True if a verified simplification was applied
        """
        if not source_label or not source_label.strip():
            return source_label, False

        clean_source = source_label.strip()

        if not label_intents:
            return clean_source, False

        # Find matching intent
        matched_intent: Optional[LabelSimplificationIntent] = None
        for intent in label_intents:
            if intent.source_label.strip() == clean_source:
                matched_intent = intent
                break
            # Case-insensitive / normalized match
            if intent.source_label.strip().lower() == clean_source.lower():
                matched_intent = intent
                break

        if not matched_intent or not matched_intent.suggested_display_text:
            return clean_source, False

        candidate = matched_intent.suggested_display_text.strip()
        if not candidate:
            return clean_source, False

        # Safety Invariants:
        # 1. Do not invent, drop, or alter digits (e.g. "FY2024" must not become "FY2025", and text without digits cannot gain numbers)
        source_digits = re.findall(r"\d+", clean_source)
        candidate_digits = re.findall(r"\d+", candidate)
        if source_digits != candidate_digits:
            logger.debug(
                "GovernedLabelResolver rejected simplification for '%s' -> '%s' (digit mismatch)",
                clean_source,
                candidate,
            )
            return clean_source, False

        # 2. Candidate must not be pure punctuation
        if not re.search(r"[a-zA-Z]", candidate):
            return clean_source, False

        return candidate, True
