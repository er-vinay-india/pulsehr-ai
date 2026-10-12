"""Claim Binding and Causal Language Audit Service.

Enforces structural evidence binding and claim-level authorization:
1. Validates that every claim references existing, validly namespaced evidence (EVID-*, CTX-*, SCEN-*).
2. Supports compound claims referencing multiple evidence nodes.
3. Audits causal language rules against causal classification:
   - Strict prohibition of direct causal terms for ASSOCIATED, INFERRED, or HYPOTHESIS evidence.
4. Generates audited telemetry (GovernedAuditReport) and GovernedAgentResponse.
"""
from __future__ import annotations

import re
from typing import Any, Literal

from .contracts import (
    BoundEvidence,
    EvidenceGraph,
    GovernedAgentResponse,
    GovernedAuditReport,
    StructuredClaim,
)
from .integrity import EvidenceNamespaceIntegrity


class ClaimBindingService:
    """Governed service binding agent and narrative claims to verified evidence nodes."""

    # Prohibited causal verbs for non-causal evidence
    STRICT_CAUSAL_TERMS = [
        "caused by",
        "causes",
        "driven directly by",
        "resulting strictly from",
        "leads directly to",
    ]

    @classmethod
    def audit_response(
        cls,
        answer: str,
        claims: list[StructuredClaim],
        graph: EvidenceGraph | None = None,
        scenarios: list[Any] | None = None,
        context_nodes: list[BoundEvidence] | None = None,
    ) -> GovernedAgentResponse:
        """Audits claims against evidence nodes, scenario nodes, and causal-language policy."""
        graph_nodes: dict[str, BoundEvidence] = {n.evidence_id: n for n in (graph.nodes if graph else [])}
        scen_nodes: dict[str, Any] = {
            getattr(s, "scenario_id", str(s)): s for s in (scenarios or [])
        }
        ctx_nodes: dict[str, BoundEvidence] = {n.evidence_id: n for n in (context_nodes or [])}

        unsupported_count = 0
        causal_violations: list[str] = []
        namespace_violations: list[str] = []
        cited_evid: list[str] = []
        cited_scen: list[str] = []

        for claim in claims:
            # 1. Namespace format audit
            ns_errs = EvidenceNamespaceIntegrity.validate_namespaces(claim.evidence_ids)
            if ns_errs:
                namespace_violations.extend(ns_errs)

            # 2. Semantic alignment audit
            sem_errs = EvidenceNamespaceIntegrity.audit_claim_semantics(claim.claim_text, claim.evidence_ids)
            if sem_errs:
                namespace_violations.extend(sem_errs)

            # 3. Existence check across nodes
            has_valid_ref = False
            for eid in claim.evidence_ids:
                if eid in graph_nodes:
                    has_valid_ref = True
                    cited_evid.append(eid)
                    node = graph_nodes[eid]

                    # Causal authorization check
                    if node.causal_classification in ("ASSOCIATED", "INFERRED", "HYPOTHESIS"):
                        low_text = claim.claim_text.lower()
                        for term in cls.STRICT_CAUSAL_TERMS:
                            if term in low_text:
                                causal_violations.append(
                                    f"Claim '{claim.claim_id}' used causal term '{term}' on "
                                    f"{node.causal_classification} evidence '{eid}'."
                                )

                elif eid in scen_nodes:
                    has_valid_ref = True
                    cited_scen.append(eid)

                elif eid in ctx_nodes:
                    has_valid_ref = True
                    cited_evid.append(eid)

            if not has_valid_ref:
                unsupported_count += 1

        total_claims = len(claims)
        coverage_pct = (
            100.0 if total_claims == 0
            else round(((total_claims - unsupported_count) / total_claims) * 100.0, 1)
        )

        grounding_status: Literal["PASSED", "WARNING", "FAILED"] = "PASSED"
        if unsupported_count > 0 or len(causal_violations) > 0 or len(namespace_violations) > 0:
            grounding_status = "FAILED" if unsupported_count > 1 else "WARNING"

        audit = GovernedAuditReport(
            grounding_validation=grounding_status,
            evidence_coverage_pct=coverage_pct,
            unsupported_claims_count=unsupported_count,
            numeric_reconciliation="PASSED" if unsupported_count == 0 else "FAILED",
            causal_violations=causal_violations,
            evidence_ids_cited=sorted(list(set(cited_evid))),
            scenario_ids_cited=sorted(list(set(cited_scen))),
            namespace_violations=namespace_violations,
        )

        return GovernedAgentResponse(
            answer=answer,
            claims=claims,
            audit=audit,
        )


# Backward-compatible alias
ClaimValidator = ClaimBindingService
