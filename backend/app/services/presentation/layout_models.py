"""HighView Presentation Studio — PPT-L5 Constraint Layout & Fit Models.

Defines the typed data structures for resolved slide geometry, canonical coordinates,
safe-area geometry, zone bounds, object bounds, fit statuses, typography policies,
image fit modes, table column allocations, and deterministic layout fingerprints.

Architectural Invariants:
1. Canonical coordinates: Normalized [0.0, 1.0] relative to presentation space (16:9 standard).
2. PPT-L5 owns geometry, fit, collision avoidance, and spacing.
3. ZERO final brand colors, ZERO final theme palette, ZERO OOXML, ZERO PowerPoint shape IDs.
4. ZERO physical slide creation (SlideExpansionEngine remains sole owner).
5. SPLIT BEFORE SHRINK: Respect font size floors and request controlled late splits on overflow.
6. Identity preservation: object_id, object_name, zone_id, physical_slide_id are immutable.
7. AI layout calls = 0 (100% deterministic).
"""

from __future__ import annotations

import enum
import hashlib
import json
import logging
from typing import Any, Optional
from pydantic import BaseModel, Field

from .content_models import ContentKind
from .layer_zone_models import (
    CoordinateSpace,
    EditabilityPolicy,
    FrameInheritancePolicy,
    LayerRole,
    ZoneType,
)
from .story_models import ContentBindingRole

logger = logging.getLogger(__name__)


# ==============================================================================
# CANONICAL GEOMETRY: 2D BOX
# ==============================================================================

class Box2D(BaseModel):
    """Canonical 2D bounding box in normalized [0.0, 1.0] coordinates.
    
    All dimensions are normalized relative to logical canvas bounds:
    - left: 0.0 (left edge) -> 1.0 (right edge)
    - top: 0.0 (top edge) -> 1.0 (bottom edge)
    - width: 0.0 -> 1.0
    - height: 0.0 -> 1.0
    """
    left: float = Field(..., ge=-0.01, le=1.01, description="Left offset in [0.0, 1.0]")
    top: float = Field(..., ge=-0.01, le=1.01, description="Top offset in [0.0, 1.0]")
    width: float = Field(..., ge=0.0, le=1.01, description="Width in [0.0, 1.0]")
    height: float = Field(..., ge=0.0, le=1.01, description="Height in [0.0, 1.0]")

    @property
    def right(self) -> float:
        return self.left + self.width

    @property
    def bottom(self) -> float:
        return self.top + self.height

    @property
    def area(self) -> float:
        return max(0.0, self.width) * max(0.0, self.height)

    def contains(self, other: Box2D, tol: float = 1e-4) -> bool:
        """Returns True if self contains other within numerical tolerance."""
        return (
            self.left - tol <= other.left
            and self.top - tol <= other.top
            and self.right + tol >= other.right
            and self.bottom + tol >= other.bottom
        )

    def intersects(self, other: Box2D, tol: float = 1e-4) -> bool:
        """Returns True if self overlaps other by more than tolerance."""
        h_overlap = min(self.right, other.right) - max(self.left, other.left)
        v_overlap = min(self.bottom, other.bottom) - max(self.top, other.top)
        return h_overlap > tol and v_overlap > tol

    def intersection(self, other: Box2D, tol: float = 1e-4) -> Optional[Box2D]:
        """Calculates intersecting Box2D if overlapping."""
        if not self.intersects(other, tol=tol):
            return None
        i_left = max(self.left, other.left)
        i_top = max(self.top, other.top)
        i_right = min(self.right, other.right)
        i_bottom = min(self.bottom, other.bottom)
        return Box2D(
            left=round(i_left, 5),
            top=round(i_top, 5),
            width=round(i_right - i_left, 5),
            height=round(i_bottom - i_top, 5),
        )

    def to_rounded_dict(self, decimals: int = 4) -> dict[str, float]:
        """Returns coordinate dictionary rounded to fixed decimals for deterministic fingerprints."""
        return {
            "left": round(self.left, decimals),
            "top": round(self.top, decimals),
            "width": round(self.width, decimals),
            "height": round(self.height, decimals),
        }


# ==============================================================================
# ENUMS & STATUS CODES
# ==============================================================================

class LayoutStatus(str, enum.Enum):
    """Overall layout resolution state."""
    LAYOUT_RESOLVED = "LAYOUT_RESOLVED"
    LAYOUT_PRESSURED = "LAYOUT_PRESSURED"
    LAYOUT_REPAIR_APPLIED = "LAYOUT_REPAIR_APPLIED"
    LATE_SPLIT_REQUIRED = "LATE_SPLIT_REQUIRED"
    LAYOUT_FAILED = "LAYOUT_FAILED"


class SlideFitStatus(str, enum.Enum):
    """Feasibility outcome for an entire physical slide."""
    PASS = "PASS"
    PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
    LATE_SPLIT_REQUIRED = "LATE_SPLIT_REQUIRED"
    FAIL = "FAIL"


class ZoneFitStatus(str, enum.Enum):
    """Feasibility outcome for a structural zone."""
    FIT = "FIT"
    PRESSURED = "PRESSURED"
    OVERFLOW = "OVERFLOW"
    REPLAN_REQUIRED = "REPLAN_REQUIRED"


