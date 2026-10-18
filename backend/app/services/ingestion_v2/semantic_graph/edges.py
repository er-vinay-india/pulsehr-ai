"""
HighView Ingestion V2 — Semantic Graph Edges
Stage 10: Semantic Graph
Defines concrete typed edge constructors for the Semantic Graph.

Supported edge types:
- STRUCTURAL_RELATIONSHIP: Column/Table foreign key relationship from I4.
- SEMANTIC_RELATIONSHIP: Conceptual relationship between business entities.
- DERIVED_FROM: Lineage from derived metric to source columns/metrics.
- MEASURED_AT_GRAIN: Links metric or table to its governed grain node.
- USES_JOIN_PLAN: Governed dependency from relational metric to authorized JoinPlan.
- SUPPORTED_BY_EVIDENCE: Links metric or finding to upstream HighView EVID-* token.
- HAS_DIMENSION: Links table or entity to its dimensional attributes.
- SOURCE_PROVENANCE: Lineage link from node to normalized source coordinate.
- BELONGS_TO_FAMILY: Membership link from metric or measure to a SemanticFamily.
- CONTAINS: Structural hierarchy (Table -> Column).
- IDENTIFIES_GRAIN: Primary entity / key column identifying table grain.
- HAS_ROLE: Column semantic role annotation.
"""

from typing import Any
from app.services.ingestion_v2.contracts.semantic_graph import (
    GraphEdgeType,
    SemanticGraphEdge,
)


def create_contains_edge(
    table_node_id: str,
    column_node_id: str,
    *,
    properties: dict[str, Any] | None = None,
) -> SemanticGraphEdge:
    edge_id = f"edge-contains:{table_node_id}->{column_node_id}"
    return SemanticGraphEdge(
        edge_id=edge_id,
        source_node_id=table_node_id,
        target_node_id=column_node_id,
        edge_type=GraphEdgeType.CONTAINS,
        properties=properties or {},
    )


def create_structural_relationship_edge(
    edge_id: str,
    source_node_id: str,
    target_node_id: str,
    *,
    cardinality: str | None = None,
    weight: float = 1.0,
    properties: dict[str, Any] | None = None,
) -> SemanticGraphEdge:
    props: dict[str, Any] = properties.copy() if properties else {}
    if cardinality:
        props["cardinality"] = cardinality

    return SemanticGraphEdge(
        edge_id=edge_id,
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        edge_type=GraphEdgeType.STRUCTURAL_RELATIONSHIP,
        weight=weight,
        properties=props,
    )


def create_semantic_relationship_edge(
    edge_id: str,
    source_entity_node_id: str,
    target_entity_node_id: str,
    *,
    relationship_name: str | None = None,
    weight: float = 1.0,
    properties: dict[str, Any] | None = None,
) -> SemanticGraphEdge:
    props: dict[str, Any] = properties.copy() if properties else {}
    if relationship_name:
        props["relationship_name"] = relationship_name

    return SemanticGraphEdge(
        edge_id=edge_id,
        source_node_id=source_entity_node_id,
        target_node_id=target_entity_node_id,
        edge_type=GraphEdgeType.SEMANTIC_RELATIONSHIP,
        weight=weight,
        properties=props,
    )


def create_derived_from_edge(
    metric_node_id: str,
    source_node_id: str,
    *,
    derivation_role: str = "SOURCE_INPUT",
    properties: dict[str, Any] | None = None,
) -> SemanticGraphEdge:
    props: dict[str, Any] = properties.copy() if properties else {}
    props["derivation_role"] = derivation_role

    return SemanticGraphEdge(
        edge_id=f"edge-derived:{metric_node_id}->{source_node_id}",
        source_node_id=metric_node_id,
        target_node_id=source_node_id,
        edge_type=GraphEdgeType.DERIVED_FROM,
        properties=props,
    )


def create_measured_at_grain_edge(
    source_node_id: str,
    grain_node_id: str,
    *,
    properties: dict[str, Any] | None = None,
) -> SemanticGraphEdge:
    return SemanticGraphEdge(
        edge_id=f"edge-grain:{source_node_id}->{grain_node_id}",
        source_node_id=source_node_id,
        target_node_id=grain_node_id,
        edge_type=GraphEdgeType.MEASURED_AT_GRAIN,
        properties=properties or {},
    )


def create_uses_join_plan_edge(
    relational_metric_node_id: str,
    join_plan_id: str,
    *,
    target_grain: str | None = None,
    properties: dict[str, Any] | None = None,
) -> SemanticGraphEdge:
    props: dict[str, Any] = properties.copy() if properties else {}
    props["join_plan_id"] = join_plan_id
    if target_grain:
        props["target_grain"] = target_grain

    # Target node is the join plan or edge identifier
    target_node = f"join_plan:{join_plan_id}"
    return SemanticGraphEdge(
        edge_id=f"edge-jp:{relational_metric_node_id}->{join_plan_id}",
        source_node_id=relational_metric_node_id,
        target_node_id=target_node,
        edge_type=GraphEdgeType.USES_JOIN_PLAN,
        properties=props,
    )


def create_supported_by_evidence_edge(
    node_id: str,
    evidence_ref: str,
    *,
    finding_type: str | None = None,
    properties: dict[str, Any] | None = None,
) -> SemanticGraphEdge:
    props: dict[str, Any] = properties.copy() if properties else {}
    if finding_type:
        props["finding_type"] = finding_type

    return SemanticGraphEdge(
        edge_id=f"edge-evid:{node_id}->{evidence_ref}",
        source_node_id=node_id,
        target_node_id=f"evidence:{evidence_ref}",
        edge_type=GraphEdgeType.SUPPORTED_BY_EVIDENCE,
        evidence_ref=evidence_ref,
        properties=props,
    )


def create_has_dimension_edge(
    table_or_entity_node_id: str,
    dimension_node_id: str,
    *,
    properties: dict[str, Any] | None = None,
) -> SemanticGraphEdge:
    return SemanticGraphEdge(
        edge_id=f"edge-has-dim:{table_or_entity_node_id}->{dimension_node_id}",
        source_node_id=table_or_entity_node_id,
        target_node_id=dimension_node_id,
        edge_type=GraphEdgeType.HAS_DIMENSION,
        properties=properties or {},
    )


def create_source_provenance_edge(
    node_id: str,
    provenance_coord: str,
    *,
    properties: dict[str, Any] | None = None,
) -> SemanticGraphEdge:
    return SemanticGraphEdge(
        edge_id=f"edge-prov:{node_id}->{provenance_coord}",
        source_node_id=node_id,
        target_node_id=f"provenance:{provenance_coord}",
        edge_type=GraphEdgeType.SOURCE_PROVENANCE,
        properties=properties or {},
    )


def create_belongs_to_family_edge(
    metric_or_measure_node_id: str,
    family_node_id: str,
    *,
    properties: dict[str, Any] | None = None,
) -> SemanticGraphEdge:
    return SemanticGraphEdge(
        edge_id=f"edge-family:{metric_or_measure_node_id}->{family_node_id}",
        source_node_id=metric_or_measure_node_id,
        target_node_id=family_node_id,
        edge_type=GraphEdgeType.BELONGS_TO_FAMILY,
        properties=properties or {},
    )
