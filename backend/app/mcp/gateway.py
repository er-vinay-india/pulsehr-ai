"""Central Governed MCP Gateway for HighView AI (Phase B).

The single entry point through which HRIDAY and future LangGraph agents invoke tools.

Enforces:
1. Tool existence and Pydantic schema validation.
2. DatasetIsolationIntegrity: blocks cross-dataset leakage and verifies active dataset scope.
3. Entitlement & Evidence requirements (e.g. presentation generation requires verified evidence).
4. Full execution ledger auditing (MCPExecutionRecord with SHA-256 arguments hash).
5. Error boundary: structured MCPToolResponse output for every call.
"""
from __future__ import annotations

import logging
import time
from uuid import uuid4
from typing import Any
from pydantic import ValidationError

from .contracts import (
    GovernanceStatus,
    MCPToolDefinition,
    MCPToolRequest,
    MCPToolResponse,
    compute_arguments_hash,
)
from .execution_ledger import mcp_execution_ledger
from .registry import mcp_registry

logger = logging.getLogger(__name__)


class GovernedMCPGateway:
    """Universal MCP execution gateway for Highview AI."""

    @classmethod
    def execute(
        cls,
        request: MCPToolRequest,
        context: Any = None,
    ) -> MCPToolResponse:
        """Executes a governed tool request with pre-flight governance and audit tracking."""
        start_time = time.perf_counter()
        exec_id = f"mcp-exec-{uuid4().hex[:12]}"
        args_hash = compute_arguments_hash(request.arguments)

        # 1. Look up tool in registry
        entry = mcp_registry.get_tool(request.tool_name)
        if not entry:
            err_msg = f"Tool '{request.tool_name}' is not registered in the HighView MCP catalog."
            mcp_execution_ledger.record_execution(
                execution_id=exec_id,
                tool_name=request.tool_name,
                caller=request.caller,
                arguments_hash=args_hash,
                duration_ms=0.0,
                success=False,
                dataset_id=request.dataset_id,
                workspace_id=request.workspace_id,
                governance_status=GovernanceStatus.DENIED,
                error_code="TOOL_NOT_FOUND",
            )
            return MCPToolResponse(
                success=False,
                tool_name=request.tool_name,
                execution_id=exec_id,
                dataset_id=request.dataset_id,
                governance_status=GovernanceStatus.DENIED,
                error_message=err_msg,
            )

        defn, handler = entry

        # 2. Dataset Isolation Pre-Flight (DatasetIsolationIntegrity)
        if defn.requires_dataset_scope:
            if request.dataset_id is None:
                err_msg = f"Tool '{request.tool_name}' requires an explicit dataset_id scope."
                mcp_execution_ledger.record_execution(
                    execution_id=exec_id,
                    tool_name=request.tool_name,
                    caller=request.caller,
                    arguments_hash=args_hash,
                    duration_ms=0.0,
                    success=False,
                    governance_status=GovernanceStatus.DENIED,
                    error_code="MISSING_DATASET_SCOPE",
                )
                return MCPToolResponse(
                    success=False,
                    tool_name=request.tool_name,
                    execution_id=exec_id,
                    governance_status=GovernanceStatus.DENIED,
                    error_message=err_msg,
                )

            # Check active dataset scope against context if provided
            active_dataset = getattr(context, "active_dataset_id", None)
            if active_dataset is not None and str(request.dataset_id) != str(active_dataset) and not defn.allows_cross_dataset:
                err_msg = (
                    f"Dataset isolation violation: requested dataset '{request.dataset_id}' "
                    f"is not authorized within active scope '{active_dataset}'."
                )
                mcp_execution_ledger.record_execution(
                    execution_id=exec_id,
                    tool_name=request.tool_name,
                    caller=request.caller,
                    arguments_hash=args_hash,
                    duration_ms=0.0,
                    success=False,
                    dataset_id=request.dataset_id,
                    governance_status=GovernanceStatus.DENIED,
                    error_code="DATASET_ISOLATION_VIOLATION",
                )
                return MCPToolResponse(
                    success=False,
                    tool_name=request.tool_name,
                    execution_id=exec_id,
                    dataset_id=request.dataset_id,
                    governance_status=GovernanceStatus.DENIED,
                    error_message=err_msg,
                )

        # 3. Grounded Evidence Pre-Flight
        if defn.requires_evidence:
            evid_ids = request.arguments.get("evidence_ids") or []
            if not evid_ids:
                err_msg = f"Tool '{request.tool_name}' requires verified evidence_ids. Unsubstantiated claims rejected."
                mcp_execution_ledger.record_execution(
                    execution_id=exec_id,
                    tool_name=request.tool_name,
                    caller=request.caller,
                    arguments_hash=args_hash,
                    duration_ms=0.0,
                    success=False,
                    dataset_id=request.dataset_id,
                    governance_status=GovernanceStatus.DENIED,
                    error_code="MISSING_EVIDENCE_GROUNDING",
                )
                return MCPToolResponse(
                    success=False,
                    tool_name=request.tool_name,
                    execution_id=exec_id,
                    dataset_id=request.dataset_id,
                    governance_status=GovernanceStatus.DENIED,
                    error_message=err_msg,
                )

        # 4. Input Schema Validation
        try:
            # Automatically populate dataset_id into arguments if missing
            call_args = dict(request.arguments)
            if defn.requires_dataset_scope and "dataset_id" not in call_args and request.dataset_id is not None:
                call_args["dataset_id"] = request.dataset_id

            validated_in = defn.input_schema.model_validate(call_args)
        except ValidationError as val_err:
            err_msg = f"Invalid arguments for tool '{request.tool_name}': {val_err}"
            mcp_execution_ledger.record_execution(
                execution_id=exec_id,
                tool_name=request.tool_name,
                caller=request.caller,
                arguments_hash=args_hash,
                duration_ms=0.0,
                success=False,
                dataset_id=request.dataset_id,
                governance_status=GovernanceStatus.DENIED,
                error_code="INVALID_ARGUMENTS",
            )
            return MCPToolResponse(
                success=False,
                tool_name=request.tool_name,
                execution_id=exec_id,
                dataset_id=request.dataset_id,
                governance_status=GovernanceStatus.DENIED,
                error_message=err_msg,
            )

        # 5. Handler Execution
        try:
            raw_output = handler(validated_in.model_dump(), context)
            output_dict = raw_output.model_dump() if hasattr(raw_output, "model_dump") else raw_output

            # Validate output against typed schema
            validated_out = defn.output_schema.model_validate(output_dict)
            final_dict = validated_out.model_dump()

            duration_ms = (time.perf_counter() - start_time) * 1000.0

            # Extract evidence and provenance IDs from result if present
            evidence_ids: list[str] = []
            if "evidence_id" in final_dict and final_dict["evidence_id"]:
                evidence_ids.append(str(final_dict["evidence_id"]))
            if "evidence_ids" in final_dict and isinstance(final_dict["evidence_ids"], list):
                evidence_ids.extend([str(e) for e in final_dict["evidence_ids"]])
            if "grounded_evidence_ids" in final_dict and isinstance(final_dict["grounded_evidence_ids"], list):
                evidence_ids.extend([str(e) for e in final_dict["grounded_evidence_ids"]])
            evidence_ids = list(dict.fromkeys(evidence_ids))

            provenance_ids: list[str] = []
            if "snapshot_id" in final_dict:
                provenance_ids.append(str(final_dict["snapshot_id"]))
            if "calculation_id" in final_dict and final_dict["calculation_id"]:
                provenance_ids.append(str(final_dict["calculation_id"]))

            # Record in execution ledger
            mcp_execution_ledger.record_execution(
                execution_id=exec_id,
                tool_name=request.tool_name,
                caller=request.caller,
                arguments_hash=args_hash,
                duration_ms=duration_ms,
                success=True,
                dataset_id=request.dataset_id,
                workspace_id=request.workspace_id,
                evidence_ids=evidence_ids,
                provenance_ids=provenance_ids,
                governance_status=GovernanceStatus.PASS,
            )

            return MCPToolResponse(
                success=True,
                tool_name=request.tool_name,
                result=final_dict,
                evidence_ids=evidence_ids,
                provenance_ids=provenance_ids,
                dataset_id=request.dataset_id,
                execution_id=exec_id,
                governance_status=GovernanceStatus.PASS,
            )

        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.exception("Error executing MCP tool '%s': %s", request.tool_name, exc)
            mcp_execution_ledger.record_execution(
                execution_id=exec_id,
                tool_name=request.tool_name,
                caller=request.caller,
                arguments_hash=args_hash,
                duration_ms=duration_ms,
                success=False,
                dataset_id=request.dataset_id,
                workspace_id=request.workspace_id,
                governance_status=GovernanceStatus.DENIED,
                error_code="EXECUTION_ERROR",
            )
            return MCPToolResponse(
                success=False,
                tool_name=request.tool_name,
                execution_id=exec_id,
                dataset_id=request.dataset_id,
                governance_status=GovernanceStatus.DENIED,
                error_message=str(exc),
            )


mcp_gateway = GovernedMCPGateway
