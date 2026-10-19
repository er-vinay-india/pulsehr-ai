"""
HighView Semantic Data Refinery — Phase SDR-4G
Geographic Normalizer (GEO-1)

Deterministic normalization of geographic strings prior to reference matching.
Handles Unicode normalization, punctuation cleaning, country aliases, and abbreviations.
Avoids unsafe global abbreviation expansion.
"""

from __future__ import annotations

import re
import unicodedata


RE_WHITESPACE = re.compile(r"\s+")
RE_SAFE_PUNCT = re.compile(r"[.,'\"`()\[\]{}]")

# Words that coincide with 2-letter state or country codes
AMBIGUOUS_SHORT_WORDS = {"IN", "OR", "ME", "GA", "CA", "IS", "TO", "IT", "NO", "SO", "AT", "BY", "OF", "ON"}

# Canonical country code alias map
COUNTRY_ALIASES = {
    "usa": "US",
    "u.s.a.": "US",
    "united states": "US",
    "united states of america": "US",
    "us": "US",
    "uk": "GB",
    "u.k.": "GB",
    "united kingdom": "GB",
    "great britain": "GB",
    "britain": "GB",
    "ind": "IN",
    "india": "IN",
    "bharat": "IN",
    "in": "IN",
    "aus": "AU",
    "australia": "AU",
    "fra": "FR",
    "france": "FR",
    "jpn": "JP",
    "japan": "JP",
    "sgp": "SG",
    "singapore": "SG",
    "deu": "DE",
    "germany": "DE",
    "deutschland": "DE",
    "can": "CA",
    "canada": "CA",
}


def normalize_geo_text(raw_text: str | None) -> str:
    """
    Deterministically normalizes a geographic token:
    - Unicode NFC normalization
    - Trim leading/trailing whitespace
    - Collapse multiple whitespace to single space
    - Remove safe boundary punctuation while preserving hyphens
    """
    if raw_text is None:
        return ""

    text = str(raw_text).strip()
    if not text:
        return ""

    # 1. Unicode NFC
    text = unicodedata.normalize("NFC", text)

    # 2. Punctuation removal for acronyms/abbreviations (U.S.A. -> USA)
    text = RE_SAFE_PUNCT.sub("", text)

    # 3. Collapse whitespace
    text = RE_WHITESPACE.sub(" ", text).strip()

    return text


def normalize_for_lookup(raw_text: str | None) -> str:
    """Returns lowercased normalized string for index lookup."""
    return normalize_geo_text(raw_text).lower()


def is_ambiguous_short_code(token: str) -> bool:
    """
    Checks if a 2-letter uppercase token coincides with common English words
    (e.g. 'IN', 'OR', 'ME', 'GA', 'CA').
    Requires explicit geographic column context to interpret as a location.
    """
    return token.strip().upper() in AMBIGUOUS_SHORT_WORDS
