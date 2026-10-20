"""
HighView Semantic Data Refinery — Phase SDR-8
Fact Comparator & Parity Engine

Implements strict parity rules across:
- Numeric parity (compacting normalization, e.g. 1.2M == 1,200,000; float tolerance 1e-4)
- Unit parity (mismatch is critical)
- Grain parity (metric at different grains is not automatically equivalent)
- Denominator parity (ratio/rate denominator semantics preserved)
- Provenance parity (observed vs derived)
- Difference classification (UNCHANGED, EXPECTED_IMPROVEMENT, EXPECTED_DIFFERENCE, REGRESSION, UNRESOLVED)
"""

from __future__ import annotations

import math
import re
from typing import Any, Union

from app.services.sdr.shadow.contracts import (
    ComparisonClass,
    DisagreementType,
    FactComparison,
    FactIdentity,
    Severity,
)


def parse_numeric_value(val: Any) -> float | None:
    """
    Parses a numeric value from raw numbers or formatted strings like:
    '$1.2M', '1,200,000', '89.2%', '91 / 102', '14.5 hours'.
    Returns float or None if missing / non-numeric.
    Crucially: preserves 0.0 as distinct from None.
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        if math.isnan(val):
            return None
        return float(val)

    s = str(val).strip()
    if s.lower() in ("null", "none", "nan", "n/a", "unavailable", ""):
        return None

    # Handle fraction "91 / 102"
    frac_match = re.match(r"^([+-]?\d+(?:\.\d+)?)\s*/\s*([+-]?\d+(?:\.\d+)?)$", s)
    if frac_match:
        num = float(frac_match.group(1))
        denom = float(frac_match.group(2))
        return num / denom if denom != 0 else None

    # Strip currency symbols and commas
    cleaned = re.sub(r"[\$,]", "", s)

    # Handle suffix multipliers (K, M, B)
    mult = 1.0
    if cleaned.endswith(("%",)):
        cleaned = cleaned[:-1]
        mult = 0.01
    elif cleaned.upper().endswith(("M",)):
        cleaned = cleaned[:-1]
        mult = 1_000_000.0
    elif cleaned.upper().endswith(("K",)):
        cleaned = cleaned[:-1]
        mult = 1_000.0
    elif cleaned.upper().endswith(("B",)):
        cleaned = cleaned[:-1]
        mult = 1_000_000_000.0

    try:
        return float(cleaned) * mult
    except ValueError:
        # Check if first token is a number (e.g. "14.5 hours")
        tokens = cleaned.split()
        if tokens:
            try:
                return float(tokens[0]) * mult
            except ValueError:
                pass
        return None


def normalize_unit(unit: str | None) -> str:
    """Normalizes unit strings for exact parity checking."""
    if not unit:
        return "none"
    u = unit.strip().lower()
    if u in ("$", "usd", "dollar", "dollars"):
        return "usd"
    if u in ("%", "pct", "percent", "percentage", "ratio"):
        return "percentage"
    if u in ("h", "hr", "hrs", "hour", "hours"):
        return "hours"
    if u in ("d", "day", "days"):
        return "days"
    if u in ("count", "items", "rows", "records", "qty", "quantity"):
        return "count"
    return u


def normalize_grain(grain: str | None) -> str:
    """Normalizes grain representation."""
    if not grain:
        return "unknown"
    return re.sub(r"\s+", "_", grain.strip().upper())


class FactComparator:
    """
    Evaluates factual parity between V2 authoritative truth and SDR shadow facts.
    """

    @classmethod
    def compare_facts(
        cls,
        metric_id: str,
        v2_fact: FactIdentity | None,
        sdr_fact: FactIdentity | None,
        tolerance: float = 1e-4,
    ) -> FactComparison:
        """
        Compares an individual V2 fact against an SDR fact.
        """
        fact_id = f"FCMP-{metric_id}"

        # 1. SDR missing / V2 present
        if sdr_fact is None and v2_fact is not None:
            return FactComparison(
                fact_id=fact_id,
                metric_id=metric_id,
                v2_fact=v2_fact,
                sdr_fact=None,
                comparison_class=ComparisonClass.EXPECTED_DIFFERENCE,
                difference_type=DisagreementType.UNRESOLVED,
                severity=Severity.WARNING,
                numeric_match=False,
                unit_match=False,
                grain_match=False,
                denominator_match=False,
                provenance_match=False,
                rationale=f"Metric {metric_id} present in V2 but missing from SDR shadow output.",
            )

        # 2. SDR present / V2 missing (Potential EXPECTED_IMPROVEMENT)
        if v2_fact is None and sdr_fact is not None:
            # Check if SDR fact is properly governed
            is_governed_relational = (
                sdr_fact.join_plan_id is not None
                or sdr_fact.provenance_type in ("DERIVED_RELATIONAL", "DERIVED_ENRICHMENT")
            )
            comp_class = (
                ComparisonClass.EXPECTED_IMPROVEMENT
                if is_governed_relational
                else ComparisonClass.EXPECTED_DIFFERENCE
            )
            diff_type = DisagreementType.EXPECTED_FIX if is_governed_relational else DisagreementType.EXPECTED_REFACTOR
            severity = Severity.INFO

            return FactComparison(
                fact_id=fact_id,
                metric_id=metric_id,
                v2_fact=None,
                sdr_fact=sdr_fact,
                comparison_class=comp_class,
                difference_type=diff_type,
                severity=severity,
                numeric_match=True,
                unit_match=True,
                grain_match=True,
                denominator_match=True,
                provenance_match=True,
                rationale=(
                    f"SDR provides governed metric {metric_id} with provenance {sdr_fact.provenance_type} "
                    f"which V2 lacked."
                ),
            )

        # 3. Both present -> check granular parity
        assert v2_fact is not None and sdr_fact is not None

        # A. Numeric Parity
        v2_num = parse_numeric_value(v2_fact.value)
        sdr_num = parse_numeric_value(sdr_fact.value)

        # Handle None / 0.0 separation
        if v2_num is None and sdr_num is None:
            numeric_match = True
        elif v2_num is None or sdr_num is None:
            # One is missing and one is present -> mismatch!
            numeric_match = False
        else:
            numeric_match = math.isclose(v2_num, sdr_num, rel_tol=tolerance, abs_tol=tolerance)

        # B. Unit Parity
        u_v2 = normalize_unit(v2_fact.unit)
        u_sdr = normalize_unit(sdr_fact.unit)
        unit_match = (u_v2 == u_sdr) or (u_v2 == "none" and u_sdr == "none")

        # C. Grain Parity
        g_v2 = normalize_grain(v2_fact.grain)
        g_sdr = normalize_grain(sdr_fact.grain)
        # If grain is undeclared/unknown from free text, it does not force a grain conflict.
        # But if both explicitly declare grains (e.g. DEPARTMENT vs EMPLOYEE), mismatch is detected!
        if g_v2 in ("UNKNOWN", "UNDECLARED", "UNSPECIFIED") or g_sdr in ("UNKNOWN", "UNDECLARED", "UNSPECIFIED"):
            grain_match = True
        else:
            grain_match = (g_v2 == g_sdr)

        # D. Denominator Parity
        d_v2_num = parse_numeric_value(v2_fact.denominator)
        d_sdr_num = parse_numeric_value(sdr_fact.denominator)
        if d_v2_num is None and d_sdr_num is None:
            denominator_match = True
        elif d_v2_num is None or d_sdr_num is None:
            # If both are rates/percentages and one has denominator and other doesn't, check string representation
            denominator_match = (str(v2_fact.denominator).strip().lower() == str(sdr_fact.denominator).strip().lower())
        else:
            denominator_match = math.isclose(d_v2_num, d_sdr_num, rel_tol=tolerance, abs_tol=tolerance)

        # E. Provenance Parity
        # SDR must not claim derived data is observed source
        provenance_match = True
        if sdr_fact.provenance_type == "OBSERVED" and v2_fact.provenance_type != "OBSERVED":
            provenance_match = False

        # Classify divergence
        reasons = []
        if not numeric_match:
            reasons.append(f"value mismatch (V2={v2_fact.value} vs SDR={sdr_fact.value})")
        if not unit_match:
            reasons.append(f"unit mismatch (V2='{v2_fact.unit}' vs SDR='{sdr_fact.unit}')")
        if not grain_match:
            reasons.append(f"grain mismatch (V2='{v2_fact.grain}' vs SDR='{sdr_fact.grain}')")
        if not denominator_match:
            reasons.append(f"denominator mismatch (V2='{v2_fact.denominator}' vs SDR='{sdr_fact.denominator}')")
        if not provenance_match:
            reasons.append(f"provenance mismatch (V2='{v2_fact.provenance_type}' vs SDR='{sdr_fact.provenance_type}')")

        if not reasons:
            return FactComparison(
                fact_id=fact_id,
                metric_id=metric_id,
                v2_fact=v2_fact,
                sdr_fact=sdr_fact,
                comparison_class=ComparisonClass.UNCHANGED,
                difference_type=DisagreementType.EXPECTED_REFACTOR if sdr_fact.provenance_type != v2_fact.provenance_type else DisagreementType.EXPECTED_FIX,
                severity=Severity.INFO,
                numeric_match=True,
                unit_match=True,
                grain_match=True,
                denominator_match=True,
                provenance_match=True,
                rationale="Factual parity verified: value, unit, grain, denominator, and evidence align.",
            )

        # There are mismatches -> REGRESSION
        is_critical = (not numeric_match) or (not unit_match) or (not grain_match) or (not denominator_match)
        return FactComparison(
            fact_id=fact_id,
            metric_id=metric_id,
            v2_fact=v2_fact,
            sdr_fact=sdr_fact,
            comparison_class=ComparisonClass.EXPECTED_DIFFERENCE,
            difference_type=DisagreementType.REGRESSION,
            severity=Severity.CRITICAL if is_critical else Severity.WARNING,
            numeric_match=numeric_match,
            unit_match=unit_match,
            grain_match=grain_match,
            denominator_match=denominator_match,
            provenance_match=provenance_match,
            rationale=f"Factual divergence detected: {', '.join(reasons)}",
        )
