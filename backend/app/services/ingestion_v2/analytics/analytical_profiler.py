"""
HighView Ingestion V2 — Governed Analytical Profiler (EDA-B Orchestrator)
Stage 8: Analytical EDA-B
Coordinates single-table and governed cross-table statistical profiling,
enforcing join plan authorization, denominator preservation, Benjamini-Hochberg FDR correction,
and analytical reliability evaluation.
"""

from __future__ import annotations

import uuid
from typing import Any
from app.services.ingestion_v2.analytics.anomaly_analysis import analyze_anomalies_and_outliers
from app.services.ingestion_v2.analytics.concentration_analysis import analyze_concentration
from app.services.ingestion_v2.analytics.correlation_analysis import analyze_correlations
from app.services.ingestion_v2.analytics.finding_registry import FindingRegistry
from app.services.ingestion_v2.analytics.univariate_analysis import analyze_univariate_profiles
from app.services.ingestion_v2.analytics.governed_join_executor import (
    GovernedJoinExecutionError,
    execute_governed_join,
)
from app.services.ingestion_v2.analytics.grouped_analysis import (
    analyze_governed_ratio,
    analyze_grouped_comparisons,
)
from app.services.ingestion_v2.analytics.helpers import (
    get_column_name,
    get_column_role,
    get_column_type,
)
from app.services.ingestion_v2.analytics.ranking import analyze_rankings
from app.services.ingestion_v2.analytics.reliability import calculate_analytical_reliability
from app.services.ingestion_v2.analytics.statistical_tests import apply_benjamini_hochberg
from app.services.ingestion_v2.analytics.trend_analysis import analyze_trends
from app.services.ingestion_v2.contracts.analytics import AnalyticalProfile
from app.services.ingestion_v2.contracts.grain import GrainProfile
from app.services.ingestion_v2.contracts.joins import JoinPlan, JoinSafetyStatus
from app.services.ingestion_v2.contracts.profiling import StructuralProfile
from app.services.ingestion_v2.contracts.relationships import ValidatedRelationshipGraph
from app.services.ingestion_v2.contracts.semantics import SemanticColumnRole, SemanticModel


