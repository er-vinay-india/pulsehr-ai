"""Scientific Formula Discovery & Domain Reasoning Engine (Stages 7 & 8).

Discovers mathematically sound, dimensionally consistent physical equations,
economic margin models, symbolic regression formulas, and Featuretools synthesis
within isolated semantic column groups.
"""

from __future__ import annotations

import logging
from typing import Any, List, Dict
import numpy as np
import pandas as pd

from .config import BudgetGuard, EnrichmentConfig
from .models import DerivedFeature, EnrichmentColumnProfile, SemanticColumnGroup, SemanticRole
from .formula_registry import FormulaRegistry
from .adapters.unit_adapter import UnitSystemAdapter
from .adapters.feature_synthesis_adapter import FeatureSynthesisAdapter
from .adapters.symbolic_adapter import SymbolicRelationshipAdapter

logger = logging.getLogger(__name__)


class ScientificFormulaEngine:
    """Evaluates algebraic laws, physical dimensions, and domain formulas inside semantic groups."""

    @classmethod
    def discover_formulas(
        cls,
        df: pd.DataFrame,
        groups: list[SemanticColumnGroup],
        profiles: dict[str, EnrichmentColumnProfile],
        budget_guard: BudgetGuard,
        config: EnrichmentConfig
    ) -> tuple[pd.DataFrame, list[DerivedFeature]]:
        enriched_df = df.copy()
        discovered_features: list[DerivedFeature] = []

        registry = FormulaRegistry()
        unit_adapter = UnitSystemAdapter(enabled=config.unit_processing_enabled)
        ft_adapter = FeatureSynthesisAdapter(enabled=config.featuretools_enabled)
        sym_adapter = SymbolicRelationshipAdapter(enabled=config.symbolic_regression_enabled)

        for group in groups:
            if not budget_guard.can_derive_column():
                break

            group_cols = [c for c in group.columns if c in enriched_df.columns]
            if len(group_cols) < 2:
                continue

            candidates_evaluated = 0
            max_candidates = config.max_formula_candidates_per_group

            # 1. Extensible Formula Registry Matching
            candidates_evaluated += cls._evaluate_formula_registry(
                registry, unit_adapter, group, group_cols, enriched_df, profiles,
                discovered_features, budget_guard, max_candidates - candidates_evaluated
            )

            # 2. Physics / Motion Dynamics Formulas
            if candidates_evaluated < max_candidates and budget_guard.can_derive_column():
                candidates_evaluated += cls._evaluate_motion_formulas(
                    unit_adapter, group, group_cols, enriched_df, profiles,
                    discovered_features, budget_guard, max_candidates - candidates_evaluated
                )

            # 3. Physical & Material Properties Formulas
            if candidates_evaluated < max_candidates and budget_guard.can_derive_column():
                candidates_evaluated += cls._evaluate_physical_property_formulas(
                    unit_adapter, group, group_cols, enriched_df, profiles,
                    discovered_features, budget_guard, max_candidates - candidates_evaluated
                )

            # 4. Financial & Economic Formulas
            if candidates_evaluated < max_candidates and budget_guard.can_derive_column():
                candidates_evaluated += cls._evaluate_financial_formulas(
                    group, group_cols, enriched_df, profiles,
                    discovered_features, budget_guard, max_candidates - candidates_evaluated
                )

            # 5. Operational & Capacity Formulas
            if candidates_evaluated < max_candidates and budget_guard.can_derive_column():
                candidates_evaluated += cls._evaluate_operational_formulas(
                    group, group_cols, enriched_df, profiles,
                    discovered_features, budget_guard, max_candidates - candidates_evaluated
                )

            # 6. Featuretools Deep Feature Synthesis
            if config.featuretools_enabled and budget_guard.can_derive_column():
                cls._evaluate_featuretools_synthesis(
                    ft_adapter, group_cols, enriched_df,
                    discovered_features, budget_guard, max_features=5
                )

            # 7. Symbolic Relationship Discovery (PySR)
            if config.symbolic_regression_enabled and budget_guard.can_derive_column():
                cls._evaluate_symbolic_relationships(
                    sym_adapter, group_cols, enriched_df,
                    discovered_features, budget_guard
                )

        return enriched_df, discovered_features

    @classmethod
    def _evaluate_formula_registry(
        cls,
        registry: FormulaRegistry,
        unit_adapter: UnitSystemAdapter,
        group: SemanticColumnGroup,
        columns: list[str],
        df: pd.DataFrame,
        profiles: dict[str, EnrichmentColumnProfile],
        features: list[DerivedFeature],
        budget: BudgetGuard,
        candidate_budget: int
    ) -> int:
        """Matches domain formula packs from FormulaRegistry against group columns."""
        count = 0
        formulas = registry.get_all()

        for form in formulas:
            if count >= candidate_budget or not budget.can_derive_column():
                return count

            if len(form.inputs) != 2:
                continue

            inp_a_spec = form.inputs[0]
            inp_b_spec = form.inputs[1]

            matches_a = [
                c for c in columns
                if any(sem in c.lower() for sem in inp_a_spec["semantics"])
                or (profiles.get(c) and any(sem in profiles[c].semantic_type.lower() for sem in inp_a_spec["semantics"]))
            ]
            matches_b = [
                c for c in columns
                if any(sem in c.lower() for sem in inp_b_spec["semantics"])
                or (profiles.get(c) and any(sem in profiles[c].semantic_type.lower() for sem in inp_b_spec["semantics"]))
            ]

            for col_a in matches_a:
                for col_b in matches_b:
                    if col_a == col_b:
                        continue
                    if count >= candidate_budget or not budget.can_derive_column():
                        return count
                    count += 1

                    feat_name = f"derived_{form.formula_id}_{col_a}_and_{col_b}"
                    if feat_name in df.columns:
                        continue

                    # Dimensional analysis validation
                    u_a = profiles.get(col_a).detected_unit if profiles.get(col_a) else None
                    u_b = profiles.get(col_b).detected_unit if profiles.get(col_b) else None
                    op = "/" if "/" in form.expression_template else ("*" if "*" in form.expression_template else "-")
                    is_valid, res_unit, _ = unit_adapter.validate_operation(op, u_a, u_b)
                    if not is_valid:
                        logger.debug("Rejected formula %s for %s and %s due to dimensional incompatibility", form.formula_id, col_a, col_b)
                        continue

                    s_a = pd.to_numeric(df[col_a], errors='coerce')
                    s_b = pd.to_numeric(df[col_b], errors='coerce')
                    valid_mask = s_a.notna() & s_b.notna()
                    if op == "/":
                        valid_mask = valid_mask & (s_b != 0)

                    if valid_mask.sum() / max(1, len(df)) >= 0.5:
                        try:
                            derived_series = form.eval_fn(s_a, s_b)
                            derived_series.loc[~valid_mask] = np.nan
                            df[feat_name] = np.round(derived_series, 4)
                            budget.record_derived_columns(1)
                            features.append(
                                DerivedFeature(
                                    name=feat_name,
                                    source_columns=[col_a, col_b],
                                    derivation_type="scientific_formula",
                                    expression=form.expression_template.format(
                                        **{inp_a_spec["name"]: col_a, inp_b_spec["name"]: col_b}
                                    ),
                                    depth=2,
                                    confidence=form.confidence_prior,
                                    utility_score=form.confidence_prior,
                                    unit=res_unit or form.output_unit_dim,
                                    roles=[SemanticRole.MEASURE, SemanticRole.QUANTITY, SemanticRole.SCIENTIFIC_MEASURE]
                                )
                            )
                        except Exception as e:
                            logger.debug("Failed evaluating formula %s: %s", form.formula_id, e)

        return count

    @classmethod
    def _evaluate_motion_formulas(
        cls,
        unit_adapter: UnitSystemAdapter,
        group: SemanticColumnGroup,
        columns: list[str],
        df: pd.DataFrame,
        profiles: dict[str, EnrichmentColumnProfile],
        features: list[DerivedFeature],
        budget: BudgetGuard,
        candidate_budget: int
    ) -> int:
        """Evaluates speed = distance / time, fuel economy = distance / fuel."""
        count = 0
        dist_cols = [c for c in columns if any(k in c.lower() for k in ("dist", "km", "mile")) or (profiles.get(c) and profiles[c].semantic_type == "distance")]
        time_cols = [c for c in columns if any(k in c.lower() for k in ("time", "duration", "hour", "sec", "min")) or (profiles.get(c) and profiles[c].semantic_type == "duration")]
        fuel_cols = [c for c in columns if any(k in c.lower() for k in ("fuel", "gas", "petrol", "diesel", "consumption", "liters", "gal"))]

        # Speed = Distance / Time (strictly average speed, not velocity vector)
        for d_col in dist_cols:
            for t_col in time_cols:
                if count >= candidate_budget or not budget.can_derive_column():
                    return count
                count += 1

                feat_name = f"derived_speed_{d_col}_per_{t_col}"
                if feat_name in df.columns:
                    continue

                d_num = pd.to_numeric(df[d_col], errors='coerce')
                t_num = pd.to_numeric(df[t_col], errors='coerce')

                # Filter valid nonzero positive times
                valid_mask = (t_num > 0) & d_num.notna() & (d_num >= 0)
                if valid_mask.sum() / max(1, len(df)) >= 0.5:
                    res = pd.Series(np.nan, index=df.index, dtype=float)
                    res.loc[valid_mask] = np.round(d_num.loc[valid_mask] / t_num.loc[valid_mask], 4)
                    
                    df[feat_name] = res
                    budget.record_derived_columns(1)
                    features.append(
                        DerivedFeature(
                            name=feat_name,
                            source_columns=[d_col, t_col],
                            derivation_type="scientific_formula",
                            expression=f"{d_col} / {t_col}",
                            depth=2,
                            confidence=0.98,
                            utility_score=0.96,
                            unit="speed_ratio",
                            roles=[SemanticRole.MEASURE, SemanticRole.QUANTITY, SemanticRole.SCIENTIFIC_MEASURE]
                        )
                    )

        # Fuel Economy = Distance / Fuel
        for d_col in dist_cols:
            for f_col in fuel_cols:
                if count >= candidate_budget or not budget.can_derive_column():
                    return count
                count += 1

                feat_name = f"derived_fuel_economy_{d_col}_per_{f_col}"
                if feat_name in df.columns:
                    continue

                d_num = pd.to_numeric(df[d_col], errors='coerce')
                f_num = pd.to_numeric(df[f_col], errors='coerce')

                valid_mask = (f_num > 0) & d_num.notna() & (d_num >= 0)
                if valid_mask.sum() / max(1, len(df)) >= 0.5:
                    res = pd.Series(np.nan, index=df.index, dtype=float)
                    res.loc[valid_mask] = np.round(d_num.loc[valid_mask] / f_num.loc[valid_mask], 4)

                    df[feat_name] = res
                    budget.record_derived_columns(1)
                    features.append(
                        DerivedFeature(
                            name=feat_name,
                            source_columns=[d_col, f_col],
                            derivation_type="scientific_formula",
                            expression=f"{d_col} / {f_col}",
                            depth=2,
                            confidence=0.95,
                            utility_score=0.94,
                            unit="economy_ratio",
                            roles=[SemanticRole.MEASURE, SemanticRole.QUANTITY, SemanticRole.SCIENTIFIC_MEASURE]
                        )
                    )

        return count

    @classmethod
    def _evaluate_physical_property_formulas(
        cls,
        unit_adapter: UnitSystemAdapter,
        group: SemanticColumnGroup,
        columns: list[str],
        df: pd.DataFrame,
        profiles: dict[str, EnrichmentColumnProfile],
        features: list[DerivedFeature],
        budget: BudgetGuard,
        candidate_budget: int
    ) -> int:
        """Evaluates density = mass / volume."""
        count = 0
        mass_cols = [c for c in columns if any(k in c.lower() for k in ("mass", "weight", "kg", "gram", "lbs")) or (profiles.get(c) and profiles[c].semantic_type == "mass")]
        vol_cols = [
            c for c in columns
            if (any(k in c.lower() for k in ("vol", "volume", "m3", "cubic")) or (profiles.get(c) and profiles[c].semantic_type == "volume"))
            and not any(f in c.lower() for f in ("fuel", "consumption", "gas", "petrol"))
        ]

        for m_col in mass_cols:
            for v_col in vol_cols:
                if count >= candidate_budget or not budget.can_derive_column():
                    return count
                count += 1

                feat_name = f"derived_density_{m_col}_per_{v_col}"
                if feat_name in df.columns:
                    continue

                m_num = pd.to_numeric(df[m_col], errors='coerce')
                v_num = pd.to_numeric(df[v_col], errors='coerce')

                valid_mask = (v_num > 0) & m_num.notna() & (m_num >= 0)
                if valid_mask.sum() / max(1, len(df)) >= 0.5:
                    res = pd.Series(np.nan, index=df.index, dtype=float)
                    res.loc[valid_mask] = np.round(m_num.loc[valid_mask] / v_num.loc[valid_mask], 4)

                    df[feat_name] = res
                    budget.record_derived_columns(1)
                    features.append(
                        DerivedFeature(
                            name=feat_name,
                            source_columns=[m_col, v_col],
                            derivation_type="scientific_formula",
                            expression=f"{m_col} / {v_col}",
                            depth=2,
                            confidence=0.99,
                            utility_score=0.97,
                            unit="density",
                            roles=[SemanticRole.MEASURE, SemanticRole.QUANTITY, SemanticRole.SCIENTIFIC_MEASURE]
                        )
                    )

        return count

    @classmethod
    def _evaluate_financial_formulas(
        cls,
        group: SemanticColumnGroup,
        columns: list[str],
        df: pd.DataFrame,
        profiles: dict[str, EnrichmentColumnProfile],
        features: list[DerivedFeature],
        budget: BudgetGuard,
        candidate_budget: int
    ) -> int:
        """Evaluates profit = revenue - cost, margin = profit / revenue."""
        count = 0
        rev_cols = [c for c in columns if any(k in c.lower() for k in ("revenue", "sales", "turnover", "income", "gross"))]
        cost_cols = [c for c in columns if any(k in c.lower() for k in ("cost", "expense", "cogs", "spend", "budget"))]

        for r_col in rev_cols:
            for c_col in cost_cols:
                if count >= candidate_budget or not budget.can_derive_column():
                    return count
                count += 1

                r_num = pd.to_numeric(df[r_col], errors='coerce')
                c_num = pd.to_numeric(df[c_col], errors='coerce')

                # Profit = Revenue - Cost
                profit_col = f"derived_profit_{r_col}_minus_{c_col}"
                valid_mask = r_num.notna() & c_num.notna()
                if valid_mask.sum() / max(1, len(df)) >= 0.5:
                    profit_vals = pd.Series(np.nan, index=df.index, dtype=float)
                    profit_vals.loc[valid_mask] = np.round(r_num.loc[valid_mask] - c_num.loc[valid_mask], 2)

                    df[profit_col] = profit_vals
                    budget.record_derived_columns(1)
                    features.append(
                        DerivedFeature(
                            name=profit_col,
                            source_columns=[r_col, c_col],
                            derivation_type="scientific_formula",
                            expression=f"{r_col} - {c_col}",
                            depth=2,
                            confidence=0.99,
                            utility_score=0.99,
                            unit="currency",
                            roles=[SemanticRole.MEASURE, SemanticRole.QUANTITY]
                        )
                    )

                    # Margin = Profit / Revenue
                    if budget.can_derive_column():
                        margin_col = f"derived_margin_{profit_col}_ratio"
                        margin_mask = valid_mask & (r_num != 0)
                        if margin_mask.sum() / max(1, len(df)) >= 0.5:
                            margin_vals = pd.Series(np.nan, index=df.index, dtype=float)
                            margin_vals.loc[margin_mask] = np.round(profit_vals.loc[margin_mask] / r_num.loc[margin_mask], 4)

                            df[margin_col] = margin_vals
                            budget.record_derived_columns(1)
                            features.append(
                                DerivedFeature(
                                    name=margin_col,
                                    source_columns=[r_col, c_col],
                                    derivation_type="scientific_formula",
                                    expression=f"({r_col} - {c_col}) / {r_col}",
                                    depth=2,
                                    confidence=0.98,
                                    utility_score=0.98,
                                    unit="ratio",
                                    roles=[SemanticRole.MEASURE, SemanticRole.QUANTITY]
                                )
                            )

        return count

    @classmethod
    def _evaluate_operational_formulas(
        cls,
        group: SemanticColumnGroup,
        columns: list[str],
        df: pd.DataFrame,
        profiles: dict[str, EnrichmentColumnProfile],
        features: list[DerivedFeature],
        budget: BudgetGuard,
        candidate_budget: int
    ) -> int:
        """Evaluates operational rate ratios: overtime / base_hours, productivity = volume / headcount."""
        count = 0
        ot_cols = [c for c in columns if any(k in c.lower() for k in ("overtime", "ot_hours", "extra_hours"))]
        total_hour_cols = [c for c in columns if any(k in c.lower() for k in ("regular_hours", "base_hours", "scheduled_hours", "total_hours"))]

        for ot in ot_cols:
            for th in total_hour_cols:
                if count >= candidate_budget or not budget.can_derive_column():
                    return count
                count += 1

                ot_num = pd.to_numeric(df[ot], errors='coerce')
                th_num = pd.to_numeric(df[th], errors='coerce')

                valid_mask = ot_num.notna() & (th_num > 0)
                if valid_mask.sum() / max(1, len(df)) >= 0.5:
                    feat_name = f"derived_ot_strain_ratio_{ot}_per_{th}"
                    res = pd.Series(np.nan, index=df.index, dtype=float)
                    res.loc[valid_mask] = np.round(ot_num.loc[valid_mask] / th_num.loc[valid_mask], 4)

                    df[feat_name] = res
                    budget.record_derived_columns(1)
                    features.append(
                        DerivedFeature(
                            name=feat_name,
                            source_columns=[ot, th],
                            derivation_type="scientific_formula",
                            expression=f"{ot} / {th}",
                            depth=2,
                            confidence=0.95,
                            utility_score=0.92,
                            unit="ratio",
                            roles=[SemanticRole.MEASURE, SemanticRole.QUANTITY]
                        )
                    )

        return count

    @classmethod
    def _evaluate_featuretools_synthesis(
        cls,
        ft_adapter: FeatureSynthesisAdapter,
        columns: list[str],
        df: pd.DataFrame,
        features: list[DerivedFeature],
        budget: BudgetGuard,
        max_features: int = 5
    ):
        """Synthesizes features via Featuretools DFS within semantic groups."""
        if not budget.can_derive_column():
            return
        allowed_count = min(max_features, budget.remaining_column_budget())
        if allowed_count <= 0:
            return

        try:
            synth_df, meta_list = ft_adapter.synthesize_features_for_group(
                df, columns, max_features=allowed_count
            )
            for meta in meta_list:
                col_name = meta["column_name"]
                if col_name in synth_df.columns and col_name not in df.columns:
                    s_vals = synth_df[col_name]
                    # Check not empty or completely NaN
                    if s_vals.notna().sum() / max(1, len(df)) >= 0.5:
                        df[col_name] = s_vals
                        budget.record_derived_columns(1)
                        features.append(
                            DerivedFeature(
                                name=col_name,
                                source_columns=meta.get("source_columns", []),
                                derivation_type="primitive_measurement",
                                expression=col_name,
                                depth=1,
                                confidence=0.88,
                                utility_score=0.85,
                                unit="dimensionless",
                                roles=[SemanticRole.MEASURE, SemanticRole.QUANTITY]
                            )
                        )
        except Exception as e:
            logger.debug("Featuretools synthesis notice: %s", e)

    @classmethod
    def _evaluate_symbolic_relationships(
        cls,
        sym_adapter: SymbolicRelationshipAdapter,
        columns: list[str],
        df: pd.DataFrame,
        features: list[DerivedFeature],
        budget: BudgetGuard
    ):
        """Discovers symbolic formulas with PySR Regressor."""
        if not sym_adapter.is_available() or not budget.can_derive_column():
            return

        num_cols = [c for c in columns if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        if len(num_cols) < 2:
            return

        try:
            # Pick primary target column
            target_col = num_cols[-1]
            feature_cols = num_cols[:-1]
            sym_res = sym_adapter.discover_symbolic_relationship(
                df, feature_cols, target_col, max_time_seconds=10
            )
            if sym_res and "expression" in sym_res:
                logger.info("Discovered symbolic relationship: %s = %s", target_col, sym_res["expression"])
        except Exception as e:
            logger.debug("Symbolic regression discovery notice: %s", e)
