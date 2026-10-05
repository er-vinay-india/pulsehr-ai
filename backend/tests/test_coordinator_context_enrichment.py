"""Coordinator interpretation is bound once; workers only execute verified plans."""
import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.db.database import get_connection
from app.main import app
from app.services import copilot_query_planner as planner, sheet_catalog
from app.services.copilot.council_coordinator import CouncilCoordinator
from app.services.copilot.coordinator_models import RouteContract


@pytest.fixture
def attendance():
    records = [
        {'Employee ID': 'A1', 'Department': 'Alpha', 'Total Attendance': 25},
        {'Employee ID': 'B1', 'Department': 'Beta', 'Total Attendance': 25},
        *[{'Employee ID': f'S{i}', 'Department': 'Sales', 'Total Attendance': 20} for i in range(3)],
    ]
    for row in records:
        row.update({'1st to 31st July': row['Total Attendance'], 'Approved Leaves': 2,
                    'interact_mean_Full Name_by_Department': 123.0})
    frame = pd.DataFrame(records)
    with get_connection() as conn:
        ds = conn.execute("INSERT INTO dataset_uploads(filename,original_name,file_type) VALUES ('attendance.csv','attendance.csv','csv')").lastrowid
        sheet_catalog.insert_sheets(conn, ds, sheet_catalog.prepare_sheets({'July Attendance': frame}, 'attendance.csv', embed=False))
        sid = conn.execute('SELECT id FROM sheets WHERE dataset_id=?', (ds,)).fetchone()['id']
        conn.commit()
    return ds, sid, frame


def no_model(*args, **kwargs):
    raise AssertionError('Known business meaning must be resolved from the semantic catalogue')


@pytest.mark.parametrize('query', [
    'which department highest present in the office',
    'Which department has the highest office presence?',
    'which department has highest WFO',
])
def test_office_presence_enriched_before_dispatch(attendance, monkeypatch, query):
    ds, sid, frame = attendance
    monkeypatch.setattr(CouncilCoordinator, '_evaluate_coordinator_llm', no_model)
    decision = CouncilCoordinator.coordinate(query, df=frame, sheet_id=sid, dataset_id=ds,
        prior_context={'sheet_id': sid, 'metric': 'leaves'})
    request = decision.analytical_request
    assert request.resolution_method == 'semantic_catalog'
    assert request.field_bindings == {'metric': 'Total Attendance', 'grouping': 'Department'}
    assert request.plan['metric'] == 'attendance'
    assert request.plan['direction'] == 'highest'
    assert request.plan['time_window'] == 'July'
    assert request.plan['sheet_id'] == sid
    assert request.response_detail == 'brief'
    assert not any(m.startswith('interact_') for m in request.available_measures)
    # The worker must not repeat interpretation or model planning.
    monkeypatch.setattr(planner, 'plan_analytical_query', no_model)
    result = CouncilCoordinator.execute_sync(decision, query, df=frame, sheet_name='July Attendance', sheet_id=sid, dataset_id=ds)
    assert result['status'] == 'success'
    assert result['coordinator']['enriched_request']['response_detail'] == 'brief'
    assert 'Alpha' in result['answer'] and 'Beta' in result['answer']
    assert 'tied for the highest average office attendance in July' in result['answer']
    assert '25.00 days per employee' in result['answer']
    # Sales has the largest total (60), but not the highest attendance per employee.
    assert result['prior_context']['last_finding']['detail']['focus_group'] != 'Sales'


def test_semantic_attendance_capability_for_period_only_sheet(attendance, monkeypatch):
    ds, sid, frame = attendance
    frame = frame.drop(columns=['Total Attendance'])
    monkeypatch.setattr(CouncilCoordinator, '_evaluate_coordinator_llm', no_model)
    request = CouncilCoordinator.coordinate('which department highest present in the office', df=frame, sheet_id=sid, dataset_id=ds).analytical_request
    assert request.plan['metric'] == 'attendance'
    assert request.source_columns == ['1st to 31st July']


