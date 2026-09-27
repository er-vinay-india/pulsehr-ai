"""Golden Test Corpus for Presentation Generation Invariants.

Defines structural invariants, required evidence, expected visual families,
and unacceptable failures across all validated domains.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class GoldenTestCase(BaseModel):
    """Specification of an empirical golden test case with structural invariants."""
    case_id: str
    name: str
    domain: str
    input_characteristics: dict[str, Any]
    required_evidence_ids: list[str]
    expected_slide_count_range: tuple[int, int]
    required_theme_id: str
    critical_expected_visuals: list[str]
    unacceptable_failures: list[str]
    invariants: dict[str, Any] = Field(default_factory=dict)


GOLDEN_CORPUS: list[GoldenTestCase] = [
    GoldenTestCase(
        case_id="GOLDEN-HR-01",
        name="Workforce Operational Attendance & Risk Review",
        domain="Workforce Operations",
        input_characteristics={
            "dataset_rows": 3450,
            "period": "Q1 - Q3 2026",
            "has_rankings": True
        },
        required_evidence_ids=["EVID-HR-01", "EVID-HR-02", "EVID-HR-03", "EVID-HR-04"],
        expected_slide_count_range=(5, 7),
        required_theme_id="bold_signal",
        critical_expected_visuals=["bar_chart", "summary_card", "ranking_table"],
        unacceptable_failures=["THEME_REGRESSION", "MISSING_EVIDENCE", "UNSUPPORTED_CLAIM"],
        invariants={
            "theme_preservation_score": 1.0,
            "min_evidence_accuracy": 1.0,
            "max_title_overflow_pct": 0.0
        }
    ),
    GoldenTestCase(
        case_id="GOLDEN-SALES-02",
        name="Commercial Sales Performance & Regional Margin Review",
        domain="Commercial Sales",
        input_characteristics={
            "dataset_rows": 8240,
            "period": "Q1 - Q3 2026",
            "instructions": "Exactly 6 slides"
        },
        required_evidence_ids=["EVID-SALES-01", "EVID-SALES-02", "EVID-SALES-03"],
        expected_slide_count_range=(6, 6),  # Exactly 6 slides
        required_theme_id="bold_signal",
        critical_expected_visuals=["bar_chart", "kpi_card", "line_chart"],
        unacceptable_failures=["THEME_REGRESSION", "MISSED_USER_QUESTION", "OVERLOADED_SLIDE"],
        invariants={
            "exact_slide_count": 6,
            "theme_preservation_score": 1.0,
            "pptx_slide_count_match": True
        }
    ),
    GoldenTestCase(
        case_id="GOLDEN-FIN-03",
        name="Fiscal Budget vs Actual Spend & Margin Review",
        domain="Corporate Finance",
        input_characteristics={
            "dataset_rows": 5120,
            "period": "FY2026",
            "budget_total": 24.50,
            "actual_total": 23.85
        },
        required_evidence_ids=["EVID-FIN-01", "EVID-FIN-02", "EVID-FIN-03", "EVID-FIN-04"],
        expected_slide_count_range=(5, 6),
        required_theme_id="bold_signal",
        critical_expected_visuals=["bar_chart", "variance_table", "kpi_card"],
        unacceptable_failures=["THEME_REGRESSION", "UNSUPPORTED_CLAIM", "WRONG_VISUAL"],
        invariants={
            "arithmetic_divergence_max": 0.001,
            "theme_preservation_score": 1.0
        }
    ),
    GoldenTestCase(
        case_id="GOLDEN-TECH-04",
        name="Microservices Architecture Latency & SLA Review",
        domain="Cloud Engineering & Distributed Systems",
        input_characteristics={
            "dataset_rows": 24000,
            "has_architecture_dependencies": True
        },
        required_evidence_ids=["EVID-TECH-01", "EVID-TECH-02", "EVID-TECH-03"],
        expected_slide_count_range=(5, 7),
        required_theme_id="bold_signal",
        critical_expected_visuals=["diagram", "bar_chart", "kpi_card"],
        unacceptable_failures=["THEME_REGRESSION", "OVERLOADED_SLIDE", "MISSED_USER_QUESTION"],
        invariants={
            "theme_preservation_score": 1.0,
            "architecture_nodes_present": True
        }
    ),
    GoldenTestCase(
        case_id="GOLDEN-EDU-05",
        name="Introduction to Transformer Attention Mechanisms",
        domain="Artificial Intelligence Education",
        input_characteristics={
            "dataset_rows": 1200,
            "instructions": "Make it beginner-friendly with low cognitive load"
        },
        required_evidence_ids=["EVID-EDU-01", "EVID-EDU-02", "EVID-EDU-03"],
        expected_slide_count_range=(4, 6),
        required_theme_id="bold_signal",
        critical_expected_visuals=["diagram", "comparison_matrix", "bar_chart"],
        unacceptable_failures=["OVERLOADED_SLIDE", "THEME_REGRESSION", "WRONG_VISUAL"],
        invariants={
            "max_bullets_per_slide": 4,
            "theme_preservation_score": 1.0
        }
    ),
    GoldenTestCase(
        case_id="GOLDEN-RES-06",
        name="Empirical Research Study: Intervention Efficacy",
        domain="Academic & Clinical Research",
        input_characteristics={
            "dataset_rows": 4800,
            "instructions": "Do not include methodology in main deck; route to appendix"
        },
        required_evidence_ids=["EVID-RES-01", "EVID-RES-02", "EVID-RES-03", "EVID-RES-04"],
        expected_slide_count_range=(5, 7),
        required_theme_id="bold_signal",
        critical_expected_visuals=["bar_chart", "callout_box", "kpi_card"],
        unacceptable_failures=["POOR_APPENDIX_ROUTING", "UNSUPPORTED_CLAIM", "THEME_REGRESSION"],
        invariants={
            "has_appendix_routing": True,
            "theme_preservation_score": 1.0
        }
    ),
    GoldenTestCase(
        case_id="GOLDEN-SPARSE-07",
        name="Alpha Pilot Feasibility: Sparse Sample Evaluation",
        domain="Product Exploratory Research",
        input_characteristics={
            "dataset_rows": 6,
            "is_sparse_sample": True
        },
        required_evidence_ids=["EVID-SPARSE-01", "EVID-SPARSE-02"],
        expected_slide_count_range=(3, 4),
        required_theme_id="bold_signal",
        critical_expected_visuals=["kpi_card", "summary_card"],
        unacceptable_failures=["UNSUPPORTED_CLAIM", "OVERLOADED_SLIDE", "THEME_REGRESSION"],
        invariants={
            "max_slides": 4,
            "theme_preservation_score": 1.0,
            "no_unsupported_projections": True
        }
    ),
    GoldenTestCase(
        case_id="GOLDEN-DENSE-08",
        name="Global Enterprise Supply Chain & Inventory Triage",
        domain="Supply Chain & Logistics",
        input_characteristics={
            "dataset_rows": 18500,
            "sheet_count": 3,
            "is_multi_sheet": True
        },
        required_evidence_ids=["EVID-DENSE-01", "EVID-DENSE-02", "EVID-DENSE-03"],
        expected_slide_count_range=(5, 7),
        required_theme_id="bold_signal",
        critical_expected_visuals=["bar_chart", "kpi_card", "ranking_table"],
        unacceptable_failures=["POOR_APPENDIX_ROUTING", "OVERLOADED_SLIDE", "THEME_REGRESSION"],
        invariants={
            "max_main_slides": 7,
            "theme_preservation_score": 1.0,
            "has_triage_applied": True
        }
    )
]
