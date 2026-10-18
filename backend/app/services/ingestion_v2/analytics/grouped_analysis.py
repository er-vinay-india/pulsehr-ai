"""
HighView Ingestion V2 — Grouped Analysis & Statistical Comparisons
Stage 8: Analytical EDA-B
Evaluates measures across categorical dimensions, executes inferential group comparisons (ANOVA, Welch t-test),
and guarantees correct headcount distinct-count and ratio denominator evaluations.
"""

from __future__ import annotations

import math
from typing import Any
import numpy as np

from app.services.ingestion_v2.analytics.finding_registry import FindingRegistry
from app.services.ingestion_v2.analytics.helpers import (
    get_column_name,
    get_column_role,
    get_column_type,
)
from app.services.ingestion_v2.analytics.statistical_tests import perform_anova, perform_two_sample_test
from app.services.ingestion_v2.contracts.analytics import FindingType
from app.services.ingestion_v2.contracts.profiling import TableStructuralProfile
from app.services.ingestion_v2.contracts.semantics import SemanticColumnRole


def analyze_grouped_comparisons(
    table_id: str,
    table_profile: TableStructuralProfile,
    column_semantics: dict[str, Any],
    rows: list[dict[str, Any]],
    registry: FindingRegistry,
    target_grain: str | None = None,
    join_plan_ids: list[str] | None = None,
) -> None:
    """
    Computes group-level summaries and statistical comparisons between groups.
    Enforces headcount COUNT(DISTINCT) and ratio SUM/SUM logic.
    """
    if not rows or len(rows) < 5:
        return

    dim_cols: list[str] = []
    metric_cols: list[str] = []
    entity_cols: list[str] = []

    for col_profile in table_profile.columns:
        col_id = get_column_name(col_profile)
        col_type = get_column_type(col_profile)
        sem = column_semantics.get(col_id)
        role = get_column_role(sem)

        if role in (SemanticColumnRole.ENTITY_IDENTIFIER,):
            entity_cols.append(col_id)
        elif col_type == "STRING" and role in (
            SemanticColumnRole.DIMENSION,
            SemanticColumnRole.ATTRIBUTE,
            SemanticColumnRole.STATUS,
            SemanticColumnRole.CATEGORY,
        ):
            dim_cols.append(col_id)
        elif col_type in ("INTEGER", "FLOAT") and role in (
            SemanticColumnRole.MEASURE,
            SemanticColumnRole.ATTRIBUTE,
        ):
            metric_cols.append(col_id)

    # 1. Headcount across dimension (COUNT(DISTINCT entity_id))
    if entity_cols and dim_cols:
        ent_col = entity_cols[0]
        for dim_col in dim_cols[:2]:
            group_entities: dict[str, set] = {}
            for r in rows:
                d_val = r.get(dim_col)
                e_val = r.get(ent_col)
                if d_val is not None and e_val is not None:
                    d_str = str(d_val).strip()
                    group_entities.setdefault(d_str, set()).add(e_val)

            if len(group_entities) >= 2:
                headcounts = {k: len(v) for k, v in group_entities.items()}
                total_distinct_headcount = len(set.union(*group_entities.values()))

                top_group = max(headcounts.items(), key=lambda x: x[1])

                desc = (
                    f"Distinct headcount for '{ent_col}' across '{dim_col}' in '{table_id}' totals {total_distinct_headcount} "
                    f"entities across {len(headcounts)} groups (largest group: '{top_group[0]}' with {top_group[1]} entities)."
                )

                registry.register(
                    finding_type=FindingType.COUNT,
                    description=desc,
                    source_table_ids=[table_id],
                    source_column_ids=[dim_col, ent_col],
                    target_grain=target_grain or f"{table_id}_ROW",
                    join_plan_ids=join_plan_ids or [],
                    result={
                        "dimension": dim_col,
                        "entity_column": ent_col,
                        "headcounts": headcounts,
                        "total_distinct_headcount": total_distinct_headcount,
                        "aggregation_type": "COUNT(DISTINCT)",
                    },
                    metric_definition=f"COUNT(DISTINCT {ent_col})",
                    dimension_definition=dim_col,
                    population_definition="ALL_ROWS",
                    confidence=1.0,
                    analysis_method="DISTINCT_HEADCOUNT",
                )

    # 2. Continuous Metric Comparisons Across Groups
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

            valid_groups = {k: v for k, v in group_vals.items() if len(v) >= 1}
            if len(valid_groups) < 2 or len(valid_groups) > 15:
                continue

            low_support_groups = [k for k, v in valid_groups.items() if len(v) < 5]
            has_low_support = len(low_support_groups) > 0
            limitations = []
            if has_low_support:
                limitations.append(f"LOW_SUPPORT: Groups {low_support_groups[:3]} have fewer than 5 observations.")

            group_summaries = {}
            for k, v in valid_groups.items():
                group_summaries[k] = {
                    "count": len(v),
                    "mean": round(float(np.mean(v)), 2),
                    "std": round(float(np.std(v, ddof=1)), 2) if len(v) > 1 else 0.0,
                    "median": round(float(np.median(v)), 2),
                }

            # Statistical testing
            sorted_groups = sorted(valid_groups.items(), key=lambda x: len(x[1]), reverse=True)
            stat_evid = None
            if len(valid_groups) == 2:
                g1_vals = sorted_groups[0][1]
                g2_vals = sorted_groups[1][1]
                stat_evid = perform_two_sample_test(g1_vals, g2_vals)
            elif len(valid_groups) >= 3:
                top_group_vals = [g[1] for g in sorted_groups[:5] if len(g[1]) >= 2]
                if len(top_group_vals) >= 2:
                    stat_evid = perform_anova(top_group_vals)

            top1_k, top1_sum = sorted_groups[0][0], group_summaries[sorted_groups[0][0]]
            top2_k, top2_sum = sorted_groups[1][0], group_summaries[sorted_groups[1][0]]

            p_val_clause = ""
            if stat_evid:
                p_val_clause = f" (test: {stat_evid.test_name}, statistic = {stat_evid.test_statistic:.2f}, p = {stat_evid.p_value:.4f})"

            desc = (
                f"Comparison of '{metric_col}' across '{dim_col}' in '{table_id}': "
                f"'{top1_k}' observed mean {top1_sum['mean']} (n={top1_sum['count']}) vs "
                f"'{top2_k}' observed mean {top2_sum['mean']} (n={top2_sum['count']}){p_val_clause}."
            )

            registry.register(
                finding_type=FindingType.GROUP_COMPARISON,
                description=desc,
                source_table_ids=[table_id],
                source_column_ids=[dim_col, metric_col],
                target_grain=target_grain or f"{table_id}_ROW",
                join_plan_ids=join_plan_ids or [],
                result={
                    "dimension": dim_col,
                    "metric": metric_col,
                    "group_summaries": group_summaries,
                    "total_groups": len(valid_groups),
                    "has_low_support": has_low_support,
                },
                metric_definition=f"AVG({metric_col})",
                dimension_definition=dim_col,
                population_definition="ALL_ROWS",
                confidence=0.80 if has_low_support else 1.0,
                limitations=limitations,
                analysis_method="GROUP_MEAN_COMPARISON",
                statistical_evidence=stat_evid,
            )


