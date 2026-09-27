import copy
import datetime
import json
import logging
from pathlib import Path
import re
from typing import Any
import httpx

from ...core import config
from ..display_formatters import format_display_label, sanitize_llm_text

logger = logging.getLogger(__name__)

TEMPLATES_PATH = Path(__file__).parent / "templates" / "instructions.json"


def _load_instructions_config() -> dict[str, Any]:
    try:
        with open(TEMPLATES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning(f"Could not load instructions.json: {exc}")
        return {}


def _call_ai_presentation_enrichment(
    domain: str,
    objective: str,
    audience: str,
    instructions: str,
    is_sales: bool,
    is_hr: bool,
    total_records: int,
    file_label: str,
    slides: list[dict[str, Any]]
) -> list[dict[str, str]] | None:
    """Calls Ollama LLM to enrich slide narrative, titles, and speaker notes using external prompt templates."""
    inst_cfg = _load_instructions_config()
    personas = inst_cfg.get("personas", {})

    if is_sales:
        persona_info = personas.get("sales", {
            "persona": "Executive Commercial Strategy Director",
            "tone_rule": "Use strictly commercial terminology."
        })
    elif is_hr:
        persona_info = personas.get("workforce", {
            "persona": "Chief People Officer & Workforce Strategist",
            "tone_rule": "Use evidence-based workforce and people analytics terminology."
        })
    else:
        persona_info = personas.get("general", {
            "persona": "Operational Analytics Strategist",
            "tone_rule": "Use objective, data-driven operational terminology."
        })

    persona = persona_info["persona"]
    tone_rule = persona_info["tone_rule"]

    slide_summaries = [
        {"order": s["order"], "layout": s["layout"], "category": s["category"], "current_title": s["title"]}
        for s in slides
    ]

    template = inst_cfg.get(
        "enrichment_prompt_template",
        "You are {persona}.\nRefine executive presentation for {audience}.\nDataset: '{file_label}' ({domain}, {total_records} records).\nTone Rule: {tone_rule}\nUser Instructions: {instructions}\n\nSlide Structure:\n{slide_structure_json}\n\nReturn ONLY valid JSON array."
    )
    prompt = template.format(
        persona=persona,
        audience=audience,
        objective=objective,
        file_label=file_label,
        domain=domain,
        total_records=total_records,
        tone_rule=tone_rule,
        instructions=instructions or "Provide crisp executive storytelling.",
        slide_structure_json=json.dumps(slide_summaries, indent=2)
    )

    try:
        from ..gateway.model_gateway import ModelGateway
        from ...core.models_config import ModelRole
        res = ModelGateway.generate(
            role=ModelRole.WRITER,
            prompt=prompt,
            step_name="presentation_deck_enrichment"
        )
        if res.success and res.raw_text:
            match = re.search(r'\[\s*\{[\s\S]*\}\s*\]', res.raw_text)
            if match:
                return json.loads(match.group(0))
    except Exception:
        pass
    return None


def regenerate_single_slide(
    deck_spec: dict[str, Any],
    slide_id: str,
    user_instructions: str
) -> dict[str, Any]:
    """Regenerates a specific slide using the canonical visual intelligence pipeline.

    Preserves other slides and manual user edits elsewhere, parses targeted intent
    (e.g., 'make it shorter', 'use a chart', 'more visual'), enforces strict layout
    budgets so text never overflows the 1920x1080 canvas, and re-materializes VisualSpecification.
    """
    updated_deck = copy.deepcopy(deck_spec)
    slides = updated_deck.get("slides", [])
    target_idx = next((i for i, s in enumerate(slides) if s["id"] == slide_id), None)
    if target_idx is None:
        raise ValueError(f"Slide '{slide_id}' not found in presentation deck.")

    target_slide = slides[target_idx]
    theme_id = (
        updated_deck.get("metadata", {}).get("theme_id")
        or updated_deck.get("theme", {}).get("id")
        or "bold_signal"
    )
    audience = updated_deck.get("metadata", {}).get("audience", "Executive Leadership")
    u_lower = (user_instructions or "").lower()

    # 1. Targeted Intent Parsing
    wants_shorter = any(w in u_lower for w in ["short", "concise", "condense", "brief", "summarize"])
    wants_visual = any(w in u_lower for w in ["visual", "chart", "graph", "plot"])
    wants_comparison = any(w in u_lower for w in ["comparison", "compare", "versus", "vs", "split"])

    if wants_comparison:
        target_slide["layout"] = "two_charts" if target_slide.get("chart") else "comparison_split"
    elif wants_visual and (target_slide.get("chart") or target_slide.get("visual_spec", {}).get("chart_spec")):
        target_slide["layout"] = "full_chart_takeaway"

    # 2. Content generation / rewriting
    inst_cfg = _load_instructions_config()
    template = inst_cfg.get(
        "regeneration_prompt_template",
        "Regenerate Slide #{slide_order} for {audience}. Category: {category}. Current Title: {current_title}. User Instructions: {user_instructions}. Return JSON with 'title', 'subtitle', 'narrative', 'bullets'."
    )
    prompt = template.format(
        slide_order=target_slide.get("order", target_idx + 1),
        audience=audience,
        category=target_slide.get("category", "EXECUTIVE REVIEW"),
        current_title=target_slide.get("title", ""),
        user_instructions=user_instructions
    )

    prompt += "\nUse only the current slide and evidence below. Preserve numerical claims, dates and units; do not invent facts. Return JSON only.\n"
    prompt += json.dumps({"slide": target_slide, "evidence": updated_deck.get("evidence_ledger", [])}, default=str)

    generated_title = None
    generated_narrative = None
    generated_subtitle = None
    generated_bullets = None

    try:
        from ..gateway.model_gateway import ModelGateway
        from ...core.models_config import ModelRole
        res = ModelGateway.generate(
            role=ModelRole.WRITER,
            prompt=prompt,
            step_name="regenerate_single_slide"
        )
        if res.success and res.raw_text:
            match = re.search(r'\{[\s\S]*\}', res.raw_text)
            if match:
                data = json.loads(match.group(0))
                generated_title = data.get("title")
                generated_subtitle = data.get("subtitle")
                generated_narrative = data.get("narrative")
                generated_bullets = data.get("bullets")
                if data.get("speaker_notes"):
                    target_slide["speaker_notes"] = data["speaker_notes"]
    except Exception as exc:
        logger.warning(f"AI slide regeneration call skipped or failed, using heuristic: {exc}")

    if not any([generated_title, generated_narrative, generated_subtitle, generated_bullets]):
        raise ValueError("HRIDAY could not produce a valid refinement. Your slide has not been changed. Please retry.")
    if generated_title:
        target_slide["title"] = format_display_label(generated_title)

    if generated_subtitle:
        target_slide["subtitle"] = generated_subtitle

    if generated_narrative:
        target_slide["narrative"] = sanitize_llm_text(generated_narrative)

    if generated_bullets and isinstance(generated_bullets, list):
        target_slide["bullets"] = [str(b) for b in generated_bullets if b]

    # 3. Content Budget & Layout Enforcement (No overflow on 1920x1080 canvas)
    from .visual.layout_registry import LayoutRegistry
    current_layout_name = target_slide.get("layout", "chart_narrative")
    budget = LayoutRegistry.get_budget(current_layout_name)

    # Bound headline
    if len(target_slide.get("title", "")) > budget.max_headline_chars:
        target_slide["title"] = target_slide["title"][:budget.max_headline_chars - 1].rsplit(' ', 1)[0] + '…'

    # Bound narrative & bullets
    max_body_words = budget.max_body_words if not wants_shorter else min(budget.max_body_words, 25)
    narrative_words = target_slide.get("narrative", "").split()
    if len(narrative_words) > max_body_words:
        target_slide["narrative"] = " ".join(narrative_words[:max_body_words]) + "."

    max_insights = budget.max_insights if not wants_shorter else min(budget.max_insights, 2)
    current_bullets = target_slide.get("bullets", [])
    if len(current_bullets) > max_insights:
        target_slide["bullets"] = current_bullets[:max_insights]

    # 4. Canonical Phase 4 Visual Intelligence Re-materialization
    try:
        from .visual import VisualIntelligenceEngine
        v_engine = VisualIntelligenceEngine()
        v_spec = v_engine.process_slide(
            target_slide,
            theme_id=theme_id,
            sequence_number=target_slide.get("order", target_idx + 1),
            total_slides=len(slides)
        )
        target_slide["visual_spec"] = v_spec.model_dump()
        if v_spec.chart_spec and not target_slide.get("chart"):
            target_slide["chart"] = {
                "type": v_spec.chart_spec.family.value.lower(),
                "title": v_spec.chart_spec.title,
                "subtitle": v_spec.chart_spec.subtitle,
                "categories": v_spec.chart_spec.categories,
                "series": [{"name": ser.name, "values": ser.data} for ser in v_spec.chart_spec.series]
            }
    except Exception as exc:
        logger.warning(f"Failed to re-materialize visual_spec for regenerated slide: {exc}")

    target_slide["provenance"] = "REGENERATED"
    updated_deck["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 5. Persist to database if deck exists
    deck_id = updated_deck.get("id")
    if deck_id:
        try:
            from ...db.database import get_connection
            with get_connection() as conn:
                conn.execute(
                    "UPDATE presentation_decks SET spec_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (json.dumps(updated_deck), deck_id)
                )
                conn.commit()
        except Exception as exc:
            logger.debug(f"Deck database update during slide regeneration skipped: {exc}")

    return updated_deck
