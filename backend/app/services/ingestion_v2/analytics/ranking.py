"""
HighView Ingestion V2 — Ranking Analysis
Stage 8: Analytical EDA-B
Generates deterministic entity rankings with explicit direction, tie policy, and sample support rules.
"""

from __future__ import annotations

from typing import Any
from app.services.ingestion_v2.analytics.finding_registry import FindingRegistry
from app.services.ingestion_v2.analytics.helpers import (
    get_column_name,
    get_column_role,
    get_column_type,
)
from app.services.ingestion_v2.contracts.analytics import FindingType
from app.services.ingestion_v2.contracts.profiling import TableStructuralProfile
from app.services.ingestion_v2.contracts.semantics import SemanticColumnRole


def analyze_rankings(
    table_id: str,
    table_profile: TableStructuralProfile,
    column_semantics: dict[str, Any],
    rows: list[dict[str, Any]],
    registry: FindingRegistry,
    target_grain: str | None = None,
) -> None:
    """
    Computes Top-N and Bottom-N entity rankings across dimensions for numeric metrics.
    """
    if not rows or len(rows) < 10:
        return

    dim_cols = []
    metric_cols = []

    for col_profile in table_profile.columns:
        col_id = get_column_name(col_profile)
        col_type = get_column_type(col_profile)
        sem = column_semantics.get(col_id)
        role = get_column_role(sem)

        if col_type == "STRING" and role in (
            SemanticColumnRole.DIMENSION,
            SemanticColumnRole.ENTITY_IDENTIFIER,
            SemanticColumnRole.ATTRIBUTE,
            SemanticColumnRole.CATEGORY,
        ):
            dim_cols.append(col_id)
        elif col_type in ("INTEGER", "FLOAT") and role in (
            SemanticColumnRole.MEASURE,
            SemanticColumnRole.ATTRIBUTE,
        ):
            metric_cols.append(col_id)

    if not dim_cols or not metric_cols:
        return

    for dim_col in dim_cols[:2]:
        for metric_col in metric_cols[:2]:
            group_vals: dict[str, list[float]] = {}
            for r in rows:
                d_val = r.get(dim_col)
                m_val = r.get(metric_col)
                if d_val is not None and m_val is not None:
                    try:
                        d_str = str(d_val).strip()
                        group_vals.setdefault(d_str, []).append(float(m_val))
                    except (ValueError, TypeError):
                        pass

            if len(group_vals) < 3:
                continue

            ranked_items = []
            for d_str, v_list in group_vals.items():
                ranked_items.append({
                    "entity": d_str,
                    "sum": sum(v_list),
                    "mean": sum(v_list) / len(v_list),
                    "count": len(v_list),
                })

            ranked_items.sort(key=lambda x: x["sum"], reverse=True)

            top_3 = ranked_items[:3]
            top_entity = top_3[0]["entity"]
            top_val = top_3[0]["sum"]

            desc = (
                f"Top ranking for '{dim_col}' by total '{metric_col}' in '{table_id}': "
                f"1st '{top_entity}' ({top_val:,.1f}), followed by "
                + ", ".join([f"'{item['entity']}' ({item['sum']:,.1f})" for item in top_3[1:]])
                + f" (across {len(ranked_items)} categories)."
            )

            registry.register(
                finding_type=FindingType.RANKING,
                description=desc,
                source_table_ids=[table_id],
                source_column_ids=[dim_col, metric_col],
                target_grain=target_grain or f"{table_id}_ROW",
                result={
                    "ranking_dimension": dim_col,
                    "ranking_metric": metric_col,
                    "direction": "DESCENDING",
                    "tie_policy": "MIN",
                    "top_entities": top_3,
                    "bottom_entities": ranked_items[-2:],
                    "total_ranked_entities": len(ranked_items),
                },
                metric_definition=f"SUM({metric_col})",
                dimension_definition=dim_col,
                population_definition="ALL_ROWS",
                confidence=1.0,
                analysis_method="RANKING_SUM_DESC",
            )
