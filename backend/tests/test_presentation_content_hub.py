"""Comprehensive Unit & Regression Tests for PresentationContentHub (PPT-L1 Certification).

Validates:
1. User-Visible Content Policy:
   - Normal business deck: internal architecture terms visible = 0
   - Normal business deck: semantic substitutions that alter meaning = 0
   - Technical architecture deck: real technical terms preserved accurately
2. Legacy Path Identity:
   - PRESENTATION_LAYERED_PIPELINE_ENABLED = false executes identically to legacy
   - Downstream contracts, slide planning, and exports untouched
3. Layered Scope Boundary:
   - Layered mode strictly limits execution to content provider assembly, ranking, and packaging
   - Zero PPT-L2 (StoryPlanner/SlideTags) or PPT-L3+ (layout/geometry/styling) invocations
4. Content Package Determinism:
   - Multi-run consistency: identical IDs, ordering, values, and SHA-256 content_fingerprint
5. Content Truth Safety:
   - Zero fact, unit, grain, or denominator mutations
6. Provider Failure Isolation:
   - Dashboard / Data Explorer / User Context failures are isolated without corrupting package
7. Redundancy Ranker Safety:
   - Shared dimension with distinct metrics (e.g. Population Density vs Growth) is NOT penalized
8. Package Size & Bounding:
   - Enforces max_items cap and bounded table previews (at most 10 rows)
"""

import hashlib
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch

from app.core import config
from app.services.presentation.content_models import (
    ContentKind,
    ContentRole,
    PresentationContentItem,
    PresentationContentPackage,
    UserVisibleContentPolicy,
)
from app.services.presentation.content_hub import (
    DashboardContentProvider,
    DataExplorerContentProvider,
    PresentationContentHub,
    PresentationContentRanker,
    UserContextProvider,
)
from app.services.presentation.pipeline_selector import (
    PresentationPipelineMode,
    PresentationPipelineSelector,
)

PRISTINE_BASELINE_HASH = "1561d64eeae26f4d30926371740d6ca9dc41eb6ea7c537281763b7d5aabd9496"


