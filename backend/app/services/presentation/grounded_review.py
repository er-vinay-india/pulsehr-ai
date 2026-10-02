"""A source-grounded fallback when a requested business story is unsupported."""
from collections import Counter
from statistics import mean
import datetime
import uuid

from .hr_report import _number, _norm
from .builders.common import THEMES
from .content_validation import seal_business_content


def build_grounded_review(scope, ctx, workspace=None):
    records = ctx.get('records') or []
    columns = ctx.get('columns') or list(records[0] if records else {})
    label = (ctx.get('target_sheet') or {}).get('name') or 'Recorded data'
    period = (workspace or {}).get('reporting_period_summary') or 'Recorded observations'
    ledger, slides = [], []

    def fact(name, value, unit, inputs, method):
        eid = f'RECORD-{len(ledger)+1:03d}'
        ledger.append({'evidence_id': eid, 'metric_name': name, 'title': name, 'numeric_value': value,
                       'metric_value': f'{value:g} {unit}', 'unit': unit, 'date_range': period,
                       'source_sheets': [label], 'calculation_inputs': inputs, 'calculation_methodology': method,
                       'finding_type': 'measured_fact', 'limitations': 'Recorded values do not establish causes or future results.'})
        return {'label': name, 'value': f'{value:g}', 'unit': unit, 'subtext': unit, 'evidence_id': eid}

    def add(title, narrative, bullets=None, metrics=None, chart=None):
        refs = [m['evidence_id'] for m in metrics or []] + (chart or {}).get('evidence_ids', [])
        slides.append({'id': f'slide_{len(slides)+1}', 'order': len(slides)+1, 'title': title,
                       'subtitle': period, 'category': 'BUSINESS REVIEW', 'narrative': narrative, 'bullets': bullets or [],
                       'layout': 'chart_narrative' if chart else 'kpi_summary' if metrics else 'comparison_split',
                       'metrics': metrics or [], 'chart': chart, 'table': None, 'evidence_ids': refs,
                       'evidence_id': refs[0] if refs else None, 'source_label': label,
                       'speaker_notes': narrative+' '+' '.join(bullets or []), 'business_report': True})

    add('Review of recorded results', 'This review summarizes measurements that can be established from the available records.',
        metrics=[fact('Source rows', len(records), 'rows', [1 for _ in records], 'sum')])
    add('What these records can tell us', 'The report describes recorded values and their distribution.',
        ['The requested business outcome is a question to investigate, rather than an established finding.',
         'Causes, forecasts and policy compliance require suitable measures and definitions.'])
    # Source fields only; engineered interactions and identifier numerics are not business KPIs.
    for column in columns:
        if len(slides) >= 8:
            break
        key = str(column).lower()
        if key.startswith(('interact_', 'derived_')) or _norm(column) in {'id', 'empid', 'employeeid', 'rowid', 'index'}:
            continue
        raw = [r.get(column) for r in records if r.get(column) not in (None, '')]
        if not raw:
            continue
        nums = [_number(v) for v in raw]
        if all(n is not None for n in nums):
            # A generic numeric field has its recorded unit; do not infer currency or days.
            unit = 'recorded units'
            m = fact('Average '+str(column), mean(nums), unit, nums, 'mean')
            ledger[-1]['denominator'] = len(nums)
            add(str(column)+' at a glance', 'This average uses records with a numeric value; missing values are excluded.', metrics=[m])
        else:
            counts = Counter(str(v) for v in raw)
            if len(counts) > 12 or len(counts) < 2:
                continue
            pairs = counts.most_common(5)
            if len(counts) > 5:
                pairs.append(('Other', sum(n for _, n in counts.most_common()[5:])))
            refs = [fact(str(column)+' records: '+name, n, 'rows', [1]*n, 'sum')['evidence_id'] for name, n in pairs]
            add('Recorded '+str(column)+' distribution', 'Counts describe the recorded categories; they do not imply preference or performance.',
                chart={'type': 'bar', 'title': str(column)+' record counts', 'metric_name': str(column)+' records', 'unit': 'rows',
                       'period': period, 'group_by': column, 'categories': [name for name, _ in pairs],
                       'series': [{'name': 'Records', 'values': [n for _, n in pairs]}], 'evidence_ids': refs})
    add('Agree the next business question', 'Confirm the measures needed for the decision, then compare like-for-like records.',
        ['Confirm business definitions and reporting scope.', 'Supply the missing measures before assessing causes or expected benefits.'])
    theme_id = scope.get('theme_id') or 'executive_dark'
    for slide in slides:
        slide['total_slides'] = len(slides)
    return seal_business_content({'id': 'deck_'+uuid.uuid4().hex[:12], 'spec_version': '2.0',
            'theme': THEMES.get(theme_id, THEMES['executive_dark']), 'slides': slides, 'evidence_ledger': ledger,
            'metadata': {'title': slides[0]['title'], 'theme_id': theme_id, 'domain': ctx.get('domain') or 'Business review',
                         'objective': scope.get('objective') or 'Recorded results review', 'audience': scope.get('audience') or 'Business managers',
                         'content_contract': 'recorded_results_v1', 'total_records': len(records), 'file_label': label,
                         'reporting_period_summary': period, 'snapshot_hash': (workspace or {}).get('snapshot_hash') or ctx.get('snapshot_hash'),
                         'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'brief': dict(scope)},
            'coverage_manifest': {'items': [{'evidence_id': e['evidence_id'], 'title': e['title'], 'disposition': 'main_deck'} for e in ledger]}})
