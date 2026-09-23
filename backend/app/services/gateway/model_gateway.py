"""Central Model Gateway providing role-based model dispatch, fallback cascades, and structured schema parsing."""

import json
import logging
import re
import time
from uuid import uuid4
from typing import Any, Generic, TypeVar
import httpx
from pydantic import BaseModel, ValidationError

from ...core import config
from ...core.models_config import ModelRole, get_role_config
from .observability import ExecutionTrace, trace_registry

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class GatewayResult(Generic[T]):
    """Standardized result wrapper returned by ModelGateway."""
    def __init__(
        self,
        raw_text: str,
        parsed: T | None = None,
        role: ModelRole = ModelRole.ANALYST,
        model_used: str = "",
        duration_ms: float = 0.0,
        fallback_triggered: bool = False,
        retry_count: int = 0,
        success: bool = True,
        error: str | None = None
    ):
        self.raw_text = raw_text
        self.parsed = parsed
        self.role = role
        self.model_used = model_used
        self.duration_ms = duration_ms
        self.fallback_triggered = fallback_triggered
        self.retry_count = retry_count
        self.success = success
        self.error = error

    def __repr__(self) -> str:
        return (
            f"<GatewayResult role={self.role.value} model={self.model_used} "
            f"success={self.success} duration={self.duration_ms:.1f}ms>"
        )


def clean_cot_reasoning(text: str) -> str:
    """Strips <think>...</think> chain-of-thought blocks emitted by DeepSeek-R1 reasoning models."""
    cleaned = re.sub(r'<think>[\s\S]*?</think>', '', text, flags=re.IGNORECASE)
    return cleaned.strip()


def extract_json_payload(text: str) -> str:
    """Extracts valid JSON substring from markdown fences or mixed raw prose."""
    cleaned = clean_cot_reasoning(text)
    # Check for markdown code fence ```json ... ```
    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', cleaned, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # Check for outermost JSON object { ... }
    obj_match = re.search(r'\{[\s\S]*\}', cleaned)
    if obj_match:
        return obj_match.group(0).strip()

    # Check for outermost JSON array [ ... ]
    arr_match = re.search(r'\[[\s\S]*\]', cleaned)
    if arr_match:
        return arr_match.group(0).strip()

    return cleaned


class ModelGateway:
    """Central gateway routing all LLM requests through logical roles with fallback cascades."""

    @classmethod
    def generate(
        cls,
        role: ModelRole | str,
        prompt: str,
        system_prompt: str | None = None,
        response_schema: type[T] | None = None,
        report_id: str = "untracked",
        step_name: str = "ai_generation",
        finding_ids: list[str] | None = None,
        temperature_override: float | None = None,
        max_retries: int = 0
    ) -> GatewayResult[T]:
        """Dispatches an inference request to the configured model for the given role with automatic fallback."""
        if isinstance(role, str):
            try:
                role = ModelRole(role.upper())
            except ValueError:
                role = ModelRole.ANALYST

        cfg = get_role_config(role)
        temp = temperature_override if temperature_override is not None else cfg.temperature

        models_to_try = [
            (cfg.primary, False),
            (cfg.fallback, True)
        ]
        # Append default system model if distinct from both primary and fallback
        if config.OLLAMA_MODEL not in (cfg.primary, cfg.fallback):
            models_to_try.append((config.OLLAMA_MODEL, True))

        last_error = None
        total_retries = 0

        for model_candidate, is_fallback in models_to_try:
            for attempt in range(max_retries + 1):
                trace_id = f"trace-{uuid4().hex[:10]}"
                start_time = time.perf_counter()
                try:
                    payload: dict[str, Any] = {
                        "model": model_candidate,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": temp,
                            "num_predict": cfg.max_tokens,
                            "num_ctx": 8192
                        }
                    }
                    if system_prompt:
                        payload["system"] = system_prompt
                    if response_schema is not None:
                        payload["format"] = "json"

                    timeout = httpx.Timeout(cfg.timeout_seconds, connect=5.0)
                    with httpx.Client(timeout=timeout) as client:
                        resp = client.post(f"{config.OLLAMA_BASE_URL}/api/generate", json=payload)
                        resp.raise_for_status()
                        body = resp.json()

                    raw_response = body.get("response", "")
                    cleaned_response = clean_cot_reasoning(raw_response)
                    duration_ms = (time.perf_counter() - start_time) * 1000

                    # Parse structured output if schema requested
                    parsed_instance = None
                    if response_schema is not None:
                        json_str = extract_json_payload(cleaned_response)
                        data_dict = json.loads(json_str)
                        parsed_instance = response_schema.model_validate(data_dict)

                    trace = ExecutionTrace(
                        trace_id=trace_id,
                        report_id=report_id,
                        workflow_step=step_name,
                        role=role.value,
                        model_requested=cfg.primary,
                        model_used=model_candidate,
                        duration_ms=duration_ms,
                        success=True,
                        fallback_triggered=is_fallback,
                        retry_count=total_retries,
                        prompt_tokens_approx=len(prompt) // 4,
                        completion_tokens_approx=len(raw_response) // 4,
                        finding_ids_referenced=finding_ids or []
                    )
                    trace_registry.record_trace(trace)

                    return GatewayResult(
                        raw_text=cleaned_response,
                        parsed=parsed_instance,
                        role=role,
                        model_used=model_candidate,
                        duration_ms=duration_ms,
                        fallback_triggered=is_fallback,
                        retry_count=total_retries,
                        success=True
                    )

                except Exception as exc:
                    total_retries += 1
                    last_error = str(exc)
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    logger.warning(
                        f"ModelGateway attempt {attempt + 1} failed for role '{role.value}' "
                        f"on model '{model_candidate}': {exc}"
                    )
                    time.sleep(0.3 * (attempt + 1))

        # If all candidates exhausted, record failure trace
        failed_trace = ExecutionTrace(
            trace_id=f"fail-{uuid4().hex[:10]}",
            report_id=report_id,
            workflow_step=step_name,
            role=role.value,
            model_requested=cfg.primary,
            model_used=cfg.primary,
            duration_ms=0.0,
            success=False,
            fallback_triggered=True,
            retry_count=total_retries,
            error=last_error
        )
        trace_registry.record_trace(failed_trace)

        return GatewayResult(
            raw_text="",
            parsed=None,
            role=role,
            model_used=cfg.primary,
            duration_ms=0.0,
            fallback_triggered=True,
            retry_count=total_retries,
            success=False,
            error=last_error
        )
