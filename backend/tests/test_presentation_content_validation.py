from copy import deepcopy

import pytest

from app.services.presentation.claim_verifier import verify_presentation_claims
from app.services.presentation.content_validation import semantic_issues
from app.services.presentation.grounded_review import build_grounded_review
from app.services.presentation.hr_report import build_hr_report
from app.services.presentation.review_gates import evaluate_automated_gates
from app.services.presentation.director.director_models import SlidePlan
from app.services.presentation.director.plan_validator import validate_plan
from test_presentation_hr_report import fixture_context
from test_presentation_business_content import context, intent

pytestmark = pytest.mark.presentation


def test_hr_report_calculations_and_chart_bindings_are_verified():
    deck = build_hr_report({}, fixture_context())
    result = verify_presentation_claims(deck, deck['evidence_ledger'])
    assert result['status'] == 'PASSED', result
    assert result['semantic_status'] == 'PASSED'


@pytest.mark.parametrize('field', ['title', 'narrative', 'bullets', 'metrics', 'chart', 'table'])
def test_modified_audience_content_is_blocked_before_export(field):
    deck = build_hr_report({}, fixture_context())
    slide = next((s for s in deck['slides'] if s.get(field)), deck['slides'][0])
    slide[field] = {'fabricated': 100} if field in {'chart', 'table'} else [] if field in {'bullets', 'metrics'} else 'Footfall drives projected ROI'
    result = verify_presentation_claims(deck, deck['evidence_ledger'])
    assert result['status'] == 'FAILED'
    gates = evaluate_automated_gates(deck, result)
    assert gates['gates']['gate_2_storyline']['status'] == 'FAILED'
    assert gates['gates']['gate_3_evidence']['status'] == 'FAILED'


def test_ledger_calculations_are_recomputed_not_just_accepted():
    deck = build_hr_report({}, fixture_context())
    fact = next(e for e in deck['evidence_ledger'] if e['metric_name'] == 'Recorded office days')
    fact['numeric_value'] = 200
    assert verify_presentation_claims(deck, deck['evidence_ledger'])['status'] == 'FAILED'


def test_completeness_cannot_verify_resilience_even_with_same_value_and_id():
    ledger = [{'evidence_id': 'EVID-GOV-01', 'metric_name': 'Data Completeness', 'numeric_value': 100, 'unit': '%'}]
    deck = {'metadata': {'completeness_pct': 100}, 'slides': [{'title': 'Reliability', 'metrics': [
        {'label': 'System Resilience', 'value': '100%', 'evidence_id': 'EVID-GOV-01'}]}]}
    assert verify_presentation_claims(deck, ledger)['discrepancies_flagged'] > 0


def test_car_fields_cannot_establish_footfall_seasonality_or_roi():
    deck = {'metadata': {}, 'slides': [{'title': 'Seasonal footfall drives projected ROI', 'narrative': 'Margin is improving.'}]}
    issues = semantic_issues(deck, ['Make', 'Colour', 'Odometer (KM)', 'Doors', 'Price'])
    assert any('footfall' in issue for issue in issues)
    assert any('seasonal' in issue for issue in issues)
    assert any('roi' in issue for issue in issues)
    assert any('margin' in issue for issue in issues)


def test_fallback_reports_source_measure_and_excludes_engineered_fields():
    ctx = {'records': [{'Make': 'Ford', 'Price': 0, 'interact_Price_Doors': 1}, {'Make': 'BMW', 'Price': 10, 'interact_Price_Doors': 2}],
           'columns': ['Make', 'Price', 'interact_Price_Doors'], 'target_sheet': {'name': 'Cars'}}
    deck = build_grounded_review({'objective': 'Project footfall and ROI'}, ctx)
    assert verify_presentation_claims(deck, deck['evidence_ledger'])['status'] == 'PASSED'
    assert next(e for e in deck['evidence_ledger'] if e['metric_name'] == 'Average Price')['numeric_value'] == 5
    assert 'interact_' not in str(deck['slides'])
    assert 'ROI' not in str(deck['slides'])


def test_known_evidence_id_is_not_enough_for_unanswered_plan():
    ctx = context()
    target = intent(ctx)
    target.key_questions_to_answer = ['How much attrition occurred?']
    slides = [SlidePlan(slide_id=str(i), section_id="review", layout="comparison_split", sequence_number=i+1, headline=f'Topic {i}', key_message=f'Different content {i}', evidence_ids=['not-in-ledger']) for i in range(3)]
    result = validate_plan(ctx, target, slides)
    assert not result.is_valid
    assert result.unanswered_user_questions
    assert any('unknown evidence' in issue for issue in result.unsupported_claims)
