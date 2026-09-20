import json
import pytest
from pptx import Presentation
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import get_connection
from app.services.presentation_service import (
    THEMES,
    PresentationJobManager,
    capture_dataset_context,
    extract_presentation_charts,
    generate_presentation_deck_spec,
    regenerate_single_slide,
    execute_presentation_pipeline_async
)
from app.services.report_generator import export_spec_to_pptx


def seed_test_sales_sheet(client: TestClient | None = None) -> int:
    if client is None:
        client = TestClient(app)
    csv_lines = ["Store,Date,Weekly_Sales,Holiday_Flag"]
    for i in range(1, 101):
        store = f"Store {((i % 15) + 1)}"
        date = f"2023-{(i % 12) + 1:02d}-01"
        sales = 15000.0 + (i * 250.0)
        flag = 1 if (i % 5 == 0) else 0
        csv_lines.append(f"{store},{date},{sales},{flag}")
    csv_bytes = "\n".join(csv_lines).encode("utf-8")
    resp = client.post("/api/upload/file", files={"file": ("walmart_sales.csv", csv_bytes, "text/csv")})
    assert resp.status_code == 200
    sheets_resp = client.get("/api/sheets")
    assert sheets_resp.status_code == 200
    sheets = sheets_resp.json()["sheets"]
    return sheets[0]["id"]


def test_theme_registry():
    assert "executive_dark" in THEMES
    assert "clean_light" in THEMES
    assert "corporate_navy" in THEMES
    assert "emerald_slate" in THEMES

    for key, t in THEMES.items():
        assert "bg_color" in t
        assert "card_bg" in t
        assert "brand_color" in t
        assert "chart_palette" in t
        assert len(t["chart_palette"]) >= 5


@pytest.fixture(autouse=True)
def fast_tests(monkeypatch):
    monkeypatch.setattr("app.services.presentation_service._call_ai_presentation_enrichment", lambda **kwargs: None)


def test_capture_dataset_context_and_charts():
    sheet_id = seed_test_sales_sheet()
    with get_connection() as conn:
        ctx = capture_dataset_context(conn, sheet_id=sheet_id)

    assert ctx["target_sheet"]["id"] == sheet_id
    assert "Sales" in ctx["domain"] or "Commercial" in ctx["domain"]
    assert len(ctx["records"]) == 100
    assert ctx["snapshot_hash"] is not None

    charts = extract_presentation_charts(ctx["visuals"], ctx["domain"])
    assert len(charts) > 0

    for chart in charts:
        if chart.get("type") in ("bar", "horizontal_bar"):
            assert len(chart.get("categories", [])) <= 10


def test_deck_spec_generation_sales_domain():
    sheet_id = seed_test_sales_sheet()
    with get_connection() as conn:
        ctx = capture_dataset_context(conn, sheet_id=sheet_id)

    scope = {
        "objective": "Quarterly Sales & Store Distribution Review",
        "audience": "Executive Vice Presidents",
        "target_length": 6,
        "theme_id": "corporate_navy",
        "instructions": "Emphasize store performance rankings."
    }

    spec = generate_presentation_deck_spec(scope, ctx)

    assert spec["spec_version"] == "2.0"
    assert spec["theme"]["id"] == "corporate_navy"
    assert spec["metadata"]["domain"] == ctx["domain"]
    assert len(spec["slides"]) >= 5

    layouts = [s["layout"] for s in spec["slides"]]
    assert "title_hero" in layouts
    assert "kpi_summary" in layouts
    assert "chart_narrative" in layouts
    assert "comparison_split" in layouts
    assert "table_detail" in layouts

    all_text = " ".join([
        s.get("title", "") + " " + s.get("narrative", "") + " " + " ".join(s.get("bullets", []))
        for s in spec["slides"]
    ]).lower()
    assert "burnout" not in all_text
    assert "flight risk" not in all_text

    for s in spec["slides"]:
        assert len(s.get("speaker_notes", "")) > 10
        assert len(s.get("evidence_sources", [])) > 0


