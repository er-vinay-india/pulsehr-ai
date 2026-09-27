"""Phase 4 Visual Intelligence & Rendering Modernization Package.

Provides canonical contracts, layout registry, chart models, design tokens,
diagram models, visual intelligence engine, and presentation adapters.
"""

from .chart_models import (
    ChartAnnotation,
    ChartFamily,
    ChartFormatting,
    ChartGuardrailCheck,
    ChartSeries,
    ChartSpec,
)
from .chart_selector import ChartSelector
from .design_tokens import SlideDesignTokens, normalize_slide_theme
from .diagram_models import (
    DiagramConnection,
    DiagramFamily,
    DiagramNode,
    DiagramSpec,
    MatrixFamily,
    MatrixQuadrant,
    MatrixSpec,
)
from .layout_registry import ContentBudget, LayoutFamily, LayoutRegistry, LayoutSpec
from .layout_selector import LayoutSelector
from .visual_intelligence import VisualIntelligenceEngine
from .visual_models import (
    PrimaryVisualDescriptor,
    SourceFooterSpec,
    TransitionType,
    VisualSpecification,
    VisualStory,
)
from .visual_validator import VisualValidator
from .adapters.echarts_adapter import EChartsAdapter
from .adapters.pptx_adapter import PPTXAdapter
from .adapters.html_adapter import HTMLAdapter

__all__ = [
    "ChartAnnotation",
    "ChartFamily",
    "ChartFormatting",
    "ChartGuardrailCheck",
    "ChartSeries",
    "ChartSpec",
    "ChartSelector",
    "SlideDesignTokens",
    "normalize_slide_theme",
    "DiagramConnection",
    "DiagramFamily",
    "DiagramNode",
    "DiagramSpec",
    "MatrixFamily",
    "MatrixQuadrant",
    "MatrixSpec",
    "ContentBudget",
    "LayoutFamily",
    "LayoutRegistry",
    "LayoutSpec",
    "LayoutSelector",
    "VisualIntelligenceEngine",
    "PrimaryVisualDescriptor",
    "SourceFooterSpec",
    "TransitionType",
    "VisualSpecification",
    "VisualStory",
    "VisualValidator",
    "EChartsAdapter",
    "PPTXAdapter",
    "HTMLAdapter",
]
