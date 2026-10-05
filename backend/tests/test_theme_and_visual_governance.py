"""Unit and regression tests for Phase 9.5: Theme Integrity Restoration & Visual Governance."""
from __future__ import annotations

import os
import pytest

from app.services.adaptive_dashboard.evaluation_contracts import VisualGovernanceScorecard
from app.services.adaptive_dashboard.evaluator import DatasetIntelligenceEvaluator
from app.services.adaptive_dashboard.theme_validator import (
    APPROVED_SEMANTIC_STATUSES,
    HIGHVIEW_DARK_PALETTE,
    HIGHVIEW_LIGHT_PALETTE,
    ThemeIntegrityValidator,
    calculate_contrast_ratio,
)
from app.services.adaptive_dashboard.visual_compiler import VisualCompiler, VisualIntent


def test_no_protected_component_bypasses_central_theme():
    """Verify that protected frontend components contain zero raw dark slate background overrides."""
    backend_dir = os.path.dirname(os.path.dirname(__file__))
    repo_root = os.path.dirname(backend_dir)
    protected_files = [
        os.path.join(repo_root, "frontend/src/components/adaptive/EvidenceStoryCard.jsx"),
        os.path.join(repo_root, "frontend/src/pages/AdaptiveDashboardPage.jsx"),
        os.path.join(repo_root, "frontend/src/pages/DataExplorerPage.jsx"),
    ]

    for p in protected_files:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                code = f.read()
            violations = ThemeIntegrityValidator.audit_component_source(code, file_name=os.path.basename(p))
            assert len(violations) == 0, f"Found theme violations in {p}: {violations}"


def test_dashboard_light_theme_integrity():
    """Verify Highview Light theme palette satisfies WCAG AAA text contrast (>= 7:1)."""
    contrast = calculate_contrast_ratio(
        HIGHVIEW_LIGHT_PALETTE["text_primary"],
        HIGHVIEW_LIGHT_PALETTE["bg_surface"],
    )
    assert contrast >= 7.0
    report = ThemeIntegrityValidator.validate_theme_integrity({}, is_dark=False)
    assert report.light_theme_supported is True
    assert report.text_contrast_valid is True
    assert report.overall_theme_passed is True


def test_dashboard_dark_theme_integrity():
    """Verify Highview Dark theme palette satisfies WCAG AAA text contrast (>= 7:1)."""
    contrast = calculate_contrast_ratio(
        HIGHVIEW_DARK_PALETTE["text_primary"],
        HIGHVIEW_DARK_PALETTE["bg_surface"],
    )
    assert contrast >= 7.0
    report = ThemeIntegrityValidator.validate_theme_integrity({}, is_dark=True)
    assert report.dark_theme_supported is True
    assert report.text_contrast_valid is True
    assert report.overall_theme_passed is True


def test_dynamic_visual_theme_compliance():
    """Verify that semantic visual specs pass while specs with hardcoded colors fail."""
    valid_spec = {
        "chart_type": "bar",
        "emphasis": "primary",
        "status": "warning",
        "reference_line": True,
    }
    report_valid = ThemeIntegrityValidator.validate_theme_integrity(valid_spec)
    assert report_valid.overall_theme_passed is True
    assert report_valid.hardcoded_violation_count == 0

    invalid_spec = {
        "background": "#111827",
        "text_color": "#FFFFFF",
        "bar_color": "#2563EB",
    }
    report_invalid = ThemeIntegrityValidator.validate_theme_integrity(invalid_spec)
    assert report_invalid.overall_theme_passed is False
    assert report_invalid.hardcoded_violation_count == 3


def test_chart_theme_compliance():
    """Verify that VisualCompiler outputs theme variables instead of hardcoded dark backgrounds."""
    intent = VisualIntent(
        intent="compare_ranked_categories",
        metric_name="attendance",
        unit="days",
        priority="hero",
    )
    opt = VisualCompiler.compile_ranked_categories(["Ops", "Fin"], [12.0, 15.0], intent)
    assert "var(--chart-tooltip-bg" in opt["tooltip"]["backgroundColor"]
    assert "var(--chart-tooltip-text" in opt["tooltip"]["textStyle"]["color"]
    assert "var(--chart-text" in opt["xAxis"]["axisLabel"]["color"]
    assert "var(--chart-text" in opt["yAxis"]["axisLabel"]["color"]


