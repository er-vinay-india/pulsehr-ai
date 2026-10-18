"""
HighView Ingestion V2 — Phase I8.2 Governed Consumer Gateway Package
Stage: Consumer Cutover Infrastructure, Circuit Breakers & Rollback Foundation
Exports the central ConsumerIntelligenceGateway, state machine, circuit breaker,
readiness evaluator, and routing ledger.
"""

from app.services.ingestion_v2.gateway.circuit_breaker import CircuitBreakerManager
from app.services.ingestion_v2.gateway.gateway import (
    ConsumerIntelligenceGateway,
    RoutingFallbackDisallowedError,
    get_consumer_gateway,
    set_consumer_gateway,
)
from app.services.ingestion_v2.gateway.persistence import (
    CutoverPersistenceStore,
    CutoverStateCorruptionError,
    UnknownCutoverSchemaVersionError,
)
from app.services.ingestion_v2.gateway.provenance import RoutingProvenanceLedger
from app.services.ingestion_v2.gateway.readiness import ConsumerReadinessEvaluator
from app.services.ingestion_v2.gateway.state_machine import (
    ConsumerCutoverStateMachine,
    CutoverOrderingViolationError,
    InvalidCutoverTransitionError,
)

__all__ = [
    "ConsumerIntelligenceGateway",
    "RoutingFallbackDisallowedError",
    "get_consumer_gateway",
    "set_consumer_gateway",
    "ConsumerCutoverStateMachine",
    "CircuitBreakerManager",
    "ConsumerReadinessEvaluator",
    "RoutingProvenanceLedger",
    "CutoverPersistenceStore",
    "CutoverStateCorruptionError",
    "UnknownCutoverSchemaVersionError",
    "InvalidCutoverTransitionError",
    "CutoverOrderingViolationError",
]

