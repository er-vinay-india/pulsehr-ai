"""Multi-sheet ($N$ sheets) entity linkage, key discovery, and cross-table metric correlation engine."""
from __future__ import annotations

import math
import re
from typing import Any
import numpy as np
import pandas as pd


def canonical_key(name: str) -> str:
    cleaned = re.sub(r"[^\w]", "", name.casefold()).replace("_", "")
    aliases = {
        "employeeid": "employee_id",
        "empid": "employee_id",
        "employeecode": "employee_id",
        "empcode": "employee_id",
        "employeename": "employee_name",
        "staffname": "employee_name",
        "fullname": "employee_name",
        "department": "department",
        "dept": "department",
        "store": "store_id",
        "storeid": "store_id",
        "date": "date",
    }
    return aliases.get(cleaned, cleaned)


def extract_entity_token(val: Any) -> str:
    if val is None:
        return ""
    s = str(val).strip()
    # Normalize EMP-014 -> emp14, Person_14 -> person14 or emp14
    m_emp = re.match(r"(?:emp|employee)[-_]?0*(\d+)", s, re.I)
    if m_emp:
        return f"entity_{int(m_emp.group(1))}"
    m_person = re.match(r"person[-_]?0*(\d+)", s, re.I)
    if m_person:
        return f"entity_{int(m_person.group(1))}"
    return s.casefold()


