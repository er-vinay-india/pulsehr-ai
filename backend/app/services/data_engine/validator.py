"""Deterministic dataset validation and data quality audit engine."""

import logging
from typing import Any
import pandas as pd
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ColumnQualityMetric(BaseModel):
    """Quality metrics for a single column."""
    column: str
    total_records: int
    missing_count: int
    null_percentage: float
    distinct_count: int
    inferred_type: str
    is_valid: bool = True
    issues: list[str] = Field(default_factory=list)


class DataQualityReport(BaseModel):
    """Structured report returned by DatasetValidator."""
    is_valid: bool
    quality_score: int = Field(ge=0, le=100)
    total_records: int
    total_columns: int
    clean_column_count: int
    columns: list[ColumnQualityMetric] = Field(default_factory=list)
    critical_errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class DatasetValidator:
    """Deterministic validator verifying dataset integrity prior to analytical processing."""

    @classmethod
    def validate(cls, df: pd.DataFrame, dataset_name: str = "Uploaded Dataset") -> DataQualityReport:
        critical_errors: list[str] = []
        warnings: list[str] = []
        recommendations: list[str] = []
        column_metrics: list[ColumnQualityMetric] = []

        total_records = len(df)
        total_cols = len(df.columns)

        # 1. Critical Empty Checks
        if total_records == 0:
            critical_errors.append("Dataset contains 0 rows of data.")
            return DataQualityReport(
                is_valid=False,
                quality_score=0,
                total_records=0,
                total_columns=total_cols,
                clean_column_count=0,
                critical_errors=critical_errors,
                recommendations=["Upload a spreadsheet containing at least 2 populated rows."]
            )

        if total_cols == 0:
            critical_errors.append("Dataset has no detectable column headers.")
            return DataQualityReport(
                is_valid=False,
                quality_score=0,
                total_records=total_records,
                total_columns=0,
                clean_column_count=0,
                critical_errors=critical_errors,
                recommendations=["Ensure CSV or Excel workbook has a valid header row."]
            )

        # 2. Check for duplicate column headers
        if df.columns.duplicated().any():
            dups = df.columns[df.columns.duplicated()].tolist()
            critical_errors.append(f"Duplicate column headers detected: {dups}")
            return DataQualityReport(
                is_valid=False,
                quality_score=0,
                total_records=total_records,
                total_columns=total_cols,
                clean_column_count=0,
                critical_errors=critical_errors,
                recommendations=["Rename columns to ensure every column header is unique."]
            )

        # 3. Analyze each column
        clean_cols = 0
        null_pct_sum = 0.0

        for col in df.columns:
            series = df[col]
            missing_count = series.isna().sum() + (series.astype(str).str.strip().isin(['', 'none', 'nan', 'null', 'n/a', '-'])).sum()
            null_pct = round((missing_count / total_records) * 100, 1)
            null_pct_sum += null_pct

            distinct_count = series.dropna().nunique()
            col_issues = []

            # Inferred type
            numeric_series = pd.to_numeric(series.astype(str).str.rstrip('%'), errors='coerce')
            non_na_nums = numeric_series.dropna()
            is_numeric = len(non_na_nums) > (total_records * 0.4)

            inferred_type = "numeric" if is_numeric else "categorical"

            # Check percentage bounds
            if is_numeric and '%' in str(series.dropna().iloc[0] if len(series.dropna()) else ''):
                inferred_type = "percentage"
                if (non_na_nums > 100.0).any() or (non_na_nums < 0.0).any():
                    col_issues.append("Values outside standard 0-100 percentage range.")
                    warnings.append(f"Column '{col}' has percentages outside standard 0-100% boundary.")

            if null_pct > 80.0:
                col_issues.append(f"Severe sparsity ({null_pct}% null).")
                warnings.append(f"Column '{col}' is {null_pct}% empty.")
            else:
                clean_cols += 1

            column_metrics.append(ColumnQualityMetric(
                column=str(col),
                total_records=total_records,
                missing_count=int(missing_count),
                null_percentage=null_pct,
                distinct_count=distinct_count,
                inferred_type=inferred_type,
                is_valid=len(col_issues) == 0,
                issues=col_issues
            ))

        # 4. Compute overall quality score
        avg_null_pct = null_pct_sum / max(1, total_cols)
        quality_score = max(0, min(100, round(100 - avg_null_pct - (len(critical_errors) * 30))))

        if quality_score < 40:
            warnings.append("Dataset quality is low due to pervasive missing fields.")
            recommendations.append("Audit source ETL pipeline to backfill empty data rows.")

        if total_records < 10:
            warnings.append("Sample size is very small (< 10 records). Statistical significance will be limited.")

        is_valid = len(critical_errors) == 0

        return DataQualityReport(
            is_valid=is_valid,
            quality_score=quality_score,
            total_records=total_records,
            total_columns=total_cols,
            clean_column_count=clean_cols,
            columns=column_metrics,
            critical_errors=critical_errors,
            warnings=warnings,
            recommendations=recommendations
        )
