"""Pydantic and Enum Contracts for the HighView AI Control Plane (Phase 11.1).

Defines strict types for:
- Multi-factor Risk Tiers (R0–R4)
- Computational Complexity Tiers (C0–C3)
- Policy-Aware Execution Budgets
- Claim Types & Evidence Entitlement Verifications
- Auditable Control Plane Trace Records
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class RiskTier(str, Enum):
    """Multi-factor organizational impact risk classification."""
    R0 = "R0"  # Deterministic lookup (point values, facts, row count, metadata)
    R1 = "R1"  # Descriptive analytics (aggregations, rankings, distributions)
    R2 = "R2"  # Interpretation (trend commentary, variance explanation)
    R3 = "R3"  # Recommendation (operational advice, schedule suggestions)
    R4 = "R4"  # High-impact decision support (policy mandates, structural shifts, headcount changes)


class ComplexityTier(str, Enum):
    """Computational and reasoning complexity classification."""
    C0 = "C0"  # Direct point value / scalar lookup (<1 computation)
    C1 = "C1"  # Single aggregation, ranking, or threshold filter across 1 table
    C2 = "C2"  # Multi-table, cross-department join, or scenario evaluation
    C3 = "C3"  # Multi-metric correlation (many columns), deep search, or high-cardinality


class ClaimType(str, Enum):
    """Scientific epistemological category of analytical statements."""
    OBSERVED = "OBSERVED"              # Historical facts directly in records ("was", "were", "attended")
    DERIVED = "DERIVED"                # Mathematically computed metrics ("equals", "calculated to", "rate is")
    ASSOCIATED = "ASSOCIATED"          # Statistical correlation, strictly non-causal ("is associated with")
    COUNTERFACTUAL = "COUNTERFACTUAL"  # What-if historical re-evaluation ("would have satisfied")
    FORECAST = "FORECAST"              # Predictive forward modeling with intervals ("is projected to")
    RECOMMENDATION = "RECOMMENDATION"  # Advisory policy proposal ("recommends considering")


class EvidenceTypeEntitlement(str, Enum):
    """Evidence category required to entitle a specific claim."""
    RAW_RECORD = "RAW_RECORD"                  # Entitles: OBSERVED
    AGGREGATION = "AGGREGATION"                # Entitles: DERIVED, OBSERVED
    CORRELATION = "CORRELATION"                # Entitles: ASSOCIATED (Never CAUSAL)
    SCENARIO_REPLAY = "SCENARIO_REPLAY"        # Entitles: COUNTERFACTUAL (Never FORECAST)
    PREDICTIVE_MODEL = "PREDICTIVE_MODEL"      # Entitles: FORECAST
    COUNCIL_CONSENSUS = "COUNCIL_CONSENSUS"    # Entitles: RECOMMENDATION (R3/R4)


# Matrix defining which Evidence Types are strictly required to entitle each Claim Type
CLAIM_ENTITLEMENT_RULES: dict[ClaimType, list[EvidenceTypeEntitlement]] = {
    ClaimType.OBSERVED: [EvidenceTypeEntitlement.RAW_RECORD, EvidenceTypeEntitlement.AGGREGATION],
    ClaimType.DERIVED: [EvidenceTypeEntitlement.AGGREGATION],
    ClaimType.ASSOCIATED: [EvidenceTypeEntitlement.CORRELATION],
    ClaimType.COUNTERFACTUAL: [EvidenceTypeEntitlement.SCENARIO_REPLAY],
    ClaimType.FORECAST: [EvidenceTypeEntitlement.PREDICTIVE_MODEL],
    ClaimType.RECOMMENDATION: [EvidenceTypeEntitlement.COUNCIL_CONSENSUS, EvidenceTypeEntitlement.AGGREGATION],
}

# Verbs mandated for linguistic conformance
MANDATED_VERB_PATTERNS: dict[ClaimType, list[str]] = {
    ClaimType.OBSERVED: ["was", "were", "observed", "recorded", "stood at"],
    ClaimType.DERIVED: ["equals", "calculated", "measures", "yields", "is"],
    ClaimType.ASSOCIATED: ["associated with", "correlated with", "co-occurred", "tracks with"],
    ClaimType.COUNTERFACTUAL: ["would have", "would meet", "under alternative", "had the policy been"],
    ClaimType.FORECAST: ["is projected to", "is forecasted to", "predicted within interval", "expected between"],
    ClaimType.RECOMMENDATION: ["recommends considering", "advises evaluating", "suggests exploring", "proposes reviewing"],
}

# Prohibited verbs (e.g. claiming causation when only correlation exists)
PROHIBITED_CAUSAL_VERBS: list[str] = [
    "caused", "resulted from", "drove the decline of", "responsible for", "leads to", "triggered"
]


class RequestFactorProfile(BaseModel):
    """Factors evaluated by MultiFactorRiskClassifier to determine RiskTier."""
    model_config = ConfigDict(extra="ignore")

    intent: str
    affected_population_scope: Literal["individual", "team", "department", "organization", "unknown"] = "unknown"
    decision_reversibility: Literal["reversible", "moderate", "irreversible"] = "reversible"
    financial_operational_impact: Literal["negligible", "low", "medium", "high", "critical"] = "low"
    changes_organizational_rule: bool = False
    query_text: str = ""


class ExecutionBudget(BaseModel):
    """Resource and SLA limits enforced on execution."""
    model_config = ConfigDict(extra="ignore")

    risk_tier: RiskTier
    complexity_tier: ComplexityTier
    max_llm_calls: int = 0
    max_tool_calls: int = 2
    critic_required: bool = False
    council_required: bool = False
    target_latency_ms: float = 250.0
    max_latency_ms: float = 1000.0


class ClaimEntitlementVerdict(BaseModel):
    """Decision from ClaimEntitlementGovernor on whether a claim is authorized."""
    model_config = ConfigDict(extra="ignore")

    claim_text: str
    detected_claim_type: ClaimType
    supporting_evidence_types: list[str]
    is_entitled: bool
    linguistic_conformance: bool
    rejection_reason: str | None = None
    suggested_reformulation: str | None = None


class ControlPlaneAuditRecord(BaseModel):
    """Auditable control-plane routing record emitted for every request."""
    model_config = ConfigDict(extra="ignore")

    request_id: str = Field(default_factory=lambda: f"REQ-{uuid.uuid4().hex[:8].upper()}")
    query: str
    risk_tier: RiskTier
    complexity_tier: ComplexityTier
    capability: str
    deterministic_tools_used: list[str] = Field(default_factory=list)
    model_route: str = "deterministic"
    critic_required: bool = False
    council_required: bool = False
    evidence_coverage: float = 1.0
    budget_status: Literal["PASS", "EXCEEDED", "THROTTLED"] = "PASS"
    claim_entitlement_status: Literal["ALLOW", "BLOCKED", "REFORMULATED"] = "ALLOW"
    latency_ms: float = 0.0
    timestamp_unix: float = Field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "query": self.query,
            "risk_tier": self.risk_tier.value,
            "complexity_tier": self.complexity_tier.value,
            "capability": self.capability,
            "deterministic_tools_used": self.deterministic_tools_used,
            "model_route": self.model_route,
            "critic_required": self.critic_required,
            "council_required": self.council_required,
            "evidence_coverage": self.evidence_coverage,
            "budget_status": self.budget_status,
            "claim_entitlement_status": self.claim_entitlement_status,
            "latency_ms": round(self.latency_ms, 2),
            "timestamp_unix": self.timestamp_unix,
        }


class ControlPlaneRequest(BaseModel):
    """Input payload delivered to HighView AI Control Plane."""
    model_config = ConfigDict(extra="ignore")

    query: str
    dataset_id: int | None = 99747
    user_id: str | None = "analyst_01"
    user_role: Literal["viewer", "analyst", "hr_business_partner", "executive", "admin"] = "analyst"
    prior_context: dict[str, Any] = Field(default_factory=dict)
    force_council: bool = False


class ControlPlaneResponse(BaseModel):
    """Authoritative structured output from the AI Control Plane."""
    model_config = ConfigDict(extra="ignore")

    answer: str
    audit_record: ControlPlaneAuditRecord
    claims_audited: list[ClaimEntitlementVerdict] = Field(default_factory=list)
    evidence_items: list[dict[str, Any]] = Field(default_factory=list)
    visual_spec: dict[str, Any] | None = None
    is_blocked: bool = False
    block_reason: str | None = None


class ControlPlaneMode(str, Enum):
    """Execution mode of the AI Control Plane."""
    SHADOW = "SHADOW"    # Runs alongside legacy route, logs comparisons, does not block
    WARN = "WARN"        # Enforces route, logs warnings on violations without throwing
    ENFORCE = "ENFORCE"  # Strictly enforces control plane routing, blocks unentitled claims


class DecisionProvenance(BaseModel):
    """Comprehensive auditable provenance graph for every recommendation and narrative."""
    model_config = ConfigDict(extra="ignore")

    request_id: str
    query: str
    surface: str
    risk_tier: RiskTier
    complexity_tier: ComplexityTier
    capability: str
    deterministic_tools_used: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    scenario_ids: list[str] = Field(default_factory=list)
    model_route: str
    critic_result: str | None = None
    council_result: str | None = None
    claim_types: list[ClaimType] = Field(default_factory=list)
    final_response_hash: str = ""
    versions: dict[str, str] = Field(default_factory=lambda: {
        "semantic_catalog_version": "v2.4.0",
        "evidence_engine_version": "v3.1.0",
        "policy_version": "v1.2.0",
        "ranking_version": "v2.0.0",
        "visual_compiler_version": "v2.1.0",
        "control_plane_version": "v1.12.0",
        "routing_policy_version": "v1.0.0",
        "scenario_engine_version": "v1.10.0",
        "model_name": "qwen2.5:7b-instruct",
        "model_version": "2026.1",
        "prompt_version": "v4.2.0",
    })
    timestamp_unix: float = Field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "query": self.query,
            "surface": self.surface,
            "risk_tier": self.risk_tier.value,
            "complexity_tier": self.complexity_tier.value,
            "capability": self.capability,
            "deterministic_tools_used": self.deterministic_tools_used,
            "evidence_ids": self.evidence_ids,
            "scenario_ids": self.scenario_ids,
            "model_route": self.model_route,
            "critic_result": self.critic_result,
            "council_result": self.council_result,
            "claim_types": [c.value for c in self.claim_types],
            "final_response_hash": self.final_response_hash,
            "versions": self.versions,
            "timestamp_unix": self.timestamp_unix,
        }

    @property
    def provenance_hash(self) -> str:
        """Returns deterministic cryptographic hash over all provenance attributes."""
        dumped = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(dumped.encode("utf-8")).hexdigest()[:16]


class ShadowValidationReport(BaseModel):
    """Side-by-side comparison between legacy and control plane execution."""
    model_config = ConfigDict(extra="ignore")

    request_id: str
    query: str
    legacy_route: str
    control_plane_route: str
    latency_legacy_ms: float
    latency_control_plane_ms: float
    llm_calls_saved: int
    tool_calls_delta: int
    claim_violations_caught: int
    verdict: Literal["OPTIMIZED", "EQUIVALENT", "BLOCKED_VIOLATION"]


class CouncilAvoidanceMetrics(BaseModel):
    """Operational telemetry tracking how effectively the Control Plane reserves the Council."""
    model_config = ConfigDict(extra="ignore")

    total_requests: int = 0
    deterministic_count: int = 0
    single_model_count: int = 0
    critic_count: int = 0
    council_count: int = 0
    council_avoidance_rate: float = 100.0
    deterministic_resolution_rate: float = 0.0
    single_model_resolution_rate: float = 0.0
    council_escalation_rate: float = 0.0


class HighviewAIRequest(BaseModel):
    """Universal request delivered to the mandatory HighviewAI facade."""
    model_config = ConfigDict(extra="ignore")

    query: str
    surface: Literal[
        "hriday",
        "dashboard_ai",
        "presentation_studio",
        "executive_briefing",
        "report_generator",
        "scenario_narrative",
        "copilot_api",
        "future_agents",
    ]
    dataset_id: int | None = 99747
    sheet_id: int | None = None
    user_id: str | None = "analyst_01"
    user_role: Literal["viewer", "analyst", "hr_business_partner", "executive", "admin"] = "analyst"
    context: dict[str, Any] = Field(default_factory=dict)
    force_council: bool = False
    mode: ControlPlaneMode = ControlPlaneMode.ENFORCE


class HighviewAIResponse(BaseModel):
    """Universal governed output returned from HighviewAI facade."""
    model_config = ConfigDict(extra="ignore")

    answer: str
    surface: str
    audit_record: ControlPlaneAuditRecord
    provenance: DecisionProvenance
    shadow_report: ShadowValidationReport | None = None
    claims_audited: list[ClaimEntitlementVerdict] = Field(default_factory=list)
    evidence_items: list[dict[str, Any]] = Field(default_factory=list)
    visual_spec: dict[str, Any] | None = None
    is_blocked: bool = False
    block_reason: str | None = None
