"""
HighView Semantic Data Refinery — Phase SDR-6
Controlled Expression Engine & Unit/Ratio Governance

Evaluates typed ControlledExpression ASTs without raw SQL generation.
Enforces:
1. Unit compatibility (blocks e.g. USD + hours).
2. Ratio aggregation trap prevention (blocks AVG over ratio/percentage without denominator semantics).
3. Safe DuckDB SQL compiler using strict quote_identifier escaping.
"""

from __future__ import annotations

import re
from typing import Any, Mapping
from app.analytics.duckdb_engine import quote_identifier
from app.services.sdr.contracts.views import ControlledExpression, ExpressionOp


class UnitConflictError(ValueError):
    """Raised when an operation combines incompatible units (e.g. USD + hours)."""
    pass


class RatioAggregationTrapError(ValueError):
    """Raised when AVG is attempted on a ratio without denominator semantics."""
    pass


class GovernedExpressionCompilationError(ValueError):
    """Raised when an invalid or untyped expression is compiled."""
    pass


def validate_unit_compatibility(
    op: ExpressionOp,
    left_unit: str | None,
    right_unit: str | None,
) -> str | None:
    """
    Enforces unit governance rules across binary operations.
    Returns the resulting unit or raises UnitConflictError.
    """
    u1 = (left_unit or "").strip().lower()
    u2 = (right_unit or "").strip().lower()

    # If both empty, unitless
    if not u1 and not u2:
        return None

    if op in (ExpressionOp.ADD, ExpressionOp.SUBTRACT):
        if u1 and u2 and u1 != u2:
            raise UnitConflictError(
                f"Cannot {op.value} incompatible units: '{left_unit}' and '{right_unit}'"
            )
        return left_unit or right_unit

    if op == ExpressionOp.MULTIPLY:
        # If one is count/unitless/empty, take the other
        if not u1:
            return right_unit
        if not u2:
            return left_unit
        if u1 in ("count", "units", "qty", "quantity"):
            return right_unit
        if u2 in ("count", "units", "qty", "quantity"):
            return left_unit
        return f"{left_unit}*{right_unit}"

    if op == ExpressionOp.DIVIDE:
        if u1 == u2 and u1 != "":
            return "ratio"
        if u2 in ("count", "units", "days", "hours") and u1:
            return f"{left_unit}_per_{right_unit}"
        return "ratio" if u1 and u2 else (left_unit or right_unit)

    return left_unit or right_unit


