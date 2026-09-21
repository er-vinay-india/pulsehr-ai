"""Universal Domain-Agnostic Executive AI Data Storytelling, Relational Insights, Visual Analytics, and Quality Audit Engine."""

import json

from ..core import config
from ..db.database import get_connection
from .time_series_forecast import build_multi_measure_forecasts
from .ai_evaluation import evaluate_ai_narrative

from .storytelling import (
    is_id_or_unwanted_column,
    coerce_to_numeric,
    detect_sheet_domain,
    clean_ai_markdown,
    profile_sheet_data,
    generate_ai_narrative,
    compute_relational_story,
)

__all__ = [
    "is_id_or_unwanted_column",
    "coerce_to_numeric",
    "detect_sheet_domain",
    "clean_ai_markdown",
    "profile_sheet_data",
    "generate_ai_narrative",
    "compute_relational_story",
    "get_or_generate_executive_story",
]


def get_or_generate_executive_story(sheet_id: int | None = None, force_refresh: bool = False, model: str | None = None) -> dict:
    """Retrieves cached executive story, multi-metric charts, and multi-measure forecasts or generates fresh AI analysis."""
    conn = get_connection()
    try:
        # First check: If no sheets exist at all, purge any stale cache and return empty immediately
        total_sheets = conn.execute('SELECT COUNT(*) FROM sheets').fetchone()[0]
        if total_sheets == 0:
            with conn:
                conn.execute('DELETE FROM executive_narratives')
            return {
                'empty': True,
                'sheet_id': None,
                'narrative': None,
                'evaluation': None,
                'charts': None,
                'forecast': None,
                'model_used': None,
                'cached': False,
                'message': 'No uploaded sheets available to analyze.'
            }

        # Select and validate target sheet
        if sheet_id:
            sheet = conn.execute('SELECT s.*, d.original_name, d.filename FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id WHERE s.id=?', (sheet_id,)).fetchone()
            if not sheet:
                # Clean up any orphan narrative for this non-existent sheet
                with conn:
                    conn.execute('DELETE FROM executive_narratives WHERE target_type=? AND target_id=?', ('sheet', sheet_id))
                return {
                    'empty': True,
                    'sheet_id': sheet_id,
                    'narrative': None,
                    'evaluation': None,
                    'charts': None,
                    'forecast': None,
                    'model_used': None,
                    'cached': False,
                    'message': f'Sheet {sheet_id} not found.'
                }
        else:
            # Pick the most information-dense analytical sheet (prioritizing dimensions & measures over validation checks)
            sheets = conn.execute('SELECT s.*, d.original_name, d.filename FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id').fetchall()
            if not sheets:
                return {'empty': True, 'narrative': None, 'evaluation': None, 'charts': None, 'forecast': None, 'message': 'No uploaded sheets available to analyze.'}

            def score_sheet(s_record):
                score = 0
                cols = [c.lower() for c in json.loads(s_record["columns_json"] or "[]")]
                s_name = s_record["name"].lower()
                if any('department' in c or 'dept' in c for c in cols):
                    score += 100
                if any('attendance' in c or 'attended' in c for c in cols):
                    score += 50
                if 'check' in s_name or 'calculation' in s_name:
                    score -= 80
                return (score, s_record["row_count"] or 0, -s_record["id"])

            sheet = sorted(sheets, key=score_sheet, reverse=True)[0]

        # Check cache if not forcing refresh
        if not force_refresh:
            if sheet_id:
                cached = conn.execute(
                    'SELECT * FROM executive_narratives WHERE target_type=? AND target_id=? ORDER BY id DESC LIMIT 1',
                    ('sheet', sheet_id)
                ).fetchone()
            else:
                cached = conn.execute(
                    'SELECT * FROM executive_narratives WHERE target_type=? AND target_id IS NULL ORDER BY id DESC LIMIT 1',
                    ('global',)
                ).fetchone()

            if cached:
                cached_narrative = json.loads(cached['narrative_json'])
                # Verify that the sheet or file in cached narrative actually still exists in current dataset_uploads
                cached_file = cached_narrative.get('original_file') if isinstance(cached_narrative, dict) else None
                file_valid = True
                if cached_file:
                    file_valid = bool(conn.execute(
                        'SELECT 1 FROM dataset_uploads WHERE original_name=? OR filename=?',
                        (cached_file, cached_file)
                    ).fetchone())

                if file_valid:
                    if isinstance(cached_narrative, dict) and 'text' in cached_narrative:
                        cached_narrative['text'] = clean_ai_markdown(cached_narrative['text'])
                    return {
                        'sheet_id': sheet['id'],
                        'narrative': cached_narrative,
                        'evaluation': json.loads(cached['evaluation_json']),
                        'charts': json.loads(cached['charts_json']),
                        'forecast': json.loads(cached['forecast_json']),
                        'model_used': cached['model'],
                        'cached': True,
                        'updated_at': cached['updated_at']
                    }
                else:
                    # Purge stale cache referencing a deleted dataset
                    with conn:
                        conn.execute('DELETE FROM executive_narratives WHERE id=?', (cached['id'],))

        sheet_dict = dict(sheet)
        columns = json.loads(sheet_dict['columns_json'])
        rows = conn.execute('SELECT data_json FROM sheet_rows WHERE sheet_id=? ORDER BY row_index', (sheet_dict['id'],)).fetchall()
        records = [json.loads(r['data_json']) for r in rows]

        # Check if generating global multi-sheet synthesis or single-sheet narrative
        is_global = sheet_id is None
        if is_global and len(sheets) > 1:
            total_rows_all = sum(s['row_count'] for s in sheets)
            sheet_summaries = []
            combined_gt = {}
            # Check domains of active sheets
            domains = set()
            for s in sheets:
                s_cols = json.loads(s['columns_json'])
                s_dom, _ = detect_sheet_domain(s_cols)
                domains.add(s_dom)
                combined_gt[f"sheet_{s['name']}_{s_dom}"] = f"{s['row_count']} rows in {s['original_name']}"
                sheet_summaries.append(f"**{s['original_name']}** ({s_dom}): {s['row_count']} records")

            has_sales = any('sales' in d.lower() or 'retail' in d.lower() or 'commercial' in d.lower() for d in domains)
            has_hr = any('attendance' in d.lower() or 'performance' in d.lower() or 'recruitment' in d.lower() or 'compensation' in d.lower() for d in domains)

            if has_sales and not has_hr:
                workspace_label = "Commercial & Retail Operations Workspace"
                domain_title = "Consolidated Commercial Intelligence"
            elif has_hr and not has_sales:
                workspace_label = "Workforce & HR Operations Workspace"
                domain_title = "Consolidated Workforce Intelligence"
            else:
                workspace_label = "Multi-Domain Analytics Workspace"
                domain_title = "Consolidated Analytics Workspace"

            linked_rels = conn.execute("SELECT r.*, l.name as l_name, rg.name as r_name FROM sheet_relationships r JOIN sheets l ON l.id=r.left_sheet JOIN sheets rg ON rg.id=r.right_sheet WHERE r.status='linked'").fetchall()
            rel_summary = f"{len(linked_rels)} cross-sheet verified key relationships discovered." if linked_rels else "Independent sheets without shared identifiers."

            ai_narrative_text = (
                f"### Consolidated Executive Briefing: {workspace_label}\n"
                f"Operational leadership synthesis evaluating **{len(sheets)} active datasets** spanning **{total_rows_all} verified records**.\n\n"
                f"#### Department & Unit Operational Findings\n"
                f"- **Core Population Coverage**: Multi-table architecture audited across {len(sheets)} source table(s) without data interpolation.\n"
                f"- **Cross-Sheet Relational Integrity**: {rel_summary}\n\n"
                f"#### Multi-Sheet Architecture & Data Coverage\n"
                + "\n".join(f"- {ss}" for ss in sheet_summaries) + "\n\n"
                f"#### Strategic Action Plan\n"
                f"- **Operational Intervention**: Target management interventions at units presenting performance lag against empirical organizational benchmarks.\n"
                f"- **Verified Drilldown**: Review entity-level weekly reconciliations and relational links to isolate operational bottlenecks."
            )
            eval_res = evaluate_ai_narrative(ai_narrative_text, combined_gt, total_rows_all)
            profile_res = profile_sheet_data(records, columns, sheet_dict['name'])
            charts = profile_res['charts']
            forecast_res = build_multi_measure_forecasts(records, sheet_dict['name'])

            narrative_payload = {
                'text': ai_narrative_text,
                'thresholds': profile_res['thresholds'],
                'sheet_name': 'All Active Sheets (Consolidated Workspace)',
                'original_file': 'Multi-Sheet Workspace',
                'domain': domain_title,
                'domain_desc': f'Workspace Synthesis across {len(sheets)} Sheets',
                'row_count': total_rows_all,
                'col_count': sum(len(json.loads(s['columns_json'])) for s in sheets)
            }
        else:
            # 1. Profile ground truth, thresholds and multi-metric charts for target sheet
            profile_res = profile_sheet_data(records, columns, sheet_dict['name'])
            ground_truth = profile_res['ground_truth']
            thresholds = profile_res['thresholds']
            charts = profile_res['charts']
            domain = profile_res['domain']
            domain_desc = profile_res['domain_desc']

            # 2. Multi-measure time-series forecasts
            forecast_res = build_multi_measure_forecasts(records, sheet_dict['name'])

            # 3. AI Narrative generation
            ai_narrative_text = generate_ai_narrative(ground_truth, sheet_dict['name'], sheet_dict['original_name'], domain=domain, model=model)

            # 4. AI Quality Evaluation
            eval_res = evaluate_ai_narrative(ai_narrative_text, ground_truth, len(records))

            narrative_payload = {
                'text': ai_narrative_text,
                'thresholds': thresholds,
                'sheet_name': sheet_dict['name'],
                'original_file': sheet_dict['original_name'],
                'domain': domain,
                'domain_desc': domain_desc,
                'row_count': len(records),
                'col_count': len(columns)
            }

        # 5. Persist to cache
        target_type = 'sheet' if sheet_id else 'global'
        with conn:
            conn.execute(
                'INSERT INTO executive_narratives(target_type, target_id, narrative_json, evaluation_json, charts_json, forecast_json, model) VALUES (?,?,?,?,?,?,?)',
                (target_type, sheet_id, json.dumps(narrative_payload), json.dumps(eval_res), json.dumps(charts), json.dumps(forecast_res or {}), model or config.OLLAMA_MODEL)
            )

        return {
            'sheet_id': sheet_dict['id'],
            'narrative': narrative_payload,
            'evaluation': eval_res,
            'charts': charts,
            'forecast': forecast_res,
            'model_used': model or config.OLLAMA_MODEL,
            'cached': False
        }
    finally:
        conn.close()
