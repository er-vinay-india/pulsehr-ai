"""Highview Governed MCP Capability Layer (Phase B).

Provides:
- 6 Governed Capability Groups (Dataset, Analytics, Evidence, Scenario, Presentation, Governance).
- GovernedMCPGateway: Unified entry point for HRIDAY and future LangGraph agents.
- MCPToolRegistry: Authoritative tool catalog with typed Pydantic contracts and risk tiers.
- MCPExecutionLedger: Thread-safe cryptographic execution trace and provenance ledger.
"""
from __future__ import annotations

from .analytics_server import register_analytics_tools
from .contracts import (
    GovernanceStatus,
    MCPToolDefinition,
    MCPToolRequest,
    MCPToolResponse,
    ToolRiskLevel,
)
from .bypass_audit import MCPBypassAuditor, MCPBypassAuditResult
from .dataset_server import register_dataset_tools
from .evidence_server import register_evidence_tools
from .execution_ledger import MCPExecutionLedger, MCPExecutionRecord, mcp_execution_ledger
from .gateway import GovernedMCPGateway, mcp_gateway
from .governance_server import register_governance_tools
from .presentation_server import register_presentation_tools
from .registry import MCPToolRegistry, mcp_registry
from .scenario_server import register_scenario_tools


# Automatically register all 6 capability groups on package import
def _initialize_mcp_catalog() -> None:
    register_dataset_tools()
    register_analytics_tools()
    register_evidence_tools()
    register_scenario_tools()
    register_presentation_tools()
    register_governance_tools()


_initialize_mcp_catalog()

__all__ = [
    "GovernedMCPGateway",
    "mcp_gateway",
    "MCPToolRequest",
    "MCPToolResponse",
    "MCPToolDefinition",
    "ToolRiskLevel",
    "GovernanceStatus",
    "MCPToolRegistry",
    "mcp_registry",
    "MCPExecutionLedger",
    "MCPExecutionRecord",
    "mcp_execution_ledger",
    "MCPBypassAuditor",
    "MCPBypassAuditResult",
]
