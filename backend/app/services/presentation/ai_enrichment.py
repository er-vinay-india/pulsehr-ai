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
    """Regenerates a specific slide's narrative and title based on user instructions."""
    updated_deck = copy.deepcopy(deck_spec)
    slides = updated_deck.get("slides", [])
    target_slide = next((s for s in slides if s["id"] == slide_id), None)
    if not target_slide:
        raise ValueError(f"Slide '{slide_id}' not found in presentation deck.")

    audience = updated_deck.get("metadata", {}).get("audience", "Leadership")
    inst_cfg = _load_instructions_config()
    template = inst_cfg.get(
        "regeneration_prompt_template",
        "Regenerate Slide #{slide_order} for {audience}. Category: {category}. Current Title: {current_title}. User Instructions: {user_instructions}. Return JSON object."
    )

    prompt = template.format(
        slide_order=target_slide.get("order", 1),
        audience=audience,
        category=target_slide.get("category", "EXECUTIVE REVIEW"),
        current_title=target_slide.get("title", ""),
        user_instructions=user_instructions
    )

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
                if data.get("title"):
                    target_slide["title"] = format_display_label(data["title"])
                if data.get("subtitle"):
                    target_slide["subtitle"] = data["subtitle"]
                if data.get("narrative"):
                    target_slide["narrative"] = sanitize_llm_text(data["narrative"])
                    if data.get("speaker_notes"):
                        target_slide["speaker_notes"] = data["speaker_notes"]
                    updated_deck["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    return updated_deck
    except Exception as exc:
        logger.warning(f"AI slide regeneration failed, falling back to rule-based update: {exc}")

    clean_inst = user_instructions.strip().capitalize()
    target_slide["title"] = f"{target_slide['title']}: {clean_inst[:45]}"
    target_slide["narrative"] = f"{target_slide['narrative']} Specific focus applied: {clean_inst}."
    target_slide["speaker_notes"] = f"Presenter note: Emphasize {clean_inst} during this discussion."
    updated_deck["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return updated_deck
