"""Presentation Pipeline Selector (PPT-L1 Dual-Path Foundation).

Provides deterministic routing between the battle-tested LEGACY presentation
pipeline and the new LAYERED presentation pipeline (PPT-L0 to PPT-L11).

Invariants:
1. LEGACY pipeline remains 100% operational and usable as fallback.
2. Dual-path routing is governed by centralized settings (PRESENTATION_LAYERED_PIPELINE_ENABLED)
   and can be selectively overridden per job/scope for canary validation.
3. Both modes satisfy identical endpoint and export contracts.
"""

from __future__ import annotations

from enum import Enum
import logging
from typing import Any

from ...core import config

logger = logging.getLogger(__name__)


class PresentationPipelineMode(str, Enum):
    """Execution modes for presentation generation."""
    LEGACY = "LEGACY"
    LAYERED = "LAYERED"


class PresentationPipelineSelector:
    """Selects between Legacy and Layered presentation generation pipelines."""

    @classmethod
    def select_pipeline(cls, scope: dict[str, Any] | None = None) -> PresentationPipelineMode:
        """Determines the presentation pipeline mode.
        
        Order of precedence:
        1. Explicit scope override: force_legacy_pipeline / force_legacy_builder -> LEGACY
        2. Explicit scope override: pipeline_mode ("layered" or "legacy")
        3. Explicit scope override: use_layered_pipeline (bool)
        4. Centralized config setting: PRESENTATION_LAYERED_PIPELINE_ENABLED
        """
        scope = scope or {}

        # 1. Force legacy override (safety valve)
        if bool(scope.get("force_legacy_pipeline") or scope.get("force_legacy_hr_builder")):
            return PresentationPipelineMode.LEGACY

        # 2. Scope-specified pipeline_mode
        mode_str = str(scope.get("pipeline_mode", "")).strip().upper()
        if mode_str in (PresentationPipelineMode.LAYERED.value, "LAYERED"):
            return PresentationPipelineMode.LAYERED
        if mode_str in (PresentationPipelineMode.LEGACY.value, "LEGACY"):
            return PresentationPipelineMode.LEGACY

        # 3. Scope-specified boolean flag (supports use_layered_pipeline and is_layered_pipeline)
        for flag_key in ("use_layered_pipeline", "is_layered_pipeline"):
            if flag_key in scope and scope[flag_key] is not None:
                if bool(scope[flag_key]):
                    return PresentationPipelineMode.LAYERED
                return PresentationPipelineMode.LEGACY

        # 4. Central configuration default
        if getattr(config, "PRESENTATION_LAYERED_PIPELINE_ENABLED", True):
            return PresentationPipelineMode.LAYERED

        return PresentationPipelineMode.LEGACY

    @classmethod
    def is_layered_mode(cls, scope: dict[str, Any] | None = None) -> bool:
        """Returns True if the layered pipeline is selected."""
        return cls.select_pipeline(scope) == PresentationPipelineMode.LAYERED
