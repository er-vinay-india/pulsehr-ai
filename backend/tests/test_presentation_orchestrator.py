"""Comprehensive Test Suite for Phase 3: IBM Granite 4.0 Presentation Execution Orchestration.

Tests all 27 critical requirements:
1. PresentationPlanSpec unchanged by Granite
2. Slide count preserved under all modes
3. Deterministic execution graph generation
4. Cycle detection in task graph
5. Execution DAG resolution order
6. Parallel/wave execution logic
7. Tool registry lookup and execution
8. Math calculation tool accuracy
9. Aggregate data tool accuracy
10. Ranking tool accuracy
11. Outlier detection tool accuracy
12. Trend detection tool accuracy
13. Chart data preparation
14. Table data preparation
15. Phi-4 Mini verification invocation
16. DeepSeek-R1 escalation invocation
17. Missing evidence detection and handling
18. Provenance retention across all tasks
19. Retry limit enforcement (tool retries <= 2, model retries <= 1)
20. Error category assignment
21. Concurrency handling
22. Slide package assembly
23. Claim verifier integration
24. Quality auditor integration
25. Graceful fallback when Granite disabled
26. Graceful fallback when Granite fails
27. Native PPTX export from orchestrator-produced deck
"""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.core import config
from app.services.presentation.director import (
    PresentationPlanningContext,
    PresentationPlanSpec,
    SlideCountConstraint,
    SlideCountMode,
    SlidePlan,
    presentation_director,
)
from app.services.presentation.orchestrator import (
    DeepSeekReasoner,
    ErrorCategory,
    ExecutionPlan,
    ExecutionTask,
    ExecutionTaskGraph,
    ExecutorType,
    PhiAnalyticalVerifier,
    PresentationExecutionOrchestrator,
    SlideExecutionPackage,
    TaskResult,
    TaskStatus,
    TaskType,
    ToolRegistry,
    execute_deterministic_task,
    presentation_orchestrator,
)
from app.services.presentation.claim_verifier import verify_presentation_claims
from app.services.presentation_quality_auditor import PresentationQualityAuditor
from app.services.report_generator import export_spec_to_pptx
from app.services.presentation.builders.common import build_default_evidence_ledger


def make_test_context(
    slide_count_mode: SlideCountMode = SlideCountMode.ADAPTIVE,
    target_slides: int = 6
) -> tuple[PresentationPlanningContext, PresentationPlanSpec]:
    """Creates a sample planning context and a valid PresentationPlanSpec from the director."""
    ev_ledger = build_default_evidence_ledger(
        file_label="Workforce_Q3.xlsx",
        total_records=14500,
        mean_val_str="92.4 pts",
        dispersion_metric_str="1.84x",
        snapshot_hash="sha256:7f83b1657ff1",
        reporting_period_summary="Q1 2026 - Q3 2026",
        is_partial_year=False,
        mean_sales=92.4
    )[:8]

    constraint = SlideCountConstraint(
        mode=slide_count_mode,
        min_slides=4,
        max_slides=10,
        target=target_slides
    )

    ctx = PresentationPlanningContext(
        domain="Workforce Operations",
        objective="Quarterly Resource Optimization",
        audience="Executive Leadership & Board",
        instructions="Provide audited throughput metrics and identify variance.",
        dataset_label="Workforce_Q3.xlsx",
        total_records=14500,
        completeness_pct=100.0,
        baseline_benchmark="92.4 pts",
        dispersion_metric="1.84x",
        reporting_period="Q1 2026 - Q3 2026",
        dataset_profiles=[{
            "ranked_categorical": [{
                "dimension": "Department",
                "top_categories": [
                    {"category": "Engineering", "count": 6200, "percentage": 42.8},
                    {"category": "Support", "count": 4100, "percentage": 28.3}
                ]
            }],
            "numeric_rankings": [{
                "dimension": "Region",
                "dispersion_ratio": 1.84,
                "top_entity": "North",
                "bottom_entity": "South"
            }]
        }],
        current_evidence=ev_ledger,
        historical_context={
            "status": "success",
            "results": [{
                "memory_id": "MEM-HIST-01",
                "memory_type": "BUSINESS_FINDING",
                "text": "Prior quarter baseline documented 4.2% variance.",
                "evidence_status": "historical"
            }]
        },
        available_charts={"line_chart": True, "bar_chart": True, "donut_chart": True},
        slide_count_constraint=constraint
    )

    # Use director with max_retries=-1 for deterministic planning
    director = presentation_director
    director.max_retries = -1
    plan_spec = director.plan_presentation(ctx)
    return ctx, plan_spec


