"""Central MCP Tool Registry for HighView AI (Phase B).

Maintains the authoritative catalog of governed MCP tools across all 6 capability groups:
1. Dataset MCP
2. Analytics MCP
3. Evidence MCP
4. Scenario MCP
5. Presentation MCP
6. Governance MCP
"""
from __future__ import annotations

import logging
from typing import Any, Callable
from .contracts import MCPToolDefinition

logger = logging.getLogger(__name__)


class MCPToolRegistry:
    """Singleton registry indexing all governed MCP tool definitions and their execution handlers."""

    def __init__(self):
        self._tools: dict[str, tuple[MCPToolDefinition, Callable]] = {}

    def register(self, definition: MCPToolDefinition, handler: Callable) -> None:
        """Registers an MCP tool with its Pydantic schemas, risk metadata, and execution handler."""
        if definition.tool_name in self._tools:
            logger.debug(f"Overwriting registration for MCP tool '{definition.tool_name}'")
        self._tools[definition.tool_name] = (definition, handler)

    def get_tool(self, tool_name: str) -> tuple[MCPToolDefinition, Callable] | None:
        """Retrieves tool definition and handler by name."""
        return self._tools.get(tool_name)

    def list_definitions(self, capability_group: str | None = None) -> list[MCPToolDefinition]:
        """Lists all registered tool definitions, optionally filtered by capability group."""
        definitions = [defn for defn, _ in self._tools.values()]
        if capability_group:
            definitions = [d for d in definitions if d.capability_group == capability_group]
        return definitions

    def get_openapi_schemas(self, capability_group: str | None = None) -> list[dict[str, Any]]:
        """Exports MCP/OpenAPI-compatible schema objects for agent discovery."""
        schemas = []
        for defn in self.list_definitions(capability_group):
            in_schema = defn.input_schema.model_json_schema()
            out_schema = defn.output_schema.model_json_schema()
            schemas.append({
                "name": defn.tool_name,
                "group": defn.capability_group,
                "description": defn.description,
                "risk_level": defn.risk_level.value,
                "input_schema": in_schema,
                "output_schema": out_schema,
                "requires_dataset_scope": defn.requires_dataset_scope,
                "requires_evidence": defn.requires_evidence,
                "requires_human_approval": defn.requires_human_approval,
            })
        return schemas

    def clear_for_test(self) -> None:
        """Resets the registry for test isolation."""
        self._tools.clear()


mcp_registry = MCPToolRegistry()
