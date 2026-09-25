"""Intra-sheet data cleansing, type normalization, and statistical profiling engine."""
from __future__ import annotations

import math
import re
from typing import Any
import numpy as np
import pandas as pd

NULL_STRINGS = {
    "", "none", "null", "nan", "na", "n/a", "-", "--", "undefined",
    "nil", "#n/a", "#null!", "n.a.", "n.a", "unknown", "n/d"
}

def is_null_val(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, float) and math.isnan(val):
        return True
    s = str(val).strip().casefold()
    return s in NULL_STRINGS


def parse_percentage(val: Any) -> tuple[float | None, bool]:
    if is_null_val(val):
        return None, False
    s = str(val).strip()
    m = re.fullmatch(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*%", s)
    if m:
        try:
            return float(m.group(1)), True
        except ValueError:
            pass
    return None, False


def parse_currency(val: Any) -> tuple[float | None, bool]:
    if is_null_val(val):
        return None, False
    s = str(val).strip()
    m = re.fullmatch(r"([+-]?)\s*[\$€£¥₹]\s*([0-9,]+(?:\.\d+)?)", s)
    if m:
        sign = -1.0 if m.group(1) == "-" else 1.0
        clean_num = m.group(2).replace(",", "")
        try:
            return sign * float(clean_num), True
        except ValueError:
            pass
    return None, False


def parse_rating_fraction(val: Any) -> tuple[float | None, float | None, bool]:
    if is_null_val(val):
        return None, None, False
    s = str(val).strip()
    m = re.fullmatch(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*/\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))", s)
    if m:
        try:
            numerator = float(m.group(1))
            denominator = float(m.group(2))
            return numerator, denominator, True
        except ValueError:
            pass
    return None, None, False