# -------------------------------------------------------------------------
# 1. PresentationPlanSpec unchanged by Granite
# -------------------------------------------------------------------------
def test_presentation_plan_spec_unchanged_by_granite():
    ctx, plan_spec = make_test_context()
    original_title = plan_spec.deck_title
    original_slide_count = len(plan_spec.slides)
    original_narrative_arc = plan_spec.narrative_strategy.arc_type

    orchestrator = PresentationExecutionOrchestrator(max_model_retries=-1)
    exec_plan = orchestrator.build_execution_plan(plan_spec, ctx)
    packages = orchestrator.execute_plan(exec_plan, ctx, plan_spec)

    assert plan_spec.deck_title == original_title
    assert len(plan_spec.slides) == original_slide_count
    assert plan_spec.narrative_strategy.arc_type == original_narrative_arc
    assert len(packages) == original_slide_count


# -------------------------------------------------------------------------
# 2. Slide count preserved under all modes
# -------------------------------------------------------------------------
@pytest.mark.parametrize("mode,target", [
    (SlideCountMode.FIXED, 4),
    (SlideCountMode.ADAPTIVE, 6),
    (SlideCountMode.MAXIMUM, 8),
    (SlideCountMode.RANGE, 5),
])
def test_slide_count_preserved_under_all_modes(mode, target):
    ctx, plan_spec = make_test_context(slide_count_mode=mode, target_slides=target)
    orchestrator = PresentationExecutionOrchestrator(max_model_retries=-1)
    exec_plan = orchestrator.build_execution_plan(plan_spec, ctx)
    packages = orchestrator.execute_plan(exec_plan, ctx, plan_spec)

    assert len(packages) == len(plan_spec.slides)


# -------------------------------------------------------------------------
# 3. Deterministic execution graph generation
# -------------------------------------------------------------------------
def test_deterministic_execution_graph_generation():
    ctx, plan_spec = make_test_context()
    orchestrator = PresentationExecutionOrchestrator(max_model_retries=-1)
    plan_1 = orchestrator.build_execution_plan(plan_spec, ctx)
    plan_2 = orchestrator.build_execution_plan(plan_spec, ctx)

    # Identical task topology and objectives
    assert len(plan_1.tasks) == len(plan_2.tasks)
    for t1, t2 in zip(plan_1.tasks, plan_2.tasks):
        assert t1.task_type == t2.task_type
        assert t1.executor == t2.executor
        assert t1.tool_name == t2.tool_name
        assert t1.objective == t2.objective


# -------------------------------------------------------------------------
# 4. Cycle detection in task graph
# -------------------------------------------------------------------------
def test_cycle_detection_in_task_graph():
    graph = ExecutionTaskGraph()
    graph.add_task(ExecutionTask(
        task_id="t-1",
        task_type=TaskType.FETCH_EVIDENCE,
        objective="Fetch",
        executor=ExecutorType.DETERMINISTIC_RETRIEVAL,
        dependencies=["t-2"]
    ))
    graph.add_task(ExecutionTask(
        task_id="t-2",
        task_type=TaskType.CALCULATE_METRIC,
        objective="Calc",
        executor=ExecutorType.DETERMINISTIC_ANALYTICS,
        dependencies=["t-1"]
    ))

    with pytest.raises(ValueError, match="Cyclic dependency detected"):
        graph.validate()


# -------------------------------------------------------------------------
# 5. Execution DAG resolution order
# -------------------------------------------------------------------------
def test_execution_dag_resolution_order():
    ctx, plan_spec = make_test_context()
    orchestrator = PresentationExecutionOrchestrator(max_model_retries=-1)
    exec_plan = orchestrator.build_execution_plan(plan_spec, ctx)
    graph = ExecutionTaskGraph.from_execution_plan(exec_plan)

    order = graph.get_topological_order()
    executed_ids = set()
    for task_id in order:
        task = graph.tasks[task_id]
        for dep in task.dependencies:
            assert dep in executed_ids, f"Dependency {dep} was not resolved before {task_id}"
        executed_ids.add(task_id)


