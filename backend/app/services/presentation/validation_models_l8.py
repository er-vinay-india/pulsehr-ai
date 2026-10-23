"""HighView Presentation Studio — PPT-L8 Validation Models.

Defines the typed data contracts for deterministic post-style validation:
- ValidationSeverity (INFO, WARNING, CRITICAL)
- DeckValidationStatus (CERTIFIED, REPAIR_REQUIRED, FAIL)
- ValidationCategory, RepairAction, RepairOwner
- ValidationIssue, RepairRecommendation
- ZoneValidationResult, SlideValidationResult, ValidationManifest
- Deterministic validation fingerprinting
"""

from __future__ import annotations

from enum import Enum
import hashlib
import json
from typing import Any, Optional
from pydantic import BaseModel, Field


class ValidationSeverity(str, Enum):
    """Deterministic severity classification for validation issues."""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class DeckValidationStatus(str, Enum):
    """Final deck certification status."""
    CERTIFIED = "CERTIFIED"
    REPAIR_REQUIRED = "REPAIR_REQUIRED"
    FAIL = "FAIL"


class ValidationCategory(str, Enum):
    """Category of validation check."""
    OBJECT_EXISTENCE = "OBJECT_EXISTENCE"
    IDENTITY_PRESERVATION = "IDENTITY_PRESERVATION"
    CONTENT_PRESERVATION = "CONTENT_PRESERVATION"
    NUMERIC_PRESERVATION = "NUMERIC_PRESERVATION"
    EDITABILITY_PRESERVATION = "EDITABILITY_PRESERVATION"
    GEOMETRY = "GEOMETRY"
    SAFE_AREA = "SAFE_AREA"
    LAYER_ORDER = "LAYER_ORDER"
    COLLISION = "COLLISION"
    TEXT_CLIPPING = "TEXT_CLIPPING"
    STYLE_REFLOW_RISK = "STYLE_REFLOW_RISK"
    TABLE_INTEGRITY = "TABLE_INTEGRITY"
    CHART_INTEGRITY = "CHART_INTEGRITY"
    IMAGE_MAP_QUALITY = "IMAGE_MAP_QUALITY"
    CONTRAST = "CONTRAST"
    SLIDE_COUNT_ORDER = "SLIDE_COUNT_ORDER"
    CONTINUATION_SEQUENCE = "CONTINUATION_SEQUENCE"
    DECK_CONSISTENCY = "DECK_CONSISTENCY"
    GOVERNANCE_LEAK = "GOVERNANCE_LEAK"
    PACKAGE_INTEGRITY = "PACKAGE_INTEGRITY"


class RepairAction(str, Enum):
    """Typed recommendation for bounded upstream repair."""
    TEXT_REFLOW_REQUIRED = "TEXT_REFLOW_REQUIRED"
    LATE_SPLIT_REQUIRED = "LATE_SPLIT_REQUIRED"
    LAYOUT_REPLAN_REQUIRED = "LAYOUT_REPLAN_REQUIRED"
    STYLE_ADJUSTMENT_REQUIRED = "STYLE_ADJUSTMENT_REQUIRED"
    ASSET_REPLACEMENT_REQUIRED = "ASSET_REPLACEMENT_REQUIRED"
    CHART_LABEL_REPLAN_REQUIRED = "CHART_LABEL_REPLAN_REQUIRED"
    TABLE_SPLIT_REQUIRED = "TABLE_SPLIT_REQUIRED"
    FONT_FALLBACK_REVIEW = "FONT_FALLBACK_REVIEW"
    RENDER_RETRY_REQUIRED = "RENDER_RETRY_REQUIRED"


class RepairOwner(str, Enum):
    """The authoritative upstream phase responsible for resolving the defect."""
    PPT_L3_EXPANSION = "PPT_L3_EXPANSION"
    PPT_L4_STRUCTURE = "PPT_L4_STRUCTURE"
    PPT_L5_LAYOUT = "PPT_L5_LAYOUT"
    PPT_L6_RENDERER = "PPT_L6_RENDERER"
    PPT_L7_STYLE = "PPT_L7_STYLE"
    ASSET_PIPELINE = "ASSET_PIPELINE"


class ValidationIssue(BaseModel):
    """An individual identified issue during post-style validation."""
    issue_id: str
    severity: ValidationSeverity
    category: ValidationCategory
    slide_id: Optional[str] = None
    zone_id: Optional[str] = None
    object_id: Optional[str] = None
    object_name: Optional[str] = None
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    recommended_owner: Optional[RepairOwner] = None
    repair_action: Optional[RepairAction] = None
    blocking: bool = False


class RepairRecommendation(BaseModel):
    """Structured request for upstream bounded repair."""
    repair_id: str
    action: RepairAction
    owner: RepairOwner
    slide_id: Optional[str] = None
    object_id: Optional[str] = None
    reason: str


class ZoneValidationResult(BaseModel):
    """Validation report for an individual zone."""
    zone_id: str
    status: str = "PASS"
    issues: list[ValidationIssue] = Field(default_factory=list)


class SlideValidationResult(BaseModel):
    """Validation report for an individual physical slide."""
    physical_slide_id: str
    sequence_index: int
    status: str = "PASS"
    blocking_issue_count: int = 0
    warnings_count: int = 0
    issues: list[ValidationIssue] = Field(default_factory=list)
    zone_results: list[ZoneValidationResult] = Field(default_factory=list)


class ValidationManifest(BaseModel):
    """Complete deterministic manifest of PPT-L8 post-style validation."""
    deck_id: str
    status: DeckValidationStatus
    slides: list[SlideValidationResult] = Field(default_factory=list)
    issues: list[ValidationIssue] = Field(default_factory=list)
    counts_by_severity: dict[str, int] = Field(default_factory=dict)
    repair_requests: list[RepairRecommendation] = Field(default_factory=list)
    stats: dict[str, Any] = Field(default_factory=dict)
    validation_fingerprint: str = ""


def compute_validation_manifest_fingerprint(manifest: ValidationManifest) -> str:
    """Computes deterministic SHA-256 fingerprint for a ValidationManifest."""
    payload = {
        "deck_id": manifest.deck_id,
        "status": manifest.status.value,
        "counts": manifest.counts_by_severity,
        "slides": [
            {
                "slide_id": s.physical_slide_id,
                "status": s.status,
                "blocking": s.blocking_issue_count,
            }
            for s in manifest.slides
        ],
        "issues": [
            {
                "id": i.issue_id,
                "severity": i.severity.value,
                "category": i.category.value,
                "slide_id": i.slide_id,
                "object_id": i.object_id,
                "message": i.message,
                "blocking": i.blocking,
            }
            for i in manifest.issues
        ],
        "repairs": [
            {
                "id": r.repair_id,
                "action": r.action.value,
                "owner": r.owner.value,
            }
            for r in manifest.repair_requests
        ],
    }
    dumped = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()