def test_unknown_wording_gets_one_validated_coordinator_mapping(attendance, monkeypatch):
    ds, sid, frame = attendance
    calls = []
    def model(query, prior, columns, analytical_context):
        calls.append(analytical_context)
        assert 'Total Attendance' in [m['name'] for m in analytical_context['measures']]
        assert 'interact_mean_Full Name_by_Department' not in columns
        return RouteContract(intent='QUERY_DATASET', route='DATASET_ENGINE', confidence=.95,
            entities={'metric': 'Total Attendance', 'group_by': 'Department', 'sheet_id': 99999,
                      'direction': 'lowest'})
    monkeypatch.setattr(CouncilCoordinator, '_evaluate_coordinator_llm', model)
    decision = CouncilCoordinator.coordinate('which department has highest desk-day engagement', df=frame, sheet_id=sid, dataset_id=ds)
    assert len(calls) == 1
    request = decision.analytical_request
    assert request.resolution_method == 'coordinator_model'
    assert request.plan['sheet_id'] == sid
    assert request.plan['direction'] == 'highest'
    monkeypatch.setattr(planner, 'plan_analytical_query', no_model)
    events = list(CouncilCoordinator.stream_events(decision, 'which department has highest desk-day engagement', df=frame, sheet_name='July Attendance', sheet_id=sid, dataset_id=ds))
    assert len(calls) == 1
    assert any('event: done' in e and 'Alpha' in e for e in events)


@pytest.mark.parametrize('metric', ['Invented Presence Index', 'Employee ID', 'interact_mean_Full Name_by_Department'])
def test_model_cannot_bind_unknown_identity_or_generated_metric(attendance, monkeypatch, metric):
    ds, sid, frame = attendance
    monkeypatch.setattr(CouncilCoordinator, '_evaluate_coordinator_llm', lambda *args: RouteContract(
        intent='QUERY_DATASET', route='DATASET_ENGINE', confidence=.99,
        entities={'metric': metric, 'group_by': 'Department'}))
    request = CouncilCoordinator.coordinate('which department highest desk-day engagement', df=frame, dataset_id=ds, sheet_id=sid).analytical_request
    assert request.resolution_method == 'clarification'
    assert request.plan['intent'] == 'ambiguity_clarification'
    assert not request.field_bindings


def test_unspecified_performance_stays_ambiguous(attendance, monkeypatch):
    ds, sid, frame = attendance
    monkeypatch.setattr(CouncilCoordinator, '_evaluate_coordinator_llm', no_model)
    request = CouncilCoordinator.coordinate('which department is best?', df=frame, dataset_id=ds, sheet_id=sid).analytical_request
    assert request.resolution_method == 'clarification'


def test_coordinator_mapping_timeout_does_not_delegate_guessing(attendance, monkeypatch):
    ds, sid, frame = attendance
    calls = []
    def unavailable(*args):
        calls.append(args)
        return None
    monkeypatch.setattr(CouncilCoordinator, '_evaluate_coordinator_llm', unavailable)
    decision = CouncilCoordinator.coordinate('which department highest desk-day engagement', df=frame, dataset_id=ds, sheet_id=sid)
    assert len(calls) == 1
    assert decision.analytical_request.resolution_method == 'clarification'
    monkeypatch.setattr(planner, 'plan_analytical_query', no_model)
    result = CouncilCoordinator.execute_sync(decision, 'which department highest desk-day engagement', df=frame, sheet_id=sid, dataset_id=ds)
    assert result['status'] == 'ambiguity_clarification_required'
    assert len(calls) == 1


def test_initial_control_plane_call_is_not_repeated_for_enrichment(attendance, monkeypatch):
    from app.services.copilot.coordinator_models import CoordinatorDecision
    ds, sid, frame = attendance
    routed = CoordinatorDecision(assignment='dataset_calculation', worker_target='analytical_planner',
        timeout_seconds=4, rationale='Qwen 3.5 Coordinator Dataset Route',
        route_contract=RouteContract(intent='QUERY_DATASET', route='DATASET_ENGINE', entities={}))
    monkeypatch.setattr(CouncilCoordinator, '_route', lambda *args: routed)
    monkeypatch.setattr(CouncilCoordinator, '_evaluate_coordinator_llm', no_model)
    decision = CouncilCoordinator.coordinate('which department highest desk-day engagement', df=frame, dataset_id=ds, sheet_id=sid)
    assert decision.analytical_request.resolution_method == 'clarification'


