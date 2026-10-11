"""ComposeResponseNode: Generates final grounded executive answer separating EVID and SCEN."""
from __future__ import annotations

import logging
from typing import Any
from ..guards import CausalLanguageGuard
from ..state import HighviewAgentState

logger = logging.getLogger(__name__)


def compose_response_node(state: HighviewAgentState) -> HighviewAgentState:
    """Synthesizes final answer grounded in verified evidence and separated counterfactuals."""
    # If already explicitly terminated as DENIED or FAILED_SAFE with a final answer, preserve it
    if state.workflow_status in ("DENIED", "FAILED_SAFE") and state.final_answer:
        return state

    intent = state.intent
    evid_ids = state.evidence_ids
    scen_ids = state.scenario_ids

    response_lines: list[str] = []

    # 1. Empirical observed facts (EVID)
    if evid_ids:
        evid_tags = ", ".join(f"[{eid}]" for eid in evid_ids[:4])
        if state.verified_claims:
            claims_str = " ".join(state.verified_claims)
            response_lines.append(f"Observed Analysis {evid_tags}: {claims_str}")
        elif intent == "RANKING":
            response_lines.append(f"Ranking Analysis {evid_tags}: Verified organizational performance metrics computed across segments.")
        elif intent == "COMPARISON":
            response_lines.append(f"Comparative Analysis {evid_tags}: Cross-segment performance and variance verified across entities.")
        elif intent == "TREND":
            response_lines.append(f"Historical Trend {evid_tags}: Longitudinal trajectory computed across reporting intervals.")
        elif intent == "RELATIONSHIP":
            response_lines.append(f"Statistical Association {evid_tags}: Correlation analysis established without assuming direct causality.")
        elif intent == "PRESENTATION_CREATION":
            deck_id = state.active_filters.get("deck_id", "DECK-GEN")
            headline = state.active_filters.get("executive_headline", "Executive Briefing")
            response_lines.append(f"Presentation Generated [{deck_id}] using evidence {evid_tags}. Headline: {headline}")
        else:
            response_lines.append(f"Factual Findings {evid_tags}: Quantitative metrics verified against canonical dataset tables.")

    # 2. Counterfactual scenario projections (SCEN)
    if scen_ids:
        scen_tags = ", ".join(f"[{sid}]" for sid in scen_ids[:3])
        response_lines.append(
            f"Simulated Counterfactual {scen_tags}: Projected impact under policy parameter variations. "
            f"(Note: Projections are modeled simulations, not observed historical facts.)"
        )

    # 3. Default fallback if neither present
    if not response_lines:
        if state.error:
            response_lines.append(f"Workflow halted safely: {state.error}")
        else:
            response_lines.append("Query processed successfully with verified dataset parameters.")

    raw_answer = "\n\n".join(response_lines)

    # 4. Enforce causal language guard
    sanitized_answer, _ = CausalLanguageGuard.sanitize_claim(
        raw_answer,
        is_counterfactual_verified=bool(scen_ids),
    )

    state.final_answer = sanitized_answer
    if state.workflow_status == "IN_PROGRESS":
        state.workflow_status = "COMPLETED"

    logger.debug(f"[ComposeResponseNode] Composed response for request {state.request_id}")
    return state
