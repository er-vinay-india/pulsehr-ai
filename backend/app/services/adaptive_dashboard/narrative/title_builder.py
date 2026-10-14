"""Title Builder for Executive Topics and Dashboards (Phase G5.3).

Transforms measures, analytical intent, and domain concepts into executive-grade presentation titles.
Guarantees:
- Zero underscore leaks.
- Zero machine taxonomy leakage (e.g., "Semantic Family", "Visual Morphology").
- Entity grain awareness (e.g., PERSON -> Employee / Individual, DEPARTMENT -> Department).
- Domain purity (retail never emits workforce tokens; environmental never emits retail tokens).
"""
from __future__ import annotations

import re
from typing import Any

from ..formatting.presentation_labels import clean_metric_name, safe_title
from .contracts import NarrativeInput
from .integrity import (
    NarrativeEntitlementIntegrity,
    NarrativeGrainIntegrity,
    NarrativeSemanticAlignmentIntegrity,
    PROHIBITED_MACHINE_TAXONOMY,
)


class TitleBuilder:
    """Deterministic title constructor for topics, cards, and executive findings."""

    GRAIN_PREFIXES = {
        "person": "Employee",
        "employee": "Employee",
        "staff": "Staff",
        "individual": "Individual",
        "department": "Department",
        "division": "Division",
        "store": "Store",
        "location": "Location",
    }

    INTENT_TEMPLATES = {
        "RANKING": "{grain_prefix} {metric_label} Ranking",
        "TREND": "{metric_label} Trend",
        "SEGMENTATION": "{metric_label} Distribution",
        "COMPOSITION": "{metric_label} Breakdown",
        "RELATIONSHIP": "{metric_label} Analysis",
        "ANOMALY": "{metric_label} Variance & Outliers",
    }

    @classmethod
    def clean_raw_title(cls, text: str) -> str:
        """Cleans raw text of underscores, machine taxonomy, and improper casing."""
        if not text:
            return "Executive Overview"
        cleaned = safe_title(text)
        # Strip any machine taxonomy phrases
        for jargon in PROHIBITED_MACHINE_TAXONOMY:
            pattern = re.compile(re.escape(jargon), re.IGNORECASE)
            cleaned = pattern.sub("", cleaned).strip()
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned or "Executive Overview"

    @classmethod
    def build_topic_title(cls, input_data: NarrativeInput) -> str:
        """Constructs an executive title from NarrativeInput."""
        metric = input_data.metric or input_data.subject or "Overview"
        metric_clean = clean_metric_name(metric)

        # Remove machine taxonomy
        for jargon in PROHIBITED_MACHINE_TAXONOMY:
            pattern = re.compile(re.escape(jargon), re.IGNORECASE)
            metric_clean = pattern.sub("", metric_clean).strip()
        metric_clean = re.sub(r"\s+", " ", metric_clean).strip() or "Performance"

        grain = (input_data.entity_grain or "").strip().lower()
        grain_prefix = cls.GRAIN_PREFIXES.get(grain, "")

        intent = (input_data.analytical_intent or "RANKING").upper()

        if intent == "RANKING":
            if grain_prefix:
                title = f"{grain_prefix} {metric_clean} Ranking"
            else:
                title = f"{metric_clean} Ranking"
        elif intent == "TREND":
            title = f"{metric_clean} Trend"
        elif intent == "COMPOSITION":
            title = f"{metric_clean} Breakdown"
        elif intent == "SEGMENTATION":
            title = f"{metric_clean} Distribution"
        elif intent == "RELATIONSHIP":
            title = f"{metric_clean} Comparison"
        elif intent == "ANOMALY":
            title = f"{metric_clean} Outliers & Variance"
        else:
            title = f"{metric_clean} Overview"

        title = safe_title(title)

        # Enforce domain purity
        NarrativeSemanticAlignmentIntegrity.audit_domain_purity(title, input_data.domain)

        # Enforce grain integrity
        NarrativeGrainIntegrity.audit_grain_wording(title, "", grain)

        return title

    @classmethod
    def build_comparison_title(cls, x_metric: str, y_metric: str, domain: str = "general") -> str:
        """Constructs a clean comparison title (e.g., 'Weekly Sales vs Fuel Price')."""
        x_clean = clean_metric_name(x_metric)
        y_clean = clean_metric_name(y_metric)
        title = safe_title(f"{x_clean} vs {y_clean}")
        NarrativeSemanticAlignmentIntegrity.audit_domain_purity(title, domain)
        return title
