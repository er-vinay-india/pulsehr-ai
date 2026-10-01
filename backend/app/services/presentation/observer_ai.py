"""
Slide Context Observer AI (Supervisor / Context Guardian)

In simple terms:
Think of this class like a Chief Editor or Executive Director in a television studio.
When building a slide presentation one slide at a time, each slide could easily forget
what the previous slides said. The Observer AI solves this:
1. It decides and locks the exact number of slides right upfront in Phase 1.
2. It watches every slide as it gets made, slide-by-slide sequentially.
3. It keeps a memory notebook of what facts and numbers have already been shared,
   and briefs the slide generator before each new slide is created so the story flows
   smoothly without repeating facts or contradicting itself.
4. It keeps track of the visual status of every slide across all phases (layout,
   content, charts, claim checks, animation, transitions, and speech notes).
"""

from __future__ import annotations

import logging
from typing import Any

from .director.director_models import SlideCountConstraint, SlideCountMode

logger = logging.getLogger(__name__)


# Default narrative templates for presentation slide outlines
DEFAULT_SLIDE_TEMPLATES = [
    {
        "title": "Executive Title Cover",
        "category": "Executive",
        "purpose": "Boardroom executive title cover establishing strategic mandate, audited population, and review scope."
    },
    {
        "title": "Executive Summary & Core Performance",
        "category": "Strategy",
        "purpose": "Deliver headline bottom-line results, top-line metrics, and executive conclusions."
    },
    {
        "title": "Analysis Scope & Dataset Governance",
        "category": "Governance",
        "purpose": "Verify dataset provenance, record counts, audit completeness, and evaluation window."
    },
    {
        "title": "Operational Performance & Peak Volumes",
        "category": "Operations",
        "purpose": "Highlight strongest performing units, volume surges, and positive momentum."
    },
    {
        "title": "Productivity Dispersion & Variance Headwinds",
        "category": "Diagnostic",
        "purpose": "Surface operating friction, performance spread between leader and laggards, and risks."
    },
    {
        "title": "Cohort & Unit Comparative Breakdown",
        "category": "Diagnostic",
        "purpose": "Examine department, category, or store-level distributions and relative contributions."
    },
    {
        "title": "Strategic Priority Initiatives",
        "category": "Roadmap",
        "purpose": "Propose concrete, high-ROI operational responses and resource investments."
    },
    {
        "title": "Governance RACI & SLA Milestones",
        "category": "Execution",
        "purpose": "Define clear ownership roles, delivery timetables, and operational safeguards."
    },
    {
        "title": "Empirical Ground-Truth Evidence Ledger",
        "category": "Evidence",
        "purpose": "Provide verifiable audit trail of every fact and calculation backing the presentation."
    }
]


