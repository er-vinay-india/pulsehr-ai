"""Assembles structured EDA reports for individual sheets and multi-sheet collections with rich visual analytics."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_sheet_eda_report(
    sheet_meta: dict[str, Any],
    norm_result: dict[str, Any],
    cross_intel: dict[str, Any],
    derived_tables: list[dict[str, Any]],
    intra_correlations: dict[str, Any] | None = None,
    metric_distributions: dict[str, Any] | None = None,
    temporal_analysis: dict[str, Any] | None = None,
    predictive_suite: dict[str, Any] | None = None,
    snapshot: str | None = None,
) -> dict[str, Any]:
    """Builds a comprehensive EDA report for a single sheet, including intra-sheet and cross-sheet findings,
    temporal dynamics, predictive models (Linear & Logistic Regression), and visual charts data.
    """
    sheet_id = sheet_meta["id"]
    sheet_name = sheet_meta.get("display_name") or sheet_meta["name"]
    dataset_id = sheet_meta.get("dataset_id")

    # Filter links and correlations relevant to this sheet
    related_links = [
        link for link in cross_intel.get("entity_links", [])
        if link["left_sheet_id"] == sheet_id or link["right_sheet_id"] == sheet_id
    ]
    related_correlations = [
        corr for corr in cross_intel.get("cross_correlations", [])
        if corr["left_sheet_id"] == sheet_id or corr["right_sheet_id"] == sheet_id
    ]
    related_derived = [
        dt for dt in derived_tables
        if sheet_id in dt.get("source_sheets", [])
    ]

    # Health status label
    score = norm_result["health_score"]
    health_status = (
        "Excellent (Production Ready)" if score >= 90
        else "Good (Normalized & Usable)" if score >= 75
        else "Fair (Some Missing Data/Outliers)" if score >= 60
        else "Needs Attention (Significant Anomalies)"
    )

    clean_corrs = intra_correlations or {"metrics": [], "pairs": [], "matrix": []}
    clean_dists = metric_distributions or {}
    clean_temporal = temporal_analysis or {"has_temporal_data": False, "timeline_series": [], "insights": []}
    clean_predictive = predictive_suite or {"linear_models": [], "logistic_models": [], "domain_executive_points": []}

    return {
        "sheet_id": sheet_id,
        "dataset_id": dataset_id,
        "snapshot": snapshot,
        "sheet_name": sheet_name,
        "health_score": score,
        "health_status": health_status,
        "generation_timestamp": datetime.now(timezone.utc).isoformat(),
        "eda_method_version": "2.0.0",

        "summary": {
            "total_rows": norm_result["total_rows"],
            "total_columns": norm_result["total_columns"],
            "total_normalized_cells": norm_result["total_normalized_cells"],
            "total_null_cells": norm_result["total_null_cells"],
            "total_anomalies": norm_result["total_anomalies"],
            "cleanliness_pct": round(100.0 - ((norm_result["total_null_cells"] / max(1, norm_result["total_rows"] * norm_result["total_columns"])) * 100), 1),
        },
        "transformations_log": norm_result["transformations_log"],
        "column_diagnostics": norm_result["column_diagnostics"],

        # Visual Analytics Suite
        "visual_analytics": {
            "correlation_matrix": clean_corrs,
            "metric_distributions": clean_dists,
            "temporal_analysis": clean_temporal,
            "predictive_modeling": clean_predictive
        },

        # Multi-sheet connections
        "cross_sheet_intelligence": {
            "entity_links": related_links,
            "correlations": related_correlations,
            "derived_tables": related_derived,
            "has_cross_sheet_connections": len(related_links) > 0,
        },
        "recommendations": _generate_recommendations(
            score,
            norm_result,
            related_links,
            related_correlations,
            clean_temporal.get("insights", []),
            clean_predictive.get("domain_executive_points", [])
        )
    }


def _generate_recommendations(
    score: int,
    norm_result: dict[str, Any],
    links: list[dict[str, Any]],
    correlations: list[dict[str, Any]],
    temporal_insights: list[str],
    predictive_insights: list[str]
) -> list[str]:
    recs: list[str] = []

    # 1. Predictive and Domain-Specific HR Points (Highest priority)
    for p_ins in predictive_insights:
        recs.append(p_ins)

    for t_ins in temporal_insights:
        recs.append(t_ins)

    # 2. Data Hygiene and Outliers
    if norm_result["total_anomalies"] > 0:
        recs.append(
            f"Review {norm_result['total_anomalies']} statistical outliers detected via IQR profiling in the Explore table view."
        )
    if norm_result["total_null_cells"] > 0:
        recs.append(
            f"Detected {norm_result['total_null_cells']} missing values across columns. Automated imputation strategies have been prepared."
        )

    # 3. Cross-sheet joins
    if links:
        recs.append(
            f"Verified {len(links)} cross-sheet entity joins. Use Post-EDA Curated or Derived views to query combined records."
        )
    if correlations:
        strong_corrs = [c for c in correlations if c.get("strength") == "strong"]
        if strong_corrs:
            recs.append(
                f"Identified {len(strong_corrs)} strong cross-sheet metric correlations (|r| ≥ 0.70) confirming cross-system reconciliation."
            )

    return recs
