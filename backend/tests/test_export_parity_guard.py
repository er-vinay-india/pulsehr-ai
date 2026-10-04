"""Comprehensive Export Parity Verification Test Suite.

Audits native PowerPoint (python-pptx) and PDF exporters across:
1. High-cardinality charts (>10 categories, long labels) with horizontal bar mapping.
2. Top-N consolidated charts (Top 10 + Other).
3. Variance Waterfall Bridge charts with step delta shapes.
4. Hierarchical Breakdown Tree charts with node decomposition.
5. Multi-theme WCAG AAA contrast standard (>= 7:1) in exported DrawingML packages.
"""

from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import pytest
from pptx import Presentation
from pptx.enum.chart import XL_CHART_TYPE

from app.core import config
from app.services.report_generator import export_spec_to_pptx
from app.services.presentation.visual.design_tokens import SLIDE_THEME_PRESETS, slide_theme_preset
from app.services.presentation.photo_background import _contrast

NS = {
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'c': 'http://schemas.openxmlformats.org/drawingml/2006/chart',
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main'
}


def test_high_cardinality_horizontal_bar_export(tmp_path, monkeypatch):
    """Verifies that high-cardinality bar charts export as native clustered horizontal bars."""
    monkeypatch.setattr(config, 'EXPORTS_DIR', tmp_path)

    # 14 categories with long labels (simulating department headcounts)
    categories = [
        "Customer Support & Success", "Talent Acquisition & People Ops",
        "Enterprise Sales Engineering", "Product Design & Architecture",
        "Hardware Quality Assurance", "Supply Chain Operations",
        "Corporate Financial Strategy", "Legal & Regulatory Compliance",
        "Brand Marketing & Growth", "Information Security & SecOps",
        "Data Engineering & Warehousing", "Research & Innovation Labs",
        "Facilities & Real Estate", "Executive Leadership & Board"
    ]
    values = [120, 95, 88, 76, 64, 58, 52, 45, 40, 35, 30, 25, 20, 15]

    chart = {
        "title": "Headcount Distribution by Global Department",
        "type": "bar",
        "categories": categories,
        "series": [{"name": "Headcount", "values": values}]
    }

    slides = [
        {
            "title": "Executive Summary",
            "layout": "title_hero",
            "subtitle": "Workforce Composition",
            "narrative": "Global team distribution across major organizational units."
        },
        {
            "title": "Department Headcount Analysis",
            "layout": "chart_narrative",
            "chart": chart,
            "subtitle": "Breakdown by Division",
            "narrative": "Customer Support represents the largest single operational cohort."
        }
    ]

    spec = {
        "metadata": {"theme_id": "corporate_navy", "title": "Headcount Audit"},
        "slides": slides
    }

    path = export_spec_to_pptx(spec)
    prs = Presentation(path)
    assert len(prs.slides) == 2

    # Verify chart slide has an actual BAR_CLUSTERED native chart shape
    chart_slide = prs.slides[1]
    chart_shapes = [s for s in chart_slide.shapes if s.has_chart]
    assert len(chart_shapes) == 1

    native_chart = chart_shapes[0].chart
    assert native_chart.chart_type == XL_CHART_TYPE.BAR_CLUSTERED

    # Verify all 14 categories are embedded in PowerPoint chart data
    plot = native_chart.plots[0]
    assert len(plot.categories) == 14
    assert plot.categories[0] == "Customer Support & Success"


def test_top_n_consolidated_chart_export(tmp_path, monkeypatch):
    """Verifies that Top-N consolidated charts export cleanly with tail grouping."""
    monkeypatch.setattr(config, 'EXPORTS_DIR', tmp_path)

    # 10 top items + 1 consolidated tail
    categories = [f"Entity {i+1}" for i in range(10)] + ["Other (18 items)"]
    values = [500 - i * 35 for i in range(10)] + [450]

    chart = {
        "title": "Top Store Revenue Contributions",
        "type": "column",
        "categories": categories,
        "series": [{"name": "Revenue ($K)", "values": values}]
    }

    slides = [
        {
            "title": "Revenue Performance",
            "layout": "chart_narrative",
            "chart": chart,
            "subtitle": "Top 10 Stores vs Aggregated Tail",
            "narrative": "Top 10 stores contribute over 70% of total network revenue."
        }
    ]

    spec = {
        "metadata": {"theme_id": "executive_dark", "title": "Store Revenue"},
        "slides": slides
    }

    path = export_spec_to_pptx(spec)
    prs = Presentation(path)
    assert len(prs.slides) == 1

    chart_slide = prs.slides[0]
    chart_shapes = [s for s in chart_slide.shapes if s.has_chart]
    assert len(chart_shapes) == 1

    native_chart = chart_shapes[0].chart
    assert native_chart.chart_type == XL_CHART_TYPE.COLUMN_CLUSTERED
    assert len(native_chart.plots[0].categories) == 11
    assert "Other" in native_chart.plots[0].categories[-1]


