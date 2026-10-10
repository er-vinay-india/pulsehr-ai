"""Domain Governance, Capability Gating, and Semantic Entitlement Engine (Phase 13.5).

Enforces the absolute architectural invariant:
    A dataset may only activate analytics, KPIs, scenarios, visuals, policies,
    and recommendations that are semantically valid for its detected domain.

Key Rules:
1. Missing Concept != Zero Value (Unsupported concepts are blocked, never rendered as 0%).
2. Invariance to Column Name Collision (Generic dimensions like 'Department' or 'Date'
   never falsely force a retail sales or finance dataset into the workforce domain).
3. Capability Gating (Downstream analytics, composition planners, and scenario explorers
   must strictly obey allowed/blocked capability sets).
"""

from __future__ import annotations

import logging
import re
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class DatasetDomain(str, Enum):
    """Authoritative semantic domains supported by Highview."""
    RETAIL_SALES = "retail_sales"
    WORKFORCE = "workforce"
    FINANCE = "finance"
    OPERATIONS = "operations"
    ACADEMIC = "academic"
    ENVIRONMENTAL = "environmental"
    GENERIC_BUSINESS = "generic_business"


class DomainCapabilityProfile(BaseModel):
    """Governed capabilities, entities, and constraints authorized for a dataset."""
    model_config = ConfigDict(extra="ignore")

    domain: DatasetDomain
    confidence: float
    detected_entities: list[str] = Field(default_factory=list)
    detected_metrics: list[str] = Field(default_factory=list)
    primary_dimensions: list[str] = Field(default_factory=list)
    temporal_column: str | None = None
    allowed_capabilities: list[str] = Field(default_factory=list)
    blocked_capabilities: list[str] = Field(default_factory=list)
    display_domain_name: str = "Business Intelligence"
    display_subtitle: str = "Synthesized business insights across {count} reconciled sources"
    governed_scenario_domain: str | None = None


