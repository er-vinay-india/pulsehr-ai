"""Comprehensive Unit & Boundary Test Suite for HighView Display Formatting (Backend).

Verifies:
- Standard compact thresholds (K, M, B, T) and rollovers.
- Multi-currency symbol mapping (USD, INR, EUR, AED, GBP, JPY).
- Semantic exclusions: IDs, Years, Percentages, Durations, Scores.
- Graceful null/NaN/Infinity handling.
- Full unrounded exact measure formatting.
- Invariance: raw values and semantic hashes remain untouched.
"""

import hashlib
import json
import math
import pytest

from app.services.display_formatting import (
    format_governed_number,
    format_exact_measure,
    is_compact_allowed,
    parse_governed_number,
)


def test_standard_compact_number_boundaries():
    """Validates K, M, B, T scaling and boundary transitions."""
    assert format_governed_number(0) == "0"
    assert format_governed_number(1) == "1"
    assert format_governed_number(950) == "950"
    assert format_governed_number(999) == "999"
    assert format_governed_number(1000) == "1K"
    assert format_governed_number(1001) == "1K"
    assert format_governed_number(1250) == "1.25K"
    assert format_governed_number(12500) == "12.5K"
    assert format_governed_number(999499) == "999.5K"
    assert format_governed_number(999999) == "1M"
    assert format_governed_number(1000000) == "1M"
    assert format_governed_number(1250000) == "1.25M"
    assert format_governed_number(58000000) == "58M"
    assert format_governed_number(999999999) == "1B"
    assert format_governed_number(1000000000) == "1B"
    assert format_governed_number(1250000000) == "1.25B"
    assert format_governed_number(2400000000000) == "2.4T"


def test_currency_formatting():
    """Validates canonical currency symbol mappings and 3-letter fallbacks."""
    assert format_governed_number(58000000, currency="USD") == "$58M"
    assert format_governed_number(58000000, unit="$") == "$58M"
    assert format_governed_number(1250000, currency="INR") == "₹1.25M"
    assert format_governed_number(923500, currency="EUR") == "€923.5K"
    assert format_governed_number(50000000, currency="AED") == "AED 50M"
    assert format_governed_number(1500000, currency="GBP") == "£1.5M"
    assert format_governed_number(80000000, currency="JPY") == "¥80M"


def test_negative_numbers():
    """Validates negative number formatting with currencies and suffixes."""
    assert format_governed_number(-1250) == "-1.25K"
    assert format_governed_number(-58000000, currency="USD") == "-$58M"
    assert format_governed_number(-450, unit="$") == "-$450"


def test_decimal_cleanup():
    """Validates trailing zero stripping and fractional rounding."""
    assert format_governed_number(58.00) == "58"
    assert format_governed_number(58.10) == "58.1"
    assert format_governed_number(58.125) == "58.13"
    assert format_governed_number(1200.0) == "1.2K"
    assert format_governed_number(1000.00) == "1K"


def test_semantic_exclusions_never_compact():
    """Validates that non-aggregatable entities are protected from compaction."""
    # 1. Identifiers
    assert format_governed_number(10523, metric_id="employee_id") == "10,523"
    assert format_governed_number(94105, measure_class="POSTAL_CODE") == "94105"
    assert format_governed_number(883492, label="Account ID") == "883,492"

    # 2. Years (1800-2200)
    assert format_governed_number(2026, label="Fiscal Year") == "2026"
    assert format_governed_number(2024, unit="year") == "2024"
    assert format_governed_number(1999, measure_class="YEAR") == "1999"

    # 3. Percentages
    assert format_governed_number(72.4, unit="%") == "72.4%"
    assert format_governed_number(88.5, label="compliance_rate") == "88.5"
    assert format_governed_number(94.2, measure_class="PERCENTAGE") == "94.2"

    # 4. Durations & Scores
    assert format_governed_number(3600, label="duration_seconds") == "3,600"
    assert format_governed_number(1500, label="performance_score") == "1,500"


def test_graceful_missing_and_invalid_handling():
    """Validates graceful handling of None, NaN, Infinity, and empty inputs."""
    assert format_governed_number(None) == "—"
    assert format_governed_number("") == "—"
    assert format_governed_number("nan") == "—"
    assert format_governed_number("NaN") == "—"
    assert format_governed_number(math.nan) == "—"
    assert format_governed_number(float("inf")) == "—"
    assert format_governed_number("unavailable") == "—"
    assert format_governed_number(None, unavailable_label="N/A") == "N/A"


def test_format_exact_measure():
    """Validates full unrounded exact measure representation for hover tooltips."""
    assert format_exact_measure(58000000, currency="USD") == "$58,000,000"
    assert format_exact_measure(1250) == "1,250"
    assert format_exact_measure(72.4, unit="%") == "72.4%"
    assert format_exact_measure(2026, measure_class="YEAR") == "2026"
    assert format_exact_measure(1234567.89, unit="$") == "$1,234,567.89"


def test_semantic_hash_and_raw_value_invariance():
    """Guarantees that raw values and cryptographic semantic hashes are unchanged by formatting."""
    raw_fact = {
        "fact_id": "FACT-REV-01",
        "metric": "gross_revenue",
        "raw_value": 58000000,
        "unit": "USD",
        "grain": "store_id",
        "denominator": "all_stores",
    }

    # Canonical hash of raw fact
    pre_hash = hashlib.sha256(json.dumps(raw_fact, sort_keys=True).encode("utf-8")).hexdigest()

    # Formatted display representation
    display_str = format_governed_number(raw_fact["raw_value"], currency=raw_fact["unit"])
    exact_hover = format_exact_measure(raw_fact["raw_value"], currency=raw_fact["unit"])

    assert display_str == "$58M"
    assert exact_hover == "$58,000,000"

    # Raw value in dictionary MUST remain untouched
    assert raw_fact["raw_value"] == 58000000

    # Post hash MUST be 100% identical
    post_hash = hashlib.sha256(json.dumps(raw_fact, sort_keys=True).encode("utf-8")).hexdigest()
    assert pre_hash == post_hash
