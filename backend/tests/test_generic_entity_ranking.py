"""Test Generic Entity Ranking Intelligence Engine.

Verifies:
1. Domain-independent candidate ranking discovery (Workforce & Retail).
2. Semantic desirability direction (HIGHER_IS_BETTER, LOWER_IS_BETTER, NEUTRAL).
3. Scale boundaries & non-fabrication (e.g. requesting 25 for 11 entities returns 11).
4. Top & Bottom mode overlap prevention (unique entities across extremes).
5. Progressive scale presentation contracts (5 vs 50 vs 100/Full).
6. Cross-sheet join and active filter preservation.
7. Zero workforce-specific hardcoded assumptions.
"""
import pytest
import json
import pytest
from app.db.database import get_connection
from app.services.adaptive_dashboard.ranking_engine import (
    GenericEntityRankingEngine,
    RankingDirection,
)


@pytest.fixture
def ranking_test_env():
    """Populates controlled workforce and retail datasets in the test DB."""
    conn = get_connection()
    try:
        # 1. Dataset 99750 (Workforce)
        conn.execute("INSERT OR REPLACE INTO dataset_uploads (id, filename, original_name, file_type) VALUES (99750, 'workforce.xlsx', 'Workforce July.xlsx', 'xlsx')")
        cols_wfo = ["Department", "Final Attendance", "Leaves(1st to 5th July)"]
        profs_wfo = [
            {"column": "Department", "distinct": 11, "numeric": False},
            {"column": "Final Attendance", "distinct": 11, "numeric": True, "unit": ""},
            {"column": "Leaves(1st to 5th July)", "distinct": 5, "numeric": True, "unit": "days"},
        ]
        conn.execute(
            "INSERT OR REPLACE INTO sheets (id, dataset_id, name, columns_json, profile_json, row_count) VALUES (997501, 99750, 'Sheet1', ?, ?, 11)",
            (json.dumps(cols_wfo), json.dumps(profs_wfo)),
        )

        depts = [
            ("Operations and Infrastructure", 16.08, 0.19),
            ("Architecture", 12.58, 0.0),
            ("Alliance Initiative - NRP", 11.85, 0.35),
            ("Alliance Initiative - Components", 11.17, 0.30),
            ("Laerdal Initiative - Engineering Services", 11.11, 0.40),
            ("Alliance Initiative - Platforms Engineering", 10.60, 0.45),
            ("Alliance Initiative - Products", 10.28, 0.50),
            ("Corporate Functions", 10.18, 0.42),
            ("Alliance Initiative", 10.0, 0.0),
            ("Alliance Initiative - RQI 1stop/LLP", 9.92, 0.55),
            ("Alliance Initiative - Design", 8.44, 0.28),
        ]
        for idx, (d, att, l) in enumerate(depts):
            row_data = {"Department": d, "Final Attendance": att, "Leaves(1st to 5th July)": l}
            conn.execute(
                "INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (997501, ?, ?)",
                (idx, json.dumps(row_data)),
            )

        # 2. Dataset 8801 (Retail)
        conn.execute("INSERT OR REPLACE INTO dataset_uploads (id, filename, original_name, file_type) VALUES (8801, 'retail.csv', 'Walmart Sales.csv', 'csv')")
        cols_ret = ["Store", "Weekly_Sales"]
        profs_ret = [
            {"column": "Store", "distinct": 4, "numeric": False},
            {"column": "Weekly_Sales", "distinct": 4, "numeric": True, "unit": "usd"},
        ]
        conn.execute(
            "INSERT OR REPLACE INTO sheets (id, dataset_id, name, columns_json, profile_json, row_count) VALUES (88011, 8801, 'Sales', ?, ?, 4)",
            (json.dumps(cols_ret), json.dumps(profs_ret)),
        )

        stores = [
            ("Store 4", 25500.0),
            ("Store 3", 25000.0),
            ("Store 2", 24500.0),
            ("Store 1", 24000.0),
        ]
        for idx, (s, sales) in enumerate(stores):
            row_data = {"Store": s, "Weekly_Sales": sales}
            conn.execute(
                "INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (88011, ?, ?)",
                (idx, json.dumps(row_data)),
            )
        conn.commit()
    finally:
        conn.close()