class ObjectFitStatus(str, enum.Enum):
    """Feasibility outcome for a specific slide object."""
    FIT = "FIT"
    FIT_WITH_ADJUSTMENT = "FIT_WITH_ADJUSTMENT"
    AT_MINIMUM_SIZE = "AT_MINIMUM_SIZE"
    OVERFLOW = "OVERFLOW"
    REPLAN_REQUIRED = "REPLAN_REQUIRED"


class ImageFitMode(str, enum.Enum):
    """Deterministic image aspect ratio preservation mode."""
    CONTAIN = "CONTAIN"          # Fit entirely within bounding box, preserving aspect ratio
    COVER = "COVER"              # Fill bounding box entirely, cropping overflow deterministically
    FIT_WIDTH = "FIT_WIDTH"      # Match box width, height derives from aspect ratio
    FIT_HEIGHT = "FIT_HEIGHT"    # Match box height, width derives from aspect ratio


class ImageQualityWarning(str, enum.Enum):
    """Pre-renderer image resolution warning."""
    NONE = "NONE"
    LOW_RESOLUTION = "LOW_RESOLUTION"
    UPSCALE_RISK = "UPSCALE_RISK"


class TextRole(str, enum.Enum):
    """Role classification for typography sizing rules."""
    TITLE = "TITLE"
    SUBTITLE = "SUBTITLE"
    BODY = "BODY"
    BULLET = "BULLET"
    KPI_VALUE = "KPI_VALUE"
    KPI_LABEL = "KPI_LABEL"
    TABLE = "TABLE"
    FOOTNOTE = "FOOTNOTE"
    CAPTION = "CAPTION"


# ==============================================================================
# LATE SPLIT CONTRACT
# ==============================================================================

class LateSplitRequest(BaseModel):
    """Formal escalation returned to SlideExpansionEngine when content cannot fit safely.
    
    PPT-L5 NEVER creates physical slides directly. It issues a typed LateSplitRequest.
    """
    physical_slide_id: str = Field(..., description="Physical slide requiring partitioning")
    logical_slide_id: str = Field(..., description="Parent logical topic ID")
    reason: str = Field(..., description="Reason code: TABLE_OVERFLOW, TEXT_OVERFLOW, CHART_SPACE_DEFICIT, BULLET_OVERFLOW")
    affected_content_ids: list[str] = Field(default_factory=list, description="IDs of items causing overflow")
    recommended_partition_hint: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata hint for SlideExpansionEngine (e.g. split_row_index, split_bullet_index)"
    )


# ==============================================================================
# RESOLVED LAYOUT CONTRACTS
# ==============================================================================

