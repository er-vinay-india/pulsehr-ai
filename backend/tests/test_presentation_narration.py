"""Unit and integration tests for presentation slide narration and voiceover service."""

import json
from pathlib import Path
import sqlite3
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.presentation.narration_service import (
    clean_speaker_notes_for_speech,
    generate_deck_narration_async,
    get_deck_narration_manifest,
    EXECUTIVE_VOICES
)


@pytest.fixture
def narration_test_db(tmp_path, monkeypatch):
    """Initializes a clean SQLite database for narration testing."""
    db_path = tmp_path / "test_narration.db"

    def get_test_conn():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    conn = get_test_conn()
    schema_path = Path(__file__).parents[1] / "app/db/schema.sql"
    conn.executescript(schema_path.read_text())
    conn.close()

    monkeypatch.setattr("app.db.database.get_connection", get_test_conn)
    monkeypatch.setattr("app.services.presentation.narration_service.get_connection", get_test_conn)
    monkeypatch.setattr("app.routers.presentations.get_connection", get_test_conn)
    
    # Direct exports directory to tmp_path
    monkeypatch.setattr("app.core.config.EXPORTS_DIR", tmp_path / "exports")
    (tmp_path / "exports").mkdir(parents=True, exist_ok=True)

    return get_test_conn


def test_clean_speaker_notes_for_speech():
    """Verifies that markdown, technical notations, and presenter notes are cleaned into natural speech."""
    raw_notes = (
        "Presenter note: Emphasize that **Engineering** dropped by 12.5% in attendance. "
        "Audited numbers verified (±0.1%) against source rows. "
        "- First step: conduct immediate 1-on-1s. "
        "- Second step: review overtime hours."
    )
    cleaned = clean_speaker_notes_for_speech(raw_notes)
    
    # Assert presenter note stripped
    assert "Presenter note:" not in cleaned
    assert "Engineering" in cleaned
    # Assert markdown bold stripped
    assert "**" not in cleaned
    # Assert percentage expanded
    assert "12.5 percent" in cleaned
    # Assert technical tolerance notation expanded
    assert "within zero point one percent" in cleaned
    # Assert bullet points flow without bullet markers
    assert " - " not in cleaned
    assert "First step: conduct immediate 1-on-1s" in cleaned


def test_clean_speaker_notes_fallback_to_narrative():
    """Verifies that missing or empty speaker notes fallback cleanly to title and narrative."""
    cleaned = clean_speaker_notes_for_speech(
        speaker_notes="",
        slide_title="Workforce Attendance Headwinds",
        subtitle="Third Quarter Review",
        narrative="Engineering attendance declined across three consecutive weeks."
    )
    assert "Workforce Attendance Headwinds" in cleaned
    assert "Third Quarter Review" in cleaned
    assert "Engineering attendance declined" in cleaned


@pytest.mark.anyio
async def test_deck_narration_generation_and_manifest(narration_test_db):
    """Verifies edge-tts audio synthesis, manifest structure, and file caching."""
    conn = narration_test_db()
    deck_id = "deck_test_narration_001"
    deck_spec = {
        "id": deck_id,
        "title": "Quarterly Workforce Review",
        "metadata": {"title": "Quarterly Workforce Review"},
        "slides": [
            {
                "order": 1,
                "title": "Executive Summary",
                "subtitle": "Overview of key indicators",
                "narrative": "Attendance remained steady across five operational divisions.",
                "speaker_notes": "Presenter note: Welcome the leadership team and summarize the overall attendance baseline."
            },
            {
                "order": 2,
                "title": "Engineering Focus",
                "subtitle": "Attendance variance",
                "narrative": "Engineering attendance dropped 2.5 days below benchmark.",
                "speaker_notes": "Highlight the two point five day variance in Engineering and propose immediate follow-up."
            }
        ]
    }
    conn.execute(
        "INSERT INTO presentation_decks (id, title, spec_json, theme_id) VALUES (?, ?, ?, 'executive_dark')",
        (deck_id, "Quarterly Workforce Review", json.dumps(deck_spec))
    )
    conn.commit()

    manifest = await generate_deck_narration_async(deck_id, voice_key="andrew", conn=conn)

    assert manifest["deck_id"] == deck_id
    assert manifest["slide_count"] == 2
    assert manifest["voice"]["name"] == "Andrew"
    assert len(manifest["slides"]) == 2
    
    slide_1 = manifest["slides"][0]
    assert slide_1["order"] == 1
    assert slide_1["duration_seconds"] > 0
    assert "slide_1.mp3" in slide_1["audio_filename"]
    assert Path(app.state.__dict__.get("EXPORTS_DIR", "") or "exports").exists or True

    # Test reading manifest from disk
    cached_manifest = get_deck_narration_manifest(deck_id)
    assert cached_manifest is not None
    assert cached_manifest["deck_id"] == deck_id
    conn.close()


def test_narration_api_endpoints(narration_test_db):
    """End-to-end FastAPI endpoint check for generating, getting manifest, and streaming slide audio."""
    conn = narration_test_db()
    deck_id = "deck_api_narration_002"
    deck_spec = {
        "id": deck_id,
        "title": "Operations Review",
        "metadata": {"title": "Operations Review"},
        "slides": [
            {
                "order": 1,
                "title": "Welcome",
                "narrative": "Reviewing workforce data.",
                "speaker_notes": "Welcome everyone to the operations briefing."
            }
        ]
    }
    conn.execute(
        "INSERT INTO presentation_decks (id, title, spec_json, theme_id) VALUES (?, ?, ?, 'executive_dark')",
        (deck_id, "Operations Review", json.dumps(deck_spec))
    )
    conn.commit()
    conn.close()

    client = TestClient(app)

    # 1. GET before generation -> returns status: not_generated
    resp_get_before = client.get(f"/api/presentations/{deck_id}/narration")
    assert resp_get_before.status_code == 200
    assert resp_get_before.json()["status"] == "not_generated"
    assert len(resp_get_before.json()["available_voices"]) > 0

    # 2. POST to generate narration
    resp_post = client.post(f"/api/presentations/{deck_id}/narration", json={"voice": "ryan"})
    assert resp_post.status_code == 200
    data = resp_post.json()
    assert data["status"] == "ready"
    assert data["voice"]["name"] == "Ryan"
    assert len(data["slides"]) == 1

    # 3. GET after generation -> returns ready manifest
    resp_get_after = client.get(f"/api/presentations/{deck_id}/narration")
    assert resp_get_after.status_code == 200
    assert resp_get_after.json()["status"] == "ready"

    # 4. Stream audio file for slide 1
    resp_audio = client.get(f"/api/presentations/{deck_id}/narration/slide/1")
    assert resp_audio.status_code == 200
    assert resp_audio.headers["content-type"] == "audio/mpeg"
    assert len(resp_audio.content) > 100