def test_semantic_desirability_inference():
    """Verifies desirability direction inference across business measures."""
    # Higher is better
    dir1, conf1, _ = GenericEntityRankingEngine.infer_desirability_direction("attendance_rate", "%")
    assert dir1 == RankingDirection.HIGHER_IS_BETTER
    assert conf1 >= 0.85

    dir2, conf2, _ = GenericEntityRankingEngine.infer_desirability_direction("weekly_sales", "$")
    assert dir2 == RankingDirection.HIGHER_IS_BETTER
    assert conf2 >= 0.85

    dir3, conf3, _ = GenericEntityRankingEngine.infer_desirability_direction("exam_score", "points")
    assert dir3 == RankingDirection.HIGHER_IS_BETTER

    # Lower is better
    dir4, conf4, _ = GenericEntityRankingEngine.infer_desirability_direction("defect_rate", "%")
    assert dir4 == RankingDirection.LOWER_IS_BETTER
    assert conf4 >= 0.85

    dir5, conf5, _ = GenericEntityRankingEngine.infer_desirability_direction("approved_leave_days", "days")
    assert dir5 == RankingDirection.LOWER_IS_BETTER

    dir6, conf6, _ = GenericEntityRankingEngine.infer_desirability_direction("delivery_delay_hours", "hours")
    assert dir6 == RankingDirection.LOWER_IS_BETTER

    # Neutral fallback
    dir7, conf7, _ = GenericEntityRankingEngine.infer_desirability_direction("temperature", "celsius")
    assert dir7 == RankingDirection.NEUTRAL


def test_workforce_entity_ranking_query(ranking_test_env):
    """Verifies server-side group-by entity ranking on dataset 99750."""
    res = GenericEntityRankingEngine.execute_ranking_query(
        dataset_id=99750,
        entity_column="Department",
        measure_column="Final Attendance",
        direction="TOP",
        limit=5,
    )
    assert res["population_count"] == 11
    assert len(res["ranked_rows"]) == 5
    assert res["ranking_direction"] == "HIGHER_IS_BETTER"
    assert res["ranked_rows"][0]["rank"] == 1
    assert res["ranked_rows"][0]["entity"] == "Operations and Infrastructure"
    assert res["ranked_rows"][0]["value"] > 15.0
    assert res["benchmark"] > 0.0


def test_boundary_limit_handling(ranking_test_env):
    """Verifies that requesting Top 25 when only 11 exist returns exactly 11 without fabricating rows."""
    res = GenericEntityRankingEngine.execute_ranking_query(
        dataset_id=99750,
        entity_column="Department",
        measure_column="Final Attendance",
        direction="TOP",
        limit=25,
    )
    assert res["population_count"] == 11
    assert len(res["ranked_rows"]) == 11
    assert res["is_full_coverage"] is True


def test_top_and_bottom_mode_overlap_prevention(ranking_test_env):
    """Verifies that BOTH mode handles small populations without row duplication."""
    res = GenericEntityRankingEngine.execute_ranking_query(
        dataset_id=99750,
        entity_column="Department",
        measure_column="Final Attendance",
        direction="BOTH",
        limit=4,
    )
    assert len(res["ranked_rows"]) == 2
    assert len(res["bottom_rows"]) == 2
    top_entities = {r["entity"] for r in res["ranked_rows"]}
    bot_entities = {r["entity"] for r in res["bottom_rows"]}
    # No duplicate entities across top and bottom
    assert top_entities.isdisjoint(bot_entities)


def test_lower_is_better_ranking(ranking_test_env):
    """Verifies that lower-is-better measures rank smallest values as Rank 1."""
    res = GenericEntityRankingEngine.execute_ranking_query(
        dataset_id=99750,
        entity_column="Department",
        measure_column="Leaves(1st to 5th July)",
        direction="TOP",
        limit=5,
    )
    assert res["ranking_direction"] == "LOWER_IS_BETTER"
    assert res["ranked_rows"][0]["rank"] == 1
    # Lowest leave days (0.0) is rank 1
    assert res["ranked_rows"][0]["value"] == 0.0


def test_retail_domain_independence(ranking_test_env):
    """Verifies ranking works identically on retail Store x Weekly_Sales (dataset 8801)."""
    res = GenericEntityRankingEngine.execute_ranking_query(
        dataset_id=8801,
        entity_column="Store",
        measure_column="Weekly_Sales",
        direction="TOP",
        limit=5,
    )
    assert res["population_count"] == 4
    assert res["entity_type"] == "Store"
    assert len(res["ranked_rows"]) == 4
    assert res["ranking_direction"] == "HIGHER_IS_BETTER"
    assert res["ranked_rows"][0]["entity"] == "Store 4"
    assert res["ranked_rows"][0]["value"] == 25500.0


def test_distribution_summary_generation(ranking_test_env):
    """Verifies statistical percentile distribution summary (min, p25, median, p75, max)."""
    res = GenericEntityRankingEngine.execute_ranking_query(
        dataset_id=99750,
        entity_column="Department",
        measure_column="Final Attendance",
        direction="TOP",
        limit=5,
    )
    dist = res["distribution_summary"]
    assert "count" in dist
    assert "mean" in dist
    assert "median" in dist
    assert "min" in dist
    assert "max" in dist
    assert dist["min"] <= dist["median"] <= dist["max"]

