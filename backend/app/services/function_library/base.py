"""Base models and definitions for the Analytical Function & Business Jargon Library.

Defines the contract for self-describing, token-optimized analytical functions,
persona jargon translations, deterministic business impact rules, and visualization bindings.
Zero-LLM arithmetic invariant is strictly enforced.
"""

from enum import Enum
from typing import Any
import re
from pydantic import BaseModel, Field

from ..data_engine.semantic_classifier import SemanticDatasetProfile, SemanticRole, MetricPolarity


class FunctionCategory(str, Enum):
    WORKFORCE_DYNAMICS = "WORKFORCE_DYNAMICS"
    FINANCIAL_IMPACT = "FINANCIAL_IMPACT"
    OPERATIONAL_VELOCITY = "OPERATIONAL_VELOCITY"
    SEGMENT_CONCENTRATION = "SEGMENT_CONCENTRATION"
    STATISTICAL_DISTRIBUTION = "STATISTICAL_DISTRIBUTION"


class ImpactType(str, Enum):
    FINANCIAL_COST = "FINANCIAL_COST"
    LOST_CAPACITY_HOURS = "LOST_CAPACITY_HOURS"
    HEADCOUNT_AT_RISK = "HEADCOUNT_AT_RISK"
    MARGIN_LEAKAGE = "MARGIN_LEAKAGE"
    OPERATIONAL_DRAG = "OPERATIONAL_DRAG"


class ImpactSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    OPPORTUNITY = "OPPORTUNITY"
    NEUTRAL = "NEUTRAL"


class JargonMapping(BaseModel):
    """Maps complex statistical and analytical terms into clear persona perspectives."""
    layman_definition: str = Field(description="Crisp 1-sentence explanation free of statistical jargon.")
    hr_perspective: str = Field(description="What HR leaders act on: burnout, retention, absence, morale.")
    finance_perspective: str = Field(description="What CFOs act on: payroll leak, replacement cost, budget overrun.")
    pm_perspective: str = Field(description="What Project Managers act on: velocity drag, missed sprint deadlines.")
    term_translations: dict[str, str] = Field(
        default_factory=dict,
        description="Direct dictionary from mathematical terms to layman equivalents."
    )

    from pydantic import model_validator

    @model_validator(mode="before")
    @classmethod
    def _map_takeaways(cls, data: Any) -> Any:
        if isinstance(data, dict):
            d = dict(data)
            if "hr_takeaway" in d and "hr_perspective" not in d:
                d["hr_perspective"] = d.pop("hr_takeaway")
            if "finance_takeaway" in d and "finance_perspective" not in d:
                d["finance_perspective"] = d.pop("finance_takeaway")
            if "pm_takeaway" in d and "pm_perspective" not in d:
                d["pm_perspective"] = d.pop("pm_takeaway")
            return d
        return data


class BusinessImpactRule(BaseModel):
    """Declarative specification for deterministic business impact translation."""
    impact_type: ImpactType
    primary_metric_name: str
    unit: str  # "$", "hours", "headcount", "days"
    formula_description: str
    default_severity: ImpactSeverity = ImpactSeverity.MODERATE


class BusinessImpactAssessment(BaseModel):
    """Deterministic, verified translation of a statistical candidate fact into real-world business currency."""
    impact_type: ImpactType
    impact_metric: str
    impact_value: float
    formatted_impact: str
    unit: str
    severity: ImpactSeverity
    formula_explanation: str
    layman_takeaway: str


class FunctionPreconditions(BaseModel):
    """Preconditions required for a dataset to admit this analytical function."""
    required_roles: list[SemanticRole] = Field(default_factory=list)
    metric_keywords: list[str] = Field(default_factory=list)
    dimension_keywords: list[str] = Field(default_factory=list)
    min_sample_size: int = 5


class VisualGrammarRecommendation(BaseModel):
    """Recommended executive visualization grammar for presentation and dashboard binding."""
    primary_visual: str  # "BREAKDOWN_TREE", "VARIANCE_WATERFALL", "IMPACT_METRIC_CARD", "PARETO_BAR"
    secondary_visual: str | None = None
    highlight_rule: str = "auto_polarity"


class AnalyticalFunctionMetadata(BaseModel):
    """Metadata container for an Analytical Function stored in the permanent registry."""
    function_id: str
    name: str
    category: FunctionCategory
    version: str = "1.0.0"
    mathematical_formula: str
    preconditions: FunctionPreconditions
    jargon_mapping: JargonMapping
    impact_rule: BusinessImpactRule
    visual_recommendation: VisualGrammarRecommendation
    compact_token_repr: str = ""
    token_cost: int = 0

    def compile_compact_token_repr(self) -> str:
        """Compiles an ultra-dense, token-optimized DSL string for LLM system prompt injection (~25-35 tokens)."""
        line = (
            f"• {self.function_id} | Math: {self.mathematical_formula} | "
            f"Impact: {self.impact_rule.impact_type.value} ({self.impact_rule.unit}) | "
            f"HR: {self.jargon_mapping.hr_perspective} | "
            f"Fin: {self.jargon_mapping.finance_perspective} | "
            f"PM: {self.jargon_mapping.pm_perspective} | "
            f"Visual: {self.visual_recommendation.primary_visual}"
        )
        self.compact_token_repr = line
        # Rough token estimate: ~1 token per 3.5 characters or word-based
        words = re.findall(r'\S+', line)
        self.token_cost = max(len(words), int(len(line) / 3.5))
        return line


class BaseAnalyticalFunction:
    """Base class for all concrete analytical functions."""
    metadata: AnalyticalFunctionMetadata

    def matches_profile(self, profile: SemanticDatasetProfile) -> bool:
        """Checks if dataset profile satisfies function preconditions."""
        if not profile or not profile.columns:
            return False

        cols = profile.columns.values()
        roles_present = {c.semantic_role for c in cols}

        for req_role in self.metadata.preconditions.required_roles:
            if req_role not in roles_present:
                return False

        if self.metadata.preconditions.metric_keywords:
            matched = False
            for c in cols:
                c_name_lower = c.name.lower()
                for kw in self.metadata.preconditions.metric_keywords:
                    if kw.lower() in c_name_lower:
                        matched = True
                        break
                if matched:
                    break
            if not matched:
                return False

        return True

    def evaluate_impact(
        self,
        fact: Any,
        df: Any,
        profile: SemanticDatasetProfile
    ) -> BusinessImpactAssessment | None:
        """Evaluates business impact deterministically without LLM arithmetic."""
        raise NotImplementedError("Subclasses must implement evaluate_impact")
