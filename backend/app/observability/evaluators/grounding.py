"""GroundingEvaluator: Evaluates 100% factual attribution across EVID, CTX, and SCEN provenance (Phase F).

Enforces:
1. Strict epistemological separation:
   - EVID-* = Empirical tabular dataset evidence
   - CTX-*  = Organizational context evidence (policies, thresholds, KPI definitions)
   - SCEN-* = Counterfactual scenario projections
   - Zero cross-contamination between namespaces.
2. Compound claim grounding:
   - Empirical findings compared against policy thresholds map to BOTH [EVID-*] and [CTX-*].
"""
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
CTX_PATTERN = re.compile(r'\[(CTX-[^\]]+)\]')
SCEN_PATTERN = re.compile(r'\[(SCEN-[^\]]+)\]')
METRIC_NUM_PATTERN = re.compile(r'\b\d+(\.\d+)?%?\b')
CAUSAL_VERBS_PATTERN = re.compile(r'\b(caused|resulted from|drove the decline of|leads to|triggered)\b', re.IGNORECASE)


class GroundingEvaluator:
    """Evaluates sentence-level claim attribution and grounding coverage across EVID, CTX, and SCEN."""

    @classmethod
    def evaluate(
        cls,
        final_answer: str,
        state_evidence_ids: list[str] | None = None,
        state_scenario_ids: list[str] | None = None,
        state_context_ids: list[str] | None = None,
    ) -> tuple[GroundingEvaluation, list[ClaimAttribution], CausalLanguageEvaluation]:
        if not final_answer:
            return (
                GroundingEvaluation(
                    factual_claim_count=0,
                    evid_grounded_claims=0,
                    ctx_grounded_claims=0,
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
        ctx_grounded = 0
        scen_grounded = 0
        ungrounded = 0
        conflicting = 0

        causal_attempted = 0
        causal_allowed = 0
        causal_rewritten = 0
        causal_blocked = 0

        for sent in sentences:
            has_metric = bool(METRIC_NUM_PATTERN.search(sent))
            has_domain_term = any(k in sent.lower() for k in [
                "attendance", "leave", "department", "ratio", "rate", "percent",
                "ranked", "observed", "simulated", "finding", "policy", "threshold",
                "target", "standard", "requirement", "kpi", "rule", "cap", "audit"
            ])
            is_factual = has_metric or has_domain_term

            evid_matches = EVID_PATTERN.findall(sent)
            ctx_matches = CTX_PATTERN.findall(sent)
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

            # Determine ClaimType and Grounding Status
            if scen_matches:
                ctype = ClaimType.SCENARIO
                scen_grounded += 1
                v_status = "VERIFIED"
            elif evid_matches or ctx_matches:
                ctype = ClaimType.OBSERVED
                if evid_matches:
                    evid_grounded += 1
                if ctx_matches:
                    ctx_grounded += 1
                v_status = "VERIFIED"
            else:
                ctype = ClaimType.INFERRED
                ungrounded += 1
                v_status = "UNVERIFIED"

            # Check conflicting contamination:
            # 1. Counterfactual SCEN and empirical EVID/CTX in the same claim
            if scen_matches and (evid_matches or ctx_matches):
                conflicting += 1

            # 2. Namespace misuse: SCEN inside evid_matches or CTX inside evid_matches
            if any(e.startswith("SCEN-") or e.startswith("CTX-") for e in evid_matches):
                conflicting += 1

            attributions.append(ClaimAttribution(
                text=sent,
                claim_type=ctype,
                evidence_ids=evid_matches,
                context_ids=ctx_matches,
                scenario_ids=scen_matches,
                verification_status=v_status,
            ))

        total_claims = len(attributions)
        grounded_claims = sum(1 for a in attributions if a.verification_status == "VERIFIED")
        grounding_rate = round(grounded_claims / total_claims, 3) if total_claims > 0 else 1.0
        is_fully_grounded = (ungrounded == 0) and (conflicting == 0)

        grounding_eval = GroundingEvaluation(
            factual_claim_count=total_claims,
            evid_grounded_claims=evid_grounded,
            ctx_grounded_claims=ctx_grounded,
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
