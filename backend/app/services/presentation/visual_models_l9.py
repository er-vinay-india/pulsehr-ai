"""HighView Presentation Studio — PPT-L9 Visual Models & Contracts.

Defines the data contracts for rendered visual inspection and bounded repair:
- RenderedSlideArtifact
- VisualSeverity
- VisualCategory
- VisualConfidence
- VisualCertificationStatus
- VisualIssue
- SlideVisualReviewResult
- VisualReviewManifest
- VisualRepairHistory
- Fingerprinting and deterministic verification functions
"""

from __future__ import annotations

import enum
import hashlib
import json
import logging
from typing import Any, Optional
from pydantic import BaseModel, Field

from app.services.presentation.validation_models_l8 import (
    RepairAction,
    RepairOwner,
    ValidationSeverity,
)

logger = logging.getLogger(__name__)

# Visual Review Boundaries
MAX_VISUAL_REPAIR_ATTEMPTS: int = 2
MIN_RENDER_WIDTH_PX: int = 1200
TARGET_RENDER_WIDTH_PX: int = 1920
TARGET_RENDER_HEIGHT_PX: int = 1080


# ==============================================================================
# ENUMS
# ==============================================================================

class VisualSeverity(str, enum.Enum):
    """Canonical visual issue severity levels, aligned 1:1 with PPT-L8."""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class VisualCategory(str, enum.Enum):
    """Typed visual defect categories observable on rendered slide evidence."""
    TEXT_CLIPPING = "TEXT_CLIPPING"
    TEXT_TOO_DENSE = "TEXT_TOO_DENSE"
    VISUAL_OVERLAP = "VISUAL_OVERLAP"
    ALIGNMENT_DEFECT = "ALIGNMENT_DEFECT"
    SPACING_DEFECT = "SPACING_DEFECT"
    HIERARCHY_DEFECT = "HIERARCHY_DEFECT"
    CHART_LABEL_COLLISION = "CHART_LABEL_COLLISION"
    AXIS_LABEL_COLLISION = "AXIS_LABEL_COLLISION"
    LEGEND_COLLISION = "LEGEND_COLLISION"
    CHART_TOO_SMALL = "CHART_TOO_SMALL"
    TABLE_UNREADABLE = "TABLE_UNREADABLE"
    IMAGE_DISTORTION = "IMAGE_DISTORTION"
    IMAGE_CROP_DEFECT = "IMAGE_CROP_DEFECT"
    IMAGE_LOW_QUALITY = "IMAGE_LOW_QUALITY"
    MAP_UNREADABLE = "MAP_UNREADABLE"
    CONTRAST_DEFECT = "CONTRAST_DEFECT"
    FRAME_COLLISION = "FRAME_COLLISION"
    PRIMARY_VISUAL_OBSCURED = "PRIMARY_VISUAL_OBSCURED"
    EXCESSIVE_WHITESPACE = "EXCESSIVE_WHITESPACE"
    VISUAL_IMBALANCE = "VISUAL_IMBALANCE"
    STYLE_INCONSISTENCY = "STYLE_INCONSISTENCY"
    CONTINUATION_VISUAL_DEFECT = "CONTINUATION_VISUAL_DEFECT"
    RENDER_CORRUPTION = "RENDER_CORRUPTION"


