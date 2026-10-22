"""HighView Presentation Studio — PPT-L4 Layer/Zone Contracts & Stable Object Identity.

Defines the structural slide specification, zone specifications, slide object specifications,
layer roles, coordinate space ownership, safe area policy, editability policy, and
architectural validation rules for PPT-L4.

Architectural Invariants:
1. PPT-L4 owns structure and identity, NOT position or geometry.
2. ZERO layout coordinates (x/y/w/h, pct bounds), ZERO EMUs, ZERO font sizes, ZERO colors/themes.
3. SlideExpansionEngine remains the SOLE owner of physical slide creation (physical slide creation in PPT-L4 = 0).
4. Zero cross-slide content movement: content allocated to a physical slide stays on that physical slide.
5. If structure cannot accommodate content, emits STRUCTURE_REPLAN_REQUIRED rather than silently creating/moving slides.
6. Stable, deterministic object IDs that survive regeneration, layout, and theme changes.
7. Truthful editability policy: raster/composite maps are NEVER marked NATIVE_EDITABLE.
8. Zero governance leakage in normal business decks; accurate preservation in technical decks.
9. AI structure calls = 0.
"""

from __future__ import annotations

import enum
import hashlib
import json
import logging
import re
from typing import Any, Optional
from pydantic import BaseModel, Field

from .content_models import ContentKind, PresentationContentPackage
from .manifest_models import PhysicalSlideInstance, PhysicalSlideManifest
from .story_models import ContentBinding, ContentBindingRole, StructuralRole

logger = logging.getLogger(__name__)


# ==============================================================================
# ENUMS & ROLES
# ==============================================================================

class LayerRole(str, enum.Enum):
    """Architectural layer role within a slide."""
    BACKGROUND = "BACKGROUND"      # Layer 1: Canvas fill, background pattern, watermark
    MASTER_FRAME = "MASTER_FRAME"  # Layer 2: Master slide chrome (ribbon, header, footer, confidentiality)
    BODY = "BODY"                  # Layer 3: Main safe content zone (titles, visuals, tables, insights)
    OVERLAY = "OVERLAY"            # Layer 4: Floating callout badges, annotations, modal highlights


class CoordinateSpace(str, enum.Enum):
    """Ownership space for zone and object coordination.
    
    Formalizes the spatial coordinate space without assigning numeric coordinate values.
    """
    SLIDE_SPACE = "SLIDE_SPACE"              # Full physical canvas coordinate ownership
    MASTER_FRAME_SPACE = "MASTER_FRAME_SPACE"# Persistent chrome reserved coordinate space
    BODY_SPACE = "BODY_SPACE"                # Safe body area enclosed within safe margins


class ZoneType(str, enum.Enum):
    """Semantic purpose of a structural zone on a slide."""
    TITLE = "TITLE"
    SUBTITLE = "SUBTITLE"
    PRIMARY_VISUAL = "PRIMARY_VISUAL"
    SECONDARY_VISUAL = "SECONDARY_VISUAL"
    INSIGHT_NARRATIVE = "INSIGHT_NARRATIVE"
    BULLETS = "BULLETS"
    KPI_STRIP = "KPI_STRIP"
    DATA_TABLE = "DATA_TABLE"
    CALLOUT_BADGE = "CALLOUT_BADGE"
    FOOTNOTE = "FOOTNOTE"
    BACKGROUND_CANVAS = "BACKGROUND_CANVAS"
    MASTER_CHROME = "MASTER_CHROME"


class EditabilityPolicy(str, enum.Enum):
    """Truthful editability capability of a slide object when rendered in native PowerPoint.
    
    Expresses downstream renderer policy expectations rather than rendering outcome results.
    """
    NATIVE_REQUIRED = "NATIVE_REQUIRED"    # Mandatory native PowerPoint DrawingML (titles, text, tables)
    NATIVE_PREFERRED = "NATIVE_PREFERRED"  # Prefer native chart DrawingML, graceful fallback permitted
    RASTER_ALLOWED = "RASTER_ALLOWED"      # Static raster/vector image allowed (maps, complex diagrams, photos)
    MEDIA_REFERENCE = "MEDIA_REFERENCE"    # External or embedded media pointer (audio/video/linked documents)


