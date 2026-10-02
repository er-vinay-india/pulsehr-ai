"""Bind a chart to a claim's measure, period and evidence, never its position."""
import re


def _key(value):
    return re.sub(r'[^a-z0-9]', '', str(value).lower())


def bind_chart(chart, evidence_ids, ledger, requested_metrics=()):
    if not chart:
        return None
    refs = set(chart.get('evidence_ids') or ([chart['evidence_id']] if chart.get('evidence_id') else []))
    cited = set(evidence_ids or [])
    if not refs or not refs <= cited:
        return None
    entries = {e.get('evidence_id'): e for e in ledger}
    if not all(r in entries for r in refs):
        return None
    measure = chart.get('metric_name') or chart.get('metric_col')
    unit = chart.get('unit')
    period = chart.get('period') or chart.get('date_range')
    if not measure or not unit or not period:
        return None
    for ref in refs:
        fact = entries[ref]
        if _key(fact.get('unit')) != _key(unit) or str(fact.get('date_range')) != str(period):
            return None
        fact_measure = fact.get('metric_name') or ''
        if _key(measure) not in _key(fact_measure):
            return None
    requested = [m.get('metric_name') or m.get('label') or m.get('name') for m in requested_metrics if isinstance(m, dict)]
    if requested and not any(_key(m) == _key(measure) for m in requested if m):
        return None
    if not chart.get('categories') or not chart.get('series'):
        return None
    return chart
