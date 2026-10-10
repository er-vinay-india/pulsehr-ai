"""Benchmark Test Suite for Visual Decision Intelligence.

Verifies:
1. Intent-first visual decisions (not purely shape-based)
2. Standard benchmark cases (Sales trend, Department ranking, Workforce capacity, Waterfall budget, Bullet target, Scatter price)
3. Decision Traps:
   - Time dimension + composition question -> NOT automatically LINE
   - Incompatible units -> blocked from single unscaled axis
   - employee-days -> NEVER labeled simply "days"
   - Correlation -> NEVER permitted causal claims without proof
   - Magnitude scale disparity (>3x) -> penalizes flat multi-line, selects 100% stacked bar
   - Unresolved metric grain -> VISUALIZATION_BLOCKED
   - Immutable audit trail generation
"""
import pytest

from app.services.adaptive_dashboard.visual_decision import (
    AnalyticalIntent,
    AnalyticalIntentClassifier,
    AudienceType,
    ChartSuitabilityRanker,
    ChartType,
    MetricSemantics,
    VisualDecisionAudit,
    VisualDecisionEngine,
    VisualQuestion,
    VisualQuestionBuilder,
    VisualSemanticValidator,
)


def test_intent_classification_distinguishes_composition_from_trend():
    """Confirms attendance + leave over time is recognized as COMPOSITION + GAP_EXPLANATION, not raw trend."""
    question = "How is weekly workforce capacity distributed between attendance and approved leave?"
    intent, sec_intent = AnalyticalIntentClassifier.classify(
        question,
        finding_context={"measures": ["office_attendance", "approved_leave"], "is_temporal": True}
    )
    assert intent == AnalyticalIntent.COMPOSITION
    assert sec_intent == AnalyticalIntent.GAP_EXPLANATION


def test_benchmark_case_weekly_sales_over_12_months():
    """Weekly sales progression over 12 months selects LINE."""
    decision = VisualDecisionEngine.decide_visual(
        visual_id="VIS-SALES-TREND",
        question_text="How have weekly retail sales trended over the past 12 months?",
        primary_dimension="week",
        measures=["weekly_sales"],
        dimension_cardinality=52,
        is_temporal_dimension=True,
        provided_units={"weekly_sales": "usd"},
    )
    assert decision["status"] == "VALIDATED"
    assert decision["analytical_intent"] == "TREND"
    assert decision["chart_type"] == "line"


def test_benchmark_case_department_ranking():
    """Department comparison with policy threshold selects HORIZONTAL_BAR."""
    decision = VisualDecisionEngine.decide_visual(
        visual_id="VIS-DEPT-RANKING",
        question_text="Which department has the largest attendance gap against the governed policy target?",
        primary_dimension="department",
        measures=["office_days"],
        dimension_cardinality=8,
        is_temporal_dimension=False,
        provided_units={"office_days": "employee_day"},
    )
    assert decision["status"] == "VALIDATED"
    assert decision["analytical_intent"] == "RANKING"
    assert decision["chart_type"] == "horizontal_bar"


def test_benchmark_case_workforce_capacity_composition():
    """Attendance + leave across weekly cycles selects 100_PERCENT_STACKED_BAR, NOT LINE."""
    decision = VisualDecisionEngine.decide_visual(
        visual_id="VIS-WORKFORCE-CAPACITY",
        question_text="How is expected workforce capacity distributed between attendance and approved leave?",
        primary_dimension="week",
        measures=["office_attendance", "approved_leave"],
        dimension_cardinality=5,
        is_temporal_dimension=True,
        series_data={
            "office_attendance": [136.0, 142.0, 130.0, 145.0, 138.0],
            "approved_leave": [12.0, 15.0, 18.0, 10.0, 14.0],
        },
        provided_units={"office_attendance": "employee_day", "approved_leave": "employee_day"},
    )
    assert decision["status"] == "VALIDATED"
    assert decision["analytical_intent"] == "COMPOSITION"
    assert decision["chart_type"] == "100_percent_stacked_bar"
    assert decision["series_magnitude_ratio"] >= 8.0
    # Line chart must be penalized
    audit = decision["audit"]
    rejected = [r["chart_type"] for r in audit["rejected_alternatives"]]
    assert "line" in rejected


def test_benchmark_case_budget_expense_waterfall():
    """Budget vs expense gap explanation selects WATERFALL."""
    decision = VisualDecisionEngine.decide_visual(
        visual_id="VIS-BUDGET-WATERFALL",
        question_text="What is the waterfall contribution bridging initial budget to realized expense variance?",
        primary_dimension="cost_category",
        measures=["variance_amount"],
        dimension_cardinality=6,
        is_temporal_dimension=False,
        provided_units={"variance_amount": "usd"},
    )
    assert decision["status"] == "VALIDATED"
    assert decision["chart_type"] == "waterfall"


