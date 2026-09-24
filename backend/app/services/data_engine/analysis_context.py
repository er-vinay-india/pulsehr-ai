"""Generic Analysis Context and Intent Reconciliation Engine.

Implements the user-intent-first architecture:
User Analysis Brief -> AnalysisContext -> Intent-Data Reconciliation -> Opportunity Map.
"""

from __future__ import annotations
import re
import logging
from typing import Literal, Any
from pydantic import BaseModel, Field

from .semantic_classifier import SemanticDatasetProfile

logger = logging.getLogger(__name__)

ProvenanceType = Literal["USER_EXPLICIT", "USER_INFERRED", "DATA_INFERRED", "SYSTEM_DEFAULT"]


class BusinessRule(BaseModel):
    """An explicit business rule, target threshold, or operational constraint."""
    metric: str
    operator: Literal[">=", "<=", "==", ">", "<", "!="] = ">="
    threshold: float
    evaluation_grain: str | None = None
    description: str | None = None
    source: ProvenanceType = "USER_EXPLICIT"

    @property
    def metric_name(self) -> str:
        return self.metric

    @property
    def target_value(self) -> float:
        return self.threshold


class AnalysisTarget(BaseModel):
    """A business KPI target or benchmark goal."""
    metric: str
    target_value: float
    direction: Literal["higher", "lower", "exact"] = "higher"
    description: str | None = None
    source: ProvenanceType = "USER_EXPLICIT"


class AnalysisContext(BaseModel):
    """Generic user analysis brief and reconciled business context."""
    dataset_id: int | None = None
    sheet_id: int | None = None
    user_objective: str = ""
    business_context: str | None = None
    questions_to_answer: list[str] = Field(default_factory=list)
    business_rules: list[BusinessRule] = Field(default_factory=list)
    targets: list[AnalysisTarget] = Field(default_factory=list)
    important_dimensions: list[str] = Field(default_factory=list)
    important_metrics: list[str] = Field(default_factory=list)
    known_exceptions: list[str] = Field(default_factory=list)
    preferred_output: str = "Executive report"
    mode: Literal["INTENT_DRIVEN", "DISCOVERY"] = "DISCOVERY"
    provenance: ProvenanceType = "USER_EXPLICIT"
    reconciled_mappings: dict[str, str] = Field(default_factory=dict)
    unsupported_requests: list[str] = Field(default_factory=list)

    @property
    def has_user_intent(self) -> bool:
        return self.mode == "INTENT_DRIVEN" and bool(
            self.user_objective.strip() or self.questions_to_answer or self.business_rules
        )