class AnalyticalProfiler:
    """
    EDA-B Analytical Profiler orchestrating governed statistical characterization.
    """

    def __init__(self, dataset_id: str, run_id: str | None = None):
        self.dataset_id = dataset_id
        self.run_id = run_id or f"run_{uuid.uuid4().hex[:12]}"
        self.registry = FindingRegistry(dataset_id=dataset_id)

    def profile(
        self,
        structural_profile: StructuralProfile,
        semantic_model: SemanticModel,
        grain_profile: GrainProfile,
        relationship_graph: ValidatedRelationshipGraph | None = None,
        join_plans: list[JoinPlan] | None = None,
        table_data: dict[str, list[dict[str, Any]]] | None = None,
        source_fingerprint: str = "",
        upstream_fingerprint: str | None = None,
    ) -> AnalyticalProfile:
        """
        Execute full governed EDA-B profiling.
        """
        table_data = table_data or {}
        join_plans = join_plans or []

        # 1. Map semantics by table and column
        sem_map: dict[str, dict[str, Any]] = {}
        for t_sem in semantic_model.tables:
            sem_map[t_sem.table_id] = {c.column_name: c for c in t_sem.columns}

        # 2. Map grains by table
        table_grains: dict[str, str] = {}
        tg_source = getattr(grain_profile, "table_grains", None) or getattr(grain_profile, "tables", [])
        for tg in tg_source:
            table_grains[tg.table_id] = getattr(tg, "primary_grain", getattr(tg, "grain_key", "TABLE_ROW"))

        # 3. Single-table analysis for each table
        min_observed_sample = 999999
        has_small_sample_groups = False
        total_missingness = 0.0
        total_columns_checked = 0

        for t_prof in structural_profile.tables:
            t_id = t_prof.table_id
            rows = table_data.get(t_id, [])
            col_sem = sem_map.get(t_id, {})
            t_grain = table_grains.get(t_id, f"{t_id}_ROW")

            if rows:
                min_observed_sample = min(min_observed_sample, len(rows))
                if len(rows) < 10:
                    has_small_sample_groups = True

            for cp in t_prof.columns:
                total_missingness += cp.null_ratio
                total_columns_checked += 1

            # Execute single-table modules
            analyze_univariate_profiles(t_id, t_prof, col_sem, rows, self.registry, t_grain)
            analyze_anomalies_and_outliers(t_id, t_prof, col_sem, rows, self.registry, t_grain)
            analyze_correlations(t_id, t_prof, col_sem, rows, self.registry, t_grain)
            analyze_concentration(t_id, t_prof, col_sem, rows, self.registry, t_grain)
            analyze_rankings(t_id, t_prof, col_sem, rows, self.registry, t_grain)
            analyze_trends(t_id, t_prof, col_sem, rows, self.registry, t_grain)
            analyze_grouped_comparisons(t_id, t_prof, col_sem, rows, self.registry, t_grain)

        # 4. Governed Cross-Table Analysis on Authorized Join Plans
        for plan in join_plans:
            # Absolute firewall: only SAFE and SAFE_WITH_PREAGGREGATION may be executed
            if plan.safety_status not in (JoinSafetyStatus.SAFE, JoinSafetyStatus.SAFE_WITH_PREAGGREGATION):
                continue

            try:
                joined_rows, target_grain = execute_governed_join(plan, table_data)
                if not joined_rows:
                    continue

                # Build combined semantics and pseudo-profile for joined table
                left_sem = sem_map.get(plan.left_table_id, {})
                right_sem = sem_map.get(plan.right_table_id, {})
                combined_sem = dict(left_sem)
                combined_sem.update(right_sem)

                left_prof = next((tp for tp in structural_profile.tables if tp.table_id == plan.left_table_id), None)
                right_prof = next((tp for tp in structural_profile.tables if tp.table_id == plan.right_table_id), None)

                if left_prof and right_prof:
                    # Combine columns for cross-table grouped comparisons
                    joined_cols = list(left_prof.columns) + [
                        cp for cp in right_prof.columns if cp.column_name not in [c.column_name for c in left_prof.columns]
                    ]
                    # Create a composite table profile representation
                    from app.services.ingestion_v2.contracts.profiling import TableStructuralProfile
                    combined_prof = TableStructuralProfile(
                        table_id=f"{plan.left_table_id}_joined_{plan.right_table_id}",
                        table_name=f"{plan.left_table_id}_x_{plan.right_table_id}",
                        row_count=len(joined_rows),
                        column_count=len(joined_cols),
                        columns=joined_cols,
                        quality=left_prof.quality,
                    )

                    analyze_grouped_comparisons(
                        table_id=combined_prof.table_id,
                        table_profile=combined_prof,
                        column_semantics=combined_sem,
                        rows=joined_rows,
                        registry=self.registry,
                        target_grain=target_grain,
                        join_plan_ids=[plan.join_plan_id],
                    )

            except GovernedJoinExecutionError:
                # Execution blocked by safety guardrails
                pass

        # 5. Benjamini-Hochberg FDR correction across inferential statistical tests
        findings_with_tests = [
            f for f in self.registry.findings
            if f.statistical_test_evidence is not None and f.statistical_test_evidence.p_value is not None
        ]

        if len(findings_with_tests) > 1:
            raw_p_values = [f.statistical_test_evidence.p_value for f in findings_with_tests]
            bh_results = apply_benjamini_hochberg(raw_p_values, alpha=0.05)

            for f, (adj_p, is_sig) in zip(findings_with_tests, bh_results):
                # Update statistical evidence with adjusted FDR significance
                updated_evid = f.statistical_test_evidence.model_copy(
                    update={
                        "is_statistically_significant": is_sig,
                        "warnings": list(f.statistical_test_evidence.warnings) + [f"FDR_adjusted_p={adj_p:.4f}"],
                    }
                )
                object.__setattr__(f, "statistical_test_evidence", updated_evid)

        # 6. Evaluate Analytical Reliability
        avg_missingness = (total_missingness / max(1, total_columns_checked))
        reliability = calculate_analytical_reliability(
            grain_profile=grain_profile,
            relationship_graph=relationship_graph,
            join_plans=join_plans,
            findings_count=len(self.registry.findings),
            min_sample_size=min_observed_sample if min_observed_sample != 999999 else 20,
            has_small_sample_groups=has_small_sample_groups,
            missingness_ratio=avg_missingness,
        )

        profile = AnalyticalProfile(
            dataset_id=self.dataset_id,
            run_id=self.run_id,
            stage_name="analytical_eda_b",
            source_fingerprint=source_fingerprint or "src_eda_b_001",
            upstream_fingerprint=upstream_fingerprint,
            findings=self.registry.findings,
            reliability=reliability,
        )

        return profile.with_fingerprint()


def build_analytical_profile(
    dataset_id: str,
    structural_profile: StructuralProfile,
    semantic_model: SemanticModel,
    grain_profile: GrainProfile,
    relationship_graph: ValidatedRelationshipGraph | None = None,
    join_plans: list[JoinPlan] | None = None,
    table_data: dict[str, list[dict[str, Any]]] | None = None,
    run_id: str | None = None,
    source_fingerprint: str = "",
    upstream_fingerprint: str | None = None,
) -> AnalyticalProfile:
    """Convenience functional interface for AnalyticalProfiler."""
    profiler = AnalyticalProfiler(dataset_id=dataset_id, run_id=run_id)
    return profiler.profile(
        structural_profile=structural_profile,
        semantic_model=semantic_model,
        grain_profile=grain_profile,
        relationship_graph=relationship_graph,
        join_plans=join_plans,
        table_data=table_data,
        source_fingerprint=source_fingerprint,
        upstream_fingerprint=upstream_fingerprint,
    )
