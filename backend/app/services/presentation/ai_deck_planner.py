import json
import logging
from pathlib import Path
import re
from typing import Any
import httpx

from ...core import config

logger = logging.getLogger(__name__)

GUIDELINES_PATH = Path(__file__).parent / "templates" / "ai_deck_guidelines.json"


def load_ai_deck_guidelines() -> dict[str, Any]:
    try:
        with open(GUIDELINES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning(f"Could not load ai_deck_guidelines.json: {exc}")
        return {}


def plan_deck_with_ai(
    domain: str,
    objective: str,
    audience: str,
    instructions: str,
    total_records: int,
    file_label: str,
    mean_val_str: str,
    dispersion_metric_str: str,
    reporting_period_summary: str,
    completeness_pct: float,
    prioritized_facts: list[dict[str, Any]],
    industrial_models: dict[str, Any] | None,
    available_charts: dict[str, bool],
    evidence_ledger: list[dict[str, Any]],
    is_sales: bool = False,
    is_hr: bool = False,
    **kwargs: Any
) -> dict[str, Any] | None:
    """Uses Ollama (defaulting to qwen3.5:9b) to dynamically plan the full presentation deck in JSON format.

    The model generates a structured JSON slide specification governed by the system guidelines,
    dynamically expanding into 12 to 20+ slides reflecting all available evidence and industrial models.
    """
    guidelines = load_ai_deck_guidelines()
    t9 = industrial_models.get("talent_9box") if industrial_models else None
    bs = industrial_models.get("burnout_strain") if industrial_models else None
    bf = industrial_models.get("bradford_factor") if industrial_models else None

    # Summarize available assets for the LLM
    available_assets = {
        "line_chart": available_charts.get("line_chart", False),
        "bar_chart": available_charts.get("bar_chart", False),
        "donut_chart": available_charts.get("donut_chart", False),
        "talent_9box_matrix": bool(t9 and t9.get("available")),
        "burnout_strain_diagnostic": bool(bs and bs.get("available")),
        "bradford_disruption_index": bool(bf and bf.get("available")),
        "data_evidence_table": True,
        "action_plan_initiatives": True,
        "execution_raci_matrix": True,
        "evidence_ledger_part1": True,
        "evidence_ledger_part2": len(evidence_ledger) > 6
    }

    facts_summary = [
        {
            "badge": f.get("badge"),
            "headline": f.get("headline"),
            "comparison": f.get("comparison"),
            "why_it_matters": f.get("why_it_matters")
        }
        for f in prioritized_facts[:8]
    ]

    prompt = f"""You are the Lead Executive Presentation Strategist for PulseHR AI.
Your objective: Generate a complete, multi-slide executive presentation plan in valid JSON.

## Presentation Metadata:
- Dataset: '{file_label}' ({domain} domain)
- Total Audited Population: {total_records:,} records ({completeness_pct}% completeness)
- Baseline Mean Benchmark: {mean_val_str}
- Observation Window: {reporting_period_summary}
- Dispersion Ratio: {dispersion_metric_str}
- Objective: {objective}
- Target Audience: {audience}
- User Instructions: {instructions or 'Produce a rigorous, flexible executive deck.'}

## Available Visual & Model Assets:
{json.dumps(available_assets, indent=2)}

## Prioritized Empirical Findings:
{json.dumps(facts_summary, indent=2)}

## Core Presentation Rules:
1. FLEXIBLE SLIDE COUNT: Expand each stage into dedicated slides based on available evidence. Aim for 14 to 18 slides.
   - Stage 1: Executive Summary (title_hero)
   - Stage 2: Scope & Baseline (kpi_summary)
   - Stage 3: Operational Strengths (1-2 slides, visual_hook='line_chart' or 'none')
   - Stage 4: Operational Headwinds (1-2 slides, visual_hook='bar_chart' or 'none')
   - Stage 5: Talent & Workforce Analytics (Generate dedicated slides for available models:
     * visual_hook='donut_chart' for Segment, Cohort or Department Breakdown (REQUIRED when donut_chart is True, layout='chart_narrative')
     * visual_hook='talent_9box' for McKinsey 9-Box Matrix (when talent_9box_matrix is True)
     * visual_hook='burnout_strain' for Overtime & Burnout Diagnostic (when burnout_strain_diagnostic is True)
     * visual_hook='bradford_factor' for Absenteeism Disruption Index (when bradford_disruption_index is True))
   - Stage 6: Honest Governance & Boundaries (1 slide comparison_split, 1 slide table_detail with visual_hook='table_categorical')
   - Stage 7: Strategic Roadmap (1 slide action_plan with visual_hook='action_plan', 1 slide table_detail with visual_hook='raci_matrix')
   - Stage 8: Evidence Ledgers (1 slide visual_hook='evidence_ledger_part1', plus 1 slide visual_hook='evidence_ledger_part2' if evidence_ledger_part2 is True)
2. Every slide title must be an assertive, conclusion-driven headline under 78 characters.
3. Every narrative must weave verified counts and percentages (e.g. 'X of {total_records:,} records (Z%)').
4. Valid visual_hook values: 'none', 'line_chart', 'bar_chart', 'donut_chart', 'rel_chart', 'talent_9box', 'burnout_strain', 'bradford_factor', 'table_categorical', 'action_plan', 'raci_matrix', 'evidence_ledger_part1', 'evidence_ledger_part2'.

Return ONLY a JSON object matching this schema:
{{
  "deck_title": "Executive Review Title",
  "slides": [
    {{
      "order": 1,
      "category": "EXECUTIVE SUMMARY",
      "layout": "title_hero",
      "title": "Assertive Headline Under 78 Chars",
      "subtitle": "Informative Subtitle",
      "narrative": "[Evidence] Concrete data-driven statement.",
      "visual_hook": "none",
      "evidence_id": "EVID-EXEC-01"
    }}
  ]
}}
"""

    from ..gateway.model_gateway import ModelGateway
    from ...core.models_config import ModelRole

    try:
        result = ModelGateway.generate(
            role=ModelRole.ANALYST,
            prompt=prompt,
            report_id=f"deck-{file_label}",
            step_name="ai_deck_planner"
        )
        if result.success and result.raw_text:
            match = re.search(r'\{[\s\S]*\}', result.raw_text)
            if match:
                parsed = json.loads(match.group(0))
                if parsed.get("slides") and len(parsed["slides"]) >= 8:
                    logger.info(f"AI Deck Planner successfully generated {len(parsed['slides'])} slides via ModelGateway ({result.model_used}).")
                    return parsed
    except Exception as exc:
        logger.warning(f"AI Deck Planner fallback triggered due to exception: {exc}")

    return None
