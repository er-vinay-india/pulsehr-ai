"""Data Profiling and Multi-Role Semantic Typing Engine (Stages 1 & 2).

Determines physical datatypes, statistical moments (mean, median, variance, min/max),
morphological patterns, detected scientific/measurement units, and multi-role semantic classifications.
"""

from __future__ import annotations

import math
import re
from typing import Any
import numpy as np
import pandas as pd

from .models import EnrichmentColumnProfile, SemanticRole

# Unit Regex Patterns
DISTANCE_PATTERN = re.compile(r'^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(km|kilometers?|m|meters?|cm|mm|miles?|mi|ft|feet|yards?|yd)\s*$', re.IGNORECASE)
MASS_PATTERN = re.compile(r'^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(kg|kilograms?|g|grams?|mg|lbs?|pounds?|oz|ounces?|tonnes?|tons?)\s*$', re.IGNORECASE)
VOLUME_PATTERN = re.compile(r'^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(l|liters?|litres?|ml|m3|m³|gallons?|gal)\s*$', re.IGNORECASE)
SPEED_PATTERN = re.compile(r'^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(km/h|kmph|m/s|mps|mph)\s*$', re.IGNORECASE)
TIME_DURATION_PATTERN = re.compile(r'^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(seconds?|sec|s|minutes?|min|m|hours?|hrs?|h|days?|d|weeks?|w)\s*$', re.IGNORECASE)
TEMPERATURE_PATTERN = re.compile(r'^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(?:°\s*([FCKfc])|deg\s*([FCKfc])|([FCfc]|Celsius|Fahrenheit|Kelvin))\s*$', re.IGNORECASE)
PERCENTAGE_PATTERN = re.compile(r'^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*%\s*$')
CURRENCY_PATTERN = re.compile(r'^\s*([+-]?)\s*([\$€£¥₹]|USD|EUR|GBP|INR|JPY|CAD|AUD)\s*([0-9,]+(?:\.\d+)?)\s*$', re.IGNORECASE)
DATE_PATTERN = re.compile(r'^\s*\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}\s*$')

NULL_STRINGS = {
    "", "none", "null", "nan", "na", "n/a", "-", "--", "undefined",
    "nil", "#n/a", "#null!", "n.a.", "n.a", "unknown", "n/d"
}


def is_null_val(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, float) and math.isnan(val):
        return True
    s = str(val).strip().casefold()
    return s in NULL_STRINGS


