"""Forward Outlook builder (Adaptive Dashboard Element 9 / Gate 9).

Evaluates target-gap or statistical forecast candidates under strict validation:
1. Target-gap: explicit target column/metadata, grain/metric match, non-inferred target.
2. Statistical forecast:
   - Prohibits employee-level attendance, individual performance, or protected outcomes.
   - Requires verified chronological temporal series with >= 12 complete periods.
   - For seasonal models, requires >= 2 full cycles (e.g. 104 weekly or 24 monthly).
   - Candidate registry: Naive Last, Naive Drift, Simple Exponential Smoothing (SES), Holt Linear, Seasonal Naive.
   - Chronological rolling-origin backtesting (no leakage).
   - Zero-safe MAE and WAPE evaluation against naive baseline.
   - Publish ONLY when candidate performs at least as well as naive baseline.
   - Empirical residual-based forecast range (widening with horizon, clamped if nonnegative/percentage).
3. Outlook unavailable: honest constructive explanation when conditions are not met.
"""
from __future__ import annotations

import math
import re
from typing import Any, Literal
import numpy as np

from .contracts import (
    ChartSpec,
    ComponentSpec,
    EvidenceResult,
    ExplainSpec,
    ForwardOutlookSpec,
    GlanceSpec,
    InspectSpec,
    ModelValidationResult,
    OutlookPoint,
    SemanticContract,
    SourceManifest,
)


def is_protected_or_individual_outcome(
    concept: str,
    metric_name: str,
    entity_type: str,
    columns: list[str],
) -> bool:
    """Detects if measure or concept targets individual employee performance, attendance, attrition, or health."""
    prohibited_terms = {
        "attendance",
        "leaves",
        "leave",
        "absent",
        "absence",
        "attrition",
        "turnover",
        "performance",
        "rating",
        "eval",
        "health",
        "sick",
        "disciplinary",
        "salary",
        "compensation",
    }
    tokens = set(concept.lower().replace("_", " ").split())
    tokens.update(metric_name.lower().replace("_", " ").split())
    tokens.update(entity_type.lower().replace("_", " ").split())
    for col in columns:
        c_lower = str(col).lower()
        if any(term in c_lower for term in ("employee", "staff", "person", "worker")):
            if any(term in tokens for term in prohibited_terms):
                return True
    return bool(tokens.intersection(prohibited_terms) and any(e in entity_type.lower() for e in ("employee", "staff", "person", "worker", "individual")))


def detect_target_column(
    columns: list[str],
    metric_name: str,
) -> str | None:
    """Finds an explicit verified target, plan, budget, or quota column matching the active metric."""
    target_keywords = ("target", "plan", "quota", "budget", "sla", "threshold", "goal")
    metric_tokens = [
        t for t in metric_name.lower().replace("_", " ").split()
        if len(t) >= 3 and t not in ("weekly", "monthly", "daily", "annual", "total", "average", "avg", "mean")
    ]

    domain_qualifiers = {
        "recruitment", "hiring", "hire", "turnover", "attrition", "retention",
        "headcount", "staffing", "attendance", "leave", "training", "hours",
        "revenue", "sales", "margin", "profit", "cost", "expense", "spend",
        "conversion", "churn", "tickets", "incidents", "defects", "scrap",
    }
    unrelated_qualifiers = domain_qualifiers - set(metric_tokens)

    # 1. Look for column containing both target keyword and metric token
    for col in columns:
        c_lower = str(col).lower().strip()
        if c_lower == metric_name.lower().strip():
            continue
        c_parts = set(re.findall(r"[a-z0-9]+", c_lower))
        if any(kw in c_parts for kw in target_keywords):
            if any(tok in c_parts or tok in c_lower for tok in metric_tokens):
                return col

    # 2. Look for pure target column without unrelated domain qualifiers
    for col in columns:
        c_lower = str(col).lower().strip()
        if c_lower == metric_name.lower().strip():
            continue
        c_parts = set(re.findall(r"[a-z0-9]+", c_lower))
        if any(kw in c_parts for kw in target_keywords):
            if c_parts & unrelated_qualifiers:
                continue
            return col

    return None


