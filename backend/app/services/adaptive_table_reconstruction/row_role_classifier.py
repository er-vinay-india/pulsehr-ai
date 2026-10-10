"""RowRoleClassifier & StructuralComplexityEvaluator:

Computes 12 structural features per row and classifies physical rows into typed roles:
DOCUMENT_METADATA, TITLE, HEADER, HEADER_CONTINUATION, DATA, DATA_CONTINUATION,
PAGE_HEADER, FOOTNOTE, SENTINEL_DEFINITION, BLANK_SEPARATOR, UNKNOWN.

Evaluates overall table structural complexity score (0.00 - 1.00) to gate fast deterministic vs.
reconstructive pipelines.
"""

import math
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from .contracts import (
    RowRole,
    RowRoleDecision,
    StructuralComplexityScore,
)
from .grid_capture import RawGrid


HEADER_KEYWORDS = {
    "id", "no", "no.", "sr", "sr.", "sno", "s.no", "name", "code", "date", "year", "month", "day",
    "total", "average", "avg", "mean", "rate", "status", "count", "pct", "percent", "percentage",
    "value", "amount", "score", "category", "type", "state", "city", "town", "country", "region",
    "department", "dept", "employee", "staff", "customer", "product", "unit", "level", "standard",
    "annual", "approved", "monitored", "target", "actual", "variance", "description", "details", "data",
}

SENTINEL_REGEX = re.compile(
    r'^\s*["\']?([A-Za-z0-9_\*\-\#]+)["\']?\s*(?:[:=]|\s-\s|-)\s*(.+)$',
    re.IGNORECASE,
)

SENTINEL_KEYWORDS = {
    "no data", "inadequate data", "not monitored", "not available", "not applicable",
    "na", "n/a", "nil", "none", "missing", "confidential", "under review", "provisional",
}


def is_numeric_str(s: str) -> bool:
    if not s:
        return False
    s_clean = s.replace(",", "").replace("%", "").strip()
    try:
        float(s_clean)
        return True
    except ValueError:
        return False


def is_sequence_id_str(s: str) -> bool:
    s_clean = s.strip().rstrip(".")
    return bool(re.match(r"^\d{1,7}$", s_clean))


