"""
HighView Semantic Data Refinery — Phase SDR-4
Governed Controlled Enrichment Engine

Orchestrates candidate generation, hard governance gates, multi-factor utility evaluation,
deterministic validation, materialization decisions, lineage tracking, and invalidation.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from app.services.sdr.contracts.enrichment import (
    EnrichmentCandidate,
    EnrichmentDecisionRecord,
    EnrichmentDecisionType,
    EnrichmentMaterialization,
    EnrichmentStatus,
    ValidatedEnrichment,
    compute_validated_enrichment_fingerprint,
)
from app.services.sdr.contracts.grain import SDRGrainProfile
from app.services.sdr.contracts.policies import EnrichmentPolicy, SDRPolicySuite
from app.services.sdr.contracts.profiles import SemanticColumnProfile
from app.services.sdr.enrichment.hard_gates import HardGovernanceGateEvaluator
from app.services.sdr.enrichment.mock_providers import (
    CodeLabelProvider,
    DatePartProvider,
)
from app.services.sdr.enrichment.provider import (
    EnrichmentProvider,
    EnrichmentProviderRegistry,
)
from app.services.sdr.enrichment.utility_evaluator import InformationGainEvaluator


class SDREnrichmentResult:
    """
    Result container for SDR-4 Controlled Enrichment Engine.
    Supports attribute access, dict indexing, and tuple unpacking.
    """

    def __init__(
        self,
        candidates: list[EnrichmentCandidate],
        validated_enrichments: list[ValidatedEnrichment],
        decisions: list[EnrichmentDecisionRecord],
        manifest: dict[str, Any],
    ):
        self.candidates = candidates
        self.validated_enrichments = validated_enrichments
        self.decisions = decisions
        self.manifest = manifest

    def __iter__(self):
        return iter((self.candidates, self.validated_enrichments, self.decisions))

    def __getitem__(self, item: str) -> Any:
        if item == "candidates":
            return self.candidates
        elif item in ("validated_enrichments", "enrichments"):
            return self.validated_enrichments
        elif item == "decisions":
            return self.decisions
        elif item == "manifest":
            return self.manifest
        raise KeyError(item)

    def get(self, item: str, default: Any = None) -> Any:
        try:
            return self[item]
        except KeyError:
            return default

    def __contains__(self, item: str) -> bool:
        return item in ("candidates", "validated_enrichments", "enrichments", "decisions", "manifest")


class SDREnrichmentEngine:
    """
    Governed Controlled Enrichment Engine.

    CORE PRINCIPLE:
    DERIVABLE != VALUABLE != AUTHORIZED
    Every enrichment must pass hard governance gates and information gain evaluation
    before becoming an accepted validated enrichment.
    """

    def __init__(
        self,
        registry: EnrichmentProviderRegistry | None = None,
        policy: EnrichmentPolicy | None = None,
    ):
        self.registry = registry or EnrichmentProviderRegistry()
        self.policy = policy or EnrichmentPolicy()
        self.hard_gates = HardGovernanceGateEvaluator(self.registry, self.policy)
        self.utility_evaluator = InformationGainEvaluator(self.policy)

        # Register default deterministic built-in providers if registry is empty
        if not self.registry.list_providers():
            self.registry.register_provider(DatePartProvider())
            self.registry.register_provider(CodeLabelProvider())

    def analyze_enrichments(
        self,
        dataset_id: str,
        sheet_id: str,
        profiles: Sequence[SemanticColumnProfile],
        grain_profile: SDRGrainProfile | None = None,
        column_data: Mapping[str, Sequence[Any]] | None = None,
        policy_suite: SDRPolicySuite | None = None,
        materialize_all: bool = False,
    ) -> SDREnrichmentResult:
        """
        Executes candidate generation, hard gate checks, utility evaluation, and validation.
        """
        policy_fp = policy_suite.compute_policy_fingerprint() if policy_suite else ""
        prof_map = {p.column_id: p for p in profiles}

        all_candidates: list[EnrichmentCandidate] = []
        validated_enrichments: list[ValidatedEnrichment] = []
        decision_records: list[EnrichmentDecisionRecord] = []

        enrichment_counts_per_col: dict[str, int] = {p.column_id: 0 for p in profiles}
        total_enrichments = 0

        # 1. Candidate Opportunity Discovery
        for profile in profiles:
            matching_providers = self.registry.find_providers_for_profile(profile)
            sample_vals = None
            if column_data:
                sample_vals = column_data.get(profile.column_id, column_data.get(profile.source_name))

            for provider in matching_providers:
                try:
                    cands = provider.generate_candidates(
                        dataset_id=dataset_id,
                        sheet_id=sheet_id,
                        profile=profile,
                        sample_values=sample_vals,
                        policy_fingerprint=policy_fp,
                    )
                    all_candidates.extend(cands)
                except Exception as exc:
                    # Provider failure must degrade gracefully: does not disrupt other providers or source
                    continue

        # 2. Evaluation & Validation
        for cand in all_candidates:
            source_prof = prof_map.get(cand.source_column_ids[0]) if cand.source_column_ids else None
            curr_count = enrichment_counts_per_col.get(cand.source_column_ids[0], 0) if cand.source_column_ids else 0

            # Step A: Hard Governance Gates
            passed_gates, failures, gate_status = self.hard_gates.evaluate_gates(cand, source_prof)

            # Step B: Information Gain Decision
            decision = self.utility_evaluator.evaluate_decision(
                candidate=cand,
                source_profile=source_prof,
                grain_profile=grain_profile,
                hard_gate_passed=passed_gates,
                hard_gate_failures=failures,
                existing_column_enrichment_count=curr_count,
                policy_fingerprint=policy_fp,
            )
            decision_records.append(decision)

            # Step C: Validation & Materialization
            if decision.decision == EnrichmentDecisionType.ACCEPT and total_enrichments < self.policy.max_total_enrichments_per_dataset:
                enrich_id = f"ENRICH-{cand.proposed_enrichment_type.split('_')[0]}-{len(validated_enrichments) + 1:03d}"
                provider = self.registry.get_provider(cand.provider_id)

                # Determine materialization policy
                # Default is virtual projection; materialized when requested or justified
                is_materialized = materialize_all
                mat_type = (
                    EnrichmentMaterialization.MATERIALIZED_ENRICHMENT
                    if is_materialized
                    else EnrichmentMaterialization.VIRTUAL_ENRICHMENT
                )

                # Resolve values / projection
                proj_expr = None
                output_ref = None
                if provider:
                    proj_expr = str(provider.resolve(cand, values=None))
                    if mat_type == EnrichmentMaterialization.MATERIALIZED_ENRICHMENT:
                        output_ref = f"silver_store://{dataset_id}/{sheet_id}/{cand.proposed_output_name}"

                val_fp = compute_validated_enrichment_fingerprint(
                    enrichment_id=enrich_id,
                    dataset_id=dataset_id,
                    sheet_id=sheet_id,
                    source_column_ids=cand.source_column_ids,
                    output_name=cand.proposed_output_name,
                    output_semantic_type=cand.proposed_output_semantic_type,
                    provider_id=cand.provider_id,
                    provider_version=cand.provider_version,
                    reference_data_version=cand.reference_data_version,
                    materialization=mat_type,
                    decision_record_id=decision.decision_id,
                    policy_fingerprint=policy_fp,
                )

                lineage_meta = {
                    "source_fingerprints": [cand.source_values_fingerprint],
                    "provider_version": cand.provider_version,
                    "reference_data_version": cand.reference_data_version,
                    "depth": cand.depth,
                    "parent_enrichment_id": cand.parent_enrichment_id,
                    "source_coordinate": cand.provenance.model_dump(),
                }

                validated = ValidatedEnrichment(
                    enrichment_id=enrich_id,
                    dataset_id=dataset_id,
                    sheet_id=sheet_id,
                    source_column_ids=cand.source_column_ids,
                    source_column_names=cand.source_column_names,
                    output_name=cand.proposed_output_name,
                    output_semantic_type=cand.proposed_output_semantic_type,
                    output_values_reference=output_ref,
                    deterministic_projection_expression=proj_expr,
                    materialization=mat_type,
                    provider_id=cand.provider_id,
                    provider_version=cand.provider_version,
                    reference_data_version=cand.reference_data_version,
                    confidence=cand.confidence,
                    authority="DERIVED_ENRICHMENT",
                    depth=cand.depth,
                    parent_enrichment_id=cand.parent_enrichment_id,
                    lineage=lineage_meta,
                    decision_record_id=decision.decision_id,
                    is_valid=True,
                    artifact_fingerprint=val_fp,
                )
                validated_enrichments.append(validated)
                total_enrichments += 1
                if cand.source_column_ids:
                    enrichment_counts_per_col[cand.source_column_ids[0]] = curr_count + 1

        manifest = {
            "dataset_id": dataset_id,
            "sheet_id": sheet_id,
            "candidates_count": len(all_candidates),
            "validated_enrichments_count": len(validated_enrichments),
            "decisions_count": len(decision_records),
            "accepted_count": sum(1 for d in decision_records if d.decision == EnrichmentDecisionType.ACCEPT),
            "rejected_count": sum(1 for d in decision_records if d.decision == EnrichmentDecisionType.REJECT),
            "blocked_count": sum(1 for d in decision_records if not d.hard_gate_passed and any("sensitive" in f.lower() for f in d.hard_gate_failures)),
            "ambiguous_count": sum(1 for d in decision_records if d.decision == EnrichmentDecisionType.AMBIGUOUS),
            "deferred_count": sum(1 for d in decision_records if d.decision == EnrichmentDecisionType.DEFER),
            "materialized_count": sum(1 for v in validated_enrichments if v.materialization == EnrichmentMaterialization.MATERIALIZED_ENRICHMENT),
            "virtual_count": sum(1 for v in validated_enrichments if v.materialization == EnrichmentMaterialization.VIRTUAL_ENRICHMENT),
        }

        return SDREnrichmentResult(
            candidates=all_candidates,
            validated_enrichments=validated_enrichments,
            decisions=decision_records,
            manifest=manifest,
        )

    def invalidate_by_source_change(
        self,
        enrichments: list[ValidatedEnrichment],
        changed_column_ids: Sequence[str],
    ) -> list[ValidatedEnrichment]:
        """
        Invalidates dependent enrichments when a source column changes values or profile.
        Preserves unrelated enrichments.
        """
        changed_set = set(changed_column_ids)
        updated: list[ValidatedEnrichment] = []
        for e in enrichments:
            if any(cid in changed_set for cid in e.source_column_ids):
                updated.append(
                    e.model_copy(
                        update={
                            "is_valid": False,
                            "invalidation_reason": "Source column fingerprint changed; dependent derivation invalidated.",
                        }
                    )
                )
            else:
                updated.append(e)
        return updated

    def invalidate_by_provider_version(
        self,
        enrichments: list[ValidatedEnrichment],
        provider_id: str,
        new_version: str,
    ) -> list[ValidatedEnrichment]:
        """
        Invalidates enrichments when provider version or reference data is upgraded.
        """
        updated: list[ValidatedEnrichment] = []
        for e in enrichments:
            if e.provider_id == provider_id and e.provider_version != new_version:
                updated.append(
                    e.model_copy(
                        update={
                            "is_valid": False,
                            "invalidation_reason": f"Provider version upgraded to {new_version}; derivation invalidated.",
                        }
                    )
                )
            else:
                updated.append(e)
        return updated
