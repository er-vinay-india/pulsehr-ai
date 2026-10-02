from __future__ import annotations

import json
import logging
import re
from typing import Any

from ...gateway.model_gateway import ModelGateway, extract_json_payload
from ....core.models_config import ModelRole
from .director_models import (
    AudienceSeniority,
    DeliveryMode,
    PresentationIntent,
    PresentationPlanningContext,
)

logger = logging.getLogger(__name__)


def plan_intent(ctx: PresentationPlanningContext, max_retries: int = 1) -> PresentationIntent:
    """Stage 1: Determines high-level semantic intent, audience framing, and target questions."""
    # Determine default seniority from audience string
    aud_lower = ctx.audience.lower()
    default_seniority = AudienceSeniority.C_SUITE
    if "engineer" in aud_lower or "developer" in aud_lower or "technical" in aud_lower or "architect" in aud_lower:
        default_seniority = AudienceSeniority.TECHNICAL_OPERATIONAL
    elif "director" in aud_lower or "vp" in aud_lower or "head" in aud_lower:
        default_seniority = AudienceSeniority.VP_DIRECTOR
    elif "manager" in aud_lower or "lead" in aud_lower:
        default_seniority = AudienceSeniority.MANAGEMENT

    # Determine default delivery mode
    default_delivery = DeliveryMode.LIVE_EXECUTIVE_PITCH
    if "read" in aud_lower or "memo" in ctx.objective.lower():
        default_delivery = DeliveryMode.STANDALONE_READ
    elif "board" in aud_lower or "board" in ctx.objective.lower():
        default_delivery = DeliveryMode.BOARD_REVIEW
    elif "tech" in aud_lower or "workshop" in ctx.objective.lower():
        default_delivery = DeliveryMode.TECHNICAL_WORKSHOP

    # Extract user questions from instructions if any
    raw_instructions = ctx.instructions or ""
    detected_questions = re.findall(r'([^.?!]*\?)', raw_instructions)
    clean_questions = [q.strip() for q in detected_questions if len(q.strip()) > 8]

    if max_retries < 0:
        return _fallback_intent(ctx, clean_questions, default_seniority, default_delivery)

    brief_info = ""
    if ctx.brief:
        brief_info = f"""
- Requested Decision / Action: {ctx.brief.decision_requested or 'None specified'}
- Main Takeaway: {ctx.brief.main_takeaway or 'None specified'}
- Presentation Time: {ctx.brief.presentation_time_minutes} minutes
- Deliverable: {ctx.brief.deliverable}
- Success Criterion: {ctx.brief.success_criterion}"""

    prompt = f"""You are the Executive Presentation Director. Analyze the presentation request and define the presentation intent.

## Input Context:
- Domain: {ctx.domain}
- Objective: {ctx.objective}
- Target Audience: {ctx.audience}
- Instructions: {ctx.instructions or 'Produce a rigorous, high-impact executive presentation.'}{brief_info}
- Dataset: '{ctx.dataset_label}' ({ctx.total_records:,} records, {ctx.completeness_pct}% completeness)
- Baseline Benchmark: {ctx.baseline_benchmark}
- Observation Window: {ctx.reporting_period}

## Instructions:
Define:
1. domain: domain name (e.g. Sales, Finance, HR, Operations, Tech Architecture)
2. purpose: concise primary purpose
3. primary_goal: executive outcome to achieve
4. target_audience: refined audience description
5. audience_seniority: one of ["C_SUITE", "VP_DIRECTOR", "MANAGEMENT", "TECHNICAL_OPERATIONAL", "GENERAL"]
6. technical_depth: one of ["high_level", "balanced", "deep_dive"]
7. delivery_mode: one of ["LIVE_EXECUTIVE_PITCH", "BOARD_REVIEW", "STANDALONE_READ", "TECHNICAL_WORKSHOP", "STATUS_UPDATE"]
8. key_takeaways: list of 3-5 critical business conclusions
9. key_questions_to_answer: list of 2-5 explicit business questions this deck must answer

Return ONLY a valid JSON object matching this schema:
{{
  "domain": "{ctx.domain}",
  "purpose": "Executive performance review and resource optimization",
  "primary_goal": "Align leadership on resource allocation and operational priorities",
  "target_audience": "{ctx.audience}",
  "audience_seniority": "{default_seniority.value}",
  "technical_depth": "balanced",
  "delivery_mode": "{default_delivery.value}",
  "key_takeaways": ["Takeaway 1", "Takeaway 2", "Takeaway 3"],
  "key_questions_to_answer": ["Question 1?", "Question 2?"]
}}
"""

    for attempt in range(max_retries + 1):
        try:
            result = ModelGateway.generate(
                role=ModelRole.ANALYST,
                prompt=prompt,
                report_id=f"director-intent-{ctx.dataset_label}",
                step_name="director_intent_planner"
            )
            if result.success and result.raw_text:
                payload = extract_json_payload(result.raw_text)
                parsed = json.loads(payload)
                if isinstance(parsed, dict) and parsed.get("domain") and parsed.get("purpose"):
                    questions = parsed.get("key_questions_to_answer") or []
                    # Guarantee user questions from prompt are preserved
                    for q in clean_questions:
                        if q not in questions:
                            questions.append(q)
                    return PresentationIntent(
                        domain=parsed.get("domain", ctx.domain),
                        purpose=parsed.get("purpose", ctx.objective),
                        primary_goal=parsed.get("primary_goal", ctx.objective),
                        target_audience=parsed.get("target_audience", ctx.audience),
                        audience_seniority=AudienceSeniority(parsed.get("audience_seniority", default_seniority.value)),
                        technical_depth=parsed.get("technical_depth", "balanced"),
                        delivery_mode=DeliveryMode(parsed.get("delivery_mode", default_delivery.value)),
                        key_takeaways=parsed.get("key_takeaways", [
                            f"Verified empirical baseline across {ctx.total_records:,} records.",
                            "Identified performance variance requiring strategic focus.",
                            "Formulated actionable governance initiatives."
                        ]),
                        key_questions_to_answer=questions or [
                            "What is the current operational baseline?",
                            "What are the highest priority variance drivers?",
                            "What strategic actions should leadership approve?"
                        ]
                    )
        except Exception as exc:
            logger.debug(f"Intent planner attempt {attempt} failed: {exc}")

    # Fallback deterministic intent
    return _fallback_intent(ctx, clean_questions, default_seniority, default_delivery)


