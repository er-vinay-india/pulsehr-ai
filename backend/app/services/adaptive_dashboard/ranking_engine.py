"""Generic Entity Ranking Intelligence Engine.

Provides domain-independent Top/Bottom entity ranking discovery,
intent extraction, semantic desirability direction, server-side group-by aggregation,
percentile calculation, benchmark alignment, and progressive view scaling (5 -> 15 -> 25 -> 50 -> 100 -> 500 -> Full).
"""
from __future__ import annotations

import collections
import hashlib
import json
import logging
import math
import re
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from app.db.database import get_connection

logger = logging.getLogger(__name__)


class RankingDirection(str, Enum):
    """Semantic desirability direction for ranking."""
    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"  # Top = highest value (e.g. Sales, Attendance Rate, Revenue, Exam Score)
    LOWER_IS_BETTER = "LOWER_IS_BETTER"    # Top = lowest value (e.g. Defect Rate, Absence Rate, Failure Rate, Downtime, Delay)
    NEUTRAL = "NEUTRAL"                    # Highest / Lowest fallback when desirability cannot be determined


class EntityRankingIntent(BaseModel):
    """Metadata governing an entity ranking configuration."""
    model_config = ConfigDict(extra="ignore")

    entity_column: str
    entity_type: str                      # e.g. "Department", "Store", "Product", "Employee", "Student", "Category"
    display_name: str
    sheet_id: int
    sheet_name: str

    measure: str
    measure_label: str
    aggregation: str = "avg"              # "sum", "avg", "mean", "count"
    unit: str = ""
    grain: str = ""

    ranking_direction: RankingDirection = RankingDirection.HIGHER_IS_BETTER
    confidence: float = 0.90
    polarity_reason: str = ""
    benchmark: float | None = None
    target: float | None = None


class RankedEntityRow(BaseModel):
    """Single ranked entity item with value, rank, and percentile."""
    model_config = ConfigDict(extra="ignore")

    rank: int
    entity: str
    value: float
    formatted_value: str
    population_count: int
    percentile: float                     # e.g. 98.5%
    percentile_label: str                 # e.g. "Top 2%" or "Bottom 5%"
    delta_benchmark: float | None = None  # value - benchmark
    is_above_benchmark: bool | None = None


class EntityRankingStory(BaseModel):
    """Analytical story contract for entity ranking."""
    model_config = ConfigDict(extra="ignore")

    story_id: str
    entity_type: str
    entity_column: str
    display_name: str
    sheet_id: int

    measure: str
    measure_label: str
    aggregation: str
    unit: str
    ranking_direction: RankingDirection

    population_count: int
    default_limit: int = 5
    supported_limits: list[int] = Field(default_factory=lambda: [5, 15, 25, 50, 100, 500])

    mode: Literal["TOP", "BOTTOM", "BOTH"] = "TOP"
    active_limit: int | str = 5           # 5, 15, 25, 50, 100, 500, or "FULL"

    ranked_rows: list[RankedEntityRow] = Field(default_factory=list)
    bottom_rows: list[RankedEntityRow] = Field(default_factory=list)  # for BOTH mode

    benchmark: float | None = None
    target: float | None = None
    distribution_summary: dict[str, Any] = Field(default_factory=dict)

    available_entities: list[dict[str, Any]] = Field(default_factory=list)
    available_measures: list[dict[str, Any]] = Field(default_factory=list)

    evidence_ids: list[str] = Field(default_factory=list)
    inspect_payload: dict[str, Any] = Field(default_factory=dict)


# Common Desirability Lexicon
HIGHER_IS_BETTER_KEYWORDS = {
    "attendance", "sales", "revenue", "profit", "margin", "income", "score", "yield",
    "retention", "completion", "satisfaction", "uptime", "conversion", "accuracy",
    "achievement", "gpa", "rating", "units_sold", "volume", "attendance_rate", "final attendance",
    "weekly_sales", "exam", "grade", "enps",
}

