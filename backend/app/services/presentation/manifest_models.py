"""HighView Presentation Studio — PPT-L3 Manifest Models & Physical Invariants.

Defines the physical slide manifest, physical slide instance, preflight results,
and architectural validation rules for PPT-L3 (Slide Expansion + Presentation Preflight).

Architectural Invariants:
1. Physical slide identity is semantic and stable (e.g. POPULATION_DENSITY-01, POPULATION_DENSITY-02).
2. Logical topic first, physical page second. Expansion happens due to capacity, not 1-topic = 1-slide.
3. Split before shrink: over-capacity topics split into continuation slides rather than shrinking fonts.
4. ZERO physical geometry: 0 coordinates (x/y/w/h), 0 zones, 0 layers, 0 font sizes, 0 EMU, 0 layouts.
5. Zero silent slide creation: only SlideExpansionEngine owns physical slide existence.
6. Zero fact, unit, grain, or denominator mutations.
7. Zero unassigned primary content items.
"""

from __future__ import annotations

import enum
import hashlib
import json
import logging
from typing import Any, Optional
from pydantic import BaseModel, Field

from .content_models import PresentationContentPackage
from .story_models import ContentBinding, ContentBindingRole, DeckStoryPlan, LogicalSlidePlan, StructuralRole

logger = logging.getLogger(__name__)


# ==============================================================================
# ENUMS & POLICIES
# ==============================================================================