class RowRoleClassifier:
    """Classifies row roles and calculates table structural complexity."""

    @classmethod
    def evaluate_complexity(cls, grid: RawGrid) -> StructuralComplexityScore:
        """Evaluates whether the file is a clean 1-header table or requires adaptive reconstruction."""
        if grid.raw_row_count == 0 or grid.raw_col_count == 0:
            return StructuralComplexityScore(
                score=0.0,
                is_complex=False,
                recommended_pipeline="FAST_DETERMINISTIC",
                factors={"empty": 0.0},
            )

        features = [cls.extract_features(grid, r) for r in range(grid.raw_row_count)]
        factors: Dict[str, float] = {}

        # 1. Preamble factor: Are rows 0..2 non-tabular or sparse?
        first_row = features[0]
        has_preamble = False
        if first_row["non_empty_ratio"] < 0.5 or first_row["text_ratio"] < 0.5:
            has_preamble = True
            factors["preamble_present"] = 0.25

        # 2. Multi-row header factor: Are there multiple rows before data with text?
        candidate_headers = 0
        for f in features[:10]:
            if f["non_empty_count"] > 0 and f["numeric_ratio"] == 0 and f["header_keyword_score"] > 0:
                candidate_headers += 1
        if candidate_headers > 1:
            factors["multi_row_headers"] = 0.30

        # 3. Sparse data rows (wrapped record candidates)
        sparse_middle_rows = 0
        for r in range(1, grid.raw_row_count - 1):
            f = features[r]
            if 0 < f["non_empty_count"] < grid.raw_col_count and not f["has_sequence_id"]:
                prev_cnt = features[r - 1]["non_empty_count"]
                next_cnt = features[r + 1]["non_empty_count"]
                if f["non_empty_count"] < max(prev_cnt, next_cnt):
                    sparse_middle_rows += 1
        if sparse_middle_rows > 0:
            factors["wrapped_sparse_rows"] = min(0.35, 0.20 + (sparse_middle_rows * 0.05))

        # 4. Footnote / Sentinel definitions at the bottom
        has_footers = False
        for f in features[-5:]:
            if f["footnote_sentinel_pattern"] and not f["has_sequence_id"]:
                has_footers = True
                factors["sentinel_definitions"] = 0.25
                break

        # 5. Repeated metadata / page headers (e.g. repeated strings every N rows)
        first_row_non_empty = [c for c in grid.get_row(0) if c.strip()]
        if first_row_non_empty:
            watermark_token = first_row_non_empty[0]
            watermark_repeats = 0
            for r in range(5, grid.raw_row_count - 5):
                if watermark_token in grid.get_row(r):
                    watermark_repeats += 1
            if watermark_repeats > 0:
                factors["repeated_page_headers"] = 0.20

        total_score = min(1.0, sum(factors.values()))
        is_complex = total_score >= 0.25

        recommended = "FAST_DETERMINISTIC"
        if total_score >= 0.80:
            recommended = "ESCALATED"
        elif total_score >= 0.60:
            recommended = "MODEL_ASSISTED"
        elif total_score >= 0.25:
            recommended = "VALIDATED_DETERMINISTIC"

        return StructuralComplexityScore(
            score=round(total_score, 2),
            is_complex=is_complex,
            recommended_pipeline=recommended,
            factors=factors,
        )

    @classmethod
    def extract_features(cls, grid: RawGrid, row_idx: int) -> Dict[str, Any]:
        """Extracts 12 structural features for a row."""
        row = grid.get_row(row_idx)
        non_empty = [c.strip() for c in row if c.strip()]
        total_cols = grid.raw_col_count or 1

        non_empty_count = len(non_empty)
        non_empty_ratio = non_empty_count / total_cols

        numeric_count = sum(1 for c in non_empty if is_numeric_str(c))
        numeric_ratio = (numeric_count / non_empty_count) if non_empty_count else 0.0
        text_ratio = 1.0 - numeric_ratio if non_empty_count else 0.0

        # Leading blanks
        leading_blank_count = 0
        for c in row:
            if not c.strip():
                leading_blank_count += 1
            else:
                break

        # Trailing blanks
        trailing_blank_count = 0
        for c in reversed(row):
            if not c.strip():
                trailing_blank_count += 1
            else:
                break

        # Sequence ID in first non-empty cell
        has_sequence_id = False
        if non_empty:
            first_val = non_empty[0]
            # Must be in col 0 or 1
            first_col = next((i for i, c in enumerate(row) if c.strip()), -1)
            if first_col in (0, 1) and is_sequence_id_str(first_val):
                has_sequence_id = True

        # Alpha fragment pattern (incomplete word fragment)
        alpha_fragment_ratio = 0.0
        if non_empty:
            fragment_count = 0
            for c in non_empty:
                # E.g. starts with lowercase, or ends with dangling slash/hyphen, or no spaces in long partial word
                if re.match(r"^[a-z]{2,15}$", c) or c.endswith(("/", "-", "&")) or c.startswith(("&", "and ")):
                    fragment_count += 1
            alpha_fragment_ratio = fragment_count / non_empty_count

        # Header keyword score
        header_keyword_score = 0
        for c in non_empty:
            tokens = re.findall(r"[A-Za-z0-9]+", c.lower())
            if any(t in HEADER_KEYWORDS for t in tokens):
                header_keyword_score += 1

        # Repeated string score (matches row 0 tokens)
        row_0_tokens = set(re.findall(r"[A-Za-z0-9\-\/]{4,}", " ".join(grid.get_row(0)).lower()))
        current_tokens = set(re.findall(r"[A-Za-z0-9\-\/]{4,}", " ".join(row).lower()))
        repeated_string_score = len(row_0_tokens.intersection(current_tokens)) if row_0_tokens and row_idx > 0 else 0

        # Footnote / sentinel pattern
        footnote_sentinel_pattern = False
        if non_empty and not has_sequence_id:
            line_str = " ".join(non_empty)
            m = SENTINEL_REGEX.match(line_str)
            if m:
                right_text = m.group(2).lower()
                if any(re.search(r'\b' + re.escape(kw) + r'\b', right_text, re.IGNORECASE) for kw in SENTINEL_KEYWORDS):
                    footnote_sentinel_pattern = True
            if not footnote_sentinel_pattern:
                if any(re.search(r'\b' + re.escape(kw) + r'\b', line_str, re.IGNORECASE) for kw in SENTINEL_KEYWORDS) and non_empty_count <= 2:
                    footnote_sentinel_pattern = True
                elif (line_str.lower().startswith("note:") or line_str.lower().startswith("*") or line_str.lower().startswith("#")) and non_empty_count <= 2:
                    footnote_sentinel_pattern = True

        # Cell length entropy
        lengths = [len(c) for c in non_empty]
        if lengths:
            avg_len = sum(lengths) / len(lengths)
            var_len = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)
            cell_length_entropy = round(math.sqrt(var_len), 2)
        else:
            cell_length_entropy = 0.0

        return {
            "row_index": row_idx,
            "non_empty_count": non_empty_count,
            "non_empty_ratio": round(non_empty_ratio, 3),
            "numeric_ratio": round(numeric_ratio, 3),
            "text_ratio": round(text_ratio, 3),
            "leading_blank_count": leading_blank_count,
            "trailing_blank_count": trailing_blank_count,
            "has_sequence_id": has_sequence_id,
            "alpha_fragment_ratio": round(alpha_fragment_ratio, 3),
            "header_keyword_score": header_keyword_score,
            "repeated_string_score": repeated_string_score,
            "footnote_sentinel_pattern": footnote_sentinel_pattern,
            "cell_length_entropy": cell_length_entropy,
        }

    @classmethod
    def classify_all_rows(cls, grid: RawGrid) -> List[RowRoleDecision]:
        """Classifies each row into its typed role with provenance reasoning."""
        if grid.raw_row_count == 0:
            return []

        features = [cls.extract_features(grid, r) for r in range(grid.raw_row_count)]
        total_rows = grid.raw_row_count
        decisions: List[RowRoleDecision] = []

        # Find watermark / repeating page header tokens
        row_0_non_empty = [c for c in grid.get_row(0) if c.strip()]
        watermark_token = row_0_non_empty[0] if row_0_non_empty else ""

        # Identify data boundary and header block
        # Step A: Find the primary candidate header row where table width begins
        primary_header_idx = -1
        for idx in range(total_rows):
            f = features[idx]
            if f["non_empty_count"] >= max(2, int(grid.raw_col_count * 0.5)):
                row_cells = [c.strip() for c in grid.get_row(idx) if c.strip()]
                if len(row_cells) > 1 and f["numeric_ratio"] < 0.5:
                    primary_header_idx = idx
                    break

        if primary_header_idx == -1:
            primary_header_idx = 0

        # Step B: Identify first data row after primary_header_idx
        first_data_idx = -1
        for idx in range(primary_header_idx + 1, total_rows):
            f = features[idx]
            # If row has sequence ID
            if f["has_sequence_id"]:
                first_data_idx = idx
                break
            # If row has numeric ratio >= 0.25 and full columns
            if f["numeric_ratio"] >= 0.25 and f["non_empty_count"] >= max(2, int(grid.raw_col_count * 0.5)):
                first_data_idx = idx
                break
            # If row has header keywords == 0 while previous row had header keywords, and full width
            if f["header_keyword_score"] == 0 and features[idx - 1]["header_keyword_score"] > 0 and f["non_empty_count"] >= max(2, int(grid.raw_col_count * 0.5)):
                first_data_idx = idx
                break

        if first_data_idx == -1:
            first_data_idx = primary_header_idx + 1 if total_rows > primary_header_idx + 1 else primary_header_idx

        # Step C: Header block starts at primary_header_idx or earlier if preceding rows contain hierarchical subheadings
        header_start_idx = primary_header_idx
        check_idx = primary_header_idx - 1
        while check_idx >= 0:
            f = features[check_idx]
            if f["non_empty_count"] == 0:
                break
            row_cells = [c.strip() for c in grid.get_row(check_idx) if c.strip()]
            if len(row_cells) == 1:
                c_text = row_cells[0].lower()
                if (
                    len(row_cells[0]) > 30
                    or any(w in c_text for w in ("report", "country", "summary", "dashboard", "confidential", "run date", "export", "as of", "generated", "timestamp"))
                ):
                    break
            if f["header_keyword_score"] > 0 and f["numeric_ratio"] == 0:
                header_start_idx = check_idx
            else:
                break
            check_idx -= 1

        # Identify last data row: check from bottom for footnote/sentinel lines
        last_data_idx = total_rows - 1
        for idx in range(total_rows - 1, -1, -1):
            f = features[idx]
            if f["footnote_sentinel_pattern"] or (f["non_empty_count"] <= 2 and f["numeric_ratio"] == 0 and idx > total_rows - 5):
                last_data_idx = idx - 1
            else:
                break

        # Now classify each row
        for idx in range(total_rows):
            f = features[idx]
            row = grid.get_row(idx)

            # 1. Blank separator
            if f["non_empty_count"] == 0:
                decisions.append(RowRoleDecision(
                    row_index=idx,
                    role=RowRole.BLANK_SEPARATOR,
                    confidence=1.0,
                    reason="Row contains only empty cells",
                    features=f,
                ))
                continue

            # 2. Footnotes & Sentinel definitions (at bottom of sheet)
            if idx > last_data_idx:
                if f["footnote_sentinel_pattern"]:
                    decisions.append(RowRoleDecision(
                        row_index=idx,
                        role=RowRole.SENTINEL_DEFINITION,
                        confidence=1.0,
                        reason="Matches footnote sentinel definition pattern (e.g. '-' or 'NM')",
                        features=f,
                    ))
                else:
                    decisions.append(RowRoleDecision(
                        row_index=idx,
                        role=RowRole.FOOTNOTE,
                        confidence=0.95,
                        reason="Trailing explanatory text after data boundary",
                        features=f,
                    ))
                continue

            # 3. Embedded Page Headers / Repeated Document Headers
            is_page_watermark = bool(
                f["non_empty_count"] <= 3 and
                any(
                    re.search(r'\b(?:page\s+\d+|confidential|watermark)\b', c, re.IGNORECASE) or
                    re.search(r'page\s+\d+\s+of\s+\d+', c, re.IGNORECASE) or
                    c.strip().startswith("--- Page")
                    for c in row if c.strip()
                )
            )
            if idx >= first_data_idx and (is_page_watermark or (watermark_token and watermark_token in row and f["non_empty_count"] <= 3)):
                decisions.append(RowRoleDecision(
                    row_index=idx,
                    role=RowRole.PAGE_HEADER,
                    confidence=1.0,
                    reason=f"Embedded page header / watermark detected: {'page pattern' if is_page_watermark else watermark_token[:20]}",
                    features=f,
                ))
                continue

            # 4. Preamble Rows (above header block)
            if idx < header_start_idx:
                if f["repeated_string_score"] > 0 or (idx == 0 and f["non_empty_count"] <= 3):
                    decisions.append(RowRoleDecision(
                        row_index=idx,
                        role=RowRole.DOCUMENT_METADATA,
                        confidence=0.95,
                        reason="Document reference/file code in preamble region",
                        features=f,
                    ))
                else:
                    decisions.append(RowRoleDecision(
                        row_index=idx,
                        role=RowRole.TITLE,
                        confidence=0.90,
                        reason="Report title or metadata heading above table header",
                        features=f,
                    ))
                continue

            # 5. Header Block Rows
            if header_start_idx <= idx < first_data_idx:
                role = RowRole.HEADER if idx == header_start_idx else RowRole.HEADER_CONTINUATION
                decisions.append(RowRoleDecision(
                    row_index=idx,
                    role=role,
                    confidence=0.95,
                    reason=f"Table header hierarchy row {idx - header_start_idx + 1} of {first_data_idx - header_start_idx}",
                    features=f,
                ))
                continue

            # 6. Data Rows vs Data Continuation (Wrapped Records)
            if first_data_idx <= idx <= last_data_idx:
                # Check if this row is a sparse continuation of an adjacent data row
                if f["non_empty_count"] <= 2 and not f["has_sequence_id"]:
                    # Look at next row: does next row have sequence ID or full columns?
                    next_idx = idx + 1
                    while next_idx < total_rows and features[next_idx]["non_empty_count"] == 0:
                        next_idx += 1
                    
                    is_continuation = False
                    reason = ""
                    if next_idx < total_rows:
                        next_f = features[next_idx]
                        if next_f["has_sequence_id"] or next_f["non_empty_count"] >= 3:
                            is_continuation = True
                            reason = f"Sparse fragment row preceding data record at row {next_idx}"

                    if not is_continuation and idx > first_data_idx:
                        # Check if it's a suffix continuation of previous row
                        prev_f = features[idx - 1]
                        if prev_f["non_empty_count"] >= 3:
                            is_continuation = True
                            reason = f"Sparse fragment row suffixing data record at row {idx - 1}"

                    if is_continuation:
                        decisions.append(RowRoleDecision(
                            row_index=idx,
                            role=RowRole.DATA_CONTINUATION,
                            confidence=0.95,
                            reason=reason,
                            features=f,
                        ))
                        continue

                # Standard complete data row
                decisions.append(RowRoleDecision(
                    row_index=idx,
                    role=RowRole.DATA,
                    confidence=1.0,
                    reason="Standard data row conforming to table record structure",
                    features=f,
                ))
                continue

            # Default fallback
            decisions.append(RowRoleDecision(
                row_index=idx,
                role=RowRole.UNKNOWN,
                confidence=0.5,
                reason="Unclassified row; requires review",
                features=f,
                requires_review=True,
            ))

        return decisions
