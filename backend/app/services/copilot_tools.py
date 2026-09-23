"""Validated, local calculation tools; no generated Python or SQL is executed."""
import ast
import math
import operator
import re
from typing import Literal, Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from ..core import config
from ..db.database import get_connection


from .copilot_query_planner import plan_analytical_query, execute_analytical_plan, AnalyticalQueryPlan


class CalculationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    dataset_id: int | None = None
    relationship_id: int | None = None
    sheet: str | None = None
    operation: Literal['count', 'sum', 'mean', 'min', 'max', 'median'] = 'mean'
    column: str | None = None
    group_by: str | None = None
    filter_column: str | None = None
    filter_value: str | None = None


class ToolRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', arbitrary_types_allowed=True)
    name: Literal['calculate', 'presentation', 'arithmetic', 'industrial_metric', 'analytical_plan']
    calculation: CalculationRequest | None = None
    expression: str | None = Field(default=None, max_length=200)
    industrial_metric: str | None = None
    analytical_plan: Any | None = None


def load_frame(request: CalculationRequest):
    """Read complete persisted sheet rows, including source-qualified exact joins."""
    conn = get_connection()
    try:
        def read(sheet):
            rows = conn.execute('SELECT data_json FROM sheet_rows WHERE sheet_id=? ORDER BY row_index', (sheet['id'],)).fetchall()
            import json
            return pd.DataFrame([json.loads(r['data_json']) for r in rows], columns=json.loads(sheet['columns_json']))
        if request.relationship_id is not None:
            if request.dataset_id is not None or request.sheet is not None:
                raise ValueError('Choose either a sheet or a relationship, not both.')
            relation = conn.execute("SELECT * FROM sheet_relationships WHERE id=? AND status='linked'", (request.relationship_id,)).fetchone()
            if relation is None:
                raise ValueError('Linked relationship not found. Refresh the source list.')
            if relation['matching_pairs'] > 20000:
                raise ValueError('This join exceeds 20,000 rows. Use a smaller source.')
            left = conn.execute('SELECT s.*,d.original_name FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id WHERE s.id=?', (relation['left_sheet'],)).fetchone()
            right = conn.execute('SELECT s.*,d.original_name FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id WHERE s.id=?', (relation['right_sheet'],)).fetchone()
            from .sheet_catalog import value_key
            lf, rf = read(left).add_prefix('left.'), read(right).add_prefix('right.')
            lk, rk = 'left.' + relation['left_column'], 'right.' + relation['right_column']
            lf['__join_key'] = lf[lk].map(value_key)
            rf['__join_key'] = rf[rk].map(value_key)
            frame = lf[lf['__join_key'] != ''].merge(rf[rf['__join_key'] != ''], on='__join_key', how='inner').drop(columns='__join_key')
            return frame, f"{left['original_name']} / {left['name']} joined to {right['original_name']} / {right['name']} ({relation['cardinality']}). Joined rows may repeat source measures."
        sql = 'SELECT s.*,d.original_name FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id'
        args, conditions = [], []
        if request.dataset_id is not None:
            conditions.append('s.dataset_id=?'); args.append(request.dataset_id)
        if request.sheet is not None:
            conditions.append('s.name=?'); args.append(request.sheet)
        matches = conn.execute(sql + (' WHERE ' + ' AND '.join(conditions) if conditions else ''), args).fetchall()
        if not matches:
            raise ValueError('No sheet data available. Upload a sheet first.')
        if len(matches) > 1:
            raise ValueError('Choose a source file and sheet in Calculate from data. Multiple sheets are available.')
        sheet = matches[0]
        return read(sheet), f"{sheet['original_name']} / {sheet['name']}"
    finally:
        conn.close()


