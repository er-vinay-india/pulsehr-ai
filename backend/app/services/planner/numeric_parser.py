"""Numeric series parsing and unit detection for uncleaned spreadsheet columns."""

import pandas as pd


def parse_numeric_series(series: pd.Series) -> tuple[pd.Series, str | None]:
    """Extracts clean floats and unit metadata from numeric-like string series."""
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors='coerce'), None

    cleaned = series.astype(str).str.strip()
    unit = None

    # Currency
    if cleaned.str.contains(r'[\$€£]').any():
        for cur in ('$', '€', '£'):
            if cleaned.str.startswith(cur).any():
                unit = cur
                cleaned = cleaned.str.replace(cur, '', regex=False)
                break

    # Percentage
    if cleaned.str.endswith('%').any():
        unit = '%'
        cleaned = cleaned.str.rstrip('%')

    # Commas in numbers
    cleaned = cleaned.str.replace(',', '', regex=False)

    # Ratings like "4.5/5.0"
    rating_split = cleaned.str.extract(r'^([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*/\s*(\d+(?:\.\d*)?)$')
    if rating_split[0].notna().sum() > len(cleaned) * 0.3:
        cleaned = rating_split[0]
        denom = rating_split[1].dropna().iloc[0] if len(rating_split[1].dropna()) else "5"
        unit = f"out of {denom}"

    numeric = pd.to_numeric(cleaned, errors='coerce')
    return numeric, unit
