"""Central Model Gateway providing role-based model dispatch, fallback cascades, and structured schema parsing.

Phase A Enhancements:
- HighView AI Task Taxonomy (STRUCTURAL_AI, SEMANTIC_AI, NARRATIVE_AI, AGENTIC_AI, PRESENTATION_AI, DETERMINISTIC_CALCULATION).
- Strongly-typed AIRequest & AIResponse execution envelope.
- Cryptographic input/output hashing for immutable audit trails (AIExecutionRecord).
- Integrated ModelHealthService & circuit breaking to skip degraded models.
- Graceful offline and deterministic calculation bypass.
"""
from __future__ import annotations

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
from .assistant_identity import guarded_completion
from .contracts import (
    AIExecutionRecord,
    AIRequest,
    AIResponse,
    AITaskType,
    ReasoningLevel,
    compute_hash,
)
from .model_health import model_health_service
from .model_router import ModelRouter
from .observability import ExecutionTrace, trace_registry

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class GatewayResult(Generic[T]):
    """Standardized result wrapper returned by ModelGateway.generate() (legacy interface)."""
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
        error: str | None = None,
        identity_guard_triggered: bool = False,
        identity_retry_count: int = 0
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
        self.runtime_model = model_used if success and raw_text else None
        self.assistant_identity = config.ASSISTANT_NAME
        self.identity_guard_triggered = identity_guard_triggered
        self.identity_retry_count = identity_retry_count

    def __repr__(self) -> str:
        return (
            f"<GatewayResult role={self.role.value} model={self.model_used} "
            f"success={self.success} duration={self.duration_ms:.1f}ms>"
        )


def clean_cot_reasoning(text: str) -> str:
    """Strips <think>...</think> chain-of-thought blocks emitted by DeepSeek-R1 reasoning models."""
    cleaned = re.sub(r'<think>[\s\S]*?(?:</think>|$)', '', text, flags=re.IGNORECASE)
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
        candidate = arr_match.group(0).strip()
        # Ensure it is a real JSON array and not an evidence citation tag like [FACT-014]
        if not re.match(r'^\[(?:FACT|F)-\d+(?:,\s*(?:FACT|F)-\d+)*\]$', candidate, re.IGNORECASE):
            try:
                json.loads(candidate)
                return candidate
            except Exception:
                pass

    return cleaned


