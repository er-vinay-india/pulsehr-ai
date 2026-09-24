"""Generic Semantic Column & Dataset Classifier for PulseHR AI.

Inspects unknown tabular datasets and infers:
- Granular semantic roles (identifiers, measures, currency, rates, datetimes, booleans, etc.)
- Dynamic row grain (transaction, customer, daily store metric, user event, etc.)
- Statistical distributions, cardinality, and completeness
- Conservative metric polarity with explicit confidence and detection rationale
"""

import math
import re
from enum import Enum
from typing import Any
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from ..display_formatters import format_display_label


class SemanticRole(str, Enum):
    IDENTIFIER = "identifier"                       # Unique ID, transaction key, uuid, barcode
    CATEGORICAL_DIMENSION = "categorical_dimension" # Cohort, segment, category, status, type
    NUMERIC_MEASURE = "numeric_measure"             # Continuous/discrete count, duration, score
    PERCENTAGE_RATE = "percentage_rate"             # Margin %, conversion %, defect %, rate
    CURRENCY_MONETARY = "currency_monetary"         # Revenue $, cost $, budget, salary, spend
    DATETIME = "datetime"                           # Order date, timestamp, fiscal month, period
    BOOLEAN = "boolean"                             # is_active, churned, has_discount, 0/1 flag
    ORDINAL = "ordinal"                             # Rating (1-5), priority (P1/P2/P3), tier, grade
    FREE_TEXT = "free_text"                         # Unstructured notes, comments, descriptions
    GEOGRAPHIC = "geographic"                       # Country, state, city, zip code, lat/long
    POSSIBLE_TARGET = "possible_target"             # Churn flag, conversion outcome, default flag


class MetricPolarity(str, Enum):
    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class ColumnSemanticProfile(BaseModel):
    """Deep statistical and semantic profile of a single column."""
    name: str
    display_name: str
    semantic_role: SemanticRole
    data_type: str                        # "float", "int", "datetime", "string", "bool"
    
    # Statistical Cardinality & Completeness
    total_records: int
    missing_count: int
    null_percentage: float
    unique_count: int
    cardinality_ratio: float              # unique_count / max(1, total_records)
    
    # Value Distribution
    is_constant: bool = False
    is_unique_key: bool = False
    min_value: float | str | None = None
    max_value: float | str | None = None
    mean: float | None = None
    median: float | None = None
    std_dev: float | None = None
    iqr: float | None = None
    
    # Inferred Context & Polarity
    unit: str | None = None               # "$", "%", "seconds", "hours", "units"
    metric_polarity: MetricPolarity = MetricPolarity.UNKNOWN
    polarity_confidence: float = 0.0
    polarity_reason: str = "Insufficient domain evidence to infer optimization direction."
    
    top_categories: list[tuple[str, int]] = Field(default_factory=list)
    confidence: float = 1.0
    detection_reasons: list[str] = Field(default_factory=list)


class SemanticDatasetProfile(BaseModel):
    """Universal semantic profile of an arbitrary tabular dataset."""
    dataset_name: str
    row_count: int
    column_count: int
    inferred_grain: str                   # e.g. "transaction", "customer", "store_day", "unspecified_record"
    grain_confidence: float = 0.5
    grain_key_columns: list[str] = Field(default_factory=list)
    observation_window: str | None = None
    
    # Categorized column registries
    identifiers: list[str] = Field(default_factory=list)
    temporal_dimensions: list[str] = Field(default_factory=list)
    categorical_dimensions: list[str] = Field(default_factory=list)
    numeric_measures: list[str] = Field(default_factory=list)
    monetary_measures: list[str] = Field(default_factory=list)
    percentage_rates: list[str] = Field(default_factory=list)
    boolean_flags: list[str] = Field(default_factory=list)
    geographic_fields: list[str] = Field(default_factory=list)
    free_text_fields: list[str] = Field(default_factory=list)
    possible_targets: list[str] = Field(default_factory=list)

    # Detailed column-level profiles
    columns: dict[str, ColumnSemanticProfile] = Field(default_factory=dict)

    # Structural hygiene & key discovery
    primary_key_candidates: list[list[str]] = Field(default_factory=list)
    suspicious_columns: list[str] = Field(default_factory=list)


