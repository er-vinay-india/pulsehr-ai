"""
Persona Router & Industry Standard Template Matcher.
Automatically detects executive persona from dataset characteristics,
column headers, sheet names, metrics, and domain cues.
Filters out irrelevant personas to guarantee high data grounding.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

from ...db.database import get_connection

logger = logging.getLogger(__name__)


def load_all_personas(conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    """Loads all seeded industry personas from persistent SQLite database."""
    close_after = False
    if conn is None:
        conn = get_connection()
        close_after = True

    try:
        rows = conn.execute(
            """
            SELECT id, persona_key, role_title, industry_domain, target_audience,
                   standard_report_name, report_description, identifying_keywords_json,
                   required_metrics_json, core_kpis_json, slide_outline_json, tone_guidelines
            FROM industry_personas
            ORDER BY id ASC
            """
        ).fetchall()

        personas = []
        for r in rows:
            personas.append({
                "id": r["id"],
                "persona_key": r["persona_key"],
                "role_title": r["role_title"],
                "industry_domain": r["industry_domain"],
                "target_audience": r["target_audience"],
                "standard_report_name": r["standard_report_name"],
                "report_description": r["report_description"],
                "identifying_keywords": json.loads(r["identifying_keywords_json"] or "[]"),
                "required_metrics": json.loads(r["required_metrics_json"] or "[]"),
                "core_kpis": json.loads(r["core_kpis_json"] or "[]"),
                "slide_outline": json.loads(r["slide_outline_json"] or "[]"),
                "tone_guidelines": r["tone_guidelines"],
            })
        return personas
    finally:
        if close_after:
            conn.close()


def detect_dataset_persona(
    dataset_context: dict[str, Any],
    conn: sqlite3.Connection | None = None
) -> dict[str, Any]:
    """Analyzes dataset columns, sheet name, sample records, and domain to detect best matching persona.

    Runs automatically without requiring explicit user selection.
    If no industry persona matches with sufficient confidence, gracefully falls back to generic executive strategist.
    """
    personas = load_all_personas(conn)
    if not personas:
        from .industry_personas_seed import INDUSTRY_PERSONAS
        personas = INDUSTRY_PERSONAS

    # Extract signals from dataset context
    target_sheet = dataset_context.get("target_sheet") or {}
    sheet_name = str(target_sheet.get("name") or target_sheet.get("original_name") or "").lower()
    domain_str = str(dataset_context.get("domain") or "").lower()
    columns = [str(c).lower().strip() for c in dataset_context.get("columns", [])]
    records = dataset_context.get("records", [])

    # Sample cell tokens
    sample_cell_text = set()
    for rec in records[:15]:
        if isinstance(rec, dict):
            for k, v in rec.items():
                if isinstance(v, str) and len(v) < 40:
                    sample_cell_text.add(v.lower().strip())

    col_text_blob = " ".join(columns)

    best_match = None
    highest_score = 0
    generic_persona = None

    for p in personas:
        if p["persona_key"] == "executive_strategist_generic":
            generic_persona = p
            continue

        score = 0
        keywords = p.get("identifying_keywords", [])

        for kw in keywords:
            kw_clean = kw.lower().strip()
            # 1. Exact or substring match in column names (highest signal)
            if any(kw_clean == c or kw_clean in c for c in columns):
                score += 4
            elif kw_clean in col_text_blob:
                score += 2

            # 2. Match in sheet name
            if kw_clean in sheet_name:
                score += 3

            # 3. Match in domain string
            if kw_clean in domain_str:
                score += 3

            # 4. Match in sample categorical values
            if any(kw_clean in cell for cell in sample_cell_text):
                score += 1

        # Match in domain name directly
        if p["industry_domain"].lower() in domain_str or domain_str in p["industry_domain"].lower():
            score += 4

        if score > highest_score:
            highest_score = score
            best_match = p

    # Threshold for auto-selection: at least 3 points (e.g. 1 exact column or domain match)
    if best_match and highest_score >= 3:
        result = dict(best_match)
        result["confidence"] = min(1.0, round(highest_score / 14.0, 2))
        result["is_auto_detected"] = True
        result["match_score"] = highest_score
        return result

    # Fallback to generic executive strategist
    if not generic_persona:
        generic_persona = personas[-1]

    result = dict(generic_persona)
    result["confidence"] = 0.50
    result["is_auto_detected"] = False
    result["match_score"] = 0
    return result


def get_relevant_personas_for_dataset(
    dataset_context: dict[str, Any],
    conn: sqlite3.Connection | None = None
) -> list[dict[str, Any]]:
    """Returns only personas relevant to the data, filtering out unrelated industry personas.

    Guarantees that irrelevant personas (e.g. Healthcare for a Sales dataset) are completely excluded.
    """
    personas = load_all_personas(conn)
    detected = detect_dataset_persona(dataset_context, conn)

    relevant = []
    # If a specific persona was detected with confidence, include it first
    if detected.get("is_auto_detected"):
        relevant.append(detected)

    # Find other personas with positive match score
    columns = [str(c).lower().strip() for c in dataset_context.get("columns", [])]
    col_text_blob = " ".join(columns)
    sheet_name = str((dataset_context.get("target_sheet") or {}).get("name") or "").lower()
    domain_str = str(dataset_context.get("domain") or "").lower()

    for p in personas:
        if p["persona_key"] in (detected["persona_key"], "executive_strategist_generic"):
            continue

        score = 0
        for kw in p.get("identifying_keywords", []):
            kw_clean = kw.lower().strip()
            if any(kw_clean == c or kw_clean in c for c in columns):
                score += 3
            if kw_clean in sheet_name or kw_clean in domain_str:
                score += 2

        if score >= 3:
            p_copy = dict(p)
            p_copy["confidence"] = min(0.9, round(score / 14.0, 2))
            p_copy["match_score"] = score
            relevant.append(p_copy)

    # Always include the generic executive strategist as an option
    generic = next((p for p in personas if p["persona_key"] == "executive_strategist_generic"), None)
    if generic and generic["persona_key"] != detected["persona_key"]:
        g_copy = dict(generic)
        g_copy["confidence"] = 0.50
        g_copy["match_score"] = 0
        relevant.append(g_copy)

    return relevant
