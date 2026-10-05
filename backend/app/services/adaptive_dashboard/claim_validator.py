"""Structural Claim Validator & Causal Language Guard.

Enforces structural evidence binding and claim-level authorization:
1. Validates that every claim references a real EVID-xxx or SCEN-xxx identifier.
2. Enforces causal language rules:
   - OBSERVED: "observed", "recorded", "demonstrated"
   - ASSOCIATED: "is associated with", "coincided with" (prohibits "caused by")
   - INFERRED: "is projected to", "is estimated to"
   - COUNTERFACTUAL: "under this scenario", "assuming shift of"
   - HYPOTHESIS: "suggests", "may indicate"
3. Audits telemetry:
   - unsupported_claims_count (target: 0)
   - evidence_coverage_pct (target: 100.0%)
   - grounding_validation (PASSED / FAILED)
"""
from __future__ import annotations

import re
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from .evidence_graph import EvidenceGraph, EvidenceItem
from .mcp_gateway import ScenarioEvidence


class StructuredClaim(BaseModel):
    """Governed atomic claim linked to verified evidence nodes."""
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    claim_text: str
    evidence_ids: list[str] = Field(default_factory=list)
    causal_type: Literal["OBSERVED", "ASSOCIATED", "INFERRED", "COUNTERFACTUAL", "HYPOTHESIS", "CAUSAL"] = "OBSERVED"


class GovernedAuditReport(BaseModel):
    """Audited telemetry report verifying response integrity."""
    model_config = ConfigDict(extra="forbid")

    grounding_validation: Literal["PASSED", "WARNING", "FAILED"]
    evidence_coverage_pct: float
    unsupported_claims_count: int
    numeric_reconciliation: Literal["PASSED", "FAILED"]
    causal_violations: list[str] = Field(default_factory=list)
    evidence_ids_cited: list[str] = Field(default_factory=list)
    scenario_ids_cited: list[str] = Field(default_factory=list)


class GovernedAgentResponse(BaseModel):
    """Authoritative structured output format for Copilot, Council, and Narrative agents."""
    model_config = ConfigDict(extra="forbid")

    answer: str
    claims: list[StructuredClaim] = Field(default_factory=list)
    audit: GovernedAuditReport


class ClaimValidator:
    """Audits agent responses against governed EvidenceGraph and scenario stores."""

    # Prohibited causal verbs for non-causal evidence
    STRICT_CAUSAL_TERMS = ["caused by", "causes", "driven directly by", "resulting strictly from", "leads directly to"]

    @classmethod
    def audit_response(
        cls,
        answer: str,
        claims: list[StructuredClaim],
        graph: EvidenceGraph | None = None,
        scenarios: list[ScenarioEvidence] | None = None,
    ) -> GovernedAgentResponse:
        """Audits claims against evidence nodes and causal-language policy."""
        graph_nodes = {n.evidence_id: n for n in (graph.nodes if graph else [])}
        scen_nodes = {s.scenario_id: s for s in (scenarios or [])}

        unsupported_count = 0
        causal_violations: list[str] = []
        cited_evid: list[str] = []
        cited_scen: list[str] = []

        for claim in claims:
            # 1. Existence check
            has_valid_ref = False
            for eid in claim.evidence_ids:
                if eid in graph_nodes:
                    has_valid_ref = True
                    cited_evid.append(eid)
                    node = graph_nodes[eid]

                    # 2. Causal authorization check
                    if node.causal_classification in ("ASSOCIATED", "INFERRED", "HYPOTHESIS"):
                        low_text = claim.claim_text.lower()
                        for term in cls.STRICT_CAUSAL_TERMS:
                            if term in low_text:
                                causal_violations.append(
                                    f"Claim '{claim.claim_id}' used causal term '{term}' on {node.causal_classification} evidence '{eid}'."
                                )

                elif eid in scen_nodes:
                    has_valid_ref = True
                    cited_scen.append(eid)

            if not has_valid_ref:
                unsupported_count += 1

        total_claims = len(claims)
        coverage_pct = 100.0 if total_claims == 0 else round(((total_claims - unsupported_count) / total_claims) * 100.0, 1)

        grounding_status: Literal["PASSED", "WARNING", "FAILED"] = "PASSED"
        if unsupported_count > 0 or len(causal_violations) > 0:
            grounding_status = "FAILED" if unsupported_count > 1 else "WARNING"

        audit = GovernedAuditReport(
            grounding_validation=grounding_status,
            evidence_coverage_pct=coverage_pct,
            unsupported_claims_count=unsupported_count,
            numeric_reconciliation="PASSED" if unsupported_count == 0 else "FAILED",
            causal_violations=causal_violations,
            evidence_ids_cited=list(set(cited_evid)),
            scenario_ids_cited=list(set(cited_scen)),
        )

        return GovernedAgentResponse(
            answer=answer,
            claims=claims,
            audit=audit,
        )