def compile_controlled_expression_to_sql(
    expr: ControlledExpression,
    unit_metadata: Mapping[str, str] | None = None,
    ratio_columns: set[str] | None = None,
    denominator_metadata: Mapping[str, str] | None = None,
    col_qualifier_map: Mapping[str, str] | None = None,
) -> tuple[str, str | None]:
    """
    Compiles a ControlledExpression AST into a safe SQL fragment for DuckDB.
    Returns (sql_string, resolved_unit).
    Raises UnitConflictError or RatioAggregationTrapError if governance invariants fail.
    """
    units = dict(unit_metadata or {})
    ratios = set(ratio_columns or set())
    denoms = dict(denominator_metadata or {})
    qualifiers = dict(col_qualifier_map or {})

    if expr.op == ExpressionOp.COLUMN:
        if not expr.column:
            raise GovernedExpressionCompilationError("COLUMN expression missing column name")
        col_name = expr.column
        resolved_u = expr.unit or units.get(col_name)
        if col_name in qualifiers:
            return f"{qualifiers[col_name]}.{quote_identifier(col_name)}", resolved_u
        return quote_identifier(col_name), resolved_u

    if expr.op == ExpressionOp.LITERAL:
        val = expr.literal_value
        if val is None:
            return "NULL", expr.unit
        if isinstance(val, (int, float)):
            return str(val), expr.unit
        # Escape string literal
        escaped = str(val).replace("'", "''")
        return f"'{escaped}'", expr.unit

    if expr.op in (ExpressionOp.ADD, ExpressionOp.SUBTRACT, ExpressionOp.MULTIPLY, ExpressionOp.DIVIDE):
        if len(expr.args) != 2:
            raise GovernedExpressionCompilationError(f"{expr.op.value} requires exactly 2 arguments")
        left_sql, left_u = compile_controlled_expression_to_sql(expr.args[0], units, ratios, denoms, qualifiers)
        right_sql, right_u = compile_controlled_expression_to_sql(expr.args[1], units, ratios, denoms, qualifiers)

        res_unit = validate_unit_compatibility(expr.op, left_u, right_u)
        op_map = {
            ExpressionOp.ADD: "+",
            ExpressionOp.SUBTRACT: "-",
            ExpressionOp.MULTIPLY: "*",
            ExpressionOp.DIVIDE: "/",
        }
        symbol = op_map[expr.op]
        if expr.op == ExpressionOp.DIVIDE:
            # Null-safe division
            return f"(CASE WHEN {right_sql} IS NULL OR {right_sql} = 0 THEN NULL ELSE {left_sql} * 1.0 / {right_sql} END)", res_unit
        return f"({left_sql} {symbol} {right_sql})", res_unit

    if expr.op in (ExpressionOp.SUM, ExpressionOp.COUNT, ExpressionOp.COUNT_DISTINCT, ExpressionOp.MIN, ExpressionOp.MAX, ExpressionOp.AVG):
        if len(expr.args) != 1:
            raise GovernedExpressionCompilationError(f"{expr.op.value} requires exactly 1 argument")
        
        inner = expr.args[0]
        # Check ratio trap on AVG
        if expr.op == ExpressionOp.AVG:
            col_target = inner.column if inner.op == ExpressionOp.COLUMN else None
            is_ratio = False
            if col_target:
                if col_target in ratios:
                    is_ratio = True
                unit_val = units.get(col_target, "").lower()
                if "ratio" in unit_val or "percent" in unit_val or "%" in unit_val or "rate" in col_target.lower():
                    is_ratio = True
                if is_ratio and col_target not in denoms:
                    raise RatioAggregationTrapError(
                        f"Ratio aggregation trap: cannot calculate AVG on ratio metric '{col_target}' "
                        f"without weighted denominator semantics. Use SUM(numerator)/SUM(denominator) instead."
                    )

        inner_sql, inner_u = compile_controlled_expression_to_sql(inner, units, ratios, denoms, qualifiers)

        if expr.op == ExpressionOp.COUNT_DISTINCT:
            return f"COUNT(DISTINCT {inner_sql})", "count"
        if expr.op == ExpressionOp.COUNT:
            return f"COUNT({inner_sql})", "count"
        return f"{expr.op.value}({inner_sql})", inner_u

    raise GovernedExpressionCompilationError(f"Unsupported expression operator '{expr.op}'")


def evaluate_expression_on_row(
    expr: ControlledExpression,
    row: Mapping[str, Any],
    unit_metadata: Mapping[str, str] | None = None,
    ratio_columns: set[str] | None = None,
    denominator_metadata: Mapping[str, str] | None = None,
) -> Any:
    """
    Evaluates a ControlledExpression AST on a single dictionary row in Python.
    Preserves NULLs and validates unit compatibility.
    """
    units = dict(unit_metadata or {})
    ratios = set(ratio_columns or set())
    denoms = dict(denominator_metadata or {})

    if expr.op == ExpressionOp.COLUMN:
        return row.get(expr.column)

    if expr.op == ExpressionOp.LITERAL:
        return expr.literal_value

    if expr.op in (ExpressionOp.ADD, ExpressionOp.SUBTRACT, ExpressionOp.MULTIPLY, ExpressionOp.DIVIDE):
        left_val = evaluate_expression_on_row(expr.args[0], row, units, ratios, denoms)
        right_val = evaluate_expression_on_row(expr.args[1], row, units, ratios, denoms)

        # Get units to validate compatibility
        _, left_u = compile_controlled_expression_to_sql(expr.args[0], units, ratios, denoms)
        _, right_u = compile_controlled_expression_to_sql(expr.args[1], units, ratios, denoms)
        validate_unit_compatibility(expr.op, left_u, right_u)

        if left_val is None or right_val is None:
            return None

        try:
            lf = float(left_val)
            rf = float(right_val)
        except (ValueError, TypeError):
            return None

        if expr.op == ExpressionOp.ADD:
            return lf + rf
        if expr.op == ExpressionOp.SUBTRACT:
            return lf - rf
        if expr.op == ExpressionOp.MULTIPLY:
            return lf * rf
        if expr.op == ExpressionOp.DIVIDE:
            return None if rf == 0 else (lf / rf)

    raise NotImplementedError(f"Row-level evaluation not implemented for op {expr.op}")
