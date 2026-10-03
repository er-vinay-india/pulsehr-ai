"""Business-content contracts and checks independent of numeric coincidence."""
from __future__ import annotations

import hashlib
import json
import math
import re
from statistics import mean, median


PUBLIC_FIELDS = ('title', 'subtitle', 'narrative', 'bullets', 'metrics', 'chart', 'table')


def content_digest(slide):
    return hashlib.sha256(json.dumps({k: slide.get(k) for k in PUBLIC_FIELDS}, sort_keys=True, default=str).encode()).hexdigest()


def seal_business_content(deck):
    deck['metadata']['content_contract_digests'] = [content_digest(s) for s in deck['slides']]
    for s in deck['slides']:
        s.setdefault('stable_slide_id', s['id'])
        s.setdefault('evidence_sources', [s.get('source_label') or 'Recorded data'])
        s.setdefault('narration_script', s.get('speaker_notes') or s.get('narrative', ''))
        s.setdefault('reading_order', ['slide_header', 'narrative_lead', 'measured_content', 'source_footer'])
        from .builders.common import calculate_timing
        s['timing_metadata'] = calculate_timing(s['narration_script'])
    seal_presenter_notes(deck)
    deck['metadata']['validation_summary'] = verify_business_content(deck)
    return deck


def seal_presenter_notes(deck):
    deck['metadata']['content_contract_notes'] = [hashlib.sha256(str(s.get('speaker_notes') or '').encode()).hexdigest() for s in deck['slides']]