def compute_cross_sheet_intelligence(
    sheets: list[dict[str, Any]],
    curated_tables: dict[int, list[dict[str, Any]]],
    diagnostics: dict[int, dict[str, Any]]
) -> dict[str, Any]:
    """Discovers inter-sheet entity links, computes cross-table metric correlations, and highlights analytical insights."""
    entity_links: list[dict[str, Any]] = []
    cross_correlations: list[dict[str, Any]] = []
    matrix_findings: list[dict[str, Any]] = []

    sheet_count = len(sheets)
    if sheet_count < 2:
        return {
            "entity_links": [],
            "cross_correlations": [],
            "matrix_findings": [],
            "summary": "Single sheet loaded; multi-sheet cross-correlation requires at least two sheets."
        }

    for i in range(sheet_count):
        left_s = sheets[i]
        left_id = left_s["id"]
        left_rows = curated_tables.get(left_id, [])
        left_cols = left_s["columns"]
        left_diag = diagnostics.get(left_id, {}).get("column_diagnostics", {})

        for j in range(i + 1, sheet_count):
            right_s = sheets[j]
            right_id = right_s["id"]
            right_rows = curated_tables.get(right_id, [])
            right_cols = right_s["columns"]
            right_diag = diagnostics.get(right_id, {}).get("column_diagnostics", {})

            # 1. Entity Linkage Discovery
            for lc in left_cols:
                l_type = left_diag.get(lc, {}).get("inferred_type", "categorical")
                l_canon = canonical_key(lc)
                l_tokens = {extract_entity_token(r.get(lc)): r.get(lc) for r in left_rows if r.get(lc) is not None}
                l_tokens.pop("", None)

                for rc in right_cols:
                    r_type = right_diag.get(rc, {}).get("inferred_type", "categorical")
                    r_canon = canonical_key(rc)
                    r_tokens = {extract_entity_token(r.get(rc)): r.get(rc) for r in right_rows if r.get(rc) is not None}
                    r_tokens.pop("", None)

                    # Check key similarity or overlap
                    is_exact_col = lc.casefold() == rc.casefold()
                    is_canon_match = l_canon == r_canon
                    overlap_tokens = set(l_tokens.keys()) & set(r_tokens.keys())

                    if (is_exact_col or is_canon_match or len(overlap_tokens) >= 3) and overlap_tokens:
                        match_count = len(overlap_tokens)
                        left_unique = len(l_tokens) == len(left_rows)
                        right_unique = len(r_tokens) == len(right_rows)
                        cardinality = ("1" if left_unique else "N") + ":" + ("1" if right_unique else "N")

                        link_info = {
                            "left_sheet_id": left_id,
                            "left_sheet_name": left_s.get("display_name") or left_s["name"],
                            "left_column": lc,
                            "right_sheet_id": right_id,
                            "right_sheet_name": right_s.get("display_name") or right_s["name"],
                            "right_column": rc,
                            "matching_keys": match_count,
                            "cardinality": cardinality,
                            "is_primary_foreign_pair": left_unique or right_unique,
                            "coverage_pct": round((match_count / max(1, min(len(left_rows), len(right_rows)))) * 100, 1),
                            "confidence": "high" if (is_exact_col and (left_unique or right_unique)) else "medium"
                        }
                        entity_links.append(link_info)

                        # 2. Cross-Sheet Metric Correlations
                        # If sheets share an entity key, perform join and correlate all numeric metric pairs
                        if match_count >= 3:
                            left_df = pd.DataFrame(left_rows)
                            right_df = pd.DataFrame(right_rows)

                            # Create mapped join token
                            left_df["_join_token"] = left_df[lc].apply(extract_entity_token)
                            right_df["_join_token"] = right_df[rc].apply(extract_entity_token)

                            joined = pd.merge(
                                left_df,
                                right_df,
                                on="_join_token",
                                suffixes=(f"_{left_id}", f"_{right_id}")
                            )

                            if len(joined) >= 3:
                                # Find numeric metrics in left and right
                                left_metrics = [
                                    c for c in left_cols
                                    if left_diag.get(c, {}).get("inferred_type") in ("numeric", "numeric_percentage", "numeric_currency", "numeric_rating")
                                ]
                                right_metrics = [
                                    c for c in right_cols
                                    if right_diag.get(c, {}).get("inferred_type") in ("numeric", "numeric_percentage", "numeric_currency", "numeric_rating")
                                ]

                                for lm in left_metrics:
                                    col_lm = f"{lm}_{left_id}" if f"{lm}_{left_id}" in joined.columns else lm
                                    for rm in right_metrics:
                                        col_rm = f"{rm}_{right_id}" if f"{rm}_{right_id}" in joined.columns else rm
                                        if col_lm not in joined.columns or col_rm not in joined.columns:
                                            continue

                                        sub = joined[[col_lm, col_rm]].dropna()
                                        if len(sub) >= 3:
                                            try:
                                                x = sub[col_lm].astype(float)
                                                y = sub[col_rm].astype(float)

                                                # Check variance
                                                if x.std() > 0 and y.std() > 0:
                                                    pearson_r = float(x.corr(y, method="pearson"))
                                                    # Spearman is Pearson correlation on rank-transformed variables (scipy-independent)
                                                    spearman_rho = float(x.rank().corr(y.rank(), method="pearson"))

                                                    if not math.isnan(pearson_r):
                                                        strength = (
                                                            "strong" if abs(pearson_r) >= 0.70
                                                            else "moderate" if abs(pearson_r) >= 0.35
                                                            else "mild" if abs(pearson_r) >= 0.15
                                                            else "negligible"
                                                        )
                                                        direction = "positive" if pearson_r > 0 else "negative"

                                                        # Formulate actionable analytical narrative
                                                        if abs(pearson_r) >= 0.15:
                                                            narrative = (
                                                                f"{strength.capitalize()} {direction} correlation "
                                                                f"(r = {pearson_r:+.2f}, N = {len(sub)}) between "
                                                                f"'{lm}' ({left_s.get('display_name') or left_s['name']}) and "
                                                                f"'{rm}' ({right_s.get('display_name') or right_s['name']})."
                                                            )
                                                            if pearson_r < -0.30:
                                                                narrative += f" Higher '{rm}' is inversely associated with '{lm}'."
                                                            elif pearson_r > 0.30:
                                                                narrative += f" Higher '{lm}' correlates directly with higher '{rm}'."

                                                            finding = {
                                                                "left_sheet_id": left_id,
                                                                "left_sheet_name": left_s.get("display_name") or left_s["name"],
                                                                "left_metric": lm,
                                                                "right_sheet_id": right_id,
                                                                "right_sheet_name": right_s.get("display_name") or right_s["name"],
                                                                "right_metric": rm,
                                                                "join_key": f"{lc} ↔ {rc}",
                                                                "sample_size": len(sub),
                                                                "pearson_r": round(pearson_r, 3),
                                                                "spearman_rho": round(spearman_rho, 3),
                                                                "strength": strength,
                                                                "direction": direction,
                                                                "narrative": narrative
                                                            }
                                                            # Deduplicate by (left_id, lm, right_id, rm) keeping higher sample size
                                                            pair_key = (left_id, lm, right_id, rm)
                                                            existing = next((c for c in cross_correlations if (c["left_sheet_id"], c["left_metric"], c["right_sheet_id"], c["right_metric"]) == pair_key), None)
                                                            if not existing or len(sub) > existing["sample_size"]:
                                                                if existing:
                                                                    cross_correlations.remove(existing)
                                                                cross_correlations.append(finding)
                                            except Exception:
                                                pass

    # Sort correlations by absolute correlation coefficient descending
    cross_correlations.sort(key=lambda c: abs(c["pearson_r"]), reverse=True)

    return {
        "entity_links": entity_links,
        "cross_correlations": cross_correlations,
        "total_links_found": len(entity_links),
        "total_correlations_computed": len(cross_correlations),
        "summary": (
            f"Discovered {len(entity_links)} verified entity linkages and "
            f"computed {len(cross_correlations)} cross-sheet metric correlations across {sheet_count} uploaded sheets."
        )
    }
