"""Governed MCP Analytical Gateway and Agent Control Plane.

Provides a unified, governed tool execution layer for all AI consumers:
- HRIDAY Copilot
- AI Council Critics
- Story Planner
- Executive Deck Generator

Enforces:
1. Strict Agent Role-Based Access Control (RBAC).
2. Deterministic execution over Semantic Catalog & Evidence Graph.
3. Separation of Observed Evidence (EVID-xxx) from Counterfactual Scenarios (SCEN-xxx).
4. MCP tool schema compliance for agent discovery.
"""
from __future__ import annotations

import enum
import logging
from typing import Any, Callable, Literal
from pydantic import BaseModel, ConfigDict, Field

from .contracts import AdaptiveDashboardResponse, UnifiedFinding
from .evidence_graph import EvidenceGraph, EvidenceItem, findings_to_evidence_graph
from .forecast_gatekeeper import ChangePoint, ForecastGatekeeper, ForecastResult, ScenarioImpact
from .insight_ranker import InsightRankingEngine, RankedInsight
from .semantic_catalog import SemanticCatalog, infer_semantic_catalog

logger = logging.getLogger(__name__)


class AgentRole(str, enum.Enum):
    """Governed agent identities within the Highview platform."""
    HRIDAY_COPILOT = "hriday_copilot"
    COUNCIL_CRITIC = "council_critic"
    STORY_PLANNER = "story_planner"
    EXECUTIVE_DECK = "executive_deck"
    ANONYMOUS_QUERY = "anonymous_query"


class MCPToolPermission(BaseModel):
    """Authorization policy for a single MCP tool."""
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    allowed_roles: list[AgentRole]
    description: str
    is_mutation: bool = False
    requires_evidence_logging: bool = True


class ScenarioEvidence(BaseModel):
    """Counterfactual scenario projection isolated from observed facts."""
    model_config = ConfigDict(extra="forbid")

    scenario_id: str  # e.g. "SCEN-001"
    metric: str
    baseline_value: float
    simulated_delta_pct: float
    projected_outcome: float
    affected_population: int
    business_consequence: str
    status: Literal["simulated", "invalid_bounds"] = "simulated"


class MCPToolResult(BaseModel):
    """Structured, audited output of an MCP tool execution."""
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    status: Literal["success", "permission_denied", "not_found", "error"]
    caller_role: AgentRole
    data: dict[str, Any] = Field(default_factory=dict)
    evidence_ids_accessed: list[str] = Field(default_factory=list)
    scenario_ids_generated: list[str] = Field(default_factory=list)
    error_message: str | None = None


# -----------------------------------------------------------------------------
# Tool Permission Matrix
# -----------------------------------------------------------------------------

