from copy import deepcopy

import pytest

from app.services.presentation.visual_binding import bind_chart
from app.services.presentation.visual.visual_intelligence import VisualIntelligenceEngine

pytestmark = pytest.mark.presentation


def assets():
    fact = {'evidence_id': 'office-days', 'metric_name': 'Average office days: Design', 'numeric_value': 3,
            'unit': 'days', 'date_range': 'July 2026'}
    chart = {'metric_name': 'Average office days', 'evidence_ids': ['office-days'], 'unit': 'days', 'period': 'July 2026',
             'categories': ['Design'], 'series': [{'name': 'Office days', 'values': [3]}]}
    return fact, chart


def test_bound_measure_is_kept():
    fact, chart = assets()
    assert bind_chart(chart, ['office-days'], [fact]) == chart


@pytest.mark.parametrize('field,value', [('unit', '%'), ('period', 'June 2026'), ('metric_name', 'Margin'), ('evidence_ids', ['other'])])
def test_mismatched_unit_period_subject_or_evidence_is_not_bound(field, value):
    fact, chart = assets()
    chart[field] = value
    assert bind_chart(chart, ['office-days'], [fact]) is None


def test_layout_request_does_not_invent_milestones():
    spec = VisualIntelligenceEngine().process_slide({'title': 'Next steps', 'layout': 'action_plan', 'bullets': ['Confirm policy']})
    assert spec.diagram_spec is None
    assert spec.matrix_spec is None
