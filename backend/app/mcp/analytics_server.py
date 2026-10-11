"""Analytics MCP Capability Server (Phase B).

Exposes deterministic mathematical and statistical analytics:
- rank_entities
- compare_segments
- calculate_distribution
- get_trend
- find_outliers
- analyze_relationship (Pearson correlation, strictly is_causal = False)
- get_benchmark_comparison

NO LLMs used. Executes directly on verified dataset tables and statistical routines.
"""
from __future__ import annotations

import json
import logging
import math
import sqlite3
from typing import Any

import numpy as np

from ..db.database import get_connection
from .contracts import (
    AnalyzeRelationshipInput,
    AnalyzeRelationshipOutput,
    CalculateDistributionInput,
    CalculateDistributionOutput,
    CompareSegmentsInput,
    CompareSegmentsOutput,
    FindOutliersInput,
    FindOutliersOutput,
    GetBenchmarkComparisonInput,
    GetBenchmarkComparisonOutput,
    GetTrendInput,
    GetTrendOutput,
    MCPToolDefinition,
    OutlierEntity,
    RankEntitiesInput,
    RankEntitiesOutput,
    RankedEntityItem,
    ToolRiskLevel,
    TrendPoint,
)
from .registry import mcp_registry

logger = logging.getLogger(__name__)


def _extract_column_series(dataset_id: int | str, col_name: str) -> list[float]:
    """Helper extracting numeric values from sheet_records."""
    values: list[float] = []
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM sheets WHERE dataset_id = ? ORDER BY id ASC LIMIT 1", (dataset_id,))
        s_row = cursor.fetchone()
        if not s_row:
            return values
        sheet_id = s_row["id"]

        cursor.execute("SELECT data FROM sheet_records WHERE sheet_id = ?", (sheet_id,))
        for r in cursor.fetchall():
            row_dict = json.loads(r["data"]) if isinstance(r["data"], str) else r["data"]
            val = row_dict.get(col_name)
            if val is not None:
                try:
                    num = float(val)
                    if not math.isnan(num) and not math.isinf(num):
                        values.append(num)
                except (ValueError, TypeError):
                    pass
    return values


# -----------------------------------------------------------------------------
# Handlers
# -----------------------------------------------------------------------------

def handle_rank_entities(args: dict[str, Any], context: Any = None) -> RankEntitiesOutput:
    inp = RankEntitiesInput.model_validate(args)
    dataset_id = inp.dataset_id
    dim = inp.entity_dimension
    measure = inp.measure
    direction = inp.direction
    limit = inp.limit

    grouped: dict[str, list[float]] = {}
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM sheets WHERE dataset_id = ? ORDER BY id ASC LIMIT 1", (dataset_id,))
        s_row = cursor.fetchone()
        if s_row:
            sheet_id = s_row["id"]
            cursor.execute("SELECT data FROM sheet_records WHERE sheet_id = ?", (sheet_id,))
            for r in cursor.fetchall():
                row_dict = json.loads(r["data"]) if isinstance(r["data"], str) else r["data"]
                k = row_dict.get(dim)
                v = row_dict.get(measure)
                if k is not None and v is not None:
                    try:
                        v_num = float(v)
                        grouped.setdefault(str(k), []).append(v_num)
                    except (ValueError, TypeError):
                        pass

    aggregated = []
    total_sum = 0.0
    for k, vals in grouped.items():
        avg_val = float(np.mean(vals))
        total_sum += avg_val
        aggregated.append((k, avg_val))

    reverse = (direction == "desc")
    aggregated.sort(key=lambda x: x[1], reverse=reverse)

    ranked_items: list[RankedEntityItem] = []
    for rank_idx, (entity, val) in enumerate(aggregated[:limit], start=1):
        share = round((val / total_sum * 100.0), 1) if total_sum > 0 else 0.0
        ranked_items.append(RankedEntityItem(
            rank=rank_idx,
            entity=entity,
            value=round(val, 2),
            formatted_value=f"{val:.1f}",
            share_of_total_pct=share,
        ))

    return RankEntitiesOutput(
        dataset_id=dataset_id,
        measure=measure,
        total_evaluated=len(aggregated),
        ranked_items=ranked_items,
        evidence_id="EVID-RANK-01",
    )


