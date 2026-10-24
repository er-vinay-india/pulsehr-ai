"""Typed Operation and Semantic Compatibility Matrix for Feature Enrichment.

Enforces unit and domain compatibility rules:
- Prohibits dimensionally invalid operations (PERCENT + COUNT, CURRENCY + COUNT, etc.).
- Prohibits arithmetic on identifiers and ordinal keys.
- Enforces semantic interpretability: even COUNT + COUNT requires related domain concepts.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from .models import EnrichmentColumnProfile, SemanticRole

logger = logging.getLogger(__name__)


class MeasureUnitClass:
    PERCENT = "PERCENT"
    COUNT = "COUNT"
    CURRENCY = "CURRENCY"
    DENSITY = "DENSITY"
    AREA = "AREA"
    DISTANCE = "DISTANCE"
    TIME_DURATION = "TIME_DURATION"
    IDENTIFIER = "IDENTIFIER"
    UNKNOWN = "UNKNOWN"


def infer_measure_class(col_name: str, profile: EnrichmentColumnProfile | None = None) -> str:
    """Infers the physical and analytical unit class of a column."""
    c_lower = col_name.lower().replace("-", "_").replace(" ", "_")

    if profile:
        if SemanticRole.IDENTIFIER in profile.roles or SemanticRole.ORDINAL in profile.roles:
            return MeasureUnitClass.IDENTIFIER
        if profile.semantic_type == "currency" or (profile.detected_unit and profile.detected_unit in ("$", "₹", "€", "£")):
            return MeasureUnitClass.CURRENCY
        if profile.semantic_type == "percentage" or profile.detected_unit == "%":
            return MeasureUnitClass.PERCENT

    # Identifier keyword checks
    if any(t in c_lower for t in ("_id", "id_", "code", "key", "uuid", "barcode", "index", "row_no", "sr_no")):
        return MeasureUnitClass.IDENTIFIER

    # Percent / Rate
    if any(k in c_lower for k in ("pct", "percent", "percentage", "rate", "ratio", "growth", "margin", "share", "yield")):
        return MeasureUnitClass.PERCENT

    # Density
    if any(k in c_lower for k in ("density", "per_km", "per_sq_km", "per_km2", "per_sq_mi", "per_acre")):
        return MeasureUnitClass.DENSITY

    # Currency
    if any(k in c_lower for k in ("revenue", "cost", "salary", "wage", "income", "profit", "expenditure", "budget", "gdp", "price", "amount")):
        return MeasureUnitClass.CURRENCY

    # Area
    if any(k in c_lower for k in ("area", "sq_km", "km2", "sq_mi", "acres", "hectares")):
        return MeasureUnitClass.AREA

    # Distance
    if any(k in c_lower for k in ("distance", "length", "km", "miles", "meters")):
        return MeasureUnitClass.DISTANCE

    # Time duration
    if any(k in c_lower for k in ("hours", "minutes", "days", "duration", "tenure")):
        return MeasureUnitClass.TIME_DURATION

    # Count / Magnitude
    if any(k in c_lower for k in ("population", "count", "headcount", "employees", "workers", "hospitals", "schools", "cases", "units", "quantity", "number")):
        return MeasureUnitClass.COUNT

    if profile and profile.physical_type in ("int", "float"):
        return MeasureUnitClass.COUNT if profile.physical_type == "int" else MeasureUnitClass.UNKNOWN

    return MeasureUnitClass.UNKNOWN


class SemanticOperationValidator:
    """Evaluates whether an arithmetic operation between two columns is dimensionally and semantically sound."""

    @classmethod
    def validate_operation(
        cls,
        operation: str,
        col_a: str,
        col_b: str,
        profiles: dict[str, EnrichmentColumnProfile] | None = None
    ) -> tuple[bool, str, str]:
        """Returns (is_valid, trust_rating, rationale).
        
        trust_rating: "TRUSTED", "CONDITIONAL", "EXPERIMENTAL", "REJECTED"
        """
        profiles = profiles or {}
        prof_a = profiles.get(col_a)
        prof_b = profiles.get(col_b)

        class_a = infer_measure_class(col_a, prof_a)
        class_b = infer_measure_class(col_b, prof_b)

        op = operation.strip()

        # 1. Reject any operation involving IDENTIFIER
        if class_a == MeasureUnitClass.IDENTIFIER or class_b == MeasureUnitClass.IDENTIFIER:
            return False, "REJECTED", f"Arithmetic on identifier column is strictly invalid ({col_a if class_a == MeasureUnitClass.IDENTIFIER else col_b})"

        # 2. Addition and Subtraction Compatibility
        if op in ("+", "-", "add_numeric", "subtract_numeric"):
            # Percent + Non-Percent is strictly prohibited
            if (class_a == MeasureUnitClass.PERCENT and class_b != MeasureUnitClass.PERCENT) or (class_b == MeasureUnitClass.PERCENT and class_a != MeasureUnitClass.PERCENT):
                return False, "REJECTED", f"Cannot add/subtract percentage/rate ({col_a if class_a == MeasureUnitClass.PERCENT else col_b}) with absolute magnitude ({col_b if class_a == MeasureUnitClass.PERCENT else col_a})"

            # Density + Non-Density is strictly prohibited
            if (class_a == MeasureUnitClass.DENSITY and class_b != MeasureUnitClass.DENSITY) or (class_b == MeasureUnitClass.DENSITY and class_a != MeasureUnitClass.DENSITY):
                return False, "REJECTED", f"Cannot add/subtract density metric with non-density metric ({class_a} vs {class_b})"

            # Currency + Non-Currency is strictly prohibited
            if (class_a == MeasureUnitClass.CURRENCY and class_b != MeasureUnitClass.CURRENCY) or (class_b == MeasureUnitClass.CURRENCY and class_a != MeasureUnitClass.CURRENCY):
                return False, "REJECTED", f"Cannot add/subtract currency with non-currency ({class_a} vs {class_b})"

            # Even COUNT + COUNT requires semantic interpretability
            if class_a == MeasureUnitClass.COUNT and class_b == MeasureUnitClass.COUNT:
                # Disallow adding population to unrelated counts like hospitals, ranks, etc.
                if "population" in col_a.lower() or "population" in col_b.lower():
                    other_col = col_b if "population" in col_a.lower() else col_a
                    if not any(k in other_col.lower() for k in ("pop", "male", "female", "child", "citizen", "rural", "urban")):
                        return False, "REJECTED", f"Semantic mismatch: population count cannot be added to non-demographic count ({other_col})"

            return True, "TRUSTED", f"Dimensionally consistent addition/subtraction between {class_a} and {class_b}"

        # 3. Division / Ratio Compatibility
        if op in ("/", "divide_numeric", "ratio"):
            # COUNT / COUNT -> Meaningful ratio or per-capita measure
            if class_a == MeasureUnitClass.COUNT and class_b == MeasureUnitClass.COUNT:
                return True, "TRUSTED", "Valid per-capita or count ratio"

            # COUNT / AREA -> Density
            if class_a == MeasureUnitClass.COUNT and class_b == MeasureUnitClass.AREA:
                return True, "TRUSTED", "Valid population/entity density calculation"

            # CURRENCY / COUNT -> Unit economics
            if class_a == MeasureUnitClass.CURRENCY and class_b == MeasureUnitClass.COUNT:
                return True, "TRUSTED", "Valid unit cost or revenue-per-entity metric"

            # Incompatible division
            if class_a == MeasureUnitClass.PERCENT and class_b in (MeasureUnitClass.COUNT, MeasureUnitClass.AREA, MeasureUnitClass.CURRENCY):
                return False, "REJECTED", f"Cannot divide rate/percent by absolute scale ({class_b})"

            return True, "CONDITIONAL", f"Ratio operation between {class_a} and {class_b}"

        # 4. Multiplication Compatibility
        if op in ("*", "multiply_numeric"):
            # PERCENT * COUNT -> Count derivation
            if (class_a == MeasureUnitClass.PERCENT and class_b == MeasureUnitClass.COUNT) or (class_b == MeasureUnitClass.PERCENT and class_a == MeasureUnitClass.COUNT):
                return True, "TRUSTED", "Valid percentage scale of count magnitude"

            # PERCENT * CURRENCY -> Currency derivation
            if (class_a == MeasureUnitClass.PERCENT and class_b == MeasureUnitClass.CURRENCY) or (class_b == MeasureUnitClass.PERCENT and class_a == MeasureUnitClass.CURRENCY):
                return True, "TRUSTED", "Valid percentage margin of currency"

            # DENSITY * AREA -> Count
            if (class_a == MeasureUnitClass.DENSITY and class_b == MeasureUnitClass.AREA) or (class_b == MeasureUnitClass.DENSITY and class_a == MeasureUnitClass.AREA):
                return True, "TRUSTED", "Valid density integration to total count"

            # COUNT * COUNT -> Square entities (invalid)
            if class_a == MeasureUnitClass.COUNT and class_b == MeasureUnitClass.COUNT:
                return False, "REJECTED", "Multiplying two count magnitudes produces non-interpretable squared units"

            # PERCENT * PERCENT -> Invalid
            if class_a == MeasureUnitClass.PERCENT and class_b == MeasureUnitClass.PERCENT:
                return False, "REJECTED", "Multiplying two percentage rates is analytically non-interpretable"

            return True, "CONDITIONAL", f"Product operation between {class_a} and {class_b}"

        return True, "EXPERIMENTAL", "Default experimental operation"
