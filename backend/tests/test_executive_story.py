import pytest
import math
from app.services.time_series_forecast import holt_damped_forecast, build_time_series_forecast, clean_float
from app.services.ai_evaluation import evaluate_ai_narrative, extract_numeric_claims
from app.services.executive_story import profile_sheet_data, get_or_generate_executive_story
from fastapi.testclient import TestClient
from app.main import app


def test_clean_float():
    assert clean_float(None) == 0.0
    assert clean_float(float('nan')) == 0.0
    assert clean_float(float('inf')) == 0.0
    assert clean_float("invalid", 5.0) == 5.0
    assert clean_float(3.14) == 3.14


def test_holt_damped_forecast_basic():
    series = [10.0, 12.0, 14.0, 13.0, 15.0, 17.0, 16.0, 18.0]
    res = holt_damped_forecast(series, steps=5)
    assert len(res['forecasts']) == 5
    metrics = res['metrics']
    assert 0.0 <= metrics['r_squared'] <= 1.0
    assert metrics['mape_pct'] >= 0.0
    assert metrics['trend_direction'] in [
        'Accelerating Upward', 'Moderate Increase', 'Sharp Decline', 'Moderate Decline', 'Stable / Mean-Reverting'
    ]
    # Verify no NaNs in forecast points
    for pt in res['forecasts']:
        assert not math.isnan(pt['forecast'])
        assert not math.isnan(pt['lower_80'])
        assert not math.isnan(pt['upper_80'])
        assert not math.isnan(pt['lower_95'])
        assert not math.isnan(pt['upper_95'])


def test_holt_damped_forecast_flat_and_edge_cases():
    # Constant series
    res_flat = holt_damped_forecast([5.0, 5.0, 5.0, 5.0], steps=3)
    assert len(res_flat['forecasts']) == 3
    assert not math.isnan(res_flat['metrics']['r_squared'])
    assert not math.isnan(res_flat['metrics']['mae'])

    # Single point
    res_single = holt_damped_forecast([10.0], steps=3)
    assert len(res_single['forecasts']) == 3

    # Empty list
    res_empty = holt_damped_forecast([], steps=3)
    assert res_empty['forecasts'] == []


def test_build_time_series_forecast_with_dates():
    records = [
        {'date': '2026-01-01', 'absent_days': 2},
        {'date': '2026-01-02', 'absent_days': 3},
        {'date': '2026-01-03', 'absent_days': 1},
        {'date': '2026-01-04', 'absent_days': 4},
        {'date': '2026-01-05', 'absent_days': 5},
    ]
    forecast_data = build_time_series_forecast(records, sheet_name='AbsenceLog')
    assert forecast_data is not None
    assert forecast_data['has_dates'] is True
    assert len(forecast_data['forecast']) > 0
    assert len(forecast_data['historical']) == 5
    assert all(f['forecast'] >= 0 for f in forecast_data['forecast'])


def test_extract_numerical_claims():
    text = "We analyzed 712 employees. Overall 42 employees took more than 3 days leave, representing 15.5% of the team."
    claims = extract_numeric_claims(text)
    assert len(claims) >= 3
    numbers = [c['value'] for c in claims if 'value' in c]
    assert 712.0 in numbers
    assert 42.0 in numbers
    assert 15.5 in numbers


def test_evaluate_ai_narrative_verification():
    ground_truth = {
        'total_records': 100,
        'employees_with_leave': 25,
        'more_than_3_days_leave': 5,
        'avg_absent_days': 2.4
    }
    # Accurate narrative
    narrative_good = (
        "Out of 100 employees, 25 recorded leaves with an average of 2.4 days. "
        "Notably, 5 individuals exceeded 3 days of absence."
    )
    eval_good = evaluate_ai_narrative(narrative_good, ground_truth, total_records=100)
    assert eval_good['trust_score'] >= 80
    assert eval_good['verified_claims_count'] >= 3

    # Hallucinated narrative
    narrative_hallucinated = (
        "We surveyed 999 workers and found 88 on leave with 99.9 average days."
    )
    eval_bad = evaluate_ai_narrative(narrative_hallucinated, ground_truth, total_records=100)
    discrepancies = [c for c in eval_bad['audit_trail'] if c['status'] == 'DISCREPANCY']
    assert len(discrepancies) > 0


def test_profile_sheet_data_leaves():
    records = [
        {'Employee': 'Alice', 'Department': 'Sales', 'Absent_Days': 1},
        {'Employee': 'Bob', 'Department': 'Sales', 'Absent_Days': 4},
        {'Employee': 'Charlie', 'Department': 'Engineering', 'Absent_Days': 2},
        {'Employee': 'Diana', 'Department': 'Engineering', 'Absent_Days': 5},
    ]
    cols = ['Employee', 'Department', 'Absent_Days']
    profile = profile_sheet_data(records, cols, 'LeaveSheet')
    gt = profile['ground_truth']
    assert gt['total_records'] == 4
    assert gt['total_on_leave'] == 4
    assert gt['more_than_3_days_leave'] == 2
    assert 'bar' in profile['charts']
    assert 'donut' in profile['charts']
    assert len(profile['thresholds']) >= 3


def test_analytics_overview_api_integration():
    client = TestClient(app)
    res = client.get('/api/analytics/overview')
    assert res.status_code == 200
    data = res.json()
    assert 'stats' in data
    assert 'sheets' in data
    assert 'executive_story' in data
    assert 'evaluation' in data
    assert 'charts' in data
    assert 'forecast' in data
    assert 'relational_story' in data
    assert 'story_meta' in data