class DomainCapabilityGate:
    """Classifies dataset domain from semantic evidence and gates capability access."""

    @classmethod
    def resolve_domain(
        cls,
        columns: list[str],
        sample_rows: list[dict[str, Any]] | None = None,
        dataset_name: str = "",
    ) -> DomainCapabilityProfile:
        """Infers the dataset domain and outputs an authoritative capability entitlement profile."""
        cols_lower = [c.lower().strip() for c in columns]
        name_lower = dataset_name.lower().strip()

        # Score domains based on entity and metric column matches
        scores: dict[DatasetDomain, float] = {
            DatasetDomain.RETAIL_SALES: 0.0,
            DatasetDomain.WORKFORCE: 0.0,
            DatasetDomain.FINANCE: 0.0,
            DatasetDomain.OPERATIONS: 0.0,
            DatasetDomain.ACADEMIC: 0.0,
            DatasetDomain.ENVIRONMENTAL: 0.0,
            DatasetDomain.GENERIC_BUSINESS: 0.0,
        }

        # 1. Retail / Sales Evidence
        retail_keys = [
            "weekly_sales", "sales", "revenue", "store", "holiday_flag",
            "temperature", "fuel_price", "cpi", "unemployment", "markdown",
            "units_sold", "price", "retail", "product_id", "pos", "orders"
        ]
        retail_matches = [k for k in retail_keys if any(k in c for c in cols_lower)]
        if retail_matches:
            scores[DatasetDomain.RETAIL_SALES] += len(retail_matches) * 2.0
        if any(w in name_lower for w in ["sales", "retail", "walmart", "store", "commerce", "pos"]):
            scores[DatasetDomain.RETAIL_SALES] += 3.0

        # 2. Workforce / Attendance Evidence
        # NOTE: 'department' ALONE is a generic organizational dimension and NOT proof of workforce!
        workforce_explicit_keys = [
            "attendance", "office_days", "presence", "leaves", "approved_leaves",
            "working_days", "absenteeism", "headcount", "employee_id", "empid", "worker_id"
        ]
        wf_matches = [k for k in workforce_explicit_keys if any(k in c for c in cols_lower)]
        if wf_matches:
            scores[DatasetDomain.WORKFORCE] += len(wf_matches) * 2.5
        if any(w in name_lower for w in ["wfo", "attendance", "workforce", "hr", "leave", "employee"]):
            scores[DatasetDomain.WORKFORCE] += 3.0

        # 3. Finance Evidence
        fin_keys = ["ebitda", "pnl", "margin", "cost_center", "actual_vs_budget", "ledger", "opex", "capex", "balance"]
        fin_matches = [k for k in fin_keys if any(k in c for c in cols_lower)]
        if fin_matches:
            scores[DatasetDomain.FINANCE] += len(fin_matches) * 2.5
        if any(w in name_lower for w in ["finance", "financial", "budget", "ledger", "pnl", "accounting"]):
            scores[DatasetDomain.FINANCE] += 3.0

        # 4. Academic Evidence
        acad_keys = ["student_id", "gpa", "exam_score", "course", "grade", "credits", "semester"]
        acad_matches = [k for k in acad_keys if any(k in c for c in cols_lower)]
        if acad_matches:
            scores[DatasetDomain.ACADEMIC] += len(acad_matches) * 2.5

        # 5. Operations Evidence
        ops_keys = ["ticket_id", "incident", "sla", "backlog", "throughput", "turnaround_time", "downtime"]
        ops_matches = [k for k in ops_keys if any(k in c for c in cols_lower)]
        if ops_matches:
            scores[DatasetDomain.OPERATIONS] += len(ops_matches) * 2.5

        # 6. Environmental / Air Quality Evidence
        env_keys = ["pm10", "pm2.5", "pm2_5", "so2", "no2", "pollutant", "pollution", "air_quality", "aqi", "emission", "cpcb", "ambient"]
        env_matches = [k for k in env_keys if any(k in c for c in cols_lower)]
        if env_matches:
            scores[DatasetDomain.ENVIRONMENTAL] += len(env_matches) * 2.5
        if any(w in name_lower for w in ["pollution", "air", "aqi", "cpcb", "location_data"]):
            scores[DatasetDomain.ENVIRONMENTAL] += 3.0

        # Select domain with highest confidence
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_domain, top_score = sorted_scores[0]

        if top_score < 2.0:
            top_domain = DatasetDomain.GENERIC_BUSINESS
            confidence = 0.50
        else:
            confidence = min(0.99, round(top_score / (top_score + 1.5), 2))

        # Detect Temporal Column
        date_col = None
        for c in columns:
            cl = c.lower()
            if any(w in cl for w in ["date", "week", "month", "period", "timestamp", "quarter", "year", "time"]):
                date_col = c
                break

        # Construct Capability Gating Matrix
        if top_domain == DatasetDomain.RETAIL_SALES:
            return DomainCapabilityProfile(
                domain=DatasetDomain.RETAIL_SALES,
                confidence=confidence,
                detected_entities=["store", "channel", "department"] if any("dept" in c for c in cols_lower) else ["store"],
                detected_metrics=[c for c in columns if any(m in c.lower() for m in ["sales", "revenue", "price", "cpi", "temp", "fuel", "unemployment"])],
                primary_dimensions=[c for c in columns if any(d in c.lower() for d in ["store", "dept", "department", "holiday", "type"])],
                temporal_column=date_col,
                allowed_capabilities=[
                    "sales_trend", "store_ranking", "holiday_analysis", "pricing_correlation",
                    "category_performance", "sales_scenarios", "volatility_index"
                ],
                blocked_capabilities=[
                    "attendance_policy", "leave_analysis", "office_presence",
                    "workforce_compliance", "policy_calendar_engine", "department_attendance_gap"
                ],
                display_domain_name="Retail Sales Intelligence",
                display_subtitle="Synthesized retail sales insights across {count} reconciled sources",
                governed_scenario_domain="retail_sales",
            )
        elif top_domain == DatasetDomain.WORKFORCE:
            return DomainCapabilityProfile(
                domain=DatasetDomain.WORKFORCE,
                confidence=confidence,
                detected_entities=["employee", "department"],
                detected_metrics=[c for c in columns if any(m in c.lower() for m in ["attendance", "leave", "presence", "days"])],
                primary_dimensions=[c for c in columns if any(d in c.lower() for d in ["dept", "department", "division", "team"])],
                temporal_column=date_col,
                allowed_capabilities=[
                    "attendance_cadence", "department_presence", "leave_reconciliation",
                    "policy_compliance", "workforce_scenarios", "headcount_distribution"
                ],
                blocked_capabilities=[
                    "sales_trend", "store_ranking", "holiday_analysis", "pricing_correlation"
                ],
                display_domain_name="Workforce & Attendance Intelligence",
                display_subtitle="Synthesized workforce conclusions across {count} reconciled sources",
                governed_scenario_domain="workforce",
            )
        elif top_domain == DatasetDomain.FINANCE:
            return DomainCapabilityProfile(
                domain=DatasetDomain.FINANCE,
                confidence=confidence,
                detected_entities=["cost_center", "account", "entity"],
                detected_metrics=[c for c in columns if any(m in c.lower() for m in ["budget", "actual", "variance", "cost", "margin", "revenue"])],
                primary_dimensions=[c for c in columns if any(d in c.lower() for d in ["account", "cost_center", "department", "category"])],
                temporal_column=date_col,
                allowed_capabilities=["budget_variance", "margin_analysis", "cost_pacing", "financial_scenarios"],
                blocked_capabilities=["attendance_policy", "leave_analysis", "office_presence", "store_ranking"],
                display_domain_name="Financial Operations Intelligence",
                display_subtitle="Synthesized financial performance insights across {count} reconciled sources",
                governed_scenario_domain="finance",
            )
        elif top_domain == DatasetDomain.ENVIRONMENTAL:
            return DomainCapabilityProfile(
                domain=DatasetDomain.ENVIRONMENTAL,
                confidence=confidence,
                detected_entities=["city", "town", "state", "location"],
                detected_metrics=[c for c in columns if any(m in c.lower() for m in ["pm10", "pm2.5", "pm2_5", "so2", "no2", "annual average", "pollutant", "aqi"])],
                primary_dimensions=[c for c in columns if any(d in c.lower() for d in ["state", "city", "town", "location", "territory"])],
                temporal_column=date_col,
                allowed_capabilities=[
                    "pollutant_ranking", "air_quality_benchmarks", "location_comparison", "particulate_distribution"
                ],
                blocked_capabilities=[
                    "attendance_policy", "leave_analysis", "office_presence",
                    "workforce_compliance", "policy_calendar_engine", "department_attendance_gap",
                    "sales_trend", "store_ranking"
                ],
                display_domain_name="Environmental & Air Quality Intelligence",
                display_subtitle="Synthesized air quality and pollutant metrics across {count} monitored locations",
                governed_scenario_domain=None,
            )
        else:
            return DomainCapabilityProfile(
                domain=DatasetDomain.GENERIC_BUSINESS,
                confidence=confidence,
                detected_entities=["record", "item"],
                detected_metrics=[c for c in columns if any(m in c.lower() for m in ["value", "amount", "count", "score", "total"])],
                primary_dimensions=[c for c in columns if any(d in c.lower() for d in ["category", "type", "group", "status", "name"])],
                temporal_column=date_col,
                allowed_capabilities=["distribution_ranking", "temporal_trend", "correlation_analysis"],
                blocked_capabilities=[
                    "attendance_policy", "leave_analysis", "office_presence",
                    "workforce_compliance", "policy_calendar_engine", "department_attendance_gap",
                    "sales_trend", "store_ranking"
                ],
                display_domain_name="Executive Business Intelligence",
                display_subtitle="Synthesized business insights across {count} reconciled sources",
                governed_scenario_domain=None,
            )


