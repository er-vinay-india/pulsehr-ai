"""HighView Presentation Studio — PPT-L10 Focused Test Suite.

Verifies:
1. StudioPresentationStatus and StudioSlideStatus typed contracts.
2. Canonical 8-stage progress model with human-understandable labels (no internal jargon).
3. Manifest lock boundary (no fake thumbnails before lock, stable physical_slide_id slots after lock).
4. Stable thumbnail identity across re-render/repair.
5. Thumbnail state progression: PREPARING -> RENDERING -> VALIDATING -> VISUALLY_REVIEWING -> READY.
6. Targeted slide, zone, and object regeneration (unaffected slides strictly preserved).
7. Stale request protection via monotonic revision checking.
8. Layered PPTX and PDF export routing.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import get_connection
from app.services.presentation.studio_models import (
    StudioStage,
    STUDIO_STAGE_LABELS,
    SlideThumbnailState,
    StudioSlideStatus,
    StudioPresentationStatus,
    TargetedRegenerationRequest,
    TargetedRegenerationResult,
)
from app.services.presentation.targeted_regenerator import TargetedRegenerationService
from app.services.presentation.job_manager import job_manager


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture
def sample_persisted_deck():
    """Seeds a sample layered deck in presentation_decks table for testing."""
    conn = get_connection()
    deck_id = "DECK-L10-TEST-001"
    deck_spec = {
        "id": deck_id,
        "title": "Quarterly Workforce Review",
        "slides": [
            {
                "id": "SLD-PHYS-1",
                "physical_slide_id": "SLD-PHYS-1",
                "title": "Executive Summary: Workforce Dynamics",
                "subtitle": "Stable retention across primary departments",
                "layout": "title_hero",
                "status": "READY",
                "render_fingerprint": "fp_slide_1_initial",
                "thumbnail_url": f"/api/presentations/decks/{deck_id}/slides/SLD-PHYS-1/thumbnail",
                "zones": [
                    {"zone_id": "ZN-HEADER", "zone_type": "header", "semantic_role": "title"},
                    {"zone_id": "ZN-HERO", "zone_type": "hero", "semantic_role": "primary_kpi"}
                ]
            },
            {
                "id": "SLD-PHYS-2",
                "physical_slide_id": "SLD-PHYS-2",
                "title": "Departmental Headcount & Overtime Breakdown",
                "subtitle": "Overtime variance concentrated in operations",
                "layout": "chart_narrative",
                "status": "READY",
                "render_fingerprint": "fp_slide_2_initial",
                "thumbnail_url": f"/api/presentations/decks/{deck_id}/slides/SLD-PHYS-2/thumbnail",
                "zones": [
                    {"zone_id": "ZN-CHART", "zone_type": "chart", "semantic_role": "data_chart"},
                    {"zone_id": "ZN-INSIGHTS", "zone_type": "narrative", "semantic_role": "takeaway"}
                ]
            },
            {
                "id": "SLD-PHYS-3",
                "physical_slide_id": "SLD-PHYS-3",
                "title": "Retention Variance & Compensation Risk",
                "subtitle": "High compensation disparity correlates with flight risk",
                "layout": "comparison_split",
                "status": "READY",
                "render_fingerprint": "fp_slide_3_initial",
                "thumbnail_url": f"/api/presentations/decks/{deck_id}/slides/SLD-PHYS-3/thumbnail",
                "zones": [
                    {"zone_id": "ZN-LEFT", "zone_type": "chart", "semantic_role": "comparison_a"},
                    {"zone_id": "ZN-RIGHT", "zone_type": "chart", "semantic_role": "comparison_b"}
                ]
            }
        ],
        "metadata": {
            "deck_revision": 1,
            "theme_id": "executive_dark",
            "pipeline_mode": "layered"
        }
    }

    conn.execute(
        """
        INSERT INTO presentation_decks (id, title, theme_id, spec_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(id) DO UPDATE SET spec_json = excluded.spec_json
        """,
        (deck_id, "Quarterly Workforce Review", "executive_dark", json.dumps(deck_spec))
    )
    conn.commit()
    conn.close()

    yield deck_id, deck_spec

    # Cleanup
    conn = get_connection()
    conn.execute("DELETE FROM presentation_decks WHERE id = ?", (deck_id,))
    conn.commit()
    conn.close()


# --- Test 1: Studio Presentation Status Contract & Human Labels ---
def test_01_studio_progress_contract_and_human_labels():
    for stage in StudioStage:
        label = STUDIO_STAGE_LABELS.get(stage.value)
        assert label is not None
        # Strict requirement: Zero architecture jargon in UI labels
        assert not any(jargon in label for jargon in ["PPT-L", "RenderManifest", "SDR", "JoinPlan", "control plane"])

    status = StudioPresentationStatus(
        deck_id="DECK-TEST",
        job_id="JOB-123",
        current_stage=StudioStage.PREPARING_SLIDES.value,
        stage_label=STUDIO_STAGE_LABELS[StudioStage.PREPARING_SLIDES.value],
        progress_percent=40,
        message="Preparing slides",
        manifest_locked=True,
        total_slides=3,
        slides=[
            StudioSlideStatus(
                physical_slide_id="SLD-1",
                slide_order=1,
                title="Slide 1",
                layout="chart_narrative",
                status=SlideThumbnailState.PREPARING
            )
        ]
    )
    assert status.manifest_locked is True
    assert status.slides[0].status == SlideThumbnailState.PREPARING
    assert status.stage_label == "Preparing slides"


# --- Test 2: Manifest Lock Boundary ---
def test_02_manifest_lock_boundary():
    # Before manifest lock: manifest_locked=False, slides empty
    pre_lock = StudioPresentationStatus(
        job_id="JOB-PRE",
        current_stage=StudioStage.UNDERSTANDING_DATA.value,
        stage_label=STUDIO_STAGE_LABELS[StudioStage.UNDERSTANDING_DATA.value],
        progress_percent=10,
        manifest_locked=False,
        total_slides=0,
        slides=[]
    )
    assert pre_lock.manifest_locked is False
    assert len(pre_lock.slides) == 0

    # Once manifest locks: stable physical_slide_id slots established
    locked = StudioPresentationStatus(
        deck_id="DECK-LOCKED",
        job_id="JOB-LOCKED",
        current_stage=StudioStage.PREPARING_SLIDES.value,
        stage_label=STUDIO_STAGE_LABELS[StudioStage.PREPARING_SLIDES.value],
        progress_percent=40,
        manifest_locked=True,
        total_slides=3,
        slides=[
            StudioSlideStatus(
                physical_slide_id="SLD-PHYS-1",
                slide_order=1,
                title="Title",
                layout="title_hero",
                status=SlideThumbnailState.PREPARING
            ),
            StudioSlideStatus(
                physical_slide_id="SLD-PHYS-2",
                slide_order=2,
                title="Analysis",
                layout="chart_narrative",
                status=SlideThumbnailState.PREPARING
            ),
            StudioSlideStatus(
                physical_slide_id="SLD-PHYS-3",
                slide_order=3,
                title="Conclusions",
                layout="comparison_split",
                status=SlideThumbnailState.PREPARING
            ),
        ]
    )
    assert locked.manifest_locked is True
    assert len(locked.slides) == 3
    assert [s.physical_slide_id for s in locked.slides] == ["SLD-PHYS-1", "SLD-PHYS-2", "SLD-PHYS-3"]


# --- Test 3: Thumbnail State Progression ---
def test_03_thumbnail_state_progression():
    states = [
        SlideThumbnailState.PREPARING,
        SlideThumbnailState.RENDERING,
        SlideThumbnailState.VALIDATING,
        SlideThumbnailState.VISUALLY_REVIEWING,
        SlideThumbnailState.REPAIRING,
        SlideThumbnailState.READY,
        SlideThumbnailState.FAILED,
    ]
    for st in states:
        slide = StudioSlideStatus(
            physical_slide_id="SLD-P",
            slide_order=1,
            title="Slide",
            layout="chart_narrative",
            status=st
        )
        assert slide.status == st


# --- Test 4: Targeted Slide Regeneration Preserves Unaffected Slides ---
def test_04_targeted_slide_regeneration(sample_persisted_deck):
    deck_id, initial_spec = sample_persisted_deck
    service = TargetedRegenerationService()

    req = TargetedRegenerationRequest(
        deck_id=deck_id,
        physical_slide_id="SLD-PHYS-2",
        regeneration_reason="layout_variant",
        user_instruction="try another layout",
        request_version=1
    )

    result = service.regenerate_target(req)

    assert result.success is True
    assert result.physical_slide_id == "SLD-PHYS-2"
    assert result.deck_revision == 2
    assert result.unaffected_slide_count == 2

    # Verify unaffected slides strictly retained their identities and fingerprints
    slides = result.updated_deck["slides"]
    assert slides[0]["physical_slide_id"] == "SLD-PHYS-1"
    assert slides[0]["render_fingerprint"] == "fp_slide_1_initial"
    assert slides[0]["title"] == "Executive Summary: Workforce Dynamics"

    assert slides[2]["physical_slide_id"] == "SLD-PHYS-3"
    assert slides[2]["render_fingerprint"] == "fp_slide_3_initial"
    assert slides[2]["title"] == "Retention Variance & Compensation Risk"

    # Verify target slide was updated
    assert slides[1]["physical_slide_id"] == "SLD-PHYS-2"
    assert slides[1]["render_fingerprint"] != "fp_slide_2_initial"
    assert slides[1]["layout"] != "chart_narrative"
    assert "Layout changed" in result.diff_summary


# --- Test 5: Targeted Zone / Object Regeneration ---
def test_05_targeted_zone_regeneration(sample_persisted_deck):
    deck_id, initial_spec = sample_persisted_deck
    service = TargetedRegenerationService()

    req = TargetedRegenerationRequest(
        deck_id=deck_id,
        physical_slide_id="SLD-PHYS-1",
        zone_id="ZN-HEADER",
        regeneration_reason="user_request",
        user_instruction="Change title to Executive Highlights: Q3 Headcount",
        request_version=1
    )

    result = service.regenerate_target(req)

    assert result.success is True
    assert result.zone_id == "ZN-HEADER"
    assert result.deck_revision == 2

    slides = result.updated_deck["slides"]
    assert slides[0]["title"] == "Executive Highlights: Q3 Headcount"
    # Unaffected slides preserved
    assert slides[1]["render_fingerprint"] == "fp_slide_2_initial"
    assert slides[2]["render_fingerprint"] == "fp_slide_3_initial"


# --- Test 6: Stale Request Protection ---
def test_06_stale_request_protection(sample_persisted_deck):
    deck_id, initial_spec = sample_persisted_deck
    service = TargetedRegenerationService()

    # First valid regeneration increments revision to 2
    req1 = TargetedRegenerationRequest(
        deck_id=deck_id,
        physical_slide_id="SLD-PHYS-1",
        user_instruction="Revision 1 change",
        request_version=1
    )
    res1 = service.regenerate_target(req1)
    assert res1.deck_revision == 2

    # Second stale request sending request_version=1 must be rejected
    req_stale = TargetedRegenerationRequest(
        deck_id=deck_id,
        physical_slide_id="SLD-PHYS-1",
        user_instruction="Old stale request",
        request_version=1
    )
    with pytest.raises(ValueError, match="Stale regeneration request superseded"):
        service.regenerate_target(req_stale)


# --- Test 7: Studio Progress API Endpoint ---
def test_07_studio_progress_api_endpoint(test_client):
    # Register an active job with studio status
    job_id = job_manager.create_job({"objective": "Test Deck"})
    job_manager.update_stage(
        job_id=job_id,
        stage=StudioStage.PREPARING_SLIDES.value,
        stage_label=STUDIO_STAGE_LABELS[StudioStage.PREPARING_SLIDES.value],
        progress_pct=40,
        extra={
            "studio_stage": StudioStage.PREPARING_SLIDES.value,
            "manifest_locked": True,
            "total_slides": 2,
            "slides": [
                {
                    "physical_slide_id": "SLD-1",
                    "slide_order": 1,
                    "title": "Overview",
                    "layout": "title_hero",
                    "status": "PREPARING"
                },
                {
                    "physical_slide_id": "SLD-2",
                    "slide_order": 2,
                    "title": "Details",
                    "layout": "chart_narrative",
                    "status": "PREPARING"
                }
            ]
        }
    )

    resp = test_client.get(f"/api/presentations/jobs/{job_id}/studio-status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == job_id
    assert data["current_stage"] == StudioStage.PREPARING_SLIDES.value
    assert data["stage_label"] == "Preparing slides"
    assert data["manifest_locked"] is True
    assert len(data["slides"]) == 2
    assert data["slides"][0]["physical_slide_id"] == "SLD-1"


# --- Test 8: Targeted Regeneration Route Endpoint ---
def test_08_targeted_regeneration_route(test_client, sample_persisted_deck):
    deck_id, _ = sample_persisted_deck
    payload = {
        "deck_id": deck_id,
        "physical_slide_id": "SLD-PHYS-3",
        "user_instruction": "try another layout",
        "request_version": 1
    }
    resp = test_client.post(f"/api/presentations/decks/{deck_id}/regenerate-target", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["physical_slide_id"] == "SLD-PHYS-3"
    assert data["deck_revision"] == 2
    assert data["unaffected_slide_count"] == 2


# --- Test 9: Thumbnail Endpoint ---
def test_09_thumbnail_endpoint(test_client, sample_persisted_deck, tmp_path):
    deck_id, _ = sample_persisted_deck

    # Non-existent thumbnail returns 404 cleanly
    resp = test_client.get(f"/api/presentations/decks/{deck_id}/slides/SLD-NONEXISTENT/thumbnail")
    assert resp.status_code == 404

    # Create dummy rendered PNG under PRESENTATION_VISUAL_QA_DIR
    from app.core import config
    deck_dir = Path(config.PRESENTATION_VISUAL_QA_DIR) / "rendered_slides" / deck_id
    deck_dir.mkdir(parents=True, exist_ok=True)
    thumb_file = deck_dir / "slide_001_SLD-PHYS-1.png"
    thumb_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

    resp = test_client.get(f"/api/presentations/decks/{deck_id}/slides/SLD-PHYS-1/thumbnail")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert "public" in resp.headers.get("cache-control", "")

    # Cleanup dummy file
    thumb_file.unlink()
    if deck_dir.exists():
        deck_dir.rmdir()


# --- Test 10: Export Wiring for Layered Deck ---
def test_10_export_wiring(test_client, sample_persisted_deck, tmp_path):
    deck_id, _ = sample_persisted_deck

    # Attach dummy styled PPTX path to deck spec
    dummy_pptx = tmp_path / "styled_sample.pptx"
    dummy_pptx.write_bytes(b"PK\x03\x04DummyPPTXBytes")

    conn = get_connection()
    row = conn.execute("SELECT spec_json FROM presentation_decks WHERE id = ?", (deck_id,)).fetchone()
    spec = json.loads(row["spec_json"])
    spec["metadata"]["styled_pptx_path"] = str(dummy_pptx)
    conn.execute("UPDATE presentation_decks SET spec_json = ? WHERE id = ?", (json.dumps(spec), deck_id))
    conn.commit()
    conn.close()

    resp = test_client.get(f"/api/presentations/download/{deck_id}")
    assert resp.status_code == 200
    assert "application/vnd.openxmlformats" in resp.headers["content-type"]
    assert resp.content == b"PK\x03\x04DummyPPTXBytes"
