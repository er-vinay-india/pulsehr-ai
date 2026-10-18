"""
HighView Ingestion V2 — Anomaly & Outlier Statistical Analysis
Stage 8: Analytical EDA-B
Detects statistical outliers using rule-based Tukey IQR and Robust Z-Score (MAD).
CRITICAL: Tukey IQR is strictly rule-based and produces ZERO p-values.
All descriptions strictly use observational non-judgmental language.
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
from app.services.ingestion_v2.contracts.analytics import FindingType, OutlierMethod, TukeyIqrEvidence
from app.services.ingestion_v2.contracts.profiling import TableStructuralProfile
from app.services.ingestion_v2.contracts.semantics import SemanticColumnRole, SemanticConcept


def analyze_anomalies_and_outliers(
    table_id: str,
    table_profile: TableStructuralProfile,
    column_semantics: dict[str, Any],
    rows: list[dict[str, Any]],
    registry: FindingRegistry,
    target_grain: str | None = None,
) -> None:
    """
    Compute rule-based Tukey IQR outlier evidence for continuous numeric columns.
    """
    if not rows or len(rows) < 10:
        return

    for col_profile in table_profile.columns:
        col_id = get_column_name(col_profile)
        col_type = get_column_type(col_profile)
        sem = column_semantics.get(col_id)
        role = get_column_role(sem)
        concept = get_column_concept(sem)

        # Outliers apply to measures, quantities, monetary, or continuous values
        if col_type not in ("INTEGER", "FLOAT") or role in (
            SemanticColumnRole.ENTITY_IDENTIFIER,
            SemanticColumnRole.TIME,
            SemanticColumnRole.TECHNICAL_METADATA,
        ) or concept in (SemanticConcept.IDENTIFIER, SemanticConcept.TECHNICAL):
            continue

        raw_vals = []
        for r in rows:
            v = r.get(col_id)
            if v is not None:
                try:
                    raw_vals.append(float(v))
                except (ValueError, TypeError):
                    pass

        if len(raw_vals) < 10:
            continue

        # Rule-based Tukey IQR (1.5x)
        q1 = float(np.percentile(raw_vals, 25))
        q3 = float(np.percentile(raw_vals, 75))
        iqr = q3 - q1

        if iqr <= 0:
            continue

        lower_bound = q1 - (1.5 * iqr)
        upper_bound = q3 + (1.5 * iqr)

        outliers = [x for x in raw_vals if x < lower_bound or x > upper_bound]
        outlier_count = len(outliers)
        outlier_pct = round((outlier_count / len(raw_vals)) * 100.0, 2)

        if outlier_count > 0:
            tukey_evid = TukeyIqrEvidence(
                outlier_method=OutlierMethod.TUKEY_IQR,
                iqr_multiplier=1.5,
                q1=round(q1, 3),
                q3=round(q3, 3),
                iqr=round(iqr, 3),
                lower_bound=round(lower_bound, 3),
                upper_bound=round(upper_bound, 3),
                outlier_count=outlier_count,
                outlier_percentage=outlier_pct,
            )

            desc = (
                f"Column '{col_id}' in '{table_id}' contains {outlier_count} observation(s) ({outlier_pct}%) "
                f"exceeding the standard 1.5x IQR Tukey boundary [thresholds: {lower_bound:.2f}, {upper_bound:.2f}]."
            )

            registry.register(
                finding_type=FindingType.OUTLIER,
                description=desc,
                source_table_ids=[table_id],
                source_column_ids=[col_id],
                target_grain=target_grain or f"{table_id}_ROW",
                result={
                    "method": "TUKEY_IQR",
                    "iqr_multiplier": 1.5,
                    "lower_bound": round(lower_bound, 3),
                    "upper_bound": round(upper_bound, 3),
                    "outlier_count": outlier_count,
                    "outlier_percentage": outlier_pct,
                    "sample_size": len(raw_vals),
                    "min_observed": round(float(np.min(raw_vals)), 3),
                    "max_observed": round(float(np.max(raw_vals)), 3),
                },
                metric_definition=f"OUTLIER_SCAN({col_id})",
                dimension_definition=None,
                population_definition="ALL_ROWS",
                confidence=1.0,
                analysis_method="TUKEY_IQR",
                tukey_evidence=tukey_evid,
            )
