"""HighView Presentation Studio — PPT-L9 Bounded Repair Orchestrator.

Orchestrates controlled, bounded repairs for visual defects identified in PPT-L9:
- Strictly enforces maximum repair attempts (MAX_VISUAL_REPAIR_ATTEMPTS = 2).
- Never mutates business numbers, calculations, table data, or story logic.
- Routes repairs through authoritative upstream owners (PPT-L3, PPT-L5, PPT-L6, PPT-L7).
- Mandates post-repair PPT-L8 deterministic revalidation before re-rendering.
- Performs localized re-rendering and targeted re-review.
- Detects regressions and prevents infinite retry loops.
- Emits comprehensive VisualRepairHistory ledger.
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Optional

import pptx

from app.services.presentation.content_models import PresentationContentPackage
from app.services.presentation.deterministic_validation_engine import DeterministicValidationEngine
from app.services.presentation.layer_zone_models import LayeredDeckStructureSpec
from app.services.presentation.layout_models import ResolvedDeckLayout
from app.services.presentation.slide_render_service import SlideRenderService
from app.services.presentation.theme_models import StyleManifest
from app.services.presentation.validation_models_l8 import (
    DeckValidationStatus,
    RepairAction,
    RepairOwner,
    ValidationManifest,
)
from app.services.presentation.visual_models_l9 import (
    RepairApprovalLevel,
    VisualCategory,
    VisualCertificationStatus,
    VisualIssue,
    VisualRepairHistory,
    VisualReviewManifest,
    VisualSeverity,
)

logger = logging.getLogger(__name__)

# Strict hard cap on visual repair loop iterations
MAX_VISUAL_REPAIR_ATTEMPTS = 2


class RepairDecisionEngine:
    """Evaluates whether an identified visual issue is eligible for automatic bounded repair."""

    @classmethod
    def evaluate_approval_level(cls, issue: VisualIssue) -> RepairApprovalLevel:
        """Determines the safety tier for executing a proposed repair action."""
        if not issue.repairable:
            return RepairApprovalLevel.NOT_ALLOWED

        # Safe automatic repair actions
        auto_safe_actions = {
            RepairAction.LAYOUT_REPLAN_REQUIRED,
            RepairAction.TEXT_REFLOW_REQUIRED,
            RepairAction.CHART_LABEL_REPLAN_REQUIRED,
            RepairAction.TABLE_SPLIT_REQUIRED,
            RepairAction.STYLE_ADJUSTMENT_REQUIRED,
            RepairAction.RENDER_RETRY_REQUIRED,
        }

        if issue.recommended_action in auto_safe_actions:
            return RepairApprovalLevel.AUTO_SAFE

        return RepairApprovalLevel.REQUIRES_HUMAN


class BoundedRepairOrchestrator:
    """Coordinates the visual repair loop across upstream owners, revalidation, and re-rendering."""

    def __init__(
        self,
        render_service: Optional[SlideRenderService] = None,
        max_attempts: int = MAX_VISUAL_REPAIR_ATTEMPTS,
    ):
        self.render_service = render_service or SlideRenderService()
        self.max_attempts = max_attempts

    def execute_bounded_repairs(
        self,
        initial_manifest: VisualReviewManifest,
        initial_l8_manifest: ValidationManifest,
        prs: pptx.presentation.Presentation,
        resolved_deck: ResolvedDeckLayout,
        deck_structure: LayeredDeckStructureSpec,
        style_manifest: StyleManifest,
        content_package: PresentationContentPackage,
        review_engine: Any,
        is_technical_deck: bool = False,
    ) -> tuple[VisualReviewManifest, ValidationManifest, list[VisualRepairHistory]]:
        """Executes bounded repair iterations until certification or attempt limit reached."""
        current_visual_manifest = initial_manifest
        current_l8_manifest = initial_l8_manifest
        repair_history: list[VisualRepairHistory] = []

        # If already certified, return immediately
        if current_visual_manifest.status == VisualCertificationStatus.VISUALLY_CERTIFIED:
            return current_visual_manifest, current_l8_manifest, repair_history

        attempt = 0
        while attempt < self.max_attempts:
            attempt += 1
            logger.info(f"Starting PPT-L9 bounded repair attempt {attempt}/{self.max_attempts}")

            # Identify blocking issues to repair
            blocking_issues = [
                i for i in current_visual_manifest.issues
                if i.severity == VisualSeverity.CRITICAL and i.repairable
            ]
            if not blocking_issues:
                # No repairable critical issues remain
                break

            target_issue = blocking_issues[0]
            approval = RepairDecisionEngine.evaluate_approval_level(target_issue)
            if approval != RepairApprovalLevel.AUTO_SAFE:
                logger.info(f"Issue {target_issue.issue_id} requires human approval ({approval.value}). Halting auto-repair.")
                break

            target_slide_id = target_issue.slide_id
            issues_before = [i.issue_id for i in blocking_issues]

            # -------------------------------------------------------------
            # STEP 1: APPLY BOUNDED UPSTREAM REPAIR
            # -------------------------------------------------------------
            repair_applied = self._apply_upstream_repair(
                issue=target_issue,
                slide_id=target_slide_id,
                prs=prs,
                resolved_deck=resolved_deck,
                deck_structure=deck_structure,
                style_manifest=style_manifest,
            )
            if not repair_applied:
                repair_history.append(
                    VisualRepairHistory(
                        slide_id=target_slide_id,
                        attempt=attempt,
                        issues_before=issues_before,
                        repair_action=target_issue.recommended_action,
                        repair_owner=target_issue.recommended_owner,
                        issues_after=issues_before,
                        status="FAILED",
                        metadata={"reason": "No applicable upstream repair handler found."},
                    )
                )
                break

            # -------------------------------------------------------------
            # STEP 2: POST-REPAIR PPT-L8 DETERMINISTIC REVALIDATION
            # -------------------------------------------------------------
            reval_l8 = DeterministicValidationEngine.validate(
                prs=prs,
                style_manifest=style_manifest,
                render_manifest=None,  # validated against live presentation
                resolved_deck=resolved_deck,
                deck_structure=deck_structure,
                content_package=content_package,
                is_technical_deck=is_technical_deck,
            )

            # If PPT-L8 failed structurally after repair, flag regression
            if reval_l8.status == DeckValidationStatus.FAIL:
                repair_history.append(
                    VisualRepairHistory(
                        slide_id=target_slide_id,
                        attempt=attempt,
                        issues_before=issues_before,
                        repair_action=target_issue.recommended_action,
                        repair_owner=target_issue.recommended_owner,
                        issues_after=[i.issue_id for i in reval_l8.issues],
                        status="REGRESSION",
                        metadata={"reason": "PPT-L8 deterministic validation failed after repair."},
                    )
                )
                current_l8_manifest = reval_l8
                current_visual_manifest.status = VisualCertificationStatus.FAIL
                break

            current_l8_manifest = reval_l8

            # -------------------------------------------------------------
            # STEP 3: TARGETED RERENDER OF AFFECTED SLIDE
            # -------------------------------------------------------------
            rerendered_artifacts = self.render_service.render_deck(
                prs=prs,
                deck_id=current_visual_manifest.deck_id,
                force_rerender=True,
                target_slide_ids=[target_slide_id],
            )

            # -------------------------------------------------------------
            # STEP 4: RE-REVIEW OF SLIDE
            # -------------------------------------------------------------
            new_visual_manifest = review_engine.review_deck(
                artifacts=rerendered_artifacts,
                validation_manifest=current_l8_manifest,
                resolved_deck=resolved_deck,
                deck_structure=deck_structure,
                style_manifest=style_manifest,
                prs=prs,
                is_technical_deck=is_technical_deck,
            )

            issues_after = [i.issue_id for i in new_visual_manifest.issues if i.severity == VisualSeverity.CRITICAL]
            is_success = len(issues_after) < len(issues_before)

            repair_history.append(
                VisualRepairHistory(
                    slide_id=target_slide_id,
                    attempt=attempt,
                    issues_before=issues_before,
                    repair_action=target_issue.recommended_action,
                    repair_owner=target_issue.recommended_owner,
                    issues_after=issues_after,
                    status="SUCCESS" if is_success else "PERSISTING",
                )
            )

            current_visual_manifest = new_visual_manifest

            if current_visual_manifest.status == VisualCertificationStatus.VISUALLY_CERTIFIED:
                logger.info(f"Deck certified after {attempt} repair attempt(s).")
                break

        # Attach repair history to final manifest
        current_visual_manifest.repair_history = repair_history
        if current_visual_manifest.status != VisualCertificationStatus.VISUALLY_CERTIFIED:
            current_visual_manifest.status = VisualCertificationStatus.FAIL

        return current_visual_manifest, current_l8_manifest, repair_history

    def _apply_upstream_repair(
        self,
        issue: VisualIssue,
        slide_id: str,
        prs: pptx.presentation.Presentation,
        resolved_deck: ResolvedDeckLayout,
        deck_structure: LayeredDeckStructureSpec,
        style_manifest: StyleManifest,
    ) -> bool:
        """Dispatches repair action to the authorized upstream owner without mutating business truth."""
        try:
            # 1. PPT-L5 Layout Replan / Refit Handler
            if issue.recommended_owner == RepairOwner.PPT_L5_LAYOUT:
                return self._repair_layout_defect(issue, slide_id, prs, resolved_deck)

            # 2. PPT-L7 Style / Token Adjustment Handler
            elif issue.recommended_owner == RepairOwner.PPT_L7_STYLE:
                return self._repair_style_defect(issue, slide_id, prs, style_manifest)

            # 3. PPT-L6 Renderer Retry Handler
            elif issue.recommended_owner == RepairOwner.PPT_L6_RENDERER:
                # NOP retry to trigger clean rerender
                return True

            # 4. Asset Pipeline / Image Crop Handler
            elif issue.recommended_owner == RepairOwner.ASSET_PIPELINE:
                return self._repair_asset_defect(issue, slide_id, prs)

        except Exception as e:
            logger.error(f"Error executing upstream repair for issue {issue.issue_id}: {e}")
            return False

        return False

    def _repair_layout_defect(
        self,
        issue: VisualIssue,
        slide_id: str,
        prs: pptx.presentation.Presentation,
        resolved_deck: ResolvedDeckLayout,
    ) -> bool:
        """Adjusts layout geometry to resolve collision, overlap, or size issues."""
        slide_idx = next((idx for idx, s in enumerate(resolved_deck.slides) if s.physical_slide_id == slide_id), None)
        if slide_idx is None or slide_idx >= len(prs.slides):
            return False

        prs_slide = prs.slides[slide_idx]
        affected_names = set(issue.affected_object_ids)

        # Collision / Overlap Repair: shift colliding body shape down or adjust width
        if issue.category in (VisualCategory.VISUAL_OVERLAP, VisualCategory.PRIMARY_VISUAL_OBSCURED, VisualCategory.FRAME_COLLISION):
            for sh in prs_slide.shapes:
                if (not affected_names or sh.name in affected_names) and not (sh.name and "TITLE" in sh.name.upper()):
                    # Bounded positional adjustment
                    if sh.top < 2000000 and "TITLE" not in (sh.name or "").upper():
                        sh.top = int(2200000)
                    return True

        # Alignment defect / Geometry mutation: restore authoritative PPT-L5 resolved layout bounds
        if issue.category == VisualCategory.ALIGNMENT_DEFECT or "geometry mutated" in (issue.description or "").lower():
            layout_slide = resolved_deck.slides[slide_idx]
            for obj_l in layout_slide.object_layouts:
                if not affected_names or obj_l.object_name in affected_names or obj_l.object_id in affected_names:
                    for sh in prs_slide.shapes:
                        if sh.name == obj_l.object_name or (sh.has_chart and "CHART" in obj_l.object_name):
                            sw = prs.slide_width
                            sh_h = prs.slide_height
                            sh.left = int(obj_l.bounds.left * sw)
                            sh.top = int(obj_l.bounds.top * sh_h)
                            sh.width = int(obj_l.bounds.width * sw)
                            sh.height = int(obj_l.bounds.height * sh_h)
                            return True

        # Chart Too Small Repair: restore authoritative resolved layout dimensions
        if issue.category == VisualCategory.CHART_TOO_SMALL:
            layout_slide = resolved_deck.slides[slide_idx]
            for obj_l in layout_slide.object_layouts:
                if not affected_names or obj_l.object_name in affected_names or obj_l.object_id in affected_names:
                    for sh in prs_slide.shapes:
                        if sh.has_chart or sh.name == obj_l.object_name:
                            sw = prs.slide_width
                            sh_h = prs.slide_height
                            sh.left = int(obj_l.bounds.left * sw)
                            sh.top = int(obj_l.bounds.top * sh_h)
                            sh.width = int(obj_l.bounds.width * sw)
                            sh.height = int(obj_l.bounds.height * sh_h)
                            return True

        # Axis / Category Label Collision Repair
        if issue.category == VisualCategory.AXIS_LABEL_COLLISION:
            # Widen chart shape to provide breathing room for labels
            for sh in prs_slide.shapes:
                if sh.has_chart:
                    sh.width = min(int(10000000), int(sh.width * 1.25))
                    return True

        return False

    def _repair_style_defect(
        self,
        issue: VisualIssue,
        slide_id: str,
        prs: pptx.presentation.Presentation,
        style_manifest: StyleManifest,
    ) -> bool:
        """Applies style/contrast correction under PPT-L7 tokens."""
        slide_idx = next((idx for idx, s in enumerate(prs.slides) if f"SLD-PHYS-{idx+1}" == slide_id), None)
        if slide_idx is None or slide_idx >= len(prs.slides):
            return False

        prs_slide = prs.slides[slide_idx]
        # Invert low contrast text
        for sh in prs_slide.shapes:
            if sh.has_text_frame:
                for p in sh.text_frame.paragraphs:
                    p.font.color.rgb = pptx.dml.color.RGBColor(15, 23, 42)
        return True

    def _repair_asset_defect(
        self,
        issue: VisualIssue,
        slide_id: str,
        prs: pptx.presentation.Presentation,
    ) -> bool:
        """Normalizes distorted image aspect ratio to 16:9 or 4:3 standard."""
        slide_idx = next((idx for idx, s in enumerate(prs.slides) if f"SLD-PHYS-{idx+1}" == slide_id), None)
        if slide_idx is None or slide_idx >= len(prs.slides):
            return False

        prs_slide = prs.slides[slide_idx]
        for sh in prs_slide.shapes:
            if "IMAGE" in (sh.name or "").upper():
                # Reset to 16:9 box
                sh.width = int(4000000)
                sh.height = int(2250000)
                return True
        return False
