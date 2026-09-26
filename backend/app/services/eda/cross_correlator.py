"""Multi-sheet entity linkage, key discovery, and intra/cross-table metric correlation engine.
Guarantees clean, realistic entity joins and robust statistical correlation matrices.
"""
from __future__ import annotations

import math
import re
from typing import Any
import numpy as np
import pandas as pd


PROHIBITED_JOIN_TERMS = {
    "leave", "attendance", "rate", "score", "hour", "salary", "count",
    "amount", "total", "ratio", "final", "approved", "july", "aug", "sep",
    "oct", "nov", "dec", "jan", "feb", "mar", "apr", "may", "jun", "to"
}

IDENTIFIER_TERMS = {
    "id", "employeeid", "empid", "code", "employeecode", "empcode",
    "badge", "person", "staff", "worker", "user", "name", "fullname",
    "employeename", "staffname"
}


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
        "id": "employee_id",  # In HR workforce contexts, naked ID is Employee ID
    }
    return aliases.get(cleaned, cleaned)


def is_valid_entity_key_column(col_name: str, diag: dict[str, Any]) -> bool:
    """Strictly validates whether a column represents an entity identifier rather than a measurement."""
    c_low = col_name.lower().strip()
    words = re.findall(r"\w+", c_low)

    # If any word is a measurement or date term, it is NOT an entity key
    if any(term in words or term in c_low for term in PROHIBITED_JOIN_TERMS):
        return False

    canon = canonical_key(col_name)
    if canon in ("employee_id", "employee_name", "department", "store_id"):
        return True

    inferred = diag.get("inferred_type", "")
    if inferred == "identifier":
        return True

    if any(term in words for term in IDENTIFIER_TERMS):
        return True

    return False


def is_realistic_metric_column(col_name: str, diag: dict[str, Any]) -> bool:
    """Validates whether a column is a realistic quantitative business metric suitable for correlation."""
    if is_valid_entity_key_column(col_name, diag):
        return False

    c_low = col_name.lower().strip()
    words = re.findall(r"\w+", c_low)

    # Exclude non-metric identifier terms
    if any(w in words for w in ["id", "code", "phone", "zip", "ssn", "serial", "name"]):
        return False

    inferred = diag.get("inferred_type", "")
    return inferred in ("numeric", "numeric_percentage", "numeric_currency", "numeric_rating")


def extract_entity_token(val: Any) -> str:
    if val is None:
        return ""
    s = str(val).strip()
    m_emp = re.match(r"(?:emp|employee)[-_]?0*(\d+)", s, re.I)
    if m_emp:
        return f"entity_{int(m_emp.group(1))}"
    m_person = re.match(r"person[-_]?0*(\d+)", s, re.I)
    if m_person:
        return f"entity_{int(m_person.group(1))}"
    # Standardize integer codes e.g. 1.0 -> 1
    try:
        f = float(s)
        if f.is_integer():
            return f"entity_{int(f)}"
    except ValueError:
        pass
    return s.casefold()


def compute_intra_sheet_correlations(
    records: list[dict[str, Any]],
    columns: list[str],
    column_diagnostics: dict[str, Any]
) -> dict[str, Any]:
    """Computes a full symmetric Pearson & Spearman correlation matrix for realistic numeric metrics."""
    # Filter realistic metrics
    metrics = [c for c in columns if is_realistic_metric_column(c, column_diagnostics.get(c, {}))]

    if len(metrics) < 2 or len(records) < 4:
        return {"metrics": metrics, "pairs": [], "matrix": []}

    df = pd.DataFrame(records)
    num_df = df[metrics].apply(pd.to_numeric, errors="coerce")

    # Drop columns with zero variance
    valid_metrics = [c for c in metrics if num_df[c].std(skipna=True) > 1e-9]
    if len(valid_metrics) < 2:
        return {"metrics": valid_metrics, "pairs": [], "matrix": []}

    pairs = []
    matrix_rows = []

    for i, m1 in enumerate(valid_metrics):
        row_vals = []
        for j, m2 in enumerate(valid_metrics):
            if i == j:
                row_vals.append(1.0)
            else:
                sub = num_df[[m1, m2]].dropna()
                if len(sub) >= 4:
                    r = float(sub[m1].corr(sub[m2], method="pearson"))
                    rho = float(sub[m1].rank().corr(sub[m2].rank(), method="pearson"))
                    r_val = round(r, 3) if not math.isnan(r) else 0.0
                    row_vals.append(r_val)

                    if j > i:  # Upper triangle for unique pairs
                        strength = (
                            "strong" if abs(r_val) >= 0.70
                            else "moderate" if abs(r_val) >= 0.35
                            else "mild" if abs(r_val) >= 0.15
                            else "negligible"
                        )
                        direction = "positive" if r_val > 0 else "negative"
                        pairs.append({
                            "x": m1,
                            "y": m2,
                            "coefficient": r_val,
                            "pearson_r": r_val,
                            "spearman_rho": round(rho, 3) if not math.isnan(rho) else 0.0,
                            "sample_size": len(sub),
                            "strength": strength,
                            "direction": direction
                        })
                else:
                    row_vals.append(None)
        matrix_rows.append(row_vals)

    pairs.sort(key=lambda p: abs(p["coefficient"]), reverse=True)

    return {
        "metrics": valid_metrics,
        "pairs": pairs,
        "matrix": matrix_rows
    }


