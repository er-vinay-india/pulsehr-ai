"""
Extensible Formula Registry with domain-specific packs (physics, business, operations, healthcare).
Supports dimensional validation, semantic matching, and execution safety.
"""

from typing import Dict, List, Any, Optional, Callable
import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

class FormulaDefinition:
    """Represents a validated scientific, financial, or operational formula."""

    def __init__(
        self,
        formula_id: str,
        name: str,
        category: str,
        inputs: List[Dict[str, Any]],
        output_semantic: str,
        output_unit_dim: str,
        expression_template: str,
        eval_fn: Callable[..., pd.Series],
        confidence_prior: float = 0.90,
        description: str = ""
    ):
        self.formula_id = formula_id
        self.name = name
        self.category = category
        self.inputs = inputs  # list of dicts: {'role': 'distance', 'semantic_matches': ['distance', 'km', 'meter']}
        self.output_semantic = output_semantic
        self.output_unit_dim = output_unit_dim
        self.expression_template = expression_template
        self.eval_fn = eval_fn
        self.confidence_prior = confidence_prior
        self.description = description


class FormulaRegistry:
    """
    Registry holding domain formula packs and matching candidates
    against semantic profiles and units.
    """

    def __init__(self):
        self.formulas: Dict[str, FormulaDefinition] = {}
        self._register_default_packs()

    def register(self, formula: FormulaDefinition):
        self.formulas[formula.formula_id] = formula

    def _register_default_packs(self):
        # 1. Physics & Scientific Pack
        self.register(FormulaDefinition(
            formula_id="physics_speed",
            name="Average Speed",
            category="physics",
            inputs=[
                {"name": "distance", "semantics": ["distance", "length", "kilometer", "meter", "mile"]},
                {"name": "time", "semantics": ["time", "duration", "hours", "hour", "seconds", "second", "minute"]}
            ],
            output_semantic="speed",
            output_unit_dim="[length] / [time]",
            expression_template="{distance} / {time}",
            eval_fn=lambda d, t: d / t.replace(0, np.nan),
            confidence_prior=0.95,
            description="Calculates average speed from distance and time duration"
        ))

        self.register(FormulaDefinition(
            formula_id="physics_acceleration",
            name="Acceleration",
            category="physics",
            inputs=[
                {"name": "speed", "semantics": ["speed", "velocity", "kph", "mph", "mps"]},
                {"name": "time", "semantics": ["time", "duration", "hours", "hour", "seconds", "second"]}
            ],
            output_semantic="acceleration",
            output_unit_dim="[length] / [time] ** 2",
            expression_template="{speed} / {time}",
            eval_fn=lambda s, t: s / t.replace(0, np.nan),
            confidence_prior=0.92,
            description="Calculates acceleration as rate of speed change over time"
        ))

        self.register(FormulaDefinition(
            formula_id="physics_force",
            name="Force",
            category="physics",
            inputs=[
                {"name": "mass", "semantics": ["mass", "weight", "kg", "kilogram", "gram", "lbs"]},
                {"name": "acceleration", "semantics": ["acceleration", "gravity"]}
            ],
            output_semantic="force",
            output_unit_dim="[mass] * [length] / [time] ** 2",
            expression_template="{mass} * {acceleration}",
            eval_fn=lambda m, a: m * a,
            confidence_prior=0.93,
            description="Newton's second law: Force = mass * acceleration"
        ))

        self.register(FormulaDefinition(
            formula_id="physics_kinetic_energy",
            name="Kinetic Energy",
            category="physics",
            inputs=[
                {"name": "mass", "semantics": ["mass", "weight", "kg", "kilogram"]},
                {"name": "velocity", "semantics": ["speed", "velocity", "mps", "kph"]}
            ],
            output_semantic="energy",
            output_unit_dim="[mass] * [length] ** 2 / [time] ** 2",
            expression_template="0.5 * {mass} * ({velocity} ** 2)",
            eval_fn=lambda m, v: 0.5 * m * (v ** 2),
            confidence_prior=0.90,
            description="Kinetic energy = 0.5 * mass * velocity^2"
        ))

        self.register(FormulaDefinition(
            formula_id="physics_density",
            name="Density",
            category="physics",
            inputs=[
                {"name": "mass", "semantics": ["mass", "weight", "kg", "kilogram", "gram"]},
                {"name": "volume", "semantics": ["volume", "cubic_meter", "m3", "cubic_cm", "cm3"]}
            ],
            output_semantic="density",
            output_unit_dim="[mass] / [length] ** 3",
            expression_template="{mass} / {volume}",
            eval_fn=lambda m, v: m / v.replace(0, np.nan),
            confidence_prior=0.91,
            description="Calculates mass density per unit volume"
        ))

        # 2. Business & Finance Pack
        self.register(FormulaDefinition(
            formula_id="biz_profit",
            name="Gross Profit",
            category="business",
            inputs=[
                {"name": "revenue", "semantics": ["revenue", "sales", "income", "price", "subtotal", "usd", "amount"]},
                {"name": "cost", "semantics": ["cost", "expense", "cogs", "spend"]}
            ],
            output_semantic="profit",
            output_unit_dim="[currency]",
            expression_template="{revenue} - {cost}",
            eval_fn=lambda r, c: r - c,
            confidence_prior=0.95,
            description="Calculates gross profit as revenue minus direct cost"
        ))

        self.register(FormulaDefinition(
            formula_id="biz_profit_margin",
            name="Profit Margin",
            category="business",
            inputs=[
                {"name": "profit", "semantics": ["profit", "net_income", "gross_profit", "earnings"]},
                {"name": "revenue", "semantics": ["revenue", "sales", "income", "turnover"]}
            ],
            output_semantic="profit_margin",
            output_unit_dim="dimensionless",
            expression_template="{profit} / {revenue}",
            eval_fn=lambda p, r: p / r.replace(0, np.nan),
            confidence_prior=0.94,
            description="Calculates percentage margin as profit divided by revenue"
        ))

        self.register(FormulaDefinition(
            formula_id="biz_roi",
            name="Return on Investment (ROI)",
            category="business",
            inputs=[
                {"name": "profit", "semantics": ["profit", "net_gain", "gain"]},
                {"name": "cost", "semantics": ["cost", "investment", "spend", "expense"]}
            ],
            output_semantic="roi",
            output_unit_dim="dimensionless",
            expression_template="{profit} / {cost}",
            eval_fn=lambda p, c: p / c.replace(0, np.nan),
            confidence_prior=0.92,
            description="Calculates return on investment as profit over initial cost"
        ))

        self.register(FormulaDefinition(
            formula_id="biz_aov",
            name="Average Order Value (AOV)",
            category="business",
            inputs=[
                {"name": "revenue", "semantics": ["revenue", "sales", "subtotal", "amount"]},
                {"name": "orders", "semantics": ["order_count", "transactions", "orders", "quantity", "count"]}
            ],
            output_semantic="aov",
            output_unit_dim="[currency]",
            expression_template="{revenue} / {orders}",
            eval_fn=lambda r, o: r / o.replace(0, np.nan),
            confidence_prior=0.93,
            description="Calculates average revenue per order or transaction"
        ))

        # 3. Operations & Logistics Pack
        self.register(FormulaDefinition(
            formula_id="ops_throughput",
            name="Throughput Rate",
            category="operations",
            inputs=[
                {"name": "units", "semantics": ["units", "output", "count", "items", "completed"]},
                {"name": "time", "semantics": ["duration", "hours", "time", "days", "shift_length"]}
            ],
            output_semantic="throughput",
            output_unit_dim="[count] / [time]",
            expression_template="{units} / {time}",
            eval_fn=lambda u, t: u / t.replace(0, np.nan),
            confidence_prior=0.91,
            description="Production throughput rate: processed units per time interval"
        ))

        self.register(FormulaDefinition(
            formula_id="ops_defect_rate",
            name="Defect Rate",
            category="operations",
            inputs=[
                {"name": "defects", "semantics": ["defects", "errors", "failed_units", "returns"]},
                {"name": "total", "semantics": ["total_units", "inspected", "volume", "total_count"]}
            ],
            output_semantic="defect_rate",
            output_unit_dim="dimensionless",
            expression_template="{defects} / {total}",
            eval_fn=lambda d, t: d / t.replace(0, np.nan),
            confidence_prior=0.94,
            description="Quality defect rate as defective items divided by total items"
        ))

        # 4. Healthcare & Biological Pack
        self.register(FormulaDefinition(
            formula_id="health_bmi",
            name="Body Mass Index (BMI)",
            category="healthcare",
            inputs=[
                {"name": "weight_kg", "semantics": ["weight", "kg", "mass", "body_weight"]},
                {"name": "height_m", "semantics": ["height", "meter", "stature"]}
            ],
            output_semantic="bmi",
            output_unit_dim="[mass] / [length] ** 2",
            expression_template="{weight_kg} / ({height_m} ** 2)",
            eval_fn=lambda w, h: w / (h ** 2).replace(0, np.nan),
            confidence_prior=0.96,
            description="Calculates Body Mass Index (kg/m^2)"
        ))

    def get_all(self) -> List[FormulaDefinition]:
        return list(self.formulas.values())

    def get_by_category(self, category: str) -> List[FormulaDefinition]:
        return [f for f in self.formulas.values() if f.category == category]
