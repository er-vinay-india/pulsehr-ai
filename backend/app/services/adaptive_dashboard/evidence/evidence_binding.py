"""Evidence Binding Service.

Transforms verified analytical findings and facts into immutable, bound evidence nodes:
- findings_to_evidence_graph: Canonical mapping from UnifiedFindings to governed EVID-* nodes
- bind_fact: Creates a BoundFact connecting an AnalyticalFact to BoundEvidence and topic_id
- create_evidence_binding: Constructs a validated EvidenceBinding with fail-closed ownership checks
"""
from __future__ import annotations

import re
from typing import Any, Literal

from ..contracts import UnifiedFinding
from .contracts import (
    AnalyticalFact,
    BoundEvidence,
    BoundFact,
    EvidenceBinding,
    EvidenceGraph,
    EvidenceItem,
    UnresolvedTemplateTokenValidator,
)
from .integrity import EvidenceNamespaceIntegrity, EvidenceOwnershipIntegrity
from .provenance import ProvenanceBinder


class EvidenceBindingService:
    """Governed service binding calculated analytical facts to immutable evidence nodes."""

    @classmethod
    def findings_to_evidence_graph(
        cls,
        findings: list[UnifiedFinding],
        sheet_id: int,
        snapshot: str,
        source_table: str = "sheet_curated_rows",
        dataset_id: int | None = None,
    ) -> EvidenceGraph:
        """Converts a collection of UnifiedFindings into a governed EvidenceGraph with EVID-xxx IDs."""
        nodes: list[BoundEvidence] = []

        for idx, f in enumerate(findings, start=1):
            evid_id = f"EVID-{idx:03d}"

            # Classify claim type
            claim_type: Literal[
                "segment_difference",
                "trend_change",
                "concentration",
                "outlier",
                "distribution_skew",
                "capacity_gap",
                "backlog_aging",
                "retention_decay",
                "target_gap",
                "general_fact",
            ] = "general_fact"

            rec = f.recipe_id.lower()
            if "segment" in rec or "disparity" in rec:
                claim_type = "segment_difference"
            elif "change" in rec or "trend" in rec or "shift" in rec:
                claim_type = "trend_change"
            elif "reasons" in rec or "concentration" in rec:
                claim_type = "concentration"
            elif "capacity" in rec or "demand" in rec:
                claim_type = "capacity_gap"
            elif "backlog" in rec or "aging" in rec:
                claim_type = "backlog_aging"
            elif "cohort" in rec or "retention" in rec:
                claim_type = "retention_decay"
            elif "target" in rec:
                claim_type = "target_gap"
            elif "tail" in rec or "spread" in rec:
                claim_type = "distribution_skew"

            # Determine causal classification
            causal: Literal["OBSERVED", "ASSOCIATED", "INFERRED", "COUNTERFACTUAL", "HYPOTHESIS"] = "OBSERVED"
            if f.allowed_claim_level == "statistical_association":
                causal = "ASSOCIATED"
            elif f.allowed_claim_level in ("non_causal_forecast", "exploratory_pattern"):
                causal = "INFERRED"
            elif f.allowed_claim_level == "policy_exposure":
                causal = "HYPOTHESIS"

            # Parse population number
            population = 0
            pop_match = re.search(r"(\d+)\s*(?:records|employees|observations|rows|units|items)", f.population_or_exposure, re.IGNORECASE)
            if pop_match:
                try:
                    population = int(pop_match.group(1))
                except ValueError:
                    population = 0

            # Confidence heuristic
            confidence: Literal["HIGH", "MEDIUM", "LOW"] = "HIGH"
            sample_warning = False
            if population > 0 and population < 15:
                confidence = "LOW"
                sample_warning = True
            elif population >= 15 and population < 30:
                confidence = "MEDIUM"

            # Difference pct heuristic
            diff_pct: float | None = None
            if f.comparison_and_effect:
                pct_match = re.search(r"([+-]?\d+(?:\.\d+)?)\s*%", f.comparison_and_effect)
                if pct_match:
                    try:
                        diff_pct = float(pct_match.group(1))
                    except ValueError:
                        diff_pct = None

            tokens = {
                "evidence_id": evid_id,
                "subject": f.short_business_title,
                "metric": f.recipe_id.replace("recipe_", "").replace("_", " "),
                "value": f.typed_value if f.typed_value is not None else f.formatted_value,
                "formatted_value": f.formatted_value,
                "unit": f.unit,
                "comparison": f.comparison_and_effect or "benchmark",
                "difference_pct": diff_pct if diff_pct is not None else 0.0,
                "population": population or f.population_or_exposure,
            }

            nodes.append(
                BoundEvidence(
                    evidence_id=evid_id,
                    claim_type=claim_type,
                    subject=f.short_business_title,
                    metric=f.recipe_id,
                    value=f.typed_value,
                    formatted_value=f.formatted_value,
                    difference_pct=diff_pct,
                    population=population,
                    source_table=source_table,
                    calculation=f.evidence_bound_observation,
                    confidence=confidence,
                    causal_classification=causal,
                    sample_warning=sample_warning,
                    provenance=f.snapshot,
                    tokens=tokens,
                    supporting_evidence_ids=[],
                    limitations=f.limitations,
                    dataset_id=dataset_id,
                    sheet_id=sheet_id,
                    namespace="EVID",
                )
            )

        return EvidenceGraph(
            sheet_id=sheet_id,
            snapshot=snapshot,
            nodes=nodes,
        )

    @classmethod
    def bind_fact(
        cls,
        fact: AnalyticalFact,
        topic_id: str,
        evidence: BoundEvidence | None = None,
        fail_closed: bool = True,
    ) -> BoundFact:
        """Binds an AnalyticalFact to a BoundEvidence node, enforcing ownership and grain validation."""
        if evidence is None:
            # Construct synthetic BoundEvidence from fact
            evid_id = f"EVID-FACT-{fact.fact_id}"
            evidence = BoundEvidence(
                evidence_id=evid_id,
                claim_type="general_fact",
                subject=fact.subject,
                metric=fact.metric,
                value=fact.value,
                formatted_value=fact.formatted_value,
                comparison_value=fact.comparison_value,
                difference_pct=fact.difference_pct,
                population=fact.population,
                period=fact.period,
                source_table=fact.source_table,
                calculation=fact.calculation_method,
                confidence=fact.confidence,
                causal_classification="OBSERVED",
                provenance=fact.provenance_snapshot,
                tokens=fact.tokens,
                limitations=fact.limitations,
                dataset_id=fact.dataset_id,
                sheet_id=fact.sheet_id,
                topic_id=topic_id,
                grain=fact.grain,
                namespace="EVID",
            )
        else:
            # Enforce dataset ownership & grain isolation
            EvidenceOwnershipIntegrity.verify_dataset_ownership(fact, evidence, fail_closed=fail_closed)
            EvidenceOwnershipIntegrity.verify_grain_isolation(
                fact.grain,
                evidence.grain,
                evidence.evidence_id,
                fail_closed=fail_closed,
            )

        return BoundFact(
            fact=fact,
            evidence=evidence,
            topic_id=topic_id,
            citation_tokens=dict(fact.tokens),
        )

    @classmethod
    def create_evidence_binding(
        cls,
        topic_id: str,
        dataset_id: int,
        primary_evidence_id: str,
        bound_facts: list[BoundFact] | None = None,
        supporting_evidence_ids: list[str] | None = None,
        grain: str = "aggregate",
        fail_closed: bool = True,
    ) -> EvidenceBinding:
        """Constructs and validates an EvidenceBinding for a topic."""
        # Validate namespace of primary evidence
        ns_violations = EvidenceNamespaceIntegrity.validate_namespaces([primary_evidence_id])
        if ns_violations and fail_closed:
            raise ValueError(f"Namespace validation failed for primary evidence: {ns_violations}")

        binding = EvidenceBinding(
            topic_id=topic_id,
            dataset_id=dataset_id,
            primary_evidence_id=primary_evidence_id,
            supporting_evidence_ids=supporting_evidence_ids or [],
            bound_facts=bound_facts or [],
            grain=grain,
        )

        EvidenceOwnershipIntegrity.validate_binding(binding, fail_closed=fail_closed)
        return binding
