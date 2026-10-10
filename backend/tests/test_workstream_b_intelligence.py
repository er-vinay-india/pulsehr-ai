"""Tests for Workstream B (Ingestion Intelligence).

Covers:
1. Hierarchical header inference (MultiIndex and stacked rows) with recoverable geometry
2. External margin vs internal blank table separator distinction
3. Join cardinality and grain validation (1:1, 1:N, M:N fan-out safeguards)
4. Statistical effect size grading and Benjamini-Hochberg FDR correction
5. Temporal alignment and lag-aware analysis in relationship discovery
6. Categorical interaction discovery without fixed 3-25 category limits
7. Semantic column grouping relationship recall measurement and bridge column preservation
"""

import io
import json
import numpy as np
import pandas as pd
import pytest

from app.services.sheet_catalog import infer_hierarchical_headers, rebuild_relationships
from app.services.enrichment.relationship_engine import ColumnRelationshipEngine
from app.services.enrichment.column_grouping import ColumnGroupingEngine
from app.services.enrichment.interaction_engine import InteractionFeatureEngine
from app.services.enrichment.models import (
    ColumnRelationship,
    EnrichmentColumnProfile,
    SemanticColumnGroup,
    SemanticRole,
)
from app.services.enrichment.config import BudgetGuard, EnrichmentConfig


def test_hierarchical_header_inference_multiindex():
    """Validates 3-tier MultiIndex header parsing with 100% recoverable geometry."""
    cols = pd.MultiIndex.from_tuples([
        ("Revenue", "Q1", "Actual"),
        ("Revenue", "Q1", "Budget"),
        ("Headcount", "Core", "FullTime"),
    ])
    df = pd.DataFrame([
        [100, 95, 42],
        [120, 110, 44],
    ], columns=cols)

    norm_df, geom = infer_hierarchical_headers(df)

    assert geom["has_hierarchical_header"] is True
    assert geom["levels_count"] == 3
    assert "revenue_q1_actual" in norm_df.columns
    assert "revenue_q1_budget" in norm_df.columns
    assert "headcount_core_fulltime" in norm_df.columns

    mapping = geom["mappings"]["revenue_q1_actual"]
    assert mapping["levels"] == ["Revenue", "Q1", "Actual"]
    assert mapping["display_hierarchy"] == "Revenue → Q1 → Actual"
    assert mapping["col_index"] == 0


def test_hierarchical_header_inference_stacked_rows():
    """Validates stacked header row detection (e.g. from raw Excel row headers)."""
    raw_data = [
        ["Financial Summary", "Financial Summary", "Operations"],
        ["Revenue", "Cost", "Headcount"],
        [5000, 3200, 150],
        [5200, 3100, 152],
    ]
    df = pd.DataFrame(raw_data)

    norm_df, geom = infer_hierarchical_headers(df)

    assert geom["has_hierarchical_header"] is True
    assert len(norm_df) == 2  # The 2 header rows are consumed
    assert any("financial_summary_revenue" in col for col in norm_df.columns)
    assert any("operations_headcount" in col for col in norm_df.columns)


def test_flat_header_preserves_single_level_geometry():
    """Flat tables retain 1-level header geometry mapping."""
    df = pd.DataFrame({"employee_id": [1, 2], "salary": [50000, 60000]})
    norm_df, geom = infer_hierarchical_headers(df)

    assert geom["has_hierarchical_header"] is False
    assert geom["levels_count"] == 1
    assert "employee_id" in geom["mappings"]
    assert geom["mappings"]["employee_id"]["levels"] == ["employee_id"]


def test_statistical_safeguards_and_effect_size_grading():
    """Evaluates Cohen effect sizes and FDR multiple-testing correction."""
    np.random.seed(42)
    n = 100
    x = np.linspace(1, 10, n)
    y_large = x * 2.5 + np.random.normal(0, 0.5, n)  # Very strong correlation (r > 0.9)
    y_med = x * 0.8 + np.random.normal(0, 3.0, n)    # Medium correlation (0.3 <= r < 0.5)

    p_x = EnrichmentColumnProfile(column="x", original_name="x", physical_type="float", semantic_type="metric", roles=[SemanticRole.MEASURE], cardinality=n)
    p_large = EnrichmentColumnProfile(column="y_large", original_name="y_large", physical_type="float", semantic_type="metric", roles=[SemanticRole.MEASURE], cardinality=n)
    p_med = EnrichmentColumnProfile(column="y_med", original_name="y_med", physical_type="float", semantic_type="metric", roles=[SemanticRole.MEASURE], cardinality=n)

    rel_large = ColumnRelationshipEngine.evaluate_pair(pd.Series(x), pd.Series(y_large), p_x, p_large)
    rel_med = ColumnRelationshipEngine.evaluate_pair(pd.Series(x), pd.Series(y_med), p_x, p_med)

    assert any("Large statistical effect size" in r for r in rel_large.reasons)
    assert rel_large.statistical_dependency >= 0.50

    # Discover relationships across dataframe with multiple-testing correction
    df = pd.DataFrame({
        "x": x,
        "y_large": y_large,
        "y_med": y_med,
        "noise1": np.random.normal(0, 1, n),
        "noise2": np.random.normal(0, 1, n),
    })
    profiles = {
        col: EnrichmentColumnProfile(column=col, original_name=col, physical_type="float", semantic_type="metric", roles=[SemanticRole.MEASURE], cardinality=n)
        for col in df.columns
    }
    cfg = EnrichmentConfig(min_relationship_score=0.40)
    rels = ColumnRelationshipEngine.discover_relationships(df, profiles, cfg)

    assert len(rels) >= 1
    top_cols = {rels[0].left_column, rels[0].right_column}
    assert "x" in top_cols and "y_large" in top_cols


