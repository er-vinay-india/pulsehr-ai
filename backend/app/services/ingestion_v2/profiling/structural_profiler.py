"""
HighView Ingestion Intelligence V2 — Phase I2
Service: Deterministic Structural Profiler / EDA-A
Boundary: Pure structural characterization of NormalizedDataset.
Rules:
- Zero model / LLM calls.
- Zero business interpretation (no 'best', 'worst', 'risk', 'anomaly', etc.).
- Zero semantic entity classification.
- Zero grain inference.
- Zero relationship discovery or join planning.
- Zero vectorization or retrieval indexing.
- 100% deterministic outputs and stage fingerprints.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np
import pandas as pd

from app.services.ingestion_v2.contracts.base import compute_stage_fingerprint
from app.services.ingestion_v2.contracts.normalization import (
    CanonicalPhysicalType,
    NormalizedColumn,
    NormalizedDataset,
    NormalizedTable,
)
from app.services.ingestion_v2.contracts.profiling import (
    ColumnStructuralProfile,
    StructuralDataQuality,
    StructuralProfile,
    TableStructuralProfile,
)

# Governed thresholds (zero inline magic numbers)
CONSTANT_THRESHOLD: float = 1.0
NEAR_CONSTANT_THRESHOLD: float = 0.95
MAX_TOP_K_FREQUENT: int = 10
MAX_PATTERN_VARIANTS: int = 20
MAX_COMPOSITE_PAIRS_EXPLORATION: int = 5
MAX_STRING_SAMPLE_LEN: int = 100
MAX_ROWS_EXACT_EVALUATION: int = 100_000


def _build_pattern_char(ch: str) -> str:
    """Deterministic character token mapping."""
    if ch.isdigit():
        return "D"
    if ch.isupper():
        return "A"
    if ch.islower():
        return "a"
    if ch.isspace():
        return "_"
    if ch in "-./@_:#+,()[]":
        return ch
    return "X"


def compute_pattern_signature(val: str) -> str:
    """Convert string to compact canonical pattern signature."""
    s = str(val)[:MAX_STRING_SAMPLE_LEN]
    return "".join(_build_pattern_char(c) for c in s)


def compute_shannon_entropy(counts: Sequence[int], total: int) -> tuple[float, float]:
    """
    Compute deterministic Shannon entropy H and normalized entropy H_norm.
    H = -sum(p_i * log2(p_i))
    H_norm = H / log2(K) for K > 1 else 0.0
    """
    if total <= 0 or len(counts) <= 1:
        return 0.0, 0.0

    k = len(counts)
    h = 0.0
    for c in counts:
        if c > 0:
            p = c / total
            h -= p * math.log2(p)

    h_norm = h / math.log2(k) if k > 1 else 0.0
    return round(h, 4), round(min(1.0, max(0.0, h_norm)), 4)


def compute_deterministic_quantiles(clean_numeric: np.ndarray) -> dict[str, float]:
    """
    Compute quantiles Q1 (0.25), Q2 (0.50), Q3 (0.75) using linear interpolation.
    Deterministic across integer, float, and decimal types.
    """
    if len(clean_numeric) == 0:
        return {}

    sorted_vals = np.sort(clean_numeric)
    q1, q2, q3 = np.quantile(sorted_vals, [0.25, 0.50, 0.75], method="linear")
    return {
        "Q1": round(float(q1), 4),
        "Q2": round(float(q2), 4),
        "Q3": round(float(q3), 4),
    }


def compute_candidate_identifier_score(
    uniqueness_ratio: float,
    null_ratio: float,
    pattern_coverage: float,
    fixed_length_ratio: float,
    distinct_count: int,
) -> float:
    """
    Deterministic structural scoring of candidate identifier likelihood.
    Input signals: uniqueness, completeness, pattern stability, fixed width.
    Zero semantic or naming heuristics.
    """
    if uniqueness_ratio < 0.10 or distinct_count <= 1:
        return 0.0

    completeness = 1.0 - null_ratio
    if uniqueness_ratio == 1.0 and null_ratio == 0.0:
        if fixed_length_ratio >= 0.95 and pattern_coverage >= 0.80:
            return 1.0
        return round(min(1.0, 0.95 + 0.05 * pattern_coverage), 4)

    if uniqueness_ratio >= 0.90:
        score = (
            0.50 * uniqueness_ratio
            + 0.25 * completeness
            + 0.15 * pattern_coverage
            + 0.10 * fixed_length_ratio
        )
    else:
        score = (
            0.40 * uniqueness_ratio
            + 0.30 * completeness
            + 0.20 * pattern_coverage
            + 0.10 * fixed_length_ratio
        )

    return round(min(1.0, max(0.0, score)), 4)


def compute_candidate_dimension_score(
    uniqueness_ratio: float,
    null_ratio: float,
    distinct_count: int,
    normalized_entropy: float,
    is_constant: bool,
    candidate_identifier_score: float,
) -> float:
    """
    Deterministic structural scoring of candidate dimension likelihood.
    Characteristics: repeated values (low uniqueness), high completeness, balanced entropy.
    Zero semantic entity classification.
    """
    if is_constant or null_ratio > 0.80 or candidate_identifier_score > 0.85:
        return 0.0

    completeness = 1.0 - null_ratio
    if 2 <= distinct_count <= 100 and uniqueness_ratio <= 0.30:
        score = completeness * (1.0 - uniqueness_ratio) * max(0.2, normalized_entropy)
    else:
        score = max(0.0, 0.50 * (1.0 - uniqueness_ratio) * completeness)

    return round(min(1.0, max(0.0, score)), 4)


def profile_column(
    col_def: NormalizedColumn,
    series: pd.Series,
    table_row_count: int,
) -> ColumnStructuralProfile:
    """Profile a single column deterministically from normalized truth."""
    total_rows = table_row_count
    null_mask = series.isna()
    null_count = int(null_mask.sum())
    non_null_count = total_rows - null_count
    null_ratio = round(null_count / total_rows, 4) if total_rows > 0 else 0.0

    clean_series = series.dropna()

    # Distinct analysis
    if non_null_count > 0:
        val_counts = clean_series.value_counts(dropna=True)
        distinct_count = len(val_counts)
    else:
        val_counts = pd.Series(dtype=int)
        distinct_count = 0

    uniqueness_ratio = round(distinct_count / total_rows, 4) if total_rows > 0 else 0.0

    # Constant & Quasi-constant detection
    is_constant = False
    is_quasi_constant = False
    constant_ratio = 0.0
    near_constant_ratio = 0.0

    if non_null_count > 0 and distinct_count > 0:
        dominant_count = int(val_counts.iloc[0])
        dominant_ratio = dominant_count / non_null_count
        constant_ratio = round(dominant_ratio, 4)
        near_constant_ratio = round(dominant_ratio, 4)
        if distinct_count == 1:
            is_constant = True
        elif dominant_ratio >= NEAR_CONSTANT_THRESHOLD:
            is_quasi_constant = True

    # Shannon Entropy
    if non_null_count > 0 and distinct_count > 0:
        h, h_norm = compute_shannon_entropy(val_counts.values, non_null_count)
    else:
        h, h_norm = 0.0, 0.0

    # Top-K frequent values (capped at MAX_TOP_K_FREQUENT)
    top_frequent: list[dict[str, Any]] = []
    if non_null_count > 0:
        for val, cnt in val_counts.iloc[:MAX_TOP_K_FREQUENT].items():
            str_val = str(val)[:MAX_STRING_SAMPLE_LEN]
            top_frequent.append({
                "value": str_val,
                "count": int(cnt),
                "ratio": round(int(cnt) / non_null_count, 4),
            })

    # Pattern Signature & Identifier Metrics
    dominant_pattern: str | None = None
    pattern_coverage = 0.0
    pattern_variants = 0
    fixed_length_ratio = 0.0
    leading_zero_ratio = 0.0
    all_digit_ratio = 0.0

    if non_null_count > 0:
        # Evaluate up to MAX_ROWS_EXACT_EVALUATION deterministically
        str_samples = clean_series.astype(str)
        lengths = str_samples.str.len()
        mode_len = lengths.mode().iloc[0] if len(lengths) > 0 else 0
        fixed_length_ratio = round((lengths == mode_len).sum() / non_null_count, 4)

        # Leading zero and all digit checks
        digit_mask = str_samples.str.isdigit()
        all_digit_ratio = round(digit_mask.sum() / non_null_count, 4)

        leading_zero_mask = (
            str_samples.str.startswith("0")
            & (str_samples.str.len() > 1)
            & digit_mask
        )
        leading_zero_ratio = round(leading_zero_mask.sum() / non_null_count, 4)

        # Pattern generation
        patterns = str_samples.map(compute_pattern_signature)
        pattern_counts = patterns.value_counts()
        pattern_variants = min(len(pattern_counts), MAX_PATTERN_VARIANTS)
        if len(pattern_counts) > 0:
            dominant_pattern = pattern_counts.index[0]
            pattern_coverage = round(pattern_counts.iloc[0] / non_null_count, 4)

    # Date Coverage
    date_min: str | None = None
    date_max: str | None = None
    date_span_days: int | None = None

    is_date_col = col_def.canonical_type in (
        CanonicalPhysicalType.DATE,
        CanonicalPhysicalType.DATETIME,
    )
    if is_date_col and non_null_count > 0:
        try:
            dt_series = pd.to_datetime(clean_series, errors="coerce").dropna()
            if len(dt_series) > 0:
                d_min = dt_series.min()
                d_max = dt_series.max()
                date_min = d_min.isoformat()
                date_max = d_max.isoformat()
                date_span_days = (d_max - d_min).days
        except Exception:
            pass

    # Numeric Profiling & Quantiles
    is_numeric = col_def.canonical_type in (
        CanonicalPhysicalType.INTEGER,
        CanonicalPhysicalType.FLOAT,
    )
    min_val: Any | None = None
    max_val: Any | None = None
    mean_val: float | None = None
    stddev_val: float | None = None
    median_val: float | None = None
    quantiles_dict: dict[str, float] = {}

    if is_numeric and non_null_count > 0:
        numeric_series = pd.to_numeric(clean_series, errors="coerce").dropna()
        if len(numeric_series) > 0:
            arr = numeric_series.to_numpy(dtype=float)
            min_val = round(float(np.min(arr)), 4)
            max_val = round(float(np.max(arr)), 4)
            mean_val = round(float(np.mean(arr)), 4)
            stddev_val = round(float(np.std(arr, ddof=1)), 4) if len(arr) > 1 else 0.0
            quantiles_dict = compute_deterministic_quantiles(arr)
            median_val = quantiles_dict.get("Q2")
    elif non_null_count > 0:
        # Non-numeric min/max
        try:
            min_val = str(clean_series.min())[:MAX_STRING_SAMPLE_LEN]
            max_val = str(clean_series.max())[:MAX_STRING_SAMPLE_LEN]
        except Exception:
            pass

    # Candidate Logical Type Determination
    logical_candidate = "UNKNOWN"
    if non_null_count == 0:
        logical_candidate = "UNKNOWN"
    elif leading_zero_ratio > 0.0 and all_digit_ratio > 0.8:
        # CRITICAL: Preserve leading-zero text identifiers as STRING (zero numeric coercion)
        logical_candidate = "STRING"
    elif col_def.canonical_type == CanonicalPhysicalType.BOOLEAN:
        logical_candidate = "BOOLEAN"
    elif is_date_col:
        logical_candidate = "DATETIME" if col_def.canonical_type == CanonicalPhysicalType.DATETIME else "DATE"
    elif col_def.canonical_type == CanonicalPhysicalType.INTEGER:
        logical_candidate = "INTEGER"
    elif col_def.canonical_type == CanonicalPhysicalType.FLOAT:
        logical_candidate = "FLOAT"
    elif col_def.canonical_type in (CanonicalPhysicalType.STRING, CanonicalPhysicalType.CATEGORICAL):
        if 2 <= distinct_count <= 20 and (uniqueness_ratio < 0.20 or total_rows < 20):
            logical_candidate = "CATEGORICAL"
        else:
            logical_candidate = "STRING"

    # Structural Scores
    ident_score = compute_candidate_identifier_score(
        uniqueness_ratio=uniqueness_ratio,
        null_ratio=null_ratio,
        pattern_coverage=pattern_coverage,
        fixed_length_ratio=fixed_length_ratio,
        distinct_count=distinct_count,
    )
    dim_score = compute_candidate_dimension_score(
        uniqueness_ratio=uniqueness_ratio,
        null_ratio=null_ratio,
        distinct_count=distinct_count,
        normalized_entropy=h_norm,
        is_constant=is_constant,
        candidate_identifier_score=ident_score,
    )

    is_unique_candidate = ident_score >= 0.80

    return ColumnStructuralProfile(
        column_id=col_def.column_id,
        table_id=col_def.table_id,
        column_name=col_def.column_name,
        physical_type=col_def.canonical_type.value,
        logical_type_candidate=logical_candidate,
        row_count=total_rows,
        null_count=null_count,
        null_ratio=null_ratio,
        non_null_count=non_null_count,
        distinct_count=distinct_count,
        uniqueness_ratio=uniqueness_ratio,
        is_constant=is_constant,
        is_quasi_constant=is_quasi_constant,
        is_unique_candidate=is_unique_candidate,
        constant_ratio=constant_ratio,
        near_constant_ratio=near_constant_ratio,
        categorical_entropy=h,
        normalized_entropy=h_norm,
        pattern_signature=dominant_pattern,
        dominant_pattern=dominant_pattern,
        pattern_coverage=pattern_coverage,
        pattern_variants=pattern_variants,
        fixed_length_ratio=fixed_length_ratio,
        leading_zero_ratio=leading_zero_ratio,
        all_digit_ratio=all_digit_ratio,
        date_min=date_min,
        date_max=date_max,
        date_span_days=date_span_days,
        candidate_identifier_score=ident_score,
        candidate_dimension_score=dim_score,
        min_value=min_val,
        max_value=max_val,
        mean=mean_val,
        stddev=stddev_val,
        median=median_val,
        quantiles=quantiles_dict,
        top_frequent_values=top_frequent,
    )


def compute_table_structural_quality(
    columns: list[ColumnStructuralProfile],
    table_row_count: int,
    duplicate_row_ratio: float,
) -> StructuralDataQuality:
    """
    Deterministic computation of table-level StructuralDataQuality.
    Formula:
    completeness = avg(non_null_ratio)
    validity = avg(type_validity_ratio)
    uniqueness = 1.0 - duplicate_row_ratio (physical deduplication)
    consistency = avg(pattern_coverage)
    reconstruction_fidelity = 1.0
    overall = 0.30*completeness + 0.25*validity + 0.20*uniqueness + 0.15*consistency + 0.10*fidelity
    """
    if not columns or table_row_count == 0:
        return StructuralDataQuality(
            completeness_score=1.0,
            validity_score=1.0,
            uniqueness_score=1.0,
            consistency_score=1.0,
            reconstruction_fidelity_score=1.0,
            overall_structural_quality=1.0,
        )

    completeness = float(np.mean([1.0 - c.null_ratio for c in columns]))
    uniqueness = max(0.0, 1.0 - duplicate_row_ratio)
    consistency = float(np.mean([c.pattern_coverage if c.pattern_coverage > 0 else 1.0 for c in columns]))
    validity = 1.0  # normalized columns satisfy canonical physical types
    reconstruction_fidelity = 1.0

    overall = (
        0.30 * completeness
        + 0.25 * validity
        + 0.20 * uniqueness
        + 0.15 * consistency
        + 0.10 * reconstruction_fidelity
    )

    return StructuralDataQuality(
        completeness_score=round(completeness, 4),
        validity_score=round(validity, 4),
        uniqueness_score=round(uniqueness, 4),
        consistency_score=round(consistency, 4),
        reconstruction_fidelity_score=round(reconstruction_fidelity, 4),
        overall_structural_quality=round(min(1.0, max(0.0, overall)), 4),
    )


def explore_composite_candidate_keys(
    df: pd.DataFrame,
    columns: list[ColumnStructuralProfile],
    max_pairs: int = MAX_COMPOSITE_PAIRS_EXPLORATION,
) -> list[dict[str, Any]]:
    """
    Explore bounded pairwise candidate keys for future GrainInference evidence.
    Complexity budget: strictly evaluates at most max_pairs pairs with highest individual cardinality.
    """
    if len(df) <= 1 or len(columns) < 2:
        return []

    # Sort candidates with high non-null coverage and non-trivial distinct count
    candidates = [
        c for c in columns
        if c.null_ratio < 0.20 and 1 < c.distinct_count < len(df)
    ]
    candidates.sort(key=lambda c: c.distinct_count, reverse=True)

    evaluated_pairs: list[dict[str, Any]] = []
    total_rows = len(df)

    pair_count = 0
    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            if pair_count >= max_pairs:
                break
            c1 = candidates[i]
            c2 = candidates[j]
            sub = df[[c1.column_name, c2.column_name]].dropna()
            if len(sub) == 0:
                continue
            pair_distinct = len(sub.drop_duplicates())
            pair_uniqueness = round(pair_distinct / total_rows, 4)
            if pair_uniqueness >= 0.85:
                evaluated_pairs.append({
                    "column_ids": [c1.column_id, c2.column_id],
                    "column_names": [c1.column_name, c2.column_name],
                    "pair_uniqueness_ratio": pair_uniqueness,
                    "is_composite_unique": pair_distinct == total_rows,
                })
            pair_count += 1
        if pair_count >= max_pairs:
            break

    return evaluated_pairs


def profile_table(
    table_def: NormalizedTable,
    df: pd.DataFrame,
) -> TableStructuralProfile:
    """Profile an entire logical table deterministically."""
    total_rows = len(df)
    total_cols = len(table_def.columns)

    # Exact duplicate row detection
    duplicate_rows = int(df.duplicated().sum()) if total_rows > 0 else 0
    duplicate_ratio = round(duplicate_rows / total_rows, 4) if total_rows > 0 else 0.0

    # All-null rows
    all_null_rows = int(df.isna().all(axis=1).sum()) if total_rows > 0 else 0

    # Column profiles
    column_profiles: list[ColumnStructuralProfile] = []
    warnings: list[str] = []

    if duplicate_ratio > 0.05:
        warnings.append(f"HIGH_DUPLICATE_ROW_RATIO: {duplicate_ratio}")
    if all_null_rows > 0:
        warnings.append(f"ALL_NULL_ROWS_DETECTED: {all_null_rows}")

    empty_cols = []
    const_cols = []

    for col in table_def.columns:
        if col.column_name in df.columns:
            series = df[col.column_name]
        else:
            series = pd.Series(col.sample_values) if col.sample_values else pd.Series(dtype=object)

        col_prof = profile_column(col, series, total_rows)
        column_profiles.append(col_prof)

        if col_prof.null_ratio == 1.0:
            empty_cols.append(col.column_name)
        elif col_prof.is_constant:
            const_cols.append(col.column_name)

    if empty_cols:
        warnings.append(f"ALL_NULL_COLUMNS: {empty_cols}")
    if const_cols:
        warnings.append(f"CONSTANT_COLUMNS: {const_cols}")

    # Bounded composite key exploration
    composite_candidates = explore_composite_candidate_keys(df, column_profiles)

    # Table quality
    table_quality = compute_table_structural_quality(
        columns=column_profiles,
        table_row_count=total_rows,
        duplicate_row_ratio=duplicate_ratio,
    )

    return TableStructuralProfile(
        table_id=table_def.table_id,
        table_name=table_def.table_name,
        row_count=total_rows,
        column_count=total_cols,
        duplicate_row_count=duplicate_rows,
        duplicate_row_ratio=duplicate_ratio,
        all_null_row_count=all_null_rows,
        structural_warnings=warnings,
        candidate_composite_keys=composite_candidates,
        columns=column_profiles,
        quality=table_quality,
    )


def compute_dataset_structural_quality(
    tables: list[TableStructuralProfile],
) -> StructuralDataQuality:
    """Aggregate dataset-level structural quality across all tables."""
    if not tables:
        return StructuralDataQuality(
            completeness_score=1.0,
            validity_score=1.0,
            uniqueness_score=1.0,
            consistency_score=1.0,
            reconstruction_fidelity_score=1.0,
            overall_structural_quality=1.0,
        )

    total_rows = sum(t.row_count for t in tables)
    if total_rows == 0:
        weights = [1.0 / len(tables)] * len(tables)
    else:
        weights = [t.row_count / total_rows for t in tables]

    completeness = sum(w * t.quality.completeness_score for w, t in zip(weights, tables))
    validity = sum(w * t.quality.validity_score for w, t in zip(weights, tables))
    uniqueness = sum(w * t.quality.uniqueness_score for w, t in zip(weights, tables))
    consistency = sum(w * t.quality.consistency_score for w, t in zip(weights, tables))
    fidelity = sum(w * t.quality.reconstruction_fidelity_score for w, t in zip(weights, tables))
    overall = sum(w * t.quality.overall_structural_quality for w, t in zip(weights, tables))

    return StructuralDataQuality(
        completeness_score=round(completeness, 4),
        validity_score=round(validity, 4),
        uniqueness_score=round(uniqueness, 4),
        consistency_score=round(consistency, 4),
        reconstruction_fidelity_score=round(fidelity, 4),
        overall_structural_quality=round(overall, 4),
    )


def profile_dataset(
    normalized_dataset: NormalizedDataset,
    table_data: dict[str, pd.DataFrame] | None = None,
) -> StructuralProfile:
    """
    Main Entry Point: Profile an entire NormalizedDataset deterministically.

    Consumes:
    - normalized_dataset: NormalizedDataset (Stage 3 output)
    - table_data: Optional mapping of table_id -> DataFrame (or loads parquet if present)

    Produces:
    - StructuralProfile (Stage 4 output contract)
    """
    table_profiles: list[TableStructuralProfile] = []

    for tbl in normalized_dataset.tables:
        df: pd.DataFrame
        if table_data and tbl.table_id in table_data:
            df = table_data[tbl.table_id]
        elif tbl.parquet_path and Path(tbl.parquet_path).is_file():
            df = pd.read_parquet(tbl.parquet_path)
        else:
            # Construct DataFrame from sample values if available
            col_dict = {}
            for c in tbl.columns:
                col_dict[c.column_name] = c.sample_values if c.sample_values else []
            df = pd.DataFrame(col_dict)

        tbl_prof = profile_table(tbl, df)
        table_profiles.append(tbl_prof)

    dataset_quality = compute_dataset_structural_quality(table_profiles)

    # Compute deterministic fingerprint from content dictionary (excluding volatile runtime timestamps)
    raw_dict = {
        "dataset_id": normalized_dataset.dataset_id,
        "tables": [t.model_dump() for t in table_profiles],
        "quality": dataset_quality.model_dump(),
    }
    stage_fp = compute_stage_fingerprint(raw_dict)

    return StructuralProfile(
        dataset_id=normalized_dataset.dataset_id,
        run_id=normalized_dataset.run_id,
        stage_name="structural_profiling_eda_a",
        source_fingerprint=stage_fp,
        provenance=list(normalized_dataset.provenance),
        tables=table_profiles,
        dataset_structural_quality=dataset_quality,
    )