# -------------------------------------------------------------------------
# 6. Parallel/wave execution logic
# -------------------------------------------------------------------------
def test_parallel_wave_execution_logic():
    ctx, plan_spec = make_test_context()
    orchestrator = PresentationExecutionOrchestrator(max_model_retries=-1)
    exec_plan = orchestrator.build_execution_plan(plan_spec, ctx)
    graph = ExecutionTaskGraph.from_execution_plan(exec_plan)

    results: dict[str, TaskResult] = {}
    # First wave should contain root tasks with 0 dependencies
    wave_1 = graph.get_ready_tasks(results)
    assert len(wave_1) >= 1
    assert all(len(t.dependencies) == 0 for t in wave_1)

    # Complete wave 1
    for t in wave_1:
        results[t.task_id] = TaskResult(task_id=t.task_id, status=TaskStatus.SUCCESS)

    # Second wave
    wave_2 = graph.get_ready_tasks(results)
    assert len(wave_2) > 0
    for t in wave_2:
        assert all(dep in results for dep in t.dependencies)


# -------------------------------------------------------------------------
# 7. Tool registry lookup and execution
# -------------------------------------------------------------------------
def test_tool_registry_lookup_and_execution():
    registry = ToolRegistry()
    assert len(registry.get_tool_definitions()) >= 10

    # Non-existent tool returns graceful error
    res_err = registry.execute_tool("non_existent_tool", foo="bar")
    assert res_err.status == "error"
    assert "not registered" in res_err.error


# -------------------------------------------------------------------------
# 8. Math calculation tool accuracy
# -------------------------------------------------------------------------
def test_math_calculation_tool_accuracy():
    registry = ToolRegistry()
    
    # Mean
    res_mean = registry.execute_tool("calculate_metric", metric_type="mean", values=[10.0, 20.0, 30.0])
    assert res_mean.data["value"] == 20.0

    # Percentage share
    res_pct = registry.execute_tool("calculate_metric", metric_type="percentage_share", values=[25.0, 75.0])
    assert res_pct.data["value"] == 25.0

    # Dispersion ratio
    res_disp = registry.execute_tool("calculate_metric", metric_type="dispersion_ratio", values=[18.4, 10.0])
    assert res_disp.data["value"] == 1.84

    # Surge delta
    res_surge = registry.execute_tool("calculate_metric", metric_type="surge_delta", baseline=100.0, comparison_value=125.0)
    assert res_surge.data["value"] == 25.0


# -------------------------------------------------------------------------
# 9. Aggregate data tool accuracy
# -------------------------------------------------------------------------
def test_aggregate_data_tool_accuracy():
    registry = ToolRegistry()
    records = [
        {"dept": "Engineering", "hours": 40},
        {"dept": "Engineering", "hours": 50},
        {"dept": "Sales", "hours": 30}
    ]
    res_agg = registry.execute_tool("aggregate_data", records=records, group_by="dept", metric_col="hours", agg_fn="sum")
    assert res_agg.status == "success"
    groups = {g["group"]: g["value"] for g in res_agg.data["aggregates"]}
    assert groups["Engineering"] == 90.0
    assert groups["Sales"] == 30.0


# -------------------------------------------------------------------------
# 10. Ranking tool accuracy
# -------------------------------------------------------------------------
def test_ranking_tool_accuracy():
    registry = ToolRegistry()
    categories = [
        {"category": "C", "count": 10},
        {"category": "A", "count": 50},
        {"category": "B", "count": 30}
    ]
    res = registry.execute_tool("rank_categories", categories=categories, top_n=2)
    assert res.status == "success"
    ranked = res.data["ranked"]
    assert len(ranked) == 2
    assert ranked[0]["category"] == "A"
    assert ranked[1]["category"] == "B"


# -------------------------------------------------------------------------
# 11. Outlier detection tool accuracy
# -------------------------------------------------------------------------
def test_outlier_detection_tool_accuracy():
    registry = ToolRegistry()
    records = [
        {"id": 1, "val": 10},
        {"id": 2, "val": 11},
        {"id": 3, "val": 12},
        {"id": 4, "val": 10},
        {"id": 5, "val": 999}  # Extreme outlier
    ]
    res = registry.execute_tool("detect_outliers", records=records, metric_col="val", method="iqr")
    assert res.status == "success"
    assert res.data["outlier_count"] == 1
    assert res.data["outliers"][0]["val"] == 999


