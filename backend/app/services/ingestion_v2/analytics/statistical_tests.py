"""
HighView Ingestion V2 — Statistical Tests & Multiple Testing Corrections
Stage 8: Analytical EDA-B
Provides formal statistical hypothesis testing with effect sizes, sample size tracking,
and Benjamini-Hochberg False Discovery Rate (FDR) correction.
"""

from __future__ import annotations

import math
from typing import Sequence
import numpy as np
import scipy.stats as stats

from app.services.ingestion_v2.contracts.analytics import StatisticalTestEvidence


def perform_two_sample_test(
    sample_a: Sequence[float],
    sample_b: Sequence[float],
    alpha: float = 0.05,
) -> StatisticalTestEvidence | None:
    """
    Perform two-sample Welch's t-test with Cohen's d effect size.
    """
    clean_a = [float(x) for x in sample_a if x is not None and not math.isnan(x)]
    clean_b = [float(x) for x in sample_b if x is not None and not math.isnan(x)]

    n_a, n_b = len(clean_a), len(clean_b)
    if n_a < 2 or n_b < 2:
        return None

    var_a = np.var(clean_a, ddof=1) if n_a > 1 else 0.0
    var_b = np.var(clean_b, ddof=1) if n_b > 1 else 0.0

    if var_a == 0.0 and var_b == 0.0:
        # No variance
        mean_diff = float(np.mean(clean_a) - np.mean(clean_b))
        return StatisticalTestEvidence(
            test_name="WELCH_T_TEST",
            test_statistic=0.0,
            p_value=1.0 if mean_diff == 0.0 else 0.0,
            effect_size=0.0,
            sample_size=n_a + n_b,
            alpha=alpha,
            degrees_of_freedom=float(n_a + n_b - 2),
            is_statistically_significant=(mean_diff != 0.0),
            assumptions=["independence"],
            warnings=["zero_variance_in_groups"],
        )

    res = stats.ttest_ind(clean_a, clean_b, equal_var=False)
    stat = float(res.statistic) if not math.isnan(res.statistic) else 0.0
    p_val = float(res.pvalue) if not math.isnan(res.pvalue) else 1.0
    p_val = max(0.0, min(1.0, p_val))

    # Welch-Satterthwaite df
    se_a = var_a / n_a
    se_b = var_b / n_b
    df = ((se_a + se_b) ** 2) / ((se_a ** 2) / (n_a - 1) + (se_b ** 2) / (n_b - 1)) if (se_a + se_b) > 0 else float(n_a + n_b - 2)

    # Cohen's d with pooled std
    pooled_sd = math.sqrt(((n_a - 1) * var_a + (n_b - 1) * var_b) / max(1, n_a + n_b - 2))
    effect_size = (float(np.mean(clean_a) - np.mean(clean_b)) / pooled_sd) if pooled_sd > 0 else 0.0

    warnings = []
    if n_a < 10 or n_b < 10:
        warnings.append("small_sample_size")

    return StatisticalTestEvidence(
        test_name="WELCH_T_TEST",
        test_statistic=round(stat, 4),
        p_value=round(p_val, 6),
        effect_size=round(effect_size, 4),
        sample_size=n_a + n_b,
        alpha=alpha,
        degrees_of_freedom=round(df, 2),
        is_statistically_significant=(p_val < alpha),
        assumptions=["independence", "continuous_scale"],
        warnings=warnings,
    )


def perform_mann_whitney(
    sample_a: Sequence[float],
    sample_b: Sequence[float],
    alpha: float = 0.05,
) -> StatisticalTestEvidence | None:
    """
    Perform Mann-Whitney U test with rank-biserial effect size r = Z / sqrt(N).
    """
    clean_a = [float(x) for x in sample_a if x is not None and not math.isnan(x)]
    clean_b = [float(x) for x in sample_b if x is not None and not math.isnan(x)]

    n_a, n_b = len(clean_a), len(clean_b)
    if n_a < 2 or n_b < 2:
        return None

    try:
        res = stats.mannwhitneyu(clean_a, clean_b, alternative="two-sided")
        u_stat = float(res.statistic)
        p_val = float(res.pvalue)
        p_val = max(0.0, min(1.0, p_val))

        # Rank-biserial correlation r = 1 - (2U / (n1 * n2))
        r_biserial = 1.0 - (2.0 * u_stat / (n_a * n_b))

        return StatisticalTestEvidence(
            test_name="MANN_WHITNEY_U",
            test_statistic=round(u_stat, 4),
            p_value=round(p_val, 6),
            effect_size=round(r_biserial, 4),
            sample_size=n_a + n_b,
            alpha=alpha,
            degrees_of_freedom=None,
            is_statistically_significant=(p_val < alpha),
            assumptions=["independence", "ordinal_or_continuous"],
            warnings=["small_sample_size"] if (n_a < 10 or n_b < 10) else [],
        )
    except Exception:
        return None


