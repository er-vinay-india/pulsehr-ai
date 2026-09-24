"""Candidate Fact Discovery Engine for PulseHR AI.

Given a SemanticDatasetProfile and AnalysisOpportunityMap from Phase 1,
deterministically discovers a collection of mathematically defensible candidate facts.
No language model is involved in discovering or computing these facts.
"""

import math
from typing import Any
import numpy as np
import pandas as pd

from .semantic_classifier import SemanticDatasetProfile, SemanticRole, MetricPolarity
from .opportunity_map import AnalysisOpportunityMap, AnalysisOpportunity, OpportunityType
from .candidate_fact import CandidateFact, ReliabilityStatus


class CandidateFactDiscoveryEngine:
    """Discovers empirical candidate facts strictly guided by the AnalysisOpportunityMap."""

    @classmethod
    def discover_facts(
        cls,
        df: pd.DataFrame,
        profile: SemanticDatasetProfile,
        opportunity_map: AnalysisOpportunityMap,
        max_facts_per_opportunity: int = 5
    ) -> tuple[list[CandidateFact], list[CandidateFact]]:
        """Executes admissible analytical opportunities and surfaces structured candidate facts.
        
        Returns:
            tuple of (reliable_facts, rejected_or_unreliable_facts)
        """
        reliable_facts: list[CandidateFact] = []
        unreliable_facts: list[CandidateFact] = []
        fact_counter = 1

        for opp in opportunity_map.opportunities:
            generated = cls._evaluate_opportunity(df, profile, opp, fact_counter, max_facts_per_opportunity)
            for fact in generated:
                fact_counter += 1
                if fact.reliability_status == ReliabilityStatus.RELIABLE:
                    reliable_facts.append(fact)
                else:
                    unreliable_facts.append(fact)

        return reliable_facts, unreliable_facts

    @classmethod
    def _evaluate_opportunity(
        cls,
        df: pd.DataFrame,
        profile: SemanticDatasetProfile,
        opp: AnalysisOpportunity,
        start_idx: int,
        max_facts: int
    ) -> list[CandidateFact]:
        """Dispatches an opportunity to its specialized mathematical evaluator."""
        opp_type = opp.opportunity_type

        facts: list[CandidateFact] = []
        if opp_type == OpportunityType.TARGET_COMPLIANCE:
            facts = cls._evaluate_target_compliance(df, profile, opp, start_idx, max_facts)
        elif opp_type == OpportunityType.PERIOD_TREND:
            facts = cls._evaluate_period_trend(df, profile, opp, start_idx, max_facts)
        elif opp_type == OpportunityType.SEGMENT_COMPARISON:
            facts = cls._evaluate_segment_comparison(df, profile, opp, start_idx, max_facts)
        elif opp_type == OpportunityType.ENTITY_CONCENTRATION:
            facts = cls._evaluate_entity_concentration(df, profile, opp, start_idx, max_facts)
        elif opp_type == OpportunityType.MEASURE_RELATIONSHIP:
            facts = cls._evaluate_measure_relationship(df, profile, opp, start_idx, max_facts)
        elif opp_type == OpportunityType.SUBGROUP_RATE_DISPARITY:
            facts = cls._evaluate_subgroup_rate_disparity(df, profile, opp, start_idx, max_facts)
        elif opp_type == OpportunityType.CATEGORICAL_CROSS_TAB:
            facts = cls._evaluate_categorical_cross_tab(df, profile, opp, start_idx, max_facts)
        elif opp_type == OpportunityType.TARGET_ASSOCIATION:
            facts = cls._evaluate_target_association(df, profile, opp, start_idx, max_facts)

        if opp.is_user_priority:
            for f in facts:
                f.priority_type = "USER_PRIORITY"
                f.provenance = "USER_EXPLICIT"
                if opp.priority_reason:
                    f.target_rule_description = opp.priority_reason

        return facts

    # -------------------------------------------------------------------------
    # 0. TARGET_COMPLIANCE (Business Rule / Target Adherence)
    # -------------------------------------------------------------------------

    @classmethod
    def _evaluate_target_compliance(
        cls,
        df: pd.DataFrame,
        profile: SemanticDatasetProfile,
        opp: AnalysisOpportunity,
        start_idx: int,
        max_facts: int
    ) -> list[CandidateFact]:
        dim_col = opp.primary_column
        metric_col = opp.secondary_column
        target_rule = opp.target_rule or {}
        threshold = float(target_rule.get("threshold", 0))
        operator = target_rule.get("operator", ">=")

        if not metric_col or metric_col not in df.columns or dim_col not in df.columns:
            return []

        clean_metric = cls._coerce_numeric(df[metric_col])
        clean_dim = df[dim_col].astype(str).str.strip()
        work_df = pd.DataFrame({"dim": clean_dim, "val": clean_metric}).dropna()

        if len(work_df) < 4:
            return []

        if operator == ">=":
            work_df["compliant"] = work_df["val"] >= threshold
        elif operator == "<=":
            work_df["compliant"] = work_df["val"] <= threshold
        elif operator == ">":
            work_df["compliant"] = work_df["val"] > threshold
        elif operator == "<":
            work_df["compliant"] = work_df["val"] < threshold
        else:
            work_df["compliant"] = work_df["val"] == threshold

        total_records = len(work_df)
        overall_compliant_count = int(work_df["compliant"].sum())
        overall_compliance_pct = round((overall_compliant_count / total_records) * 100.0, 2)

        facts: list[CandidateFact] = []
        grouped = work_df.groupby("dim")
        group_stats = []
        for g_name, g_df in grouped:
            g_total = len(g_df)
            if g_total >= 1:
                g_comp = int(g_df["compliant"].sum())
                g_pct = round((g_comp / g_total) * 100.0, 2)
                group_stats.append((g_name, g_total, g_comp, g_pct))

        group_stats.sort(key=lambda x: x[3], reverse=True)

        rule_desc = f"{metric_col} {operator} {threshold:g}"
        for idx, (g_name, g_total, g_comp, g_pct) in enumerate(group_stats[:max_facts]):
            abs_diff = round(g_pct - overall_compliance_pct, 2)
            stmt = (
                f"Segment '{g_name}' achieved {g_pct:.1f}% compliance with explicit business rule "
                f"'{rule_desc}' ({g_comp}/{g_total} records compliant; overall dataset baseline is {overall_compliance_pct:.1f}%)."
            )
            fact = CandidateFact(
                fact_id=f"FACT-{start_idx + idx:03d}",
                fact_type=OpportunityType.TARGET_COMPLIANCE.value,
                metric=f"{metric_col}_compliance_pct",
                dimensions={dim_col: g_name},
                value=g_pct,
                baseline_value=overall_compliance_pct,
                absolute_difference=abs_diff,
                relative_difference=round((abs_diff / overall_compliance_pct) * 100.0, 2) if overall_compliance_pct > 0 else 0.0,
                sample_size=g_total,
                statistical_info={
                    "compliant_records": g_comp,
                    "total_records": g_total,
                    "target_threshold": threshold,
                    "target_operator": operator,
                    "overall_compliance_pct": overall_compliance_pct
                },
                source_columns=[dim_col, metric_col],
                polarity=MetricPolarity.HIGHER_IS_BETTER if g_pct >= overall_compliance_pct else MetricPolarity.LOWER_IS_BETTER,
                calculation_method="threshold_compliance_rate_by_segment",
                statement=stmt,
                reliability_status=ReliabilityStatus.RELIABLE,
                priority_type="USER_PRIORITY",
                provenance="USER_EXPLICIT",
                target_rule_description=rule_desc
            )
            facts.append(fact)

        return facts

    # -------------------------------------------------------------------------
    # Helper utilities: Data cleaning and pure statistics
    # -------------------------------------------------------------------------

    @staticmethod
    def _coerce_numeric(series: pd.Series) -> pd.Series:
        cleaned = series.astype(str).str.strip().str.replace(r'[\$€£¥₹%]', '', regex=True).str.replace(',', '', regex=False)
        return pd.to_numeric(cleaned, errors='coerce')

    @classmethod
    def _format_diff_str(cls, diff: float, unit: str, is_rate: bool) -> str:
        sign = "+" if diff > 0 else ""
        if is_rate or unit == "%":
            return f"{sign}{diff:.2f} percentage points"
        elif unit == "$":
            return f"{sign}${abs(diff):,.2f}" if diff >= 0 else f"-${abs(diff):,.2f}"
        elif unit:
            return f"{sign}{diff:.2f} {unit}"
        return f"{sign}{diff:.2f}"

    @classmethod
    def _format_value_str(cls, val: float, unit: str) -> str:
        if unit == "$":
            return f"${val:,.2f}"
        elif unit == "%":
            return f"{val:.2f}%"
        elif unit:
            return f"{val:.2f} {unit}"
        return f"{val:.2f}"

    @staticmethod
    def _calculate_ols(x_arr: np.ndarray, y_arr: np.ndarray) -> tuple[float, float]:
        """Calculates Ordinary Least Squares linear regression slope and R^2."""
        n = len(x_arr)
        if n < 2:
            return 0.0, 0.0
        x_mean = float(np.mean(x_arr))
        y_mean = float(np.mean(y_arr))
        ss_xx = float(np.sum((x_arr - x_mean) ** 2))
        ss_yy = float(np.sum((y_arr - y_mean) ** 2))
        ss_xy = float(np.sum((x_arr - x_mean) * (y_arr - y_mean)))

        if ss_xx == 0 or ss_yy == 0:
            return 0.0, 0.0
        slope = ss_xy / ss_xx
        r2 = (ss_xy ** 2) / (ss_xx * ss_yy)
        return float(slope), float(r2)

    @staticmethod
    def _p_value_from_z(z_score: float) -> float:
        """Approximates two-tailed p-value using the standard normal error function."""
        try:
            p = 1.0 - math.erf(abs(z_score) / math.sqrt(2.0))
            return max(0.0, min(1.0, float(p)))
        except Exception:
            return 1.0

    # -------------------------------------------------------------------------
    # 1. PERIOD_TREND
    # -------------------------------------------------------------------------

    @classmethod
    def _evaluate_period_trend(
        cls,
        df: pd.DataFrame,
        profile: SemanticDatasetProfile,
        opp: AnalysisOpportunity,
        start_idx: int,
        max_facts: int
    ) -> list[CandidateFact]:
        dt_col = opp.primary_column
        m_col = opp.secondary_column
        if not m_col or dt_col not in df.columns or m_col not in df.columns:
            return []

        col_prof = profile.columns.get(m_col)
        polarity = col_prof.metric_polarity if col_prof else MetricPolarity.UNKNOWN
        unit = col_prof.unit or ""
        is_rate = col_prof.semantic_role == SemanticRole.PERCENTAGE_RATE if col_prof else False

        # Parse date and coerce numeric
        dt_series = pd.to_datetime(df[dt_col], errors='coerce')
        num_series = cls._coerce_numeric(df[m_col])
        valid_mask = dt_series.notna() & num_series.notna()
        valid_df = pd.DataFrame({"_dt": dt_series[valid_mask], "_val": num_series[valid_mask]}).sort_values("_dt")

        if len(valid_df) < 3:
            return [
                CandidateFact(
                    fact_id=f"FACT-{start_idx:03d}",
                    fact_type=OpportunityType.PERIOD_TREND.value,
                    metric=m_col,
                    dimensions={"time_dimension": dt_col},
                    sample_size=len(valid_df),
                    source_columns=[dt_col, m_col],
                    polarity=polarity,
                    calculation_method="chronological_period_aggregation",
                    reliability_status=ReliabilityStatus.UNRELIABLE,
                    reliability_reason=f"Insufficient valid temporal records (n={len(valid_df)} < 3)",
                    statement=f"Trend analysis for {m_col} over {dt_col} rejected: fewer than 3 valid data points."
                )
            ]

        # Determine frequency (Yearly, Monthly, or Daily)
        span_days = (valid_df["_dt"].max() - valid_df["_dt"].min()).days
        if span_days > 730:
            freq = "Y"
        elif span_days > 45:
            freq = "M"
        else:
            freq = "D"

        valid_df["_period"] = valid_df["_dt"].dt.to_period(freq).astype(str)
        grouped = valid_df.groupby("_period")["_val"].agg(["count", "mean"]).reset_index().sort_values("_period")

        # If grouping reduced periods below 3 and freq was M/Y, try finer frequency
        if len(grouped) < 3 and freq != "D":
            freq = "D"
            valid_df["_period"] = valid_df["_dt"].dt.to_period(freq).astype(str)
            grouped = valid_df.groupby("_period")["_val"].agg(["count", "mean"]).reset_index().sort_values("_period")

        if len(grouped) < 3:
            return [
                CandidateFact(
                    fact_id=f"FACT-{start_idx:03d}",
                    fact_type=OpportunityType.PERIOD_TREND.value,
                    metric=m_col,
                    dimensions={"time_dimension": dt_col, "frequency": freq},
                    sample_size=int(grouped["count"].sum()),
                    source_columns=[dt_col, m_col],
                    polarity=polarity,
                    calculation_method="chronological_period_aggregation",
                    reliability_status=ReliabilityStatus.UNRELIABLE,
                    reliability_reason=f"Insufficient distinct periods (found {len(grouped)}, required >= 3)",
                    statement=f"Trend analysis for {m_col} over {dt_col} rejected: only {len(grouped)} time periods available."
                )
            ]

        # Calculate chronological metrics
        periods = grouped["_period"].tolist()
        means = grouped["mean"].tolist()
        counts = grouped["count"].tolist()

        start_val = float(means[0])
        end_val = float(means[-1])
        abs_diff = round(end_val - start_val, 2)
        rel_diff = round((abs_diff / abs(start_val) * 100), 1) if start_val != 0 else None

        # Linear regression slope over period indices 0, 1, ..., k-1
        x_indices = np.arange(len(means), dtype=float)
        slope, r2 = cls._calculate_ols(x_indices, np.array(means, dtype=float))

        diff_str = cls._format_diff_str(abs_diff, unit, is_rate)
        rel_str = f", {rel_diff:+0.1f}% relative" if rel_diff is not None else ""
        start_str = cls._format_value_str(start_val, unit)
        end_str = cls._format_value_str(end_val, unit)
        total_sample = int(sum(counts))

        statement = (
            f"Over {len(grouped)} periods ({periods[0]} to {periods[-1]}), mean {m_col} changed from "
            f"{start_str} to {end_str} (difference = {diff_str}{rel_str}, "
            f"linear slope = {slope:+.4f}/period, R² = {r2:.2f}; n = {total_sample})."
        )

        fact = CandidateFact(
            fact_id=f"FACT-{start_idx:03d}",
            fact_type=OpportunityType.PERIOD_TREND.value,
            metric=m_col,
            dimensions={"time_dimension": dt_col, "frequency": freq, "period_count": len(grouped)},
            value=round(end_val, 2),
            baseline_value=round(start_val, 2),
            absolute_difference=abs_diff,
            relative_difference=rel_diff,
            sample_size=total_sample,
            statistical_info={
                "slope": round(slope, 4),
                "r_squared": round(r2, 4),
                "periods_evaluated": len(grouped),
                "start_period": periods[0],
                "end_period": periods[-1]
            },
            source_columns=[dt_col, m_col],
            time_window=f"{periods[0]} to {periods[-1]}",
            polarity=polarity,
            semantic_confidence=col_prof.confidence if col_prof else 0.8,
            calculation_method="chronological_period_aggregation_and_ordinary_least_squares",
            evidence_metadata={
                "periods": periods,
                "period_means": [round(float(m), 2) for m in means],
                "period_counts": counts
            },
            statement=statement,
            reliability_status=ReliabilityStatus.RELIABLE
        )
        return [fact]

    # -------------------------------------------------------------------------
    # 2. SEGMENT_COMPARISON
    # -------------------------------------------------------------------------

    @classmethod
    def _evaluate_segment_comparison(
        cls,
        df: pd.DataFrame,
        profile: SemanticDatasetProfile,
        opp: AnalysisOpportunity,
        start_idx: int,
        max_facts: int
    ) -> list[CandidateFact]:
        dim_col = opp.primary_column
        m_col = opp.secondary_column
        if not m_col or dim_col not in df.columns or m_col not in df.columns:
            return []

        col_prof = profile.columns.get(m_col)
        polarity = col_prof.metric_polarity if col_prof else MetricPolarity.UNKNOWN
        unit = col_prof.unit or ""
        is_rate = col_prof.semantic_role == SemanticRole.PERCENTAGE_RATE if col_prof else False

        num_series = cls._coerce_numeric(df[m_col])
        clean_df = pd.DataFrame({"_dim": df[dim_col].dropna().astype(str).str.strip(), "_val": num_series}).dropna()

        if len(clean_df) < 3:
            return [
                CandidateFact(
                    fact_id=f"FACT-{start_idx:03d}",
                    fact_type=OpportunityType.SEGMENT_COMPARISON.value,
                    metric=m_col,
                    dimensions={"dimension": dim_col},
                    sample_size=len(clean_df),
                    source_columns=[dim_col, m_col],
                    polarity=polarity,
                    calculation_method="segment_group_mean_and_baseline_variance",
                    reliability_status=ReliabilityStatus.UNRELIABLE,
                    reliability_reason=f"Insufficient valid records for segment analysis (n={len(clean_df)} < 3)",
                    statement=f"Segment comparison for {m_col} across {dim_col} rejected: insufficient valid data points."
                )
            ]

        baseline_mean = float(clean_df["_val"].mean())
        baseline_std = float(clean_df["_val"].std()) if len(clean_df) > 1 else 0.0

        grouped = clean_df.groupby("_dim")["_val"].agg(["count", "mean", "std"]).reset_index()
        if len(grouped) < 2:
            return [
                CandidateFact(
                    fact_id=f"FACT-{start_idx:03d}",
                    fact_type=OpportunityType.SEGMENT_COMPARISON.value,
                    metric=m_col,
                    dimensions={"dimension": dim_col},
                    sample_size=len(clean_df),
                    source_columns=[dim_col, m_col],
                    polarity=polarity,
                    calculation_method="segment_group_mean_and_baseline_variance",
                    reliability_status=ReliabilityStatus.UNRELIABLE,
                    reliability_reason=f"Dimension '{dim_col}' has fewer than 2 distinct valid groups",
                    statement=f"Segment comparison for {m_col} across {dim_col} rejected: only {len(grouped)} segment."
                )
            ]

        # Calculate ANOVA F-statistic
        grand_mean = baseline_mean
        ss_between = float(sum(row.count * ((row.mean - grand_mean) ** 2) for row in grouped.itertuples()))
        df_between = len(grouped) - 1
        ms_between = ss_between / df_between if df_between > 0 else 0.0

        ss_within = float(sum((row.count - 1) * ((row.std if not pd.isna(row.std) else 0.0) ** 2) for row in grouped.itertuples()))
        df_within = len(clean_df) - len(grouped)
        ms_within = ss_within / df_within if df_within > 0 else 1.0

        f_stat = ms_between / ms_within if ms_within > 0 else 0.0

        # Sort descending by mean
        grouped = grouped.sort_values("mean", ascending=False).reset_index(drop=True)

        facts: list[CandidateFact] = []
        cur_idx = start_idx

        # Select highest segment, lowest segment, and greatest deviation
        segments_to_emit = []
        segments_to_emit.append((grouped.iloc[0], 1, "highest_segment"))
        if len(grouped) > 1:
            segments_to_emit.append((grouped.iloc[-1], len(grouped), "lowest_segment"))

        for seg_row, rank, tier in segments_to_emit:
            seg_val = str(seg_row["_dim"])
            n_seg = int(seg_row["count"])
            s_mean = float(seg_row["mean"])
            abs_diff = round(s_mean - baseline_mean, 2)
            rel_diff = round((abs_diff / abs(baseline_mean) * 100), 1) if baseline_mean != 0 else None

            # Statistical reliability check: small group sample size
            is_unreliable = n_seg < 3
            status = ReliabilityStatus.UNRELIABLE if is_unreliable else ReliabilityStatus.RELIABLE
            reason = f"Small subgroup sample size (n={n_seg} < 3)" if is_unreliable else None

            diff_str = cls._format_diff_str(abs_diff, unit, is_rate)
            rel_str = f" ({rel_diff:+0.1f}% relative)" if rel_diff is not None else ""
            seg_mean_str = cls._format_value_str(s_mean, unit)
            base_mean_str = cls._format_value_str(baseline_mean, unit)

            statement = (
                f"Segment '{seg_val}' in {dim_col} (rank {rank}/{len(grouped)}) has mean {m_col} = {seg_mean_str}; "
                f"overall baseline = {base_mean_str}; difference = {diff_str}{rel_str}; n = {n_seg}."
            )

            seg_std = float(seg_row["std"]) if not pd.isna(seg_row["std"]) else 0.0

            fact = CandidateFact(
                fact_id=f"FACT-{cur_idx:03d}",
                fact_type=OpportunityType.SEGMENT_COMPARISON.value,
                metric=m_col,
                dimensions={dim_col: seg_val, "rank": rank, "tier": tier},
                value=round(s_mean, 2),
                baseline_value=round(baseline_mean, 2),
                absolute_difference=abs_diff,
                relative_difference=rel_diff,
                sample_size=n_seg,
                statistical_info={
                    "between_group_f_stat": round(f_stat, 2),
                    "baseline_mean": round(baseline_mean, 2),
                    "baseline_std": round(baseline_std, 2),
                    "group_std": round(seg_std, 2),
                    "total_segments": len(grouped)
                },
                source_columns=[dim_col, m_col],
                polarity=polarity,
                semantic_confidence=col_prof.confidence if col_prof else 0.8,
                calculation_method="segment_group_mean_and_baseline_variance",
                evidence_metadata={
                    "dimension": dim_col,
                    "segment_value": seg_val,
                    "segment_count": n_seg,
                    "total_sample": len(clean_df)
                },
                statement=statement,
                reliability_status=status,
                reliability_reason=reason
            )
            facts.append(fact)
            cur_idx += 1

        return facts[:max_facts]

    # -------------------------------------------------------------------------
    # 3. ENTITY_CONCENTRATION
    # -------------------------------------------------------------------------

    @classmethod
    def _evaluate_entity_concentration(
        cls,
        df: pd.DataFrame,
        profile: SemanticDatasetProfile,
        opp: AnalysisOpportunity,
        start_idx: int,
        max_facts: int
    ) -> list[CandidateFact]:
        ent_col = opp.primary_column
        m_col = opp.secondary_column
        if not m_col or ent_col not in df.columns or m_col not in df.columns:
            return []

        col_prof = profile.columns.get(m_col)
        polarity = col_prof.metric_polarity if col_prof else MetricPolarity.UNKNOWN
        unit = col_prof.unit or ""

        num_series = cls._coerce_numeric(df[m_col])
        clean_df = pd.DataFrame({"_ent": df[ent_col].dropna().astype(str), "_val": num_series}).dropna()
        # Filter for positive volume
        clean_df = clean_df[clean_df["_val"] > 0]

        if len(clean_df) < 5:
            return [
                CandidateFact(
                    fact_id=f"FACT-{start_idx:03d}",
                    fact_type=OpportunityType.ENTITY_CONCENTRATION.value,
                    metric=m_col,
                    dimensions={"entity_column": ent_col},
                    sample_size=len(clean_df),
                    source_columns=[ent_col, m_col],
                    polarity=polarity,
                    calculation_method="pareto_cumulative_volume_and_gini_coefficient",
                    reliability_status=ReliabilityStatus.UNRELIABLE,
                    reliability_reason=f"Insufficient positive entities for concentration analysis (n={len(clean_df)} < 5)",
                    statement=f"Concentration analysis for {m_col} by {ent_col} rejected: fewer than 5 positive entities."
                )
            ]

        # Aggregate sum per entity
        ent_agg = clean_df.groupby("_ent")["_val"].sum().sort_values(ascending=False).reset_index()
        total_volume = float(ent_agg["_val"].sum())
        total_entities = len(ent_agg)

        if total_volume <= 0 or total_entities < 5:
            return [
                CandidateFact(
                    fact_id=f"FACT-{start_idx:03d}",
                    fact_type=OpportunityType.ENTITY_CONCENTRATION.value,
                    metric=m_col,
                    dimensions={"entity_column": ent_col},
                    sample_size=total_entities,
                    source_columns=[ent_col, m_col],
                    polarity=polarity,
                    calculation_method="pareto_cumulative_volume_and_gini_coefficient",
                    reliability_status=ReliabilityStatus.UNRELIABLE,
                    reliability_reason="Total metric volume non-positive or distinct entities < 5",
                    statement=f"Concentration analysis for {m_col} by {ent_col} rejected: non-positive sum or < 5 entities."
                )
            ]

        # Top 20% calculation
        k_20 = max(1, int(round(0.20 * total_entities)))
        top_20_volume = float(ent_agg.iloc[:k_20]["_val"].sum())
        top_20_share_pct = round((top_20_volume / total_volume) * 100, 1)

        # Top 1 entity calculation
        top_1_volume = float(ent_agg.iloc[0]["_val"])
        top_1_share_pct = round((top_1_volume / total_volume) * 100, 1)

        # Gini coefficient calculation
        sorted_vals = np.sort(ent_agg["_val"].values.astype(float))
        n = len(sorted_vals)
        index = np.arange(1, n + 1)
        gini = float((np.sum((2 * index - n - 1) * sorted_vals)) / (n * np.sum(sorted_vals)))

        abs_diff = round(top_20_share_pct - 20.0, 1)
        rel_diff = round((abs_diff / 20.0) * 100, 1)

        total_vol_str = cls._format_value_str(total_volume, unit)
        top_20_vol_str = cls._format_value_str(top_20_volume, unit)

        statement = (
            f"Top 20% of {ent_col} entities ({k_20} of {total_entities}) account for "
            f"{top_20_share_pct:.1f}% of total {m_col} ({top_20_vol_str} of {total_vol_str}; "
            f"Gini coefficient = {gini:.3f}; top entity '{ent_agg.iloc[0]['_ent']}' accounts for {top_1_share_pct:.1f}%; "
            f"n = {total_entities})."
        )

        fact = CandidateFact(
            fact_id=f"FACT-{start_idx:03d}",
            fact_type=OpportunityType.ENTITY_CONCENTRATION.value,
            metric=m_col,
            dimensions={"entity_column": ent_col, "concentration_tier": "top_20_percent"},
            value=top_20_share_pct,
            baseline_value=20.0,
            absolute_difference=abs_diff,
            relative_difference=rel_diff,
            sample_size=total_entities,
            statistical_info={
                "gini_coefficient": round(gini, 3),
                "top_20_entity_count": k_20,
                "top_1_entity_share_pct": top_1_share_pct,
                "total_volume": round(total_volume, 2),
                "top_20_volume": round(top_20_volume, 2)
            },
            source_columns=[ent_col, m_col],
            polarity=polarity,
            semantic_confidence=col_prof.confidence if col_prof else 0.85,
            calculation_method="pareto_cumulative_volume_and_gini_coefficient",
            evidence_metadata={
                "top_entities": ent_agg.iloc[:k_20]["_ent"].tolist(),
                "top_entity_volumes": [round(float(v), 2) for v in ent_agg.iloc[:k_20]["_val"].tolist()]
            },
            statement=statement,
            reliability_status=ReliabilityStatus.RELIABLE
        )
        return [fact]

    # -------------------------------------------------------------------------
    # 4. MEASURE_RELATIONSHIP
    # -------------------------------------------------------------------------

    @classmethod
    def _evaluate_measure_relationship(
        cls,
        df: pd.DataFrame,
        profile: SemanticDatasetProfile,
        opp: AnalysisOpportunity,
        start_idx: int,
        max_facts: int
    ) -> list[CandidateFact]:
        m1 = opp.primary_column
        m2 = opp.secondary_column
        if not m2 or m1 not in df.columns or m2 not in df.columns:
            return []

        p1 = profile.columns.get(m1)
        p2 = profile.columns.get(m2)

        s1 = cls._coerce_numeric(df[m1])
        s2 = cls._coerce_numeric(df[m2])
        valid_df = pd.DataFrame({"x": s1, "y": s2}).dropna()

        n = len(valid_df)
        if n < 4:
            return [
                CandidateFact(
                    fact_id=f"FACT-{start_idx:03d}",
                    fact_type=OpportunityType.MEASURE_RELATIONSHIP.value,
                    metric=f"{m1}_vs_{m2}",
                    dimensions={"measure_x": m1, "measure_y": m2},
                    sample_size=n,
                    source_columns=[m1, m2],
                    polarity=MetricPolarity.NEUTRAL,
                    calculation_method="pearson_and_spearman_bivariate_correlation",
                    reliability_status=ReliabilityStatus.UNRELIABLE,
                    reliability_reason=f"Insufficient paired observations for correlation (n={n} < 4)",
                    statement=f"Relationship between {m1} and {m2} rejected: fewer than 4 paired observations."
                )
            ]

        x_vals = valid_df["x"].values.astype(float)
        y_vals = valid_df["y"].values.astype(float)

        std_x = float(np.std(x_vals))
        std_y = float(np.std(y_vals))

        if std_x == 0 or std_y == 0:
            return [
                CandidateFact(
                    fact_id=f"FACT-{start_idx:03d}",
                    fact_type=OpportunityType.MEASURE_RELATIONSHIP.value,
                    metric=f"{m1}_vs_{m2}",
                    dimensions={"measure_x": m1, "measure_y": m2},
                    sample_size=n,
                    source_columns=[m1, m2],
                    polarity=MetricPolarity.NEUTRAL,
                    calculation_method="pearson_and_spearman_bivariate_correlation",
                    reliability_status=ReliabilityStatus.UNRELIABLE,
                    reliability_reason="Zero variance in one or both measures; correlation is mathematically undefined",
                    statement=f"Relationship between {m1} and {m2} rejected: one or both variables have zero variance."
                )
            ]

        # Pearson correlation
        corr_matrix = np.corrcoef(x_vals, y_vals)
        r = float(corr_matrix[0, 1])
        r2 = float(r ** 2)

        # Spearman rank correlation
        rank_x = pd.Series(x_vals).rank().values
        rank_y = pd.Series(y_vals).rank().values
        spearman_rho = float(np.corrcoef(rank_x, rank_y)[0, 1])

        # Approximate p-value via t-test
        t_stat = r * math.sqrt((n - 2) / max(1e-9, (1.0 - r2)))
        p_val = cls._p_value_from_z(t_stat)

        # Statistical responsibility: NEVER imply causation
        direction_word = "positive" if r > 0 else "negative" if r < 0 else "zero"
        statement = (
            f"Pearson correlation between {m1} and {m2} is r = {r:+.3f} "
            f"(p = {p_val:.3f}, R² = {r2:.2f}, Spearman ρ = {spearman_rho:+.3f}; n = {n}), "
            f"indicating a {direction_word} statistical association without implying causation."
        )

        fact = CandidateFact(
            fact_id=f"FACT-{start_idx:03d}",
            fact_type=OpportunityType.MEASURE_RELATIONSHIP.value,
            metric=f"{m1}_vs_{m2}",
            dimensions={"measure_x": m1, "measure_y": m2},
            value=round(r, 3),
            baseline_value=0.0,
            absolute_difference=round(r, 3),
            relative_difference=None,
            sample_size=n,
            statistical_info={
                "pearson_r": round(r, 3),
                "spearman_rho": round(spearman_rho, 3),
                "r_squared": round(r2, 3),
                "t_stat": round(t_stat, 2),
                "p_value": round(p_val, 3),
                "correlation_direction": direction_word
            },
            source_columns=[m1, m2],
            polarity=MetricPolarity.NEUTRAL,
            semantic_confidence=min(p1.confidence if p1 else 0.8, p2.confidence if p2 else 0.8),
            calculation_method="pearson_and_spearman_bivariate_correlation",
            evidence_metadata={
                "mean_x": round(float(np.mean(x_vals)), 2),
                "mean_y": round(float(np.mean(y_vals)), 2),
                "std_x": round(std_x, 2),
                "std_y": round(std_y, 2)
            },
            statement=statement,
            reliability_status=ReliabilityStatus.RELIABLE
        )
        return [fact]

    # -------------------------------------------------------------------------
    # 5. SUBGROUP_RATE_DISPARITY
    # -------------------------------------------------------------------------

    @classmethod
    def _evaluate_subgroup_rate_disparity(
        cls,
        df: pd.DataFrame,
        profile: SemanticDatasetProfile,
        opp: AnalysisOpportunity,
        start_idx: int,
        max_facts: int
    ) -> list[CandidateFact]:
        dim_col = opp.primary_column
        r_col = opp.secondary_column
        if not r_col or dim_col not in df.columns or r_col not in df.columns:
            return []

        col_prof = profile.columns.get(r_col)
        polarity = col_prof.metric_polarity if col_prof else MetricPolarity.UNKNOWN

        num_series = cls._coerce_numeric(df[r_col])
        clean_df = pd.DataFrame({"_dim": df[dim_col].dropna().astype(str).str.strip(), "_rate": num_series}).dropna()

        if len(clean_df) < 3:
            return [
                CandidateFact(
                    fact_id=f"FACT-{start_idx:03d}",
                    fact_type=OpportunityType.SUBGROUP_RATE_DISPARITY.value,
                    metric=r_col,
                    dimensions={"dimension": dim_col},
                    sample_size=len(clean_df),
                    source_columns=[dim_col, r_col],
                    polarity=polarity,
                    calculation_method="subgroup_rate_spread_and_disparity_ratio",
                    reliability_status=ReliabilityStatus.UNRELIABLE,
                    reliability_reason=f"Insufficient valid rate records (n={len(clean_df)} < 3)",
                    statement=f"Rate disparity analysis for {r_col} across {dim_col} rejected: insufficient valid data points."
                )
            ]

        baseline_rate = float(clean_df["_rate"].mean())
        grouped = clean_df.groupby("_dim")["_rate"].agg(["count", "mean"]).reset_index()

        if len(grouped) < 2:
            return [
                CandidateFact(
                    fact_id=f"FACT-{start_idx:03d}",
                    fact_type=OpportunityType.SUBGROUP_RATE_DISPARITY.value,
                    metric=r_col,
                    dimensions={"dimension": dim_col},
                    sample_size=len(clean_df),
                    source_columns=[dim_col, r_col],
                    polarity=polarity,
                    calculation_method="subgroup_rate_spread_and_disparity_ratio",
                    reliability_status=ReliabilityStatus.UNRELIABLE,
                    reliability_reason=f"Dimension '{dim_col}' has only 1 subgroup",
                    statement=f"Rate disparity analysis for {r_col} across {dim_col} rejected: only 1 subgroup available."
                )
            ]

        grouped = grouped.sort_values("mean", ascending=False).reset_index(drop=True)

        facts: list[CandidateFact] = []
        cur_idx = start_idx

        # Focus on highest and lowest subgroup rate
        subgroups = [grouped.iloc[0]]
        if len(grouped) > 1:
            subgroups.append(grouped.iloc[-1])

        for row in subgroups:
            subgroup_name = str(row["_dim"])
            n_sub = int(row["count"])
            rate_val = float(row["mean"])
            # Difference for rates MUST be stated in percentage points (pp)
            diff_pp = round(rate_val - baseline_rate, 2)
            rel_diff = round((diff_pp / abs(baseline_rate) * 100), 1) if baseline_rate != 0 else None

            is_unreliable = n_sub < 3
            status = ReliabilityStatus.UNRELIABLE if is_unreliable else ReliabilityStatus.RELIABLE
            reason = f"Small subgroup sample size (n={n_sub} < 3)" if is_unreliable else None

            rel_str = f" ({rel_diff:+0.1f}% relative)" if rel_diff is not None else ""
            statement = (
                f"Subgroup '{subgroup_name}' in {dim_col} has {r_col} = {rate_val:.2f}%; "
                f"overall baseline = {baseline_rate:.2f}%; difference = {diff_pp:+0.2f} percentage points{rel_str}; "
                f"n = {n_sub}."
            )

            fact = CandidateFact(
                fact_id=f"FACT-{cur_idx:03d}",
                fact_type=OpportunityType.SUBGROUP_RATE_DISPARITY.value,
                metric=r_col,
                dimensions={dim_col: subgroup_name},
                value=round(rate_val, 2),
                baseline_value=round(baseline_rate, 2),
                absolute_difference=diff_pp,
                relative_difference=rel_diff,
                sample_size=n_sub,
                statistical_info={
                    "baseline_rate_pct": round(baseline_rate, 2),
                    "disparity_ratio": round(rate_val / max(0.001, baseline_rate), 2),
                    "difference_unit": "percentage_points"
                },
                source_columns=[dim_col, r_col],
                polarity=polarity,
                semantic_confidence=col_prof.confidence if col_prof else 0.85,
                calculation_method="subgroup_rate_spread_and_disparity_ratio",
                evidence_metadata={
                    "subgroup": subgroup_name,
                    "subgroup_count": n_sub,
                    "total_records": len(clean_df)
                },
                statement=statement,
                reliability_status=status,
                reliability_reason=reason
            )
            facts.append(fact)
            cur_idx += 1

        return facts[:max_facts]

    # -------------------------------------------------------------------------
    # 6. CATEGORICAL_CROSS_TAB
    # -------------------------------------------------------------------------

    @classmethod
    def _evaluate_categorical_cross_tab(
        cls,
        df: pd.DataFrame,
        profile: SemanticDatasetProfile,
        opp: AnalysisOpportunity,
        start_idx: int,
        max_facts: int
    ) -> list[CandidateFact]:
        c1 = opp.primary_column
        c2 = opp.secondary_column
        if not c2 or c1 not in df.columns or c2 not in df.columns:
            return []

        clean_df = df[[c1, c2]].dropna()
        n = len(clean_df)
        if n < 4:
            return [
                CandidateFact(
                    fact_id=f"FACT-{start_idx:03d}",
                    fact_type=OpportunityType.CATEGORICAL_CROSS_TAB.value,
                    metric=f"{c1}_x_{c2}",
                    dimensions={"dimension_1": c1, "dimension_2": c2},
                    sample_size=n,
                    source_columns=[c1, c2],
                    polarity=MetricPolarity.NEUTRAL,
                    calculation_method="contingency_table_chi_squared_and_cramers_v",
                    reliability_status=ReliabilityStatus.UNRELIABLE,
                    reliability_reason=f"Insufficient records for cross-tabulation (n={n} < 4)",
                    statement=f"Cross-tabulation of {c1} and {c2} rejected: fewer than 4 valid observations."
                )
            ]

        # Contingency table
        ct = pd.crosstab(clean_df[c1], clean_df[c2])
        r, c = ct.shape
        if r < 2 or c < 2:
            return [
                CandidateFact(
                    fact_id=f"FACT-{start_idx:03d}",
                    fact_type=OpportunityType.CATEGORICAL_CROSS_TAB.value,
                    metric=f"{c1}_x_{c2}",
                    dimensions={"dimension_1": c1, "dimension_2": c2},
                    sample_size=n,
                    source_columns=[c1, c2],
                    polarity=MetricPolarity.NEUTRAL,
                    calculation_method="contingency_table_chi_squared_and_cramers_v",
                    reliability_status=ReliabilityStatus.UNRELIABLE,
                    reliability_reason="One or both dimensions have fewer than 2 distinct categories",
                    statement=f"Cross-tabulation of {c1} and {c2} rejected: non-viable contingency matrix ({r}x{c})."
                )
            ]

        # Calculate Chi-squared and expected cell frequencies
        row_totals = ct.sum(axis=1).values
        col_totals = ct.sum(axis=0).values
        expected = np.outer(row_totals, col_totals) / float(n)
        chi2 = float(np.sum(((ct.values - expected) ** 2) / expected))
        df_deg = (r - 1) * (c - 1)

        # Cramer's V
        min_dim = min(r - 1, c - 1)
        cramers_v = math.sqrt(chi2 / (n * min_dim)) if min_dim > 0 and n > 0 else 0.0

        # Sparse table check (Cochran: > 20% expected frequencies < 5)
        sparse_cells_pct = float(np.mean(expected < 5.0) * 100.0)
        is_sparse = sparse_cells_pct > 20.0 and n < 50
        status = ReliabilityStatus.UNRELIABLE if is_sparse else ReliabilityStatus.RELIABLE
        reason = f"Sparse contingency table ({sparse_cells_pct:.0f}% of expected cell counts < 5 in small sample n={n})" if is_sparse else None

        # Find highest co-occurrence cell
        stacked = ct.stack().reset_index()
        stacked.columns = ["d1", "d2", "observed"]
        top_cell = stacked.sort_values("observed", ascending=False).iloc[0]
        top_d1 = str(top_cell["d1"])
        top_d2 = str(top_cell["d2"])
        top_count = int(top_cell["observed"])
        top_share_pct = round((top_count / n) * 100, 1)

        statement = (
            f"Contingency cross-tabulation between {c1} and {c2} shows co-occurrence "
            f"(Chi² = {chi2:.2f}, df = {df_deg}, Cramer's V = {cramers_v:.2f}; n = {n}), "
            f"with highest joint volume in '{top_d1}' within '{top_d2}' ({top_count} of {n} observations, {top_share_pct:.1f}%)."
        )

        fact = CandidateFact(
            fact_id=f"FACT-{start_idx:03d}",
            fact_type=OpportunityType.CATEGORICAL_CROSS_TAB.value,
            metric=f"{c1}_x_{c2}",
            dimensions={c1: top_d1, c2: top_d2},
            value=top_share_pct,
            baseline_value=round((100.0 / (r * c)), 1),
            absolute_difference=round(top_share_pct - (100.0 / (r * c)), 1),
            relative_difference=None,
            sample_size=n,
            statistical_info={
                "chi_squared": round(chi2, 2),
                "degrees_of_freedom": df_deg,
                "cramers_v": round(cramers_v, 3),
                "sparse_expected_pct": round(sparse_cells_pct, 1),
                "highest_cell_count": top_count
            },
            source_columns=[c1, c2],
            polarity=MetricPolarity.NEUTRAL,
            semantic_confidence=0.85,
            calculation_method="contingency_table_chi_squared_and_cramers_v",
            evidence_metadata={
                "top_pair": [top_d1, top_d2],
                "matrix_shape": [r, c]
            },
            statement=statement,
            reliability_status=status,
            reliability_reason=reason
        )
        return [fact]

    # -------------------------------------------------------------------------
    # 7. TARGET_ASSOCIATION
    # -------------------------------------------------------------------------

    @classmethod
    def _evaluate_target_association(
        cls,
        df: pd.DataFrame,
        profile: SemanticDatasetProfile,
        opp: AnalysisOpportunity,
        start_idx: int,
        max_facts: int
    ) -> list[CandidateFact]:
        tgt_col = opp.primary_column
        sec_col = opp.secondary_column
        if not sec_col or tgt_col not in df.columns or sec_col not in df.columns:
            return []

        tgt_prof = profile.columns.get(tgt_col)
        sec_prof = profile.columns.get(sec_col)

        # Parse target as boolean / binary 0-1
        tgt_str = df[tgt_col].astype(str).str.lower().str.strip()
        pos_tokens = {'1', 'true', 'yes', 't', 'y'}
        tgt_bool = tgt_str.isin(pos_tokens)

        # Check extreme target imbalance
        pos_count = int(tgt_bool.sum())
        neg_count = int((~tgt_bool).sum())
        total_valid = pos_count + neg_count

        if pos_count < 2 or neg_count < 2:
            return [
                CandidateFact(
                    fact_id=f"FACT-{start_idx:03d}",
                    fact_type=OpportunityType.TARGET_ASSOCIATION.value,
                    metric=tgt_col,
                    dimensions={"predictor": sec_col},
                    sample_size=total_valid,
                    source_columns=[tgt_col, sec_col],
                    polarity=tgt_prof.metric_polarity if tgt_prof else MetricPolarity.UNKNOWN,
                    calculation_method="target_cohort_comparison",
                    reliability_status=ReliabilityStatus.UNRELIABLE,
                    reliability_reason=f"Severe target imbalance (positive n={pos_count}, negative n={neg_count}; need >= 2 each)",
                    statement=f"Target association between {tgt_col} and {sec_col} rejected: severe class imbalance."
                )
            ]

        # Case A: Secondary column is NUMERIC_MEASURE, CURRENCY_MONETARY, or PERCENTAGE_RATE
        if sec_prof and sec_prof.semantic_role in (
            SemanticRole.NUMERIC_MEASURE,
            SemanticRole.CURRENCY_MONETARY,
            SemanticRole.PERCENTAGE_RATE,
            SemanticRole.ORDINAL
        ):
            num_series = cls._coerce_numeric(df[sec_col])
            valid_df = pd.DataFrame({"tgt": tgt_bool, "val": num_series}).dropna()

            pos_vals = valid_df[valid_df["tgt"]]["val"].values.astype(float)
            neg_vals = valid_df[~valid_df["tgt"]]["val"].values.astype(float)

            n1, n0 = len(pos_vals), len(neg_vals)
            if n1 < 2 or n0 < 2:
                return [
                    CandidateFact(
                        fact_id=f"FACT-{start_idx:03d}",
                        fact_type=OpportunityType.TARGET_ASSOCIATION.value,
                        metric=sec_col,
                        dimensions={"target_flag": tgt_col},
                        sample_size=len(valid_df),
                        source_columns=[tgt_col, sec_col],
                        polarity=sec_prof.metric_polarity,
                        calculation_method="two_sample_t_and_cohens_d",
                        reliability_status=ReliabilityStatus.UNRELIABLE,
                        reliability_reason=f"Insufficient target cohort sample (n_true={n1}, n_false={n0})",
                        statement=f"Target association between {tgt_col} and {sec_col} rejected: cohort sizes too small."
                    )
                ]

            m1, m0 = float(np.mean(pos_vals)), float(np.mean(neg_vals))
            s1, s0 = float(np.std(pos_vals, ddof=1)) if n1 > 1 else 0.0, float(np.std(neg_vals, ddof=1)) if n0 > 1 else 0.0

            abs_diff = round(m1 - m0, 2)
            rel_diff = round((abs_diff / abs(m0) * 100), 1) if m0 != 0 else None

            # Two-sample t-statistic and pooled standard deviation
            pooled_denom = ((n1 - 1) * (s1 ** 2) + (n0 - 1) * (s0 ** 2)) / max(1, (n1 + n0 - 2))
            s_pooled = math.sqrt(pooled_denom) if pooled_denom > 0 else 1.0
            cohens_d = (m1 - m0) / s_pooled if s_pooled > 0 else 0.0

            se_diff = math.sqrt((s1 ** 2 / n1) + (s0 ** 2 / n0))
            t_stat = (m1 - m0) / se_diff if se_diff > 0 else 0.0
            p_val = cls._p_value_from_z(t_stat)

            unit = sec_prof.unit or ""
            is_rate = sec_prof.semantic_role == SemanticRole.PERCENTAGE_RATE
            diff_str = cls._format_diff_str(abs_diff, unit, is_rate)
            m1_str = cls._format_value_str(m1, unit)
            m0_str = cls._format_value_str(m0, unit)

            statement = (
                f"For {tgt_col}=True, mean {sec_col} is {m1_str} vs {m0_str} for {tgt_col}=False "
                f"(difference = {diff_str}; t = {t_stat:+.2f}, p = {p_val:.3f}, Cohen's d = {cohens_d:+.2f}; "
                f"n = {n1 + n0}, n_true = {n1}, n_false = {n0})."
            )

            fact = CandidateFact(
                fact_id=f"FACT-{start_idx:03d}",
                fact_type=OpportunityType.TARGET_ASSOCIATION.value,
                metric=sec_col,
                dimensions={"target": tgt_col, "target_condition": "True_vs_False"},
                value=round(m1, 2),
                baseline_value=round(m0, 2),
                absolute_difference=abs_diff,
                relative_difference=rel_diff,
                sample_size=n1 + n0,
                statistical_info={
                    "t_statistic": round(t_stat, 2),
                    "p_value": round(p_val, 3),
                    "cohens_d": round(cohens_d, 2),
                    "n_target_true": n1,
                    "n_target_false": n0,
                    "target_true_mean": round(m1, 2),
                    "target_false_mean": round(m0, 2)
                },
                source_columns=[tgt_col, sec_col],
                polarity=sec_prof.metric_polarity,
                semantic_confidence=min(tgt_prof.confidence if tgt_prof else 0.8, sec_prof.confidence if sec_prof else 0.8),
                calculation_method="two_sample_t_and_cohens_d",
                evidence_metadata={
                    "target_column": tgt_col,
                    "feature_column": sec_col,
                    "target_distribution": {"true": n1, "false": n0}
                },
                statement=statement,
                reliability_status=ReliabilityStatus.RELIABLE
            )
            return [fact]

        # Case B: Secondary column is CATEGORICAL_DIMENSION
        elif sec_prof and sec_prof.semantic_role in (SemanticRole.CATEGORICAL_DIMENSION, SemanticRole.GEOGRAPHIC):
            valid_df = pd.DataFrame({"tgt": tgt_bool, "dim": df[sec_col].dropna().astype(str)}).dropna()
            overall_rate = float(valid_df["tgt"].mean() * 100.0)

            grouped = valid_df.groupby("dim")["tgt"].agg(["count", "mean"]).reset_index()
            grouped["mean_pct"] = grouped["mean"] * 100.0
            grouped = grouped.sort_values("mean_pct", ascending=False).reset_index(drop=True)

            top_row = grouped.iloc[0]
            top_cat = str(top_row["dim"])
            top_rate = float(top_row["mean_pct"])
            top_count = int(top_row["count"])

            diff_pp = round(top_rate - overall_rate, 2)
            rel_diff = round((diff_pp / overall_rate * 100), 1) if overall_rate > 0 else None

            is_unreliable = top_count < 3
            status = ReliabilityStatus.UNRELIABLE if is_unreliable else ReliabilityStatus.RELIABLE
            reason = f"Small subgroup sample size (n={top_count} < 3)" if is_unreliable else None

            statement = (
                f"Target rate for {tgt_col} in subgroup '{top_cat}' of {sec_col} is {top_rate:.1f}% "
                f"vs overall baseline {overall_rate:.1f}% (difference = {diff_pp:+0.1f} percentage points; "
                f"n_subgroup = {top_count}, n_total = {len(valid_df)})."
            )

            fact = CandidateFact(
                fact_id=f"FACT-{start_idx:03d}",
                fact_type=OpportunityType.TARGET_ASSOCIATION.value,
                metric=tgt_col,
                dimensions={sec_col: top_cat},
                value=round(top_rate, 1),
                baseline_value=round(overall_rate, 1),
                absolute_difference=diff_pp,
                relative_difference=rel_diff,
                sample_size=top_count,
                statistical_info={
                    "overall_target_rate_pct": round(overall_rate, 1),
                    "subgroup_target_rate_pct": round(top_rate, 1),
                    "total_sample": len(valid_df)
                },
                source_columns=[tgt_col, sec_col],
                polarity=tgt_prof.metric_polarity if tgt_prof else MetricPolarity.UNKNOWN,
                semantic_confidence=0.85,
                calculation_method="target_subgroup_proportional_risk",
                evidence_metadata={
                    "target_column": tgt_col,
                    "dimension_column": sec_col,
                    "category": top_cat
                },
                statement=statement,
                reliability_status=status,
                reliability_reason=reason
            )
            return [fact]

        return []
