"""ModelRoutingEvaluator: Evaluates model selection, fallback behavior, and compute cost (Phase D)."""
from __future__ import annotations

import logging
from typing import Any
from ..contracts import ComputeCostMetric, ModelRoutingEvaluation

logger = logging.getLogger(__name__)


class ModelRoutingEvaluator:
    """Evaluates ModelGateway routing decisions, fallback frequencies, and compute cost."""

    @classmethod
    def evaluate(
        cls,
        task_type: str,
        primary_model: str,
        actual_model: str,
        latency_ms: float,
        tokens_used: int = 0,
        structured_valid: bool = True,
    ) -> tuple[ModelRoutingEvaluation, ComputeCostMetric]:
        fallback_used = (primary_model.lower() != actual_model.lower())

        # Routing efficiency: 1.0 for primary successful, 0.8 for fallback, 0.5 for invalid structured
        score = 1.0
        if fallback_used:
            score -= 0.2
        if not structured_valid:
            score -= 0.3
        if latency_ms > 5000.0:
            score -= 0.2

        routing_score = max(0.0, min(1.0, round(score, 3)))

        routing_eval = ModelRoutingEvaluation(
            task_type=task_type,
            primary_model=primary_model,
            actual_model=actual_model,
            fallback_used=fallback_used,
            latency_ms=round(latency_ms, 2),
            token_count=tokens_used,
            structured_output_valid=structured_valid,
            routing_efficiency_score=routing_score,
        )

        # Estimate compute cost
        in_tokens = int(tokens_used * 0.6)
        out_tokens = int(tokens_used * 0.4)
        cpu_sec = round((latency_ms / 1000.0) * 0.75, 3)
        gpu_sec = round((latency_ms / 1000.0) * 0.25, 3)

        cost_metric = ComputeCostMetric(
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            latency_ms=round(latency_ms, 2),
            estimated_cpu_seconds=cpu_sec,
            estimated_gpu_seconds=gpu_sec,
        )

        return routing_eval, cost_metric
