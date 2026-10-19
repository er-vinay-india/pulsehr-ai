"""
HighView Semantic Data Refinery — Phase SDR-1
Tests: Column Profiler Engine & Deterministic Classification
"""

import pytest
from app.services.ingestion_v2.contracts.semantics import (
    MeasureClass,
    SemanticColumnRole,
    SemanticConcept,
)
from app.services.sdr.contracts.policies import SemanticConfidencePolicy
from app.services.sdr.contracts.profiles import (
    PrivacyClassification,
    ProfilingAmbiguityState,
    SemanticDtype,
)
from app.services.sdr.profiling.column_profiler import SDRColumnProfiler
from app.services.sdr.profiling.deterministic_features import extract_deterministic_features


def test_deterministic_feature_extractor_on_mixed_values():
    """Verify statistical and format feature extraction on dirty and null values."""
    raw = ["$100", "$250.50", "N/A", "$300", None, "$450.00", ""]
    features = extract_deterministic_features(raw)

    assert features.row_count == 7
    assert features.null_count == 3  # "N/A", None, ""
    assert features.null_ratio == pytest.approx(3 / 7, 0.01)
    assert features.distinct_count == 4
    assert features.currency_symbol_ratio == 1.0  # 4 non-nulls all have '$'
    assert features.numeric_parseable_ratio == 1.0
    assert len(features.sample_values) == 4


def test_physical_vs_semantic_dtype_separation():
    """Verify that physical type is never mutated and semantic type is independently deduced."""
    profiler = SDRColumnProfiler()

    # 1. Physical string containing currency
    prof_curr = profiler.profile_column(
        dataset_id="ds_test",
        sheet_id="s1",
        column_id="c_sal",
        source_name="annual_salary",
        physical_dtype="string",
        raw_values=["$75,000", "$82,000", "$105,000", "$94,000", "$120,000"],
    )
    assert prof_curr.physical_dtype == "string"
    assert prof_curr.semantic_dtype == SemanticDtype.CURRENCY_AMOUNT
    assert prof_curr.semantic_role == SemanticColumnRole.MEASURE
    assert prof_curr.measure_class == MeasureClass.FINANCIAL
    assert prof_curr.privacy_classification == PrivacyClassification.SENSITIVE_ATTRIBUTE

    # 2. Physical string containing ISO dates
    prof_date = profiler.profile_column(
        dataset_id="ds_test",
        sheet_id="s1",
        column_id="c_dt",
        source_name="event_timestamp",
        physical_dtype="string",
        raw_values=["2026-01-15", "2026-02-20", "2026-03-10", "2026-04-05"],
    )
    assert prof_date.physical_dtype == "string"
    assert prof_date.semantic_dtype == SemanticDtype.DATE
    assert prof_date.semantic_role == SemanticColumnRole.TIME
    assert prof_date.semantic_concept == SemanticConcept.TIME_SPAN

    # 3. Physical int64 representing an employee identifier
    prof_id = profiler.profile_column(
        dataset_id="ds_test",
        sheet_id="s1",
        column_id="c_emp",
        source_name="employee_id",
        physical_dtype="int64",
        raw_values=[1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008],
    )
    assert prof_id.physical_dtype == "int64"
    assert prof_id.semantic_role == SemanticColumnRole.ENTITY_IDENTIFIER
    assert prof_id.privacy_classification == PrivacyClassification.DIRECT_IDENTIFIER


def test_measure_detection_percentage_and_headcount():
    """Verify percentage and headcount measure classifications."""
    profiler = SDRColumnProfiler()

    prof_pct = profiler.profile_column(
        dataset_id="ds_test",
        sheet_id="s1",
        column_id="c_pct",
        source_name="turnover_rate",
        physical_dtype="float64",
        raw_values=["14.2%", "10.5%", "18.0%", "9.1%", "12.3%"],
    )
    assert prof_pct.semantic_dtype == SemanticDtype.PERCENTAGE_RATE
    assert prof_pct.semantic_role == SemanticColumnRole.MEASURE
    assert prof_pct.measure_class == MeasureClass.PERCENTAGE

    prof_hc = profiler.profile_column(
        dataset_id="ds_test",
        sheet_id="s1",
        column_id="c_hc",
        source_name="active_headcount",
        physical_dtype="int64",
        raw_values=[50, 42, 60, 38, 55],
    )
    assert prof_hc.semantic_role == SemanticColumnRole.MEASURE
    assert prof_hc.measure_class == MeasureClass.HEADCOUNT


def test_adversarial_contradiction_handling():
    """Verify that value structure overrides deceptive column names."""
    profiler = SDRColumnProfiler()

    # Column named 'employee_id' but containing only 2 distinct categories over 20 rows
    vals = ["Engineering", "HR"] * 10
    prof = profiler.profile_column(
        dataset_id="ds_test",
        sheet_id="s1",
        column_id="c_fake_id",
        source_name="employee_id",
        physical_dtype="string",
        raw_values=vals,
    )
    # Must NOT be classified as ENTITY_IDENTIFIER!
    assert prof.semantic_role == SemanticColumnRole.DIMENSION
    assert prof.ambiguity_state == ProfilingAmbiguityState.CONTRADICTORY_SIGNALS


def test_responsible_abstention_on_unknown():
    """Verify low-confidence or uninterpretable columns yield UNKNOWN without guessing."""
    profiler = SDRColumnProfiler()

    prof = profiler.profile_column(
        dataset_id="ds_test",
        sheet_id="s1",
        column_id="c_blob",
        source_name="raw_payload_x",
        physical_dtype="string",
        raw_values=["0x889a", "0x12bc", "0xfa30", "0x9911", "0x4422"],
    )
    assert prof.semantic_role == SemanticColumnRole.UNKNOWN
    assert prof.semantic_dtype == SemanticDtype.UNKNOWN
    assert prof.ambiguity_state == ProfilingAmbiguityState.UNKNOWN_DISTRIBUTION
    assert prof.confidence < 0.45


def test_configurable_policy_thresholds():
    """Verify that profiler respects custom policy thresholds."""
    # Policy with strict promotion threshold 0.90
    strict_policy = SemanticConfidencePolicy(promotion_threshold=0.90)
    profiler_strict = SDRColumnProfiler(policy=strict_policy)

    prof = profiler_strict.profile_column(
        dataset_id="ds_test",
        sheet_id="s1",
        column_id="c_dept",
        source_name="department",
        physical_dtype="string",
        raw_values=["Sales", "HR", "Engineering", "Marketing", "Finance"],
    )
    # Even if identified as dimension with confidence 0.80, classification_source reflects fallback/review
    assert prof.confidence == 0.80
    assert prof.classification_source.value == "FALLBACK"
