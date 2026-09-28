"""Assembles structured EDA reports for individual sheets and multi-sheet collections."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_sheet_eda_report(
    sheet_meta: dict[str, Any],
    norm_result: dict[str, Any],
    cross_intel: dict[str, Any],
    derived_tables: list[dict[str, Any]],
    snapshot: str | None = None,
) -> dict[str, Any]:
    """Builds a comprehensive EDA report for a single sheet, including intra-sheet and cross-sheet findings."""
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

    return {
        "sheet_id": sheet_id,
        "dataset_id": dataset_id,
        "snapshot": snapshot,
        "sheet_name": sheet_name,
        "health_score": score,
        "health_status": health_status,
        "generation_timestamp": datetime.now(timezone.utc).isoformat(),
        "eda_method_version": "1.0.0",

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
        "cross_sheet_intelligence": {
            "entity_links": related_links,
            "correlations": related_correlations,
            "derived_tables": related_derived,
            "has_cross_sheet_connections": len(related_links) > 0,
        },
        "recommendations": _generate_recommendations(score, norm_result, related_links, related_correlations)
    }


def _generate_recommendations(
    score: int,
    norm_result: dict[str, Any],
    links: list[dict[str, Any]],
    correlations: list[dict[str, Any]]
) -> list[str]:
    recs: list[str] = []
    if norm_result["total_anomalies"] > 0:
        recs.append(
            f"Review {norm_result['total_anomalies']} statistical outliers detected via IQR profiling in the Explore table view."
        )
    if norm_result["total_null_cells"] > 0:
        recs.append(
            f"Detected {norm_result['total_null_cells']} missing values across columns. Automated imputation strategies (median for skewed metrics, mode for categories) have been prepared."
        )
    if norm_result["total_normalized_cells"] > 0:
        recs.append(
            f"{norm_result['total_normalized_cells']} cells were successfully coerced into canonical numbers, ratings, or dates."
        )
    if links:
        recs.append(
            f"Verified {len(links)} cross-sheet entity joins. Use Post-EDA Curated or Derived views to query combined records."
        )
    if correlations:
        strong_corrs = [c for c in correlations if c.get("strength") == "strong"]
        if strong_corrs:
            recs.append(
                f"Identified {len(strong_corrs)} strong cross-sheet metric correlations ($|r| \\ge 0.70$) that can inform predictive models."
            )
    if not recs:
        recs.append("Data profile is clean and fully normalized for downstream projection pipelines.")
    return recs
