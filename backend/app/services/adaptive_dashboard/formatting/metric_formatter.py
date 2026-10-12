"""
Metric Formatter and Numerical Utilities (Phase G5.1).

Extracts pure formatting, date arithmetic, duration scaling, and quantile calculation
utilities out of adaptive_dashboard/engine.py into a cohesive, zero-dependency contract.
"""
from __future__ import annotations

import calendar
import hashlib
import json
import math
import re
from typing import Any


def compute_source_snapshot(sheet_id: int, columns: list[str], rows: list[dict[str, Any]]) -> str:
    """Computes a deterministic cryptographic hash of sheet schema and all row values."""
    hasher = hashlib.sha256()
    hasher.update(str(sheet_id).encode("utf-8"))
    hasher.update(json.dumps(columns, sort_keys=True).encode("utf-8"))
    for r in rows:
        hasher.update(json.dumps(r, sort_keys=True, default=str).encode("utf-8"))
    return hasher.hexdigest()[:16]


def parse_date_safe(val: Any) -> tuple[int, int, int] | None:
    """Robustly parse date string in ISO (YYYY-MM-DD), European (DD-MM-YYYY), US (MM/DD/YYYY) into (year, month, day)."""
    if not val:
        return None
    s = str(val).strip().split("T")[0].split(" ")[0]
    # 1. YYYY-MM-DD or YYYY/MM/DD
    m1 = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$", s)
    if m1:
        y, m, d = int(m1.group(1)), int(m1.group(2)), int(m1.group(3))
        if 1 <= m <= 12 and 1 <= d <= 31:
            try:
                max_d = calendar.monthrange(y, m)[1]
                if d <= max_d:
                    return (y, m, d)
            except Exception:
                pass

    # 2. DD-MM-YYYY or MM-DD-YYYY or DD/MM/YYYY or MM/DD/YYYY
    m2 = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$", s)
    if m2:
        p1, p2, y = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
        if p1 > 12 and 1 <= p2 <= 12:
            d, m = p1, p2
        elif p2 > 12 and 1 <= p1 <= 12:
            m, d = p1, p2
        else:
            d, m = p1, p2
        if 1 <= m <= 12 and 1 <= d <= 31:
            try:
                max_d = calendar.monthrange(y, m)[1]
                if d <= max_d:
                    return (y, m, d)
            except Exception:
                pass
    return None


def parse_iso_date(val: Any) -> tuple[int, int, int] | None:
    """Parse strictly ISO format (YYYY-MM-DD)."""
    return parse_date_safe(val)


def parse_date_range(rows: list[dict[str, Any]], date_col: str | None) -> dict[str, Any] | None:
    """Calculates min date, max date, distinct date count and row record count."""
    if not date_col or not rows:
        return None
    dates = []
    for r in rows:
        val = r.get(date_col)
        parsed = parse_date_safe(val)
        if parsed:
            y, m, d = parsed
            dates.append(f"{y:04d}-{m:02d}-{d:02d}")
        elif val is not None and str(val).strip():
            dates.append(str(val).strip())
    if not dates:
        return None
    sorted_dates = sorted(dates)
    return {
        "start": sorted_dates[0],
        "end": sorted_dates[-1],
        "distinct_dates": len(set(dates)),
        "total_records": len(dates),
    }


def format_currency_short(val: float) -> str:
    """Format large currency values into $X.XXB, $X.XXM, $X.XK or $X."""
    abs_v = abs(val)
    prefix = "-" if val < 0 else ""
    if abs_v >= 1_000_000_000:
        return f"{prefix}${abs_v / 1_000_000_000:.2f}B"
    elif abs_v >= 1_000_000:
        val_m = abs_v / 1_000_000
        return f"{prefix}${val_m:.2f}M" if (val_m * 10) % 1 != 0 else f"{prefix}${val_m:.1f}M"
    elif abs_v >= 1_000:
        return f"{prefix}${abs_v / 1_000:.0f}K"
    else:
        return f"{prefix}${abs_v:,.0f}"


def format_percentage(val: float, decimals: int = 1) -> str:
    """Format floating value as percentage string."""
    return f"{val:.{decimals}f}%"


def format_compact_number(val: float | int) -> str:
    """Format numbers into K, M, B compact representation."""
    abs_v = abs(val)
    prefix = "-" if val < 0 else ""
    if abs_v >= 1_000_000_000:
        return f"{prefix}{abs_v / 1_000_000_000:.1f}B"
    elif abs_v >= 1_000_000:
        return f"{prefix}{abs_v / 1_000_000:.1f}M"
    elif abs_v >= 1_000:
        return f"{prefix}{abs_v / 1_000:.1f}K"
    return f"{prefix}{val:,.0f}" if isinstance(val, int) or val.is_integer() else f"{prefix}{val:,.1f}"