def handle_compare_segments(args: dict[str, Any], context: Any = None) -> CompareSegmentsOutput:
    inp = CompareSegmentsInput.model_validate(args)
    dataset_id = inp.dataset_id
    dim = inp.dimension
    measure = inp.measure
    seg_a = inp.segment_a
    seg_b = inp.segment_b

    vals_a: list[float] = []
    vals_b: list[float] = []

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM sheets WHERE dataset_id = ? ORDER BY id ASC LIMIT 1", (dataset_id,))
        s_row = cursor.fetchone()
        if s_row:
            sheet_id = s_row["id"]
            cursor.execute("SELECT data FROM sheet_records WHERE sheet_id = ?", (sheet_id,))
            for r in cursor.fetchall():
                row_dict = json.loads(r["data"]) if isinstance(r["data"], str) else r["data"]
                k = str(row_dict.get(dim, ""))
                v = row_dict.get(measure)
                if v is not None:
                    try:
                        v_num = float(v)
                        if k.lower() == seg_a.lower():
                            vals_a.append(v_num)
                        elif k.lower() == seg_b.lower():
                            vals_b.append(v_num)
                    except (ValueError, TypeError):
                        pass

    mean_a = float(np.mean(vals_a)) if vals_a else 0.0
    mean_b = float(np.mean(vals_b)) if vals_b else 0.0
    delta = round(mean_a - mean_b, 2)
    delta_pct = round(((delta / mean_b) * 100.0), 1) if mean_b != 0 else 0.0

    return CompareSegmentsOutput(
        dataset_id=dataset_id,
        measure=measure,
        segment_a_name=seg_a,
        segment_a_value=round(mean_a, 2),
        segment_b_name=seg_b,
        segment_b_value=round(mean_b, 2),
        delta=delta,
        delta_pct=delta_pct,
        evidence_id="EVID-COMP-01",
    )


def handle_calculate_distribution(args: dict[str, Any], context: Any = None) -> CalculateDistributionOutput:
    inp = CalculateDistributionInput.model_validate(args)
    dataset_id = inp.dataset_id
    measure = inp.measure

    values = _extract_column_series(dataset_id, measure)
    if not values:
        values = [0.0]

    arr = np.array(values)
    p_min = float(np.min(arr))
    p25 = float(np.percentile(arr, 25))
    median = float(np.median(arr))
    p75 = float(np.percentile(arr, 75))
    p_max = float(np.max(arr))
    iqr = round(p75 - p25, 2)

    dist_id = f"DIST-{abs(hash((str(dataset_id), measure))) % 10000:04d}"

    return CalculateDistributionOutput(
        dataset_id=dataset_id,
        measure=measure,
        count=len(values),
        min=round(p_min, 2),
        p25=round(p25, 2),
        median=round(median, 2),
        p75=round(p75, 2),
        max=round(p_max, 2),
        iqr=iqr,
        distribution_id=dist_id,
        evidence_id="EVID-DIST-01",
    )


def handle_get_trend(args: dict[str, Any], context: Any = None) -> GetTrendOutput:
    inp = GetTrendInput.model_validate(args)
    dataset_id = inp.dataset_id
    time_dim = inp.time_dimension
    measure = inp.measure

    points: list[TrendPoint] = []
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM sheets WHERE dataset_id = ? ORDER BY id ASC LIMIT 1", (dataset_id,))
        s_row = cursor.fetchone()
        if s_row:
            sheet_id = s_row["id"]
            cursor.execute(
                f"SELECT json_extract(data, '$.\"' || ? || '\"') as t_col, "
                f"AVG(CAST(json_extract(data, '$.\"' || ? || '\"') AS REAL)) as avg_val "
                f"FROM sheet_records WHERE sheet_id = ? AND t_col IS NOT NULL "
                f"GROUP BY t_col ORDER BY t_col ASC LIMIT 12",
                (time_dim, measure, sheet_id)
            )
            for r in cursor.fetchall():
                if r["t_col"] and r["avg_val"] is not None:
                    points.append(TrendPoint(period=str(r["t_col"]), value=round(float(r["avg_val"]), 2)))

    direction = "FLAT"
    if len(points) >= 2:
        start_val = points[0].value
        end_val = points[-1].value
        if end_val > start_val * 1.05:
            direction = "UPWARD"
        elif end_val < start_val * 0.95:
            direction = "DOWNWARD"

    return GetTrendOutput(
        dataset_id=dataset_id,
        measure=measure,
        is_temporal=len(points) > 0,
        direction=direction if points else "NON_TEMPORAL",
        points=points,
        evidence_id="EVID-TREND-01",
    )


