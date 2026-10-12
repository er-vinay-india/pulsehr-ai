"""
Presentation Label and Title Utilities (Phase G5.1).

Provides deterministic label correction mechanics, underscore elimination,
and safe title construction without hardcoding or domain leakage.
"""
from __future__ import annotations

import re


def clean_metric_name(name: str) -> str:
    """Removes underscores, replaces kebab-case, and cleans metric labels into Title Case."""
    if not name:
        return ""
    # Replace underscores and hyphens with spaces
    cleaned = re.sub(r"[_\-]+", " ", str(name)).strip()
    # Normalize multiple whitespace
    cleaned = re.sub(r"\s+", " ", cleaned)
    # Title-case words while preserving well-known uppercase acronyms
    acronyms = {"id", "cpi", "aqi", "cpcb", "so2", "no2", "pm10", "pm2.5", "hr", "kpi", "ebitda", "cogs"}
    words = cleaned.split(" ")
    formatted_words = []
    for w in words:
        if w.lower() in acronyms:
            formatted_words.append(w.upper())
        else:
            formatted_words.append(w.capitalize())
    return " ".join(formatted_words)


def safe_title(title: str, domain: str | None = None) -> str:
    """Constructs clean executive-grade presentation titles with zero underscore leaks."""
    if not title:
        return "Executive Overview"
    clean = clean_metric_name(title)
    # Clean up common title suffixes
    clean = re.sub(r"\s+Vs\s+", " vs ", clean)
    clean = re.sub(r"\s+Over\s+", " over ", clean)
    clean = re.sub(r"\s+By\s+", " by ", clean)
    clean = re.sub(r"\s+And\s+", " & ", clean)
    return clean


def sanitize_axis_label(label: str) -> str:
    """Sanitizes raw dataframe columns for visual axis labels with zero underscore leakage."""
    return clean_metric_name(label)
