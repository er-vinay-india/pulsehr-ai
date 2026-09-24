"""Deterministic Claim Validator for PulseHR AI.

Performs zero-LLM factual verification of generated claims against the EvidenceStore:
- Citation & evidence integrity (verifies [F-XXX] existence)
- Quantitative figure matching with configurable metric-aware tolerances
- Directional polarity validation (numerical increase vs decrease)
- Business sentiment validation (distinguishing numerical direction from outcome sentiment)
- Detection of uncited quantitative assertions (flagged as INVALID/NEEDS_CITATION)
- Detection of ambiguous semantic/causal leaps (routed to Phi semantic critic)
"""

import re
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

from ..evidence.evidence_models import Finding
from ..evidence.evidence_store import EvidenceStore
from ..reporting.writer_agent import WrittenSection


class ClaimValidationStatus(str, Enum):
    VERIFIED = "VERIFIED"      # Fully confirmed deterministically (0 LLM calls)
    INVALID = "INVALID"        # Proven false deterministically (0 LLM calls, fails/repairs)
    AMBIGUOUS = "AMBIGUOUS"    # Requires semantic reasoning (delegated to Phi)


class ToleranceConfig(BaseModel):
    """Configurable numerical tolerances for factual verification."""
    absolute_percentage_tolerance: float = 0.25   # e.g., 22.4% vs 22.5% allowed (rounding)
    relative_tolerance: float = 0.02             # 2% relative tolerance for counts/amounts
    allow_integer_rounding: bool = True          # e.g., 76.25% rounded to 76% or 76.3%
    max_denominator_ratio_error: float = 3.0     # flags orders-of-magnitude sample distortion


class ClaimValidationResult(BaseModel):
    """Structured result returned for every audited sentence."""
    status: ClaimValidationStatus
    claim: str
    evidence_ids: list[str] = Field(default_factory=list)
    violations: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    requires_llm: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


# Directional vocabulary
NUMERICAL_INCREASE_WORDS = {
    "increase", "increased", "increases", "increasing",
    "rose", "rise", "rising",
    "grew", "grow", "growing", "growth",
    "higher", "surged", "surge", "surging",
    "climbed", "climb", "climbing",
    "jumped", "jump", "jumping",
    "up", "exceeded", "above", "outpaced"
}

NUMERICAL_DECREASE_WORDS = {
    "decrease", "decreased", "decreases", "decreasing",
    "fell", "fall", "falling",
    "dropped", "drop", "dropping",
    "declined", "decline", "declining",
    "lower", "plummeted", "down",
    "reduction", "reduced", "reducing",
    "below", "trailing", "trailed", "lacked"
}

POSITIVE_SENTIMENT_WORDS = {
    "improved", "improving", "improvement",
    "better", "outperformed", "outperforming",
    "healthy", "healthier", "favorable", "gained", "gain", "positive",
    "beneficial", "progressed", "strengthened"
}

NEGATIVE_SENTIMENT_WORDS = {
    "worsened", "worsening", "worse",
    "deteriorated", "deteriorating", "deterioration",
    "degraded", "underperformed", "underperforming",
    "unfavorable", "suffered", "negative", "lagged", "critical"
}

# Metrics where LOWER numerical value is BETTER business outcome
LOWER_IS_BETTER_KEYWORDS = {
    "turnover", "attrition", "exit", "absenteeism", "incident",
    "burnout", "cost", "risk", "gap", "defect", "error", "churn"
}

# Causal leaping markers and subjective qualitative terms
CAUSAL_MARKERS = [
    r'\b(caused|causing|causes|caused by|leads to|led to|leading to|driven by|drives|drive)\b',
    r'\b(because|because of|due to|as a result of|as a result|resulting from|resulted in)\b',
    r'\b(triggered by|triggers|impacted by|spurred by|attributed to)\b',
    r'\b(intervention improved|intervention caused|management caused)\b'
]

SUBJECTIVE_SEMANTIC_MARKERS = [
    r'\b(morale|fragile|fragility|crisis|frustrated|dissatisfaction|stress)\b',
    r'\b(underlying issue|systemic failure|toxic|alarmingly|catastrophic)\b',
    r'\b(complacent|disillusioned|burnout)\b'
]


