"""Capability Router & Authorization Gate (Phase 11.2).

Enforces:
1. AuthorizationIntegrity: verifies dataset boundaries, role permissions, and sensitive HR grain restrictions.
2. RoutingIntegrity: selects the cheapest valid execution path, prioritizing deterministic tools before invoking any LLM.
"""
from __future__ import annotations

from typing import Any, Literal
from .contracts import (
    ComplexityTier,
    RiskTier,
)


class AuthorizationError(Exception):
    """Raised when query violates authorization boundaries."""
    pass


class AuthorizationGate:
    """Enforces AuthorizationIntegrity across datasets, tenants, and sensitive HR columns."""

    RESTRICTED_INDIVIDUAL_FIELDS = {"ssn", "base_salary", "disciplinary_record", "medical_leave_detail"}

    @classmethod
    def verify_authorization(
        cls,
        user_role: str,
        query: str,
        dataset_id: int | None = None,
        requested_fields: list[str] | None = None,
    ) -> bool:
        """Validates whether the user's role permits executing the requested query and fields."""
        # 1. Dataset ID validation
        if dataset_id is not None and dataset_id <= 0:
            raise AuthorizationError(f"Invalid dataset access ID: {dataset_id}")

        q_lower = query.lower()

        # 2. Viewer role restrictions
        if user_role == "viewer":
            if any(term in q_lower for term in ["salary", "compensation", "bonus", "terminate", "lay off"]):
                raise AuthorizationError("Viewer role is not authorized to access sensitive workforce compensation or termination data.")

        # 3. Field-level privacy restrictions
        fields = requested_fields or []
        for f in fields:
            if f.lower() in cls.RESTRICTED_INDIVIDUAL_FIELDS and user_role not in ["executive", "admin"]:
                raise AuthorizationError(f"Field '{f}' requires executive or admin authorization.")

        return True


class CapabilityRouter:
    """Selects the cheapest valid analytical execution path, prioritizing deterministic execution."""

    @classmethod
    def route_capability(
        cls,
        query: str,
        risk: RiskTier,
        complexity: ComplexityTier,
        context: dict[str, Any] | None = None,
    ) -> tuple[str, bool, list[str]]:
        """Determines:

        1. Required analytical capability
        2. Whether an LLM is required (False = deterministic tool suffices)
        3. Deterministic tools to execute
        """
        q_lower = query.lower().strip()
        ctx = context or {}

        # 1. High-Impact Policy Deliberation (R4) -> Multi-model Council + Critic deliberation
        if risk == RiskTier.R4:
            return "policy_deliberation", True, ["query_metric", "simulate_scenario", "retrieve_evidence", "policy_engine"]

        # 2. Deterministic Scenario Replay
        if any(w in q_lower for w in ["what happens", "simulate", "scenario", "counterfactual"]):
            return "scenario_replay", False, ["simulate_scenario", "policy_engine"]

        # 3. Deterministic Metric Point Lookup (R0 / C0)
        if risk == RiskTier.R0 and complexity == ComplexityTier.C0:
            return "metric_lookup", False, ["query_metric", "get_sheet_metadata"]

        # 4. Deterministic Descriptive Analytics (R1 / C1)
        # "Which department has lowest attendance?" -> query_metric + rank -> 100% deterministic!
        if risk == RiskTier.R1 and complexity <= ComplexityTier.C1:
            if any(w in q_lower for w in ["lowest", "highest", "rank", "average", "gap", "attendance", "compliance", "leaves"]):
                return "descriptive_aggregation", False, ["query_metric", "aggregate_dataframe"]

        # 5. Visualization only
        if any(w in q_lower for w in ["chart", "plot", "visualize", "graph"]):
            return "visualization", False, ["generate_chart_spec", "query_metric"]

        # 6. Interpretation (R2) -> Requires analytical extraction + LLM synthesizer
        if risk == RiskTier.R2:
            return "narrative_synthesis", True, ["query_metric", "retrieve_evidence", "change_point_detection"]

        # 7. Operational Recommendation (R3) -> Requires analytical extraction + LLM synthesizer
        if risk == RiskTier.R3:
            return "recommendation", True, ["query_metric", "simulate_scenario", "retrieve_evidence"]

        # Default fallback
        return "general_analytical", True, ["retrieve_evidence"]