class IntentDataReconciler:
    """Parses free-text user analysis briefs and reconciles intent with dataset semantics."""

    @classmethod
    def _find_matching_column(cls, term: str, profile: SemanticDatasetProfile) -> str | None:
        """Finds closest matching column in dataset for a user-specified concept."""
        term_clean = term.lower().strip()
        if not term_clean:
            return None

        # 1. Exact match
        for col in profile.columns.keys():
            if col.lower() == term_clean:
                return col

        # 2. Substring match
        for col in profile.columns.keys():
            if term_clean in col.lower() or col.lower() in term_clean:
                return col

        # 3. Synonym dictionary (generic across domains)
        synonyms = {
            "department": ["dept", "division", "team", "department_name", "dept_name"],
            "employee": ["worker", "staff", "person", "emp_id", "employee_id", "emp"],
            "compliance": ["wfo_days", "wfo_compliance", "compliance_pct", "adherence", "compliance"],
            "leave": ["leave_days", "leave_count", "leaves", "absent", "absence", "time_off"],
            "sales": ["revenue", "sales_amount", "gross_sales", "amount", "income"],
            "profit": ["margin", "net_profit", "net_margin", "earnings"],
            "scrap": ["scrap_rate", "scrap_count", "waste"],
            "defect": ["defects", "defect_rate", "defect_count", "failures"],
            "customer": ["client", "account", "buyer"],
            "product": ["item", "sku", "product_name", "product_category"]
        }
        for concept, cands in synonyms.items():
            if concept in term_clean or any(c in term_clean for c in cands):
                for cand in [concept] + cands:
                    for col in profile.columns.keys():
                        if cand in col.lower():
                            return col
        return None

    @classmethod
    def _extract_business_rules(
        cls,
        text: str,
        profile: SemanticDatasetProfile
    ) -> tuple[list[BusinessRule], list[str]]:
        """Extracts deterministic business rules only when language is explicit (compulsory/must/minimum/etc.)."""
        rules: list[BusinessRule] = []
        unsupported: list[str] = []
        t_lower = text.lower()

        # Strict keyword check for mandatory intent: "must", "at least", "compulsory", "minimum", "required", ">= "
        mandatory_indicators = ["must", "at least", "compulsory", "minimum", "required", "should work", "expected to work", "threshold of"]
        is_mandatory = any(ind in t_lower for ind in mandatory_indicators)

        if is_mandatory:
            # Pattern 1: e.g. "at least 3 days", "3 days ... compulsory", "minimum 3"
            m = re.search(r'(?:at least|minimum|compulsory|required|expected to work|threshold of|>=)\s*(\d+(?:\.\d+)?)', t_lower)
            if not m:
                m = re.search(r'(\d+(?:\.\d+)?)\s*(?:days?|hours?|units?|shifts?)\s*(?:is|are)?\s*(?:compulsory|mandatory|required|minimum)', t_lower)

            if m:
                val = float(m.group(1))
                # Resolve target metric
                target_col = None
                for candidate in ["wfo", "work from office", "attendance", "days", "hours", "rate", "score"]:
                    if candidate in t_lower:
                        target_col = cls._find_matching_column(candidate, profile)
                        if target_col:
                            break

                # Fallback to first numeric measure if text indicates compliance
                if not target_col:
                    for col, cp in profile.columns.items():
                        if getattr(cp, "semantic_type", "") in ("numeric measure", "count / integer", "currency / monetary measure"):
                            target_col = col
                            break

                if target_col:
                    rules.append(BusinessRule(
                        metric=target_col,
                        operator=">=",
                        threshold=val,
                        evaluation_grain=getattr(profile, "inferred_grain", None) or getattr(profile, "primary_grain", None) or "record",
                        description=f"Minimum expected threshold of {val:g} for {target_col}",
                        source="USER_EXPLICIT"
                    ))
                else:
                    unsupported.append(f"Business rule threshold of {val:g} was requested, but no matching metric column was found.")

        return rules, unsupported

    @classmethod
    def _extract_questions(cls, text: str) -> list[str]:
        """Extracts candidate analytical questions from free text."""
        questions: list[str] = []
        # Split by periods, question marks, newlines, and bullet points
        raw_clauses = re.split(r'[?.\n;]|(?:\s*-\s*)', text)
        for clause in raw_clauses:
            cleaned = clause.strip()
            if not cleaned or len(cleaned) < 8:
                continue
            lower_c = cleaned.lower()
            # If clause looks like an inquiry or directive
            action_words = ["rank", "show", "identify", "which", "what", "compare", "evaluate", "is there", "how does", "why"]
            if any(lower_c.startswith(w) or f" {w} " in lower_c for w in action_words) or "?" in clause:
                questions.append(cleaned.capitalize())
        return questions

    @classmethod
    def parse_and_reconcile(
        cls,
        raw_text: str,
        profile: SemanticDatasetProfile,
        dataset_id: int | None = None,
        sheet_id: int | None = None,
        structured_rules: list[dict] | None = None,
        important_dimensions: list[str] | None = None,
        important_metrics: list[str] | None = None,
        preferred_output: str = "Executive report",
        business_context: str | None = None
    ) -> AnalysisContext:
        """Parses user brief, establishes concept reconciliation, and constructs AnalysisContext."""
        cleaned_text = (raw_text or "").strip()

        # If user provided nothing, fall back to pure open-ended discovery mode
        if not cleaned_text and not structured_rules and not important_dimensions and not important_metrics:
            return AnalysisContext(
                dataset_id=dataset_id,
                sheet_id=sheet_id,
                user_objective="Open-ended discovery across dataset",
                mode="DISCOVERY",
                provenance="SYSTEM_DEFAULT"
            )

        reconciled_mappings: dict[str, str] = {}
        unsupported_requests: list[str] = []

        # 1. Extract rules from text or accept structured rules
        business_rules: list[BusinessRule] = []
        if structured_rules:
            for r in structured_rules:
                metric_col = cls._find_matching_column(r.get("metric", ""), profile)
                if metric_col:
                    business_rules.append(BusinessRule(
                        metric=metric_col,
                        operator=r.get("operator", ">="),
                        threshold=float(r.get("threshold", 0)),
                        evaluation_grain=r.get("evaluation_grain") or getattr(profile, "inferred_grain", None) or getattr(profile, "primary_grain", None) or "record",
                        description=r.get("description"),
                        source="USER_EXPLICIT"
                    ))
                    reconciled_mappings[r.get("metric", "")] = metric_col
                else:
                    unsupported_requests.append(f"Specified metric '{r.get('metric')}' was not found in dataset columns.")

        # Extract text-based rules
        extracted_rules, text_unsupported = cls._extract_business_rules(cleaned_text, profile)
        for er in extracted_rules:
            # avoid duplicating if already in structured
            if not any(br.metric == er.metric and br.threshold == er.threshold for br in business_rules):
                business_rules.append(er)
                reconciled_mappings[er.metric] = er.metric
        unsupported_requests.extend(text_unsupported)

        # 2. Extract questions
        questions = cls._extract_questions(cleaned_text)

        # 3. Check for explicitly unrepresented concepts in prompt
        common_business_concepts = ["salary", "compensation", "revenue", "cost", "turnover", "attrition", "nps", "price"]
        t_lower = cleaned_text.lower()
        for concept in common_business_concepts:
            if concept in t_lower and not cls._find_matching_column(concept, profile):
                msg = f"'{concept.title()}' was requested in the analysis brief, but was not found in the uploaded dataset. That comparison cannot currently be performed."
                if msg not in unsupported_requests:
                    unsupported_requests.append(msg)

        # 4. Reconcile important dimensions
        reconciled_dims: list[str] = []
        if important_dimensions:
            for d in important_dimensions:
                col = cls._find_matching_column(d, profile)
                if col:
                    reconciled_dims.append(col)
                    reconciled_mappings[d] = col
                else:
                    unsupported_requests.append(f"Requested dimension '{d}' was not found in dataset.")
        else:
            # Auto-detect mentioned dimensions from prompt text
            for col, cp in profile.columns.items():
                if getattr(cp, "semantic_role", "") in ("categorical_dimension", "dimension", "categorical") or getattr(cp, "semantic_type", "") in ("low-cardinality category", "nominal category"):
                    if col.lower() in t_lower:
                        reconciled_dims.append(col)
                        reconciled_mappings[col] = col

        # 5. Reconcile important metrics
        reconciled_metrics: list[str] = []
        if important_metrics:
            for m in important_metrics:
                col = cls._find_matching_column(m, profile)
                if col:
                    reconciled_metrics.append(col)
                    reconciled_mappings[m] = col
                else:
                    unsupported_requests.append(f"Requested metric '{m}' was not found in dataset.")
        else:
            for col, cp in profile.columns.items():
                if getattr(cp, "semantic_role", "") in ("numeric_measure", "measure", "metric") or getattr(cp, "semantic_type", "") in ("numeric measure", "percentage / rate", "count / integer"):
                    if col.lower() in t_lower:
                        reconciled_metrics.append(col)
                        reconciled_mappings[col] = col

        return AnalysisContext(
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            user_objective=cleaned_text if cleaned_text else "Intent-driven analysis",
            business_context=business_context,
            questions_to_answer=questions,
            business_rules=business_rules,
            important_dimensions=list(dict.fromkeys(reconciled_dims)),
            important_metrics=list(dict.fromkeys(reconciled_metrics)),
            preferred_output=preferred_output,
            mode="INTENT_DRIVEN",
            provenance="USER_EXPLICIT",
            reconciled_mappings=reconciled_mappings,
            unsupported_requests=unsupported_requests
        )
