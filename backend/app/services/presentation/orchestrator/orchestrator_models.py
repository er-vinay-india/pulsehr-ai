from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class TaskType(str, Enum):
    """Controlled task types for presentation execution orchestration."""
    RETRIEVE_CONTEXT = "RETRIEVE_CONTEXT"
    FETCH_EVIDENCE = "FETCH_EVIDENCE"
    ANALYZE_DATA = "ANALYZE_DATA"
    CALCULATE_METRIC = "CALCULATE_METRIC"
    COMPARE_GROUPS = "COMPARE_GROUPS"
    DETECT_TREND = "DETECT_TREND"
    DETECT_OUTLIER = "DETECT_OUTLIER"
    VERIFY_ANALYSIS = "VERIFY_ANALYSIS"
    DEEP_REASONING = "DEEP_REASONING"
    SUMMARIZE_CONTENT = "SUMMARIZE_CONTENT"
    GENERATE_SLIDE_COPY = "GENERATE_SLIDE_COPY"
    SELECT_VISUAL_FAMILY = "SELECT_VISUAL_FAMILY"
    PREPARE_CHART_DATA = "PREPARE_CHART_DATA"
    PREPARE_TABLE_DATA = "PREPARE_TABLE_DATA"
    PREPARE_DIAGRAM_DATA = "PREPARE_DIAGRAM_DATA"
    RESOLVE_IMAGE_NEED = "RESOLVE_IMAGE_NEED"
    BUILD_SPEAKER_NOTES = "BUILD_SPEAKER_NOTES"
    VALIDATE_EVIDENCE_BINDING = "VALIDATE_EVIDENCE_BINDING"
    VALIDATE_TASK_RESULT = "VALIDATE_TASK_RESULT"


class ExecutorType(str, Enum):
    """Controlled executor identities for task dispatch."""
    DETERMINISTIC_ANALYTICS = "DETERMINISTIC_ANALYTICS"
    DETERMINISTIC_RETRIEVAL = "DETERMINISTIC_RETRIEVAL"
    DETERMINISTIC_FORMATTER = "DETERMINISTIC_FORMATTER"
    GRANITE = "GRANITE"
    PHI4_MINI = "PHI4_MINI"
    DEEPSEEK_R1 = "DEEPSEEK_R1"
    QWEN_DIRECTOR_ESCALATION = "QWEN_DIRECTOR_ESCALATION"
    EXISTING_CHART_SYNTHESIZER = "EXISTING_CHART_SYNTHESIZER"
    EXISTING_CLAIM_VERIFIER = "EXISTING_CLAIM_VERIFIER"


class TaskStatus(str, Enum):
    """Lifecycle states of an execution task."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"


class ErrorCategory(str, Enum):
    """Standardized error categories for orchestrator recovery and routing."""
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    TOOL_FAILURE = "TOOL_FAILURE"
    MODEL_FAILURE = "MODEL_FAILURE"
    SCHEMA_FAILURE = "SCHEMA_FAILURE"
    TIMEOUT = "TIMEOUT"
    UNSUPPORTED_TASK = "UNSUPPORTED_TASK"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"


class ExecutionIssue(BaseModel):
    """Execution anomaly, constraint violation, or task failure reported during orchestration."""
    issue_id: str
    task_id: str | None = None
    slide_id: str | None = None
    category: ErrorCategory
    message: str
    recoverable: bool = True
    escalation_target: ExecutorType | None = None
    raw_details: dict[str, Any] = Field(default_factory=dict)


class ExecutionTask(BaseModel):
    """Atomic unit of work in the presentation execution plan."""
    task_id: str
    slide_id: str | None = None
    sequence_number: int = 1
    task_type: TaskType
    objective: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    executor: ExecutorType
    tool_name: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    retry_count: int = 0
    max_retries: int = 2
    error: str | None = None
    error_category: ErrorCategory | None = None
    execution_time_ms: float = 0.0


class TaskResult(BaseModel):
    """Standardized output produced by a task executor with strict provenance retention."""
    task_id: str
    slide_id: str | None = None
    status: TaskStatus = TaskStatus.SUCCESS
    result: dict[str, Any] = Field(default_factory=dict)
    source_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    dataset_ids: list[str] = Field(default_factory=list)
    memory_ids: list[str] = Field(default_factory=list)
    calculation_method: str = ""
    executor: ExecutorType = ExecutorType.DETERMINISTIC_ANALYTICS
    model_used: str | None = None
    tool_used: str | None = None
    confidence: float = 1.0
    execution_time_ms: float = 0.0
    error: str | None = None
    error_category: ErrorCategory | None = None


class ExecutionPlan(BaseModel):
    """The canonical orchestration contract detailing the complete task DAG."""
    execution_id: str
    plan_spec_version: str = "2.0"
    orchestrator_model: str = "granite4:3b-h"
    tasks: list[ExecutionTask] = Field(default_factory=list)
    status: str = "INITIALIZED"  # INITIALIZED | EXECUTING | COMPLETED | FAILED | RECOVERED
    created_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SlideExecutionPackage(BaseModel):
    """Fully resolved content, analytical evidence, charts, and speaker notes for a slide."""
    slide_id: str
    sequence_number: int
    headline: str
    subtitle: str = ""
    resolved_content: dict[str, Any] = Field(default_factory=dict)
    resolved_metrics: list[dict[str, Any]] = Field(default_factory=list)
    resolved_evidence: list[dict[str, Any]] = Field(default_factory=list)
    visual_intent: dict[str, Any] = Field(default_factory=dict)
    chart_data: dict[str, Any] | None = None
    table_data: dict[str, Any] | None = None
    speaker_notes: str = ""
    execution_trace: list[dict[str, Any]] = Field(default_factory=list)
    verified: bool = False
    verification_summary: dict[str, Any] = Field(default_factory=dict)
    visual_spec: dict[str, Any] | None = None
