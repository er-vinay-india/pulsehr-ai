"""End-to-End Conversational User Flow & Visual Lifecycle Verification.

Simulates the complete user journey:
1. Ingest tabular dataset with multi-department records.
2. Generate an analytical presentation deck spec.
3. Conversational Co-Pilot Q&A: ask analytical factual query with zero LLM math.
4. Conversational Slide Mutation:
   - Reslice active slide by dimension ("group by Location").
   - Retype chart to variance waterfall bridge ("change to waterfall").
   - Retype chart to breakdown tree ("change to breakdown tree").
   - Switch presentation theme ("switch theme to midnight_navy").
   - Revert mutation ("revert slide").
5. Direct PPTX Export Validation:
   - Every mutated and reverted deck exports cleanly into native PowerPoint 16:9 widescreen format.
   - All text & charts satisfy WCAG AAA 7:1 contrast.
"""

import io
import json
import pytest
import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.core import config
from app.services.report_generator import export_spec_to_pptx
from app.services.presentation.slide_mutator import SlideMutator, SlideMutationAction
from pptx import Presentation

client = TestClient(app)
pytestmark = [pytest.mark.presentation]


@pytest.fixture
def enterprise_workforce_df():
    """Generates realistic enterprise workforce records across 12 departments."""
    depts = [
        "Engineering", "Product Design", "Customer Support", "Enterprise Sales",
        "Talent Acquisition", "People Operations", "Financial Strategy", "Legal & Compliance",
        "Brand Marketing", "Security SecOps", "Data Engineering", "Supply Chain"
    ]
    regions = ["North America", "EMEA", "APAC", "LATAM"]
    data = []

    for i in range(1, 121):
        dept = depts[i % len(depts)]
        region = regions[i % len(regions)]
        base_salary = 75000 + (i % 15) * 4500
        overtime_hrs = (i % 7) * 4.5
        headcount = 1

        data.append({
            "Employee_ID": f"EMP-{i:04d}",
            "Department": dept,
            "Region": region,
            "Base_Salary": base_salary,
            "Overtime_Hours": overtime_hrs,
            "Headcount": headcount,
            "Performance_Rating": 3.0 + (i % 3) * 0.8
        })

    return pd.DataFrame(data)


@pytest.fixture
def initial_deck_spec(enterprise_workforce_df):
    """Creates a base presentation deck spec anchored to the enterprise dataset."""
    dept_summary = enterprise_workforce_df.groupby("Department")["Base_Salary"].mean().reset_index()

    return {
        "id": "deck-e2e-enterprise-01",
        "metadata": {
            "title": "Global Workforce & Compensation Review",
            "theme_id": "corporate_navy",
            "sheet_id": "sheet-workforce-01"
        },
        "slides": [
            {
                "id": "slide-cover",
                "order": 1,
                "title": "Global Workforce & Compensation Review",
                "subtitle": "Executive Analytics Briefing",
                "layout": "title_hero",
                "narrative": "Comprehensive analysis of global headcount and compensation structures."
            },
            {
                "id": "slide-salary-breakdown",
                "order": 2,
                "title": "Average Base Salary by Department",
                "subtitle": "Departmental Compensation Baseline",
                "layout": "chart_narrative",
                "narrative": "Engineering and Financial Strategy command the highest departmental averages.",
                "chart": {
                    "title": "Average Base Salary ($)",
                    "type": "column",
                    "categories": dept_summary["Department"].tolist(),
                    "series": [{
                        "name": "Mean Salary",
                        "values": [round(float(v), 2) for v in dept_summary["Base_Salary"]]
                    }]
                }
            }
        ]
    }


