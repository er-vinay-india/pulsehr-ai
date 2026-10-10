"""Claim Entitlement Governor (Phase 11.4).

Enforces ClaimEntitlementIntegrity:
1. Validates whether the evidence type ENTITLES the claim (e.g. correlation cannot entitle causation).
2. Enforces mandated linguistic verb conformance (e.g. "was" for observed, "would have" for counterfactual).
3. Automatically BLOCKS invalid claims and suggests mathematically sound reformulations.
"""
from __future__ import annotations

import re
from typing import Any
from .contracts import (
    CLAIM_ENTITLEMENT_RULES,
    MANDATED_VERB_PATTERNS,
    PROHIBITED_CAUSAL_VERBS,
    ClaimEntitlementVerdict,
    ClaimType,
    EvidenceTypeEntitlement,
)


class ClaimEntitlementGovernor:
    """Audits generated statements against supporting evidence types and linguistic rules."""

    @classmethod
    def detect_claim_type(cls, sentence: str) -> ClaimType:
        """Classifies the epistemic type of an analytical sentence."""
        s_lower = sentence.lower()

        # 1. Recommendation
        if any(w in s_lower for w in ["recommend", "advises", "suggests", "should consider", "proposes"]):
            return ClaimType.RECOMMENDATION

        # 2. Counterfactual Replay / Negative Prediction Disclaimers
        if re.search(r"\b(?:does\s+not|doesn't|not)\s+(?:predict|forecast)\b", s_lower):
            return ClaimType.COUNTERFACTUAL

        if any(w in s_lower for w in [
            "would have", "would meet", "under a 2-day", "under a 4-day",
            "under alternative policy", "counterfactual", "re-evaluates",
            "alternative rules", "scenario"
        ]):
            return ClaimType.COUNTERFACTUAL

        # 3. Forecast
        if any(w in s_lower for w in ["is projected to", "forecast", "will increase to", "will decline to", "predicted"]):
            return ClaimType.FORECAST

        # 4. Association / Correlation
        if any(w in s_lower for w in ["associated with", "correlated with", "tracks with", "co-occurred"]):
            return ClaimType.ASSOCIATED

        # 5. Derived Math
        if any(w in s_lower for w in ["equals", "calculated to", "rate is", "gap is", "measures", "yields"]):
            return ClaimType.DERIVED

        # 6. Default: Observed Fact
        return ClaimType.OBSERVED

    @classmethod
    def audit_claim(
        cls,
        sentence: str,
        available_evidence_types: list[str],
    ) -> ClaimEntitlementVerdict:
        """Validates claim entitlement and linguistic integrity."""
        claim_type = cls.detect_claim_type(sentence)
        s_lower = sentence.lower()

        # Normalize evidence types to EvidenceTypeEntitlement strings
        evid_set = set(available_evidence_types)

        # 1. Check for Unjustified Causal Claims (e.g. "X caused Y" with only correlation evidence)
        has_causal_word = any(re.search(rf"\b{re.escape(w)}\b", s_lower) for w in PROHIBITED_CAUSAL_VERBS)
        if has_causal_word:
            # Causality is strictly prohibited unless validated by controlled experiment / counterfactual engine
            if EvidenceTypeEntitlement.CORRELATION.value in evid_set and EvidenceTypeEntitlement.PREDICTIVE_MODEL.value not in evid_set:
                reformulated = re.sub(
                    r"\b(caused|resulted from|drove the decline of|leads to)\b",
                    "was associated with",
                    sentence,
                    flags=re.IGNORECASE,
                )
                return ClaimEntitlementVerdict(
                    claim_text=sentence,
                    detected_claim_type=ClaimType.ASSOCIATED,
                    supporting_evidence_types=available_evidence_types,
                    is_entitled=False,
                    linguistic_conformance=False,
                    rejection_reason="Causal claim rejected: correlation evidence does not entitle causal attribution. Must state as statistical association.",
                    suggested_reformulation=reformulated,
                )

        # 2. Check for Counterfactual Replay conflated with Forecast
        if claim_type == ClaimType.FORECAST:
            if EvidenceTypeEntitlement.SCENARIO_REPLAY.value in evid_set and EvidenceTypeEntitlement.PREDICTIVE_MODEL.value not in evid_set:
                reformulated = re.sub(
                    r"\b(is projected to|will)\b",
                    "would have",
                    sentence,
                    flags=re.IGNORECASE,
                )
                return ClaimEntitlementVerdict(
                    claim_text=sentence,
                    detected_claim_type=ClaimType.FORECAST,
                    supporting_evidence_types=available_evidence_types,
                    is_entitled=False,
                    linguistic_conformance=False,
                    rejection_reason="Predictive forecast claim rejected: historical scenario replay does not entitle future forecasting without longitudinal backtesting.",
                    suggested_reformulation=reformulated,
                )

        # 3. Check Required Evidence Entitlement Rules
        required_evid = CLAIM_ENTITLEMENT_RULES.get(claim_type, [])
        is_supported = any(r.value in evid_set for r in required_evid)

        if not is_supported and len(required_evid) > 0:
            req_names = ", ".join(r.value for r in required_evid)
            return ClaimEntitlementVerdict(
                claim_text=sentence,
                detected_claim_type=claim_type,
                supporting_evidence_types=available_evidence_types,
                is_entitled=False,
                linguistic_conformance=True,
                rejection_reason=f"Claim type '{claim_type.value}' is not entitled by available evidence. Requires at least one of: [{req_names}].",
                suggested_reformulation=None,
            )

        # 4. Check Linguistic Verb Conformance
        valid_verbs = MANDATED_VERB_PATTERNS.get(claim_type, [])
        conforms_verb = any(v in s_lower for v in valid_verbs) if valid_verbs else True

        return ClaimEntitlementVerdict(
            claim_text=sentence,
            detected_claim_type=claim_type,
            supporting_evidence_types=available_evidence_types,
            is_entitled=True,
            linguistic_conformance=conforms_verb,
            rejection_reason=None,
            suggested_reformulation=None,
        )

    @classmethod
    def audit_response_text(
        cls,
        text: str,
        available_evidence_types: list[str],
    ) -> tuple[bool, list[ClaimEntitlementVerdict], str]:
        """Audits all sentences in a response. Returns (all_passed, verdicts, sanitized_or_blocked_text)."""
        # Split into sentences
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        verdicts = []
        all_passed = True
        repaired_sentences = []

        for s in sentences:
            verdict = cls.audit_claim(s, available_evidence_types)
            verdicts.append(verdict)
            if not verdict.is_entitled:
                all_passed = False
                if verdict.suggested_reformulation:
                    repaired_sentences.append(verdict.suggested_reformulation)
                else:
                    # Exclude unentitled sentence
                    pass
            else:
                repaired_sentences.append(s)

        final_text = " ".join(repaired_sentences) if repaired_sentences else text
        return all_passed, verdicts, final_text