def _fallback_intent(
    ctx: PresentationPlanningContext,
    clean_questions: list[str],
    default_seniority: AudienceSeniority,
    default_delivery: DeliveryMode
) -> PresentationIntent:
    brief = ctx.brief
    fallback_questions = list(clean_questions) if clean_questions else [
        f"What does the {ctx.domain} empirical evidence reveal about operational throughput?",
        "Where are the key operational bottlenecks or productivity variances?",
        "What governance initiatives will stabilize and optimize performance?"
    ]
    if brief and brief.decision_requested:
        fallback_questions.append(f"How will leadership execute the decision to {brief.decision_requested}?")

    takeaways = [
        f"Ground truth established across {ctx.total_records:,} verified records ({ctx.completeness_pct}% data integrity).",
        f"Baseline metric: {ctx.baseline_benchmark or 'Audited Mean'} with {ctx.dispersion_metric or 'observed spread'}.",
        "Empirically grounded action plan formulated with clear owners and timeline."
    ]
    if brief and brief.main_takeaway:
        takeaways.insert(0, brief.main_takeaway)

    primary_goal = (
        f"Enable leadership to decide or do '{brief.decision_requested}' based on {ctx.domain} evidence"
        if (brief and brief.decision_requested)
        else f"Inform leadership on {ctx.domain} findings and drive strategic alignment"
    )

    return PresentationIntent(
        domain=ctx.domain or "Enterprise Operations",
        purpose=ctx.objective or "Executive Review",
        primary_goal=primary_goal,
        target_audience=ctx.audience or "Executive Leadership",
        audience_seniority=default_seniority,
        technical_depth="balanced",
        delivery_mode=default_delivery,
        key_takeaways=takeaways,
        key_questions_to_answer=fallback_questions
    )