# -------------------------------------------------------------------------
# 12. Trend detection tool accuracy
# -------------------------------------------------------------------------
def test_trend_detection_tool_accuracy():
    registry = ToolRegistry()
    records = [
        {"period": "2026-01", "throughput": 100},
        {"period": "2026-02", "throughput": 120},
        {"period": "2026-03", "throughput": 150}
    ]
    res = registry.execute_tool("detect_trend", records=records, time_col="period", value_col="throughput")
    assert res.status == "success"
    assert res.data["direction"] == "increasing"
    assert res.data["total_change_pct"] == 50.0


# -------------------------------------------------------------------------
# 13. Chart data preparation
# -------------------------------------------------------------------------
def test_chart_data_preparation():
    registry = ToolRegistry()
    series = [
        {"name": "Engineering", "values": [10, 20, 30]},
        {"name": "Sales", "values": [5, 15, 25]}
    ]
    res = registry.execute_tool("prepare_chart_data", visual_type="line_chart", categories=["Q1", "Q2", "Q3"], series=series)
    assert res.status == "success"
    chart = res.data["chart_data"]
    assert chart["type"] == "line"
    assert len(chart["series"]) == 2


# -------------------------------------------------------------------------
# 14. Table data preparation
# -------------------------------------------------------------------------
def test_table_data_preparation():
    registry = ToolRegistry()
    headers = ["Department", "Headcount", "Dispersion"]
    rows = [["Engineering", "145", "1.2x"], ["Operations", "210", "1.8x"]]
    res = registry.execute_tool("prepare_table_data", headers=headers, rows=rows)
    assert res.status == "success"
    assert res.data["table_data"]["headers"] == headers
    assert len(res.data["table_data"]["rows"]) == 2


# -------------------------------------------------------------------------
# 15. Phi-4 Mini verification invocation
# -------------------------------------------------------------------------
def test_phi4_mini_verification_invocation():
    verifier = PhiAnalyticalVerifier(max_retries=-1)
    # Valid percentage change: baseline 100, current 125 -> +25%
    valid_res = verifier.verify_metric(
        metric_name="Growth Rate",
        reported_value=25.0,
        inputs={"baseline": 100.0, "current": 125.0},
        calculation_method="Percentage change"
    )
    assert valid_res["valid"] is True
    assert len(valid_res["discrepancies"]) == 0

    # Discrepancy: reported 40.0 but actual is 25.0
    invalid_res = verifier.verify_metric(
        metric_name="Growth Rate",
        reported_value=40.0,
        inputs={"baseline": 100.0, "current": 125.0},
        calculation_method="Percentage change"
    )
    assert invalid_res["valid"] is False
    assert len(invalid_res["discrepancies"]) > 0


# -------------------------------------------------------------------------
# 16. DeepSeek-R1 escalation invocation
# -------------------------------------------------------------------------
def test_deepseek_r1_escalation_invocation():
    reasoner = DeepSeekReasoner(max_retries=-1)
    conflict_desc = "Regional discrepancy between East (+12%) and West (-8%)"
    conflicting_ev = [
        {"metric_name": "East Throughput", "value": "+12%", "confidence": 0.95},
        {"metric_name": "West Throughput", "value": "-8%", "confidence": 0.85}
    ]
    res = reasoner.resolve_conflict(conflict_desc, conflicting_ev)
    assert res["resolved"] is True
    assert "East" in res["recommended_precedence"] or "Throughput" in res["recommended_precedence"]
    assert res["confidence"] >= 0.8


# -------------------------------------------------------------------------
# 17. Missing evidence detection and handling
# -------------------------------------------------------------------------
def test_missing_evidence_detection_and_handling():
    registry = ToolRegistry()
    # Ledger with only EVID-01
    ledger = [{"evidence_id": "EVID-01", "title": "Verified Baseline"}]
    res = registry.execute_tool("fetch_evidence", evidence_ids=["EVID-MISSING-99"], evidence_ledger=ledger)
    assert res.status == "empty"
    assert res.data["matched_count"] == 0
    assert len(res.evidence_ids) == 0