class DeterministicClaimValidator:
    """Zero-LLM deterministic auditor for analytical claims."""

    @classmethod
    def extract_evidence_ids(cls, text: str) -> list[str]:
        """Extracts [F-XXX] or [F-XXXX] tokens."""
        matches = re.findall(r'\[(F-\d{3,4})\]', text, flags=re.IGNORECASE)
        # deduplicate preserving order
        seen = set()
        result = []
        for m in matches:
            fid = m.upper()
            if fid not in seen:
                seen.add(fid)
                result.append(fid)
        return result

    @classmethod
    def extract_numbers_from_text(cls, text: str) -> list[dict[str, Any]]:
        """Extracts numeric quantities while ignoring evidence citation tags and years."""
        # First remove citations like [F-001]
        cleaned = re.sub(r'\[F-\d{3,4}\]', '', text, flags=re.IGNORECASE)

        numbers = []

        # 1. Percentages (e.g. 22.4%, -10.45%, 15 %)
        pct_matches = re.finditer(r'([+-]?\d+(?:\.\d+)?)\s*%', cleaned)
        for m in pct_matches:
            val = float(m.group(1))
            numbers.append({"raw": m.group(0), "val": val, "is_percentage": True, "start": m.start()})

        # 2. Points / percentage points (e.g. 10.45 points, 10.45 percentage points)
        pt_matches = re.finditer(r'([+-]?\d+(?:\.\d+)?)\s*(?:percentage\s*points?|points?\b)', cleaned, flags=re.IGNORECASE)
        for m in pt_matches:
            val = float(m.group(1))
            # Don't duplicate if already found
            if not any(abs(n["val"] - val) < 1e-4 and n.get("is_percentage") for n in numbers):
                numbers.append({"raw": m.group(0), "val": val, "is_percentage": True, "start": m.start()})

        # 3. Currency (e.g. $1.2M, $450k, $500)
        curr_matches = re.finditer(r'\$\s*([+-]?\d+(?:\.\d+)?)\s*([KkMmBbTt])?', cleaned)
        for m in curr_matches:
            base_val = float(m.group(1))
            multiplier = 1.0
            mult_str = (m.group(2) or "").upper()
            if mult_str == "K":
                multiplier = 1_000.0
            elif mult_str == "M":
                multiplier = 1_000_000.0
            elif mult_str == "B":
                multiplier = 1_000_000_000.0
            numbers.append({
                "raw": m.group(0),
                "val": base_val * multiplier,
                "is_currency": True,
                "start": m.start()
            })

        # 4. Standalone floats or counts
        plain_matches = re.finditer(r'\b([+-]?\d+(?:\.\d+)?)\b', cleaned)
        for m in plain_matches:
            # Check if this match overlaps with any previously found percentage or currency
            start, end = m.span()
            val = float(m.group(1))

            # Filter out common calendar years (e.g. 2020..2030) unless specifically small float
            if val.is_integer() and 1990 <= int(val) <= 2035:
                continue

            # Check overlap
            already_covered = False
            for existing in numbers:
                if abs(existing.get("start", -100) - start) <= len(existing["raw"]) + 2:
                    already_covered = True
                    break

            if not already_covered:
                numbers.append({"raw": m.group(0), "val": val, "is_plain": True, "start": start})

        return numbers

    @classmethod
    def _is_metric_lower_is_better(cls, metric_name: str) -> bool:
        metric_lower = (metric_name or "").lower()
        return any(kw in metric_lower for kw in LOWER_IS_BETTER_KEYWORDS)

    @classmethod
    def _get_admissible_numbers(cls, finding: Finding) -> list[dict[str, Any]]:
        """Gathers all verified numbers associated with a finding."""
        admissible = []

        def _add(val: float | None, desc: str, is_pct: bool = False):
            if val is not None:
                admissible.append({"val": float(val), "desc": desc, "is_pct": is_pct})
                # Add absolute value for differences
                if "diff" in desc or "gap" in desc:
                    admissible.append({"val": abs(float(val)), "desc": f"abs_{desc}", "is_pct": is_pct})

        _add(finding.segment_value, "segment_value", is_pct=False)
        _add(finding.overall_value, "overall_value", is_pct=False)
        _add(finding.difference, "difference", is_pct=False)
        _add(finding.difference_percentage_points, "difference_percentage_points", is_pct=True)

        # Evidence references (denominators/row counts)
        if finding.evidence:
            for ev in finding.evidence:
                if ev.row_count is not None:
                    admissible.append({"val": float(ev.row_count), "desc": "sample_size/denominator", "is_pct": False})

        return admissible

    @classmethod
    def _matches_number_in_evidence(
        cls,
        num_dict: dict[str, Any],
        admissible: list[dict[str, Any]],
        tolerances: ToleranceConfig
    ) -> tuple[bool, str]:
        """Checks if a claimed number matches any admissible number in evidence within tolerance."""
        claimed = num_dict["val"]
        is_pct = num_dict.get("is_percentage", False)

        for adm in admissible:
            target = adm["val"]
            desc = adm["desc"]

            # Exact match
            if abs(claimed - target) < 1e-4:
                return True, f"Exact match with {desc} ({target})"

            # Percentage absolute tolerance
            if is_pct or adm.get("is_pct", False) or abs(target) <= 100.0:
                if abs(claimed - target) <= tolerances.absolute_percentage_tolerance:
                    return True, f"Matches {desc} ({target}) within ±{tolerances.absolute_percentage_tolerance}%"

            # Relative tolerance for counts/amounts
            if abs(target) > 1e-4:
                rel_diff = abs(claimed - target) / abs(target)
                if rel_diff <= tolerances.relative_tolerance:
                    return True, f"Matches {desc} ({target}) within relative tolerance ({rel_diff*100:.1f}%)"

            # Integer rounding tolerance
            if tolerances.allow_integer_rounding:
                if abs(round(target) - round(claimed)) == 0 and abs(claimed - target) <= 1.0:
                    return True, f"Matches {desc} ({target}) via integer rounding"
                if abs(round(target, 1) - round(claimed, 1)) == 0:
                    return True, f"Matches {desc} ({target}) via 1-decimal rounding"

        return False, f"Value {num_dict['raw']} does not match any finding figure"

    @classmethod
    def validate_claim(
        cls,
        claim: str,
        evidence_store: EvidenceStore,
        tolerances: ToleranceConfig | None = None
    ) -> ClaimValidationResult:
        """Validates a single claim deterministically against the EvidenceStore."""
        if tolerances is None:
            tolerances = ToleranceConfig()

        text = claim.strip()
        evidence_ids = cls.extract_evidence_ids(text)
        extracted_numbers = cls.extract_numbers_from_text(text)
        words = set(re.findall(r'\b[a-zA-Z]+\b', text.lower()))

        # Check 1: Uncited quantitative claim
        if extracted_numbers and not evidence_ids:
            # Contains material numbers or percentages but no evidence citation
            return ClaimValidationResult(
                status=ClaimValidationStatus.INVALID,
                claim=text,
                evidence_ids=[],
                violations=["Quantitative claim lacks evidence citation tag [F-XXX]"],
                confidence=1.0,
                requires_llm=False,
                details={"unsupported_numbers": [n["raw"] for n in extracted_numbers]}
            )

        # Check 2: Evidence integrity (check if cited finding IDs exist in EvidenceStore)
        if evidence_ids:
            missing_ids = [fid for fid in evidence_ids if evidence_store.get_finding(fid) is None]
            if missing_ids:
                return ClaimValidationResult(
                    status=ClaimValidationStatus.INVALID,
                    claim=text,
                    evidence_ids=evidence_ids,
                    violations=[f"Cited finding ID does not exist in EvidenceStore: {fid}" for fid in missing_ids],
                    confidence=1.0,
                    requires_llm=False,
                    details={"missing_ids": missing_ids}
                )

        # Retrieve valid findings cited
        findings: list[Finding] = []
        if evidence_ids:
            findings = [evidence_store.get_finding(fid) for fid in evidence_ids if evidence_store.get_finding(fid) is not None]

        # Check 3: Numerical verification
        if extracted_numbers and findings:
            all_admissible = []
            for f in findings:
                all_admissible.extend(cls._get_admissible_numbers(f))

            unmatched = []
            for n in extracted_numbers:
                matched, _ = cls._matches_number_in_evidence(n, all_admissible, tolerances)
                if not matched:
                    # Check for denominator distortion: e.g. claiming 10,000 employees when sample is 100
                    sample_sizes = [adm["val"] for adm in all_admissible if adm["desc"] == "sample_size/denominator"]
                    if sample_sizes and any(n["val"] > s * tolerances.max_denominator_ratio_error for s in sample_sizes):
                        unmatched.append(f"{n['raw']} (exceeds verified sample size {int(sample_sizes[0])})")
                    else:
                        unmatched.append(n["raw"])

            if unmatched:
                return ClaimValidationResult(
                    status=ClaimValidationStatus.INVALID,
                    claim=text,
                    evidence_ids=evidence_ids,
                    violations=[f"Unmatched numerical figure(s): {', '.join(unmatched)}"],
                    confidence=1.0,
                    requires_llm=False,
                    details={"unsupported_numbers": unmatched}
                )

        # Check 4: Directional & Business Sentiment Validation
        if findings:
            for f in findings:
                diff = f.difference if f.difference is not None else 0.0
                if diff == 0.0 and f.difference_percentage_points is not None:
                    diff = f.difference_percentage_points

                lower_is_better = cls._is_metric_lower_is_better(f.metric)

                has_increase_word = any(w in words for w in NUMERICAL_INCREASE_WORDS)
                has_decrease_word = any(w in words for w in NUMERICAL_DECREASE_WORDS)
                has_positive_sentiment = any(w in words for w in POSITIVE_SENTIMENT_WORDS)
                has_negative_sentiment = any(w in words for w in NEGATIVE_SENTIMENT_WORDS)

                # Directional check: difference is positive, but claim asserts decrease
                if diff > 0.01 and has_decrease_word and not has_increase_word:
                    return ClaimValidationResult(
                        status=ClaimValidationStatus.INVALID,
                        claim=text,
                        evidence_ids=evidence_ids,
                        violations=[
                            f"Numerical direction contradiction: claim asserts decrease, but {f.finding_id} ({f.metric}) difference is +{diff}"
                        ],
                        confidence=1.0,
                        requires_llm=False
                    )

                # Directional check: difference is negative, but claim asserts increase
                if diff < -0.01 and has_increase_word and not has_decrease_word:
                    return ClaimValidationResult(
                        status=ClaimValidationStatus.INVALID,
                        claim=text,
                        evidence_ids=evidence_ids,
                        violations=[
                            f"Numerical direction contradiction: claim asserts increase, but {f.finding_id} ({f.metric}) difference is {diff}"
                        ],
                        confidence=1.0,
                        requires_llm=False
                    )

                # Business sentiment check:
                # If metric is higher-is-better (e.g. completion rate):
                # diff < 0 means performance dropped. If claim states "improved", it contradicts sentiment!
                if not lower_is_better and diff < -0.01 and has_positive_sentiment and not has_negative_sentiment:
                    return ClaimValidationResult(
                        status=ClaimValidationStatus.INVALID,
                        claim=text,
                        evidence_ids=evidence_ids,
                        violations=[
                            f"Sentiment contradiction: metric {f.metric} underperformed baseline ({diff}), but claim asserts improvement"
                        ],
                        confidence=0.95,
                        requires_llm=False
                    )

                # If metric is lower-is-better (e.g. turnover rate):
                # diff > 0 means turnover increased (bad!). If claim states "improved", it contradicts sentiment!
                if lower_is_better and diff > 0.01 and has_positive_sentiment and not has_negative_sentiment:
                    return ClaimValidationResult(
                        status=ClaimValidationStatus.INVALID,
                        claim=text,
                        evidence_ids=evidence_ids,
                        violations=[
                            f"Sentiment contradiction: {f.metric} increased ({diff}), which is undesirable, but claim asserts improvement"
                        ],
                        confidence=0.95,
                        requires_llm=False
                    )

        # Check 5: Ambiguous Semantic / Causal Leaps
        # Check if the claim contains causal assertions or subjective extrapolations
        for pattern in CAUSAL_MARKERS:
            if re.search(pattern, text, re.IGNORECASE):
                return ClaimValidationResult(
                    status=ClaimValidationStatus.AMBIGUOUS,
                    claim=text,
                    evidence_ids=evidence_ids,
                    violations=[],
                    confidence=0.7,
                    requires_llm=True,
                    details={"ambiguity_type": "causal_claim"}
                )

        for pattern in SUBJECTIVE_SEMANTIC_MARKERS:
            if re.search(pattern, text, re.IGNORECASE):
                return ClaimValidationResult(
                    status=ClaimValidationStatus.AMBIGUOUS,
                    claim=text,
                    evidence_ids=evidence_ids,
                    violations=[],
                    confidence=0.7,
                    requires_llm=True,
                    details={"ambiguity_type": "subjective_interpretation"}
                )

        # Check 6: If there are NO citations and NO numbers (pure qualitative narrative sentence)
        if not evidence_ids and not extracted_numbers:
            # Pure qualitative sentence without numbers or citations -> AMBIGUOUS (needs semantic review)
            return ClaimValidationResult(
                status=ClaimValidationStatus.AMBIGUOUS,
                claim=text,
                evidence_ids=[],
                violations=[],
                confidence=0.6,
                requires_llm=True,
                details={"ambiguity_type": "qualitative_uncited_statement"}
            )

        # Check 7: Fast-Pass Verified!
        # Reached here: Cites valid findings, all numbers matched within tolerance, directional and sentiment polarity consistent, no causal/subjective leaps.
        return ClaimValidationResult(
            status=ClaimValidationStatus.VERIFIED,
            claim=text,
            evidence_ids=evidence_ids,
            violations=[],
            confidence=1.0,
            requires_llm=False,
            details={"match": "deterministic_fast_pass"}
        )

    @classmethod
    def validate_section(
        cls,
        section: WrittenSection,
        evidence_store: EvidenceStore,
        tolerances: ToleranceConfig | None = None
    ) -> list[ClaimValidationResult]:
        """Validates all bullet points and key takeaway in a WrittenSection."""
        results = []
        for bullet in section.bullet_points:
            res = cls.validate_claim(bullet, evidence_store, tolerances=tolerances)
            results.append(res)
        return results
