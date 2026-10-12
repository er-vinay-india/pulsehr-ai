"""
Migration 0004: Add industry personas table and initial seed data.
"""
from __future__ import annotations

import json
import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS industry_personas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            persona_key TEXT UNIQUE NOT NULL,
            role_title TEXT NOT NULL,
            industry_domain TEXT NOT NULL,
            target_audience TEXT NOT NULL,
            standard_report_name TEXT NOT NULL,
            report_description TEXT NOT NULL,
            identifying_keywords_json TEXT NOT NULL,
            required_metrics_json TEXT NOT NULL,
            core_kpis_json TEXT NOT NULL,
            slide_outline_json TEXT NOT NULL,
            tone_guidelines TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_personas_domain ON industry_personas(industry_domain)")

    try:
        cur = conn.execute("SELECT COUNT(*) FROM industry_personas")
        count = cur.fetchone()[0]
        if count < 20:
            from app.services.presentation.industry_personas_seed import INDUSTRY_PERSONAS
            for p in INDUSTRY_PERSONAS:
                conn.execute(
                    """
                    INSERT INTO industry_personas (
                        persona_key, role_title, industry_domain, target_audience,
                        standard_report_name, report_description, identifying_keywords_json,
                        required_metrics_json, core_kpis_json, slide_outline_json, tone_guidelines
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(persona_key) DO UPDATE SET
                        role_title = excluded.role_title,
                        industry_domain = excluded.industry_domain,
                        target_audience = excluded.target_audience,
                        standard_report_name = excluded.standard_report_name,
                        report_description = excluded.report_description,
                        identifying_keywords_json = excluded.identifying_keywords_json,
                        required_metrics_json = excluded.required_metrics_json,
                        core_kpis_json = excluded.core_kpis_json,
                        slide_outline_json = excluded.slide_outline_json,
                        tone_guidelines = excluded.tone_guidelines
                    """,
                    (
                        p["persona_key"],
                        p["role_title"],
                        p["industry_domain"],
                        p["target_audience"],
                        p["standard_report_name"],
                        p["report_description"],
                        json.dumps(p["identifying_keywords"]),
                        json.dumps(p["required_metrics"]),
                        json.dumps(p["core_kpis"]),
                        json.dumps(p["slide_outline"]),
                        p["tone_guidelines"],
                    ),
                )
    except Exception:
        pass
