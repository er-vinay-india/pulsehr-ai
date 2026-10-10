"""Semantic Column Classifier, Unit Detector, Time Intelligence, and Domain Inference.

Provides:
- SemanticColumnRole classification (IDENTIFIER, METRIC, PERCENTAGE, CURRENCY, etc.)
- SemanticUnit detection (currency, percentage, count, duration, rate, ratio)
- TimeIntelligence extraction (reporting period, granularity, partial year)
- Cautious DomainInference (HR, Sales, Finance, Supply Chain, Tech, Research, Education)
"""

from __future__ import annotations

import re
from typing import Any
import pandas as pd

from .models import (
    ColumnProfile,
    DatasetProfile,
    InferredDomain,
    SemanticColumnRole,
    SemanticUnit,
    TimeIntelligence,
)


class SemanticClassifier:
    """Classifies column semantics, units, temporal properties, and business domains."""

    # Domain vocabulary signal weights
    DOMAIN_SIGNALS: dict[InferredDomain, list[str]] = {
        InferredDomain.HR_WORKFORCE: [
            "attendance", "employee", "headcount", "leave", "overtime", "turnover", "attrition",
            "department", "payroll", "salary", "bonus", "tenure", "hr", "workforce", "hiring", "fte"
        ],
        InferredDomain.SALES: [
            "revenue", "sales", "quota", "arr", "mrr", "deal", "pipeline", "discount", "margin",
            "customer", "account", "churn", "renewal", "commission", "booking", "sku", "lead"
        ],
        InferredDomain.FINANCE: [
            "budget", "actual", "variance", "ebitda", "opex", "capex", "ledger", "invoice", "cogs",
            "expense", "profit", "net_income", "cash_flow", "audit", "fiscal", "balance"
        ],
        InferredDomain.SUPPLY_CHAIN: [
            "warehouse", "freight", "inventory", "supplier", "shipment", "carrier", "logistics",
            "dispatch", "customs", "sku", "fulfillment", "lead_time", "transit", "dock"
        ],
        InferredDomain.SOFTWARE_ENGINEERING: [
            "latency", "throughput", "rps", "p99", "p95", "service", "endpoint", "api", "microservice",
            "bug", "commit", "deployment", "incident", "sev", "uptime", "availability", "error_rate"
        ],
        InferredDomain.INFRASTRUCTURE: [
            "cpu", "memory", "cluster", "node", "pod", "kubernetes", "network", "bandwidth", "disk",
            "iops", "host", "datacenter", "telemetry", "prometheus", "kafka", "queue"
        ],
        InferredDomain.RESEARCH: [
            "cohort", "trial", "treatment", "control", "placebo", "p_value", "efficacy", "intervention",
            "kappa", "standard_dev", "correlation", "regression", "patient", "clinical", "sample_size"
        ],
        InferredDomain.EDUCATION: [
            "student", "grade", "course", "curriculum", "lecture", "module", "exam", "score",
            "teacher", "instructor", "enrollment", "gpa", "semester", "academic", "parental",
            "math", "reading", "writing", "school", "lunch"
        ],
        InferredDomain.ENVIRONMENTAL: [
            "pollution", "air_quality", "cpcb", "pm2_5", "pm10", "so2", "no2", "pollutant",
            "aqi", "emission", "particulate", "ambient", "monitored", "environmental"
        ],
    }

    CURRENCY_SYMBOLS = {"$", "€", "£", "¥", "₹", "usd", "eur", "gbp"}
    PERCENT_SYMBOLS = {"%", "pct", "percent", "percentage", "rate", "ratio"}

    @classmethod
    def enrich_column_semantics(cls, col_prof: ColumnProfile, sample_series: pd.Series | None = None) -> ColumnProfile:
        """Determines the semantic role and unit for a column using name, type, and sample distribution."""
        name_lower = col_prof.name.lower().replace(" ", "_").replace("-", "_")
        tokens = set(re.split(r'[^a-zA-Z0-9%]+', name_lower))

        # 1. Date / Time
        if col_prof.data_type == "datetime" or any(k in name_lower for k in ("date", "timestamp", "created_at", "updated_at")):
            col_prof.semantic_role = SemanticColumnRole.DATE
            col_prof.semantic_unit = SemanticUnit.DATE
            return col_prof

        if any(k in name_lower for k in ("time", "hour", "minute", "second", "duration")):
            col_prof.semantic_role = SemanticColumnRole.TIME
            col_prof.semantic_unit = SemanticUnit.DURATION
            return col_prof

        # 2. Percentage / Ratios (token-aware to prevent 'preparation' matching 'rate')
        is_pct_name = "%" in name_lower or "percent" in name_lower or any(t in tokens for t in ("pct", "percentage", "rate", "ratio"))
        if is_pct_name or (
            col_prof.data_type == "numeric" and col_prof.min_val is not None and col_prof.max_val is not None
            and 0.0 <= col_prof.min_val and col_prof.max_val <= 1.0 and any(t in tokens for t in ("ratio", "pct", "rate", "score"))
        ):
            col_prof.semantic_role = SemanticColumnRole.PERCENTAGE
            col_prof.semantic_unit = SemanticUnit.PERCENTAGE
            return col_prof

        # 3. Currency / Financial
        if any(k in name_lower for k in ("revenue", "sales", "budget", "cost", "spend", "expense", "price", "amount", "salary", "wage", "margin", "ebitda", "usd")):
            col_prof.semantic_role = SemanticColumnRole.CURRENCY
            col_prof.semantic_unit = SemanticUnit.CURRENCY
            return col_prof

        # 4. Target / Actual / Benchmark
        if any(k in name_lower for k in ("target", "quota", "goal", "plan")):
            col_prof.semantic_role = SemanticColumnRole.TARGET
            col_prof.semantic_unit = SemanticUnit.COUNT if col_prof.data_type == "numeric" else SemanticUnit.UNKNOWN
            return col_prof

        if any(k in name_lower for k in ("actual", "achieved", "completed")):
            col_prof.semantic_role = SemanticColumnRole.ACTUAL
            col_prof.semantic_unit = SemanticUnit.COUNT if col_prof.data_type == "numeric" else SemanticUnit.UNKNOWN
            return col_prof

        if any(k in name_lower for k in ("benchmark", "baseline", "standard")):
            col_prof.semantic_role = SemanticColumnRole.BENCHMARK
            return col_prof

        # 5. Identifier / Key / Ordinal (row numbers and serials are identifiers, never metrics)
        is_ordinal = bool(re.match(r'^(sr|s|seq|row)[\._\s]?no\.?', col_prof.name, re.I)) or name_lower in (
            "sr_no", "s_no", "srno", "sno", "serial_no", "row_num", "row_no", "row_id", "seq_no"
        )
        if col_prof.is_identifier_candidate or name_lower.endswith("_id") or name_lower == "id" or name_lower.endswith("code") or is_ordinal:
            col_prof.semantic_role = SemanticColumnRole.IDENTIFIER
            return col_prof

        # 6. Geographic Location (prioritized before generic status keywords to prevent 'State / Union Territory' becoming STATUS)
        if any(k in name_lower for k in ("region", "country", "city", "town", "location", "territory", "zone", "facility", "site", "hub", "state")):
            col_prof.semantic_role = SemanticColumnRole.LOCATION
            return col_prof

        # 7. Person / Organization
        if any(k in name_lower for k in ("employee", "customer", "user", "author", "manager", "lead", "person", "name")):
            col_prof.semantic_role = SemanticColumnRole.PERSON
            return col_prof

        if any(k in name_lower for k in ("company", "department", "division", "team", "organization", "agency", "branch")):
            col_prof.semantic_role = SemanticColumnRole.ORGANIZATION
            return col_prof

        # 8. Status / Workflow State
        if any(k in name_lower for k in ("status", "flag", "stage", "phase")) or name_lower.endswith("_status"):
            col_prof.semantic_role = SemanticColumnRole.STATUS
            col_prof.semantic_unit = SemanticUnit.COUNT
            return col_prof

        # 8. Numeric Metric or Dimension
        if col_prof.data_type == "numeric":
            col_prof.semantic_role = SemanticColumnRole.METRIC
            col_prof.semantic_unit = SemanticUnit.COUNT
        elif col_prof.data_type == "boolean":
            col_prof.semantic_role = SemanticColumnRole.BOOLEAN
        else:
            col_prof.semantic_role = SemanticColumnRole.CATEGORY

        return col_prof

    @classmethod
    def infer_domain(
        cls,
        profiles: list[DatasetProfile],
        dataset_name: str = "",
        user_instruction: str = ""
    ) -> tuple[InferredDomain, float, list[str]]:
        """Cautiously infers the business domain from column profiles, dataset titles, and user cues."""
        all_cols = []
        for p in profiles:
            all_cols.extend([c.name for c in p.columns])
        col_text = " ".join(all_cols)
        raw_text = f"{dataset_name} {user_instruction} {col_text}".lower()
        # Replace non-alphanumeric characters with spaces to avoid underscore boundary issues
        normalized_corpus = re.sub(r'[^a-zA-Z0-9]+', ' ', raw_text)

        domain_scores: dict[InferredDomain, int] = {}
        domain_signals_found: dict[InferredDomain, list[str]] = {}

        for domain, keywords in cls.DOMAIN_SIGNALS.items():
            matched = []
            for kw in keywords:
                clean_kw = re.sub(r'[^a-zA-Z0-9]+', ' ', kw.lower()).strip()
                if re.search(r'\b' + re.escape(clean_kw) + r'\b', normalized_corpus):
                    matched.append(kw)
            domain_scores[domain] = len(matched)
            domain_signals_found[domain] = matched

        # Find top domain
        best_domain = InferredDomain.GENERIC_ANALYTICS
        best_score = 0
        for domain, score in domain_scores.items():
            if score > best_score:
                best_score = score
                best_domain = domain

        if best_score < 2:
            return InferredDomain.GENERIC_ANALYTICS, 0.50, ["Insufficient domain-specific keywords; using generic analytics."]

        # Calculate cautious confidence (0.6 to 0.95)
        confidence = min(0.95, round(0.60 + (best_score * 0.05), 2))
        return best_domain, confidence, domain_signals_found[best_domain]

    @classmethod
    def extract_time_intelligence(cls, profiles: list[DatasetProfile]) -> TimeIntelligence:
        """Extracts reporting period, periodicity granularity, and temporal boundaries."""
        min_dates = []
        max_dates = []

        for p in profiles:
            if p.date_range:
                if p.date_range.get("min_date"):
                    min_dates.append(p.date_range["min_date"])
                if p.date_range.get("max_date"):
                    max_dates.append(p.date_range["max_date"])

        if not min_dates or not max_dates:
            return TimeIntelligence(
                reporting_period="Current Period",
                granularity="unspecified",
                is_partial_year=False
            )

        overall_min = min(min_dates)
        overall_max = max(max_dates)

        # Period label formatting
        period_label = f"{overall_min} to {overall_max}" if overall_min != overall_max else str(overall_min)

        # Detect year/quarter if possible
        try:
            d_min = pd.to_datetime(overall_min)
            d_max = pd.to_datetime(overall_max)
            days_span = (d_max - d_min).days

            granularity = "daily" if days_span < 35 else ("weekly" if days_span < 90 else ("monthly" if days_span < 365 else "yearly"))
            is_partial = days_span < 300

            if d_min.year == d_max.year:
                q_start = (d_min.month - 1) // 3 + 1
                q_end = (d_max.month - 1) // 3 + 1
                if q_start == q_end:
                    period_label = f"Q{q_start} {d_min.year}"
                else:
                    period_label = f"Q{q_start} - Q{q_end} {d_min.year}"
            else:
                period_label = f"{d_min.year} - {d_max.year}"
        except Exception:
            granularity = "unspecified"
            is_partial = False

        return TimeIntelligence(
            reporting_period=period_label,
            granularity=granularity,
            min_date=overall_min,
            max_date=overall_max,
            is_partial_year=is_partial
        )