LOWER_IS_BETTER_KEYWORDS = {
    "defect", "scrap", "churn", "attrition", "turnover", "loss", "cost", "expense",
    "latency", "downtime", "incident", "error", "delay", "absenteeism", "bounce",
    "leave", "leaves", "failure", "fail", "penalty", "complaint", "return", "returns",
    "return_rate", "cancellation", "rejection", "unemployment", "deviation", "variance",
    "so2", "no2", "pm10", "pm2.5", "pm2_5", "pollution", "pollutant", "aqi", "emission", "contaminant",
}

NON_ENTITY_TOKENS = {
    "id", "uuid", "guid", "row", "index", "created_at", "updated_at", "timestamp",
    "date", "hash", "comment", "notes", "description", "text", "message", "url",
    "interact_", "ratio_", "mean_", "sum_",
}


class GenericEntityRankingEngine:
    """Core domain-independent ranking intelligence engine."""

    @classmethod
    def infer_desirability_direction(cls, measure_name: str, unit: str = "") -> tuple[RankingDirection, float, str]:
        """Infers HIGHER_IS_BETTER, LOWER_IS_BETTER, or NEUTRAL without workforce-specific assumptions."""
        clean = measure_name.strip().lower()
        tokens = set(re.split(r"[^a-zA-Z0-9]+", clean))

        # 1. Check for negative polarity keywords
        low_matches = tokens.intersection(LOWER_IS_BETTER_KEYWORDS)
        if low_matches:
            matched = list(low_matches)[0]
            return (
                RankingDirection.LOWER_IS_BETTER,
                0.90,
                f"Measure '{measure_name}' contains cost/friction/defect token '{matched}' (lower is better)",
            )

        # 2. Check for positive polarity keywords
        high_matches = tokens.intersection(HIGHER_IS_BETTER_KEYWORDS)
        if high_matches:
            matched = list(high_matches)[0]
            return (
                RankingDirection.HIGHER_IS_BETTER,
                0.90,
                f"Measure '{measure_name}' contains yield/productivity/revenue token '{matched}' (higher is better)",
            )

        # 3. Currency / Monetary fallback: default to HIGHER_IS_BETTER unless cost/expense
        if unit in ("$", "€", "£", "₹", "USD", "EUR") or any(t in tokens for t in ("price", "amount", "spend")):
            if any(t in tokens for t in ("cost", "expense", "fee", "penalty")):
                return RankingDirection.LOWER_IS_BETTER, 0.85, "Monetary expenditure measure (lower is better)"
            return RankingDirection.HIGHER_IS_BETTER, 0.80, "Monetary income/value measure (higher is better)"

        # 4. Conservative neutral fallback
        return (
            RankingDirection.NEUTRAL,
            0.50,
            f"Neutral polarity for '{measure_name}'; directional desirability not asserted",
        )

    @classmethod
    def discover_rankable_entities_and_measures(
        cls,
        dataset_id: int,
        conn=None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Discovers meaningful candidate entities and rankable measures from sheets."""
        close_conn = False
        if conn is None:
            conn = get_connection()
            close_conn = True

        entities: list[dict[str, Any]] = []
        measures: list[dict[str, Any]] = []

        try:
            s_rows = conn.execute(
                "SELECT id, name, display_name, columns_json, profile_json FROM sheets WHERE dataset_id = ? ORDER BY id ASC",
                (dataset_id,),
            ).fetchall()

            for s in s_rows:
                sid, sname, sdisp, cols_json, prof_json = s[0], s[1], s[2], s[3], s[4]
                cols = json.loads(cols_json) if cols_json else []
                profs = json.loads(prof_json) if prof_json else []
                prof_map = {p.get("column", ""): p for p in profs}

                for col in cols:
                    low_c = col.lower().strip()
                    prof = prof_map.get(col, {})
                    is_numeric = bool(prof.get("numeric")) or prof.get("physical_type", "").lower() in ("float", "int", "numeric", "real")
                    card = prof.get("distinct") or prof.get("cardinality", 0)
                    role = prof.get("semantic_role") or prof.get("probable_semantic_role") or ""

                    # Filter out synthetic interaction and internal columns
                    if any(low_c.startswith(prefix) for prefix in ("interact_", "col_")) or " + " in col:
                        continue

                    # Filter out row sequence ordinals, identifiers, and surrogate keys from both entity and measure candidates
                    is_seq_id = (
                        bool(re.match(r'^(sr|s|seq|row)[\._\s]?no\.?', low_c, re.I))
                        or low_c in ("sr_no", "s_no", "srno", "sno", "serial_no", "row_num", "row_no", "row_id", "record_id", "id", "key", "uuid", "hash")
                        or low_c.endswith(("_id", "_key", "_code", "_idx"))
                        or role == "IDENTIFIER"
                    )
                    if is_seq_id:
                        continue

                    # Entity / Dimension candidate: Must be non-numeric categorical/cohort, or low-cardinality discrete dimension
                    if not is_numeric:
                        if not any(low_c == t or low_c.endswith(f"_{t}") for t in ("date", "datetime", "timestamp", "quarter", "month", "year", "week")):
                            # Meaningful entity check
                            is_meaningful = True
                            if low_c in ("id", "key", "uuid", "hash", "sno", "srno"):
                                is_meaningful = False
                            if is_meaningful and card >= 2:
                                ent_type = cls._infer_entity_type_label(col)
                                is_indiv = any(t in low_c for t in ("employee", "student", "customer", "person", "full name", "staff", "user"))
                                entities.append({
                                    "sheet_id": sid,
                                    "sheet_name": sname,
                                    "column": col,
                                    "entity_type": ent_type,
                                    "display_name": col.replace("_", " ").title(),
                                    "cardinality": card,
                                    "is_individual": is_indiv,
                                })

                    # Rankable Measure candidate: Must be true continuous/discrete numeric metric
                    is_id_name = (
                        low_c in ("full name", "name", "id", "code", "key", "number", "num", "idx", "zip", "postal")
                        or low_c.endswith(("_id", "_key", "_code", "_idx"))
                    )
                    if is_numeric and not is_id_name:
                        unit = prof.get("unit") or prof.get("detected_unit") or ""
                        direction, conf, reason = cls.infer_desirability_direction(col, unit)
                        agg = "avg" if any(t in low_c for t in ("rate", "pct", "avg", "mean", "attendance", "cpi", "unemployment", "score", "grade", "price", "annual average", "average", "pm10", "pm2.5", "so2", "no2")) else "sum"
                        measures.append({
                            "sheet_id": sid,
                            "sheet_name": sname,
                            "column": col,
                            "measure_label": col.replace("_", " ").title(),
                            "aggregation": agg,
                            "unit": unit,
                            "ranking_direction": direction.value,
                            "confidence": conf,
                            "polarity_reason": reason,
                        })
        finally:
            if close_conn:
                conn.close()

        # Deduplicate entities by column name
        seen_ents = set()
        unique_entities = []
        for e in entities:
            if e["column"] not in seen_ents:
                seen_ents.add(e["column"])
                unique_entities.append(e)

        # Sort entities by executive priority:
        # Prioritize executive aggregate cohorts (City, State, Department, Store, Product, Category, Region) over individual-level drilldowns
        def entity_priority_key(ent: dict[str, Any]) -> tuple[int, int]:
            # Priority 0: Explicit group entities (City, State, Department, Store, Product, Region, Category)
            is_group = any(t in ent["entity_type"].lower() for t in ("city", "state", "department", "store", "product", "region", "category", "branch", "division"))
            return (1 if not is_group else 0, 1 if ent["is_individual"] else 0, -ent["cardinality"])

        unique_entities.sort(key=entity_priority_key)

        # Deduplicate measures by column name
        seen_meas = set()
        unique_measures = []
        for m in measures:
            if m["column"] not in seen_meas:
                seen_meas.add(m["column"])
                unique_measures.append(m)

        # Prioritize dominant business measures (PM10, PM2.5, Attendance, Sales, Revenue, Margin, Score)
        def measure_priority_key(meas: dict[str, Any]) -> int:
            col_l = meas["column"].lower()
            if any(k in col_l for k in ("pm10", "pm2.5", "pm2_5", "final attendance", "attendance rate", "weekly_sales", "sales", "revenue", "profit", "score", "gpa")):
                return 0
            if any(k in col_l for k in ("so2", "no2", "attendance", "leave", "margin", "volume", "units")):
                return 1
            return 2

        unique_measures.sort(key=measure_priority_key)

        return unique_entities, unique_measures

    @classmethod
    def _infer_entity_type_label(cls, col_name: str) -> str:
        clean = col_name.lower().replace("_", " ").strip()
        for token in ("department", "dept"):
            if token in clean:
                return "Department"
        for token in ("store", "shop", "branch", "location", "facility"):
            if token in clean:
                return "Store"
        for token in ("product", "item", "sku", "merchandise"):
            if token in clean:
                return "Product"
        for token in ("employee", "staff", "worker", "agent", "person", "full name"):
            if token in clean:
                return "Employee"
        for token in ("student", "pupil", "learner"):
            if token in clean:
                return "Student"
        for token in ("customer", "client", "buyer", "user", "account"):
            if token in clean:
                return "Customer"
        for token in ("supplier", "vendor", "provider", "partner"):
            if token in clean:
                return "Supplier"
        if any(t in clean for t in ("city", "town", "municipality")):
            return "City"
        if any(t in clean for t in ("state", "province", "union territory")):
            return "State"
        for token in ("region", "territory", "district", "country", "zone"):
            if token in clean:
                return "Region"
        for token in ("machine", "equipment", "asset", "device"):
            if token in clean:
                return "Machine"
        for token in ("course", "class", "module", "subject"):
            if token in clean:
                return "Course"
        return col_name.replace("_", " ").title()

    @classmethod
    def execute_ranking_query(
        cls,
        dataset_id: int,
        entity_column: str,
        measure_column: str,
        sheet_id: int | None = None,
        aggregation: str = "avg",
        direction: str = "TOP",              # TOP, BOTTOM, BOTH
        limit: int | str = 5,                # 5, 15, 25, 50, 100, 500, or "FULL"
        offset: int = 0,
        filter_context: dict[str, Any] | None = None,
        conn=None,
    ) -> dict[str, Any]:
        """Executes server-side SQL group-by aggregation with ranking and percentiles."""
        close_conn = False
        if conn is None:
            conn = get_connection()
            close_conn = True

        filter_context = filter_context or {}

        try:
            # 1. Resolve sheet if not provided
            if sheet_id is None:
                row = conn.execute(
                    "SELECT id FROM sheets WHERE dataset_id = ? AND columns_json LIKE ? LIMIT 1",
                    (dataset_id, f'%"{entity_column}"%'),
                ).fetchone()
                sheet_id = row[0] if row else None

            if sheet_id is None:
                return {
                    "entity_column": entity_column,
                    "measure_column": measure_column,
                    "population_count": 0,
                    "ranked_rows": [],
                    "bottom_rows": [],
                    "limit": limit,
                    "mode": direction,
                }

            # 2. Extract profile to determine unit & benchmark
            prof_row = conn.execute("SELECT profile_json FROM sheets WHERE id = ?", (sheet_id,)).fetchone()
            profs = json.loads(prof_row[0]) if prof_row and prof_row[0] else []
            m_prof = next((p for p in profs if p.get("column") == measure_column), {})
            unit = m_prof.get("unit") or m_prof.get("detected_unit") or ""

            # Determine semantic desirability direction
            desirability, conf, reason = cls.infer_desirability_direction(measure_column, unit)

            # Map TOP vs BOTTOM to numeric ordering based on semantic desirability:
            # If HIGHER_IS_BETTER: TOP = DESC, BOTTOM = ASC
            # If LOWER_IS_BETTER:  TOP = ASC (lowest numeric is best!), BOTTOM = DESC
            # If NEUTRAL:          TOP = DESC (Highest), BOTTOM = ASC (Lowest)
            is_lower_better = (desirability == RankingDirection.LOWER_IS_BETTER)

            # Build SQL Group By Aggregation
            agg_func = "AVG" if aggregation.lower() in ("avg", "mean") else "SUM"
            val_expr = f"{agg_func}(CAST(json_extract(data_json, '$.{entity_column}') AS TEXT))" if agg_func == "COUNT" else f"{agg_func}(CAST(json_extract(data_json, '$.{measure_column}') AS REAL))"

            # Base query across rows
            sql_base = f"""
                SELECT 
                    json_extract(data_json, '$.{entity_column}') AS entity_val,
                    {val_expr} AS metric_val,
                    COUNT(*) AS record_count
                FROM sheet_rows
                WHERE sheet_id = ?
                  AND json_extract(data_json, '$.{entity_column}') IS NOT NULL
                  AND json_extract(data_json, '$.{entity_column}') != ''
                  AND json_extract(data_json, '$.{measure_column}') IS NOT NULL
            """
            params: list[Any] = [sheet_id]

            # Apply active dashboard filters
            for f_col, f_val in filter_context.items():
                if f_val is not None:
                    sql_base += f" AND json_extract(data_json, '$.{f_col}') = ?"
                    params.append(str(f_val))

            sql_base += " GROUP BY 1"

            # Execute and retrieve full grouped population
            all_groups = conn.execute(sql_base, params).fetchall()
            population_count = len(all_groups)

            if population_count == 0:
                return {
                    "entity_column": entity_column,
                    "measure_column": measure_column,
                    "population_count": 0,
                    "ranked_rows": [],
                    "bottom_rows": [],
                    "limit": limit,
                    "mode": direction,
                    "ranking_direction": desirability.value,
                }

            # Parse and sort population in Python
            parsed_population = []
            for r in all_groups:
                ent_name = str(r[0]).strip()
                val = float(r[1]) if r[1] is not None and not (isinstance(r[1], float) and math.isnan(r[1])) else 0.0
                parsed_population.append({"entity": ent_name, "value": val, "records": r[2]})

            # Sort best to worst according to desirability
            # If higher is better: descending. If lower is better: ascending.
            reverse_sort = not is_lower_better
            sorted_population = sorted(parsed_population, key=lambda x: x["value"], reverse=reverse_sort)

            # Overall benchmark / average
            all_vals = [p["value"] for p in sorted_population]
            benchmark_val = round(sum(all_vals) / len(all_vals), 2) if all_vals else 0.0

            # Compute percentiles and row structures
            def make_ranked_rows(sub_list: list[dict[str, Any]], start_rank: int = 1) -> list[RankedEntityRow]:
                rows = []
                for idx, item in enumerate(sub_list):
                    rank_num = start_rank + idx
                    # Percentile: (population - rank + 1) / population * 100
                    p_tile = round(((population_count - rank_num + 1) / max(1, population_count)) * 100.0, 1)
                    p_tile = max(0.1, min(100.0, p_tile))

                    p_label = f"Top {round(100.0 - p_tile + (100.0 / population_count), 1)}%" if rank_num <= population_count / 2 else f"Bottom {round(p_tile, 1)}%"
                    if rank_num == 1:
                        p_label = "Rank 1"

                    v = round(item["value"], 2)
                    delta = round(v - benchmark_val, 2)
                    is_above = (v >= benchmark_val) if not is_lower_better else (v <= benchmark_val)

                    fmt_v = f"{v:,}" if unit != "$" else f"${v:,.2f}"
                    if unit and unit != "$":
                        fmt_v = f"{v:,.1f} {unit}"

                    rows.append(RankedEntityRow(
                        rank=rank_num,
                        entity=item["entity"],
                        value=v,
                        formatted_value=fmt_v,
                        population_count=population_count,
                        percentile=p_tile,
                        percentile_label=p_label,
                        delta_benchmark=delta,
                        is_above_benchmark=is_above,
                    ))
                return rows

            # Resolve limit
            is_full = (str(limit).upper() == "FULL" or limit is None or int(limit) >= population_count)
            n_limit = population_count if is_full else min(int(limit), population_count)

            ranked_rows: list[RankedEntityRow] = []
            bottom_rows: list[RankedEntityRow] = []

            mode_upper = direction.upper()

            if mode_upper == "TOP":
                ranked_rows = make_ranked_rows(sorted_population[:n_limit])
            elif mode_upper == "BOTTOM":
                # Worst according to desirability (the tail of sorted_population)
                # To display bottom ranks intuitively: Rank N down to Rank 1 from the bottom
                tail = list(reversed(sorted_population))[:n_limit]
                # Keep worst items, ranked from worst (e.g. Rank 1 of bottom)
                bottom_ranked = []
                for idx, item in enumerate(tail):
                    rank_num = population_count - idx
                    p_tile = round(((population_count - rank_num + 1) / max(1, population_count)) * 100.0, 1)
                    v = round(item["value"], 2)
                    fmt_v = f"{v:,}" if unit != "$" else f"${v:,.2f}"
                    if unit and unit != "$":
                        fmt_v = f"{v:,.1f} {unit}"
                    bottom_ranked.append(RankedEntityRow(
                        rank=rank_num,
                        entity=item["entity"],
                        value=v,
                        formatted_value=fmt_v,
                        population_count=population_count,
                        percentile=p_tile,
                        percentile_label=f"Bottom {round((idx + 1) / population_count * 100.0, 1)}%",
                        delta_benchmark=round(v - benchmark_val, 2),
                        is_above_benchmark=(v >= benchmark_val) if not is_lower_better else (v <= benchmark_val),
                    ))
                ranked_rows = bottom_ranked
            elif mode_upper == "BOTH":
                # Top N and Bottom N with overlap prevention
                half_limit = n_limit // 2 if n_limit > 1 else 1
                if 2 * half_limit >= population_count:
                    # Population fully covered without duplication!
                    ranked_rows = make_ranked_rows(sorted_population)
                else:
                    ranked_rows = make_ranked_rows(sorted_population[:half_limit])
                    worst_items = list(reversed(sorted_population))[:half_limit]
                    bottom_rows = []
                    for idx, item in enumerate(worst_items):
                        rank_num = population_count - idx
                        p_tile = round(((population_count - rank_num + 1) / max(1, population_count)) * 100.0, 1)
                        v = round(item["value"], 2)
                        fmt_v = f"{v:,}" if unit != "$" else f"${v:,.2f}"
                        if unit and unit != "$":
                            fmt_v = f"{v:,.1f} {unit}"
                        bottom_rows.append(RankedEntityRow(
                            rank=rank_num,
                            entity=item["entity"],
                            value=v,
                            formatted_value=fmt_v,
                            population_count=population_count,
                            percentile=p_tile,
                            percentile_label=f"Bottom {round((idx + 1) / population_count * 100.0, 1)}%",
                            delta_benchmark=round(v - benchmark_val, 2),
                            is_above_benchmark=(v >= benchmark_val) if not is_lower_better else (v <= benchmark_val),
                        ))

            # Distribution Summary (P10, P25, P50, P75, P90, min, max, std)
            vals_sorted_num = sorted(all_vals)
            p10 = vals_sorted_num[int(len(vals_sorted_num) * 0.10)]
            p25 = vals_sorted_num[int(len(vals_sorted_num) * 0.25)]
            p50 = vals_sorted_num[int(len(vals_sorted_num) * 0.50)]
            p75 = vals_sorted_num[int(len(vals_sorted_num) * 0.75)]
            p90 = vals_sorted_num[min(int(len(vals_sorted_num) * 0.90), len(vals_sorted_num) - 1)]

            dist_summary = {
                "count": population_count,
                "mean": benchmark_val,
                "median": round(p50, 2),
                "min": round(vals_sorted_num[0], 2),
                "max": round(vals_sorted_num[-1], 2),
                "p10": round(p10, 2),
                "p25": round(p25, 2),
                "p75": round(p75, 2),
                "p90": round(p90, 2),
            }

            return {
                "entity_column": entity_column,
                "entity_type": cls._infer_entity_type_label(entity_column),
                "measure_column": measure_column,
                "aggregation": aggregation,
                "unit": unit,
                "ranking_direction": desirability.value,
                "population_count": population_count,
                "benchmark": benchmark_val,
                "ranked_rows": [r.model_dump() for r in ranked_rows],
                "bottom_rows": [r.model_dump() for r in bottom_rows],
                "distribution_summary": dist_summary,
                "limit": limit,
                "mode": direction,
                "is_full_coverage": len(ranked_rows) >= population_count or (len(ranked_rows) + len(bottom_rows) >= population_count),
            }

        finally:
            if close_conn:
                conn.close()

    @classmethod
    def build_entity_ranking_story(
        cls,
        dataset_id: int,
        conn=None,
    ) -> EntityRankingStory | None:
        """Discovers best entity & measure and builds initial EntityRankingStory."""
        close_conn = False
        if conn is None:
            conn = get_connection()
            close_conn = True

        try:
            entities, measures = cls.discover_rankable_entities_and_measures(dataset_id, conn)
            if not entities or not measures:
                return None

            # Pick dominant entity (prefer group/categorical entity)
            pri_entity = entities[0]
            # Pick dominant measure (prefer highest-signal measure)
            pri_measure = measures[0]

            ent_col = pri_entity["column"]
            m_col = pri_measure["column"]

            query_res = cls.execute_ranking_query(
                dataset_id=dataset_id,
                entity_column=ent_col,
                measure_column=m_col,
                sheet_id=pri_entity["sheet_id"],
                aggregation=pri_measure["aggregation"],
                direction="TOP",
                limit=5,
                conn=conn,
            )

            story_id = f"STORY-RANK-{hashlib.sha256(f'{dataset_id}_{ent_col}_{m_col}'.encode()).hexdigest()[:8]}"

            return EntityRankingStory(
                story_id=story_id,
                entity_type=pri_entity["entity_type"],
                entity_column=ent_col,
                display_name=pri_entity["display_name"],
                sheet_id=pri_entity["sheet_id"],
                measure=m_col,
                measure_label=pri_measure["measure_label"],
                aggregation=pri_measure["aggregation"],
                unit=pri_measure["unit"],
                ranking_direction=RankingDirection(query_res["ranking_direction"]),
                population_count=query_res["population_count"],
                default_limit=5,
                supported_limits=[5, 15, 25, 50, 100, 500],
                mode="TOP",
                active_limit=5,
                ranked_rows=[RankedEntityRow(**r) for r in query_res["ranked_rows"]],
                bottom_rows=[RankedEntityRow(**r) for r in query_res.get("bottom_rows", [])],
                benchmark=query_res.get("benchmark"),
                distribution_summary=query_res.get("distribution_summary", {}),
                available_entities=entities[:6],
                available_measures=measures[:6],
                evidence_ids=[f"EVID-RANK-{ent_col}-{m_col}"],
                inspect_payload={
                    "dataset_id": dataset_id,
                    "entity_column": ent_col,
                    "entity_type": pri_entity["entity_type"],
                    "measure_column": m_col,
                    "measure_label": pri_measure["measure_label"],
                    "aggregation": pri_measure["aggregation"],
                    "unit": pri_measure["unit"],
                    "ranking_direction": query_res["ranking_direction"],
                    "polarity_reason": pri_measure.get("polarity_reason", ""),
                    "population_size": query_res["population_count"],
                    "benchmark": query_res.get("benchmark"),
                    "selection_reason": f"Discovered dominant {pri_entity['entity_type']} grouping ({query_res['population_count']} entities) evaluated on governed {pri_measure['measure_label']}.",
                },
            )
        finally:
            if close_conn:
                conn.close()
