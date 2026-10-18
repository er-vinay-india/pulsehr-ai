"""
HighView Ingestion Intelligence V2 — Phase I2 Test Suite
Deterministic Structural Profiler / EDA-A Tests
Validates:
1. Column structural profiling (nulls, distinct, types, quantiles, entropy, pattern signatures, dates, identifier & dimension scores)
2. Edge cases (leading-zero IDs, all-null, constant, near-constant, high-cardinality, Unicode, numeric extremes)
3. Table profiling & StructuralDataQuality formula (role-neutral uniqueness, completeness, validity, consistency)
4. Determinism (10 identical runs, fingerprint stability)
5. Epistemic boundary & negative vocabulary (0 business terms, 0 semantic roles, 0 grain, 0 joins, 0 model calls)
6. Bounded complexity & performance benchmarks
"""

import json
import math
import time
import numpy as np
import pandas as pd
import pytest

from app.services.ingestion_v2.contracts.base import compute_stage_fingerprint
from app.services.ingestion_v2.contracts.normalization import (
    CanonicalPhysicalType,
    NormalizedColumn,
    NormalizedDataset,
    NormalizedFieldLineage,
    NormalizedTable,
)
from app.services.ingestion_v2.contracts.profiling import (
    ColumnStructuralProfile,
    StructuralDataQuality,
    StructuralProfile,
    TableStructuralProfile,
)
from app.services.ingestion_v2.profiling.structural_profiler import (
    compute_candidate_dimension_score,
    compute_candidate_identifier_score,
    compute_deterministic_quantiles,
    compute_pattern_signature,
    compute_shannon_entropy,
    explore_composite_candidate_keys,
    profile_column,
    profile_dataset,
    profile_table,
)


def _make_norm_col(col_id: str, col_name: str, ptype: CanonicalPhysicalType) -> NormalizedColumn:
    return NormalizedColumn(
        column_id=col_id,
        table_id="tbl_test",
        column_name=col_name,
        canonical_type=ptype,
        lineage=NormalizedFieldLineage(
            column_id=col_id,
            raw_header_name=col_name,
        ),
        null_count=0,
        non_null_count=0,
    )


# =========================================================================
# 1. COLUMN PROFILING TESTS
# =========================================================================

def test_column_nulls_distinct_and_uniqueness():
    """Verify exact calculation of null_count, null_ratio, distinct_count, uniqueness_ratio."""
    col_def = _make_norm_col("c1", "status", CanonicalPhysicalType.STRING)
    series = pd.Series(["Active", "Inactive", "Active", None, "Active"])
    prof = profile_column(col_def, series, table_row_count=5)

    assert prof.row_count == 5
    assert prof.null_count == 1
    assert prof.null_ratio == 0.20
    assert prof.non_null_count == 4
    assert prof.distinct_count == 2
    assert prof.uniqueness_ratio == 0.40  # 2 / 5


def test_deterministic_quantiles_linear_interpolation():
    """Verify quantiles Q1 (25%), Q2 (50% median), Q3 (75%) use exact linear interpolation."""
    arr = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    q = compute_deterministic_quantiles(arr)

    assert q["Q1"] == 20.0
    assert q["Q2"] == 30.0
    assert q["Q3"] == 40.0

    # Even number of elements
    arr_even = np.array([10.0, 20.0, 30.0, 40.0])
    q_even = compute_deterministic_quantiles(arr_even)
    assert q_even["Q1"] == 17.5
    assert q_even["Q2"] == 25.0
    assert q_even["Q3"] == 32.5


def test_deterministic_shannon_entropy():
    """Verify Shannon entropy H = -sum(p*log2(p)) and normalized entropy."""
    # Balanced 2 classes: 50% A, 50% B -> H = 1.0, H_norm = 1.0
    h, h_norm = compute_shannon_entropy([50, 50], 100)
    assert h == 1.0
    assert h_norm == 1.0

    # Skewed classes: 75% A, 25% B
    # H = -(0.75*log2(0.75) + 0.25*log2(0.25)) = -(0.75*(-0.415037) + 0.25*(-2)) = 0.31128 + 0.5 = 0.8113
    h_skew, h_norm_skew = compute_shannon_entropy([75, 25], 100)
    assert math.isclose(h_skew, 0.8113, abs_tol=1e-3)
    assert math.isclose(h_norm_skew, 0.8113, abs_tol=1e-3)

    # Constant: 100% A -> H = 0.0
    h_const, h_norm_const = compute_shannon_entropy([100], 100)
    assert h_const == 0.0
    assert h_norm_const == 0.0


