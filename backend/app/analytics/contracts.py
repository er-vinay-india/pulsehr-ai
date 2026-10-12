"""
Phase G3 Analytical Plane Contracts and Data Structures.
Defines typed query requests, results, aggregations, and metadata contracts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class AggregationType(str, Enum):
    SUM = "SUM"
    AVG = "AVG"
    MIN = "MIN"
    MAX = "MAX"
    COUNT = "COUNT"
    COUNT_DISTINCT = "COUNT_DISTINCT"
    MEDIAN = "MEDIAN"
    STDDEV = "STDDEV"
    VAR = "VAR"


class FilterOperator(str, Enum):
    EQUALS = "="
    NOT_EQUALS = "!="
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_THAN_OR_EQUAL = ">="
    LESS_THAN_OR_EQUAL = "<="
    IN = "IN"
    NOT_IN = "NOT IN"
    IS_NULL = "IS NULL"
    IS_NOT_NULL = "IS NOT NULL"
    LIKE = "LIKE"


class OrderDirection(str, Enum):
    ASC = "ASC"
    DESC = "DESC"


class FilterSpec(BaseModel):
    field: str
    operator: FilterOperator = FilterOperator.EQUALS
    value: Any = None
    value2: Any = None


class MeasureSpec(BaseModel):
    field: str
    aggregation: AggregationType = AggregationType.SUM
    alias: str | None = None

    @property
    def output_name(self) -> str:
        return self.alias or f"{self.aggregation.value.lower()}_{self.field}"


class OrderBySpec(BaseModel):
    field: str
    direction: OrderDirection = OrderDirection.DESC


class AnalyticalQueryRequest(BaseModel):
    dataset_id: int
    logical_table_id: str
    dataset_version: int = 1
    dimensions: list[str] = Field(default_factory=list)
    measures: list[MeasureSpec] = Field(default_factory=list)
    filters: list[FilterSpec] = Field(default_factory=list)
    order_by: list[OrderBySpec] = Field(default_factory=list)
    limit: int | None = None
    offset: int | None = None


class AnalyticalQueryResult(BaseModel):
    rows: list[dict[str, Any]]
    columns: list[str]
    total_rows: int
    execution_time_ms: float
    engine: str = "duckdb"
    parquet_path: str | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)


class AnalyticalStatus(str, Enum):
    PARQUET_READY = "PARQUET_READY"
    PARQUET_FAILED = "PARQUET_FAILED"
    LEGACY_ONLY = "LEGACY_ONLY"


@dataclass(frozen=True)
class TableParquetMetadata:
    dataset_id: int
    sheet_id: int
    dataset_version: int
    logical_table_id: str
    parquet_path: str
    content_hash: str
    schema_hash: str
    row_count: int
    column_count: int
    uncompressed_bytes: int
    parquet_bytes: int
    status: AnalyticalStatus
    schema_json: str | None = None
