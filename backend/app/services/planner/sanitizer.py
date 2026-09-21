"""Sanitization utilities for untrusted spreadsheet contents."""

import re
from typing import Any


def sanitize_untrusted_text(text: Any, max_len: int = 120) -> str:
    """Sanitizes untrusted spreadsheet cell contents to prevent prompt or layout injection."""
    if text is None:
        return ""
    s = str(text).strip()
    # Strip potential prompt injection prefixes or instruction delimiters
    s = re.sub(r'[\r\n\t]+', ' ', s)
    s = re.sub(r'(?i)\b(ignore|instructions?|prompts?|assistants?|overrides?|systems?|commands?|bypasses?)\b', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    if len(s) > max_len:
        return s[:max_len - 3] + "..."
    return s
