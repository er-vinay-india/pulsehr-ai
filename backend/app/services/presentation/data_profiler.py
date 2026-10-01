import logging
import math
from typing import Any
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def profile_presentation_dataset(
    records: list[dict[str, Any]],
    columns: list[str]
) -> dict[str, Any]:
    """Inspects all records, columns, categories, statuses, and distributions.
    Computes exact counts, non-null rates, percentages, distributions, outliers,
    and ranks dimensions by analytical usefulness.
    Follows: SOURCE DATA -> DATA PROFILING -> METRIC CALCULATION -> PATTERN DISCOVERY."""
    total_records = len(records)
    if total_records == 0 or not columns:
        return {
            "total_records": 0,
            "valid_records": 0,
            "completeness_pct": 0.0,
            "dimensions": {},
            "ranked_dimensions": [],
            "status_distributions": {},
            "top_categories": [],
            "patterns": [],
            "traceable_metrics": []
        }

    df = pd.DataFrame(records)

    # 1. Total records, validity, completeness
    non_null_counts = df.notnull().sum()
    total_cells = df.size
    valid_cells = int(non_null_counts.sum()) if total_cells > 0 else 0
    completeness_pct = round((valid_cells / total_cells) * 100, 1) if total_cells > 0 else 100.0

    # Clean valid records (rows where critical fields are non-empty)
    valid_rows = int(df.dropna(how="all").shape[0])

    dimensions: dict[str, dict[str, Any]] = {}
    categorical_rankings: list[dict[str, Any]] = []
    numeric_rankings: list[dict[str, Any]] = []
    status_distributions: dict[str, Any] = {}
    traceable_metrics: list[dict[str, Any]] = []
    patterns: list[dict[str, Any]] = []

    # Detect status / outcome / classification columns
    status_col_candidates = []
    for col in columns:
        col_lower = col.lower().replace("_", "").replace(" ", "")
        if any(k in col_lower for k in ("status", "result", "outcome", "flag", "state", "disposition", "category", "type")):
            status_col_candidates.append(col)

    for col in columns:
        if col not in df.columns:
            continue
        series = df[col]
        non_null_n = int(series.notnull().sum())
        null_n = total_records - non_null_n

        # Check if numeric
        numeric_series = pd.to_numeric(series, errors="coerce")
        valid_num = numeric_series.dropna()

        if len(valid_num) >= max(2, int(non_null_n * 0.7)) and non_null_n > 0:
            # Numerical Dimension
            mean_val = float(valid_num.mean())
            median_val = float(valid_num.median())
            std_val = float(valid_num.std()) if len(valid_num) > 1 else 0.0
            min_val = float(valid_num.min())
            max_val = float(valid_num.max())

            # Outliers (values > 2 std dev)
            outliers = []
            if std_val > 0:
                z_scores = np.abs((valid_num - mean_val) / std_val)
                outliers = valid_num[z_scores > 2.0].tolist()

            dim_info = {
                "type": "numeric",
                "name": col,
                "count": non_null_n,
                "null_count": null_n,
                "mean": round(mean_val, 2),
                "median": round(median_val, 2),
                "std": round(std_val, 2),
                "min": round(min_val, 2),
                "max": round(max_val, 2),
                "outlier_count": len(outliers),
                "dispersion_ratio": round(max_val / max(min_val, 0.001), 2) if min_val > 0 else None
            }
            dimensions[col] = dim_info
            numeric_rankings.append(dim_info)

            traceable_metrics.append({
                "metric_id": f"METRIC-NUM-{col.upper()[:8]}",
                "label": f"Average {col}",
                "value": round(mean_val, 2),
                "denominator": non_null_n,
                "percentage": None,
                "source_column": col,
                "calculation": f"mean({col})"
            })
        else:
            # Categorical Dimension
            val_counts = series.dropna().astype(str).value_counts()
            unique_count = len(val_counts)
            if unique_count == 0:
                continue

            top_cats = []
            for cat_name, count in val_counts.head(10).items():
                pct = round((count / max(total_records, 1)) * 100, 1)
                top_cats.append({
                    "category": cat_name,
                    "count": int(count),
                    "percentage": pct
                })

            dim_info = {
                "type": "categorical",
                "name": col,
                "count": non_null_n,
                "null_count": null_n,
                "unique_count": unique_count,
                "top_categories": top_cats,
                "leading_category": top_cats[0]["category"] if top_cats else None,
                "leading_count": top_cats[0]["count"] if top_cats else 0,
                "leading_pct": top_cats[0]["percentage"] if top_cats else 0.0
            }
            dimensions[col] = dim_info
            # Analytical usefulness score: cardinality between 2 and 15 is ideal for executive storytelling
            is_date_col = any(d in col.lower() for d in ('date', 'timestamp', 'created_at', 'updated_at', 'dob', 'time'))
            if is_date_col:
                usefulness = 1.0
            elif 2 <= unique_count <= 12:
                usefulness = 100.0
            else:
                usefulness = max(5.0, 100.0 - abs(unique_count - 6) * 5)
            dim_info["usefulness_score"] = usefulness
            categorical_rankings.append(dim_info)

            # Check if this is a status/outcome distribution
            if col in status_col_candidates or any(k in col.lower() for k in ("status", "result", "flag")):
                status_distributions[col] = top_cats

            # Traceable metrics for top categories
            if top_cats:
                for tc in top_cats[:3]:
                    traceable_metrics.append({
                        "metric_id": f"METRIC-CAT-{col.upper()[:4]}-{tc['category'].upper()[:6]}",
                        "label": f"{tc['category']} Share",
                        "value": tc["count"],
                        "denominator": total_records,
                        "percentage": tc["percentage"],
                        "source_column": col,
                        "calculation": f"count({col} == '{tc['category']}') / {total_records}"
                    })

    # Sort rankings
    categorical_rankings.sort(key=lambda x: x.get("usefulness_score", 0), reverse=True)

    # Identify recurring patterns / concentrations
    for cat_dim in categorical_rankings[:3]:
        top_cats = cat_dim.get("top_categories", [])
        if top_cats:
            leader = top_cats[0]
            if leader["percentage"] >= 35.0:
                patterns.append({
                    "pattern_type": "concentration",
                    "column": cat_dim["name"],
                    "category": leader["category"],
                    "count": leader["count"],
                    "percentage": leader["percentage"],
                    "summary": f"{leader['count']} of {total_records} records ({leader['percentage']}%) concentrated in '{leader['category']}'."
                })
            if len(top_cats) >= 2 and top_cats[-1]["percentage"] <= 8.0:
                laggard = top_cats[-1]
                patterns.append({
                    "pattern_type": "exception",
                    "column": cat_dim["name"],
                    "category": laggard["category"],
                    "count": laggard["count"],
                    "percentage": laggard["percentage"],
                    "summary": f"{laggard['count']} records ({laggard['percentage']}%) in minority cohort '{laggard['category']}' require inspection."
                })

    # 4. Multi-Grain Temporal Profiling (Per Day, Per Week, Per Month, Per Annum)
    temporal_profile = {}
    try:
        from ..analytics.temporal_categorical_engine import extract_multi_grain_temporal_insights
        temporal_profile = extract_multi_grain_temporal_insights(df, columns)
        if temporal_profile.get("has_temporal_data"):
            weekly = temporal_profile.get("weekly", {})
            if weekly.get("has_weekly"):
                timeline = weekly.get("timeline", [])
                if timeline:
                    top_w = max(timeline, key=lambda x: x["mean"])
                    traceable_metrics.append({
                        "metric_id": "METRIC-TEMP-WEEKLY-PEAK",
                        "label": f"Peak Week ({top_w['period_label']}) Mean",
                        "value": top_w["mean"],
                        "denominator": top_w["count"],
                        "percentage": None,
                        "source_column": temporal_profile.get("primary_measure") or temporal_profile.get("date_column"),
                        "calculation": f"max(weekly_mean({temporal_profile.get('primary_measure')}))"
                    })
                if weekly.get("avg_wow_velocity") is not None:
                    traceable_metrics.append({
                        "metric_id": "METRIC-TEMP-WOW-VELOCITY",
                        "label": "Average Week-over-Week Momentum",
                        "value": weekly["avg_wow_velocity"],
                        "denominator": len(timeline),
                        "percentage": weekly["avg_wow_velocity"],
                        "source_column": temporal_profile.get("primary_measure") or temporal_profile.get("date_column"),
                        "calculation": "mean(wow_growth_pct)"
                    })
            daily = temporal_profile.get("daily", {})
            if daily.get("has_daily") and daily.get("peak_day"):
                traceable_metrics.append({
                    "metric_id": "METRIC-TEMP-PEAK-DAY",
                    "label": "Peak Day of Week",
                    "value": daily["peak_day"],
                    "denominator": total_records,
                    "percentage": None,
                    "source_column": temporal_profile.get("date_column"),
                    "calculation": "mode(day_of_week)"
                })
            annual = temporal_profile.get("annual", {})
            if annual.get("has_annual") and annual.get("annualized_run_rate"):
                traceable_metrics.append({
                    "metric_id": "METRIC-TEMP-ANNUAL-RUNRATE",
                    "label": "Annualized Projected Volume",
                    "value": annual["annualized_run_rate"],
                    "denominator": total_records,
                    "percentage": None,
                    "source_column": temporal_profile.get("primary_measure"),
                    "calculation": "sum(period_totals) * annualization_factor"
                })
            for ins in temporal_profile.get("insights", []):
                patterns.append({
                    "pattern_type": "temporal_trajectory",
                    "column": temporal_profile.get("date_column") or "Temporal",
                    "category": temporal_profile.get("grain_type", "time_series"),
                    "count": len(weekly.get("timeline", [])),
                    "percentage": weekly.get("avg_wow_velocity"),
                    "summary": ins
                })
    except Exception as exc:
        logger.debug(f"Data profiler temporal extraction skipped: {exc}")

    # 5. Bivariate Categorical Group-By Cross-Tabulations
    categorical_profile = {}
    try:
        from ..analytics.temporal_categorical_engine import extract_bivariate_categorical_insights
        categorical_profile = extract_bivariate_categorical_insights(df, columns)
        if categorical_profile.get("has_categorical_data"):
            for dim, meas_map in categorical_profile.get("breakdowns", {}).items():
                for meas, b_info in meas_map.items():
                    traceable_metrics.append({
                        "metric_id": f"METRIC-CAT-DISP-{dim[:4].upper()}-{meas[:4].upper()}",
                        "label": f"{b_info['dimension_label']} Dispersion Ratio ({b_info['measure_label']})",
                        "value": b_info["dispersion_ratio"],
                        "denominator": b_info["total_records"],
                        "percentage": b_info["disparity_pct"],
                        "source_column": f"{dim} x {meas}",
                        "calculation": f"max({meas}) / min({meas}) across {dim}"
                    })
                    traceable_metrics.append({
                        "metric_id": f"METRIC-CAT-LEAD-{dim[:4].upper()}-{meas[:4].upper()}",
                        "label": f"Top Cohort: {b_info['top_category']} Mean",
                        "value": b_info["top_mean"],
                        "denominator": b_info["counts"][0] if b_info["counts"] else total_records,
                        "percentage": b_info["shares"][0] if b_info["shares"] else None,
                        "source_column": f"{dim} x {meas}",
                        "calculation": f"mean({meas}) for {dim} == '{b_info['top_category']}'"
                    })
            for ins in categorical_profile.get("insights", []):
                patterns.append({
                    "pattern_type": "categorical_disparity",
                    "column": categorical_profile.get("dimensions", ["Categorical"])[0],
                    "category": "bivariate_breakdown",
                    "count": total_records,
                    "percentage": None,
                    "summary": ins
                })
    except Exception as exc:
        logger.debug(f"Data profiler categorical extraction skipped: {exc}")

    return {
        "total_records": total_records,
        "valid_records": valid_rows,
        "completeness_pct": completeness_pct,
        "dimensions": dimensions,
        "ranked_categorical": categorical_rankings,
        "ranked_numeric": numeric_rankings,
        "status_distributions": status_distributions,
        "patterns": patterns,
        "traceable_metrics": traceable_metrics,
        "temporal_profile": temporal_profile,
        "categorical_profile": categorical_profile
    }
