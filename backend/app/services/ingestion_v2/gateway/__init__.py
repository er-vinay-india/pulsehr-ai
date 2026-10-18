"""
HighView Ingestion V2 — Phase I8.2 Governed Consumer Gateway Package
Stage: Consumer Cutover Infrastructure, Circuit Breakers & Rollback Foundation
Exports the central ConsumerIntelligenceGateway, state machine, circuit breaker,
readiness evaluator, and routing ledger.
"""

from app.services.ingestion_v2.gateway.circuit_breaker import CircuitBreakerManager
from app.services.ingestion_v2.gateway.gateway import ConsumerIntelligenceGateway
from app.services.ingestion_v2.gateway.provenance import RoutingProvenanceLedger
from app.services.ingestion_v2.gateway.readiness import ConsumerReadinessEvaluator
from app.services.ingestion_v2.gateway.state_machine import (
    ConsumerCutoverStateMachine,
    CutoverOrderingViolationError,
    InvalidCutoverTransitionError,
)

__all__ = [
    "ConsumerIntelligenceGateway",
    "ConsumerCutoverStateMachine",
    "CircuitBreakerManager",
    "ConsumerReadinessEvaluator",
    "RoutingProvenanceLedger",
    "InvalidCutoverTransitionError",
    "CutoverOrderingViolationError",
]
