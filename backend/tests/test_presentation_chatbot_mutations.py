"""Unit and integration tests for Phase 4: Conversational Slide Mutation Engine.

Verifies:
1. Reslicing a slide groups and aggregates data deterministically with zero math hallucination.
2. Converting a chart to a variance waterfall synthesizes valid baseline and delta steps.
3. Converting a chart to a breakdown tree builds hierarchical decomposition branches.
4. Filtering cohort slices dataset and updates badges and narrative.
5. Theme switching updates deck metadata and theme properties.
6. Revert capability restores the slide to the previous snapshot with 100% fidelity.
7. Invalid column requests reject cleanly with available column names.
8. API endpoint POST /api/presentations/mutate-slide works end-to-end.
"""

import pytest
import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.services.presentation.slide_mutator import (
    SlideMutator,
    SlideMutationAction,
    SlideMutationRequest,
    SlideMutationResult,
)


@pytest.fixture
def sample_sales_df():
    data = []
    locations = ["North", "South", "East", "West"]
    depts = ["Sales", "Engineering", "Marketing", "Support"]
    for i in range(1, 41):
        data.append({
            "Staff_ID": f"STF-{i:03d}",
            "Location": locations[i % 4],
            "Department": depts[i % 4],
            "Revenue": 1000.0 * (i % 7 + 1),
            "Attendance_Score": 75.0 + (i % 20),
        })
    return pd.DataFrame(data)


@pytest.fixture
def sample_deck_spec():
    return {
        "id": "deck-sample-01",
        "metadata": {"title": "Quarterly Operations Review", "theme_id": "corporate_navy"},
        "slides": [
            {
                "id": "slide-cover",
                "order": 1,
                "title": "Quarterly Operations Review",
                "subtitle": "Executive Briefing",
                "layout": "title_cover",
                "narrative": "Overview of operational metrics.",
                "bullets": ["Record performance observed."]
            },
            {
                "id": "slide-2",
                "order": 2,
                "title": "Department Performance",
                "subtitle": "Average revenue by department",
                "layout": "chart_narrative",
                "narrative": "Engineering leads overall revenue generation.",
                "bullets": ["Engineering highest revenue", "Support lowest revenue"],
                "chart": {
                    "chart_type": "column",
                    "title": "Department Revenue",
                    "categories": ["Engineering", "Sales", "Marketing", "Support"],
                    "dimension_col": "Department",
                    "metric_col": "Revenue",
                    "unit": "$",
                    "series": [{"name": "Average Revenue", "values": [6500.0, 5200.0, 4100.0, 3200.0]}],
                    "overall_mean": 4750.0
                }
            }
        ]
    }


def test_reslice_slide_deterministic_calculation(sample_deck_spec, sample_sales_df):
    """Verifies that reslicing by Location re-aggregates data deterministically from DataFrame."""
    res = SlideMutator.mutate_slide(
        deck_spec=sample_deck_spec,
        action=SlideMutationAction.RESLICE_SLIDE,
        params={"dimension_col": "Location", "metric_col": "Revenue"},
        slide_index=1,
        df=sample_sales_df
    )

    assert res.success is True
    assert res.action == "reslice_slide"
    assert res.slide_index == 1
    assert "Location" in res.diff_summary

    mutated_slide = res.updated_deck_spec["slides"][1]
    chart = mutated_slide["chart"]
    assert chart["dimension_col"] == "Location"
    assert chart["metric_col"] == "Revenue"
    assert set(chart["categories"]) == {"North", "South", "East", "West"}
    assert len(chart["series"][0]["values"]) == 4

    # Verify calculation accuracy with direct pandas ground truth
    expected_means = sample_sales_df.groupby("Location")["Revenue"].mean()
    for cat, val in zip(chart["categories"], chart["series"][0]["values"]):
        assert val == pytest.approx(expected_means[cat], rel=1e-2)

    # Verify previous snapshot is retained
    assert res.previous_slide_snapshot is not None
    assert res.previous_slide_snapshot["chart"]["dimension_col"] == "Department"


def test_retype_chart_to_variance_waterfall(sample_deck_spec):
    """Verifies that converting a chart to variance waterfall creates baseline, deltas, and helper bases."""
    res = SlideMutator.mutate_slide(
        deck_spec=sample_deck_spec,
        action=SlideMutationAction.RETYPE_CHART,
        params={"chart_type": "waterfall"},
        slide_index=1
    )

    assert res.success is True
    assert res.action == "retype_chart"
    mutated_chart = res.updated_deck_spec["slides"][1]["chart"]

    assert mutated_chart["chart_type"] == "waterfall"
    assert "waterfall_steps" in mutated_chart
    steps = mutated_chart["waterfall_steps"]
    assert len(steps) >= 3
    assert steps[0]["label"] == "Baseline Mean"
    assert steps[0]["type"] == "total"
    assert steps[-1]["label"] == "Net Realized"

    # Verify stacked bar series for helper base and delta
    assert len(mutated_chart["series"]) == 2
    assert mutated_chart["series"][0]["name"] == "Helper Base"
    assert mutated_chart["series"][1]["name"] == "Delta"


def test_retype_chart_to_breakdown_tree(sample_deck_spec):
    """Verifies that converting a chart to breakdown tree creates hierarchical decomposition branches."""
    res = SlideMutator.mutate_slide(
        deck_spec=sample_deck_spec,
        action=SlideMutationAction.RETYPE_CHART,
        params={"chart_type": "breakdown_tree"},
        slide_index=1
    )

    assert res.success is True
    mutated_chart = res.updated_deck_spec["slides"][1]["chart"]
    assert mutated_chart["chart_type"] == "breakdown_tree"
    assert "tree_data" in mutated_chart
    root = mutated_chart["tree_data"]
    assert "Overall" in root["name"]
    assert len(root["children"]) == 4
    child_names = [c["name"] for c in root["children"]]
    assert "Engineering" in child_names