# Backward compatibility aliases for transition
EditabilityPolicy.NATIVE_EDITABLE = EditabilityPolicy.NATIVE_REQUIRED  # type: ignore[attr-defined]
EditabilityPolicy.PARTIALLY_EDITABLE = EditabilityPolicy.NATIVE_PREFERRED  # type: ignore[attr-defined]
EditabilityPolicy.STATIC_IMAGE_FALLBACK = EditabilityPolicy.RASTER_ALLOWED  # type: ignore[attr-defined]
EditabilityPolicy.NON_EDITABLE = EditabilityPolicy.RASTER_ALLOWED  # type: ignore[attr-defined]


class FrameInheritancePolicy(str, enum.Enum):
    """Inheritance intent for master frame chrome objects and structural zones."""
    MASTER_PREFERRED = "MASTER_PREFERRED"  # Prefer inheritance from PowerPoint slide master
    PER_SLIDE = "PER_SLIDE"                # Explicitly bound per physical slide


class StructureStatus(str, enum.Enum):
    """Feasibility outcome of structural zone and object assembly."""
    STRUCTURE_VALIDATED = "STRUCTURE_VALIDATED"
    STRUCTURE_REPLAN_REQUIRED = "STRUCTURE_REPLAN_REQUIRED"


# ==============================================================================
# SAFE AREA POLICY (CONCEPTUAL, ZERO NUMERIC COORDINATES)
# ==============================================================================

class SafeAreaSpec(BaseModel):
    """Conceptual safe area contract defining zone margin and chrome reservation policies.
    
    Declares margin and reservation policies without computing or assigning
    physical x/y/w/h coordinates or pixel geometries.
    """
    policy_name: str = Field(default="standard_executive_safe_area")
    margin_policy: str = Field(
        default="STANDARD_INSET",
        description="Policy rule: uniform margins around physical slide perimeter"
    )
    header_reservation_rule: str = Field(
        default="RESERVE_TOP_CHROME",
        description="Rule reserving top band for category ribbon and slide title"
    )
    footer_reservation_rule: str = Field(
        default="RESERVE_BOTTOM_CHROME",
        description="Rule reserving bottom band for page numbers, confidentiality, and footnotes"
    )
    body_containment_rule: str = Field(
        default="STRICT_BODY_BOUNDS",
        description="Rule enforcing that all body zones remain strictly inside safe body bounds"
    )


# ==============================================================================
# SLIDE OBJECT & ZONE SPECIFICATIONS
# ==============================================================================

