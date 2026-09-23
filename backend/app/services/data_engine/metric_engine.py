"""Deterministic mathematical and statistical computation engine.
All quantitative business metrics are calculated here; language models never do math."""

import math
from typing import Any
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field


class MetricSummary(BaseModel):
    """Deterministic summary of a continuous numerical metric."""
    metric: str
    count: int
    mean: float
    median: float
    std_dev: float
    min_value: float
    max_value: float
    iqr: float
    unit: str = ""


class SegmentMetric(BaseModel):
    """Comparative metric for a specific categorical segment."""
    segment_dimension: str
    segment_value: str
    count: int
    mean: float
    median: float
    diff_from_baseline: float
    percentage_gap: float
    is_outperformer: bool
    is_underperformer: bool
    rank: int


class PeriodTrend(BaseModel):
    """Chronological metric trend observation."""
    period: str
    metric: str
    value: float
    diff_from_previous: float | None = None
    percentage_change: float | None = None


class CandidateFact(BaseModel):
    """Deterministic candidate observation surfaced for the Analyst model."""
    fact_id: str
    fact_type: str  # "segment_gap", "outlier", "trend", "overall_baseline", "concentration"
    metric: str
    segment: str | None = None
    observed_value: float
    baseline_value: float | None = None
    difference: float | None = None
    percentage_gap: float | None = None
    sample_size: int
    significance_score: float = 0.0  # Normalized 0.0 - 1.0 based on variance/dispersion
    raw_proof: dict[str, Any] = Field(default_factory=dict)