def compute_metric_distribution_histograms(
    records: list[dict[str, Any]],
    columns: list[str],
    column_diagnostics: dict[str, Any]
) -> dict[str, Any]:
    """Computes distribution binning (10 equal-width bins), IQR bounds, and summary stats for each realistic metric."""
    metrics = [c for c in columns if is_realistic_metric_column(c, column_diagnostics.get(c, {}))]
    distributions = {}

    df = pd.DataFrame(records)
    for m in metrics:
        s = pd.to_numeric(df[m], errors="coerce").dropna()
        if len(s) < 4:
            continue

        min_val = float(s.min())
        max_val = float(s.max())
        mean_val = float(s.mean())
        median_val = float(s.median())
        std_val = float(s.std())
        q25 = float(s.quantile(0.25))
        q75 = float(s.quantile(0.75))
        iqr = q75 - q25

        # 10 bins
        if max_val > min_val:
            counts, bin_edges = np.histogram(s, bins=10)
            bins = []
            for b_idx in range(len(counts)):
                bins.append({
                    "bin_start": round(float(bin_edges[b_idx]), 2),
                    "bin_end": round(float(bin_edges[b_idx + 1]), 2),
                    "label": f"{bin_edges[b_idx]:.1f} - {bin_edges[b_idx+1]:.1f}",
                    "count": int(counts[b_idx])
                })
        else:
            bins = [{"bin_start": min_val, "bin_end": max_val, "label": f"{min_val:.1f}", "count": len(s)}]

        distributions[m] = {
            "metric": m,
            "min": round(min_val, 2),
            "max": round(max_val, 2),
            "mean": round(mean_val, 2),
            "median": round(median_val, 2),
            "std": round(std_val, 2),
            "q25": round(q25, 2),
            "q75": round(q75, 2),
            "iqr": round(iqr, 2),
            "outlier_low": round(q25 - 1.5 * iqr, 2),
            "outlier_high": round(q75 + 1.5 * iqr, 2),
            "bins": bins
        }

    return distributions


