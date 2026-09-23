"""Tests for the Copilot streaming SSE endpoint and latency optimizations."""

import json
from fastapi.testclient import TestClient
from app.main import app
from app.services import ai_copilot

client = TestClient(app)


def test_copilot_stream_deterministic_calculation():
    """Verify that deterministic tools return immediate done events via stream."""
    response = client.post(
        "/api/copilot/query/stream",
        json={"query": "Calculate (12 + 8) / 4"}
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    
    events = [line for line in response.text.split("\n\n") if line.strip()]
    assert len(events) >= 1
    
    done_event = [e for e in events if "event: done" in e]
    assert len(done_event) == 1
    
    # Extract data payload
    data_line = [l for l in done_event[0].split("\n") if l.startswith("data: ")][0]
    payload = json.loads(data_line[6:])
    assert "5" in payload["answer"]
    assert payload.get("timings", {}).get("is_deterministic") is True


def test_copilot_stream_llm_generation(monkeypatch):
    """Verify that general LLM queries stream status events and token chunks."""
    monkeypatch.setattr(ai_copilot, 'hybrid_search', lambda *args, **kwargs: [])
    monkeypatch.setattr(ai_copilot, 'get_aggregate_context', lambda *args, **kwargs: 'Verified test context')
    
    class FakeStreamResponse:
        status_code = 200
        def raise_for_status(self): pass
        def iter_lines(self):
            tokens = ["The ", "attendance ", "average ", "is ", "92%."]
            for t in tokens:
                yield json.dumps({"response": t}).encode("utf-8")
        def __enter__(self): return self
        def __exit__(self, *args): pass

    class FakeClient:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def stream(self, method, url, **kwargs):
            return FakeStreamResponse()

    monkeypatch.setattr(ai_copilot.httpx, 'Client', FakeClient)

    response = client.post(
        "/api/copilot/query/stream",
        json={"query": "Summarize attendance across teams"}
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    
    events = [line for line in response.text.split("\n\n") if line.strip()]
    # Check status events
    status_events = [e for e in events if "event: status" in e]
    assert len(status_events) >= 2
    
    # Check token events
    token_events = [e for e in events if "event: token" in e]
    assert len(token_events) == 5
    
    # Check final done event
    done_events = [e for e in events if "event: done" in e]
    assert len(done_events) == 1
    data_line = [l for l in done_events[0].split("\n") if l.startswith("data: ")][0]
    done_payload = json.loads(data_line[6:])
    assert done_payload["answer"] == "The attendance average is 92%."
    assert "timings" in done_payload
