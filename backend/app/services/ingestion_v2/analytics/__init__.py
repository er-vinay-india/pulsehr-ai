"""
HighView Ingestion V2 — Governed Analytical Profiler / EDA-B
Stage 8: Analytical EDA-B
"""

from app.services.ingestion_v2.analytics.analytical_profiler import (
    AnalyticalProfiler,
    build_analytical_profile,
)
from app.services.ingestion_v2.analytics.anomaly_analysis import analyze_anomalies_and_outliers
from app.services.ingestion_v2.analytics.concentration_analysis import analyze_concentration
from app.services.ingestion_v2.analytics.correlation_analysis import analyze_correlations
from app.services.ingestion_v2.analytics.finding_registry import (
    FindingRegistry,
    generate_finding_fingerprint,
)
from app.services.ingestion_v2.analytics.governed_join_executor import (
    GovernedJoinExecutionError,
    execute_governed_join,
)
from app.services.ingestion_v2.analytics.grouped_analysis import (
    analyze_governed_ratio,
    analyze_grouped_comparisons,
)
from app.services.ingestion_v2.analytics.ranking import analyze_rankings
from app.services.ingestion_v2.analytics.reliability import calculate_analytical_reliability
from app.services.ingestion_v2.analytics.statistical_tests import (
    apply_benjamini_hochberg,
    perform_anova,
    perform_chi_square,
    perform_correlation_test,
    perform_mann_whitney,
    perform_two_sample_test,
)
from app.services.ingestion_v2.analytics.trend_analysis import analyze_trends
from app.services.ingestion_v2.analytics.univariate_analysis import analyze_univariate_profiles

__all__ = [
    "AnalyticalProfiler",
    "build_analytical_profile",
    "FindingRegistry",
    "generate_finding_fingerprint",
    "calculate_analytical_reliability",
    "execute_governed_join",
    "GovernedJoinExecutionError",
    "analyze_univariate_profiles",
    "analyze_anomalies_and_outliers",
    "analyze_correlations",
    "analyze_concentration",
    "analyze_rankings",
    "analyze_trends",
    "analyze_grouped_comparisons",
    "analyze_governed_ratio",
    "perform_two_sample_test",
    "perform_mann_whitney",
    "perform_anova",
    "perform_chi_square",
    "perform_correlation_test",
    "apply_benjamini_hochberg",
]
