"""Unit and integration tests for HighView Model Gateway (Phase A).

Verifies:
1. AI task taxonomy & contract validation (STRUCTURAL_AI, SEMANTIC_AI, etc.).
2. Deterministic calculation bypass (0 tokens, immediate return, no LLM invoked).
3. Task-specific candidate cascades and High reasoning escalation.
4. Real-time ModelHealthService and circuit breaker trip/recovery.
5. ModelGateway.execute() end-to-end execution with structured schema validation.
6. Multi-model fallback cascade on candidate failure.
7. Graceful offline degradation when local LLM server is unreachable.
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch
import pytest
from pydantic import BaseModel

from app.services.gateway.contracts import (
    AIExecutionRecord,
    AIRequest,
    AIResponse,
    AITaskType,
    ModelHealthState,
    ReasoningLevel,
    compute_hash,
)
from app.services.gateway.model_gateway import ModelGateway
from app.services.gateway.model_health import ModelHealthService, model_health_service
from app.services.gateway.model_router import ModelRouter, TASK_MODEL_CASCADES


class DepartmentMetricSummary(BaseModel):
    department: str
    attendance_rate: float
    status: str


@pytest.fixture(autouse=True)
def reset_health():
    """Resets model health state before each test."""
    model_health_service.reset()
    yield
    model_health_service.reset()


def test_ai_task_taxonomy_and_contracts():
    """Verifies that all 6 governed task taxonomy members and reasoning levels exist."""
    assert AITaskType.STRUCTURAL_AI.value == "STRUCTURAL_AI"
    assert AITaskType.SEMANTIC_AI.value == "SEMANTIC_AI"
    assert AITaskType.NARRATIVE_AI.value == "NARRATIVE_AI"
    assert AITaskType.AGENTIC_AI.value == "AGENTIC_AI"
    assert AITaskType.PRESENTATION_AI.value == "PRESENTATION_AI"
    assert AITaskType.DETERMINISTIC_CALCULATION.value == "DETERMINISTIC_CALCULATION"

    req = AIRequest(
        task_type=AITaskType.SEMANTIC_AI,
        dataset_id=123,
        query="What does SO2 measure?",
        reasoning_level=ReasoningLevel.STANDARD,
    )
    assert req.dataset_id == 123
    assert req.task_type == AITaskType.SEMANTIC_AI
    assert len(req.request_id) > 0


def test_deterministic_calculation_bypass():
    """Verifies that DETERMINISTIC_CALCULATION bypasses LLMs entirely with 0 tokens and no HTTP call."""
    deterministic_data = {"calculated_mean": 84.5, "delta": "+4.2%"}

    req = AIRequest(
        task_type=AITaskType.DETERMINISTIC_CALCULATION,
        dataset_id="workforce_01",
        query="Calculate mean attendance",
        deterministic_fallback=deterministic_data,
    )

    with patch("httpx.Client.post") as mock_post:
        resp = ModelGateway.execute(req)

        # No network call may be made
        mock_post.assert_not_called()

        assert resp.deterministic_bypass is True
        assert resp.success is True
        assert resp.execution_record.model == "deterministic_bypass"
        assert resp.execution_record.tokens_used == 0
        assert resp.parsed == deterministic_data


def test_model_router_cascades_by_task_type():
    """Verifies that each AITaskType resolves to its designated model cascade."""
    # Structural AI -> Phi first
    req_struct = AIRequest(task_type=AITaskType.STRUCTURAL_AI)
    cascade_struct = ModelRouter.route_ai_request(req_struct)
    assert cascade_struct[0] == "phi4-mini:latest"

    # Semantic AI -> Qwen 2b first
    req_semantic = AIRequest(task_type=AITaskType.SEMANTIC_AI)
    cascade_semantic = ModelRouter.route_ai_request(req_semantic)
    assert cascade_semantic[0] == "qwen3.5:2b"

    # Narrative AI -> Gemma 12b or Qwen 9b first
    req_narrative = AIRequest(task_type=AITaskType.NARRATIVE_AI)
    cascade_narrative = ModelRouter.route_ai_request(req_narrative)
    assert cascade_narrative[0] in ("gemma4:12b", "qwen3.5:9b")

    # High reasoning level -> DeepSeek-R1 promoted to front
    req_high = AIRequest(
        task_type=AITaskType.SEMANTIC_AI,
        reasoning_level=ReasoningLevel.HIGH
    )
    cascade_high = ModelRouter.route_ai_request(req_high)
    assert "deepseek-r1:7b" in cascade_high[:2]


def test_model_health_and_circuit_breaker():
    """Verifies that repeated model failures trip circuit breaker and router deprioritizes degraded models."""
    health = model_health_service
    test_model = "qwen3.5:2b"

    assert health.is_healthy(test_model) is True

    # 1. Simulate 2 failures -> still healthy (< threshold 3)
    health.record_failure(test_model, "Timeout error 1")
    health.record_failure(test_model, "Timeout error 2")
    assert health.is_healthy(test_model) is True

    # 2. 3rd failure -> trips breaker to DEGRADED
    health.record_failure(test_model, "Timeout error 3")
    assert health.is_healthy(test_model) is False
    status = health._get_or_create(test_model)
    assert status.state == ModelHealthState.DEGRADED

    # 3. Router should place degraded model after healthy models in cascade
    req = AIRequest(task_type=AITaskType.SEMANTIC_AI)
    cascade = ModelRouter.route_ai_request(req)
    # Since qwen3.5:2b is degraded, phi4-mini:latest should take priority
    assert cascade.index("phi4-mini:latest") < cascade.index("qwen3.5:2b")

    # 4. Success restores healthy status
    health.record_success(test_model, latency_ms=120.0)
    assert health.is_healthy(test_model) is True
    assert status.state == ModelHealthState.HEALTHY


def test_gateway_execution_success_and_provenance():
    """Verifies that ModelGateway.execute() returns typed schema and generates valid cryptographic provenance."""
    sample_json = '{"department": "Engineering", "attendance_rate": 91.5, "status": "Compliant"}'

    req = AIRequest(
        task_type=AITaskType.SEMANTIC_AI,
        dataset_id=99767,
        prompt="Summarize Engineering attendance",
        structured_output_schema=DepartmentMetricSummary,
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "message": {"content": sample_json}
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        res: AIResponse[DepartmentMetricSummary] = ModelGateway.execute(req)

        assert res.success is True
        assert res.parsed is not None
        assert res.parsed.department == "Engineering"
        assert res.parsed.attendance_rate == 91.5

        # Check cryptographic audit trail
        rec = res.execution_record
        assert rec.request_id == req.request_id
        assert rec.task_type == AITaskType.SEMANTIC_AI
        assert len(rec.structured_input_hash) > 0
        assert len(rec.structured_output_hash) > 0
        assert rec.tokens_used is not None
        assert rec.fallback_used is False


def test_gateway_execution_fallback_cascade():
    """Verifies that when the primary model candidate fails, ModelGateway cascades to secondary candidate."""
    sample_json = '{"department": "Operations", "attendance_rate": 78.2, "status": "Warning"}'

    req = AIRequest(
        task_type=AITaskType.STRUCTURAL_AI,  # Primary: phi4-mini, Secondary: qwen3.5:2b
        dataset_id=99767,
        prompt="Reconstruct Operations row",
        structured_output_schema=DepartmentMetricSummary,
    )

    # First call (phi4-mini) raises Timeout, second call (qwen3.5:2b) succeeds
    mock_success = MagicMock(status_code=200)
    mock_success.json.return_value = {"message": {"content": sample_json}}

    call_count = 0
    def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Phi4-mini connection timeout (5000ms)")
        return mock_success

    with patch("httpx.Client.post", side_effect=mock_post):
        res: AIResponse[DepartmentMetricSummary] = ModelGateway.execute(req)

        assert res.success is True
        assert res.fallback_triggered is True
        assert res.execution_record.fallback_used is True
        assert len(res.execution_record.models_attempted) >= 2
        assert res.parsed.department == "Operations"


def test_gateway_graceful_offline_degradation():
    """Verifies that if all models are unavailable, gateway returns deterministic fallback cleanly."""
    fallback_obj = DepartmentMetricSummary(
        department="Deterministic HR",
        attendance_rate=80.0,
        status="Rule-Based"
    )

    req = AIRequest(
        task_type=AITaskType.NARRATIVE_AI,
        dataset_id=99767,
        prompt="Provide executive summary",
        structured_output_schema=DepartmentMetricSummary,
        deterministic_fallback=fallback_obj,
    )

    # Simulate complete Ollama daemon offline failure
    with patch("httpx.Client.post", side_effect=Exception("Connection refused to Ollama daemon on port 11434")):
        res: AIResponse[DepartmentMetricSummary] = ModelGateway.execute(req)

        assert res.success is True
        assert res.fallback_triggered is True
        assert res.parsed == fallback_obj
        assert "deterministic_fallback" in res.execution_record.model
        assert res.execution_record.circuit_breaker_triggered is True
