"""Typography Resolver Service.

Coordinates AI intent determination and deterministic engineering resolution
for presentation content blocks across PPTX, HTML, and future PDF renderers.
Maintains an immutable TypographyManifest capturing execution provenance.
"""
from __future__ import annotations

import logging
from typing import Any

from .contracts import (
    ResolvedTypographySpec,
    SemanticTypographyRole,
    TypographyBlockProvenance,
    TypographyIntent,
    TypographyManifest,
    normalize_semantic_role,
)
from .deterministic_engine import DeterministicTypographyEngine
from .specialist import TypographyIntelligenceModel

logger = logging.getLogger(__name__)


class TypographyResolver:
    """Unified service for presentation typography resolution."""

    _manifest: TypographyManifest = TypographyManifest()

    @classmethod
    def reset_manifest(cls) -> None:
        """Resets the active presentation typography manifest for a new deck run."""
        cls._manifest = TypographyManifest()

    @classmethod
    def get_current_manifest(cls) -> TypographyManifest:
        """Returns the active typography manifest containing execution provenance."""
        return cls._manifest

    @classmethod
    def resolve_block_typography(
        cls,
        block_id: str,
        text: str,
        semantic_role: SemanticTypographyRole | str,
        theme_mode: str = "light",
        font_family: str = "Calibri",
        container_lines: int = 3,
        use_ai: bool = True,
        background_hex: str | None = None,
        is_on_image: bool = False,
    ) -> ResolvedTypographySpec:
        """Resolves typography for a single content block into concrete render values."""
        norm_role = normalize_semantic_role(semantic_role)

        if use_ai:
            intent, provenance = TypographyIntelligenceModel.resolve_intent(
                block_id=block_id,
                text=text,
                candidate_role=norm_role,
                container_lines=container_lines,
                theme_mode=theme_mode
            )
        else:
            intent = DeterministicTypographyEngine.create_fallback_intent(
                block_id=block_id,
                text=text,
                role=norm_role,
                container_lines=container_lines
            )
            provenance = TypographyBlockProvenance(
                typography_source="DETERMINISTIC_FALLBACK",
                base_model="mlx-community/Phi-4-mini-instruct-mlx-4Bit",
                adapter_loaded=False,
                adapter_version="none",
                fallback_used=True,
                fallback_reason="Explicit use_ai=False requested",
                latency_ms=0.05
            )

        spec = DeterministicTypographyEngine.resolve_spec(
            intent=intent,
            font_family=font_family,
            theme_mode=theme_mode,
            available_lines=container_lines,
            background_hex=background_hex,
            is_on_image=is_on_image,
            provenance=provenance
        )

        # Update manifest telemetry
        cls._manifest.total_blocks_resolved += 1
        cls._manifest.total_aaa_checks += 1
        if spec.aaa_pass:
            cls._manifest.total_aaa_passes += 1
        else:
            cls._manifest.total_aaa_failures += 1

        if spec.color_repaired:
            cls._manifest.total_color_repairs_applied += 1

        if spec.readability_pass:
            cls._manifest.total_readability_passes += 1
        else:
            cls._manifest.total_readability_failures += 1

        if provenance.fallback_used:
            cls._manifest.total_fallback_inferences += 1
            if cls._manifest.total_ai_inferences == 0:
                cls._manifest.typography_source = "DETERMINISTIC_FALLBACK"
                cls._manifest.fallback_used = True
                cls._manifest.fallback_reason = provenance.fallback_reason
        else:
            cls._manifest.total_ai_inferences += 1
            cls._manifest.typography_source = "PHI_LORA"
            cls._manifest.adapter_loaded = True

        # Running average latency
        prev_n = cls._manifest.total_blocks_resolved - 1
        cls._manifest.avg_latency_ms = (
            (cls._manifest.avg_latency_ms * prev_n + provenance.latency_ms)
            / cls._manifest.total_blocks_resolved
        )

        cls._manifest.blocks.append({
            "block_id": block_id,
            "semantic_role": norm_role.value,
            "text_preview": text[:60] + "..." if len(text) > 60 else text,
            "source": provenance.typography_source,
            "fallback_used": provenance.fallback_used,
            "font_size_pt": spec.font_size_pt,
            "font_weight": spec.font_weight,
            "color_hex": spec.color_hex,
            "foreground_hex": spec.foreground_hex,
            "background_hex": spec.background_hex,
            "contrast_ratio": spec.contrast_ratio,
            "aaa_threshold": spec.aaa_threshold,
            "aaa_pass": spec.aaa_pass,
            "color_repaired": spec.color_repaired,
            "readability_floor_pt": spec.readability_floor_pt,
            "readability_pass": spec.readability_pass,
            "backing_plate_hex": spec.backing_plate_hex,
            "reflow_action": spec.reflow_action.value,
            "latency_ms": round(provenance.latency_ms, 2),
            "intent": intent.model_dump()
        })

        return spec

    @classmethod
    def resolve_slide_blocks(
        cls,
        blocks: list[dict[str, Any]],
        theme_mode: str = "light",
        font_family: str = "Calibri",
        use_ai: bool = True
    ) -> dict[str, ResolvedTypographySpec]:
        """Batch-resolves typography for all textual blocks on a slide."""
        results: dict[str, ResolvedTypographySpec] = {}
        for block in blocks:
            b_id = block.get("block_id", "")
            text = block.get("text", "")
            role = block.get("role", SemanticTypographyRole.BODY)
            lines = block.get("max_lines", 3)
            bg_hex = block.get("background_hex")
            on_img = block.get("is_on_image", False)
            spec = cls.resolve_block_typography(
                block_id=b_id,
                text=text,
                semantic_role=role,
                theme_mode=theme_mode,
                font_family=font_family,
                container_lines=lines,
                use_ai=use_ai,
                background_hex=bg_hex,
                is_on_image=on_img
            )
            results[b_id] = spec
        return results
