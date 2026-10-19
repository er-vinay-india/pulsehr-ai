"""
HighView Semantic Data Refinery — Phase SDR-1
False-Split Prevention Guards
"""

from __future__ import annotations

import re
from typing import Sequence

# Regex guards for atomic patterns
RE_PHONE_INTL = re.compile(r"^\+?\d{1,4}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}$")
RE_DATE_STRICT = re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}$|^\d{1,2}[-/]\d{1,2}[-/]\d{4}$")
RE_DATE_QUARTER = re.compile(r"^(?:\d{4}[-_\s]?[Qq][1-4]|[Qq][1-4][-_\s]?\d{4}|FY\d{2,4}[-_]?[MQ][0-9]{1,2})$", re.IGNORECASE)
RE_FORMATTED_NUMBER = re.compile(r"^[-+]?[$€£₹¥]?\s*\d{1,3}(?:,\d{2,3})*(?:\.\d+)?\s*[%a-zA-Z]{0,4}$")
RE_ACRONYM_PAIR = re.compile(r"^[A-Z&]{1,5}\s*[/]\s*[A-Za-z\s]{3,20}$")  # e.g., "R&D / Innovation"


def is_phone_number(val_str: Any) -> bool:
    """Detects phone numbers with country codes or hyphens."""
    s = str(val_str).strip()
    if is_date_or_quarter_literal(s):
        return False
    if ("+" in s or s.startswith("1-800") or s.startswith("1-888") or (s.count("-") >= 2 and len(s) >= 12)) and RE_PHONE_INTL.match(s):
        digits = re.sub(r"\D", "", s)
        if len(digits) >= 10:
            return True
    return False


def is_date_or_quarter_literal(val_str: Any) -> bool:
    """Detects date strings and fiscal quarters that must never be split."""
    s = str(val_str).strip()
    if RE_DATE_STRICT.match(s) or RE_DATE_QUARTER.match(s):
        return True
    return False


def is_formatted_number_literal(val_str: Any) -> bool:
    """Detects formatted monetary or numeric quantities with commas/decimals."""
    s = str(val_str).strip()
    # If it's a numeric amount with thousands separator
    if ("," in s or "." in s) and RE_FORMATTED_NUMBER.match(s):
        # Verify it has digits around the comma/period
        return True
    return False


def is_compound_category_literal(val_str: Any) -> bool:
    """
    Detects single business categories containing punctuation like slashes or ampersands.
    e.g. 'R&D / Innovation', 'Strategy & Ops', 'Oil & Gas'.
    """
    s = str(val_str).strip()
    if RE_ACRONYM_PAIR.match(s) or s.lower() in ("r&d / innovation", "sales / marketing", "oil & gas", "strategy & ops"):
        return True
    return False


def evaluate_false_split_rejection(
    sample_values: Sequence[str],
    candidate_delimiter: str,
) -> tuple[bool, str | None]:
    """
    Evaluates whether splitting on candidate_delimiter would cause a false decomposition.
    Returns (should_reject, rejection_reason).
    """
    if not sample_values:
        return True, "EMPTY_SAMPLE"

    # Guard 1: Whitespace alone is never an authorized composite delimiter
    if candidate_delimiter.strip() == "":
        return True, "WHITESPACE_DELIMITER_FORBIDDEN"

    total = len(sample_values)
    phone_count = 0
    date_count = 0
    formatted_num_count = 0
    compound_cat_count = 0

    for s in sample_values:
        if is_phone_number(s):
            phone_count += 1
        if is_date_or_quarter_literal(s):
            date_count += 1
        if is_formatted_number_literal(s):
            formatted_num_count += 1
        if is_compound_category_literal(s):
            compound_cat_count += 1

    # If > 50% match phone number pattern, reject splitting on '-'
    if phone_count / total >= 0.50:
        return True, "PHONE_NUMBER_PROTECTION"

    # If > 50% match date pattern, reject splitting on '-' or '/'
    if date_count / total >= 0.50:
        return True, "DATE_LITERAL_PROTECTION"

    # If > 50% match formatted numbers, reject splitting on ',' or '.'
    if formatted_num_count / total >= 0.50:
        return True, "FORMATTED_NUMBER_PROTECTION"

    # If > 50% match compound categories, reject splitting on '/'
    if compound_cat_count / total >= 0.50:
        return True, "COMPOUND_CATEGORY_PROTECTION"

    return False, None