def test_export_spec_to_pptx_with_native_charts():
    sheet_id = seed_test_sales_sheet()
    with get_connection() as conn:
        ctx = capture_dataset_context(conn, sheet_id=sheet_id)

    spec = generate_presentation_deck_spec({
        "objective": "Store Throughput Review",
        "theme_id": "emerald_slate"
    }, ctx)

    pptx_path = export_spec_to_pptx(spec)
    assert pptx_path.exists()
    assert pptx_path.stat().st_size > 10000

    prs = Presentation(str(pptx_path))
    assert abs(prs.slide_width.inches - 13.333) < 0.01
    assert abs(prs.slide_height.inches - 7.5) < 0.01
    assert len(prs.slides) == len(spec["slides"])

    has_at_least_one_chart = False
    for slide in prs.slides:
        if slide.has_notes_slide:
            assert len(slide.notes_slide.notes_text_frame.text) > 0
        chart_count = sum(1 for s in slide.shapes if s.has_chart)
        if chart_count > 0:
            has_at_least_one_chart = True
            for s in slide.shapes:
                if s.has_chart:
                    assert len(s.chart.series) > 0

    assert has_at_least_one_chart is True


def test_regenerate_single_slide():
    sheet_id = seed_test_sales_sheet()
    with get_connection() as conn:
        ctx = capture_dataset_context(conn, sheet_id=sheet_id)

    spec = generate_presentation_deck_spec({"objective": "General Overview"}, ctx)
    target_slide = spec["slides"][1]
    slide_id = target_slide["id"]

    prompt = "Focus sharply on holiday promotional uplift and inventory prep."
    updated_deck = regenerate_single_slide(spec, slide_id, prompt)

    updated_slide = next(s for s in updated_deck["slides"] if s["id"] == slide_id)
    assert len(updated_slide["bullets"]) >= 2
    assert prompt.lower() in updated_slide["speaker_notes"].lower() or len(updated_slide["speaker_notes"]) > 10


def test_presentation_job_manager_cancellation():
    manager = PresentationJobManager()
    job_id = manager.create_job({"objective": "Test Job"})

    job = manager.get_job(job_id)
    assert job["status"] in ("in_progress", "pending")
    assert job["stage"] in ("collecting_findings", "queued")

    manager.update_stage(job_id, "planning_outline", "Structuring presentation slides", 35)
    job = manager.get_job(job_id)
    assert job["stage"] == "planning_outline"
    assert job["progress_pct"] == 35

    assert manager.is_cancelled(job_id) is False
    manager.cancel_job(job_id)
    assert manager.is_cancelled(job_id) is True

    job = manager.get_job(job_id)
    assert job["status"] == "cancelled"


def test_presentations_api_endpoints():
    client = TestClient(app)
    sheet_id = seed_test_sales_sheet(client)

    # 1. Themes
    res = client.get("/api/presentations/themes")
    assert res.status_code == 200
    themes = res.json()["themes"]
    assert len(themes) == 4

    # 2. Start generation job
    res = client.post("/api/presentations/generate", json={
        "objective": "API Integration Test",
        "theme_id": "clean_light",
        "sheet_id": sheet_id
    })
    assert res.status_code == 200
    job_id = res.json()["job_id"]
    assert job_id is not None

    # 3. Poll job
    res = client.get(f"/api/presentations/jobs/{job_id}")
    assert res.status_code == 200
    assert "stage" in res.json()

    # 4. Cancel job
    res = client.post(f"/api/presentations/jobs/{job_id}/cancel")
    assert res.status_code == 200
    assert res.json()["status"] == "cancelled"


def test_ready_job_attaches_deck():
    client = TestClient(app)
    sheet_id = seed_test_sales_sheet(client)
    with get_connection() as conn:
        ctx = capture_dataset_context(conn, sheet_id=sheet_id)
    spec = generate_presentation_deck_spec({"objective": "Test Ready Deck"}, ctx)
    deck_id = spec["id"]
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO presentation_decks (id, title, dataset_id, sheet_id, theme_id, spec_json, pptx_filename, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
            (deck_id, spec["metadata"]["title"], None, sheet_id, spec["metadata"]["theme_id"], json.dumps(spec), "test.pptx")
        )
        conn.commit()

    from app.routers.presentations import job_manager as router_job_mgr
    job_id = router_job_mgr.create_job({"objective": "Test Ready Deck"})
    router_job_mgr.update_stage(job_id, "ready", "Presentation ready to review", 100, deck_id=deck_id)

    res = client.get(f"/api/presentations/jobs/{job_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert "deck" in data
    assert data["deck"]["id"] == deck_id
    assert len(data["deck"]["slides"]) >= 4

