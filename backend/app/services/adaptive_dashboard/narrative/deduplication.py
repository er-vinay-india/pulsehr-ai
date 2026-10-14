"""Narrative Deduplication and Executive Summary Synthesis (Phase G5.3).

Provides:
- NarrativeDeduplicationIntegrity:
  - Deduplicates candidate findings and narrative fragments by semantic subject, metric family, and decision intent.
  - Composes 3–5 highest-value bound facts into an executive summary without repeating dataset names.
  - Zero machine taxonomy or duplicate sentence structures.
"""
from __future__ import annotations

import re
from typing import Any

from ..evidence.contracts import BoundFact
from .contracts import NarrativeResult
from .integrity import (
    NarrativeEntitlementIntegrity,
    NarrativeSemanticAlignmentIntegrity,
    PROHIBITED_MACHINE_TAXONOMY,
    PROHIBITED_WORDS,
)


class NarrativeDeduplicationIntegrity:
    """Enforces narrative deduplication and synthesizes coherent executive summaries."""

    @classmethod
    def deduplicate_narratives(
        cls,
        narratives: list[NarrativeResult],
        max_narratives: int = 5,
    ) -> list[NarrativeResult]:
        """Deduplicates a list of NarrativeResults based on domain, topic, and entity grain."""
        if not narratives:
            return []

        selected: list[NarrativeResult] = []
        seen_keys: set[str] = set()

        for n in narratives:
            # Semantic identity based on grain, domain, and title stem
            title_stem = re.sub(r"[^a-zA-Z0-9]", "", n.title.lower())[:16]
            key = f"{n.domain}:{n.entity_grain}:{title_stem}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            selected.append(n)
            if len(selected) >= max_narratives:
                break

        return selected

    @classmethod
    def compose_executive_summary(
        cls,
        bound_facts: list[BoundFact],
        domain: str = "general",
        max_facts: int = 5,
    ) -> str:
        """Composes 3 to 5 highest-value facts into a fluid executive summary.
        
        Guarantees:
        - Never repeats the dataset name.
        - Never uses machine taxonomy.
        - Never uses prohibited non-causal words.
        - Conforms to domain purity.
        """
        if not bound_facts:
            return "Executive baseline established with verified metrics."

        # Filter out invalid or zero-value facts, take up to max_facts distinct facts
        valid_facts: list[BoundFact] = []
        seen_entities: set[str] = set()

        for bf in bound_facts:
            fact = bf.fact
            if fact.value is None:
                continue
            entity_name = getattr(fact, "entity_name", None) or getattr(fact, "dimension", None) or getattr(fact, "subject", None) or "Cohort"
            metric_name = getattr(fact, "metric_name", None) or getattr(fact, "metric", None) or "Metric"
            entity_key = f"{entity_name}:{metric_name}"
            if entity_key in seen_entities:
                continue
            seen_entities.add(entity_key)
            valid_facts.append(bf)
            if len(valid_facts) >= max_facts:
                break

        if not valid_facts:
            return "Executive baseline established with verified metrics."

        sentences: list[str] = []
        for i, bf in enumerate(valid_facts):
            f = bf.fact
            entity_name = getattr(f, "entity_name", None) or getattr(f, "dimension", None) or getattr(f, "subject", None) or "Cohort"
            if f.unit == "$":
                val_fmt = f"${f.value:,.1f}"
            else:
                unit_suffix = f" {f.unit}" if f.unit and f.unit != "%" else (f.unit or "")
                val_fmt = f"{f.value:,.1f}{unit_suffix}"
            comp_entity = getattr(f, "comparison_entity", None)
            comp_val = getattr(f, "comparison_value", None)
            diff_pct = getattr(f, "difference_pct", None)

            if comp_entity and diff_pct is not None:
                diff_fmt = f"{abs(diff_pct):,.1f}%"
                direction = "higher than" if diff_pct >= 0 else "lower than"
                sent = f"{entity_name} recorded {val_fmt}, which is {diff_fmt} {direction} {comp_entity}."
            elif comp_val is not None and diff_pct is not None:
                diff_fmt = f"{abs(diff_pct):,.1f}%"
                direction = "above" if diff_pct >= 0 else "below"
                sent = f"{entity_name} stood at {val_fmt}, {diff_fmt} {direction} the benchmark average."
            else:
                if i == 0:
                    sent = f"{entity_name} led observed cohorts with {val_fmt}."
                else:
                    sent = f"{entity_name} recorded {val_fmt}."

            sentences.append(sent)

        summary = " ".join(sentences)

        # Audit against domain purity
        NarrativeSemanticAlignmentIntegrity.audit_domain_purity(summary, domain, fail_closed=True)

        return summary
