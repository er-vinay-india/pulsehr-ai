"""Primitive Feature Derivation & Morphological Normalization Engine (Stages 5 & 6).

Systematically derives canonical primitive features from dates, physical measurements,
percentages, and monetary currencies with SI base-unit standardization and budget enforcement.
"""

from __future__ import annotations

import re
from typing import Any
import pandas as pd

from .config import BudgetGuard
from .models import DerivedFeature, EnrichmentColumnProfile, SemanticRole

# Standard SI conversion factors
DISTANCE_TO_METERS = {
    "km": 1000.0, "kilometer": 1000.0, "kilometers": 1000.0,
    "m": 1.0, "meter": 1.0, "meters": 1.0,
    "cm": 0.01, "centimeter": 0.01,
    "mm": 0.001, "millimeter": 0.001,
    "mile": 1609.344, "miles": 1609.344, "mi": 1609.344,
    "ft": 0.3048, "feet": 0.3048, "foot": 0.3048,
    "yd": 0.9144, "yard": 0.9144, "yards": 0.9144
}

MASS_TO_KG = {
    "kg": 1.0, "kilogram": 1.0, "kilograms": 1.0,
    "g": 0.001, "gram": 0.001, "grams": 0.001,
    "mg": 0.000001,
    "lb": 0.45359237, "lbs": 0.45359237, "pound": 0.45359237, "pounds": 0.45359237,
    "oz": 0.028349523, "ounce": 0.028349523, "ounces": 0.028349523,
    "ton": 1000.0, "tonne": 1000.0, "tonnes": 1000.0
}

VOLUME_TO_M3 = {
    "l": 0.001, "liter": 0.001, "liters": 0.001, "litre": 0.001, "litres": 0.001,
    "ml": 0.000001, "milliliter": 0.000001,
    "m3": 1.0, "m³": 1.0,
    "gal": 0.00378541, "gallon": 0.00378541, "gallons": 0.00378541
}

SPEED_TO_MPS = {
    "km/h": 0.277778, "kmph": 0.277778,
    "m/s": 1.0, "mps": 1.0,
    "mph": 0.44704
}

DURATION_TO_SECONDS = {
    "s": 1.0, "sec": 1.0, "second": 1.0, "seconds": 1.0,
    "m": 60.0, "min": 60.0, "minute": 60.0, "minutes": 60.0,
    "h": 3600.0, "hr": 3600.0, "hrs": 3600.0, "hour": 3600.0, "hours": 3600.0,
    "d": 86400.0, "day": 86400.0, "days": 86400.0,
    "w": 604800.0, "week": 604800.0, "weeks": 604800.0
}

CURRENCY_MAP = {
    "$": "USD", "USD": "USD",
    "€": "EUR", "EUR": "EUR",
    "£": "GBP", "GBP": "GBP",
    "₹": "INR", "INR": "INR",
    "¥": "JPY", "JPY": "JPY",
    "CAD": "CAD", "AUD": "AUD"
}


