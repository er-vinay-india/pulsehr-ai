from app.services.leadership_report import chart_choices, validate_plan, plan_report
import pytest

FINDINGS = [{'id': 'a', 'detail': {'groups': [{'group': 'A', 'value': 3}]}}, {'id': 'b', 'detail': {'points': [{'period': '2026-01', 'value': 2}]}}, {'id': 'c', 'detail': {'coefficient': .8}}]


def test_chart_contract_rejects_invented_visuals_and_ids():
    assert validate_plan({'sections': [{'id': 'fake', 'chart': 'dot'}, {'id': 'a', 'chart': 'donut'}, {'id': 'a', 'chart': 'line'}, {'id': 'b', 'chart': 'line'}, {'id': 'c', 'chart': 'scatter'}]}, FINDINGS) == [{'id': 'a', 'chart': 'dot'}, {'id': 'b', 'chart': 'line'}, {'id': 'c', 'chart': 'table'}]


def test_empty_model_selection_rejected():
    assert validate_plan({'sections': []}, FINDINGS) == []
    with pytest.raises(ValueError):
        validate_plan({'sections': [{'id': 'invented'}]}, FINDINGS)


def test_empty_evidence_does_not_call_model():
    assert plan_report({'findings': []}, 'HR', 'worst department')['sections'] == []


def test_timeout_retains_computed_evidence(monkeypatch):
    import httpx
    def fail(*args, **kwargs):
        raise httpx.ReadTimeout('slow model')
    monkeypatch.setattr(httpx.Client, 'post', fail)
    result = plan_report({'findings': FINDINGS}, 'CEO', 'What matters?')
    assert result['mode'] == 'evidence'
    assert len(result['sections']) == 3


@pytest.mark.parametrize("payload", [None, [], {"sections": None}, {"sections": [{"id": []}]}])
def test_malformed_model_output_is_rejected(payload):
    with pytest.raises(ValueError):
        validate_plan(payload, FINDINGS)


def test_fallback_prioritizes_outcomes_without_losing_context(monkeypatch):
    import httpx
    monkeypatch.setattr(httpx.Client, 'post', lambda *a, **k: (_ for _ in ()).throw(httpx.ReadTimeout('slow')))
    findings = [{'id': 'weather', 'metric': 'Temperature'}, {'id': 'economy', 'metric': 'Unemployment'}, {'id': 'sales', 'metric': 'Weekly_Sales'}]
    result = plan_report({'findings': findings}, 'Sales manager', 'What needs attention?')
    assert [s['id'] for s in result['sections']] == ['sales', 'weather', 'economy']
    assert findings[0]['id'] == 'weather'


def test_relevance_respects_role_and_preserves_unknown_order():
    from app.services.leadership_report import order_findings
    findings = [{'id': 'sales', 'metric': 'Sales'}, {'id': 'hr', 'metric': 'Attendance'}, {'id': 'unknown', 'metric': 'Custom indicator'}]
    assert order_findings(findings, 'HR head')[0]['id'] == 'hr'
    assert order_findings([findings[2], {}], 'CEO') == [findings[2], {}]
