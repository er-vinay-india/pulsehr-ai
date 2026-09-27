"""Workspace Context Integration & User Control Test Suite.

Verifies all 27 requirements from Section 33:
1. WorkspaceContext API retrieval (<200ms)
2. Partial PATCH override (<100ms)
3. Domain override outranks inference
4. Semantic column role override & candidate realignment
5. Primary dataset override
6. User intent editing
7. Question mapping refresh
8. Readiness refresh
9. No physical dataset re-read on intent update
10. No physical re-read on semantic override
11. Safe join acceptance
12. Unsafe many-to-many remains blocked
13. Audit provenance records override
14. EDA receives corrected context
15. Dashboard receives corrected context
16. Presentation receives corrected context
17. Cross-feature semantic consistency across EDA, Dashboard & Presentation
18. Sensitive sample values remain redacted
19. High-confidence context requires no mandatory dialog
20. Low-confidence context flags review
21. Unsupported question is surfaced with explanation
22. Web application theme tokens (_tokens.scss) unchanged
23. No global CSS introduced
24. Application light/dark mode tokens pristine
"""

import os
import re
import time
import pytest
from fastapi.testclient import TestClient
import pandas as pd

from app.main import app
from app.services.input_intelligence import (
    AlignmentStatus,
    DashboardContextAdapter,
    EDAContextAdapter,
    InputIntelligenceService,
    JoinCardinality,
    OutputIntent,
    ProvenanceOrigin,
    ReadinessStatus,
    SemanticColumnRole,
    SnapshotManager,
    WorkspaceContext,
    WorkspaceToPresentationAdapter,
)

client = TestClient(app)


@pytest.fixture
def sample_workspace():
    """Builds a test workspace context with attendance data and mixed columns."""
    ws_id = "ws_test_integration_01"
    records = [
        {"emp_id": "E101", "dept": "Eng", "office_days": 18, "salary": 140000, "email": "e101@pulsehr.com"},
        {"emp_id": "E102", "dept": "Eng", "office_days": 19, "salary": 145000, "email": "e102@pulsehr.com"},
        {"emp_id": "E103", "dept": "Sales", "office_days": 14, "salary": 110000, "email": "e103@pulsehr.com"},
        {"emp_id": "E104", "dept": "Sales", "office_days": 12, "salary": 115000, "email": "e104@pulsehr.com"},
    ]
    ctx = InputIntelligenceService.process_workspace_input(
        workspace_id=ws_id,
        files_or_data=[{"id": "attendance_q3", "filename": "attendance_q3.csv", "records": records}],
        user_instruction="Analyze attendance and office days by department."
    )
    return ctx


# =============================================================================
# 1. WorkspaceContext API Retrieval (<200ms)
# =============================================================================
def test_01_workspace_context_api_retrieval(sample_workspace):
    t0 = time.perf_counter()
    resp = client.get(f"/api/workspace/{sample_workspace.workspace_id}/context")
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert resp.status_code == 200
    data = resp.json()
    assert data["workspace_id"] == sample_workspace.workspace_id
    assert "context_summary" in data
    assert elapsed_ms < 200, f"API retrieval took {elapsed_ms}ms, expected < 200ms"


# =============================================================================
# 2. Partial PATCH Override (<100ms)
# =============================================================================
def test_02_partial_patch_override(sample_workspace):
    t0 = time.perf_counter()
    patch_payload = {
        "user_objective": "Identify departments with unusually high remote days."
    }
    resp = client.patch(f"/api/workspace/{sample_workspace.workspace_id}/context", json=patch_payload)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert resp.status_code == 200
    data = resp.json()
    assert "Identify departments with unusually high remote days" in data["user_request"]["normalized_objective"]
    assert elapsed_ms < 100, f"Partial patch took {elapsed_ms}ms, expected < 100ms"


