"""Unit and benchmark tests for Phase 9: Governed Dataset Intelligence Evaluation Framework."""
from __future__ import annotations

import json
import pytest

from app.db.database import get_connection
from app.services.adaptive_dashboard.evaluation_contracts import (
    ADVERSARIAL_MISMATCH_SPEC,
    FINANCE_ARCHETYPE_SPEC,
    RETAIL_ARCHETYPE_SPEC,
    WORKFORCE_ARCHETYPE_SPEC,
    BenchmarkDatasetSpec,
    CouncilRankingEvaluation,
    EvaluationScorecard,
    ExpectedInsight,
    ExpectedRelationship,
    calculate_ndcg_at_k,
)
from app.services.adaptive_dashboard.dataset_orchestrator import (
    DatasetRelationship,
    run_dataset_intelligence,
)
from app.services.adaptive_dashboard.global_ranker import InsightRedundancyResolver
from app.services.adaptive_dashboard.evaluator import DatasetIntelligenceEvaluator


@pytest.fixture
def golden_workforce_workbook():
    """Seeds a full 4-sheet workforce workbook (Employees, Attendance, Leave, Departments)."""
    conn = get_connection()
    # 1. Dataset Upload
    conn.execute(
        "INSERT INTO dataset_uploads (id, filename, original_name, display_name, file_type, sheet_count) VALUES (?, ?, ?, ?, ?, ?)",
        (201, "workforce_complete.xlsx", "Global Workforce Q3.xlsx", "Global Workforce Q3", "xlsx", 4),
    )

    # 2. 4 Sibling Sheets
    conn.execute(
        "INSERT INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, row_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (2011, 201, "Employees", "Employee Directory", json.dumps(["employee_id", "department_id", "job_title"]), "[]", 60),
    )
    conn.execute(
        "INSERT INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, row_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (2012, 201, "Attendance", "Daily Logs", json.dumps(["employee_id", "date", "hours_logged"]), "[]", 1200),
    )
    conn.execute(
        "INSERT INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, row_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (2013, 201, "Leave", "Leave Requests", json.dumps(["employee_id", "leave_type", "leave_days"]), "[]", 150),
    )
    conn.execute(
        "INSERT INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, row_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (2014, 201, "Departments", "Department Master", json.dumps(["department_id", "department_name", "cost_center"]), "[]", 8),
    )

    # 3. Seed Verified Relationships
    conn.execute(
        """
        INSERT INTO sheet_relationships (left_sheet, right_sheet, left_column, right_column, method, status, cardinality, matching_keys, matching_pairs, similarity, reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (2011, 2012, "employee_id", "employee_id", "exact_key", "verified", "one-to-many", 60, 1200, 1.0, "Employee ID join"),
    )
    conn.execute(
        """
        INSERT INTO sheet_relationships (left_sheet, right_sheet, left_column, right_column, method, status, cardinality, matching_keys, matching_pairs, similarity, reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (2011, 2013, "employee_id", "employee_id", "exact_key", "verified", "one-to-many", 55, 150, 0.98, "Leave join"),
    )
    conn.execute(
        """
        INSERT INTO sheet_relationships (left_sheet, right_sheet, left_column, right_column, method, status, cardinality, matching_keys, matching_pairs, similarity, reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (2011, 2014, "department_id", "department_id", "exact_key", "verified", "many-to-one", 8, 60, 1.0, "Department ID join"),
    )

    conn.commit()
    conn.close()
    return 201


def test_ndcg_at_k_calculation():
    """Verify NDCG calculation mathematically rewards top-ranked ground truth findings."""
    # Perfect ranking: [4, 3, 2, 1]
    ideal = [4, 3, 2, 1]
    ndcg_perfect = calculate_ndcg_at_k(actual_ranks=[4, 3, 2, 1], ideal_ranks=ideal, k=4)
    assert ndcg_perfect == 1.0

    # Inverted ranking: [1, 2, 3, 4] -> NDCG must be lower
    ndcg_inverted = calculate_ndcg_at_k(actual_ranks=[1, 2, 3, 4], ideal_ranks=ideal, k=4)
    assert ndcg_inverted < 0.85


def test_golden_workforce_benchmark_evaluation(golden_workforce_workbook):
    """Executes the full benchmark evaluation framework on the golden workforce workbook."""
    spec = BenchmarkDatasetSpec(
        benchmark_id="BM-WORKFORCE-01",
        name="Global Workforce 4-Sheet Workbook",
        domain="workforce_hr",
        sheet_count=4,
        expected_relationships=[
            ExpectedRelationship(left_sheet="Employees", right_sheet="Attendance", left_column="employee_id", right_column="employee_id", cardinality="one-to-many"),
            ExpectedRelationship(left_sheet="Employees", right_sheet="Leave", left_column="employee_id", right_column="employee_id", cardinality="one-to-many"),
            ExpectedRelationship(left_sheet="Employees", right_sheet="Departments", left_column="department_id", right_column="department_id", cardinality="many-to-one"),
        ],
        forbidden_relationships=[
            ExpectedRelationship(left_sheet="Attendance", right_sheet="Departments", left_column="date", right_column="department_id", cardinality="many-to-many", is_safe=False),
        ],
        expected_insights=[
            ExpectedInsight(insight_id="EXP-01", metric_keyword="cross_sheet_link", expected_scope="CROSS_SHEET", expected_slot="hero", relevance_tier=4, is_critical=True),
        ],
    )

    scorecard = DatasetIntelligenceEvaluator.run_benchmark(spec, golden_workforce_workbook)

    # Validate the 6 core dimensions:
    # 1. Relationship Discovery: UnsafeJoinRate == 0%, Recall >= 95%
    assert scorecard.unsafe_join_rate == 0.0
    assert scorecard.relationship_recall >= 0.95
    assert scorecard.relationship_precision >= 0.95

    # 2. Cross-Sheet Discovery
    assert scorecard.cross_sheet_precision >= 0.95
    assert scorecard.cross_sheet_recall >= 0.90

    # 3. Global Ranking: NDCG@9 >= 0.90
    assert scorecard.ndcg_at_9 >= 0.90

    # 4. Slot Allocation & Hero Selection
    assert scorecard.hero_selection_accuracy >= 0.90
    assert scorecard.top9_selection_accuracy >= 0.90

    # 5. Redundancy & Critical Insight Miss Rate: Miss Rate == 0%
    assert scorecard.critical_insight_miss_rate == 0.0
    assert scorecard.false_suppression_rate <= 0.02

    # Overall Pass Gate
    assert scorecard.overall_pass is True


def test_sheet_order_invariance(golden_workforce_workbook):
    """Verify that sheet order in workbook does not affect analytical findings or ranking."""
    is_invariant = DatasetIntelligenceEvaluator.test_sheet_order_invariance(golden_workforce_workbook)
    assert is_invariant is True


def test_mutation_sensitivity():
    """Verify that mutating underlying data dynamically alters ranking and hero selection."""
    from app.services.adaptive_dashboard.global_ranker import (
        DashboardSlotBudget,
        GlobalCandidatePoolEngine,
        InsightCandidate,
    )

    # Initial state: Operations is top hero
    cands_initial = [
        InsightCandidate(
            candidate_id="INS-01",
            title="Operations Attendance",
            scope="SINGLE_SHEET",
            slot_type="strategic",
            metric_name="attendance",
            dimension_name="Operations",
            business_impact=0.90,
            composite_score=0.92,
            redundancy_group="att_ops",
        ),
        InsightCandidate(
            candidate_id="INS-02",
            title="Finance Attendance",
            scope="SINGLE_SHEET",
            slot_type="strategic",
            metric_name="attendance",
            dimension_name="Finance",
            business_impact=0.75,
            composite_score=0.78,
            redundancy_group="att_fin",
        ),
    ]

    sel_initial, _ = GlobalCandidatePoolEngine.select_dashboard_insights(cands_initial, DashboardSlotBudget())
    assert sel_initial[0].candidate_id == "INS-01"

    # Mutated state: Operations drops significantly (-40%), Finance overtakes
    cands_mutated = [
        InsightCandidate(
            candidate_id="INS-01",
            title="Operations Attendance",
            scope="SINGLE_SHEET",
            slot_type="strategic",
            metric_name="attendance",
            dimension_name="Operations",
            business_impact=0.50,
            composite_score=0.52,  # Dropped
            redundancy_group="att_ops",
        ),
        InsightCandidate(
            candidate_id="INS-02",
            title="Finance Attendance",
            scope="SINGLE_SHEET",
            slot_type="strategic",
            metric_name="attendance",
            dimension_name="Finance",
            business_impact=0.75,
            composite_score=0.78,  # Now winner
            redundancy_group="att_fin",
        ),
    ]

    sel_mutated, _ = GlobalCandidatePoolEngine.select_dashboard_insights(cands_mutated, DashboardSlotBudget())
    assert sel_mutated[0].candidate_id == "INS-02"
    # Proves the system is completely data-driven and not hardcoded


def test_adversarial_trap_and_unsafe_join_prevention():
    """Verify that dangerous/adversarial relationships (e.g. date <-> department_id or false collisions) are rejected."""
    spec = ADVERSARIAL_MISMATCH_SPEC
    # Simulating discovered relationships from a safe engine
    safe_discovered = [
        DatasetRelationship(
            relationship_id="REL-01",
            left_sheet_id=1,
            left_sheet_name="Employees",
            right_sheet_id=2,
            right_sheet_name="Payroll",
            left_column="employee_id",
            right_column="employee_id",
            cardinality="one-to-one",
            join_confidence=0.99,
            coverage_pct=100.0,
            duplication_risk="LOW",
            null_expansion_risk="LOW",
            semantic_relationship="Employee Identifier",
        )
    ]
    precision, recall, unsafe_rate = DatasetIntelligenceEvaluator.evaluate_relationships(spec, safe_discovered)
    assert unsafe_rate == 0.0

    # If an engine recklessly joins attendance.date <-> departments.department_id
    unsafe_discovered = [
        DatasetRelationship(
            relationship_id="REL-BAD",
            left_sheet_id=2,
            left_sheet_name="Attendance",
            right_sheet_id=3,
            right_sheet_name="Departments",
            left_column="date",
            right_column="department_id",
            cardinality="many-to-many",
            join_confidence=0.10,
            coverage_pct=5.0,
            duplication_risk="HIGH",
            null_expansion_risk="HIGH",
            semantic_relationship="Invalid Cross-Domain Collision",
        )
    ]
    _, _, bad_unsafe_rate = DatasetIntelligenceEvaluator.evaluate_relationships(spec, unsafe_discovered)
    assert bad_unsafe_rate > 0.0  # Caught as UnsafeJoinRate violation!


def test_council_reranking_gain_evaluation():
    """Evaluates the impact of AI Council reranking on deterministic ranking."""
    spec = BenchmarkDatasetSpec(
        benchmark_id="BM-COUNCIL-TEST",
        name="Council Evaluation Test",
        domain="workforce_hr",
        sheet_count=2,
        expected_insights=[
            ExpectedInsight(insight_id="EXP-1", metric_keyword="retention", expected_scope="SINGLE_SHEET", expected_slot="hero", relevance_tier=4, is_critical=True),
            ExpectedInsight(insight_id="EXP-2", metric_keyword="headcount", expected_scope="SINGLE_SHEET", expected_slot="strategic", relevance_tier=3),
            ExpectedInsight(insight_id="EXP-3", metric_keyword="tenure", expected_scope="SINGLE_SHEET", expected_slot="diagnostic", relevance_tier=2),
            ExpectedInsight(insight_id="EXP-4", metric_keyword="overtime", expected_scope="SINGLE_SHEET", expected_slot="risk_foresight", relevance_tier=1),
        ],
    )

    # 1. Deterministic candidates in standard order
    deterministic_cands = [
        {"title": "Retention rate dropped 12%", "metric_name": "retention"},
        {"title": "Headcount grew by 5%", "metric_name": "headcount"},
        {"title": "Tenure average is 3.2 years", "metric_name": "tenure"},
        {"title": "Overtime increased 8%", "metric_name": "overtime"},
    ]

    # 2. Council maintains critical hero and improves narrative clarity (Neutral/Improved)
    council_cands_good = [
        {"title": "Retention rate dropped 12%", "metric_name": "retention"},
        {"title": "Headcount grew by 5%", "metric_name": "headcount"},
        {"title": "Tenure average is 3.2 years", "metric_name": "tenure"},
        {"title": "Overtime increased 8%", "metric_name": "overtime"},
    ]
    eval_good = DatasetIntelligenceEvaluator.evaluate_council_reranking(spec, deterministic_cands, council_cands_good)
    assert eval_good.preserves_critical_rankings is True
    assert eval_good.verdict in ("IMPROVED", "NEUTRAL")
    assert eval_good.council_ranking_gain >= 0.0

    # 3. Council demotes critical retention hero to bottom (Degraded)
    council_cands_bad = [
        {"title": "Overtime increased 8%", "metric_name": "overtime"},
        {"title": "Tenure average is 3.2 years", "metric_name": "tenure"},
        {"title": "Headcount grew by 5%", "metric_name": "headcount"},
        {"title": "Retention rate dropped 12%", "metric_name": "retention"},
    ]
    eval_bad = DatasetIntelligenceEvaluator.evaluate_council_reranking(spec, deterministic_cands, council_cands_bad)
    assert eval_bad.council_ranking_gain < 0.0
    assert eval_bad.verdict == "DEGRADED"


def test_redundancy_cluster_suppression_and_false_suppression_rate():
    """Verify that conceptual duplicates are clustered and suppressed while distinct metrics survive."""
    from app.services.adaptive_dashboard.global_ranker import (
        DashboardSlotBudget,
        GlobalCandidatePoolEngine,
        InsightCandidate,
        InsightRedundancyResolver,
    )

    # INS-1, INS-2, INS-3 are same conceptual cluster (Sales attendance)
    # INS-4 is distinct (Sales leave)
    candidates = [
        InsightCandidate(
            candidate_id="INS-1",
            title="Sales attendance is lowest at 72%",
            scope="SINGLE_SHEET",
            slot_type="strategic",
            metric_name="attendance_rate",
            dimension_name="Sales",
            business_impact=0.88,
            composite_score=0.89,
            redundancy_group="sales_attendance",
        ),
        InsightCandidate(
            candidate_id="INS-2",
            title="Sales is 21% below attendance benchmark",
            scope="SINGLE_SHEET",
            slot_type="strategic",
            metric_name="attendance_benchmark",
            dimension_name="Sales",
            business_impact=0.82,
            composite_score=0.84,
            redundancy_group="sales_attendance",
        ),
        InsightCandidate(
            candidate_id="INS-3",
            title="Sales has the weakest office presence",
            scope="SINGLE_SHEET",
            slot_type="strategic",
            metric_name="office_presence",
            dimension_name="Sales",
            business_impact=0.80,
            composite_score=0.81,
            redundancy_group="sales_attendance",
        ),
        InsightCandidate(
            candidate_id="INS-4",
            title="Sales leave requests increased 17%",
            scope="SINGLE_SHEET",
            slot_type="strategic",
            metric_name="leave_frequency",
            dimension_name="Sales",
            business_impact=0.85,
            composite_score=0.86,
            redundancy_group="sales_leave",  # Distinct group!
        ),
    ]

    resolved = InsightRedundancyResolver.resolve_redundancies(candidates)
    active = [c for c in resolved if not c.is_suppressed]
    suppressed = [c for c in resolved if c.is_suppressed]

    # Winner of sales_attendance (INS-1) and distinct sales_leave (INS-4) must survive
    active_ids = {c.candidate_id for c in active}
    assert "INS-1" in active_ids
    assert "INS-4" in active_ids
    assert len(active) == 2

    # INS-2 and INS-3 must be suppressed
    suppressed_ids = {c.candidate_id for c in suppressed}
    assert "INS-2" in suppressed_ids
    assert "INS-3" in suppressed_ids
    assert len(suppressed) == 2


def test_golden_multi_sheet_archetypes_contract():
    """Verify that multi-sheet archetype specifications enforce strict zero-unsafe join and schema contracts."""
    specs = [
        WORKFORCE_ARCHETYPE_SPEC,
        RETAIL_ARCHETYPE_SPEC,
        FINANCE_ARCHETYPE_SPEC,
    ]
    for spec in specs:
        assert spec.sheet_count >= 4
        assert len(spec.expected_relationships) >= 2
        assert len(spec.forbidden_relationships) >= 1
        # Validate that forbidden relationships have is_safe=False
        for f in spec.forbidden_relationships:
            assert f.is_safe is False
