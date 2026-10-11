"""GroundingEvaluator: Evaluates 100% factual attribution to EVID and SCEN provenance (Phase D)."""
from __future__ import annotations

import logging
import re
from typing import Any
from ..contracts import (
    ClaimAttribution,
    ClaimType,
    CausalLanguageEvaluation,
    GroundingEvaluation,
)

logger = logging.getLogger(__name__)

EVID_PATTERN = re.compile(r'\[(EVID-[^\]]+)\]')
SCEN_PATTERN = re.compile(r'\[(SCEN-[^\]]+)\]')
METRIC_NUM_PATTERN = re.compile(r'\b\d+(\.\d+)?%?\b')
CAUSAL_VERBS_PATTERN = re.compile(r'\b(caused|resulted from|drove the decline of|leads to|triggered)\b', re.IGNORECASE)


class GroundingEvaluator:
    """Evaluates sentence-level claim attribution and grounding coverage."""

    @classmethod
    def evaluate(
        cls,
        final_answer: str,
        state_evidence_ids: list[str] | None = None,
        state_scenario_ids: list[str] | None = None,
    ) -> tuple[GroundingEvaluation, list[ClaimAttribution], CausalLanguageEvaluation]:
        if not final_answer:
            return (
                GroundingEvaluation(
                    factual_claim_count=0,
                    evid_grounded_claims=0,
                    scen_grounded_claims=0,
                    ungrounded_claims=0,
                    conflicting_claims=0,
                    grounding_rate=1.0,
                    is_fully_grounded=True,
                ),
                [],
                CausalLanguageEvaluation(),
            )

        # Split into analytical statements/paragraphs
        sentences = [s.strip() for s in re.split(r'\n+|\.\s+', final_answer) if s.strip()]

        attributions: list[ClaimAttribution] = []
        evid_grounded = 0
        scen_grounded = 0
        ungrounded = 0
        conflicting = 0

        causal_attempted = 0
        causal_allowed = 0
        causal_rewritten = 0
        causal_blocked = 0

        for sent in sentences:
            # Check if this sentence makes an empirical/analytical claim (contains metrics, ranks, comparisons)
            has_metric = bool(METRIC_NUM_PATTERN.search(sent))
            has_domain_term = any(k in sent.lower() for k in ["attendance", "leave", "department", "ratio", "rate", "percent", "ranked", "observed", "simulated", "finding"])
            is_factual = has_metric or has_domain_term

            evid_matches = EVID_PATTERN.findall(sent)
            scen_matches = SCEN_PATTERN.findall(sent)

            # Check causal language
            has_causal_verb = bool(CAUSAL_VERBS_PATTERN.search(sent))
            if has_causal_verb:
                causal_attempted += 1
                if scen_matches:
                    causal_allowed += 1  # Verified counterfactual scenario
                else:
                    causal_blocked += 1

            if "associated with" in sent.lower():
                causal_rewritten += 1

            if not is_factual:
                continue

            # Determine ClaimType
            if scen_matches:
                ctype = ClaimType.SCENARIO
                scen_grounded += 1
                v_status = "VERIFIED"
            elif evid_matches:
                ctype = ClaimType.OBSERVED
                evid_grounded += 1
                v_status = "VERIFIED"
            else:
                ctype = ClaimType.INFERRED
                ungrounded += 1
                v_status = "UNVERIFIED"

            # Check conflicting contamination (EVID and SCEN in same claim)
            if evid_matches and scen_matches:
                conflicting += 1

            attributions.append(ClaimAttribution(
                text=sent,
                claim_type=ctype,
                evidence_ids=evid_matches,
                scenario_ids=scen_matches,
                verification_status=v_status,
            ))

        total_claims = evid_grounded + scen_grounded + ungrounded
        grounding_rate = round((evid_grounded + scen_grounded) / total_claims, 3) if total_claims > 0 else 1.0
        is_fully_grounded = (ungrounded == 0) and (conflicting == 0)

        grounding_eval = GroundingEvaluation(
            factual_claim_count=total_claims,
            evid_grounded_claims=evid_grounded,
            scen_grounded_claims=scen_grounded,
            ungrounded_claims=ungrounded,
            conflicting_claims=conflicting,
            grounding_rate=grounding_rate,
            is_fully_grounded=is_fully_grounded,
        )

        causal_overclaim_rate = round(causal_blocked / max(1, causal_attempted), 3) if causal_attempted > 0 else 0.0
        causal_eval = CausalLanguageEvaluation(
            causal_claims_attempted=causal_attempted,
            causal_claims_allowed=causal_allowed,
            causal_claims_rewritten=causal_rewritten,
            causal_claims_blocked=causal_blocked,
            causal_overclaim_rate=causal_overclaim_rate,
        )

        return grounding_eval, attributions, causal_eval