class EnrichmentProfiler:
    """Profiles arbitrary tabular datasets and assigns fine-grained, multi-role semantic tags."""

    @classmethod
    def profile_dataset(cls, df: pd.DataFrame) -> dict[str, EnrichmentColumnProfile]:
        profiles: dict[str, EnrichmentColumnProfile] = {}
        for col in df.columns:
            profiles[str(col)] = cls.profile_column(str(col), df[col].tolist())
        return profiles

    @classmethod
    def profile_column(cls, col_name: str, values: list[Any]) -> EnrichmentColumnProfile:
        total_records = len(values)
        non_nulls = [v for v in values if not is_null_val(v)]
        null_count = total_records - len(non_nulls)
        null_ratio = round(null_count / max(1, total_records), 4)

        unique_vals = list(dict.fromkeys(non_nulls))
        unique_count = len(unique_vals)
        cardinality_ratio = round(unique_count / max(1, len(non_nulls)), 4) if non_nulls else 0.0

        sample_values = non_nulls[:5]

        # Frequent values calculation
        freq_dict: dict[Any, int] = {}
        for v in non_nulls:
            v_str = str(v).strip()
            freq_dict[v_str] = freq_dict.get(v_str, 0) + 1
        sorted_freq = sorted(freq_dict.items(), key=lambda x: x[1], reverse=True)[:5]
        frequent_values = [{"value": k, "count": count} for k, count in sorted_freq]

        # Pattern and Unit Detection
        detected_unit: str | None = None
        detected_pattern: str | None = None
        semantic_type = "string"
        possible_domain: str | None = None

        c_lower = col_name.lower().replace("_", " ").replace("-", " ").strip()

        # Check for numeric or string with unit
        if non_nulls:
            first_few = [str(v).strip() for v in non_nulls[:30]]
            
            # 1. Percentage check
            pct_matches = sum(1 for v in first_few if PERCENTAGE_PATTERN.match(v))
            if pct_matches / len(first_few) >= 0.7:
                detected_unit = "%"
                detected_pattern = "percentage"
                semantic_type = "percentage"
                possible_domain = "analytics"

            # 2. Currency check
            curr_matches = sum(1 for v in first_few if CURRENCY_PATTERN.match(v))
            if not detected_unit and curr_matches / len(first_few) >= 0.7:
                sample_match = next((CURRENCY_PATTERN.match(v) for v in first_few if CURRENCY_PATTERN.match(v)), None)
                curr_symbol = sample_match.group(2) if sample_match else "$"
                detected_unit = curr_symbol
                detected_pattern = "currency"
                semantic_type = "currency"
                possible_domain = "finance"

            # 3. Distance check
            dist_matches = sum(1 for v in first_few if DISTANCE_PATTERN.match(v))
            if not detected_unit and dist_matches / len(first_few) >= 0.7:
                sample_m = next((DISTANCE_PATTERN.match(v) for v in first_few if DISTANCE_PATTERN.match(v)), None)
                detected_unit = sample_m.group(2).lower() if sample_m else "km"
                detected_pattern = "distance_measurement"
                semantic_type = "distance"
                possible_domain = "transportation"

            # 4. Mass check
            mass_matches = sum(1 for v in first_few if MASS_PATTERN.match(v))
            if not detected_unit and mass_matches / len(first_few) >= 0.7:
                sample_m = next((MASS_PATTERN.match(v) for v in first_few if MASS_PATTERN.match(v)), None)
                detected_unit = sample_m.group(2).lower() if sample_m else "kg"
                detected_pattern = "mass_measurement"
                semantic_type = "mass"
                possible_domain = "physics"

            # 5. Volume check
            vol_matches = sum(1 for v in first_few if VOLUME_PATTERN.match(v))
            if not detected_unit and vol_matches / len(first_few) >= 0.7:
                sample_m = next((VOLUME_PATTERN.match(v) for v in first_few if VOLUME_PATTERN.match(v)), None)
                detected_unit = sample_m.group(2).lower() if sample_m else "l"
                detected_pattern = "volume_measurement"
                semantic_type = "volume"
                possible_domain = "physics"

            # 6. Speed check
            speed_matches = sum(1 for v in first_few if SPEED_PATTERN.match(v))
            if not detected_unit and speed_matches / len(first_few) >= 0.7:
                sample_m = next((SPEED_PATTERN.match(v) for v in first_few if SPEED_PATTERN.match(v)), None)
                detected_unit = sample_m.group(2).lower() if sample_m else "km/h"
                detected_pattern = "speed_measurement"
                semantic_type = "speed"
                possible_domain = "transportation"

            # 7. Time duration check
            dur_matches = sum(1 for v in first_few if TIME_DURATION_PATTERN.match(v))
            if not detected_unit and dur_matches / len(first_few) >= 0.7:
                sample_m = next((TIME_DURATION_PATTERN.match(v) for v in first_few if TIME_DURATION_PATTERN.match(v)), None)
                detected_unit = sample_m.group(2).lower() if sample_m else "hours"
                detected_pattern = "time_duration"
                semantic_type = "duration"
                possible_domain = "operations"

            # 8. Temperature check
            temp_matches = sum(1 for v in first_few if TEMPERATURE_PATTERN.match(v))
            if not detected_unit and temp_matches / len(first_few) >= 0.7:
                sample_m = next((TEMPERATURE_PATTERN.match(v) for v in first_few if TEMPERATURE_PATTERN.match(v)), None)
                u_code = sample_m.group(2) or sample_m.group(3) or sample_m.group(4) or "C"
                detected_unit = f"°{u_code.upper()[:1]}"
                detected_pattern = "temperature"
                semantic_type = "temperature"
                possible_domain = "physics"

            # 9. Date check
            date_matches = sum(1 for v in first_few if DATE_PATTERN.match(v))
            if not detected_unit and date_matches / len(first_few) >= 0.7:
                detected_pattern = "iso_date"
                semantic_type = "date"
                possible_domain = "temporal"

        # Check column name via UnitSystemAdapter if unit still not detected
        if not detected_unit:
            try:
                from .adapters.unit_adapter import UnitSystemAdapter
                u_adapter = UnitSystemAdapter(enabled=True)
                inferred_unit = u_adapter.detect_unit_from_name(col_name)
                if inferred_unit:
                    detected_unit = inferred_unit
                    detected_pattern = "name_inferred_unit"
                    if "usd" in inferred_unit or "eur" in inferred_unit or "inr" in inferred_unit or "currency" in inferred_unit:
                        semantic_type = "currency"
                        possible_domain = "finance"
                    elif "meter" in inferred_unit or "mile" in inferred_unit or "kilometer" in inferred_unit:
                        semantic_type = "distance"
                        possible_domain = "physics"
                    elif "gram" in inferred_unit or "pound" in inferred_unit or "kilogram" in inferred_unit:
                        semantic_type = "mass"
                        possible_domain = "physics"
                    elif "hour" in inferred_unit or "second" in inferred_unit or "minute" in inferred_unit:
                        semantic_type = "duration"
                        possible_domain = "operations"
            except Exception:
                pass

        # Statistical Moments for Numeric or Cleanable Numerics
        min_val, max_val, mean_val, median_val, variance_val, std_dev_val = None, None, None, None, None, None
        physical_type = "string"

        # Try converting to clean numeric float list
        num_floats: list[float] = []
        is_clean_numeric = False
        try:
            # Check native numbers
            if non_nulls and all(isinstance(v, (int, float, np.number)) and not isinstance(v, bool) for v in non_nulls):
                num_floats = [float(v) for v in non_nulls]
                is_clean_numeric = True
                physical_type = "int" if all(float(v).is_integer() for v in num_floats) else "float"
            elif detected_pattern in ("percentage", "currency", "distance_measurement", "mass_measurement", "volume_measurement", "speed_measurement", "time_duration", "temperature"):
                # Extract clean numbers from strings
                for v in non_nulls:
                    v_str = str(v).replace(",", "")
                    match = re.search(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)', v_str)
                    if match:
                        num_floats.append(float(match.group(0)))
                physical_type = "string_with_unit"
            else:
                # Test if raw strings parse as numbers
                parsed_nums = []
                for v in non_nulls[:100]:
                    try:
                        parsed_nums.append(float(str(v).replace(",", "")))
                    except ValueError:
                        break
                if len(parsed_nums) == len(non_nulls[:100]):
                    num_floats = [float(str(v).replace(",", "")) for v in non_nulls]
                    is_clean_numeric = True
                    physical_type = "float"
        except Exception:
            num_floats = []

        if num_floats:
            arr = np.array(num_floats, dtype=float)
            min_val = round(float(np.min(arr)), 4)
            max_val = round(float(np.max(arr)), 4)
            mean_val = round(float(np.mean(arr)), 4)
            median_val = round(float(np.median(arr)), 4)
            variance_val = round(float(np.var(arr)), 4)
            std_dev_val = round(float(np.std(arr)), 4)

        # Multi-Role Assignment (IDENTIFIER, DIMENSION, MEASURE, TIME, GEO, CATEGORY, ORDINAL, BOOLEAN, TEXT, UNIT, QUANTITY, SCIENTIFIC_MEASURE)
        roles: list[SemanticRole] = []

        # Identifier
        clean_name_key = col_name.lower().replace("_", "").replace("-", "")
        if clean_name_key.endswith("id") or clean_name_key == "id" or clean_name_key.endswith("code") or clean_name_key.endswith("key"):
            if unique_count > 0 and cardinality_ratio >= 0.8:
                roles.append(SemanticRole.IDENTIFIER)

        # Boolean
        if non_nulls and all(str(v).lower() in ("true", "false", "0", "1", "yes", "no", "t", "f") for v in non_nulls[:50]):
            roles.append(SemanticRole.BOOLEAN)
            if unique_count <= 2:
                roles.append(SemanticRole.CATEGORY)

        # Time / Date
        time_keywords = ("date", "time", "timestamp", "year", "month", "day", "quarter", "week", "hour", "dt")
        if semantic_type in ("date", "duration") or any(k in c_lower.split() for k in time_keywords):
            roles.append(SemanticRole.TIME)

        # Geo
        geo_keywords = ("country", "city", "state", "region", "zip", "postal", "lat", "latitude", "lon", "longitude", "address")
        if any(k in c_lower.split() for k in geo_keywords):
            roles.append(SemanticRole.GEO)
            roles.append(SemanticRole.DIMENSION)

        # Scientific Measure & Quantity
        scientific_types = ("distance", "mass", "volume", "speed", "temperature", "pressure", "energy")
        if semantic_type in scientific_types:
            roles.append(SemanticRole.SCIENTIFIC_MEASURE)
            roles.append(SemanticRole.QUANTITY)
            roles.append(SemanticRole.MEASURE)
            if detected_unit:
                roles.append(SemanticRole.UNIT)

        # Measure (General numeric)
        if (is_clean_numeric or num_floats) and SemanticRole.IDENTIFIER not in roles:
            if SemanticRole.MEASURE not in roles:
                roles.append(SemanticRole.MEASURE)
            if SemanticRole.QUANTITY not in roles:
                roles.append(SemanticRole.QUANTITY)

        # Dimension / Category / Text
        if physical_type in ("string", "object") and SemanticRole.SCIENTIFIC_MEASURE not in roles:
            if unique_count <= 50 or cardinality_ratio <= 0.2:
                if SemanticRole.CATEGORY not in roles:
                    roles.append(SemanticRole.CATEGORY)
                if SemanticRole.DIMENSION not in roles:
                    roles.append(SemanticRole.DIMENSION)
            else:
                roles.append(SemanticRole.TEXT)

        # If no role assigned yet
        if not roles:
            if is_clean_numeric:
                roles.append(SemanticRole.MEASURE)
            else:
                roles.append(SemanticRole.DIMENSION)

        # Refine semantic_type if generic
        if semantic_type == "string" and is_clean_numeric:
            semantic_type = "numeric"
        elif semantic_type == "string" and SemanticRole.CATEGORY in roles:
            semantic_type = "categorical"

        probable_role = roles[0].value if roles else "DIMENSION"

        return EnrichmentColumnProfile(
            column=col_name,
            original_name=col_name,
            physical_type=physical_type,
            semantic_type=semantic_type,
            roles=roles,
            null_count=null_count,
            null_ratio=null_ratio,
            unique_count=unique_count,
            cardinality=unique_count,
            min_val=min_val,
            max_val=max_val,
            mean_val=mean_val,
            median_val=median_val,
            variance=variance_val,
            std_dev=std_dev_val,
            sample_values=sample_values,
            frequent_values=frequent_values,
            pattern=detected_pattern,
            detected_unit=detected_unit,
            probable_semantic_role=probable_role,
            possible_domain=possible_domain or "general_operations",
            confidence=0.95
        )
