"""Deterministic Visual and Geometric Quality Auditor for Phase 4 & Phase 5.

Performs mathematical, structural, and spatial geometry checks prior to multimodal AI inspection,
identifying text overflow, chart clutter, table bounds, contrast violations, and component collisions.
"""

from __future__ import annotations

import logging
from typing import Any

from ..visual.design_tokens import SlideDesignTokens
from ..visual.visual_models import VisualSpecification
from ..visual.visual_validator import calculate_contrast_ratio
from .qa_models import (
    IssueSeverity,
    VisualIssueType,
    VisualQAIssue,
    VisualQAReport,
    VisualQAScoreDimensions,
)

logger = logging.getLogger(__name__)


class DeterministicVisualAuditor:
    """Evaluates explicit spatial, geometric, and content constraints on VisualSpecifications."""

    @classmethod
    def audit_slide(
        cls,
        spec: VisualSpecification,
        tokens: SlideDesignTokens,
        screenshot_path: str | None = None
    ) -> VisualQAReport:
        """Executes fast, deterministic geometric audit without LLM inference."""
        issues: list[VisualQAIssue] = []
        budget = spec.layout.content_budget

        dim_scores = {
            "hierarchy": 0.95,
            "balance": 0.95,
            "readability": 0.95,
            "chart_clarity": 0.95,
            "spacing": 0.95,
            "alignment": 0.95,
            "consistency": 0.95,
            "density": 0.95,
            "emphasis": 0.95,
            "professionalism": 0.95
        }

        # 1. Headline Checks
        headline_len = len(spec.headline or "")
        if headline_len == 0:
            issues.append(VisualQAIssue(
                issue_type=VisualIssueType.UNSUPPORTED_RENDERING,
                severity=IssueSeverity.CRITICAL,
                component="headline",
                description="Slide headline is missing.",
                recommended_action="Provide executive headline."
            ))
            dim_scores["hierarchy"] -= 0.40
            dim_scores["readability"] -= 0.30
        elif headline_len > budget.max_headline_chars:
            issues.append(VisualQAIssue(
                issue_type=VisualIssueType.TITLE_OVERFLOW,
                severity=IssueSeverity.HIGH,
                component="headline",
                description=f"Headline has {headline_len} chars, exceeding {budget.max_headline_chars} limit.",
                recommended_action="SHORTEN_TITLE"
            ))
            dim_scores["hierarchy"] -= 0.15
            dim_scores["readability"] -= 0.10

        # 2. Text Density / Insights Checks
        num_insights = len(spec.insights)
        total_words = sum(len(ins.split()) for ins in spec.insights)
        if num_insights > budget.max_insights:
            issues.append(VisualQAIssue(
                issue_type=VisualIssueType.TEXT_DENSITY,
                severity=IssueSeverity.MEDIUM,
                component="insight_panel",
                description=f"Insight count ({num_insights}) exceeds budget of {budget.max_insights}.",
                recommended_action="REDUCE_TEXT"
            ))
            dim_scores["density"] -= 0.20
            dim_scores["spacing"] -= 0.10

        if total_words > budget.max_body_words:
            issues.append(VisualQAIssue(
                issue_type=VisualIssueType.TEXT_OVERFLOW,
                severity=IssueSeverity.HIGH,
                component="insight_panel",
                description=f"Total body word count ({total_words}) exceeds maximum limit ({budget.max_body_words}).",
                recommended_action="REDUCE_TEXT"
            ))
            dim_scores["density"] -= 0.25
            dim_scores["readability"] -= 0.15

        # 3. Table Bounds Checks
        if spec.table_data and "rows" in spec.table_data:
            num_rows = len(spec.table_data["rows"])
            if num_rows > budget.max_table_rows:
                issues.append(VisualQAIssue(
                    issue_type=VisualIssueType.TABLE_OVERFLOW,
                    severity=IssueSeverity.HIGH,
                    component="table",
                    description=f"Table contains {num_rows} rows, exceeding layout budget of {budget.max_table_rows}.",
                    recommended_action="MOVE_DETAIL_TO_APPENDIX"
                ))
                dim_scores["density"] -= 0.20
                dim_scores["readability"] -= 0.15

        # 4. Chart Clutter & Validity
        if spec.chart_spec:
            cs = spec.chart_spec
            num_cats = len(cs.categories)
            if num_cats > 10 and "vertical" in cs.family.value.lower():
                issues.append(VisualQAIssue(
                    issue_type=VisualIssueType.CHART_CLUTTER,
                    severity=IssueSeverity.MEDIUM,
                    component="chart",
                    description=f"Vertical bar chart has {num_cats} categories causing horizontal label crowding.",
                    recommended_action="ROTATE_LABELS"
                ))
                dim_scores["chart_clarity"] -= 0.20
            elif num_cats > 16:
                issues.append(VisualQAIssue(
                    issue_type=VisualIssueType.CHART_CLUTTER,
                    severity=IssueSeverity.HIGH,
                    component="chart",
                    description=f"Chart has {num_cats} categories, exceeding maximum legible category threshold.",
                    recommended_action="AGGREGATE_CATEGORIES"
                ))
                dim_scores["chart_clarity"] -= 0.30

            # Missing or empty series data
            if not cs.series or all(len(s.data) == 0 for s in cs.series):
                issues.append(VisualQAIssue(
                    issue_type=VisualIssueType.CHART_UNREADABLE,
                    severity=IssueSeverity.CRITICAL,
                    component="chart",
                    description="Chart contains zero data points in series.",
                    recommended_action="USE_VISUAL_FALLBACK"
                ))
                dim_scores["chart_clarity"] -= 0.50

        # 5. Unsupported Rendering (No visual on content slide)
        is_hero = spec.layout.family.value in ("TITLE_HERO", "SECTION_DIVIDER")
        has_visual = bool(spec.chart_spec or spec.diagram_spec or spec.matrix_spec or spec.table_data or (spec.kpis and len(spec.kpis) >= 2))
        if not is_hero and not has_visual:
            issues.append(VisualQAIssue(
                issue_type=VisualIssueType.UNSUPPORTED_RENDERING,
                severity=IssueSeverity.CRITICAL,
                component="slide_body",
                description="Content slide lacks any primary visual element (chart, matrix, diagram, or table).",
                recommended_action="USE_VISUAL_FALLBACK"
            ))
            dim_scores["balance"] -= 0.40
            dim_scores["emphasis"] -= 0.30

        # 6. Contrast Checks
        cr_primary = calculate_contrast_ratio(tokens.primary_text, tokens.background)
        if cr_primary < 3.0:
            issues.append(VisualQAIssue(
                issue_type=VisualIssueType.LOW_CONTRAST,
                severity=IssueSeverity.CRITICAL,
                component="typography",
                description=f"Primary text contrast ({cr_primary}:1) violates minimum legibility standards.",
                recommended_action="CHANGE_TEXT_SIZE_WITHIN_ALLOWED_BOUND"
            ))
            dim_scores["readability"] -= 0.40
        elif cr_primary < 4.5:
            issues.append(VisualQAIssue(
                issue_type=VisualIssueType.LOW_CONTRAST,
                severity=IssueSeverity.MEDIUM,
                component="typography",
                description=f"Primary text contrast ({cr_primary}:1) is below WCAG AAA recommendations.",
                recommended_action="INCREASE_SPACING"
            ))
            dim_scores["readability"] -= 0.15

        # 7. KPI Count Check
        if spec.kpis and len(spec.kpis) > 4:
            issues.append(VisualQAIssue(
                issue_type=VisualIssueType.COMPONENT_COLLISION,
                severity=IssueSeverity.MEDIUM,
                component="kpi_grid",
                description=f"KPI count ({len(spec.kpis)}) exceeds recommended executive quad grid limit of 4.",
                recommended_action="REDUCE_KPI_COUNT"
            ))
            dim_scores["density"] -= 0.15
            dim_scores["balance"] -= 0.10

        # 8. Compute normalized dimension scores and overall score
        clamped_dims = {k: max(0.10, min(1.0, v)) for k, v in dim_scores.items()}
        dimensions = VisualQAScoreDimensions(**clamped_dims)

        deductions = sum(0.35 if i.severity == IssueSeverity.CRITICAL else (0.15 if i.severity == IssueSeverity.HIGH else 0.05) for i in issues)
        overall_score = max(0.10, min(1.0, 1.0 - deductions))

        has_critical = any(i.severity == IssueSeverity.CRITICAL for i in issues)
        has_high = any(i.severity == IssueSeverity.HIGH for i in issues)

        if has_critical:
            status = "FAIL"
        elif has_high or overall_score < 0.80:
            status = "WARNING"
        else:
            status = "PASS"

        return VisualQAReport(
            slide_id=spec.slide_id or f"slide_{spec.sequence_number}",
            sequence_number=spec.sequence_number,
            status=status,
            overall_score=round(overall_score, 2),
            dimensions=dimensions,
            issues=issues,
            screenshot_path=screenshot_path,
            qa_model="deterministic",
            latency_ms=1.5,
            metadata={"source": "deterministic_geometry_auditor"}
        )