class ContentDensity(str, enum.Enum):
    """Estimated content density category for a logical topic or physical slide."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class ExpansionReason(str, enum.Enum):
    """Explicit rationale for expanding a logical topic into multiple physical slides."""
    NONE = "NONE"
    CONTENT_DENSITY = "CONTENT_DENSITY"
    TABLE_LENGTH = "TABLE_LENGTH"
    MULTI_VISUAL = "MULTI_VISUAL"
    NARRATIVE_SEPARATION = "NARRATIVE_SEPARATION"
    PRIMARY_CONTENT_CONFLICT = "PRIMARY_CONTENT_CONFLICT"
    SUPPORTING_DETAIL = "SUPPORTING_DETAIL"
    APPENDIX_DEFERRED = "APPENDIX_DEFERRED"
    READABILITY_PROTECTION = "READABILITY_PROTECTION"
    LATE_SPLIT_REQUESTED = "LATE_SPLIT_REQUESTED"


class DeckLengthPolicy(str, enum.Enum):
    """Guidance for desired deck scale and capacity tolerance."""
    EXECUTIVE_SHORT = "EXECUTIVE_SHORT"  # 5-7 slides
    STANDARD = "STANDARD"                # 8-12 slides
    DETAILED = "DETAILED"                # 12-16 slides
    ANALYTICAL = "ANALYTICAL"            # 16-22 slides
    CUSTOM = "CUSTOM"


class PreflightStatus(str, enum.Enum):
    """Overall feasibility status from PresentationPreflightEngine."""
    PASS = "PASS"
    PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
    FAIL = "FAIL"


class TargetLengthStatus(str, enum.Enum):
    """Relationship between target deck length guidance and feasible physical count."""
    OPTIMAL = "OPTIMAL"
    ACCEPTABLE = "ACCEPTABLE"
    TARGET_LENGTH_CONFLICT = "TARGET_LENGTH_CONFLICT"
    UNCONSTRAINED = "UNCONSTRAINED"


# ==============================================================================
# PREFLIGHT MODELS
# ==============================================================================

class LogicalTopicPreflightResult(BaseModel):
    """Preflight capacity and feasibility evaluation for a single logical slide."""
    logical_slide_id: str = Field(..., description="ID of the evaluated LogicalSlidePlan")
    semantic_topic: str = Field(..., description="Semantic domain topic evaluated")
    structural_role: StructuralRole = Field(..., description="Narrative structural role")
    estimated_density: ContentDensity = Field(default=ContentDensity.MEDIUM)
    recommended_physical_slides: int = Field(default=1, ge=1)
    expansion_reason: ExpansionReason = Field(default=ExpansionReason.NONE)
    primary_bindings_count: int = Field(default=0)
    supporting_bindings_count: int = Field(default=0)
    optional_bindings_count: int = Field(default=0)
    table_split_recommended: bool = Field(default=False)
    multi_visual_split_recommended: bool = Field(default=False)
    warnings: list[str] = Field(default_factory=list)
    notes: str = Field(default="")


class PresentationPreflightResult(BaseModel):
    """Comprehensive preflight evaluation of a DeckStoryPlan before physical expansion."""
    status: PreflightStatus = Field(default=PreflightStatus.PASS)
    deck_story_plan_id: str = Field(...)
    logical_topic_results: list[LogicalTopicPreflightResult] = Field(default_factory=list)
    estimated_physical_slide_count: int = Field(default=0)
    target_length_guidance: Optional[int] = Field(default=None)
    target_length_policy: DeckLengthPolicy = Field(default=DeckLengthPolicy.STANDARD)
    target_length_status: TargetLengthStatus = Field(default=TargetLengthStatus.UNCONSTRAINED)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ==============================================================================
# PHYSICAL SLIDE MODELS
# ==============================================================================

class PhysicalSlideInstance(BaseModel):
    """Stable, geometry-free physical slide instance produced by SlideExpansionEngine.
    
    Identifies WHAT content belongs on THIS physical page and HOW it links to
    the parent logical topic, without any coordinate placement, typography sizing,
    or zone layout geometry.
    """
    physical_slide_id: str = Field(
        ...,
        description="Deterministic semantic physical ID (e.g. POPULATION_DENSITY-01, POPULATION_DENSITY-02)"
    )
    logical_slide_id: str = Field(..., description="Parent LogicalSlidePlan identifier")
    semantic_topic: str = Field(..., description="Domain semantic topic")
    structural_role: StructuralRole = Field(..., description="Structural narrative role")
    sequence_index: int = Field(..., ge=1, description="1-based physical sequence order in presentation")
    continuation_index: int = Field(default=1, ge=1, description="1-based index within the continuation chain")
    is_continuation: bool = Field(default=False, description="True if this is continuation page (pt2+)")
    content_bindings: list[ContentBinding] = Field(
        default_factory=list,
        description="Content items allocated to this physical slide"
    )
    slide_purpose: str = Field(default="", description="Narrative purpose of this physical slide")
    headline: str = Field(default="", description="Slide headline text")
    section_name: str = Field(default="", description="Parent presentation section")
    estimated_density: ContentDensity = Field(default=ContentDensity.MEDIUM)
    expansion_reason: ExpansionReason = Field(default=ExpansionReason.NONE)
    primary_owner_slide_id: Optional[str] = Field(
        default=None,
        description="Tracks primary physical owner slide for content reuse tracking"
    )
    is_intentional_duplication: bool = Field(
        default=False,
        description="True if content on this slide intentionally repeats context from another slide"
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def title(self) -> str:
        return self.headline or self.semantic_topic.replace("_", " ").title()

    @property
    def headline_text(self) -> str:
        return self.headline

    @property
    def takeaway_text(self) -> str:
        return self.metadata.get("takeaway", "") or self.slide_purpose or self.headline

    @property
    def planned_layout_family(self) -> str:
        return self.metadata.get("planned_layout_family", "chart_narrative")

    @property
    def logical_tag(self) -> str:
        return self.structural_role.value if hasattr(self.structural_role, "value") else str(self.structural_role)


class LogicalTopicMapping(BaseModel):
    """Tracks the expansion mapping from one logical slide to one or more physical slides."""
    logical_slide_id: str = Field(...)
    semantic_topic: str = Field(...)
    structural_role: StructuralRole = Field(...)
    physical_slide_ids: list[str] = Field(default_factory=list)
    expansion_reason: ExpansionReason = Field(default=ExpansionReason.NONE)
    is_split: bool = Field(default=False)


class SectionMapping(BaseModel):
    """Tracks section boundaries across physical slides for later TOC and navigation."""
    section_id: str = Field(...)
    section_name: str = Field(...)
    first_physical_slide_id: str = Field(...)
    last_physical_slide_id: str = Field(...)
    first_sequence_index: int = Field(..., ge=1)
    last_sequence_index: int = Field(..., ge=1)
    physical_count: int = Field(..., ge=1)


class PhysicalSlideManifest(BaseModel):
    """The authoritative physical slide manifest emitted by PPT-L3.
    
    Contains the complete set of physical slides, logical mappings, section boundaries,
    and preflight telemetry. Strictly zero layout geometry.
    """
    manifest_id: str = Field(..., description="Unique manifest ID (e.g. MANIFEST-PLAN-...)")
    deck_story_plan_id: str = Field(..., description="ID of source DeckStoryPlan")
    slides: list[PhysicalSlideInstance] = Field(
        default_factory=list,
        description="Ordered list of physical slide instances"
    )
    logical_topic_mappings: list[LogicalTopicMapping] = Field(
        default_factory=list,
        description="Mapping from logical units to physical slide IDs"
    )
    section_mappings: list[SectionMapping] = Field(
        default_factory=list,
        description="Section boundaries across physical sequence"
    )
    preflight_summary: Optional[PresentationPreflightResult] = Field(default=None)
    manifest_version: int = Field(default=1, ge=1, description="Manifest revision version")
    parent_manifest_fingerprint: Optional[str] = Field(
        default=None,
        description="Fingerprint of prior manifest if this is a controlled late split revision"
    )
    revision_reason: Optional[str] = Field(
        default=None,
        description="Reason for late manifest revision"
    )
    manifest_fingerprint: str = Field(
        default="",
        description="Deterministic SHA-256 fingerprint over physical slide manifest structure"
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    def compute_manifest_fingerprint(self) -> str:
        """Computes a deterministic SHA-256 fingerprint over canonical physical manifest properties."""
        canonical_slides = []
        for s in sorted(self.slides, key=lambda x: (x.sequence_index, x.physical_slide_id)):
            sorted_bindings = sorted(s.content_bindings, key=lambda b: (b.content_id, b.binding_role.value))
            canonical_slides.append({
                "physical_slide_id": s.physical_slide_id,
                "logical_slide_id": s.logical_slide_id,
                "semantic_topic": s.semantic_topic,
                "structural_role": s.structural_role.value,
                "sequence_index": s.sequence_index,
                "continuation_index": s.continuation_index,
                "is_continuation": s.is_continuation,
                "headline": s.headline,
                "section": s.section_name,
                "expansion_reason": s.expansion_reason.value,
                "bindings": [
                    {"id": b.content_id, "role": b.binding_role.value}
                    for b in sorted_bindings
                ]
            })

        canonical_mappings = [
            {
                "logical_id": m.logical_slide_id,
                "topic": m.semantic_topic,
                "physical_ids": list(m.physical_slide_ids),
                "reason": m.expansion_reason.value
            }
            for m in sorted(self.logical_topic_mappings, key=lambda x: x.logical_slide_id)
        ]

        canonical_sections = [
            {
                "section_id": sm.section_id,
                "name": sm.section_name,
                "first_id": sm.first_physical_slide_id,
                "last_id": sm.last_physical_slide_id,
                "count": sm.physical_count
            }
            for sm in sorted(self.section_mappings, key=lambda x: x.first_sequence_index)
        ]

        payload = {
            "story_plan_id": self.deck_story_plan_id,
            "version": self.manifest_version,
            "parent_fingerprint": self.parent_manifest_fingerprint or "",
            "revision_reason": self.revision_reason or "",
            "slides": canonical_slides,
            "mappings": canonical_mappings,
            "sections": canonical_sections,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


# ==============================================================================
# EXCEPTIONS & VALIDATION
# ==============================================================================

class ManifestValidationError(Exception):
    """Raised when a PhysicalSlideManifest violates architectural invariants."""
    pass


class UnassignedPrimaryContentError(ManifestValidationError):
    """Raised when a primary content item from DeckStoryPlan is not assigned to any physical slide."""
    pass


class ExpansionLimitExceededError(ManifestValidationError):
    """Raised when a logical topic exceeds the maximum allowable physical slide expansion."""
    pass


class TargetLengthConflictError(ManifestValidationError):
    """Raised when a requested deck length cannot fit required primary content without violation."""
    pass


class InvalidContinuationChainError(ManifestValidationError):
    """Raised when continuation slides have broken sequences or non-contiguous ordering."""
    pass


class ManifestContentMismatchError(ManifestValidationError):
    """Raised when content IDs in physical manifest do not match the source package/plan."""
    pass


class PhysicalLayoutLeakageError(ManifestValidationError):
    """Raised if layout coordinates, typography sizing, or zones leak into PPT-L3."""
    pass


class PhysicalSlideManifestValidator:
    """Validates PhysicalSlideManifest compliance against DeckStoryPlan and PPT-L3 invariants."""

    FORBIDDEN_GEOMETRY_FIELDS = {
        "x", "y", "width", "height", "left", "top", "pt_x", "pt_y",
        "zones", "layers", "bounding_box", "coordinate_space",
        "canvas_width", "canvas_height", "font_size_pt", "font_size",
        "emu", "layout_template", "layout_coordinates", "theme_style",
        "font_family", "line_height_pt", "shape_type"
    }

    @classmethod
    def validate(
        cls,
        manifest: PhysicalSlideManifest,
        story_plan: DeckStoryPlan,
        content_pkg: PresentationContentPackage
    ) -> None:
        """Validates all architectural invariants of the PhysicalSlideManifest.
        
        Args:
            manifest: The PhysicalSlideManifest to validate.
            story_plan: The source DeckStoryPlan.
            content_pkg: The source PresentationContentPackage.
        """
        if not manifest.slides:
            raise ManifestValidationError("PhysicalSlideManifest must contain at least one physical slide")

        # 1. Zero geometry leakage check
        cls._check_no_geometry_leakage(manifest)

        # 2. Unique physical IDs
        seen_phys_ids: set[str] = set()
        for idx, slide in enumerate(manifest.slides):
            if not slide.physical_slide_id or not slide.physical_slide_id.strip():
                raise ManifestValidationError(f"Slide index {idx} has empty physical_slide_id")
            if slide.physical_slide_id in seen_phys_ids:
                raise ManifestValidationError(f"Duplicate physical_slide_id detected: '{slide.physical_slide_id}'")
            seen_phys_ids.add(slide.physical_slide_id)

        # 3. Sequence integrity (1..N contiguous, no gaps, no duplicates)
        sequences = [s.sequence_index for s in manifest.slides]
        expected_sequences = list(range(1, len(manifest.slides) + 1))
        if sequences != expected_sequences:
            raise ManifestValidationError(
                f"Physical sequence indices must be strictly 1..{len(manifest.slides)} without gaps or reordering. "
                f"Found: {sequences}"
            )

        # 4. Valid logical references
        valid_logical_ids = {s.logical_slide_id for s in story_plan.logical_slides}
        for slide in manifest.slides:
            if slide.logical_slide_id not in valid_logical_ids:
                raise ManifestValidationError(
                    f"Physical slide '{slide.physical_slide_id}' references unknown logical_slide_id: '{slide.logical_slide_id}'"
                )

        # 5. Primary content coverage (unassigned primary = 0)
        # Collect all primary content bindings from the logical story plan
        required_primary_ids: set[str] = set()
        for l_slide in story_plan.logical_slides:
            for b in l_slide.content_bindings:
                if b.binding_role == ContentBindingRole.PRIMARY:
                    required_primary_ids.add(b.content_id)

        # Collect assigned primary content from physical slides
        assigned_content_ids: set[str] = set()
        for slide in manifest.slides:
            for b in slide.content_bindings:
                assigned_content_ids.add(b.content_id)

        unassigned_primaries = required_primary_ids - assigned_content_ids
        if unassigned_primaries:
            raise UnassignedPrimaryContentError(
                f"The following {len(unassigned_primaries)} primary content items from DeckStoryPlan are unassigned: "
                f"{sorted(unassigned_primaries)}. Silent primary content loss is strictly prohibited."
            )

        # 6. Verify all referenced content exists in source package
        known_pkg_ids = {it.content_id for it in content_pkg.items} | {k.content_id for k in content_pkg.global_kpis}
        for slide in manifest.slides:
            for b in slide.content_bindings:
                if b.content_id not in known_pkg_ids:
                    raise ManifestContentMismatchError(
                        f"Physical slide '{slide.physical_slide_id}' references unknown content_id: '{b.content_id}'"
                    )

        # 7. Continuation chain contiguity check
        # For each logical topic, continuation slides must have indices 1..K and be physically contiguous
        logical_to_physical: dict[str, list[PhysicalSlideInstance]] = {}
        for s in manifest.slides:
            logical_to_physical.setdefault(s.logical_slide_id, []).append(s)

        for l_id, p_slides in logical_to_physical.items():
            # Check continuation indices 1..K
            cont_indices = [ps.continuation_index for ps in p_slides]
            expected_cont = list(range(1, len(p_slides) + 1))
            if cont_indices != expected_cont:
                raise InvalidContinuationChainError(
                    f"Logical slide '{l_id}' has broken continuation chain: {cont_indices} (expected {expected_cont})"
                )

            # Check sequence contiguity (physical sequence indices must be adjacent)
            p_seqs = [ps.sequence_index for ps in p_slides]
            expected_p_seqs = list(range(p_seqs[0], p_seqs[0] + len(p_slides)))
            if p_seqs != expected_p_seqs:
                raise InvalidContinuationChainError(
                    f"Continuation slides for logical slide '{l_id}' are not contiguous in physical sequence! "
                    f"Found sequences: {p_seqs}"
                )

            # Check continuation flag
            if p_slides[0].is_continuation:
                raise InvalidContinuationChainError(
                    f"First slide '{p_slides[0].physical_slide_id}' of logical slide '{l_id}' must have is_continuation=False"
                )
            for ps in p_slides[1:]:
                if not ps.is_continuation:
                    raise InvalidContinuationChainError(
                        f"Subsequent slide '{ps.physical_slide_id}' of logical slide '{l_id}' must have is_continuation=True"
                    )

        # 8. Structural order invariants: TITLE first (if present), CLOSING last (if present)
        first_slide = manifest.slides[0]
        if any(s.structural_role == StructuralRole.TITLE for s in story_plan.logical_slides):
            if first_slide.structural_role != StructuralRole.TITLE:
                raise ManifestValidationError(
                    f"First physical slide must be StructuralRole.TITLE when story plan contains TITLE. "
                    f"Found: {first_slide.structural_role}"
                )

        last_slide = manifest.slides[-1]
        has_closing_in_plan = any(s.structural_role == StructuralRole.CLOSING for s in story_plan.logical_slides)
        if has_closing_in_plan:
            if last_slide.structural_role != StructuralRole.CLOSING:
                raise ManifestValidationError(
                    f"Last physical slide must be StructuralRole.CLOSING when story plan contains CLOSING. "
                    f"Found: {last_slide.structural_role}"
                )

        # 9. Story narrative order preservation
        # Ensure that the first appearance of each logical slide in the physical sequence follows
        # the logical_order defined in DeckStoryPlan
        logical_order_map = {s.logical_slide_id: s.logical_order for s in story_plan.logical_slides}
        seen_first_sequences: list[tuple[int, str]] = []  # (logical_order, logical_slide_id)
        seen_lids_order: set[str] = set()

        for s in manifest.slides:
            if s.logical_slide_id not in seen_lids_order:
                seen_lids_order.add(s.logical_slide_id)
                seen_first_sequences.append((logical_order_map[s.logical_slide_id], s.logical_slide_id))

        extracted_orders = [ord_idx for ord_idx, _ in seen_first_sequences]
        if extracted_orders != sorted(extracted_orders):
            raise ManifestValidationError(
                f"Physical slides violate logical story narrative order! Sequence: {seen_first_sequences}"
            )

        # 10. Manifest fingerprint verification
        if manifest.manifest_fingerprint:
            computed_fp = manifest.compute_manifest_fingerprint()
            if manifest.manifest_fingerprint != computed_fp:
                raise ManifestValidationError(
                    f"Manifest fingerprint mismatch! Stored: {manifest.manifest_fingerprint}, Computed: {computed_fp}"
                )

    @classmethod
    def _check_no_geometry_leakage(cls, manifest: PhysicalSlideManifest) -> None:
        """Recursively checks for forbidden geometry, coordinate, or typography fields."""
        manifest_dict = manifest.model_dump()
        found_fields: list[str] = []

        def _traverse(obj: Any, path: str = "") -> None:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    k_lower = str(k).lower()
                    if k_lower in cls.FORBIDDEN_GEOMETRY_FIELDS:
                        found_fields.append(f"{path}.{k}" if path else str(k))
                    _traverse(v, f"{path}.{k}" if path else str(k))
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    _traverse(item, f"{path}[{i}]")

        _traverse(manifest_dict)
        if found_fields:
            raise PhysicalLayoutLeakageError(
                f"PhysicalSlideManifest contains forbidden layout/geometry fields in PPT-L3: {found_fields}. "
                f"Geometry, coordinates, typography, and zones belong strictly to PPT-L4/L5."
            )