def test_current_scope_does_not_inherit_another_sheets_metric(attendance, monkeypatch):
    ds, sid, frame = attendance
    monkeypatch.setattr(CouncilCoordinator, '_evaluate_coordinator_llm', no_model)
    request = CouncilCoordinator.coordinate('which department highest', df=frame, dataset_id=ds, sheet_id=sid,
        prior_context={'sheet_id': sid + 1, 'metric': 'attendance'}).analytical_request
    assert request.plan['intent'] == 'ambiguity_clarification'
    assert request.plan['metric'] is None
    assert CouncilCoordinator.coordinate('what is 2+2', df=frame).analytical_request is None
    assert CouncilCoordinator.coordinate('Explain median', df=frame).analytical_request is None


def test_reported_question_json_and_stream_use_same_enriched_plan(attendance, monkeypatch):
    ds, sid, frame = attendance
    monkeypatch.setattr(CouncilCoordinator, '_evaluate_coordinator_llm', no_model)
    client = TestClient(app)
    results = []
    for endpoint in ('/api/copilot/query', '/api/copilot/query/stream'):
        response = client.post(endpoint, json={'query': 'which department highest present in the office', 'dataset_id': ds, 'sheet_id': sid})
        assert response.status_code == 200
        if endpoint.endswith('/stream'):
            done = next(e for e in response.text.split('\n\n') if e.startswith('event: done'))
            result = json.loads(done.split('data: ', 1)[1])
        else:
            result = response.json()
        assert result['status'] == 'success'
        assert result['timings']['is_deterministic'] is True
        assert result['coordinator']['enriched_request']['field_bindings']['metric'] == 'Total Attendance'
        results.append(result)
    assert results[0]['answer'] == results[1]['answer']
    assert results[0]['coordinator']['enriched_request']['response_detail'] == 'brief'


def test_default_brief_answer_matches_exact_target(monkeypatch):
    """Verifies that the default answer for direct factual question matches exact target:
    'Operations and Infrastructure had the highest average office attendance in July: 17.23 days per employee, across 26 employees.'
    """
    records = []
    # Operations and Infrastructure: 26 employees, average 17.23 days
    for i in range(26):
        records.append({
            'Employee ID': f'OI_{i}',
            'Department': 'Operations and Infrastructure',
            '1st to 31st July': 17.23,
            'Total Attendance': 17.23,
            'Approved Leaves': 2.0
        })
    # Corporate Functions: 30 employees, average 10.2 days
    for i in range(30):
        records.append({
            'Employee ID': f'CF_{i}',
            'Department': 'Corporate Functions',
            '1st to 31st July': 10.20,
            'Total Attendance': 10.20,
            'Approved Leaves': 3.0
        })

    frame = pd.DataFrame(records)
    with get_connection() as conn:
        ds = conn.execute("INSERT INTO dataset_uploads(filename,original_name,file_type) VALUES ('ops_infra.csv','ops_infra.csv','csv')").lastrowid
        sheet_catalog.insert_sheets(conn, ds, sheet_catalog.prepare_sheets({'July Attendance': frame}, 'ops_infra.csv', embed=False))
        sid = conn.execute('SELECT id FROM sheets WHERE dataset_id=?', (ds,)).fetchone()['id']
        conn.commit()

    monkeypatch.setattr(CouncilCoordinator, '_evaluate_coordinator_llm', no_model)
    query = "which department has the highest attendance?"
    decision = CouncilCoordinator.coordinate(query, df=frame, sheet_id=sid, dataset_id=ds)

    assert decision.analytical_request.response_detail == 'brief'
    result = CouncilCoordinator.execute_sync(decision, query, df=frame, sheet_name='July Attendance', sheet_id=sid, dataset_id=ds)

    expected = "Operations and Infrastructure had the highest average office attendance in July: 17.23 days per employee, across 26 employees."
    assert result['answer'] == expected
    assert result['coordinator']['enriched_request']['response_detail'] == 'brief'
    # No markdown tables or extra governance notes in brief mode
    assert "| Period |" not in result['answer']
    assert "> **Data Governance Limitations**:" not in result['answer']