# Vocabulary registries for multi-signal heuristic evaluation
ID_HEADER_TOKENS = {"id", "uuid", "guid", "key", "code", "barcode", "sku", "number", "num", "hash", "sno", "srno"}
GEO_HEADER_TOKENS = {"country", "state", "city", "zip", "postal", "region", "province", "latitude", "longitude", "lat", "lon", "geo", "loc", "location"}
CURRENCY_SYMBOLS = {"$", "€", "£", "¥", "₹"}
CURRENCY_HEADER_TOKENS = {"price", "cost", "revenue", "profit", "salary", "wage", "budget", "spend", "amount", "fee", "usd", "eur", "gbp", "cad", "billing", "income", "margin_usd", "sales"}
RATE_HEADER_TOKENS = {"rate", "pct", "percent", "percentage", "ratio", "share", "margin", "yield", "discount", "proportion"}
DATE_HEADER_TOKENS = {"date", "time", "timestamp", "created_at", "updated_at", "period", "month", "year", "quarter", "week", "day"}
BOOL_HEADER_TOKENS = {"is_", "has_", "flag", "active", "churned", "status_flag", "defaulted", "returned", "passed"}
TEXT_HEADER_TOKENS = {"note", "comment", "feedback", "review", "description", "summary", "text", "body", "message"}
TARGET_HEADER_TOKENS = {"churn", "churned", "converted", "conversion", "default", "fraud", "retained", "retention", "success", "passed_qa", "target"}

# Explicit Polarity Lexicons
HIGH_POLARITY_KEYWORDS = {"revenue", "profit", "net_income", "margin", "completion", "retention", "uptime", "yield", "satisfaction", "enps", "conversion", "accuracy", "achievement"}
LOW_POLARITY_KEYWORDS = {"defect", "scrap", "churn", "attrition", "turnover", "loss", "cost", "expense", "latency", "downtime", "incident", "error", "delay", "absenteeism", "bounce"}


