"""
HighView Semantic Data Refinery — Phase SDR-1
Deterministic Feature Extractor
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Sequence

from app.services.sdr.contracts.profiles import DeterministicColumnFeatures

from app.services.sdr.decomposition.false_split_guards import (
    is_compound_category_literal,
    is_formatted_number_literal,
    is_phone_number,
)

# Pre-compiled strict regex patterns
RE_INT = re.compile(r"^[-+]?\d+$")
RE_FLOAT = re.compile(r"^[-+]?\d+(?:,\d{3})*(?:\.\d+)?$")
RE_DATE_ISO = re.compile(r"^\d{4}[-/](?:0[1-9]|1[0-2])[-/](?:0[1-9]|[12]\d|3[01])$")
RE_DATE_DMY = re.compile(r"^(?:0[1-9]|[12]\d|3[01])[-/](?:0[1-9]|1[0-2])[-/]\d{4}$")
RE_DATE_YM = re.compile(r"^\d{4}[-/](?:0[1-9]|1[0-2])$")
RE_DATE_QUARTER = re.compile(r"^(?:\d{4}[-_\s]?[Qq][1-4]|[Qq][1-4][-_\s]?\d{4})$")
RE_IDENTIFIER_CODE = re.compile(r"^[A-Za-z]{2,6}[-_]\d{2,10}$|^[A-Za-z]{1,4}\d{3,10}$|^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}")

BOOLEAN_TOKENS: set[str] = {"true", "false", "yes", "no", "y", "n", "0", "1", "t", "f"}
CURRENCY_SYMBOLS: set[str] = {"$", "€", "£", "₹", "¥"}
CURRENCY_CODES: set[str] = {"usd", "inr", "eur", "gbp", "jpy", "cad", "aud"}
PERCENT_TOKENS: set[str] = {"%", "pct", "percent"}
DELIMITERS: list[str] = [" - ", " | ", "/", ",", ":", ";", " _ "]


def is_date_like(val_str: str) -> bool:
    """Strict date format validation to avoid false positives."""
    s = val_str.strip()
    if RE_DATE_ISO.match(s) or RE_DATE_DMY.match(s) or RE_DATE_YM.match(s) or RE_DATE_QUARTER.match(s):
        return True
    return False


def is_numeric_like(val_str: str) -> tuple[bool, bool]:
    """
    Returns (is_numeric, is_integer).
    Cleans out optional currency symbols and commas.
    """
    s = val_str.strip()
    # Strip known currency symbols
    for sym in CURRENCY_SYMBOLS:
        if s.startswith(sym) or s.endswith(sym):
            s = s.replace(sym, "").strip()
    # Strip known currency codes at start/end
    lower = s.lower()
    for code in CURRENCY_CODES:
        if lower.startswith(code):
            s = s[len(code):].strip()
        elif lower.endswith(code):
            s = s[:-len(code)].strip()
    # Strip percent
    if s.endswith("%"):
        s = s[:-1].strip()

    # Remove thousands separators
    s_clean = s.replace(",", "")
    if RE_INT.match(s_clean):
        return True, True
    if RE_FLOAT.match(s_clean) or RE_FLOAT.match(s):
        return True, False
    return False, False


def extract_deterministic_features(
    values: Sequence[Any],
    max_samples: int = 10,
) -> DeterministicColumnFeatures:
    """
    Calculates deterministic structural and pattern features from raw column values.
    Pure functional calculation with zero external side effects or model dependencies.
    """
    row_count = len(values)
    if row_count == 0:
        return DeterministicColumnFeatures(
            row_count=0,
            null_count=0,
            null_ratio=0.0,
            distinct_count=0,
            distinct_ratio=0.0,
        )

    null_count = 0
    non_null_strings: list[str] = []
    seen_distinct: set[str] = set()

    for v in values:
        if v is None:
            null_count += 1
            continue
        s = str(v).strip()
        if s == "" or s.lower() in ("null", "none", "nan", "n/a", "#n/a", "-"):
            null_count += 1
            continue
        non_null_strings.append(s)
        seen_distinct.add(s)

    non_null_count = len(non_null_strings)
    null_ratio = round(null_count / row_count, 4)
    distinct_count = len(seen_distinct)
    distinct_ratio = round(distinct_count / non_null_count, 4) if non_null_count > 0 else 0.0

    if non_null_count == 0:
        return DeterministicColumnFeatures(
            row_count=row_count,
            null_count=null_count,
            null_ratio=null_ratio,
            distinct_count=0,
            distinct_ratio=0.0,
        )

    # Feature counters
    numeric_count = 0
    integer_count = 0
    date_count = 0
    boolean_count = 0
    currency_count = 0
    percent_count = 0
    identifier_pattern_count = 0
    total_length = 0
    delimiter_counts: dict[str, int] = {d: 0 for d in DELIMITERS}

    for s in non_null_strings:
        total_length += len(s)
        lower = s.lower()

        # Numeric check
        is_num, is_int = is_numeric_like(s)
        if is_num:
            numeric_count += 1
            if is_int:
                integer_count += 1

        # Date check
        if is_date_like(s):
            date_count += 1

        # Boolean check
        if lower in BOOLEAN_TOKENS:
            boolean_count += 1

        # Currency symbol check
        has_curr = any(sym in s for sym in CURRENCY_SYMBOLS) or any(
            f" {code}" in lower or f"{code} " in lower or lower == code for code in CURRENCY_CODES
        )
        if has_curr:
            currency_count += 1

        # Percentage check
        if any(pct in lower for pct in PERCENT_TOKENS):
            percent_count += 1

        # Identifier pattern check
        if RE_IDENTIFIER_CODE.match(s):
            identifier_pattern_count += 1

        # Delimiter checks (guarded against false-split literals)
        is_protected_literal = (
            is_date_like(s)
            or is_phone_number(s)
            or is_formatted_number_literal(s)
            or is_compound_category_literal(s)
        )
        if not is_protected_literal:
            for d in DELIMITERS:
                if d in s:
                    delimiter_counts[d] += 1

    # Take deterministic sample values (sorted unique representation of first observed distinct)
    deterministic_samples = sorted(list(seen_distinct)[:max_samples])
    sample_payload = json.dumps(deterministic_samples, sort_keys=True)
    sample_fingerprint = hashlib.sha256(sample_payload.encode("utf-8")).hexdigest()

    return DeterministicColumnFeatures(
        row_count=row_count,
        null_count=null_count,
        null_ratio=null_ratio,
        distinct_count=distinct_count,
        distinct_ratio=distinct_ratio,
        numeric_parseable_ratio=round(numeric_count / non_null_count, 4),
        integer_ratio=round(integer_count / non_null_count, 4),
        date_parseable_ratio=round(date_count / non_null_count, 4),
        boolean_vocabulary_ratio=round(boolean_count / non_null_count, 4),
        currency_symbol_ratio=round(currency_count / non_null_count, 4),
        percentage_symbol_ratio=round(percent_count / non_null_count, 4),
        identifier_pattern_ratio=round(identifier_pattern_count / non_null_count, 4),
        avg_value_length=round(total_length / non_null_count, 2),
        delimiter_counts={k: v for k, v in delimiter_counts.items() if v > 0},
        sample_values=deterministic_samples,
        sample_fingerprint=sample_fingerprint,
    )