def calculate(request: CalculationRequest) -> dict:
    frame, source = load_frame(request)
    from .sheet_catalog import canonical
    # Resolve canonical shortcut names only when the source has one matching column.
    request = request.model_copy()
    for field in ('column', 'group_by', 'filter_column'):
        selected = getattr(request, field)
        if selected and selected not in frame.columns:
            candidates = [c for c in frame.columns if canonical(c) == canonical(selected)]
            if len(candidates) == 1:
                setattr(request, field, candidates[0])
    source_rows = len(frame)
    for column in (request.column, request.group_by, request.filter_column):
        if column is not None and column not in frame.columns:
            raise ValueError(f'Unknown column: {column}. Choose a column from the source.')
    if (request.filter_column is None) != (request.filter_value is None):
        raise ValueError('Both a filter column and filter value are required.')
    if request.filter_column:
        frame = frame[frame[request.filter_column].astype('string').str.casefold() == request.filter_value.casefold()]
    if request.operation != 'count' and request.column is None:
        raise ValueError('Choose a numeric column for this operation.')
    if request.operation == 'sum' and request.column and any(x in request.column.lower() for x in ('rate', 'rating', 'percent')):
        raise ValueError('Summing rates or ratings is not meaningful. Choose mean, min, max or median.')
    unit = None
    if request.operation != 'count':
        frame = frame.copy()
        raw = frame[request.column].replace(r'^\s*$', pd.NA, regex=True)
        from .sheet_catalog import numeric_values
        numeric, unit = numeric_values(raw, request.column)
        if (raw.notna() & numeric.isna()).any() or numeric.dropna().map(lambda n: not math.isfinite(n)).any():
            raise ValueError('The selected column contains non-numeric or non-finite values. Clean them before calculating.')
        frame[request.column] = numeric
    groups = frame.groupby(request.group_by, dropna=False, sort=True) if request.group_by else [('All selected rows', frame)]
    results = []
    for label, group in groups:
        if request.operation == 'count':
            value, used = len(group), len(group)
        else:
            series = group[request.column].dropna()
            used = len(series)
            value = getattr(series, request.operation)() if used else None
            value = float(value) if value is not None else None
            if value is not None and not math.isfinite(value):
                raise ValueError('Calculation exceeded the supported numeric range.')
        results.append({'group': '(missing)' if pd.isna(label) else str(label), 'value': value,
                        'rows': len(group), 'used_rows': used, 'missing_rows': len(group) - used})
    return {'source': source, 'source_rows': source_rows, 'matched_rows': len(frame),
            'operation': request.operation, 'unit': unit, 'column': request.column, 'group_by': request.group_by,
            'filter_column': request.filter_column, 'filter_value': request.filter_value,
            'results': results, 'note': 'Uses all source rows. Missing numeric cells are excluded. Count counts rows. Means are unweighted.'}