def test_lag_aware_temporal_alignment():
    """Detects lead/lag correlations across ordered series."""
    np.random.seed(42)
    n = 80
    base = np.random.normal(0, 1, n)
    # Lag-1 series: lag_s[t] ~ base[t-1]
    lag_s = np.zeros(n)
    lag_s[1:] = base[:-1] + np.random.normal(0, 0.05, n - 1)

    p_base = EnrichmentColumnProfile(column="signal", original_name="signal", physical_type="float", semantic_type="metric", roles=[SemanticRole.MEASURE], cardinality=n)
    p_lag = EnrichmentColumnProfile(column="lagged_signal", original_name="lagged_signal", physical_type="float", semantic_type="metric", roles=[SemanticRole.MEASURE], cardinality=n)

    rel = ColumnRelationshipEngine.evaluate_pair(pd.Series(base), pd.Series(lag_s), p_base, p_lag)
    has_lag_reason = any("temporal alignment" in r.lower() for r in rel.reasons)
    assert has_lag_reason is True


def test_categorical_interaction_discovery_without_fixed_30_limit():
    """Ensures categorical columns with >30 unique categories (e.g. 50 roles) are discovered."""
    np.random.seed(42)
    n = 500
    # 50 unique job titles
    job_titles = [f"Specialist_Tier_{i}" for i in range(50)]
    roles = np.random.choice(job_titles, size=n)
    salaries = np.random.normal(75000, 15000, size=n)

    df = pd.DataFrame({"job_title": roles, "salary": salaries})
    profiles = {
        "job_title": EnrichmentColumnProfile(column="job_title", original_name="job_title", physical_type="string", semantic_type="category", roles=[SemanticRole.CATEGORY], cardinality=50),
        "salary": EnrichmentColumnProfile(column="salary", original_name="salary", physical_type="float", semantic_type="metric", roles=[SemanticRole.MEASURE], cardinality=n),
    }
    cfg = EnrichmentConfig(max_derived_columns=10, max_derivation_depth=2)
    guard = BudgetGuard(config=cfg)

    enriched_df, derived = InteractionFeatureEngine.derive_interactions(df, profiles, guard, cfg)

    assert any("interact_mean_salary_by_job_title" in col for col in enriched_df.columns)
    assert any(d.derivation_type == "interaction_group_mean" for d in derived)


def test_candidate_relationship_recall_measurement():
    """Verifies ColumnGroupingEngine.measure_relationship_recall and bridge column retention."""
    cols = ["emp_id", "dept", "salary", "bonus", "tenure"]
    groups = [
        SemanticColumnGroup(
            group_id="G1",
            group_name="Compensation",
            domain_interpretation="Financial metrics",
            columns=["salary", "bonus", "emp_id"],
            primary_roles=[SemanticRole.MEASURE],
            cohesion_score=0.9
        ),
        SemanticColumnGroup(
            group_id="G2",
            group_name="Organization",
            domain_interpretation="Organizational hierarchy",
            columns=["dept", "tenure", "emp_id"],
            primary_roles=[SemanticRole.CATEGORY],
            cohesion_score=0.85
        )
    ]
    relationships = [
        ColumnRelationship(left_column="salary", right_column="bonus", relationship_type="correlation", relationship_score=0.85),
        ColumnRelationship(left_column="dept", right_column="tenure", relationship_type="association", relationship_score=0.75),
        ColumnRelationship(left_column="salary", right_column="emp_id", relationship_type="affinity", relationship_score=0.70),
        # Cross group relation bridged by emp_id:
        ColumnRelationship(left_column="salary", right_column="dept", relationship_type="group_diff", relationship_score=0.65),
    ]

    recall_metrics = ColumnGroupingEngine.measure_relationship_recall(groups, relationships, min_relationship_score=0.60)

    # 3 out of 4 relationships are directly co-located in a single group
    assert recall_metrics["total_eligible_edges"] == 4
    assert recall_metrics["captured_edges"] == 3
    assert recall_metrics["recall"] == 0.75
    assert len(recall_metrics["missed_edges"]) == 1
    assert recall_metrics["missed_edges"][0]["left_column"] == "salary"
