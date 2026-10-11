"""Pydantic contracts and taxonomy for HighView Model Gateway (Phase A).

Defines:
- AITaskType taxonomy (STRUCTURAL_AI, SEMANTIC_AI, NARRATIVE_AI, AGENTIC_AI, PRESENTATION_AI, DETERMINISTIC_CALCULATION)
- ReasoningLevel (NONE, LOW, STANDARD, HIGH)
- ModelHealthState (HEALTHY, DEGRADED, UNAVAILABLE)
- AIRequest execution envelope
- AIExecutionRecord auditable cryptographic trace
- AIResponse typed outcome container
"""
from __future__ import annotations

import enum
import hashlib
import json
import time
from uuid import uuid4
from typing import Any, Generic, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T", bound=BaseModel)


class AITaskType(str, enum.Enum):
    """Governed AI task taxonomy. Every AI workload belongs to an approved class."""
    STRUCTURAL_AI = "STRUCTURAL_AI"              # Header reconstruction, continuation ambiguity, boundary checks
    SEMANTIC_AI = "SEMANTIC_AI"                  # Column domain meaning, metric grain classification
    NARRATIVE_AI = "NARRATIVE_AI"                # Executive summary, concise explanation, short findings
    AGENTIC_AI = "AGENTIC_AI"                    # Multi-step workflow planning, tool dispatch routing
    PRESENTATION_AI = "PRESENTATION_AI"          # Slide narrative, visual storytelling
    DETERMINISTIC_CALCULATION = "DETERMINISTIC_CALCULATION"  # NO MODEL - mathematical bypass


class ReasoningLevel(str, enum.Enum):
    """Desired computational reasoning depth."""
    NONE = "NONE"          # Deterministic lookup or simple fast mapping
    LOW = "LOW"            # Lightweight classification or short naming
    STANDARD = "STANDARD"  # Synthesis, aggregation summary, standard analysis
    HIGH = "HIGH"          # Deep anomaly explanation, root cause analysis, trade-offs


class ModelHealthState(str, enum.Enum):
    """Operational health status of a local LLM."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"      # Repeated timeouts, in circuit-breaker cool-down
    UNAVAILABLE = "UNAVAILABLE"  # Model not found or host unreachable


def compute_hash(data: Any) -> str:
    """Computes deterministic SHA-256 hex digest for inputs and outputs."""
    if isinstance(data, (dict, list)):
        serialized = json.dumps(data, sort_keys=True, default=str)
    elif isinstance(data, BaseModel):
        serialized = data.model_dump_json()
    else:
        serialized = str(data)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


class AIRequest(BaseModel):
    """Universal execution envelope for all HighView AI inference workloads."""
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    request_id: str = Field(default_factory=lambda: f"req-{uuid4().hex[:12]}")
    task_type: AITaskType = AITaskType.SEMANTIC_AI
    dataset_id: int | str | None = None
    required_capability: str = ""
    max_latency_ms: float = 30000.0
    reasoning_level: ReasoningLevel = ReasoningLevel.STANDARD
    structured_output_schema: type[BaseModel] | None = None

    query: str = ""
    prompt: str = ""
    system_prompt: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    user_role: str = "analyst"

    temperature_override: float | None = None
    model_override: str | None = None
    deterministic_fallback: Any | None = None


class AIExecutionRecord(BaseModel):
    """Cryptographically auditable record of AI inference execution and provenance."""
    model_config = ConfigDict(extra="ignore")

    request_id: str
    task_type: AITaskType
    model: str
    model_version: str | None = None
    dataset_id: int | str | None = None
    evidence_ids: list[str] = Field(default_factory=list)

    structured_input_hash: str
    structured_output_hash: str

    latency_ms: float
    fallback_used: bool = False
    models_attempted: list[str] = Field(default_factory=list)
    entitlement_status: str = "PASS"
    tokens_used: int | None = None
    circuit_breaker_triggered: bool = False

    success: bool = True
    error: str | None = None


class AIResponse(Generic[T]):
    """Standardized result returned by HighviewModelGateway."""
    def __init__(
        self,
        raw_text: str,
        execution_record: AIExecutionRecord,
        parsed: T | None = None,
        success: bool = True,
        fallback_triggered: bool = False,
        deterministic_bypass: bool = False,
        error: str | None = None,
    ):
        self.raw_text = raw_text
        self.execution_record = execution_record
        self.parsed = parsed
        self.success = success
        self.fallback_triggered = fallback_triggered
        self.deterministic_bypass = deterministic_bypass
        self.error = error

    @property
    def model_used(self) -> str:
        return self.execution_record.model

    @property
    def latency_ms(self) -> float:
        return self.execution_record.latency_ms

    def __repr__(self) -> str:
        return (
            f"<AIResponse task={self.execution_record.task_type.value} "
            f"model={self.model_used} success={self.success} "
            f"latency={self.latency_ms:.1f}ms fallback={self.fallback_triggered}>"
        )
