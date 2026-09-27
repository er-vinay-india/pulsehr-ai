"""Comprehensive Test Suite for Deferred Original Phase 1: Input, Context & Ingestion Intelligence.

Tests all 28 required test scenarios:
1. single CSV
2. simple Excel
3. multi-sheet workbook
4. multiple related files
5. unrelated files
6. user instruction present
7. no user instruction (fallback)
8. changed user instruction (incremental update without re-profiling)
9. replaced file (cache invalidation)
10. sparse data (cautious warnings)
11. large dataset profiling
12. date-based dataset & time intelligence
13. financial data classification
14. HR data classification
15. technical metrics classification
16. generic unknown domain fallback
17. unsupported user question detection
18. partially supported question detection
19. sensitive columns detection & redaction
20. duplicate records detection
21. missing values detection & hygiene scoring
22. relationship detection & candidate join discovery
23. ambiguous / unsafe join detection (many-to-many)
24. user override precedence (user correction wins)
25. WorkspaceContext -> PresentationPlanningContext adaptation
26. Phase 1 semantic memory integration
27. stale snapshot invalidation
28. current web application theme unchanged
"""

import os
import re
import pytest
import pandas as pd

from app.services.input_intelligence import (
    AlignmentStatus,
    AnalysisReadiness,
    DataProfiler,
    DatasetProfile,
    InferredDomain,
    InputIntelligenceService,
    IntentStatus,
    JoinCardinality,
    MemoryIntegrationBridge,
    MultiSheetIntelligence,
    OutputIntent,
    ReadinessStatus,
    SemanticClassifier,
    SemanticColumnRole,
    SemanticUnit,
    SnapshotManager,
    SourceItem,
    SourceRole,
    SourceType,
    UserIntentEngine,
    WorkspaceContext,
    WorkspaceToPresentationAdapter,
)


# =============================================================================
# 1. Single CSV
# =============================================================================
def test_01_single_csv():
    records = [
        {"emp_id": "E1", "dept": "Sales", "hours": 40.0},
        {"emp_id": "E2", "dept": "Eng", "hours": 42.5},
        {"emp_id": "E3", "dept": "Support", "hours": 38.0}
    ]
    df = pd.DataFrame(records)
    prof, qual = DataProfiler.profile_dataframe(df, dataset_id="csv_1", dataset_name="employees.csv")
    assert prof.row_count == 3
    assert prof.col_count == 3
    assert "emp_id" in prof.primary_keys or any(c.is_identifier_candidate for c in prof.columns)
    assert qual.overall_health_score > 0.5


# =============================================================================
# 2. Simple Excel
# =============================================================================
def test_02_simple_excel():
    source = SourceItem(
        source_id="src_excel",
        source_type=SourceType.EXCEL,
        filename="sales_q3.xlsx",
        original_name="sales_q3.xlsx"
    )
    role = MultiSheetIntelligence.classify_source_role(source)
    assert role == SourceRole.PRIMARY_DATA


# =============================================================================
# 3. Multi-Sheet Workbook
# =============================================================================
def test_03_multi_sheet_workbook():
    p1 = DatasetProfile(
        dataset_id="s1", name="Transactions", original_name="Transactions", row_count=500, col_count=4
    )
    p2 = DatasetProfile(
        dataset_id="s2", name="Lookup_Metadata", original_name="Lookup_Metadata", row_count=20, col_count=2
    )
    wb = MultiSheetIntelligence.build_workbook_context("Global_ERP.xlsx", "src_wb", [p1, p2])
    assert wb.workbook_name == "Global_ERP.xlsx"
    assert "s1" in wb.primary_sheet_candidates
    assert "s2" in wb.reference_sheet_candidates


# =============================================================================
# 4. Multiple Related Files
# =============================================================================
def test_04_multiple_related_files():
    df_orders = pd.DataFrame([{"order_id": "O1", "cust_id": "C100", "amt": 50.0}])
    df_customers = pd.DataFrame([{"cust_id": "C100", "name": "Acme Corp"}])

    p_orders, _ = DataProfiler.profile_dataframe(df_orders, dataset_id="orders", dataset_name="orders.csv")
    p_cust, _ = DataProfiler.profile_dataframe(df_customers, dataset_id="customers", dataset_name="customers.csv")

    for c in p_orders.columns:
        SemanticClassifier.enrich_column_semantics(c)
    for c in p_cust.columns:
        SemanticClassifier.enrich_column_semantics(c)

    rels = MultiSheetIntelligence.detect_relationships([p_orders, p_cust])
    assert len(rels) >= 1
    assert rels[0].left_column == "cust_id" or rels[0].right_column == "cust_id"
    assert rels[0].confidence >= 0.80


