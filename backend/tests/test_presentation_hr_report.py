import pytest

from app.services.presentation.hr_report import build_hr_report
from app.services.presentation.deck_generator import generate_presentation_deck_spec

pytestmark = pytest.mark.presentation


def fixture_context(records=None):
    records = records if records is not None else [
        {"Emp ID": "001", "Department": "Design", "1st to 5th July 2026": 0, "6th to 12th July 2026": 3,
         "Total Attendance": 3, "Approved Leaves": 2, "Final Attendance": 1},
        {"Emp ID": "002", "Department": "Operations", "1st to 5th July 2026": 2, "6th to 12th July 2026": 4,
         "Total Attendance": 6, "Approved Leaves": 1, "Final Attendance": 5},
        {"Emp ID": "003", "Department": "Design", "1st to 5th July 2026": None, "6th to 12th July 2026": 1,
         "Total Attendance": None, "Approved Leaves": None, "Final Attendance": None},
    ]
    return {"records": records, "columns": list(records[0]) if records else [],
            "target_sheet": {"name": "July WFO", "original_name": "attendance.xlsx"}, "snapshot_hash": "fixture"}


def test_hr_path_runs_without_model_or_generic_sales_context():
    deck = generate_presentation_deck_spec({}, fixture_context())
    assert deck['metadata']['content_contract'] == 'hr_attendance_v1'
    facts = {e['metric_name']: e for e in deck['evidence_ledger']}
    assert facts['Recorded office days']['numeric_value'] == 9
    assert facts['Median office days']['numeric_value'] == 4.5
    assert facts['Average office days: Design']['denominator'] == 1
    assert facts['Average office days: 1 to 5 July 2026']['numeric_value'] == 1
    assert facts['Average office days: 1 to 5 July 2026']['denominator'] == 2
    assert 'July 2026' == deck['metadata']['reporting_period_summary']
    text = str(deck['slides'])
    assert '001' in text
    assert 'double subtraction' in text
    assert 'calendar days or working days' in text
    assert 'SQL' not in text and 'cryptographic' not in text and 'ROI' not in text


def test_missing_and_duplicate_ids_withhold_employee_rollups():
    ctx = fixture_context()
    ctx['records'][1]['Emp ID'] = '001'
    ctx['records'][2]['Emp ID'] = None
    deck = build_hr_report({}, ctx)
    assert len(deck['slides']) == 3
    assert '001' in str(deck['slides'])
    assert not any(e['metric_name'] == 'Employees' for e in deck['evidence_ledger'])


def test_multi_month_source_is_not_presented_as_one_month():
    ctx = fixture_context()
    ctx['columns'].append('1st to 5th August 2026')
    deck = build_hr_report({}, ctx)
    assert 'Several reporting months' in str(deck['slides'])
    assert not any(e['metric_name'] == 'Recorded office days' for e in deck['evidence_ledger'])


def test_non_hr_data_does_not_take_attendance_path():
    assert build_hr_report({}, {'records': [{'Make': 'Ford', 'Price': 100}], 'columns': ['Make', 'Price']}) is None


def test_all_missing_attendance_never_becomes_zero():
    ctx = fixture_context()
    for row in ctx['records']:
        row['Total Attendance'] = None
    deck = build_hr_report({}, ctx)
    assert not any(e['metric_name'] in {'Recorded office days', 'Median office days'} for e in deck['evidence_ledger'])
