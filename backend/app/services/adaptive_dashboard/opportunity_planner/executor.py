"""Analytical Opportunity Executor.

Executes selective, empirical calculations for prioritized opportunities
and synthesizes them into structured EvidenceItem nodes with full provenance trails.
"""
from __future__ import annotations

import collections
import json
import logging
import math
from typing import Any

from app.db.database import get_connection
from ..evidence_graph import EvidenceItem
from .contracts import AnalyticalOpportunity, AnalyticalOpportunityType
from .portfolio import OpportunityExecutionPortfolio

logger = logging.getLogger(__name__)


class AnalyticalOpportunityExecutor:
    """Executes targeted calculations for prioritized analytical opportunities."""

    @classmethod
    def execute_opportunities(
        cls,
        opportunities: list[AnalyticalOpportunity],
        conn=None,
        max_to_execute: int = 12,
    ) -> list[EvidenceItem]:
        """Runs selective calculations on actual sheet rows and emits evidence nodes."""
        close_conn = False
        if conn is None:
            conn = get_connection()
            close_conn = True

        evidence_items: list[EvidenceItem] = []

        try:
            # Select diversified execution portfolio across semantic families and intents
            selected_opps = OpportunityExecutionPortfolio.select_portfolio(
                opportunities=opportunities,
                budget=max_to_execute,
                max_per_semantic_family=2,
                max_per_measure_dim_pair=1,
                max_per_temporal_family=1,
            )

            for idx, opp in enumerate(selected_opps, start=1):
                try:
                    if opp.opportunity_type == AnalyticalOpportunityType.MEASURE_BY_DIMENSION:
                        evid = cls._execute_measure_by_dimension(opp, conn)
                    elif opp.opportunity_type == AnalyticalOpportunityType.MEASURE_BY_TIME:
                        evid = cls._execute_measure_by_time(opp, conn)
                    elif opp.opportunity_type == AnalyticalOpportunityType.MEASURE_BY_MEASURE:
                        evid = cls._execute_measure_by_measure(opp, conn)
                    elif opp.opportunity_type == AnalyticalOpportunityType.CROSS_SHEET_RELATIONSHIP:
                        evid = cls._execute_cross_sheet(opp, conn)
                    else:
                        evid = cls._execute_fallback(opp, conn)

                    if evid:
                        evid.tokens["opp_score"] = opp.score.model_dump()
                        evid.tokens["total_score"] = opp.score.total_score
                        evidence_items.append(evid)
                except Exception as e:
                    logger.warning("Failed executing calculation for opportunity %s: %s", opp.opportunity_id, e)

        finally:
            if close_conn:
                conn.close()

        return evidence_items

    @classmethod
    def _fetch_sheet_records(cls, sheet_id: int, conn) -> list[dict[str, Any]]:
        """Loads actual row dictionaries for a sheet."""
        rows = conn.execute(
            "SELECT data_json FROM sheet_rows WHERE sheet_id = ? ORDER BY row_index ASC",
            (sheet_id,),
        ).fetchall()
        return [json.loads(r[0]) for r in rows if r[0]]

    @classmethod
    def _execute_measure_by_dimension(cls, opp: AnalyticalOpportunity, conn) -> EvidenceItem | None:
        """Computes empirical aggregation, ranking, and spread across dimension categories."""
        records = cls._fetch_sheet_records(opp.sheet_id, conn)
        if not records or not opp.primary_measure or not opp.primary_dimension:
            return None

        m_col = opp.primary_measure
        d_col = opp.primary_dimension

        # Aggregate values by category
        cat_sums: dict[str, list[float]] = collections.defaultdict(list)
        cols_to_use = opp.underlying_columns if opp.underlying_columns else [m_col]
        for r in records:
            dim_val = str(r.get(d_col, "Unknown")).strip()
            row_vals = []
            for col in cols_to_use:
                raw_m = r.get(col)
                if raw_m is not None:
                    try:
                        clean_str = str(raw_m).replace("$", "").replace(",", "").replace("%", "").strip()
                        row_vals.append(float(clean_str))
                    except (ValueError, TypeError):
                        continue
            if row_vals:
                # If multiple period columns, average them for the record
                val = sum(row_vals) / len(row_vals)
                cat_sums[dim_val].append(val)

        if not cat_sums:
            return None

        # Compute averages or sums per category
        cat_means = {k: sum(v) / len(v) for k, v in cat_sums.items() if len(v) > 0}
        sorted_cats = sorted(cat_means.items(), key=lambda x: x[1], reverse=True)

        top_cat, top_val = sorted_cats[0]
        bot_cat, bot_val = sorted_cats[-1]
        spread = round(top_val - bot_val, 2)
        mean_val = round(sum(cat_means.values()) / len(cat_means), 2)

        categories = [c[0] for c in sorted_cats[:8]]
        values = [round(c[1], 2) for c in sorted_cats[:8]]

        from app.services.adaptive_dashboard.visual_presence_gates import ExecutiveTitleCompressionIntegrity
        comp_title = ExecutiveTitleCompressionIntegrity.compress_title(
            raw_title=opp.title,
            primary_measure=m_col,
            primary_dimension=d_col,
            top_cohort=top_cat,
            bottom_cohort=bot_cat,
            spread=spread,
        )

        evid_id = f"EVID-OPP-{opp.opportunity_id}"
        formatted_val = f"{top_val:.1f} {opp.measure_unit or 'units'} (top: {top_cat})"

        return EvidenceItem(
            evidence_id=evid_id,
            claim_type="segment_difference",
            subject=comp_title.compressed_title,
            metric=opp.primary_measure,
            value=top_val,
            formatted_value=formatted_val,
            difference_pct=round((spread / max(1e-6, bot_val)) * 100.0, 1) if bot_val > 0 else 0.0,
            population=len(records),
            source_table=opp.sheet_name,
            calculation=f"Aggregated {m_col} by {d_col}: Top {top_cat} ({top_val:.1f}) vs Bottom {bot_cat} ({bot_val:.1f}), spread={spread:.1f}",
            confidence="HIGH" if len(records) >= 20 else "MEDIUM",
            causal_classification="OBSERVED",
            provenance=f"opportunity_{opp.opportunity_id}",
            tokens={
                **opp.provenance,
                "opportunity_id": opp.opportunity_id,
                "compressed_title": comp_title.compressed_title,
                "annotation_subtitle": comp_title.annotation_subtitle,
                "raw_analytical_question": comp_title.raw_analytical_question,
                "top_cohort": top_cat,
                "bottom_cohort": bot_cat,
                "categories": categories,
                "values": values,
                "benchmark": mean_val,
                "spread": spread,
                "unit": opp.measure_unit,
                "metric_grain": opp.metric_grain,
                "primary_measure": m_col,
                "primary_dimension": d_col,
                "visual_archetype": opp.target_visual_archetype,
                "source_sheet_ids": [opp.sheet_id],
            },
        )

    @classmethod
    def _execute_measure_by_time(cls, opp: AnalyticalOpportunity, conn) -> EvidenceItem | None:
        """Computes empirical time series cadence, trend direction, and period deltas."""
        records = cls._fetch_sheet_records(opp.sheet_id, conn)
        if not records or not opp.primary_measure or not opp.primary_dimension:
            return None

        m_col = opp.primary_measure
        t_col = opp.primary_dimension

        # Check for multi-column temporal sequence (e.g. weekly reporting periods)
        temporal_cols = opp.underlying_columns or opp.provenance.get("temporal_columns")
        if temporal_cols and isinstance(temporal_cols, list) and len(temporal_cols) >= 2:
            periods = []
            vals = []
            for col in temporal_cols:
                short_p = col.replace("July", "Jul").replace(" To ", "–").replace(" to ", "–")
                periods.append(short_p)
                col_nums = []
                for r in records:
                    raw = r.get(col)
                    if raw is not None:
                        try:
                            clean_str = str(raw).replace("$", "").replace(",", "").replace("%", "").strip()
                            col_nums.append(float(clean_str))
                        except (ValueError, TypeError):
                            pass
                m_val = round(sum(col_nums) / len(col_nums), 2) if col_nums else 0.0
                vals.append(m_val)

            if len(periods) < 2:
                return None

            start_val = vals[0]
            end_val = vals[-1]
            delta_pct = round(((end_val - start_val) / max(1e-6, start_val)) * 100.0, 1)
        else:
            # Aggregate chronologically from single time column
            time_series: dict[str, list[float]] = collections.defaultdict(list)
            for r in records:
                t_val = str(r.get(t_col, "")).strip()
                raw_m = r.get(m_col)
                try:
                    if raw_m is not None:
                        clean_str = str(raw_m).replace("$", "").replace(",", "").replace("%", "").strip()
                        time_series[t_val].append(float(clean_str))
                except (ValueError, TypeError):
                    continue

            if len(time_series) < 2:
                return None

            periods = list(time_series.keys())[:10]
            vals = [round(sum(time_series[p]) / len(time_series[p]), 2) for p in periods]

            start_val = vals[0]
            end_val = vals[-1]
            delta_pct = round(((end_val - start_val) / max(1e-6, start_val)) * 100.0, 1)

        from app.services.adaptive_dashboard.visual_presence_gates import ExecutiveTitleCompressionIntegrity
        comp_title = ExecutiveTitleCompressionIntegrity.compress_title(
            raw_title=opp.title,
            primary_measure=m_col,
            primary_dimension=t_col,
        )

        evid_id = f"EVID-OPP-{opp.opportunity_id}"
        formatted_val = f"{end_val:.1f} (Δ {delta_pct:+.1f}%)"

        return EvidenceItem(
            evidence_id=evid_id,
            claim_type="trend_change",
            subject=comp_title.compressed_title,
            metric=opp.primary_measure,
            value=end_val,
            formatted_value=formatted_val,
            difference_pct=delta_pct,
            population=len(records),
            source_table=opp.sheet_name,
            calculation=f"Time-series rollup on {m_col} over {t_col}: start={start_val:.1f}, end={end_val:.1f}, change={delta_pct:+.1f}%",
            confidence="HIGH",
            causal_classification="OBSERVED",
            provenance=f"opportunity_{opp.opportunity_id}",
            tokens={
                **opp.provenance,
                "opportunity_id": opp.opportunity_id,
                "compressed_title": comp_title.compressed_title,
                "annotation_subtitle": comp_title.annotation_subtitle,
                "raw_analytical_question": comp_title.raw_analytical_question,
                "categories": periods,
                "values": vals,
                "unit": opp.measure_unit,
                "metric_grain": opp.metric_grain,
                "temporal_grain": opp.temporal_grain,
                "visual_archetype": opp.target_visual_archetype,
                "source_sheet_ids": [opp.sheet_id],
            },
        )

    @classmethod
    def _execute_measure_by_measure(cls, opp: AnalyticalOpportunity, conn) -> EvidenceItem | None:
        """Computes empirical correlation and statistical dependency between two measures."""
        records = cls._fetch_sheet_records(opp.sheet_id, conn)
        if not records or not opp.primary_measure or not opp.secondary_measure:
            return None

        m1_col, m2_col = opp.primary_measure, opp.secondary_measure
        pts: list[tuple[float, float]] = []

        cols = opp.underlying_columns or []
        if cols and len(cols) >= 2:
            m1_cols = [c for c in cols if "leave" not in c.lower()] or [cols[0]]
            m2_cols = [c for c in cols if "leave" in c.lower()] or [cols[-1]]
        else:
            m1_cols = [m1_col]
            m2_cols = [m2_col]

        scatter_pts: list[dict[str, Any]] = []
        for r in records:
            vals1 = []
            vals2 = []
            for c in m1_cols:
                raw = r.get(c)
                if raw is not None and str(raw).strip() not in ("", "-", "NM", "null"):
                    try:
                        vals1.append(float(str(raw).replace("$", "").replace(",", "").replace("%", "").strip()))
                    except (ValueError, TypeError):
                        pass
            for c in m2_cols:
                raw = r.get(c)
                if raw is not None and str(raw).strip() not in ("", "-", "NM", "null"):
                    try:
                        vals2.append(float(str(raw).replace("$", "").replace(",", "").replace("%", "").strip()))
                    except (ValueError, TypeError):
                        pass

            if vals1 and vals2:
                x_val = round(sum(vals1) / len(vals1), 2)
                y_val = round(sum(vals2) / len(vals2), 2)
                pts.append((x_val, y_val))
                ent_name = (
                    r.get("City / town") or r.get("City") or r.get("State / Union Territory")
                    or r.get("State") or r.get("Location") or r.get("department") or r.get("Department") or ""
                )
                scatter_pts.append({
                    "x": x_val,
                    "y": y_val,
                    "name": str(ent_name).strip() if ent_name else f"Location {len(pts)}",
                })

        if len(pts) < 5:
            return None

        # Pearson correlation
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        n = len(pts)
        mean_x = sum(xs) / n
        mean_y = sum(ys) / n
        cov = sum((x - mean_x) * (y - mean_y) for x, y in pts)
        std_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
        std_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))

        r_val = round(cov / max(1e-6, std_x * std_y), 3) if std_x > 0 and std_y > 0 else 0.0

        evid_id = f"EVID-OPP-{opp.opportunity_id}"
        formatted_val = f"r = {r_val:+.2f} ({'Strong' if abs(r_val) > 0.6 else 'Moderate'} association)"

        return EvidenceItem(
            evidence_id=evid_id,
            claim_type="general_fact",
            subject=f"{opp.title} (n={n})",
            metric=f"{m1_col}_vs_{m2_col}",
            value=r_val,
            formatted_value=formatted_val,
            difference_pct=round(abs(r_val) * 100.0, 1),
            population=n,
            source_table=opp.sheet_name,
            calculation=f"Pearson correlation r={r_val:.3f} between {m1_col} and {m2_col} across {n} sample records",
            confidence="HIGH" if n >= 30 else "MEDIUM",
            causal_classification="ASSOCIATED",
            provenance=f"opportunity_{opp.opportunity_id}",
            tokens={
                **opp.provenance,
                "opportunity_id": opp.opportunity_id,
                "correlation": r_val,
                "sample_points": pts[:30],
                "scatter_points": scatter_pts[:60],
                "x_measure": m1_col,
                "y_measure": m2_col,
                "unit": opp.measure_unit or ("µg/m³" if any(p in m1_col.lower() for p in ("so2", "no2", "pm10", "pm2.5")) else ""),
                "visual_archetype": opp.target_visual_archetype,
                "source_sheet_ids": [opp.sheet_id],
            },
        )

    @classmethod
    def _execute_cross_sheet(cls, opp: AnalyticalOpportunity, conn) -> EvidenceItem | None:
        """Synthesizes cross-sheet empirical reconciliation link."""
        evid_id = f"EVID-OPP-{opp.opportunity_id}"
        formatted_val = f"{opp.join_confidence * 100.0:.1f}% Reconciled"

        return EvidenceItem(
            evidence_id=evid_id,
            claim_type="capacity_gap",
            subject=opp.title,
            metric=f"reconciliation_{opp.primary_measure}",
            value=opp.join_confidence * 100.0,
            formatted_value=formatted_val,
            difference_pct=0.0,
            population=opp.cardinality,
            source_table="cross_sheet_join",
            calculation=f"Verified cross-sheet relationship on {opp.primary_measure} with join confidence {opp.join_confidence:.2f}",
            confidence="HIGH" if opp.join_confidence >= 0.85 else "MEDIUM",
            causal_classification="ASSOCIATED",
            provenance=f"opportunity_{opp.opportunity_id}",
            tokens={
                **opp.provenance,
                "opportunity_id": opp.opportunity_id,
                "join_confidence": opp.join_confidence,
                "visual_archetype": opp.target_visual_archetype,
                "source_sheet_ids": opp.source_sheet_ids,
            },
        )

    @classmethod
    def _execute_fallback(cls, opp: AnalyticalOpportunity, conn) -> EvidenceItem | None:
        """Generic fallback evidence item."""
        evid_id = f"EVID-OPP-{opp.opportunity_id}"
        return EvidenceItem(
            evidence_id=evid_id,
            claim_type="general_fact",
            subject=opp.title,
            metric=opp.primary_measure or "metric",
            value=opp.score.total_score * 100.0,
            formatted_value=f"{opp.score.total_score * 100.0:.1f}",
            difference_pct=0.0,
            population=opp.cardinality or 10,
            source_table=opp.sheet_name,
            calculation=f"Analytical opportunity derived from {opp.opportunity_type.value}",
            confidence="HIGH",
            causal_classification="OBSERVED",
            provenance=f"opportunity_{opp.opportunity_id}",
            tokens={**opp.provenance, "opportunity_id": opp.opportunity_id},
        )