def handle_find_outliers(args: dict[str, Any], context: Any = None) -> FindOutliersOutput:
    inp = FindOutliersInput.model_validate(args)
    dataset_id = inp.dataset_id
    measure = inp.measure
    threshold = inp.threshold_sigma

    records: list[tuple[str, float]] = []
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM sheets WHERE dataset_id = ? ORDER BY id ASC LIMIT 1", (dataset_id,))
        s_row = cursor.fetchone()
        if s_row:
            sheet_id = s_row["id"]
            cursor.execute("SELECT data FROM sheet_records WHERE sheet_id = ?", (sheet_id,))
            for r in cursor.fetchall():
                row_dict = json.loads(r["data"]) if isinstance(r["data"], str) else r["data"]
                # Look for primary identifier or first non-measure string
                ent_name = "Record"
                for k, v in row_dict.items():
                    if isinstance(v, str) and k != measure:
                        ent_name = v
                        break
                val = row_dict.get(measure)
                if val is not None:
                    try:
                        records.append((ent_name, float(val)))
                    except (ValueError, TypeError):
                        pass

    outliers: list[OutlierEntity] = []
    if len(records) >= 3:
        vals = np.array([r[1] for r in records])
        mean = float(np.mean(vals))
        std = float(np.std(vals))
        if std > 0:
            for ent, val in records:
                z = (val - mean) / std
                if abs(z) >= threshold:
                    sev = "MODERATE"
                    if abs(z) >= 3.0:
                        sev = "EXTREME"
                    elif abs(z) >= 2.5:
                        sev = "SEVERE"
                    outliers.append(OutlierEntity(
                        entity=ent,
                        value=round(val, 2),
                        z_score=round(float(z), 2),
                        severity=sev,
                    ))

    return FindOutliersOutput(
        dataset_id=dataset_id,
        measure=measure,
        outlier_count=len(outliers),
        outliers=outliers[:10],
        evidence_id="EVID-OUTLIER-01",
    )


def handle_analyze_relationship(args: dict[str, Any], context: Any = None) -> AnalyzeRelationshipOutput:
    inp = AnalyzeRelationshipInput.model_validate(args)
    dataset_id = inp.dataset_id
    x_col = inp.measure_x
    y_col = inp.measure_y

    pairs: list[tuple[float, float]] = []
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM sheets WHERE dataset_id = ? ORDER BY id ASC LIMIT 1", (dataset_id,))
        s_row = cursor.fetchone()
        if s_row:
            sheet_id = s_row["id"]
            cursor.execute("SELECT data FROM sheet_records WHERE sheet_id = ?", (sheet_id,))
            for r in cursor.fetchall():
                row_dict = json.loads(r["data"]) if isinstance(r["data"], str) else r["data"]
                vx = row_dict.get(x_col)
                vy = row_dict.get(y_col)
                if vx is not None and vy is not None:
                    try:
                        pairs.append((float(vx), float(vy)))
                    except (ValueError, TypeError):
                        pass

    corr = 0.0
    strength = "negligible"
    if len(pairs) >= 3:
        arr_x = np.array([p[0] for p in pairs])
        arr_y = np.array([p[1] for p in pairs])
        if np.std(arr_x) > 0 and np.std(arr_y) > 0:
            corr = float(np.corrcoef(arr_x, arr_y)[0, 1])
            abs_c = abs(corr)
            if abs_c >= 0.7:
                strength = "strong"
            elif abs_c >= 0.4:
                strength = "moderate"
            elif abs_c >= 0.2:
                strength = "weak"

    return AnalyzeRelationshipOutput(
        dataset_id=dataset_id,
        measure_x=x_col,
        measure_y=y_col,
        correlation_coefficient=round(corr, 3),
        association_strength=strength,
        sample_size=len(pairs),
        is_causal=False,  # Hard invariant: statistical association, never causation
        evidence_id="EVID-REL-01",
    )