def calculate_wape(actuals: np.ndarray, preds: np.ndarray) -> float:
    """Computes zero-safe Weighted Absolute Percentage Error (WAPE = sum(|y - y_hat|) / sum(|y|))."""
    abs_errors = np.abs(actuals - preds)
    sum_actuals = float(np.sum(np.abs(actuals)))
    if sum_actuals == 0.0:
        return 0.0 if float(np.sum(abs_errors)) == 0.0 else 1.0
    return float(np.sum(abs_errors) / sum_actuals)


def calculate_mae(actuals: np.ndarray, preds: np.ndarray) -> float:
    """Computes Mean Absolute Error."""
    return float(np.mean(np.abs(actuals - preds)))


def fit_and_predict_candidate(
    model_id: str,
    train_y: np.ndarray,
    horizon: int = 1,
    seasonal_period: int | None = None,
) -> np.ndarray:
    """Fits candidate model on historical train_y and predicts horizon steps ahead."""
    n = len(train_y)
    if n == 0:
        return np.zeros(horizon)

    if model_id == "naive_last":
        return np.full(horizon, train_y[-1])

    if model_id == "naive_drift":
        if n < 2:
            return np.full(horizon, train_y[-1])
        drift_slope = (train_y[-1] - train_y[0]) / (n - 1)
        return np.array([train_y[-1] + h * drift_slope for h in range(1, horizon + 1)])

    if model_id == "seasonal_naive":
        m = seasonal_period or 52
        if n >= m:
            preds = []
            for h in range(1, horizon + 1):
                idx = -m + ((h - 1) % m)
                preds.append(train_y[idx])
            return np.array(preds)
        return np.full(horizon, train_y[-1])

    if model_id == "ses":
        # Grid search alpha in [0.1, 0.9] to minimize in-sample SSE
        best_alpha = 0.3
        best_sse = float("inf")
        for alpha in np.linspace(0.1, 0.9, 9):
            level = train_y[0]
            sse = 0.0
            for t in range(1, n):
                pred = level
                err = train_y[t] - pred
                sse += err * err
                level = alpha * train_y[t] + (1.0 - alpha) * level
            if sse < best_sse:
                best_sse = sse
                best_alpha = alpha

        # Run with best_alpha to get final level
        level = train_y[0]
        for t in range(1, n):
            level = best_alpha * train_y[t] + (1.0 - best_alpha) * level
        return np.full(horizon, level)

    if model_id == "holt_linear":
        # Grid search alpha and beta
        best_params = (0.3, 0.1)
        best_sse = float("inf")
        if n < 3:
            return np.full(horizon, train_y[-1])

        init_level = train_y[0]
        init_trend = train_y[1] - train_y[0]

        for alpha in [0.2, 0.4, 0.6, 0.8]:
            for beta in [0.05, 0.1, 0.2]:
                level = init_level
                trend = init_trend
                sse = 0.0
                for t in range(1, n):
                    pred = level + trend
                    err = train_y[t] - pred
                    sse += err * err
                    new_level = alpha * train_y[t] + (1.0 - alpha) * (level + trend)
                    new_trend = beta * (new_level - level) + (1.0 - beta) * trend
                    level = new_level
                    trend = new_trend
                if sse < best_sse:
                    best_sse = sse
                    best_params = (alpha, beta)

        # Final fit
        alpha, beta = best_params
        level = init_level
        trend = init_trend
        for t in range(1, n):
            new_level = alpha * train_y[t] + (1.0 - alpha) * (level + trend)
            new_trend = beta * (new_level - level) + (1.0 - beta) * trend
            level = new_level
            trend = new_trend

        return np.array([level + h * trend for h in range(1, horizon + 1)])

    # Fallback to naive last
    return np.full(horizon, train_y[-1])


