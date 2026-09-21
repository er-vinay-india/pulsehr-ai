"""Data profiling, column type coercion, domain detection, and distribution metrics for executive stories."""

import pandas as pd
from ..time_series_forecast import clean_float, infer_measure_unit


from ..semantic_mapping import is_identity_header, infer_semantic_catalog


def is_id_or_unwanted_column(col_name: str) -> bool:
    """Detects if a column is an ID, index, code, name, or unnamed artifact."""
    return is_identity_header(col_name)


def coerce_to_numeric(series: pd.Series) -> pd.Series:
    """Intelligently parses strings like '79.7%', '4.7/5.0', '$120,000', '1,200' into valid floats."""
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors='coerce')
    
    cleaned = (
        series.astype(str)
        .str.strip()
        .str.replace('$', '', regex=False)
        .str.replace('€', '', regex=False)
        .str.replace('£', '', regex=False)
        .str.replace(',', '', regex=False)
        .str.replace('%', '', regex=False)
        .str.replace(r'^[=]\s*(?=[+-]?\d)', '', regex=True)
    )
    split_slash = cleaned.str.extract(r'^([\d.]+)\s*/\s*[\d.]+$')
    cleaned = cleaned.where(split_slash[0].isna(), split_slash[0])
    return pd.to_numeric(cleaned, errors='coerce')


def detect_sheet_domain(columns: list[str]) -> tuple[str, str]:
    """Detects primary business domain and badge description from column names."""
    cols_clean = [str(c).lower().replace('_', '').replace(' ', '') for c in columns]

    sales_kw = ('sales', 'weeklysales', 'store', 'revenue', 'order', 'orders', 'transaction', 'customer', 'product', 'item', 'price', 'pricing', 'cpi', 'fuelprice', 'unemployment', 'holiday', 'retail', 'margin', 'inventory', 'volume')
    recruitment_kw = ('candidate', 'applicant', 'stage', 'timetohire', 'requisition', 'recruiter', 'offer', 'interview', 'source')
    attendance_kw = ('attendance', 'absent', 'absence', 'leave', 'sick', 'present', 'shift', 'hours', 'overtime')
    performance_kw = ('performance', 'rating', 'score', 'eval', 'kpi', 'goal', 'review', 'competency', 'potential')
    compensation_kw = ('salary', 'compensation', 'payroll', 'bonus', 'equity', 'wage', 'hourly', 'pay')
    retention_kw = ('attrition', 'turnover', 'exit', 'tenure', 'resignation', 'retention', 'termination')
    training_kw = ('training', 'course', 'learning', 'certification', 'skill', 'module')
    finance_kw = ('ebitda', 'expense', 'expenses', 'profit', 'cashflow', 'asset', 'liability', 'equity', 'opex', 'capex', 'ledger')
    logistics_kw = ('shipment', 'shipping', 'delivery', 'carrier', 'warehouse', 'freight', 'transit', 'tracking', 'dispatch', 'route')

    scores = {
        'Retail & Commercial Sales Analytics': sum(any(k in c for k in sales_kw) for c in cols_clean),
        'Recruitment & Hiring Pipeline': sum(any(k in c for k in recruitment_kw) for c in cols_clean),
        'Attendance & Working Hours': sum(any(k in c for k in attendance_kw) for c in cols_clean),
        'Performance & Talent Appraisal': sum(any(k in c for k in performance_kw) for c in cols_clean),
        'Compensation & Payroll': sum(any(k in c for k in compensation_kw) for c in cols_clean),
        'Workforce Retention & Attrition': sum(any(k in c for k in retention_kw) for c in cols_clean),
        'Training & Skills Development': sum(any(k in c for k in training_kw) for c in cols_clean),
        'Finance & Accounting Analytics': sum(any(k in c for k in finance_kw) for c in cols_clean),
        'Supply Chain & Logistics': sum(any(k in c for k in logistics_kw) for c in cols_clean),
    }

    best_domain = max(scores, key=scores.get)
    if scores[best_domain] > 0:
        return best_domain, f"Specialized {best_domain}"
    return "General Tabular Analytics", "General Tabular Analytics"


def clean_ai_markdown(text: str) -> str:
    """Strips enclosing markdown code fences (```markdown ... ```) and cleans whitespace."""
    if not text:
        return ''
    s = str(text).strip()
    if s.startswith('```markdown'):
        s = s[len('```markdown'):].lstrip('\r\n')
    elif s.startswith('```md'):
        s = s[len('```md'):].lstrip('\r\n')
    elif s.startswith('```'):
        s = s[3:].lstrip('\r\n')
    if s.endswith('```'):
        s = s[:-3].rstrip('\r\n')
    return s.strip()