# -------------------------------------------------------------------------
# 18. Provenance retention across all tasks
# -------------------------------------------------------------------------
def test_provenance_retention_across_all_tasks():
    ctx, plan_spec = make_test_context()
    orchestrator = PresentationExecutionOrchestrator(max_model_retries=-1)
    exec_plan = orchestrator.build_execution_plan(plan_spec, ctx)

    context_dict = {
        "evidence_ledger": ctx.current_evidence,
        "retrieval_context": ctx.historical_context,
        "dataset_id": ctx.dataset_label
    }

    # Execute fetch task and verify provenance
    fetch_task = next(t for t in exec_plan.tasks if t.task_type == TaskType.FETCH_EVIDENCE and t.slide_id)
    res = execute_deterministic_task(fetch_task, orchestrator.tool_registry, context_dict)
    assert res.status == TaskStatus.SUCCESS
    assert len(res.evidence_ids) > 0
    assert res.dataset_ids == [ctx.dataset_label]
    assert res.calculation_method != ""


# -------------------------------------------------------------------------
# 19. Retry limit enforcement
# -------------------------------------------------------------------------
def test_retry_limit_enforcement():
    orchestrator = PresentationExecutionOrchestrator(max_tool_retries=2, max_model_retries=1)
    assert orchestrator.max_tool_retries == 2
    assert orchestrator.max_model_retries == 1

    ctx, plan_spec = make_test_context()
    exec_plan = orchestrator.build_execution_plan(plan_spec, ctx)

    for task in exec_plan.tasks:
        if task.executor in (
            ExecutorType.DETERMINISTIC_ANALYTICS,
            ExecutorType.DETERMINISTIC_RETRIEVAL,
            ExecutorType.DETERMINISTIC_FORMATTER,
            ExecutorType.EXISTING_CLAIM_VERIFIER
        ):
            assert task.max_retries <= 2
        else:
            assert task.max_retries <= 1


# -------------------------------------------------------------------------
# 20. Error category assignment
# -------------------------------------------------------------------------
def test_error_category_assignment():
    ctx, plan_spec = make_test_context()
    orchestrator = PresentationExecutionOrchestrator(max_model_retries=-1)
    exec_plan = orchestrator.build_execution_plan(plan_spec, ctx)

    # Fail a task with an unknown tool
    failing_task = ExecutionTask(
        task_id="bad-task",
        task_type=TaskType.ANALYZE_DATA,
        objective="Fail intentionally",
        executor=ExecutorType.DETERMINISTIC_ANALYTICS,
        tool_name="non_existent_tool_123"
    )
    res = execute_deterministic_task(failing_task, orchestrator.tool_registry, {})
    assert res.status == TaskStatus.FAILED
    assert res.error_category == ErrorCategory.TOOL_FAILURE


# -------------------------------------------------------------------------
# 21. Concurrency handling
# -------------------------------------------------------------------------
def test_concurrency_handling():
    ctx, plan_spec = make_test_context()
    orchestrator = PresentationExecutionOrchestrator(max_model_retries=-1)
    exec_plan = orchestrator.build_execution_plan(plan_spec, ctx)

    # Multiple ready tasks in early wave
    graph = ExecutionTaskGraph.from_execution_plan(exec_plan)
    graph.mark_completed("task-global-evidence-fetch", TaskResult(task_id="task-global-evidence-fetch", status=TaskStatus.SUCCESS))
    ready = graph.get_ready_tasks()
    # Multiple slide-level fetch tasks should be concurrently ready
    assert len(ready) == len(plan_spec.slides)


# -------------------------------------------------------------------------
# 22. Slide package assembly
# -------------------------------------------------------------------------
def test_slide_package_assembly():
    ctx, plan_spec = make_test_context()
    orchestrator = PresentationExecutionOrchestrator(max_model_retries=-1)
    exec_plan = orchestrator.build_execution_plan(plan_spec, ctx)
    packages = orchestrator.execute_plan(exec_plan, ctx, plan_spec)

    assert len(packages) == len(plan_spec.slides)
    for pkg in packages:
        assert isinstance(pkg, SlideExecutionPackage)
        assert pkg.slide_id.startswith("slide_")
        assert len(pkg.headline) > 5
        assert isinstance(pkg.resolved_content.get("bullet_points"), list)
        assert pkg.verified is True
        assert len(pkg.execution_trace) > 0


# -------------------------------------------------------------------------
# 23. Claim verifier integration
# -------------------------------------------------------------------------
def test_claim_verifier_integration():
    ctx, plan_spec = make_test_context()
    orchestrator = PresentationExecutionOrchestrator(max_model_retries=-1)
    deck_spec, _ = orchestrator.orchestrate(
        plan_spec=plan_spec,
        ctx=ctx,
        theme={},
        theme_id="executive_dark",
        evidence_ledger=ctx.current_evidence
    )

    verification_res = verify_presentation_claims(deck_spec, deck_spec["evidence_ledger"])
    assert verification_res["discrepancies_flagged"] == 0
    assert verification_res["status"] == "PASSED"


