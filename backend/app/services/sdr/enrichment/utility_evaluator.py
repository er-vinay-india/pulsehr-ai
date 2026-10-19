"""
HighView Semantic Data Refinery — Phase SDR-4
Information Gain & Analytical Utility Decision Engine

Computes multi-factor utility scoring and issues governed EnrichmentDecisionRecord.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.services.sdr.contracts.enrichment import (
    EnrichmentCandidate,
    EnrichmentDecisionRecord,
    EnrichmentDecisionType,
    compute_enrichment_decision_fingerprint,
)
from app.services.sdr.contracts.grain import SDRGrainProfile
from app.services.sdr.contracts.policies import EnrichmentPolicy
from app.services.sdr.contracts.profiles import SemanticColumnProfile


class InformationGainEvaluator:
    """
    Evaluates practical information gain and domain relevance for enrichment candidates.
    Ensures that derivable != valuable != authorized.
    """

    def __init__(self, policy: EnrichmentPolicy | None = None):
        self.policy = policy or EnrichmentPolicy()

    def evaluate_decision(
        self,
        candidate: EnrichmentCandidate,
        source_profile: SemanticColumnProfile | None = None,
        grain_profile: SDRGrainProfile | None = None,
        hard_gate_passed: bool = True,
        hard_gate_failures: list[str] | None = None,
        existing_column_enrichment_count: int = 0,
        policy_fingerprint: str = "",
    ) -> EnrichmentDecisionRecord:
        """
        Calculates information gain and issues an authoritative decision record.
        """
        gate_failures = hard_gate_failures or []

        # If hard gate failed, decision is immediately non-ACCEPT
        if not hard_gate_passed:
            is_ambig = any("ambiguous" in f.lower() for f in gate_failures)
            dec_type = EnrichmentDecisionType.AMBIGUOUS if is_ambig else EnrichmentDecisionType.REJECT
            fp = compute_enrichment_decision_fingerprint(
                candidate_id=candidate.candidate_id,
                decision=dec_type,
                hard_gate_passed=False,
                hard_gate_failures=gate_failures,
                analytical_utility=0.0,
                net_information_gain=0.0,
                policy_fingerprint=policy_fingerprint,
            )
            return EnrichmentDecisionRecord(
                decision_id=f"dec_{candidate.candidate_id}",
                candidate_id=candidate.candidate_id,
                dataset_id=candidate.dataset_id,
                sheet_id=candidate.sheet_id,
                decision=dec_type,
                hard_gate_passed=False,
                hard_gate_failures=gate_failures,
                analytical_utility=0.0,
                domain_relevance=0.0,
                confidence=candidate.confidence,
                ambiguity_score=1.0 if is_ambig else 0.0,
                privacy_risk_score=1.0 if any("sensitive" in f.lower() for f in gate_failures) else 0.0,
                net_information_gain=0.0,
                rationale="; ".join(gate_failures),
                artifact_fingerprint=fp,
            )

        # 1. Analytical Utility Evaluation
        base_util = float(candidate.information_gain_record.get("base_utility", 0.50))
        # Temporal aggregations (year, month, quarter) and standard code expansions have high utility
        if "DATE_PART" in candidate.proposed_enrichment_type:
            analytical_utility = 0.90
        elif "CODE_LABEL" in candidate.proposed_enrichment_type:
            analytical_utility = 0.85
        elif "TRIVIAL" in candidate.proposed_enrichment_type or "LENGTH" in candidate.proposed_enrichment_type:
            analytical_utility = 0.15
        elif "PLANET" in candidate.proposed_output_name.upper():
            analytical_utility = 0.05
        else:
            analytical_utility = base_util

        # 2. Domain Relevance Evaluation
        domain_relevance = 0.80
        if grain_profile:
            # Check alignment with primary entity / grain
            if grain_profile.primary_entity.value in candidate.proposed_output_name.upper():
                domain_relevance = 0.95
            elif "DATE" in candidate.proposed_enrichment_type and grain_profile.temporal_grain.value != "NONE":
                domain_relevance = 0.95

        # 3. Budget & Count Checks
        if existing_column_enrichment_count >= self.policy.max_enrichments_per_column:
            dec_type = EnrichmentDecisionType.DEFER
            rationale = (
                f"Column enrichment budget exceeded: source column already has {existing_column_enrichment_count} "
                f"enrichments (max allowed: {self.policy.max_enrichments_per_column}). Candidate deferred."
            )
            fp = compute_enrichment_decision_fingerprint(
                candidate_id=candidate.candidate_id,
                decision=dec_type,
                hard_gate_passed=True,
                hard_gate_failures=[],
                analytical_utility=analytical_utility,
                net_information_gain=0.0,
                policy_fingerprint=policy_fingerprint,
            )
            return EnrichmentDecisionRecord(
                decision_id=f"dec_{candidate.candidate_id}",
                candidate_id=candidate.candidate_id,
                dataset_id=candidate.dataset_id,
                sheet_id=candidate.sheet_id,
                decision=dec_type,
                hard_gate_passed=True,
                analytical_utility=analytical_utility,
                domain_relevance=domain_relevance,
                confidence=candidate.confidence,
                compute_cost=0.1,
                storage_cost=0.1,
                net_information_gain=0.0,
                rationale=rationale,
                artifact_fingerprint=fp,
            )

        # 4. Net Information Gain Calculation
        net_gain = (
            analytical_utility * 0.45
            + domain_relevance * 0.25
            + candidate.confidence * 0.25
            - 0.05  # Standard compute cost penalty
        )

        # Threshold Decision
        if analytical_utility < self.policy.min_utility_score or net_gain < self.policy.min_utility_score:
            dec_type = EnrichmentDecisionType.REJECT
            rationale = (
                f"Low information gain: analytical utility ({analytical_utility:.2f}) and net score ({net_gain:.2f}) "
                f"fall below minimum threshold ({self.policy.min_utility_score:.2f}). Rejected as analytically uninformative."
            )
        elif candidate.confidence < self.policy.min_confidence:
            dec_type = EnrichmentDecisionType.DEFER
            rationale = f"Insufficient provider confidence ({candidate.confidence:.2f} < {self.policy.min_confidence:.2f})."
        else:
            dec_type = EnrichmentDecisionType.ACCEPT
            rationale = (
                f"Accepted: strong analytical utility ({analytical_utility:.2f}) and domain relevance ({domain_relevance:.2f}) "
                f"with net information gain {net_gain:.2f}."
            )

        fp = compute_enrichment_decision_fingerprint(
            candidate_id=candidate.candidate_id,
            decision=dec_type,
            hard_gate_passed=True,
            hard_gate_failures=[],
            analytical_utility=analytical_utility,
            net_information_gain=net_gain,
            policy_fingerprint=policy_fingerprint,
        )

        return EnrichmentDecisionRecord(
            decision_id=f"dec_{candidate.candidate_id}",
            candidate_id=candidate.candidate_id,
            dataset_id=candidate.dataset_id,
            sheet_id=candidate.sheet_id,
            decision=dec_type,
            hard_gate_passed=True,
            analytical_utility=analytical_utility,
            domain_relevance=domain_relevance,
            confidence=candidate.confidence,
            ambiguity_score=0.0,
            privacy_risk_score=0.0,
            provenance_quality=1.0,
            compute_cost=0.05,
            storage_cost=0.05,
            net_information_gain=net_gain,
            rationale=rationale,
            artifact_fingerprint=fp,
        )