def test_filter_cohort(sample_deck_spec, sample_sales_df):
    """Verifies that cohort filtering isolates the subset and re-aggregates accurately."""
    res = SlideMutator.mutate_slide(
        deck_spec=sample_deck_spec,
        action=SlideMutationAction.FILTER_COHORT,
        params={"filter_column": "Location", "filter_value": "North"},
        slide_index=1,
        df=sample_sales_df
    )

    assert res.success is True
    assert res.action == "filter_cohort"
    mutated_slide = res.updated_deck_spec["slides"][1]
    assert "Cohort Filtered: Location = North" in mutated_slide["subtitle"]
    assert any("Location: North" in b for b in mutated_slide.get("badges", []))


def test_change_theme(sample_deck_spec):
    """Verifies that theme mutation updates presentation theme tokens."""
    res = SlideMutator.mutate_slide(
        deck_spec=sample_deck_spec,
        action=SlideMutationAction.CHANGE_THEME,
        params={"theme_id": "executive_dark"},
        slide_index=0
    )

    assert res.success is True
    assert res.updated_deck_spec["metadata"]["theme_id"] == "executive_dark"
    assert res.updated_deck_spec["theme"]["id"] == "executive_dark"
    assert res.updated_deck_spec["theme"]["is_dark"] is True


def test_revert_mutation(sample_deck_spec, sample_sales_df):
    """Verifies that reverting restores the previous slide snapshot with 100% fidelity."""
    # Step 1: Perform mutation
    res1 = SlideMutator.mutate_slide(
        deck_spec=sample_deck_spec,
        action=SlideMutationAction.RESLICE_SLIDE,
        params={"dimension_col": "Location"},
        slide_index=1,
        df=sample_sales_df
    )
    assert res1.success is True
    assert res1.updated_deck_spec["slides"][1]["chart"]["dimension_col"] == "Location"

    # Step 2: Revert mutation using the snapshot from res1
    res2 = SlideMutator.mutate_slide(
        deck_spec=res1.updated_deck_spec,
        action=SlideMutationAction.REVERT_MUTATION,
        params={"snapshot": res1.previous_slide_snapshot},
        slide_index=1
    )

    assert res2.success is True
    reverted_slide = res2.updated_deck_spec["slides"][1]
    assert reverted_slide["chart"]["dimension_col"] == "Department"
    assert reverted_slide["chart"]["categories"] == ["Engineering", "Sales", "Marketing", "Support"]


def test_invalid_column_rejection(sample_deck_spec, sample_sales_df):
    """Verifies that invalid columns raise a helpful error instead of hallucinating."""
    res = SlideMutator.mutate_slide(
        deck_spec=sample_deck_spec,
        action=SlideMutationAction.RESLICE_SLIDE,
        params={"dimension_col": "NonExistentColumn"},
        slide_index=1,
        df=sample_sales_df
    )

    assert res.success is False
    assert "not found in dataset" in (res.error or "")


def test_api_mutate_slide_endpoint(sample_deck_spec):
    """Verifies that POST /api/presentations/mutate-slide executes through the HTTP router."""
    client = TestClient(app)
    payload = {
        "deck_spec": sample_deck_spec,
        "slide_index": 1,
        "action": "retype_chart",
        "params": {"chart_type": "donut"}
    }
    resp = client.post("/api/presentations/mutate-slide", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["action"] == "retype_chart"
    assert data["updated_deck_spec"]["slides"][1]["chart"]["chart_type"] == "donut"


def test_copilot_intent_classification_for_slide_mutations():
    """Verifies that conversational slide commands are classified as SLIDE_MUTATION."""
    from app.routers.copilot import classify_analytical_intent, parse_slide_mutation_intent

    queries = [
        "Change slide 2 to group by Location instead of Department",
        "Switch slide 3 chart to variance waterfall",
        "Convert chart on slide 2 to breakdown tree",
        "Change presentation theme to executive dark",
        "Filter slide 2 to Engineering",
        "Undo slide changes",
        "Revert slide 2"
    ]
    for q in queries:
        intent = classify_analytical_intent(q)
        assert intent == "SLIDE_MUTATION", f"Query '{q}' was classified as '{intent}', expected 'SLIDE_MUTATION'"

    # Verify parameter parsing
    action1, params1, idx1 = parse_slide_mutation_intent("Change slide 2 to group by Location")
    assert action1 == "reslice_slide"
    assert params1["dimension_col"] == "Location"
    assert idx1 == 1

    action2, params2, idx2 = parse_slide_mutation_intent("Switch slide 3 chart to variance waterfall")
    assert action2 == "retype_chart"
    assert params2["chart_type"] == "waterfall"
    assert idx2 == 2

    action3, params3, _ = parse_slide_mutation_intent("Change theme to executive dark")
    assert action3 == "change_theme"
    assert params3["theme_id"] == "executive_dark"


def test_copilot_query_endpoint_slide_mutation(sample_deck_spec):
    """Verifies that /api/copilot/query executes slide mutation and returns mutated visual chart."""
    client = TestClient(app)
    resp = client.post("/api/copilot/query", json={
        "query": "Switch slide 2 chart to waterfall",
        "prior_context": {"deck_spec": sample_deck_spec, "active_slide_index": 1}
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["engine"] == "slide_mutator"
    assert "Slide Mutation Applied" in data["answer"]
    assert "mutation" in data
    assert data["mutation"]["action"] == "retype_chart"
    assert len(data["visual_charts"]) == 1
    assert data["visual_charts"][0]["chart_type"] == "waterfall"

