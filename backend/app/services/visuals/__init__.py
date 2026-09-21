"""Visual intelligence dashboard and projection components."""

from .visual_common import (
    PALETTE,
    is_name_or_text_column,
    clean_file_label,
    generate_comparative_insight,
    extract_sheet_temporal_profile,
)
from .raw_projections import get_sheet_raw_projections
from .dashboard_builder import build_workspace_visual_dashboard

__all__ = [
    "PALETTE",
    "is_name_or_text_column",
    "clean_file_label",
    "generate_comparative_insight",
    "extract_sheet_temporal_profile",
    "get_sheet_raw_projections",
    "build_workspace_visual_dashboard",
]
