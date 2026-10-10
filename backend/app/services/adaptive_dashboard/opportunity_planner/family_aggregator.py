"""Semantic Family Aggregator.

Aggregates repeated temporal and measure columns into coherent SemanticStoryFamily
abstractions BEFORE analytical opportunity scoring.

Enforces:
Repeated period columns
→ semantic temporal family
→ ONE analytical opportunity
→ ONE visual story
"""
from __future__ import annotations

import re
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from .contracts import (
    AnalyticalOpportunity,
    AnalyticalOpportunityScore,
    AnalyticalOpportunityType,
    RelationshipReductionTracker,
)


PERIOD_PATTERN = re.compile(
    r"(\d+(?:st|nd|rd|th)?\s*(?:to|-)\s*\d+(?:st|nd|rd|th)?\s*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)|\b(?:week|wk|w|q|quarter)\s*\d+|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*(?:\s*\d{2,4})?)",
    re.IGNORECASE,
)


class SemanticStoryFamily(BaseModel):
    """Governed semantic group binding multiple related column/period observations."""
    model_config = ConfigDict(extra="ignore")

    family_id: str
    measure_family: str
    related_measure_family: str | None = None
    dimension: str | None = None
    periods: list[str] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    sheet_ids: list[int] = Field(default_factory=list)
    sheet_names: list[str] = Field(default_factory=list)
    family_type: str = "MEASURE_BY_DIMENSION"
    semantic_group: str = "general"
    intent: str = "ranking"
    title: str = ""
    question: str = ""


class SemanticFamilyAggregator:
    """Discovers and consolidates repeated temporal/measure families before opportunity scoring."""

    @classmethod
    def extract_period_and_base(cls, col_name: str, default_measure: str = "metric") -> tuple[str, str | None]:
        """Extracts base measure name and temporal period from a column name.
        
        Examples:
            '1st to 5th July' -> ('attendance', '1st to 5th July') if attendance-like or ('period_metric', '1st to 5th July')
            'Leaves(1st to 5th July)' -> ('leave', '1st to 5th July')
            'Sales_Jan' -> ('sales', 'Jan')
        """
        match = PERIOD_PATTERN.search(col_name)
        if not match:
            return col_name, None

        period_str = match.group(0).strip()
        # Clean prefix/suffix to identify base measure
        cleaned = PERIOD_PATTERN.sub("", col_name).strip(" ()-_")
        low = cleaned.lower()

        if not low or low in ("interact", "mean", "total", "sum", "avg"):
            # Check context
            if "leave" in col_name.lower():
                base_measure = "leave"
            elif any(k in col_name.lower() for k in ("attend", "office", "presence")):
                base_measure = "attendance"
            else:
                base_measure = default_measure
        else:
            base_measure = cleaned

        return base_measure, period_str

    @classmethod
    def aggregate_temporal_measures(
        cls,
        measures: list[dict[str, Any]],
        sid: int,
        sname: str,
        is_workforce: bool = False,
    ) -> list[SemanticStoryFamily]:
        """Groups individual period measures into unified SemanticStoryFamily objects."""
        # Map: base_measure -> list of (period, col_meta)
        grouped: dict[str, list[tuple[str, dict[str, Any]]]] = {}

        for m in measures:
            col = m["column"]
            default_base = "attendance" if is_workforce else "metric"
            base_name, period = cls.extract_period_and_base(col, default_measure=default_base)
            if period:
                key = base_name.lower()
                grouped.setdefault(key, []).append((period, m))

        families: list[SemanticStoryFamily] = []
        for base_key, items in grouped.items():
            if len(items) >= 2:
                # Discovered a genuine temporal family!
                periods = [it[0] for it in items]
                cols = [it[1]["column"] for it in items]
                m_family_name = base_key.replace("_", " ").title()
                fam_id = f"FAM-TIME-{sid}-{base_key}"
                families.append(
                    SemanticStoryFamily(
                        family_id=fam_id,
                        measure_family=base_key,
                        periods=periods,
                        columns=cols,
                        sheet_ids=[sid],
                        sheet_names=[sname],
                        family_type="MEASURE_BY_TIME",
                        semantic_group=items[0][1].get("semantic_group", "temporal"),
                        intent="trend",
                        title=f"{m_family_name} Cadence Across Periods",
                        question=f"How has {m_family_name.lower()} progressed across reporting periods?",
                    )
                )

        return families

    @classmethod
    def aggregate_cross_sheet_relationships(
        cls,
        raw_relationships: list[dict[str, Any]],
        dataset_id: int,
    ) -> list[dict[str, Any]]:
        """Collapses repeated period relationships between sheets into unified reconciliation families.
        
        Example:
        5 separate sheet_relationships (1-5 Jul, 6-12 Jul...) between Sheet1 and Leave Check
        -> 1 consolidated cross-sheet reconciliation family.
        """
        # Group by (left_sheet, right_sheet, measure_type)
        grouped: dict[tuple[int, int, str], list[dict[str, Any]]] = {}

        for r in raw_relationships:
            l_col = r.get("left_column", "")
            base, period = cls.extract_period_and_base(l_col, default_measure="reconciliation")
            type_key = "attendance_leave" if ("leave" in l_col.lower() or "leave" in r.get("right_column", "").lower()) else base.lower()
            group_key = (r["left_sheet"], r["right_sheet"], type_key)
            grouped.setdefault(group_key, []).append(r)

        consolidated: list[dict[str, Any]] = []
        for (l_sid, r_sid, m_type), rels in grouped.items():
            first = rels[0]
            periods = []
            for item in rels:
                _, p = cls.extract_period_and_base(item.get("left_column", ""))
                if p and p not in periods:
                    periods.append(p)

            # Average join confidence
            sims = [float(item.get("similarity", 0.90) or 0.90) for item in rels]
            avg_sim = round(sum(sims) / len(sims), 2)
            keys_count = max(item.get("matching_keys", 1) or 1 for item in rels)

            consolidated.append({
                "id": first["id"],
                "family_id": f"FAM-REL-{l_sid}-{r_sid}-{m_type}",
                "left_sheet": l_sid,
                "right_sheet": r_sid,
                "left_column": first["left_column"],
                "right_column": first["right_column"],
                "cardinality": first.get("cardinality", "many-to-one"),
                "similarity": avg_sim,
                "matching_keys": keys_count,
                "periods": periods,
                "underlying_relationships": [item["id"] for item in rels],
                "measure_family": m_type,
                "title": f"Cross-Source Reconciliation: {m_type.replace('_', ' ').title()}",
                "reason": f"Unified reconciliation across {len(rels)} reporting periods",
            })

        return consolidated
