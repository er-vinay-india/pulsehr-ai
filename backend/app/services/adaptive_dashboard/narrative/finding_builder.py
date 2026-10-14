"""Finding and Narrative Builder (Phase G5.3).

Constructs evidence-bound findings, takeaways, and business questions strictly
from verified BoundFacts.

Guarantees:
- Zero number invention or recomputation.
- Zero causal overreach (prohibits "caused by", "will recover", etc.).
- Zero machine taxonomy in business text.
- Full evidence traceability (retains EVID, CTX, SCEN identifiers).
- Domain purity and grain consistency.
"""
from __future__ import annotations

import re
from typing import Any

from ..formatting.presentation_labels import clean_metric_name
from .contracts import NarrativeInput, NarrativeResult
from .integrity import (
    NarrativeEntitlementIntegrity,
    NarrativeGrainIntegrity,
    NarrativeSemanticAlignmentIntegrity,
)
from .title_builder import TitleBuilder


class FindingBuilder:
    """Deterministic, evidence-grounded finding constructor."""

    @classmethod
    def build_narrative(cls, input_data: NarrativeInput) -> NarrativeResult:
        """Synthesizes verified BoundFacts into a complete, entitled NarrativeResult."""
        # 1. Build executive title
        title = TitleBuilder.build_topic_title(input_data)

        # 2. Extract facts and evidence references
        facts = input_data.bound_facts
        evidence_ids: list[str] = list(input_data.evidence_ids)
        for bf in facts:
            eid = getattr(bf, "evidence_id", None) or (
                bf.evidence.evidence_id
                if hasattr(bf, "evidence") and hasattr(bf.evidence, "evidence_id")
                else None
            )
            if eid and eid not in evidence_ids:
                evidence_ids.append(eid)

        grain = (input_data.entity_grain or "aggregate").strip().lower()
        metric_label = clean_metric_name(input_data.metric or input_data.subject or "Metric")

        # 3. Construct finding from primary bound facts
        if not facts:
            finding = f"Summary data indicates {metric_label.lower()} baseline established."
            takeaway = f"Baseline {metric_label.lower()} monitored across {grain} cohorts."
            business_q = f"How does {metric_label.lower()} track against planned expectations?"
            summary_frag = f"{title} reflects baseline observations."
        else:
            primary_bf = facts[0]
            pf = primary_bf.fact

            # Build finding statement
            if pf.value is not None:
                if pf.unit == "$":
                    val_str = f"${pf.value:,.1f}"
                    unit_suffix = ""
                else:
                    val_str = f"{pf.value:,.1f}"
                    unit_suffix = f" {pf.unit}" if pf.unit and pf.unit != "%" else (pf.unit or "")
            else:
                val_str = "N/A"
                unit_suffix = ""
            entity_label = getattr(pf, "entity_name", None) or getattr(pf, "dimension", None) or getattr(pf, "subject", None) or grain.capitalize()
            comp_entity = getattr(pf, "comparison_entity", None)
            comp_val = getattr(pf, "comparison_value", None)
            diff_pct = getattr(pf, "difference_pct", None)

            if comp_entity and diff_pct is not None:
                diff_str = f"{abs(diff_pct):,.1f}%"
                direction = "higher than" if diff_pct >= 0 else "lower than"
                finding = (
                    f"{entity_label} recorded {val_str}{unit_suffix}, which is {diff_str} "
                    f"{direction} {comp_entity}."
                )
                takeaway = (
                    f"A {diff_str} variance was observed between {entity_label} and {comp_entity}."
                )
                business_q = (
                    f"What operating factors distinguish {entity_label} from {comp_entity}?"
                )
            elif comp_val is not None and diff_pct is not None:
                diff_str = f"{abs(diff_pct):,.1f}%"
                direction = "above" if diff_pct >= 0 else "below"
                finding = (
                    f"{entity_label} recorded {val_str}{unit_suffix}, standing {diff_str} "
                    f"{direction} benchmark ({comp_val:,.1f}{unit_suffix})."
                )
                takeaway = f"{metric_label} variance of {diff_str} observed against benchmark."
                business_q = f"How can {metric_label.lower()} variance against benchmark be managed?"
            else:
                finding = f"{entity_label} recorded {metric_label.lower()} of {val_str}{unit_suffix}."
                takeaway = f"{entity_label} maintains {metric_label.lower()} at {val_str}{unit_suffix}."
                business_q = f"How does {entity_label} {metric_label.lower()} align with operational goals?"

            summary_frag = f"{entity_label}: {val_str}{unit_suffix}."

        # 4. Audit all generated text against entitlement, purity, and grain
        full_text = f"{title}. {finding} {takeaway}"
        NarrativeEntitlementIntegrity.audit_narrative_text(full_text, input_data, fail_closed=True)
        NarrativeSemanticAlignmentIntegrity.audit_domain_purity(full_text, input_data.domain, fail_closed=True)
        NarrativeGrainIntegrity.audit_grain_wording(title, finding, grain, fail_closed=True)

        return NarrativeResult(
            topic_id=input_data.topic_id,
            title=title,
            finding=finding,
            takeaway=takeaway,
            business_question=business_q,
            executive_summary_fragment=summary_frag,
            recommended_action=f"Review {metric_label.lower()} drivers across {grain} cohorts.",
            claim_refs=[f"claim_{eid}" for eid in evidence_ids],
            evidence_ids=evidence_ids,
            context_ids=list(input_data.context_refs),
            scenario_ids=list(input_data.scenario_refs),
            entity_grain=input_data.entity_grain,
            domain=input_data.domain,
        )
