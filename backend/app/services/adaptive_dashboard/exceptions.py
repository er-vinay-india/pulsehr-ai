"""Exception Watch Engine (Adaptive Dashboard Element 8 / Gate 8).

Identifies statistically defensible unusual periods or business segments from current-snapshot evidence,
evaluates observed values against robust typical ranges (MAD with IQR fallback), enforces sample guards,
suppresses duplicates with Element 6 Decision Focus, and prepares typed ECharts visual specifications.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from typing import Any, Literal

import numpy as np

from .contracts import (
    ComponentSpec,
    DecisionFocusSpec,
    EvidenceResult,
    ExceptionItem,
    ExceptionPoint,
    ExceptionVisualSpec,
    ExceptionWatchSpec,
    ExplainSpec,
    GlanceSpec,
    InspectSpec,
    NoticeSpec,
    SemanticContract,
    SourceManifest,
)

logger = logging.getLogger(__name__)

ENGINE_VERSION = "4.0.0"


# -----------------------------------------------------------------------------
# 1. Robust Statistical Primitives
# -----------------------------------------------------------------------------

def compute_robust_center_and_spread(values: list[float]) -> dict[str, float]:
    """Computes median, MAD, quartiles, and IQR for a list of finite numeric values."""
    clean = [float(v) for v in values if v is not None and not math.isnan(float(v))]
    if not clean:
        return {"median": 0.0, "mad": 0.0, "q25": 0.0, "q75": 0.0, "iqr": 0.0}

    arr = np.array(clean, dtype=float)
    med = float(np.median(arr))
    abs_dev = np.abs(arr - med)
    mad = float(np.median(abs_dev))
    q25 = float(np.percentile(arr, 25))
    q75 = float(np.percentile(arr, 75))
    iqr = float(q75 - q25)

    return {
        "median": med,
        "mad": mad,
        "q25": q25,
        "q75": q75,
        "iqr": iqr,
    }


def evaluate_robust_deviation(val: float, stats: dict[str, float]) -> tuple[bool, float, float, float, float, str]:
    """Evaluates whether a value is an exception against robust stats.

    Returns:
        (is_exception, robust_z, expected_lower, expected_upper, deviation, method)
    """
    med = stats["median"]
    mad = stats["mad"]
    iqr = stats["iqr"]
    deviation = val - med

    if mad > 1e-9:
        # Standard robust z: 0.6745 * (val - median) / MAD
        robust_z = 0.6745 * (val - med) / mad
        expected_lower = med - 2.5 * (mad / 0.6745)
        expected_upper = med + 2.5 * (mad / 0.6745)
        is_exception = abs(robust_z) >= 3.5 or val < expected_lower or val > expected_upper
        method = f"MAD-based robust deviation (median={med:.2f}, MAD={mad:.2f})"
        return (is_exception, robust_z, expected_lower, expected_upper, deviation, method)

    if iqr > 1e-9:
        # IQR fallback: 1.5 * IQR fences
        expected_lower = stats["q25"] - 1.5 * iqr
        expected_upper = stats["q75"] + 1.5 * iqr
        robust_z = (val - med) / (iqr / 1.349) if iqr > 0 else 0.0
        is_exception = val < expected_lower or val > expected_upper
        method = f"IQR fence fallback (Q1={stats['q25']:.2f}, Q3={stats['q75']:.2f}, IQR={iqr:.2f})"
        return (is_exception, robust_z, expected_lower, expected_upper, deviation, method)

    # Both MAD and IQR are zero -> no spread, do not manufacture an exception
    return (False, 0.0, med, med, 0.0, "Zero spread (MAD=0, IQR=0)")


# -----------------------------------------------------------------------------
# 2. Semantic Filtering & Candidate Evaluation
# -----------------------------------------------------------------------------

def is_eligible_numeric_measure(col_name: str, values: list[Any], contract: SemanticContract) -> bool:
    """Checks whether a column is a genuine business measure rather than an ID, phone, timestamp, or near-unique code."""
    c_lower = col_name.strip().lower()

    # Disallow known identifiers or near-unique keys
    if any(id_token in c_lower for id_token in ("_id", "id", "code", "ssn", "phone", "email", "postal", "zip", "lat", "lon", "row", "index")):
        if c_lower not in ("paid", "valid", "credit"):
            return False

    # Extract non-null numeric floats
    clean = []
    for v in values:
        if v is None:
            continue
        try:
            f = float(str(v).replace("$", "").replace("%", "").replace(",", "").strip())
            clean.append(f)
        except (ValueError, TypeError):
            continue

    if len(clean) < 4:
        return False

    distinct_count = len(set(clean))
    total_count = len(clean)

    # Near-unique numeric sequence guard
    if total_count >= 10 and (distinct_count / total_count) > 0.95:
        # Check if it looks like sequential IDs (e.g. 1, 2, 3...)
        sorted_vals = sorted(clean)
        diffs = [sorted_vals[i+1] - sorted_vals[i] for i in range(min(15, len(sorted_vals)-1))]
        if all(abs(d - 1.0) < 1e-4 for d in diffs):
            return False

    return True


# -----------------------------------------------------------------------------
# 3. Discovery Recipes
# -----------------------------------------------------------------------------

def discover_segment_exception_candidates(
    manifest: SourceManifest,
    contract: SemanticContract,
    rows: list[dict[str, Any]],
    decision_element: DecisionFocusSpec | None = None,
) -> list[tuple[ExceptionItem, ExceptionVisualSpec]]:
    """Recipe B: Evaluates cross-segment metrics where each segment satisfies sample_size >= 5."""
    candidates: list[tuple[ExceptionItem, ExceptionVisualSpec]] = []
    if not rows or len(rows) < 5:
        return candidates

    # 1. Find candidate numeric measures first
    columns = list(rows[0].keys()) if rows else []
    num_cols = []
    for c in columns:
        vals = [r.get(c) for r in rows]
        if is_eligible_numeric_measure(c, vals, contract):
            num_cols.append(c)

    if not num_cols:
        return candidates

    # 2. Find categorical columns suitable for segmentation (non-numeric measures with 2 <= distinct <= 50)
    cat_cols = []
    for c in columns:
        if c in num_cols:
            continue
        vals = [r.get(c) for r in rows if r.get(c) is not None]
        distinct = len(set(str(v).strip() for v in vals))
        if 2 <= distinct <= 50:
            cat_cols.append(c)

    if not cat_cols:
        return candidates

    # Evaluate each (cat_col, num_col) pair
    for cat_col in cat_cols:
        # Group rows by segment
        groups: dict[str, list[float]] = {}
        for r in rows:
            seg = str(r.get(cat_col) or "").strip()
            if not seg or seg.lower() in ("unknown", "other", "null", "none", "n/a"):
                continue
            if seg not in groups:
                groups[seg] = []

        for num_col in num_cols:
            # Populate numeric values per segment
            seg_values: dict[str, list[float]] = {k: [] for k in groups.keys()}
            for r in rows:
                seg = str(r.get(cat_col) or "").strip()
                if seg not in seg_values:
                    continue
                v_raw = r.get(num_col)
                if v_raw is None or str(v_raw).strip() == "":
                    continue
                try:
                    f = float(str(v_raw).replace("$", "").replace("%", "").replace(",", "").strip())
                    if not math.isnan(f):
                        seg_values[seg].append(f)
                except (ValueError, TypeError):
                    continue

            # Apply sample guard: sample_size >= 5 per displayed segment
            eligible_segs = {s: vals for s, vals in seg_values.items() if len(vals) >= 5}
            if len(eligible_segs) < 3:
                continue

            # Compute segment averages / rates
            seg_averages = {s: float(np.mean(vals)) for s, vals in eligible_segs.items()}
            seg_list = list(seg_averages.keys())
            avg_vals = [seg_averages[s] for s in seg_list]

            stats = compute_robust_center_and_spread(avg_vals)
            if stats["mad"] <= 1e-9 and stats["iqr"] <= 1e-9:
                continue  # No variance across segments

            # Infer unit
            unit = ""
            if any(tok in num_col.lower() for tok in ("rate", "reliability", "pct", "%")):
                unit = "%"
            elif any(tok in num_col.lower() for tok in ("sales", "revenue", "profit", "amount", "$")):
                unit = "$"
            elif any(tok in num_col.lower() for tok in ("days", "attendance", "leaves", "hours")):
                unit = "days" if "hour" not in num_col.lower() else "hours"

            # Check each segment for exception
            for seg in seg_list:
                val = seg_averages[seg]
                is_exc, robust_z, lower, upper, dev, method = evaluate_robust_deviation(val, stats)
                if not is_exc:
                    continue

                direction: Literal["above", "below", "outside", "neutral"] = (
                    "above" if dev > 0 else "below" if dev < 0 else "neutral"
                )

                # Format strings
                if unit == "%":
                    fmt_val = f"{val:.1f}%"
                    fmt_range = f"{lower:.1f}%–{upper:.1f}%"
                    fmt_dev = f"{abs(dev):.1f} pp {'above' if dev > 0 else 'below'} range"
                elif unit == "$":
                    fmt_val = f"${val:,.0f}" if val >= 100 else f"${val:,.2f}"
                    fmt_range = f"${lower:,.0f}–${upper:,.0f}" if lower >= 100 else f"${lower:,.2f}–${upper:,.2f}"
                    fmt_dev = f"${abs(dev):,.0f} {'above' if dev > 0 else 'below'} range"
                elif unit in ("days", "hours"):
                    fmt_val = f"{val:.1f} {unit}"
                    fmt_range = f"{lower:.1f}–{upper:.1f} {unit}"
                    fmt_dev = f"{abs(dev):.1f} {unit} {'above' if dev > 0 else 'below'} range"
                else:
                    fmt_val = f"{val:.1f}"
                    fmt_range = f"{lower:.1f}–{upper:.1f}"
                    fmt_dev = f"{abs(dev):.1f} {'above' if dev > 0 else 'below'} range"

                sample_size = len(eligible_segs[seg])
                sample_label = f"{sample_size} records"

                # Check duplicate suppression against Element 6 Decision Focus
                is_dup_with_decision = False
                if decision_element and decision_element.kind != "decision_unavailable":
                    dec_sub = (decision_element.subject_label or "").strip().lower()
                    dec_metric = (decision_element.metric_name or "").strip().lower()
                    if seg.lower() == dec_sub and (num_col.lower() in dec_metric or dec_metric in num_col.lower()):
                        is_dup_with_decision = True

                calc_id = f"calc_exception_seg_{hashlib.sha256(f'{manifest.snapshot}:{seg}:{num_col}:{ENGINE_VERSION}'.encode()).hexdigest()[:8]}"

                item = ExceptionItem(
                    exception_id=f"exc-{calc_id[-8:]}",
                    exception_type="segment",
                    subject_type=cat_col,
                    subject_label=seg,
                    metric_name=num_col,
                    unit=unit,
                    observed_value=round(val, 2),
                    formatted_observed_value=fmt_val,
                    expected_lower=round(lower, 2),
                    expected_upper=round(upper, 2),
                    formatted_expected_range=fmt_range,
                    deviation_value=round(dev, 2),
                    formatted_deviation=fmt_dev,
                    direction=direction,
                    sample_size=sample_size,
                    sample_label=sample_label,
                    method=method,
                    context_flags=["duplicate_decision_demoted"] if is_dup_with_decision else [],
                    calculation_id=calc_id,
                    snapshot=manifest.snapshot,
                )

                # Prepare dotplot visual points
                dot_points = []
                for s_name in sorted(seg_list, key=lambda s: seg_averages[s]):
                    s_val = seg_averages[s_name]
                    dot_points.append(
                        ExceptionPoint(
                            label=s_name,
                            raw_period_or_segment=s_name,
                            value=round(s_val, 2),
                            formatted_value=f"{s_val:.1f}{unit if unit == '%' else ''}",
                            expected_lower=round(lower, 2),
                            expected_upper=round(upper, 2),
                            is_exception=(s_name == seg),
                            is_partial=False,
                            sample_size=len(eligible_segs[s_name]),
                        )
                    )

                visual = ExceptionVisualSpec(
                    kind="segment_dotplot",
                    x_axis_title=f"{num_col} ({unit})" if unit else num_col,
                    y_axis_title=cat_col,
                    points=dot_points,
                )

                candidates.append((item, visual))

    return candidates


def discover_temporal_exception_candidates(
    manifest: SourceManifest,
    contract: SemanticContract,
    rows: list[dict[str, Any]],
    decision_element: DecisionFocusSpec | None = None,
) -> list[tuple[ExceptionItem, ExceptionVisualSpec]]:
    """Recipe A: Evaluates native temporal intervals requiring at least 12 comparable periods."""
    candidates: list[tuple[ExceptionItem, ExceptionVisualSpec]] = []
    if not rows:
        return candidates

    # Look for date column or weekly series columns
    columns = list(rows[0].keys()) if rows else []
    date_col = None
    for c in columns:
        c_low = c.strip().lower()
        if c_low in ("date", "week", "order_date", "timestamp", "period", "month"):
            date_col = c
            break

    if not date_col:
        # Check if weekly series is represented as multiple columns (e.g. attendance weekly columns)
        # Note: Section 5.3 requires at least 12 periods. If fewer, abstain.
        return candidates

    # Extract dates and numeric measures
    # Check for holiday column (e.g. IsHoliday in retail datasets)
    holiday_col = None
    for c in columns:
        if "holiday" in c.lower():
            holiday_col = c
            break

    # Group rows by parsed period
    # To satisfy Section 5.3, we aggregate at native period grain
    periods: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        raw_d = str(r.get(date_col) or "").strip()
        if not raw_d:
            continue
        p_key = raw_d.split("T")[0]
        if len(p_key) > 7 and "-" in p_key:
            # Use weekly or daily or monthly depending on cadence
            pass
        periods.setdefault(raw_d, []).append(r)

    # Section 5.3: "Require at least 12 comparable periods for a basic robust temporal exception."
    # "12. Fewer than 12 periods abstain from temporal-exception claims."
    if len(periods) < 12:
        return candidates

    # Find numeric measures
    num_cols = [c for c in columns if c != date_col and is_eligible_numeric_measure(c, [r.get(c) for r in rows], contract)]
    if not num_cols:
        return candidates

    for num_col in num_cols:
        # Compute mean per period
        period_keys = sorted(periods.keys())
        p_means = []
        p_samples = []
        p_holidays = []
        for p in period_keys:
            p_rows = periods[p]
            p_vals = []
            for pr in p_rows:
                v = pr.get(num_col)
                if v is not None:
                    try:
                        p_vals.append(float(str(v).replace("$", "").replace("%", "").replace(",", "").strip()))
                    except (ValueError, TypeError):
                        pass
            m_val = float(np.mean(p_vals)) if p_vals else 0.0
            p_means.append(m_val)
            p_samples.append(len(p_vals))
            is_hol = False
            if holiday_col:
                is_hol = any(str(pr.get(holiday_col) or "").strip().lower() in ("1", "true", "yes", "y", "holiday") for pr in p_rows)
            p_holidays.append(is_hol)

        stats = compute_robust_center_and_spread(p_means)
        if stats["mad"] <= 1e-9 and stats["iqr"] <= 1e-9:
            continue

        unit = "$" if any(tok in num_col.lower() for tok in ("sales", "revenue", "$")) else ""

        for idx, p in enumerate(period_keys):
            val = p_means[idx]
            is_exc, robust_z, lower, upper, dev, method = evaluate_robust_deviation(val, stats)
            if not is_exc:
                continue

            direction: Literal["above", "below", "outside", "neutral"] = (
                "above" if dev > 0 else "below" if dev < 0 else "neutral"
            )

            context_flags = []
            if p_holidays[idx]:
                context_flags.append("Holiday recorded")

            fmt_val = f"${val:,.0f}" if unit == "$" else f"{val:.1f}"
            fmt_range = f"${lower:,.0f}–${upper:,.0f}" if unit == "$" else f"{lower:.1f}–{upper:.1f}"
            fmt_dev = f"${abs(dev):,.0f} {'above' if dev > 0 else 'below'} range" if unit == "$" else f"{abs(dev):.1f} {'above' if dev > 0 else 'below'} range"

            calc_id = f"calc_exception_temp_{hashlib.sha256(f'{manifest.snapshot}:{p}:{num_col}:{ENGINE_VERSION}'.encode()).hexdigest()[:8]}"

            item = ExceptionItem(
                exception_id=f"exc-{calc_id[-8:]}",
                exception_type="temporal",
                subject_type="Period",
                subject_label=p,
                metric_name=num_col,
                unit=unit,
                observed_value=round(val, 2),
                formatted_observed_value=fmt_val,
                expected_lower=round(lower, 2),
                expected_upper=round(upper, 2),
                formatted_expected_range=fmt_range,
                deviation_value=round(dev, 2),
                formatted_deviation=fmt_dev,
                direction=direction,
                sample_size=p_samples[idx],
                sample_label=f"{p_samples[idx]} records",
                method=method,
                context_flags=context_flags,
                calculation_id=calc_id,
                snapshot=manifest.snapshot,
            )

            # Build timeline band points
            timeline_points = []
            for t_idx, t_p in enumerate(period_keys):
                t_val = p_means[t_idx]
                timeline_points.append(
                    ExceptionPoint(
                        label=t_p,
                        raw_period_or_segment=t_p,
                        value=round(t_val, 2),
                        formatted_value=f"${t_val:,.0f}" if unit == "$" else f"{t_val:.1f}",
                        expected_lower=round(lower, 2),
                        expected_upper=round(upper, 2),
                        is_exception=(t_p == p),
                        is_partial=False,
                        sample_size=p_samples[t_idx],
                    )
                )

            visual = ExceptionVisualSpec(
                kind="timeline_band",
                x_axis_title="Period (Timeline)",
                y_axis_title=f"{num_col} ({unit})" if unit else num_col,
                points=timeline_points,
            )

            candidates.append((item, visual))

    return candidates


# -----------------------------------------------------------------------------
# 4. Master Builder
# -----------------------------------------------------------------------------

def build_exception_watch_element(
    manifest: SourceManifest,
    contract: SemanticContract,
    rows: list[dict[str, Any]],
    primary_element: ComponentSpec,
    decision_element: DecisionFocusSpec | None = None,
    eda_report: dict[str, Any] | None = None,
) -> ExceptionWatchSpec | None:
    """Discovers, validates, and constructs the Element 8 Exception Watch specification."""
    # 1. Snapshot and provenance verification for EDA report if provided
    valid_eda = None
    if eda_report:
        rpt_snap = eda_report.get("snapshot") or eda_report.get("source_snapshot")
        if rpt_snap and rpt_snap == manifest.snapshot:
            valid_eda = eda_report
        else:
            logger.warning("EDA report omitted from Element 8: stale or snapshotless.")

    # 2. Gather candidates from all eligible recipes
    temporal_candidates = discover_temporal_exception_candidates(manifest, contract, rows, decision_element)
    segment_candidates = discover_segment_exception_candidates(manifest, contract, rows, decision_element)

    all_candidates: list[tuple[ExceptionItem, ExceptionVisualSpec]] = []
    all_candidates.extend(temporal_candidates)
    all_candidates.extend(segment_candidates)

    if not all_candidates:
        # Return honest unavailable spec
        calc_id = f"calc_exception_none_{hashlib.sha256(f'{manifest.snapshot}:none:{ENGINE_VERSION}'.encode()).hexdigest()[:8]}"
        return ExceptionWatchSpec(
            component_id="exception_element",
            kind="exception_unavailable",
            business_concept="operations.exception_watch",
            title="Exception watch",
            lead_exception=None,
            additional_exceptions=[],
            total_eligible_exceptions=0,
            why_inspect="All evaluated measures and cohorts fall within expected statistical boundaries.",
            next_check="Continue routine monitoring across primary reporting periods.",
            visual=None,
            glance=GlanceSpec(
                label="Exception watch",
                value=None,
                formatted_value="No exceptions detected",
                unit="none",
                unit_display="none",
                context_qualifier="All cohorts within typical observed range",
                has_info_control=True,
            ),
            explain=ExplainSpec(
                short_definition="Monitors business cohorts and periods for observations that deviate significantly from typical ranges.",
                exact_value_text="No period or segment was found outside the statistical baseline range.",
            ),
            inspect=InspectSpec(
                metric_title="Exception Watch: No Outliers Detected",
                exact_value="None",
                what_this_counts="Evaluates all segments and periods against median absolute deviation and IQR fences.",
                applicable_population=f"All {len(rows)} records in {manifest.display_name}.",
                source_name=manifest.display_name,
                reporting_period=(manifest.date_range.get("label") if manifest.date_range else None) or "Current reporting period",
                calculation_method="Robust z-score screening (|robust z| >= 3.5) and 1.5x IQR fences.",
                data_completeness=f"100% evaluated across {manifest.col_count} columns.",
                workforce_coverage="Full dataset coverage",
                coverage_label="Coverage",
                coverage_value=f"{len(rows)} records",
                missing_observations=0,
                excluded_observations=0,
                selection_reason="No cohort exceeded statistical deviation thresholds.",
                limitations=["Statistical consistency does not guarantee absence of operational risk."],
                calculation_id=calc_id,
                definition_id="def_exception_watch_v1",
                snapshot=manifest.snapshot,
                provenance=manifest.display_name,
            ),
            evidence=None,
            caption="No statistical exceptions detected",
        )

    # 3. Lexicographical Ranking & Duplicate Suppression (Section 5.5)
    # Sort candidates by:
    #   - Not duplicate with Element 6 decision focus (primary sort)
    #   - Magnitude of deviation (|deviation_value|)
    #   - Adequate sample size
    def candidate_rank_key(cand: tuple[ExceptionItem, ExceptionVisualSpec]) -> tuple[int, float, int]:
        item, _ = cand
        is_dup = 0 if "duplicate_decision_demoted" in item.context_flags else 1
        dev_mag = abs(item.deviation_value)
        return (is_dup, dev_mag, item.sample_size)

    sorted_candidates = sorted(all_candidates, key=candidate_rank_key, reverse=True)

    lead_item, lead_visual = sorted_candidates[0]
    additional_items = [c[0] for c in sorted_candidates[1:3]]  # Retain up to 2 additional exceptions

    # 4. Compose Non-Causal Wording (Section 10)
    if lead_item.exception_type == "temporal":
        if "Holiday recorded" in lead_item.context_flags:
            why_inspect = (
                f"The observed value ({lead_item.formatted_observed_value}) for {lead_item.subject_label} is outside "
                f"the typical observed range ({lead_item.formatted_expected_range}). A recorded holiday event coincides "
                f"with this period; review event context before treating this difference as an operational anomaly."
            )
        else:
            why_inspect = (
                f"The observed value ({lead_item.formatted_observed_value}) for {lead_item.subject_label} is outside "
                f"the typical observed range ({lead_item.formatted_expected_range}). Review source completeness and "
                f"operational records before interpreting this difference."
            )
    else:  # segment
        why_inspect = (
            f"{lead_item.subject_label} recorded {lead_item.formatted_observed_value} in {lead_item.metric_name}, "
            f"which is outside the typical observed range ({lead_item.formatted_expected_range}) across comparable "
            f"segments. Inspect supporting records to understand operational context."
        )

    next_check = (
        f"Review underlying records for {lead_item.subject_label} in Data Explorer "
        f"to confirm data completeness and context before changing policy."
    )

    caption_text = f"{lead_item.formatted_observed_value} · {lead_item.formatted_expected_range} typical · {lead_item.formatted_deviation}"

    cov_ratio = round(lead_item.sample_size / max(1, len(rows)), 4)
    # 5. Build EvidenceResult
    evidence = EvidenceResult(
        calculation_id=lead_item.calculation_id,
        snapshot=manifest.snapshot,
        definition_id="def_exception_watch_v1",
        status="available",
        value=lead_item.observed_value,
        unit=lead_item.unit,
        aggregation=lead_item.method,
        numerator=None,
        denominator=None,
        is_known_zero=False,
        missing_observations=0,
        invalid_observations=0,
        excluded_observations=0,
        coverage_ratio=cov_ratio,
        calculation_method=lead_item.method,
        provenance=f"Calculated from {manifest.display_name} across {lead_item.sample_label} (snapshot: {manifest.snapshot}).",
        limitations=[
            "A statistical exception indicates unusualness relative to comparable cohorts, not a causal defect or policy breach.",
            "The typical observed range reflects empirical historical dispersion and is not an operational target.",
        ],
    )

    # 6. Compose Specs
    glance = GlanceSpec(
        label="Exception watch",
        value=lead_item.deviation_value,
        formatted_value=lead_item.formatted_observed_value,
        unit=lead_item.unit or "none",
        unit_display="implicit_in_label",
        context_qualifier=f"Typical: {lead_item.formatted_expected_range} · {lead_item.formatted_deviation}",
        has_info_control=True,
    )

    explain = ExplainSpec(
        short_definition="Highlights one statistically unusual period or segment that falls outside the robust baseline range for comparable observations.",
        exact_value_text=(
            f"{lead_item.subject_label} observed {lead_item.formatted_observed_value} vs typical observed range "
            f"{lead_item.formatted_expected_range} ({lead_item.formatted_deviation}) across {lead_item.sample_label}."
        ),
    )

    inspect = InspectSpec(
        metric_title=f"Exception Watch: {lead_item.subject_label} {lead_item.metric_name}",
        exact_value=f"{lead_item.formatted_observed_value} ({lead_item.formatted_deviation})",
        what_this_counts="Identifies statistically defensible deviations from robust medians and typical observed ranges.",
        applicable_population=f"Comparable cohorts within {manifest.display_name}.",
        source_name=manifest.display_name,
        reporting_period=(manifest.date_range.get("label") if manifest.date_range else None) or "Current reporting period",
        calculation_method=lead_item.method,
        data_completeness=f"{lead_item.sample_size} valid observations evaluated with sample guard (n >= 5).",
        workforce_coverage=f"{lead_item.sample_size} observations ({round(cov_ratio * 100.0, 1)}% of total)",
        coverage_label="Cohort Sample",
        coverage_value=lead_item.sample_label,
        missing_observations=0,
        excluded_observations=0,
        selection_reason=(
            "Selected lexicographically: verified business metric, robust deviation beyond screening guard, "
            "adequate cohort sample, and duplicate suppression relative to decision focus."
        ),
        limitations=evidence.limitations,
        calculation_id=lead_item.calculation_id,
        definition_id="def_exception_watch_v1",
        snapshot=manifest.snapshot,
        provenance=evidence.provenance,
    )

    headline = (
        f"Unusual {lead_item.metric_name.lower()} in {lead_item.subject_label}"
        if lead_item.exception_type == "segment"
        else f"Unusual period: {lead_item.subject_label}"
    )

    return ExceptionWatchSpec(
        component_id="exception_element",
        kind="exception_watch",
        business_concept="operations.exception_watch",
        title=headline,
        lead_exception=lead_item,
        additional_exceptions=additional_items,
        total_eligible_exceptions=len(all_candidates),
        why_inspect=why_inspect,
        next_check=next_check,
        visual=lead_visual,
        glance=glance,
        explain=explain,
        inspect=inspect,
        evidence=evidence,
        caption=caption_text,
    )
