"""Modular presentation generation service adhering to the PulseHR AI Data-Driven Presentation Standard."""

from .job_manager import PresentationJobManager, job_manager
from .scope_detector import (
    detect_sheet_date_range,
    get_connected_sheet_groups,
    get_validated_relationships_for_sheets,
    preview_presentation_scope,
    collect_workspace_evidence,
    capture_dataset_context
)
from .chart_synthesizer import (
    extract_presentation_charts,
    synthesize_presentation_charts
)
from .data_profiler import profile_presentation_dataset
from .storyline_generator import plan_dynamic_storyline
from .deck_generator import (
    THEMES,
    generate_presentation_deck_spec
)
from .claim_verifier import verify_presentation_claims
from .ai_enrichment import (
    _call_ai_presentation_enrichment,
    regenerate_single_slide
)
from .pipeline_orchestrator import (
    execute_presentation_pipeline_async,
    start_presentation_job
)

__all__ = [
    "THEMES",
    "PresentationJobManager",
    "job_manager",
    "detect_sheet_date_range",
    "get_connected_sheet_groups",
    "get_validated_relationships_for_sheets",
    "preview_presentation_scope",
    "collect_workspace_evidence",
    "capture_dataset_context",
    "extract_presentation_charts",
    "synthesize_presentation_charts",
    "profile_presentation_dataset",
    "plan_dynamic_storyline",
    "generate_presentation_deck_spec",
    "verify_presentation_claims",
    "_call_ai_presentation_enrichment",
    "regenerate_single_slide",
    "execute_presentation_pipeline_async",
    "start_presentation_job"
]
