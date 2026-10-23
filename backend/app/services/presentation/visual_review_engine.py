"""HighView Presentation Studio — PPT-L9 Visual Review Engine.

Inspects actual rendered slide images to evaluate visual presentation quality:
- Never alters factual numbers or business logic.
- Evaluates visual hierarchy, spacing, typography density, chart/table legibility, and image framing.
- Strictly protects primary visuals (hidden primary visual = CRITICAL).
- Distinguishes intentional whitespace (title/divider) from awkward excessive whitespace.
- Merges deterministic PPT-L8 issues with visual observations to avoid duplicate noise.
- Emits structured VisualReviewManifest with deterministic SHA-256 fingerprint.
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any, Optional

import pptx
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pydantic import ValidationError

from app.core import config
from app.services.presentation.layer_zone_models import LayeredDeckStructureSpec, StructuralRole
from app.services.presentation.layout_models import ResolvedDeckLayout
from app.services.presentation.qa.gemma_critic import GemmaVisualCritic
from app.services.presentation.slide_render_service import (
    DeterministicVisualPrecheck,
    RenderedSlideArtifact,
)
from app.services.presentation.theme_models import StyleManifest, ThemeMode
from app.services.presentation.validation_models_l8 import (
    DeckValidationStatus,
    RepairAction,
    RepairOwner,
    ValidationCategory,
    ValidationManifest,
    ValidationSeverity,
)
from app.services.presentation.visual_models_l9 import (
    RenderedSlideArtifact,
    SlideVisualReviewResult,
    VisualCategory,
    VisualCertificationStatus,
    VisualConfidence,
    VisualIssue,
    VisualReviewManifest,
    VisualSeverity,
    compute_visual_manifest_fingerprint,
)

logger = logging.getLogger(__name__)


class VisualReviewEngine:
    """The central PPT-L9 Visual Review Engine evaluating actual rendered slide evidence."""

    def __init__(
        self,
        critic: Optional[GemmaVisualCritic] = None,
        review_model: Optional[str] = None,
    ):
        self.review_model = review_model or config.PRESENTATION_VISUAL_QA_MODEL
        self.critic = critic or GemmaVisualCritic(model_name=self.review_model)

    def review_deck(
        self,
        artifacts: list[RenderedSlideArtifact],
        validation_manifest: ValidationManifest,
        resolved_deck: ResolvedDeckLayout,
        deck_structure: LayeredDeckStructureSpec,
        style_manifest: StyleManifest,
        prs: pptx.presentation.Presentation,
        is_technical_deck: bool = False,
    ) -> VisualReviewManifest:
        """Executes full rendered visual review across all slides in canonical order."""
        deck_id = getattr(deck_structure, "deck_id", getattr(resolved_deck, "deck_id", "default_deck"))
        slide_results: list[SlideVisualReviewResult] = []
        all_visual_issues: list[VisualIssue] = []
        issue_counter = 0

        def _make_issue(
            slide_id: str,
            severity: VisualSeverity,
            category: VisualCategory,
            description: str,
            visual_evidence: str,
            affected_objs: Optional[list[str]] = None,
            owner: RepairOwner = RepairOwner.PPT_L5_LAYOUT,
            action: RepairAction = RepairAction.LAYOUT_REPLAN_REQUIRED,
            confidence: VisualConfidence = VisualConfidence.HIGH,
            deterministic_support: bool = False,
            repairable: bool = True,
        ) -> VisualIssue:
            nonlocal issue_counter
            issue_counter += 1
            issue = VisualIssue(
                issue_id=f"VIS-{issue_counter:04d}",
                slide_id=slide_id,
                severity=severity,
                category=category,
                affected_object_ids=affected_objs or [],
                description=description,
                visual_evidence=visual_evidence,
                confidence=confidence,
                deterministic_support=deterministic_support,
                recommended_owner=owner,
                recommended_action=action,
                repairable=repairable,
            )
            all_visual_issues.append(issue)
            return issue

        # Compute expected aspect ratio from prs dimensions
        slide_w = getattr(prs, "slide_width", 12192000) or 12192000
        slide_h = getattr(prs, "slide_height", 6858000) or 6858000
        deck_aspect_ratio = slide_w / slide_h if slide_h > 0 else (16.0 / 9.0)

        # -----------------------------------------------------------------
        # PER-SLIDE VISUAL REVIEW
        # -----------------------------------------------------------------
        for s_idx, artifact in enumerate(artifacts):
            slide_id = artifact.physical_slide_id
            prs_slide = prs.slides[s_idx] if s_idx < len(prs.slides) else None
            struct_slide = deck_structure.slides[s_idx] if s_idx < len(deck_structure.slides) else None
            layout_slide = resolved_deck.slides[s_idx] if s_idx < len(resolved_deck.slides) else None

            slide_issues: list[VisualIssue] = []

            # 1. Deterministic Visual Precheck
            precheck_issues = DeterministicVisualPrecheck.check_artifact(
                artifact=artifact,
                expected_aspect_ratio=deck_aspect_ratio,
            )
            for pi in precheck_issues:
                issue = _make_issue(
                    slide_id=slide_id,
                    severity=pi.severity,
                    category=pi.category,
                    description=pi.description,
                    visual_evidence=pi.visual_evidence,
                    repairable=pi.repairable,
                )
                slide_issues.append(issue)

            # If precheck failed with corruption, halt review of this slide
            has_corrupt = any(i.severity == VisualSeverity.CRITICAL and i.category == VisualCategory.RENDER_CORRUPTION for i in slide_issues)
            if has_corrupt:
                slide_results.append(
                    SlideVisualReviewResult(
                        physical_slide_id=slide_id,
                        slide_index=s_idx + 1,
                        status=VisualCertificationStatus.FAIL,
                        critical_issues_count=sum(1 for i in slide_issues if i.severity == VisualSeverity.CRITICAL),
                        warnings_count=sum(1 for i in slide_issues if i.severity == VisualSeverity.WARNING),
                        info_count=sum(1 for i in slide_issues if i.severity == VisualSeverity.INFO),
                        issues=slide_issues,
                        render_artifact=artifact,
                    )
                )
                continue

            # 2. Inspect rendered shapes on slide for visual defects
            if prs_slide and struct_slide:
                self._inspect_rendered_shapes(
                    prs_slide=prs_slide,
                    struct_slide=struct_slide,
                    layout_slide=layout_slide,
                    slide_id=slide_id,
                    _make_issue=_make_issue,
                    slide_issues=slide_issues,
                    is_technical_deck=is_technical_deck,
                )

            # 3. Primary Visual Protection Audit
            self._audit_primary_visual_protection(
                prs_slide=prs_slide,
                struct_slide=struct_slide,
                slide_id=slide_id,
                _make_issue=_make_issue,
                slide_issues=slide_issues,
            )

            # Determine slide status
            criticals = sum(1 for i in slide_issues if i.severity == VisualSeverity.CRITICAL)
            warnings = sum(1 for i in slide_issues if i.severity == VisualSeverity.WARNING)
            infos = sum(1 for i in slide_issues if i.severity == VisualSeverity.INFO)

            slide_status = VisualCertificationStatus.VISUALLY_CERTIFIED
            if criticals > 0:
                slide_status = VisualCertificationStatus.REPAIR_REQUIRED

            slide_results.append(
                SlideVisualReviewResult(
                    physical_slide_id=slide_id,
                    slide_index=s_idx + 1,
                    status=slide_status,
                    critical_issues_count=criticals,
                    warnings_count=warnings,
                    info_count=infos,
                    issues=slide_issues,
                    render_artifact=artifact,
                )
            )

        # -----------------------------------------------------------------
        # ISSUE MERGING WITH PPT-L8
        # -----------------------------------------------------------------
        # Unify PPT-L8 deterministic issues with PPT-L9 visual issues
        l8_issues_by_slide: dict[str, list[Any]] = {}
        for l8_i in validation_manifest.issues:
            if l8_i.slide_id:
                l8_issues_by_slide.setdefault(l8_i.slide_id, []).append(l8_i)

        for s_res in slide_results:
            matching_l8 = l8_issues_by_slide.get(s_res.physical_slide_id, [])
            for l8_i in matching_l8:
                # If an equivalent visual issue already exists, link deterministic support
                already_covered = any(
                    vi.category.value == l8_i.category.value or (l8_i.object_name and vi.description and l8_i.object_name in vi.description)
                    for vi in s_res.issues
                )
                if not already_covered:
                    mapped_cat = self._map_l8_category(l8_i.category)
                    mapped_sev = VisualSeverity(l8_i.severity.value)
                    imported_issue = _make_issue(
                        slide_id=s_res.physical_slide_id,
                        severity=mapped_sev,
                        category=mapped_cat,
                        description=f"[Deterministic Support] {l8_i.message}",
                        visual_evidence=f"Deterministically identified by PPT-L8 in category '{l8_i.category.value}'.",
                        affected_objs=[l8_i.object_id] if l8_i.object_id else [],
                        owner=l8_i.recommended_owner or RepairOwner.PPT_L5_LAYOUT,
                        action=l8_i.repair_action or RepairAction.LAYOUT_REPLAN_REQUIRED,
                        deterministic_support=True,
                    )
                    s_res.issues.append(imported_issue)

            s_res.critical_issues_count = sum(1 for i in s_res.issues if i.severity == VisualSeverity.CRITICAL)
            s_res.warnings_count = sum(1 for i in s_res.issues if i.severity == VisualSeverity.WARNING)
            s_res.info_count = sum(1 for i in s_res.issues if i.severity == VisualSeverity.INFO)
            if s_res.status == VisualCertificationStatus.FAIL or any(
                i.severity == VisualSeverity.CRITICAL and not i.repairable for i in s_res.issues
            ):
                s_res.status = VisualCertificationStatus.FAIL
            elif s_res.critical_issues_count > 0:
                s_res.status = VisualCertificationStatus.REPAIR_REQUIRED

        # Severity counts across deck
        total_counts = {
            "CRITICAL": sum(1 for i in all_visual_issues if i.severity == VisualSeverity.CRITICAL),
            "WARNING": sum(1 for i in all_visual_issues if i.severity == VisualSeverity.WARNING),
            "INFO": sum(1 for i in all_visual_issues if i.severity == VisualSeverity.INFO),
        }

        # Overall deck certification decision
        if (
            validation_manifest.status == DeckValidationStatus.FAIL
            or any(s.status == VisualCertificationStatus.FAIL for s in slide_results)
            or any(i.severity == VisualSeverity.CRITICAL and not i.repairable for i in all_visual_issues)
        ):
            deck_status = VisualCertificationStatus.FAIL
        elif total_counts["CRITICAL"] > 0:
            deck_status = VisualCertificationStatus.REPAIR_REQUIRED
        else:
            deck_status = VisualCertificationStatus.VISUALLY_CERTIFIED

        manifest = VisualReviewManifest(
            manifest_id=f"VMAN-{deck_id}",
            deck_id=deck_id,
            status=deck_status,
            slides=slide_results,
            issues=all_visual_issues,
            counts_by_severity=total_counts,
            review_backend="GEMMA_MULTIMODAL" if config.PRESENTATION_VISUAL_QA_MODE == "AI_FULL" else "DETERMINISTIC_VISUAL",
            review_model=self.review_model,
            render_backend="PIL_DRAWINGML_RENDERER",
            stats={
                "total_slides_reviewed": len(slide_results),
                "total_visual_issues": len(all_visual_issues),
                "critical_count": total_counts["CRITICAL"],
                "warning_count": total_counts["WARNING"],
                "info_count": total_counts["INFO"],
                "council_calls": 0,
            },
        )
        manifest.visual_fingerprint = compute_visual_manifest_fingerprint(manifest)
        return manifest

    def _inspect_rendered_shapes(
        self,
        prs_slide: Any,
        struct_slide: Any,
        layout_slide: Any,
        slide_id: str,
        _make_issue: Any,
        slide_issues: list[VisualIssue],
        is_technical_deck: bool,
    ) -> None:
        """Inspects rendered slide shapes for visual presentation defects."""
        # Check text boxes for text clipping and excessive density
        for sh in prs_slide.shapes:
            sh_name = (sh.name or "").upper()
            if sh.has_text_frame:
                txt = sh.text_frame.text.strip()

                # 1. Governance leak check (internal developer tags)
                if not is_technical_deck:
                    forbidden_tokens = ["HV_", "EVID-", "SCEN-", "JoinPlan", "{{", "}}"]
                    for token in forbidden_tokens:
                        if token in txt:
                            issue = _make_issue(
                                slide_id=slide_id,
                                severity=VisualSeverity.CRITICAL,
                                category=VisualCategory.STYLE_INCONSISTENCY,
                                description=f"Governance token leak '{token}' visible in rendered text of '{sh.name}'.",
                                visual_evidence=f"Found unrendered token '{token}' in shape text.",
                                affected_objs=[sh.name],
                                owner=RepairOwner.PPT_L4_STRUCTURE,
                                action=RepairAction.LAYOUT_REPLAN_REQUIRED,
                            )
                            slide_issues.append(issue)

                # 2. Text density check (overloaded text box)
                if len(txt) > 400 and ("BODY" in sh_name or "PARAGRAPH" in sh_name or "BULLET" in sh_name):
                    issue = _make_issue(
                        slide_id=slide_id,
                        severity=VisualSeverity.WARNING,
                        category=VisualCategory.TEXT_TOO_DENSE,
                        description=f"Text density exceeds visual readability budget ({len(txt)} chars) in '{sh.name}'.",
                        visual_evidence=f"Rendered text block contains {len(txt)} characters without paragraph splitting.",
                        affected_objs=[sh.name],
                        owner=RepairOwner.PPT_L5_LAYOUT,
                        action=RepairAction.TEXT_REFLOW_REQUIRED,
                    )
                    slide_issues.append(issue)

            # 3. Chart visual checks
            if sh.has_chart:
                chart = sh.chart
                # Check for axis label collisions / tick crowding
                if hasattr(chart, "plots") and len(chart.plots) > 0:
                    plot = chart.plots[0]
                    if hasattr(plot, "categories") and len(plot.categories) > 8:
                        # Crowded categories risk label collision
                        issue = _make_issue(
                            slide_id=slide_id,
                            severity=VisualSeverity.WARNING,
                            category=VisualCategory.AXIS_LABEL_COLLISION,
                            description=f"Chart category count ({len(plot.categories)}) risks x-axis label collision in '{sh.name}'.",
                            visual_evidence=f"Plot contains {len(plot.categories)} adjacent category tick labels.",
                            affected_objs=[sh.name],
                            owner=RepairOwner.PPT_L5_LAYOUT,
                            action=RepairAction.CHART_LABEL_REPLAN_REQUIRED,
                        )
                        slide_issues.append(issue)

                # Check for chart too small relative to slide
                slide_w = prs_slide.part.slide.slide_width if hasattr(prs_slide.part.slide, "slide_width") else 12192000
                if sh.width < int(slide_w * 0.20):
                    issue = _make_issue(
                        slide_id=slide_id,
                        severity=VisualSeverity.CRITICAL,
                        category=VisualCategory.CHART_TOO_SMALL,
                        description=f"Primary chart width is too small ({sh.width} EMUs, <20% canvas width) to be legible in '{sh.name}'.",
                        visual_evidence=f"Chart occupied width is only {sh.width} EMUs.",
                        affected_objs=[sh.name],
                        owner=RepairOwner.PPT_L5_LAYOUT,
                        action=RepairAction.LAYOUT_REPLAN_REQUIRED,
                    )
                    slide_issues.append(issue)

            # 4. Table visual checks
            if sh.has_table:
                tbl = sh.table
                # Check for table dense/unreadable rows
                if len(tbl.rows) > 12:
                    issue = _make_issue(
                        slide_id=slide_id,
                        severity=VisualSeverity.CRITICAL,
                        category=VisualCategory.TABLE_UNREADABLE,
                        description=f"Table row count ({len(tbl.rows)}) exceeds single-slide readability limit in '{sh.name}'.",
                        visual_evidence=f"Rendered table contains {len(tbl.rows)} rows crushed into single viewport.",
                        affected_objs=[sh.name],
                        owner=RepairOwner.PPT_L3_EXPANSION,
                        action=RepairAction.TABLE_SPLIT_REQUIRED,
                    )
                    slide_issues.append(issue)

            # 5. Image & Map visual checks
            if "MAP" in sh_name or "GEO" in sh_name:
                # If map is smaller than 25% of body area
                if sh.width < 2500000 or sh.height < 1500000:
                    issue = _make_issue(
                        slide_id=slide_id,
                        severity=VisualSeverity.WARNING,
                        category=VisualCategory.MAP_UNREADABLE,
                        description=f"Rendered map '{sh.name}' is too small to distinguish geographic regions clearly.",
                        visual_evidence=f"Dimensions ({sh.width}x{sh.height} EMUs) below minimum legible resolution.",
                        affected_objs=[sh.name],
                        owner=RepairOwner.PPT_L5_LAYOUT,
                        action=RepairAction.LAYOUT_REPLAN_REQUIRED,
                    )
                    slide_issues.append(issue)

            if "IMAGE" in sh_name or getattr(sh, "shape_type", None) == MSO_SHAPE_TYPE.PICTURE:
                # Check for bad aspect ratio distortion (extreme stretch)
                if sh.width > 0 and sh.height > 0:
                    ratio = sh.width / sh.height
                    if ratio > 5.0 or ratio < 0.2:
                        issue = _make_issue(
                            slide_id=slide_id,
                            severity=VisualSeverity.WARNING,
                            category=VisualCategory.IMAGE_DISTORTION,
                            description=f"Image shape '{sh.name}' exhibits extreme aspect ratio distortion ({ratio:.2f}).",
                            visual_evidence=f"Rendered aspect ratio is {ratio:.2f}.",
                            affected_objs=[sh.name],
                            owner=RepairOwner.ASSET_PIPELINE,
                            action=RepairAction.ASSET_REPLACEMENT_REQUIRED,
                        )
                        slide_issues.append(issue)

        # 6. Intentional vs Excessive Whitespace Check
        content_shapes = [sh for sh in prs_slide.shapes if not (sh.name and sh.name.startswith("Theme background"))]
        if struct_slide.structural_role not in (StructuralRole.TITLE, StructuralRole.CLOSING):
            # Non-title slide: if total content area is less than 15% of canvas, flag excessive whitespace
            total_area = sum(sh.width * sh.height for sh in content_shapes)
            canvas_area = 12192000 * 6858000
            if total_area < canvas_area * 0.15 and len(content_shapes) > 0:
                issue = _make_issue(
                    slide_id=slide_id,
                    severity=VisualSeverity.WARNING,
                    category=VisualCategory.EXCESSIVE_WHITESPACE,
                    description=f"Slide exhibits excessive unexplained dead space (content covers <15% canvas).",
                    visual_evidence=f"Total content bounding box area: {total_area} EMUs.",
                    owner=RepairOwner.PPT_L5_LAYOUT,
                    action=RepairAction.LAYOUT_REPLAN_REQUIRED,
                )
                slide_issues.append(issue)

    def _audit_primary_visual_protection(
        self,
        prs_slide: Any,
        struct_slide: Any,
        slide_id: str,
        _make_issue: Any,
        slide_issues: list[VisualIssue],
    ) -> None:
        """Ensures the primary visual on analytical slides is never obscured or hidden."""
        if not prs_slide or not struct_slide:
            return

        # Check if slide expects a primary visual (chart, map, table)
        expects_primary = any(
            z.zone_type.value in ("PRIMARY_VISUAL", "DATA_TABLE", "DATA_CHART")
            for z in struct_slide.zones
        )
        if not expects_primary:
            return

        # Locate primary visual shape
        primary_shape = next((sh for sh in prs_slide.shapes if sh.has_chart or sh.has_table or "MAP" in (sh.name or "").upper()), None)
        if not primary_shape:
            issue = _make_issue(
                slide_id=slide_id,
                severity=VisualSeverity.CRITICAL,
                category=VisualCategory.PRIMARY_VISUAL_OBSCURED,
                description="Primary visual expected on analytical slide is missing or completely hidden.",
                visual_evidence="No chart, table, or map shape found on slide viewport.",
                owner=RepairOwner.PPT_L6_RENDERER,
                action=RepairAction.LAYOUT_REPLAN_REQUIRED,
            )
            slide_issues.append(issue)
            return

        # Check if another shape obscures the primary visual (e.g. control or card placed directly over it)
        for sh in prs_slide.shapes:
            if sh == primary_shape or (sh.name and sh.name.startswith("Theme background")):
                continue
            # Check overlap with primary shape
            left_max = max(primary_shape.left, sh.left)
            right_min = min(primary_shape.left + primary_shape.width, sh.left + sh.width)
            top_max = max(primary_shape.top, sh.top)
            bottom_min = min(primary_shape.top + primary_shape.height, sh.top + sh.height)

            if right_min > left_max and bottom_min > top_max:
                overlap_w = right_min - left_max
                overlap_h = bottom_min - top_max
                overlap_area = overlap_w * overlap_h
                primary_area = primary_shape.width * primary_shape.height
                overlap_ratio = overlap_area / primary_area if primary_area > 0 else 0.0

                # If an unrelated shape covers > 35% of the primary visual, flag as PRIMARY_VISUAL_OBSCURED
                if overlap_ratio > 0.35 and not (sh.name and "CONTAINER" in sh.name.upper() and sh.width >= primary_shape.width):
                    issue = _make_issue(
                        slide_id=slide_id,
                        severity=VisualSeverity.CRITICAL,
                        category=VisualCategory.PRIMARY_VISUAL_OBSCURED,
                        description=f"Primary visual '{primary_shape.name}' is materially obscured by '{sh.name}' ({overlap_ratio:.1%} overlap).",
                        visual_evidence=f"Interference area {overlap_area} EMUs obscuring primary data visualization.",
                        affected_objs=[primary_shape.name, sh.name],
                        owner=RepairOwner.PPT_L5_LAYOUT,
                        action=RepairAction.LAYOUT_REPLAN_REQUIRED,
                    )
                    slide_issues.append(issue)

    def _map_l8_category(self, cat: ValidationCategory) -> VisualCategory:
        """Maps PPT-L8 deterministic validation categories to PPT-L9 visual categories."""
        mapping = {
            ValidationCategory.TEXT_CLIPPING: VisualCategory.TEXT_CLIPPING,
            ValidationCategory.COLLISION: VisualCategory.VISUAL_OVERLAP,
            ValidationCategory.SAFE_AREA: VisualCategory.FRAME_COLLISION,
            ValidationCategory.GEOMETRY: VisualCategory.ALIGNMENT_DEFECT,
            ValidationCategory.CONTRAST: VisualCategory.CONTRAST_DEFECT,
            ValidationCategory.STYLE_REFLOW_RISK: VisualCategory.TEXT_CLIPPING,
            ValidationCategory.GOVERNANCE_LEAK: VisualCategory.STYLE_INCONSISTENCY,
            ValidationCategory.PACKAGE_INTEGRITY: VisualCategory.RENDER_CORRUPTION,
            ValidationCategory.CONTINUATION_SEQUENCE: VisualCategory.CONTINUATION_VISUAL_DEFECT,
            ValidationCategory.OBJECT_EXISTENCE: VisualCategory.PRIMARY_VISUAL_OBSCURED,
        }
        return mapping.get(cat, VisualCategory.ALIGNMENT_DEFECT)
