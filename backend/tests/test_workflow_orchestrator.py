"""End-to-end integration tests for the full WorkflowOrchestrator state machine."""

import pandas as pd
import pytest

from app.services.reporting.workflow_orchestrator import WorkflowOrchestrator, WorkflowExecutionResult


@pytest.fixture
def enterprise_df():
    return pd.DataFrame({
        "staff_id": [f"ID-{i}" for i in range(1, 21)],
        "unit": ["Retail"] * 10 + ["Support"] * 10,
        "score": [88, 92, 85, 90, 94, 89, 91, 87, 93, 90, 72, 75, 71, 74, 78, 70, 73, 76, 72, 74],
        "log_date": ["2026-03-01"] * 10 + ["2026-03-02"] * 10
    })


def test_workflow_orchestrator_end_to_end(enterprise_df):
    """Verifies that WorkflowOrchestrator executes all 8 stages from CSV to verified evidence-aware deck."""
    progress_records = []

    def on_progress(msg: str, pct: int):
        progress_records.append((msg, pct))

    result = WorkflowOrchestrator.execute(
        df=enterprise_df,
        dataset_name="Enterprise Staff Log",
        objective="Q1 Divisional Benchmarks",
        on_progress=on_progress
    )

    assert isinstance(result, WorkflowExecutionResult)
    assert result.status == "COMPLETED"
    assert result.quality_report is not None
    assert result.quality_report.is_valid is True
    assert result.profile is not None
    assert result.profile.row_count == 20
    assert result.finding_count >= 1

    # Verify ReportPlan and Narrative
    assert result.plan is not None
    assert len(result.plan.sections) >= 1
    assert result.report is not None
    assert len(result.report.sections) >= 1

    # Verify Evidence-Aware Slide Deck
    assert "slides" in result.deck_spec
    assert len(result.deck_spec["slides"]) >= 2  # Hero title slide + section slides
    assert "evidence_ledger" in result.deck_spec
    assert len(result.deck_spec["evidence_ledger"]) >= 1

    # Verify that every slide has finding_ids
    for slide in result.deck_spec["slides"]:
        assert "title" in slide
        assert "category" in slide
        assert "finding_ids" in slide

    # Verify progress telemetry
    assert len(progress_records) >= 5
    assert progress_records[0][1] == 10  # validation
    assert progress_records[-1][1] == 100  # completion


def test_workflow_orchestrator_halts_on_bad_data():
    """Verifies that invalid datasets halt before LLM calls and return DATA_QUALITY_REJECTED."""
    empty_df = pd.DataFrame()
    result = WorkflowOrchestrator.execute(empty_df, dataset_name="Corrupt CSV")
    assert result.status == "DATA_QUALITY_REJECTED"
    assert result.plan is None
    assert result.report is None
    assert "0 rows" in result.error_message
