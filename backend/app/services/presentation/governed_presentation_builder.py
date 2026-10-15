"""Governed Presentation Builder (Product Track 3.2).

Assembles boardroom presentation deck specifications strictly from upstream
governed ExecutiveTopics and VisualSpecs via PresentationTopics.

Enforces Track 3.2 Invariants:
1. One governed ExecutiveTopic maps to one presentation topic identity,
   which may render as one or more physical slides without changing fact/evidence ownership.
2. NO raw-column reinterpretation.
3. NO build_hr_report analytical bypass.
4. NO build_grounded_review analytical fallback.
5. NO new metric calculation.
6. NO loss of topic_id / fact_id / evidence_ids.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Callable

from .builders.common import THEMES
from .content_validation import seal_business_content
from .topic_contract import PresentationTopic

logger = logging.getLogger(__name__)


def build_governed_presentation_deck(
    scope: dict[str, Any],
    dataset_context: dict[str, Any],
    workspace_evidence: dict[str, Any] | None = None,
    presentation_topics: list[PresentationTopic] | None = None,
    on_slide_start: Callable[..., Any] | None = None,
    on_slide_progress: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Generates a complete boardroom presentation deck grounded strictly in governed PresentationTopics."""
    topics = presentation_topics or []
    if not topics and dataset_context.get("presentation_topics"):
        topics = dataset_context["presentation_topics"]
    if not topics and workspace_evidence and workspace_evidence.get("presentation_topics"):
        topics = workspace_evidence["presentation_topics"]

    # If still no PresentationTopics, attempt to resolve them from upstream executive_topics
    if not topics:
        raw_exec = (
            dataset_context.get("executive_topics")
            or (workspace_evidence and workspace_evidence.get("executive_topics"))
            or []
        )
        domain = dataset_context.get("domain", "general")
        sheet_name = (dataset_context.get("target_sheet") or {}).get("name") or ""
        topics = [
            PresentationTopic.from_executive_topic(t, domain=domain, source_sheet_name=sheet_name)
            for t in raw_exec
        ]

    # Target metadata
    target_sheet = dataset_context.get("target_sheet") or {}
    domain = dataset_context.get("domain") or "general"
    snapshot_hash = dataset_context.get("snapshot_hash") or "000000000000"
    file_label = target_sheet.get("original_name") or target_sheet.get("name") or f"{domain.title()} Dataset"
    theme_id = scope.get("theme_id") or "executive_dark"

    deck_id = f"deck_{uuid.uuid4().hex[:12]}"
    deck_title = f"{domain.title()} Executive Performance Review"
    deck_subtitle = f"Governed Boardroom Strategic Diagnostic · Snapshot {snapshot_hash}"

    # Build Cover / Executive Briefing Slide (Slide 1)
    slides: list[dict[str, Any]] = []

    # Slide 1: Executive Title Cover / Briefing
    cover_bullets = [
        f"Audited review covering {len(topics)} governed business questions across verified operations.",
        f"Grounded directly in snapshot {snapshot_hash}; zero raw-column interpolation."
    ]
    if topics and topics[0].primary_takeaway:
        cover_bullets.append(f"Primary Finding: {topics[0].primary_takeaway}")

    cover_slide: dict[str, Any] = {
        "id": "slide_1",
        "stable_slide_id": "slide_title_cover",
        "order": 1,
        "total_slides": len(topics) + 1,
        "category": f"{domain.upper()[:22]} · EXECUTIVE BRIEFING",
        "layout": "title_hero",
        "title": deck_title,
        "subtitle": deck_subtitle,
        "narrative": f"Governed executive briefing synthesized across {len(topics)} strategic analytical topics.",
        "bullets": cover_bullets,
        "narration_script": f"Welcome to the {domain} Executive Performance Review. This briefing presents {len(topics)} governed topics grounded directly in verified dataset records.",
        "speaker_takeaway": f"Complete strategic diagnostic covering {len(topics)} governed topics.",
        "speaker_notes": f"Presenter Briefing:\n- Dataset: {file_label}\n- Topics Evaluated: {len(topics)}\n- Snapshot Hash: {snapshot_hash}",
        "notes": f"Dataset: {file_label}, Snapshot: {snapshot_hash}",
        "reading_order": ["category", "title", "subtitle", "narrative", "bullets", "footer"],
        "metrics": [
            {
                "label": "Governed Topics",
                "value": str(len(topics)),
                "unit": "topics",
                "subtext": "Complete Coverage",
                "evidence_id": "EVID-EXEC-01"
            }
        ],
        "chart": None,
        "table": None,
        "topic_id": "TOPIC-BRIEFING-00",
        "fact_id": "FACT-BRIEFING-PORTFOLIO",
        "evidence_ids": [t.evidence_ids[0] for t in topics if t.evidence_ids][:4],
        "key_metric": f"{len(topics)} Topics",
        "unit": "topics",
        "leader": None,
        "leader_value": None,
        "ranking_direction": None,
        "reference_line": None,
        "analytical_intent": "EXECUTIVE_SYNTHESIS",
        "visual_spec": {},
        "inspect_payload": {}
    }
    slides.append(cover_slide)

    # Slides 2 to N+1: Governed PresentationTopics
    enable_pagination = scope.get("enable_table_pagination", False)
    max_items = int(scope.get("max_items_per_slide", 10))
    current_order = 2
    for p_topic in topics:
        # Invariant: One governed ExecutiveTopic maps to one presentation topic identity,
        # which may render as one or more physical slides without changing fact/evidence ownership.
        topic_slides = p_topic.to_slide_contracts(
            start_order=current_order,
            total_slides=len(topics) + 1,
            max_items_per_slide=max_items,
            enable_pagination=enable_pagination
        )
        slides.extend(topic_slides)
        current_order += len(topic_slides)

    # Recalculate total_slides and order across all materialized physical slides
    actual_total = len(slides)
    for idx, s in enumerate(slides, start=1):
        s["order"] = idx
        s["total_slides"] = actual_total


    # Fire callbacks
    for s in slides:
        s_order = s["order"]
        s_title = s["title"]
        s_cat = s.get("category", "Analysis")
        if callable(on_slide_start):
            try:
                on_slide_start(s_order, actual_total, s_title, s_cat)
            except Exception:
                pass
        if callable(on_slide_progress):
            try:
                on_slide_progress(s_order, actual_total, s_title, s_cat, slide_dict=s)
            except Exception:
                pass

    # Build unified evidence ledger from topics
    evidence_ledger: list[dict[str, Any]] = []
    seen_ev = set()
    for t in topics:
        for eid in t.evidence_ids:
            if eid not in seen_ev:
                seen_ev.add(eid)
                evidence_ledger.append({
                    "evidence_id": eid,
                    "title": t.title,
                    "finding_type": "measured_fact",
                    "metric_name": t.metric or t.title,
                    "metric_value": t.metric,
                    "unit": t.unit,
                    "analytical_intent": t.analytical_intent,
                    "what_it_establishes": t.primary_takeaway,
                    "recommended_action": t.recommended_action
                })

    deck_dict = {
        "id": deck_id,
        "spec_version": "2.0",
        "title": deck_title,
        "subtitle": deck_subtitle,
        "domain": domain,
        "theme": THEMES.get(theme_id, THEMES.get("executive_dark", {})),
        "slides": slides,
        "slide_count": actual_total,
        "evidence_ledger": evidence_ledger,
        "presentation_topics": [t.model_dump() for t in topics],
        "coverage_manifest": {"items": [{"evidence_id": e["evidence_id"], "title": e["title"], "disposition": "main_deck"} for e in evidence_ledger]},
        "metadata": {
            "title": deck_title,
            "source": file_label,
            "theme_id": theme_id,
            "domain": domain,
            "data_snapshot_hash": snapshot_hash,
            "governed_synthesis": True,
            "topics_count": len(topics),
            "physical_slides_count": actual_total,
            "contract_mode": "EXECUTIVE_TOPIC_BOUND",
            "content_contract": "executive_topic_bound_v1"
        }
    }
    return seal_business_content(deck_dict)