# =============================================================================
# 5. Unrelated Files
# =============================================================================
def test_05_unrelated_files():
    df1 = pd.DataFrame([{"server_ip": "10.0.0.1", "ping_ms": 12.4}])
    df2 = pd.DataFrame([{"fruit_name": "Apple", "harvest_month": "October"}])

    p1, _ = DataProfiler.profile_dataframe(df1, "servers", "servers.csv")
    p2, _ = DataProfiler.profile_dataframe(df2, "fruits", "fruits.csv")

    rels = MultiSheetIntelligence.detect_relationships([p1, p2])
    assert len(rels) == 0


# =============================================================================
# 6. User Instruction Present
# =============================================================================
def test_06_user_instruction_present():
    instruction = "Create a presentation comparing regional sales margins for executive leadership. Exactly 6 slides."
    intent = UserIntentEngine.parse_user_intent(instruction)
    assert intent.intent_status == IntentStatus.EXPLICIT
    assert intent.expected_output == OutputIntent.PRESENTATION
    assert intent.audience == "Executive Leadership & Board"
    assert "Exactly 6 slides" in intent.presentation_constraints
    assert "margin" in intent.analysis_focus


# =============================================================================
# 7. No User Instruction (Fallback)
# =============================================================================
def test_07_no_user_instruction_fallback():
    records = [{"department": "Eng", "attendance_days": 18, "leave_days": 2}]
    df = pd.DataFrame(records)
    prof, _ = DataProfiler.profile_dataframe(df, "hr", "hr.csv")

    intent = UserIntentEngine.parse_user_intent("", dataset_profiles=[prof])
    assert intent.intent_status == IntentStatus.UNSPECIFIED
    assert len(intent.possible_analysis_capabilities) >= 1
    assert any("attendance" in cap.lower() or "leave" in cap.lower() for cap in intent.possible_analysis_capabilities)


# =============================================================================
# 8. Changed User Instruction (Incremental Update)
# =============================================================================
def test_08_changed_user_instruction_incremental():
    ctx = InputIntelligenceService.process_workspace_input(
        workspace_id="ws_inc_01",
        files_or_data=[{
            "id": "f1",
            "filename": "sales.csv",
            "records": [{"region": "North", "sales": 100, "profit": 20}]
        }],
        user_instruction="Focus on sales volume."
    )
    assert ctx.user_request.normalized_objective == "Focus on sales volume"

    # Now change instruction only
    updated = SnapshotManager.update_user_instructions_only(
        current_context=ctx,
        new_instruction="Focus on profit margins for executive board.",
        new_audience="Executive Board"
    )
    assert updated.user_request.normalized_objective == "Focus on profit margins for executive board"
    assert updated.user_request.audience == "Executive Board"
    assert len(updated.datasets) == 1
    assert updated.datasets[0].row_count == 1  # Profiling preserved without re-reading disk


# =============================================================================
# 9. Replaced File (Invalidation)
# =============================================================================
def test_09_replaced_file_invalidation():
    SnapshotManager.cache_context(WorkspaceContext(workspace_id="ws_stale_01"))
    assert SnapshotManager.get_cached_context("ws_stale_01") is not None

    SnapshotManager.invalidate_workspace("ws_stale_01")
    assert SnapshotManager.get_cached_context("ws_stale_01") is None


# =============================================================================
# 10. Sparse Data (Caution Warnings)
# =============================================================================
def test_10_sparse_data():
    records = [{"client_id": "C1", "nps": 9}, {"client_id": "C2", "nps": 8}]
    df = pd.DataFrame(records)
    prof, qual = DataProfiler.profile_dataframe(df, "sparse", "pilot.csv")
    assert prof.row_count == 2
    assert any(i.issue_type == "LOW_SAMPLE_SIZE" for i in qual.issues)