TOOL_POLICIES: dict[str, MCPToolPermission] = {
    "discover_semantic_metrics": MCPToolPermission(
        tool_name="discover_semantic_metrics",
        allowed_roles=[AgentRole.HRIDAY_COPILOT, AgentRole.COUNCIL_CRITIC, AgentRole.STORY_PLANNER, AgentRole.EXECUTIVE_DECK],
        description="Discover governed metrics, units, and directionality for a sheet.",
    ),
    "get_metric_definition": MCPToolPermission(
        tool_name="get_metric_definition",
        allowed_roles=[AgentRole.HRIDAY_COPILOT, AgentRole.COUNCIL_CRITIC, AgentRole.STORY_PLANNER, AgentRole.EXECUTIVE_DECK],
        description="Fetch verified formula, policy threshold, and unit for a specific metric.",
    ),
    "query_metric": MCPToolPermission(
        tool_name="query_metric",
        allowed_roles=[AgentRole.HRIDAY_COPILOT, AgentRole.COUNCIL_CRITIC, AgentRole.EXECUTIVE_DECK],
        description="Execute deterministic metric query aggregated by dimension.",
    ),
    "compare_segments": MCPToolPermission(
        tool_name="compare_segments",
        allowed_roles=[AgentRole.HRIDAY_COPILOT, AgentRole.COUNCIL_CRITIC, AgentRole.STORY_PLANNER, AgentRole.EXECUTIVE_DECK],
        description="Compare performance across cohorts or segments against benchmark.",
    ),
    "get_evidence": MCPToolPermission(
        tool_name="get_evidence",
        allowed_roles=[AgentRole.HRIDAY_COPILOT, AgentRole.COUNCIL_CRITIC, AgentRole.STORY_PLANNER, AgentRole.EXECUTIVE_DECK],
        description="Retrieve exact calculation, population, and provenance for an EVID-xxx ID.",
    ),
    "get_evidence_lineage": MCPToolPermission(
        tool_name="get_evidence_lineage",
        allowed_roles=[AgentRole.COUNCIL_CRITIC, AgentRole.HRIDAY_COPILOT],
        description="Retrieve cryptographic snapshot, row lineage, and calculation trace for audit.",
    ),
    "query_insights": MCPToolPermission(
        tool_name="query_insights",
        allowed_roles=[AgentRole.HRIDAY_COPILOT, AgentRole.STORY_PLANNER, AgentRole.EXECUTIVE_DECK],
        description="Query top ranked deterministic insights prioritized by multi-factor scoring.",
    ),
    "query_change_points": MCPToolPermission(
        tool_name="query_change_points",
        allowed_roles=[AgentRole.HRIDAY_COPILOT, AgentRole.COUNCIL_CRITIC, AgentRole.EXECUTIVE_DECK],
        description="Detect structural regime shifts and sudden breaks (>2.0 sigma) in a series.",
    ),
    "get_forecast": MCPToolPermission(
        tool_name="get_forecast",
        allowed_roles=[AgentRole.HRIDAY_COPILOT, AgentRole.EXECUTIVE_DECK],
        description="Retrieve governed time series projection with N >= 6 eligibility checks.",
    ),
    "run_counterfactual": MCPToolPermission(
        tool_name="run_counterfactual",
        allowed_roles=[AgentRole.HRIDAY_COPILOT, AgentRole.EXECUTIVE_DECK],
        description="Run deterministic what-if scenario. Yields isolated SCEN-xxx tokens.",
    ),
    "get_dashboard_context": MCPToolPermission(
        tool_name="get_dashboard_context",
        allowed_roles=[AgentRole.HRIDAY_COPILOT, AgentRole.STORY_PLANNER, AgentRole.EXECUTIVE_DECK],
        description="Fetch complete executive briefing, priority insight, and layout specs.",
    ),
    "discover_dataset_metrics": MCPToolPermission(
        tool_name="discover_dataset_metrics",
        allowed_roles=[AgentRole.HRIDAY_COPILOT, AgentRole.COUNCIL_CRITIC, AgentRole.STORY_PLANNER, AgentRole.EXECUTIVE_DECK],
        description="Discover all governed metrics across all sibling sheets in an uploaded workbook.",
    ),
    "query_dataset_insights": MCPToolPermission(
        tool_name="query_dataset_insights",
        allowed_roles=[AgentRole.HRIDAY_COPILOT, AgentRole.STORY_PLANNER, AgentRole.EXECUTIVE_DECK],
        description="Query top global insights across all sheets using slot-budgeted ranking.",
    ),
    "get_dataset_relationships": MCPToolPermission(
        tool_name="get_dataset_relationships",
        allowed_roles=[AgentRole.HRIDAY_COPILOT, AgentRole.COUNCIL_CRITIC, AgentRole.STORY_PLANNER, AgentRole.EXECUTIVE_DECK],
        description="Retrieve verified cross-sheet relationship graph and join safety metrics.",
    ),
    "query_cross_sheet_insights": MCPToolPermission(
        tool_name="query_cross_sheet_insights",
        allowed_roles=[AgentRole.HRIDAY_COPILOT, AgentRole.COUNCIL_CRITIC, AgentRole.STORY_PLANNER, AgentRole.EXECUTIVE_DECK],
        description="Retrieve cross-sheet interaction evidence and joined cohort insights.",
    ),
}