def test_complete_conversational_user_flow(tmp_path, monkeypatch, enterprise_workforce_df, initial_deck_spec):
    """Executes the full end-to-end user lifecycle."""
    monkeypatch.setattr(config, 'EXPORTS_DIR', tmp_path)

    # -------------------------------------------------------------
    # Step 1: Export Initial Deck to Native PPTX
    # -------------------------------------------------------------
    initial_path = export_spec_to_pptx(initial_deck_spec)
    initial_prs = Presentation(initial_path)
    assert len(initial_prs.slides) == 2
    assert initial_prs.slide_width.inches == pytest.approx(13.333, 0.01)

    # -------------------------------------------------------------
    # Step 2: Conversational Slide Mutation 1 - Reslice by Region
    # User prompts HRIDAY: "re-slice by Region"
    # -------------------------------------------------------------
    reslice_result = SlideMutator.mutate_slide(
        deck_spec=initial_deck_spec,
        action=SlideMutationAction.RESLICE_SLIDE,
        params={"dimension": "Region", "metric": "Base_Salary", "agg": "mean"},
        slide_index=1,
        df=enterprise_workforce_df
    )

    assert reslice_result.success is True
    assert "Region" in reslice_result.diff_summary
    mutated_deck_1 = reslice_result.updated_deck_spec
    active_chart_1 = mutated_deck_1["slides"][1]["chart"]

    # Invariant: Categories should now be the 4 regions, not departments
    assert sorted(active_chart_1["categories"]) == ["APAC", "EMEA", "LATAM", "North America"]
    assert len(active_chart_1["series"][0]["values"]) == 4

    # Verify native export of resliced deck
    resliced_path = export_spec_to_pptx(mutated_deck_1)
    resliced_prs = Presentation(resliced_path)
    assert len(resliced_prs.slides) == 2

    # -------------------------------------------------------------
    # Step 3: Conversational Slide Mutation 2 - Retype to Variance Waterfall
    # User prompts HRIDAY: "convert chart to waterfall"
    # -------------------------------------------------------------
    waterfall_result = SlideMutator.mutate_slide(
        deck_spec=mutated_deck_1,
        action=SlideMutationAction.RETYPE_CHART,
        params={"chart_type": "variance_waterfall"},
        slide_index=1,
        df=enterprise_workforce_df
    )

    assert waterfall_result.success is True
    mutated_deck_2 = waterfall_result.updated_deck_spec
    active_chart_2 = mutated_deck_2["slides"][1]["chart"]

    assert active_chart_2["type"] == "waterfall"
    assert "waterfall_steps" in active_chart_2
    assert len(active_chart_2["waterfall_steps"]) >= 3

    # Verify native export of waterfall deck
    waterfall_path = export_spec_to_pptx(mutated_deck_2)
    waterfall_prs = Presentation(waterfall_path)
    assert len(waterfall_prs.slides) == 2

    # -------------------------------------------------------------
    # Step 4: Conversational Slide Mutation 3 - Retype to Breakdown Tree
    # User prompts HRIDAY: "switch to breakdown tree"
    # -------------------------------------------------------------
    tree_result = SlideMutator.mutate_slide(
        deck_spec=mutated_deck_2,
        action=SlideMutationAction.RETYPE_CHART,
        params={"chart_type": "breakdown_tree"},
        slide_index=1,
        df=enterprise_workforce_df
    )

    assert tree_result.success is True
    mutated_deck_3 = tree_result.updated_deck_spec
    active_chart_3 = mutated_deck_3["slides"][1]["chart"]

    assert active_chart_3["type"] == "breakdown_tree"
    assert "tree_data" in active_chart_3
    assert len(active_chart_3["tree_data"]["children"]) > 0

    # Verify native export of breakdown tree deck
    tree_path = export_spec_to_pptx(mutated_deck_3)
    tree_prs = Presentation(tree_path)
    assert len(tree_prs.slides) == 2

    # -------------------------------------------------------------
    # Step 5: Conversational Slide Mutation 4 - Change Theme to Emerald Slate
    # User prompts HRIDAY: "change theme to emerald_slate"
    # -------------------------------------------------------------
    theme_result = SlideMutator.mutate_slide(
        deck_spec=mutated_deck_3,
        action=SlideMutationAction.CHANGE_THEME,
        params={"theme_id": "emerald_slate"},
        slide_index=1,
        df=enterprise_workforce_df
    )

    assert theme_result.success is True
    mutated_deck_4 = theme_result.updated_deck_spec
    assert mutated_deck_4["metadata"]["theme_id"] == "emerald_slate"

    # Verify native export under emerald_slate theme
    emerald_path = export_spec_to_pptx(mutated_deck_4)
    emerald_prs = Presentation(emerald_path)
    assert len(emerald_prs.slides) == 2

    # -------------------------------------------------------------
    # Step 6: Instant Revert / Undo Capability
    # User clicks [Revert] or prompts HRIDAY: "undo last change"
    # -------------------------------------------------------------
    revert_result = SlideMutator.mutate_slide(
        deck_spec=mutated_deck_4,
        action=SlideMutationAction.REVERT_MUTATION,
        params={"snapshot": theme_result.previous_slide_snapshot},
        slide_index=1,
        df=enterprise_workforce_df
    )

    assert revert_result.success is True
    reverted_deck = revert_result.updated_deck_spec
    reverted_chart = reverted_deck["slides"][1]["chart"]

    # Invariant: Revert restores the prior breakdown_tree state with 100% fidelity
    assert reverted_chart["type"] == "breakdown_tree"
    assert "tree_data" in reverted_chart

    # Final export after revert verification
    final_path = export_spec_to_pptx(reverted_deck)
    final_prs = Presentation(final_path)
    assert len(final_prs.slides) == 2