class SemanticClassifier:
    """Classifies columns and dataset structures across arbitrary tabular domains."""

    @classmethod
    def _is_date(cls, series: pd.Series, col_clean: str) -> tuple[bool, float, list[str]]:
        reasons = []
        conf = 0.0
        c_lower = col_clean.lower()

        has_date_token = any(re.search(rf'\b{t}\b', c_lower) or c_lower.endswith(f"_{t}") or c_lower.startswith(f"{t}_") for t in DATE_HEADER_TOKENS)
        if has_date_token:
            conf += 0.45
            reasons.append(f"Header contains temporal keyword '{col_clean}'")

        # Sample conversion
        sample = series.dropna().astype(str).head(30)
        if len(sample) >= 3:
            # Check if pure numbers (e.g. 2024 or 12345)
            if sample.str.replace(r'^[+-]?\d+$', '', regex=True).eq('').all():
                numeric_vals = pd.to_numeric(sample, errors='coerce').dropna()
                # 4-digit years like 1990..2035
                if len(numeric_vals) >= 3 and (numeric_vals.between(1980, 2035)).all():
                    conf += 0.5
                    reasons.append("Values are 4-digit calendar years (1980-2035)")
                    return True, min(1.0, conf), reasons
                return False, 0.0, []

            try:
                # Test date parse
                parsed = pd.to_datetime(sample, errors='coerce')
                valid_ratio = parsed.notna().sum() / len(sample)
                if valid_ratio >= 0.75:
                    conf += 0.55
                    reasons.append(f"{int(valid_ratio*100)}% of sampled values successfully parse as valid datetimes")
            except Exception:
                pass

        is_dt = conf >= 0.65
        return is_dt, min(1.0, conf), reasons

    @classmethod
    def classify_column(cls, series: pd.Series, col_name: str, total_records: int) -> ColumnSemanticProfile:
        clean_col = str(col_name).strip()
        c_lower = clean_col.lower()
        col_tokens = set(re.findall(r'[a-zA-Z0-9]+', c_lower))
        display_name = format_display_label(clean_col)

        # Missing & Cardinality
        non_null_series = series.dropna()
        str_series = series.astype(str).str.strip()
        null_markers = {'', 'none', 'nan', 'null', 'n/a', '-', 'na', 'nil', '#n/a'}
        missing_count = int(series.isna().sum() + str_series.str.casefold().isin(null_markers).sum())
        null_pct = round((missing_count / max(1, total_records)) * 100, 1)

        valid_vals = non_null_series[~str_series.str.casefold().isin(null_markers)]
        unique_count = int(valid_vals.nunique())
        cardinality_ratio = round(unique_count / max(1, len(valid_vals)), 4) if len(valid_vals) > 0 else 0.0

        is_constant = unique_count <= 1 and len(valid_vals) > 0
        is_unique_key = unique_count == total_records and total_records >= 2

        # 1. Check Datetime
        is_dt, dt_conf, dt_reasons = cls._is_date(valid_vals, clean_col)
        if is_dt:
            min_val_str = None
            max_val_str = None
            try:
                dt_parsed = pd.to_datetime(valid_vals, errors='coerce').dropna()
                if len(dt_parsed) > 0:
                    min_val_str = dt_parsed.min().strftime('%Y-%m-%d')
                    max_val_str = dt_parsed.max().strftime('%Y-%m-%d')
            except Exception:
                pass

            return ColumnSemanticProfile(
                name=clean_col,
                display_name=display_name,
                semantic_role=SemanticRole.DATETIME,
                data_type="datetime",
                total_records=total_records,
                missing_count=missing_count,
                null_percentage=null_pct,
                unique_count=unique_count,
                cardinality_ratio=cardinality_ratio,
                is_constant=is_constant,
                is_unique_key=is_unique_key,
                min_value=min_val_str,
                max_value=max_val_str,
                unit="date",
                metric_polarity=MetricPolarity.NEUTRAL,
                polarity_confidence=1.0,
                polarity_reason="Temporal dimension; optimization polarity is not applicable.",
                confidence=round(dt_conf, 2),
                detection_reasons=dt_reasons
            )

        # 2. Check Boolean
        sample_head = valid_vals.astype(str).str.lower().str.strip()
        bool_vocab = {'0', '1', 'true', 'false', 'yes', 'no', 't', 'f', 'y', 'n'}
        is_bool_values = unique_count <= 2 and len(valid_vals) > 0 and sample_head.isin(bool_vocab).all()
        has_bool_token = any(t in BOOL_HEADER_TOKENS for t in col_tokens) or any(clean_col.lower().startswith(b) for b in ('is_', 'has_', 'flag_'))

        if is_bool_values:
            reasons = ["Values strictly restricted to binary boolean tokens (true/false, 0/1, yes/no)"]
            conf = 0.90 if has_bool_token else 0.80
            role = SemanticRole.POSSIBLE_TARGET if any(t in TARGET_HEADER_TOKENS for t in col_tokens) else SemanticRole.BOOLEAN
            if role == SemanticRole.POSSIBLE_TARGET:
                reasons.append(f"Header '{clean_col}' matches known binary outcome/target pattern")

            return ColumnSemanticProfile(
                name=clean_col,
                display_name=display_name,
                semantic_role=role,
                data_type="bool",
                total_records=total_records,
                missing_count=missing_count,
                null_percentage=null_pct,
                unique_count=unique_count,
                cardinality_ratio=cardinality_ratio,
                is_constant=is_constant,
                is_unique_key=is_unique_key,
                unit="flag",
                metric_polarity=MetricPolarity.NEUTRAL,
                polarity_confidence=0.7,
                polarity_reason="Boolean indicator; polarity depends on specific outcome definition.",
                confidence=conf,
                detection_reasons=reasons
            )

        # 3. Numeric Parseability
        stripped = valid_vals.astype(str).str.strip().str.replace(',', '', regex=False)
        has_currency_sym = stripped.str.contains(r'[\$€£¥₹]').any()
        has_pct_sym = stripped.str.endswith('%').any()

        clean_numeric_str = stripped.str.replace(r'[\$€£¥₹%]', '', regex=True)
        numeric_series = pd.to_numeric(clean_numeric_str, errors='coerce')
        valid_nums = numeric_series.dropna()
        numeric_ratio = len(valid_nums) / max(1, len(valid_vals))
        is_numeric = numeric_ratio >= 0.75 and len(valid_nums) >= 2

        # 4. Check Identifier (Primary Key / UUID / Index)
        has_id_token = (
            any(t in ID_HEADER_TOKENS for t in col_tokens)
            or clean_col.lower().endswith("id")
            or clean_col.lower().endswith("_id")
            or clean_col.lower().endswith("key")
            or clean_col.lower().endswith("code")
        )

        if is_unique_key and (has_id_token or not is_numeric):
            conf = 0.95 if has_id_token else 0.70
            reasons = [f"100% distinct values ({unique_count}/{total_records}) forming a valid unique entity key"]
            if has_id_token:
                reasons.append(f"Header contains identifier token '{clean_col}'")
            else:
                reasons.append("Unique values without explicit identifier header; classified as key candidate")

            return ColumnSemanticProfile(
                name=clean_col,
                display_name=display_name,
                semantic_role=SemanticRole.IDENTIFIER,
                data_type="int" if is_numeric else "string",
                total_records=total_records,
                missing_count=missing_count,
                null_percentage=null_pct,
                unique_count=unique_count,
                cardinality_ratio=cardinality_ratio,
                is_constant=False,
                is_unique_key=True,
                metric_polarity=MetricPolarity.NEUTRAL,
                polarity_confidence=1.0,
                polarity_reason="Primary identifier key; no directional polarity.",
                confidence=conf,
                detection_reasons=reasons
            )

        if has_id_token and cardinality_ratio > 0.4 and not has_currency_sym and not has_pct_sym:
            return ColumnSemanticProfile(
                name=clean_col,
                display_name=display_name,
                semantic_role=SemanticRole.IDENTIFIER,
                data_type="int" if is_numeric else "string",
                total_records=total_records,
                missing_count=missing_count,
                null_percentage=null_pct,
                unique_count=unique_count,
                cardinality_ratio=cardinality_ratio,
                is_constant=is_constant,
                is_unique_key=is_unique_key,
                metric_polarity=MetricPolarity.NEUTRAL,
                polarity_confidence=1.0,
                polarity_reason="High-cardinality identity code.",
                confidence=0.85,
                detection_reasons=[f"Header contains ID token and high cardinality ratio ({cardinality_ratio*100:.1f}%)"]
            )

        # 5. Check Numeric Measure Subtypes (Monetary, Percentage, Continuous Measure, Ordinal)
        if is_numeric:
            min_v = float(valid_nums.min())
            max_v = float(valid_nums.max())
            mean_v = float(valid_nums.mean())
            median_v = float(valid_nums.median())
            std_v = float(valid_nums.std()) if len(valid_nums) > 1 else 0.0
            q75, q25 = np.percentile(valid_nums, [75, 25]) if len(valid_nums) >= 4 else (max_v, min_v)
            iqr_v = float(q75 - q25)

            # 5a. Currency / Monetary
            has_curr_token = any(t in CURRENCY_HEADER_TOKENS for t in col_tokens)
            if has_currency_sym or has_curr_token:
                reasons = []
                conf = 0.5
                unit = "$"
                if has_currency_sym:
                    conf += 0.4
                    reasons.append("Values formatted with explicit monetary currency symbol")
                if has_curr_token:
                    conf += 0.35
                    reasons.append(f"Header matches monetary nomenclature '{clean_col}'")

                # Polarity check for financial metric
                pol, pol_conf, pol_reason = cls._infer_polarity(clean_col, col_tokens, SemanticRole.CURRENCY_MONETARY)

                return ColumnSemanticProfile(
                    name=clean_col,
                    display_name=display_name,
                    semantic_role=SemanticRole.CURRENCY_MONETARY,
                    data_type="float",
                    total_records=total_records,
                    missing_count=missing_count,
                    null_percentage=null_pct,
                    unique_count=unique_count,
                    cardinality_ratio=cardinality_ratio,
                    is_constant=is_constant,
                    is_unique_key=is_unique_key,
                    min_value=round(min_v, 2),
                    max_value=round(max_v, 2),
                    mean=round(mean_v, 2),
                    median=round(median_v, 2),
                    std_dev=round(std_v, 2),
                    iqr=round(iqr_v, 2),
                    unit=unit,
                    metric_polarity=pol,
                    polarity_confidence=pol_conf,
                    polarity_reason=pol_reason,
                    confidence=min(1.0, round(conf, 2)),
                    detection_reasons=reasons
                )

            # 5b. Percentage / Rate
            has_rate_token = any(t in RATE_HEADER_TOKENS for t in col_tokens)
            is_bounded_pct = (0.0 <= min_v <= 100.0) and (max_v <= 100.0)
            is_ratio_01 = (0.0 <= min_v <= 1.0) and (max_v <= 1.0) and (median_v <= 1.0) and unique_count > 3

            if has_pct_sym or (has_rate_token and (is_bounded_pct or is_ratio_01)):
                reasons = []
                conf = 0.5
                if has_pct_sym:
                    conf += 0.45
                    reasons.append("Values formatted with explicit '%' symbol")
                if has_rate_token:
                    conf += 0.35
                    reasons.append(f"Header matches rate/ratio nomenclature '{clean_col}'")
                if is_bounded_pct:
                    reasons.append(f"Values strictly bounded in 0-100 range [{min_v:.1f}, {max_v:.1f}]")

                pol, pol_conf, pol_reason = cls._infer_polarity(clean_col, col_tokens, SemanticRole.PERCENTAGE_RATE)

                return ColumnSemanticProfile(
                    name=clean_col,
                    display_name=display_name,
                    semantic_role=SemanticRole.PERCENTAGE_RATE,
                    data_type="float",
                    total_records=total_records,
                    missing_count=missing_count,
                    null_percentage=null_pct,
                    unique_count=unique_count,
                    cardinality_ratio=cardinality_ratio,
                    is_constant=is_constant,
                    is_unique_key=is_unique_key,
                    min_value=round(min_v, 2),
                    max_value=round(max_v, 2),
                    mean=round(mean_v, 2),
                    median=round(median_v, 2),
                    std_dev=round(std_v, 2),
                    iqr=round(iqr_v, 2),
                    unit="%",
                    metric_polarity=pol,
                    polarity_confidence=pol_conf,
                    polarity_reason=pol_reason,
                    confidence=min(1.0, round(conf, 2)),
                    detection_reasons=reasons
                )

            # 5c. Ordinal / Small Score
            is_small_integer_scale = (
                (valid_nums.astype(int) == valid_nums).all()
                and 0 <= min_v <= 2
                and 3 <= max_v <= 10
                and unique_count <= 10
                and any(t in {"rating", "score", "level", "grade", "rank", "tier", "priority"} for t in col_tokens)
            )
            if is_small_integer_scale:
                return ColumnSemanticProfile(
                    name=clean_col,
                    display_name=display_name,
                    semantic_role=SemanticRole.ORDINAL,
                    data_type="int",
                    total_records=total_records,
                    missing_count=missing_count,
                    null_percentage=null_pct,
                    unique_count=unique_count,
                    cardinality_ratio=cardinality_ratio,
                    is_constant=is_constant,
                    is_unique_key=is_unique_key,
                    min_value=int(min_v),
                    max_value=int(max_v),
                    mean=round(mean_v, 2),
                    median=round(median_v, 2),
                    unit="scale",
                    metric_polarity=MetricPolarity.UNKNOWN,
                    polarity_confidence=0.4,
                    polarity_reason="Ordinal rank/score; polarity depends on scale orientation.",
                    confidence=0.85,
                    detection_reasons=[f"Integer values bounded to scale {int(min_v)}-{int(max_v)} with ordinal header '{clean_col}'"]
                )

            # 5d. General Numeric Measure
            pol, pol_conf, pol_reason = cls._infer_polarity(clean_col, col_tokens, SemanticRole.NUMERIC_MEASURE)
            unit_guess = cls._infer_unit_from_header(clean_col, col_tokens)

            return ColumnSemanticProfile(
                name=clean_col,
                display_name=display_name,
                semantic_role=SemanticRole.NUMERIC_MEASURE,
                data_type="float" if not (valid_nums.astype(int) == valid_nums).all() else "int",
                total_records=total_records,
                missing_count=missing_count,
                null_percentage=null_pct,
                unique_count=unique_count,
                cardinality_ratio=cardinality_ratio,
                is_constant=is_constant,
                is_unique_key=is_unique_key,
                min_value=round(min_v, 2),
                max_value=round(max_v, 2),
                mean=round(mean_v, 2),
                median=round(median_v, 2),
                std_dev=round(std_v, 2),
                iqr=round(iqr_v, 2),
                unit=unit_guess,
                metric_polarity=pol,
                polarity_confidence=pol_conf,
                polarity_reason=pol_reason,
                confidence=0.90 if not clean_col.startswith("col_") else 0.60,
                detection_reasons=["Continuous numeric distribution parseable across records"]
            )

        # 6. Check Geographic Field
        has_geo_token = any(t in GEO_HEADER_TOKENS for t in col_tokens)
        if has_geo_token and unique_count <= 500:
            top_cats = valid_vals.value_counts().head(5).items()
            return ColumnSemanticProfile(
                name=clean_col,
                display_name=display_name,
                semantic_role=SemanticRole.GEOGRAPHIC,
                data_type="string",
                total_records=total_records,
                missing_count=missing_count,
                null_percentage=null_pct,
                unique_count=unique_count,
                cardinality_ratio=cardinality_ratio,
                is_constant=is_constant,
                is_unique_key=is_unique_key,
                top_categories=[(str(k), int(v)) for k, v in top_cats],
                metric_polarity=MetricPolarity.NEUTRAL,
                polarity_confidence=1.0,
                polarity_reason="Geographic territory / location dimension.",
                confidence=0.88,
                detection_reasons=[f"Header matches geographic entity keyword '{clean_col}'"]
            )

        # 7. Check Free Text vs Categorical Dimension
        avg_str_len = float(valid_vals.astype(str).str.len().mean()) if len(valid_vals) > 0 else 0.0
        has_text_token = any(t in TEXT_HEADER_TOKENS for t in col_tokens)

        if (avg_str_len > 35 and cardinality_ratio > 0.4) or has_text_token:
            return ColumnSemanticProfile(
                name=clean_col,
                display_name=display_name,
                semantic_role=SemanticRole.FREE_TEXT,
                data_type="string",
                total_records=total_records,
                missing_count=missing_count,
                null_percentage=null_pct,
                unique_count=unique_count,
                cardinality_ratio=cardinality_ratio,
                is_constant=is_constant,
                is_unique_key=is_unique_key,
                metric_polarity=MetricPolarity.NEUTRAL,
                polarity_confidence=1.0,
                polarity_reason="Unstructured free text narrative.",
                confidence=0.85,
                detection_reasons=[f"Long average string length ({avg_str_len:.1f} chars) and high dispersion"]
            )

        # 8. Categorical Dimension (Default fallback for discrete strings)
        top_cats = valid_vals.value_counts().head(5).items()
        conf = 0.90 if 2 <= unique_count <= 60 else (0.75 if unique_count <= 250 else 0.45)
        reasons = [f"Discrete cohort grouping with {unique_count} distinct categories"]
        if clean_col.startswith("col_"):
            conf = 0.40
            reasons.append("Ambiguous non-descriptive header column")

        return ColumnSemanticProfile(
            name=clean_col,
            display_name=display_name,
            semantic_role=SemanticRole.CATEGORICAL_DIMENSION,
            data_type="string",
            total_records=total_records,
            missing_count=missing_count,
            null_percentage=null_pct,
            unique_count=unique_count,
            cardinality_ratio=cardinality_ratio,
            is_constant=is_constant,
            is_unique_key=is_unique_key,
            top_categories=[(str(k), int(v)) for k, v in top_cats],
            metric_polarity=MetricPolarity.NEUTRAL,
            polarity_confidence=1.0,
            polarity_reason="Categorical cohort; directional polarity is not applicable.",
            confidence=conf,
            detection_reasons=reasons
        )

    @classmethod
    def _infer_unit_from_header(cls, col_name: str, tokens: set[str]) -> str | None:
        c_lower = col_name.lower()
        if any(t in {"sec", "second", "seconds"} for t in tokens) or "_sec" in c_lower:
            return "seconds"
        if any(t in {"min", "minute", "minutes"} for t in tokens) or "_min" in c_lower:
            return "minutes"
        if any(t in {"hr", "hour", "hours"} for t in tokens) or "_hr" in c_lower or "_hours" in c_lower:
            return "hours"
        if any(t in {"day", "days"} for t in tokens):
            return "days"
        if any(t in {"unit", "units", "items", "qty", "quantity", "count"} for t in tokens):
            return "units"
        if any(t in {"score", "points"} for t in tokens):
            return "points"
        return None

    @classmethod
    def _infer_polarity(cls, col_name: str, tokens: set[str], role: SemanticRole) -> tuple[MetricPolarity, float, str]:
        """Conservatively assigns polarity only when strong, unequivocal domain signals exist."""
        # 1. High polarity keywords
        high_matches = tokens.intersection(HIGH_POLARITY_KEYWORDS)
        if high_matches:
            matched = list(high_matches)[0]
            return (
                MetricPolarity.HIGHER_IS_BETTER,
                0.85,
                f"Metric name explicitly contains high-performance terminology '{matched}'"
            )

        # 2. Low polarity keywords
        low_matches = tokens.intersection(LOW_POLARITY_KEYWORDS)
        if low_matches:
            matched = list(low_matches)[0]
            return (
                MetricPolarity.LOWER_IS_BETTER,
                0.85,
                f"Metric name explicitly contains friction/defect/cost terminology '{matched}'"
            )

        # 3. Currency - check if cost vs revenue
        if role == SemanticRole.CURRENCY_MONETARY:
            if any(t in {"cost", "expense", "spend", "fee", "penalty"} for t in tokens):
                return MetricPolarity.LOWER_IS_BETTER, 0.80, "Monetary measure represents financial expenditure/cost."
            if any(t in {"revenue", "profit", "sales", "income", "margin"} for t in tokens):
                return MetricPolarity.HIGHER_IS_BETTER, 0.80, "Monetary measure represents financial intake/revenue."

        # Default: UNKNOWN with explicit conservative reasoning
        return (
            MetricPolarity.UNKNOWN,
            0.30,
            f"Insufficient domain evidence for '{col_name}'; polarity depends on business objectives."
        )

    @classmethod
    def infer_grain(
        cls,
        df: pd.DataFrame,
        columns: dict[str, ColumnSemanticProfile]
    ) -> tuple[str, float, list[str]]:
        """Dynamically identifies dataset row grain without assuming an employee entity."""
        total_rows = len(df)
        if total_rows == 0:
            return "empty_dataset", 1.0, []

        # 1. Check for single-column primary key
        for name, prof in columns.items():
            if prof.is_unique_key:
                c_low = name.lower()
                if "order" in c_low or "transaction" in c_low or "invoice" in c_low:
                    return "transaction / order record", 0.95, [name]
                if "customer" in c_low or "client" in c_low or "user" in c_low or "account" in c_low:
                    return "customer / user entity", 0.95, [name]
                if "employee" in c_low or "staff" in c_low or "worker" in c_low:
                    return "employee profile", 0.95, [name]
                if "batch" in c_low or "lot" in c_low:
                    return "manufacturing batch", 0.95, [name]
                if "session" in c_low:
                    return "web session", 0.95, [name]
                if "store" in c_low:
                    return "store entity", 0.90, [name]
                if "item" in c_low or "product" in c_low or "sku" in c_low:
                    return "product / catalog item", 0.90, [name]
                if "id" in c_low or "key" in c_low or "code" in c_low:
                    return f"unique entity ({name})", 0.85, [name]

        # 2. Check 2-column composite primary keys (e.g. Entity + Date or Order + Item)
        id_cols = [n for n, p in columns.items() if p.semantic_role == SemanticRole.IDENTIFIER or p.cardinality_ratio > 0.1]
        dt_cols = [n for n, p in columns.items() if p.semantic_role == SemanticRole.DATETIME]

        for id_c in id_cols[:3]:
            for dt_c in dt_cols[:2]:
                pair_unique = df[[id_c, dt_c]].dropna().drop_duplicates().shape[0]
                if pair_unique == total_rows:
                    return f"time-series record ({id_c} × {dt_c})", 0.90, [id_c, dt_c]

        # 3. Check Order + Line Item or Parent + Child ID
        if len(id_cols) >= 2:
            for i in range(min(4, len(id_cols))):
                for j in range(i + 1, min(4, len(id_cols))):
                    c1, c2 = id_cols[i], id_cols[j]
                    pair_unique = df[[c1, c2]].dropna().drop_duplicates().shape[0]
                    if pair_unique == total_rows:
                        return f"composite line item ({c1} + {c2})", 0.85, [c1, c2]

        # 4. Ambiguous fallback
        return "unspecified row record", 0.35, []

    @classmethod
    def profile_dataset(cls, df: pd.DataFrame, dataset_name: str = "Dataset") -> SemanticDatasetProfile:
        """Constructs an exhaustive SemanticDatasetProfile from an arbitrary pandas DataFrame."""
        total_rows = len(df)
        total_cols = len(df.columns)

        col_profiles: dict[str, ColumnSemanticProfile] = {}
        identifiers = []
        temporals = []
        categoricals = []
        numerics = []
        currencies = []
        percentages = []
        booleans = []
        geos = []
        texts = []
        targets = []
        suspicious = []
        primary_keys = []

        observation_window = None

        for col in df.columns:
            prof = cls.classify_column(df[col], str(col), total_rows)
            col_profiles[str(col)] = prof

            if prof.is_constant:
                suspicious.append(f"Column '{col}' is 100% constant ({prof.unique_count} distinct value).")
            if prof.null_percentage > 85.0:
                suspicious.append(f"Column '{col}' is {prof.null_percentage}% empty.")

            if prof.is_unique_key:
                primary_keys.append([str(col)])

            role = prof.semantic_role
            if role == SemanticRole.IDENTIFIER:
                identifiers.append(str(col))
            elif role == SemanticRole.DATETIME:
                temporals.append(str(col))
                if prof.min_value and prof.max_value:
                    observation_window = f"{prof.min_value} to {prof.max_value}"
            elif role == SemanticRole.CATEGORICAL_DIMENSION:
                categoricals.append(str(col))
            elif role == SemanticRole.NUMERIC_MEASURE:
                numerics.append(str(col))
            elif role == SemanticRole.CURRENCY_MONETARY:
                currencies.append(str(col))
                numerics.append(str(col))  # Also counts as numeric measure
            elif role == SemanticRole.PERCENTAGE_RATE:
                percentages.append(str(col))
                numerics.append(str(col))  # Also counts as numeric measure
            elif role == SemanticRole.BOOLEAN:
                booleans.append(str(col))
            elif role == SemanticRole.GEOGRAPHIC:
                geos.append(str(col))
                categoricals.append(str(col))
            elif role == SemanticRole.FREE_TEXT:
                texts.append(str(col))
            elif role == SemanticRole.POSSIBLE_TARGET:
                targets.append(str(col))
                booleans.append(str(col))

        grain, grain_conf, grain_keys = cls.infer_grain(df, col_profiles)
        if grain_keys and grain_keys not in primary_keys:
            primary_keys.append(grain_keys)

        return SemanticDatasetProfile(
            dataset_name=dataset_name,
            row_count=total_rows,
            column_count=total_cols,
            inferred_grain=grain,
            grain_confidence=round(grain_conf, 2),
            grain_key_columns=grain_keys,
            observation_window=observation_window,
            identifiers=identifiers,
            temporal_dimensions=temporals,
            categorical_dimensions=categoricals,
            numeric_measures=numerics,
            monetary_measures=currencies,
            percentage_rates=percentages,
            boolean_flags=booleans,
            geographic_fields=geos,
            free_text_fields=texts,
            possible_targets=targets,
            columns=col_profiles,
            primary_key_candidates=primary_keys,
            suspicious_columns=suspicious
        )
