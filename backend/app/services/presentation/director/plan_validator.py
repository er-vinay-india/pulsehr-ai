from __future__ import annotations

import difflib
import logging
import re
from typing import Any

from .director_models import (
    PlanningValidationResult,
    PresentationIntent,
    PresentationPlanningContext,
    SlidePlan,
)

logger = logging.getLogger(__name__)


def validate_plan(
    ctx: PresentationPlanningContext,
    intent: PresentationIntent,
    slides: list[SlidePlan]
) -> PlanningValidationResult:
    """Stage 5: Validates presentation plan consistency, concept duplication, and question answering."""
    duplicate_concepts: list[str] = []
    unanswered_questions: list[str] = []
    unsupported_claims: list[str] = []
    warnings: list[str] = []
    recommendations: list[str] = []

    # 1. Duplicate Concept Detection
    for i in range(len(slides)):
        for j in range(i + 1, len(slides)):
            s1 = slides[i]
            s2 = slides[j]

            # Headline similarity
            sim_ratio = difflib.SequenceMatcher(None, s1.headline.lower(), s2.headline.lower()).ratio()
            if sim_ratio > 0.85:
                duplicate_concepts.append(
                    f"Slide {s1.sequence_number} ('{s1.headline}') and Slide {s2.sequence_number} ('{s2.headline}') share high headline similarity ({sim_ratio:.0%})."
                )

            # Key message exact or high similarity
            if s1.key_message and s2.key_message:
                km_ratio = difflib.SequenceMatcher(None, s1.key_message.lower(), s2.key_message.lower()).ratio()
                if km_ratio > 0.85:
                    duplicate_concepts.append(
                        f"Slide {s1.sequence_number} and Slide {s2.sequence_number} have duplicate key messages."
                    )

            # Redundant visual hook with identical layout
            if (
                s1.visual_intent.visual_type != "none"
                and s1.visual_intent.visual_type == s2.visual_intent.visual_type
                and s1.layout == s2.layout
                and s1.visual_intent.visual_type not in ("evidence_ledger", "table")
            ):
                warnings.append(
                    f"Duplicate visual hook '{s1.visual_intent.visual_type}' used on both Slide {s1.sequence_number} and Slide {s2.sequence_number}."
                )

    # 2. Unanswered User Questions Detection
    combined_slide_text = " ".join([
        f"{s.headline} {s.subtitle} {s.key_message} {' '.join(s.bullet_points)}"
        for s in slides
    ]).lower()

    for q in intent.key_questions_to_answer:
        # Extract meaningful keywords from question (excluding stop words)
        words = [w for w in re.findall(r'\b[a-zA-Z]{4,}\b', q.lower()) if w not in ("what", "where", "when", "which", "does", "about", "current", "this", "these")]
        if words:
            matched_words = [w for w in words if w in combined_slide_text]
            # If less than 20% of keywords appear in any slide text, flag as potentially unanswered
            if len(matched_words) == 0:
                unanswered_questions.append(q)

    # 3. Evidence grounding check
    for s in slides:
        if not s.evidence_ids and not s.information_unit_ids and s.layout not in ("title_hero", "kpi_summary"):
            unsupported_claims.append(f"Slide {s.sequence_number} ('{s.headline}') lacks explicit evidence or information unit citations.")

    # 4. Slide count constraint satisfaction check
    constraint = ctx.slide_count_constraint
    if not constraint.is_satisfied(len(slides)):
        warnings.append(
            f"Slide count ({len(slides)}) does not strictly satisfy constraint {constraint.mode.value} (target={constraint.target}, min={constraint.min_slides}, max={constraint.max_slides})."
        )

    # Compile recommendations
    if duplicate_concepts:
        recommendations.append("Consolidate overlapping slides or differentiate their core analytical lenses.")
    if unanswered_questions:
        recommendations.append(f"Incorporate explicit answers to {len(unanswered_questions)} unaddressed key questions.")
    if unsupported_claims:
        recommendations.append("Bind ungrounded slides to specific items in the shared evidence ledger.")

    is_valid = len(duplicate_concepts) == 0 and len(slides) >= 3

    return PlanningValidationResult(
        is_valid=is_valid,
        duplicate_concepts_detected=duplicate_concepts,
        unanswered_user_questions=unanswered_questions,
        unsupported_claims=unsupported_claims,
        warnings=warnings,
        recommendations=recommendations
    )
