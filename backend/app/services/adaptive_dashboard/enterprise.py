"""Enterprise Synthesis Engine — Element 10 execution pipeline.

Follows Revision 12 of docs/adaptive-dashboard-design.md:
- What do the safely connected sources collectively establish, and where can leadership inspect the linked evidence?
- Stable title: Enterprise synthesis.
- Same-dataset sibling sheet scope only: default scope is the selected sheet's dataset_id and its sibling sheets from the same upload.
- Multi-source manifest and combined deterministic content hash snapshot.
- Recipes evaluated in strict priority order:
    Recipe A: Reconciled lifecycle metric (e.g. orders <-> returns, leads <-> wins).
    Recipe B: Matched cohort comparison (privacy-safe aggregation, like-for-like groups).
    Recipe C: Cross-source association (N >= 30, nonzero variance, agreeing Pearson/Spearman, outlier checked).
    Recipe D: Aligned temporal co-movement (detrended/differenced, matching periods >= 12).
    Recipe E: Coverage-only synthesis (when multiple sources exist but no safe join passes).
- Single-sheet dataset: clean coverage-only state explaining multi-sheet scope requirement.
- Privacy guarantee: no row-level PII (names, personal IDs, or raw individual rows) in responses or chart points.
- Visual choices: scatter (with descriptive trend line), paired_dot, lifecycle_flow, or none.
- ECharts is the only chart library.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from typing import Any

from .contracts import (
    CrossSourceEvidence,
    EnterpriseDrilldownTarget,
    EnterpriseSourceRef,
    EnterpriseSynthesisSpec,
    EnterpriseVisualPoint,
    EnterpriseVisualSpec,
    EvidenceResult,
    ExplainSpec,
    GlanceSpec,
    InspectSpec,
    SemanticContract,
    SourceManifest,
)

logger = logging.getLogger(__name__)

# Reserved identifier patterns for candidate entity keys
ENTITY_KEY_PATTERNS = [
    r"^id$",
    r"^.*_id$",
    r"^.*id$",
    r"^employee[_\s]?id$",
    r"^emp[_\s]?id$",
    r"^order[_\s]?id$",
    r"^lead[_\s]?id$",
    r"^ticket[_\s]?id$",
    r"^customer[_\s]?id$",
    r"^cust[_\s]?id$",
    r"^user[_\s]?id$",
    r"^account[_\s]?id$",
    r"^code$",
    r"^department$",
    r"^dept$",
    r"^sku$",
    r"^email$",
]

# Sensitive PII column keywords that must NEVER be exposed in visual points or labels
PII_COLUMN_PATTERNS = [
    r"name",
    r"full[_\s]?name",
    r"first[_\s]?name",
    r"last[_\s]?name",
    r"ssn",
    r"social[_\s]?security",
    r"phone",
    r"address",
    r"email",
    r"salary",
    r"compensation",
    r"employee[_\s]?id",
    r"personal[_\s]?id",
    r"person[_\s]?id",
]


def is_pii_column(col_name: str) -> bool:
    """Check if a column contains direct personal identifying information."""
    lower = col_name.strip().lower()
    return any(re.search(pat, lower) for pat in PII_COLUMN_PATTERNS)


def compute_combined_snapshot(sources: list[EnterpriseSourceRef]) -> str:
    """Computes a deterministic cryptographic hash of all included source identities and snapshots."""
    hasher = hashlib.sha256()
    # Sort deterministically by sheet_id
    for src in sorted(sources, key=lambda s: s.sheet_id):
        hasher.update(f"{src.sheet_id}:{src.snapshot}|".encode("utf-8"))
    return hasher.hexdigest()[:16]


def normalize_token(s: str) -> str:
    """Normalize string for key comparison."""
    return re.sub(r"[^a-z0-9]", "", s.strip().lower())


def detect_candidate_join_keys(
    left_cols: list[str],
    right_cols: list[str],
    left_rows: list[dict[str, Any]],
    right_rows: list[dict[str, Any]],
) -> list[tuple[str, str, float]]:
    """Detects candidate join keys between two sheets, returning (left_col, right_col, match_score)."""
    candidates = []

    for l_col in left_cols:
        l_norm = normalize_token(l_col)
        l_is_entity = any(re.search(pat, l_col.strip().lower()) for pat in ENTITY_KEY_PATTERNS)

        for r_col in right_cols:
            r_norm = normalize_token(r_col)
            r_is_entity = any(re.search(pat, r_col.strip().lower()) for pat in ENTITY_KEY_PATTERNS)

            if not (l_is_entity or r_is_entity or l_norm == r_norm):
                continue

            # Check value overlap in sample rows
            l_vals = {str(r.get(l_col, "")).strip() for r in left_rows if r.get(l_col) is not None and str(r.get(l_col, "")).strip()}
            r_vals = {str(r.get(r_col, "")).strip() for r in right_rows if r.get(r_col) is not None and str(r.get(r_col, "")).strip()}

            # Reject empty sets or single degenerate value
            if len(l_vals) <= 1 or len(r_vals) <= 1:
                continue

            common = l_vals & r_vals
            overlap_ratio = len(common) / max(min(len(l_vals), len(r_vals)), 1)

            # A shared label alone is not a verified entity key. For columns that
            # are not recognised entity identifiers, require near-unique values
            # on both sides before treating the field as a candidate key.
            if not (l_is_entity or r_is_entity):
                l_nonempty_count = sum(
                    1 for row in left_rows
                    if row.get(l_col) is not None and str(row.get(l_col, "")).strip()
                )
                r_nonempty_count = sum(
                    1 for row in right_rows
                    if row.get(r_col) is not None and str(row.get(r_col, "")).strip()
                )
                l_uniqueness = len(l_vals) / max(l_nonempty_count, 1)
                r_uniqueness = len(r_vals) / max(r_nonempty_count, 1)
                if l_uniqueness < 0.8 or r_uniqueness < 0.8:
                    continue

            # Reject small integer measures that happen to match names (e.g., 0, 1, 2)
            if not (l_is_entity or r_is_entity):
                try:
                    num_vals = [float(v) for v in common]
                    if all(v.is_integer() and 0 <= v <= 20 for v in num_vals):
                        continue
                except (ValueError, TypeError):
                    pass

            # Strict guard: require at least 5 common distinct values and at least 15% overlap
            if len(common) >= 5 and overlap_ratio >= 0.15:
                score = overlap_ratio
                if l_is_entity and r_is_entity:
                    score += 5.0
                elif l_is_entity or r_is_entity:
                    score += 2.0
                elif l_norm == r_norm:
                    score += 0.5
                candidates.append((l_col, r_col, score))

    candidates.sort(key=lambda c: c[2], reverse=True)
    return candidates


def inspect_cardinality(
    left_rows: list[dict[str, Any]],
    right_rows: list[dict[str, Any]],
    left_col: str,
    right_col: str,
) -> dict[str, Any]:
    """Inspects cardinality and matching statistics for a join key pair."""
    l_keys: list[str] = [str(r.get(left_col, "")).strip() for r in left_rows if r.get(left_col) is not None and str(r.get(left_col, "")).strip()]
    r_keys: list[str] = [str(r.get(right_col, "")).strip() for r in right_rows if r.get(right_col) is not None and str(r.get(right_col, "")).strip()]

    l_set = set(l_keys)
    r_set = set(r_keys)
    common_set = l_set & r_set

    l_has_dups = len(l_keys) > len(l_set)
    r_has_dups = len(r_keys) > len(r_set)

    if not l_has_dups and not r_has_dups:
        cardinality = "1:1"
    elif l_has_dups and not r_has_dups:
        cardinality = "N:1"
    elif not l_has_dups and r_has_dups:
        cardinality = "1:N"
    else:
        cardinality = "N:N"

    matched_count = len(common_set)
    left_eligible = len(l_set)
    right_eligible = len(r_set)
    total_eligible = max(left_eligible, right_eligible)
    unmatched_count = (left_eligible - matched_count) + (right_eligible - matched_count)
    coverage_ratio = matched_count / max(left_eligible, 1)

    return {
        "cardinality": cardinality,
        "is_safe": cardinality != "N:N",
        "matched_count": matched_count,
        "left_eligible": left_eligible,
        "right_eligible": right_eligible,
        "unmatched_count": unmatched_count,
        "coverage_ratio": round(coverage_ratio, 4),
        "common_set": common_set,
    }


def find_grouping_dimension(cols: list[str], rows: list[dict[str, Any]]) -> str | None:
    """Finds a privacy-safe categorical grouping dimension (e.g. Department, Category, Segment)."""
    group_patterns = [r"department", r"dept", r"category", r"segment", r"region", r"division", r"cohort", r"team"]
    for col in cols:
        if is_pii_column(col):
            continue
        lower = col.strip().lower()
        if any(re.search(pat, lower) for pat in group_patterns):
            vals = {str(r.get(col, "")).strip() for r in rows if r.get(col) is not None and str(r.get(col, "")).strip()}
            if 2 <= len(vals) <= 30:
                return col
    # Fallback to any low-cardinality non-PII categorical column
    for col in cols:
        if is_pii_column(col):
            continue
        vals = {str(r.get(col, "")).strip() for r in rows if r.get(col) is not None and str(r.get(col, "")).strip()}
        if 2 <= len(vals) <= 20:
            return col
    return None


def find_numeric_metric_column(cols: list[str], rows: list[dict[str, Any]], exclude_cols: set[str]) -> str | None:
    """Finds a representative numeric metric column, prioritizing summary and executive measures."""
    valid_cols: list[tuple[str, float]] = []
    priority_patterns = [r"total", r"final", r"overall", r"summary", r"annual", r"monthly", r"rate", r"score", r"amount", r"attendance", r"leave", r"revenue", r"sales"]

    for col in cols:
        if col in exclude_cols or is_pii_column(col):
            continue
        num_vals = []
        for r in rows:
            v = r.get(col)
            if v is not None and v != "":
                try:
                    num_vals.append(float(str(v).replace(",", "").replace("%", "").strip()))
                except (ValueError, TypeError):
                    pass
        if len(num_vals) >= len(rows) * 0.5:
            std = _calc_std(num_vals)
            if std > 0:
                score = 1.0
                lower = col.strip().lower()
                for pat in priority_patterns:
                    if re.search(pat, lower):
                        score += 3.0
                valid_cols.append((col, score))

    if not valid_cols:
        return None
    valid_cols.sort(key=lambda t: t[1], reverse=True)
    return valid_cols[0][0]


def _calc_std(vals: list[float]) -> float:
    if len(vals) < 2:
        return 0.0
    mean = sum(vals) / len(vals)
    return math.sqrt(sum((x - mean) ** 2 for x in vals) / (len(vals) - 1))


def _calc_pearson(x: list[float], y: list[float]) -> float:
    n = len(x)
    if n < 3:
        return 0.0
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    den_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x))
    den_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y))
    if den_x == 0 or den_y == 0:
        return 0.0
    return num / (den_x * den_y)


def _calc_spearman(x: list[float], y: list[float]) -> float:
    n = len(x)
    if n < 3:
        return 0.0

    def rank(seq):
        indexed = sorted(enumerate(seq), key=lambda t: t[1])
        ranks = [0.0] * len(seq)
        i = 0
        while i < len(seq):
            j = i
            while j + 1 < len(seq) and indexed[j + 1][1] == indexed[i][1]:
                j += 1
            avg_rank = (i + j + 2) / 2.0
            for k in range(i, j + 1):
                ranks[indexed[k][0]] = avg_rank
            i = j + 1
        return ranks

    rx = rank(x)
    ry = rank(y)
    return _calc_pearson(rx, ry)


def _currency_code(column_name: str) -> str | None:
    """Infer only explicit currency declarations; never guess from magnitude."""
    lower = column_name.strip().lower()
    currency_patterns = {
        "USD": (r"(?:^|[^a-z])usd(?:$|[^a-z])", r"us[_\s]?dollar", r"\$"),
        "EUR": (r"(?:^|[^a-z])eur(?:$|[^a-z])", r"euro", r"€"),
        "GBP": (r"(?:^|[^a-z])gbp(?:$|[^a-z])", r"pound", r"£"),
        "INR": (r"(?:^|[^a-z])inr(?:$|[^a-z])", r"rupee", r"₹"),
    }
    for code, patterns in currency_patterns.items():
        if any(re.search(pattern, lower) for pattern in patterns):
            return code
    return None


def _period_tokens(columns: list[str], rows: list[dict[str, Any]]) -> set[str]:
    """Extract comparable calendar tokens from explicit date/period columns."""
    period_columns = [
        col for col in columns
        if re.search(r"date|month|period|week|year", col.strip().lower())
    ]
    tokens: set[str] = set()
    for col in period_columns:
        for row in rows:
            raw = str(row.get(col, "")).strip()
            if not raw:
                continue
            month_match = re.search(r"(20\d{2})[-/]?(0[1-9]|1[0-2])", raw)
            week_match = re.search(r"(20\d{2})[-\s]?W(0?[1-9]|[1-4]\d|5[0-3])", raw, re.IGNORECASE)
            if month_match:
                tokens.add(f"{month_match.group(1)}-{month_match.group(2)}")
            elif week_match:
                tokens.add(f"{week_match.group(1)}-W{int(week_match.group(2)):02d}")
    return tokens


def _mean_by_key(
    rows: list[dict[str, Any]],
    key_column: str,
    metric_column: str,
) -> dict[str, float]:
    """Aggregate repeated observations to an explicit entity grain."""
    values: dict[str, list[float]] = {}
    for row in rows:
        key = str(row.get(key_column, "")).strip()
        if not key:
            continue
        try:
            value = float(str(row.get(metric_column, "")).replace(",", "").replace("%", "").strip())
        except (ValueError, TypeError):
            continue
        values.setdefault(key, []).append(value)
    return {key: sum(items) / len(items) for key, items in values.items() if items}


def build_enterprise_synthesis_element(
    conn: Any,
    dataset_id: int,
    sheet_id: int,
    manifest: SourceManifest,
    contract: SemanticContract,
    rows: list[dict[str, Any]],
) -> EnterpriseSynthesisSpec | None:
    """Builds the Element 10 Enterprise Synthesis specification for the dashboard."""
    # 1. Scope check: Fetch all sheets belonging to this dataset_id ONLY
    sheet_rows = conn.execute(
        "SELECT id, name, display_name, columns_json, row_count FROM sheets WHERE dataset_id=? ORDER BY id ASC",
        (dataset_id,),
    ).fetchall()

    if not sheet_rows:
        return None

    primary_columns = list(rows[0].keys()) if rows else []

    # Load metadata for all sibling sheets
    sibling_meta: list[dict[str, Any]] = []
    for r in sheet_rows:
        sid, s_name, s_disp, s_cols_json, s_row_count = r
        s_cols = json.loads(s_cols_json) if s_cols_json else []
        sibling_meta.append({
            "sheet_id": sid,
            "name": s_name,
            "display_name": s_disp or s_name,
            "columns": s_cols,
            "row_count": s_row_count or 0,
        })

    # If single sheet in dataset, return honest coverage-only specification
    if len(sibling_meta) <= 1:
        source_ref = EnterpriseSourceRef(
            sheet_id=sheet_id,
            display_name=manifest.display_name,
            snapshot=manifest.snapshot,
            entity_count=len(rows),
            period=None,
            role="primary",
        )
        combined_snap = compute_combined_snapshot([source_ref])
        return EnterpriseSynthesisSpec(
            component_id="enterprise_element",
            kind="coverage_only",
            business_concept="Cross-source coverage",
            title="Enterprise synthesis",
            sources=[source_ref],
            source_count=1,
            lead_finding=None,
            visual=EnterpriseVisualSpec(kind="none"),
            what_it_establishes="Dataset scope is currently restricted to 1 uploaded sheet.",
            what_it_does_not_establish="Cross-source lifecycle, matched comparison, or association metrics cannot be computed without a secondary sibling sheet in the same upload.",
            next_check="Upload a multi-sheet workbook or sibling table to evaluate verified cross-source enterprise relationships.",
            drilldown_targets=[
                EnterpriseDrilldownTarget(
                    sheet_id=sheet_id,
                    label=manifest.display_name,
                    target_type="sheet",
                    route=f"/explorer?sheet_id={sheet_id}",
                )
            ],
            glance=GlanceSpec(
                label="Evaluated sources",
                value=1,
                formatted_value="1 source",
                context_qualifier="Single sheet scope",
            ),
            explain=ExplainSpec(
                short_definition="Enterprise synthesis reconciles multiple sources within the same upload into verified lifecycle or cohort relationships.",
                exact_value_text="1 sheet evaluated (multi-source synthesis requires >= 2 sibling sheets).",
            ),
            inspect=InspectSpec(
                metric_title="Enterprise Synthesis Coverage",
                exact_value="1 source evaluated",
                what_this_counts="Number of sibling sheets evaluated in this dataset upload.",
                applicable_population=f"Dataset {dataset_id}",
                source_name=manifest.display_name,
                calculation_method="Count of sibling sheets in dataset upload catalog.",
                data_completeness=f"{len(rows)} records in primary sheet",
                workforce_coverage="100% of single sheet",
                selection_reason="Single sheet upload scope verified.",
                excluded_observations=0,
                limitations=["No secondary source available in this dataset for cross-reconciliation."],
                calculation_id=f"calc_ent_cov_{combined_snap[:8]}",
                definition_id="def_enterprise_coverage_v1",
                snapshot=combined_snap,
                provenance=f"Dataset {dataset_id} -> Sheet {sheet_id}: {manifest.display_name}",
            ),
            evidence=None,
            caption="1 evaluated source · Single-sheet scope",
        )

    # 2. Multi-source manifest: Load rows and snapshots for all sibling sheets
    source_refs: list[EnterpriseSourceRef] = []
    sibling_data: dict[int, dict[str, Any]] = {}

    for sm in sibling_meta:
        sid = sm["sheet_id"]
        if sid == sheet_id:
            s_rows = rows
            s_snap = manifest.snapshot
        else:
            # Fetch curated rows, fallback to raw rows
            recs = conn.execute(
                "SELECT data_json FROM sheet_curated_rows WHERE sheet_id=? ORDER BY row_index",
                (sid,),
            ).fetchall()
            if not recs:
                recs = conn.execute(
                    "SELECT data_json FROM sheet_rows WHERE sheet_id=? ORDER BY row_index",
                    (sid,),
                ).fetchall()
            s_rows = [json.loads(r[0]) for r in recs]

            # Deterministic snapshot for sibling sheet
            hasher = hashlib.sha256()
            hasher.update(str(sid).encode("utf-8"))
            hasher.update(json.dumps(sm["columns"], sort_keys=True).encode("utf-8"))
            for r in s_rows:
                hasher.update(json.dumps(r, sort_keys=True, default=str).encode("utf-8"))
            s_snap = hasher.hexdigest()[:16]

        s_ref = EnterpriseSourceRef(
            sheet_id=sid,
            display_name=sm["display_name"],
            snapshot=s_snap,
            entity_count=len(s_rows),
            period=None,
            role="primary" if sid == sheet_id else "sibling",
        )
        source_refs.append(s_ref)
        sibling_data[sid] = {
            "meta": sm,
            "ref": s_ref,
            "rows": s_rows,
            "columns": sm["columns"],
            "snapshot": s_snap,
        }

    combined_snapshot = compute_combined_snapshot(source_refs)
    other_sids = [sid for sid in sibling_data if sid != sheet_id]

    drilldown_targets = [
        EnterpriseDrilldownTarget(
            sheet_id=s.sheet_id,
            label=s.display_name,
            target_type="sheet",
            route=f"/explorer?sheet_id={s.sheet_id}",
        )
        for s in source_refs
    ]

    # Evaluate candidate sibling sheets against primary sheet
    best_candidate = None
    for other_id in other_sids:
        other = sibling_data[other_id]
        key_candidates = detect_candidate_join_keys(
            left_cols=primary_columns,
            right_cols=other["columns"],
            left_rows=rows,
            right_rows=other["rows"],
        )
        if not key_candidates:
            continue

        for l_key, r_key, score in key_candidates:
            card_info = inspect_cardinality(rows, other["rows"], l_key, r_key)

            if not card_info["is_safe"]:
                # N:N join without aggregation is rejected!
                continue

            if card_info["matched_count"] >= 5 and card_info["coverage_ratio"] >= 0.1:
                best_candidate = {
                    "other_id": other_id,
                    "other": other,
                    "left_key": l_key,
                    "right_key": r_key,
                    "cardinality": card_info["cardinality"],
                    "matched_count": card_info["matched_count"],
                    "left_eligible": card_info["left_eligible"],
                    "right_eligible": card_info["right_eligible"],
                    "unmatched_count": card_info["unmatched_count"],
                    "coverage_ratio": card_info["coverage_ratio"],
                    "common_set": card_info["common_set"],
                }
                break

        if best_candidate:
            break

    # If no safe join candidate passed, emit Coverage-only synthesis (Recipe E)
    if not best_candidate:
        return EnterpriseSynthesisSpec(
            component_id="enterprise_element",
            kind="coverage_only",
            business_concept="Cross-source coverage",
            title="Enterprise synthesis",
            sources=source_refs,
            source_count=len(source_refs),
            lead_finding=None,
            visual=EnterpriseVisualSpec(kind="none"),
            what_it_establishes=f"{len(source_refs)} sources evaluated within dataset {dataset_id}.",
            what_it_does_not_establish="No safe entity key or common period passed cardinality and overlap validation to support a combined analytical metric.",
            next_check="Verify key naming and entity format consistency across sheets to enable cross-source lifecycle or cohort analysis.",
            drilldown_targets=drilldown_targets,
            glance=GlanceSpec(
                label="Evaluated sources",
                value=len(source_refs),
                formatted_value=f"{len(source_refs)} sources",
                context_qualifier="No safe join key",
            ),
            explain=ExplainSpec(
                short_definition="Enterprise synthesis requires a verified join key with documented cardinality and sufficient overlap.",
                exact_value_text=f"{len(source_refs)} sheets evaluated, 0 safe connections verified.",
            ),
            inspect=InspectSpec(
                metric_title="Enterprise Synthesis Coverage",
                exact_value=f"{len(source_refs)} sources evaluated",
                what_this_counts="Number of sibling sheets screened for candidate join keys.",
                applicable_population=f"All sheets in Dataset {dataset_id}",
                source_name=manifest.display_name,
                calculation_method="Candidate key identification and overlap verification.",
                data_completeness=f"{sum(s.entity_count for s in source_refs)} records across {len(source_refs)} sheets",
                workforce_coverage="Screened across all sheets in dataset",
                selection_reason="Evaluated all sibling sheets within same upload.",
                excluded_observations=0,
                limitations=["No common verified entity key met minimum overlap (>= 15% overlap and >= 5 keys)."],
                calculation_id=f"calc_ent_cov_{combined_snapshot[:8]}",
                definition_id="def_enterprise_coverage_v1",
                snapshot=combined_snapshot,
                provenance=f"Dataset {dataset_id} ({len(source_refs)} sheets evaluated)",
            ),
            evidence=None,
            caption=f"{len(source_refs)} evaluated sources · 0 connected",
        )

    # We have a safe candidate! Let's evaluate recipes in strict order:
    other = best_candidate["other"]
    other_rows = other["rows"]
    l_key = best_candidate["left_key"]
    r_key = best_candidate["right_key"]
    matched_count = best_candidate["matched_count"]
    unmatched_count = best_candidate["unmatched_count"]
    coverage_ratio = best_candidate["coverage_ratio"]
    common_set = best_candidate["common_set"]
    left_eligible = best_candidate["left_eligible"]
    analytical_blocker: str | None = None

    left_periods = _period_tokens(primary_columns, rows)
    right_periods = _period_tokens(other["columns"], other_rows)
    if left_periods and right_periods and not (left_periods & right_periods):
        analytical_blocker = (
            "Source periods do not overlap, so the as-of policy rejects a combined analytical metric."
        )

    if re.search(r"date|month|period|week|year", f"{l_key} {r_key}", re.IGNORECASE):
        analytical_blocker = (
            "The candidate connection is a time index; raw trending series require detrending or "
            "first-difference validation before temporal co-movement can be reported."
        )

    # -------------------------------------------------------------
    # RECIPE A: Reconciled Lifecycle Metric
    # -------------------------------------------------------------
    # Check for order -> return, lead -> win, ticket -> satisfaction, or employee -> leave reconciliation
    left_col_names_lower = [c.lower() for c in primary_columns]
    right_col_names_lower = [c.lower() for c in other["columns"]]

    is_order_return = any("order" in c for c in left_col_names_lower) and any("return" in c for c in right_col_names_lower)
    is_lead_win = any("lead" in c for c in left_col_names_lower) and any("win" in c or "opp" in c for c in right_col_names_lower)

    if (is_order_return or is_lead_win) and not analytical_blocker:
        # Reconciled lifecycle rate
        recipe_title = "Delivered order return rate" if is_order_return else "Lead-to-win conversion rate"
        rate_val = round((matched_count / max(left_eligible, 1)) * 100, 1)

        evidence = CrossSourceEvidence(
            finding_id="finding_lifecycle_reconciled",
            recipe_id="recipe_a_lifecycle",
            title=recipe_title,
            observation=f"{matched_count} distinct entities reconciled across {manifest.display_name} and {other['ref'].display_name}.",
            interpretation=f"Verified lifecycle rate is {rate_val}% across {round(coverage_ratio * 100, 1)}% of eligible records. Unmatched records remain excluded.",
            metric_names=[recipe_title],
            values=[rate_val],
            units=["%"],
            paired_or_eligible_count=left_eligible,
            matched_count=matched_count,
            unmatched_count=unmatched_count,
            coverage_ratio=coverage_ratio,
            join_description=f"Joined on {l_key} ↔ {r_key} ({best_candidate['cardinality']}).",
            calculation_id=f"calc_ent_life_{combined_snapshot[:8]}",
            source_sheet_ids=[sheet_id, other["ref"].sheet_id],
            snapshot=combined_snapshot,
        )

        flow_points = [
            EnterpriseVisualPoint(label="Eligible cohort", x=0.0, y=float(left_eligible), sample_size=left_eligible, formatted_y=f"{left_eligible:,}"),
            EnterpriseVisualPoint(label="Reconciled stage", x=1.0, y=float(matched_count), sample_size=matched_count, formatted_y=f"{matched_count:,}"),
        ]

        return EnterpriseSynthesisSpec(
            component_id="enterprise_element",
            kind="reconciled_metric",
            business_concept="Reconciled lifecycle metric",
            title="Enterprise synthesis",
            sources=source_refs,
            source_count=len(source_refs),
            lead_finding=evidence,
            visual=EnterpriseVisualSpec(
                kind="lifecycle_flow",
                x_axis_title="Lifecycle stage",
                y_axis_title="Distinct entities",
                points=flow_points,
            ),
            what_it_establishes=f"{recipe_title} is {rate_val}% across {matched_count:,} verified matched entities without event-row multiplication.",
            what_it_does_not_establish="Unmatched records are not assumed to have passed or failed without verifiable receipt.",
            next_check=f"Inspect the {unmatched_count:,} unmatched records in Data Explorer to verify data capture timing.",
            drilldown_targets=drilldown_targets,
            glance=GlanceSpec(
                label=recipe_title,
                value=rate_val,
                formatted_value=f"{rate_val}%",
                unit="%",
                unit_display="explicit_suffix",
                context_qualifier=f"{matched_count:,} matched entities",
            ),
            explain=ExplainSpec(
                short_definition="Reconciled lifecycle rates connect distinct entities through verified milestones using unique identifiers.",
                exact_value_text=f"{rate_val}% ({matched_count:,} matched of {left_eligible:,} eligible).",
            ),
            inspect=InspectSpec(
                metric_title=recipe_title,
                exact_value=f"{rate_val}%",
                what_this_counts="Distinct entities successfully reconciled between lifecycle stages.",
                applicable_population=f"Eligible records in {manifest.display_name} with verified key in {other['ref'].display_name}.",
                source_name=f"{manifest.display_name} & {other['ref'].display_name}",
                calculation_method=f"Distinct entity matching on {l_key} = {r_key} with strict cardinality enforcement.",
                data_completeness=f"{matched_count:,} of {left_eligible:,} eligible entities matched ({round(coverage_ratio * 100, 1)}%)",
                workforce_coverage=f"{round(coverage_ratio * 100, 1)}% match coverage",
                selection_reason=f"Verified lifecycle entity progression between {manifest.display_name} and {other['ref'].display_name}.",
                excluded_observations=unmatched_count,
                limitations=["Events outside the observed recording window are excluded."],
                calculation_id=f"calc_ent_life_{combined_snapshot[:8]}",
                definition_id="def_enterprise_lifecycle_v1",
                snapshot=combined_snapshot,
                provenance=f"Sheets {sheet_id} & {other['ref'].sheet_id} in Dataset {dataset_id}",
            ),
            evidence=EvidenceResult(
                calculation_id=f"calc_ent_life_{combined_snapshot[:8]}",
                snapshot=combined_snapshot,
                definition_id="def_enterprise_lifecycle_v1",
                status="available",
                value=rate_val,
                unit="%",
                aggregation="ratio",
                numerator=float(matched_count),
                denominator=float(max(left_eligible, 1)),
                is_known_zero=matched_count == 0,
                missing_observations=0,
                invalid_observations=0,
                excluded_observations=unmatched_count,
                coverage_ratio=coverage_ratio,
                calculation_method=f"Distinct entity join on {l_key} = {r_key}.",
                provenance=f"Dataset {dataset_id}: {manifest.display_name} ↔ {other['ref'].display_name}",
                limitations=["Cross-source lifecycle timing relies on recorded event timestamps."],
            ),
            caption=f"{len(source_refs)} evaluated sources · 2 connected ({rate_val}% lifecycle rate)",
        )

    # -------------------------------------------------------------
    # RECIPE B: Matched Cohort Comparison (Privacy-safe aggregation)
    # -------------------------------------------------------------
    # Grouping dimension (e.g. Department, Category, Segment)
    group_col = find_grouping_dimension(primary_columns, rows)
    num_l = find_numeric_metric_column(primary_columns, rows, exclude_cols={l_key})
    num_r = find_numeric_metric_column(other["columns"], other_rows, exclude_cols={r_key})

    left_currency = _currency_code(num_l) if num_l else None
    right_currency = _currency_code(num_r) if num_r else None
    if left_currency and right_currency and left_currency != right_currency:
        analytical_blocker = (
            f"Mixed currencies ({left_currency} and {right_currency}) cannot be combined without "
            "an explicit exchange-rate and as-of policy."
        )

    # Build entity lookup map for right table on r_key
    r_map: dict[str, list[dict[str, Any]]] = {}
    for r in other_rows:
        k = str(r.get(r_key, "")).strip()
        if k:
            r_map.setdefault(k, []).append(r)

    if group_col and num_l and num_r and not analytical_blocker:
        # Aggregate to cohort grain to ensure privacy-safe representation (NO personal PII rows!)
        cohort_stats: dict[str, dict[str, Any]] = {}
        left_metric_by_key = _mean_by_key(rows, l_key, num_l)
        right_metric_by_key = _mean_by_key(other_rows, r_key, num_r)
        groups_by_key: dict[str, set[str]] = {}
        for row in rows:
            key = str(row.get(l_key, "")).strip()
            group = str(row.get(group_col, "")).strip()
            if key and group:
                groups_by_key.setdefault(key, set()).add(group)

        for k in sorted(common_set):
            groups = groups_by_key.get(k, set())
            if len(groups) != 1 or k not in left_metric_by_key or k not in right_metric_by_key:
                continue
            grp = next(iter(groups))
            vl = left_metric_by_key[k]
            vr = right_metric_by_key[k]

            if grp not in cohort_stats:
                cohort_stats[grp] = {"x_vals": [], "y_vals": [], "count": 0}
            cohort_stats[grp]["x_vals"].append(vl)
            cohort_stats[grp]["y_vals"].append(vr)
            cohort_stats[grp]["count"] += 1

        # Require at least 2 valid cohorts with >= 3 members each
        valid_cohorts = [grp for grp, d in cohort_stats.items() if d["count"] >= 3]

        if len(valid_cohorts) >= 2:
            visual_points: list[EnterpriseVisualPoint] = []
            for grp in sorted(valid_cohorts):
                d = cohort_stats[grp]
                avg_x = round(sum(d["x_vals"]) / len(d["x_vals"]), 2)
                avg_y = round(sum(d["y_vals"]) / len(d["y_vals"]), 2)
                visual_points.append(
                    EnterpriseVisualPoint(
                        label=grp,
                        x=avg_x,
                        y=avg_y,
                        sample_size=d["count"],
                        formatted_x=f"{avg_x:,}",
                        formatted_y=f"{avg_y:,}",
                    )
                )

            evidence = CrossSourceEvidence(
                finding_id="finding_cohort_comparison",
                recipe_id="recipe_b_cohort_comparison",
                title=f"Matched cohort comparison across {len(valid_cohorts)} {group_col.lower()}s",
                observation=f"{manifest.display_name} ({num_l}) and {other['ref'].display_name} ({num_r}) compared across {len(valid_cohorts)} privacy-safe cohorts.",
                interpretation=f"Cohort comparison reflects {matched_count:,} matched entities aggregated by {group_col} ({round(coverage_ratio * 100, 1)}% match coverage).",
                metric_names=[num_l, num_r],
                values=[visual_points[0].x, visual_points[0].y],
                units=["avg", "avg"],
                paired_or_eligible_count=len(rows),
                matched_count=matched_count,
                unmatched_count=unmatched_count,
                coverage_ratio=coverage_ratio,
                join_description=f"Aggregated by {group_col} via {l_key} ↔ {r_key} ({best_candidate['cardinality']}).",
                calculation_id=f"calc_ent_cohort_{combined_snapshot[:8]}",
                source_sheet_ids=[sheet_id, other["ref"].sheet_id],
                snapshot=combined_snapshot,
            )

            return EnterpriseSynthesisSpec(
                component_id="enterprise_element",
                kind="matched_comparison",
                business_concept="Matched cohort comparison",
                title="Enterprise synthesis",
                sources=source_refs,
                source_count=len(source_refs),
                lead_finding=evidence,
                visual=EnterpriseVisualSpec(
                    kind="paired_dot",
                    x_axis_title=f"{manifest.display_name} — {num_l}",
                    y_axis_title=f"{other['ref'].display_name} — {num_r}",
                    points=visual_points,
                ),
                what_it_establishes=f"{num_l} and {num_r} differ systematically across {len(valid_cohorts)} matched {group_col.lower()} cohorts.",
                what_it_does_not_establish="This comparison reflects observed group aggregates and does not establish that group membership causes differences.",
                next_check=f"Compare cohort sizes, role mix, and observation periods before planning targeted operational changes.",
                drilldown_targets=drilldown_targets,
                glance=GlanceSpec(
                    label="Matched cohorts",
                    value=len(valid_cohorts),
                    formatted_value=f"{len(valid_cohorts)} cohorts",
                    context_qualifier=f"{matched_count:,} matched entities",
                ),
                explain=ExplainSpec(
                    short_definition="Matched cohort comparison aggregates linked multi-source measures to privacy-safe group grains.",
                    exact_value_text=f"{len(valid_cohorts)} {group_col.lower()} cohorts evaluated across {matched_count:,} matched records.",
                ),
                inspect=InspectSpec(
                    metric_title="Matched Cohort Comparison",
                    exact_value=f"{len(valid_cohorts)} cohorts evaluated",
                    what_this_counts=f"Privacy-safe {group_col.lower()} cohorts with at least 3 matched entities.",
                    applicable_population=f"Matched records between {manifest.display_name} and {other['ref'].display_name}.",
                    source_name=f"{manifest.display_name} & {other['ref'].display_name}",
                    calculation_method=f"Privacy-safe aggregation by {group_col} joined on {l_key} = {r_key}.",
                    data_completeness=f"{matched_count:,} matched records grouped into {len(valid_cohorts)} cohorts",
                    workforce_coverage=f"{round(coverage_ratio * 100, 1)}% match coverage",
                    selection_reason=f"Privacy-safe cohort comparison across {group_col} dimension.",
                    excluded_observations=unmatched_count,
                    limitations=["Aggregated group figures mask within-cohort variance."],
                    calculation_id=f"calc_ent_cohort_{combined_snapshot[:8]}",
                    definition_id="def_enterprise_cohort_v1",
                    snapshot=combined_snapshot,
                    provenance=f"Sheets {sheet_id} & {other['ref'].sheet_id} in Dataset {dataset_id}",
                ),
                evidence=EvidenceResult(
                    calculation_id=f"calc_ent_cohort_{combined_snapshot[:8]}",
                    snapshot=combined_snapshot,
                    definition_id="def_enterprise_cohort_v1",
                    status="available",
                    value=float(len(valid_cohorts)),
                    unit="cohorts",
                    aggregation="cohort_mean",
                    numerator=float(len(valid_cohorts)),
                    denominator=float(len(valid_cohorts)),
                    is_known_zero=False,
                    missing_observations=0,
                    invalid_observations=0,
                    excluded_observations=unmatched_count,
                    coverage_ratio=coverage_ratio,
                    calculation_method=f"Grouped by {group_col} over verified {l_key} = {r_key} matches.",
                    provenance=f"Dataset {dataset_id}: {manifest.display_name} ↔ {other['ref'].display_name}",
                    limitations=["Evaluated at aggregated group level to prevent individual row exposure."],
                ),
                caption=f"{len(source_refs)} evaluated sources · 2 connected ({len(valid_cohorts)} cohorts)",
            )

    # -------------------------------------------------------------
    # RECIPE C: Cross-Source Association (Correlation guards)
    # -------------------------------------------------------------
    if num_l and num_r and not analytical_blocker:
        x_paired: list[float] = []
        y_paired: list[float] = []
        left_metric_by_key = _mean_by_key(rows, l_key, num_l)
        right_metric_by_key = _mean_by_key(other_rows, r_key, num_r)

        for k in sorted(common_set):
            if k in left_metric_by_key and k in right_metric_by_key:
                x_paired.append(left_metric_by_key[k])
                y_paired.append(right_metric_by_key[k])

        # Strict statistical guards:
        # 1. Sample size guard: N >= 30
        # 2. Nonzero variance guard: std_x > 0 and std_y > 0
        if len(x_paired) >= 30 and _calc_std(x_paired) > 0 and _calc_std(y_paired) > 0:
            r_val = _calc_pearson(x_paired, y_paired)
            rho_val = _calc_spearman(x_paired, y_paired)

            # Direction agreement check: sign(r) == sign(rho)
            direction_agrees = (r_val >= 0 and rho_val >= 0) or (r_val <= 0 and rho_val <= 0)

            # Outlier sensitivity check: trim top/bottom 2.5% extreme points
            n_trim = max(int(len(x_paired) * 0.025), 1)
            sorted_by_x = sorted(zip(x_paired, y_paired), key=lambda p: p[0])
            trimmed = sorted_by_x[n_trim:-n_trim]
            trim_x = [p[0] for p in trimmed]
            trim_y = [p[1] for p in trimmed]

            trim_r = _calc_pearson(trim_x, trim_y) if len(trim_x) >= 20 and _calc_std(trim_x) > 0 and _calc_std(trim_y) > 0 else r_val
            outlier_stable = (r_val >= 0 and trim_r >= 0) or (r_val <= 0 and trim_r <= 0)
            if abs(r_val - trim_r) > 0.45:
                outlier_stable = False

            if direction_agrees and outlier_stable and abs(r_val) >= 0.15:
                # Privacy-safe aggregation for scatter visual (aggregate into 10 quantiles/bins)
                n_bins = min(10, len(x_paired) // 3)
                bin_step = len(sorted_by_x) / n_bins
                scatter_points: list[EnterpriseVisualPoint] = []
                for i in range(n_bins):
                    chunk = sorted_by_x[int(i * bin_step):int((i + 1) * bin_step)]
                    if chunk:
                        bx = round(sum(p[0] for p in chunk) / len(chunk), 2)
                        by = round(sum(p[1] for p in chunk) / len(chunk), 2)
                        scatter_points.append(
                            EnterpriseVisualPoint(
                                label=f"Bin {i + 1}",
                                x=bx,
                                y=by,
                                sample_size=len(chunk),
                                formatted_x=f"{bx:,}",
                                formatted_y=f"{by:,}",
                            )
                        )

                corr_label = "positive" if r_val > 0 else "negative"
                evidence = CrossSourceEvidence(
                    finding_id="finding_cross_association",
                    recipe_id="recipe_c_association",
                    title=f"Cross-source association (r = {r_val:.2f})",
                    observation=f"{num_l} and {num_r} exhibit a {corr_label} statistical association across {len(x_paired):,} matched records (Pearson r = {r_val:.2f}, Spearman ρ = {rho_val:.2f}).",
                    interpretation="This statistical association establishes co-movement across sources, never causation or policy impact.",
                    metric_names=[num_l, num_r],
                    values=[round(r_val, 2), round(rho_val, 2)],
                    units=["r", "ρ"],
                    paired_or_eligible_count=len(rows),
                    matched_count=len(x_paired),
                    unmatched_count=unmatched_count,
                    coverage_ratio=coverage_ratio,
                    join_description=f"Joined on {l_key} ↔ {r_key} ({best_candidate['cardinality']}).",
                    calculation_id=f"calc_ent_assoc_{combined_snapshot[:8]}",
                    source_sheet_ids=[sheet_id, other["ref"].sheet_id],
                    snapshot=combined_snapshot,
                )

                return EnterpriseSynthesisSpec(
                    component_id="enterprise_element",
                    kind="cross_source_association",
                    business_concept="Cross-source association",
                    title="Enterprise synthesis",
                    sources=source_refs,
                    source_count=len(source_refs),
                    lead_finding=evidence,
                    visual=EnterpriseVisualSpec(
                        kind="scatter",
                        x_axis_title=f"{manifest.display_name} — {num_l}",
                        y_axis_title=f"{other['ref'].display_name} — {num_r}",
                        points=scatter_points,
                        reference_line="Descriptive trend line (non-causal)",
                    ),
                    what_it_establishes=f"{num_l} and {num_r} vary together across {len(x_paired):,} matched records (r = {r_val:.2f}).",
                    what_it_does_not_establish="This statistical association does not prove that changing one variable will influence the other.",
                    next_check="Examine underlying operational factors, timing lags, and confounding variables before acting on this relationship.",
                    drilldown_targets=drilldown_targets,
                    glance=GlanceSpec(
                        label="Cross-source association",
                        value=round(r_val, 2),
                        formatted_value=f"r = {r_val:.2f}",
                        context_qualifier=f"{len(x_paired):,} matched records",
                    ),
                    explain=ExplainSpec(
                        short_definition="Cross-source association measures whether metrics from separate tables move together across verified entities.",
                        exact_value_text=f"Pearson r = {r_val:.2f}, Spearman ρ = {rho_val:.2f} across {len(x_paired):,} matched pairs.",
                    ),
                    inspect=InspectSpec(
                        metric_title="Cross-Source Association",
                        exact_value=f"r = {r_val:.2f}",
                        what_this_counts=f"Paired observations of {num_l} and {num_r} across matched entities.",
                        applicable_population=f"Records in {manifest.display_name} and {other['ref'].display_name} with valid numerical values.",
                        source_name=f"{manifest.display_name} & {other['ref'].display_name}",
                        calculation_method="Bivariate correlation with Pearson/Spearman direction agreement and 2.5% trimmed outlier stability.",
                        data_completeness=f"{len(x_paired):,} complete pairs with nonzero variance",
                        workforce_coverage=f"{round(coverage_ratio * 100, 1)}% match coverage",
                        selection_reason="Cross-source statistical association passing sample size and stability screening.",
                        excluded_observations=unmatched_count,
                        limitations=["Correlation does not establish causation or policy impact."],
                        calculation_id=f"calc_ent_assoc_{combined_snapshot[:8]}",
                        definition_id="def_enterprise_assoc_v1",
                        snapshot=combined_snapshot,
                        provenance=f"Sheets {sheet_id} & {other['ref'].sheet_id} in Dataset {dataset_id}",
                    ),
                    evidence=EvidenceResult(
                        calculation_id=f"calc_ent_assoc_{combined_snapshot[:8]}",
                        snapshot=combined_snapshot,
                        definition_id="def_enterprise_assoc_v1",
                        status="available",
                        value=round(r_val, 2),
                        unit="r",
                        aggregation="cross_correlation",
                        numerator=round(r_val, 2),
                        denominator=1.0,
                        is_known_zero=round(r_val, 2) == 0.0,
                        missing_observations=0,
                        invalid_observations=0,
                        excluded_observations=unmatched_count,
                        coverage_ratio=coverage_ratio,
                        calculation_method=f"Pearson and Spearman correlation over {len(x_paired):,} matched keys.",
                        provenance=f"Dataset {dataset_id}: {manifest.display_name} ↔ {other['ref'].display_name}",
                        limitations=["Descriptive correlation only; non-causal."],
                    ),
                    caption=f"{len(source_refs)} evaluated sources · 2 connected (r = {r_val:.2f})",
                )

    # -------------------------------------------------------------
    # Fallback to Coverage-Only Synthesis (Recipe E)
    # -------------------------------------------------------------
    return EnterpriseSynthesisSpec(
        component_id="enterprise_element",
        kind="coverage_only",
        business_concept="Cross-source coverage",
        title="Enterprise synthesis",
        sources=source_refs,
        source_count=len(source_refs),
        lead_finding=None,
        visual=EnterpriseVisualSpec(kind="none"),
        what_it_establishes=f"{len(source_refs)} sources evaluated within dataset {dataset_id}; key overlap on {l_key} ↔ {r_key} verified across {matched_count:,} records.",
        what_it_does_not_establish=analytical_blocker or "Compatible numeric metrics or cohort dimensions were insufficient to produce a statistically defensible lifecycle rate, cohort comparison, or association.",
        next_check="Inspect individual sheets in Data Explorer to verify metric definitions and compatibility.",
        drilldown_targets=drilldown_targets,
        glance=GlanceSpec(
            label="Verified key overlap",
            value=matched_count,
            formatted_value=f"{matched_count:,} matched",
            context_qualifier="Coverage only",
        ),
        explain=ExplainSpec(
            short_definition="Enterprise synthesis requires compatible numeric metrics or cohort dimensions to calculate cross-source relationships.",
            exact_value_text=f"{matched_count:,} matched keys on {l_key} ↔ {r_key}, 0 compatible analytical recipes.",
        ),
        inspect=InspectSpec(
            metric_title="Verified Key Coverage",
            exact_value=f"{matched_count:,} matched keys",
            what_this_counts="Distinct entities matching on verified key.",
            applicable_population=f"Dataset {dataset_id}: {manifest.display_name} and {other['ref'].display_name}",
            source_name=f"{manifest.display_name} & {other['ref'].display_name}",
            calculation_method=f"Entity match on {l_key} = {r_key} with recipe screening across lifecycle, cohort, and association rules.",
            data_completeness=f"{matched_count:,} matched of {len(rows):,} eligible records ({round(coverage_ratio * 100, 1)}%)",
            workforce_coverage=f"{round(coverage_ratio * 100, 1)}% match coverage",
            selection_reason="Key overlap verified, awaiting compatible analytical recipe dimensions.",
            excluded_observations=unmatched_count,
            limitations=[analytical_blocker or "No compatible numeric measures supported lifecycle flow or association."],
            calculation_id=f"calc_ent_cov_{combined_snapshot[:8]}",
            definition_id="def_enterprise_coverage_v1",
            snapshot=combined_snapshot,
            provenance=f"Dataset {dataset_id} ({len(source_refs)} sheets evaluated)",
        ),
        evidence=None,
        caption=f"{len(source_refs)} evaluated sources · {matched_count:,} matched keys (coverage only)",
    )
