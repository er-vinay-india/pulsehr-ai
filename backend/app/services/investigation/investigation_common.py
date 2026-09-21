"""Common utility and cross-sheet relation helpers for investigation services."""

import math
from typing import Any
import pandas as pd


def clean_val(v: Any) -> Any:
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return None
    return v


def find_connected_evidence(
    conn, all_sheets, sheet_records, target_df: pd.DataFrame, current_sheet_id: int | None = None
) -> list[dict]:
    """Retrieves matching records from other sheets using verified relationships or shared keys."""
    connected = []
    if target_df.empty:
        return connected

    # Check verified relationships
    rels = conn.execute("SELECT * FROM sheet_relationships WHERE status='linked'").fetchall()
    seen_sheets = {current_sheet_id} if current_sheet_id else set()

    for rel in rels:
        directions = [
            (rel["left_sheet"], rel["right_sheet"], rel["left_column"], rel["right_column"]),
            (rel["right_sheet"], rel["left_sheet"], rel["right_column"], rel["left_column"])
        ]
        for src_sid, target_sid, src_col, target_col in directions:
            if target_sid in seen_sheets:
                continue
            if src_col in target_df.columns and target_sid in sheet_records:
                other_sheet = next((s for s in all_sheets if s["id"] == target_sid), None)
                if not other_sheet:
                    continue
                other_records = sheet_records[target_sid]
                other_df = pd.DataFrame(other_records)
                if target_col in other_df.columns:
                    target_keys = set(target_df[src_col].dropna().astype(str).str.strip().str.lower())
                    matched = other_df[other_df[target_col].astype(str).str.strip().str.lower().isin(target_keys)]
                    if len(matched) > 0:
                        seen_sheets.add(target_sid)
                        connected.append({
                            "relationship_id": rel["id"],
                            "related_sheet": other_sheet["name"],
                            "related_file": other_sheet["original_name"],
                            "join_key": f"{src_col} ↔ {target_col}",
                            "matched_count": len(matched),
                            "sample_rows": [
                                {k: clean_val(v) for k, v in r.items() if not k.startswith("__")}
                                for _, r in matched.head(5).iterrows()
                            ]
                        })
                        break

    # Fallback: if no relationship rows exist, look for exact shared ID column names across other sheets
    if not connected:
        candidate_cols = [
            c for c in target_df.columns
            if not c.startswith("__") and any(k in str(c).lower() for k in ("id", "code", "name"))
        ]
        for other_sheet in all_sheets:
            target_sid = other_sheet["id"]
            if target_sid in seen_sheets:
                continue
            other_records = sheet_records.get(target_sid, [])
            if not other_records:
                continue
            other_df = pd.DataFrame(other_records)
            for c in candidate_cols:
                matching_other_col = next(
                    (oc for oc in other_df.columns if oc.strip().lower() == c.strip().lower()), None
                )
                if matching_other_col:
                    target_keys = set(target_df[c].dropna().astype(str).str.strip().str.lower())
                    matched = other_df[other_df[matching_other_col].astype(str).str.strip().str.lower().isin(target_keys)]
                    if len(matched) > 0 and len(matched) <= len(other_df):
                        seen_sheets.add(target_sid)
                        connected.append({
                            "relationship_id": f"auto_{c}",
                            "related_sheet": other_sheet["name"],
                            "related_file": other_sheet["original_name"],
                            "join_key": f"{c} ↔ {matching_other_col}",
                            "matched_count": len(matched),
                            "sample_rows": [
                                {k: clean_val(v) for k, v in r.items() if not k.startswith("__")}
                                for _, r in matched.head(5).iterrows()
                            ]
                        })
                        break
    return connected


def find_individual_connected_evidence(
    conn, all_sheets, sheet_records, target_row: pd.Series, id_col: str | None, name_col: str | None, current_sheet_id: int | None = None
) -> list[dict]:
    connected = []
    rels = conn.execute("SELECT * FROM sheet_relationships WHERE status='linked'").fetchall()
    seen_sheets = {current_sheet_id} if current_sheet_id else set()

    for rel in rels:
        directions = [
            (rel["left_sheet"], rel["right_sheet"], rel["left_column"], rel["right_column"]),
            (rel["right_sheet"], rel["left_sheet"], rel["right_column"], rel["left_column"])
        ]
        for src_sid, target_sid, src_col, target_col in directions:
            if target_sid in seen_sheets:
                continue
            lookup_val = None
            if src_col in target_row and pd.notna(target_row[src_col]):
                lookup_val = str(target_row[src_col]).strip().lower()
            elif id_col and id_col in target_row and pd.notna(target_row[id_col]):
                lookup_val = str(target_row[id_col]).strip().lower()
            elif name_col and name_col in target_row and pd.notna(target_row[name_col]):
                lookup_val = str(target_row[name_col]).strip().lower()

            if lookup_val and target_sid in sheet_records:
                other_sheet = next((s for s in all_sheets if s["id"] == target_sid), None)
                if not other_sheet:
                    continue
                other_df = pd.DataFrame(sheet_records[target_sid])
                if target_col in other_df.columns:
                    matched = other_df[other_df[target_col].astype(str).str.strip().str.lower() == lookup_val]
                    if len(matched) > 0:
                        seen_sheets.add(target_sid)
                        connected.append({
                            "relationship_id": rel["id"],
                            "related_sheet": other_sheet["name"],
                            "related_file": other_sheet["original_name"],
                            "join_key": f"{src_col} = {lookup_val}",
                            "matched_count": len(matched),
                            "sample_rows": [
                                {k: clean_val(v) for k, v in r.items() if not k.startswith("__")}
                                for _, r in matched.head(5).iterrows()
                            ]
                        })
                        break

    # Fallback: if no relationship rows exist, look for shared identifier keys
    if not connected:
        candidate_cols = [c for c in (id_col, name_col) if c and c in target_row and pd.notna(target_row[c])]
        for other_sheet in all_sheets:
            target_sid = other_sheet["id"]
            if target_sid in seen_sheets:
                continue
            other_records = sheet_records.get(target_sid, [])
            if not other_records:
                continue
            other_df = pd.DataFrame(other_records)
            for c in candidate_cols:
                lookup_val = str(target_row[c]).strip().lower()
                matching_other_col = next((oc for oc in other_df.columns if oc.strip().lower() == c.strip().lower()), None)
                if matching_other_col:
                    matched = other_df[other_df[matching_other_col].astype(str).str.strip().str.lower() == lookup_val]
                    if len(matched) > 0:
                        seen_sheets.add(target_sid)
                        connected.append({
                            "relationship_id": f"auto_{c}",
                            "related_sheet": other_sheet["name"],
                            "related_file": other_sheet["original_name"],
                            "join_key": f"{c} = {lookup_val}",
                            "matched_count": len(matched),
                            "sample_rows": [
                                {k: clean_val(v) for k, v in r.items() if not k.startswith("__")}
                                for _, r in matched.head(5).iterrows()
                            ]
                        })
                        break
    return connected
