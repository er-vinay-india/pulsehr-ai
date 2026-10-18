"""
HighView Ingestion V2 — Concentration Statistical Analysis
Stage 8: Analytical EDA-B
Evaluates concentration, Top-N share, HHI (Herfindahl-Hirschman Index), and Pareto distribution
of numeric measures across categorical entities.
"""

from __future__ import annotations

import math
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


def analyze_concentration(
    table_id: str,
    table_profile: TableStructuralProfile,
    column_semantics: dict[str, Any],
    rows: list[dict[str, Any]],
    registry: FindingRegistry,
    target_grain: str | None = None,
) -> None:
    """
    Computes Top-N share, HHI, and Pareto distribution for metric columns across dimensions.
    """
    if not rows or len(rows) < 10:
        return

    metric_cols = []
    dimension_cols = []

    for col_profile in table_profile.columns:
        col_id = get_column_name(col_profile)
        col_type = get_column_type(col_profile)
        sem = column_semantics.get(col_id)
        role = get_column_role(sem)

        if col_type in ("INTEGER", "FLOAT") and role in (
            SemanticColumnRole.MEASURE,
            SemanticColumnRole.ATTRIBUTE,
        ):
            metric_cols.append(col_id)
        elif role in (SemanticColumnRole.DIMENSION, SemanticColumnRole.ENTITY_IDENTIFIER, SemanticColumnRole.ATTRIBUTE, SemanticColumnRole.CATEGORY) and col_type == "STRING":
            dimension_cols.append(col_id)

    if not metric_cols or not dimension_cols:
        return

    for dim_col in dimension_cols[:3]:
        for metric_col in metric_cols[:3]:
            dim_sums: dict[str, float] = {}
            for r in rows:
                dim_val = r.get(dim_col)
                met_val = r.get(metric_col)
                if dim_val is not None and met_val is not None:
                    try:
                        f_val = float(met_val)
                        if f_val >= 0:
                            d_key = str(dim_val).strip()
                            dim_sums[d_key] = dim_sums.get(d_key, 0.0) + f_val
                    except (ValueError, TypeError):
                        pass

            total_sum = sum(dim_sums.values())
            n_entities = len(dim_sums)
            if total_sum <= 0 or n_entities < 4:
                continue

            sorted_shares = sorted(
                [(k, v / total_sum) for k, v in dim_sums.items()],
                key=lambda x: x[1],
                reverse=True,
            )

            top1_entity, top1_share = sorted_shares[0]
            top3_share = sum(s[1] for s in sorted_shares[:3])
            hhi = sum((share * 100.0) ** 2 for _, share in sorted_shares)

            top_20_count = max(1, math.ceil(0.20 * n_entities))
            top_20_share = sum(s[1] for s in sorted_shares[:top_20_count])

            hhi_class = "HIGH" if hhi > 2500 else ("MODERATE" if hhi >= 1500 else "LOW")

            desc = (
                f"Concentration for '{metric_col}' across '{dim_col}' in '{table_id}': "
                f"Top 3 categories account for {top3_share * 100.0:.1f}% of total "
                f"(top category '{top1_entity}' holds {top1_share * 100.0:.1f}%; HHI is {int(hhi)})."
            )

            registry.register(
                finding_type=FindingType.CONCENTRATION,
                description=desc,
                source_table_ids=[table_id],
                source_column_ids=[dim_col, metric_col],
                target_grain=target_grain or f"{table_id}_ROW",
                result={
                    "metric": metric_col,
                    "dimension": dim_col,
                    "top_1_entity": top1_entity,
                    "top_1_share": round(top1_share, 4),
                    "top_3_share": round(top3_share, 4),
                    "top_20pct_entities_share": round(top_20_share, 4),
                    "hhi": round(hhi, 1),
                    "concentration_class": hhi_class,
                    "total_categories": n_entities,
                },
                metric_definition=f"SUM({metric_col})",
                dimension_definition=dim_col,
                population_definition="ALL_ROWS",
                confidence=1.0,
                analysis_method="CONCENTRATION_HHI",
            )
