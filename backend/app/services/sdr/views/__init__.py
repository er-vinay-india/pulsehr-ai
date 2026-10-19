"""
HighView Semantic Data Refinery — Phase SDR-6
Views Package
"""

from app.services.sdr.views.expression_engine import (
    GovernedExpressionCompilationError,
    RatioAggregationTrapError,
    UnitConflictError,
    compile_controlled_expression_to_sql,
    evaluate_expression_on_row,
    validate_unit_compatibility,
)
from app.services.sdr.views.metric_derivers import (
    LocalMetricDeriver,
    MetricDerivationError,
    RelationalMetricDeriver,
)
from app.services.sdr.views.duckdb_executor import (
    GovernedAnalyticalExecutionError,
    GrainViolationError,
    SDRDuckDBExecutor,
)
from app.services.sdr.views.view_engine import SDRAnalyticalViewEngine

__all__ = [
    "GovernedExpressionCompilationError",
    "RatioAggregationTrapError",
    "UnitConflictError",
    "compile_controlled_expression_to_sql",
    "evaluate_expression_on_row",
    "validate_unit_compatibility",
    "LocalMetricDeriver",
    "MetricDerivationError",
    "RelationalMetricDeriver",
    "GovernedAnalyticalExecutionError",
    "GrainViolationError",
    "SDRDuckDBExecutor",
    "SDRAnalyticalViewEngine",
]