class SlideObjectSpec(BaseModel):
    """Stable, geometry-free structural specification of a single object on a slide.
    
    Carries permanent semantic identity (object_id), Selection-Pane friendly name (object_name),
    source traceability, and editability policy.
    Zero coordinates, zero font sizes, zero colors, zero PPTX shape IDs.
    """
    object_id: str = Field(
        ...,
        description="Deterministic HighView semantic object identity, e.g. POPULATION_DENSITY-01__OBJ_MAP_ITEM-GEO-01"
    )
    object_name: str = Field(
        default="",
        description="Renderer-facing Selection Pane friendly label, e.g. HV_POPULATION_DENSITY_01_PRIMARY_VISUAL"
    )
    name: str = Field(..., description="Human-readable semantic object label")
    content_id: str = Field(..., description="Linked PresentationContentItem ID from content package")
    binding_role: ContentBindingRole = Field(..., description="Role of this item (PRIMARY, SUPPORTING, OPTIONAL)")
    kind: ContentKind = Field(..., description="Physical visual or textual format")
    semantic_topic: str = Field(..., description="Parent domain semantic topic")
    editability: EditabilityPolicy = Field(
        ...,
        description="Truthful editability classification in PowerPoint"
    )
    inheritance_policy: FrameInheritancePolicy = Field(
        default=FrameInheritancePolicy.PER_SLIDE,
        description="Inheritance intent for master frame vs slide level"
    )
    headline: str = Field(default="", description="Object headline or title")
    narrative_text: str = Field(default="", description="Object body narrative or takeaway")
    data_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Summary metadata of underlying data (e.g. row count, metric value, series count)"
    )
    source_traceability: dict[str, Any] = Field(
        default_factory=dict,
        description="Audited lineage back to source dataset, sheet, grain, unit, and fact ID"
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class ZoneSpec(BaseModel):
    """Structural zone within a layer, grouping related slide objects.
    
    Zero coordinates (x/y/w/h), zero layout proportions, zero EMUs.
    """
    zone_id: str = Field(
        ...,
        description="Deterministic semantic zone identity, e.g. POPULATION_DENSITY-01__ZONE_PRIMARY_VISUAL"
    )
    zone_type: ZoneType = Field(..., description="Functional zone classification")
    layer_role: LayerRole = Field(default=LayerRole.BODY, description="Architectural layer role")
    coordinate_space: CoordinateSpace = Field(
        default=CoordinateSpace.BODY_SPACE,
        description="Logical coordinate space owner"
    )
    inheritance_policy: FrameInheritancePolicy = Field(
        default=FrameInheritancePolicy.PER_SLIDE,
        description="Inheritance intent for this zone"
    )
    objects: list[SlideObjectSpec] = Field(
        default_factory=list,
        description="Slide objects bound to this zone"
    )
    allowed_kinds: list[ContentKind] = Field(
        default_factory=list,
        description="Content kinds permitted in this zone"
    )
    z_index: int = Field(default=1, ge=0, description="Stacking order within the layer")
    metadata: dict[str, Any] = Field(default_factory=dict)


class LayeredSlideSpec(BaseModel):
    """Authoritative structural specification of a single physical slide.
    
    Binds the physical slide to its layers, zones, and objects.
    Contains strictly zero coordinates, zero layout proportions, and zero typography sizing.
    """
    physical_slide_id: str = Field(..., description="Linked PhysicalSlideInstance identifier")
    logical_slide_id: str = Field(..., description="Parent LogicalSlidePlan identifier")
    semantic_topic: str = Field(..., description="Domain semantic topic")
    structural_role: StructuralRole = Field(..., description="Structural narrative role")
    sequence_index: int = Field(..., ge=1, description="Physical slide sequence order")
    continuation_index: int = Field(default=1, ge=1, description="Continuation page index")
    is_continuation: bool = Field(default=False)
    headline: str = Field(default="", description="Slide headline")
    section_name: str = Field(default="", description="Parent presentation section")
    zones: list[ZoneSpec] = Field(
        default_factory=list,
        description="Structural zones declared on this slide"
    )
    safe_area: SafeAreaSpec = Field(default_factory=SafeAreaSpec)
    structure_status: StructureStatus = Field(default=StructureStatus.STRUCTURE_VALIDATED)
    replan_reason: Optional[str] = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LayeredDeckStructureSpec(BaseModel):
    """Complete structural specification for an entire deck across all physical slides."""
    manifest_id: str = Field(...)
    manifest_version: int = Field(default=1, ge=1)
    slides: list[LayeredSlideSpec] = Field(default_factory=list)
    object_registry: dict[str, SlideObjectSpec] = Field(
        default_factory=dict,
        description="Global catalog of all objects in the deck for targeted tracking and regeneration"
    )
    structure_fingerprint: str = Field(
        default="",
        description="Deterministic SHA-256 fingerprint over complete slide and zone structure"
    )
    replan_required: bool = Field(default=False)
    replan_reasons: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def compute_structure_fingerprint(self) -> str:
        """Computes a deterministic SHA-256 fingerprint over structural hierarchy and objects."""
        canonical_slides = []
        for s in sorted(self.slides, key=lambda x: (x.sequence_index, x.physical_slide_id)):
            canonical_zones = []
            for z in sorted(s.zones, key=lambda x: (x.z_index, x.zone_id)):
                canonical_objects = []
                for o in sorted(z.objects, key=lambda x: x.object_id):
                    canonical_objects.append({
                        "object_id": o.object_id,
                        "object_name": o.object_name,
                        "content_id": o.content_id,
                        "kind": o.kind.value,
                        "role": o.binding_role.value,
                        "editability": o.editability.value,
                        "inheritance_policy": o.inheritance_policy.value,
                        "headline": o.headline,
                    })
                canonical_zones.append({
                    "zone_id": z.zone_id,
                    "zone_type": z.zone_type.value,
                    "layer": z.layer_role.value,
                    "coord_space": z.coordinate_space.value,
                    "inheritance_policy": z.inheritance_policy.value,
                    "objects": canonical_objects
                })
            canonical_slides.append({
                "physical_slide_id": s.physical_slide_id,
                "logical_slide_id": s.logical_slide_id,
                "semantic_topic": s.semantic_topic,
                "structural_role": s.structural_role.value,
                "sequence_index": s.sequence_index,
                "continuation_index": s.continuation_index,
                "is_continuation": s.is_continuation,
                "zones": canonical_zones
            })

        payload = {
            "manifest_id": self.manifest_id,
            "manifest_version": self.manifest_version,
            "slides": canonical_slides,
            "replan_required": self.replan_required,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


# ==============================================================================
# EXCEPTIONS & VALIDATION
# ==============================================================================

class StructureValidationError(Exception):
    """Raised when a LayeredDeckStructureSpec violates architectural invariants."""
    pass


class StructureReplanRequiredError(StructureValidationError):
    """Raised when a slide's content cannot be structurally accommodated without replanning."""
    pass


class OrphanObjectError(StructureValidationError):
    """Raised when an object is not assigned to any zone or its content reference is missing."""
    pass


class UnmappedPrimaryContentError(StructureValidationError):
    """Raised when primary content from PhysicalSlideManifest is missing from the structure."""
    pass


class CrossSlideMovementError(StructureValidationError):
    """Raised if an object allocated to one physical slide is moved to another physical slide."""
    pass


class PhysicalGeometryLeakageError(StructureValidationError):
    """Raised if layout coordinates, typography sizes, colors, or PPTX objects leak into PPT-L4."""
    pass


class GovernanceLeakageError(StructureValidationError):
    """Raised when internal governance jargon leaks into normal business presentations."""
    pass


class LayeredSlideStructureValidator:
    """Validates LayeredDeckStructureSpec compliance against PhysicalSlideManifest and PPT-L4 invariants."""

    FORBIDDEN_GEOMETRY_AND_STYLE_FIELDS = {
        "x", "y", "width", "height", "left", "top", "pt_x", "pt_y",
        "left_pct", "top_pct", "width_pct", "height_pct",
        "emu", "pt", "canvas_width", "canvas_height",
        "font_size", "font_size_pt", "font_family", "line_height", "line_height_pt",
        "color", "theme_color", "background_color", "hex", "palette", "fill",
        "layout_template", "layout_proportions", "grid_columns", "column_proportions",
        "shape", "drawingml", "pptx", "shape_id", "pptx_id", "pptx_shape_id", "shape_type"
    }

    FORBIDDEN_GOVERNANCE_PATTERNS = [
        r"\bSDR\b",
        r"\bSDR-\d+\b",
        r"\bJoinPlan\b",
        r"\bJoinGraph\b",
        r"\bEVID-[A-Za-z0-9_\-]+\b",
        r"\b[a-f0-9]{32,64}\b",  # Checksums / hashes
        r"\bcontrol\s+plane\b",
        r"\borchestrator\s+task\b",
    ]

    @classmethod
    def validate(
        cls,
        deck_structure: LayeredDeckStructureSpec,
        manifest: PhysicalSlideManifest,
        content_pkg: PresentationContentPackage,
        is_technical_deck: bool = False
    ) -> None:
        """Validates all architectural invariants of the LayeredDeckStructureSpec.
        
        Args:
            deck_structure: The LayeredDeckStructureSpec to validate.
            manifest: The source PhysicalSlideManifest from PPT-L3.
            content_pkg: The source PresentationContentPackage from PPT-L1.
            is_technical_deck: If True, preserves requested technical terms.
        """
        # 1. Check for physical geometry and styling leakage
        cls._check_no_geometry_or_style_leakage(deck_structure)

        # 2. Invariant: SlideExpansionEngine is sole owner of physical slides
        # Structure must have EXACTLY the same number of slides and identical physical slide IDs
        manifest_slide_ids = [s.physical_slide_id for s in manifest.slides]
        structure_slide_ids = [s.physical_slide_id for s in deck_structure.slides]
        if manifest_slide_ids != structure_slide_ids:
            raise StructureValidationError(
                f"Slide count or physical slide IDs mismatch between Manifest and Structure! "
                f"Manifest slides: {manifest_slide_ids}, Structure slides: {structure_slide_ids}. "
                f"SlideExpansionEngine is the SOLE owner of physical slide creation."
            )

        # 3. Check sequence and continuity
        for idx, (m_slide, s_slide) in enumerate(zip(manifest.slides, deck_structure.slides)):
            if m_slide.sequence_index != s_slide.sequence_index:
                raise StructureValidationError(
                    f"Slide index {idx} sequence mismatch: Manifest={m_slide.sequence_index}, Structure={s_slide.sequence_index}"
                )
            if m_slide.logical_slide_id != s_slide.logical_slide_id:
                raise StructureValidationError(
                    f"Slide index {idx} logical ID mismatch: Manifest={m_slide.logical_slide_id}, Structure={s_slide.logical_slide_id}"
                )

        # 4. Invariant: Zero cross-slide content movement
        # Content bound to physical slide N in manifest MUST belong to physical slide N in structure
        for m_slide, s_slide in zip(manifest.slides, deck_structure.slides):
            m_content_ids = {b.content_id for b in m_slide.content_bindings}
            # Non-structural content IDs (originating from content package)
            s_content_ids = {
                obj.content_id
                for zone in s_slide.zones
                for obj in zone.objects
                if not obj.content_id.startswith(f"{s_slide.physical_slide_id}__")
            }
            # Check for cross-slide leaks from other manifest slides
            other_manifest_ids = {
                b.content_id
                for other in manifest.slides
                if other.physical_slide_id != m_slide.physical_slide_id
                for b in other.content_bindings
            }
            cross_leaks = s_content_ids & other_manifest_ids
            if cross_leaks:
                raise CrossSlideMovementError(
                    f"Physical slide '{s_slide.physical_slide_id}' contains content IDs {sorted(cross_leaks)} "
                    f"allocated to other physical slides. Cross-slide content movement is prohibited."
                )
            
            # Check for unallocated external content IDs
            extra_ids = s_content_ids - m_content_ids
            if extra_ids:
                raise CrossSlideMovementError(
                    f"Physical slide '{s_slide.physical_slide_id}' contains content IDs {sorted(extra_ids)} "
                    f"not allocated to it in PhysicalSlideManifest. Cross-slide content movement is prohibited."
                )

            # Invariant: All primary content on this physical slide must be mapped
            primary_m_ids = {b.content_id for b in m_slide.content_bindings if b.binding_role == ContentBindingRole.PRIMARY}
            unmapped_primaries = primary_m_ids - s_content_ids
            if unmapped_primaries:
                raise UnmappedPrimaryContentError(
                    f"Physical slide '{s_slide.physical_slide_id}' left primary content unmapped: {sorted(unmapped_primaries)}"
                )

        # 5. Invariant: Stable unique object IDs, zone IDs, and Selection-Pane object names
        seen_zone_ids: set[str] = set()
        seen_object_ids: set[str] = set()
        seen_object_names: set[str] = set()

        for s_slide in deck_structure.slides:
            for zone in s_slide.zones:
                if not zone.zone_id or not zone.zone_id.strip():
                    raise StructureValidationError(f"Slide '{s_slide.physical_slide_id}' has empty zone_id")
                if zone.zone_id in seen_zone_ids:
                    raise StructureValidationError(f"Duplicate zone_id detected: '{zone.zone_id}'")
                seen_zone_ids.add(zone.zone_id)

                for obj in zone.objects:
                    if not obj.object_id or not obj.object_id.strip():
                        raise OrphanObjectError(f"Zone '{zone.zone_id}' contains object with empty object_id")
                    if obj.object_id in seen_object_ids:
                        raise StructureValidationError(f"Duplicate object_id detected: '{obj.object_id}'")
                    seen_object_ids.add(obj.object_id)

                    # Invariant: Selection-Pane friendly object_name must be distinct and unique
                    if not obj.object_name or not obj.object_name.strip():
                        raise StructureValidationError(f"Object '{obj.object_id}' has empty object_name")
                    if obj.object_name == obj.object_id:
                        raise StructureValidationError(
                            f"Object '{obj.object_id}' has identical object_name and object_id. "
                            f"HighView semantic object_id and Selection-Pane object_name must remain distinct."
                        )
                    if obj.object_name in seen_object_names:
                        raise StructureValidationError(f"Duplicate object_name detected: '{obj.object_name}'")
                    seen_object_names.add(obj.object_name)

                    # Invariant: Truthful map editability
                    if obj.kind == ContentKind.MAP:
                        if obj.editability in (EditabilityPolicy.NATIVE_REQUIRED, EditabilityPolicy.NATIVE_PREFERRED):
                            raise StructureValidationError(
                                f"Object '{obj.object_id}' is a MAP but is marked {obj.editability.value}. "
                                f"Raster/composite maps must use RASTER_ALLOWED."
                            )

        # 6. Object Registry verification
        for obj_id in seen_object_ids:
            if obj_id not in deck_structure.object_registry:
                raise OrphanObjectError(f"Object '{obj_id}' is present on a slide but missing from object_registry")

        # 7. Invariant: Zero governance leakage in normal business decks
        if not is_technical_deck:
            cls._check_governance_leakage(deck_structure)

        # 8. Deterministic structure fingerprint
        if deck_structure.structure_fingerprint:
            computed_fp = deck_structure.compute_structure_fingerprint()
            if deck_structure.structure_fingerprint != computed_fp:
                raise StructureValidationError(
                    f"Structure fingerprint mismatch! Stored: {deck_structure.structure_fingerprint}, Computed: {computed_fp}"
                )

    @classmethod
    def _check_no_geometry_or_style_leakage(cls, deck_structure: LayeredDeckStructureSpec) -> None:
        """Recursively scans for forbidden geometry, coordinate, typography size, or styling fields."""
        struct_dict = deck_structure.model_dump()
        found_fields: list[str] = []

        def _traverse(obj: Any, path: str = "") -> None:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    k_lower = str(k).lower()
                    if k_lower in cls.FORBIDDEN_GEOMETRY_AND_STYLE_FIELDS:
                        found_fields.append(f"{path}.{k}" if path else str(k))
                    _traverse(v, f"{path}.{k}" if path else str(k))
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    _traverse(item, f"{path}[{i}]")

        _traverse(struct_dict)
        if found_fields:
            raise PhysicalGeometryLeakageError(
                f"LayeredDeckStructureSpec contains forbidden geometry/styling fields in PPT-L4: {found_fields}. "
                f"Coordinates, EMUs, typography sizing, colors, and layout proportions belong strictly to PPT-L5/L6/L7."
            )

    @classmethod
    def _check_governance_leakage(cls, deck_structure: LayeredDeckStructureSpec) -> None:
        """Audits user-visible strings across all zones and objects for governance jargon leakage."""
        for s in deck_structure.slides:
            # Check slide headline
            cls._scan_text(s.headline, f"Slide '{s.physical_slide_id}' headline")

            for z in s.zones:
                for obj in z.objects:
                    cls._scan_text(obj.headline, f"Object '{obj.object_id}' headline")
                    cls._scan_text(obj.narrative_text, f"Object '{obj.object_id}' narrative_text")

    @classmethod
    def _scan_text(cls, text: str, context: str) -> None:
        if not text:
            return
        for pattern in cls.FORBIDDEN_GOVERNANCE_PATTERNS:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                raise GovernanceLeakageError(
                    f"Internal governance token '{match.group(0)}' leaked into user-visible text at {context}. "
                    f"Business presentations must strictly omit internal pipeline terminology."
                )
