"""Multi-Factor Classifiers for Risk and Complexity (Phase 11.2).

Guarantees:
1. Risk is NOT classified from wording alone: evaluates intent, population scope,
   decision reversibility, operational/financial impact, and whether it alters organizational rules.
2. Risk and Complexity are strictly orthogonal (e.g. R1/C1, R4/C2, R2/C3).
"""
from __future__ import annotations

import re
from typing import Any
from .contracts import (
    ComplexityTier,
    RequestFactorProfile,
    RiskTier,
)


class MultiFactorRiskClassifier:
    """Classifies risk based on comprehensive organizational and operational factors."""

    # Keywords signaling rule changes or structural interventions
    RULE_CHANGE_KEYWORDS = {
        "mandate", "change policy", "alter policy", "enforce new", "require everyone to",
        "should we change", "should we mandate", "terminate", "lay off", "reduce headcount",
        "salary change", "restructure department"
    }

    # Keywords signaling recommendation seeking
    RECOMMENDATION_KEYWORDS = {
        "what should management do", "what should we do", "recommend", "how can we fix",
        "action plan", "suggest an intervention", "improve compliance", "best schedule"
    }

    # Keywords signaling interpretation or causal inquiry
    INTERPRETATION_KEYWORDS = {
        "why did", "why are", "explain the decline", "what caused", "root cause",
        "reason for", "why is attendance low", "correlate", "relationship between"
    }

    # Keywords signaling descriptive analytics
    ANALYTICS_KEYWORDS = {
        "rank", "average", "mean", "sum", "total", "distribution", "breakdown",
        "highest", "lowest", "compare departments", "top 5", "bottom 5"
    }

    @classmethod
    def extract_factor_profile(cls, query: str, context: dict[str, Any] | None = None) -> RequestFactorProfile:
        """Extracts multidimensional decision factors from query text and contextual environment."""
        q_lower = query.lower().strip()
        ctx = context or {}

        # 1. Check whether query can change organizational rules
        changes_rule = any(kw in q_lower for kw in cls.RULE_CHANGE_KEYWORDS) or ctx.get("changes_rule", False)

        # 2. Determine affected population scope
        if any(w in q_lower for w in ["everyone", "organization", "company-wide", "all employees", "all departments", "corporate"]):
            scope = "organization"
        elif any(w in q_lower for w in ["engineering", "operations", "design", "department", "dept", "sales", "functions"]):
            scope = "department"
        elif any(w in q_lower for w in ["team", "squad", "unit", "pod"]):
            scope = "team"
        elif any(w in q_lower for w in ["employee id", "worker", "john", "alice", "person", "individual", "staff #"]):
            scope = "individual"
        else:
            scope = ctx.get("scope", "department")

        # 3. Determine decision reversibility & financial/operational impact
        if changes_rule and scope in ["organization", "department"]:
            reversibility = "irreversible"
            impact = "critical" if scope == "organization" else "high"
        elif any(kw in q_lower for kw in cls.RECOMMENDATION_KEYWORDS):
            reversibility = "moderate"
            impact = "medium"
        elif any(kw in q_lower for kw in cls.INTERPRETATION_KEYWORDS):
            reversibility = "reversible"
            impact = "low"
        else:
            reversibility = "reversible"
            impact = "negligible"

        # 4. Resolve intent
        if changes_rule:
            intent = "policy_mandate_deliberation"
        elif any(kw in q_lower for kw in cls.RECOMMENDATION_KEYWORDS):
            intent = "operational_recommendation"
        elif any(kw in q_lower for kw in cls.INTERPRETATION_KEYWORDS):
            intent = "interpretive_investigation"
        elif any(kw in q_lower for kw in cls.ANALYTICS_KEYWORDS):
            intent = "descriptive_aggregation"
        else:
            intent = "deterministic_lookup"

        return RequestFactorProfile(
            intent=intent,
            affected_population_scope=scope,
            decision_reversibility=reversibility,
            financial_operational_impact=impact,
            changes_organizational_rule=changes_rule,
            query_text=query,
        )

    @classmethod
    def classify(cls, query: str, context: dict[str, Any] | None = None) -> tuple[RiskTier, RequestFactorProfile]:
        """Classifies a user query into R0–R4 based on multi-factor profile."""
        profile = cls.extract_factor_profile(query, context)

        # Rule 1: High-impact decision support (R4)
        # Requires: intent to change rules OR irreversible impact on organization/department
        if profile.changes_organizational_rule and profile.affected_population_scope in ["organization", "department"]:
            return RiskTier.R4, profile
        if profile.financial_operational_impact in ["high", "critical"] and profile.decision_reversibility == "irreversible":
            return RiskTier.R4, profile

        # Rule 2: Recommendation (R3)
        # Proposing actions or interventions without mandating organizational policy
        if profile.intent == "operational_recommendation":
            return RiskTier.R3, profile

        # Rule 3: Interpretation (R2)
        # Explanatory, causal investigation, or variance decomposition
        if profile.intent == "interpretive_investigation":
            return RiskTier.R2, profile

        # Rule 4: Descriptive Analytics (R1)
        # Aggregations, rankings, or distributions across multiple rows
        if profile.intent == "descriptive_aggregation":
            return RiskTier.R1, profile

        # What-if Replay Distinction:
        # "What happens if we move to 4 days/week?" is an exploratory replay -> R1/R2, NOT R4
        if "what happens if" in profile.query_text.lower() or "simulate" in profile.query_text.lower():
            return RiskTier.R1, profile

        # Rule 5: Deterministic lookup (R0)
        # Simple point values, row count, metadata, or facts
        return RiskTier.R0, profile


class ComplexityClassifier:
    """Classifies computational and reasoning difficulty (C0–C3) independently of risk."""

    @classmethod
    def classify(cls, query: str, context: dict[str, Any] | None = None) -> ComplexityTier:
        q_lower = query.lower().strip()
        ctx = context or {}

        # C3: High-cardinality correlation, multi-metric deep search, or >10 metric matrix
        if (
            any(w in q_lower for w in ["correlated metrics", "50 metrics", "all correlations", "cross-matrix", "deep causal search", "cluster all", "anomaly matrix"])
            or re.search(r"\b\d+\s+(?:correlated\s+)?metrics\b", q_lower)
        ):
            return ComplexityTier.C3
        metric_count = ctx.get("metrics_count", 1)
        if metric_count >= 10:
            return ComplexityTier.C3

        # C2: Multi-table join, cross-department comparison, scenario replay, or headcount trade-offs
        if any(w in q_lower for w in [
            "scenario", "what-if", "simulate", "compare across all sheets", "cross-sheet",
            "trade-off", "trade off", "headcount", "restructure", "reallocation"
        ]):
            return ComplexityTier.C2
        if ctx.get("joins_required", False) or ctx.get("sheets_count", 1) > 1:
            return ComplexityTier.C2

        # C1: Standard aggregation, ranking, or filtering across 1 table
        if any(w in q_lower for w in ["rank", "average", "sum", "total", "distribution", "breakdown", "top", "bottom", "gap", "difference"]):
            return ComplexityTier.C1

        # C0: Direct point value, row count, metadata, or single scalar lookup
        return ComplexityTier.C0