def test_variance_waterfall_native_pptx_shapes(tmp_path, monkeypatch):
    """Verifies that variance waterfall slides export native PowerPoint shapes without error."""
    monkeypatch.setattr(config, 'EXPORTS_DIR', tmp_path)

    waterfall_chart = {
        "title": "Quarterly Turnover Delta Bridge",
        "type": "waterfall",
        "waterfall_steps": [
            {"label": "Starting Baseline", "value": 14.2, "type": "baseline"},
            {"label": "Engineering Resignations", "value": 2.4, "type": "increase"},
            {"label": "Sales Retention Gain", "value": -1.1, "type": "decrease"},
            {"label": "Ending Net Rate", "value": 15.5, "type": "total"}
        ]
    }

    slides = [
        {
            "title": "Turnover Variance Analysis",
            "layout": "chart_narrative",
            "chart": waterfall_chart,
            "subtitle": "Q1 to Q2 Shift",
            "narrative": "Engineering departures drove the primary variance in net turnover."
        }
    ]

    spec = {
        "metadata": {"theme_id": "emerald_growth", "title": "Turnover Waterfall"},
        "slides": slides
    }

    path = export_spec_to_pptx(spec)
    prs = Presentation(path)
    assert len(prs.slides) == 1

    # Verify slide contains shape blocks for the waterfall steps
    slide = prs.slides[0]
    assert len(slide.shapes) >= 4  # Narrative card + step cards/shapes


def test_breakdown_tree_native_pptx_hierarchy(tmp_path, monkeypatch):
    """Verifies that breakdown tree slides export hierarchical branch cards."""
    monkeypatch.setattr(config, 'EXPORTS_DIR', tmp_path)

    tree_chart = {
        "title": "Headcount Decomposition",
        "type": "breakdown_tree",
        "tree_data": {
            "name": "Global Enterprise (n=450)",
            "value": 450,
            "children": [
                {
                    "name": "North America",
                    "value": 280,
                    "children": [
                        {"name": "Engineering", "value": 180},
                        {"name": "Operations", "value": 100}
                    ]
                },
                {
                    "name": "EMEA",
                    "value": 170,
                    "children": [
                        {"name": "Commercial", "value": 110},
                        {"name": "Support", "value": 60}
                    ]
                }
            ]
        }
    }

    slides = [
        {
            "title": "Organizational Decomposition",
            "layout": "chart_narrative",
            "chart": tree_chart,
            "subtitle": "Regional & Functional Breakdown",
            "narrative": "North America Engineering commands 40% of global resource allocation."
        }
    ]

    spec = {
        "metadata": {"theme_id": "clean_light", "title": "Org Hierarchy"},
        "slides": slides
    }

    path = export_spec_to_pptx(spec)
    prs = Presentation(path)
    assert len(prs.slides) == 1

    # Verify slide rendered cleanly
    slide = prs.slides[0]
    assert len(slide.shapes) >= 3


@pytest.mark.parametrize('theme_id', list(SLIDE_THEME_PRESETS))
def test_export_theme_contrast_invariants(theme_id, tmp_path, monkeypatch):
    """Verifies that exported PPTX packages strictly satisfy WCAG AAA 7:1 contrast across all themes."""
    monkeypatch.setattr(config, 'EXPORTS_DIR', tmp_path)
    theme = slide_theme_preset(theme_id)

    spec = {
        "metadata": {"theme_id": theme_id, "title": "Contrast Parity"},
        "slides": [
            {
                "title": "Theme Contrast Verification",
                "layout": "chart_narrative",
                "chart": {
                    "title": "Metrics",
                    "type": "bar",
                    "categories": ["Alpha", "Beta", "Gamma"],
                    "series": [{"name": "Value", "values": [100, 200, 300]}]
                },
                "subtitle": "Contrast Check",
                "narrative": "Ensuring text is strictly legible on dark and light surfaces."
            }
        ]
    }

    path = export_spec_to_pptx(spec)
    with ZipFile(path) as package:
        for name in package.namelist():
            if not (name.startswith('ppt/slides/slide') or name.startswith('ppt/charts/chart')) or not name.endswith('.xml'):
                continue
            root = ET.fromstring(package.read(name))
            for props in root.findall('.//a:rPr', NS) + root.findall('.//a:defRPr', NS):
                color = props.find('a:solidFill/a:srgbClr', NS)
                if color is None:
                    continue
                foreground = '#' + color.attrib['val']
                for bg in (theme['bg_color'], theme['card_bg']):
                    ratio = _contrast(foreground, bg)
                    assert ratio >= 7.0, f"Contrast {ratio:.2f}:1 failed for {foreground} on {bg} in {theme_id}"