def test_benchmark_case_actual_vs_policy_target():
    """Compliance adherence against target selects BULLET_BAR."""
    decision = VisualDecisionEngine.decide_visual(
        visual_id="VIS-POLICY-TARGET",
        question_text="What is the actual adherence against the policy compliance target benchmark?",
        primary_dimension="cohort",
        measures=["compliance_rate"],
        dimension_cardinality=4,
        is_temporal_dimension=False,
        provided_units={"compliance_rate": "percent"},
    )
    assert decision["status"] == "VALIDATED"
    assert decision["analytical_intent"] == "TARGET_VS_ACTUAL"
    assert decision["chart_type"] == "bullet_bar"


def test_benchmark_case_price_vs_sales_scatter():
    """Relationship between continuous price and sales selects SCATTER."""
    decision = VisualDecisionEngine.decide_visual(
        visual_id="VIS-PRICE-SALES",
        question_text="What is the relationship between unit price and sales volume across items?",
        primary_dimension="item_sku",
        measures=["unit_price", "sales_volume"],
        dimension_cardinality=100,
        is_temporal_dimension=False,
        provided_units={"unit_price": "usd", "sales_volume": "count"},
    )
    assert decision["status"] == "VALIDATED"
    assert decision["analytical_intent"] == "RELATIONSHIP"
    assert decision["chart_type"] == "scatter"


def test_trap_time_dimension_does_not_imply_line_for_composition():
    """Guarantees that a temporal dimension does NOT automatically default to a line chart when intent is composition."""
    question = VisualQuestionBuilder.build_question(
        question_text="How is total workforce capacity distributed by week?",
        primary_dimension="week",
        measures=["attendance", "leave"],
        dimension_cardinality=4,
        is_temporal_dimension=True,
        provided_units={"attendance": "employee_day", "leave": "employee_day"},
    )
    assert question.intent == AnalyticalIntent.COMPOSITION

    ranked = ChartSuitabilityRanker.rank_candidates(question, series_magnitude_ratio=5.0)
    top_chart = ranked[0].chart_type
    assert top_chart == ChartType.ONE_HUNDRED_PERCENT_STACKED_BAR

    # Line chart must have high ambiguity and clutter penalty
    line_score = next(r for r in ranked if r.chart_type == ChartType.LINE)
    assert line_score.ambiguity_penalty > 0.30
    assert line_score.clutter_penalty > 0.30


def test_trap_incompatible_units_cannot_share_single_axis():
    """Incompatible units (e.g. USD and Percent) on a single axis are blocked."""
    q = VisualQuestionBuilder.build_question(
        question_text="Comparison of revenue and discount rate over time",
        primary_dimension="month",
        measures=["revenue_usd", "discount_pct"],
        dimension_cardinality=12,
        is_temporal_dimension=True,
        provided_units={"revenue_usd": "usd", "discount_pct": "percent"},
    )
    is_valid, reason = VisualSemanticValidator.validate_visual_plan(
        question=q,
        selected_chart=ChartType.LINE,
        title="Revenue and Discount",
        takeaway="Comparing revenue and discounts.",
    )
    assert is_valid is False
    assert "INCOMPATIBLE_UNITS" in reason


def test_trap_employee_days_never_labeled_simply_days():
    """Unit fidelity guard: employee_day measures cannot be displayed as plain 'days'."""
    q = VisualQuestion(
        question="What was average attendance?",
        intent=AnalyticalIntent.RANKING,
        primary_dimension="department",
        measures=["attendance"],
        metric_semantics=[
            MetricSemantics(
                metric_name="attendance",
                semantic_role="MEASURE",
                unit="employee_day",
                display_unit="days",  # Violates fidelity!
                aggregation="SUM",
                grain="employee × working_day",
            )
        ]
    )
    is_valid, reason = VisualSemanticValidator.validate_visual_plan(
        question=q,
        selected_chart=ChartType.HORIZONTAL_BAR,
        title="Attendance",
        takeaway="Observed attendance.",
    )
    assert is_valid is False
    assert "METRIC_UNIT_MISMATCH" in reason


