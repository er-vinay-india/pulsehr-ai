"""Sheet visual projections and column statistics profiling engine for Data Explorer."""

import json
import pandas as pd

from ..executive_story import is_id_or_unwanted_column, coerce_to_numeric
from ..time_series_forecast import clean_float, infer_measure_unit
from ..display_formatters import format_display_label, generate_analytical_title
from .visual_common import PALETTE, is_name_or_text_column


def get_sheet_raw_projections(conn, sheet_id: int) -> dict:
    """Generates direct data extracts, column statistics, and basic charts for Data Explorer."""
    sheet = conn.execute(
        'SELECT s.*, d.original_name, d.filename FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id WHERE s.id=?',
        (sheet_id,)
    ).fetchone()
    if not sheet:
        return {'available': False, 'message': 'Sheet not found'}

    rows = conn.execute('SELECT data_json FROM sheet_rows WHERE sheet_id=? ORDER BY row_index', (sheet_id,)).fetchall()
    records = [json.loads(r['data_json']) for r in rows]
    if not records:
        return {'available': False, 'message': 'No rows available for this sheet'}

    df = pd.DataFrame(records)
    cols = json.loads(sheet['columns_json'] or '[]')

    # Compute column summary statistics
    column_stats = []
    numeric_cols = []
    categorical_cols = []

    for c in cols:
        vals = [r[c] for r in records if c in r and str(r[c]).strip() not in ('', 'None', 'nan')]
        nonempty = len(vals)
        missing = len(records) - nonempty
        distinct = len(set(str(v).strip().lower() for v in vals))

        is_id = is_id_or_unwanted_column(c)
        s_num = coerce_to_numeric(pd.Series(vals)) if not is_id else pd.Series([])

        stat_item = {
            'column': c,
            'display_name': format_display_label(c),
            'nonempty': nonempty,
            'missing': missing,
            'distinct': distinct,
            'is_numeric': False
        }

        if len(s_num.dropna()) >= max(2, int(len(records) * 0.3)) and not is_id:
            unit = infer_measure_unit(c)
            stat_item.update({
                'is_numeric': True,
                'mean': round(float(s_num.mean()), 2),
                'median': round(float(s_num.median()), 2),
                'min': round(float(s_num.min()), 2),
                'max': round(float(s_num.max()), 2),
                'unit': unit
            })
            numeric_cols.append(c)
            df[f'__clean_{c}'] = coerce_to_numeric(df[c])
        elif 1 < distinct <= 10 and not is_id and not is_name_or_text_column(c):
            categorical_cols.append(c)

        column_stats.append(stat_item)

    # Find primary categorical grouping column (Department, Team, Role, Stage)
    primary_cat = None
    for term in ('department', 'dept', 'team', 'division', 'role', 'status', 'stage'):
        for c in categorical_cols:
            if term in str(c).lower().replace('_', '').replace(' ', ''):
                primary_cat = c
                break
        if primary_cat:
            break
    if not primary_cat and categorical_cols:
        primary_cat = categorical_cols[0]

    # Build direct data extract bar charts (Average Rating, Attendance, Overtime, Absent Days)
    projections = []
    for num_col in numeric_cols:
        clean_c = f'__clean_{num_col}' if f'__clean_{num_col}' in df.columns else num_col
        unit = infer_measure_unit(num_col)

        if primary_cat:
            is_additive = unit in ('days', 'hrs', 'count', '$') and 'rate' not in str(num_col).lower()
            if is_additive:
                grp = df.groupby(primary_cat)[clean_c].sum().reset_index()
                calc_type = "Summation"
            else:
                grp = df.groupby(primary_cat)[clean_c].mean().reset_index()
                calc_type = "Arithmetic Mean"

            grp = grp.sort_values(by=clean_c, ascending=False)
            bars = [
                {'label': str(r[primary_cat]), 'value': round(clean_float(r[clean_c]), 2)}
                for _, r in grp.iterrows()
                if pd.notna(r[primary_cat])
            ]
            if bars:
                title, _ = generate_analytical_title(
                    calc_type=calc_type,
                    metric_col=num_col,
                    group_col=primary_cat,
                    total_count=len(bars)
                )
                projections.append({
                    'id': f"proj_bar_{num_col}",
                    'type': 'bar',
                    'title': title,
                    'category_col': primary_cat,
                    'metric_col': num_col,
                    'unit': unit,
                    'bars': bars
                })

    # Build categorical distribution donuts
    for cat_col in categorical_cols:
        vc = df[cat_col].value_counts().head(8)
        tot = max(1, int(vc.sum()))
        slices = [
            {
                'label': str(lbl),
                'count': int(cnt),
                'pct': round((cnt / tot) * 100, 1),
                'color': PALETTE[idx % len(PALETTE)]
            }
            for idx, (lbl, cnt) in enumerate(vc.items())
        ]
        if len(slices) >= 2:
            donut_title, _ = generate_analytical_title(
                calc_type="Distribution",
                metric_col=cat_col,
                group_col=cat_col,
                comparison_type="donut",
                total_count=tot
            )
            projections.append({
                'id': f"proj_donut_{cat_col}",
                'type': 'donut',
                'title': donut_title,
                'category_col': cat_col,
                'total': tot,
                'slices': slices
            })

    return {
        'available': True,
        'sheet_id': sheet['id'],
        'sheet_name': sheet['name'],
        'original_name': sheet['original_name'],
        'row_count': len(records),
        'col_count': len(cols),
        'column_stats': column_stats,
        'projections': projections
    }
