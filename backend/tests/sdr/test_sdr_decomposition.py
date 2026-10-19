"""
HighView Semantic Data Refinery — Phase SDR-1
Tests: Decomposition Candidate Engine & False-Split Prevention
"""

import copy
from app.services.sdr.contracts.decomposition import (
    CompositePatternType,
    DecompositionValidationStatus,
)
from app.services.sdr.decomposition.decomposition_engine import SDRDecompositionEngine
from app.services.sdr.profiling.column_profiler import SDRColumnProfiler


def test_geographic_hierarchy_decomposition():
    """Verify multi-tier location string produces validated city/state/country components."""
    profiler = SDRColumnProfiler()
    engine = SDRDecompositionEngine()

    raw_locations = [
        "Bengaluru - Karnataka - India",
        "Mumbai - Maharashtra - India",
        "Austin - Texas - USA",
        "London - England - UK",
        "Berlin - Brandenburg - Germany",
    ]
    prof = profiler.profile_column(
        dataset_id="ds_geo",
        sheet_id="s1",
        column_id="c_loc",
        source_name="office_location",
        physical_dtype="string",
        raw_values=raw_locations,
    )
    candidates = engine.generate_candidates(prof, raw_locations)

    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.pattern_type == CompositePatternType.GEOGRAPHIC_HIERARCHY
    assert cand.validation_status == DecompositionValidationStatus.VALIDATED
    assert cand.is_destructive is False
    assert len(cand.components) == 3
    assert [c.candidate_name for c in cand.components] == ["city", "state", "country"]
    assert cand.components[0].sample_extractions[0] == "Bengaluru"
    assert cand.components[1].sample_extractions[0] == "Karnataka"
    assert cand.components[2].sample_extractions[0] == "India"


def test_code_label_decomposition():
    """Verify code + label string produces validated code and label components."""
    profiler = SDRColumnProfiler()
    engine = SDRDecompositionEngine()

    raw_depts = [
        "ENG | Engineering",
        "SAL | Sales",
        "MKT | Marketing",
        "FIN | Finance",
        "OPS | Operations",
    ]
    prof = profiler.profile_column(
        dataset_id="ds_org",
        sheet_id="s1",
        column_id="c_dept_code",
        source_name="dept_assignment",
        physical_dtype="string",
        raw_values=raw_depts,
    )
    candidates = engine.generate_candidates(prof, raw_depts)

    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.pattern_type == CompositePatternType.CODE_LABEL_PAIR
    assert cand.validation_status == DecompositionValidationStatus.VALIDATED
    assert cand.is_destructive is False
    assert len(cand.components) == 2
    assert cand.components[0].candidate_name == "code"
    assert cand.components[1].candidate_name == "label"


def test_currency_with_unit_formatted_value():
    """Verify monetary string with symbol and code produces CURRENCY_WITH_UNIT candidate."""
    profiler = SDRColumnProfiler()
    engine = SDRDecompositionEngine()

    raw_curr = [
        "₹1,25,000 INR",
        "₹95,000 INR",
        "₹1,10,000 INR",
        "₹80,000 INR",
        "₹1,50,000 INR",
    ]
    prof = profiler.profile_column(
        dataset_id="ds_fin",
        sheet_id="s1",
        column_id="c_inr",
        source_name="monthly_ctc",
        physical_dtype="string",
        raw_values=raw_curr,
    )
    candidates = engine.generate_candidates(prof, raw_curr)

    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.pattern_type == CompositePatternType.CURRENCY_WITH_UNIT
    assert cand.validation_status == DecompositionValidationStatus.VALIDATED
    assert cand.is_destructive is False
    assert len(cand.components) == 2
    assert cand.components[0].candidate_name == "amount"
    assert cand.components[1].candidate_name == "currency"


def test_false_split_prevention_on_dates():
    """CRITICAL: ISO and formatted dates with '-' or '/' must NEVER be decomposed."""
    profiler = SDRColumnProfiler()
    engine = SDRDecompositionEngine()

    raw_dates = [
        "2026-10-19",
        "2026-11-20",
        "2026-12-15",
        "2026-01-10",
        "2026-02-28",
    ]
    prof = profiler.profile_column(
        dataset_id="ds_dates",
        sheet_id="s1",
        column_id="c_date",
        source_name="completion_date",
        physical_dtype="string",
        raw_values=raw_dates,
    )
    candidates = engine.generate_candidates(prof, raw_dates)
    # ZERO decomposition candidates allowed!
    assert len(candidates) == 0


def test_false_split_prevention_on_phone_numbers():
    """CRITICAL: International and toll-free phone numbers must NEVER be split on '-'."""
    profiler = SDRColumnProfiler()
    engine = SDRDecompositionEngine()

    raw_phones = [
        "+91-9876543210",
        "+91-9876543211",
        "+1-800-555-0199",
        "+44-20-7946-0919",
        "+91-9876543214",
    ]
    prof = profiler.profile_column(
        dataset_id="ds_phone",
        sheet_id="s1",
        column_id="c_phone",
        source_name="work_phone",
        physical_dtype="string",
        raw_values=raw_phones,
    )
    candidates = engine.generate_candidates(prof, raw_phones)
    assert len(candidates) == 0


def test_false_split_prevention_on_formatted_numbers():
    """CRITICAL: Numbers with thousand-separating commas must NEVER split on commas."""
    profiler = SDRColumnProfiler()
    engine = SDRDecompositionEngine()

    raw_numbers = [
        "1,250.50",
        "2,400.00",
        "850.75",
        "10,120.25",
        "5,500.00",
    ]
    prof = profiler.profile_column(
        dataset_id="ds_num",
        sheet_id="s1",
        column_id="c_num",
        source_name="volume_metric",
        physical_dtype="string",
        raw_values=raw_numbers,
    )
    candidates = engine.generate_candidates(prof, raw_numbers)
    assert len(candidates) == 0


def test_false_split_prevention_on_compound_categories():
    """CRITICAL: Compound business categories like 'R&D / Innovation' must NOT split on '/'."""
    profiler = SDRColumnProfiler()
    engine = SDRDecompositionEngine()

    raw_cats = [
        "R&D / Innovation",
        "R&D / Innovation",
        "Sales / Marketing",
        "Strategy & Ops",
        "R&D / Innovation",
    ]
    prof = profiler.profile_column(
        dataset_id="ds_cat",
        sheet_id="s1",
        column_id="c_bu",
        source_name="business_unit",
        physical_dtype="string",
        raw_values=raw_cats,
    )
    candidates = engine.generate_candidates(prof, raw_cats)
    assert len(candidates) == 0


def test_source_immutability_during_decomposition():
    """Verify source input list and objects are bit-for-bit unchanged after profiling and decomposition."""
    profiler = SDRColumnProfiler()
    engine = SDRDecompositionEngine()

    original_raw = [
        "Bengaluru - Karnataka - India",
        "Mumbai - Maharashtra - India",
        "Austin - Texas - USA",
    ]
    input_copy = copy.deepcopy(original_raw)

    prof = profiler.profile_column(
        dataset_id="ds_immut",
        sheet_id="s1",
        column_id="c_test",
        source_name="Location",
        physical_dtype="string",
        raw_values=input_copy,
    )
    candidates = engine.generate_candidates(prof, input_copy)

    # Input list remains strictly identical
    assert input_copy == original_raw
    assert prof.source_name == "Location"
    assert prof.physical_dtype == "string"
    assert len(candidates) == 1
    assert candidates[0].is_destructive is False