# =============================================================================
# 3. Domain Override
# =============================================================================
def test_03_domain_override(sample_workspace):
    patch_payload = {"domain": "Business Operations"}
    resp = client.patch(f"/api/workspace/{sample_workspace.workspace_id}/context", json=patch_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["context_summary"]["domain"] == "Business Operations"

    # Verify audit trail
    assert len(data["override_history"]) >= 1
    last_audit = data["override_history"][-1]
    assert last_audit["field"] == "domain"
    assert last_audit["new_value"] == "Business Operations"
    assert last_audit["origin"] == "USER_OVERRIDE"


# =============================================================================
# 4. Semantic Column Role Override
# =============================================================================
def test_04_semantic_column_role_override(sample_workspace):
    patch_payload = {
        "column_roles": {
            "office_days": "METRIC"
        }
    }
    resp = client.patch(f"/api/workspace/{sample_workspace.workspace_id}/context", json=patch_payload)
    assert resp.status_code == 200
    data = resp.json()
    col = next(c for c in data["datasets"][0]["columns"] if c["name"] == "office_days")
    assert col["semantic_role"] == "METRIC"
    assert "office_days" in data["datasets"][0]["metric_candidates"]


# =============================================================================
# 5. Primary Dataset Override
# =============================================================================
def test_05_primary_dataset_override():
    ws_id = "ws_multi_ds_override"
    df1 = pd.DataFrame([{"dept": "Eng", "score": 90}])
    df2 = pd.DataFrame([{"loc": "HQ", "count": 20}])
    ctx = InputIntelligenceService.process_workspace_input(
        workspace_id=ws_id,
        files_or_data=[
            {"id": "ds_a", "filename": "a.csv", "records": df1.to_dict("records")},
            {"id": "ds_b", "filename": "b.csv", "records": df2.to_dict("records")}
        ]
    )
    assert ctx.primary_dataset_id == "ds_a"

    # Override to ds_b
    patch_payload = {"primary_dataset_id": "ds_b"}
    resp = client.patch(f"/api/workspace/{ws_id}/context", json=patch_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["primary_dataset_id"] == "ds_b"
    assert data["context_summary"]["primary_dataset"] == "b.csv"


# =============================================================================
# 6. User Intent Editing
# =============================================================================
def test_06_intent_edit(sample_workspace):
    updated = SnapshotManager.update_user_instructions_only(
        current_context=sample_workspace,
        new_instruction="Examine employee burnout strain and correlation with office days."
    )
    assert "burnout" in updated.user_request.normalized_objective.lower()
    assert updated.context_summary.user_goal == updated.user_request.normalized_objective


# =============================================================================
# 7. Question Mapping Refresh
# =============================================================================
def test_07_question_mapping_refresh(sample_workspace):
    patch_payload = {
        "explicit_questions": [
            "Which department has highest office days?",
            "What is customer churn rate?"
        ]
    }
    resp = client.patch(f"/api/workspace/{sample_workspace.workspace_id}/context", json=patch_payload)
    assert resp.status_code == 200
    data = resp.json()

    q_map = data["question_mappings"]
    assert len(q_map) == 2
    # Q1 is supported by dept and office_days
    assert q_map[0]["alignment_status"] in ("SUPPORTED", "PARTIALLY_SUPPORTED")
    # Q2 is unsupported (no churn or customer columns)
    assert q_map[1]["alignment_status"] == "UNSUPPORTED"


# =============================================================================
# 8. Readiness Refresh
# =============================================================================
def test_08_readiness_refresh(sample_workspace):
    # When all questions are supported, readiness is READY or READY_WITH_WARNINGS
    patch_payload = {
        "explicit_questions": ["What is office days by dept?"]
    }
    resp = client.patch(f"/api/workspace/{sample_workspace.workspace_id}/context", json=patch_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["readiness"]["status"] in ("READY", "READY_WITH_WARNINGS")

    # When questions demand missing columns, readiness becomes NEEDS_MAPPING
    patch_payload_missing = {
        "explicit_questions": ["What is EBITDA by customer tier?"]
    }
    resp2 = client.patch(f"/api/workspace/{sample_workspace.workspace_id}/context", json=patch_payload_missing)
    data2 = resp2.json()
    assert data2["readiness"]["status"] == "NEEDS_MAPPING"


# =============================================================================
# 9. No Physical Dataset Re-Read on Intent-Only Update
# =============================================================================
def test_09_no_physical_dataset_reread_on_intent_update(sample_workspace):
    # Modify instruction only
    snap_before = sample_workspace.provenance.snapshot_hash
    t0 = time.perf_counter()
    updated = SnapshotManager.update_user_instructions_only(sample_workspace, "Updated intent prompt")
    elapsed_ms = (time.perf_counter() - t0) * 1000

    # Dataset profile must remain identical
    assert updated.provenance.snapshot_hash == snap_before
    assert updated.datasets[0].row_count == sample_workspace.datasets[0].row_count
    assert elapsed_ms < 50, f"Intent-only update took {elapsed_ms}ms, expected < 50ms"


# =============================================================================
# 10. No Physical Re-Read on Semantic Override
# =============================================================================
def test_10_no_physical_reread_on_semantic_override(sample_workspace):
    t0 = time.perf_counter()
    updated = SnapshotManager.apply_user_overrides(
        current_context=sample_workspace,
        overrides={"domain": "Corporate Finance"}
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert updated.context_summary.domain == "Corporate Finance"
    assert updated.datasets[0].row_count == sample_workspace.datasets[0].row_count
    assert elapsed_ms < 50, f"Semantic override took {elapsed_ms}ms, expected < 50ms"


# =============================================================================
# 11. Safe Join Acceptance
# =============================================================================
def test_11_safe_join_acceptance():
    ws_id = "ws_join_safe_01"
    df1 = pd.DataFrame([{"dept_id": "D1", "dept_name": "Eng"}])
    df2 = pd.DataFrame([{"emp_id": "E1", "dept_id": "D1"}, {"emp_id": "E2", "dept_id": "D1"}])
    ctx = InputIntelligenceService.process_workspace_input(
        workspace_id=ws_id,
        files_or_data=[
            {"id": "depts", "filename": "depts.csv", "records": df1.to_dict("records")},
            {"id": "employees", "filename": "employees.csv", "records": df2.to_dict("records")}
        ]
    )
    assert len(ctx.relationships) >= 1
    rel_id = ctx.relationships[0].relationship_id

    resp = client.post(f"/api/workspace/{ws_id}/context/join-override", json={"relationship_id": rel_id, "accept": True})
    assert resp.status_code == 200
    data = resp.json()
    rel = next(r for r in data["relationships"] if r["relationship_id"] == rel_id)
    assert rel["is_safe"] is True


# =============================================================================
# 12. Unsafe Many-to-Many Remains Blocked
# =============================================================================
def test_12_unsafe_many_to_many_remains_blocked():
    ws_id = "ws_m2m_block_01"
    df1 = pd.DataFrame([{"tag": "T1", "item": "A"}, {"tag": "T1", "item": "B"}])
    df2 = pd.DataFrame([{"tag": "T1", "role": "Dev"}, {"tag": "T1", "role": "QA"}])
    ctx = InputIntelligenceService.process_workspace_input(
        workspace_id=ws_id,
        files_or_data=[
            {"id": "items", "filename": "items.csv", "records": df1.to_dict("records")},
            {"id": "roles", "filename": "roles.csv", "records": df2.to_dict("records")}
        ]
    )
    assert len(ctx.relationships) >= 1
    rel = ctx.relationships[0]
    assert rel.cardinality == JoinCardinality.MANY_TO_MANY
    assert rel.is_safe is False

    # Attempt to force accept unsafe many-to-many join
    resp = client.post(f"/api/workspace/{ws_id}/context/join-override", json={"relationship_id": rel.relationship_id, "accept": True})
    assert resp.status_code == 200
    data = resp.json()
    rel_after = next(r for r in data["relationships"] if r["relationship_id"] == rel.relationship_id)
    # Permanent invariant: unsafe many-to-many remains False
    assert rel_after["is_safe"] is False


# =============================================================================
# 13. Audit Provenance Records Override
# =============================================================================
def test_13_audit_provenance_records_override(sample_workspace):
    updated = SnapshotManager.apply_user_overrides(
        current_context=sample_workspace,
        overrides={"domain": "Corporate Finance", "reporting_period": "Q3 2026"}
    )
    assert len(updated.override_history) >= 2
    fields = [a.field for a in updated.override_history]
    assert "domain" in fields
    assert "reporting_period" in fields
    for a in updated.override_history:
        assert a.origin == ProvenanceOrigin.USER_OVERRIDE


# =============================================================================
# 14. EDA Receives Corrected Context
# =============================================================================
def test_14_eda_receives_corrected_context(sample_workspace):
    # Override column role
    updated = SnapshotManager.apply_user_overrides(
        current_context=sample_workspace,
        overrides={"domain": "Commercial Sales", "column_roles": {"office_days": "CURRENCY"}}
    )
    eda_ctx = EDAContextAdapter.adapt(updated)
    assert eda_ctx.domain == "Commercial Sales"
    assert eda_ctx.semantic_roles["office_days"] == "CURRENCY"
    assert eda_ctx.context_version == updated.workspace_context_version


# =============================================================================
# 15. Dashboard Receives Corrected Context
# =============================================================================
def test_15_dashboard_receives_corrected_context(sample_workspace):
    updated = SnapshotManager.apply_user_overrides(
        current_context=sample_workspace,
        overrides={
            "domain": "Commercial Sales",
            "explicit_questions": ["What is office days by dept?"]
        }
    )
    dash_ctx = DashboardContextAdapter.adapt(updated)
    assert dash_ctx.domain == "Commercial Sales"
    assert "What is office days by dept?" in dash_ctx.supported_questions
    assert len(dash_ctx.suggested_widgets) >= 1
    assert dash_ctx.suggested_widgets[0]["target_question"] == "What is office days by dept?"


# =============================================================================
# 16. Presentation Receives Corrected Context
# =============================================================================
def test_16_presentation_receives_corrected_context(sample_workspace):
    updated = SnapshotManager.apply_user_overrides(
        current_context=sample_workspace,
        overrides={"domain": "Commercial Sales"}
    )
    pres_ctx = WorkspaceToPresentationAdapter.adapt(updated, theme_id="bold_signal")
    assert pres_ctx.domain == "Commercial Sales"
    assert pres_ctx.theme_id == "bold_signal"


# =============================================================================
# 17. Cross-Feature Semantic Consistency Across EDA, Dashboard & Presentation
# =============================================================================
def test_17_all_three_receive_identical_semantic_role_interpretation(sample_workspace):
    updated = SnapshotManager.apply_user_overrides(
        current_context=sample_workspace,
        overrides={
            "column_roles": {"office_days": "METRIC"}
        }
    )
    eda_ctx = EDAContextAdapter.adapt(updated)
    dash_ctx = DashboardContextAdapter.adapt(updated)
    pres_ctx = WorkspaceToPresentationAdapter.adapt(updated)

    # All three must agree on office_days being a metric
    assert "office_days" in eda_ctx.metric_candidates
    assert "office_days" in dash_ctx.priority_metrics
    assert any("office_days" in p.get("metric_candidates", []) for p in pres_ctx.dataset_profiles)


# =============================================================================
# 18. Sensitive Sample Values Remain Redacted
# =============================================================================
def test_18_sensitive_sample_values_remain_redacted(sample_workspace):
    # Verify in DatasetProfile samples that email and salary were redacted
    profile = sample_workspace.datasets[0]
    for row in profile.sample_rows:
        if "email" in row:
            assert "@" not in row["email"] or "[REDACTED" in row["email"]
        if "salary" in row:
            assert "[REDACTED" in str(row["salary"])


# =============================================================================
# 19. High-Confidence Flow Requires No Mandatory Dialog
# =============================================================================
def test_19_high_confidence_flow_requires_no_mandatory_dialog(sample_workspace):
    assert sample_workspace.readiness.is_ready is True
    assert sample_workspace.user_request.confidence >= 0.8
    # System status is READY
    assert sample_workspace.readiness.status in (ReadinessStatus.READY, ReadinessStatus.READY_WITH_WARNINGS)


# =============================================================================
# 20. Low-Confidence Context Requests Review
# =============================================================================
def test_20_low_confidence_context_requests_review():
    # Unsupported or ambiguous instruction with explicit questions
    records = [{"x": 1, "y": 2}]
    ctx = InputIntelligenceService.process_workspace_input(
        workspace_id="ws_low_conf",
        files_or_data=[{"id": "unknown_file", "filename": "data.csv", "records": records}],
        user_instruction="What is our Q4 net profit and customer churn rate?"
    )
    assert ctx.readiness.status == ReadinessStatus.NEEDS_MAPPING
    assert ctx.readiness.is_ready is False


# =============================================================================
# 21. Unsupported Question is Surfaced
# =============================================================================
def test_21_unsupported_question_is_surfaced(sample_workspace):
    updated = SnapshotManager.apply_user_overrides(
        current_context=sample_workspace,
        overrides={"explicit_questions": ["What is customer lifetime value?"]}
    )
    dash_ctx = DashboardContextAdapter.adapt(updated)
    assert "What is customer lifetime value?" in dash_ctx.unsupported_questions
    assert len(dash_ctx.unsupported_questions) == 1


# =============================================================================
# 22. Theme Tokens Unchanged
# =============================================================================
def test_22_theme_tokens_unchanged():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    tokens_file = os.path.join(repo_root, "frontend", "src", "styles", "_tokens.scss")
    assert os.path.exists(tokens_file)
    with open(tokens_file, "r") as f:
        content = f.read()
    assert "--color-bg-page: #F8FAFC;" in content
    assert "--color-text-primary: #0B1F3A;" in content
    assert "--color-brand-primary: #0B1F3A;" in content
    assert "--color-brand-accent: #155EEF;" in content


# =============================================================================
# 23. No Global CSS Introduced
# =============================================================================
def test_23_no_global_css_introduced():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    scoped_scss = os.path.join(repo_root, "frontend", "src", "styles", "presentation-scoped-bootstrap.scss")
    with open(scoped_scss, "r") as f:
        content = f.read()
    assert ":root" not in content
    assert not re.search(r"^\s*body\s*\{", content, re.MULTILINE)
    assert not re.search(r"^\s*html\s*\{", content, re.MULTILINE)


# =============================================================================
# 24. Application Light/Dark Mode Tokens Pristine
# =============================================================================
def test_24_application_light_dark_mode_unaffected():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    tokens_file = os.path.join(repo_root, "frontend", "src", "styles", "_tokens.scss")
    with open(tokens_file, "r") as f:
        content = f.read()
    assert "[data-theme=\"dark\"]" in content
    assert "--color-bg-page: #08111F;" in content
