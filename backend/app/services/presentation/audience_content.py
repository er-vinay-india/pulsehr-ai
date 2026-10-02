"""Encapsulate implementation details while retaining an internal audit trail."""
from __future__ import annotations

import re


INTERNAL = re.compile(r"\b(?:EVID[-_][\w-]+|snapshot hash|cryptographic|SQLite|SQL|ETL|model voting|council votes)\b", re.I)
TECHNICAL_SECTION = re.compile(r"evidence (?:ledger|appendix)|dataset governance|cryptographic|audit trail", re.I)


def polish_audience_content(deck: dict, include_technical_appendix: bool = False) -> dict:
    if deck.get('metadata', {}).get('deck_style') == 'decision_brief':
        return deck
    visible, hidden = [], list(deck.get('technical_appendix') or [])
    for slide in deck.get('slides', []):
        if TECHNICAL_SECTION.search(slide.get('title', '')) and not include_technical_appendix:
            hidden.append(slide)
            continue
        # Keep original generated wording for diagnostics; only business content is public.
        original = {k: slide.get(k) for k in ('title', 'narrative', 'bullets', 'speaker_notes')}
        slide.setdefault('internal_content', original)
        slide['title'] = slide.get('title', '').strip()
        for key in ('narrative', 'subtitle'):
            text = slide.get(key) or ''
            if INTERNAL.search(text):
                slide[key] = 'Review the recorded figures and the limitations before deciding next steps.'
        slide['bullets'] = [b for b in slide.get('bullets') or [] if not INTERNAL.search(str(b))]
        notes = slide.get('speaker_notes') or ''
        if INTERNAL.search(notes) or '=== PRESENTER BRIEFING' in notes:
            slide['speaker_notes'] = ' '.join([slide.get('narrative') or '', *slide.get('bullets', [])]).strip()
        slide['notes'] = slide.get('speaker_notes', '')
        slide['narration_script'] = slide.get('speaker_notes') or slide.get('narrative', '')
        # Rebuild canonical visual text after polishing, rather than exporting stale copy.
        slide.pop('visual_spec', None)
        visible.append(slide)
    deck['technical_appendix'] = hidden
    for i, slide in enumerate(visible, 1):
        slide['order'] = i
        slide['total_slides'] = len(visible)
    deck['slides'] = visible
    used = {ref for s in visible for ref in [s.get('evidence_id'), *(s.get('evidence_ids') or [])] if ref}
    for item in deck.get('coverage_manifest', {}).get('items', []):
        if item.get('evidence_id') not in used:
            item.update(disposition='internal', reason='Retained in the internal evidence record.')
    return deck
