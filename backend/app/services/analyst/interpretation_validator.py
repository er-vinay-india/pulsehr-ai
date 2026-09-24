"""Deterministic Claim Validator for AI Interpretations (Phase 3A).

Verifies that AI-generated interpretations strictly adhere to verified empirical evidence:
1. Citation Integrity: All cited [FACT-XXX] exist in the verified fact pool.
2. Numeric Fidelity: Numbers in observation statements match cited facts within tolerance.
3. Polarity Neutrality: UNKNOWN/NEUTRAL polarities do not use subjective value judgements.
4. Non-Causality: Observational statements do not assert unproven causal links.
"""

import re
from typing import Any
from pydantic import BaseModel, Field

from ..data_engine.candidate_fact import CandidateFact
from ..data_engine.semantic_classifier import MetricPolarity
from .interpretation_models import InterpretationInsight, InterpretationResponse


class ToleranceConfig(BaseModel):
    absolute_percentage_tolerance: float = 0.50   # 0.5% tolerance for rounding in percentages
    relative_tolerance: float = 0.03              # 3% relative tolerance for counts/amounts
    allow_integer_rounding: bool = True           # Allow rounding to whole integers


class InsightViolation(BaseModel):
    violation_type: str
    message: str
    snippet: str | None = None
    severity: str = "ERROR"   # "ERROR" or "WARNING"


class InsightAuditReport(BaseModel):
    insight_id: str
    passed: bool
    violations: list[InsightViolation] = Field(default_factory=list)
    cited_fact_ids: list[str] = Field(default_factory=list)
    numbers_verified: list[str] = Field(default_factory=list)
    unsupported_numbers: list[str] = Field(default_factory=list)


class InterpretationAuditResult(BaseModel):
    all_passed: bool
    total_insights: int
    passed_insights: int
    total_violations: int
    reports: list[InsightAuditReport] = Field(default_factory=list)


# Evaluative sentiment vocabulary (forbidden when polarity is UNKNOWN or NEUTRAL)
EVALUATIVE_POSITIVE = {
    "improved", "improving", "improvement", "better", "outperformed",
    "outperforming", "healthy", "healthier", "favorable", "beneficial",
    "progressed", "strengthened", "advantageous"
}

EVALUATIVE_NEGATIVE = {
    "worsened", "worsening", "worse", "deteriorated", "deteriorating",
    "deterioration", "degraded", "underperformed", "underperforming",
    "unfavorable", "suffered", "critical", "alarming"
}

# Explicit causal markers (forbidden in OBSERVATION)
CAUSAL_MARKERS = [
    r'\b(caused|causing|causes|caused by)\b',
    r'\b(leads to|led to|leading to)\b',
    r'\b(driven by|drives|drive)\b',
    r'\b(due to|as a result of|resulting from|resulted in)\b',
    r'\b(triggered by|triggers|spurred by)\b'
]

# Strong conclusory claims unsupported by raw correlation/association (forbidden in observation and interpretation)
FORBIDDEN_CONCLUSORY_MARKERS = [
    r'\b(systemic issue|systemic operational vulnerability|systemic problem)\b',
    r'\b(root cause|root causes)\b',
    r'\b(sole driver|primary driver|main driver)\b',
    r'\b(proves|proven to|proves that)\b',
    r'\b(effective filtering process|effectively filters out)\b',
    r'\b(explains the|explains why)\b'
]

# Business meaning vocabulary forbidden when column semantics / domain is ambiguous
INVENTED_BUSINESS_TERMS = {
    "performance", "resource allocation", "success", "failure",
    "operational problems", "inefficiency", "profitability", "underperform"
}