class GovernedMCPGateway:
    """Analytical Control Plane dispatching governed tools to AI consumers."""

    @classmethod
    def get_tool_definitions(cls, role: AgentRole) -> list[dict[str, Any]]:
        """Returns OpenAPI/MCP-compliant tool schemas accessible to the caller role."""
        available_tools = []
        for name, policy in TOOL_POLICIES.items():
            if role in policy.allowed_roles:
                available_tools.append({
                    "name": name,
                    "description": policy.description,
                    "parameters": {"type": "object", "properties": {"sheet_id": {"type": "integer"}}},
                })
        return available_tools

    @classmethod
    def execute_tool(
        cls,
        tool_name: str,
        params: dict[str, Any],
        caller_role: AgentRole,
        dashboard_response: AdaptiveDashboardResponse | None = None,
    ) -> MCPToolResult:
        """Executes a governed tool enforcing agent role authorization and mathematical isolation."""
        # 1. Authorization check
        policy = TOOL_POLICIES.get(tool_name)
        if not policy:
            return MCPToolResult(
                tool_name=tool_name,
                status="not_found",
                caller_role=caller_role,
                error_message=f"Tool '{tool_name}' is not registered in the governed analytical control plane.",
            )

        if caller_role not in policy.allowed_roles:
            return MCPToolResult(
                tool_name=tool_name,
                status="permission_denied",
                caller_role=caller_role,
                error_message=f"Role '{caller_role.value}' is unauthorized to invoke '{tool_name}'. Allowed: {[r.value for r in policy.allowed_roles]}",
            )

        is_dataset_tool = "dataset" in tool_name or "cross_sheet" in tool_name
        if not dashboard_response and not is_dataset_tool:
            return MCPToolResult(
                tool_name=tool_name,
                status="error",
                caller_role=caller_role,
                error_message="Governed runtime requires an active AdaptiveDashboardResponse context.",
            )

        # 2. Dispatch authorized tool
        try:
            handler = getattr(cls, f"_tool_{tool_name}", None)
            if not handler:
                return MCPToolResult(
                    tool_name=tool_name,
                    status="error",
                    caller_role=caller_role,
                    error_message=f"Implementation for '{tool_name}' missing on gateway.",
                )
            return handler(params, caller_role, dashboard_response)
        except Exception as e:
            logger.exception("Error executing governed MCP tool %s: %s", tool_name, e)
            return MCPToolResult(
                tool_name=tool_name,
                status="error",
                caller_role=caller_role,
                error_message=str(e),
            )

    # -------------------------------------------------------------------------
    # Governed Tool Implementations
    # -------------------------------------------------------------------------

    @classmethod
    def _tool_discover_semantic_metrics(
        cls, params: dict[str, Any], role: AgentRole, resp: AdaptiveDashboardResponse
    ) -> MCPToolResult:
        catalog = resp.semantic_catalog or {}
        metrics = catalog.get("metrics", [])
        return MCPToolResult(
            tool_name="discover_semantic_metrics",
            status="success",
            caller_role=role,
            data={"sheet_id": resp.sheet_id, "entity_type": catalog.get("entity_type", "record"), "metrics": metrics},
        )

    @classmethod
    def _tool_get_metric_definition(
        cls, params: dict[str, Any], role: AgentRole, resp: AdaptiveDashboardResponse
    ) -> MCPToolResult:
        metric_name = params.get("metric_name", "")
        catalog = resp.semantic_catalog or {}
        for m in catalog.get("metrics", []):
            if m.get("name") == metric_name or m.get("source_column") == metric_name:
                return MCPToolResult(
                    tool_name="get_metric_definition",
                    status="success",
                    caller_role=role,
                    data={"metric": m},
                )
        return MCPToolResult(
            tool_name="get_metric_definition",
            status="not_found",
            caller_role=role,
            error_message=f"Metric '{metric_name}' not found in governed catalog.",
        )

    @classmethod
    def _tool_query_metric(
        cls, params: dict[str, Any], role: AgentRole, resp: AdaptiveDashboardResponse
    ) -> MCPToolResult:
        # Returns verified primary or breakdown values
        val = resp.element.verified_value
        return MCPToolResult(
            tool_name="query_metric",
            status="success",
            caller_role=role,
            data={
                "metric": resp.element.business_concept,
                "value": val,
                "formatted_value": resp.element.formatted_value,
                "unit": resp.element.unit,
                "population": resp.element.inspect.applicable_population,
                "calculation": resp.element.inspect.calculation_method,
            },
        )

    @classmethod
    def _tool_compare_segments(
        cls, params: dict[str, Any], role: AgentRole, resp: AdaptiveDashboardResponse
    ) -> MCPToolResult:
        comp = resp.quaternary_element
        disp = resp.quinary_element
        items = []
        if disp and disp.items:
            items = [item.model_dump() for item in disp.items]
        elif comp and comp.items:
            items = [item.model_dump() for item in comp.items]

        return MCPToolResult(
            tool_name="compare_segments",
            status="success",
            caller_role=role,
            data={"segments": items, "spread": getattr(disp, "formatted_spread", None)},
        )

    @classmethod
    def _tool_get_evidence(
        cls, params: dict[str, Any], role: AgentRole, resp: AdaptiveDashboardResponse
    ) -> MCPToolResult:
        evidence_id = params.get("evidence_id", "")
        graph = resp.evidence_graph or {}
        nodes = graph.get("nodes", [])
        for n in nodes:
            if n.get("evidence_id") == evidence_id:
                return MCPToolResult(
                    tool_name="get_evidence",
                    status="success",
                    caller_role=role,
                    data={"evidence": n},
                    evidence_ids_accessed=[evidence_id],
                )
        return MCPToolResult(
            tool_name="get_evidence",
            status="not_found",
            caller_role=role,
            error_message=f"Evidence ID '{evidence_id}' does not exist in graph.",
        )

    @classmethod
    def _tool_get_evidence_lineage(
        cls, params: dict[str, Any], role: AgentRole, resp: AdaptiveDashboardResponse
    ) -> MCPToolResult:
        evidence_id = params.get("evidence_id", "")
        graph = resp.evidence_graph or {}
        nodes = graph.get("nodes", [])
        target = next((n for n in nodes if n.get("evidence_id") == evidence_id), None)
        if not target:
            return MCPToolResult(
                tool_name="get_evidence_lineage",
                status="not_found",
                caller_role=role,
                error_message=f"Evidence node '{evidence_id}' not found.",
            )

        lineage = {
            "evidence_id": evidence_id,
            "snapshot_hash": resp.snapshot,
            "source_sheet": resp.manifest.sheet_name,
            "total_rows": resp.manifest.row_count,
            "calculation": target.get("calculation"),
            "source_table": target.get("source_table"),
            "provenance": target.get("provenance"),
            "tokens": target.get("tokens"),
        }
        return MCPToolResult(
            tool_name="get_evidence_lineage",
            status="success",
            caller_role=role,
            data={"lineage": lineage},
            evidence_ids_accessed=[evidence_id],
        )

    @classmethod
    def _tool_query_insights(
        cls, params: dict[str, Any], role: AgentRole, resp: AdaptiveDashboardResponse
    ) -> MCPToolResult:
        top_n = params.get("top_n", 6)
        story = resp.story_plan or {}
        graph = resp.evidence_graph or {}
        nodes = graph.get("nodes", [])
        return MCPToolResult(
            tool_name="query_insights",
            status="success",
            caller_role=role,
            data={
                "narrative_angle": story.get("narrative_angle"),
                "hero_evidence_id": story.get("hero_evidence_id"),
                "top_insights": nodes[:top_n],
            },
            evidence_ids_accessed=[n["evidence_id"] for n in nodes[:top_n] if "evidence_id" in n],
        )

    @classmethod
    def _tool_query_change_points(
        cls, params: dict[str, Any], role: AgentRole, resp: AdaptiveDashboardResponse
    ) -> MCPToolResult:
        # Check secondary time series
        sec = resp.secondary_element
        if not sec or not sec.chart_series or not sec.chart_series.points:
            return MCPToolResult(
                tool_name="query_change_points",
                status="success",
                caller_role=role,
                data={"change_points": [], "message": "No temporal series observed in active dataset."},
            )

        pts = sec.chart_series.points
        periods = [p.period for p in pts]
        vals = [p.average_hours or 0.0 for p in pts]
        change_points = ForecastGatekeeper.detect_change_points(periods, vals)
        return MCPToolResult(
            tool_name="query_change_points",
            status="success",
            caller_role=role,
            data={"change_points": [cp.model_dump() for cp in change_points]},
        )

    @classmethod
    def _tool_get_forecast(
        cls, params: dict[str, Any], role: AgentRole, resp: AdaptiveDashboardResponse
    ) -> MCPToolResult:
        sec = resp.secondary_element
        horizon = params.get("horizon", 3)
        if not sec or not sec.chart_series or not sec.chart_series.points:
            return MCPToolResult(
                tool_name="get_forecast",
                status="success",
                caller_role=role,
                data={"forecast_status": "insufficient_history", "forecast_points": []},
            )

        pts = sec.chart_series.points
        periods = [p.period for p in pts]
        vals = [p.average_hours or 0.0 for p in pts]
        fc_res = ForecastGatekeeper.evaluate_forecast(periods, vals, horizon=horizon)
        return MCPToolResult(
            tool_name="get_forecast",
            status="success",
            caller_role=role,
            data=fc_res.model_dump(),
        )

    @classmethod
    def _tool_run_counterfactual(
        cls, params: dict[str, Any], role: AgentRole, resp: AdaptiveDashboardResponse
    ) -> MCPToolResult:
        """Executes what-if scenario. NEVER mutates EvidenceGraph; returns isolated SCEN-xxx."""
        delta_pct = float(params.get("delta_pct", 0.0))
        baseline = float(resp.element.verified_value or 100.0)
        metric_name = resp.element.business_concept
        unit = resp.element.unit

        scen_id = f"SCEN-{abs(int(delta_pct * 10)):03d}"
        impacts = ForecastGatekeeper.simulate_scenarios(
            baseline_value=baseline,
            metric_name=metric_name,
            unit=unit,
            scenarios=[(f"Scenario {delta_pct:+.1f}%", delta_pct)],
        )

        impact = impacts[0]
        scenario_evidence = ScenarioEvidence(
            scenario_id=scen_id,
            metric=metric_name,
            baseline_value=baseline,
            simulated_delta_pct=delta_pct,
            projected_outcome=impact.projected_outcome,
            affected_population=getattr(resp.contract, "distinct_entity_count", 0) or 0,
            business_consequence=impact.business_consequence,
        )

        return MCPToolResult(
            tool_name="run_counterfactual",
            status="success",
            caller_role=role,
            data={"scenario_result": scenario_evidence.model_dump()},
            scenario_ids_generated=[scen_id],
        )

    @classmethod
    def _tool_get_dashboard_context(
        cls, params: dict[str, Any], role: AgentRole, resp: AdaptiveDashboardResponse
    ) -> MCPToolResult:
        story = resp.story_plan or {}
        briefing = resp.briefing_element
        return MCPToolResult(
            tool_name="get_dashboard_context",
            status="success",
            caller_role=role,
            data={
                "sheet_name": resp.manifest.sheet_name,
                "snapshot": resp.snapshot,
                "narrative_angle": story.get("narrative_angle"),
                "executive_summary": story.get("executive_summary"),
                "briefing_transcript": getattr(briefing, "transcript_text", ""),
                "run_status": resp.run_status,
            },
        )

    @classmethod
    def _tool_discover_dataset_metrics(
        cls, params: dict[str, Any], role: AgentRole, resp: AdaptiveDashboardResponse | None
    ) -> MCPToolResult:
        from .dataset_orchestrator import run_dataset_intelligence
        dataset_id = params.get("dataset_id") or (resp.manifest.dataset_id if resp and resp.manifest else 1)
        ds_resp = run_dataset_intelligence(dataset_id=dataset_id)
        return MCPToolResult(
            tool_name="discover_dataset_metrics",
            status="success",
            caller_role=role,
            data={"dataset_id": dataset_id, "sheet_count": ds_resp.sheet_count, "relationship_count": ds_resp.relationship_count},
        )

    @classmethod
    def _tool_query_dataset_insights(
        cls, params: dict[str, Any], role: AgentRole, resp: AdaptiveDashboardResponse | None
    ) -> MCPToolResult:
        from .dataset_orchestrator import run_dataset_intelligence
        dataset_id = params.get("dataset_id") or (resp.manifest.dataset_id if resp and resp.manifest else 1)
        ds_resp = run_dataset_intelligence(dataset_id=dataset_id)
        return MCPToolResult(
            tool_name="query_dataset_insights",
            status="success",
            caller_role=role,
            data={
                "dataset_id": dataset_id,
                "dataset_name": ds_resp.dataset_name,
                "selected_dashboard_insights": ds_resp.selected_dashboard_insights,
                "coverage_warnings": ds_resp.coverage_warnings,
            },
        )

    @classmethod
    def _tool_get_dataset_relationships(
        cls, params: dict[str, Any], role: AgentRole, resp: AdaptiveDashboardResponse | None
    ) -> MCPToolResult:
        from .dataset_orchestrator import run_dataset_intelligence
        dataset_id = params.get("dataset_id") or (resp.manifest.dataset_id if resp and resp.manifest else 1)
        ds_resp = run_dataset_intelligence(dataset_id=dataset_id)
        return MCPToolResult(
            tool_name="get_dataset_relationships",
            status="success",
            caller_role=role,
            data={"dataset_id": dataset_id, "relationship_graph": ds_resp.relationship_graph.model_dump()},
        )

    @classmethod
    def _tool_query_cross_sheet_insights(
        cls, params: dict[str, Any], role: AgentRole, resp: AdaptiveDashboardResponse | None
    ) -> MCPToolResult:
        from .dataset_orchestrator import run_dataset_intelligence
        dataset_id = params.get("dataset_id") or (resp.manifest.dataset_id if resp and resp.manifest else 1)
        ds_resp = run_dataset_intelligence(dataset_id=dataset_id)
        cross_insights = [
            i for i in (ds_resp.selected_dashboard_insights + ds_resp.suppressed_insights)
            if i.get("scope") == "CROSS_SHEET"
        ]
        return MCPToolResult(
            tool_name="query_cross_sheet_insights",
            status="success",
            caller_role=role,
            data={"dataset_id": dataset_id, "cross_sheet_insights": cross_insights},
        )