def semantic_issues(deck, source_columns=None):
    """Check report integrity, calculation meaning, and visual bindings.

    Contract decks have deliberately bounded language. Older AI plans additionally
    require actual source capabilities for causal/commercial assertions.
    """
    if deck.get('metadata', {}).get('deck_style') == 'decision_brief':
        return []  # Its independent immutable snapshot verifier owns this path.
    issues = []
    ledger = {e.get('evidence_id'): e for e in deck.get('evidence_ledger', [])}
    slides = deck.get('slides') or []
    expected = deck.get('metadata', {}).get('content_contract_digests')
    notes = deck.get('metadata', {}).get('content_contract_notes')
    for index, slide in enumerate(slides):
        match = re.search(r'\((\d+)\s*/\s*(\d+)\)\s*$', str(slide.get('title') or ''))
        if match:
            part, total = map(int, match.groups())
            base = str(slide['title'])[:match.start()].strip()
            start = index-part+1
            titles = [str(s.get('title') or '') for s in slides[max(0, start):start+total]]
            if not 1 <= part <= total or start < 0 or len(titles) != total or any(not re.fullmatch(re.escape(base)+r'\s*\('+str(i)+r'\s*/\s*'+str(total)+r'\)', title) for i, title in enumerate(titles, 1)):
                issues.append(f"Continuation title has missing or mismatched parts on '{slide.get('title')}'.")
    if notes is not None and notes != [hashlib.sha256(str(s.get('speaker_notes') or '').encode()).hexdigest() for s in slides]:
        issues.append('Presenter notes changed after content verification.')
    if expected is not None and expected != [content_digest(s) for s in slides]:
        issues.append('Business report wording or values changed after evidence grounding.')
    for e in ledger.values():
        nums = e.get('calculation_inputs')
        method = e.get('calculation_methodology')
        if nums is not None and method in {'sum', 'mean', 'median', 'count'}:
            try:
                if method in {'mean', 'median'} and e.get('denominator') != len(nums):
                    issues.append(f"Denominator does not match recorded inputs for {e.get('metric_name')}.")
                actual = {'sum': sum, 'mean': mean, 'median': median, 'count': len}[method](nums)
                if not math.isclose(float(e['numeric_value']), actual, rel_tol=1e-9, abs_tol=1e-9):
                    issues.append(f"Calculation does not reproduce {e.get('metric_name')}.")
            except (ValueError, TypeError, KeyError):
                issues.append(f"Invalid calculation inputs for {e.get('metric_name')}.")
    from .visual_binding import bind_chart
    for s in slides:
        for m in s.get('metrics') or []:
            e = ledger.get(m.get('evidence_id'))
            if expected is not None:
                try:
                    if not e or m.get('label') != e.get('metric_name') or m.get('unit') != e.get('unit') or not math.isclose(float(str(m['value']).replace(',', '')), float(e['numeric_value']), rel_tol=.001, abs_tol=.01):
                        issues.append(f"Metric is not bound to its recorded measure on '{s.get('title')}'.")
                except (ValueError, TypeError, KeyError):
                    issues.append(f"Invalid metric on '{s.get('title')}'.")
        chart = s.get('chart')
        if chart and not bind_chart(chart, s.get('evidence_ids') or [s.get('evidence_id')], list(ledger.values())):
            issues.append(f"Chart lacks matching measure, unit or period on '{s.get('title')}'.")
        if chart and expected is not None:
            values = [v for series in chart.get('series', []) for v in series.get('values', [])]
            refs = chart.get('evidence_ids', [])
            if len(values) != len(refs) or any(ref not in ledger or not math.isclose(float(v), float(ledger[ref]['numeric_value']), rel_tol=.001, abs_tol=.01) for v, ref in zip(values, refs)):
                issues.append(f"Chart values disagree with their evidence on '{s.get('title')}'.")
    source_columns = source_columns if source_columns is not None else deck.get("metadata", {}).get("source_columns")
    if source_columns is None and deck.get('metadata', {}).get('traceable_metrics'):
        source_columns = [m.get('source_column', '') for m in deck['metadata']['traceable_metrics']]
    if source_columns is not None and expected is None:
        fields = ' '.join(str(c).lower() for c in source_columns)
        assertions = ' '.join(str(s.get(k) or '') for s in slides for k in ('title', 'narrative', 'bullets')).lower()
        requirements = {
            'footfall': ('footfall', 'visitors', 'traffic'), 'margin': ('margin',),
            'roi': ('roi', 'return on investment'), 'seasonal': ('date', 'month', 'season', 'week'),
            'policy compliance': ('policy', 'required', 'compliance'), 'zero service failures': ('failure', 'incident'),
        }
        for claim, required in requirements.items():
            if re.search(r'\b'+re.escape(claim)+r'\b', assertions) and not any(w in fields for w in required):
                issues.append(f"'{claim}' is not supported by the recorded fields.")
    if expected is None:
        for s in slides:
            text = ' '.join(str(s.get(k) or '') for k in ('title', 'narrative', 'bullets')).lower()
            refs = s.get('evidence_ids') or [s.get('evidence_id')]
            facts = [ledger[r] for r in refs if r in ledger]
            if re.search(r'\b(?:causes?|caused|drives?|driven by|ensures?|guarantees?)\b', text) and not any(e.get('finding_type') == 'causal_analysis' for e in facts):
                issues.append(f"Causal assertion lacks supporting analysis on '{s.get('title')}'.")
            if re.search(r'\b(?:forecast|projected|prediction|expected return)\b', text) and not any(e.get('finding_type') == 'forecast' and e.get('assumptions') for e in facts):
                issues.append(f"Forecast lacks a model and assumptions on '{s.get('title')}'.")
            chart = s.get('chart') or {}
            if str(chart.get('chart_type') or chart.get('type')).lower() in {'pie', 'donut', 'doughnut'}:
                values = [v for series in chart.get('series', []) for v in series.get('values', []) if isinstance(v, (int, float))]
                if chart.get('unit') == '%' and any(v > 100 for v in values):
                    issues.append(f"Composition counts are labelled as percentages on '{s.get('title')}'.")
                if values and 'majority' in text and max(values) <= sum(values)/2:
                    issues.append(f"No category has a majority on '{s.get('title')}'.")
    planning = deck.get('metadata', {}).get('planning_validation') or {}
    if planning and not planning.get('is_valid', False):
        issues.extend(planning.get('unsupported_claims') or ['Presentation plan is not grounded.'])
    return list(dict.fromkeys(issues))


def validate_legacy_export(deck):
    """Previously cached audit results cannot certify an older generated deck."""
    metadata = deck.get('metadata', {})
    if metadata.get('content_contract') or metadata.get('deck_style') == 'decision_brief':
        return
    if metadata.get('traceable_metrics') or metadata.get('validation_summary'):
        issues = semantic_issues(deck)
        if issues:
            raise ValueError('This older presentation needs an evidence refresh before export: ' + '; '.join(issues[:3]))


def verify_business_content(deck):
    issues = semantic_issues(deck)
    checked = len(deck.get('evidence_ledger', []))
    return {'status': 'FAILED' if issues else 'PASSED', 'total_metrics_checked': checked,
            'passed_verification': 0 if issues else checked, 'discrepancies_flagged': len(issues),
            'discrepancies': [{'reason': issue} for issue in issues], 'checked_items': [],
            'semantic_issues': issues, 'semantic_status': 'FAILED' if issues else 'PASSED'}