class AnalyticalEntitlementIntegrity:
    """Enforces semantic entitlement checks preventing missing concepts from rendering as fake zero metrics."""

    REQUIRED_CONCEPTS_FOR_METRIC = {
        "office_presence_rate": ["attendance", "workforce", "employee"],
        "policy_compliance": ["attendance", "policy_calendar", "workforce"],
        "approved_leave_rate": ["approved_leaves", "workforce"],
        "department_attendance_gap": ["attendance", "department", "workforce"],
        "weekly_sales_total": ["sales", "store"],
        "average_weekly_sales": ["sales"],
        "holiday_sales_lift": ["sales", "holiday"],
    }

    @classmethod
    def verify_metric_entitlement(
        cls,
        metric_key: str | None = None,
        profile: DomainCapabilityProfile | None = None,
        available_columns: list[str] | None = None,
        metric_concept: str | None = None,
        dataset_columns: list[str] | None = None,
        detected_entities: list[str] | None = None,
    ) -> tuple[bool, str]:
        """Validates if a metric is semantically entitled.

        Returns:
            (True, "ENTITLED") if supported.
            (False, "UNSUPPORTED_CONCEPT") or (False, "NOT_APPLICABLE") if concept is missing.
        """
        target_metric = (metric_concept or metric_key or "").lower().replace(" ", "_")
        cols = dataset_columns or available_columns or []
        cols_lower = " ".join(cols).lower()

        # 1. Check capability blocking if profile is provided
        if profile:
            for blocked in profile.blocked_capabilities:
                if blocked in target_metric:
                    return False, "NOT_APPLICABLE"

        # 2. Check concept requirements
        reqs = cls.REQUIRED_CONCEPTS_FOR_METRIC.get(target_metric)
        if reqs:
            if "attendance" in reqs and not any(w in cols_lower for w in ["attendance", "presence", "wfo"]):
                return False, "UNSUPPORTED_CONCEPT"
            if "approved_leaves" in reqs and not any(w in cols_lower for w in ["leave", "leaves"]):
                return False, "UNSUPPORTED_CONCEPT"
            if "sales" in reqs and not any(w in cols_lower for w in ["sales", "revenue"]):
                return False, "UNSUPPORTED_CONCEPT"

        return True, "ENTITLED"
