"""Centralized Display-Label Formatter & Analytical Title Engine.

Standardizes user-facing labels and analytical titles across the application:
1. Converts snake_case, kebab-case, and camelCase into natural readable words.
2. Applies sentence case consistently (first letter capitalized, rest lowercase).
3. Preserves recognized industrial, economic, and technical acronyms in uppercase.
4. Generates concise, objective analytical titles free of unproven causal claims.
5. Keeps original database identifiers untouched for queries, joins, and calculations.
"""

import re
from typing import Any

# Recognized industrial, economic, financial, and organizational acronyms
RECOGNIZED_ACRONYMS = {
    'HR',
    'ID',
    'KPI',
    'FTE',
    'USD',
    'CPI',
    'OLS',
    'AI',
    'IT',
    'GE',
    'CEO',
    'CFO',
    'CPO',
    'CTO',
    'ROI',
    'YTD',
    'Q1',
    'Q2',
    'Q3',
    'Q4',
    'P&L',
    'SLA',
}

# Explicit dataset-specific column overrides (for non-standard or domain-specific names)
SPECIAL_DISPLAY_OVERRIDES: dict[str, str] = {
    'cpi': 'CPI',
    'cpi_index': 'CPI index',
    'weekly_sales': 'Weekly sales',
    'holiday_flag': 'Holiday flag',
    'fuel_price': 'Fuel price',
    'unemployment': 'Unemployment',
    'store': 'Store',
    'date': 'Date',
    'temperature': 'Temperature',
    'dept': 'Department',
    'department': 'Department',
    'fte': 'FTE',
    'kpi': 'KPI',
    'ols': 'OLS',
}


def format_display_label(raw_name: Any) -> str:
    """Converts raw column / identifier name into clean sentence-cased display label.

    Preserves recognized acronyms in UPPERCASE and handles snake_case, camelCase,
    and kebab-case cleanly.
    """
    if raw_name is None:
        return ''

    text = str(raw_name).strip()
    if not text:
        return ''

    # Handle prefixed names like 'left.Weekly_Sales' or 'right.Store'
    prefix = ''
    if '.' in text and not text.replace('.', '').isdigit():
        parts = text.split('.', 1)
        prefix = parts[0] + ' '
        text = parts[1]

    lower_key = text.lower().replace(' ', '_').replace('-', '_')
    if lower_key in SPECIAL_DISPLAY_OVERRIDES:
        result = SPECIAL_DISPLAY_OVERRIDES[lower_key]
        return f"{prefix}{result}".strip()

    # CamelCase splitting: e.g. "employeeID" -> "employee ID", "monthlySales" -> "monthly Sales"
    s1 = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', text)
    s2 = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', s1)

    # Replace underscores and hyphens with space
    normalized = re.sub(r'[_\\-]+', ' ', s2).strip()

    # Split into individual word tokens
    tokens = normalized.split()
    if not tokens:
        return text

    processed_tokens = []
    for token in tokens:
        # Strip outer punctuation for check
        clean_token = token.strip('.,:;()[]')
        token_upper = clean_token.upper()

        if token_upper in RECOGNIZED_ACRONYMS:
            # Preserve acronym casing, maintaining any surrounding punctuation
            processed_tokens.append(token.replace(clean_token, token_upper))
        else:
            processed_tokens.append(token.lower())

    joined = ' '.join(processed_tokens)
    if not joined:
        return text

    # Sentence case: capitalize only the very first character of the full string
    # If the first token is already an acronym (e.g. CPI), preserve it
    first_token_clean = tokens[0].strip('.,:;()[]').upper()
    if first_token_clean in RECOGNIZED_ACRONYMS:
        final_str = joined
    else:
        final_str = joined[0].upper() + joined[1:]

    return f"{prefix}{final_str}".strip()