def parse_temperature(val: Any) -> tuple[float | None, str | None, bool]:
    if is_null_val(val):
        return None, None, False
    s = str(val).strip()
    m = re.fullmatch(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(?:°\s*([FCKfc])|deg\s*([FCKfc])|([FCfc]|Celsius|Fahrenheit|Kelvin))", s, re.IGNORECASE)
    if m:
        try:
            num = float(m.group(1))
            unit_char = (m.group(2) or m.group(3) or m.group(4) or "C").upper()[:1]
            unit = f"°{unit_char}" if unit_char in ("F", "C") else unit_char
            return num, unit, True
        except ValueError:
            pass
    return None, None, False


def parse_area(val: Any) -> tuple[float | None, str | None, bool]:
    if is_null_val(val):
        return None, None, False
    s = str(val).strip()
    m = re.fullmatch(r"([+-]?(?:[0-9,]+(?:\.\d*)?|\.\d+))\s*(sq\s*ft|sqft|sq\s*m|sqm|m²|m2|sq\s*km|sqkm|km²|acres?|hectares?|ha)", s, re.IGNORECASE)
    if m:
        try:
            num = float(m.group(1).replace(",", ""))
            u_raw = m.group(2).lower()
            if "ft" in u_raw:
                unit = "sq ft"
            elif "km" in u_raw or "km²" in u_raw:
                unit = "km²"
            elif "m" in u_raw or "m²" in u_raw:
                unit = "m²"
            elif "acre" in u_raw:
                unit = "acres"
            elif "ha" in u_raw or "hectare" in u_raw:
                unit = "ha"
            else:
                unit = u_raw
            return num, unit, True
        except ValueError:
            pass
    return None, None, False


def parse_clean_numeric(val: Any) -> tuple[float | int | None, bool]:
    if is_null_val(val):
        return None, False
    if isinstance(val, (int, float)):
        return val, True
    s = str(val).strip().replace(",", "")
    if re.fullmatch(r"[+-]?\d+", s):
        try:
            return int(s), True
        except ValueError:
            pass
    if re.fullmatch(r"[+-]?(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?", s):
        try:
            return float(s), True
        except ValueError:
            pass
    return None, False


def parse_iso_date(val: Any) -> tuple[str | None, bool]:
    if is_null_val(val):
        return None, False
    s = str(val).strip()
    # Check if clock interval like 08:43-16:42
    if re.search(r"\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}", s):
        return None, False
    # Check if already ISO format YYYY-MM-DD
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s, True
    # Require date-like pattern with year/month/day
    if not re.search(r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}", s):
        return None, False
    try:
        dt = pd.to_datetime(s, errors="raise")
        return dt.strftime("%Y-%m-%d"), True
    except Exception:
        return None, False


def is_time_interval(val: Any) -> bool:
    if is_null_val(val):
        return False
    return bool(re.search(r"\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}", str(val).strip()))


def infer_column_type(col_name: str, values: list[Any]) -> dict[str, Any]:
    non_nulls = [v for v in values if not is_null_val(v)]
    total = len(values)
    if not non_nulls:
        return {"inferred_type": "empty", "unit": None, "scale_max": None}

    # Identifier check
    c_lower = col_name.lower().replace("_", "").replace("-", "").strip()
    is_id = c_lower.endswith("id") or c_lower == "id" or "code" in c_lower or c_lower.endswith("key")

    # Time interval check (e.g. 08:43-16:42 clock logs)
    interval_matches = sum(1 for v in non_nulls if is_time_interval(v))
    if interval_matches / len(non_nulls) >= 0.8:
        return {"inferred_type": "time_interval", "unit": "hours_log", "scale_max": None}

    # Percentage check
    pct_matches = sum(1 for v in non_nulls if parse_percentage(v)[1])
    if pct_matches / len(non_nulls) >= 0.8:
        return {"inferred_type": "numeric_percentage", "unit": "%", "scale_max": 100.0}

    # Currency check
    curr_matches = sum(1 for v in non_nulls if parse_currency(v)[1])
    if curr_matches / len(non_nulls) >= 0.8:
        return {"inferred_type": "numeric_currency", "unit": "$", "scale_max": None}

    # Rating fraction check
    rating_matches = [parse_rating_fraction(v) for v in non_nulls]
    success_ratings = [r for r in rating_matches if r[2]]
    if len(success_ratings) / len(non_nulls) >= 0.8:
        max_scale = max(r[1] for r in success_ratings if r[1] is not None) if success_ratings else 5.0
        return {"inferred_type": "numeric_rating", "unit": f"out of {max_scale:g}", "scale_max": max_scale}

    # Temperature check
    temp_matches = sum(1 for v in non_nulls if parse_temperature(v)[2])
    if temp_matches / len(non_nulls) >= 0.8:
        sample_u = next((parse_temperature(v)[1] for v in non_nulls if parse_temperature(v)[2]), "°C")
        return {"inferred_type": "numeric_temperature", "unit": sample_u, "scale_max": None}

    # Area check
    area_matches = sum(1 for v in non_nulls if parse_area(v)[2])
    if area_matches / len(non_nulls) >= 0.8:
        sample_u = next((parse_area(v)[1] for v in non_nulls if parse_area(v)[2]), "sq ft")
        return {"inferred_type": "numeric_area", "unit": sample_u, "scale_max": None}

    # Numeric check
    num_matches = sum(1 for v in non_nulls if parse_clean_numeric(v)[1])
    if num_matches / len(non_nulls) >= 0.8:
        if is_id:
            return {"inferred_type": "identifier", "unit": None, "scale_max": None}
        return {"inferred_type": "numeric", "unit": None, "scale_max": None}

    # Date check
    date_matches = sum(1 for v in non_nulls if parse_iso_date(v)[1])
    if date_matches / len(non_nulls) >= 0.8:
        return {"inferred_type": "datetime", "unit": None, "scale_max": None}

    if is_id:
        return {"inferred_type": "identifier", "unit": None, "scale_max": None}

    return {"inferred_type": "categorical", "unit": None, "scale_max": None}


def normalize_dataset(sheet_id: int, sheet_name: str, columns: list[str], raw_records: list[dict[str, Any]]) -> dict[str, Any]:
    """Cleans, normalizes, detects outliers, and generates curated records and EDA diagnostics."""
    total_rows = len(raw_records)
    curated_records: list[dict[str, Any]] = [{} for _ in range(total_rows)]
    anomalies_per_row: list[list[dict[str, Any]]] = [[] for _ in range(total_rows)]
    transformations_log: list[dict[str, Any]] = []
    column_diagnostics: dict[str, Any] = {}

    total_cells = max(1, total_rows * len(columns))
    total_normalized_cells = 0
    total_null_cells = 0
    total_anomalies = 0

    for col in columns:
        raw_vals = [rec.get(col) for rec in raw_records]
        type_info = infer_column_type(col, raw_vals)
        inferred_type = type_info["inferred_type"]
        unit = type_info["unit"]
        scale_max = type_info["scale_max"]

        normalized_vals: list[Any] = []
        col_transforms = 0

        for r_idx, val in enumerate(raw_vals):
            if is_null_val(val):
                normalized_vals.append(None)
                total_null_cells += 1
                if val is not None and str(val).strip() != "":
                    col_transforms += 1
                continue

            if inferred_type == "numeric_percentage":
                num, ok = parse_percentage(val)
                if not ok:
                    num, ok = parse_clean_numeric(val)
                if ok and num is not None:
                    normalized_vals.append(round(float(num), 2))
                    col_transforms += 1
                else:
                    normalized_vals.append(None)

            elif inferred_type == "numeric_currency":
                num, ok = parse_currency(val)
                if not ok:
                    num, ok = parse_clean_numeric(val)
                if ok and num is not None:
                    normalized_vals.append(round(float(num), 2))
                    col_transforms += 1
                else:
                    normalized_vals.append(None)

            elif inferred_type == "numeric_rating":
                num, denom, ok = parse_rating_fraction(val)
                if not ok:
                    num, ok = parse_clean_numeric(val)
                if ok and num is not None:
                    normalized_vals.append(round(float(num), 2))
                    col_transforms += 1
                else:
                    normalized_vals.append(None)

            elif inferred_type == "numeric_temperature":
                num, u, ok = parse_temperature(val)
                if not ok:
                    num, ok = parse_clean_numeric(val)
                if ok and num is not None:
                    normalized_vals.append(round(float(num), 2))
                    col_transforms += 1
                else:
                    normalized_vals.append(None)

            elif inferred_type == "numeric_area":
                num, u, ok = parse_area(val)
                if not ok:
                    num, ok = parse_clean_numeric(val)
                if ok and num is not None:
                    normalized_vals.append(round(float(num), 2))
                    col_transforms += 1
                else:
                    normalized_vals.append(None)

            elif inferred_type == "numeric":
                num, ok = parse_clean_numeric(val)
                if ok and num is not None:
                    # Keep int if exact integer
                    if isinstance(num, int) or (isinstance(num, float) and num.is_integer()):
                        normalized_vals.append(int(num))
                    else:
                        normalized_vals.append(round(float(num), 4))
                    if str(val) != str(normalized_vals[-1]):
                        col_transforms += 1
                else:
                    normalized_vals.append(None)

            elif inferred_type == "datetime":
                dt_str, ok = parse_iso_date(val)
                if ok and dt_str:
                    normalized_vals.append(dt_str)
                    if str(val) != dt_str:
                        col_transforms += 1
                else:
                    normalized_vals.append(str(val).strip())

            else:
                # String / Categorical / Identifier
                cleaned_str = " ".join(str(val).strip().split())
                normalized_vals.append(cleaned_str)
                if cleaned_str != str(val):
                    col_transforms += 1

        total_normalized_cells += col_transforms

        # Populate curated records
        for r_idx in range(total_rows):
            curated_records[r_idx][col] = normalized_vals[r_idx]

        # Outlier Detection for numeric columns
        outliers: list[dict[str, Any]] = []
        num_vals = [v for v in normalized_vals if v is not None and isinstance(v, (int, float))]
        min_val, max_val, mean_val, median_val, std_val = None, None, None, None, None

        if len(num_vals) >= 4:
            s = pd.Series(num_vals)
            q1 = float(s.quantile(0.25))
            q3 = float(s.quantile(0.75))
            iqr = q3 - q1
            min_val = round(float(s.min()), 2)
            max_val = round(float(s.max()), 2)
            mean_val = round(float(s.mean()), 2)
            median_val = round(float(s.median()), 2)
            std_val = round(float(s.std()), 2)

            if iqr > 0:
                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr
                for r_idx, v in enumerate(normalized_vals):
                    if v is not None and isinstance(v, (int, float)):
                        if v < lower_bound or v > upper_bound:
                            outlier_info = {
                                "row_index": r_idx + 1,
                                "column": col,
                                "value": v,
                                "expected_range": [round(lower_bound, 2), round(upper_bound, 2)],
                                "type": "statistical_outlier"
                            }
                            outliers.append(outlier_info)
                            anomalies_per_row[r_idx].append(outlier_info)
                            total_anomalies += 1

        elif len(num_vals) > 0:
            s = pd.Series(num_vals)
            min_val = round(float(s.min()), 2)
            max_val = round(float(s.max()), 2)
            mean_val = round(float(s.mean()), 2)
            median_val = round(float(s.median()), 2)

        null_cnt = sum(1 for v in normalized_vals if v is None)
        distinct_cnt = len(set(v for v in normalized_vals if v is not None))

        # Smart Missing Value Imputation Calculation (Mean, Median, Mode)
        imputation_info = None
        if null_cnt > 0:
            if num_vals:
                s_num = pd.Series(num_vals)
                skewness = float(s_num.skew()) if len(num_vals) >= 3 else 0.0
                has_outliers = len(outliers) > 0
                if abs(skewness) > 1.0 or has_outliers:
                    imp_val = median_val
                    strategy = "median"
                    rationale = f"Skewed distribution (skew={skewness:.2f}) or outliers detected; median provides robust non-parametric central tendency."
                else:
                    imp_val = mean_val
                    strategy = "mean"
                    rationale = f"Symmetric distribution (skew={skewness:.2f}); mean preserves unbiased linear aggregation."
            else:
                valid_strs = [str(v) for v in normalized_vals if v is not None]
                if valid_strs:
                    mode_val = pd.Series(valid_strs).mode().iloc[0]
                    imp_val = mode_val
                    strategy = "mode"
                    rationale = f"Discrete categorical variable; mode '{mode_val}' represents the highest-frequency baseline."
                else:
                    imp_val = None
                    strategy = "constant_empty"
                    rationale = "All records null; constant sentinel assigned."

            imputation_info = {
                "strategy": strategy,
                "recommended_value": imp_val,
                "missing_count": null_cnt,
                "missing_pct": round((null_cnt / max(1, total_rows)) * 100, 1),
                "rationale": rationale
            }

        column_diagnostics[col] = {
            "column": col,
            "inferred_type": inferred_type,
            "unit": unit,
            "scale_max": scale_max,
            "null_count": null_cnt,
            "null_percentage": round((null_cnt / max(1, total_rows)) * 100, 1),
            "distinct_count": distinct_cnt,
            "min": min_val,
            "max": max_val,
            "mean": mean_val,
            "median": median_val,
            "std": std_val,
            "outlier_count": len(outliers),
            "outliers": outliers[:10],
            "imputation": imputation_info,
            "transformations_applied": col_transforms
        }

        if col_transforms > 0:
            transformations_log.append({
                "column": col,
                "inferred_type": inferred_type,
                "cells_transformed": col_transforms,
                "transformation": (
                    f"Converted to {inferred_type} ({unit or 'standardized'}) and standardized nulls"
                    if unit else f"Coerced to clean {inferred_type} format"
                )
            })

    # Overall Data Cleanliness Health Score (0 - 100)
    avg_null_pct = (total_null_cells / total_cells) * 100.0
    outlier_rate = (total_anomalies / max(1, total_rows)) * 100.0
    health_score = max(10, min(100, round(100.0 - (0.5 * avg_null_pct) - (2.0 * outlier_rate))))

    return {
        "sheet_id": sheet_id,
        "sheet_name": sheet_name,
        "health_score": health_score,
        "total_rows": total_rows,
        "total_columns": len(columns),
        "total_normalized_cells": total_normalized_cells,
        "total_null_cells": total_null_cells,
        "total_anomalies": total_anomalies,
        "curated_records": curated_records,
        "anomalies_per_row": anomalies_per_row,
        "transformations_log": transformations_log,
        "column_diagnostics": column_diagnostics
    }
