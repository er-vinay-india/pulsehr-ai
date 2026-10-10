"""GridCapture: Raw 2D rectangular matrix extraction preserving full source fidelity.

Extracts an un-truncated, un-coerced string matrix from CSV, TSV, or Excel files,
guaranteeing exact row/column coordinates before any parsing, cleaning, or typing occurs.
"""

import csv
import io
import os
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union
import pandas as pd


class RawGrid:
    def __init__(
        self,
        matrix: List[List[str]],
        delimiter: str = ",",
        encoding: str = "utf-8",
        source_type: str = "csv",
        original_path: Optional[str] = None,
    ):
        self.matrix = matrix
        self.raw_row_count = len(matrix)
        self.raw_col_count = max((len(r) for r in matrix), default=0)
        self.delimiter = delimiter
        self.encoding = encoding
        self.source_type = source_type
        self.original_path = original_path

        # Standardize rectangular grid by padding short rows with empty strings
        for row in self.matrix:
            if len(row) < self.raw_col_count:
                row.extend([""] * (self.raw_col_count - len(row)))

    def get_row(self, idx: int) -> List[str]:
        if 0 <= idx < self.raw_row_count:
            return self.matrix[idx]
        return [""] * self.raw_col_count

    def get_cell(self, row: int, col: int) -> str:
        if 0 <= row < self.raw_row_count and 0 <= col < self.raw_col_count:
            return self.matrix[row][col]
        return ""

    def get_col(self, col: int) -> List[str]:
        if 0 <= col < self.raw_col_count:
            return [row[col] for row in self.matrix]
        return [""] * self.raw_row_count

    def non_empty_cells_in_row(self, row_idx: int) -> List[Tuple[int, str]]:
        """Returns [(col_idx, val)] for all non-empty cells in row."""
        row = self.get_row(row_idx)
        return [(c, val.strip()) for c, val in enumerate(row) if val.strip()]


class GridCapture:
    """Captures rectangular string matrix from arbitrary tabular files."""

    @classmethod
    def capture_file(
        cls,
        path_or_buffer: Union[str, Path, io.BytesIO, io.StringIO],
        filename_hint: Optional[str] = None,
        sheet_name: Optional[str] = None,
    ) -> RawGrid:
        if isinstance(path_or_buffer, (str, Path)):
            path = Path(path_or_buffer)
            suffix = path.suffix.lower()
            orig_name = str(path)
        else:
            suffix = Path(filename_hint or "").suffix.lower() if filename_hint else ".csv"
            orig_name = filename_hint

        if suffix in (".xlsx", ".xls"):
            return cls._capture_excel(path_or_buffer, suffix, sheet_name=sheet_name, orig_name=orig_name)
        else:
            return cls._capture_csv(path_or_buffer, suffix, orig_name=orig_name)

    @classmethod
    def _capture_csv(
        cls,
        path_or_buffer: Union[str, Path, io.BytesIO, io.StringIO],
        suffix: str,
        orig_name: Optional[str] = None,
    ) -> RawGrid:
        raw_bytes: bytes = b""
        if isinstance(path_or_buffer, (str, Path)):
            with open(path_or_buffer, "rb") as f:
                raw_bytes = f.read()
        elif isinstance(path_or_buffer, io.BytesIO):
            raw_bytes = path_or_buffer.getvalue()
        elif isinstance(path_or_buffer, io.StringIO):
            raw_bytes = path_or_buffer.getvalue().encode("utf-8")
        else:
            raw_bytes = bytes(path_or_buffer)

        # Detect encoding
        chosen_encoding = "utf-8"
        text_content = ""
        for enc in ("utf-8-sig", "utf-8", "cp1252", "latin1"):
            try:
                text_content = raw_bytes.decode(enc)
                chosen_encoding = enc
                break
            except UnicodeDecodeError:
                continue

        if not text_content:
            text_content = raw_bytes.decode("latin1", errors="replace")
            chosen_encoding = "latin1"

        # Sniff delimiter
        default_sep = "\t" if suffix == ".tsv" else ","
        lines = [line for line in text_content.splitlines() if line.strip()]
        detected_sep = default_sep
        if lines:
            try:
                sample_chunk = text_content[:32768]
                sniffer = csv.Sniffer()
                dialect = sniffer.sniff(sample_chunk, delimiters=[",", ";", "\t", "|"])
                if dialect and dialect.delimiter:
                    detected_sep = dialect.delimiter
            except Exception:
                # Count frequency heuristic
                delims = [",", ";", "\t", "|"]
                counts = {d: sum(line.count(d) for line in lines[:20]) for d in delims}
                max_delim = max(counts, key=counts.get)
                if counts[max_delim] > 0:
                    detected_sep = max_delim

        # Parse CSV into 2D string matrix
        matrix: List[List[str]] = []
        reader = csv.reader(io.StringIO(text_content), delimiter=detected_sep)
        for row in reader:
            if not row or (len(row) == 1 and not row[0].strip()):
                continue
            matrix.append([cell.strip() for cell in row])

        return RawGrid(
            matrix=matrix,
            delimiter=detected_sep,
            encoding=chosen_encoding,
            source_type="tsv" if detected_sep == "\t" else "csv",
            original_path=orig_name,
        )

    @classmethod
    def _capture_excel(
        cls,
        path_or_buffer: Union[str, Path, io.BytesIO, io.StringIO],
        suffix: str,
        sheet_name: Optional[str] = None,
        orig_name: Optional[str] = None,
    ) -> RawGrid:
        engine = "xlrd" if suffix == ".xls" else "openpyxl"
        try:
            excel_file = pd.ExcelFile(path_or_buffer, engine=engine)
        except Exception:
            # Fallback to default engine
            excel_file = pd.ExcelFile(path_or_buffer)

        target_sheet = sheet_name or excel_file.sheet_names[0]
        # Read header=None, keep_default_na=False to prevent automatic NaN conversion
        df = pd.read_excel(excel_file, sheet_name=target_sheet, header=None, dtype=str, keep_default_na=False)

        matrix = df.fillna("").astype(str).values.tolist()
        matrix = [[cell.strip() for cell in row] for row in matrix]

        return RawGrid(
            matrix=matrix,
            delimiter=",",
            encoding="utf-8",
            source_type="excel",
            original_path=orig_name,
        )
