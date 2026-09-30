"""
Unit System Adapter using Pint for dimensional analysis and unit validation.
Enforces physical and scientific correctness in derived features.
"""

from typing import Optional, Tuple, Dict, Any
import logging
import re
import pandas as pd

logger = logging.getLogger(__name__)

# Lazy singleton for Pint UnitRegistry
_ureg = None

def get_unit_registry():
    global _ureg
    if _ureg is None:
        try:
            import pint
            _ureg = pint.UnitRegistry(autoconvert_offset_to_baseunit=True)
            # Define common business units if not present
            try:
                _ureg.define("usd = [currency] = dollar")
                _ureg.define("eur = [currency] = euro")
                _ureg.define("gbp = [currency] = pound")
                _ureg.define("inr = [currency] = rupee")
                _ureg.define("item = [count] = unit")
                _ureg.define("employee = [count]")
                _ureg.define("customer = [count]")
            except Exception:
                pass
        except Exception as e:
            logger.warning("Pint failed to initialize: %s", e)
            _ureg = None
    return _ureg


class UnitSystemAdapter:
    """
    Adapter providing dimensional consistency checks, unit inference,
    and physical dimension derivation for candidate features.
    """

    # Common regex patterns to infer units from column names
    UNIT_SUFFIX_PATTERNS = [
        (r'_(kg|kilograms?|kgs)$', 'kilogram'),
        (r'_(g|grams?)$', 'gram'),
        (r'_(lbs?|pounds?)$', 'pound'),
        (r'_(km|kilometers?)$', 'kilometer'),
        (r'_(m|meters?)$', 'meter'),
        (r'_(cm|centimeters?)$', 'centimeter'),
        (r'_(mm|millimeters?)$', 'millimeter'),
        (r'_(miles?|mi)$', 'mile'),
        (r'_(feet|ft)$', 'foot'),
        (r'_(inches|in)$', 'inch'),
        (r'_(hours?|hrs?|hr|h)$', 'hour'),
        (r'_(minutes?|mins?|min|m)$', 'minute'),
        (r'_(seconds?|secs?|sec|s)$', 'second'),
        (r'_(days?|d)$', 'day'),
        (r'_(weeks?|wk)$', 'week'),
        (r'_(months?|mo)$', 'month'),
        (r'_(years?|yrs?|yr|y)$', 'year'),
        (r'_(usd|\$|dollars?)$', 'usd'),
        (r'_(eur|euros?|€)$', 'eur'),
        (r'_(inr|rs|rupees?|₹)$', 'inr'),
        (r'_(celsius|deg_c|c)$', 'degC'),
        (r'_(fahrenheit|deg_f|f)$', 'degF'),
        (r'_(kelvin|k)$', 'kelvin'),
        (r'_(liters?|l)$', 'liter'),
        (r'_(ml|milliliters?)$', 'milliliter'),
        (r'_(m2|sq_meters?|sqm)$', 'meter**2'),
        (r'_(m3|cubic_meters?)$', 'meter**3'),
        (r'_(kph|kmh|km_per_hr)$', 'kilometer / hour'),
        (r'_(mph|miles_per_hr)$', 'mile / hour'),
        (r'_(mps|m_per_s)$', 'meter / second'),
        (r'_(percent|pct|percentage)$', 'percent'),
    ]

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.ureg = get_unit_registry() if enabled else None

    def detect_unit_from_name(self, column_name: str) -> Optional[str]:
        """Infers physical/business unit from column name suffixes."""
        if not column_name:
            return None
        name_lower = column_name.lower().strip()
        for pattern, unit_name in self.UNIT_SUFFIX_PATTERNS:
            if re.search(pattern, name_lower):
                return unit_name
        return None

    def get_dimensionality(self, unit_str: Optional[str]) -> Optional[str]:
        """Returns the base dimensional representation of a unit string, e.g. [length]/[time]."""
        if not self.enabled or not self.ureg or not unit_str:
            return None
        try:
            qty = self.ureg(unit_str)
            return str(qty.dimensionality)
        except Exception:
            return None

    def are_compatible(self, unit_a: Optional[str], unit_b: Optional[str]) -> bool:
        """
        Returns True if two units share the same physical dimensions
        (meaning they can be added, subtracted, or compared).
        """
        if not self.enabled or not self.ureg:
            return True  # If unit engine disabled, do not block
        if not unit_a or not unit_b:
            return True  # Cannot prove incompatibility if units unknown
        try:
            qty_a = self.ureg(unit_a)
            qty_b = self.ureg(unit_b)
            return qty_a.dimensionality == qty_b.dimensionality
        except Exception as e:
            logger.debug("Unit compatibility check failed for %s and %s: %s", unit_a, unit_b, e)
            return True

    def validate_operation(
        self,
        op: str,
        unit_a: Optional[str],
        unit_b: Optional[str]
    ) -> Tuple[bool, Optional[str], str]:
        """
        Validates whether operation `op` between `unit_a` and `unit_b` is dimensionally sound.
        Returns: (is_valid, resulting_unit, explanation)
        """
        if not self.enabled or not self.ureg:
            return True, None, "Unit engine disabled; skipped check"

        # If both are dimensionless/unknown, allow
        if not unit_a and not unit_b:
            return True, None, "Both units unspecified"

        try:
            qty_a = self.ureg(unit_a) if unit_a else self.ureg("dimensionless")
            qty_b = self.ureg(unit_b) if unit_b else self.ureg("dimensionless")

            if op in ("+", "-"):
                if unit_a and unit_b and qty_a.dimensionality != qty_b.dimensionality:
                    return (
                        False,
                        None,
                        f"Incompatible dimensions: cannot add/subtract {qty_a.dimensionality} and {qty_b.dimensionality}"
                    )
                resulting_unit = unit_a or unit_b
                return True, resulting_unit, f"Dimensionally consistent: {qty_a.dimensionality}"

            elif op == "*":
                res = qty_a * qty_b
                res_unit_str = str(res.units)
                return True, res_unit_str, f"Product dimension: {res.dimensionality}"

            elif op == "/":
                res = qty_a / qty_b
                res_unit_str = str(res.units)
                return True, res_unit_str, f"Ratio dimension: {res.dimensionality}"

            else:
                return True, None, f"Unsupported unit op {op}; skipped"

        except Exception as e:
            logger.debug("Unit operation validation error: %s", e)
            return True, None, f"Pint validation error fallback: {str(e)}"

    def convert_series(
        self,
        series: pd.Series,
        from_unit: str,
        to_unit: str
    ) -> pd.Series:
        """Converts numerical values from one compatible unit to another."""
        if not self.enabled or not self.ureg:
            return series
        try:
            factor = self.ureg.Quantity(1, from_unit).to(to_unit).magnitude
            return series * factor
        except Exception as e:
            logger.warning("Failed unit conversion from %s to %s: %s", from_unit, to_unit, e)
            return series
