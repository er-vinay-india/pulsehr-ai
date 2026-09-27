"""Visual QA Orchestrator for Phase 5.

Coordinates deterministic geometry inspection, screenshot capture, Gemma multimodal critique,
bounded automated repair loops, and deck-level consistency audits across all QA operating modes.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from ....core import config
from ..visual.design_tokens import SlideDesignTokens, normalize_slide_theme
from ..visual.layout_registry import LayoutFamily
from ..visual.visual_models import VisualSpecification
from .deck_consistency_auditor import DeckConsistencyAuditor
from .deterministic_qa import DeterministicVisualAuditor
from .gemma_critic import GemmaVisualCritic
from .qa_models import IssueSeverity, VisualQAReport, VisualRepairPlan
from .repair_engine import VisualRepairEngine
from .screenshot_service import ScreenshotService

logger = logging.getLogger(__name__)


class VisualQAOrchestrator:
    """The central Visual QA & Repair Orchestrator coordinating multimodal visual audits."""

    def __init__(
        self,
        qa_mode: str | None = None,
        max_repairs: int | None = None,
        min_score: float | None = None,
        critic: GemmaVisualCritic | None = None,
        screenshot_service: ScreenshotService | None = None,
        repair_engine: VisualRepairEngine | None = None
    ):
        self.qa_mode = (qa_mode or getattr(config, "PRESENTATION_VISUAL_QA_MODE", "STANDARD")).upper()
        self.max_repairs = max_repairs if max_repairs is not None else getattr(config, "PRESENTATION_VISUAL_QA_MAX_REPAIRS", 2)
        self.min_score = min_score if min_score is not None else getattr(config, "PRESENTATION_VISUAL_QA_MIN_SCORE", 0.80)
        self.critic = critic or GemmaVisualCritic()
        self.screenshot_service = screenshot_service or ScreenshotService()
        self.repair_engine = repair_engine or VisualRepairEngine()

    def audit_and_repair_deck(
        self,
        slides: list[VisualSpecification],
        theme_tokens: SlideDesignTokens | None = None,
        deck_id: str = "deck_default"
    ) -> tuple[list[VisualSpecification], dict[str, Any]]:
        """Audits each slide, executes bounded repairs, and produces deck-level QA metadata."""
        start_time = time.perf_counter()
        tokens = theme_tokens or normalize_slide_theme(slides[0].theme_id if slides else "bold_signal")

        repaired_slides: list[VisualSpecification] = []
        slide_reports: list[VisualQAReport] = []
        total_repairs_applied = 0
        critical_count = 0

        logger.info(f"Visual QA Orchestrator initiated for deck '{deck_id}' ({len(slides)} slides) in mode '{self.qa_mode}'")

        for idx, spec in enumerate(slides):
            slide_id = spec.slide_id or f"slide_{spec.sequence_number}"
            current_spec = spec
            current_iteration = 0

            # -------------------------------------------------------------
            # STEP 1: INITIAL DETERMINISTIC AUDIT
            # -------------------------------------------------------------
            det_report = DeterministicVisualAuditor.audit_slide(current_spec, tokens)

            # Determine whether to invoke multimodal Gemma inspection
            should_run_critic = self._should_run_critic(det_report, current_spec)

            if should_run_critic:
                screenshot_path = self.screenshot_service.capture_slide_screenshot(
                    spec=current_spec,
                    tokens=tokens,
                    deck_id=deck_id,
                    suffix="initial"
                )
                meta = {
                    "slide_id": slide_id,
                    "sequence_number": current_spec.sequence_number,
                    "purpose": current_spec.visual_story.primary_message,
                    "primary_message": current_spec.visual_story.takeaway,
                    "layout_family": current_spec.layout.family.value,
                    "chart_family": current_spec.chart_spec.family.value if current_spec.chart_spec else "NONE",
                    "audience": "Executive Decision Makers",
                    "visual_priority": current_spec.visual_story.priority.value
                }
                current_report = self.critic.evaluate_screenshot(
                    screenshot_path=screenshot_path,
                    slide_metadata=meta,
                    deterministic_baseline=det_report
                )
            else:
                current_report = det_report

            # -------------------------------------------------------------
            # STEP 2: BOUNDED REPAIR LOOP (Max self.max_repairs)
            # -------------------------------------------------------------
            allow_repairs = self.qa_mode in ("STANDARD", "STRICT") and self.max_repairs > 0

            while (
                allow_repairs and
                current_iteration < self.max_repairs and
                (current_report.status in ("FAIL", "WARNING") or current_report.overall_score < self.min_score)
            ):
                current_iteration += 1
                logger.info(f"Applying visual repair iteration {current_iteration} on {slide_id}")

                repair_plan = self.repair_engine.build_repair_plan(
                    spec=current_spec,
                    qa_report=current_report,
                    iteration=current_iteration
                )

                if not repair_plan.repairs:
                    break

                # Apply repairs deterministically
                current_spec = self.repair_engine.apply_repairs(current_spec, repair_plan)
                total_repairs_applied += 1

                # Re-audit
                re_det_report = DeterministicVisualAuditor.audit_slide(current_spec, tokens)
                if should_run_critic and self.qa_mode == "STRICT":
                    re_shot = self.screenshot_service.capture_slide_screenshot(
                        spec=current_spec,
                        tokens=tokens,
                        deck_id=deck_id,
                        suffix=f"repair_{current_iteration}"
                    )
                    current_report = self.critic.evaluate_screenshot(
                        screenshot_path=re_shot,
                        slide_metadata=meta,
                        deterministic_baseline=re_det_report
                    )
                else:
                    current_report = re_det_report

                current_report.repair_iteration = current_iteration

            if current_report.has_critical_issues:
                critical_count += 1

            repaired_slides.append(current_spec)
            slide_reports.append(current_report)

        # -----------------------------------------------------------------
        # STEP 3: DECK-LEVEL CONSISTENCY AUDIT
        # -----------------------------------------------------------------
        deck_consistency = DeckConsistencyAuditor.audit_deck(repaired_slides)

        elapsed_sec = time.perf_counter() - start_time
        deck_status = "FAILED" if critical_count > 0 else ("WARNING" if any(r.status == "WARNING" for r in slide_reports) else "PASSED")

        qa_summary = {
            "status": deck_status,
            "qa_mode": self.qa_mode,
            "slides_checked": len(slides),
            "slides_repaired": total_repairs_applied,
            "critical_issues": critical_count,
            "qa_model": self.critic.model_name if self.qa_mode != "OFF" else "none",
            "duration_seconds": round(elapsed_sec, 2),
            "deck_consistency": deck_consistency,
            "slide_reports": [r.model_dump() for r in slide_reports]
        }

        # Cleanup screenshots if configured
        self.screenshot_service.cleanup_deck_screenshots(deck_id)

        return repaired_slides, qa_summary

    def _should_run_critic(self, det_report: VisualQAReport, spec: VisualSpecification | None = None) -> bool:
        """Determines whether multimodal Gemma critic should be dispatched."""
        if self.qa_mode == "OFF":
            return False
        if self.qa_mode == "FAST":
            # Only run critic if deterministic checks flagged issues
            return det_report.status in ("FAIL", "WARNING")

        # In STANDARD mode, optimize away unnecessary model calls:
        # If the slide is a clean TITLE_HERO or SECTION_DIVIDER with zero deterministic issues,
        # skip heavy multimodal screenshot & critic inference to avoid local memory thrashing.
        if self.qa_mode == "STANDARD" and spec is not None:
            if spec.layout.family in (LayoutFamily.TITLE_HERO, LayoutFamily.SECTION_DIVIDER):
                if det_report.status == "PASS" and not det_report.issues:
                    return False

        if self.qa_mode in ("STANDARD", "STRICT"):
            return True
        return False