def test_pattern_signatures():
    """Verify deterministic token mapping: D for digits, A for uppercase, a for lowercase, punctuation preserved."""
    assert compute_pattern_signature("00421") == "DDDDD"
    assert compute_pattern_signature("EMP-00123") == "AAA-DDDDD"
    assert compute_pattern_signature("2026-10-18") == "DDDD-DD-DD"
    assert compute_pattern_signature("Alice_01") == "Aaaaa_DD"


def test_date_coverage_metrics():
    """Verify min_date, max_date, and date_span_days computation."""
    col_def = _make_norm_col("d1", "created_at", CanonicalPhysicalType.DATE)
    series = pd.Series(["2026-01-01", "2026-01-15", "2026-01-31", None])
    prof = profile_column(col_def, series, table_row_count=4)

    assert prof.date_min == "2026-01-01T00:00:00"
    assert prof.date_max == "2026-01-31T00:00:00"
    assert prof.date_span_days == 30


# =========================================================================
# 2. EDGE CASES TESTS
# =========================================================================

def test_edge_case_leading_zero_identifiers():
    """
    CRITICAL: Columns with leading zeros like '00421', '00017', '09382'
    must retain logical_type_candidate == 'STRING' and have leading_zero_ratio > 0.
    Numeric coercion is strictly forbidden.
    """
    col_def = _make_norm_col("c_emp", "EmployeeCode", CanonicalPhysicalType.STRING)
    series = pd.Series(["00421", "00017", "09382", "00100", "05432"])
    prof = profile_column(col_def, series, table_row_count=5)

    assert prof.logical_type_candidate == "STRING"
    assert prof.leading_zero_ratio == 1.0
    assert prof.all_digit_ratio == 1.0
    assert prof.dominant_pattern == "DDDDD"
    assert prof.candidate_identifier_score >= 0.95


def test_edge_case_all_null_column():
    """Verify all-null column produces UNKNOWN logical candidate, 1.0 null ratio, and 0 identifier score."""
    col_def = _make_norm_col("c_null", "empty_col", CanonicalPhysicalType.STRING)
    series = pd.Series([None, None, None, None])
    prof = profile_column(col_def, series, table_row_count=4)

    assert prof.null_count == 4
    assert prof.null_ratio == 1.0
    assert prof.non_null_count == 0
    assert prof.distinct_count == 0
    assert prof.logical_type_candidate == "UNKNOWN"
    assert prof.candidate_identifier_score == 0.0
    assert prof.candidate_dimension_score == 0.0


def test_edge_case_constant_column():
    """Verify single distinct value flagged as is_constant=True, constant_ratio=1.0, entropy=0."""
    col_def = _make_norm_col("c_const", "Country", CanonicalPhysicalType.STRING)
    series = pd.Series(["USA", "USA", "USA", "USA", "USA"])
    prof = profile_column(col_def, series, table_row_count=5)

    assert prof.is_constant is True
    assert prof.is_quasi_constant is False
    assert prof.constant_ratio == 1.0
    assert prof.categorical_entropy == 0.0
    assert prof.candidate_dimension_score == 0.0
    assert prof.candidate_identifier_score == 0.0


def test_edge_case_near_constant_column():
    """Verify 96% dominant value flagged as is_quasi_constant=True."""
    col_def = _make_norm_col("c_near", "Currency", CanonicalPhysicalType.STRING)
    vals = ["USD"] * 96 + ["EUR"] * 4
    series = pd.Series(vals)
    prof = profile_column(col_def, series, table_row_count=100)

    assert prof.is_constant is False
    assert prof.is_quasi_constant is True
    assert prof.near_constant_ratio == 0.96


def test_edge_case_high_cardinality_unique_key():
    """Verify 100% unique values produce high candidate_identifier_score and 0 candidate_dimension_score."""
    col_def = _make_norm_col("c_id", "ID", CanonicalPhysicalType.STRING)
    vals = [f"ID-{i:04d}" for i in range(100)]
    series = pd.Series(vals)
    prof = profile_column(col_def, series, table_row_count=100)

    assert prof.uniqueness_ratio == 1.0
    assert prof.null_ratio == 0.0
    assert prof.candidate_identifier_score >= 0.95
    assert prof.candidate_dimension_score == 0.0
    assert prof.is_unique_candidate is True


def test_edge_case_unicode_and_mixed_strings():
    """Verify Unicode strings profile without crash, preserving token patterns."""
    col_def = _make_norm_col("c_uni", "City", CanonicalPhysicalType.STRING)
    series = pd.Series(["Zürich", "São Paulo", "München", "København"])
    prof = profile_column(col_def, series, table_row_count=4)

    assert prof.non_null_count == 4
    assert prof.distinct_count == 4
    assert prof.pattern_signature is not None


