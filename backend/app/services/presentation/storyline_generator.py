import logging
from typing import Any

logger = logging.getLogger(__name__)


def plan_dynamic_storyline(
    profiled_data: dict[str, Any],
    domain: str,
    target_length: int = 0
) -> list[dict[str, Any]]:
    """Synthesizes an evidence-driven presentation outline based on actual dataset characteristics.
    
    NEVER forces an arbitrary 8-stage narrative.
    Derives sections from:
    - Audit/compliance distributions if status columns exist
    - Longitudinal trends if date dimensions exist
    - Comparative rankings if multiple entities/departments exist
    - Concentration risks if skews/outliers exist
    """
    total_records = profiled_data.get("total_records", 0)
    ranked_cat = profiled_data.get("ranked_categorical", [])
    ranked_num = profiled_data.get("ranked_numeric", [])
    status_dists = profiled_data.get("status_distributions", {})
    patterns = profiled_data.get("patterns", [])

    is_audit = bool(status_dists) or "audit" in domain.lower() or "compliance" in domain.lower()
    has_dates = any("date" in c.lower() or "period" in c.lower() or "month" in c.lower() for c in profiled_data.get("dimensions", {}))
    has_numerical = len(ranked_num) > 0
    has_entities = len(ranked_cat) > 0

    storyline = []

    # 1. Executive Summary (Always First, with real calculated findings)
    storyline.append({
        "section_id": "exec_summary",
        "category": "EXECUTIVE SUMMARY",
        "focus": "Core empirical findings, totals, and primary concentrations",
        "layout": "title_hero"
    })

    # 2. Analysis Scope (Always Early, explicitly surfacing dataset facts)
    storyline.append({
        "section_id": "analysis_scope",
        "category": "ANALYSIS SCOPE",
        "focus": f"Explicit review boundaries for {total_records:,} records, coverage & completeness",
        "layout": "kpi_summary"
    })

    # 3. Primary Distribution or Macro Outcome
    if is_audit and status_dists:
        stat_col = list(status_dists.keys())[0]
        storyline.append({
            "section_id": "status_distribution",
            "category": "AUDIT DISTRIBUTION",
            "focus": f"Overall outcome distribution across {stat_col}",
            "layout": "full_chart_takeaway"
        })
    elif has_numerical:
        num_name = ranked_num[0]["name"]
        storyline.append({
            "section_id": "baseline_outcome",
            "category": "EMPIRICAL BASELINE",
            "focus": f"Macro benchmark and central tendency for {num_name}",
            "layout": "kpi_summary"
        })

    # 4. Longitudinal Trend (if dates present)
    if has_dates:
        storyline.append({
            "section_id": "trend_baseline",
            "category": "LONGITUDINAL BASELINE",
            "focus": "Chronological throughput and cyclical behavior",
            "layout": "chart_narrative"
        })

    # 5. Entity Comparison & Performance Spread
    if has_entities:
        lead_cat = ranked_cat[0]["name"]
        storyline.append({
            "section_id": "entity_breakdown",
            "category": "CATEGORY BREAKDOWN" if is_audit else "OPERATIONAL BENCHMARK",
            "focus": f"Ranking and distribution across {lead_cat}",
            "layout": "chart_narrative"
        })

    # 6. Concentrations, Exceptions, or Headwinds
    if patterns or (has_entities and len(ranked_cat) > 1):
        storyline.append({
            "section_id": "concentrations_exceptions",
            "category": "CONCENTRATION & EXCEPTIONS" if is_audit else "OPERATIONAL HEADWINDS",
            "focus": "Concentration of exceptions, outliers, and performance dispersion",
            "layout": "comparison_split"
        })

    # 7. Connected Cross-Dimension Analysis
    if len(ranked_cat) >= 2 or len(ranked_num) >= 2:
        storyline.append({
            "section_id": "connected_discovery",
            "category": "CONNECTED DISCOVERY",
            "focus": "Multi-dimensional relationships and cohort segmentation",
            "layout": "full_chart_takeaway"
        })

    # 8. Data Evidence Slide (Representative findings / records)
    storyline.append({
        "section_id": "data_evidence",
        "category": "EVIDENCE LEDGER",
        "focus": "Representative records and categorical frequency breakdown",
        "layout": "table_detail"
    })

    # 9. Actionable Recommendations
    storyline.append({
        "section_id": "action_plan",
        "category": "STRATEGIC ROADMAP",
        "focus": "Evidence-linked action proposals with assigned leadership roles",
        "layout": "action_plan"
    })

    # 10. Audit Lineage & Governance
    storyline.append({
        "section_id": "audit_trail",
        "category": "GOVERNANCE & AUDIT TRAIL",
        "focus": "Cryptographic SHA-256 snapshot seal and claim traceability",
        "layout": "table_detail"
    })

    # If target length is specified, expand or adjust
    if target_length > 0:
        if target_length > len(storyline):
            # Duplicate detailed investigation slides as needed
            needed = target_length - len(storyline)
            for i in range(needed):
                storyline.insert(len(storyline) - 2, {
                    "section_id": f"extended_finding_{i+1}",
                    "category": "DETAILED INVESTIGATION",
                    "focus": f"Secondary dimension analysis and sub-cohort breakdown part {i+1}",
                    "layout": "chart_narrative"
                })

    return storyline