class SlideContextObserver:
    """The Observer AI monitors presentation generation slide-by-slide,

    preserving the cumulative story narrative and maintaining the state of
    all slide units.
    """

    def __init__(
        self,
        scope: dict[str, Any],
        primary_ctx: dict[str, Any] | None = None,
        workspace_evidence: dict[str, Any] | None = None
    ):
        # The user's goal or topic for this presentation
        self.scope = scope or {}
        self.primary_ctx = primary_ctx or {}
        self.workspace_evidence = workspace_evidence or {}
        self.objective = self.scope.get("objective") or "Executive Leadership Review"
        self.domain = self.primary_ctx.get("domain") or "Operations"

        # 1. Lock in the exact slide count right in Phase 1
        self.total_slides = self._resolve_slide_count()

        # 2. Initialize all slide units upfront
        self.slides: list[dict[str, Any]] = self._build_initial_slides()

        # 3. Context memory ledger: stores summary of what each completed slide covered
        self.completed_history: dict[int, dict[str, Any]] = {}

    def _resolve_slide_count(self) -> int:
        """Determines and locks the total number of slides during Phase 1.

        Layman explanation:
        We look at what the user asked for (e.g. if they set a target length like 8 slides,
        or wrote 'at least 6 slides' in instructions). If not specified, we pick a smart
        default (usually 8 slides) so we can create a complete story structure from start to finish.
        """
        instructions = self.scope.get("instructions") or ""
        target_length = self.scope.get("target_length")

        try:
            # Use the SlideCountConstraint parser to see if user set rules
            constraint = SlideCountConstraint.from_inputs(
                instructions=instructions,
                target_length=target_length
            )

            if constraint.mode == SlideCountMode.FIXED and constraint.target:
                count = constraint.target
            elif constraint.mode == SlideCountMode.MINIMUM and constraint.min_slides:
                count = max(8, constraint.min_slides)
            elif constraint.mode == SlideCountMode.MAXIMUM and constraint.max_slides:
                count = min(12, max(4, constraint.max_slides))
            elif constraint.mode == SlideCountMode.RANGE:
                count = max(constraint.min_slides or 6, min(constraint.max_slides or 10, 8))
            else:
                # In adaptive mode: default to target_length if supplied, else 8
                if target_length and int(target_length) > 0:
                    count = int(target_length)
                else:
                    count = 8
        except Exception as exc:
            logger.debug(f"Slide count resolution error, defaulting to 8: {exc}")
            count = 8

        # Ensure sensible bounds between 4 and 20 slides
        return max(4, min(count, 20))

    def _build_initial_slides(self) -> list[dict[str, Any]]:
        """Builds the initial lineup of slides locked in Phase 1.

        Layman explanation:
        We create each slide unit with an order number, an initial title, a category,
        and mark its status as 'pending'.
        """
        slides = []
        num_templates = len(DEFAULT_SLIDE_TEMPLATES)

        for i in range(self.total_slides):
            slide_num = i + 1
            if i == 0:
                title = self.objective if (self.objective and self.objective != "Executive Leadership Review") else "Executive Title Cover"
                category = "Executive"
            elif i < num_templates:
                tpl = DEFAULT_SLIDE_TEMPLATES[i]
                title = tpl["title"]
                category = tpl["category"]
            else:
                # Extra slides get specialized analytical deep dives
                title = f"Deep Dive Analysis {slide_num - num_templates + 1}"
                category = "Diagnostic"

            slides.append({
                "order": slide_num,
                "title": title,
                "category": category,
                "status": "pending",  # 'pending', 'building', or 'complete'
                "phase": "layout",    # which pipeline phase this slide is currently in
                "badge": "Planned",   # short label shown on the slide indicator
                "takeaway": ""        # will store the main finding once generated
            })

        return slides

    def get_slide_status_list(
        self,
        active_phase: str = "layout",
        current_building_slide: int = 0
    ) -> list[dict[str, Any]]:
        """Returns a clean list of all slide statuses for the frontend UI.

        Layman explanation:
        The frontend needs to know which slides are done (green checkmark), which one
        is currently being built (spinning / active), and which are waiting in line.
        """
        results = []
        for s in self.slides:
            slide_copy = dict(s)
            slide_copy["phase"] = active_phase

            if slide_copy["order"] in self.completed_history:
                slide_copy["status"] = "complete"
                slide_copy["badge"] = slide_copy.get("badge") or "Complete"
            elif slide_copy["order"] == current_building_slide:
                slide_copy["status"] = "building"
                slide_copy["badge"] = "Synthesizing"
            else:
                if slide_copy["status"] != "complete":
                    slide_copy["status"] = "pending"
                    slide_copy["badge"] = "Pending"

            results.append(slide_copy)
        return results

    def get_observer_briefing_for_slide(
        self,
        slide_num: int,
        slide_title: str,
        category: str = ""
    ) -> str:
        """Generates an Observer AI briefing note before synthesizing a slide.

        Layman explanation:
        The Observer AI provides a live verification note explaining what context it is
        handing over from the previous slides so the current slide stays on topic.
        """
        if slide_num == 1:
            return f"Observer AI: Establishing executive baseline & master thesis for {self.domain}."

        prev_order = slide_num - 1
        prev_summary = self.completed_history.get(prev_order, {})
        prev_title = prev_summary.get("title", f"Slide {prev_order}")

        return (
            f"Observer AI: Guiding Slide {slide_num} of {self.total_slides} ({category or 'Analysis'}) "
            f"· Carrying forward context from '{prev_title[:30]}'."
        )

    def on_slide_start(
        self,
        slide_num: int,
        slide_title: str,
        category: str = "",
        active_phase: str = "narrative_ai"
    ) -> dict[str, Any]:
        """Notifies the Observer AI that work has begun on a specific slide.

        Layman explanation:
        Marks this specific slide as 'building' so the user sees it active,
        while the progress stream smoothly updates to focus on it.
        """
        if 1 <= slide_num <= len(self.slides):
            clean_title = slide_title.strip()
            if clean_title:
                self.slides[slide_num - 1]["title"] = clean_title
            if category:
                self.slides[slide_num - 1]["category"] = category
            self.slides[slide_num - 1]["status"] = "building"
            self.slides[slide_num - 1]["badge"] = "Synthesizing"

        briefing = self.get_observer_briefing_for_slide(slide_num, slide_title, category)
        return {
            "briefing": briefing,
            "current_slide": slide_num,
            "total_slides": self.total_slides,
            "slide_status_list": self.get_slide_status_list(
                active_phase=active_phase,
                current_building_slide=slide_num
            )
        }

    def on_slide_complete(
        self,
        slide_num: int,
        slide_title: str,
        category: str = "",
        slide_dict: dict[str, Any] | None = None,
        active_phase: str = "narrative_ai"
    ) -> dict[str, Any]:
        """Notifies the Observer AI that a slide has finished synthesis.

        Layman explanation:
        Marks this slide as 'complete' (green checkmark), records its key takeaway
        into the Observer's memory ledger, and prepares to advance to the next slide.
        """
        clean_title = slide_title.strip()

        # Extract takeaway if available from slide data
        takeaway = ""
        evidence_id = ""
        if slide_dict:
            takeaway = slide_dict.get("narrative") or slide_dict.get("key_message") or ""
            evidence_id = slide_dict.get("evidence_id") or ""

        # Store in cumulative history
        self.completed_history[slide_num] = {
            "order": slide_num,
            "title": clean_title,
            "category": category,
            "takeaway": takeaway,
            "evidence_id": evidence_id
        }

        # Update slide card
        if 1 <= slide_num <= len(self.slides):
            self.slides[slide_num - 1]["title"] = clean_title
            if category:
                self.slides[slide_num - 1]["category"] = category
            self.slides[slide_num - 1]["status"] = "complete"
            self.slides[slide_num - 1]["badge"] = "Complete"
            self.slides[slide_num - 1]["takeaway"] = takeaway

        observer_note = (
            f"Observer AI: Verified Slide {slide_num}/{self.total_slides} '{clean_title[:32]}' "
            f"into context ledger."
        )

        return {
            "observer_note": observer_note,
            "current_slide": slide_num,
            "total_slides": self.total_slides,
            "slide_status_list": self.get_slide_status_list(
                active_phase=active_phase,
                current_building_slide=0
            )
        }

    def set_phase_for_all(self, phase_name: str, badge_text: str = ""):
        """Updates the status and badge of all slides when entering subsequent phases.

        Layman explanation:
        When we move from slide text to rendering charts or claim checks,
        this updates the badge on all slides so the user sees the whole deck advancing.
        """
        for s in self.slides:
            s["phase"] = phase_name
            if badge_text:
                s["badge"] = badge_text
