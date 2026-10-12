"""
Phase G3 Analytical Data Plane and Query Engine Package.
"""
from .contracts import (
    AggregationType,
    AnalyticalQueryResult,
    AnalyticalQueryRequest,
    AnalyticalStatus,
    FilterOperator,
    FilterSpec,
    MeasureSpec,
    OrderBySpec,
    OrderDirection,
    TableParquetMetadata,
)
from .storage_integrity import AnalyticalStorageIsolationIntegrity
from .parquet_materializer import ParquetMaterializer
from .duckdb_engine import DuckDBEngine
from .query_service import AnalyticalQueryService
from .shadow_validator import ShadowValidator, NumericalEquivalenceTolerance
from .backfill import DatasetParquetBackfill

__all__ = [
    "AggregationType",
    "AnalyticalQueryResult",
    "AnalyticalQueryRequest",
    "AnalyticalStatus",
    "FilterOperator",
    "FilterSpec",
    "MeasureSpec",
    "OrderBySpec",
    "OrderDirection",
    "TableParquetMetadata",
    "AnalyticalStorageIsolationIntegrity",
    "ParquetMaterializer",
    "DuckDBEngine",
    "AnalyticalQueryService",
    "ShadowValidator",
    "NumericalEquivalenceTolerance",
    "DatasetParquetBackfill",
]