class PrimitiveFeatureDeriver:
    """Extracts, decomposes, and normalizes primitive calendar, measurement, percentage, and currency features."""

    @classmethod
    def derive_primitives(
        cls,
        df: pd.DataFrame,
        profiles: dict[str, EnrichmentColumnProfile],
        budget_guard: BudgetGuard
    ) -> tuple[pd.DataFrame, list[DerivedFeature]]:
        derived_df = df.copy()
        derived_features: list[DerivedFeature] = []

        for col_name in list(df.columns):
            if not budget_guard.can_derive_column():
                break

            prof = profiles.get(col_name)
            if not prof:
                continue

            # 1. Date / Temporal Decomposition
            if prof.semantic_type == "date" or SemanticRole.TIME in prof.roles:
                cls._derive_date_features(col_name, derived_df, derived_features, budget_guard)

            # 2. Percentage Normalization
            elif prof.semantic_type == "percentage" or prof.pattern == "percentage":
                cls._derive_percentage_features(col_name, derived_df, derived_features, budget_guard)

            # 3. Currency Normalization
            elif prof.semantic_type == "currency" or prof.pattern == "currency":
                cls._derive_currency_features(col_name, derived_df, derived_features, budget_guard)

            # 4. Physical Scientific Measurements (Distance, Mass, Volume, Speed, Duration, Temperature)
            elif prof.pattern in ("distance_measurement", "mass_measurement", "volume_measurement", "speed_measurement", "time_duration", "temperature") or SemanticRole.SCIENTIFIC_MEASURE in prof.roles:
                cls._derive_measurement_features(col_name, prof, derived_df, derived_features, budget_guard)

        return derived_df, derived_features

    @classmethod
    def _derive_date_features(
        cls,
        col: str,
        df: pd.DataFrame,
        features: list[DerivedFeature],
        budget: BudgetGuard
    ):
        """Derives 7 standard temporal features: year, quarter, month, week, day, weekday, is_weekend."""
        if not budget.can_derive_column(7):
            return

        dt_series = pd.to_datetime(df[col], errors='coerce')
        if dt_series.notna().sum() / max(1, len(df)) < 0.5:
            return

        derivatives = [
            (f"{col}_year", dt_series.dt.year.astype("Int64"), "year", [SemanticRole.TIME, SemanticRole.DIMENSION]),
            (f"{col}_quarter", dt_series.dt.quarter.astype("Int64"), "quarter", [SemanticRole.TIME, SemanticRole.CATEGORY]),
            (f"{col}_month", dt_series.dt.month.astype("Int64"), "month", [SemanticRole.TIME, SemanticRole.CATEGORY]),
            (f"{col}_week", dt_series.dt.isocalendar().week.astype("Int64"), "week_number", [SemanticRole.TIME]),
            (f"{col}_day", dt_series.dt.day.astype("Int64"), "day_of_month", [SemanticRole.TIME]),
            (f"{col}_weekday", dt_series.dt.day_name().astype("string"), "weekday_name", [SemanticRole.TIME, SemanticRole.CATEGORY]),
            (f"{col}_is_weekend", dt_series.dt.weekday.isin([5, 6]).astype(int), "is_weekend_flag", [SemanticRole.BOOLEAN, SemanticRole.CATEGORY]),
        ]

        for new_name, series_val, desc, roles in derivatives:
            if not budget.can_derive_column():
                break
            df[new_name] = series_val
            budget.record_derived_columns(1)
            features.append(
                DerivedFeature(
                    name=new_name,
                    source_columns=[col],
                    derivation_type="primitive_date",
                    expression=f"extract_{desc}({col})",
                    depth=1,
                    confidence=1.0,
                    utility_score=0.90,
                    unit=None,
                    roles=roles
                )
            )

    @classmethod
    def _derive_percentage_features(
        cls,
        col: str,
        df: pd.DataFrame,
        features: list[DerivedFeature],
        budget: BudgetGuard
    ):
        """Converts percentage string (e.g. '45%') to normalized fraction (0.45)."""
        if not budget.can_derive_column():
            return

        def parse_pct(val: Any) -> float | None:
            if pd.isna(val):
                return None
            s = str(val).replace("%", "").strip()
            try:
                num = float(s)
                return round(num / 100.0, 4) if num > 1.0 else round(num, 4)
            except ValueError:
                return None

        new_name = f"{col}_ratio"
        df[new_name] = df[col].apply(parse_pct)
        budget.record_derived_columns(1)
        features.append(
            DerivedFeature(
                name=new_name,
                source_columns=[col],
                derivation_type="primitive_percentage",
                expression=f"{col} / 100",
                depth=1,
                confidence=1.0,
                utility_score=0.95,
                unit="ratio",
                roles=[SemanticRole.MEASURE, SemanticRole.QUANTITY]
            )
        )

    @classmethod
    def _derive_currency_features(
        cls,
        col: str,
        df: pd.DataFrame,
        features: list[DerivedFeature],
        budget: BudgetGuard
    ):
        """Decomposes currency (e.g. '₹3500') into amount (3500.0) and currency code ('INR')."""
        if not budget.can_derive_column(2):
            return

        amounts: list[float | None] = []
        currencies: list[str | None] = []

        for val in df[col]:
            if pd.isna(val):
                amounts.append(None)
                currencies.append(None)
                continue
            s = str(val).strip()
            match = re.search(r'([\$€£¥₹]|USD|EUR|GBP|INR|JPY|CAD|AUD)?\s*([0-9,]+(?:\.\d+)?)', s)
            if match:
                symbol = match.group(1) or "$"
                clean_num = match.group(2).replace(",", "")
                try:
                    amounts.append(float(clean_num))
                    currencies.append(CURRENCY_MAP.get(symbol.upper(), "USD"))
                except ValueError:
                    amounts.append(None)
                    currencies.append(None)
            else:
                amounts.append(None)
                currencies.append(None)

        amt_col = f"{col}_amount"
        curr_col = f"{col}_currency"

        df[amt_col] = amounts
        budget.record_derived_columns(1)
        features.append(
            DerivedFeature(
                name=amt_col,
                source_columns=[col],
                derivation_type="primitive_currency_amount",
                expression=f"extract_amount({col})",
                depth=1,
                confidence=0.99,
                utility_score=0.98,
                unit="currency_amount",
                roles=[SemanticRole.MEASURE, SemanticRole.QUANTITY]
            )
        )

        if budget.can_derive_column():
            df[curr_col] = currencies
            budget.record_derived_columns(1)
            features.append(
                DerivedFeature(
                    name=curr_col,
                    source_columns=[col],
                    derivation_type="primitive_currency_code",
                    expression=f"extract_currency_code({col})",
                    depth=1,
                    confidence=0.99,
                    utility_score=0.85,
                    unit="iso_currency",
                    roles=[SemanticRole.CATEGORY, SemanticRole.UNIT]
                )
            )

    @classmethod
    def _derive_measurement_features(
        cls,
        col: str,
        prof: EnrichmentColumnProfile,
        df: pd.DataFrame,
        features: list[DerivedFeature],
        budget: BudgetGuard
    ):
        """Extracts value, unit, and standard SI base unit from physical measurement strings (e.g. '8 km')."""
        if not budget.can_derive_column(3):
            return

        values: list[float | None] = []
        units: list[str | None] = []
        si_values: list[float | None] = []

        target_si_label = "m"
        si_converter = DISTANCE_TO_METERS

        if prof.semantic_type == "mass" or prof.pattern == "mass_measurement":
            target_si_label = "kg"
            si_converter = MASS_TO_KG
        elif prof.semantic_type == "volume" or prof.pattern == "volume_measurement":
            target_si_label = "m3"
            si_converter = VOLUME_TO_M3
        elif prof.semantic_type == "speed" or prof.pattern == "speed_measurement":
            target_si_label = "mps"
            si_converter = SPEED_TO_MPS
        elif prof.semantic_type == "duration" or prof.pattern == "time_duration":
            target_si_label = "seconds"
            si_converter = DURATION_TO_SECONDS

        for val in df[col]:
            if pd.isna(val):
                values.append(None)
                units.append(None)
                si_values.append(None)
                continue
            s = str(val).strip().lower()
            m = re.search(r'([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*([a-zA-Z°/³3]+)?', s)
            if m:
                try:
                    num = float(m.group(1))
                    u = (m.group(2) or prof.detected_unit or "").lower()
                    values.append(num)
                    units.append(u)

                    # SI conversion
                    factor = si_converter.get(u, 1.0)
                    si_values.append(round(num * factor, 4))
                except ValueError:
                    values.append(None)
                    units.append(None)
                    si_values.append(None)
            else:
                values.append(None)
                units.append(None)
                si_values.append(None)

        val_col = f"{col}_value"
        unit_col = f"{col}_unit"
        si_col = f"{col}_{target_si_label}"

        # Register value
        df[val_col] = values
        budget.record_derived_columns(1)
        features.append(
            DerivedFeature(
                name=val_col,
                source_columns=[col],
                derivation_type="primitive_measurement_value",
                expression=f"extract_numeric_value({col})",
                depth=1,
                confidence=0.98,
                utility_score=0.95,
                unit=prof.detected_unit,
                roles=[SemanticRole.MEASURE, SemanticRole.QUANTITY, SemanticRole.SCIENTIFIC_MEASURE]
            )
        )

        # Register unit
        if budget.can_derive_column():
            df[unit_col] = units
            budget.record_derived_columns(1)
            features.append(
                DerivedFeature(
                    name=unit_col,
                    source_columns=[col],
                    derivation_type="primitive_measurement_unit",
                    expression=f"extract_unit({col})",
                    depth=1,
                    confidence=0.95,
                    utility_score=0.80,
                    unit="unit_string",
                    roles=[SemanticRole.UNIT, SemanticRole.CATEGORY]
                )
            )

        # Register SI normalized base unit
        if budget.can_derive_column():
            df[si_col] = si_values
            budget.record_derived_columns(1)
            features.append(
                DerivedFeature(
                    name=si_col,
                    source_columns=[col],
                    derivation_type="primitive_si_normalized",
                    expression=f"normalize_to_si_{target_si_label}({col})",
                    depth=1,
                    confidence=0.99,
                    utility_score=0.99,
                    unit=target_si_label,
                    roles=[SemanticRole.MEASURE, SemanticRole.QUANTITY, SemanticRole.SCIENTIFIC_MEASURE]
                )
            )
