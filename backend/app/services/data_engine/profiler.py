"""Deterministic dataset profiling engine categorizing measures, dimensions, and timeline context."""

import re
from typing import Any
import pandas as pd
from pydantic import BaseModel, Field

from ..display_formatters import format_display_label


class ColumnProfile(BaseModel):
    """Detailed profile of an individual column."""
    name: str
    display_name: str
    inferred_type: str  # "numeric_measure", "categorical_dimension", "datetime", "identifier"
    null_percentage: float
    distinct_count: int
    unit: str = ""
    summary: dict[str, Any] = Field(default_factory=dict)


class DatasetProfile(BaseModel):
    """Holistic profile of the dataset consumed by analyst models."""
    dataset_name: str
    business_domain: str
    row_count: int
    column_count: int
    numeric_measures: list[str] = Field(default_factory=list)
    categorical_dimensions: list[str] = Field(default_factory=list)
    timeline_columns: list[str] = Field(default_factory=list)
    identifier_columns: list[str] = Field(default_factory=list)
    profiles: list[ColumnProfile] = Field(default_factory=list)
    observation_window: str = "Cross-sectional snapshot"


def is_id_column(col_name: str) -> bool:
    c = col_name.lower().replace("_", "").replace("-", "").strip()
    return c.endswith("id") or c == "id" or "uuid" in c or c.endswith("code") or c == "key"


def is_date_column(col_name: str, series: pd.Series) -> bool:
    c = col_name.lower()
    if any(k in c for k in ("date", "time", "timestamp", "month", "year", "quarter", "period", "week")):
        return True
    # Test date conversion on non-empty sample
    sample = series.dropna().astype(str).head(10)
    if len(sample) >= 3:
        try:
            pd.to_datetime(sample, errors='raise')
            return True
        except Exception:
            pass
    return False


def infer_domain(columns: list[str], dataset_name: str = "") -> str:
    combined = " ".join([c.lower() for c in columns] + [dataset_name.lower()])
    if any(k in combined for k in ("sales", "revenue", "store", "product", "retail", "price", "order", "inventory")):
        return "Commercial Sales & Retail"
    if any(k in combined for k in ("employee", "attendance", "performance", "rating", "salary", "turnover", "attrition", "department", "hr", "leave", "staff")):
        return "Workforce Health & Talent Analytics"
    if any(k in combined for k in ("shipment", "warehouse", "logistics", "freight", "carrier", "route", "transit")):
        return "Logistics & Supply Chain"
    if any(k in combined for k in ("patient", "clinical", "hospital", "diagnosis", "health", "doctor")):
        return "Clinical Operations & Healthcare"
    if any(k in combined for k in ("cost", "budget", "pnl", "margin", "ebitda", "financial", "expenditure")):
        return "Financial Planning & Analysis"
    return "Enterprise Operations"


class DatasetProfiler:
    """Profiles tabular datasets deterministically."""

    @classmethod
    def profile(cls, df: pd.DataFrame, dataset_name: str = "Dataset") -> DatasetProfile:
        row_count = len(df)
        column_count = len(df.columns)
        domain = infer_domain(list(df.columns), dataset_name)

        numeric_measures = []
        categorical_dims = []
        timeline_cols = []
        identifier_cols = []
        profiles = []
        observation_window = "Cross-sectional snapshot"

        for col in df.columns:
            series = df[col]
            clean_series = series.astype(str).str.strip()
            missing = (series.isna() | clean_series.isin(['', 'none', 'nan', 'null', 'n/a', '-'])).sum()
            null_pct = round((missing / max(1, row_count)) * 100, 1)
            distinct_count = series.dropna().nunique()
            display_name = format_display_label(str(col))

            # 1. Identifier check
            if is_id_column(str(col)):
                identifier_cols.append(str(col))
                profiles.append(ColumnProfile(
                    name=str(col),
                    display_name=display_name,
                    inferred_type="identifier",
                    null_percentage=null_pct,
                    distinct_count=distinct_count
                ))
                continue

            # 2. Datetime check
            if is_date_column(str(col), series):
                timeline_cols.append(str(col))
                try:
                    dt_series = pd.to_datetime(series.dropna(), errors='coerce').dropna()
                    if len(dt_series) > 0:
                        min_dt = dt_series.min().strftime('%Y-%m-%d')
                        max_dt = dt_series.max().strftime('%Y-%m-%d')
                        observation_window = f"{min_dt} to {max_dt}"
                except Exception:
                    pass

                profiles.append(ColumnProfile(
                    name=str(col),
                    display_name=display_name,
                    inferred_type="datetime",
                    null_percentage=null_pct,
                    distinct_count=distinct_count
                ))
                continue

            # 3. Numeric measure check
            s_stripped = clean_series.str.rstrip('%').str.replace(',', '', regex=False)
            num_series = pd.to_numeric(s_stripped, errors='coerce')
            valid_nums = num_series.dropna()

            if len(valid_nums) >= max(2, int(row_count * 0.4)):
                unit = "%" if clean_series.str.endswith('%').any() else ("$" if clean_series.str.startswith('$').any() else "")
                numeric_measures.append(str(col))
                profiles.append(ColumnProfile(
                    name=str(col),
                    display_name=display_name,
                    inferred_type="numeric_measure",
                    null_percentage=null_pct,
                    distinct_count=distinct_count,
                    unit=unit,
                    summary={
                        "min": round(float(valid_nums.min()), 2),
                        "max": round(float(valid_nums.max()), 2),
                        "mean": round(float(valid_nums.mean()), 2),
                        "median": round(float(valid_nums.median()), 2)
                    }
                ))
                continue

            # 4. Otherwise categorical dimension
            if 2 <= distinct_count <= 200:
                categorical_dims.append(str(col))
                top_cats = series.value_counts().head(5).to_dict()
                profiles.append(ColumnProfile(
                    name=str(col),
                    display_name=display_name,
                    inferred_type="categorical_dimension",
                    null_percentage=null_pct,
                    distinct_count=distinct_count,
                    summary={"top_categories": {str(k): int(v) for k, v in top_cats.items()}}
                ))
            else:
                profiles.append(ColumnProfile(
                    name=str(col),
                    display_name=display_name,
                    inferred_type="text_or_sparse",
                    null_percentage=null_pct,
                    distinct_count=distinct_count
                ))

        return DatasetProfile(
            dataset_name=dataset_name,
            business_domain=domain,
            row_count=row_count,
            column_count=column_count,
            numeric_measures=numeric_measures,
            categorical_dimensions=categorical_dims,
            timeline_columns=timeline_cols,
            identifier_columns=identifier_cols,
            profiles=profiles,
            observation_window=observation_window
        )