def handle_get_benchmark_comparison(args: dict[str, Any], context: Any = None) -> GetBenchmarkComparisonOutput:
    inp = GetBenchmarkComparisonInput.model_validate(args)
    dataset_id = inp.dataset_id
    measure = inp.measure
    benchmark = inp.benchmark_value

    values = _extract_column_series(dataset_id, measure)
    if not values:
        values = [0.0]

    actual_mean = float(np.mean(values))
    gap = round(actual_mean - benchmark, 2)
    gap_pct = round(((gap / benchmark) * 100.0), 1) if benchmark != 0 else 0.0
    compliant_count = sum(1 for v in values if v >= benchmark)
    comp_ratio = round((compliant_count / len(values) * 100.0), 1)

    return GetBenchmarkComparisonOutput(
        dataset_id=dataset_id,
        measure=measure,
        benchmark_value=benchmark,
        actual_mean=round(actual_mean, 2),
        gap=gap,
        gap_pct=gap_pct,
        compliant_ratio_pct=comp_ratio,
        evidence_id="EVID-BENCH-01",
    )


# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------

def register_analytics_tools() -> None:
    """Registers all Analytics MCP tools into the central registry."""
    tools = [
        (
            MCPToolDefinition(
                tool_name="rank_entities",
                capability_group="analytics",
                description="Rank dimension entities (e.g. departments, regions) by numeric measure.",
                input_schema=RankEntitiesInput,
                output_schema=RankEntitiesOutput,
                risk_level=ToolRiskLevel.MEDIUM,
            ),
            handle_rank_entities,
        ),
        (
            MCPToolDefinition(
                tool_name="compare_segments",
                capability_group="analytics",
                description="Compare mathematical performance and percentage gap between two cohort segments.",
                input_schema=CompareSegmentsInput,
                output_schema=CompareSegmentsOutput,
                risk_level=ToolRiskLevel.MEDIUM,
            ),
            handle_compare_segments,
        ),
        (
            MCPToolDefinition(
                tool_name="calculate_distribution",
                capability_group="analytics",
                description="Calculate five-number summary (min, p25, median, p75, max, IQR) for a measure.",
                input_schema=CalculateDistributionInput,
                output_schema=CalculateDistributionOutput,
                risk_level=ToolRiskLevel.MEDIUM,
            ),
            handle_calculate_distribution,
        ),
        (
            MCPToolDefinition(
                tool_name="get_trend",
                capability_group="analytics",
                description="Calculate chronological series trajectory across verified temporal dimensions.",
                input_schema=GetTrendInput,
                output_schema=GetTrendOutput,
                risk_level=ToolRiskLevel.MEDIUM,
            ),
            handle_get_trend,
        ),
        (
            MCPToolDefinition(
                tool_name="find_outliers",
                capability_group="analytics",
                description="Detect statistical outliers exceeding z-score threshold sigma (> 2.0).",
                input_schema=FindOutliersInput,
                output_schema=FindOutliersOutput,
                risk_level=ToolRiskLevel.MEDIUM,
            ),
            handle_find_outliers,
        ),
        (
            MCPToolDefinition(
                tool_name="analyze_relationship",
                capability_group="analytics",
                description="Calculate bivariate correlation coefficient and association strength (strictly non-causal).",
                input_schema=AnalyzeRelationshipInput,
                output_schema=AnalyzeRelationshipOutput,
                risk_level=ToolRiskLevel.MEDIUM,
            ),
            handle_analyze_relationship,
        ),
        (
            MCPToolDefinition(
                tool_name="get_benchmark_comparison",
                capability_group="analytics",
                description="Compare actual metric mean against statutory or policy benchmark threshold.",
                input_schema=GetBenchmarkComparisonInput,
                output_schema=GetBenchmarkComparisonOutput,
                risk_level=ToolRiskLevel.MEDIUM,
            ),
            handle_get_benchmark_comparison,
        ),
    ]

    for defn, handler in tools:
        mcp_registry.register(defn, handler)
