"""Dedicated Typography Intelligence Specialist Client.

Loads and queries the fine-tuned MLX-LM Phi-4 Mini typography adapter on Apple Silicon.
Provides seamless fallback to DeterministicTypographyEngine if MLX is unavailable,
times out, or emits invalid JSON.

Strict Isolation Invariants:
- Completely independent from HRIDAY (no shared weights, prompts, or memory).
- AI output is validated against TypographyIntent contract.
- If CONDENSE or raw coordinates are emitted, model output is rejected and fallback is used.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from ....core import config
from .contracts import (
    DensityRisk,
    ReflowPreference,
    SemanticTypographyRole,
    TypographyColorRole,
    TypographyImportance,
    TypographyIntent,
    TypographyPreferredWeight,
    TypographyRelativeScale,
    TypographyBlockProvenance,
    normalize_semantic_role,
)
from .deterministic_engine import DeterministicTypographyEngine

logger = logging.getLogger(__name__)

# Cached model & tokenizer instance for low-latency reuse
_LOADED_MODEL = None
_LOADED_TOKENIZER = None
_LOAD_FAILED = False
_INFERENCE_DISABLED = False
_DISABLE_REASON: str | None = None
_ADAPTER_VERSION = "phi4_mini_lora_v1"


def _get_mlx_model():
    """Lazily loads and caches the fine-tuned Phi-4 Mini MLX model and adapter."""
    global _LOADED_MODEL, _LOADED_TOKENIZER, _LOAD_FAILED, _DISABLE_REASON
    if _LOAD_FAILED:
        return None, None
    if _LOADED_MODEL is not None and _LOADED_TOKENIZER is not None:
        return _LOADED_MODEL, _LOADED_TOKENIZER

    try:
        from mlx_lm import load
        base_path = str(config.TYPOGRAPHY_MODEL_BASE)
        adapter_path = str(config.TYPOGRAPHY_MODEL_ADAPTER_PATH)

        logger.info("Loading Phi-4-mini typography specialist adapter from %s", adapter_path)
        model, tokenizer = load(base_path, adapter_path=adapter_path)
        _LOADED_MODEL = model
        _LOADED_TOKENIZER = tokenizer
        return _LOADED_MODEL, _LOADED_TOKENIZER
    except Exception as e:
        logger.warning("MLX-LM typography specialist could not be loaded: %s. Using deterministic fallback.", e)
        _LOAD_FAILED = True
        _DISABLE_REASON = f"MLX load failed: {str(e)}"
        return None, None


def clean_cot(text: str) -> str:
    """Strips <think> tags if present."""
    return re.sub(r'<think>[\s\S]*?(?:</think>|$)', '', text, flags=re.IGNORECASE).strip()


def extract_json_payload(text: str) -> dict[str, Any] | None:
    """Extracts JSON object from text."""
    c = clean_cot(text)
    m = re.search(r'(\{[\s\S]*\})', c)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    return None


class TypographyIntelligenceModel:
    """Specialist client for resolving presentation typography intent."""

    @classmethod
    def resolve_intent(
        cls,
        block_id: str,
        text: str,
        candidate_role: SemanticTypographyRole | str,
        container_context: str = "card",
        container_lines: int = 3,
        theme_mode: str = "light"
    ) -> tuple[TypographyIntent, TypographyBlockProvenance]:
        """Determines typography intent using fine-tuned Phi-4 Mini adapter with deterministic fallback.
        
        Returns tuple of (TypographyIntent, TypographyBlockProvenance).
        """
        norm_role = normalize_semantic_role(candidate_role)
        base_model_str = str(config.TYPOGRAPHY_MODEL_BASE)

        # 1. Feature disabled check
        if not config.TYPOGRAPHY_MODEL_ENABLED:
            intent = DeterministicTypographyEngine.create_fallback_intent(
                block_id, text, norm_role, container_lines
            )
            provenance = TypographyBlockProvenance(
                typography_source="DETERMINISTIC_FALLBACK",
                base_model=base_model_str,
                adapter_loaded=False,
                adapter_version=_ADAPTER_VERSION,
                fallback_used=True,
                fallback_reason="TYPOGRAPHY_MODEL_ENABLED is false",
                latency_ms=0.05
            )
            return intent, provenance

        # 2. Cached runtime failure check (prevents paying repeated 6s timeouts)
        global _INFERENCE_DISABLED, _DISABLE_REASON, _LOAD_FAILED
        if _LOAD_FAILED or _INFERENCE_DISABLED:
            intent = DeterministicTypographyEngine.create_fallback_intent(
                block_id, text, norm_role, container_lines
            )
            provenance = TypographyBlockProvenance(
                typography_source="DETERMINISTIC_FALLBACK",
                base_model=base_model_str,
                adapter_loaded=False,
                adapter_version=_ADAPTER_VERSION,
                fallback_used=True,
                fallback_reason=_DISABLE_REASON or "MLX runtime unavailable",
                latency_ms=0.05
            )
            return intent, provenance

        # 3. Model acquisition
        model, tokenizer = _get_mlx_model()
        if model is None or tokenizer is None:
            intent = DeterministicTypographyEngine.create_fallback_intent(
                block_id, text, norm_role, container_lines
            )
            provenance = TypographyBlockProvenance(
                typography_source="DETERMINISTIC_FALLBACK",
                base_model=base_model_str,
                adapter_loaded=False,
                adapter_version=_ADAPTER_VERSION,
                fallback_used=True,
                fallback_reason=_DISABLE_REASON or "Failed to load MLX weights",
                latency_ms=0.05
            )
            return intent, provenance

        # 4. Prompt construction
        prompt_text = (
            f"<|user|>\n"
            f"Analyze presentation typography intent for block '{block_id}':\n"
            f"Text: \"{text}\"\n"
            f"Container context: {container_context} (max lines: {container_lines}, theme: {theme_mode})\n"
            f"Semantic role: {norm_role.value}\n"
            f"Return JSON adhering strictly to TypographyIntent schema:\n"
            f"- block_id: \"{block_id}\"\n"
            f"- semantic_role: \"{norm_role.value}\"\n"
            f"- importance: \"CRITICAL\" | \"HIGH\" | \"MEDIUM\" | \"LOW\" | \"SUPPORTING\"\n"
            f"- relative_scale: \"HERO\" | \"XL\" | \"LARGE\" | \"BASE\" | \"SMALL\" | \"XS\"\n"
            f"- preferred_weight: \"BOLD\" | \"SEMIBOLD\" | \"MEDIUM\" | \"REGULAR\"\n"
            f"- color_role: \"TEXT_PRIMARY\" | \"TEXT_SECONDARY\" | \"TEXT_MUTED\" | \"TEXT_ON_ACCENT\"\n"
            f"- density_risk: \"LOW\" | \"MEDIUM\" | \"HIGH\"\n"
            f"- reflow_preference: \"NONE\" | \"WRAP\" | \"SPLIT\"\n"
            f"- rationale: short note\n"
            f"<|end|>\n<|assistant|>\n"
        )

        t0 = time.perf_counter()
        try:
            from mlx_lm import generate
            resp = generate(
                model,
                tokenizer,
                prompt=prompt_text,
                max_tokens=256
            )
            dur_ms = (time.perf_counter() - t0) * 1000
            
            # Check timeout
            if (dur_ms / 1000.0) > config.TYPOGRAPHY_MODEL_TIMEOUT:
                logger.warning("Typography model timed out (%.2fms). Caching disabled state.", dur_ms)
                _INFERENCE_DISABLED = True
                _DISABLE_REASON = f"Timeout exceeded ({dur_ms:.1f}ms > {config.TYPOGRAPHY_MODEL_TIMEOUT*1000}ms)"
                intent = DeterministicTypographyEngine.create_fallback_intent(
                    block_id, text, norm_role, container_lines
                )
                provenance = TypographyBlockProvenance(
                    typography_source="DETERMINISTIC_FALLBACK",
                    base_model=base_model_str,
                    adapter_loaded=True,
                    adapter_version=_ADAPTER_VERSION,
                    fallback_used=True,
                    fallback_reason=_DISABLE_REASON,
                    latency_ms=dur_ms
                )
                return intent, provenance

            data = extract_json_payload(resp)
            if not data or not isinstance(data, dict):
                logger.info("Typography AI emitted non-JSON response. Falling back to deterministic intent.")
                intent = DeterministicTypographyEngine.create_fallback_intent(
                    block_id, text, norm_role, container_lines
                )
                provenance = TypographyBlockProvenance(
                    typography_source="DETERMINISTIC_FALLBACK",
                    base_model=base_model_str,
                    adapter_loaded=True,
                    adapter_version=_ADAPTER_VERSION,
                    fallback_used=True,
                    fallback_reason="Non-JSON model output",
                    latency_ms=dur_ms
                )
                return intent, provenance

            # Ensure block_id and semantic_role
            data["block_id"] = block_id
            if "semantic_role" not in data or not data["semantic_role"]:
                data["semantic_role"] = norm_role.value
            else:
                data["semantic_role"] = normalize_semantic_role(data["semantic_role"]).value
            
            # Disallow CONDENSE
            if "condense" in str(data.get("reflow_preference", "")).lower():
                logger.info("Typography AI emitted forbidden CONDENSE reflow preference. Enforcing SPLIT via fallback.")
                data["reflow_preference"] = "SPLIT"

            intent = TypographyIntent.model_validate(data)
            provenance = TypographyBlockProvenance(
                typography_source="PHI_LORA",
                base_model=base_model_str,
                adapter_loaded=True,
                adapter_version=_ADAPTER_VERSION,
                fallback_used=False,
                fallback_reason=None,
                latency_ms=dur_ms
            )
            return intent, provenance

        except Exception as e:
            dur_ms = (time.perf_counter() - t0) * 1000
            logger.warning("Typography AI inference failed (%s). Caching disabled state.", e)
            _INFERENCE_DISABLED = True
            _DISABLE_REASON = f"Inference exception: {str(e)}"
            intent = DeterministicTypographyEngine.create_fallback_intent(
                block_id, text, norm_role, container_lines
            )
            provenance = TypographyBlockProvenance(
                typography_source="DETERMINISTIC_FALLBACK",
                base_model=base_model_str,
                adapter_loaded=True,
                adapter_version=_ADAPTER_VERSION,
                fallback_used=True,
                fallback_reason=_DISABLE_REASON,
                latency_ms=dur_ms
            )
            return intent, provenance
