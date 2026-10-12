"""Structural Claim Validator & Causal Language Guard (Backward-Compatible Facade).

All core claim models and validation services have migrated to
`app.services.adaptive_dashboard.evidence`.
This module preserves 100% backward compatibility for all legacy consumers.
"""
from __future__ import annotations

from .evidence import (
    ClaimValidator,
    GovernedAgentResponse,
    GovernedAuditReport,
    StructuredClaim,
)

__all__ = [
    "StructuredClaim",
    "GovernedAuditReport",
    "GovernedAgentResponse",
    "ClaimValidator",
]