def profile_sheet_data(records: list[dict], columns: list[str], sheet_name: str = 'Sheet') -> dict:
    """Computes comprehensive deterministic ground-truth aggregates, thresholds, and multi-metric charts for ANY sheet."""
    if not records:
        return {
            'ground_truth': {},
            'charts': {'available_metrics': [], 'available_categories': [], 'bar': None, 'donut': None, 'bar_charts': {}, 'donut_charts': {}},
            'thresholds': [],
            'domain': 'General Tabular Analytics'
        }

    df = pd.DataFrame(records)
    total_records = len(records)
    ground_truth = {'total_records': total_records}
    thresholds = []
    
    domain, domain_desc = detect_sheet_domain(columns)
    ground_truth['business_domain'] = domain

    # 1. Classify Column Types dynamically
    numeric_cols = []
    categorical_cols = []
    
    for c in columns:
        if is_id_or_unwanted_column(c):
            continue
        s_num = coerce_to_numeric(df[c])
        valid_num_count = int(s_num.notna().sum())
        if valid_num_count >= max(2, int(total_records * 0.25)):
            numeric_cols.append(c)
            df[f'__clean_{c}'] = s_num
        else:
            n_unique = int(df[c].nunique())
            if 1 < n_unique <= min(25, max(2, int(total_records * 0.8))):
                categorical_cols.append(c)

    # Pick primary categorical column for grouping (prefer Department, Team, Role, Stage, Status)
    primary_cat = None
    for term in ('department', 'dept', 'team', 'division', 'stage', 'status', 'role', 'risklevel', 'risk'):
        for c in categorical_cols:
            if term in str(c).lower().replace('_', '').replace(' ', ''):
                primary_cat = c
                break
        if primary_cat:
            break
    if not primary_cat and categorical_cols:
        primary_cat = categorical_cols[0]

    # Compute summary stats and Bar Charts for ALL numeric columns
    bar_charts = {}
    metric_summaries = []
    
    for num_col in numeric_cols:
        clean_col = f'__clean_{num_col}' if f'__clean_{num_col}' in df.columns else num_col
        s = df[clean_col].dropna() if clean_col in df.columns else coerce_to_numeric(df[num_col]).dropna()
        if len(s) == 0:
            continue
        col_mean = clean_float(s.mean())
        col_median = clean_float(s.median())
        col_min = clean_float(s.min())
        col_max = clean_float(s.max())
        col_sum = clean_float(s.sum())
        unit = infer_measure_unit(num_col)

        gt_prefix = str(num_col).lower().replace(' ', '_').replace('(', '').replace(')', '').replace('-', '_')
        ground_truth[f'avg_{gt_prefix}'] = round(col_mean, 2)
        ground_truth[f'mean_{gt_prefix}'] = round(col_mean, 2)
        ground_truth[f'max_{gt_prefix}'] = round(col_max, 2)
        ground_truth[f'min_{gt_prefix}'] = round(col_min, 2)
        if unit in ('days', 'hrs', 'count', '$'):
            ground_truth[f'total_{gt_prefix}'] = round(col_sum, 1)

        metric_summaries.append({
            'column': num_col,
            'label': num_col,
            'unit': unit,
            'mean': round(col_mean, 2),
            'median': round(col_median, 2),
            'min': round(col_min, 2),
            'max': round(col_max, 2),
            'sum': round(col_sum, 1)
        })

        # Bar chart grouped by primary_cat
        if primary_cat:
            is_additive = unit in ('days', 'hrs', 'count', '$') and 'rate' not in str(num_col).lower()
            if is_additive:
                grouped = df.groupby(primary_cat)[clean_col].apply(lambda x: coerce_to_numeric(x).sum()).reset_index()
                chart_title = f"Total {num_col} by {primary_cat}"
            else:
                grouped = df.groupby(primary_cat)[clean_col].apply(lambda x: coerce_to_numeric(x).mean()).reset_index()
                chart_title = f"Average {num_col} by {primary_cat}"

            grouped = grouped.sort_values(by=clean_col, ascending=False)
            bar_charts[num_col] = {
                'title': chart_title,
                'category_col': primary_cat,
                'metric_col': num_col,
                'unit': unit,
                'bars': [{'label': str(row[primary_cat]), 'value': round(clean_float(row[clean_col]), 2)} for _, row in grouped.iterrows() if pd.notna(row[primary_cat])]
            }

    # Donut Charts for ALL categorical columns + binned numeric distributions
    donut_charts = {}
    for cat_col in categorical_cols:
        vc = df[cat_col].value_counts().head(8)
        tot = max(1, int(vc.sum()))
        palette = ['#8ef0c8', '#818cf8', '#38bdf8', '#f3d19a', '#ffb4be', '#c084fc', '#f43f5e', '#a3e635']
        donut_charts[cat_col] = {
            'title': f'{cat_col} Distribution',
            'category_col': cat_col,
            'total': tot,
            'slices': [
                {
                    'label': str(lbl),
                    'count': int(cnt),
                    'pct': round((cnt / tot) * 100, 1),
                    'color': palette[idx % len(palette)]
                }
                for idx, (lbl, cnt) in enumerate(vc.items())
            ]
        }

    # Generate binned donut distribution for continuous ratings / scores if available
    for num_col in numeric_cols:
        s = coerce_to_numeric(df[num_col]).dropna()
        c_clean = str(num_col).lower()
        if ('rating' in c_clean or 'score' in c_clean) and len(s) > 3:
            s_max = float(s.max())
            if s_max <= 5.5:
                # 5-star scale
                b1 = int((s < 3.0).sum())
                b2 = int(((s >= 3.0) & (s < 4.0)).sum())
                b3 = int((s >= 4.0).sum())
                bin_key = f"{num_col} Bands"
                donut_charts[bin_key] = {
                    'title': f'{num_col} Tier Breakdown',
                    'category_col': bin_key,
                    'total': len(s),
                    'slices': [
                        {'label': 'Top Tier (≥ 4.0)', 'count': b3, 'pct': round((b3/len(s))*100, 1), 'color': '#8ef0c8'},
                        {'label': 'Solid / Meets (3.0–3.9)', 'count': b2, 'pct': round((b2/len(s))*100, 1), 'color': '#38bdf8'},
                        {'label': 'Needs Review (< 3.0)', 'count': b1, 'pct': round((b1/len(s))*100, 1), 'color': '#ffb4be'}
                    ]
                }
            elif s_max <= 10.5:
                # 10-point scale
                b1 = int((s < 6.0).sum())
                b2 = int(((s >= 6.0) & (s < 8.0)).sum())
                b3 = int((s >= 8.0).sum())
                bin_key = f"{num_col} Bands"
                donut_charts[bin_key] = {
                    'title': f'{num_col} Tier Breakdown',
                    'category_col': bin_key,
                    'total': len(s),
                    'slices': [
                        {'label': 'High Performers (≥ 8.0)', 'count': b3, 'pct': round((b3/len(s))*100, 1), 'color': '#8ef0c8'},
                        {'label': 'Core Performers (6.0–7.9)', 'count': b2, 'pct': round((b2/len(s))*100, 1), 'color': '#38bdf8'},
                        {'label': 'Under Review (< 6.0)', 'count': b1, 'pct': round((b1/len(s))*100, 1), 'color': '#ffb4be'}
                    ]
                }
        elif 'attendance' in c_clean and len(s) > 3:
            s_pct = s if s.max() > 1.5 else s * 100.0
            low_att = int((s_pct < 85.0).sum())
            mid_att = int(((s_pct >= 85.0) & (s_pct < 95.0)).sum())
            high_att = int((s_pct >= 95.0).sum())
            bin_key = "Attendance Rate Bands"
            donut_charts[bin_key] = {
                'title': 'Attendance Regularity Distribution',
                'category_col': bin_key,
                'total': len(s),
                'slices': [
                    {'label': 'Punctual (≥ 95%)', 'count': high_att, 'pct': round((high_att/len(s))*100, 1), 'color': '#8ef0c8'},
                    {'label': 'Acceptable (85%–94%)', 'count': mid_att, 'pct': round((mid_att/len(s))*100, 1), 'color': '#f3d19a'},
                    {'label': 'Irregular (< 85%)', 'count': low_att, 'pct': round((low_att/len(s))*100, 1), 'color': '#ffb4be'}
                ]
            }

    # 3. Dynamic Critical Threshold Cards
    if primary_cat and primary_cat in df.columns:
        top_cat_name = str(df[primary_cat].value_counts().index[0])
        top_cat_count = int(df[primary_cat].value_counts().iloc[0])
        thresholds.append({
            'label': f'Largest {primary_cat}',
            'value': top_cat_name,
            'sub': f"{top_cat_count} of {total_records} rows ({round((top_cat_count/total_records)*100, 1)}%)",
            'tone': 'neutral'
        })

    for m in metric_summaries[:3]:
        col = m['column']
        u = m['unit']
        mean_v = m['mean']
        c_lower = str(col).lower()

        if 'attendance' in c_lower:
            thresholds.append({
                'label': f'Avg {col}',
                'value': f"{mean_v}{u}",
                'sub': f"Spread {m['min']}{u} to {m['max']}{u}",
                'tone': 'good' if mean_v >= 90 or mean_v >= 0.9 else 'warning'
            })
        elif 'rating' in c_lower or 'score' in c_lower or 'performance' in c_lower:
            thresholds.append({
                'label': f'Average {col}',
                'value': f"{mean_v} {u}",
                'sub': f"Peak: {m['max']} · Floor: {m['min']}",
                'tone': 'good' if mean_v >= 3.5 or mean_v >= 7.0 else 'warning'
            })
        elif 'absent' in c_lower or 'leave' in c_lower:
            s_abs = coerce_to_numeric(df[col]).fillna(0)
            gt_3 = int((s_abs > 3).sum())
            total_on_leave = int((s_abs > 0).sum())
            ground_truth['total_on_leave'] = total_on_leave
            ground_truth['more_than_3_days_leave'] = gt_3
            thresholds.append({
                'label': 'Total on Leave',
                'value': f"{total_on_leave} / {total_records}",
                'sub': f"{round((total_on_leave/total_records)*100, 1)}% of workforce",
                'tone': 'neutral'
            })
            thresholds.append({
                'label': 'Took > 3 Days Leave',
                'value': f"{gt_3} Employees",
                'sub': f"{round((gt_3/total_records)*100, 1)}% critical absence",
                'tone': 'warning' if gt_3 > 0 else 'good'
            })
        elif any(k in c_lower for k in ('sales', 'weeklysales', 'revenue', 'volume', 'amount', 'profit')):
            s_val = m.get('sum') or 0
            thresholds.append({
                'label': f'Total {col}',
                'value': f"${s_val:,.0f}" if mean_v > 100 else f"{s_val:,.0f} units",
                'sub': f"Average: ${mean_v:,.2f} · Peak: ${m['max']:,.2f}" if mean_v > 100 else f"Average: {mean_v} · Peak: {m['max']}",
                'tone': 'good'
            })
        elif 'overtime' in c_lower or 'hours' in c_lower:
            s_val = m.get('sum') or 0
            thresholds.append({
                'label': f'Total {col}',
                'value': f"{s_val} {u}",
                'sub': f"Average {mean_v} {u} per record",
                'tone': 'warning' if mean_v > 10 else 'neutral'
            })
        elif 'salary' in c_lower or 'compensation' in c_lower:
            thresholds.append({
                'label': f'Average {col}',
                'value': f"${mean_v:,.0f}" if mean_v > 1000 else f"{mean_v} {u}",
                'sub': f"Range: {m['min']} to {m['max']}",
                'tone': 'neutral'
            })
        else:
            thresholds.append({
                'label': f'Average {col}',
                'value': f"{mean_v} {u}",
                'sub': f"Max: {m['max']} {u}",
                'tone': 'neutral'
            })

    # Pick default primary bar and donut charts
    primary_num_col = numeric_cols[0] if numeric_cols else None
    primary_cat_col = list(donut_charts.keys())[0] if donut_charts else None

    charts = {
        'available_metrics': metric_summaries,
        'available_categories': list(donut_charts.keys()),
        'primary_metric': primary_num_col,
        'primary_category': primary_cat_col,
        'bar': bar_charts.get(primary_num_col) if primary_num_col else None,
        'donut': donut_charts.get(primary_cat_col) if primary_cat_col else None,
        'bar_charts': bar_charts,
        'donut_charts': donut_charts
    }

    semantic_cat = infer_semantic_catalog(columns, records, sheet_name=sheet_name)
    ground_truth['semantic_catalog'] = [f.to_dict() for f in semantic_cat.fields.values()]
    ground_truth['data_anomalies'] = semantic_cat.anomalies

    return {
        'ground_truth': ground_truth,
        'thresholds': thresholds,
        'charts': charts,
        'domain': domain,
        'domain_desc': domain_desc,
        'semantic_catalog': [f.to_dict() for f in semantic_cat.fields.values()],
        'data_anomalies': semantic_cat.anomalies
    }
