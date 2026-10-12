"""Governed Evidence Binding and Provenance Boundary Package.

Provides the canonical boundary between raw analytical facts and presentation/narrative artifacts:
- Contracts: AnalyticalFact, BoundEvidence, EvidenceItem, BoundFact, EvidenceBinding, StructuredClaim, GovernedAuditReport, GovernedAgentResponse
- Integrity: EvidenceNamespaceIntegrity, EvidenceOwnershipIntegrity, EvidenceOwnershipMismatchError
- Provenance: ProvenanceBinder, ProvenanceRecord
- Services: EvidenceBindingService, ClaimBindingService, ClaimValidator
- Graphs: EvidenceGraph, findings_to_evidence_graph
"""
from __future__ import annotations

from .contracts import (
    AnalyticalFact,
    BoundEvidence,
    BoundFact,
    EvidenceBinding,
    EvidenceGraph,
    EvidenceItem,
    GovernedAgentResponse,
    GovernedAuditReport,
    StructuredClaim,
    UnresolvedTemplateTokenValidator,
)
from .integrity import (
    EvidenceNamespaceIntegrity,
    EvidenceOwnershipIntegrity,
    EvidenceOwnershipMismatchError,
)
from .provenance import (
    ProvenanceBinder,
    ProvenanceRecord,
)
from .evidence_binding import (
    EvidenceBindingService,
)
from .claim_binding import (
    ClaimBindingService,
    ClaimValidator,
)

# Canonical functional helper matching legacy signature
findings_to_evidence_graph = EvidenceBindingService.findings_to_evidence_graph

__all__ = [
    "AnalyticalFact",
    "BoundEvidence",
    "EvidenceItem",
    "BoundFact",
    "EvidenceBinding",
    "StructuredClaim",
    "GovernedAuditReport",
    "GovernedAgentResponse",
    "EvidenceGraph",
    "UnresolvedTemplateTokenValidator",
    "EvidenceNamespaceIntegrity",
    "EvidenceOwnershipIntegrity",
    "EvidenceOwnershipMismatchError",
    "ProvenanceBinder",
    "ProvenanceRecord",
    "EvidenceBindingService",
    "ClaimBindingService",
    "ClaimValidator",
    "findings_to_evidence_graph",
]