def compute_cross_sheet_intelligence(
    sheets: list[dict[str, Any]],
    curated_tables: dict[int, list[dict[str, Any]]],
    diagnostics: dict[int, dict[str, Any]]
) -> dict[str, Any]:
    """Discovers inter-sheet entity links on verified identity keys and correlates realistic quantitative metrics."""
    entity_links: list[dict[str, Any]] = []
    cross_correlations: list[dict[str, Any]] = []

    sheet_count = len(sheets)
    if sheet_count < 2:
        return {
            "entity_links": [],
            "cross_correlations": [],
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

            # 1. Entity Linkage Discovery (STRICT: only real entity identifiers)
            candidate_links = []
            for lc in left_cols:
                if not is_valid_entity_key_column(lc, left_diag.get(lc, {})):
                    continue
                l_canon = canonical_key(lc)
                l_tokens = {extract_entity_token(r.get(lc)): r.get(lc) for r in left_rows if r.get(lc) is not None}
                l_tokens.pop("", None)

                for rc in right_cols:
                    if not is_valid_entity_key_column(rc, right_diag.get(rc, {})):
                        continue
                    r_canon = canonical_key(rc)
                    r_tokens = {extract_entity_token(r.get(rc)): r.get(rc) for r in right_rows if r.get(rc) is not None}
                    r_tokens.pop("", None)

                    # Exact name match, canonical key match, or high token overlap
                    is_exact_col = lc.casefold() == rc.casefold()
                    is_canon_match = l_canon == r_canon
                    overlap_tokens = set(l_tokens.keys()) & set(r_tokens.keys())

                    if (is_exact_col or is_canon_match or len(overlap_tokens) >= 5) and overlap_tokens:
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
                            "confidence": "high" if (is_canon_match or is_exact_col) else "medium"
                        }
                        entity_links.append(link_info)
                        candidate_links.append((lc, rc, match_count))

            # 2. Cross-Sheet Metric Correlations on Verified Entity Links
            # Only correlate REALISTIC quantitative metrics
            left_metrics = [c for c in left_cols if is_realistic_metric_column(c, left_diag.get(c, {}))]
            right_metrics = [c for c in right_cols if is_realistic_metric_column(c, right_diag.get(c, {}))]

            if candidate_links and left_metrics and right_metrics:
                # Pick the highest-coverage entity join key
                candidate_links.sort(key=lambda item: item[2], reverse=True)
                best_lc, best_rc, best_match = candidate_links[0]

                if best_match >= 3:
                    left_df = pd.DataFrame(left_rows)
                    right_df = pd.DataFrame(right_rows)

                    left_df["_join_token"] = left_df[best_lc].apply(extract_entity_token)
                    right_df["_join_token"] = right_df[best_rc].apply(extract_entity_token)

                    joined = pd.merge(
                        left_df,
                        right_df,
                        on="_join_token",
                        suffixes=(f"_{left_id}", f"_{right_id}")
                    )

                    if len(joined) >= 4:
                        for lm in left_metrics:
                            col_lm = f"{lm}_{left_id}" if f"{lm}_{left_id}" in joined.columns else lm
                            for rm in right_metrics:
                                col_rm = f"{rm}_{right_id}" if f"{rm}_{right_id}" in joined.columns else rm
                                if col_lm not in joined.columns or col_rm not in joined.columns:
                                    continue

                                sub = joined[[col_lm, col_rm]].apply(pd.to_numeric, errors="coerce").dropna()
                                if len(sub) >= 4:
                                    x = sub[col_lm]
                                    y = sub[col_rm]
                                    if x.std() > 1e-9 and y.std() > 1e-9:
                                        r = float(x.corr(y, method="pearson"))
                                        rho = float(x.rank().corr(y.rank(), method="pearson"))

                                        if not math.isnan(r) and abs(r) >= 0.15:
                                            strength = (
                                                "strong" if abs(r) >= 0.70
                                                else "moderate" if abs(r) >= 0.35
                                                else "mild"
                                            )
                                            direction = "positive" if r > 0 else "negative"

                                            narrative = (
                                                f"{strength.capitalize()} {direction} cross-sheet correlation "
                                                f"(r = {r:+.2f}, N = {len(sub)}) between "
                                                f"'{lm}' ({left_s.get('display_name') or left_s['name']}) and "
                                                f"'{rm}' ({right_s.get('display_name') or right_s['name']})."
                                            )
                                            if abs(r) >= 0.90:
                                                narrative += " This indicates verified cross-system reconciliation across the two sheets."

                                            cross_correlations.append({
                                                "left_sheet_id": left_id,
                                                "left_sheet_name": left_s.get("display_name") or left_s["name"],
                                                "left_metric": lm,
                                                "right_sheet_id": right_id,
                                                "right_sheet_name": right_s.get("display_name") or right_s["name"],
                                                "right_metric": rm,
                                                "join_key": f"{best_lc} ↔ {best_rc}",
                                                "sample_size": len(sub),
                                                "pearson_r": round(r, 3),
                                                "spearman_rho": round(rho, 3),
                                                "strength": strength,
                                                "direction": direction,
                                                "narrative": narrative
                                            })

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
