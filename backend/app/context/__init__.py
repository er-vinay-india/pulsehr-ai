"""Enterprise Knowledge & Context Fabric (Phase F).

Provides:
- ContextDocument & ContextEvidence (CTX-*) contracts
- ContextStore singleton indexing organizational policies, thresholds, and KPI definitions
- Strict separation of empirical EVID-*, contextual CTX-*, and counterfactual SCEN-* namespaces.
"""
from __future__ import annotations

from .contracts import (
    ContextArtifactType,
    ContextChunk,
    ContextDocument,
    ContextEvidence,
    ContextQueryResult,
)
from .store import ContextStore, context_store

__all__ = [
    "ContextArtifactType",
    "ContextChunk",
    "ContextDocument",
    "ContextEvidence",
    "ContextQueryResult",
    "ContextStore",
    "context_store",
]