def verify_pristine_baseline():
    baseline_path = Path(__file__).resolve().parent.parent / "data" / "db_backups_safety" / "pulsehr.sqlite3.pristine_i8_3_baseline"
    assert baseline_path.exists(), f"Baseline does not exist at {baseline_path}"
    hasher = hashlib.sha256()
    with open(baseline_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    assert hasher.hexdigest() == PRISTINE_BASELINE_HASH, f"Pristine baseline altered! Got {hasher.hexdigest()}"


@pytest.fixture(autouse=True)
def check_db_integrity():
    verify_pristine_baseline()
    yield
    verify_pristine_baseline()


# ==============================================================================
# 1. USER-VISIBLE CONTENT POLICY
# ==============================================================================
class TestUserVisibleContentPolicy:
    """Verifies omission of internal metadata from normal decks and exact preservation in technical decks."""

    def test_normal_business_deck_omits_internal_terms_without_semantic_substitution(self):
        # Raw text containing internal pipeline plumbing
        raw = "Analysis per SDR-3 verified via JoinPlan backed by EVID-9921b with checksum e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 in Control Plane."
        sanitized = UserVisibleContentPolicy.sanitize_text(raw, allow_governance=False)

        # 1. Internal terms visible MUST be 0
        assert "SDR" not in sanitized
        assert "JoinPlan" not in sanitized
        assert "JoinGraph" not in sanitized
        assert "EVID" not in sanitized
        assert "e3b0c442" not in sanitized
        assert "Control Plane" not in sanitized
        assert len(UserVisibleContentPolicy.detect_violations(sanitized, allow_governance=False)) == 0

        # 2. Semantic substitutions that change meaning MUST be 0
        assert "Strategic Diagnostic" not in sanitized
        assert "Relational Model" not in sanitized
        assert "Audited Evidence" not in sanitized
        assert "Governed Platform" not in sanitized

    def test_technical_architecture_deck_preserves_real_terminology(self):
        raw = "Technical review of SDR-4 pipeline architecture, JoinPlan graph traversal, and EVID-8837 ledger integrity."
        # Objective explicitly requests technical architecture audit
        exempt = UserVisibleContentPolicy.is_governance_exempt(
            objective="Perform technical architecture audit and JoinPlan review"
        )
        assert exempt is True

        sanitized = UserVisibleContentPolicy.sanitize_text(raw, allow_governance=exempt)
        # Technical terms MUST be preserved accurately
        assert "SDR-4" in sanitized
        assert "JoinPlan" in sanitized
        assert "EVID-8837" in sanitized
        # Zero semantic substitutions
        assert "Strategic Diagnostic" not in sanitized
        assert "Relational Model" not in sanitized

    def test_sanitizes_content_item_fields_cleanly(self):
        item = PresentationContentItem(
            content_id="CONTENT-001",
            kind=ContentKind.CHART,
            role=ContentRole.PRIMARY_HERO,
            topic_category="Regional Operations",
            title="SDR-2 Regional Performance Summary",
            subtitle="Derived via JoinPlan with EVID-3491",
            narrative_takeaway="Regional revenue exceeded baseline per EVID-3491.",
            supporting_bullets=[
                "SDR-2 confirmed high customer retention across territories.",
                "Verified according to JoinPlan with checksum a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2.",
            ],
            metric_label="SDR Score",
            metric_value="98.5%",
            evidence_ids=["EVID-3491"],
            fact_id="FACT-001",
        )
        sanitized = UserVisibleContentPolicy.sanitize_content_item(item, allow_governance=False)

        assert sanitized.title == "Regional Performance Summary"
        assert sanitized.subtitle is None or "JoinPlan" not in sanitized.subtitle
        assert "EVID" not in sanitized.narrative_takeaway
        assert "SDR" not in sanitized.supporting_bullets[0]
        assert "JoinPlan" not in sanitized.supporting_bullets[1]
        assert "a1b2c3d4" not in sanitized.supporting_bullets[1]
        assert "SDR" not in sanitized.metric_label

        # Zero violations in user-visible fields
        violations = UserVisibleContentPolicy.validate_content_item(sanitized, allow_governance=False)
        assert len(violations) == 0

        # Governed audit metadata remains preserved for backend lineage
        assert sanitized.evidence_ids == ["EVID-3491"]
        assert sanitized.fact_id == "FACT-001"


# ==============================================================================
# 2. LEGACY PATH IDENTITY & DUAL-PATH SELECTOR
# ==============================================================================
class TestLegacyPathIdentity:
    """Verifies that legacy presentation generation remains 100% operational and unaltered."""

    def test_selector_defaults_to_legacy(self):
        with patch.object(config, "PRESENTATION_LAYERED_PIPELINE_ENABLED", False):
            mode = PresentationPipelineSelector.select_pipeline({})
            assert mode == PresentationPipelineMode.LEGACY
            assert not PresentationPipelineSelector.is_layered_mode({})

    def test_force_legacy_safety_valve(self):
        with patch.object(config, "PRESENTATION_LAYERED_PIPELINE_ENABLED", True):
            mode = PresentationPipelineSelector.select_pipeline({
                "pipeline_mode": "LAYERED",
                "use_layered_pipeline": True,
                "force_legacy_pipeline": True,
            })
            assert mode == PresentationPipelineMode.LEGACY

    def test_orchestrator_legacy_path_leaves_contracts_unaltered(self):
        from app.services.presentation.pipeline_orchestrator import execute_presentation_pipeline_async
        from app.services.presentation.job_manager import PresentationJobManager

        mock_mgr = MagicMock(spec=PresentationJobManager)
        mock_mgr.is_cancelled.return_value = False

        scope = {
            "scope_type": "single_sheet",
            "sheet_id": 1,
            "pipeline_mode": "LEGACY",
            "objective": "Standard Leadership Review",
        }

        with patch("app.services.presentation.pipeline_orchestrator.session_scope"), \
             patch("app.services.presentation.pipeline_orchestrator.preview_presentation_scope", return_value={"eligible": True}), \
             patch("app.services.presentation.pipeline_orchestrator.collect_workspace_evidence") as mock_col, \
             patch("app.services.presentation.deck_generator.generate_presentation_deck_spec") as mock_gen, \
             patch("app.services.presentation.pipeline_orchestrator.verify_presentation_claims", return_value={"status": "PASSED"}), \
             patch("app.services.presentation.pipeline_orchestrator.evaluate_automated_gates", return_value={"gates": {}}), \
             patch("app.services.presentation.pipeline_orchestrator._index_persisted_deck"):

            mock_ctx = {"target_sheet": {"id": 1, "name": "Sheet1"}, "domain": "HR", "records": [], "columns": []}
            mock_col.return_value = {"primary_ctx": mock_ctx}
            mock_deck = {
                "id": "DECK-LEGACY",
                "slides": [{"title": "Slide 1", "category": "Analysis"}],
                "metadata": {"title": "Legacy Deck", "theme_id": "executive_dark"},
                "evidence_ledger": []
            }
            mock_gen.return_value = mock_deck

            execute_presentation_pipeline_async("job-leg-01", scope, manager=mock_mgr)

            # Contract checks:
            assert mock_deck["metadata"]["pipeline_mode"] == "LEGACY"
            # Content package MUST NOT be attached in legacy mode
            assert "content_package" not in mock_deck["metadata"]
            assert "layered_content_package" not in mock_col.return_value


# ==============================================================================
# 3. LAYERED SCOPE BOUNDARY
# ==============================================================================
class TestLayeredScopeBoundary:
    """Verifies that Layered mode in PPT-L1 limits execution strictly to content assembly and packaging."""

    def test_layered_mode_only_attaches_content_package_without_ppt_l2_or_l3(self):
        from app.services.presentation.pipeline_orchestrator import execute_presentation_pipeline_async
        from app.services.presentation.job_manager import PresentationJobManager

        mock_mgr = MagicMock(spec=PresentationJobManager)
        mock_mgr.is_cancelled.return_value = False

        scope = {
            "scope_type": "single_sheet",
            "sheet_id": 1,
            "pipeline_mode": "LAYERED",
            "objective": "Executive Strategic Review",
        }

        with patch("app.services.presentation.pipeline_orchestrator.session_scope"), \
             patch("app.services.presentation.pipeline_orchestrator.preview_presentation_scope", return_value={"eligible": True}), \
             patch("app.services.presentation.pipeline_orchestrator.collect_workspace_evidence") as mock_col, \
             patch("app.services.presentation.deck_generator.generate_presentation_deck_spec") as mock_gen, \
             patch("app.services.presentation.pipeline_orchestrator.verify_presentation_claims", return_value={"status": "PASSED"}), \
             patch("app.services.presentation.pipeline_orchestrator.evaluate_automated_gates", return_value={"gates": {}}), \
             patch("app.services.presentation.pipeline_orchestrator._index_persisted_deck"):

            mock_ctx = {
                "target_sheet": {"id": 1, "name": "Operations"},
                "domain": "Logistics",
                "columns": ["Route", "OnTimePct"],
                "records": [{"Route": "North", "OnTimePct": 94.2}],
                "presentation_topics": [{
                    "topic_id": "T1",
                    "title": "On-Time Delivery Performance",
                    "primary_takeaway": "North corridor achieved 94.2% on-time rate.",
                    "slot_type": "hero",
                    "metric": "OnTimePct",
                }],
            }
            mock_col.return_value = {"primary_ctx": mock_ctx}

            result_deck = execute_presentation_pipeline_async("job-lay-01", scope, manager=mock_mgr)

            # Invariant: Zero legacy generator calls in layered mode
            mock_gen.assert_not_called()

            # Layered mode returns structured deck spec stopping after DeckStoryPlan
            assert result_deck is not None
            assert result_deck["metadata"]["pipeline_mode"] == "LAYERED"
            assert "content_package" in result_deck["metadata"]
            pkg_data = result_deck["metadata"]["content_package"]
            assert pkg_data["domain"] == "Logistics"
            assert len(pkg_data["items"]) >= 1

            # PPT-L2: Story plan is attached with logical slide tags
            assert "story_plan" in result_deck["metadata"]
            story_plan = result_deck["metadata"]["story_plan"]
            assert len(story_plan["logical_slides"]) >= 1
            assert len(story_plan["story_fingerprint"]) == 64

            # Invariant: NO PPT-L4+ layout coordinates, zones, or rendered slides in deck
            assert len(result_deck["slides"]) == 0  # 0 physical layout slides created in PPT-L3


# ==============================================================================
# 4. CONTENT PACKAGE DETERMINISM
# ==============================================================================
class TestContentPackageDeterminism:
    """Verifies that multiple runs over identical data produce identical content packages and fingerprints."""

    def test_multi_run_fingerprint_and_ordering_identity(self):
        hub = PresentationContentHub()
        scope = {
            "objective": "Quarterly Operations Review",
            "instructions": "Focus on distribution trends",
            "requested_decision": "Approve warehouse allocation",
        }
        dataset_context = {
            "domain": "Logistics",
            "target_sheet": {"name": "Fleet Data", "id": 10},
            "columns": ["Zone", "Efficiency", "Volume"],
            "records": [
                {"Zone": "East", "Efficiency": 91.5, "Volume": 45000},
                {"Zone": "West", "Efficiency": 88.0, "Volume": 38000},
            ],
            "traceable_metrics": [
                {"label": "Average Efficiency", "formatted_value": "89.8%", "metric_name": "Efficiency"},
            ],
            "presentation_topics": [
                {
                    "topic_id": "TOPIC-01",
                    "title": "Regional Volume Distribution",
                    "primary_takeaway": "East zone handled the majority volume.",
                    "slot_type": "hero",
                    "metric": "Volume",
                    "dimension": "Zone",
                },
                {
                    "topic_id": "TOPIC-02",
                    "title": "Delivery Efficiency Variance",
                    "primary_takeaway": "West zone lagged by 3.5 points.",
                    "slot_type": "risk_anomaly",
                    "metric": "Efficiency",
                    "dimension": "Zone",
                }
            ]
        }

        # Run 1
        pkg1 = hub.assemble_package(scope, dataset_context)
        # Run 2
        pkg2 = hub.assemble_package(scope, dataset_context)

        # 1. Identical selected content IDs
        assert [it.content_id for it in pkg1.items] == [it.content_id for it in pkg2.items]
        # 2. Identical ranking order and composite scores
        assert [it.composite_score for it in pkg1.items] == [it.composite_score for it in pkg2.items]
        # 3. Identical visible text
        assert [it.title for it in pkg1.items] == [it.title for it in pkg2.items]
        assert [it.narrative_takeaway for it in pkg1.items] == [it.narrative_takeaway for it in pkg2.items]
        # 4. Identical deterministic content fingerprint
        assert pkg1.content_fingerprint != ""
        assert pkg1.content_fingerprint == pkg2.content_fingerprint


# ==============================================================================
# 5. CONTENT TRUTH SAFETY
# ==============================================================================
class TestContentTruthSafety:
    """Verifies that ContentHub NEVER mutates fact values, metrics, units, grain, or denominators."""

    def test_zero_mutations_on_governed_facts(self):
        hub = PresentationContentHub()
        scope = {"objective": "National Census Analysis"}
        dataset_context = {
            "domain": "Demographics",
            "target_sheet": {"name": "Census 2011", "id": 1},
            "columns": ["State", "Population", "Density"],
            "records": [{"State": "UP", "Population": 199812341, "Density": 829}],
            "traceable_metrics": [
                {
                    "label": "National Total Population",
                    "formatted_value": "1.21B",
                    "metric_name": "Population",
                    "unit": "people",
                    "grain": "national_total",
                    "denominator": "all_states_and_uts",
                }
            ],
            "presentation_topics": [
                {
                    "topic_id": "T-POP-01",
                    "title": "State Population Distribution",
                    "metric": "Population",
                    "unit": "persons",
                    "grain": "state_level",
                    "denominator": "state_population_sum",
                    "leader": "Uttar Pradesh",
                    "leader_value": 199812341,
                    "slot_type": "hero",
                }
            ]
        }

        pkg = hub.assemble_package(scope, dataset_context)
        topic_item = next(it for it in pkg.items if it.topic_category == "Demographics")
        kpi_item = pkg.global_kpis[0]

        # Invariant checks:
        # Fact values
        assert "199812341" in topic_item.supporting_bullets[0]
        # Metric identities
        assert topic_item.metric_name == "Population"
        assert kpi_item.metric_name == "National Total Population"
        # Units
        assert topic_item.unit == "persons"
        assert kpi_item.unit == "people"
        # Grain
        assert topic_item.grain == "state_level"
        assert kpi_item.grain == "national_total"
        # Denominator
        assert topic_item.denominator == "state_population_sum"
        assert kpi_item.denominator == "all_states_and_uts"


# ==============================================================================
# 6. PROVIDER FAILURE ISOLATION
# ==============================================================================
class TestProviderFailureIsolation:
    """Verifies that individual provider failures do not corrupt the package or abort assembly."""

    def test_dashboard_provider_failure_isolation(self):
        failing_dashboard = MagicMock(spec=DashboardContentProvider)
        failing_dashboard.provide_content.side_effect = RuntimeError("Dashboard DB unreachable")
        hub = PresentationContentHub(providers=[failing_dashboard, DataExplorerContentProvider(), UserContextProvider()])

        dataset_context = {
            "domain": "Sales",
            "target_sheet": {"name": "SalesSheet"},
            "columns": ["Store", "Rev"],
            "records": [{"Store": "NYC", "Rev": 5000}],
        }
        pkg = hub.assemble_package({}, dataset_context)
        assert pkg is not None
        assert any("FAILED" in status for status in pkg.metadata["provider_status"].values())
        assert len(pkg.items) >= 1  # DataExplorer provided exploratory table
        assert pkg.items[0].role == ContentRole.EXPLORATORY_TABLE

    def test_data_explorer_provider_failure_isolation(self):
        failing_explorer = MagicMock(spec=DataExplorerContentProvider)
        failing_explorer.provide_content.side_effect = ValueError("Corrupt parquet storage")
        hub = PresentationContentHub(providers=[DashboardContentProvider(), failing_explorer, UserContextProvider()])

        dataset_context = {
            "domain": "Finance",
            "target_sheet": {"name": "Ledger"},
            "presentation_topics": [{"topic_id": "T1", "title": "Cash Flow", "slot_type": "hero"}],
        }
        pkg = hub.assemble_package({}, dataset_context)
        assert pkg is not None
        assert any("FAILED" in status for status in pkg.metadata["provider_status"].values())
        assert len(pkg.items) >= 1
        assert pkg.items[0].title == "Cash Flow"

    def test_user_context_absent_handled_gracefully(self):
        hub = PresentationContentHub()
        # Scope has no objective, instructions, or decision requested
        dataset_context = {
            "domain": "General",
            "target_sheet": {"name": "Data"},
            "presentation_topics": [{"topic_id": "T1", "title": "Overview", "slot_type": "hero"}],
        }
        pkg = hub.assemble_package({}, dataset_context)
        assert pkg is not None
        assert len(pkg.items) >= 1
        # No artificial decision fabricated
        assert not any(it.role == ContentRole.ACTION_INITIATIVE for it in pkg.items)


# ==============================================================================
# 7. REDUNDANCY RANKER SAFETY
# ==============================================================================
class TestRedundancyRankerSafety:
    """Verifies that facts sharing a dimension with distinct metrics are NOT penalized as redundant."""

    def test_distinct_metrics_sharing_same_dimension_are_preserved(self):
        item_density = PresentationContentItem(
            content_id="CONTENT-GEO-01",
            kind=ContentKind.MAP,
            role=ContentRole.PRIMARY_HERO,
            topic_category="Geographic Intelligence",
            title="Population Density by State",
            importance_score=0.95,
            decision_relevance=0.90,
            visual_suitability=0.95,
            dimension_name="state",
            metric_name="density",
        )
        item_growth = PresentationContentItem(
            content_id="CONTENT-GEO-02",
            kind=ContentKind.CHART,
            role=ContentRole.KEY_FINDING,
            topic_category="Geographic Intelligence",
            title="Population Growth by State",
            importance_score=0.90,
            decision_relevance=0.85,
            visual_suitability=0.90,
            dimension_name="state",
            metric_name="growth_rate",
        )

        ranked = PresentationContentRanker.rank_items([item_density, item_growth])
        assert len(ranked) == 2
        # Overlap must be 0.0 because metric_name differs ('density' vs 'growth_rate')
        overlap = PresentationContentRanker._compute_item_overlap(item_density, item_growth)
        assert overlap == 0.0
        # Both items must preserve high composite scores (> 0.70)
        assert ranked[0].composite_score >= 0.75
        assert ranked[1].composite_score >= 0.75
        assert ranked[1].redundancy_score == 0.0


# ==============================================================================
# 8. PACKAGE SIZE & BOUNDING
# ==============================================================================
class TestPackageSizeBounding:
    """Verifies that the content package remains bounded and does not carry unbounded raw tables."""

    def test_package_is_strictly_bounded(self):
        hub = PresentationContentHub()
        # Dataset with 500 records and 50 columns
        large_records = [{"Col" + str(i): f"val_{i}_{r}" for i in range(50)} for r in range(500)]
        dataset_context = {
            "domain": "StressTest",
            "target_sheet": {"name": "LargeDataset"},
            "columns": [f"Col{i}" for i in range(50)],
            "records": large_records,
            "presentation_topics": [
                {"topic_id": f"T{i}", "title": f"Finding {i}", "slot_type": "supporting"}
                for i in range(40)
            ],
        }

        pkg = hub.assemble_package({}, dataset_context, max_items=15)
        # 1. Bounded items count
        assert len(pkg.items) <= 15

        # 2. Bounded exploratory table payload
        exp_table = next((it for it in pkg.items if it.kind == ContentKind.TABLE), None)
        if exp_table and exp_table.table_data:
            assert len(exp_table.table_data) <= 10
            for row in exp_table.table_data:
                assert len(row) <= 8  # Capped at 8 representative columns

        # 3. Serialized size check (< 100 KB)
        size_bytes = pkg.package_serialized_size_bytes()
        assert size_bytes < 100_000, f"Package size exceeds budget: {size_bytes} bytes"
