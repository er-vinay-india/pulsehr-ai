"""Exploratory Data Analysis (EDA) & Multi-Sheet Intelligence Package."""
from .normalizer import normalize_dataset, is_null_val
from .cross_correlator import (
    compute_cross_sheet_intelligence,
    compute_intra_sheet_correlations,
    compute_metric_distribution_histograms
)
from .temporal_analyzer import analyze_temporal_dynamics, extract_temporal_periods
from .predictive_models import (
    fit_linear_regression,
    fit_logistic_regression,
    generate_predictive_suite_for_sheet
)
from .derived_tables import synthesize_derived_tables
from .report_generator import build_sheet_eda_report
from .engine import run_eda_pipeline

__all__ = [
    "run_eda_pipeline",
    "normalize_dataset",
    "compute_cross_sheet_intelligence",
    "compute_intra_sheet_correlations",
    "compute_metric_distribution_histograms",
    "analyze_temporal_dynamics",
    "extract_temporal_periods",
    "fit_linear_regression",
    "fit_logistic_regression",
    "generate_predictive_suite_for_sheet",
    "synthesize_derived_tables",
    "build_sheet_eda_report",
    "is_null_val",
]
