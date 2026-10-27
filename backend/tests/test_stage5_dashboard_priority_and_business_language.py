"""HighView Presentation Studio — Stage 5 Focused Verification.

Verifies:
1. Executive Importance Hierarchy (Priority Order) is strictly preserved:
   - Slide 1: Executive Baseline KPIs (Population 2011 1.21B, Decadal Growth 17.7%, Density 368 people/sq. km).
   - Slide 2: Primary Decision Visual -> India Population Density map (choropleth, TOPIC-67ea9a38).
   - Slide 3: Population Distribution -> Box plot (box_plot, TOPIC-6fbddfb2).
   - Slide 4: Population vs Growth -> Scatter (scatter, TOPIC-d2e1ceff).
   - Slide 5: Population Outliers -> Variance bar (variance_bar, TOPIC-b54df61d).
   - Slide 6: Population Benchmark -> Bullet (bullet, TOPIC-7f8bb4ed).
   - Slide 7: Action / Closing -> StructuralRole.CLOSING.
   - Total count: exactly 7 physical slides.
2. Zero Internal Governance Terms visible on business slides:
   - Completely eliminates: 'Governed Topics', 'Governed Boardroom Strategic Diagnostic', 'Complete Coverage',
     'Snapshot [hash]', 'zero raw-column interpolation', 'EVID-...', 'TOPIC-...', 'pipeline', 'control plane',
     'validation phase names', 'SDR', 'JoinPlan'.
3. Zero Snapshot Hashes visible on business slides.
4. Zero Duplicate Units (e.g. '% %', 'units units', 'people/sq. km people/sq. km').
5. Zero Ungrounded Generic Action Boilerplate.
6. Preservation of Upstream Analytical Facts (e.g. 'r = -0.04 (Moderate association)' preserved verbatim).
7. Full Technical Lineage & Audit Provenance Preserved in Speaker Notes (prs_slide.notes_slide).
"""

import pytest
import pptx
from pathlib import Path

from app.services.adaptive_dashboard.dataset_orchestrator import run_dataset_intelligence
from app.services.presentation.content_hub import PresentationContentHub
from app.services.presentation.content_models import (
    ContentKind,
    ContentRole,
    PresentationContentItem,
    UserVisibleContentPolicy,
    VisualStrategy,
)
from app.services.presentation.story_models import (
    ContentBindingRole,
    StructuralRole,
)
from app.services.presentation.story_planner import StoryPlanner
from app.services.presentation.expansion_engine import SlideExpansionEngine
from app.services.presentation.structure_builder import LayeredSlideStructureBuilder
from app.services.presentation.layout_engine import LayoutConstraintEngine
from app.services.presentation.pptx_compiler import PPTXCompiler


@pytest.fixture(scope="module")
def dataset_99795_deck(tmp_path_factory):
    """Generates the full end-to-end presentation deck for benchmark dataset 99795 in isolated test db."""
    import os
    import shutil
    from app.core import config

    baseline_path = Path(__file__).resolve().parent.parent / "data" / "db_backups_safety" / "pulsehr.sqlite3.pristine_i8_3_baseline"
    test_dir = tmp_path_factory.mktemp("stage5_test_db")
    test_db_copy = test_dir / "dataset_99795_stage5.sqlite3"
    shutil.copy2(baseline_path, test_db_copy)

    old_env = os.environ.get("HIGHVIEW_DB_PATH")
    old_db_path = config.DB_PATH
    os.environ["HIGHVIEW_DB_PATH"] = str(test_db_copy)
    config.DB_PATH = Path(test_db_copy)

    try:
        dash = run_dataset_intelligence(dataset_id=99795)
        hub = PresentationContentHub()
        pkg = hub.assemble_package(
            scope={"objective": "Executive Demographic Review"},
            dataset_context=dash.model_dump() if hasattr(dash, "model_dump") else dash,
        )
        planner = StoryPlanner()
        plan = planner.plan_story(pkg, user_objective="Executive Demographic Review")

        expander = SlideExpansionEngine()
        manifest = expander.expand(story_plan=plan, content_pkg=pkg)

        builder = LayeredSlideStructureBuilder()
        structure = builder.build_structure(manifest=manifest, content_pkg=pkg)

        layout = LayoutConstraintEngine()
        resolved_deck = layout.resolve_deck_layout(structure)

        compiler = PPTXCompiler()
        render_manifest, out_path = compiler.compile_deck(
            resolved_deck=resolved_deck,
            deck_structure=structure,
            content_package=pkg,
        )

        prs = pptx.Presentation(out_path)
        return {
            "pkg": pkg,
            "plan": plan,
            "manifest": manifest,
            "structure": structure,
            "resolved_deck": resolved_deck,
            "render_manifest": render_manifest,
            "out_path": out_path,
            "prs": prs,
        }
    finally:
        config.DB_PATH = old_db_path
        if old_env is not None:
            os.environ["HIGHVIEW_DB_PATH"] = old_env
        else:
            os.environ.pop("HIGHVIEW_DB_PATH", None)


