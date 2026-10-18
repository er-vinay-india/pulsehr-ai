"""
HighView Ingestion V2 — Correlation Statistical Analysis
Stage 8: Analytical EDA-B
Evaluates bivariate correlation between numeric measures with strict semantic identifier guardrails
and observational, non-causal language.
"""

from __future__ import annotations

import math
from typing import Any
import numpy as np

from app.services.ingestion_v2.analytics.finding_registry import FindingRegistry
from app.services.ingestion_v2.analytics.helpers import (
    get_column_concept,
    get_column_name,
    get_column_role,
    get_column_type,
)
from app.services.ingestion_v2.analytics.statistical_tests import perform_correlation_test
from app.services.ingestion_v2.contracts.analytics import FindingType
from app.services.ingestion_v2.contracts.profiling import TableStructuralProfile
from app.services.ingestion_v2.contracts.semantics import SemanticColumnRole, SemanticConcept


def analyze_correlations(
    table_id: str,
    table_profile: TableStructuralProfile,
    column_semantics: dict[str, Any],
    rows: list[dict[str, Any]],
    registry: FindingRegistry,
    target_grain: str | None = None,
) -> None:
    """
    Computes Pearson correlation for eligible numeric column pairs.
    Strictly excludes entity identifiers, keys, timestamps, and technical indices.
    """
    if not rows or len(rows) < 10:
        return

    # Filter eligible measure columns
    eligible_cols: list[str] = []
    for col_profile in table_profile.columns:
        col_id = get_column_name(col_profile)
        col_type = get_column_type(col_profile)
        sem = column_semantics.get(col_id)
        role = get_column_role(sem)
        concept = get_column_concept(sem)

        # Strict firewall against identifiers, timestamps, and technical columns
        if role in (
            SemanticColumnRole.ENTITY_IDENTIFIER,
            SemanticColumnRole.TIME,
            SemanticColumnRole.TECHNICAL_METADATA,
        ) or concept in (SemanticConcept.IDENTIFIER, SemanticConcept.TECHNICAL):
            continue

        if col_type in ("INTEGER", "FLOAT"):
            eligible_cols.append(col_id)

    if len(eligible_cols) < 2:
        return

    # Check pairwise correlations
    n_cols = len(eligible_cols)
    for i in range(n_cols):
        col_a = eligible_cols[i]
        for j in range(i + 1, n_cols):
            col_b = eligible_cols[j]

            pairs = []
            for r in rows:
                va = r.get(col_a)
                vb = r.get(col_b)
                if va is not None and vb is not None:
                    try:
                        pairs.append((float(va), float(vb)))
                    except (ValueError, TypeError):
                        pass

            if len(pairs) < 10:
                continue

            vec_a = [p[0] for p in pairs]
            vec_b = [p[1] for p in pairs]

            if np.var(vec_a) == 0.0 or np.var(vec_b) == 0.0:
                continue

            test_evid = perform_correlation_test(vec_a, vec_b, method="pearson")
            if not test_evid:
                continue

            r_val = test_evid.test_statistic
            abs_r = abs(r_val)

            # Record if meaningful correlation exists (|r| >= 0.40) or significant
            if abs_r >= 0.40:
                direction = "positive" if r_val > 0 else "negative"
                strength = "strong" if abs_r >= 0.70 else "moderate"

                desc = (
                    f"Observed {strength} {direction} linear correlation between '{col_a}' and '{col_b}' "
                    f"in '{table_id}' (Pearson r = {r_val:.2f}, p = {test_evid.p_value:.4f}, n = {len(pairs)})."
                )

                registry.register(
                    finding_type=FindingType.CORRELATION,
                    description=desc,
                    source_table_ids=[table_id],
                    source_column_ids=[col_a, col_b],
                    target_grain=target_grain or f"{table_id}_ROW",
                    result={
                        "pearson_r": r_val,
                        "p_value": test_evid.p_value,
                        "sample_size": len(pairs),
                        "direction": direction,
                        "strength": strength,
                        "is_significant": test_evid.is_statistically_significant,
                    },
                    metric_definition=f"CORRELATION({col_a}, {col_b})",
                    dimension_definition=None,
                    population_definition="ALL_ROWS",
                    effect_size=test_evid.effect_size,
                    confidence=1.0,
                    analysis_method="PEARSON_CORRELATION",
                    statistical_evidence=test_evid,
                    limitations=["Correlation indicates statistical association, not causation."],
                )
