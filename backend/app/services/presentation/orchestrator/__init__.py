"""Presentation Execution Orchestrator Package (IBM Granite 4.0)."""

from .orchestrator_models import (
    ErrorCategory,
    ExecutionIssue,
    ExecutionPlan,
    ExecutionTask,
    ExecutorType,
    SlideExecutionPackage,
    TaskResult,
    TaskStatus,
    TaskType,
)
from .task_graph import ExecutionTaskGraph
from .tool_contracts import (
    AggregateDataArgs,
    CalculateMetricArgs,
    DetectOutliersArgs,
    DetectTrendArgs,
    FetchEvidenceArgs,
    PrepareChartDataArgs,
    PrepareTableDataArgs,
    RankCategoriesArgs,
    RetrieveMemoryArgs,
    ToolExecutionResult,
    VerifyClaimArgs,
)
from .tool_registry import ToolDefinition, ToolRegistry
from .specialists import (
    DeepSeekReasoner,
    PhiAnalyticalVerifier,
    execute_deterministic_task,
)
from .granite_orchestrator import (
    PresentationExecutionOrchestrator,
    presentation_orchestrator,
)

__all__ = [
    "ErrorCategory",
    "ExecutionIssue",
    "ExecutionPlan",
    "ExecutionTask",
    "ExecutorType",
    "SlideExecutionPackage",
    "TaskResult",
    "TaskStatus",
    "TaskType",
    "ExecutionTaskGraph",
    "ToolDefinition",
    "ToolRegistry",
    "ToolExecutionResult",
    "RetrieveMemoryArgs",
    "FetchEvidenceArgs",
    "CalculateMetricArgs",
    "AggregateDataArgs",
    "RankCategoriesArgs",
    "DetectOutliersArgs",
    "DetectTrendArgs",
    "PrepareChartDataArgs",
    "PrepareTableDataArgs",
    "VerifyClaimArgs",
    "DeepSeekReasoner",
    "PhiAnalyticalVerifier",
    "execute_deterministic_task",
    "PresentationExecutionOrchestrator",
    "presentation_orchestrator",
]
