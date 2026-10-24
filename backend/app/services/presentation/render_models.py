"""HighView Presentation Studio — PPT-L6 Render Models.

Defines the core data contracts for PPT-L6 native editable rendering:
- RenderStatus
- ShapeType
- RenderedObjectRecord
- RenderedSlideRecord
- RenderManifest
- Fingerprint computation functions
"""

from __future__ import annotations

import enum
import hashlib
import json
import logging
from typing import Any, Optional
from pydantic import BaseModel, Field

from app.services.presentation.layer_zone_models import EditabilityPolicy
from app.services.presentation.layout_models import Box2D

logger = logging.getLogger(__name__)


class RenderStatus(str, enum.Enum):
    """Overall rendering outcome status."""
    SUCCESS = "SUCCESS"
    FALLBACK_APPLIED = "FALLBACK_APPLIED"
    FAILED = "FAILED"


class ShapeType(str, enum.Enum):
    """PowerPoint DrawingML shape type classification."""
    TEXT_BOX = "TEXT_BOX"
    TABLE = "TABLE"
    CHART = "CHART"
    PICTURE = "PICTURE"
    AUTO_SHAPE = "AUTO_SHAPE"
    GROUP = "GROUP"
    UNKNOWN = "UNKNOWN"


class RenderedObjectRecord(BaseModel):
    """Audit record for an individual rendered PowerPoint shape."""
    object_id: str
    object_name: str
    zone_id: str
    physical_slide_id: str
    shape_id: int
    shape_type: ShapeType
    is_native_editable: bool
    editability_policy: EditabilityPolicy
    fallback_applied: bool = False
    fallback_reason: Optional[str] = None
    applied_bounds: Box2D
    metadata: dict[str, Any] = Field(default_factory=dict)


class RenderedSlideRecord(BaseModel):
    """Audit record for a rendered physical slide."""
    physical_slide_id: str
    logical_slide_id: str
    slide_index: int
    objects: list[RenderedObjectRecord] = Field(default_factory=list)
    render_status: RenderStatus = RenderStatus.SUCCESS
    slide_fingerprint: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def slide_id(self) -> str:
        return self.physical_slide_id

    @property
    def render_fingerprint(self) -> str:
        return self.slide_fingerprint


class RenderManifest(BaseModel):
    """Immutable audit manifest of a compiled PowerPoint presentation."""
    manifest_id: str
    deck_id: str
    pptx_path: str
    slides: list[RenderedSlideRecord] = Field(default_factory=list)
    total_slides: int = 0
    total_objects_rendered: int = 0
    total_native_editable: int = 0
    total_fallbacks: int = 0
    semantic_render_fingerprint: str
    replan_required: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


def compute_rendered_slide_fingerprint(slide: RenderedSlideRecord) -> str:
    """Computes a deterministic fingerprint for a rendered slide record."""
    obj_payloads = []
    for obj in sorted(slide.objects, key=lambda o: (o.zone_id, o.object_id)):
        obj_payloads.append({
            "object_id": obj.object_id,
            "object_name": obj.object_name,
            "shape_type": obj.shape_type.value,
            "is_native_editable": obj.is_native_editable,
            "fallback_applied": obj.fallback_applied,
            "bounds": [
                round(obj.applied_bounds.left, 4),
                round(obj.applied_bounds.top, 4),
                round(obj.applied_bounds.width, 4),
                round(obj.applied_bounds.height, 4),
            ],
        })

    payload = {
        "physical_slide_id": slide.physical_slide_id,
        "logical_slide_id": slide.logical_slide_id,
        "slide_index": slide.slide_index,
        "objects": obj_payloads,
    }
    raw = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_render_manifest_fingerprint(
    manifest_id: str,
    deck_id: str,
    slides: list[RenderedSlideRecord],
) -> str:
    """Computes a deterministic whole-deck semantic render fingerprint."""
    slide_fps = [s.slide_fingerprint for s in slides]
    payload = f"{manifest_id}::{deck_id}::" + "::".join(slide_fps)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