def format_duration_short(val: float) -> str:
    """Format hours or minutes into human-readable compact string."""
    if val >= 24:
        days = val / 24
        return f"{days:.1f}d"
    elif val >= 1:
        return f"{val:.1f}h"
    else:
        mins = val * 60
        return f"{mins:.0f}m"


def format_month_label(ym: str) -> str:
    """Format '2023-01' to 'Jan 2023'."""
    try:
        y, m = ym.split("-")
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        idx = int(m) - 1
        if 0 <= idx < 12:
            return f"{month_names[idx]} {y}"
    except Exception:
        pass
    return ym


def format_month_tick(ym: str) -> str:
    """Format '2023-01' to 'Jan ’23'."""
    try:
        y, m = ym.split("-")
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        idx = int(m) - 1
        short_y = y[2:] if len(y) == 4 else y
        if 0 <= idx < 12:
            return f"{month_names[idx]} ’{short_y}"
    except Exception:
        pass
    return ym


def calendar_month_range(start_ym: str, end_ym: str) -> list[str]:
    """Generates contiguous list of 'YYYY-MM' strings between start_ym and end_ym inclusive."""
    try:
        sy, sm = (int(x) for x in start_ym.split("-")[:2])
        ey, em = (int(x) for x in end_ym.split("-")[:2])
        months = []
        cy, cm = sy, sm
        while (cy < ey) or (cy == ey and cm <= em):
            months.append(f"{cy:04d}-{cm:02d}")
            cm += 1
            if cm > 12:
                cm = 1
                cy += 1
        return months
    except Exception:
        return [start_ym, end_ym] if start_ym != end_ym else [start_ym]


def parse_clock_interval(val: Any) -> tuple[int | None, str, tuple[int, int, int, int] | None]:
    """Parse clock interval string (HH:MM-HH:MM or HH:MM–HH:MM) to positive elapsed duration in minutes.

    Returns (duration_minutes, status, normalized_endpoints).
    normalized_endpoints is (start_h, start_m, end_h, end_m) or None.
    Status is one of:
      - 'valid'
      - 'blank'
      - 'malformed'
      - 'invalid_time'
      - 'overnight_or_zero'
    """
    if val is None:
        return None, "blank", None
    s_val = str(val).strip()
    if not s_val:
        return None, "blank", None

    m = re.match(r"^(\d{1,2}):(\d{2})\s*[-–—]\s*(\d{1,2}):(\d{2})$", s_val)
    if not m:
        return None, "malformed", None

    sh, sm, eh, em = map(int, m.groups())
    if not (0 <= sh <= 23 and 0 <= sm <= 59 and 0 <= eh <= 23 and 0 <= em <= 59):
        return None, "invalid_time", None

    start_mins = sh * 60 + sm
    end_mins = eh * 60 + em
    if end_mins <= start_mins:
        # Same-day positive intervals only. Overnight wrap or equal times are unresolved in this slice.
        return None, "overnight_or_zero", None

    return end_mins - start_mins, "valid", (sh, sm, eh, em)


def linear_quantile(values: list[int | float], p: float) -> float:
    """Computes linear quantile for a list of numbers using h = (n - 1) * p.

    Interpolates linearly between surrounding order statistics.
    """
    if not values:
        raise ValueError("Cannot compute quantile of empty list")
    s = sorted(values)
    n = len(s)
    if n == 1:
        return float(s[0])
    h = (n - 1) * p
    i = int(h)
    r = h - i
    if i >= n - 1:
        return float(s[-1])
    return float(s[i] + r * (s[i + 1] - s[i]))


