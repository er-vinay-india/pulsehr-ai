"""Dedicated Granite 4 Presentation Composition Intelligence Specialist Client.

Loads and queries the fine-tuned Granite 4 Micro Hybrid LoRA adapter on Apple Silicon Metal via MLX-LM.
Provides genuine adapter weight serving behind ModelGateway with clean fallback when
MLX is unavailable, times out, or emits invalid JSON.

Strict Isolation & Provenance Invariants:
- Dedicated to AITaskType.PRESENTATION_COMPOSITION.
- True adapter status: adapter_loaded = True ONLY when MLX LoRA weights (84 LoRA modules) are active.
- If adapter loading fails or is disabled, adapter_loaded = False.
- Semantic outputs are validated against the CompositionDecision contract.
"""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from ....core import config
from ...gateway.contracts import AIExecutionRecord, AIRequest, AIResponse, compute_hash
from .composition_models import CompositionDecision, CompositionDecisionSource

logger = logging.getLogger(__name__)

# Cached model & tokenizer instance for low-latency reuse
_LOADED_MODEL = None
_LOADED_TOKENIZER = None
_LOAD_FAILED = False
_INFERENCE_DISABLED = False
_DISABLE_REASON: str | None = None
_ADAPTER_VERSION = "v1"
_ADAPTER_NAME = "granite4_presentation_composition_lora_v1"
_CHECKPOINT_NAME = "0000020_adapters.safetensors"
_BASE_MODEL_NAME = "mlx-community/granite-4.0-h-micro-4bit"
_LORA_MODULES_COUNT = 0


CANONICAL_SYSTEM_PROMPT = """You are HighView's Slide Composition Intelligence Engine.
Your task is to make a high-level SEMANTIC COMPOSITION DECISION for the following logical presentation slide.

CRITICAL RULES:
1. Zero coordinates (x, y, width, height).
2. Zero typography measurements (pt, font size).
3. Zero colors (hex, rgb).
4. Zero DrawingML, SVG, or HTML markup.
5. Reference ONLY the valid content IDs listed below. Never hallucinate or invent new content IDs.

Valid Archetypes:
HERO_METRIC, KPI_GRID, VISUAL_HERO, VISUAL_WITH_INSIGHT, VISUAL_WITH_SUPPORTING_METRICS,
COMPARISON, RANKING, DISTRIBUTION, CORRELATION, SCENARIO, TABLE_DEEP_DIVE, OUTLIER_SUMMARY,
MULTI_INSIGHT, EXECUTIVE_SYNTHESIS, TITLE_COVER, CLOSING_SUMMARY

Return only a valid JSON object matching the CompositionDecision schema."""


def clean_cot(text: str) -> str:
    """Strips <think> tags if present."""
    return re.sub(r"<think>[\s\S]*?(?:</think>|$)", "", text, flags=re.IGNORECASE).strip()


def extract_json_payload(text: str) -> dict[str, Any] | None:
    """Extracts JSON object from text or markdown fences."""
    c = clean_cot(text)
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", c, re.IGNORECASE)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except Exception:
            pass
    m = re.search(r"(\{[\s\S]*\})", c)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    return None


def get_mlx_composition_model():
    """Lazily loads and caches the fine-tuned Granite 4 Micro Hybrid MLX model and adapter."""
    global _LOADED_MODEL, _LOADED_TOKENIZER, _LOAD_FAILED, _DISABLE_REASON, _LORA_MODULES_COUNT
    if _LOAD_FAILED:
        return None, None, False
    if _LOADED_MODEL is not None and _LOADED_TOKENIZER is not None:
        return _LOADED_MODEL, _LOADED_TOKENIZER, (_LORA_MODULES_COUNT > 0)

    try:
        from mlx_lm import load

        base_path = str(config.COMPOSITION_MODEL_BASE)
        adapter_path = str(config.COMPOSITION_MODEL_ADAPTER_PATH)

        target_file = Path(adapter_path) / "adapters.safetensors"
        if not target_file.exists():
            logger.warning("Granite 4 LoRA adapter file not found at %s", target_file)
            _LOAD_FAILED = True
            _DISABLE_REASON = f"Adapter safetensors not found at {target_file}"
            return None, None, False

        logger.info("Loading Granite 4 composition specialist adapter from %s", adapter_path)
        model, tokenizer = load(base_path, adapter_path=adapter_path)

        # Confirm adapter weights are genuinely loaded
        lora_count = 0
        for _, mod in model.named_modules():
            if hasattr(mod, "lora_a") or hasattr(mod, "lora_b"):
                lora_count += 1

        _LORA_MODULES_COUNT = lora_count
        if lora_count == 0:
            logger.warning("Granite 4 model loaded but 0 active LoRA modules detected!")
            _LOADED_MODEL = model
            _LOADED_TOKENIZER = tokenizer
            return model, tokenizer, False

        logger.info("Granite 4 composition specialist loaded successfully with %d LoRA modules.", lora_count)
        _LOADED_MODEL = model
        _LOADED_TOKENIZER = tokenizer
        return _LOADED_MODEL, _LOADED_TOKENIZER, True

    except Exception as e:
        logger.warning(
            "MLX-LM Granite 4 composition specialist could not be loaded: %s. Using fallback.", e
        )
        _LOAD_FAILED = True
        _DISABLE_REASON = f"MLX load failed: {str(e)}"
        return None, None, False