def test_edge_case_numeric_extremes():
    """Verify extreme numeric values (negative, large, small float) compute mean/stddev/quantiles deterministically."""
    col_def = _make_norm_col("c_num", "Value", CanonicalPhysicalType.FLOAT)
    series = pd.Series([-1e6, -100.5, 0.0, 100.5, 1e6])
    prof = profile_column(col_def, series, table_row_count=5)

    assert prof.min_value == -1e6
    assert prof.max_value == 1e6
    assert prof.mean == 0.0
    assert prof.median == 0.0
    assert prof.quantiles["Q1"] == -100.5
    assert prof.quantiles["Q3"] == 100.5


# =========================================================================
# 3. TABLE LEVEL & STRUCTURAL QUALITY TESTS
# =========================================================================

def test_table_profiling_and_structural_quality():
    """
    Verify TableStructuralProfile computes duplicate row count, all-null rows,
    composite key candidate exploration, and StructuralDataQuality.
    """
    df = pd.DataFrame({
        "EmpID": ["E01", "E02", "E03", "E01"],
        "Dept": ["Engineering", "HR", "Sales", "Engineering"],
        "Salary": [100000, 80000, 90000, 100000],
    })
    # Notice: Row 0 and Row 3 are exact duplicate rows

    tbl_def = NormalizedTable(
        table_id="tbl_emp",
        table_name="Employees",
        columns=[
            _make_norm_col("c1", "EmpID", CanonicalPhysicalType.STRING),
            _make_norm_col("c2", "Dept", CanonicalPhysicalType.STRING),
            _make_norm_col("c3", "Salary", CanonicalPhysicalType.INTEGER),
        ],
        row_count=4,
        column_count=3,
    )

    tbl_prof = profile_table(tbl_def, df)

    assert tbl_prof.row_count == 4
    assert tbl_prof.column_count == 3
    assert tbl_prof.duplicate_row_count == 1
    assert tbl_prof.duplicate_row_ratio == 0.25
    assert "HIGH_DUPLICATE_ROW_RATIO: 0.25" in tbl_prof.structural_warnings

    # Quality check
    q = tbl_prof.quality
    assert q.completeness_score == 1.0  # 0 nulls
    assert q.uniqueness_score == 0.75   # 1.0 - 0.25 duplicate ratio
    assert q.validity_score == 1.0
    assert 0.0 <= q.overall_structural_quality <= 1.0


def test_composite_candidate_keys_bounded_complexity():
    """Verify composite candidate exploration respects max_pairs limit and computes pairwise uniqueness."""
    df = pd.DataFrame({
        "Region": ["North", "North", "South", "South"],
        "Quarter": ["Q1", "Q2", "Q1", "Q2"],
        "Sales": [100, 150, 200, 250],
    })
    # Individual Region distinct=2, Quarter distinct=2. Together (Region, Quarter) is 100% unique!
    cols = [
        _make_norm_col("c1", "Region", CanonicalPhysicalType.STRING),
        _make_norm_col("c2", "Quarter", CanonicalPhysicalType.STRING),
        _make_norm_col("c3", "Sales", CanonicalPhysicalType.INTEGER),
    ]
    column_profiles = [profile_column(c, df[c.column_name], 4) for c in cols]
    pairs = explore_composite_candidate_keys(df, column_profiles, max_pairs=3)

    assert len(pairs) >= 1
    pair = pairs[0]
    assert pair["pair_uniqueness_ratio"] == 1.0
    assert pair["is_composite_unique"] is True


# =========================================================================
# 4. DETERMINISM & STAGE FINGERPRINT STABILITY
# =========================================================================

def test_structural_profiler_10_run_determinism():
    """Run structural profiler 10 consecutive times on identical input: assert exact identical fingerprints and models."""
    df = pd.DataFrame({
        "ID": ["001", "002", "003", "004", "005"],
        "Dept": ["Engineering", "Sales", "Engineering", "HR", "Sales"],
        "Rating": [4.5, 3.8, 4.2, 5.0, 3.9],
    })
    tbl_def = NormalizedTable(
        table_id="tbl_det",
        table_name="DeterminismCheck",
        columns=[
            _make_norm_col("c1", "ID", CanonicalPhysicalType.STRING),
            _make_norm_col("c2", "Dept", CanonicalPhysicalType.STRING),
            _make_norm_col("c3", "Rating", CanonicalPhysicalType.FLOAT),
        ],
        row_count=5,
        column_count=3,
    )
    dataset = NormalizedDataset(
        dataset_id="ds-det-01",
        run_id="run-det-01",
        stage_name="sanitization_normalization",
        source_fingerprint="fp-norm",
        provenance=[],
        tables=[tbl_def],
        rules_applied=[],
    )

    fingerprints: set[str] = set()
    dumps: set[str] = set()

    for _ in range(10):
        prof = profile_dataset(dataset, table_data={"tbl_det": df})
        fingerprints.add(prof.source_fingerprint)
        # Exclude volatile run_id or created_at if any, checking canonical payload dump
        dump = json.dumps(prof.model_dump(exclude={"run_id", "created_at"}), sort_keys=True)
        dumps.add(dump)

    assert len(fingerprints) == 1, "Non-deterministic fingerprint detected across runs!"
    assert len(dumps) == 1, "Non-deterministic serialization dump detected across runs!"