# -------------------------------------------------------------------------
# 24. Quality auditor integration
# -------------------------------------------------------------------------
def test_quality_auditor_integration():
    ctx, plan_spec = make_test_context()
    chart_pack = {
        "line_chart": {
            "chart_type": "line",
            "title": "Weekly Throughput Velocity",
            "categories": ["W1", "W2", "W3", "W4"],
            "series": [{"name": "Throughput", "values": [120.0, 140.0, 135.0, 160.0]}]
        },
        "bar_chart": {
            "chart_type": "bar",
            "title": "Regional Spread",
            "categories": ["North", "South", "East", "West"],
            "series": [{"name": "Score", "values": [90.0, 75.0, 82.0, 68.0]}]
        },
        "donut_chart": {
            "chart_type": "donut",
            "title": "Category Allocation",
            "categories": ["Engineering", "Operations", "Sales"],
            "series": [{"name": "Headcount", "values": [6200, 4100, 4200]}]
        }
    }
    orchestrator = PresentationExecutionOrchestrator(max_model_retries=-1)
    deck_spec, _ = orchestrator.orchestrate(
        plan_spec=plan_spec,
        ctx=ctx,
        theme={"id": "executive_dark", "background": "#0F172A", "primary": "#38BDF8", "secondary": "#94A3B8"},
        theme_id="executive_dark",
        chart_pack=chart_pack,
        evidence_ledger=ctx.current_evidence
    )

    audit_res = PresentationQualityAuditor.audit_deck_spec(deck_spec, deck_spec["evidence_ledger"])
    assert audit_res.get("critical_count", 0) == 0


# -------------------------------------------------------------------------
# 25. Graceful fallback when Granite disabled
# -------------------------------------------------------------------------
def test_graceful_fallback_when_granite_disabled():
    ctx, plan_spec = make_test_context()
    orchestrator = PresentationExecutionOrchestrator(enabled=False, max_model_retries=-1)
    deck_spec, packages = orchestrator.orchestrate(
        plan_spec=plan_spec,
        ctx=ctx,
        theme={},
        theme_id="executive_dark",
        evidence_ledger=ctx.current_evidence
    )

    assert len(packages) == len(plan_spec.slides)
    assert len(deck_spec["slides"]) == len(plan_spec.slides)
    assert deck_spec["orchestrator_metadata"]["total_slides"] == len(plan_spec.slides)


# -------------------------------------------------------------------------
# 26. Graceful fallback when Granite fails
# -------------------------------------------------------------------------
def test_graceful_fallback_when_granite_fails():
    ctx, plan_spec = make_test_context()
    orchestrator = PresentationExecutionOrchestrator(enabled=True, max_model_retries=1)

    # Patch ModelGateway to raise an unexpected runtime error during Granite copy generation
    with patch("app.services.gateway.model_gateway.ModelGateway.generate", side_effect=RuntimeError("Ollama connection reset")):
        deck_spec, packages = orchestrator.orchestrate(
            plan_spec=plan_spec,
            ctx=ctx,
            theme={},
            theme_id="executive_dark",
            evidence_ledger=ctx.current_evidence
        )

    # Must not crash, but gracefully use deterministic plan fallback
    assert len(packages) == len(plan_spec.slides)
    assert len(deck_spec["slides"]) == len(plan_spec.slides)


# -------------------------------------------------------------------------
# 27. Native PPTX export from orchestrator-produced deck
# -------------------------------------------------------------------------
def test_native_pptx_export_from_orchestrator_produced_deck(tmp_path):
    ctx, plan_spec = make_test_context()
    orchestrator = PresentationExecutionOrchestrator(max_model_retries=-1)
    deck_spec, _ = orchestrator.orchestrate(
        plan_spec=plan_spec,
        ctx=ctx,
        theme={"id": "executive_dark", "background": "#0F172A", "primary": "#38BDF8", "secondary": "#94A3B8"},
        theme_id="executive_dark",
        evidence_ledger=ctx.current_evidence
    )

    pptx_path = export_spec_to_pptx(deck_spec)
    assert Path(pptx_path).exists()
    assert Path(pptx_path).stat().st_size > 1000
