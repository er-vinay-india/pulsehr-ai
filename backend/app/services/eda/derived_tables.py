"""Synthesis and materialization of cross-sheet derived tables."""
from __future__ import annotations

import json
import sqlite3
from typing import Any
import pandas as pd
from .cross_correlator import extract_entity_token


def synthesize_derived_tables(
    conn: sqlite3.Connection,
    sheets: list[dict[str, Any]],
    curated_tables: dict[int, list[dict[str, Any]]],
    entity_links: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Identifies high-confidence 1:1 or 1:N entity joins and materializes unified derived tables."""
    derived_summaries: list[dict[str, Any]] = []

    # Clear previous derived tables
    conn.execute("DELETE FROM derived_table_rows")
    conn.execute("DELETE FROM derived_tables")

    # Group links by pair of sheets
    processed_pairs = set()

    for link in entity_links:
        if link.get("confidence") != "high" or link.get("matching_keys", 0) < 3:
            continue

        left_id = link["left_sheet_id"]
        right_id = link["right_sheet_id"]
        pair_key = tuple(sorted([left_id, right_id]))
        if pair_key in processed_pairs:
            continue
        processed_pairs.add(pair_key)

        left_s = next((s for s in sheets if s["id"] == left_id), None)
        right_s = next((s for s in sheets if s["id"] == right_id), None)
        if not left_s or not right_s:
            continue

        left_rows = curated_tables.get(left_id, [])
        right_rows = curated_tables.get(right_id, [])
        if not left_rows or not right_rows:
            continue

        lc = link["left_column"]
        rc = link["right_column"]

        left_df = pd.DataFrame(left_rows)
        right_df = pd.DataFrame(right_rows)

        left_df["_join_token"] = left_df[lc].apply(extract_entity_token)
        right_df["_join_token"] = right_df[rc].apply(extract_entity_token)

        # Merge on token
        # Deduplicate common columns like Name, Department, and Employee ID
        common_cols = set(left_s["columns"]) & set(right_s["columns"])
        cols_to_drop_from_right = list(common_cols)
        right_df_clean = right_df.drop(columns=cols_to_drop_from_right, errors="ignore")

        merged = pd.merge(
            left_df,
            right_df_clean,
            on="_join_token",
            how="inner",
            suffixes=("", "_alt")
        )

        merged = merged.drop(columns=["_join_token"], errors="ignore")
        if merged.empty:
            continue

        # Clean column list
        final_cols = list(merged.columns)
        merged_records = json.loads(merged.to_json(orient="records", date_format="iso"))

        # Table naming
        left_title = left_s.get("display_name") or left_s["name"]
        right_title = right_s.get("display_name") or right_s["name"]
        derived_name = f"derived_{left_id}_{right_id}"
        derived_display = f"Unified {left_title} & {right_title}"
        derived_desc = (
            f"Synthesized cross-sheet view joining {left_title} and {right_title} "
            f"on '{lc} ↔ {rc}' ({len(merged_records)} matched entities)."
        )

        # Insert into derived_tables
        cur = conn.execute(
            """
            INSERT INTO derived_tables(name, display_name, description, source_sheets_json, join_keys_json, columns_json, row_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                derived_name,
                derived_display,
                derived_desc,
                json.dumps([left_id, right_id]),
                json.dumps({"left_column": lc, "right_column": rc}),
                json.dumps(final_cols),
                len(merged_records)
            )
        )
        derived_id = cur.lastrowid

        # Insert rows into derived_table_rows
        for r_idx, rec in enumerate(merged_records):
            conn.execute(
                """
                INSERT INTO derived_table_rows(derived_table_id, row_index, data_json)
                VALUES (?, ?, ?)
                """,
                (derived_id, r_idx, json.dumps(rec))
            )

        derived_summaries.append({
            "id": derived_id,
            "name": derived_name,
            "display_name": derived_display,
            "description": derived_desc,
            "source_sheets": [left_id, right_id],
            "join_keys": {"left_column": lc, "right_column": rc},
            "columns": final_cols,
            "row_count": len(merged_records)
        })

    return derived_summaries
