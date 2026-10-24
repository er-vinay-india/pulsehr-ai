"""HighView Presentation Studio — PPT-L10 Studio Models and Contracts.

Typed contracts for:
- StudioPresentationStatus (progressive progress reflecting real backend state)
- StudioSlideStatus (slide states from manifest lock to visual certification)
- TargetedRegenerationRequest (slide / zone / object level targeted regeneration)
- TargetedRegenerationResult (targeted regeneration response with stale protection)
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class StudioStage(str, Enum):
    UNDERSTANDING_DATA = "understanding_data"
    PLANNING_STORY = "planning_story"
    PREPARING_SLIDES = "preparing_slides"
    ARRANGING_CONTENT = "arranging_content"
    RENDERING_PRESENTATION = "rendering_presentation"
    CHECKING_SLIDE_QUALITY = "checking_slide_quality"
    FINALIZING_PRESENTATION = "finalizing_presentation"
    READY = "ready"
    FAILED = "failed"


STUDIO_STAGE_LABELS: dict[str, str] = {
    StudioStage.UNDERSTANDING_DATA.value: "Understanding your data",
    StudioStage.PLANNING_STORY.value: "Planning the story",
    StudioStage.PREPARING_SLIDES.value: "Preparing slides",
    StudioStage.ARRANGING_CONTENT.value: "Arranging content",
    StudioStage.RENDERING_PRESENTATION.value: "Rendering presentation",
    StudioStage.CHECKING_SLIDE_QUALITY.value: "Checking slide quality",
    StudioStage.FINALIZING_PRESENTATION.value: "Finalizing presentation",
    StudioStage.READY.value: "Ready",
    StudioStage.FAILED.value: "Generation failed",
}


class SlideThumbnailState(str, Enum):
    PREPARING = "PREPARING"
    RENDERING = "RENDERING"
    VALIDATING = "VALIDATING"
    VISUALLY_REVIEWING = "VISUALLY_REVIEWING"
    READY = "READY"
    REPAIRING = "REPAIRING"
    FAILED = "FAILED"


class StudioSlideStatus(BaseModel):
    """Reflects the exact lifecycle state of a physical slide after manifest lock."""
    physical_slide_id: str
    slide_order: int
    title: str
    layout: str
    status: SlideThumbnailState = SlideThumbnailState.PREPARING
    thumbnail_url: Optional[str] = None
    render_fingerprint: Optional[str] = None
    zones: list[str] = Field(default_factory=list)
    error: Optional[str] = None


class StudioPresentationStatus(BaseModel):
    """Typed studio progress contract reflecting real backend state without fake timers."""
    deck_id: Optional[str] = None
    job_id: str
    current_stage: str = StudioStage.UNDERSTANDING_DATA.value
    stage_label: str = "Understanding your data"
    progress_percent: int = 0
    message: str = "Understanding your data"
    manifest_locked: bool = False
    total_slides: int = 0
    rendered_slides: int = 0
    validated_slides: int = 0
    visually_certified_slides: int = 0
    failed_slides: int = 0
    recoverable: bool = True
    error: Optional[str] = None
    slides: list[StudioSlideStatus] = Field(default_factory=list)


class TargetedRegenerationRequest(BaseModel):
    """Targeted regeneration request for a physical slide, zone, or individual object."""
    deck_id: str
    physical_slide_id: str
    zone_id: Optional[str] = None
    object_id: Optional[str] = None
    regeneration_reason: str = "user_request"
    user_instruction: Optional[str] = None
    request_version: Optional[int] = None


class TargetedRegenerationResult(BaseModel):
    """Outcome of targeted regeneration preserving unaffected slide identities and render fingerprints."""
    success: bool
    deck_id: str
    physical_slide_id: str
    zone_id: Optional[str] = None
    object_id: Optional[str] = None
    deck_revision: int
    slide_status: StudioSlideStatus
    diff_summary: str
    unaffected_slide_count: int
    updated_deck: dict[str, Any]
