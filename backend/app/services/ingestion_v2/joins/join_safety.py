"""
HighView Ingestion V2 — Phase I4: Join Safety Analyzer
Stage: Join Safety Assessment

Distinguishes between valid structural relationships and analytically safe joins.
Evaluates grain compatibility, Cartesian fanout risks, measure duplication, and temporal alignment.
Zero model / LLM calls. Fully deterministic.
"""

from __future__ import annotations

from typing import Sequence
import pandas as pd

from app.services.ingestion_v2.contracts.grain import CanonicalGrain, GrainProfile, TableGrainProfile
from app.services.ingestion_v2.contracts.joins import JoinSafetyAssessment, JoinSafetyStatus
from app.services.ingestion_v2.contracts.profiling import StructuralProfile, TableStructuralProfile
from app.services.ingestion_v2.contracts.relationships import (
    RelationshipCardinality,
    RelationshipStatus,
    ValidatedRelationshipEdge,
    ValidatedRelationshipGraph,
)
from app.services.ingestion_v2.contracts.semantics import SemanticColumnRole, SemanticModel, TableSemanticModel


class JoinSafetyAnalyzer:
    """
    Evaluates whether a validated structural relationship edge can be safely joined
    for analytical computations, and whether pre-aggregation or grain alignment is required.
    """

    @staticmethod
    def assess_edge_safety(
        edge: ValidatedRelationshipEdge,
        grain_profile: GrainProfile,
        structural_profile: StructuralProfile | None = None,
        semantic_model: SemanticModel | None = None,
        analysis_purpose: str = "GENERAL_ANALYTICS",
        requested_target_grain: str | None = None,
    ) -> JoinSafetyAssessment:
        """
        Evaluate join safety for a single validated relationship edge.
        """
        grain_map: dict[str, TableGrainProfile] = {t.table_id: t for t in (getattr(grain_profile, "table_grains", None) or getattr(grain_profile, "tables", []))}
        s_grain = grain_map.get(edge.source_table_id)
        t_grain = grain_map.get(edge.target_table_id)

        s_grain_expr = s_grain.grain_expression if s_grain else "UNKNOWN"
        t_grain_expr = t_grain.grain_expression if t_grain else "UNKNOWN"

        assessment_id = f"safety_{edge.edge_id}"

        # 1. Edge rejection check: If structural relationship is REJECTED or AMBIGUOUS
        if edge.status == RelationshipStatus.REJECTED:
            return JoinSafetyAssessment(
                assessment_id=assessment_id,
                edge_id=edge.edge_id,
                left_table_id=edge.source_table_id,
                right_table_id=edge.target_table_id,
                safety_status=JoinSafetyStatus.UNSAFE,
                is_grain_compatible=False,
                fact_duplication_risk=True,
                dimension_propagation_safe=False,
                measure_duplication_risk=True,
                temporal_mismatch=False,
                many_to_many_risk=edge.duplication_risk_flag,
                estimated_row_multiplier=edge.estimated_row_multiplier,
                required_pre_aggregation=False,
                rationale=f"RELATIONSHIP_REJECTED: {edge.rejection_reason or 'Structurally invalid relationship'}",
                recommended_target_grain=None,
            )

        # 2. Many-to-Many Cartesian fanout trap
        # E.g. Attendance (22 rows/emp) joined to Leave (3 rows/emp) produces 66 rows/emp
        if edge.cardinality == RelationshipCardinality.MANY_TO_MANY or edge.duplication_risk_flag:
            has_temporal_mismatch = (
                ("MONTH" in s_grain_expr and "DAY" in t_grain_expr) or
                ("DAY" in s_grain_expr and "MONTH" in t_grain_expr) or
                ("WEEK" in s_grain_expr and "MONTH" in t_grain_expr)
            )
            if "PREAGGREGATION" in analysis_purpose or requested_target_grain:
                return JoinSafetyAssessment(
                    assessment_id=assessment_id,
                    edge_id=edge.edge_id,
                    left_table_id=edge.source_table_id,
                    right_table_id=edge.target_table_id,
                    safety_status=JoinSafetyStatus.SAFE_WITH_PREAGGREGATION,
                    is_grain_compatible=False,
                    fact_duplication_risk=True,
                    dimension_propagation_safe=False,
                    measure_duplication_risk=True,
                    temporal_mismatch=has_temporal_mismatch,
                    many_to_many_risk=True,
                    estimated_row_multiplier=edge.estimated_row_multiplier,
                    required_pre_aggregation=True,
                    rationale=f"PREAGGREGATION_GOVERNED_M2M: Raw join produces {edge.estimated_row_multiplier}x fanout; governed pre-aggregation plan reduces target grain to '{requested_target_grain or 'AGGREGATE'}'.",
                    recommended_target_grain=requested_target_grain or "AGGREGATE",
                )
            return JoinSafetyAssessment(
                assessment_id=assessment_id,
                edge_id=edge.edge_id,
                left_table_id=edge.source_table_id,
                right_table_id=edge.target_table_id,
                safety_status=JoinSafetyStatus.UNSAFE,
                is_grain_compatible=False,
                fact_duplication_risk=True,
                dimension_propagation_safe=False,
                measure_duplication_risk=True,
                temporal_mismatch=has_temporal_mismatch,
                many_to_many_risk=True,
                estimated_row_multiplier=edge.estimated_row_multiplier,
                required_pre_aggregation=True,
                rationale=f"MANY_TO_MANY_CARTESIAN_RISK: Direct join produces row multiplication (multiplier {edge.estimated_row_multiplier}x). Requires pre-aggregation or bridge.",
                recommended_target_grain=None,
            )

        # 3. Fact-to-Fact Join Trap
        # If both tables are multi-row periodic or event facts:
        # e.g. PERSON x DAY vs PERSON x INCIDENT
        is_source_periodic_or_event = any(k in s_grain_expr for k in [" x ", "DAY", "MONTH", "WEEK", "TRANSACTION", "EVENT", "INCIDENT"])
        is_target_periodic_or_event = any(k in t_grain_expr for k in [" x ", "DAY", "MONTH", "WEEK", "TRANSACTION", "EVENT", "INCIDENT"])

        if is_source_periodic_or_event and is_target_periodic_or_event:
            # Check if grains match exactly
            if s_grain_expr == t_grain_expr and edge.key_type.value == "COMPOSITE":
                # E.g. STORE x WEEK <-> STORE x WEEK with composite keys [store_id, week]
                return JoinSafetyAssessment(
                    assessment_id=assessment_id,
                    edge_id=edge.edge_id,
                    left_table_id=edge.source_table_id,
                    right_table_id=edge.target_table_id,
                    safety_status=JoinSafetyStatus.SAFE,
                    is_grain_compatible=True,
                    fact_duplication_risk=False,
                    dimension_propagation_safe=True,
                    measure_duplication_risk=False,
                    temporal_mismatch=False,
                    many_to_many_risk=False,
                    estimated_row_multiplier=edge.estimated_row_multiplier,
                    required_pre_aggregation=False,
                    rationale="ALIGNED_COMPOSITE_GRAIN: Source and target have identical periodic grains and key alignment.",
                    recommended_target_grain=s_grain_expr,
                )
            else:
                # E.g. PERSON x DAY vs PERSON x INCIDENT, or DEPARTMENT x MONTH vs PERSON x DAY
                has_temporal_mismatch = (
                    ("MONTH" in s_grain_expr and "DAY" in t_grain_expr) or
                    ("DAY" in s_grain_expr and "MONTH" in t_grain_expr) or
                    ("WEEK" in s_grain_expr and "MONTH" in t_grain_expr)
                )

                if "PREAGGREGATION" in analysis_purpose or requested_target_grain:
                    return JoinSafetyAssessment(
                        assessment_id=assessment_id,
                        edge_id=edge.edge_id,
                        left_table_id=edge.source_table_id,
                        right_table_id=edge.target_table_id,
                        safety_status=JoinSafetyStatus.SAFE_WITH_PREAGGREGATION,
                        is_grain_compatible=False,
                        fact_duplication_risk=True,
                        dimension_propagation_safe=False,
                        measure_duplication_risk=True,
                        temporal_mismatch=has_temporal_mismatch,
                        many_to_many_risk=True,
                        estimated_row_multiplier=edge.estimated_row_multiplier,
                        required_pre_aggregation=True,
                        rationale="FACT_TO_FACT_GRAIN_MISMATCH: Direct join unsafe; requires pre-aggregating child fact to common grain.",
                        recommended_target_grain=requested_target_grain or s_grain_expr,
                    )
                else:
                    return JoinSafetyAssessment(
                        assessment_id=assessment_id,
                        edge_id=edge.edge_id,
                        left_table_id=edge.source_table_id,
                        right_table_id=edge.target_table_id,
                        safety_status=JoinSafetyStatus.UNSAFE,
                        is_grain_compatible=False,
                        fact_duplication_risk=True,
                        dimension_propagation_safe=False,
                        measure_duplication_risk=True,
                        temporal_mismatch=has_temporal_mismatch,
                        many_to_many_risk=True,
                        estimated_row_multiplier=edge.estimated_row_multiplier,
                        required_pre_aggregation=True,
                        rationale=f"UNSAFE_FACT_TO_FACT_JOIN: Direct raw join between {s_grain_expr} and {t_grain_expr} causes metric inflation and grain distortion.",
                        recommended_target_grain=None,
                    )

        # 4. Dimension-to-Fact Join (Grain-Preserving Dimension Propagation)
        # E.g. PERSON (Employees master) joined to PERSON x DAY (Daily attendance)
        # E.g. PRODUCT (Products master) joined to PRODUCT x LOCATION x DAY (Daily inventory)
        if (not is_source_periodic_or_event and is_target_periodic_or_event) or \
           (is_source_periodic_or_event and not is_target_periodic_or_event):
            # One table is a pure dimension table, the other is a fact table
            fact_grain = t_grain_expr if is_target_periodic_or_event else s_grain_expr
            dim_table = edge.source_table_id if not is_source_periodic_or_event else edge.target_table_id

            return JoinSafetyAssessment(
                assessment_id=assessment_id,
                edge_id=edge.edge_id,
                left_table_id=edge.source_table_id,
                right_table_id=edge.target_table_id,
                safety_status=JoinSafetyStatus.SAFE,
                is_grain_compatible=True,
                fact_duplication_risk=False,
                dimension_propagation_safe=True,
                measure_duplication_risk=False,
                temporal_mismatch=False,
                many_to_many_risk=False,
                estimated_row_multiplier=1.0,
                required_pre_aggregation=False,
                rationale=f"DIMENSION_ENRICHMENT_SAFE: Propagates attributes from dimension table '{dim_table}' onto fact table preserving grain '{fact_grain}'.",
                recommended_target_grain=fact_grain,
            )

        # 5. Dimension-to-Dimension Join (1:1 or 1:N)
        if edge.cardinality in (RelationshipCardinality.ONE_TO_ONE, RelationshipCardinality.ONE_TO_MANY, RelationshipCardinality.MANY_TO_ONE):
            target_g = s_grain_expr if s_grain_expr != "UNKNOWN" else t_grain_expr
            return JoinSafetyAssessment(
                assessment_id=assessment_id,
                edge_id=edge.edge_id,
                left_table_id=edge.source_table_id,
                right_table_id=edge.target_table_id,
                safety_status=JoinSafetyStatus.SAFE,
                is_grain_compatible=True,
                fact_duplication_risk=False,
                dimension_propagation_safe=True,
                measure_duplication_risk=False,
                temporal_mismatch=False,
                many_to_many_risk=False,
                estimated_row_multiplier=1.0,
                required_pre_aggregation=False,
                rationale="DIMENSION_ALIGNMENT_SAFE: Clean 1:1 or 1:N dimension join without row multiplication.",
                recommended_target_grain=target_g,
            )

        # Default fallback: AMBIGUOUS
        return JoinSafetyAssessment(
            assessment_id=assessment_id,
            edge_id=edge.edge_id,
            left_table_id=edge.source_table_id,
            right_table_id=edge.target_table_id,
            safety_status=JoinSafetyStatus.AMBIGUOUS,
            is_grain_compatible=False,
            fact_duplication_risk=False,
            dimension_propagation_safe=False,
            measure_duplication_risk=False,
            temporal_mismatch=False,
            many_to_many_risk=False,
            estimated_row_multiplier=edge.estimated_row_multiplier,
            required_pre_aggregation=False,
            rationale="GRAIN_SAFETY_AMBIGUOUS: Observational grain could not be proved safe for unguided join.",
            recommended_target_grain=None,
        )

    @classmethod
    def assess_graph(
        cls,
        relationship_graph: ValidatedRelationshipGraph,
        grain_profile: GrainProfile,
        structural_profile: StructuralProfile | None = None,
        semantic_model: SemanticModel | None = None,
    ) -> list[JoinSafetyAssessment]:
        """Assess join safety for all edges in the validated relationship graph."""
        assessments: list[JoinSafetyAssessment] = []
        for edge in relationship_graph.edges:
            assessments.append(cls.assess_edge_safety(edge, grain_profile, structural_profile, semantic_model))
        return assessments