# =============================================================================
# 11. Large Dataset Profiling
# =============================================================================
def test_11_large_dataset_profiling():
    # 5,000 synthetic rows
    rows = [{"id": f"ID_{i}", "metric": float(i * 1.5), "cat": f"Cat_{i%10}"} for i in range(5000)]
    df = pd.DataFrame(rows)
    prof, qual = DataProfiler.profile_dataframe(df, "large", "transactions.csv")
    assert prof.row_count == 5000
    assert prof.col_count == 3
    assert len(prof.representative_samples) <= 5  # Bounded sample budget


# =============================================================================
# 12. Date-Based Dataset & Time Intelligence
# =============================================================================
def test_12_date_dataset_and_time_intelligence():
    records = [
        {"trans_date": "2026-01-15", "amount": 100},
        {"trans_date": "2026-06-30", "amount": 250},
        {"trans_date": "2026-09-20", "amount": 300},
    ]
    df = pd.DataFrame(records)
    prof, _ = DataProfiler.profile_dataframe(df, "time_ds", "timeseries.csv")
    for c in prof.columns:
        SemanticClassifier.enrich_column_semantics(c)

    time_intel = SemanticClassifier.extract_time_intelligence([prof])
    assert time_intel.min_date == "2026-01-15"
    assert time_intel.max_date == "2026-09-20"
    assert "2026" in time_intel.reporting_period


# =============================================================================
# 13. Financial Data Classification
# =============================================================================
def test_13_financial_data_classification():
    records = [
        {"cost_center": "Marketing", "budget_usd": 400000, "actual_spend": 380000, "variance_pct": -0.05}
    ]
    df = pd.DataFrame(records)
    prof, _ = DataProfiler.profile_dataframe(df, "fin", "budget.csv")
    for c in prof.columns:
        SemanticClassifier.enrich_column_semantics(c)

    roles = {c.name: c.semantic_role for c in prof.columns}
    assert roles["budget_usd"] == SemanticColumnRole.CURRENCY
    assert roles["variance_pct"] == SemanticColumnRole.PERCENTAGE

    domain, conf, _ = SemanticClassifier.infer_domain([prof], dataset_name="budget.csv")
    assert domain == InferredDomain.FINANCE


# =============================================================================
# 14. HR Data Classification
# =============================================================================
def test_14_hr_data_classification():
    records = [
        {"employee_id": "EMP-01", "department": "Eng", "attendance_rate": 0.94, "leave_days": 3}
    ]
    df = pd.DataFrame(records)
    prof, _ = DataProfiler.profile_dataframe(df, "hr", "attendance_q3.csv")
    domain, conf, signals = SemanticClassifier.infer_domain([prof], dataset_name="attendance_q3.csv")
    assert domain == InferredDomain.HR_WORKFORCE
    assert "attendance" in signals or "employee" in signals


# =============================================================================
# 15. Technical Metrics Classification
# =============================================================================
def test_15_technical_metrics_classification():
    records = [
        {"service_name": "API_Gateway", "p99_latency_ms": 42.8, "rps_throughput": 12000, "error_rate": 0.001}
    ]
    df = pd.DataFrame(records)
    prof, _ = DataProfiler.profile_dataframe(df, "tech", "microservice_telemetry.log")
    domain, conf, signals = SemanticClassifier.infer_domain([prof], dataset_name="microservice_telemetry.log")
    assert domain in (InferredDomain.SOFTWARE_ENGINEERING, InferredDomain.INFRASTRUCTURE)


# =============================================================================
# 16. Generic Unknown Domain Fallback
# =============================================================================
def test_16_generic_unknown_domain_fallback():
    records = [
        {"col_a": 10, "col_b": 20, "col_c": 30}
    ]
    df = pd.DataFrame(records)
    prof, _ = DataProfiler.profile_dataframe(df, "gen", "misc_numbers.csv")
    domain, conf, _ = SemanticClassifier.infer_domain([prof], dataset_name="misc_numbers.csv")
    assert domain == InferredDomain.GENERIC_ANALYTICS
    assert conf == 0.50