def test_trap_unresolved_metric_grain_blocks_visualization():
    """Hard requirement: No chart generated if metric grain or unit is unresolved."""
    decision = VisualDecisionEngine.decide_visual(
        visual_id="VIS-BLOCKED-AMBIGUOUS",
        question_text="Custom unmapped metric summary",
        primary_dimension="category",
        measures=["unregistered_random_score"],
        provided_units={"unregistered_random_score": ""},
    )
    assert decision["status"] == "VISUALIZATION_BLOCKED"
    assert "AMBIGUOUS_METRIC_GRAIN" in decision["blocking_reason"]


def test_trap_causal_language_sanitization_for_observational_data():
    """Narrative entitlement guard: causal words are rejected or sanitized when unproven."""
    unentitled_takeaway = "Approved leave caused the attendance decline across departments."
    sanitized = VisualSemanticValidator.check_takeaway_entitlement(unentitled_takeaway, is_causal_proven=False)
    assert "caused" not in sanitized.lower()
    assert "co-occurs with" in sanitized.lower()


def test_audit_record_traceability():
    """Confirms audit trail contains complete reasoning, selection score, and rejected options."""
    decision = VisualDecisionEngine.decide_visual(
        visual_id="VIS-AUDIT-TEST",
        question_text="Which department has the largest attendance spread?",
        primary_dimension="dept",
        measures=["attendance"],
        provided_units={"attendance": "employee_day"},
    )
    audit = decision["audit"]
    assert audit["visual_id"] == "VIS-AUDIT-TEST"
    assert audit["analytical_intent"] == "RANKING"
    assert audit["selected_chart"] == "horizontal_bar"
    assert audit["selection_score"] > 0.70
    assert len(audit["rejected_alternatives"]) >= 2
    assert audit["metric_grain"] == "employee × working_day"
    assert audit["validation_status"] == "VALIDATED"


def test_trap_incomplete_composition_without_residual_blocked():
    """TRAP: Attempting to render a 100% composition where presence (136) + leave (19) != 160

    without accounting for the residual population must be BLOCKED with INCOMPLETE_COMPOSITION.
    Missing components must never be silently normalized away.
    """
    decision = VisualDecisionEngine.decide_visual(
        visual_id="VIS-INCOMPLETE-COMP",
        question_text="How was workforce capacity distributed across attendance and leave?",
        primary_dimension="period",
        measures=["office_attendance", "approved_leave"],
        is_temporal_dimension=True,
        temporal_grain="week",
        series_data={
            "office_attendance": [136.0],
            "approved_leave": [19.0],
        },
        provided_units={
            "office_attendance": "employee_day",
            "approved_leave": "employee_day",
        },
        denominator_metric="expected_capacity_employee_days",
        denominator_value=160.0,
        # Residual component NOT provided -> 136 + 19 = 155 != 160
    )

    assert decision["status"] == "VISUALIZATION_BLOCKED"
    assert "INCOMPLETE_COMPOSITION" in decision["blocking_reason"]
    audit = decision["audit"]
    assert audit["validation_status"] == "BLOCKED"
    assert audit["denominator_integrity"] is not None
    assert audit["denominator_integrity"]["is_reconciled"] is False
    assert audit["denominator_integrity"]["unreconciled_delta"] == 5.0


def test_composition_reconciliation_integrity_with_residual_passes():
    """Verify that providing all components (Presence 136 + Leave 19 + Remaining Gap 5 = 160)

    properly satisfies DenominatorIntegrity and is VALIDATED with exact percentage shares.
    """
    decision = VisualDecisionEngine.decide_visual(
        visual_id="VIS-RECONCILED-COMP",
        question_text="How was workforce capacity distributed each week?",
        primary_dimension="period",
        measures=["office_attendance", "approved_leave", "remaining_attendance_gap"],
        is_temporal_dimension=True,
        temporal_grain="week",
        series_data={
            "office_attendance": [136.0],
            "approved_leave": [19.0],
            "remaining_attendance_gap": [5.0],
        },
        provided_units={
            "office_attendance": "employee_day",
            "approved_leave": "employee_day",
            "remaining_attendance_gap": "employee_day",
        },
        denominator_metric="expected_capacity_employee_days",
        denominator_value=160.0,
        residual_component="remaining_attendance_gap",
    )

    assert decision["status"] == "VALIDATED"
    assert decision["chart_type"] == "100_percent_stacked_bar"
    audit = decision["audit"]
    assert audit["validation_status"] == "VALIDATED"
    assert audit["denominator_integrity"] is not None
    assert audit["denominator_integrity"]["is_reconciled"] is True
    assert audit["denominator_integrity"]["unreconciled_delta"] == 0.0
    assert audit["denominator_integrity"]["residual_component"] == "remaining_attendance_gap"

