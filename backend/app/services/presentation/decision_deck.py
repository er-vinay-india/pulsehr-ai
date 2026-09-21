"""Project the overview's immutable decision evidence into existing slide layouts.

No second inference/aggregation pass: displayed values, text, actions and chart series
are bound to a frozen per-slide contract and verified again after layout processing.
"""
import copy
import datetime
import uuid
from .builders.common import THEMES, calculate_timing

CLAIM_FIELDS = ('title', 'subtitle', 'narrative', 'bullets', 'metrics', 'chart', 'table', 'speaker_notes', 'narration_script', 'evidence_sources')


def short(text, size):
    text = str(text)
    return text if len(text) <= size else text[:size-1].rsplit(' ', 1)[0] + '…'


def generate_decision_deck(scope, brief, on_slide_progress=None):
    if brief['empty']:
        raise ValueError('No sheets in the selected scope.')
    theme_id = scope.get('theme_id') or 'executive_dark'
    slides, ledger = [], []

    def append(title, narrative, bullets, source, finding_id, chart=None, table=None, notes=''):
        order = len(slides)+1
        eid = f'DECISION-{order:03}'
        subtitle = short(source, 115)
        slide = {
            'id': f'slide_{uuid.uuid4().hex[:8]}', 'stable_slide_id': f'decision_{order}', 'order': order,
            'layout': 'table_detail' if table else ('chart_narrative' if chart else 'comparison_split'),
            'category': 'EVIDENCE APPENDIX' if finding_id == 'coverage' else 'DECISION BRIEF', 'title': short(title, 78), 'subtitle': subtitle,
            'narrative': short(narrative, 275), 'bullets': [short(b, 155) for b in bullets[:3]],
            'metrics': [] if chart else [{'label':'Evidence', 'value':'Descriptive', 'subtext':'Scoped source records'}, {'label':'Actions', 'value':'Proposed', 'subtext':'Review before commitment'}, {'label':'Interpretation', 'value':'Not causal', 'subtext':'Coverage limits apply'}], 'chart': chart, 'table': table, 'evidence_id': eid,
            'evidence_sources': [source], 'finding_id': finding_id,
            'speaker_notes': f'{title}\n{narrative}\n' + '\n'.join(bullets) + f'\n{notes}\nSnapshot: {brief["snapshot"]}\nPresenter notes (user supplied, not verified): {scope.get("instructions", "")}',
            'narration_script': narrative, 'timing_metadata': calculate_timing(narrative),
            'is_partial_year': None,
        }
        ev = {'evidence_id': eid, 'title': title, 'finding_id': finding_id, 'source_sheets': [source],
              'metric_name': 'Bound decision evidence', 'metric_value': 'See source finding', 'numeric_value': None,
              'calculation_methodology': notes, 'what_it_establishes': narrative,
              'what_it_does_not_establish': 'No causal, exposure-adjusted or overall performance conclusion.',
              'snapshot_hash': brief['snapshot'], 'slide_claims': {k: copy.deepcopy(slide[k]) for k in CLAIM_FIELDS}}
        slide['evidence_item'] = copy.deepcopy(ev)
        slides.append(slide); ledger.append(ev)

    findings = brief['findings']
    # Narrative cover uses actual findings, not source counts as the business headline.
    append('Leadership decisions supported by the uploaded data',
           findings[0]['observation'] if findings else 'No material descriptive differences met the analysis rules. Review coverage before drawing conclusions.',
           [f['title'] for f in findings[:3]], 'Selected sources · analyzed separately', 'overview',
           notes='The same scoped findings shown in Executive Overview. Proposed actions are not approved commitments.')

    for f in findings:
        detail = f['detail']; groups = [g for g in detail.get('groups', []) if g['value'] is not None]
        if detail.get('focus_group'):
            groups.sort(key=lambda g: g['group'] != detail['focus_group'])
        points = detail.get('points', [])
        chunks = [groups[i:i+6] for i in range(0, len(groups), 6)] if groups else [None]
        for page, chunk in enumerate(chunks):
            chart = None
            if chunk:
                cats = [f'{page*6+i+1}. {short(g["group"], 13)}' for i,g in enumerate(chunk)]
                chart = {'type': 'bar', 'chart_type': 'bar', 'title': short(f['metric'], 78),
                         'categories': cats, 'series': [{'name':'Mean / valid record', 'values':[g['value'] for g in chunk]}],
                         'unit': 'Source scale', 'source': f['source']['file'], 'source_sheet': f['source']['sheet'],
                         'measurement': f['metric'], 'calculation': f['method'], 'population': 'Valid source records',
                         'date_range': 'As recorded; see source finding', 'total_population': detail.get('used_rows', 0)}
            elif points:
                chart = {'type':'line','chart_type':'line','title':short(f['metric'],78),
                         'categories':[p['period'] for p in points],
                         'series':[{'name':'Monthly mean / record','values':[p['value'] for p in points]}],
                         'unit':'Source scale','source':f['source']['file'],'measurement':f['metric'],
                         'population':'Valid dated records','date_range':f'{points[0]["period"]} to {points[-1]["period"]}'}
            title = f['title'] if page == 0 else f'Comparison continued · {f["metric"]}'
            mapping = '\n'.join(f'{cat}: {g["group"]}; mean={g["value"]}; valid={g["used_rows"]}; missing={g["missing_rows"]}' for cat,g in zip(chart['categories'],chunk)) if chunk else ''
            append(title, f['observation'], [f'Proposed action: {f["action"]}', f'Proposed owner: {f["owner"]}', f['implication']],
                   f'{f["source"]["file"]} / {f["source"]["sheet"]}', f['id'], chart=chart,
                   notes=f'{f["method"]}\n{mapping}\nFull evidence: {detail}')

    boundary_signatures = set()
    for profile in brief['profiles']:
        limits = profile['limitations']
        signature = (profile['source']['file'], profile['source']['sheet'], tuple(limits))
        if signature in boundary_signatures:
            continue
        boundary_signatures.add(signature)
        # Paginated boundary cards preserve every limitation without tiny text.
        for start in range(0, len(limits), 3):
            append('Coverage and interpretation boundaries', 'Apply these limits when planning an action from this source.',
                   limits[start:start+3], f'{profile["source"]["file"]} / {profile["source"]["sheet"]}', 'coverage',
                   notes='\n'.join(limits[start:start+3]))
    for slide in slides:
        slide['total_slides'] = len(slides)
        if on_slide_progress:
            on_slide_progress(slide['order'], len(slides), slide['title'], slide['category'])
    deck = {'id':f'deck_{uuid.uuid4().hex[:12]}', 'spec_version':'2.0',
            'theme':THEMES.get(theme_id, THEMES.get('executive_dark', {})),
            'metadata':{'title':'Executive decision brief','theme_id':theme_id,'deck_style':'decision_brief',
                        'snapshot_hash':brief['snapshot'],'data_snapshot_hash':brief['snapshot'],
                        'domain':', '.join(dict.fromkeys(p['domain'] for p in brief['profiles'])),
                        'objective':scope.get('objective','Leadership review'),'audience':scope.get('audience','Leadership'),
                        'sheet_id':brief['profiles'][0]['source']['sheet_id'] if len(brief['profiles'])==1 else None,
                        'sheet_ids':[p['source']['sheet_id'] for p in brief['profiles']],
                        'total_records':sum(p['row_count'] for p in brief['profiles']),
                        'file_label':'Selected uploaded sources','created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        'is_partial_year':None,'reporting_period_summary':'Source-specific periods; see findings'},
            'slides':slides,'evidence_ledger':ledger,
            'coverage_manifest':{'main_deck_count':sum(s['finding_id'] != 'coverage' for s in slides),'appendix_count':sum(s['finding_id'] == 'coverage' for s in slides),'excluded_count':0,
                                 'items':[{'evidence_id':s['evidence_id'],'title':s['title'],'disposition':'appendix' if s['finding_id']=='coverage' else 'main_deck','reason':'Bound overview finding or explicit coverage limit'} for s in slides]},
            'decision_brief':brief}
    deck['metadata']['validation_summary'] = verify_decision_deck(deck, ledger)
    return deck


def verify_decision_deck(deck, ledger):
    """Exact typed equality preserves signs, scales, scope, text and chart-to-entity bindings."""
    evidence = {e['evidence_id']:e for e in ledger}
    checked, discrepancies = [], []
    seen = set()
    for slide in deck.get('slides', []):
        eid = slide.get('evidence_id')
        contract = evidence.get(eid, {}).get('slide_claims')
        if not contract or eid in seen:
            discrepancies.append({'slide':slide.get('title'), 'reason':'Missing or duplicate evidence contract'})
            continue
        seen.add(eid)
        for field in CLAIM_FIELDS:
            passed = field in contract and slide.get(field) == contract[field]
            checked.append({'slide':slide.get('title'),'metric':field,'passed':passed,'status':'PASSED' if passed else 'DISCREPANCY'})
            if not passed:
                discrepancies.append({'slide':slide.get('title'),'metric':field,'reason':'Display differs from frozen evidence contract'})
    if not deck.get('slides'):
        discrepancies.append({'reason':'Empty decision deck'})
    return {'status':'PASSED' if not discrepancies else 'DISCREPANCIES_FLAGGED',
            'total_metrics_checked':len(checked),'passed_verification':sum(c['passed'] for c in checked),
            'discrepancies_flagged':len(discrepancies),'checked_items':checked,'discrepancies':discrepancies,
            'tolerance_threshold':'Exact typed evidence contract'}