def generate_analytical_title(
    calc_type: str,
    metric_col: str,
    group_col: str | None = None,
    comparison_type: str | None = None,
    total_count: int | None = None
) -> tuple[str, str]:
    """Generates concise, objective, sentence-cased analytical title and subtitle pairs.

    Replaces redundant prefixes ("Comparison of") and unproven causal phrasing ("Impact").
    """
    m_label = format_display_label(metric_col)
    m_lower = m_label if m_label in RECOGNIZED_ACRONYMS else m_label.lower()

    # 1. Categorical Composition / Donut Chart
    if comparison_type == 'donut' or calc_type.lower() in ('distribution', 'composition', 'share'):
        if group_col and 'holiday' in group_col.lower():
            title = "Distribution: Holiday vs non-holiday"
            subtitle = f"Proportional composition across {total_count or 'all'} recorded periods"
        elif group_col:
            g_label = format_display_label(group_col)
            title = f"Distribution by {g_label.lower()}"
            subtitle = f"Proportional composition across {total_count or 'all'} recorded entities"
        else:
            title = f"Distribution of {m_lower}"
            subtitle = "Proportional composition across recorded categories"
        return title, subtitle

    # 2. Binary Flag / Seasonal Comparison (e.g. Holiday Weeks vs Regular Weeks)
    if comparison_type == 'binary_flag' or (group_col and ('holiday' in group_col.lower() or 'flag' in group_col.lower())):
        g_clean = (group_col or '').lower()
        if 'holiday' in g_clean:
            title = f"Average {m_lower}: Holiday vs non-holiday"
            subtitle = "Average comparison between holiday and regular weeks"
        else:
            g_label = format_display_label(group_col)
            title = f"Average {m_lower}: {g_label} comparison"
            subtitle = f"Performance comparison segmented by {g_label.lower()}"
        return title, subtitle

    # 3. Sequential Trend / Time-Series Line Chart
    if comparison_type == 'time_series' or (group_col and any(k in group_col.lower() for k in ('date', 'time', 'week', 'month', 'year'))):
        is_total = 'total' in calc_type.lower() or 'sum' in calc_type.lower()
        agg_desc = "Total network" if is_total else "Average"
        title = f"{agg_desc} {m_lower} over time"
        if total_count:
            subtitle = f"Longitudinal progression across {total_count} recorded periods"
        else:
            subtitle = "Longitudinal progression across recorded periods"
        return title, subtitle

    # 4. Standard Categorical Bar Chart (Rankings, Means & Sums)
    if group_col:
        g_label = format_display_label(group_col)
        g_lower = g_label if g_label in RECOGNIZED_ACRONYMS else g_label.lower()

        is_total = 'total' in calc_type.lower() or 'sum' in calc_type.lower()
        measure_word = "Total" if is_total else "Average"

        title = f"{measure_word} {m_lower} by {g_lower}"
        if total_count:
            subtitle = f"Ranked across {total_count} {g_lower} entities by {measure_word.lower()} {m_lower}"
        else:
            subtitle = f"Ranked by {measure_word.lower()} {m_lower}"
        return title, subtitle

    # Fallback default
    title = f"{calc_type.capitalize()} {m_lower}"
    subtitle = f"Calculated {calc_type.lower()} across evaluated records"
    return title, subtitle


def sanitize_llm_text(text: str, column_mapping: dict[str, str] | None = None) -> str:
    """Replaces raw column identifiers with display labels in user-facing LLM prose.

    Avoids replacing inside markdown code blocks, backticks, or URLs.
    """
    if not text or not column_mapping:
        return text

    # Split text by code blocks to avoid corrupting code or SQL
    parts = re.split(r'(```[\s\S]*?```|`[^`]+`)', text)
    result_parts = []

    for part in parts:
        if part.startswith('`'):
            result_parts.append(part)
        else:
            clean_part = part
            for raw_col, display_label in column_mapping.items():
                if raw_col in clean_part and raw_col != display_label:
                    # Match exact word boundaries
                    pattern = re.compile(rf'\b{re.escape(raw_col)}\b')
                    clean_part = pattern.sub(display_label, clean_part)
            result_parts.append(clean_part)

    return ''.join(result_parts)
