"""Governed Semantic and Metric Layer for Decision-Intelligence Analytics.

Provides typed Pydantic contracts and automated catalog derivation for:
- SemanticMetrics (units, aggregation rules, directionality, benchmarks)
- SemanticDimensions (cardinality, types, entity keys)
- BusinessPolicies (targets, thresholds, guardrails)
- SemanticCatalog (sheet-level governed business semantics)
"""
from __future__ import annotations

import re
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class SemanticDimension(BaseModel):
    """Governed analytical dimension (category, department, region, cohort)."""
    model_config = ConfigDict(extra="forbid")

    name: str
    display_name: str
    data_type: Literal["string", "categorical", "temporal", "geographic", "identifier"] = "categorical"
    cardinality: int = 0
    sample_values: list[str] = Field(default_factory=list)
    is_primary_entity_key: bool = False


class PolicyThreshold(BaseModel):
    """Policy or SLA boundary for an operational metric."""
    model_config = ConfigDict(extra="forbid")

    threshold_id: str
    operator: Literal[">=", "<=", ">", "<", "=="]
    value: float
    unit: str
    label: str
    severity: Literal["critical", "warning", "info"] = "warning"


class SemanticMetric(BaseModel):
    """Governed measure with unit, directionality, and aggregation rules."""
    model_config = ConfigDict(extra="forbid")

    name: str
    display_name: str
    unit: str = ""
    direction: Literal["higher_is_better", "lower_is_better", "neutral"] = "neutral"
    aggregation_rule: Literal["sum", "avg", "count", "count_distinct", "ratio", "median"] = "avg"
    entity_type: str = "entity"
    source_column: str
    description: str | None = None
    benchmark_value: float | None = None
    policy_threshold: PolicyThreshold | None = None


class BusinessPolicy(BaseModel):
    """Organizational policy, quota, or operational commitment."""
    model_config = ConfigDict(extra="forbid")

    policy_id: str
    name: str
    target_metric: str
    expected_threshold: float
    operator: Literal[">=", "<=", ">", "<", "=="]
    severity: Literal["critical", "warning", "info"] = "warning"
    description: str


class SemanticCatalog(BaseModel):
    """Governed semantic catalog binding raw sheet columns to executive business concepts."""
    model_config = ConfigDict(extra="forbid")

    sheet_id: int
    sheet_name: str
    entity_type: str = "record"
    primary_key: str | None = None
    time_column: str | None = None
    time_grain: Literal["daily", "weekly", "monthly", "quarterly", "yearly", "none"] = "none"
    metrics: list[SemanticMetric] = Field(default_factory=list)
    dimensions: list[SemanticDimension] = Field(default_factory=list)
    policies: list[BusinessPolicy] = Field(default_factory=list)

    def get_metric(self, name: str) -> SemanticMetric | None:
        """Fetch a metric by name or source column."""
        for m in self.metrics:
            if m.name == name or m.source_column == name:
                return m
        return None

    def get_dimension(self, name: str) -> SemanticDimension | None:
        """Fetch a dimension by name."""
        for d in self.dimensions:
            if d.name == name:
                return d
        return None

    def primary_measure_name(self) -> str | None:
        """Return primary measure name if metrics exist."""
        if self.metrics:
            return self.metrics[0].name
        return None


def infer_semantic_catalog(
    sheet_id: int,
    sheet_name: str,
    columns: list[str],
    dtypes: dict[str, str] | None = None,
    sample_rows: list[dict[str, Any]] | None = None,
    domain: str = "general_tabular",
) -> SemanticCatalog:
    """Deterministically infers governed semantic catalog from schema and data profiling.
    
    Extracts metrics, dimensions, directionality, units, and entity identifiers.
    """
    dtypes = dtypes or {}
    sample_rows = sample_rows or []

    metrics: list[SemanticMetric] = []
    dimensions: list[SemanticDimension] = []
    time_column: str | None = None
    primary_key: str | None = None

    # Detect entity / primary key
    for col in columns:
        low = col.lower()
        if low in ("employee_id", "emp_id", "user_id", "customer_id", "id", "sku", "patient_id"):
            primary_key = col
            break

    # Categorize columns
    for col in columns:
        low = col.lower()
        col_type = dtypes.get(col, "string").lower()
        is_num = any(t in col_type for t in ("int", "float", "double", "decimal", "numeric"))
        
        # Check if date/time
        if any(kw in low for kw in ("date", "time", "month", "year", "quarter", "day", "timestamp", "period")):
            if not is_num or "year" in low:
                if not time_column:
                    time_column = col
                dimensions.append(
                    SemanticDimension(
                        name=col,
                        display_name=col.replace("_", " ").title(),
                        data_type="temporal",
                    )
                )
                continue

        if is_num:
            # Infer directionality & unit
            unit = ""
            direction: Literal["higher_is_better", "lower_is_better", "neutral"] = "neutral"
            
            if any(kw in low for kw in ("rate", "pct", "percent", "percentage", "ratio")):
                unit = "%"
            elif any(kw in low for kw in ("day", "days")):
                unit = "days"
            elif any(kw in low for kw in ("hour", "hours")):
                unit = "hours"
            elif any(kw in low for kw in ("cost", "revenue", "sales", "salary", "spend", "price", "amount", "budget")):
                unit = "$"
            elif any(kw in low for kw in ("count", "headcount", "volume", "quantity", "qty")):
                unit = "units"

            # Directionality heuristic
            if any(kw in low for kw in ("sales", "revenue", "profit", "attendance", "score", "retention", "yield", "accuracy", "compliance")):
                direction = "higher_is_better"
            elif any(kw in low for kw in ("cost", "attrition", "churn", "defect", "error", "delay", "friction", "leave", "complaint", "breach")):
                direction = "lower_is_better"

            metrics.append(
                SemanticMetric(
                    name=col,
                    display_name=col.replace("_", " ").title(),
                    unit=unit,
                    direction=direction,
                    aggregation_rule="sum" if unit in ("$", "units") else "avg",
                    source_column=col,
                )
            )
        else:
            # Dimension
            dim_type: Literal["string", "categorical", "temporal", "geographic", "identifier"] = "categorical"
            if col == primary_key or "id" in low:
                dim_type = "identifier"
            elif any(kw in low for kw in ("city", "country", "state", "region", "zip", "location")):
                dim_type = "geographic"

            dimensions.append(
                SemanticDimension(
                    name=col,
                    display_name=col.replace("_", " ").title(),
                    data_type=dim_type,
                    is_primary_entity_key=(col == primary_key),
                )
            )

    # Determine time grain if time_column exists
    time_grain: Literal["daily", "weekly", "monthly", "quarterly", "yearly", "none"] = "none"
    if time_column:
        low_time = time_column.lower()
        if "month" in low_time:
            time_grain = "monthly"
        elif "year" in low_time:
            time_grain = "yearly"
        elif "day" in low_time or "date" in low_time:
            time_grain = "daily"
        else:
            time_grain = "monthly"

    return SemanticCatalog(
        sheet_id=sheet_id,
        sheet_name=sheet_name,
        entity_type=primary_key.replace("_id", "") if primary_key else "record",
        primary_key=primary_key,
        time_column=time_column,
        time_grain=time_grain,
        metrics=metrics,
        dimensions=dimensions,
        policies=[],
    )
