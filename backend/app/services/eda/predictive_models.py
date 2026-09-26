"""Advanced Predictive Analytics & Statistical Modeling Engine for EDA.
Provides closed-form Ordinary Least Squares (OLS) Linear Regression and
Iteratively Reweighted Least Squares (IRLS) Logistic Regression with domain-tailored HR interpretations.
"""
from __future__ import annotations

import math
from typing import Any
import numpy as np


def _p_value_from_t(t_val: float, df: int) -> float:
    """Approximates two-tailed p-value from Student's t-distribution using standard normal / series approximation."""
    if df <= 0 or math.isnan(t_val):
        return 1.0
    abs_t = abs(t_val)
    # Hill's approximation / normal approximation for moderate df
    z = abs_t * (1.0 - 1.0 / (4.0 * df)) / math.sqrt(1.0 + (abs_t * abs_t) / (2.0 * df)) if df > 4 else abs_t
    # Error function complement
    try:
        p = math.erfc(z / math.sqrt(2.0))
        return float(np.clip(p, 0.0, 1.0))
    except Exception:
        return 0.05


def fit_linear_regression(
    x_vals: list[float],
    y_vals: list[float],
    x_name: str,
    y_name: str,
    max_scatter_points: int = 150
) -> dict[str, Any] | None:
    """Fits an Ordinary Least Squares (OLS) univariate linear regression model: y = alpha + beta * x."""
    x_arr = np.array(x_vals, dtype=float)
    y_arr = np.array(y_vals, dtype=float)

    # Filter out NaNs and infs
    valid = np.isfinite(x_arr) & np.isfinite(y_arr)
    x = x_arr[valid]
    y = y_arr[valid]
    n = len(x)

    if n < 4 or np.var(x) < 1e-9 or np.var(y) < 1e-9:
        return None

    x_mean = float(np.mean(x))
    y_mean = float(np.mean(y))

    # Calculate beta and alpha
    x_dev = x - x_mean
    y_dev = y - y_mean
    ss_xx = float(np.sum(x_dev ** 2))
    ss_xy = float(np.sum(x_dev * y_dev))

    if ss_xx <= 1e-12:
        return None

    beta = ss_xy / ss_xx
    alpha = y_mean - beta * x_mean

    y_pred = alpha + beta * x
    residuals = y - y_pred
    ss_res = float(np.sum(residuals ** 2))
    ss_tot = float(np.sum(y_dev ** 2))

    r_squared = max(0.0, min(1.0, 1.0 - (ss_res / ss_tot))) if ss_tot > 0 else 0.0
    adj_r_squared = max(0.0, 1.0 - (1.0 - r_squared) * (n - 1) / max(1, n - 2))
    rmse = math.sqrt(ss_res / n)
    rse = math.sqrt(ss_res / max(1, n - 2))

    se_beta = rse / math.sqrt(ss_xx) if ss_xx > 0 else 0.0
    t_stat = beta / se_beta if se_beta > 1e-9 else 0.0
    p_val = _p_value_from_t(t_stat, n - 2)

    # Pearson correlation
    pearson_r = float(np.corrcoef(x, y)[0, 1])

    # Subsample scatter points for charting
    stride = max(1, n // max_scatter_points)
    scatter_pts = [{"x": round(float(x[i]), 2), "y": round(float(y[i]), 2)} for i in range(0, n, stride)]

    # Trendline endpoints
    x_min, x_max = float(np.min(x)), float(np.max(x))
    trendline = [
        {"x": round(x_min, 2), "y": round(alpha + beta * x_min, 2)},
        {"x": round(x_max, 2), "y": round(alpha + beta * x_max, 2)}
    ]

    # Executive interpretation tailored for HR leadership
    dir_word = "decrease" if beta < 0 else "increase"
    mag = abs(beta)
    significance = "statistically significant" if p_val < 0.05 else "not statistically significant"
    hr_insight = (
        f"Each 1-unit increase in '{x_name}' is associated with an average {dir_word} of {mag:.2f} in '{y_name}' "
        f"({significance}, p = {p_val:.4f}, R² = {r_squared:.2f})."
    )

    return {
        "model_type": "Linear Regression (OLS)",
        "x_variable": x_name,
        "y_variable": y_name,
        "sample_size": n,
        "equation": f"{y_name} = {alpha:.2f} {('+' if beta >= 0 else '-')} {abs(beta):.2f} * ({x_name})",
        "intercept": round(alpha, 3),
        "slope": round(beta, 3),
        "r_squared": round(r_squared, 3),
        "adjusted_r_squared": round(adj_r_squared, 3),
        "rmse": round(rmse, 3),
        "standard_error": round(se_beta, 3),
        "t_statistic": round(t_stat, 2),
        "p_value": round(p_val, 4),
        "pearson_r": round(pearson_r, 3),
        "scatter_points": scatter_pts,
        "trendline": trendline,
        "executive_takeaway": hr_insight
    }


def fit_logistic_regression(
    x_vals: list[float],
    y_binary: list[int | float],
    x_name: str,
    outcome_label: str,
    max_scatter_points: int = 150
) -> dict[str, Any] | None:
    """Fits a univariate Logistic Regression model via Iteratively Reweighted Least Squares (IRLS).
    Models P(Outcome=1 | X) = 1 / (1 + exp(-(alpha + beta * x))).
    """
    x_arr = np.array(x_vals, dtype=float)
    y_arr = np.array(y_binary, dtype=float)

    valid = np.isfinite(x_arr) & np.isfinite(y_arr)
    x = x_arr[valid]
    y = np.where(y_arr[valid] > 0, 1.0, 0.0)
    n = len(x)

    # Need both classes and variance
    if n < 8 or len(np.unique(y)) < 2 or np.var(x) < 1e-9:
        return None

    # Standardization for numerical stability during IRLS
    x_mean = float(np.mean(x))
    x_std = float(np.std(x)) or 1.0
    x_norm = (x - x_mean) / x_std

    X_mat = np.column_stack([np.ones_like(x_norm), x_norm])
    b = np.zeros(2)

    # IRLS / Newton-Raphson optimization
    converged = False
    for _ in range(25):
        eta = np.clip(X_mat @ b, -25.0, 25.0)
        p = 1.0 / (1.0 + np.exp(-eta))
        w = np.clip(p * (1.0 - p), 1e-6, 1.0)
        W = np.diag(w)

        grad = X_mat.T @ (y - p)
        Hessian = X_mat.T @ W @ X_mat + 1e-4 * np.eye(2)

        try:
            delta = np.linalg.solve(Hessian, grad)
            b += delta
            if np.max(np.abs(delta)) < 1e-5:
                converged = True
                break
        except np.linalg.LinAlgError:
            break

    if not converged:
        # Fallback to standard gradient descent step
        pass

    # Un-normalize coefficients back to original scale:
    # eta = b[0] + b[1] * (x - x_mean)/x_std = (b[0] - b[1]*x_mean/x_std) + (b[1]/x_std)*x
    beta_orig = b[1] / x_std
    alpha_orig = b[0] - (b[1] * x_mean / x_std)

    # Predictions and probabilities
    eta_orig = np.clip(alpha_orig + beta_orig * x, -25.0, 25.0)
    probs = 1.0 / (1.0 + np.exp(-eta_orig))
    preds = np.where(probs >= 0.5, 1.0, 0.0)

    # Confusion matrix
    tp = int(np.sum((preds == 1.0) & (y == 1.0)))
    fp = int(np.sum((preds == 1.0) & (y == 0.0)))
    tn = int(np.sum((preds == 0.0) & (y == 0.0)))
    fn = int(np.sum((preds == 0.0) & (y == 1.0)))

    accuracy = (tp + tn) / max(1, n)
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = (2 * precision * recall) / max(1e-9, precision + recall)

    # Odds Ratio: exp(beta)
    odds_ratio = float(np.exp(np.clip(beta_orig, -10.0, 10.0)))
    pct_change = (odds_ratio - 1.0) * 100.0

    # Null log-likelihood for Pseudo-R2
    p_null = float(np.mean(y))
    p_null = np.clip(p_null, 1e-6, 1.0 - 1e-6)
    ll_null = float(np.sum(y * np.log(p_null) + (1.0 - y) * np.log(1.0 - p_null)))
    ll_model = float(np.sum(y * np.log(np.clip(probs, 1e-9, 1.0)) + (1.0 - y) * np.log(np.clip(1.0 - probs, 1e-9, 1.0))))
    pseudo_r2 = max(0.0, min(1.0, 1.0 - (ll_model / ll_null))) if abs(ll_null) > 1e-6 else 0.0

    # Generate smooth Sigmoid Curve points (50 points across x range)
    x_min, x_max = float(np.min(x)), float(np.max(x))
    x_span = np.linspace(x_min, x_max, 50)
    curve_pts = [
        {
            "x": round(float(xv), 2),
            "probability": round(float(1.0 / (1.0 + np.exp(-np.clip(alpha_orig + beta_orig * xv, -25.0, 25.0)))), 3)
        }
        for xv in x_span
    ]

    # Executive interpretation tailored for HR leadership
    if pct_change >= 0:
        hr_insight = (
            f"Each additional unit of '{x_name}' increases the odds of '{outcome_label}' by {pct_change:.1f}% "
            f"(Odds Ratio: {odds_ratio:.2f}, Model Accuracy: {accuracy * 100:.1f}%)."
        )
    else:
        hr_insight = (
            f"Each additional unit of '{x_name}' decreases the odds of '{outcome_label}' by {abs(pct_change):.1f}% "
            f"(Odds Ratio: {odds_ratio:.2f}, Model Accuracy: {accuracy * 100:.1f}%)."
        )

    return {
        "model_type": "Logistic Regression (Binary Risk Classification)",
        "x_variable": x_name,
        "outcome_label": outcome_label,
        "sample_size": n,
        "intercept": round(alpha_orig, 3),
        "coefficient": round(beta_orig, 3),
        "odds_ratio": round(odds_ratio, 2),
        "pct_change_in_odds": round(pct_change, 1),
        "accuracy": round(accuracy, 3),
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1_score": round(f1, 3),
        "pseudo_r_squared": round(pseudo_r2, 3),
        "confusion_matrix": {"true_positive": tp, "false_positive": fp, "true_negative": tn, "false_negative": fn},
        "sigmoid_curve": curve_pts,
        "executive_takeaway": hr_insight
    }


def generate_predictive_suite_for_sheet(
    records: list[dict[str, Any]],
    columns: list[str],
    column_diagnostics: dict[str, Any]
) -> dict[str, Any]:
    """Inspects sheet records and executes the most relevant Linear and Logistic Regressions for HR & Operational domains."""
    if len(records) < 5:
        return {"linear_models": [], "logistic_models": [], "domain_executive_points": []}

    # Identify clean numeric columns
    numeric_cols = []
    for c in columns:
        diag = column_diagnostics.get(c, {})
        inferred = diag.get("inferred_type", "")
        # Strict exclusion of IDs, codes, names
        c_low = c.lower()
        if any(bad in c_low for bad in ["id", "code", "phone", "zip", "serial", "key"]):
            continue
        if inferred in ("numeric", "numeric_percentage", "numeric_rating", "numeric_currency"):
            numeric_cols.append(c)

    linear_models: list[dict[str, Any]] = []
    logistic_models: list[dict[str, Any]] = []
    executive_points: list[str] = []

    # 1. Primary candidate search for Linear Regression
    # Preference for pairs like: (Approved Leaves -> Final Attendance), (Total Attendance -> Final Attendance), etc.
    candidate_pairs = []
    for i, c1 in enumerate(numeric_cols):
        for j, c2 in enumerate(numeric_cols):
            if i != j:
                # Prefer leaves predicting attendance or period-over-period
                c1_low, c2_low = c1.lower(), c2.lower()
                score = 0
                if "leave" in c1_low and "attendance" in c2_low:
                    score += 10
                elif "1st" in c1_low and ("total" in c2_low or "final" in c2_low):
                    score += 5
                elif "total" in c1_low and "final" in c2_low:
                    score += 4
                candidate_pairs.append((score, c1, c2))

    candidate_pairs.sort(key=lambda item: item[0], reverse=True)

    tested_linear = set()
    for _, x_col, y_col in candidate_pairs:
        if (x_col, y_col) in tested_linear or len(linear_models) >= 3:
            continue
        x_vals = []
        y_vals = []
        for r in records:
            xv = r.get(x_col)
            yv = r.get(y_col)
            if xv is not None and yv is not None:
                try:
                    x_vals.append(float(xv))
                    y_vals.append(float(yv))
                except (ValueError, TypeError):
                    pass

        res = fit_linear_regression(x_vals, y_vals, x_col, y_col)
        if res:
            linear_models.append(res)
            tested_linear.add((x_col, y_col))
            if res["r_squared"] >= 0.20:
                executive_points.append(
                    f"Linear Analysis: {res['x_variable']} directly predicts {res['y_variable']} "
                    f"(R² = {res['r_squared']:.2f}, β = {res['slope']}). {res['executive_takeaway']}"
                )

    # 2. Logistic Regression: Predict Chronic Absenteeism or Low Attendance Risk
    # Find attendance column and leave column
    att_col = next((c for c in numeric_cols if "final" in c.lower() or "attendance" in c.lower()), None)
    leave_col = next((c for c in numeric_cols if "total" in c.lower() and "leave" in c.lower() or "approved" in c.lower()), None)
    if not leave_col:
        leave_col = next((c for c in numeric_cols if "leave" in c.lower()), None)

    if att_col and leave_col:
        # Define Binary Risk Outcome: Attendance in lowest 25% or < 80% of mean
        att_vals = [float(r[att_col]) for r in records if r.get(att_col) is not None]
        if att_vals:
            threshold = float(np.percentile(att_vals, 25))
            x_vals = []
            y_bin = []
            for r in records:
                xv = r.get(leave_col)
                yv = r.get(att_col)
                if xv is not None and yv is not None:
                    try:
                        x_vals.append(float(xv))
                        # 1 = High Absenteeism Risk (bottom quartile attendance), 0 = Standard
                        y_bin.append(1 if float(yv) <= threshold else 0)
                    except (ValueError, TypeError):
                        pass

            log_res = fit_logistic_regression(
                x_vals=x_vals,
                y_binary=y_bin,
                x_name=leave_col,
                outcome_label=f"High Absenteeism Risk ({att_col} ≤ {threshold:.1f})"
            )
            if log_res:
                logistic_models.append(log_res)
                executive_points.append(
                    f"Logistic Risk Model: {log_res['x_variable']} is a primary risk driver for {log_res['outcome_label']} "
                    f"(Odds Ratio: {log_res['odds_ratio']}x, Model Accuracy: {log_res['accuracy']*100:.1f}%)."
                )
    elif leave_col and len(numeric_cols) >= 2:
        # Predict High Leave Spike / Disruption Risk (top 25% leave count) from early periods
        predictor_col = next((c for c in numeric_cols if c != leave_col), None)
        leave_vals = [float(r[leave_col]) for r in records if r.get(leave_col) is not None]
        if leave_vals and predictor_col:
            threshold = float(np.percentile(leave_vals, 75))
            if threshold > min(leave_vals):
                x_vals = []
                y_bin = []
                for r in records:
                    xv = r.get(predictor_col)
                    yv = r.get(leave_col)
                    if xv is not None and yv is not None:
                        try:
                            x_vals.append(float(xv))
                            y_bin.append(1 if float(yv) >= threshold else 0)
                        except (ValueError, TypeError):
                            pass
                if len(set(y_bin)) > 1:
                    log_res = fit_logistic_regression(
                        x_vals=x_vals,
                        y_binary=y_bin,
                        x_name=predictor_col,
                        outcome_label=f"High Leave Burden Risk ({leave_col} ≥ {threshold:.1f})"
                    )
                    if log_res:
                        logistic_models.append(log_res)
                        executive_points.append(
                            f"Logistic Risk Model: {log_res['x_variable']} is a primary risk driver for {log_res['outcome_label']} "
                            f"(Odds Ratio: {log_res['odds_ratio']}x, Model Accuracy: {log_res['accuracy']*100:.1f}%)."
                        )

    return {
        "linear_models": linear_models,
        "logistic_models": logistic_models,
        "domain_executive_points": executive_points
    }
