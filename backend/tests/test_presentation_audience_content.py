from copy import deepcopy

import pytest

from app.services.presentation.audience_content import polish_audience_content
from app.services.presentation.builders.common import format_briefing

pytestmark = pytest.mark.presentation


def test_technical_appendix_is_preserved_internally():
    technical = {'title': 'Evidence Ledger & Audit Trail', 'table': {'rows': [['EVID-01', 'SQLite']]}}
    ordinary = {'title': 'Office days', 'narrative': 'Recorded office attendance is lower in Design.',
                'bullets': ['Compare leave before interpreting this difference.', 'SQL snapshot hash proves trust'],
                'speaker_notes': '=== PRESENTER BRIEFING SQL snapshot hash xyz', 'visual_spec': {'headline': 'SQL'}, 'evidence_id': 'EVID-01'}
    deck = {'metadata': {}, 'slides': [ordinary, technical], 'evidence_ledger': [{'evidence_id': 'EVID-01'}]}
    polished = polish_audience_content(deck)
    assert polished['technical_appendix'] == [technical]
    assert len(polished['slides']) == 1
    assert 'SQL' in polished['slides'][0]['internal_content']['speaker_notes']
    assert 'SQL' not in polished['slides'][0]['speaker_notes']
    assert polished['evidence_ledger'][0]['evidence_id'] == 'EVID-01'
    assert 'visual_spec' not in polished['slides'][0]


def test_decision_brief_is_immutable():
    deck = {'metadata': {'deck_style': 'decision_brief'}, 'slides': [{'title': 'Evidence Ledger', 'speaker_notes': 'SQL'}]}
    before = deepcopy(deck)
    assert polish_audience_content(deck) == before


def test_speaker_notes_explain_limits_without_audit_machinery():
    notes = format_briefing({'evidence_id': 'EVID-01', 'limitations': 'Policy not supplied', 'calculation_methodology': 'SQL'},
                           'Attendance', 'Leave and office days are separate.', '', 'Confirm the working-day calendar.', 'secret-hash')
    assert 'Policy not supplied' in notes and 'working-day calendar' in notes
    assert 'SQL' not in notes and 'EVID' not in notes and 'secret-hash' not in notes
