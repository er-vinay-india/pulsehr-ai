"""Deterministic Dataset Profiler, Hygiene Auditor, and Sensitive Field Scanner.

Provides:
- Column-level statistical profiling (types, nulls, unique count, ranges)
- Sensitive column detection (PII, salary, health, national identifiers)
- Representative data sampling (top categories, edge values, null examples)
- Data quality scoring and health audit (DataQualityProfile)
"""

from __future__ import annotations

import math
import re
from typing import Any
import pandas as pd

from .models import (
    ColumnProfile,
    DataQualityIssue,
    DataQualityProfile,
    DatasetProfile,
    IssueSeverity,
    SemanticColumnRole,
    SemanticUnit,
)


class DataProfiler:
    """Performs fast deterministic profiling on tabular data frames or record lists."""

    # Regex patterns for sensitive data detection
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
    PHONE_PATTERN = re.compile(r'^\+?1?\d{9,15}$')
    SSN_PATTERN = re.compile(r'^\d{3}-?\d{2}-?\d{4}$')

    SENSITIVE_COLUMN_KEYWORDS = {
        "email": "Email address",
        "phone": "Phone number",
        "mobile": "Mobile number",
        "ssn": "Social Security Number",
        "national_id": "National Identity Number",
        "passport": "Passport Number",
        "salary": "Compensation / Salary Information",
        "wage": "Wage Information",
        "compensation": "Compensation Information",
        "bonus": "Bonus Compensation",
        "medical": "Medical or Health Record",
        "health": "Health or Diagnosis Record",
        "diagnosis": "Medical Diagnosis",
        "disability": "Disability Information",
        "bank_account": "Banking / Financial Identifier",
        "credit_card": "Credit Card Number",
        "password": "Security Credential",
    }

    @classmethod
    def profile_dataframe(
        cls,
        df: pd.DataFrame,
        dataset_id: str = "dataset_01",
        dataset_name: str = "Data"
    ) -> tuple[DatasetProfile, DataQualityProfile]:
        """Profiles a pandas DataFrame deterministically and generates a DataQualityProfile."""
        total_rows = len(df)
        total_cols = len(df.columns)

        duplicate_rows = int(df.duplicated().sum()) if total_rows > 0 else 0
        duplicate_rate = round(duplicate_rows / max(1, total_rows), 4)

        column_profiles: list[ColumnProfile] = []
        quality_issues: list[DataQualityIssue] = []

        primary_keys: list[str] = []
        metric_candidates: list[str] = []
        dimension_candidates: list[str] = []
        time_candidates: list[str] = []
        sensitive_columns: list[str] = []
        numeric_ranges: dict[str, dict[str, Any]] = {}
        categorical_cardinality: dict[str, int] = {}
        date_range: dict[str, Any] | None = None

        if total_rows < 10:
            quality_issues.append(
                DataQualityIssue(
                    issue_type="LOW_SAMPLE_SIZE",
                    severity=IssueSeverity.WARNING,
                    message=f"Dataset has only {total_rows} records. Statistical variance and generalizations may be unreliable.",
                    count_affected=total_rows
                )
            )

        if duplicate_rows > 0:
            quality_issues.append(
                DataQualityIssue(
                    issue_type="DUPLICATE_ROWS",
                    severity=IssueSeverity.WARNING if duplicate_rate > 0.05 else IssueSeverity.INFO,
                    message=f"Found {duplicate_rows} duplicate rows ({round(duplicate_rate * 100, 2)}% of dataset).",
                    count_affected=duplicate_rows
                )
            )

        for col_name in df.columns:
            series = df[col_name]
            clean_series = series.dropna()
            null_count = int(series.isna().sum())
            null_pct = round(null_count / max(1, total_rows), 4)
            unique_count = int(clean_series.nunique())

            # Data quality checks on missingness
            if null_pct > 0.40:
                quality_issues.append(
                    DataQualityIssue(
                        issue_type="HIGH_MISSINGNESS",
                        severity=IssueSeverity.WARNING if null_pct > 0.60 else IssueSeverity.INFO,
                        column_name=str(col_name),
                        message=f"Column '{col_name}' has {round(null_pct * 100, 1)}% missing values.",
                        count_affected=null_count
                    )
                )

            # Determine basic data type
            is_numeric = pd.api.types.is_numeric_dtype(series)
            is_datetime = pd.api.types.is_datetime64_any_dtype(series)
            is_bool = pd.api.types.is_bool_dtype(series)

            # Date heuristic if stored as object/string
            if not is_datetime and not is_numeric and unique_count > 0:
                is_datetime = cls._check_date_like(clean_series)

            dtype_str = "datetime" if is_datetime else ("numeric" if is_numeric else ("boolean" if is_bool else "string"))

            # Sensitive column scanning
            is_sensitive, sens_reason = cls._check_sensitivity(col_name, clean_series)
            if is_sensitive:
                sensitive_columns.append(str(col_name))
                quality_issues.append(
                    DataQualityIssue(
                        issue_type="SENSITIVE_FIELD",
                        severity=IssueSeverity.INFO,
                        column_name=str(col_name),
                        message=f"Detected potentially sensitive field: {sens_reason}.",
                        count_affected=total_rows
                    )
                )

            # Sample values (safe representative sampling)
            sample_vals = cls._extract_sample_values(clean_series, is_sensitive)

            # Ranges & metrics
            min_val = None
            max_val = None
            mean_val = None

            if is_numeric and len(clean_series) > 0:
                try:
                    num_series = pd.to_numeric(clean_series, errors='coerce').dropna()
                    if not num_series.empty:
                        min_val = float(num_series.min())
                        max_val = float(num_series.max())
                        mean_val = round(float(num_series.mean()), 2)
                        numeric_ranges[str(col_name)] = {"min": min_val, "max": max_val, "mean": mean_val}
                except Exception:
                    pass

            if is_datetime and len(clean_series) > 0:
                try:
                    dt_series = pd.to_datetime(clean_series, errors='coerce').dropna()
                    if not dt_series.empty:
                        min_dt = str(dt_series.min().date())
                        max_dt = str(dt_series.max().date())
                        min_val = min_dt
                        max_val = max_dt
                        if date_range is None:
                            date_range = {"min_date": min_dt, "max_date": max_dt}
                except Exception:
                    pass

            # Classification candidates
            is_id = (unique_count == total_rows and total_rows > 1) or ("id" in str(col_name).lower() and unique_count > total_rows * 0.8)
            is_metric = is_numeric and not is_id and unique_count > 2
            is_dim = not is_numeric and not is_id and not is_datetime and unique_count > 1
            is_time = is_datetime or any(k in str(col_name).lower() for k in ("date", "month", "year", "quarter", "week", "day", "time"))

            if is_id:
                primary_keys.append(str(col_name))
            if is_metric:
                metric_candidates.append(str(col_name))
            if is_dim:
                dimension_candidates.append(str(col_name))
                categorical_cardinality[str(col_name)] = unique_count
            if is_time:
                time_candidates.append(str(col_name))

            col_prof = ColumnProfile(
                name=str(col_name),
                original_name=str(col_name),
                data_type=dtype_str,
                null_count=null_count,
                null_pct=null_pct,
                unique_count=unique_count,
                sample_values=sample_vals,
                min_val=min_val,
                max_val=max_val,
                mean_val=mean_val,
                cardinality=unique_count,
                is_identifier_candidate=is_id,
                is_metric_candidate=is_metric,
                is_dimension_candidate=is_dim,
                is_time_candidate=is_time,
                is_sensitive=is_sensitive,
                sensitivity_reason=sens_reason,
                confidence=1.0
            )
            column_profiles.append(col_prof)

        # Representative sampling (5 bounded rows)
        rep_samples = cls._extract_representative_dataframe_samples(df, sensitive_columns, limit=5)

        # Health score calculation
        total_cells = max(1, total_rows * total_cols)
        total_nulls = sum(c.null_count for c in column_profiles)
        missingness_rate = round(total_nulls / total_cells, 4)
        health_penalty = (missingness_rate * 0.3) + (duplicate_rate * 0.3) + (0.2 if total_rows < 10 else 0.0)
        overall_health = max(0.2, round(1.0 - health_penalty, 2))

        quality_prof = DataQualityProfile(
            dataset_id=dataset_id,
            total_records=total_rows,
            overall_health_score=overall_health,
            missingness_rate=missingness_rate,
            duplicate_rate=duplicate_rate,
            issues=quality_issues
        )

        dataset_prof = DatasetProfile(
            dataset_id=dataset_id,
            name=dataset_name,
            original_name=dataset_name,
            row_count=total_rows,
            col_count=total_cols,
            columns=column_profiles,
            duplicate_row_count=duplicate_rows,
            duplicate_rate=duplicate_rate,
            date_range=date_range,
            numeric_ranges=numeric_ranges,
            categorical_cardinality=categorical_cardinality,
            primary_keys=primary_keys,
            metric_candidates=metric_candidates,
            dimension_candidates=dimension_candidates,
            time_candidates=time_candidates,
            sensitive_columns=sensitive_columns,
            representative_samples=rep_samples
        )

        return dataset_prof, quality_prof

    @classmethod
    def _check_date_like(cls, series: pd.Series) -> bool:
        """Heuristically checks if string values can be reliably parsed as dates."""
        sample = series.head(10).astype(str)
        try:
            parsed = pd.to_datetime(sample, errors='coerce')
            return parsed.notna().sum() >= max(1, len(sample) * 0.8)
        except Exception:
            return False

    @classmethod
    def _check_sensitivity(cls, col_name: Any, clean_series: pd.Series) -> tuple[bool, str | None]:
        """Detects if a column is sensitive based on name keywords and sample content."""
        lower_name = str(col_name).lower().replace(" ", "_").replace("-", "_")

        for kw, reason in cls.SENSITIVE_COLUMN_KEYWORDS.items():
            if kw in lower_name:
                return True, reason

        if len(clean_series) > 0:
            sample_str = clean_series.head(5).astype(str).tolist()
            if any(cls.EMAIL_PATTERN.match(val) for val in sample_str):
                return True, "Personal email address"
            if any(cls.PHONE_PATTERN.match(val) for val in sample_str):
                return True, "Telephone number"
            if any(cls.SSN_PATTERN.match(val) for val in sample_str):
                return True, "National identification number"

        return False, None

    @classmethod
    def _extract_sample_values(cls, clean_series: pd.Series, is_sensitive: bool) -> list[Any]:
        """Extracts representative sample values while masking sensitive fields."""
        if len(clean_series) == 0:
            return []

        if is_sensitive:
            return ["[REDACTED_SENSITIVE_DATA]"]

        # Take top value, bottom value, and up to 3 frequent values
        uniques = clean_series.drop_duplicates()
        samples = uniques.head(4).tolist()
        # Convert any timestamps / non-JSON serializables to string
        clean_samples = []
        for s in samples:
            if isinstance(s, (pd.Timestamp, pd.Timedelta)):
                clean_samples.append(str(s))
            elif isinstance(s, float) and math.isnan(s):
                continue
            else:
                clean_samples.append(s)
        return clean_samples

    @classmethod
    def _extract_representative_dataframe_samples(
        cls,
        df: pd.DataFrame,
        sensitive_cols: list[str],
        limit: int = 5
    ) -> list[dict[str, Any]]:
        """Extracts bounded representative rows with masked sensitive columns for prompt injection."""
        if df.empty:
            return []

        sample_df = df.head(limit).copy()
        for col in sensitive_cols:
            if col in sample_df.columns:
                sample_df[col] = "[REDACTED]"

        # Fill NaNs with None for clean JSON serialization
        records = sample_df.to_dict(orient='records')
        clean_records = []
        for r in records:
            clean_r = {}
            for k, v in r.items():
                if isinstance(v, float) and math.isnan(v):
                    clean_r[k] = None
                elif isinstance(v, (pd.Timestamp, pd.Timedelta)):
                    clean_r[k] = str(v)
                else:
                    clean_r[k] = v
            clean_records.append(clean_r)
        return clean_records
