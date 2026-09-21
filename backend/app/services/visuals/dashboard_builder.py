"""Executive visual intelligence dashboard synthesis and multi-sheet aggregation engine."""

import json

from ..industrial_analytics import run_ingestion_industrial_pipeline
from ..fact_discovery import discover_prioritized_hr_facts
from .industrial_suite import build_industrial_suite
from .comparative_suite import build_comparative_suite, build_longitudinal_suite
from .dynamic_suite import build_dynamic_suite


def build_workspace_visual_dashboard(conn, sheet_id: int | None = None, model: str | None = None) -> dict:
    """Assembles the executive suite with industrial formula-based People Analytics."""
    sheets_query = (
        'SELECT s.id, s.name, s.row_count, s.columns_json, d.original_name '
        'FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id ORDER BY s.id ASC'
    )
    all_sheet_rows = conn.execute(sheets_query).fetchall()
    sheet_meta_map = {r['id']: dict(r) for r in all_sheet_rows}

    sheet_data_map = {}
    for sid in sheet_meta_map:
        rows = conn.execute('SELECT data_json FROM sheet_rows WHERE sheet_id=? ORDER BY row_index', (sid,)).fetchall()
        sheet_data_map[sid] = [json.loads(r['data_json']) for r in rows]

    # Run Industrial Pipeline
    industrial_res = run_ingestion_industrial_pipeline(conn)

    visualizations = []
    visualizations.extend(build_industrial_suite(sheet_meta_map, industrial_res, all_sheet_rows))
    visualizations.extend(build_comparative_suite(conn, sheet_meta_map, sheet_data_map))
    visualizations.extend(build_longitudinal_suite(sheet_meta_map, sheet_data_map))
    visualizations.extend(build_dynamic_suite(sheet_meta_map, sheet_data_map))

    # Prioritized Linked Facts Discovery
    prioritized_facts = discover_prioritized_hr_facts(
        visualizations, industrial_res, list(sheet_meta_map.values())
    )

    # Filtering by sheet_id if provided
    if sheet_id is not None:
        visualizations = [v for v in visualizations if sheet_id in v.get('sheet_ids', [])]
        prioritized_facts = [
            f for f in prioritized_facts
            if not f.get('investigation_target', {}).get('sheet_id') or f.get('investigation_target', {}).get('sheet_id') == sheet_id
        ]

    # Category counts
    cat_counts = {}
    for v in visualizations:
        c = v.get('category', 'Other')
        cat_counts[c] = cat_counts.get(c, 0) + 1

    category_list = ['All'] + [c for c in ('Cross-Sheet Intelligence', 'Industrial People Analytics', 'Workforce Risk & Burnout', 'Longitudinal Forecasts', 'Workforce Operations', 'Longitudinal Trends') if c in cat_counts]
    for c in cat_counts:
        if c not in category_list:
            category_list.append(c)

    return {
        'total_visualizations': len(visualizations),
        'categories': category_list,
        'category_counts': {'All': len(visualizations), **cat_counts},
        'visualizations': visualizations,
        'prioritized_facts': prioritized_facts
    }
