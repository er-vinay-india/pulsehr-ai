"""Presentation Structure & Slide Reordering Engine.

Ensures executive decks strictly follow the canonical boardroom presentation narrative:
1. Title / Cover Slide (Executive Title Cover)
2. Executive Summary & Core Performance Findings
3. Analysis Scope & Dataset Baseline Governance
4. Operational Strengths & Peak Volume Resilience
5. Operational Headwinds & Performance Dispersion
6. Category / Cohort Distributions & Relational Discovery
7. Analytical Diagnostics & Industrial Models
8. Honest Governance Boundaries (Proven Facts vs Open Questions)
9. Strategic Implementation Roadmap & Priority Initiatives
10. Implementation Governance, RACI Ownership & SLAs
11. Executive Conclusions & Leadership Mandates
12. Data Evidence & Audited Evidence Ledger Appendix

Guarantees:
- The Presentation Title Page / Cover Slide is ALWAYS Slide 1 (index 0).
- If a title page was generated or placed at the end or in the middle, it is relocated to Slide 1.
- Conclusion and closing mandate slides stay at the end of the narrative arc and are not styled as duplicate title covers.
- Slide order numbers and total_slides counts are cleanly re-indexed.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def classify_presentation_slide(slide: dict[str, Any], deck_title: str = "") -> float:
    """Classifies a slide into its canonical presentation narrative position.

    Returns a float score representing the stage in the presentation arc (0.0 to 12.0).
    Lower scores appear earlier in the presentation.
    """
    title = (slide.get("title") or "").strip().lower()
    cat = (slide.get("category") or "").strip().lower()
    layout = (slide.get("layout") or "").strip().lower()
    stable_id = (slide.get("stable_slide_id") or "").strip().lower()
    deck_title_clean = (deck_title or "").strip().lower()

    is_conclusion = any(w in title for w in ["conclusion", "closing mandate", "leadership mandate", "next step", "wrap-up"])
    is_raci = any(w in title for w in ["raci", "sla", "responsibility matrix", "ownership & sla", "governance & sla", "execution governance"]) or "raci" in cat
    is_ledger = any(w in title for w in ["evidence ledger", "audit trail", "cryptographic verification"]) or "audit trail" in cat or "ledger" in cat
    is_data_evidence = "data evidence" in title or "frequency and outcome" in title

    # 0.0: Presentation Title Cover Page
    # Criteria: Explicit title_cover layout or title_cover stable_id, or title contains "title cover",
    # or matches the primary deck title while NOT being a conclusion, RACI, or ledger slide.
    if not is_conclusion and not is_raci and not is_ledger and not is_data_evidence:
        if layout == "title_cover" or stable_id == "slide_title_cover":
            return 0.0
        if "title cover" in title or "executive title" in title:
            return 0.0
        if deck_title_clean and len(deck_title_clean) > 8:
            if (deck_title_clean in title or title in deck_title_clean) and not any(
                w in title for w in ["scope", "baseline", "summary", "strength", "headwind", "part 1", "part 2", "governance"]
            ):
                return 0.0

    # 1.0: Executive Summary & Performance Diagnostic
    if stable_id == "slide_exec_overview" or "executive summary" in title or "core performance" in title:
        return 1.0
    if "executive briefing" in title and not is_conclusion:
        return 1.0
    if "executive summary" in cat:
        return 1.0

    # 2.0: Analysis Scope & Baseline Governance
    if stable_id == "slide_macro_outcomes" or "analysis scope" in title or "baseline scope" in title or "audited baseline" in title or "population integrity" in title:
        return 2.0
    if "scope" in title and "governance" in title:
        return 2.0

    # 3.0: Operational Strengths & Peak Volume Resilience
    if "operational strength" in title or "volume surge" in title or "peak volume" in title or "strengths" in cat or "throughput resilience" in title:
        return 3.0
    if "peak" in title and "pts" in title:
        return 3.0

    # 4.0: Operational Headwinds & Performance Dispersion
    if "headwind" in title or "headwinds" in cat or "dispersion" in title or "disparity" in title or "outpaces lower-quartile" in title or "friction" in title:
        return 4.0

    # 5.0: Category / Cohort Distributions & Relational Discovery
    if "distribution" in title or "concentration" in title or "cohort" in title or "cross-dimension" in title or "category distribution" in title:
        return 5.0

    # 6.0: Analytical Diagnostics & Industrial Models
    if "diagnostic" in title or "9-box" in title or "talent" in title or "strain" in title or "analytical diagnostic" in title:
        return 6.0
    if "talent & capacity" in cat or "strain diagnostic" in cat:
        return 6.0

    # 7.0: Honest Governance Boundaries
    if "governance boundaries" in title or "open questions" in title or "honest governance" in cat or "boundaries" in title:
        return 7.0

    # 8.0: Strategic Implementation Roadmap & Priority Initiatives
    if "strategic roadmap" in title or "action plan" in title or "stabilization initiatives" in title or "roadmap" in cat or "action_plan" in stable_id:
        return 8.0

    # 9.0: Implementation Governance, RACI Ownership & SLAs
    if is_raci or "operational governance" in cat:
        return 9.0

    # 10.0: Executive Conclusions & Leadership Mandates
    if is_conclusion:
        return 10.0

    # 11.0: Data Evidence & Audited Evidence Ledger Appendix
    if is_ledger or is_data_evidence or "evidence appendix" in cat or "governance & audit trail" in cat:
        return 11.0

    # Default intermediate rank for analytical content
    return 5.5


def reorder_presentation_slides(slides: list[dict[str, Any]], deck_title: str = "") -> list[dict[str, Any]]:
    """Sorts slides into boardroom presentation narrative sequence.

    Guarantees:
    - Slide 1 is always the Title Cover.
    - If a Title Cover slide was located elsewhere (e.g. at the end), it is moved to Slide 1.
    - Conclusion slides stay at the concluding section.
    - Appendix / Evidence Ledger slides stay at the end.
    - Slide order indices (1-indexed) and total_slides counts are normalized.
    """
    if not slides or len(slides) <= 1:
        if slides:
            slides[0]["order"] = 1
            slides[0]["total_slides"] = 1
        return slides

    # Score each slide while maintaining original index for stable sorting
    scored_items = []
    for orig_idx, slide in enumerate(slides):
        score = classify_presentation_slide(slide, deck_title)
        scored_items.append((score, orig_idx, slide))

    # Stable sort by canonical narrative score, preserving relative position within ties
    scored_items.sort(key=lambda item: (item[0], item[1]))
    reordered = [item[2] for item in scored_items]

    # Post-sort layout normalization:
    # 1. Slide 1 (index 0) must be a proper Title Cover
    if reordered:
        first_slide = reordered[0]
        if first_slide.get("layout") not in ("title_cover", "title_hero", "image_story"):
            first_slide["layout"] = "title_cover"

    # 2. Prevent subsequent non-cover slides from accidentally retaining "title_cover" layout
    for idx in range(1, len(reordered)):
        s = reordered[idx]
        if s.get("layout") == "title_cover":
            t = (s.get("title") or "").lower()
            if any(w in t for w in ["raci", "sla", "matrix", "table", "ownership", "governance"]):
                s["layout"] = "table_detail"
            elif any(w in t for w in ["conclusion", "mandate", "next step", "closing"]):
                s["layout"] = "comparison_split"
            elif any(w in t for w in ["action", "roadmap", "initiative"]):
                s["layout"] = "action_plan"
            elif any(w in t for w in ["scope", "baseline", "kpi"]):
                s["layout"] = "kpi_summary"
            else:
                s["layout"] = "chart_narrative"

    # 3. Cleanly re-index order and total_slides across all slides
    total_count = len(reordered)
    for idx, s in enumerate(reordered):
        s["order"] = idx + 1
        s["total_slides"] = total_count

    return reordered


def reorder_presentation_deck(deck_spec: dict[str, Any]) -> dict[str, Any]:
    """Applies canonical presentation slide ordering to a complete PresentationDeckSpec.

    Updates:
    - deck_spec['slides']
    - metadata title alignment
    - total_slides consistency
    """
    if not deck_spec or "slides" not in deck_spec:
        return deck_spec

    meta = deck_spec.get("metadata", {})
    deck_title = meta.get("title") or deck_spec.get("title", "")

    slides = deck_spec.get("slides", [])
    reordered_slides = reorder_presentation_slides(slides, deck_title=deck_title)
    deck_spec["slides"] = reordered_slides

    # Ensure metadata title matches the lead cover slide if title exists
    if reordered_slides and reordered_slides[0].get("title"):
        lead_title = reordered_slides[0]["title"]
        if not deck_title or deck_title == "Executive Presentation":
            deck_spec["title"] = lead_title
            if "metadata" in deck_spec:
                deck_spec["metadata"]["title"] = lead_title

    logger.info(f"Reordered presentation deck '{deck_title}' with {len(reordered_slides)} slides in canonical narrative sequence.")
    return deck_spec