def analyze_governed_ratio(
    table_id: str,
    numerator_col: str,
    denominator_col: str,
    rows: list[dict[str, Any]],
    registry: FindingRegistry,
    dimension_col: str | None = None,
    target_grain: str | None = None,
    join_plan_ids: list[str] | None = None,
) -> None:
    """
    Evaluates governed ratio calculation: SUM(num) / NULLIF(SUM(den), 0).
    Guarantees that overall ratio is computed by summing numerators and denominators,
    never by averaging individual group ratios (avoiding Simpson's / ratio paradox).
    """
    if not rows:
        return

    valid_pairs = []
    group_pairs: dict[str, list[tuple[float, float]]] = {}

    for r in rows:
        n_val = r.get(numerator_col)
        d_val = r.get(denominator_col)
        if n_val is not None and d_val is not None:
            try:
                fn = float(n_val)
                fd = float(d_val)
                valid_pairs.append((fn, fd))
                if dimension_col:
                    dim_k = str(r.get(dimension_col, "OTHER")).strip()
                    group_pairs.setdefault(dim_k, []).append((fn, fd))
            except (ValueError, TypeError):
                pass

    if not valid_pairs:
        return

    total_num = sum(p[0] for p in valid_pairs)
    total_den = sum(p[1] for p in valid_pairs)
    overall_ratio = (total_num / total_den) if total_den != 0 else 0.0

    group_results = {}
    if dimension_col and group_pairs:
        for g_name, pairs in group_pairs.items():
            g_num = sum(p[0] for p in pairs)
            g_den = sum(p[1] for p in pairs)
            g_ratio = (g_num / g_den) if g_den != 0 else 0.0
            group_results[g_name] = {
                "numerator_sum": round(g_num, 2),
                "denominator_sum": round(g_den, 2),
                "ratio": round(g_ratio, 4),
            }

    desc = (
        f"Governed ratio '{numerator_col} / {denominator_col}' in '{table_id}' totals {overall_ratio:.4f} "
        f"({total_num:,.1f} / {total_den:,.1f} across {len(valid_pairs)} records)."
    )

    registry.register(
        finding_type=FindingType.RATE,
        description=desc,
        source_table_ids=[table_id],
        source_column_ids=[c for c in [numerator_col, denominator_col, dimension_col] if c],
        target_grain=target_grain or f"{table_id}_ROW",
        join_plan_ids=join_plan_ids or [],
        result={
            "overall_numerator_sum": round(total_num, 2),
            "overall_denominator_sum": round(total_den, 2),
            "overall_ratio": round(overall_ratio, 4),
            "sample_size": len(valid_pairs),
            "group_ratios": group_results,
        },
        metric_definition=f"SUM({numerator_col}) / NULLIF(SUM({denominator_col}), 0)",
        dimension_definition=dimension_col,
        population_definition="ALL_ROWS",
        numerator_definition=f"SUM({numerator_col})",
        denominator_definition=f"SUM({denominator_col})",
        confidence=1.0,
        analysis_method="GOVERNED_RATIO_SUM_OVER_SUM",
    )
