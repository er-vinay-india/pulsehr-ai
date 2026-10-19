"""
HighView Semantic Data Refinery — Phase SDR-4
Hard Governance Gates Evaluator

Non-negotiable precondition gates.
If any hard gate fails, the candidate is immediately BLOCKED or marked AMBIGUOUS;
no weighted utility or information gain score may override a hard gate failure.
"""

from __future__ import annotations

from typing import Tuple

from app.services.sdr.contracts.enrichment import (
    EnrichmentCandidate,
    EnrichmentProviderType,
    EnrichmentStatus,
)
from app.services.sdr.contracts.policies import EnrichmentPolicy
from app.services.sdr.contracts.profiles import (
    PrivacyClassification,
    ProfilingAmbiguityState,
    SemanticColumnProfile,
    SemanticDtype,
)
from app.services.sdr.enrichment.provider import EnrichmentProviderRegistry

PROHIBITED_SENSITIVE_TERMS = {
    "health", "disease", "medical", "diagnosis", "ethnicity", "race",
    "religion", "faith", "political", "politics", "disability",
    "pregnancy", "sexual_orientation", "union_membership",
}


class HardGovernanceGateEvaluator:
    """
    Evaluates mandatory safety and integrity gates for enrichment candidates.
    """

    def __init__(self, registry: EnrichmentProviderRegistry, policy: EnrichmentPolicy | None = None):
        self.registry = registry
        self.policy = policy or EnrichmentPolicy()

    def evaluate_gates(
        self,
        candidate: EnrichmentCandidate,
        source_profile: SemanticColumnProfile | None = None,
    ) -> Tuple[bool, list[str], EnrichmentStatus]:
        """
        Runs all hard gates.
        Returns: (passed: bool, failure_reasons: list[str], status: EnrichmentStatus)
        """
        failures: list[str] = []

        # Gate 1: Strict Prohibition on Inferred Sensitive Attributes
        if (
            candidate.privacy_classification == PrivacyClassification.INFERRED_SENSITIVE_ATTRIBUTE
            or any(term in candidate.proposed_output_name.lower() for term in PROHIBITED_SENSITIVE_TERMS)
            or any(term in candidate.proposed_enrichment_type.lower() for term in PROHIBITED_SENSITIVE_TERMS)
        ):
            failures.append(
                f"Prohibited sensitive inference: '{candidate.proposed_output_name}' attempts to derive "
                f"sensitive personal attributes (health, ethnicity, religion, political beliefs, or protected characteristics). "
                f"Probabilistic derivation of sensitive data is strictly forbidden by HighView governance."
            )
            return False, failures, EnrichmentStatus.BLOCKED

        # Gate 2: Provider Availability and Legitimacy
        provider = self.registry.get_provider(candidate.provider_id)
        if provider is None:
            failures.append(f"Provider unavailable: Registered provider '{candidate.provider_id}' is not operational.")
            return False, failures, EnrichmentStatus.BLOCKED

        # Gate 3: Source Semantic Compatibility
        if candidate.source_semantic_type not in provider.metadata.supported_input_semantics:
            failures.append(
                f"Source semantic mismatch: Provider '{provider.provider_id}' requires input types "
                f"{[t.value for t in provider.metadata.supported_input_semantics]}, but source has '{candidate.source_semantic_type.value}'."
            )
            return False, failures, EnrichmentStatus.BLOCKED

        # Gate 4: Ambiguity Gate
        if (
            candidate.ambiguity_state != ProfilingAmbiguityState.CLEAR
            or candidate.validation_status == EnrichmentStatus.AMBIGUOUS
        ):
            failures.append(
                f"Ambiguous source signal: Candidate '{candidate.candidate_id}' has ambiguity state "
                f"'{candidate.ambiguity_state.value}'. Withholds resolution without explicit disambiguation."
            )
            return False, failures, EnrichmentStatus.AMBIGUOUS

        # Gate 5: Direct Identifier Governance
        if source_profile and source_profile.privacy_classification == PrivacyClassification.DIRECT_IDENTIFIER:
            # DIRECT IDENTIFIERS may participate internally in governed deterministic processing
            # (e.g. employee_id used internally to lookup an authorized deterministic internal label).
            # BLOCK only when enrichment would cause:
            # 1. Unauthorized exposure / external leakage (non-deterministic or external provider)
            # 2. Sensitive personal inference (predicted health, political, etc.)
            # 3. Unsupported propagation or unnecessary identifier surfacing

            # Check 1: Inferred sensitivity is blocked
            if (
                candidate.privacy_classification == PrivacyClassification.INFERRED_SENSITIVE_ATTRIBUTE
                or any(term in candidate.proposed_output_name.lower() for term in PROHIBITED_SENSITIVE_TERMS)
                or any(term in candidate.proposed_enrichment_type.lower() for term in PROHIBITED_SENSITIVE_TERMS)
            ):
                failures.append(
                    f"Direct identifier unauthorized exposure: Attempting sensitive personal inference from identifier '{source_profile.source_name}'."
                )
                return False, failures, EnrichmentStatus.BLOCKED

            # Check 2: Unauthorized exposure / external leakage: Direct identifiers cannot be routed to non-deterministic or external providers
            if provider.metadata.provider_type not in (
                EnrichmentProviderType.LOCAL_REFERENCE,
                EnrichmentProviderType.DETERMINISTIC_RULE,
            ):
                failures.append(
                    f"Direct identifier unauthorized exposure: Direct identifier '{source_profile.source_name}' "
                    f"cannot be propagated to non-deterministic or external provider '{provider.provider_id}'."
                )
                return False, failures, EnrichmentStatus.BLOCKED

            # Check 3: Unsupported propagation / unnecessary identifier surfacing
            if (
                candidate.proposed_output_semantic_type == SemanticDtype.IDENTIFIER_CODE
                and candidate.proposed_output_name.lower() != source_profile.source_name.lower()
            ):
                failures.append(
                    f"Direct identifier unauthorized propagation: Unnecessary identifier surfacing for '{candidate.proposed_output_name}'."
                )
                return False, failures, EnrichmentStatus.BLOCKED

        # Gate 6: Maximum Enrichment Depth Limit
        if candidate.depth > self.policy.max_enrichment_depth:
            failures.append(
                f"Enrichment depth exceeded: Candidate depth {candidate.depth} exceeds configured policy limit {self.policy.max_enrichment_depth}."
            )
            return False, failures, EnrichmentStatus.REJECTED

        # Gate 7: Supported Output Semantics
        if candidate.proposed_output_semantic_type not in provider.metadata.supported_output_semantics:
            failures.append(
                f"Unsupported output semantics: Provider '{provider.provider_id}' cannot produce "
                f"'{candidate.proposed_output_semantic_type.value}'."
            )
            return False, failures, EnrichmentStatus.BLOCKED

        return True, [], EnrichmentStatus.AUTHORIZED