def test_brief_and_detailed_use_identical_calculations_preserve_ties_and_qualifications(monkeypatch):
    """Verifies that brief and detailed responses:
    1. Use identical calculations
    2. Preserve ties
    3. Retain any qualification that materially affects the answer
    4. Provide tables, recommendations, and extra governance notes when requested.
    """
    # 2 tied departments with small population (2 employees each)
    records = [
        {'Employee ID': 'T1_A', 'Department': 'Team Alpha', '1st to 31st July': 22.5, 'Total Attendance': 22.5, 'Approved Leaves': 1},
        {'Employee ID': 'T1_B', 'Department': 'Team Alpha', '1st to 31st July': 22.5, 'Total Attendance': 22.5, 'Approved Leaves': 1},
        {'Employee ID': 'T2_A', 'Department': 'Team Beta', '1st to 31st July': 22.5, 'Total Attendance': 22.5, 'Approved Leaves': 1},
        {'Employee ID': 'T2_B', 'Department': 'Team Beta', '1st to 31st July': 22.5, 'Total Attendance': 22.5, 'Approved Leaves': 1},
        {'Employee ID': 'T3_A', 'Department': 'Team Gamma', '1st to 31st July': 15.0, 'Total Attendance': 15.0, 'Approved Leaves': 2},
    ]
    frame = pd.DataFrame(records)
    with get_connection() as conn:
        ds = conn.execute("INSERT INTO dataset_uploads(filename,original_name,file_type) VALUES ('tied_teams.csv','tied_teams.csv','csv')").lastrowid
        sheet_catalog.insert_sheets(conn, ds, sheet_catalog.prepare_sheets({'July Attendance': frame}, 'tied_teams.csv', embed=False))
        sid = conn.execute('SELECT id FROM sheets WHERE dataset_id=?', (ds,)).fetchone()['id']
        conn.commit()

    monkeypatch.setattr(CouncilCoordinator, '_evaluate_coordinator_llm', no_model)

    # 1. Brief: Direct factual question
    q_brief = "which department has the highest attendance?"
    dec_brief = CouncilCoordinator.coordinate(q_brief, df=frame, sheet_id=sid, dataset_id=ds)
    assert dec_brief.analytical_request.response_detail == 'brief'
    res_brief = CouncilCoordinator.execute_sync(dec_brief, q_brief, df=frame, sheet_name='July Attendance', sheet_id=sid, dataset_id=ds)

    # 2. Detailed: Requesting explanation, breakdown, and evidence
    q_detailed = "which department has the highest attendance? Give explanation, breakdown, and evidence"
    dec_detailed = CouncilCoordinator.coordinate(q_detailed, df=frame, sheet_id=sid, dataset_id=ds)
    assert dec_detailed.analytical_request.response_detail == 'detailed'
    res_detailed = CouncilCoordinator.execute_sync(dec_detailed, q_detailed, df=frame, sheet_name='July Attendance', sheet_id=sid, dataset_id=ds)

    # Calculations must be 100% IDENTICAL
    assert res_brief['calculation'] == res_detailed['calculation']
    assert res_brief['evidence']['calculation_method'] == res_detailed['evidence']['calculation_method']
    assert res_brief['evidence']['coverage'] == res_detailed['evidence']['coverage']
    assert res_brief['prior_context']['last_ranking'] == res_detailed['prior_context']['last_ranking']

    # Both must PRESERVE TIES
    assert "Team Alpha and Team Beta tied" in res_brief['answer']
    assert "Team Alpha" in res_detailed['answer'] and "Team Beta" in res_detailed['answer']
    assert "tied for the **highest average attendance**" in res_detailed['answer']

    # Material qualification (small population caveat) retained beside the answer in brief
    assert "(Note: Group headcount is small; individual absences impact the average heavily.)" in res_brief['answer']
    # And present in detailed
    assert "Group headcount" in res_detailed['answer']

    # Detailed response contains extra tables, recommendations, and governance notes
    assert "> **Data Governance Limitations**:" in res_detailed['answer']
    assert "> **Data Governance Limitations**:" not in res_brief['answer']