class MetricEngine:
    """Pure deterministic statistical computation engine."""

    @staticmethod
    def _coerce_series(series: pd.Series) -> pd.Series:
        cleaned = series.astype(str).str.strip().str.rstrip('%').str.replace(',', '', regex=False)
        return pd.to_numeric(cleaned, errors='coerce').dropna()

    @classmethod
    def calculate_global_summary(cls, df: pd.DataFrame, metric_col: str, unit: str = "") -> MetricSummary | None:
        if metric_col not in df.columns:
            return None
        nums = cls._coerce_series(df[metric_col])
        if len(nums) == 0:
            return None

        mean_val = float(nums.mean())
        median_val = float(nums.median())
        std_val = float(nums.std()) if len(nums) > 1 else 0.0
        q75, q25 = np.percentile(nums, [75, 25]) if len(nums) >= 4 else (nums.max(), nums.min())
        iqr_val = float(q75 - q25)

        return MetricSummary(
            metric=metric_col,
            count=len(nums),
            mean=round(mean_val, 2),
            median=round(median_val, 2),
            std_dev=round(std_val, 2),
            min_value=round(float(nums.min()), 2),
            max_value=round(float(nums.max()), 2),
            iqr=round(iqr_val, 2),
            unit=unit
        )

    @classmethod
    def calculate_segment_comparison(
        cls,
        df: pd.DataFrame,
        metric_col: str,
        segment_col: str,
        min_segment_records: int = 2
    ) -> list[SegmentMetric]:
        if metric_col not in df.columns or segment_col not in df.columns:
            return []

        work_df = df[[segment_col, metric_col]].copy()
        work_df["_clean_metric"] = pd.to_numeric(
            work_df[metric_col].astype(str).str.strip().str.rstrip('%').str.replace(',', '', regex=False),
            errors='coerce'
        )
        work_df = work_df.dropna(subset=["_clean_metric", segment_col])
        if len(work_df) == 0:
            return []

        baseline_mean = float(work_df["_clean_metric"].mean())
        baseline_std = float(work_df["_clean_metric"].std()) if len(work_df) > 1 else 1.0

        grouped = work_df.groupby(segment_col)["_clean_metric"].agg(["count", "mean", "median"]).reset_index()
        grouped = grouped[grouped["count"] >= min_segment_records]
        if len(grouped) == 0:
            return []

        # Sort descending by mean
        grouped = grouped.sort_values(by="mean", ascending=False).reset_index(drop=True)

        results: list[SegmentMetric] = []
        for rank, row in enumerate(grouped.itertuples(), start=1):
            seg_mean = float(row.mean)
            diff = round(seg_mean - baseline_mean, 2)
            pct_gap = round((diff / abs(baseline_mean) * 100), 1) if baseline_mean != 0 else 0.0

            is_outperformer = diff > (baseline_std * 0.75)
            is_underperformer = diff < -(baseline_std * 0.75)

            results.append(SegmentMetric(
                segment_dimension=segment_col,
                segment_value=str(getattr(row, segment_col)),
                count=int(row.count),
                mean=round(seg_mean, 2),
                median=round(float(row.median), 2),
                diff_from_baseline=diff,
                percentage_gap=pct_gap,
                is_outperformer=is_outperformer,
                is_underperformer=is_underperformer,
                rank=rank
            ))

        return results

    @classmethod
    def calculate_period_trends(
        cls,
        df: pd.DataFrame,
        metric_col: str,
        date_col: str,
        freq: str = 'M'
    ) -> list[PeriodTrend]:
        if metric_col not in df.columns or date_col not in df.columns:
            return []

        work_df = df[[date_col, metric_col]].copy()
        work_df["_dt"] = pd.to_datetime(work_df[date_col], errors='coerce')
        work_df["_val"] = pd.to_numeric(
            work_df[metric_col].astype(str).str.strip().str.rstrip('%').str.replace(',', '', regex=False),
            errors='coerce'
        )
        work_df = work_df.dropna(subset=["_dt", "_val"])
        if len(work_df) < 2:
            return []

        work_df["_period"] = work_df["_dt"].dt.to_period(freq).astype(str)
        agg = work_df.groupby("_period")["_val"].mean().reset_index()
        agg = agg.sort_values(by="_period").reset_index(drop=True)

        trends: list[PeriodTrend] = []
        prev_val = None
        for row in agg.itertuples():
            val = round(float(row._val), 2)
            diff = round(val - prev_val, 2) if prev_val is not None else None
            pct_chg = round((diff / abs(prev_val) * 100), 1) if prev_val is not None and prev_val != 0 else None

            trends.append(PeriodTrend(
                period=str(row._period),
                metric=metric_col,
                value=val,
                diff_from_previous=diff,
                percentage_change=pct_chg
            ))
            prev_val = val

        return trends

    @classmethod
    def discover_candidate_facts(cls, df: pd.DataFrame, max_candidates: int = 15) -> list[CandidateFact]:
        """Exhaustively surfaces mathematical candidates across all numeric metrics and dimensions."""
        candidates: list[CandidateFact] = []
        fact_idx = 1

        # 1. Profile numeric and categorical columns
        numeric_cols = []
        categorical_cols = []
        for c in df.columns:
            nums = cls._coerce_series(df[c])
            if len(nums) >= max(2, int(len(df) * 0.4)):
                numeric_cols.append(c)
            elif 2 <= df[c].dropna().nunique() <= 30:
                categorical_cols.append(c)

        # 2. Global metric baselines
        for m_col in numeric_cols[:4]:
            summary = cls.calculate_global_summary(df, m_col)
            if summary:
                candidates.append(CandidateFact(
                    fact_id=f"FACT-{fact_idx:03d}",
                    fact_type="overall_baseline",
                    metric=m_col,
                    observed_value=summary.mean,
                    baseline_value=summary.median,
                    difference=round(summary.mean - summary.median, 2),
                    sample_size=summary.count,
                    significance_score=0.9,
                    raw_proof=summary.model_dump()
                ))
                fact_idx += 1

        # 3. Segment variance across primary dimensions
        for m_col in numeric_cols[:3]:
            for d_col in categorical_cols[:2]:
                segments = cls.calculate_segment_comparison(df, m_col, d_col)
                if not segments:
                    continue

                # Top segment (Outperformer)
                top = segments[0]
                candidates.append(CandidateFact(
                    fact_id=f"FACT-{fact_idx:03d}",
                    fact_type="segment_gap",
                    metric=m_col,
                    segment=f"{d_col}:{top.segment_value}",
                    observed_value=top.mean,
                    baseline_value=round(top.mean - top.diff_from_baseline, 2),
                    difference=top.diff_from_baseline,
                    percentage_gap=top.percentage_gap,
                    sample_size=top.count,
                    significance_score=min(1.0, abs(top.percentage_gap) / 50.0),
                    raw_proof=top.model_dump()
                ))
                fact_idx += 1

                # Bottom segment (Headwind/Underperformer)
                if len(segments) > 1:
                    bottom = segments[-1]
                    candidates.append(CandidateFact(
                        fact_id=f"FACT-{fact_idx:03d}",
                        fact_type="segment_gap",
                        metric=m_col,
                        segment=f"{d_col}:{bottom.segment_value}",
                        observed_value=bottom.mean,
                        baseline_value=round(bottom.mean - bottom.diff_from_baseline, 2),
                        difference=bottom.diff_from_baseline,
                        percentage_gap=bottom.percentage_gap,
                        sample_size=bottom.count,
                        significance_score=min(1.0, abs(bottom.percentage_gap) / 50.0),
                        raw_proof=bottom.model_dump()
                    ))
                    fact_idx += 1

        # Sort candidate facts by significance score descending
        candidates.sort(key=lambda f: f.significance_score, reverse=True)
        return candidates[:max_candidates]