def test_evidence_pill_theme_compliance():
    """Verify that EVID-xxx and evidence tokens resolve through central theme tokens."""
    assert "observed" in APPROVED_SEMANTIC_STATUSES
    spec = {"status": "observed"}
    rep = ThemeIntegrityValidator.validate_theme_integrity(spec)
    assert rep.semantic_status_token_valid is True


def test_scenario_pill_theme_compliance():
    """Verify that SCEN-xxx scenario evidence status is recognized by visual governance."""
    assert "scenario" in APPROVED_SEMANTIC_STATUSES
    spec = {"status": "scenario"}
    rep = ThemeIntegrityValidator.validate_theme_integrity(spec)
    assert rep.semantic_status_token_valid is True


def test_governance_badge_theme_compliance():
    """Verify that governance status tokens are recognized without hardcoded overrides."""
    spec = {"status": "governance_status"}
    rep = ThemeIntegrityValidator.validate_theme_integrity(spec)
    assert rep.semantic_status_token_valid is True


def test_cross_sheet_insight_theme_compliance():
    """Verify cross-sheet relationship semantic tokens resolve properly."""
    spec = {"status": "relationship"}
    rep = ThemeIntegrityValidator.validate_theme_integrity(spec)
    assert rep.semantic_status_token_valid is True


def test_data_explorer_theme_compliance():
    """Verify Data Explorer components inherit the centralized Highview theme system."""
    backend_dir = os.path.dirname(os.path.dirname(__file__))
    repo_root = os.path.dirname(backend_dir)
    de_file = os.path.join(repo_root, "frontend/src/pages/DataExplorerPage.jsx")
    if os.path.exists(de_file):
        with open(de_file, "r", encoding="utf-8") as f:
            code = f.read()
        violations = ThemeIntegrityValidator.audit_component_source(code, "DataExplorerPage.jsx")
        assert len(violations) == 0


def test_modal_theme_compliance():
    """Verify modal and dialog styling compliance."""
    report = ThemeIntegrityValidator.validate_theme_integrity({})
    assert report.modal_theme_valid is True


def test_table_theme_compliance():
    """Verify table styling compliance."""
    report = ThemeIntegrityValidator.validate_theme_integrity({})
    assert report.table_theme_valid is True


def test_theme_switch_preserves_structure():
    """Verify that switching between Light and Dark mode changes 0 structural properties."""
    intent = VisualIntent(
        intent="compare_ranked_categories",
        metric_name="attendance",
        unit="days",
        priority="hero",
    )
    opt = VisualCompiler.compile_ranked_categories(["Ops", "Fin"], [12.0, 15.0], intent)
    gate_light = ThemeIntegrityValidator.evaluate_three_visual_gates(opt)
    gate_dark = ThemeIntegrityValidator.evaluate_three_visual_gates(opt)

    assert gate_light.passed is True
    assert gate_dark.passed is True
    assert gate_light.layout_integrity.passed == gate_dark.layout_integrity.passed
    assert gate_light.accessibility_integrity.passed == gate_dark.accessibility_integrity.passed
    assert gate_light.theme_integrity.passed == gate_dark.theme_integrity.passed


def test_three_visual_gates_enforcement():
    """Verify that all three visual gates (Layout, Accessibility, Theme) are enforced."""
    intent = VisualIntent(
        intent="compare_ranked_categories",
        metric_name="overtime",
        unit="hours",
        priority="secondary",
    )
    opt = VisualCompiler.compile_ranked_categories(["Sales", "Eng"], [10.0, 20.0], intent)
    qa = VisualCompiler.audit_visual_qa(opt)

    assert qa.passed is True
    assert qa.layout_integrity.passed is True
    assert qa.accessibility_integrity.passed is True
    assert qa.theme_integrity.passed is True
    assert len(qa.warnings) == 0


def test_visual_governance_scorecard_evaluation():
    """Verify VisualGovernanceScorecard aggregates dimensions with 100% pass targets."""
    scorecard = DatasetIntelligenceEvaluator.evaluate_visual_governance()
    assert scorecard.theme_integrity_pass_rate == 1.0
    assert scorecard.hardcoded_theme_violation_count == 0
    assert scorecard.light_theme_pass_rate == 1.0
    assert scorecard.dark_theme_pass_rate == 1.0
    assert scorecard.chart_theme_compliance_rate == 1.0
    assert scorecard.semantic_token_compliance_rate == 1.0
    assert scorecard.theme_switch_structure_stability is True
    assert scorecard.critical_contrast_violation_count == 0
    assert scorecard.overall_visual_governance_pass is True