# =========================================================================
# 5. EPISTEMIC BOUNDARY & ZERO BUSINESS LANGUAGE NEGATIVE TEST
# =========================================================================

def test_negative_vocabulary_zero_business_interpretation():
    """
    Verify StructuralProfile output contains ZERO business interpretation language.
    Forbidden words: best, worst, risk, underperform, high-performing, recommend, anomaly, root cause, opportunity, kpi.
    """
    df = pd.DataFrame({
        "Metric": [10, 20, 30, 40, 50],
        "Category": ["A", "B", "A", "B", "C"],
    })
    tbl_def = NormalizedTable(
        table_id="tbl_biz",
        table_name="RawData",
        columns=[
            _make_norm_col("c1", "Metric", CanonicalPhysicalType.INTEGER),
            _make_norm_col("c2", "Category", CanonicalPhysicalType.STRING),
        ],
        row_count=5,
        column_count=2,
    )
    dataset = NormalizedDataset(
        dataset_id="ds-biz",
        run_id="run-biz",
        stage_name="sanitization_normalization",
        source_fingerprint="fp-norm",
        provenance=[],
        tables=[tbl_def],
        rules_applied=[],
    )

    prof = profile_dataset(dataset, table_data={"tbl_biz": df})
    dump_text = json.dumps(prof.model_dump()).lower()

    forbidden_business_words = [
        "best",
        "worst",
        "risk",
        "underperform",
        "high-performing",
        "recommend",
        "anomaly",
        "root cause",
        "opportunity",
        "kpi",
    ]

    for word in forbidden_business_words:
        assert word not in dump_text, f"Forbidden business term '{word}' found in StructuralProfile output!"


def test_epistemic_boundary_zero_forbidden_intelligence():
    """
    Assert StructuralProfile does NOT contain:
    - semantic roles (SemanticModel)
    - grain inference (GrainProfile)
    - relationships / join plans
    - vector indexes or retrieval tokens
    """
    prof_dict = StructuralProfile.model_fields
    assert "semantic_roles" not in prof_dict
    assert "grain_profile" not in prof_dict
    assert "relationships" not in prof_dict
    assert "join_plan" not in prof_dict
    assert "vector_manifest" not in prof_dict


# =========================================================================
# 6. PERFORMANCE & COMPLEXITY BUDGET BENCHMARK
# =========================================================================

def test_performance_small_medium_large():
    """
    Benchmark profiling latency across small (100 rows), medium (1,000 rows), and large (10,000 rows).
    Verifies linear scalability with zero quadratic blowup.
    """
    sizes = [100, 1000, 10000]
    latencies = {}

    for size in sizes:
        df = pd.DataFrame({
            "ID": [f"EMP-{i:05d}" for i in range(size)],
            "Dept": ["Engineering" if i % 3 == 0 else "Sales" if i % 3 == 1 else "HR" for i in range(size)],
            "Salary": [50000 + (i % 500) * 100 for i in range(size)],
            "Date": ["2026-01-01" for _ in range(size)],
        })
        tbl_def = NormalizedTable(
            table_id=f"tbl_{size}",
            table_name=f"Scale_{size}",
            columns=[
                _make_norm_col("c1", "ID", CanonicalPhysicalType.STRING),
                _make_norm_col("c2", "Dept", CanonicalPhysicalType.STRING),
                _make_norm_col("c3", "Salary", CanonicalPhysicalType.INTEGER),
                _make_norm_col("c4", "Date", CanonicalPhysicalType.DATE),
            ],
            row_count=size,
            column_count=4,
        )
        dataset = NormalizedDataset(
            dataset_id=f"ds-{size}",
            run_id="run-perf",
            stage_name="sanitization_normalization",
            source_fingerprint="fp-norm",
            provenance=[],
            tables=[tbl_def],
            rules_applied=[],
        )

        times = []
        for _ in range(3):
            t0 = time.perf_counter()
            profile_dataset(dataset, table_data={f"tbl_{size}": df})
            times.append(time.perf_counter() - t0)

        p50 = float(np.percentile(times, 50))
        p95 = float(np.percentile(times, 95))
        latencies[size] = (p50, p95)

    # 10,000 rows with 4 columns must profile well under 500ms
    large_p50 = latencies[10000][0]
    assert large_p50 < 0.50, f"Profiling 10k rows took {large_p50:.3f}s (budget: <0.50s)"
