"""HighView Presentation Studio — PPT-L3 Slide Expansion Engine.

Expands a validated DeckStoryPlan into a stable, deterministic PhysicalSlideManifest.
Translates logical story units into physical slide instances while enforcing:
- Split-over-shrink
- Contiguous continuation chains
- Semantic, deterministic physical IDs (e.g. POPULATION_DENSITY-01, POPULATION_DENSITY-02)
- Zero primary content loss
- Zero layout geometry, coordinates, typography sizing, or rendering logic
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Optional

from .content_models import ContentKind, PresentationContentPackage
from .manifest_models import (
    ContentDensity,
    DeckLengthPolicy,
    ExpansionReason,
    LogicalTopicMapping,
    ManifestValidationError,
    PhysicalSlideInstance,
    PhysicalSlideManifest,
    PhysicalSlideManifestValidator,
    PresentationPreflightResult,
    SectionMapping,
)
from .preflight_engine import PresentationPreflightEngine
from .story_models import (
    ContentBinding,
    ContentBindingRole,
    DeckStoryPlan,
    LogicalSlidePlan,
    StructuralRole,
)

logger = logging.getLogger(__name__)


class SlideExpansionEngine:
    """Deterministic expansion engine converting DeckStoryPlan into PhysicalSlideManifest."""

    def __init__(
        self,
        preflight_engine: Optional[PresentationPreflightEngine] = None,
        max_slides_per_topic: int = 3,
        max_total_slides: int = 30
    ):
        self.preflight_engine = preflight_engine or PresentationPreflightEngine(
            max_slides_per_topic=max_slides_per_topic,
            max_total_slides=max_total_slides
        )
        self.max_slides_per_topic = max_slides_per_topic
        self.max_total_slides = max_total_slides

    def expand(
        self,
        story_plan: DeckStoryPlan,
        content_pkg: PresentationContentPackage,
        preflight_result: Optional[PresentationPreflightResult] = None,
        target_slide_count: Optional[int] = None,
        length_policy: DeckLengthPolicy = DeckLengthPolicy.STANDARD,
        metadata: Optional[dict[str, Any]] = None
    ) -> PhysicalSlideManifest:
        """Expands a DeckStoryPlan into a verified PhysicalSlideManifest.
        
        Args:
            story_plan: Validated DeckStoryPlan.
            content_pkg: Source PresentationContentPackage.
            preflight_result: Optional pre-computed preflight result.
            target_slide_count: Optional user-requested slide count.
            length_policy: Target deck length policy.
            metadata: Optional expansion metadata.
            
        Returns:
            PhysicalSlideManifest conforming to all architectural invariants.
        """
        # 1. Run preflight if not supplied
        if preflight_result is None:
            preflight_result = self.preflight_engine.preflight(
                story_plan=story_plan,
                content_pkg=content_pkg,
                target_slide_count=target_slide_count,
                length_policy=length_policy,
                metadata=metadata
            )

        preflight_map = {r.logical_slide_id: r for r in preflight_result.logical_topic_results}
        items_lookup = {it.content_id: it for it in content_pkg.items}
        kpis_lookup = {k.content_id: k for k in content_pkg.global_kpis}
        all_pkg_lookup = {**items_lookup, **kpis_lookup}

        physical_slides: list[PhysicalSlideInstance] = []
        topic_mappings: list[LogicalTopicMapping] = []
        section_slides_map: dict[str, list[PhysicalSlideInstance]] = {}

        # 2. Iterate through logical slides in story narrative order
        current_seq = 1
        for l_slide in story_plan.logical_slides:
            pf_res = preflight_map.get(l_slide.logical_slide_id)
            target_slides = pf_res.recommended_physical_slides if pf_res else 1
            expansion_reason = pf_res.expansion_reason if pf_res else ExpansionReason.NONE

            # Generate physical slides for this logical slide
            p_instances = self._expand_logical_slide(
                l_slide=l_slide,
                target_physical_count=target_slides,
                expansion_reason=expansion_reason,
                start_sequence=current_seq,
                all_pkg_lookup=all_pkg_lookup
            )

            physical_ids = [ps.physical_slide_id for ps in p_instances]
            topic_mappings.append(
                LogicalTopicMapping(
                    logical_slide_id=l_slide.logical_slide_id,
                    semantic_topic=l_slide.semantic_topic,
                    structural_role=l_slide.structural_role,
                    physical_slide_ids=physical_ids,
                    expansion_reason=expansion_reason,
                    is_split=(len(p_instances) > 1)
                )
            )

            for ps in p_instances:
                physical_slides.append(ps)
                sec_name = ps.section_name or "General"
                section_slides_map.setdefault(sec_name, []).append(ps)

            current_seq += len(p_instances)

        # 3. Assemble section mappings for TOC and navigation
        section_mappings: list[SectionMapping] = []
        sec_idx = 1
        for sec_name in story_plan.sections:
            sec_slides = section_slides_map.get(sec_name, [])
            if sec_slides:
                section_mappings.append(
                    SectionMapping(
                        section_id=f"SEC-{sec_idx:02d}",
                        section_name=sec_name,
                        first_physical_slide_id=sec_slides[0].physical_slide_id,
                        last_physical_slide_id=sec_slides[-1].physical_slide_id,
                        first_sequence_index=sec_slides[0].sequence_index,
                        last_sequence_index=sec_slides[-1].sequence_index,
                        physical_count=len(sec_slides)
                    )
                )
                sec_idx += 1

        # Also handle any slides whose section was not in story_plan.sections
        for sec_name, sec_slides in section_slides_map.items():
            if not any(sm.section_name == sec_name for sm in section_mappings) and sec_slides:
                section_mappings.append(
                    SectionMapping(
                        section_id=f"SEC-{sec_idx:02d}",
                        section_name=sec_name,
                        first_physical_slide_id=sec_slides[0].physical_slide_id,
                        last_physical_slide_id=sec_slides[-1].physical_slide_id,
                        first_sequence_index=sec_slides[0].sequence_index,
                        last_sequence_index=sec_slides[-1].sequence_index,
                        physical_count=len(sec_slides)
                    )
                )
                sec_idx += 1

        # 4. Create PhysicalSlideManifest
        manifest_id = f"MANIFEST-{story_plan.plan_id}"
        manifest = PhysicalSlideManifest(
            manifest_id=manifest_id,
            deck_story_plan_id=story_plan.plan_id,
            slides=physical_slides,
            logical_topic_mappings=topic_mappings,
            section_mappings=section_mappings,
            preflight_summary=preflight_result,
            manifest_version=1,
            metadata=metadata or {}
        )

        # 5. Compute deterministic manifest fingerprint
        manifest.manifest_fingerprint = manifest.compute_manifest_fingerprint()

        # 6. Validate manifest against all architectural invariants
        PhysicalSlideManifestValidator.validate(manifest, story_plan, content_pkg)

        return manifest

    def _expand_logical_slide(
        self,
        l_slide: LogicalSlidePlan,
        target_physical_count: int,
        expansion_reason: ExpansionReason,
        start_sequence: int,
        all_pkg_lookup: dict[str, Any]
    ) -> list[PhysicalSlideInstance]:
        """Expands a single logical slide into 1..K physical slide instances."""
        base_id = l_slide.logical_slide_id.strip()

        # Single physical slide case
        if target_physical_count <= 1 or not l_slide.allow_split or len(l_slide.content_bindings) <= 1:
            p_id = f"{base_id}-01"
            return [
                PhysicalSlideInstance(
                    physical_slide_id=p_id,
                    logical_slide_id=l_slide.logical_slide_id,
                    semantic_topic=l_slide.semantic_topic,
                    structural_role=l_slide.structural_role,
                    sequence_index=start_sequence,
                    continuation_index=1,
                    is_continuation=False,
                    content_bindings=list(l_slide.content_bindings),
                    slide_purpose=l_slide.purpose,
                    headline=l_slide.headline,
                    section_name=l_slide.section_name,
                    estimated_density=ContentDensity.MEDIUM,
                    expansion_reason=ExpansionReason.NONE,
                    primary_owner_slide_id=p_id
                )
            ]

        # Multi-slide expansion case (SPLIT BEFORE SHRINK)
        # Distribute content across physical slides
        split_bindings = self._partition_bindings(
            bindings=l_slide.content_bindings,
            target_count=target_physical_count,
            all_pkg_lookup=all_pkg_lookup
        )

        instances: list[PhysicalSlideInstance] = []
        for idx, b_group in enumerate(split_bindings, start=1):
            p_id = f"{base_id}-{idx:02d}"
            is_cont = (idx > 1)
            headline_text = l_slide.headline if idx == 1 else f"{l_slide.headline} (Continuation)"
            purpose_text = l_slide.purpose if idx == 1 else f"Detailed continuation for {l_slide.semantic_topic}"

            instances.append(
                PhysicalSlideInstance(
                    physical_slide_id=p_id,
                    logical_slide_id=l_slide.logical_slide_id,
                    semantic_topic=l_slide.semantic_topic,
                    structural_role=l_slide.structural_role,
                    sequence_index=start_sequence + idx - 1,
                    continuation_index=idx,
                    is_continuation=is_cont,
                    content_bindings=b_group,
                    slide_purpose=purpose_text,
                    headline=headline_text,
                    section_name=l_slide.section_name,
                    estimated_density=ContentDensity.MEDIUM,
                    expansion_reason=expansion_reason,
                    primary_owner_slide_id=p_id
                )
            )

        return instances

    def _partition_bindings(
        self,
        bindings: list[ContentBinding],
        target_count: int,
        all_pkg_lookup: dict[str, Any]
    ) -> list[list[ContentBinding]]:
        """Partitions content bindings across target continuation slides preserving primary content."""
        if not bindings:
            return [[] for _ in range(target_count)]

        # Classify bindings
        primary_visuals: list[ContentBinding] = []
        primary_others: list[ContentBinding] = []
        supporting_tables: list[ContentBinding] = []
        supporting_others: list[ContentBinding] = []
        optional_items: list[ContentBinding] = []

        for b in bindings:
            it = all_pkg_lookup.get(b.content_id)
            kind = it.kind if it else ContentKind.NARRATIVE_INSIGHT
            if b.binding_role == ContentBindingRole.PRIMARY:
                if kind in (ContentKind.MAP, ContentKind.CHART):
                    primary_visuals.append(b)
                else:
                    primary_others.append(b)
            elif b.binding_role == ContentBindingRole.SUPPORTING:
                if kind == ContentKind.TABLE:
                    supporting_tables.append(b)
                else:
                    supporting_others.append(b)
            else:
                optional_items.append(b)

        partitions: list[list[ContentBinding]] = [[] for _ in range(target_count)]

        # Slide 1: Primary hero visual + primary other
        if primary_visuals:
            partitions[0].append(primary_visuals[0])
            for pv in primary_visuals[1:]:
                # Subsequent primary visuals go to subsequent continuation slides
                placed = False
                for p_idx in range(1, target_count):
                    if not any(
                        all_pkg_lookup.get(x.content_id) and all_pkg_lookup[x.content_id].kind in (ContentKind.MAP, ContentKind.CHART)
                        for x in partitions[p_idx]
                    ):
                        partitions[p_idx].append(pv)
                        placed = True
                        break
                if not placed:
                    partitions[-1].append(pv)
        elif primary_others:
            partitions[0].append(primary_others[0])
            for po in primary_others[1:]:
                partitions[1 % target_count].append(po)

        # Supporting tables go to continuation slides (Slide 2+)
        for st in supporting_tables:
            if target_count >= 2:
                partitions[1].append(st)
            else:
                partitions[0].append(st)

        # Supporting others and remaining primary items
        for so in supporting_others + primary_others:
            if not any(so.content_id == b.content_id for group in partitions for b in group):
                # Place on slide with fewest bindings
                min_group = min(range(target_count), key=lambda i: len(partitions[i]))
                partitions[min_group].append(so)

        # Optional items
        for opt in optional_items:
            if not any(opt.content_id == b.content_id for group in partitions for b in group):
                partitions[-1].append(opt)

        # Guarantee every single binding is present
        for b in bindings:
            if not any(b.content_id == item.content_id for group in partitions for item in group):
                partitions[0].append(b)

        # Filter out empty trailing partitions if content was insufficient to fill all target partitions
        non_empty = [p for p in partitions if p]
        return non_empty if non_empty else [list(bindings)]

    def expand_late_split(
        self,
        current_manifest: PhysicalSlideManifest,
        offending_physical_slide_id: str,
        revision_reason: str,
        story_plan: DeckStoryPlan,
        content_pkg: PresentationContentPackage
    ) -> PhysicalSlideManifest:
        """Controlled late split revision contract for layout-stage escalation.
        
        When a downstream layout engine encounters physical overflow, it escalates
        to SlideExpansionEngine to issue an authoritative revised PhysicalSlideManifest.
        Layout engines never create untracked slides directly.
        """
        target_slide_idx = -1
        for idx, s in enumerate(current_manifest.slides):
            if s.physical_slide_id == offending_physical_slide_id:
                target_slide_idx = idx
                break

        if target_slide_idx == -1:
            raise ManifestValidationError(
                f"Cannot perform late split: physical_slide_id '{offending_physical_slide_id}' not found in manifest"
            )

        offending_slide = current_manifest.slides[target_slide_idx]
        if len(offending_slide.content_bindings) <= 1:
            # Cannot split a single binding
            raise ManifestValidationError(
                f"Cannot split slide '{offending_physical_slide_id}': contains only {len(offending_slide.content_bindings)} binding"
            )

        # Split content bindings of the offending slide into 2
        half = len(offending_slide.content_bindings) // 2
        b_part1 = offending_slide.content_bindings[:half]
        b_part2 = offending_slide.content_bindings[half:]

        # Create updated slides
        new_slides: list[PhysicalSlideInstance] = []
        for idx, s in enumerate(current_manifest.slides):
            if idx < target_slide_idx:
                new_slides.append(s)
            elif idx == target_slide_idx:
                # Part 1 retains existing ID or becomes -01
                p1 = copy.deepcopy(s)
                p1.content_bindings = b_part1
                p1.expansion_reason = ExpansionReason.LATE_SPLIT_REQUESTED
                new_slides.append(p1)

                # Part 2 gets continuation ID
                base_id = s.logical_slide_id
                next_cont = s.continuation_index + 1
                p2_id = f"{base_id}-{next_cont:02d}"
                p2 = PhysicalSlideInstance(
                    physical_slide_id=p2_id,
                    logical_slide_id=s.logical_slide_id,
                    semantic_topic=s.semantic_topic,
                    structural_role=s.structural_role,
                    sequence_index=s.sequence_index + 1,
                    continuation_index=next_cont,
                    is_continuation=True,
                    content_bindings=b_part2,
                    slide_purpose=f"Late split continuation for {s.semantic_topic}",
                    headline=f"{s.headline} (Continuation)",
                    section_name=s.section_name,
                    estimated_density=ContentDensity.MEDIUM,
                    expansion_reason=ExpansionReason.LATE_SPLIT_REQUESTED,
                    primary_owner_slide_id=p2_id
                )
                new_slides.append(p2)
            else:
                # Subsequent slides get their sequence index shifted by +1
                shifted = copy.deepcopy(s)
                shifted.sequence_index += 1
                new_slides.append(shifted)

        # Update mappings
        updated_mappings: list[LogicalTopicMapping] = []
        for m in current_manifest.logical_topic_mappings:
            if m.logical_slide_id == offending_slide.logical_slide_id:
                phys_ids = [ps.physical_slide_id for ps in new_slides if ps.logical_slide_id == m.logical_slide_id]
                updated_mappings.append(
                    LogicalTopicMapping(
                        logical_slide_id=m.logical_slide_id,
                        semantic_topic=m.semantic_topic,
                        structural_role=m.structural_role,
                        physical_slide_ids=phys_ids,
                        expansion_reason=ExpansionReason.LATE_SPLIT_REQUESTED,
                        is_split=True
                    )
                )
            else:
                updated_mappings.append(m)

        # Re-derive section mappings
        sec_slides_map: dict[str, list[PhysicalSlideInstance]] = {}
        for ps in new_slides:
            sec_slides_map.setdefault(ps.section_name or "General", []).append(ps)

        updated_sections: list[SectionMapping] = []
        sec_idx = 1
        for sec_name in story_plan.sections:
            sec_slides = sec_slides_map.get(sec_name, [])
            if sec_slides:
                updated_sections.append(
                    SectionMapping(
                        section_id=f"SEC-{sec_idx:02d}",
                        section_name=sec_name,
                        first_physical_slide_id=sec_slides[0].physical_slide_id,
                        last_physical_slide_id=sec_slides[-1].physical_slide_id,
                        first_sequence_index=sec_slides[0].sequence_index,
                        last_sequence_index=sec_slides[-1].sequence_index,
                        physical_count=len(sec_slides)
                    )
                )
                sec_idx += 1

        revised_manifest = PhysicalSlideManifest(
            manifest_id=f"{current_manifest.manifest_id}-REV{current_manifest.manifest_version + 1}",
            deck_story_plan_id=current_manifest.deck_story_plan_id,
            slides=new_slides,
            logical_topic_mappings=updated_mappings,
            section_mappings=updated_sections,
            preflight_summary=current_manifest.preflight_summary,
            manifest_version=current_manifest.manifest_version + 1,
            parent_manifest_fingerprint=current_manifest.manifest_fingerprint,
            revision_reason=revision_reason,
            metadata=current_manifest.metadata
        )
        revised_manifest.manifest_fingerprint = revised_manifest.compute_manifest_fingerprint()

        PhysicalSlideManifestValidator.validate(revised_manifest, story_plan, content_pkg)
        return revised_manifest