class ModelGateway:
    """Central gateway routing all LLM requests through logical roles with fallback cascades."""

    # -------------------------------------------------------------------------
    # Phase A Typed Execution Entry Point: ModelGateway.execute(request)
    # -------------------------------------------------------------------------
    @classmethod
    def execute(cls, request: AIRequest) -> AIResponse[Any]:
        """Universal execution entrypoint for HighView AI requests.

        Enforces:
        1. DETERMINISTIC_CALCULATION bypass (0 tokens, no model call).
        2. Health-aware model routing and circuit breaking.
        3. Cascading fallbacks through available local models.
        4. Structured output validation against Pydantic schemas.
        5. Immutable cryptographic audit logging (AIExecutionRecord).
        6. Resilient offline degradation to deterministic fallback.
        """
        start_time = time.perf_counter()

        # 1. Deterministic Calculation Bypass
        if request.task_type == AITaskType.DETERMINISTIC_CALCULATION:
            inp_hash = compute_hash(request.model_dump())
            out_hash = compute_hash("deterministic_bypass")
            rec = AIExecutionRecord(
                request_id=request.request_id,
                task_type=request.task_type,
                model="deterministic_bypass",
                dataset_id=request.dataset_id,
                evidence_ids=request.evidence_ids,
                structured_input_hash=inp_hash,
                structured_output_hash=out_hash,
                latency_ms=0.0,
                fallback_used=False,
                models_attempted=[],
                entitlement_status="PASS",
                tokens_used=0,
                success=True,
            )
            parsed_val = request.deterministic_fallback
            raw_text = str(request.deterministic_fallback) if request.deterministic_fallback is not None else ""
            return AIResponse(
                raw_text=raw_text,
                parsed=parsed_val,
                execution_record=rec,
                success=True,
                deterministic_bypass=True,
            )

        # 2. Compute Input Hash
        inp_hash = compute_hash({
            "prompt": request.prompt or request.query,
            "system_prompt": request.system_prompt,
            "context": request.context,
            "schema": request.structured_output_schema.__name__ if request.structured_output_schema else None,
        })

        # 3. Resolve Model Candidate Cascade
        candidates = ModelRouter.route_ai_request(request)
        if not candidates:
            candidates = [getattr(config, "OLLAMA_MODEL", "qwen3.5:2b")]

        models_attempted: list[str] = []
        last_error: str | None = None
        prompt_content = request.prompt or request.query
        timeout_sec = min(request.max_latency_ms / 1000.0, 60.0)

        # 4. Iterate Candidates
        for idx, model_candidate in enumerate(candidates):
            models_attempted.append(model_candidate)
            model_start = time.perf_counter()

            try:
                messages = []
                if request.system_prompt:
                    messages.append({"role": "system", "content": request.system_prompt})
                messages.append({"role": "user", "content": prompt_content})

                temp = request.temperature_override if request.temperature_override is not None else 0.15

                payload: dict[str, Any] = {
                    "model": model_candidate,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": temp,
                        "num_predict": 4096 if request.reasoning_level == ReasoningLevel.HIGH else 2048,
                        "num_ctx": 8192
                    }
                }

                # Disable thinking mode unless DeepSeek-R1 or reasoning role
                if not any(k in model_candidate.lower() for k in ("deepseek-r1", "r1")):
                    payload["think"] = False

                if request.structured_output_schema is not None:
                    payload["format"] = "json"

                client_timeout = httpx.Timeout(timeout_sec, connect=4.0)
                with httpx.Client(timeout=client_timeout) as client:
                    resp = client.post(f"{config.OLLAMA_BASE_URL}/api/chat", json=payload)
                    resp.raise_for_status()
                    body = resp.json()

                msg_obj = body.get("message", {})
                raw_response = msg_obj.get("content", "") or body.get("response", "") or msg_obj.get("thinking", "")
                cleaned = clean_cot_reasoning(raw_response)

                if not cleaned:
                    raise ValueError(f"Model '{model_candidate}' returned an empty response.")

                # Parse structured JSON if requested
                parsed_instance = None
                if request.structured_output_schema is not None:
                    json_str = extract_json_payload(cleaned)
                    data_dict = json.loads(json_str)
                    parsed_instance = request.structured_output_schema.model_validate(data_dict)

                model_latency_ms = (time.perf_counter() - model_start) * 1000.0
                total_latency_ms = (time.perf_counter() - start_time) * 1000.0

                # Record success with ModelHealthService
                model_health_service.record_success(model_candidate, model_latency_ms)

                out_hash = compute_hash(json_str if request.structured_output_schema else cleaned)
                rec = AIExecutionRecord(
                    request_id=request.request_id,
                    task_type=request.task_type,
                    model=model_candidate,
                    dataset_id=request.dataset_id,
                    evidence_ids=request.evidence_ids,
                    structured_input_hash=inp_hash,
                    structured_output_hash=out_hash,
                    latency_ms=total_latency_ms,
                    fallback_used=(idx > 0),
                    models_attempted=models_attempted,
                    entitlement_status="PASS",
                    tokens_used=(len(prompt_content) + len(cleaned)) // 4,
                    success=True,
                )

                return AIResponse(
                    raw_text=cleaned,
                    parsed=parsed_instance,
                    execution_record=rec,
                    success=True,
                    fallback_triggered=(idx > 0),
                )

            except Exception as exc:
                model_latency_ms = (time.perf_counter() - model_start) * 1000.0
                last_error = str(exc)
                logger.warning(
                    f"ModelGateway candidate '{model_candidate}' failed ({model_latency_ms:.0f}ms): {exc}. "
                    f"Falling back to next candidate..."
                )
                model_health_service.record_failure(model_candidate, last_error)
                continue

        # 5. If all models fail: Graceful Offline Degradation
        total_latency_ms = (time.perf_counter() - start_time) * 1000.0
        out_hash = compute_hash(str(request.deterministic_fallback or "fallback_exhausted"))

        rec = AIExecutionRecord(
            request_id=request.request_id,
            task_type=request.task_type,
            model="deterministic_fallback" if request.deterministic_fallback is not None else "none",
            dataset_id=request.dataset_id,
            evidence_ids=request.evidence_ids,
            structured_input_hash=inp_hash,
            structured_output_hash=out_hash,
            latency_ms=total_latency_ms,
            fallback_used=True,
            models_attempted=models_attempted,
            entitlement_status="PASS",
            tokens_used=0,
            circuit_breaker_triggered=True,
            success=(request.deterministic_fallback is not None),
            error=last_error,
        )

        fallback_parsed = None
        if request.structured_output_schema is not None and isinstance(request.deterministic_fallback, request.structured_output_schema):
            fallback_parsed = request.deterministic_fallback

        fallback_text = str(request.deterministic_fallback) if request.deterministic_fallback is not None else (
            "Deterministic fallback: Core calculations verified from evidence graph. AI narrative unavailable."
        )

        return AIResponse(
            raw_text=fallback_text,
            parsed=fallback_parsed,
            execution_record=rec,
            success=(request.deterministic_fallback is not None),
            fallback_triggered=True,
            error=last_error,
        )

    # -------------------------------------------------------------------------
    # Legacy Interface: ModelGateway.generate(...)
    # Preserved for existing callers with 100% backward compatibility
    # -------------------------------------------------------------------------
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
        max_retries: int = 0,
        model_override: str | None = None,
        identity_query: str | None = None
    ) -> GatewayResult[T]:
        """Dispatches an inference request to the configured model for the given role with automatic fallback."""
        if isinstance(role, str):
            try:
                role = ModelRole(role.upper())
            except ValueError:
                role = ModelRole.ANALYST

        cfg = get_role_config(role)
        temp = temperature_override if temperature_override is not None else cfg.temperature

        models_to_try = []
        if model_override:
            models_to_try.append((model_override, False))
        models_to_try.extend([
            (cfg.primary, False),
            (cfg.fallback, True)
        ])
        # Append default system model if distinct from both primary and fallback
        if config.OLLAMA_MODEL not in (cfg.primary, cfg.fallback):
            models_to_try.append((config.OLLAMA_MODEL, True))

        last_error = None
        total_retries = 0
        identity_retries = 0
        identity_triggered = False

        for model_candidate, is_fallback in models_to_try:
            for attempt in range(max_retries + 1):
                trace_id = f"trace-{uuid4().hex[:10]}"
                start_time = time.perf_counter()
                try:
                    def invoke(identity_system):
                        messages = []
                        if identity_system:
                            messages.append({"role": "system", "content": identity_system})
                        messages.append({"role": "user", "content": prompt})

                        payload: dict[str, Any] = {
                            "model": model_candidate,
                            "messages": messages,
                            "stream": False,
                            "options": {
                                "temperature": temp,
                                "num_predict": cfg.max_tokens,
                                "num_ctx": 8192
                            }
                        }
                        # Disable Ollama internal thinking mode for non-REASONER roles
                        if role != ModelRole.REASONER and not any(k in model_candidate.lower() for k in ("deepseek-r1", "r1")):
                            payload["think"] = False

                        # Request structured json format when schema requested
                        if response_schema is not None:
                            payload["format"] = "json"

                        timeout = httpx.Timeout(cfg.timeout_seconds, connect=5.0)
                        with httpx.Client(timeout=timeout) as client:
                            resp = client.post(f"{config.OLLAMA_BASE_URL}/api/chat", json=payload)
                            resp.raise_for_status()
                            body = resp.json()

                        msg_obj = body.get("message", {})
                        raw_response = msg_obj.get("content", "") or body.get("response", "") or msg_obj.get("thinking", "")
                        cleaned = clean_cot_reasoning(raw_response)
                        return extract_json_payload(cleaned) if response_schema else cleaned

                    identity_result = guarded_completion(
                        invoke, query=identity_query if identity_query is not None else prompt, runtime_model=model_candidate,
                        task_system=system_prompt, structured=response_schema is not None,
                        max_retries=config.ASSISTANT_MAX_IDENTITY_RETRIES - identity_retries,
                        corrective=identity_triggered,
                    )
                    identity_retries += identity_result.identity_retry_count
                    identity_triggered |= identity_result.identity_guard_triggered
                    if identity_result.response_blocked:
                        raise ValueError('Assistant identity validation failed.')
                    cleaned_response = identity_result.text
                    if not cleaned_response:
                        raise ValueError('Model returned an empty response.')
                    raw_response = cleaned_response
                    duration_ms = (time.perf_counter() - start_time) * 1000

                    # Parse structured output if schema requested
                    parsed_instance = None
                    if response_schema is not None:
                        json_str = extract_json_payload(cleaned_response)
                        data_dict = json.loads(json_str)
                        parsed_instance = response_schema.model_validate(data_dict)

                    model_health_service.record_success(model_candidate, duration_ms)

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
                        finding_ids_referenced=finding_ids or [],
                        assistant_identity=config.ASSISTANT_NAME,
                        identity_guard_triggered=identity_triggered,
                        identity_retry_count=identity_retries
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
                        success=True,
                        identity_guard_triggered=identity_triggered,
                        identity_retry_count=identity_retries
                    )

                except Exception as exc:
                    total_retries += 1
                    last_error = str(exc)
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    logger.warning(
                        f"ModelGateway attempt {attempt + 1} failed for role '{role.value}' "
                        f"on model '{model_candidate}': {exc}"
                    )
                    model_health_service.record_failure(model_candidate, last_error)
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
            error=last_error,
            assistant_identity=config.ASSISTANT_NAME,
            identity_guard_triggered=identity_triggered,
            identity_retry_count=identity_retries
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
            error=last_error,
            identity_guard_triggered=identity_triggered,
            identity_retry_count=identity_retries
        )


HighviewModelGateway = ModelGateway