def perform_anova(
    groups: Sequence[Sequence[float]],
    alpha: float = 0.05,
) -> StatisticalTestEvidence | None:
    """
    Perform One-Way ANOVA with Eta-squared (eta^2) effect size.
    """
    clean_groups = [
        [float(x) for x in g if x is not None and not math.isnan(x)]
        for g in groups
    ]
    valid_groups = [g for g in clean_groups if len(g) >= 2]
    if len(valid_groups) < 2:
        return None

    try:
        res = stats.f_oneway(*valid_groups)
        f_stat = float(res.statistic)
        p_val = float(res.pvalue)
        if math.isnan(f_stat) or math.isnan(p_val):
            return None
        p_val = max(0.0, min(1.0, p_val))

        # Eta-squared calculation
        all_vals = [v for g in valid_groups for v in g]
        grand_mean = np.mean(all_vals)
        ss_between = sum(len(g) * ((np.mean(g) - grand_mean) ** 2) for g in valid_groups)
        ss_total = sum((v - grand_mean) ** 2 for v in all_vals)
        eta_squared = float(ss_between / ss_total) if ss_total > 0 else 0.0

        k = len(valid_groups)
        n = len(all_vals)
        df = float(k - 1)

        return StatisticalTestEvidence(
            test_name="ONE_WAY_ANOVA",
            test_statistic=round(f_stat, 4),
            p_value=round(p_val, 6),
            effect_size=round(eta_squared, 4),
            sample_size=n,
            alpha=alpha,
            degrees_of_freedom=df,
            is_statistically_significant=(p_val < alpha),
            assumptions=["independence", "normality", "homoscedasticity"],
            warnings=[],
        )
    except Exception:
        return None


def perform_chi_square(
    contingency_table: Sequence[Sequence[int]],
    alpha: float = 0.05,
) -> StatisticalTestEvidence | None:
    """
    Perform Chi-Square Test of Independence with Cramér's V effect size.
    """
    table = np.array(contingency_table)
    if table.ndim != 2 or table.shape[0] < 2 or table.shape[1] < 2:
        return None

    n = float(table.sum())
    if n <= 0:
        return None

    try:
        res = stats.chi2_contingency(table)
        chi2_stat = float(res.statistic)
        p_val = float(res.pvalue)
        p_val = max(0.0, min(1.0, p_val))

        r, c = table.shape
        min_dim = min(r - 1, c - 1)
        cramers_v = math.sqrt(chi2_stat / (n * min_dim)) if (n * min_dim) > 0 else 0.0

        return StatisticalTestEvidence(
            test_name="CHI_SQUARE_INDEPENDENCE",
            test_statistic=round(chi2_stat, 4),
            p_value=round(p_val, 6),
            effect_size=round(cramers_v, 4),
            sample_size=int(n),
            alpha=alpha,
            degrees_of_freedom=float(res.dof),
            is_statistically_significant=(p_val < alpha),
            assumptions=["independence", "expected_frequencies >= 5"],
            warnings=["low_expected_count"] if np.any(res.expected_freq < 5) else [],
        )
    except Exception:
        return None


def perform_correlation_test(
    x: Sequence[float],
    y: Sequence[float],
    method: str = "pearson",
    alpha: float = 0.05,
) -> StatisticalTestEvidence | None:
    """
    Perform Pearson or Spearman correlation test.
    """
    pairs = [
        (float(a), float(b))
        for a, b in zip(x, y)
        if a is not None and b is not None and not math.isnan(a) and not math.isnan(b)
    ]
    if len(pairs) < 3:
        return None

    clean_x = [p[0] for p in pairs]
    clean_y = [p[1] for p in pairs]

    # Guard against constant vectors
    if np.var(clean_x) == 0.0 or np.var(clean_y) == 0.0:
        return None

    m_lower = method.lower()
    if m_lower == "spearman":
        res = stats.spearmanr(clean_x, clean_y)
        test_name = "SPEARMAN_RANK_CORRELATION"
    else:
        res = stats.pearsonr(clean_x, clean_y)
        test_name = "PEARSON_CORRELATION"

    stat = float(res.statistic) if not math.isnan(res.statistic) else 0.0
    p_val = float(res.pvalue) if not math.isnan(res.pvalue) else 1.0
    p_val = max(0.0, min(1.0, p_val))

    return StatisticalTestEvidence(
        test_name=test_name,
        test_statistic=round(stat, 4),
        p_value=round(p_val, 6),
        effect_size=round(abs(stat), 4),
        sample_size=len(pairs),
        alpha=alpha,
        degrees_of_freedom=float(len(pairs) - 2),
        is_statistically_significant=(p_val < alpha),
        assumptions=["linearity" if m_lower == "pearson" else "monotonicity"],
        warnings=["small_sample_size"] if len(pairs) < 15 else [],
    )


def apply_benjamini_hochberg(
    p_values: Sequence[float],
    alpha: float = 0.05,
) -> list[tuple[float, bool]]:
    """
    Apply Benjamini-Hochberg (BH) False Discovery Rate (FDR) procedure.

    Returns:
        List of tuples (adjusted_p_value, is_significant) matching the original order.
    """
    m = len(p_values)
    if m == 0:
        return []

    # Sort p-values ascending while keeping track of original indices
    sorted_pairs = sorted(enumerate(p_values), key=lambda x: x[1])

    # Compute step-up adjusted p-values
    # q_i = min_{k >= i} (p_k * m / k)
    adjusted: list[tuple[int, float]] = []
    min_so_far = 1.0
    for rank_idx, (orig_idx, p_val) in reversed(list(enumerate(sorted_pairs, start=1))):
        q = (p_val * m) / rank_idx
        min_so_far = min(min_so_far, q)
        adjusted.append((orig_idx, min(1.0, max(0.0, min_so_far))))

    # Restore original order
    adjusted_dict = dict(adjusted)
    results: list[tuple[float, bool]] = []
    for i in range(m):
        adj_p = round(adjusted_dict[i], 6)
        sig = adj_p < alpha
        results.append((adj_p, sig))

    return results
