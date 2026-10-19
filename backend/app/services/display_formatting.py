"""HighView Unified Semantic-Aware Numeric Display Formatter (Backend).

Provides a single shared display contract for compact, executive-grade number formatting
across Backend services, PPTX generation, and PDF generation.

Invariants:
- Underlying raw governed values remain 100% untouched.
- Semantic hashes and analytical provenance continue to use raw governed numbers.
- Non-aggregatable entities (IDs, years, postal codes, phone numbers, percentages) are NEVER compacted.
- Exact full values are preserved for accessible hover tooltips and audit inspection.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import math
import re
from typing import Any

# Canonical Currency Symbol Mapping
CURRENCY_SYMBOLS: dict[str, str] = {
    "USD": "$",
    "$": "$",
    "EUR": "€",
    "€": "€",
    "GBP": "£",
    "£": "£",
    "INR": "₹",
    "₹": "₹",
    "JPY": "¥",
    "¥": "¥",
    "CNY": "¥",
    "AUD": "A$",
    "CAD": "CA$",
    "CHF": "CHF",
    "AED": "AED",
    "SGD": "SGD",
    "HKD": "HK$",
    "NZD": "NZ$",
    "BRL": "R$",
    "SEK": "kr",
    "ZAR": "R",
}

FORBIDDEN_COMPACT_CLASSES = {
    "IDENTIFIER",
    "ENTITY_IDENTIFIER",
    "YEAR",
    "DATE",
    "TIME",
    "CODE",
    "POSTAL_CODE",
    "PHONE_NUMBER",
    "PERCENTAGE",
    "DURATION",
    "SCORE",
    "INDEX",
}

IDENTIFIER_TOKENS = {
    "id", "identifier", "code", "zip", "postal", "phone", "ssn", "ein", "itin",
    "uuid", "guid", "pin", "account_no", "acc_no", "sheet_id", "dataset_id", "evid"
}
YEAR_TOKENS = {"year", "yr", "fiscal_year", "fy", "calendar_year"}
PERCENT_TOKENS = {
    "pct", "percent", "percentage", "rate", "ratio", "compliance",
    "utilization", "yield", "margin", "share", "proportion"
}
DURATION_TOKENS = {
    "duration", "hours", "hrs", "minutes", "mins", "seconds", "secs",
    "days", "weeks", "months", "years_of_service", "tenure"
}
SCORE_TOKENS = {"score", "rating", "grade", "rank", "index", "plddt", "confidence", "probability"}


def parse_governed_number(val: Any) -> float | int | None:
    """Normalizes input value to a float or int if finite; otherwise None."""
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return None
        return val

    clean_str = str(val).replace(",", "").strip()
    if not clean_str or clean_str.lower() in ("nan", "infinity", "-infinity", "none", "null", "unavailable", "—"):
        return None

    # Strip currency symbol or percent suffix if present
    clean_str = re.sub(r"^[\$€£₹¥]\s*", "", clean_str)
    clean_str = re.sub(r"%\s*$", "", clean_str)

    try:
        if clean_str.lstrip("-").isdigit():
            return int(clean_str)
        f_val = float(clean_str)
        if math.isnan(f_val) or math.isinf(f_val):
            return None
        return f_val
    except (ValueError, TypeError):
        return None


def is_currency(unit: str = "", currency: str = "") -> bool:
    """Checks if unit or currency represents currency."""
    u = (currency or unit or "").upper().strip()
    if not u:
        return False
    return u in CURRENCY_SYMBOLS or u in {
        "USD", "EUR", "GBP", "INR", "JPY", "CNY", "AUD", "CAD", "CHF", "AED", "SGD", "$", "€", "£", "₹", "¥"
    }


def resolve_currency_format(unit: str = "", currency: str = "") -> tuple[str, bool, bool]:
    """Resolves currency symbol or prefix for a given currency code or unit.
    Returns: (symbol_or_code, is_prefix, is_code).
    """
    raw_code = (currency or unit or "").strip()
    upper_code = raw_code.upper()

    sym = CURRENCY_SYMBOLS.get(upper_code) or CURRENCY_SYMBOLS.get(raw_code)
    if sym:
        is_code = len(sym) >= 3 and sym.isalpha()
        return sym, True, is_code

    if len(upper_code) == 3 and upper_code.isalpha():
        return upper_code, True, True

    return raw_code, False, False


def is_compact_allowed(
    val: Any,
    unit: str = "",
    measure_class: str = "",
    semantic_role: str = "",
    metric_id: str = "",
    label: str = "",
    column_name: str = "",
    allow_compact: bool | None = None,
) -> bool:
    """Determines whether a measure is semantically eligible for compact K/M/B/T notation."""
    if allow_compact is False:
        return False

    m_class = str(measure_class or "").upper().strip()
    if m_class in FORBIDDEN_COMPACT_CLASSES:
        return False

    u = str(unit or "").strip()
    if "%" in u:
        return False

    role = str(semantic_role or "").lower().strip()
    if role in ("identifier", "dimension", "year", "date", "code"):
        return False

    combined_names = f"{metric_id} {label} {column_name}".strip().lower()
    tokens = set(re.split(r"[_\s\-]+", combined_names)) if combined_names else set()

    if tokens.intersection(IDENTIFIER_TOKENS):
        return False

    num = parse_governed_number(val)
    if num is not None and isinstance(num, int) and 1800 <= num <= 2200:
        if tokens.intersection(YEAR_TOKENS) or u.lower() in ("year", "yr"):
            return False

    has_curr = is_currency(unit=u)
    if not has_curr:
        if tokens.intersection(PERCENT_TOKENS):
            return False
        if tokens.intersection(DURATION_TOKENS):
            return False
        if tokens.intersection(SCORE_TOKENS):
            return False

    return True


def _format_clean_decimal(val: float, max_decimals: int) -> str:
    """Formats float up to max_decimals using ROUND_HALF_UP and strips unnecessary trailing zeroes."""
    try:
        d = Decimal(str(val))
    except Exception:
        d = Decimal(f"{val:.10f}")

    q_pattern = Decimal("1") if max_decimals == 0 else Decimal(f"1e-{max_decimals}")
    rounded = d.quantize(q_pattern, rounding=ROUND_HALF_UP)
    s = f"{rounded:f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def _format_compact_mantissa(num: float | int, max_decimals: int = 2) -> tuple[str, str]:
    """Formats number in compact K/M/B/T notation handling rollovers (e.g. 999,999 -> 1M)."""
    abs_v = abs(num)

    tiers = [
        (1e12, "T"),
        (1e9, "B"),
        (1e6, "M"),
        (1e3, "K"),
    ]

    for i, (divisor, suffix) in enumerate(tiers):
        if abs_v >= divisor:
            scaled = abs_v / divisor
            mantissa = _format_clean_decimal(scaled, max_decimals)

            # Check if rounded mantissa pushed to 1000 (e.g. 999.999 -> 1000)
            if float(mantissa) >= 1000.0 and i > 0:
                next_divisor, next_suffix = tiers[i - 1]
                next_scaled = abs_v / next_divisor
                return _format_clean_decimal(next_scaled, max_decimals), next_suffix

            return mantissa, suffix

    # Check rollover for values just below 1e3 (e.g. 999.999)
    scaled = abs_v / 1e3
    mantissa = _format_clean_decimal(scaled, max_decimals)
    if float(mantissa) >= 1.0:
        return mantissa, "K"

    # < 1000
    if isinstance(num, int) or (isinstance(num, float) and num.is_integer()):
        return f"{int(abs_v):,}", ""
    return _format_clean_decimal(abs_v, max_decimals), ""


def _apply_currency_and_unit(
    core_str: str,
    sign: str,
    unit: str,
    currency_info: tuple[str, bool, bool],
) -> str:
    """Attaches currency symbol or unit suffix cleanly without space collision."""
    symbol, is_prefix, is_code = currency_info
    if is_prefix:
        if is_code or (len(symbol) >= 3 and symbol.isalpha()):
            return f"{sign}{symbol} {core_str}"
        return f"{sign}{symbol}{core_str}"

    u = (unit or "").strip()
    if u.lower() in ("year", "yr"):
        return f"{sign}{core_str}"
    if u == "%":
        return f"{sign}{core_str}%"
    if u:
        return f"{sign}{core_str} {u}"
    return f"{sign}{core_str}"


def format_governed_number(
    value: Any,
    unit: str = "",
    currency: str = "",
    measure_class: str = "",
    semantic_role: str = "",
    metric_id: str = "",
    label: str = "",
    column_name: str = "",
    max_decimals: int = 2,
    allow_compact: bool | None = None,
    unavailable_label: str = "—",
) -> str:
    """Formats a governed numeric value into executive-grade display notation."""
    num = parse_governed_number(value)
    if num is None:
        return unavailable_label

    sign = "-" if num < 0 else ""
    abs_num = abs(num)

    currency_info = resolve_currency_format(unit=unit, currency=currency)
    eligible = is_compact_allowed(
        val=num,
        unit=unit,
        measure_class=measure_class,
        semantic_role=semantic_role,
        metric_id=metric_id,
        label=label,
        column_name=column_name,
        allow_compact=allow_compact,
    )

    if not eligible or abs_num < 1000:
        # Non-compacted number formatting
        if isinstance(num, int) or (isinstance(num, float) and num.is_integer()):
            combined = f"{metric_id} {label} {column_name}".strip().lower()
            tokens = set(re.split(r"[_\s\-]+", combined)) if combined else set()
            is_year_or_id = (
                measure_class in ("YEAR", "IDENTIFIER", "POSTAL_CODE")
                or str(unit).lower().strip() in ("year", "yr")
                or (1800 <= abs_num <= 2200 and tokens.intersection(YEAR_TOKENS))
                or tokens.intersection(IDENTIFIER_TOKENS)
            )
            # IDs without commas if postal or short code or year; otherwise standard thousands
            if measure_class in ("YEAR", "POSTAL_CODE") or str(unit).lower().strip() in ("year", "yr") or (1800 <= abs_num <= 2200 and tokens.intersection(YEAR_TOKENS)):
                formatted_num = str(int(abs_num))
            else:
                formatted_num = f"{int(abs_num):,}"
        else:
            formatted_num = _format_clean_decimal(float(abs_num), max_decimals)

        return _apply_currency_and_unit(formatted_num, sign, unit, currency_info)

    # Compact K/M/B/T formatting
    mantissa, suffix = _format_compact_mantissa(abs_num, max_decimals)
    compact_str = f"{mantissa}{suffix}"
    return _apply_currency_and_unit(compact_str, sign, unit, currency_info)


def format_exact_measure(
    value: Any,
    unit: str = "",
    currency: str = "",
    measure_class: str = "",
    semantic_role: str = "",
    metric_id: str = "",
    label: str = "",
    column_name: str = "",
    unavailable_label: str = "—",
) -> str:
    """Formats a governed value in full, unrounded/exact notation with standard thousands separators."""
    num = parse_governed_number(value)
    if num is None:
        return unavailable_label

    sign = "-" if num < 0 else ""
    abs_num = abs(num)
    str_val = str(abs_num).strip()

    combined = f"{metric_id} {label} {column_name}".strip().lower()
    tokens = set(re.split(r"[_\s\-]+", combined)) if combined else set()

    if (isinstance(num, float) and num.is_integer()) or isinstance(num, int):
        int_num = int(abs_num)
        is_year_or_postal = (
            measure_class in ("YEAR", "POSTAL_CODE")
            or str(unit).lower().strip() in ("year", "yr")
            or (1800 <= abs_num <= 2200 and tokens.intersection(YEAR_TOKENS))
        )
        formatted_num = str(int_num) if is_year_or_postal else f"{int_num:,}"
    elif "." in str_val:
        int_part, dec_part = str_val.split(".", 1)
        int_num = int(int_part)
        formatted_num = f"{int_num:,}.{dec_part}"
    else:
        is_year_or_postal = (
            measure_class in ("YEAR", "POSTAL_CODE")
            or str(unit).lower().strip() in ("year", "yr")
            or (1800 <= abs_num <= 2200 and tokens.intersection(YEAR_TOKENS))
        )
        formatted_num = str_val if is_year_or_postal else f"{int(abs_num):,}"

    currency_info = resolve_currency_format(unit=unit, currency=currency)
    return _apply_currency_and_unit(formatted_num, sign, unit, currency_info)
