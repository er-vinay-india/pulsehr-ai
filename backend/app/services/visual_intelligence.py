"""Autonomous AI Multi-Sheet Visual Intelligence Dashboard Engine.

Re-exports core components from the visuals subpackage:
- Industrial People Analytics Visual Intelligence Suite (McKinsey 9-Box, Bradford Factor, Burnout Strain, Elasticity)
- Longitudinal Trajectory Forecasting
- Comparative Grouped Visualizations
- Data Explorer Projections & Profiles
"""

from .visuals import (
    PALETTE,
    is_name_or_text_column,
    clean_file_label,
    generate_comparative_insight,
    extract_sheet_temporal_profile,
    get_sheet_raw_projections,
    build_workspace_visual_dashboard,
)

__all__ = [
    "PALETTE",
    "is_name_or_text_column",
    "clean_file_label",
    "generate_comparative_insight",
    "extract_sheet_temporal_profile",
    "get_sheet_raw_projections",
    "build_workspace_visual_dashboard",
]
