"""Governed Dataset Intelligence Benchmark & Evaluation Framework Contracts.

Defines ground truth specifications, evaluation dimensions, and quantitative scorecards:
1. Relationship Discovery (Precision, Recall, UnsafeJoinRate).
2. Cross-Sheet Insight Validity (CrossSheetPrecision, CrossSheetRecall).
3. Global Ranking Quality (NDCG@9, Precision@K).
4. Dashboard Slot Allocation (Top9Accuracy, HeroAccuracy).
5. Redundancy Suppression (FalseSuppressionRate).
6. Invariance & Mutation Verification (SheetOrderInvariance, MutationSensitivity).
"""
from __future__ import annotations

import math
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class ExpectedRelationship(BaseModel):
    """Ground-truth expected relationship between two sheets in a workbook."""
    model_config = ConfigDict(extra="forbid")

    left_sheet: str
    right_sheet: str
    left_column: str
    right_column: str
    cardinality: Literal["one-to-one", "one-to-many", "many-to-one", "many-to-many"]
    is_safe: bool = True  # If False, discovering this join is considered an UnsafeJoin violation


class ExpectedInsight(BaseModel):
    """Ground-truth expected finding with rank tier and slot assignment."""
    model_config = ConfigDict(extra="forbid")

    insight_id: str
    metric_keyword: str
    expected_scope: Literal["SINGLE_SHEET", "CROSS_SHEET"]
    expected_slot: Literal["hero", "strategic", "diagnostic", "risk_foresight", "action_scenario"]
    relevance_tier: int  # 1 (Hero / Critical) to 4 (Minor)
    is_critical: bool = False  # If True, missing this from top 9 is a CriticalInsightMiss violation
    redundancy_cluster: str | None = None


class BenchmarkDatasetSpec(BaseModel):
    """Ground truth benchmark dataset specification."""
    model_config = ConfigDict(extra="forbid")

    benchmark_id: str
    name: str
    domain: str
    sheet_count: int
    expected_relationships: list[ExpectedRelationship] = Field(default_factory=list)
    forbidden_relationships: list[ExpectedRelationship] = Field(default_factory=list)
    expected_insights: list[ExpectedInsight] = Field(default_factory=list)


class EvaluationScorecard(BaseModel):
    """Audited evaluation scorecard measuring Highview dataset intelligence."""
    model_config = ConfigDict(extra="forbid")

    benchmark_id: str
    # 1. Relationships
    relationship_precision: float
    relationship_recall: float
    unsafe_join_rate: float
    # 2. Cross-Sheet Insights
    cross_sheet_precision: float
    cross_sheet_recall: float
    # 3. Global Ranking
    ndcg_at_9: float
    # 4. Slot Selection
    hero_selection_accuracy: float
    top9_selection_accuracy: float
    # 5. Redundancy & Coverage
    false_suppression_rate: float
    critical_insight_miss_rate: float
    coverage_warnings_emitted: list[str] = Field(default_factory=list)
    # 6. Invariance & Performance
    sheet_order_invariance: bool
    mutation_test_passed: bool = True
    visual_governance: VisualGovernanceScorecard | None = None
    total_latency_ms: float
    overall_pass: bool


class VisualGovernanceScorecard(BaseModel):
    """Measures visual governance and theme compliance independently of analytical ranking."""
    model_config = ConfigDict(extra="forbid")

    theme_integrity_pass_rate: float = 1.0  # 100%
    hardcoded_theme_violation_count: int = 0  # Target: 0
    light_theme_pass_rate: float = 1.0  # 100%
    dark_theme_pass_rate: float = 1.0  # 100%
    chart_theme_compliance_rate: float = 1.0  # 100%
    semantic_token_compliance_rate: float = 1.0  # 100%
    theme_switch_structure_stability: bool = True
    critical_contrast_violation_count: int = 0
    overall_visual_governance_pass: bool = True


class CouncilRankingEvaluation(BaseModel):
    """Measures impact of AI Council reranking on deterministic analytical ranking."""
    model_config = ConfigDict(extra="forbid")

    deterministic_ndcg_at_9: float
    council_ndcg_at_9: float
    council_ranking_gain: float  # council_ndcg - deterministic_ndcg
    preserves_critical_rankings: bool
    verdict: Literal["IMPROVED", "NEUTRAL", "DEGRADED"]


