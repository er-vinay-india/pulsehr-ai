"""Validation Result Contract and Failure Taxonomy for Real-World Hardening.

Defines:
- FailureTaxonomy (controlled failure classification)
- ValidationIssue (root-cause attributed defect)
- DeckScorecard (0-10 engineering diagnostic evaluation)
- ModelObservabilityReport (per-model call metrics & latencies)
- ThemeIntegrityCheckResult (mechanical theme preservation invariants)
- PresentationValidationResult (conforming to prompt Section 3 contract)
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class FailureTaxonomy(str, Enum):
    """Controlled taxonomy of presentation generation failures."""
    NARRATIVE_WEAKNESS = "NARRATIVE_WEAKNESS"
    MISSED_USER_QUESTION = "MISSED_USER_QUESTION"
    DUPLICATE_INSIGHT = "DUPLICATE_INSIGHT"
    WRONG_VISUAL = "WRONG_VISUAL"
    OVERLOADED_SLIDE = "OVERLOADED_SLIDE"
    UNDERUTILIZED_SLIDE = "UNDERUTILIZED_SLIDE"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    UNSUPPORTED_CLAIM = "UNSUPPORTED_CLAIM"
    POOR_APPENDIX_ROUTING = "POOR_APPENDIX_ROUTING"
    THEME_REGRESSION = "THEME_REGRESSION"
    PPTX_PARITY_ISSUE = "PPTX_PARITY_ISSUE"
    VISUAL_QA_REPAIR_FAILURE = "VISUAL_QA_REPAIR_FAILURE"
    PERFORMANCE_BOTTLENECK = "PERFORMANCE_BOTTLENECK"
    MODEL_ROUTING_ERROR = "MODEL_ROUTING_ERROR"
    TOOL_EXECUTION_ERROR = "TOOL_EXECUTION_ERROR"
    MEMORY_RETRIEVAL_NOISE = "MEMORY_RETRIEVAL_NOISE"


class ResponsibleLayer(str, Enum):
    """Architectural layer responsible for the root cause."""
    PHASE_1_MEMORY = "Phase 1: Memory & Retrieval"
    PHASE_2_DIRECTOR = "Phase 2: Presentation Director"
    PHASE_3_ORCHESTRATOR = "Phase 3: Execution Orchestrator"
    PHASE_4_VISUAL = "Phase 4: Visual Intelligence"
    PHASE_5_QA = "Phase 5: Visual QA & Repair"


class ValidationIssue(BaseModel):
    """Detailed validation issue attributed to a specific architectural layer and root cause."""
    issue_id: str
    category: FailureTaxonomy
    severity: str = "MEDIUM"  # LOW, MEDIUM, HIGH, CRITICAL
    slide_id: str | None = None
    slide_index: int | None = None
    layer: ResponsibleLayer
    message: str
    root_cause: str
    suggested_remediation: str


class DeckScorecard(BaseModel):
    """Quality scorecard for engineering diagnostics across 7 critical dimensions (0 to 10 scale)."""
    narrative: float = Field(default=10.0, ge=0.0, le=10.0)
    evidence: float = Field(default=10.0, ge=0.0, le=10.0)
    visual_selection: float = Field(default=10.0, ge=0.0, le=10.0)
    readability: float = Field(default=10.0, ge=0.0, le=10.0)
    theme_integrity: float = Field(default=10.0, ge=0.0, le=10.0)  # Must be 10.0
    pptx_fidelity: float = Field(default=10.0, ge=0.0, le=10.0)
    performance: float = Field(default=10.0, ge=0.0, le=10.0)
    overall: float = Field(default=10.0, ge=0.0, le=10.0)


class ModelObservabilityReport(BaseModel):
    """Detailed observability tracking invocation counts, latencies, retries and efficiencies per model."""
    qwen: dict[str, Any] = Field(default_factory=lambda: {
        "calls": 0,
        "planning_latency_ms": 0.0,
        "retry_count": 0,
        "schema_failures": 0,
        "mode": "deterministic_or_llm"
    })
    granite: dict[str, Any] = Field(default_factory=lambda: {
        "calls": 0,
        "task_count": 0,
        "routing_accuracy": 1.0,
        "retries": 0,
        "synthesis_latency_ms": 0.0
    })
    phi: dict[str, Any] = Field(default_factory=lambda: {
        "verification_calls": 0,
        "skipped_calls": 0,
        "discrepancies": 0,
        "latency_ms": 0.0
    })
    deepseek: dict[str, Any] = Field(default_factory=lambda: {
        "escalation_frequency": 0,
        "skipped_calls": 0,
        "actual_usefulness": 1.0,
        "latency_ms": 0.0
    })
    gemma: dict[str, Any] = Field(default_factory=lambda: {
        "qa_calls": 0,
        "skipped_title_calls": 0,
        "latency_ms": 0.0,
        "issue_count": 0,
        "repair_success_rate": 1.0
    })


class ThemeIntegrityCheckResult(BaseModel):
    """Rigorous mechanical validation of application theme preservation and scoped presentation styles."""
    passed: bool = True
    tokens_scss_valid: bool = True
    scoped_css_valid: bool = True
    theme_id_preserved: bool = True
    no_arbitrary_colors: bool = True
    webpage_theme_isolated: bool = True
    score: float = 1.0  # 1.0 or 0.0 (blocking)
    details: list[str] = Field(default_factory=list)


class PresentationValidationResult(BaseModel):
    """Canonical presentation validation contract for real-world scenarios."""
    scenario_id: str
    scenario_name: str
    domain: str
    status: str = "PASS"  # PASS, WARNING, FAIL
    generation_time_ms: float
    slide_count: int
    metrics: dict[str, float] = Field(default_factory=lambda: {
        "evidence_accuracy": 1.0,
        "claim_verification": 1.0,
        "visual_qa_score": 1.0,
        "narrative_coverage": 1.0,
        "question_coverage": 1.0,
        "theme_integrity": 1.0,
        "pptx_parity": 1.0
    })
    scorecard: DeckScorecard = Field(default_factory=DeckScorecard)
    model_observability: ModelObservabilityReport = Field(default_factory=ModelObservabilityReport)
    theme_check: ThemeIntegrityCheckResult = Field(default_factory=ThemeIntegrityCheckResult)
    stage_latencies_ms: dict[str, float] = Field(default_factory=dict)
    issues: list[ValidationIssue] = Field(default_factory=list)
    pptx_path: str | None = None
    html_preview_path: str | None = None