class VisualConfidence(str, enum.Enum):
    """Confidence score of multimodal AI visual detection."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class VisualCertificationStatus(str, enum.Enum):
    """Overall visual certification state of a slide or deck."""
    VISUALLY_CERTIFIED = "VISUALLY_CERTIFIED"
    REPAIR_REQUIRED = "REPAIR_REQUIRED"
    FAIL = "FAIL"


class RepairApprovalLevel(str, enum.Enum):
    """Approval tier for visual repair execution."""
    AUTO_SAFE = "AUTO_SAFE"
    REQUIRES_HUMAN = "REQUIRES_HUMAN"
    NOT_ALLOWED = "NOT_ALLOWED"


# ==============================================================================
# RENDER ARTIFACT
# ==============================================================================

class RenderedSlideArtifact(BaseModel):
    """Metadata and filesystem pointer for an individual rendered slide image."""
    physical_slide_id: str
    slide_index: int
    image_path: str
    width_px: int
    height_px: int
    dpi: int = 150
    renderer_backend: str
    render_fingerprint: str
    source_pptx_fingerprint: str
    metadata: dict[str, Any] = Field(default_factory=dict)


# ==============================================================================
# VISUAL ISSUES & RESULTS
# ==============================================================================

class VisualIssue(BaseModel):
    """Typed visual defect detected on actual rendered slide evidence."""
    issue_id: str
    slide_id: str
    severity: VisualSeverity
    category: VisualCategory
    affected_object_ids: list[str] = Field(default_factory=list)
    description: str
    visual_evidence: str
    confidence: VisualConfidence = VisualConfidence.HIGH
    deterministic_support: bool = False
    recommended_owner: RepairOwner = RepairOwner.PPT_L5_LAYOUT
    recommended_action: RepairAction = RepairAction.LAYOUT_REPLAN_REQUIRED
    repairable: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class SlideVisualReviewResult(BaseModel):
    """Per-slide visual audit outcome."""
    physical_slide_id: str
    slide_index: int
    status: VisualCertificationStatus
    critical_issues_count: int = 0
    warnings_count: int = 0
    info_count: int = 0
    issues: list[VisualIssue] = Field(default_factory=list)
    render_artifact: Optional[RenderedSlideArtifact] = None


class VisualRepairHistory(BaseModel):
    """Audit ledger tracking each bounded repair attempt for a slide."""
    slide_id: str
    attempt: int
    issues_before: list[str]
    repair_action: RepairAction
    repair_owner: RepairOwner
    issues_after: list[str]
    status: str  # "SUCCESS", "PERSISTING", "REGRESSION", "FAILED"
    metadata: dict[str, Any] = Field(default_factory=dict)


class VisualReviewManifest(BaseModel):
    """Complete visual quality certification manifest for an entire presentation."""
    manifest_id: str
    deck_id: str
    status: VisualCertificationStatus
    slides: list[SlideVisualReviewResult] = Field(default_factory=list)
    issues: list[VisualIssue] = Field(default_factory=list)
    counts_by_severity: dict[str, int] = Field(default_factory=dict)
    review_backend: str = "GEMMA_MULTIMODAL"
    review_model: str = "gemma-27b"
    render_backend: str = "PIL_DRAWINGML_RENDERER"
    visual_fingerprint: str = ""
    repair_history: list[VisualRepairHistory] = Field(default_factory=list)
    stats: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ==============================================================================
# DETERMINISTIC FINGERPRINTING
# ==============================================================================

def compute_visual_manifest_fingerprint(manifest: VisualReviewManifest) -> str:
    """Computes a deterministic SHA-256 fingerprint over visual review evidence."""
    payload = {
        "manifest_id": manifest.manifest_id,
        "deck_id": manifest.deck_id,
        "status": manifest.status.value,
        "slides": [
            {
                "slide_id": s.physical_slide_id,
                "status": s.status.value,
                "critical": s.critical_issues_count,
                "warnings": s.warnings_count,
                "render_fp": s.render_artifact.render_fingerprint if s.render_artifact else "",
            }
            for s in manifest.slides
        ],
        "issues": [
            {
                "id": i.issue_id,
                "slide": i.slide_id,
                "sev": i.severity.value,
                "cat": i.category.value,
                "owner": i.recommended_owner.value,
                "action": i.recommended_action.value,
            }
            for i in manifest.issues
        ],
        "review_backend": manifest.review_backend,
        "review_model": manifest.review_model,
        "render_backend": manifest.render_backend,
        "repairs_count": len(manifest.repair_history),
    }
    dumped = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()