class ResolvedObjectLayout(BaseModel):
    """Geometry-resolved specification for a single slide object.
    
    Carries exact Box2D bounds and typography/fit decisions while strictly
    preserving frozen object_id, object_name, and EditabilityPolicy.
    """
    object_id: str = Field(..., description="Permanent HighView semantic object ID from PPT-L4")
    object_name: str = Field(..., description="Permanent Selection-Pane friendly name from PPT-L4")
    content_id: str = Field(..., description="Source content item ID")
    name: str = Field(..., description="Human-readable object name")
    kind: ContentKind = Field(..., description="Visual content kind")
    binding_role: ContentBindingRole = Field(..., description="Binding importance (PRIMARY, SUPPORTING, OPTIONAL)")
    editability: EditabilityPolicy = Field(..., description="Truthful editability capability")
    bounds: Box2D = Field(..., description="Resolved normalized bounding box")
    fit_status: ObjectFitStatus = Field(default=ObjectFitStatus.FIT)
    resolved_font_size: Optional[float] = Field(default=None, description="Resolved font size in points")
    line_count: Optional[int] = Field(default=None, description="Estimated line count")
    fit_mode: Optional[ImageFitMode] = Field(default=None, description="Image fit mode if kind == IMAGE/MAP")
    crop_box: Optional[Box2D] = Field(default=None, description="Deterministic crop box if COVER mode")
    column_widths: Optional[list[float]] = Field(default=None, description="Table column width fractions")
    row_heights: Optional[list[float]] = Field(default=None, description="Table row height fractions")
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResolvedZoneLayout(BaseModel):
    """Geometry-resolved structural zone containing positioned objects."""
    zone_id: str = Field(..., description="Permanent zone identity from PPT-L4")
    zone_type: ZoneType = Field(..., description="Zone functional classification")
    layer_role: LayerRole = Field(..., description="Layer role (BACKGROUND, MASTER_FRAME, BODY, OVERLAY)")
    coordinate_space: CoordinateSpace = Field(..., description="Coordinate space owner")
    bounds: Box2D = Field(..., description="Resolved normalized zone bounding box")
    fit_status: ZoneFitStatus = Field(default=ZoneFitStatus.FIT)
    objects: list[ResolvedObjectLayout] = Field(default_factory=list)
    z_index: int = Field(default=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResolvedSafeArea(BaseModel):
    """Calculated safe area bounds in normalized presentation space."""
    slide_bounds: Box2D = Field(default_factory=lambda: Box2D(left=0.0, top=0.0, width=1.0, height=1.0))
    safe_area_bounds: Box2D = Field(..., description="Outer boundary enclosing safe content")
    frame_header_bounds: Box2D = Field(..., description="Reserved header frame band")
    frame_footer_bounds: Box2D = Field(..., description="Reserved footer frame band")
    body_bounds: Box2D = Field(..., description="Available body content zone between header and footer")


class ResolvedSlideLayout(BaseModel):
    """Complete, validated layout for a single physical slide.
    
    First phase in the pipeline permitted to contain concrete geometry.
    """
    physical_slide_id: str = Field(..., description="Linked PhysicalSlideInstance identifier")
    logical_slide_id: str = Field(..., description="Parent logical topic identifier")
    sequence_index: int = Field(..., ge=1, description="Physical sequence order")
    aspect_ratio: str = Field(default="16:9", description="Canvas aspect ratio")
    slide_bounds: Box2D = Field(default_factory=lambda: Box2D(left=0.0, top=0.0, width=1.0, height=1.0))
    safe_area: ResolvedSafeArea = Field(..., description="Resolved safe area bands")
    zones: list[ResolvedZoneLayout] = Field(default_factory=list, description="Resolved zones")
    object_layouts: list[ResolvedObjectLayout] = Field(default_factory=list, description="Resolved objects")
    fit_status: SlideFitStatus = Field(default=SlideFitStatus.PASS)
    warnings: list[str] = Field(default_factory=list)
    late_split_request: Optional[LateSplitRequest] = Field(default=None)
    repair_attempts: int = Field(default=0, ge=0)
    repair_actions: list[str] = Field(default_factory=list)
    layout_fingerprint: str = Field(default="", description="Deterministic SHA-256 fingerprint")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResolvedDeckLayout(BaseModel):
    """Complete layout specification for an entire deck across all physical slides."""
    deck_id: str = Field(..., description="Unique deck identifier")
    slides: list[ResolvedSlideLayout] = Field(default_factory=list)
    deck_fingerprint: str = Field(default="", description="SHA-256 over all slide fingerprints")
    late_splits: list[LateSplitRequest] = Field(default_factory=list)
    total_slides: int = Field(default=0)
    total_objects: int = Field(default=0)
    replan_required: bool = Field(default=False)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ==============================================================================
# DETERMINISTIC FINGERPRINTING
# ==============================================================================

def compute_layout_fingerprint(
    slide_id: str,
    aspect_ratio: str,
    safe_area: ResolvedSafeArea,
    zones: list[ResolvedZoneLayout],
    fit_status: SlideFitStatus,
    late_split: Optional[LateSplitRequest] = None,
    repair_actions: Optional[list[str]] = None,
) -> str:
    """Computes a strict, deterministic SHA-256 layout fingerprint.
    
    Includes geometry, bounds, typography decisions, crop boxes, and repair outcomes.
    Excludes timestamps, runtime IDs, latencies, colors, themes, and renderer IDs.
    """
    sorted_zones = sorted(zones, key=lambda z: z.zone_id)
    zone_payloads = []
    for z in sorted_zones:
        sorted_objs = sorted(z.objects, key=lambda o: o.object_id)
        obj_payloads = [
            {
                "object_id": o.object_id,
                "object_name": o.object_name,
                "kind": o.kind.value,
                "binding_role": o.binding_role.value,
                "editability": o.editability.value,
                "bounds": o.bounds.to_rounded_dict(),
                "fit_status": o.fit_status.value,
                "resolved_font_size": round(o.resolved_font_size, 2) if o.resolved_font_size is not None else None,
                "line_count": o.line_count,
                "fit_mode": o.fit_mode.value if o.fit_mode else None,
                "crop_box": o.crop_box.to_rounded_dict() if o.crop_box else None,
                "column_widths": [round(w, 4) for w in o.column_widths] if o.column_widths else None,
                "row_heights": [round(h, 4) for h in o.row_heights] if o.row_heights else None,
            }
            for o in sorted_objs
        ]
        zone_payloads.append({
            "zone_id": z.zone_id,
            "zone_type": z.zone_type.value,
            "layer_role": z.layer_role.value,
            "bounds": z.bounds.to_rounded_dict(),
            "fit_status": z.fit_status.value,
            "objects": obj_payloads,
        })

    late_split_dict = late_split.model_dump() if late_split else None

    payload = {
        "physical_slide_id": slide_id,
        "aspect_ratio": aspect_ratio,
        "safe_area": {
            "safe_area_bounds": safe_area.safe_area_bounds.to_rounded_dict(),
            "frame_header_bounds": safe_area.frame_header_bounds.to_rounded_dict(),
            "frame_footer_bounds": safe_area.frame_footer_bounds.to_rounded_dict(),
            "body_bounds": safe_area.body_bounds.to_rounded_dict(),
        },
        "zones": zone_payloads,
        "fit_status": fit_status.value,
        "late_split": late_split_dict,
        "repair_actions": sorted(repair_actions or []),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
