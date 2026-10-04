"""Deterministic missing-cell audits at source-sheet grain, without LLM math."""
import re
import time
from pathlib import Path
from typing import Any

import pandas as pd

from ...core import config
from ...db.database import get_connection
from ..sheet_catalog import read_sheets


def is_missing_values_query(query: str) -> bool:
    q = query.lower()
    missing = bool(re.search(r"\b(missing|nulls?|blanks?|empty|incomplete)\b", q))
    count = bool(re.search(r"\b(how many|number of|count|total|values?|cells?|entries|records?|rows?|data|columns?)\b", q))
    definition = bool(re.match(r"\s*(define|meaning of|what (?:is|are) (?:a |an |the )?(?:missing|null|blank))\b", q))
    return missing and count and not definition


def missing_value_summary(frame: pd.DataFrame) -> dict[str, Any]:
    # OR the masks: a real null and its string representation count only once.
    # Raw data retains non-empty labels such as 'none' (no test preparation),
    # 'NA' or 'null'. Import cleanup's sentinel rules must not turn legitimate
    # source categories into missing cells during an audit of the original file.
    missing = frame.isna() | frame.map(lambda value: isinstance(value, str) and not value.strip())
    rows, columns = frame.shape
    per_column = [{"column": str(c), "missing_cells": int(missing[c].sum())} for c in frame.columns]
    return {"rows": rows, "columns": columns, "total_cells": rows * columns,
            "missing_cells": sum(c["missing_cells"] for c in per_column),
            "rows_with_missing": int(missing.any(axis=1).sum()),
            "fully_empty_rows": int(missing.all(axis=1).sum()) if columns else 0,
            "per_column": per_column}


def answer_missing_values(query: str, sheet_id: int | None, dataset_id: int | None = None) -> dict[str, Any]:
    start = time.perf_counter()
    with get_connection() as conn:
        sql = "SELECT s.id, s.dataset_id, s.name, s.display_name, d.filename FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id"
        args = []
        if sheet_id is not None:
            sql += " WHERE s.id=?"; args.append(sheet_id)
            if dataset_id is not None:
                sql += " AND s.dataset_id=?"; args.append(dataset_id)
        elif dataset_id is not None:
            sql += " WHERE s.dataset_id=?"; args.append(dataset_id)
        sheet = conn.execute(sql + " ORDER BY s.id DESC LIMIT 1", args).fetchone()

    def result(answer, status="success", summary=None):
        return {"query": query, "answer": answer, "engine": "sheet_quality",
                "model_used": "verified_source_quality", "status": status,
                "visual_charts": [], "data_quality": summary,
                # This is a new question about the sheet, not a ranking
                # refinement. Drop metric/dimension/filter context completely.
                "prior_context": {"sheet_id": sheet["id"] if sheet else sheet_id,
                                  "dataset_id": sheet["dataset_id"] if sheet else dataset_id,
                                  "last_intent": "missing_values", "last_query": query},
                "evidence": {"source_ids": [sheet["id"]] if sheet else [],
                             "result_grain": "source_sheet", "source_kind": "original_upload",
                             "calculation_method": "Count blanks and actual nulls once per original source cell; preserve non-empty text labels; exclude headers and derived fields."},
                "timings": {"total_ms": round((time.perf_counter() - start) * 1000, 1),
                            "llm_calls": 0, "is_deterministic": True}}

    if sheet is None:
        return result("Please select or upload a sheet before checking missing values.", "source_unavailable")
    path = config.UPLOADS_DIR / Path(sheet["filename"]).name
    if not path.is_file():
        return result("The original uploaded file is unavailable, so I can’t verify the raw sheet’s missing-value count. Please upload the original file again.", "source_unavailable")
    try:
        frames = read_sheets(path, prune_empty=False)
        frame = frames.get(sheet["name"])
        if frame is None:
            return result("The selected sheet is unavailable in the original uploaded file. Please select the correct sheet.", "source_unavailable")
    except (ValueError, OSError):
        return result("I couldn’t read the original uploaded sheet to verify missing values. Please check or upload the original file again.", "source_unavailable")

    if re.search(r"\b(by|where|only|among|excluding|except)\b", query, re.I):
        return result("Please specify a source column to check, or ask for the whole raw sheet. I couldn’t resolve the requested grouping or filter for this missing-value count.", "clarification_required")

    # A named-column question is bounded to that source field. An unnamed
    # sheet-wide question never inherits the previous conversation's metric.
    normalize = lambda text: re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()
    q = f" {normalize(query)} "
    quality_words = {"missing", "null", "blank", "empty", "incomplete", "raw", "sheet", "data", "rows", "records", "values", "cells"}
    matched = []
    for column in frame.columns:
        label = normalize(column)
        if not label or f" {label} " not in q:
            continue
        # 'empty rows' describes an audit, even when a column is named 'empty'.
        # Such column names require an explicit column reference or quotes.
        if label in quality_words and not (
            re.search(rf"\b(?:in|column|field)\s+(?:the\s+)?{re.escape(label)}\b", q)
            or re.search(rf"[\"'`]{re.escape(str(column))}[\"'`]", query, re.I)
        ):
            continue
        matched.append(column)
    if matched:
        frame = frame[matched]
    summary = missing_value_summary(frame)
    name = str(sheet["display_name"] or sheet["name"]).replace("\n", " ")
    scope = "selected source columns" if matched else "original columns"
    observation = f"There are **{summary['missing_cells']:,} missing values**"
    if re.search(r"\b(empty|blank|null)\s+(rows?|records?)\b", query, re.I):
        count = summary['fully_empty_rows']
        observation = f"There {'is' if count == 1 else 'are'} **{count:,} completely empty {'row' if count == 1 else 'rows'}**"
    elif re.search(r"\b(rows?|records?)\b", query, re.I):
        observation = f"There are **{summary['rows_with_missing']:,} rows with missing values**"
    answer = (f"{observation} in the raw sheet **{name}**.\n\n"
              f"Checked **{summary['rows']:,} rows × {summary['columns']:,} {scope} "
              f"({summary['total_cells']:,} cells)**. **{summary['rows_with_missing']:,} rows** contain at least one missing value.\n\n"
              "Missing means blank cells or actual nulls. Non-empty text labels, such as ‘none’, remain recorded values. Derived fields and headers are excluded.")
    affected = [c for c in summary["per_column"] if c["missing_cells"]]
    if affected:
        answer += "\n\n| Column | Missing cells |\n| --- | ---: |"
        for entry in affected:
            label = entry["column"].replace("|", "\\|").replace("\n", " ")
            answer += f"\n| {label} | {entry['missing_cells']:,} |"
    return result(answer, summary=summary)