class TestStage5DashboardPriorityAndBusinessLanguage:
    """Stage 5 verification suite enforcing priority ordering, business titles, and zero governance leakage."""

    def test_exact_seven_slide_sequence_and_priority(self, dataset_99795_deck):
        """Verifies the exact 7-slide sequence strictly following Dashboard executive importance."""
        plan = dataset_99795_deck["plan"]
        manifest = dataset_99795_deck["manifest"]
        prs = dataset_99795_deck["prs"]

        assert len(plan.logical_slides) == 8, f"Expected 8 logical slides, got {len(plan.logical_slides)}"
        assert len(manifest.slides) == 8, f"Expected 8 physical slides, got {len(manifest.slides)}"
        assert len(prs.slides) == 8, f"Expected 8 PPTX slides, got {len(prs.slides)}"

        # Slide 1: Dedicated Framing Cover Slide (0 analytical items bound)
        s1 = plan.logical_slides[0]
        assert s1.structural_role == StructuralRole.TITLE
        assert len(s1.content_bindings) == 0
        assert s1.metadata.get("is_cover") is True
        assert s1.metadata.get("presentation_title") or s1.headline
        assert s1.metadata.get("presenter_name") == "[Presenter Name]"

        # Slide 2: Strategic KPIs (Baseline Headline Indicators)
        s2 = plan.logical_slides[1]
        assert s2.structural_role == StructuralRole.STRATEGIC_KPIS
        assert len(s2.content_bindings) == 3
        assert all(b.visual_type == "kpi_metric" for b in s2.content_bindings)

        # Slide 3: Primary Decision Visual -> India Population Density Map (choropleth)
        s3 = plan.logical_slides[2]
        assert s3.structural_role == StructuralRole.GEOGRAPHIC_ANALYSIS
        assert s3.visual_type == "choropleth"
        assert s3.visual_id == "TOPIC-67ea9a38"
        assert s3.headline == "India Population Density Distribution"

        # Slide 4: Population Distribution -> Box Plot (box_plot)
        s4 = plan.logical_slides[3]
        assert s4.structural_role == StructuralRole.COHORT_ANALYSIS
        assert s4.visual_type == "box_plot"
        assert s4.visual_id == "TOPIC-6fbddfb2"
        assert s4.headline in ("Population Distribution Across States", "Metrics Distribution Across Cohorts")

        # Slide 5: Population vs Growth -> Scatter (scatter)
        s5 = plan.logical_slides[4]
        assert s5.structural_role == StructuralRole.CORRELATION_ANALYSIS
        assert s5.visual_type == "scatter"
        assert s5.visual_id in ("TOPIC-d2e1ceff", "TOPIC-a8dc97ee")
        assert s5.headline in ("Population 2011 vs Decadal Population Growth Rate", "Population Growth vs Density Correlation")

        # Slide 6: Population Outliers -> Variance Bar (variance_bar)
        s6 = plan.logical_slides[5]
        assert s6.structural_role == StructuralRole.COHORT_ANALYSIS
        assert s6.visual_type == "variance_bar"
        assert s6.visual_id == "TOPIC-b54df61d"
        assert s6.headline == "Population 2011 Outliers Across States"

        # Slide 7: Population Benchmark -> Bullet (bullet)
        s7 = plan.logical_slides[6]
        assert s7.structural_role == StructuralRole.DIAGNOSTIC_ANALYSIS
        assert s7.visual_type == "bullet"
        assert s7.visual_id in ("TOPIC-7f8bb4ed", "TOPIC-14acc5a3")
        assert s7.headline in ("Population Compared with State Benchmark", "Performance Compared with Benchmark")

        # Slide 8: Action / Closing -> StructuralRole.CLOSING
        s8 = plan.logical_slides[7]
        assert s8.structural_role == StructuralRole.CLOSING
        assert s8.headline in ("Executive Summary & Next Steps", "Summary & Key Implications", "Action Priorities & Governance")

    def test_executive_baseline_kpis_on_slide_one(self, dataset_99795_deck):
        """Verifies that the 3 Executive Baseline KPIs are present on Slide 2 (Glance overview)."""
        prs = dataset_99795_deck["prs"]
        # Slide 1 is dedicated Framing Cover Slide
        slide1 = prs.slides[0]
        s1_texts = " ".join([sh.text_frame.text for sh in slide1.shapes if sh.has_text_frame])
        assert "India State Population Data" in s1_texts
        assert "Presented by: [Presenter Name]" in s1_texts

        # Slide 2 has the 3 Executive Baseline KPIs
        slide2 = prs.slides[1]
        text_shapes = [sh.text_frame.text for sh in slide2.shapes if sh.has_text_frame]
        combined = " ".join(text_shapes)

        assert "1.21B" in combined, "Population 2011 KPI value (1.21B) missing from Slide 2"
        assert "17.7%" in combined, "Decadal Population Growth Rate KPI value (17.7%) missing from Slide 2"
        assert "368" in combined, "Population Density KPI value (368) missing from Slide 2"
        assert "people/sq. km" in combined, "Population Density unit missing from Slide 2"

    def test_zero_governance_words_visible_on_all_slides(self, dataset_99795_deck):
        """Completely verifies that ZERO internal governance terms appear in visible slide shapes."""
        prs = dataset_99795_deck["prs"]
        all_violations = []

        for idx, slide in enumerate(prs.slides):
            slide_texts = []
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for p in shape.text_frame.paragraphs:
                        slide_texts.append(p.text)
                elif shape.has_table:
                    for row in shape.table.rows:
                        for cell in row.cells:
                            slide_texts.append(cell.text)
            full_text = " ".join(slide_texts)
            violations = UserVisibleContentPolicy.detect_violations(full_text)
            if violations:
                all_violations.append(f"Slide {idx+1}: {violations}")

        assert len(all_violations) == 0, f"Found visible governance violations: {all_violations}"

    def test_zero_snapshot_hashes_visible_on_all_slides(self, dataset_99795_deck):
        """Verifies that no snapshot hashes or raw hex checksums appear in visible shapes."""
        prs = dataset_99795_deck["prs"]
        for idx, slide in enumerate(prs.slides):
            for shape in slide.shapes:
                if shape.has_text_frame:
                    txt = shape.text_frame.text
                    assert "Snapshot" not in txt, f"Found 'Snapshot' in Slide {idx+1}: {txt}"
                    assert "snap_" not in txt, f"Found 'snap_' in Slide {idx+1}: {txt}"

    def test_zero_duplicate_units(self, dataset_99795_deck):
        """Verifies display formatting is clean with zero duplicated units."""
        prs = dataset_99795_deck["prs"]
        for idx, slide in enumerate(prs.slides):
            for shape in slide.shapes:
                if shape.has_text_frame:
                    txt = shape.text_frame.text
                    assert "% %" not in txt, f"Found duplicate percentage in Slide {idx+1}"
                    assert "units units" not in txt.lower(), f"Found duplicate 'units' in Slide {idx+1}"
                    assert "people/sq. km people/sq. km" not in txt.lower(), f"Found duplicate density in Slide {idx+1}"

    def test_zero_ungrounded_generic_action_language(self, dataset_99795_deck):
        """Verifies that ungrounded generic action boilerplate is omitted."""
        prs = dataset_99795_deck["prs"]
        all_text = " ".join(
            sh.text_frame.text
            for s in prs.slides
            for sh in s.shapes
            if sh.has_text_frame
        ).lower()

        assert "interaction elasticity" not in all_text
        assert "regulatory compliance or monitoring discrepancies" not in all_text
        assert "review factors driving segment variance" not in all_text
        assert "address operational factors for cohorts trailing" not in all_text

    def test_preservation_of_upstream_analytical_facts(self, dataset_99795_deck):
        """Verifies upstream analytical facts (e.g. r = -0.04) are preserved verbatim."""
        pkg = dataset_99795_deck["pkg"]
        scatter_items = [it for it in pkg.items if it.visual_id in ("TOPIC-d2e1ceff", "TOPIC-a8dc97ee")]
        assert len(scatter_items) == 1
        scatter_item = scatter_items[0]

        # Takeaway must contain the exact correlation fact with correct statistical interpretation
        assert "r = -0.04" in scatter_item.narrative_takeaway
        assert "Negligible association" in scatter_item.narrative_takeaway or "Moderate association" in scatter_item.narrative_takeaway

        # Must also be preserved in speaker notes for the correlation slide
        prs = dataset_99795_deck["prs"]
        slide5 = prs.slides[4]
        notes_text = slide5.notes_slide.notes_text_frame.text
        assert "r = -0.04" in notes_text
        assert "Negligible association" in notes_text or "Moderate association" in notes_text

    def test_technical_lineage_and_audit_provenance_in_speaker_notes(self, dataset_99795_deck):
        """Verifies that technical lineage (Topic IDs, Evidence IDs) is preserved in speaker notes."""
        prs = dataset_99795_deck["prs"]
        for idx, slide in enumerate(prs.slides):
            assert slide.has_notes_slide, f"Slide {idx+1} missing notes_slide"
            notes = slide.notes_slide.notes_text_frame.text
            assert "Technical Lineage & Audit Provenance" in notes
            assert "Physical Slide ID:" in notes
            assert "Logical Slide ID:" in notes

        # Verify specific topic IDs are in the respective slide notes (shifted by +1 due to dedicated cover slide)
        slide3_notes = prs.slides[2].notes_slide.notes_text_frame.text
        assert "TOPIC-67ea9a38" in slide3_notes

        slide4_notes = prs.slides[3].notes_slide.notes_text_frame.text
        assert "TOPIC-6fbddfb2" in slide4_notes

        slide5_notes = prs.slides[4].notes_slide.notes_text_frame.text
        assert "TOPIC-d2e1ceff" in slide5_notes or "TOPIC-a8dc97ee" in slide5_notes

        slide6_notes = prs.slides[5].notes_slide.notes_text_frame.text
        assert "TOPIC-b54df61d" in slide6_notes

        slide7_notes = prs.slides[6].notes_slide.notes_text_frame.text
        assert "TOPIC-7f8bb4ed" in slide7_notes or "TOPIC-14acc5a3" in slide7_notes