def calculate_dcg(relevance_scores: list[int], k: int = 9) -> float:
    """Calculates Discounted Cumulative Gain at K."""
    dcg = 0.0
    for i, rel in enumerate(relevance_scores[:k]):
        dcg += (2**rel - 1) / math.log2(i + 2)
    return dcg


def calculate_ndcg_at_k(actual_ranks: list[int], ideal_ranks: list[int], k: int = 9) -> float:
    """Calculates Normalized Discounted Cumulative Gain at K."""
    actual_dcg = calculate_dcg(actual_ranks, k=k)
    ideal_dcg = calculate_dcg(sorted(ideal_ranks, reverse=True), k=k)
    if ideal_dcg == 0.0:
        return 1.0
    return round(min(1.0, actual_dcg / ideal_dcg), 4)


# Pre-defined Golden Multi-Sheet Archetypes for Benchmark Evaluation
WORKFORCE_ARCHETYPE_SPEC = BenchmarkDatasetSpec(
    benchmark_id="ARCH-WORKFORCE-01",
    name="Enterprise Workforce & Attendance",
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
        ExpectedInsight(insight_id="WF-01", metric_keyword="cross_sheet_link", expected_scope="CROSS_SHEET", expected_slot="hero", relevance_tier=4, is_critical=True),
        ExpectedInsight(insight_id="WF-02", metric_keyword="attendance", expected_scope="SINGLE_SHEET", expected_slot="strategic", relevance_tier=3),
    ],
)

RETAIL_ARCHETYPE_SPEC = BenchmarkDatasetSpec(
    benchmark_id="ARCH-RETAIL-01",
    name="Omnichannel Retail & Inventory",
    domain="retail_sales",
    sheet_count=4,
    expected_relationships=[
        ExpectedRelationship(left_sheet="Transactions", right_sheet="Products", left_column="product_id", right_column="product_id", cardinality="many-to-one"),
        ExpectedRelationship(left_sheet="Transactions", right_sheet="Stores", left_column="store_id", right_column="store_id", cardinality="many-to-one"),
    ],
    forbidden_relationships=[
        ExpectedRelationship(left_sheet="Products", right_sheet="Stores", left_column="category", right_column="store_location", cardinality="many-to-many", is_safe=False),
    ],
    expected_insights=[
        ExpectedInsight(insight_id="RET-01", metric_keyword="revenue", expected_scope="CROSS_SHEET", expected_slot="hero", relevance_tier=4, is_critical=True),
    ],
)

FINANCE_ARCHETYPE_SPEC = BenchmarkDatasetSpec(
    benchmark_id="ARCH-FINANCE-01",
    name="Corporate Finance & Budget Variance",
    domain="finance",
    sheet_count=4,
    expected_relationships=[
        ExpectedRelationship(left_sheet="Expenses", right_sheet="Budget", left_column="cost_center", right_column="cost_center", cardinality="many-to-one"),
        ExpectedRelationship(left_sheet="Revenue", right_sheet="Business Units", left_column="unit_id", right_column="unit_id", cardinality="many-to-one"),
    ],
    forbidden_relationships=[
        ExpectedRelationship(left_sheet="Expenses", right_sheet="Revenue", left_column="transaction_id", right_column="transaction_id", cardinality="many-to-many", is_safe=False),
    ],
    expected_insights=[
        ExpectedInsight(insight_id="FIN-01", metric_keyword="budget_variance", expected_scope="CROSS_SHEET", expected_slot="hero", relevance_tier=4, is_critical=True),
    ],
)

ADVERSARIAL_MISMATCH_SPEC = BenchmarkDatasetSpec(
    benchmark_id="ADV-TRAP-01",
    name="Adversarial Trap: Mismatched Types and Collision Columns",
    domain="adversarial",
    sheet_count=3,
    expected_relationships=[],
    forbidden_relationships=[
        ExpectedRelationship(left_sheet="Employees", right_sheet="Sales", left_column="department_id", right_column="department_id", cardinality="many-to-many", is_safe=False),
        ExpectedRelationship(left_sheet="Attendance", right_sheet="Departments", left_column="date", right_column="department_id", cardinality="many-to-many", is_safe=False),
    ],
    expected_insights=[],
)
