"""Tests for ModelRole abstraction, ModelGateway dispatch, fallback cascades, and schema validation."""

import pytest
from unittest.mock import patch, MagicMock
from pydantic import BaseModel

from app.core.models_config import ModelRole, get_role_config, RoleModelConfig
from app.services.gateway.model_gateway import ModelGateway, clean_cot_reasoning, extract_json_payload


class SampleResponseSchema(BaseModel):
    headline: str
    score: float


def test_model_role_mappings():
    """Verifies that all 5 logical roles have primary and fallback models configured."""
    for role in [ModelRole.FAST, ModelRole.ANALYST, ModelRole.REASONER, ModelRole.WRITER, ModelRole.CRITIC]:
        cfg = get_role_config(role)
        assert isinstance(cfg, RoleModelConfig)
        assert cfg.primary
        assert cfg.fallback
        assert cfg.primary != cfg.fallback


def test_clean_cot_reasoning():
    """Verifies that <think>...</think> reasoning tags are stripped cleanly."""
    raw = "<think>Let me reason through the data carefully.</think>Here is the final answer."
    assert clean_cot_reasoning(raw) == "Here is the final answer."

    raw_multiline = """<think>
    Step 1: Check segment variance.
    Step 2: Compare with baseline.
    </think>
    {"headline": "Engineering leads", "score": 92.4}"""
    assert clean_cot_reasoning(raw_multiline) == '{"headline": "Engineering leads", "score": 92.4}'


def test_extract_json_payload():
    """Verifies extraction of JSON from markdown blocks, braces, or prose."""
    # From markdown fence
    fenced = '```json\n{"headline": "Sales surge", "score": 88.5}\n```'
    assert extract_json_payload(fenced) == '{"headline": "Sales surge", "score": 88.5}'

    # From reasoning model with think tags and fence
    mixed = '<think>Reasoning</think>Some intro\n```json\n{"headline": "Result", "score": 10.0}\n```'
    assert extract_json_payload(mixed) == '{"headline": "Result", "score": 10.0}'


def test_model_gateway_fallback_cascade():
    """Verifies that when the primary model fails, the gateway transparently invokes the fallback model."""
    mock_responses = [
        # Attempt 1 on primary: Connection error
        MagicMock(status_code=500),
        # Attempt 2 on primary retry: Connection error
        MagicMock(status_code=500),
        # Attempt 3 on primary retry: Connection error
        MagicMock(status_code=500),
        # Attempt 1 on fallback: Success!
        MagicMock(status_code=200, json=lambda: {"response": '{"headline": "Fallback success", "score": 99.0}'})
    ]

    with patch("httpx.Client.post") as mock_post:
        # First 3 calls fail with HTTPError, 4th succeeds
        import httpx
        mock_post.side_effect = [
            httpx.HTTPError("Primary model offline"),
            httpx.HTTPError("Primary model offline"),
            httpx.HTTPError("Primary model offline"),
            MagicMock(status_code=200, json=lambda: {"response": '{"headline": "Fallback success", "score": 99.0}'})
        ]

        result = ModelGateway.generate(
            role=ModelRole.ANALYST,
            prompt="Analyze the metrics",
            response_schema=SampleResponseSchema,
            max_retries=2
        )

        assert result.success is True
        assert result.fallback_triggered is True
        assert result.parsed is not None
        assert result.parsed.headline == "Fallback success"
        assert result.parsed.score == 99.0
