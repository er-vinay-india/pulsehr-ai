"""Audience content stays tied to actual values, periods and source fields."""
import json
from types import SimpleNamespace

import pytest

from app.services.presentation.director.director_models import PresentationPlanningContext, PresentationIntent
from app.services.presentation.director.information_extractor import extract_and_triage_information
from app.services.presentation.director.narrative_planner import plan_narrative
from app.services.presentation.director.evidence_context import evidence_context

pytestmark = pytest.mark.presentation


def context(**kwargs):
    values = dict(domain='Workforce attendance', objective='July attendance review',
                  audience='HR managers', dataset_label='WFO July 2026', reporting_period='July 2026',
                  total_records=3, current_evidence=[{
                      'evidence_id': 'ATT-01', 'title': 'Recorded office attendance',
                      'metric_name': 'Office days', 'metric_value': '0 days', 'numeric_value': 0,
                      'unit': 'days', 'denominator': 3, 'date_range': 'July 2026',
                      'limitations': 'WFO policy not supplied', 'finding_type': 'measured_fact',
                  }])
    return PresentationPlanningContext(**(values | kwargs))


def intent(ctx):
    return PresentationIntent(domain=ctx.domain, purpose=ctx.objective, primary_goal=ctx.objective, target_audience=ctx.audience)


def test_writer_context_retains_zero_units_period_and_limitation():
    ctx = context()
    units = extract_and_triage_information(ctx, intent(ctx), max_retries=-1)
    payload = evidence_context(ctx, units)
    fact = payload['findings'][0]
    assert fact['numeric_value'] == 0
    assert fact['unit'] == 'days'
    assert fact['denominator'] == 3
    assert fact['date_range'] == 'July 2026'
    assert fact['limitations'] == 'WFO policy not supplied'
    assert units[0].statement.endswith('100.0% of data cells are non-empty.')
    assert 'data integrity' not in units[0].statement


def test_narrative_prompt_has_facts_without_commercial_anchor(monkeypatch):
    ctx = context()
    seen = []

    def generate(**kwargs):
        seen.append(kwargs['prompt'])
        return SimpleNamespace(success=True, raw_text=json.dumps({'sections': [{'title': 'Attendance', 'purpose': 'Review office days'}]}))

    monkeypatch.setattr('app.services.presentation.director.narrative_planner.ModelGateway.generate', generate)
    strategy = plan_narrative(ctx, intent(ctx), [], max_retries=0)
    assert '"numeric_value": 0' in seen[0]
    assert 'WFO policy not supplied' in seen[0]
    assert 'top-quartile performance dispersion presents' not in seen[0]
    assert strategy.executive_thesis == 'Office days: 0 days'


def test_narrative_fallback_does_not_invent_success_or_repeat_user_goal():
    ctx = context(current_evidence=[])
    strategy = plan_narrative(ctx, intent(ctx), [], max_retries=-1)
    assert strategy.executive_thesis == 'WFO July 2026 review for July 2026'
    assert 'stabilization' not in strategy.executive_thesis