def arithmetic(expression: str) -> float:
    """Small arithmetic grammar, with bounded size and no calls, names or powers."""
    if not expression or len(expression) > 200:
        raise ValueError('Enter an arithmetic expression of at most 200 characters.')
    operations = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}
    def evaluate(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            value = float(node.value)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = evaluate(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        elif isinstance(node, ast.BinOp) and type(node.op) in operations:
            value = operations[type(node.op)](evaluate(node.left), evaluate(node.right))
        else:
            raise ValueError('Use only numbers, parentheses and +, -, *, /.')
        if not math.isfinite(value) or abs(value) > 1e15:
            raise ValueError('Result is outside the supported numeric range.')
        return value
    try:
        return evaluate(ast.parse(expression, mode='eval').body)
    except (SyntaxError, ZeroDivisionError, OverflowError, RecursionError) as exc:
        raise ValueError('Invalid arithmetic expression or division by zero.') from exc


def format_calculation(result):
    rows = [f"**{result['operation'].title()} of {result['column'] or 'rows'}** ({result.get('unit') or 'source units'})", f"Source: {result['source']}",
            f"Rows selected: {result['matched_rows']} of {result['source_rows']}."]
    if result['filter_column']:
        rows.append(f"Filter: {result['filter_column']} = {result['filter_value']}")
    for item in result['results']:
        value = 'No numeric data' if item['value'] is None else f"{item['value']:,.6g}"
        rows.append(f"- {item['group']}: **{value}** ({item['used_rows']} rows used, {item['missing_rows']} missing)")
    return '\n\n'.join(rows) + '\n\n' + result['note']


def infer_tool(
    query: str,
    dataset_id: int | None = None,
    sheet_id: int | None = None,
    prior_context: dict[str, Any] | None = None
) -> ToolRequest | None:
    """Conservative shortcuts and structured analytical query planning for domain questions."""
    q = query.strip().lower().rstrip('?')

    expression = re.sub(r'^(calculate|what is|compute)\s+', '', q)
    if re.fullmatch(r'[\d\s.+*/()\-]+', expression) and re.search(r'\d', expression):
        return ToolRequest(name='arithmetic', expression=expression)
    if re.fullmatch(r'(?:please )?(?:create|make|generate|build)(?: me)? (?:a |an |the )?(?:workforce |hr |executive )?(?:presentation|powerpoint|pptx|deck)(?: for (?:the )?workforce)?[.!]?', q):
        return ToolRequest(name='presentation')
    # Exact grammar avoids silently dropping dates, filters or multiple metrics.
    match = re.fullmatch(r'(?:calculate |what is |show |compare )?(?:the )?(total|average|mean|minimum|maximum|median) (attendance|attendance rate|overtime|overtime hours|rating|punctuality)(?: (by department|across departments))?', q)
    if match:
        op, metric, grouped = match.groups()
        cols = {'attendance': 'attendance_rate', 'attendance rate': 'attendance_rate', 'overtime': 'overtime_hours', 'overtime hours': 'overtime_hours', 'rating': 'rating', 'punctuality': 'punctuality_rate'}
        ops = {'total': 'sum', 'average': 'mean', 'mean': 'mean', 'minimum': 'min', 'maximum': 'max', 'median': 'median'}
        return ToolRequest(name='calculate', calculation=CalculationRequest(operation=ops[op], column=cols[metric], group_by='department' if grouped else None))

    # Check for analytical ranking/breakdown questions (e.g. lowest attendance department)
    analytical_plan = plan_analytical_query(query, dataset_id=dataset_id, sheet_id=sheet_id, prior_context=prior_context)
    if analytical_plan:
        return ToolRequest(name='analytical_plan', analytical_plan=analytical_plan)
    if any(k in q for k in ('bradford', 'bradford factor', 'bradford score', 'absence disruption')):
        return ToolRequest(name='industrial_metric', industrial_metric='bradford_factor')
    if any(k in q for k in ('9 box', '9-box', 'nine box', 'talent matrix', 'potential matrix')):
        return ToolRequest(name='industrial_metric', industrial_metric='talent_9box')
    if any(k in q for k in ('burnout', 'strain index', 'workload strain', 'burnout zone', 'burnout index')):
        return ToolRequest(name='industrial_metric', industrial_metric='burnout_strain')
    if any(k in q for k in ('elasticity', 'tipping point', 'absence penalty', 'performance penalty')):
        return ToolRequest(name='industrial_metric', industrial_metric='elasticity')
    if q in ('how many employees', 'how many employees are there', 'total headcount', 'headcount by department'):
        return ToolRequest(name='calculate', calculation=CalculationRequest(operation='count', group_by='department' if 'by department' in q else None))
    return None


def execute_tool(
    query: str,
    request: ToolRequest,
    dataset_id: int | None = None,
    sheet_id: int | None = None,
    prior_context: dict[str, Any] | None = None
) -> dict:
    artifacts, result = [], None
    try:
        if request.name == 'analytical_plan':
            plan = request.analytical_plan
            if not plan:
                plan = plan_analytical_query(query, dataset_id=dataset_id, sheet_id=sheet_id, prior_context=prior_context)
            plan_res = execute_analytical_plan(plan)
            suggested = plan_res.get('suggested_questions') or [
                "What is the attendance breakdown by department?",
                "Which department has the lowest attendance in July?",
                "Show weekly attendance drilldown"
            ]
            return {
                'query': query,
                'answer': plan_res['answer'],
                'model_used': 'Verified analytical query planner',
                'tool_used': 'analytical_plan',
                'status': plan_res.get('status', 'success'),
                'evidence': plan_res.get('evidence'),
                'calculation': plan_res.get('raw_analysis'),
                'prior_context': plan_res.get('prior_context'),
                'artifacts': [],
                'citations': plan_res.get('citations', []),
                'exact_matches': [],
                'suggested_questions': suggested
            }
        elif request.name == 'arithmetic':
            answer = f"{request.expression} = **{arithmetic(request.expression):,.12g}**"
        elif request.name == 'calculate':
            if request.calculation is None:
                raise ValueError('Select the source, operation and column in Calculate.')
            result = calculate(request.calculation)
            answer = format_calculation(result)
        elif request.name == 'industrial_metric':
            from .industrial_analytics import run_ingestion_industrial_pipeline
            conn = get_connection()
            try:
                pipeline_res = run_ingestion_industrial_pipeline(conn)
                m_key = request.industrial_metric or 'bradford_factor'
                m_data = pipeline_res.get(m_key)
                if not m_data or not m_data.get('available'):
                    answer = f"**Industrial Analytics**: {m_data.get('message', 'No compatible dataset available for this calculation.')}"
                else:
                    result = m_data
                    if m_key == 'bradford_factor':
                        lines = [
                            f"### Industrial Bradford Factor Disruption Index",
                            f"**Formula**: `{m_data['formula']}`",
                            f"- **Organizational Average Bradford Score**: **{m_data['organizational_avg_bradford']} pts**",
                            f"- **Staff Exceeding Formal Review Threshold (>200 pts)**: **{m_data['high_disruption_count']} ({m_data['high_disruption_pct']}%)**",
                            f"\n**Department Disruption Ranking**:"
                        ]
                        for d in m_data['departments']:
                            lines.append(f"- **{d['department']}**: Avg Bradford = **{d['avg_bradford_score']} pts** | Days Lost = **{d['total_absent_days']}d** ({d['risk_pct']}% high disruption)")
                        lines.append(f"\n{m_data['ai_insight']}")
                        answer = '\n'.join(lines)
                    elif m_key == 'talent_9box':
                        lines = [
                            f"### McKinsey / GE 9-Box Talent & Risk Matrix",
                            f"- **Total Evaluated Personnel**: **{m_data['total_evaluated']} staff**",
                            f"- **High Performers Total**: **{m_data['high_performers_count']} employees**",
                            f"- **Critical At-Risk Stars (Flight Risk)**: **{m_data['retention_vulnerable_stars']} employees**",
                            f"- **Underperformers (PIP Required)**: **{m_data['underperformers_count']} employees**",
                            f"\n**Key Talent Quadrants**:"
                        ]
                        for c in m_data['cells']:
                            if c['count'] > 0:
                                lines.append(f"- **{c['title']}**: **{c['count']} staff ({c['pct']}%)** — {c['desc']}")
                        lines.append(f"\n{m_data['ai_insight']}")
                        answer = '\n'.join(lines)
                    elif m_key == 'burnout_strain':
                        lines = [
                            f"### Workforce Burnout & Workload Strain Diagnostic",
                            f"**Formula**: `{m_data['formula']}`",
                            f"- **Peak Strain Department**: **{m_data['highest_strain_department']}** (**{m_data['highest_strain_pct']}% strain**)",
                            f"\n**Department Workload Breakdown**:"
                        ]
                        for d in m_data['departments']:
                            lines.append(f"- **{d['department']}**: Strain = **{d['strain_index_pct']}%** ({d['status']}) | Avg Overtime = **{d['avg_overtime_hours']} hrs**")
                        lines.append(f"\n{m_data['ai_insight']}")
                        answer = '\n'.join(lines)
                    else:
                        lines = [
                            f"### Performance-Absenteeism Statistical Cross-Elasticity",
                            f"- **Empirical Penalty Beta**: **{m_data['beta_coefficient']} pts** per absent day",
                            f"- **Model Fit $R^2$**: **{m_data['r_squared']}** (Pearson $r = {m_data['pearson_correlation']}$)",
                            f"- **Operational Tipping Point**: **{m_data['tipping_point_days']} absent days**",
                            f"\n{m_data['ai_insight']}"
                        ]
                        answer = '\n'.join(lines)
            finally:
                conn.close()
        else:
            from .report_generator import generate_pptx_presentation, generate_calculation_presentation
            if request.calculation:
                result = calculate(request.calculation)
                path = generate_calculation_presentation(result)
            else:
                path = generate_pptx_presentation()
            artifacts = [{'name': path.name, 'url': f'/api/reports/presentation/files/{path.name}'}]
            answer = 'Your PowerPoint is ready. It contains calculated figures and source notes.'
    except ValueError as exc:
        answer = f'I could not complete that request: {exc}'
    return {'query': query, 'answer': answer, 'model_used': 'Verified industrial tools',
            'tool_used': request.name, 'calculation': result, 'artifacts': artifacts,
            'citations': [], 'exact_matches': [], 'suggested_questions': []}

