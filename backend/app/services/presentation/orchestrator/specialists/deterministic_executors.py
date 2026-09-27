"""Deterministic Executors for presentation orchestration tasks.

Dispatches mathematical, retrieval, filtering, and formatting tasks
directly to the deterministic ToolRegistry, guaranteeing zero hallucination
and complete audit provenance.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from ..orchestrator_models import (
    ErrorCategory,
    ExecutionTask,
    ExecutorType,
    TaskResult,
    TaskStatus,
    TaskType,
)
from ..tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


def execute_deterministic_task(
    task: ExecutionTask,
    tool_registry: ToolRegistry,
    context: dict[str, Any]
) -> TaskResult:
    """Executes a deterministic execution task using registered tools with strict provenance tracking."""
    start_time = time.perf_counter()
    inputs = dict(task.inputs)
    tool_name = task.tool_name

    # Auto-resolve tool name if omitted based on task type
    if not tool_name:
        if task.task_type == TaskType.RETRIEVE_CONTEXT:
            tool_name = "retrieve_memory"
        elif task.task_type == TaskType.FETCH_EVIDENCE:
            tool_name = "fetch_evidence"
        elif task.task_type in (TaskType.CALCULATE_METRIC, TaskType.COMPARE_GROUPS):
            tool_name = "calculate_metric"
        elif task.task_type == TaskType.ANALYZE_DATA:
            tool_name = "aggregate_data"
        elif task.task_type == TaskType.DETECT_OUTLIER:
            tool_name = "detect_outliers"
        elif task.task_type == TaskType.DETECT_TREND:
            tool_name = "detect_trend"
        elif task.task_type == TaskType.PREPARE_CHART_DATA:
            tool_name = "prepare_chart_data"
        elif task.task_type == TaskType.PREPARE_TABLE_DATA:
            tool_name = "prepare_table_data"
        elif task.task_type == TaskType.VALIDATE_EVIDENCE_BINDING:
            tool_name = "verify_claim"
        else:
            tool_name = "calculate_metric"

    # Inject shared context (e.g. evidence ledger, retrieval context, dataset records) if not present
    if "evidence_ledger" not in inputs and "evidence_ledger" in context:
        inputs["evidence_ledger"] = context["evidence_ledger"]
    if "retrieval_context" not in inputs and "retrieval_context" in context:
        inputs["retrieval_context"] = context["retrieval_context"]
    if "records" not in inputs and "records" in context:
        inputs["records"] = context["records"]

    exec_result = tool_registry.execute_tool(tool_name, **inputs)
    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

    if exec_result.status == "error":
        return TaskResult(
            task_id=task.task_id,
            slide_id=task.slide_id,
            status=TaskStatus.FAILED,
            error=exec_result.error or f"Tool '{tool_name}' failed.",
            error_category=ErrorCategory.TOOL_FAILURE,
            executor=task.executor,
            tool_used=tool_name,
            confidence=0.0,
            execution_time_ms=duration_ms
        )

    # Derive provenance from tool result and inputs
    source_ids = list(exec_result.source_ids)
    evidence_ids = list(exec_result.evidence_ids)
    memory_ids = list(exec_result.memory_ids)
    dataset_ids = []

    if "dataset_id" in inputs:
        dataset_ids.append(str(inputs["dataset_id"]))
    elif "dataset_id" in context:
        dataset_ids.append(str(context["dataset_id"]))

    # If evidence_ids was passed in task inputs and tool didn't strip it, ensure retained
    if "evidence_ids" in inputs and isinstance(inputs["evidence_ids"], list):
        for eid in inputs["evidence_ids"]:
            if str(eid) not in evidence_ids:
                evidence_ids.append(str(eid))

    return TaskResult(
        task_id=task.task_id,
        slide_id=task.slide_id,
        status=TaskStatus.SUCCESS,
        result=exec_result.data,
        source_ids=source_ids,
        evidence_ids=evidence_ids,
        dataset_ids=dataset_ids,
        memory_ids=memory_ids,
        calculation_method=exec_result.calculation_method or f"Deterministic tool '{tool_name}'",
        executor=task.executor,
        tool_used=tool_name,
        confidence=1.0,
        execution_time_ms=duration_ms
    )
