"""Tests for the AI Union War Room Democratic Election of Replier."""

import json
import pytest
from app.services.copilot.union_war_room import UnionWarRoomEngine, COUNCIL_DELEGATES


@pytest.fixture(autouse=True)
def mock_ollama_calls(monkeypatch):
    """Mocks all Ollama HTTP calls so unit tests run instantaneously without network or GPU latency."""
    def fake_call_ollama(model, prompt, max_tokens=150, timeout_s=12.0, temperature=0.2, system_prompt=None):
        if "STRICT DEMOCRATIC VOTING RULE" in prompt:
            # Enforce peer voting: if voter is deepseek_reasoner, vote for qwen_analyst; otherwise vote for deepseek_reasoner
            if "You are DeepSeek-R1" in prompt:
                return "VOTE_FOR: qwen_analyst\nRATIONALE: Robust empirical baselines and ground-truth metrics."
            return "VOTE_FOR: deepseek_reasoner\nRATIONALE: Rigorous deductive causality and systemic dependency analysis."
        return f"Authoritative analysis from {model} addressing the inquiry with domain-grounded operational recommendations."

    monkeypatch.setattr("app.services.copilot.union_war_room._call_ollama_completion", fake_call_ollama)


def test_war_room_council_election_structure():
    """Verify that council deliberation gathers candidate answers and democratically elects a replier."""
    result = UnionWarRoomEngine.execute_deliberation(
        user_query="How should leadership address attrition in shift schedules?",
        df=None,
        sheet_name="ShiftAttrition",
        timeout_seconds=5.0
    )

    assert "elected_replier" in result
    elected = result["elected_replier"]
    assert elected["id"] in [d.id for d in COUNCIL_DELEGATES]
    assert elected["name"] is not None
    assert elected["votes_received"] >= 1
    assert elected["total_votes"] == 5
    assert elected["vote_percentage"] > 0

    assert "candidate_answers" in result
    assert len(result["candidate_answers"]) == 5
    for cand in result["candidate_answers"]:
        assert "id" in cand
        assert "name" in cand
        assert "answer" in cand
        assert len(cand["answer"]) > 10

    assert "ballots" in result
    assert len(result["ballots"]) == 5
    for b in result["ballots"]:
        assert "voter_id" in b
        assert "voter_name" in b
        assert "voted_for_id" in b
        assert "voted_for_name" in b
        assert b["voter_id"] != b["voted_for_id"], f"Delegate {b['voter_id']} illegally voted for itself!"
        assert "rationale" in b
        assert len(b["rationale"]) > 0

    assert "vote_tally" in result
    assert result["vote_tally"]["winner_votes"] == elected["votes_received"]
    assert result["vote_tally"]["total_delegates"] == 5


def test_war_room_stream_emits_election_events():
    """Verify that the SSE stream emits candidate answers, delegate ballots, and elected replier done payload."""
    gen = UnionWarRoomEngine.stream_war_room_deliberation(
        user_query="What is the root cause of frontline absenteeism?",
        df=None,
        sheet_name="Operations",
        timeout_seconds=5.0
    )

    events = list(gen)
    full_text = "".join(events)

    assert "event: war_room_init" in full_text
    assert "event: candidate_answer" in full_text
    assert "event: delegate_vote" in full_text
    assert "event: token" in full_text
    assert "event: done" in full_text

    # Extract and parse the done event payload
    done_chunks = [e for e in events if e.startswith("event: done")]
    assert len(done_chunks) == 1
    data_line = [l for l in done_chunks[0].split("\n") if l.startswith("data: ")][0]
    done_payload = json.loads(data_line[6:])

    assert "elected_replier" in done_payload
    assert done_payload["elected_replier"]["id"] is not None
    assert "candidate_answers" in done_payload
    assert len(done_payload["candidate_answers"]) == 5
    assert "ballots" in done_payload
    assert len(done_payload["ballots"]) == 5
    for b in done_payload["ballots"]:
        assert b["voter_id"] != b["voted_for_id"], f"Streamed delegate {b['voter_id']} illegally voted for itself!"
    assert "vote_tally" in done_payload