# =============================================================================
# 17. Unsupported User Question Detection
# =============================================================================
def test_17_unsupported_user_question():
    records = [{"department": "Sales", "headcount": 40}]
    df = pd.DataFrame(records)
    prof, _ = DataProfiler.profile_dataframe(df, "ds", "data.csv")

    # User asks about salary, but data has no salary/compensation
    mappings = UserIntentEngine.reconcile_questions_against_data(
        questions=["Which employees are underpaid and what is the median salary?"],
        profiles=[prof]
    )
    assert len(mappings) == 1
    assert mappings[0].alignment_status == AlignmentStatus.UNSUPPORTED
    assert "salary" in mappings[0].explanation.lower() or "missing" in mappings[0].explanation.lower()


# =============================================================================
# 18. Partially Supported Question Detection
# =============================================================================
def test_18_partially_supported_question():
    records = [{"department": "Sales", "revenue": 100000}]
    df = pd.DataFrame(records)
    prof, _ = DataProfiler.profile_dataframe(df, "ds", "data.csv")

    # Mapped department and revenue, but 'projected_growth' is missing
    mappings = UserIntentEngine.reconcile_questions_against_data(
        questions=["Which department had highest revenue and projected growth?"],
        profiles=[prof]
    )
    assert len(mappings) == 1
    assert mappings[0].alignment_status == AlignmentStatus.PARTIALLY_SUPPORTED
    assert "revenue" in mappings[0].mapped_fields or "department" in mappings[0].mapped_fields


# =============================================================================
# 19. Sensitive Columns Detection & Redaction
# =============================================================================
def test_19_sensitive_columns_detection_and_redaction():
    records = [
        {"name": "Alice", "email": "alice@company.com", "salary": 120000, "score": 95},
        {"name": "Bob", "email": "bob@company.com", "salary": 110000, "score": 88}
    ]
    df = pd.DataFrame(records)
    prof, qual = DataProfiler.profile_dataframe(df, "hr_sens", "confidential.csv")

    assert "email" in prof.sensitive_columns
    assert "salary" in prof.sensitive_columns

    # Verify that representative samples redact sensitive columns
    for s in prof.representative_samples:
        assert s["email"] == "[REDACTED]"
        assert s["salary"] == "[REDACTED]"
        assert s["score"] != "[REDACTED]"


# =============================================================================
# 20. Duplicate Records Detection
# =============================================================================
def test_20_duplicate_records_detection():
    records = [
        {"id": "A1", "val": 10},
        {"id": "A1", "val": 10},
        {"id": "A2", "val": 20}
    ]
    df = pd.DataFrame(records)
    prof, qual = DataProfiler.profile_dataframe(df, "dup_ds", "dups.csv")
    assert prof.duplicate_row_count == 1
    assert any(i.issue_type == "DUPLICATE_ROWS" for i in qual.issues)


# =============================================================================
# 21. Missing Values Detection & Hygiene Scoring
# =============================================================================
def test_21_missing_values_and_hygiene():
    records = [
        {"id": 1, "score": None},
        {"id": 2, "score": None},
        {"id": 3, "score": None},
        {"id": 4, "score": 85.0}
    ]
    df = pd.DataFrame(records)
    prof, qual = DataProfiler.profile_dataframe(df, "null_ds", "nulls.csv")
    score_col = next(c for c in prof.columns if c.name == "score")
    assert score_col.null_pct == 0.75
    assert qual.overall_health_score < 0.95


# =============================================================================
# 22. Relationship Detection & Join Candidate Discovery
# =============================================================================
def test_22_relationship_detection():
    df1 = pd.DataFrame([{"dept_id": "D1", "name": "Eng"}])
    df2 = pd.DataFrame([{"emp_id": "E1", "dept_id": "D1"}, {"emp_id": "E2", "dept_id": "D1"}])

    p1, _ = DataProfiler.profile_dataframe(df1, "depts", "depts.csv")
    p2, _ = DataProfiler.profile_dataframe(df2, "employees", "employees.csv")

    for p in (p1, p2):
        for c in p.columns:
            SemanticClassifier.enrich_column_semantics(c)

    rels = MultiSheetIntelligence.detect_relationships([p1, p2])
    assert len(rels) >= 1
    assert rels[0].cardinality in (JoinCardinality.ONE_TO_MANY, JoinCardinality.MANY_TO_ONE)
    assert rels[0].is_safe is True


