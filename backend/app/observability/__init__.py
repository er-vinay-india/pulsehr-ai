"""AI Observability, Evaluation & Runtime Intelligence (Phase D).

Unifies:
- AITrace, NodeExecutionMetric, ClaimAttribution, RuntimeQualityScore
- WorkflowLatencyBudget, Latency SLA verification
- Intent, Tool, Grounding, Governance, Model, Outcome evaluators
- Benchmark corpus & runner
- AIObservabilityService facade
"""
from __future__ import annotations

from .benchmark import BENCHMARK_CORPUS, BenchmarkReport, BenchmarkRunner, BenchmarkTestCase
from .contracts import (
    AITrace,
    ClaimAttribution,
    ClaimType,
    ComputeCostMetric,
    GroundingEvaluation,
    IntentAlignmentEvaluation,
    NodeExecutionMetric,
    RuntimeAnomaly,
    RuntimeQualityScore,
    ToolSelectionQuality,
    WorkflowOutcomeEvaluation,
)
from .evaluators import (
    AgentIntentAlignmentEvaluator,
    EvidenceQualityEvaluator,
    GovernanceHealthEvaluator,
    GroundingEvaluator,
    ModelRoutingEvaluator,
    ToolSelectionQualityEvaluator,
    WorkflowOutcomeEvaluator,
)
from .latency_budget import ToolLatencySpec, WorkflowLatencyBudget, WorkflowLatencySpec
from .metrics import AnomalyDetector, MetricsAggregator, RuntimeHealthKPIs
from .service import AIObservabilityService, ai_observability_service
from .trace_context import TraceContext
from .trace_store import TraceStore, trace_store

__all__ = [
    "AITrace",
    "NodeExecutionMetric",
    "ClaimAttribution",
    "ClaimType",
    "ComputeCostMetric",
    "GroundingEvaluation",
    "GroundingEvaluator",
    "IntentAlignmentEvaluation",
    "AgentIntentAlignmentEvaluator",
    "ToolSelectionQuality",
    "ToolSelectionQualityEvaluator",
    "EvidenceQualityEvaluator",
    "ModelRoutingEvaluator",
    "GovernanceHealthEvaluator",
    "WorkflowOutcomeEvaluator",
    "WorkflowOutcomeEvaluation",
    "RuntimeQualityScore",
    "RuntimeAnomaly",
    "WorkflowLatencyBudget",
    "WorkflowLatencySpec",
    "ToolLatencySpec",
    "TraceContext",
    "TraceStore",
    "trace_store",
    "MetricsAggregator",
    "AnomalyDetector",
    "RuntimeHealthKPIs",
    "BENCHMARK_CORPUS",
    "BenchmarkTestCase",
    "BenchmarkRunner",
    "BenchmarkReport",
    "AIObservabilityService",
    "ai_observability_service",
]
