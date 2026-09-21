"""Automated ingestion pipeline orchestrator running industrial analytics upon sheet uploads."""

import json
import pandas as pd
from .bradford_model import calculate_bradford_factor
from .talent_9box_model import calculate_9box_matrix
from .workforce_strain_model import (
    calculate_burnout_strain_index,
    calculate_cross_sheet_elasticity,
)


def run_ingestion_industrial_pipeline(conn, dataset_id: int | None = None) -> dict:
    """Orchestrates industrial People Analytics calculations across all sheets upon upload."""
    sheets_query = (
        'SELECT s.id, s.name, s.row_count, s.columns_json, d.original_name '
        'FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id ORDER BY s.id ASC'
    )
    all_sheet_rows = conn.execute(sheets_query).fetchall()
    sheet_data = {}
    for r in all_sheet_rows:
        rows = conn.execute('SELECT data_json FROM sheet_rows WHERE sheet_id=? ORDER BY row_index', (r['id'],)).fetchall()
        sheet_data[r['id']] = {
            'meta': dict(r),
            'records': [json.loads(row['data_json']) for row in rows]
        }

    results = {
        'bradford_factor': None,
        'talent_9box': None,
        'burnout_strain': None,
        'elasticity': None
    }

    # Find sheets with performance, absence, and attendance
    perf_sheet = None
    abs_sheet = None

    for sid, s in sheet_data.items():
        cols_lower = [str(c).lower() for c in json.loads(s['meta']['columns_json'] or '[]')]
        if any('perf' in c or 'rating' in c for c in cols_lower):
            perf_sheet = s
        if any('absent' in c or 'leave' in c for c in cols_lower):
            abs_sheet = s

    # 1. Bradford Factor on Absenteeism Sheet
    if abs_sheet:
        results['bradford_factor'] = calculate_bradford_factor(abs_sheet['records'])

    # 2. 9-Box Matrix on Performance Sheet
    if perf_sheet:
        results['talent_9box'] = calculate_9box_matrix(perf_sheet['records'])

    # 3. Burnout Strain
    if perf_sheet:
        df_p = pd.DataFrame(perf_sheet['records'])
        df_a = pd.DataFrame(abs_sheet['records']) if abs_sheet else None
        results['burnout_strain'] = calculate_burnout_strain_index(df_p, df_a)

    # 4. Cross-Sheet Elasticity
    if perf_sheet and abs_sheet:
        df_p = pd.DataFrame(perf_sheet['records'])
        df_a = pd.DataFrame(abs_sheet['records'])
        results['elasticity'] = calculate_cross_sheet_elasticity(df_p, df_a)

    return results