# =============================================================================
# 23. Ambiguous / Unsafe Join Detection (Many-to-Many)
# =============================================================================
def test_23_ambiguous_many_to_many_join():
    # Both sides have duplicate join keys
    df1 = pd.DataFrame([{"project_tag": "AI", "lead": "A"}, {"project_tag": "AI", "lead": "B"}])
    df2 = pd.DataFrame([{"project_tag": "AI", "tool": "Python"}, {"project_tag": "AI", "tool": "C++"}])

    p1, _ = DataProfiler.profile_dataframe(df1, "projects", "projects.csv")
    p2, _ = DataProfiler.profile_dataframe(df2, "tools", "tools.csv")

    rels = MultiSheetIntelligence.detect_relationships([p1, p2])
    assert len(rels) >= 1
    assert rels[0].cardinality == JoinCardinality.MANY_TO_MANY
    assert rels[0].is_safe is False  # Safe flag set to False for many-to-many


# =============================================================================
# 24. User Override Precedence (User Correction Wins)
# =============================================================================
def test_24_user_override_precedence():
    records = [{"item": "Bolt", "count": 100}]
    ctx = InputIntelligenceService.process_workspace_input(
        workspace_id="ws_ovr_01",
        files_or_data=[{"id": "f1", "filename": "data.csv", "records": records}],
        user_instruction="Analyze items.",
        user_overrides={
            "domain": "Aerospace Hardware",
            "objective": "Audited Aerospace Part Traceability"
        }
    )
    # User override must win over inference
    assert ctx.context_summary.domain == "Aerospace Hardware"
    assert ctx.user_request.normalized_objective == "Audited Aerospace Part Traceability"


# =============================================================================
# 25. WorkspaceContext -> PresentationPlanningContext Adaptation
# =============================================================================
def test_25_workspace_to_presentation_adaptation():
    records = [{"region": "North", "sales_m": 18.4, "margin_pct": 0.64}]
    ctx = InputIntelligenceService.process_workspace_input(
        workspace_id="ws_pres_01",
        files_or_data=[{"id": "sales_q3", "filename": "sales.csv", "records": records}],
        user_instruction="Executive sales review. Exactly 6 slides.",
    )
    pres_ctx = WorkspaceToPresentationAdapter.adapt(
        context=ctx,
        theme_id="bold_signal"
    )
    assert pres_ctx.domain == "Commercial Sales"
    assert pres_ctx.dataset_label == "sales.csv"
    assert pres_ctx.total_records == 1
    assert pres_ctx.slide_count_constraint.target == 6
    assert pres_ctx.theme_id == "bold_signal"


# =============================================================================
# 26. Phase 1 Semantic Memory Integration
# =============================================================================
def test_26_phase1_semantic_memory_integration():
    records = [{"dept": "Eng", "score": 95.0}]
    ctx = InputIntelligenceService.process_workspace_input(
        workspace_id="ws_mem_01",
        files_or_data=[{"id": "ds_mem", "filename": "benchmarks.csv", "records": records}],
        user_instruction="Benchmark review for leadership."
    )
    indexed_count = MemoryIntegrationBridge.index_workspace_context(ctx, force=True)
    assert indexed_count >= 1


# =============================================================================
# 27. Stale Snapshot Invalidation
# =============================================================================
def test_27_stale_snapshot_invalidation():
    s1 = SourceItem(source_id="f1", source_type=SourceType.CSV, filename="f1.csv", original_name="f1.csv", file_hash="hash_a", size_bytes=100)
    snap1 = SnapshotManager.create_snapshot("ws_inv", [s1])

    # Replace file
    s2 = SourceItem(source_id="f1", source_type=SourceType.CSV, filename="f1.csv", original_name="f1.csv", file_hash="hash_b_changed", size_bytes=120)
    snap2 = SnapshotManager.create_snapshot("ws_inv", [s2])

    assert snap1.snapshot_hash != snap2.snapshot_hash


# =============================================================================
# 28. Current Application Theme Unchanged
# =============================================================================
def test_28_application_theme_unchanged():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    tokens_file = os.path.join(repo_root, "frontend", "src", "styles", "_tokens.scss")
    with open(tokens_file, "r") as f:
        content = f.read()

    assert "--color-bg-page: #F8FAFC;" in content
    assert "--color-text-primary: #0B1F3A;" in content
    assert "--color-brand-primary: #0B1F3A;" in content
    assert "--color-brand-accent: #155EEF;" in content