class InterpretationClaimValidator:
    """Zero-LLM auditor ensuring that generated interpretations remain grounded in CandidateFacts."""

    @classmethod
    def extract_fact_citations(cls, text: str) -> list[str]:
        """Extracts [FACT-XXX] or [F-XXX] citations, including multi-citations like [FACT-012, FACT-014]."""
        citations: list[str] = []
        bracket_blocks = re.findall(r'\[(.*?)\]', text)
        for block in bracket_blocks:
            found = re.findall(r'\b(FACT-\d{3,4}|F-\d{3,4})\b', block, flags=re.IGNORECASE)
            for f in found:
                citations.append(f.upper())
        # Deduplicate preserving order
        seen = set()
        deduped = []
        for c in citations:
            if c not in seen:
                seen.add(c)
                deduped.append(c)
        return deduped

    @classmethod
    def extract_numbers(cls, text: str) -> list[dict[str, Any]]:
        """Extracts numeric quantities while stripping citations and common calendar years."""
        cleaned = re.sub(r'\[.*?\]', '', text)
        # Strip mentions of Fact IDs like "Fact 013", "Fact 009"
        cleaned = re.sub(r'\b(?:Fact|FACT|F)\s*-?\s*\d+\b', '', cleaned, flags=re.IGNORECASE)
        numbers = []

        # 1. Percentages (e.g. 81.8%, -15.5%, 1,200.5%)
        pct_matches = re.finditer(r'([+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*%', cleaned)
        for m in pct_matches:
            val = float(m.group(1).replace(',', ''))
            numbers.append({"raw": m.group(0), "val": val, "is_percentage": True, "start": m.start()})

        # 2. Currency (e.g. $125.50, $800, $2,510.00)
        curr_matches = re.finditer(r'\$\s*([+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*([KkMmBb])?', cleaned)
        for m in curr_matches:
            base_val = float(m.group(1).replace(',', ''))
            mult = 1.0
            if m.group(2):
                letter = m.group(2).upper()
                if letter == "K":
                    mult = 1000.0
                elif letter == "M":
                    mult = 1000000.0
                elif letter == "B":
                    mult = 1000000000.0
            numbers.append({"raw": m.group(0), "val": base_val * mult, "is_currency": True, "start": m.start()})

        # 3. Plain floats or counts (e.g. 10, 0.25, 4.48, 1,000)
        plain_matches = re.finditer(r'\b([+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\b', cleaned)
        for m in plain_matches:
            start, end = m.span()
            val = float(m.group(1).replace(',', ''))

            # Exclude standard year numbers
            if val.is_integer() and 1990 <= int(val) <= 2035:
                continue

            # Skip alphanumeric code tokens like M-01, ORD-0001, BATCH-001, U-004
            prefix = cleaned[max(0, start - 6):start]
            if re.search(r'[A-Za-z]+-$', prefix) or (start > 0 and cleaned[start - 1].isalnum()):
                continue
            if end < len(cleaned) and cleaned[end].isalnum():
                continue

            # Check overlap with existing currency or percentage
            overlap = False
            for exist in numbers:
                if abs(exist["start"] - start) <= len(exist["raw"]) + 2:
                    overlap = True
                    break
            if not overlap:
                numbers.append({"raw": m.group(0), "val": val, "is_plain": True, "start": start})

        return numbers

    @classmethod
    def get_admissible_numbers_from_fact(cls, fact: CandidateFact) -> list[dict[str, Any]]:
        """Collects all mathematically admissible numbers associated with a CandidateFact."""
        admissible = []

        def _add(val: float | int | None, desc: str, is_pct: bool = False):
            if val is not None and not (isinstance(val, float) and (val != val)):  # check NaN
                fval = float(val)
                admissible.append({"val": fval, "desc": desc, "is_pct": is_pct})
                if abs(fval) > 1e-6:
                    admissible.append({"val": abs(fval), "desc": f"abs_{desc}", "is_pct": is_pct})

        _add(fact.value, "value")
        _add(fact.baseline_value, "baseline_value")
        _add(fact.absolute_difference, "absolute_difference")
        _add(fact.relative_difference, "relative_difference", is_pct=True)
        _add(fact.sample_size, "sample_size")

        # Statistical info items
        if fact.statistical_info:
            for k, v in fact.statistical_info.items():
                if isinstance(v, (int, float)):
                    _add(v, f"stat_{k}")
                    # If correlation or percentage
                    if "rate" in k or "pct" in k or "share" in k:
                        _add(v * 100.0 if abs(v) <= 1.0 else v, f"stat_{k}_pct", is_pct=True)

        # Dimensions if numeric
        if fact.dimensions:
            for k, v in fact.dimensions.items():
                if isinstance(v, (int, float)):
                    _add(v, f"dim_{k}")

        return admissible

    @classmethod
    def matches_admissible_evidence(
        cls,
        num_dict: dict[str, Any],
        admissible: list[dict[str, Any]],
        tolerances: ToleranceConfig
    ) -> bool:
        """Determines if a claimed number matches any admissible evidence within tolerance."""
        claimed = num_dict["val"]
        is_pct = num_dict.get("is_percentage", False)

        for adm in admissible:
            target = adm["val"]
            adm_is_pct = adm.get("is_pct", False)

            # Exact match
            if abs(claimed - target) < 1e-4:
                return True

            # Percentage tolerance
            if is_pct or adm_is_pct:
                if abs(claimed - target) <= tolerances.absolute_percentage_tolerance:
                    return True
                # If claimed is e.g. 81.8% and target is 0.818
                if abs(claimed - target * 100.0) <= tolerances.absolute_percentage_tolerance:
                    return True

            # Relative tolerance
            if abs(target) > 1e-4:
                rel_diff = abs(claimed - target) / abs(target)
                if rel_diff <= tolerances.relative_tolerance:
                    return True

            # Integer or 1-decimal rounding
            if tolerances.allow_integer_rounding:
                if abs(round(target) - round(claimed)) == 0 and abs(claimed - target) <= 1.0:
                    return True
                if abs(round(target, 1) - round(claimed, 1)) == 0:
                    return True

        return False

    @classmethod
    def check_unsupported_intersections(
        cls,
        text: str,
        active_facts: list[CandidateFact]
    ) -> list[str]:
        """Detects if text asserts a joint intersection between dimensions from separate facts without evidence.

        Example: Combining 'Night' shift (Fact A) and 'M-01' machine (Fact B) into 'Night/M-01' or
        'Night operations on M-01' when no single fact measures both Night and M-01.
        """
        # Collect verified joint dimension pairs across all active facts
        verified_pairs: set[frozenset[str]] = set()
        all_dim_values: dict[str, str] = {}  # val_lower -> original_val

        for fact in active_facts:
            dims = fact.dimensions or {}
            vals = [str(v).strip() for v in dims.values() if v is not None and len(str(v).strip()) > 1]
            for v in vals:
                all_dim_values[v.lower()] = v
            # If a single fact has multiple dimensions, every pair within it is verified
            for i in range(len(vals)):
                for j in range(i + 1, len(vals)):
                    verified_pairs.add(frozenset([vals[i].lower(), vals[j].lower()]))

        dim_vals = list(all_dim_values.keys())
        violations = []

        for i in range(len(dim_vals)):
            for j in range(i + 1, len(dim_vals)):
                v1, v2 = dim_vals[i], dim_vals[j]
                if frozenset([v1, v2]) in verified_pairs:
                    continue  # This combination actually exists in a single fact

                # Check if text asserts a joint intersection
                patterns = [
                    rf'\b{re.escape(v1)}\s*/\s*{re.escape(v2)}\b',
                    rf'\b{re.escape(v2)}\s*/\s*{re.escape(v1)}\b',
                    rf'\b{re.escape(v1)}\s+(?:operations\s+on|running\s+on|on\s+machine|on\s+shift)\s+{re.escape(v2)}\b',
                    rf'\b{re.escape(v2)}\s+(?:operations\s+on|running\s+on|on\s+machine|on\s+shift)\s+{re.escape(v1)}\b',
                    rf'\bjoint\s+(?:configuration|impact|effect)\s+of\s+{re.escape(v1)}\s+and\s+{re.escape(v2)}\b',
                    rf'\b{re.escape(v1)}\s+and\s+{re.escape(v2)}\s+combined\b'
                ]
                for p in patterns:
                    if re.search(p, text, flags=re.IGNORECASE):
                        violations.append(
                            f"Unsupported intersection between '{all_dim_values[v1]}' and '{all_dim_values[v2]}' asserted without a joint fact."
                        )
                        break

        return violations

    @classmethod
    def audit_insight(
        cls,
        insight: InterpretationInsight,
        facts_lookup: dict[str, CandidateFact],
        tolerances: ToleranceConfig | None = None,
        profile: Any = None
    ) -> InsightAuditReport:
        """Thoroughly audits a single InterpretationInsight."""
        if tolerances is None:
            tolerances = ToleranceConfig()

        violations: list[InsightViolation] = []
        cited_ids = set(cls.extract_fact_citations(insight.observation + " " + insight.interpretation))
        for fid in insight.supporting_fact_ids:
            cited_ids.add(fid.upper())

        # 1. Check Citation Existence
        if not cited_ids:
            violations.append(InsightViolation(
                violation_type="MISSING_CITATIONS",
                message="Insight does not cite any [FACT-XXX] in observation, interpretation, or supporting_fact_ids.",
                snippet=insight.title,
                severity="ERROR"
            ))

        for fid in cited_ids:
            if fid not in facts_lookup:
                violations.append(InsightViolation(
                    violation_type="UNKNOWN_FACT_CITATION",
                    message=f"Cited fact ID '{fid}' does not exist in the candidate fact pool.",
                    snippet=fid,
                    severity="ERROR"
                ))

        # Collect admissible facts for this insight
        active_facts = [facts_lookup[fid] for fid in cited_ids if fid in facts_lookup]
        admissible_numbers: list[dict[str, Any]] = []
        for f in active_facts:
            admissible_numbers.extend(cls.get_admissible_numbers_from_fact(f))
            # Also register fact ID numeric suffix so references like "in 009" match
            fid_num = re.search(r'\d+', f.fact_id)
            if fid_num:
                admissible_numbers.append({"val": float(fid_num.group(0)), "desc": f"fact_id_{f.fact_id}"})

        # 2. Check Numbers in Observation
        obs_numbers = cls.extract_numbers(insight.observation)
        numbers_verified: list[str] = []
        unsupported_numbers: list[str] = []

        for num in obs_numbers:
            # Check against admissible numbers
            if cls.matches_admissible_evidence(num, admissible_numbers, tolerances):
                numbers_verified.append(num["raw"])
            else:
                unsupported_numbers.append(num["raw"])
                violations.append(InsightViolation(
                    violation_type="UNSUPPORTED_NUMERIC_CLAIM",
                    message=f"Number '{num['raw']}' in observation does not match any cited fact evidence.",
                    snippet=insight.observation,
                    severity="ERROR"
                ))

        # 3. Check Polarity Neutrality
        # If any cited fact has UNKNOWN or NEUTRAL polarity, check for evaluative words
        unknown_polarity_metrics = [
            f.metric for f in active_facts
            if f.polarity in (MetricPolarity.UNKNOWN, MetricPolarity.NEUTRAL)
        ]
        if unknown_polarity_metrics:
            combined_text = f"{insight.observation} {insight.interpretation}".lower()
            tokens = set(re.findall(r'\b\w+\b', combined_text))
            
            forbidden_pos = tokens.intersection(EVALUATIVE_POSITIVE)
            if forbidden_pos:
                violations.append(InsightViolation(
                    violation_type="UNSUPPORTED_POLARITY_ASSUMPTION",
                    message=f"Evaluative positive term(s) {forbidden_pos} used for metrics with UNKNOWN polarity: {unknown_polarity_metrics}",
                    snippet=str(forbidden_pos),
                    severity="ERROR"
                ))
                
            forbidden_neg = tokens.intersection(EVALUATIVE_NEGATIVE)
            if forbidden_neg:
                violations.append(InsightViolation(
                    violation_type="UNSUPPORTED_POLARITY_ASSUMPTION",
                    message=f"Evaluative negative term(s) {forbidden_neg} used for metrics with UNKNOWN polarity: {unknown_polarity_metrics}",
                    snippet=str(forbidden_neg),
                    severity="ERROR"
                ))

        # 4. Check Non-Causality in Observation
        for marker_regex in CAUSAL_MARKERS:
            match = re.search(marker_regex, insight.observation, flags=re.IGNORECASE)
            if match:
                violations.append(InsightViolation(
                    violation_type="UNSUPPORTED_CAUSAL_CLAIM",
                    message=f"Causal marker '{match.group(0)}' used in observational statement.",
                    snippet=insight.observation,
                    severity="ERROR"
                ))

        # 5. Check Conclusory / Causal Claims across Observation & Interpretation
        combined_insight_text = f"{insight.observation} {insight.interpretation}"
        for marker_regex in FORBIDDEN_CONCLUSORY_MARKERS:
            match = re.search(marker_regex, combined_insight_text, flags=re.IGNORECASE)
            if match:
                violations.append(InsightViolation(
                    violation_type="UNSUPPORTED_CONCLUSORY_CLAIM",
                    message=f"Conclusory/causal marker '{match.group(0)}' used without direct causal evidence.",
                    snippet=match.group(0),
                    severity="ERROR"
                ))

        # 6. Check Unsupported Dimension Intersections
        intersection_violations = cls.check_unsupported_intersections(combined_insight_text, active_facts)
        for iv in intersection_violations:
            violations.append(InsightViolation(
                violation_type="UNSUPPORTED_DIMENSION_INTERSECTION",
                message=iv,
                snippet=insight.title,
                severity="ERROR"
            ))

        # 7. Check Invented Business Terms on Low-Confidence / Ambiguous Datasets
        if profile is not None:
            is_ambiguous = (
                getattr(profile, "domain", "") in ("UNKNOWN", "generic", "unknown")
                or any(getattr(c, "semantic_confidence", 1.0) < 0.6 for c in getattr(profile, "columns", {}).values())
                or any(str(c).startswith("col_") or str(c).startswith("val") or str(c).startswith("flag") for c in getattr(profile, "columns", {}).keys())
            )
            if is_ambiguous:
                lower_insight = combined_insight_text.lower()
                for term in INVENTED_BUSINESS_TERMS:
                    if re.search(rf'\b{re.escape(term)}\b', lower_insight):
                        violations.append(InsightViolation(
                            violation_type="UNSUPPORTED_BUSINESS_MEANING",
                            message=f"Invented business term '{term}' used for ambiguous dataset with low semantic confidence.",
                            snippet=term,
                            severity="ERROR"
                        ))

        passed = len(violations) == 0
        return InsightAuditReport(
            insight_id=insight.insight_id,
            passed=passed,
            violations=violations,
            cited_fact_ids=list(cited_ids),
            numbers_verified=numbers_verified,
            unsupported_numbers=unsupported_numbers
        )

    @classmethod
    def audit_response(
        cls,
        response: InterpretationResponse,
        facts_lookup: dict[str, CandidateFact],
        tolerances: ToleranceConfig | None = None,
        profile: Any = None
    ) -> InterpretationAuditResult:
        """Audits all insights in an InterpretationResponse, including executive_synthesis."""
        if tolerances is None:
            tolerances = ToleranceConfig()

        reports = [
            cls.audit_insight(ins, facts_lookup, tolerances, profile=profile)
            for ins in response.insights
        ]

        # Audit Executive Synthesis
        synth_violations: list[InsightViolation] = []
        synth_text = response.executive_synthesis or ""
        synth_citations = cls.extract_fact_citations(synth_text)

        # 1. Require citations in executive_synthesis
        if not synth_citations:
            synth_violations.append(InsightViolation(
                violation_type="MISSING_CITATIONS",
                message="Executive synthesis does not cite any [FACT-XXX].",
                snippet=synth_text[:100],
                severity="ERROR"
            ))

        for fid in synth_citations:
            if fid not in facts_lookup:
                synth_violations.append(InsightViolation(
                    violation_type="UNKNOWN_FACT_CITATION",
                    message=f"Cited fact ID '{fid}' in executive synthesis does not exist in the candidate fact pool.",
                    snippet=fid,
                    severity="ERROR"
                ))

        synth_active_facts = [facts_lookup[fid] for fid in synth_citations if fid in facts_lookup]
        synth_admissible_numbers: list[dict[str, Any]] = []
        for f in synth_active_facts:
            synth_admissible_numbers.extend(cls.get_admissible_numbers_from_fact(f))
            fid_num = re.search(r'\d+', f.fact_id)
            if fid_num:
                synth_admissible_numbers.append({"val": float(fid_num.group(0)), "desc": f"fact_id_{f.fact_id}"})

        # 2. Check numbers in executive synthesis
        synth_numbers = cls.extract_numbers(synth_text)
        synth_nums_verified = []
        synth_nums_unsupported = []
        for num in synth_numbers:
            if cls.matches_admissible_evidence(num, synth_admissible_numbers, tolerances):
                synth_nums_verified.append(num["raw"])
            else:
                synth_nums_unsupported.append(num["raw"])
                synth_violations.append(InsightViolation(
                    violation_type="UNSUPPORTED_NUMERIC_CLAIM",
                    message=f"Number '{num['raw']}' in executive synthesis does not match any cited fact evidence.",
                    snippet=synth_text,
                    severity="ERROR"
                ))

        # 3. Check causal & conclusory claims in executive synthesis
        for marker_regex in CAUSAL_MARKERS:
            match = re.search(marker_regex, synth_text, flags=re.IGNORECASE)
            if match:
                synth_violations.append(InsightViolation(
                    violation_type="UNSUPPORTED_CAUSAL_CLAIM",
                    message=f"Causal marker '{match.group(0)}' used in executive synthesis.",
                    snippet=synth_text,
                    severity="ERROR"
                ))

        for marker_regex in FORBIDDEN_CONCLUSORY_MARKERS:
            match = re.search(marker_regex, synth_text, flags=re.IGNORECASE)
            if match:
                synth_violations.append(InsightViolation(
                    violation_type="UNSUPPORTED_CONCLUSORY_CLAIM",
                    message=f"Conclusory marker '{match.group(0)}' used in executive synthesis.",
                    snippet=match.group(0),
                    severity="ERROR"
                ))

        # 4. Check unsupported intersections in executive synthesis
        synth_intersection_violations = cls.check_unsupported_intersections(synth_text, synth_active_facts)
        for iv in synth_intersection_violations:
            synth_violations.append(InsightViolation(
                violation_type="UNSUPPORTED_DIMENSION_INTERSECTION",
                message=iv,
                snippet=synth_text[:100],
                severity="ERROR"
            ))

        # 5. Check ambiguous business terms in executive synthesis
        if profile is not None:
            is_ambiguous = (
                getattr(profile, "domain", "") in ("UNKNOWN", "generic", "unknown")
                or any(getattr(c, "semantic_confidence", 1.0) < 0.6 for c in getattr(profile, "columns", {}).values())
                or any(str(c).startswith("col_") or str(c).startswith("val") or str(c).startswith("flag") for c in getattr(profile, "columns", {}).keys())
            )
            if is_ambiguous:
                lower_synth = synth_text.lower()
                for term in INVENTED_BUSINESS_TERMS:
                    if re.search(rf'\b{re.escape(term)}\b', lower_synth):
                        synth_violations.append(InsightViolation(
                            violation_type="UNSUPPORTED_BUSINESS_MEANING",
                            message=f"Invented business term '{term}' used in executive synthesis for ambiguous dataset with low semantic confidence.",
                            snippet=term,
                            severity="ERROR"
                        ))

        synth_report = InsightAuditReport(
            insight_id="EXECUTIVE_SYNTHESIS",
            passed=len(synth_violations) == 0,
            violations=synth_violations,
            cited_fact_ids=list(synth_citations),
            numbers_verified=synth_nums_verified,
            unsupported_numbers=synth_nums_unsupported
        )
        reports.insert(0, synth_report)

        total = len(reports)
        passed = sum(1 for r in reports if r.passed)
        total_viol = sum(len(r.violations) for r in reports)

        return InterpretationAuditResult(
            all_passed=(passed == total and total > 0),
            total_insights=total,
            passed_insights=passed,
            total_violations=total_viol,
            reports=reports
        )