def backtest_candidate_models(
    series: list[float],
    grain: str,
) -> tuple[str, ModelValidationResult, float, dict[str, Any]]:
    """Runs rolling-origin cross-validation comparing candidates against Naive baseline."""
    arr = np.array(series, dtype=float)
    n = len(arr)

    # Number of folds: between 3 and 5
    num_folds = min(5, max(3, n // 5))
    start_train_len = n - num_folds

    is_weekly = (grain == "weekly")
    seasonal_period = 52 if is_weekly else 12
    can_use_seasonal = (n >= 2 * seasonal_period)

    # Registry of candidates
    candidates = ["naive_drift", "ses", "holt_linear"]
    if can_use_seasonal:
        candidates.append("seasonal_naive")

    baseline_model = "seasonal_naive" if can_use_seasonal else "naive_last"

    # Evaluate baseline
    baseline_actuals = []
    baseline_preds = []
    for k in range(start_train_len, n):
        train = arr[:k]
        actual = arr[k]
        pred = fit_and_predict_candidate(baseline_model, train, horizon=1, seasonal_period=seasonal_period)[0]
        baseline_actuals.append(actual)
        baseline_preds.append(pred)

    b_act = np.array(baseline_actuals)
    b_pred = np.array(baseline_preds)
    baseline_mae = calculate_mae(b_act, b_pred)
    baseline_wape = calculate_wape(b_act, b_pred)

    # Evaluate each candidate
    best_candidate = baseline_model
    best_mae = baseline_mae
    best_wape = baseline_wape
    best_errors: list[float] = list(b_act - b_pred)

    candidate_results = {}
    for cand in candidates:
        cand_actuals = []
        cand_preds = []
        for k in range(start_train_len, n):
            train = arr[:k]
            actual = arr[k]
            pred = fit_and_predict_candidate(cand, train, horizon=1, seasonal_period=seasonal_period)[0]
            cand_actuals.append(actual)
            cand_preds.append(pred)

        c_act = np.array(cand_actuals)
        c_pred = np.array(cand_preds)
        c_mae = calculate_mae(c_act, c_pred)
        c_wape = calculate_wape(c_act, c_pred)
        candidate_results[cand] = {"mae": c_mae, "wape": c_wape}

        # Check if candidate beats baseline within tolerance (MAE <= baseline_mae * 1.00)
        if c_mae < best_mae:
            best_candidate = cand
            best_mae = c_mae
            best_wape = c_wape
            best_errors = list(c_act - c_pred)

    # Labels
    labels = {
        "naive_last": "Last-observation Naïve",
        "naive_drift": "Naïve Drift",
        "ses": "Simple Exponential Smoothing (SES)",
        "holt_linear": "Holt's Linear Trend",
        "seasonal_naive": "Seasonal Naïve (Annual)",
    }

    # Pass condition: A candidate model must outperform the baseline.
    # Equal performance to baseline is NOT model improvement.
    passed = (best_candidate != baseline_model and best_mae < baseline_mae)
    rejection_reason = None
    if not passed:
        rejection_reason = f"No candidate model outperformed baseline MAE ({baseline_mae:.2f}) across {num_folds} rolling folds."

    val_res = ModelValidationResult(
        model_id=best_candidate,
        model_label=labels.get(best_candidate, best_candidate),
        fold_count=num_folds,
        mae=round(best_mae, 4),
        wape=round(best_wape, 4),
        baseline_mae=round(baseline_mae, 4),
        baseline_wape=round(baseline_wape, 4),
        passed=passed,
        rejection_reason=rejection_reason,
    )

    # Residual standard error from validation folds
    res_std = float(np.std(best_errors, ddof=1)) if len(best_errors) > 1 else (best_mae * 1.25)
    if res_std <= 0:
        res_std = best_mae * 0.5 or 1.0

    meta = {
        "candidate_results": candidate_results,
        "residual_std": res_std,
        "baseline_model": baseline_model,
        "seasonal_period": seasonal_period if can_use_seasonal else None,
    }

    return best_candidate, val_res, res_std, meta


def format_forecast_value(val: float, unit: str) -> str:
    """Formats numeric value with unit."""
    if unit == "$":
        if abs(val) >= 1_000_000:
            return f"${val / 1_000_000:.2f}M"
        if abs(val) >= 1_000:
            return f"${val / 1_000:.1f}K"
        return f"${val:,.2f}"
    if unit == "%":
        return f"{val:.1f}%"
    if unit in ("hours", "hrs"):
        return f"{val:.1f} hrs"
    if unit in ("days", "d"):
        return f"{val:.1f} days"
    if abs(val) >= 1_000_000:
        return f"{val / 1_000_000:.2f}M {unit}"
    if abs(val) >= 1_000:
        return f"{val / 1_000:.1f}K {unit}"
    return f"{val:.1f} {unit}".strip()


def build_forward_outlook_element(
    sheet_id: int,
    rows: list[dict[str, Any]],
    manifest: SourceManifest,
    contract: SemanticContract,
    primary_element: ComponentSpec,
    secondary_element: ChartSpec | None = None,
    analysis_context: dict[str, Any] | None = None,
) -> ForwardOutlookSpec:
    """Builds the Gate 9 Forward Outlook component (target-gap, forecast, or unavailable)."""
    columns = list(rows[0].keys()) if rows else []
    metric_name = contract.primary_measure or "Observed Metric"
    concept = primary_element.business_concept
    unit = "$" if "sales" in metric_name.lower() or "$" in primary_element.glance.formatted_value else "%" if "%" in primary_element.glance.formatted_value else "units"

    # 1. Check for Target Gap Mode
    target_col = detect_target_column(columns, metric_name)
    if target_col is not None:
        target_vals = []
        actual_vals = []
        missing_actual_count = 0
        missing_target_count = 0
        for r in rows:
            t_raw = r.get(target_col)
            a_raw = r.get(metric_name)
            if t_raw is None or str(t_raw).strip() == "":
                missing_target_count += 1
                continue
            if a_raw is None or str(a_raw).strip() == "":
                missing_actual_count += 1
                continue
            try:
                t_clean = float(str(t_raw).replace("$", "").replace(",", "").replace("%", ""))
                a_clean = float(str(a_raw).replace("$", "").replace(",", "").replace("%", ""))
                target_vals.append(t_clean)
                actual_vals.append(a_clean)
            except (ValueError, TypeError):
                continue

        if len(actual_vals) == 0 and missing_actual_count > 0:
            return build_unavailable_outlook(
                concept=concept,
                metric_name=metric_name,
                unit=unit,
                sheet_id=manifest.sheet_id,
                manifest=manifest,
                reason=f"Recorded target column '{target_col}' exists, but all matching actual observations for '{metric_name}' are missing or unrecorded.",
            )

        if len(target_vals) >= 3 and len(actual_vals) >= 3:
            avg_actual = float(np.mean(actual_vals))
            avg_target = float(np.mean(target_vals))
            gap = avg_actual - avg_target

            unit_gaps = [a - t for a, t in zip(actual_vals, target_vals)]
            units_behind = sum(1 for g in unit_gaps if g < 0)
            pct_behind = round((units_behind / len(actual_vals)) * 100.0, 1)

            gap_direction = "above" if gap >= 0 else "below"
            abs_gap = abs(gap)
            formatted_gap = format_forecast_value(abs_gap, unit)
            formatted_actual = format_forecast_value(avg_actual, unit)
            formatted_target = format_forecast_value(avg_target, unit)

            if unit == "%":
                gap_phrase = f"{abs_gap:.1f} percentage points {gap_direction} the recorded target"
            else:
                gap_phrase = f"{formatted_gap} {gap_direction} the recorded target ({formatted_target})"

            if gap >= 0 and units_behind > 0:
                why = (
                    f"Current average performance of {formatted_actual} meets or exceeds target of {formatted_target} "
                    f"({gap_phrase}), but {units_behind} of {len(actual_vals)} units ({pct_behind:.0f}%) remain behind target."
                )
            else:
                why = f"Current observed performance stands at {formatted_actual} against an explicit target of {formatted_target}, resulting in a gap of {gap_phrase}."
            review_stmt = "Review operational capacity and underlying segment distribution before adjusting target baselines."

            points = [
                OutlookPoint(
                    period="actual",
                    period_label="Current Actual",
                    actual_value=round(avg_actual, 2),
                    is_partial=False,
                ),
                OutlookPoint(
                    period="target",
                    period_label="Target Baseline",
                    actual_value=round(avg_target, 2),
                    is_partial=False,
                ),
            ]

            return ForwardOutlookSpec(
                component_id="outlook_element",
                kind="target_gap",
                business_concept=concept,
                title="Forward outlook",
                metric_name=metric_name,
                unit=unit,
                temporal_grain=secondary_element.temporal_grain if secondary_element else "period",
                horizon=1,
                actual_value=round(avg_actual, 2),
                target_value=round(avg_target, 2),
                gap_value=round(gap, 2),
                forecast_value=None,
                lower_bound=None,
                upper_bound=None,
                model_id=None,
                validation=None,
                points=points,
                next_review_period="Next planning cycle",
                why_available_or_unavailable=why,
                glance=GlanceSpec(
                    label="Target gap",
                    value=round(gap, 2),
                    formatted_value=gap_phrase,
                    context_qualifier=f"Target: {formatted_target}",
                ),
                explain=ExplainSpec(
                    short_definition=f"Explicit comparison of current {metric_name} against recorded {target_col} target.",
                    exact_value_text=f"Actual: {formatted_actual} | Target: {formatted_target} | Gap: {gap_phrase}",
                ),
                inspect=InspectSpec(
                    metric_title="Target Gap",
                    exact_value=gap_phrase,
                    what_this_counts="Variance between current observed measure and explicit recorded target.",
                    applicable_population=f"Valid records in {manifest.display_name} containing both actual and target values.",
                    source_name=manifest.display_name,
                    calculation_method=f"gap = mean({metric_name}) - mean({target_col})",
                    data_completeness=f"{len(target_vals)} records with paired actual and target values",
                    workforce_coverage="100% of paired records",
                    selection_reason="Identified explicit recorded target column matching active metric dimension.",
                    calculation_id=f"calc-target-gap-{sheet_id}",
                    definition_id="def-target-gap",
                    snapshot=manifest.snapshot,
                    provenance=f"Sheet {sheet_id}: {manifest.display_name}",
                    limitations=["Target values are taken directly from source records and not independently audited."],
                ),
                evidence=EvidenceResult(
                    calculation_id=f"calc-target-gap-{sheet_id}",
                    snapshot=manifest.snapshot,
                    definition_id="def-target-gap",
                    status="available",
                    value=round(gap, 2),
                    unit=unit,
                    aggregation="mean_difference",
                    calculation_method="explicit_target_comparison",
                    provenance=f"Sheet {sheet_id}: {manifest.display_name}",
                ),
                caption=f"Target comparison based on recorded {target_col}.",
            )

    # 2. Check Governance Policy: Prohibit individual/protected outcome forecasting
    if is_protected_or_individual_outcome(concept, metric_name, contract.entity_type, columns):
        why_unavail = (
            "Employee-level attendance, individual performance scores, and protected workforce "
            "outcomes are excluded from automated forward forecasting under data governance policies."
        )
        return build_unavailable_outlook(
            concept=concept,
            metric_name=metric_name,
            unit=unit,
            sheet_id=sheet_id,
            manifest=manifest,
            reason=why_unavail,
        )

    # 3. Check for Statistical Forecast Series Eligibility
    if not secondary_element or not secondary_element.chart_series or not secondary_element.chart_series.points:
        why_unavail = (
            f"A statistical forward forecast requires a verified chronological time series; "
            f"no temporal progression was established for {manifest.display_name}."
        )
        return build_unavailable_outlook(
            concept=concept,
            metric_name=metric_name,
            unit=unit,
            sheet_id=sheet_id,
            manifest=manifest,
            reason=why_unavail,
        )

    chart_points = secondary_element.chart_series.points
    grain = secondary_element.temporal_grain or "monthly"
    unit = secondary_element.chart_series.unit or unit

    # Separate complete historical points and exclude partial latest period if marked
    usable_points = []
    has_partial_latest = False
    for pt in chart_points:
        if pt.average_hours is not None:
            if pt.is_partial and pt == chart_points[-1]:
                has_partial_latest = True
                continue
            usable_points.append(pt)

    n_complete = len(usable_points)
    if n_complete < 12:
        why_unavail = (
            f"A forward outlook needs at least 12 complete {grain} periods; "
            f"this source contains {n_complete} complete periods."
        )
        return build_unavailable_outlook(
            concept=concept,
            metric_name=metric_name,
            unit=unit,
            sheet_id=sheet_id,
            manifest=manifest,
            reason=why_unavail,
        )

    # Extract historical values
    history_values = [p.average_hours for p in usable_points if p.average_hours is not None]

    # Run Rolling-Origin Cross-Validation
    best_model_id, val_result, res_std, meta = backtest_candidate_models(history_values, grain)

    if not val_result.passed:
        why_unavail = (
            f"The available history did not outperform a naïve baseline across {val_result.fold_count} "
            f"rolling backtest folds (candidate MAE={val_result.mae:.2f} vs baseline MAE={val_result.baseline_mae:.2f}), "
            f"so no forecast is shown."
        )
        return build_unavailable_outlook(
            concept=concept,
            metric_name=metric_name,
            unit=unit,
            sheet_id=sheet_id,
            manifest=manifest,
            reason=why_unavail,
            validation=val_result,
        )

    # Fit best model on all complete historical data
    horizon = 1
    forecast_arr = fit_and_predict_candidate(
        best_model_id,
        np.array(history_values, dtype=float),
        horizon=horizon,
        seasonal_period=meta.get("seasonal_period"),
    )
    point_forecast = float(forecast_arr[0])

    # Empirical forecast range (+- 1.96 * residual_std)
    margin = 1.96 * res_std * math.sqrt(horizon)
    lower_bound = point_forecast - margin
    upper_bound = point_forecast + margin

    # Nonnegative & percentage clamping guards
    is_nonnegative = ("$" in unit or "sales" in metric_name.lower() or "count" in unit.lower() or "hrs" in unit.lower())
    clamp_note = []
    if is_nonnegative and lower_bound < 0.0:
        lower_bound = 0.0
        clamp_note.append("clamped lower bound to 0 for non-negative measure")

    if unit == "%":
        if lower_bound < 0.0:
            lower_bound = 0.0
            clamp_note.append("clamped lower bound to 0%")
        if upper_bound > 100.0:
            upper_bound = 100.0
            clamp_note.append("clamped upper bound to 100%")

    # Construct Outlook Points (historical actuals + forecast point)
    points: list[OutlookPoint] = []
    for pt in usable_points:
        points.append(
            OutlookPoint(
                period=pt.period,
                period_label=pt.period_label,
                actual_value=round(pt.average_hours, 2) if pt.average_hours is not None else None,
                forecast_value=None,
                lower_bound=None,
                upper_bound=None,
                is_partial=False,
            )
        )

    # Next period label
    last_pt = usable_points[-1]
    next_period_label = f"Next {grain.title()}"
    next_period_key = f"{last_pt.period}+1"

    points.append(
        OutlookPoint(
            period=next_period_key,
            period_label=next_period_label,
            actual_value=None,
            forecast_value=round(point_forecast, 2),
            lower_bound=round(lower_bound, 2),
            upper_bound=round(upper_bound, 2),
            is_partial=False,
        )
    )

    formatted_forecast = format_forecast_value(point_forecast, unit)
    formatted_lower = format_forecast_value(lower_bound, unit)
    formatted_upper = format_forecast_value(upper_bound, unit)
    range_phrase = f"{formatted_lower}–{formatted_upper}"

    why = (
        f"The selected model ({val_result.model_label}) estimates {formatted_forecast} for {next_period_label.lower()}, "
        f"with an empirical forecast range of {range_phrase} based on {val_result.fold_count} rolling-origin validation folds."
    )
    if clamp_note:
        why += f" ({', '.join(clamp_note)})."

    caption = f"Statistically backtested {val_result.model_label} (WAPE {val_result.wape * 100:.1f}% vs baseline {val_result.baseline_wape * 100:.1f}%)."

    return ForwardOutlookSpec(
        component_id="outlook_element",
        kind="statistical_forecast",
        business_concept=concept,
        title="Forward outlook",
        metric_name=metric_name,
        unit=unit,
        temporal_grain=grain,
        horizon=horizon,
        actual_value=round(history_values[-1], 2),
        target_value=None,
        gap_value=None,
        forecast_value=round(point_forecast, 2),
        lower_bound=round(lower_bound, 2),
        upper_bound=round(upper_bound, 2),
        model_id=best_model_id,
        validation=val_result,
        points=points,
        next_review_period=next_period_label,
        why_available_or_unavailable=why,
        glance=GlanceSpec(
            label=f"Next {grain.title()} estimate",
            value=round(point_forecast, 2),
            formatted_value=formatted_forecast,
            context_qualifier=f"Range: {range_phrase} | Model: {val_result.model_label}",
        ),
        explain=ExplainSpec(
            short_definition=f"Short-horizon statistical forecast for {metric_name} using rolling-origin backtested model.",
            exact_value_text=f"Estimate: {formatted_forecast} (empirical range {range_phrase})",
        ),
        inspect=InspectSpec(
            metric_title=f"{metric_name} Forward Forecast",
            exact_value=formatted_forecast,
            what_this_counts=f"Statistically projected {metric_name} for the next chronological {grain} period.",
            applicable_population=f"{n_complete} complete historical {grain} periods in {manifest.display_name}.",
            source_name=manifest.display_name,
            calculation_method=f"{val_result.model_label} rolling-origin validation (MAE={val_result.mae:.2f}, WAPE={val_result.wape:.3f}, folds={val_result.fold_count})",
            data_completeness=f"{n_complete} validated chronological periods",
            workforce_coverage="100% of usable historical periods",
            selection_reason="Selected best performing time-series model outperforming naive baseline in rolling-origin cross-validation.",
            calculation_id=f"calc-forecast-{sheet_id}-{best_model_id}",
            definition_id="def-forward-forecast",
            snapshot=manifest.snapshot,
            provenance=f"Sheet {sheet_id}: {manifest.display_name}",
            limitations=[
                "Empirical forecast range reflects past residual variability and is not a guaranteed SLA.",
                "Partial trailing periods excluded from model calibration.",
            ],
        ),
        evidence=EvidenceResult(
            calculation_id=f"calc-forecast-{sheet_id}-{best_model_id}",
            snapshot=manifest.snapshot,
            definition_id="def-forward-forecast",
            status="available",
            value=round(point_forecast, 2),
            unit=unit,
            aggregation="point_forecast",
            calculation_method=f"rolling_origin_{best_model_id}",
            provenance=f"Sheet {sheet_id}: {manifest.display_name}",
        ),
        caption=caption,
    )


def build_unavailable_outlook(
    concept: str,
    metric_name: str,
    unit: str,
    sheet_id: int,
    manifest: SourceManifest,
    reason: str,
    validation: ModelValidationResult | None = None,
) -> ForwardOutlookSpec:
    """Builds an honest, constructive outlook unavailable card."""
    return ForwardOutlookSpec(
        component_id="outlook_element",
        kind="outlook_unavailable",
        business_concept=concept,
        title="Forward outlook",
        metric_name=metric_name,
        unit=unit,
        temporal_grain=None,
        horizon=None,
        actual_value=None,
        target_value=None,
        gap_value=None,
        forecast_value=None,
        lower_bound=None,
        upper_bound=None,
        model_id=None,
        validation=validation,
        points=[],
        next_review_period=None,
        why_available_or_unavailable=reason,
        glance=GlanceSpec(
            label="Forward outlook",
            value=None,
            formatted_value="Unavailable",
            context_qualifier="Evidence withheld per governance & data requirements",
        ),
        explain=ExplainSpec(
            short_definition="Forward-looking outlook requires either a verified explicit target or a backtested statistical time series.",
            exact_value_text="Unavailable",
        ),
        inspect=InspectSpec(
            metric_title="Forward Outlook (Unavailable)",
            exact_value="Unavailable",
            what_this_counts="Forward outlook eligibility check.",
            applicable_population=f"Data records in {manifest.display_name}.",
            source_name=manifest.display_name,
            calculation_method="Withheld per Gate 9 validation guards (target verification, sample size, or governance policies).",
            data_completeness="Evaluated for forward forecasting eligibility",
            workforce_coverage="N/A",
            selection_reason="Source data did not satisfy minimum requirements for forward outlook.",
            calculation_id=f"calc-outlook-unavail-{sheet_id}",
            definition_id="def-forward-outlook-unavail",
            snapshot=manifest.snapshot,
            provenance=f"Sheet {sheet_id}: {manifest.display_name}",
            limitations=[reason],
        ),
        evidence=None,
        caption=None,
    )