def compute_focused_duration_scale(
    plotted_values_minutes: list[float],
) -> tuple[float, float, list[float], list[str], bool]:
    """Computes a unit-aware, readable duration axis scale (min, max, ticks, tick_labels, is_focused).

    Returns (y_min_hours, y_max_hours, tick_values_hours, tick_labels, is_focused_scale).
    """
    if not plotted_values_minutes:
        return 0.0, 10.0, [0.0, 2.0, 4.0, 6.0, 8.0, 10.0], ["0h", "2h", "4h", "6h", "8h", "10h"], False

    v_min = min(plotted_values_minutes)
    v_max = max(plotted_values_minutes)

    span = v_max - v_min
    if span < 60.0:
        mid = (v_min + v_max) / 2.0
        v_min = mid - 30.0
        v_max = mid + 30.0
        span = 60.0

    if span <= 120.0:
        step = 15.0
    elif span <= 240.0:
        step = 30.0
    elif span <= 480.0:
        step = 60.0
    else:
        step = 120.0

    min_mins = math.floor((v_min - step) / step) * step
    if min_mins < 0.0:
        min_mins = 0.0
    max_mins = math.ceil((v_max + step) / step) * step

    num_intervals = int(round((max_mins - min_mins) / step))
    if num_intervals > 8:
        if step == 15.0:
            step = 30.0
        elif step == 30.0:
            step = 60.0
        elif step == 60.0:
            step = 120.0
        min_mins = math.floor((v_min - step) / step) * step
        if min_mins < 0.0:
            min_mins = 0.0
        max_mins = math.ceil((v_max + step) / step) * step

    ticks_hours = []
    tick_labels = []
    curr = min_mins
    while curr <= max_mins + 0.01:
        ticks_hours.append(round(curr / 60.0, 3))
        h_val = int(curr // 60)
        m_val = int(round(curr % 60))
        if m_val == 60:
            h_val += 1
            m_val = 0
        if m_val == 0:
            tick_labels.append(f"{h_val}h")
        else:
            tick_labels.append(f"{h_val}h {m_val:02d}m")
        curr += step

    y_min_hours = round(min_mins / 60.0, 3)
    y_max_hours = round(max_mins / 60.0, 3)
    is_focused = (min_mins > 0.0)

    return y_min_hours, y_max_hours, ticks_hours, tick_labels, is_focused


def compute_numeric_focused_scale(
    plotted_values: list[float],
    is_currency: bool = False,
    unit_symbol: str = "$",
) -> tuple[float, float, list[float], list[str], bool]:
    """Computes a unit-aware readable numeric scale with nice tick intervals and labels.

    Returns (y_min, y_max, ticks, tick_labels, is_focused_scale).
    """
    if not plotted_values:
        return 0.0, 100.0, [0.0, 20.0, 40.0, 60.0, 80.0, 100.0], ["0", "20", "40", "60", "80", "100"], False

    v_min = min(plotted_values)
    v_max = max(plotted_values)

    span = v_max - v_min
    if span <= 0:
        span = abs(v_max) if v_max != 0 else 10.0

    raw_step = span / 5.0
    exponent = math.floor(math.log10(raw_step))
    fraction = raw_step / (10 ** exponent)

    if fraction < 1.5:
        nice_fraction = 1.0
    elif fraction < 3.0:
        nice_fraction = 2.0
    elif fraction < 7.0:
        nice_fraction = 5.0
    else:
        nice_fraction = 10.0

    step = nice_fraction * (10 ** exponent)

    if v_min >= 0 and (v_min - step <= 0 or span > 0.7 * v_max):
        min_val = 0.0
    else:
        min_val = math.floor((v_min - (step * 0.5)) / step) * step
        if v_min >= 0 and min_val < 0:
            min_val = 0.0

    max_val = math.ceil((v_max + (step * 0.5)) / step) * step

    ticks: list[float] = []
    tick_labels: list[str] = []
    curr = min_val
    max_iter = 25
    while curr <= max_val + (step * 0.01) and max_iter > 0:
        val = round(curr, 4)
        ticks.append(val)
        if is_currency:
            tick_labels.append(format_currency_short(val))
        else:
            if step >= 1:
                tick_labels.append(f"{int(round(val)):,}")
            else:
                tick_labels.append(f"{val:,.2f}")
        curr += step
        max_iter -= 1

    is_focused = (min_val > 0.0)
    return round(min_val, 4), round(max_val, 4), ticks, tick_labels, is_focused


class MetricFormatter:
    """Unified static facade for pure metric and numerical formatting."""
    format_currency_short = staticmethod(format_currency_short)
    format_percentage = staticmethod(format_percentage)
    format_compact_number = staticmethod(format_compact_number)
    format_duration_short = staticmethod(format_duration_short)
    format_month_label = staticmethod(format_month_label)
    format_month_tick = staticmethod(format_month_tick)
    calendar_month_range = staticmethod(calendar_month_range)
    parse_date_safe = staticmethod(parse_date_safe)
    parse_iso_date = staticmethod(parse_iso_date)
    parse_date_range = staticmethod(parse_date_range)
    parse_clock_interval = staticmethod(parse_clock_interval)
    linear_quantile = staticmethod(linear_quantile)
    compute_focused_duration_scale = staticmethod(compute_focused_duration_scale)
    compute_numeric_focused_scale = staticmethod(compute_numeric_focused_scale)
    compute_source_snapshot = staticmethod(compute_source_snapshot)
