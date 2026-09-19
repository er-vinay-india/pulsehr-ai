"""Unit tests for Industrial People Analytics formulas and ingestion pipeline."""

import json
import pytest
from app.db.database import get_connection
from app.services.industrial_analytics import (
    calculate_bradford_factor,
    calculate_9box_matrix,
    calculate_burnout_strain_index,
    calculate_cross_sheet_elasticity,
    run_ingestion_industrial_pipeline,
)
from app.services.visual_intelligence import get_sheet_raw_projections


def test_calculate_bradford_factor():
    records = [
        {'Employee Name': 'Alice', 'Department': 'Tech', 'Absent ( no of days )': 0},
        {'Employee Name': 'Bob', 'Department': 'Tech', 'Absent ( no of days )': 1},
        {'Employee Name': 'Charlie', 'Department': 'Sales', 'Absent ( no of days )': 3},
        {'Employee Name': 'Diana', 'Department': 'Sales', 'Absent ( no of days )': 8},
    ]
    res = calculate_bradford_factor(records)
    assert res['available'] is True
    assert res['total_employees_reviewed'] == 4
    assert res['organizational_avg_bradford'] > 0
    assert len(res['departments']) == 2
    assert len(res['employees']) == 4

    # Alice should have B = 0
    alice = next(e for e in res['employees'] if e['name'] == 'Alice')
    assert alice['bradford_score'] == 0
    assert alice['tier'] == 'Normal'

    # Diana should have B = 4^2 * 8 = 128
    diana = next(e for e in res['employees'] if e['name'] == 'Diana')
    assert diana['bradford_score'] == 128.0
    assert diana['tier'] == 'Moderate Disruption'

    assert 'Bradford Disruption Analysis' in res['ai_insight']


def test_calculate_9box_matrix():
    records = [
        {'Employee Name': 'Alice', 'Department': 'Engineering', 'Performance Score': 9.2, 'Risk Level': 'Low'},
        {'Employee Name': 'Bob', 'Department': 'Engineering', 'Performance Score': 8.8, 'Risk Level': 'High'},
        {'Employee Name': 'Charlie', 'Department': 'Sales', 'Performance Score': 7.8, 'Risk Level': 'Medium'},
        {'Employee Name': 'David', 'Department': 'Sales', 'Performance Score': 6.0, 'Risk Level': 'High'},
    ]
    res = calculate_9box_matrix(records)
    assert res['available'] is True
    assert res['total_evaluated'] == 4
    assert len(res['cells']) == 9

    # Check At-Risk Star (High Perf + High Risk)
    at_risk_cell = next(c for c in res['cells'] if c['id'] == 'at_risk_stars')
    assert len(at_risk_cell['roster']) == 1
    assert at_risk_cell['roster'][0]['name'] == 'Bob'

    # Check Underperformer (Low Perf + High Risk)
    underperf_cell = next(c for c in res['cells'] if c['id'] == 'underperformers')
    assert len(underperf_cell['roster']) == 1
    assert underperf_cell['roster'][0]['name'] == 'David'

    assert '9-Box Talent Diagnostic' in res['ai_insight']


def test_calculate_burnout_strain_index():
    df_perf = [
        {'Department': 'Engineering', 'Overtime Hours': 30.0},
        {'Department': 'Engineering', 'Overtime Hours': 25.0},
        {'Department': 'Operations', 'Overtime Hours': 5.0},
    ]
    import pandas as pd
    res = calculate_burnout_strain_index(pd.DataFrame(df_perf))
    assert res['available'] is True
    assert len(res['departments']) == 2
    top_dept = res['departments'][0]
    assert top_dept['department'] == 'Engineering'
    assert top_dept['strain_index_pct'] > 10.0


def test_calculate_cross_sheet_elasticity():
    import pandas as pd
    df_p = pd.DataFrame([
        {'Employee ID': 'E1', 'Performance Score': 95.0},
        {'Employee ID': 'E2', 'Performance Score': 90.0},
        {'Employee ID': 'E3', 'Performance Score': 80.0},
        {'Employee ID': 'E4', 'Performance Score': 70.0},
    ])
    df_a = pd.DataFrame([
        {'Employee ID': 'E1', 'Absent ( no of days )': 1},
        {'Employee ID': 'E2', 'Absent ( no of days )': 2},
        {'Employee ID': 'E3', 'Absent ( no of days )': 5},
        {'Employee ID': 'E4', 'Absent ( no of days )': 8},
    ])
    res = calculate_cross_sheet_elasticity(df_p, df_a)
    assert res['available'] is True
    assert res['matched_records'] == 4
    assert res['beta_coefficient'] < 0  # negative impact
    assert 0 <= res['r_squared'] <= 1.0
    assert 'Cross-Sheet Elasticity' in res['ai_insight']
