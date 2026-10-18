"""
HighView Ingestion V2 — Univariate Statistical Analysis
Stage 8: Analytical EDA-B
Computes descriptive distributions, proportions, and distinct counts on single tables.
Adheres strictly to neutral, observational language.
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
from app.services.ingestion_v2.contracts.analytics import FindingType
from app.services.ingestion_v2.contracts.profiling import TableStructuralProfile
from app.services.ingestion_v2.contracts.semantics import SemanticColumnRole, SemanticConcept


def analyze_univariate_profiles(
    table_id: str,
    table_profile: TableStructuralProfile,
    column_semantics: dict[str, Any],
    rows: list[dict[str, Any]],
    registry: FindingRegistry,
    target_grain: str | None = None,
) -> None:
    """
    Perform univariate statistical analysis for all eligible columns in a table.
    Registers DISTRIBUTION, DISTINCT_COUNT, and PROPORTION findings.
    """
    if not rows:
        return

    n_rows = len(rows)

    for col_profile in table_profile.columns:
        col_id = get_column_name(col_profile)
        col_type = get_column_type(col_profile)
        sem = column_semantics.get(col_id)
        role = get_column_role(sem)
        concept = get_column_concept(sem)

        # Extract non-null values
        raw_vals = [r.get(col_id) for r in rows if r.get(col_id) is not None]
        if not raw_vals:
            continue

        # 1. Distinct Count Findings for Identifiers or Entities
        if role in (SemanticColumnRole.ENTITY_IDENTIFIER,) or concept == SemanticConcept.IDENTIFIER:
            distinct_set = set(raw_vals)
            distinct_count = len(distinct_set)

            desc = f"Table '{table_id}' contains {distinct_count} distinct values for identifier '{col_id}' across {n_rows} rows."

            registry.register(
                finding_type=FindingType.DISTINCT_COUNT,
                description=desc,
                source_table_ids=[table_id],
                source_column_ids=[col_id],
                target_grain=target_grain or f"{table_id}_ROW",
                result={"distinct_count": distinct_count, "total_rows": n_rows, "uniqueness_ratio": round(distinct_count / n_rows, 4)},
                metric_definition=f"COUNT(DISTINCT {col_id})",
                dimension_definition=None,
                population_definition="ALL_ROWS",
                confidence=1.0,
            )
            continue

        # 2. Continuous Numeric Columns -> Distribution Findings
        if col_type in ("INTEGER", "FLOAT") and role not in (SemanticColumnRole.TIME, SemanticColumnRole.TECHNICAL_METADATA):
            num_vals = []
            for v in raw_vals:
                try:
                    num_vals.append(float(v))
                except (ValueError, TypeError):
                    pass

            if len(num_vals) >= 5:
                mean_val = float(np.mean(num_vals))
                std_val = float(np.std(num_vals, ddof=1)) if len(num_vals) > 1 else 0.0
                median_val = float(np.median(num_vals))
                q25 = float(np.percentile(num_vals, 25))
                q75 = float(np.percentile(num_vals, 75))
                min_val = float(np.min(num_vals))
                max_val = float(np.max(num_vals))
                skew = float(((mean_val - median_val) / std_val)) if std_val > 0 else 0.0

                desc = (
                    f"Column '{col_id}' in '{table_id}' has an observed mean of {mean_val:.2f} "
                    f"(median {median_val:.2f}, std {std_val:.2f}, range [{min_val:.2f}, {max_val:.2f}])."
                )

                registry.register(
                    finding_type=FindingType.DISTRIBUTION,
                    description=desc,
                    source_table_ids=[table_id],
                    source_column_ids=[col_id],
                    target_grain=target_grain or f"{table_id}_ROW",
                    result={
                        "mean": round(mean_val, 3),
                        "median": round(median_val, 3),
                        "std": round(std_val, 3),
                        "q25": round(q25, 3),
                        "q75": round(q75, 3),
                        "min": round(min_val, 3),
                        "max": round(max_val, 3),
                        "skewness_proxy": round(skew, 3),
                        "sample_size": len(num_vals),
                    },
                    metric_definition=f"DISTRIBUTION({col_id})",
                    dimension_definition=None,
                    population_definition="ALL_ROWS",
                    confidence=1.0,
                )

        # 3. Categorical / Low-Cardinality Attributes -> Proportion Findings
        elif col_type in ("STRING", "CATEGORY", "BOOLEAN") and role in (
            SemanticColumnRole.DIMENSION,
            SemanticColumnRole.ATTRIBUTE,
            SemanticColumnRole.STATUS,
            SemanticColumnRole.BOOLEAN,
            SemanticColumnRole.CATEGORY,
        ):
            val_counts: dict[str, int] = {}
            for v in raw_vals:
                s_val = str(v).strip()
                val_counts[s_val] = val_counts.get(s_val, 0) + 1

            if 1 < len(val_counts) <= 20:
                top_items = sorted(val_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                proportions = {k: round(cnt / len(raw_vals), 4) for k, cnt in top_items}

                top_cat, top_cnt = top_items[0]
                top_pct = round(100.0 * top_cnt / len(raw_vals), 1)

                desc = (
                    f"Column '{col_id}' in '{table_id}' has {len(val_counts)} distinct categories; "
                    f"'{top_cat}' is the most frequent category at {top_pct}% ({top_cnt}/{len(raw_vals)})."
                )

                registry.register(
                    finding_type=FindingType.PROPORTION,
                    description=desc,
                    source_table_ids=[table_id],
                    source_column_ids=[col_id],
                    target_grain=target_grain or f"{table_id}_ROW",
                    result={
                        "category_counts": dict(top_items),
                        "category_proportions": proportions,
                        "distinct_categories": len(val_counts),
                        "total_valid_rows": len(raw_vals),
                    },
                    metric_definition=f"PROPORTION({col_id})",
                    dimension_definition=col_id,
                    population_definition="ALL_ROWS",
                    confidence=1.0,
                )