class GraniteCompositionSpecialist:
    """Specialist client for resolving presentation composition intent using fine-tuned Granite 4."""

    @classmethod
    def is_available(cls) -> bool:
        """Returns True if the MLX runtime and adapter are configured and ready."""
        if not config.COMPOSITION_MODEL_ENABLED:
            return False
        global _LOAD_FAILED, _INFERENCE_DISABLED
        if _LOAD_FAILED or _INFERENCE_DISABLED:
            return False
        return True

    @classmethod
    def execute_request(cls, request: AIRequest) -> AIResponse[Any]:
        """Executes a composition intelligence request using the local Granite 4 MLX specialist.
        
        Enforces strict schema validation, provenance tracking, and error handling.
        """
        start_time = time.perf_counter()
        inp_hash = compute_hash({
            "prompt": request.prompt or request.query,
            "system_prompt": request.system_prompt,
            "schema": "CompositionDecision",
        })

        # 1. Feature disabled check
        if not config.COMPOSITION_MODEL_ENABLED:
            raise RuntimeError("COMPOSITION_MODEL_ENABLED is false; specialist bypassed.")

        global _INFERENCE_DISABLED, _DISABLE_REASON, _LOAD_FAILED
        if _LOAD_FAILED or _INFERENCE_DISABLED:
            raise RuntimeError(f"Granite composition specialist offline: {_DISABLE_REASON or 'load failure'}")

        # 2. Acquire model and verify adapter loading
        model, tokenizer, is_adapter_loaded = get_mlx_composition_model()
        if model is None or tokenizer is None or not is_adapter_loaded:
            raise RuntimeError(f"Granite 4 adapter weights not loaded: {_DISABLE_REASON or 'No active LoRA'}")

        # 3. Format prompt using chat template matching training distribution
        sys_prompt = request.system_prompt
        if not sys_prompt or "CRITICAL RULES" not in sys_prompt:
            sys_prompt = CANONICAL_SYSTEM_PROMPT

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": request.prompt or request.query or ""},
        ]

        try:
            prompt_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        except Exception:
            prompt_text = f"{sys_prompt}\n\n{request.prompt or request.query}"

        # 4. Generate with MLX Metal
        t0 = time.perf_counter()
        from mlx_lm import generate

        timeout_sec = min(request.max_latency_ms / 1000.0, float(config.COMPOSITION_MODEL_TIMEOUT))

        resp_text = generate(
            model,
            tokenizer,
            prompt=prompt_text,
            max_tokens=1024,
            verbose=False,
        )
        gen_duration_ms = (time.perf_counter() - t0) * 1000.0
        total_latency_ms = (time.perf_counter() - start_time) * 1000.0

        if (gen_duration_ms / 1000.0) > timeout_sec:
            logger.warning("Granite composition specialist exceeded latency budget (%.1fms > %.1fms)", gen_duration_ms, timeout_sec * 1000.0)
            raise TimeoutError(f"Granite composition timeout ({gen_duration_ms:.1f}ms > {timeout_sec * 1000.0}ms)")

        # 5. Extract JSON
        parsed_dict = extract_json_payload(resp_text)
        if not parsed_dict or not isinstance(parsed_dict, dict):
            raise ValueError(f"Granite composition specialist emitted non-JSON output: {resp_text[:200]}")

        # 6. Validate CompositionDecision schema
        decision = CompositionDecision.model_validate(parsed_dict)
        decision.decision_source = CompositionDecisionSource.AI_MODEL

        # 7. Record accurate provenance in metadata
        decision.metadata["model_family"] = "GRANITE"
        decision.metadata["base_model"] = _BASE_MODEL_NAME
        decision.metadata["adapter_name"] = _ADAPTER_NAME
        decision.metadata["adapter_version"] = _ADAPTER_VERSION
        decision.metadata["checkpoint"] = _CHECKPOINT_NAME
        decision.metadata["adapter_loaded"] = True
        decision.metadata["lora_modules_active"] = _LORA_MODULES_COUNT
        decision.metadata["runtime_framework"] = "mlx-lm-metal"
        decision.metadata["fallback_used"] = False
        decision.metadata["latency_ms"] = round(total_latency_ms, 2)

        out_hash = compute_hash(decision.model_dump())

        # 8. Build auditable execution record
        rec = AIExecutionRecord(
            request_id=request.request_id,
            task_type=request.task_type,
            model=f"{_BASE_MODEL_NAME}+{_ADAPTER_NAME}:{_CHECKPOINT_NAME}",
            dataset_id=request.dataset_id,
            evidence_ids=request.evidence_ids,
            structured_input_hash=inp_hash,
            structured_output_hash=out_hash,
            latency_ms=total_latency_ms,
            fallback_used=False,
            models_attempted=[f"{_BASE_MODEL_NAME}+{_ADAPTER_NAME}"],
            entitlement_status="PASS",
            tokens_used=len(resp_text.split()),
            success=True,
        )

        return AIResponse(
            raw_text=resp_text,
            parsed=decision,
            execution_record=rec,
            success=True,
            fallback_triggered=False,
        )
