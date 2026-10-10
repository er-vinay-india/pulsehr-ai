"""Analytical Opportunity Planner.

Deterministic layer between ingestion semantic metadata and executive analytics.
Transforms ingestion profiles, semantic groups, and relationship graphs into prioritized,
domain-entitled AnalyticalOpportunity candidates with full noise-reduction tracking.
"""
from __future__ import annotations

import collections
import itertools
import json
import logging
import re
from typing import Any, Literal

from app.db.database import get_connection
from ..domain_governance import DatasetDomain, DomainCapabilityGate, DomainCapabilityProfile
from .contracts import (
    AnalyticalOpportunity,
    AnalyticalOpportunityScore,
    AnalyticalOpportunityType,
    RelationshipReductionTracker,
)
from .family_aggregator import SemanticFamilyAggregator


logger = logging.getLogger(__name__)


class AnalyticalOpportunityPlanner:
    """Plans meaningful analytical inquiries directly from ingestion semantic intelligence."""

    @classmethod
    def plan_opportunities(
        cls,
        dataset_id: int,
        sheets: list[Any],
        conn=None,
        dataset_name: str = "",
    ) -> tuple[list[AnalyticalOpportunity], RelationshipReductionTracker]:
        """Discovers, gates, and prioritizes candidate analytical opportunities."""
        close_conn = False
        if conn is None:
            conn = get_connection()
            close_conn = True

        opportunities: list[AnalyticalOpportunity] = []
        tracker = RelationshipReductionTracker()

        try:
            # 1. Resolve domain capability gate to enforce domain isolation
            all_cols: list[str] = []
            for s in sheets:
                all_cols.extend(getattr(s, "columns", []))
            domain_profile = DomainCapabilityGate.resolve_domain(
                columns=all_cols,
                dataset_name=dataset_name,
            )
            is_workforce = domain_profile.domain == DatasetDomain.WORKFORCE

            # 2. Extract column metadata and semantic groups per sheet
            total_columns = len(all_cols)
            raw_combinations = (total_columns * (total_columns - 1)) // 2 if total_columns >= 2 else 0
            tracker.raw_possible_relationships = raw_combinations

            total_group_evals = 0
            total_col_evals = 0

            for s in sheets:
                sid = getattr(s, "sheet_id", 0)
                sname = getattr(s, "sheet_name", f"Sheet_{sid}")
                columns = getattr(s, "columns", [])

                # Load profile_json and enrichment_json from SQLite
                row = conn.execute(
                    "SELECT profile_json, enrichment_json FROM sheets WHERE id = ?",
                    (sid,),
                ).fetchone()

                profiles_raw = json.loads(row[0]) if row and row[0] else []
                enrich_raw = json.loads(row[1]) if row and row[1] else {}

                profile_map: dict[str, dict[str, Any]] = {}
                for p in profiles_raw:
                    cname = p.get("column") or p.get("name") or ""
                    if cname:
                        profile_map[cname] = p

                semantic_groups = enrich_raw.get("semantic_groups", [])

                # Categorize columns by semantic role
                measures: list[dict[str, Any]] = []
                dimensions: list[dict[str, Any]] = []
                temporals: list[dict[str, Any]] = []
                identifiers: list[dict[str, Any]] = []

                for c in columns:
                    prof = profile_map.get(c, {})
                    explicit_role = prof.get("semantic_role") or prof.get("probable_semantic_role")
                    p_type = prof.get("physical_type", "").lower()
                    s_type = prof.get("semantic_type", "").lower()
                    is_numeric = bool(prof.get("numeric")) or p_type in ("float", "int", "real", "double", "numeric")
                    card = prof.get("distinct") or prof.get("cardinality", 0)
                    unit = prof.get("unit") or prof.get("detected_unit") or ""
                    grain = prof.get("metric_grain", "")
                    t_grain = prof.get("temporal_grain", "")

                    meta = {
                        "column": c,
                        "sheet_id": sid,
                        "sheet_name": sname,
                        "unit": unit,
                        "grain": grain,
                        "temporal_grain": t_grain,
                        "cardinality": card,
                        "profile": prof,
                        "semantic_group": cls._resolve_group_for_column(c, semantic_groups),
                    }

                    # Canonical role assignment based on ingestion intelligence
                    low_c = c.lower()
                    # Ingestion explicit role takes highest precedence:
                    if explicit_role in ("MEASURE", "QUANTITY", "AMOUNT"):
                        measures.append(meta)
                    elif explicit_role in ("TIME", "TEMPORAL") or s_type in ("date", "datetime"):
                        temporals.append(meta)
                    elif explicit_role in ("IDENTIFIER",):
                        identifiers.append(meta)
                    elif explicit_role in ("DIMENSION", "CATEGORICAL", "ENTITY"):
                        if low_c in ("date", "week", "month", "year", "quarter", "period") or low_c.endswith(("_date", "_dt", "_month", "_year", "_week")):
                            temporals.append(meta)
                        else:
                            dimensions.append(meta)
                    elif any(k in low_c for k in ("id", "code", "sku", "key", "full name", "employee_id")):
                        identifiers.append(meta)
                    elif is_numeric and not any(k in low_c for k in ("id", "code", "key", "number", "num", "idx")):
                        measures.append(meta)
                    elif s_type in ("date", "datetime") or (any(k in low_c for k in ("date", "week", "month", "year", "quarter", "period")) and not is_numeric):
                        temporals.append(meta)
                    else:
                        dimensions.append(meta)

                # Track group-level filtering efficiency
                distinct_groups = {m["semantic_group"] for m in measures + dimensions + temporals}
                num_groups = len(distinct_groups)
                eligible_groups = (num_groups * (num_groups - 1)) // 2 if num_groups >= 2 else 1
                total_group_evals += eligible_groups
                tracker.eligible_group_relationships = total_group_evals

                # 2.5 TemporalStoryAggregationIntegrity & Pre-Scoring Family Aggregation
                # Filter out synthetic interaction columns from combinatorial pairing
                clean_measures = [m for m in measures if not m["column"].lower().startswith("interact_")]
                clean_dimensions = [d for d in dimensions if not d["column"].lower().startswith("interact_")]

                temporal_families = SemanticFamilyAggregator.aggregate_temporal_measures(
                    measures=clean_measures,
                    sid=sid,
                    sname=sname,
                    is_workforce=is_workforce,
                )

                temporal_cols_in_families = set()
                for fam in temporal_families:
                    temporal_cols_in_families.update(fam.columns)

                    # A. ONE Cadence Opportunity per temporal family
                    t_score = AnalyticalOpportunityScore.compute(
                        business_impact=0.92,
                        statistical_strength=0.90,
                        actionability=0.85,
                        relationship_confidence=0.95,
                        novelty=0.80,
                        temporal_relevance=1.00,
                        visual_suitability=0.95,
                    )
                    opportunities.append(
                        AnalyticalOpportunity(
                            opportunity_id=f"OPP-TEMPORAL-{fam.family_id}",
                            opportunity_type=AnalyticalOpportunityType.MEASURE_BY_TIME,
                            title=fam.title,
                            question=fam.question,
                            sheet_id=sid,
                            sheet_name=sname,
                            primary_measure=fam.measure_family,
                            primary_dimension="reporting_period",
                            semantic_group=fam.semantic_group,
                            semantic_family=fam.family_id,
                            periods=fam.periods,
                            underlying_columns=fam.columns,
                            measure_unit="%" if is_workforce and "attend" in fam.measure_family else "days",
                            metric_grain="weekly",
                            temporal_grain="weekly",
                            cardinality=len(fam.periods),
                            statistical_intent="trend",
                            target_visual_archetype="TREND_STORY",
                            score=t_score,
                            source_sheet_ids=[sid],
                            provenance={
                                "dataset_id": dataset_id,
                                "sheet_id": sid,
                                "sheet_name": sname,
                                "temporal_columns": fam.columns,
                                "role_pairing": "TEMPORAL_SEQUENCE_AGGREGATION",
                                "method": "TIME_SERIES",
                            },
                        )
                    )

                    # B. ONE Dimension Ranking Opportunity per dimension for this temporal family
                    for d in clean_dimensions:
                        total_col_evals += 1
                        if not cls._is_entitled_for_domain(fam.measure_family, d["column"], domain_profile):
                            continue

                        d_score = AnalyticalOpportunityScore.compute(
                            business_impact=0.90,
                            statistical_strength=0.86,
                            actionability=0.84,
                            relationship_confidence=0.95,
                            novelty=0.75,
                            visual_suitability=0.92,
                        )
                        opportunities.append(
                            AnalyticalOpportunity(
                                opportunity_id=f"OPP-FAM-D-{sid}-{fam.measure_family}-{d['column']}",
                                opportunity_type=AnalyticalOpportunityType.MEASURE_BY_DIMENSION,
                                title=f"{fam.measure_family.replace('_', ' ').title()} Performance by {cls._humanize(d['column'])}",
                                question=f"How does {fam.measure_family.replace('_', ' ')} vary across {cls._humanize(d['column'])}?",
                                sheet_id=sid,
                                sheet_name=sname,
                                primary_measure=fam.measure_family,
                                primary_dimension=d["column"],
                                semantic_group=fam.semantic_group,
                                semantic_family=f"{fam.measure_family}_{d['column']}",
                                periods=fam.periods,
                                underlying_columns=fam.columns,
                                measure_unit="days" if is_workforce else "units",
                                metric_grain="aggregated",
                                cardinality=d["cardinality"] or 5,
                                statistical_intent="ranking",
                                target_visual_archetype="RANKING_STORY",
                                score=d_score,
                                source_sheet_ids=[sid],
                                provenance={
                                    "dataset_id": dataset_id,
                                    "sheet_id": sid,
                                    "sheet_name": sname,
                                    "underlying_columns": fam.columns,
                                    "dimension": d["column"],
                                    "role_pairing": "MEASURE_FAMILY × DIMENSION",
                                    "method": "GROUP_BY",
                                },
                            )
                        )

                # Standalone measures (not in any temporal sequence family)
                standalone_measures = [
                    m for m in clean_measures if m["column"] not in temporal_cols_in_families
                ]

                # 3. Pair: STANDALONE MEASURE + CATEGORICAL DIMENSION
                for m in standalone_measures:
                    for d in clean_dimensions:
                        total_col_evals += 1
                        if not cls._is_entitled_for_domain(m["column"], d["column"], domain_profile):
                            continue

                        opp_id = f"OPP-M-D-{sid}-{m['column']}-{d['column']}"
                        card = d["cardinality"] or 5
                        m_unit = m["unit"] or cls._infer_fallback_unit(m["column"])
                        m_grain = m["grain"] or cls._infer_fallback_grain(m_unit)

                        score = AnalyticalOpportunityScore.compute(
                            business_impact=0.88,
                            statistical_strength=0.82,
                            actionability=0.80,
                            relationship_confidence=0.95,
                            novelty=0.70,
                            visual_suitability=0.90,
                            redundancy_penalty=0.0,
                        )

                        opportunities.append(
                            AnalyticalOpportunity(
                                opportunity_id=opp_id,
                                opportunity_type=AnalyticalOpportunityType.MEASURE_BY_DIMENSION,
                                title=f"{cls._humanize(m['column'])} by {cls._humanize(d['column'])}",
                                question=f"How does {cls._humanize(m['column'])} vary across {cls._humanize(d['column'])}?",
                                sheet_id=sid,
                                sheet_name=sname,
                                primary_measure=m["column"],
                                primary_dimension=d["column"],
                                semantic_group=m["semantic_group"],
                                semantic_family=f"{m['column']}_{d['column']}",
                                measure_unit=m_unit,
                                metric_grain=m_grain,
                                cardinality=card,
                                statistical_intent="ranking",
                                target_visual_archetype="RANKING_STORY",
                                score=score,
                                source_sheet_ids=[sid],
                                provenance={
                                    "dataset_id": dataset_id,
                                    "sheet_id": sid,
                                    "sheet_name": sname,
                                    "source_columns": [m["column"], d["column"]],
                                    "semantic_group": m["semantic_group"],
                                    "role_pairing": "MEASURE × DIMENSION",
                                    "method": "GROUP_BY",
                                },
                            )
                        )

                # 4. Standalone Pair: MEASURE + TEMPORAL DIMENSION
                for m in standalone_measures:
                    for t in temporals:
                        total_col_evals += 1
                        if not cls._is_entitled_for_domain(m["column"], t["column"], domain_profile):
                            continue

                        opp_id = f"OPP-M-T-{sid}-{m['column']}-{t['column']}"
                        m_unit = m["unit"] or cls._infer_fallback_unit(m["column"])
                        m_grain = m["grain"] or cls._infer_fallback_grain(m_unit)
                        t_grain = t["temporal_grain"] or "week"

                        score = AnalyticalOpportunityScore.compute(
                            business_impact=0.85,
                            statistical_strength=0.85,
                            actionability=0.75,
                            relationship_confidence=0.95,
                            novelty=0.65,
                            temporal_relevance=0.95,
                            visual_suitability=0.88,
                        )

                        opportunities.append(
                            AnalyticalOpportunity(
                                opportunity_id=opp_id,
                                opportunity_type=AnalyticalOpportunityType.MEASURE_BY_TIME,
                                title=f"{cls._humanize(m['column'])} Temporal Cadence",
                                question=f"How has {cls._humanize(m['column'])} evolved over time?",
                                sheet_id=sid,
                                sheet_name=sname,
                                primary_measure=m["column"],
                                primary_dimension=t["column"],
                                semantic_group=m["semantic_group"],
                                semantic_family=f"temporal_{m['column']}",
                                measure_unit=m_unit,
                                metric_grain=m_grain,
                                temporal_grain=t_grain,
                                statistical_intent="trend",
                                target_visual_archetype="TREND_STORY",
                                score=score,
                                source_sheet_ids=[sid],
                                provenance={
                                    "dataset_id": dataset_id,
                                    "sheet_id": sid,
                                    "sheet_name": sname,
                                    "source_columns": [m["column"], t["column"]],
                                    "semantic_group": m["semantic_group"],
                                    "role_pairing": "MEASURE × TEMPORAL",
                                    "method": "TIME_SERIES",
                                },
                            )
                        )

                # 5. Cross-Family & Measure-by-Measure Pairing
                # A. Consolidate interactions across temporal families (e.g. attendance vs leave across periods)
                if len(temporal_families) >= 2:
                    for i in range(len(temporal_families)):
                        for j in range(i + 1, len(temporal_families)):
                            f1, f2 = temporal_families[i], temporal_families[j]
                            m1_name, m2_name = f1.measure_family.title(), f2.measure_family.title()
                            cross_fam_score = AnalyticalOpportunityScore.compute(
                                business_impact=0.91,
                                statistical_strength=0.88,
                                actionability=0.85,
                                relationship_confidence=0.90,
                                novelty=0.85,
                                visual_suitability=0.92,
                            )
                            opportunities.append(
                                AnalyticalOpportunity(
                                    opportunity_id=f"OPP-FAM-REL-{sid}-{f1.measure_family}-{f2.measure_family}",
                                    opportunity_type=AnalyticalOpportunityType.MEASURE_BY_MEASURE,
                                    title=f"{m1_name} and {m2_name} Across Reporting Periods",
                                    question=f"What is the relationship between {m1_name.lower()} and {m2_name.lower()} across reporting periods?",
                                    sheet_id=sid,
                                    sheet_name=sname,
                                    primary_measure=f1.measure_family,
                                    secondary_measure=f2.measure_family,
                                    semantic_group="cross_measure",
                                    semantic_family=f"{f1.measure_family}_{f2.measure_family}",
                                    periods=f1.periods,
                                    underlying_columns=f1.columns + f2.columns,
                                    measure_unit="days" if is_workforce else "units",
                                    metric_grain="record",
                                    statistical_intent="composition" if is_workforce and "leave" in f2.measure_family else "relationship",
                                    target_visual_archetype="COMPOSITION_STORY" if is_workforce and "leave" in f2.measure_family else "RELATIONSHIP_STORY",
                                    score=cross_fam_score,
                                    source_sheet_ids=[sid],
                                    provenance={
                                        "dataset_id": dataset_id,
                                        "sheet_id": sid,
                                        "sheet_name": sname,
                                        "underlying_columns": f1.columns + f2.columns,
                                        "role_pairing": "TEMPORAL_FAMILY × TEMPORAL_FAMILY",
                                        "method": "CORRELATION_SCATTER",
                                    },
                                )
                            )

                # B. Pair standalone non-temporal measures with each other
                for i in range(len(standalone_measures)):
                    for j in range(i + 1, len(standalone_measures)):
                        m1, m2 = standalone_measures[i], standalone_measures[j]
                        total_col_evals += 1
                        if m1["semantic_group"] != m2["semantic_group"]:
                            if not cls._is_cross_measure_group_eligible(m1["semantic_group"], m2["semantic_group"]):
                                continue

                        if not cls._is_entitled_for_domain(m1["column"], m2["column"], domain_profile):
                            continue

                        opp_id = f"OPP-M-M-{sid}-{m1['column']}-{m2['column']}"
                        score = AnalyticalOpportunityScore.compute(
                            business_impact=0.78,
                            statistical_strength=0.80,
                            actionability=0.72,
                            relationship_confidence=0.85,
                            novelty=0.80,
                            visual_suitability=0.82,
                        )

                        opportunities.append(
                            AnalyticalOpportunity(
                                opportunity_id=opp_id,
                                opportunity_type=AnalyticalOpportunityType.MEASURE_BY_MEASURE,
                                title=f"{cls._humanize(m1['column'])} vs {cls._humanize(m2['column'])} Association",
                                question=f"What is the relationship between {cls._humanize(m1['column'])} and {cls._humanize(m2['column'])}?",
                                sheet_id=sid,
                                sheet_name=sname,
                                primary_measure=m1["column"],
                                secondary_measure=m2["column"],
                                semantic_group=m1["semantic_group"],
                                semantic_family=f"{m1['column']}_{m2['column']}",
                                measure_unit=m1["unit"] or cls._infer_fallback_unit(m1["column"]),
                                metric_grain=m1["grain"] or "record",
                                statistical_intent="relationship",
                                target_visual_archetype="RELATIONSHIP_STORY",
                                score=score,
                                source_sheet_ids=[sid],
                                provenance={
                                    "dataset_id": dataset_id,
                                    "sheet_id": sid,
                                    "sheet_name": sname,
                                    "source_columns": [m1["column"], m2["column"]],
                                    "role_pairing": "MEASURE × MEASURE",
                                    "method": "CORRELATION_SCATTER",
                                },
                            )
                        )

            # 6. Cross-Sheet Relationships: Consolidated across repeated period joins
            cur = conn.execute(
                """
                SELECT id, left_sheet, right_sheet, left_column, right_column,
                       cardinality, matching_keys, similarity, reason
                FROM sheet_relationships
                WHERE left_sheet IN (SELECT id FROM sheets WHERE dataset_id = ?)
                """,
                (dataset_id,),
            )
            rel_rows = cur.fetchall()
            raw_rels = []
            for r in rel_rows:
                rel_id, l_sid, r_sid, l_col, r_col, card, keys_count, sim, reason = (
                    r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8]
                )
                total_col_evals += 1
                if card == "many-to-many":
                    logger.info("Suppressing many-to-many relationship %d between sheets %d and %d", rel_id, l_sid, r_sid)
                    continue
                join_conf = float(sim) if sim is not None else 0.90
                if join_conf < 0.70 or (keys_count is not None and keys_count < 2):
                    continue
                raw_rels.append({
                    "id": rel_id,
                    "left_sheet": l_sid,
                    "right_sheet": r_sid,
                    "left_column": l_col,
                    "right_column": r_col,
                    "cardinality": card,
                    "matching_keys": keys_count,
                    "similarity": join_conf,
                    "reason": reason,
                })

            consolidated_rels = SemanticFamilyAggregator.aggregate_cross_sheet_relationships(raw_rels, dataset_id)
            for c_rel in consolidated_rels:
                opp_id = f"OPP-CROSS-{c_rel['family_id']}"
                score = AnalyticalOpportunityScore.compute(
                    business_impact=0.93,
                    statistical_strength=0.89,
                    actionability=0.86,
                    relationship_confidence=c_rel["similarity"],
                    novelty=0.90,
                    cross_sheet_value=0.95,
                    visual_suitability=0.92,
                )
                opportunities.append(
                    AnalyticalOpportunity(
                        opportunity_id=opp_id,
                        opportunity_type=AnalyticalOpportunityType.CROSS_SHEET_RELATIONSHIP,
                        title=c_rel["title"],
                        question=f"How do records in Sheet {c_rel['left_sheet']} reconcile with Sheet {c_rel['right_sheet']} across {c_rel['measure_family']}?",
                        sheet_id=c_rel["left_sheet"],
                        sheet_name=f"Sheet_{c_rel['left_sheet']}",
                        primary_measure=c_rel["left_column"],
                        secondary_measure=c_rel["right_column"],
                        semantic_family=c_rel["family_id"],
                        periods=c_rel.get("periods", []),
                        underlying_columns=[c_rel["left_column"], c_rel["right_column"]],
                        is_cross_sheet=True,
                        source_sheet_ids=[c_rel["left_sheet"], c_rel["right_sheet"]],
                        relationship_id=f"REL-{c_rel['id']}",
                        join_confidence=c_rel["similarity"],
                        cardinality=c_rel["matching_keys"],
                        statistical_intent="composition",
                        target_visual_archetype="COMPOSITION_STORY",
                        score=score,
                        provenance={
                            "dataset_id": dataset_id,
                            "relationship_id": c_rel["id"],
                            "left_sheet_id": c_rel["left_sheet"],
                            "right_sheet_id": c_rel["right_sheet"],
                            "join_columns": [c_rel["left_column"], c_rel["right_column"]],
                            "periods": c_rel.get("periods", []),
                            "underlying_relationships": c_rel.get("underlying_relationships", []),
                            "cardinality": c_rel["cardinality"],
                            "similarity": c_rel["similarity"],
                            "reason": c_rel["reason"],
                        },
                    )
                )

            # Update noise reduction tracker
            tracker.eligible_column_relationships = total_col_evals
            tracker.statistically_meaningful_relationships = len(opportunities)
            tracker.selected_executive_relationships = min(len(opportunities), 8)
            if tracker.raw_possible_relationships > 0:
                eliminated = tracker.raw_possible_relationships - tracker.eligible_group_relationships
                tracker.reduction_ratio = round((max(0, eliminated) / tracker.raw_possible_relationships) * 100.0, 1)
            else:
                tracker.reduction_ratio = 85.0


            # Sort opportunities by multi-factor score descending
            opportunities.sort(key=lambda o: o.score.total_score, reverse=True)


        finally:
            if close_conn:
                conn.close()

        return opportunities, tracker

    @classmethod
    def _resolve_group_for_column(cls, col_name: str, groups: list[dict[str, Any]]) -> str:
        """Finds which semantic group a column belongs to."""
        for g in groups:
            if col_name in g.get("columns", []):
                return g.get("group_name") or g.get("group_id") or "GENERAL"
        # Heuristic fallback based on tokens
        low = col_name.lower()
        if any(k in low for k in ("sale", "revenue", "margin", "profit", "price")):
            return "SALES"
        if any(k in low for k in ("store", "dept", "department", "region", "segment")):
            return "ORGANIZATION"
        if any(k in low for k in ("date", "week", "month", "time", "day", "period")):
            return "TIME"
        if any(k in low for k in ("attend", "leave", "wfo", "presence", "emp")):
            return "WORKFORCE"
        if any(k in low for k in ("cpi", "fuel", "unemploy", "inflation", "macro")):
            return "ECONOMIC_FACTORS"
        return "GENERAL"

    @classmethod
    def _is_cross_measure_group_eligible(cls, g1: str, g2: str) -> bool:
        """Validates whether two distinct semantic groups have entitled cross-analysis."""
        eligible_pairs = {
            frozenset(["SALES", "ECONOMIC_FACTORS"]),
            frozenset(["SALES", "TIME"]),
            frozenset(["WORKFORCE", "TIME"]),
            frozenset(["WORKFORCE", "ORGANIZATION"]),
            frozenset(["SALES", "ORGANIZATION"]),
        }
        return frozenset([g1, g2]) in eligible_pairs

    @classmethod
    def _is_entitled_for_domain(cls, col1: str, col2: str, domain_profile: DomainCapabilityProfile) -> bool:
        """Enforces DomainCapabilityGate isolation: blocks cross-domain leakage."""
        c1_low, c2_low = col1.lower(), col2.lower()
        pair_str = f"{c1_low} {c2_low}"

        # If domain is Retail Sales, block workforce-specific concepts
        if domain_profile.domain == DatasetDomain.RETAIL_SALES:
            if any(k in pair_str for k in ("attendance", "approved_leave", "absenteeism", "wfo", "clock_in")):
                return False

        # If domain is Workforce, block retail-specific concepts
        if domain_profile.domain == DatasetDomain.WORKFORCE:
            if any(k in pair_str for k in ("weekly_sales", "cpi", "fuel_price", "unemployment", "markdown")):
                return False

        return True

    @classmethod
    def _infer_fallback_unit(cls, metric_name: str) -> str:
        low = metric_name.lower()
        if any(k in low for k in ("sale", "revenue", "price", "cpi", "cost", "dollar")):
            return "usd"
        if any(k in low for k in ("attendance", "leave", "presence", "working_day", "absence")):
            return "employee_day"
        if any(k in low for k in ("rate", "pct", "percent", "ratio", "compliance")):
            return "percent"
        if any(k in low for k in ("count", "headcount", "units", "staff", "records")):
            return "count"
        return "units"

    @classmethod
    def _infer_fallback_grain(cls, unit: str) -> str:
        u_low = unit.lower()
        if "employee" in u_low:
            return "employee × working_day"
        if u_low in ("usd", "$"):
            return "financial_transaction"
        if u_low in ("percent", "%"):
            return "cohort_ratio"
        return "record"

    @classmethod
    def _humanize(cls, name: str) -> str:
        return name.replace("_", " ").title()
