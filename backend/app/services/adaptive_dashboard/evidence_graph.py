"""Evidence Graph Store and EvidenceItem Models (Backward-Compatible Facade).

All core evidence models, integrity validators, and graph implementations
have migrated to `app.services.adaptive_dashboard.evidence`.
This module preserves 100% backward compatibility for all legacy consumers.
"""
from __future__ import annotations

from .evidence import (
    EvidenceGraph,
    EvidenceItem,
    UnresolvedTemplateTokenValidator,
    findings_to_evidence_graph,
)

__all__ = [
    "EvidenceItem",
    "EvidenceGraph",
    "UnresolvedTemplateTokenValidator",
    "findings_to_evidence_graph",
]
