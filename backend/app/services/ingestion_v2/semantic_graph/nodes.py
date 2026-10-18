"""
HighView Ingestion V2 — Semantic Graph Nodes
Stage 10: Semantic Graph
Defines concrete typed node constructors for the Semantic Graph.

Supported node types:
- TableNode: Represents physical/canonical logical tables.
- ColumnNode: Represents normalized columns.
- EntityNode: Represents real-world business entities (e.g. PERSON, STORE, PRODUCT).
- GrainNode: Represents canonical and composite grain definitions.
- DimensionNode: Represents contextual categorical/dimensional attributes.
- MeasureNode: Represents raw numerical quantitative measurements with unit and additivity.
- MetricNode: Represents derived reusable governed metrics (both Local and Relational).
- TimeNode: Represents temporal anchor dimensions and grains.
- SemanticFamilyNode: Represents domain-neutral concept groupings.
"""

from typing import Any
from app.services.ingestion_v2.contracts.semantic_graph import (
    GraphNodeType,
    SemanticGraphNode,
)


def create_table_node(
    table_id: str,
    table_name: str,
    *,
    row_count: int = 0,
    column_count: int = 0,
    storage_format: str = "PARQUET",
    provenance_ref: str | None = None,
    properties: dict[str, Any] | None = None,
) -> SemanticGraphNode:
    props: dict[str, Any] = {
        "table_id": table_id,
        "table_name": table_name,
        "row_count": row_count,
        "column_count": column_count,
        "storage_format": storage_format,
    }
    if provenance_ref:
        props["provenance_ref"] = provenance_ref
    if properties:
        props.update(properties)

    return SemanticGraphNode(
        node_id=f"table:{table_id}",
        node_type=GraphNodeType.TABLE,
        label=table_name,
        properties=props,
    )


def create_column_node(
    table_id: str,
    column_name: str,
    data_type: str,
    *,
    semantic_role: str | None = None,
    concept: str | None = None,
    entity_type: str | None = None,
    provenance_ref: str | None = None,
    properties: dict[str, Any] | None = None,
) -> SemanticGraphNode:
    props: dict[str, Any] = {
        "table_id": table_id,
        "column_name": column_name,
        "data_type": data_type,
    }
    if semantic_role:
        props["semantic_role"] = semantic_role
    if concept:
        props["concept"] = concept
    if entity_type:
        props["entity_type"] = entity_type
    if provenance_ref:
        props["provenance_ref"] = provenance_ref
    if properties:
        props.update(properties)

    return SemanticGraphNode(
        node_id=f"col:{table_id}.{column_name}",
        node_type=GraphNodeType.COLUMN,
        label=f"{table_id}.{column_name}",
        properties=props,
    )


def create_entity_node(
    entity_type: str,
    *,
    primary_table_id: str | None = None,
    key_column: str | None = None,
    provenance_ref: str | None = None,
    properties: dict[str, Any] | None = None,
) -> SemanticGraphNode:
    props: dict[str, Any] = {
        "entity_type": entity_type.upper(),
    }
    if primary_table_id:
        props["primary_table_id"] = primary_table_id
    if key_column:
        props["key_column"] = key_column
    if provenance_ref:
        props["provenance_ref"] = provenance_ref
    if properties:
        props.update(properties)

    return SemanticGraphNode(
        node_id=f"entity:{entity_type.upper()}",
        node_type=GraphNodeType.ENTITY,
        label=entity_type.upper(),
        properties=props,
    )


def create_grain_node(
    grain_expression: str,
    *,
    table_id: str | None = None,
    key_columns: list[str] | None = None,
    provenance_ref: str | None = None,
    properties: dict[str, Any] | None = None,
) -> SemanticGraphNode:
    props: dict[str, Any] = {
        "grain_expression": grain_expression.upper(),
        "key_columns": key_columns or [],
    }
    if table_id:
        props["table_id"] = table_id
    if provenance_ref:
        props["provenance_ref"] = provenance_ref
    if properties:
        props.update(properties)

    return SemanticGraphNode(
        node_id=f"grain:{grain_expression.upper()}",
        node_type=GraphNodeType.GRAIN,
        label=grain_expression.upper(),
        properties=props,
    )


def create_dimension_node(
    dimension_id: str,
    name: str,
    *,
    table_id: str | None = None,
    source_column: str | None = None,
    cardinality: int | None = None,
    entity_type: str | None = None,
    provenance_ref: str | None = None,
    properties: dict[str, Any] | None = None,
) -> SemanticGraphNode:
    props: dict[str, Any] = {
        "dimension_id": dimension_id,
        "name": name,
    }
    if table_id:
        props["table_id"] = table_id
    if source_column:
        props["source_column"] = source_column
    if cardinality is not None:
        props["cardinality"] = cardinality
    if entity_type:
        props["entity_type"] = entity_type
    if provenance_ref:
        props["provenance_ref"] = provenance_ref
    if properties:
        props.update(properties)

    return SemanticGraphNode(
        node_id=f"dim:{dimension_id}",
        node_type=GraphNodeType.DIMENSION,
        label=name,
        properties=props,
    )


def create_measure_node(
    measure_id: str,
    name: str,
    *,
    table_id: str | None = None,
    source_column: str | None = None,
    data_type: str = "FLOAT",
    unit: str | None = None,
    additivity: str = "ADDITIVE",
    provenance_ref: str | None = None,
    properties: dict[str, Any] | None = None,
) -> SemanticGraphNode:
    props: dict[str, Any] = {
        "measure_id": measure_id,
        "name": name,
        "data_type": data_type,
        "unit": unit,
        "additivity": additivity.upper(),
    }
    if table_id:
        props["table_id"] = table_id
    if source_column:
        props["source_column"] = source_column
    if provenance_ref:
        props["provenance_ref"] = provenance_ref
    if properties:
        props.update(properties)

    return SemanticGraphNode(
        node_id=f"measure:{measure_id}",
        node_type=GraphNodeType.MEASURE,
        label=name,
        properties=props,
    )


def create_metric_node(
    metric_id: str,
    metric_name: str,
    formula: str,
    target_grain: str,
    *,
    metric_type: str = "LOCAL",
    source_table_ids: list[str] | None = None,
    source_column_ids: list[str] | None = None,
    unit: str | None = None,
    additivity: str = "NON_ADDITIVE",
    numerator_definition: str | None = None,
    denominator_definition: str | None = None,
    join_plan_id: str | None = None,
    fingerprint: str | None = None,
    evidence_ref: str | None = None,
    provenance_refs: list[str] | None = None,
    display_aliases: list[str] | None = None,
    properties: dict[str, Any] | None = None,
) -> SemanticGraphNode:
    props: dict[str, Any] = {
        "metric_id": metric_id,
        "metric_name": metric_name,
        "formula": formula,
        "target_grain": target_grain.upper(),
        "metric_type": metric_type.upper(),
        "source_table_ids": source_table_ids or [],
        "source_column_ids": source_column_ids or [],
        "unit": unit,
        "additivity": additivity.upper(),
        "numerator_definition": numerator_definition,
        "denominator_definition": denominator_definition,
        "join_plan_id": join_plan_id,
        "fingerprint": fingerprint or "",
        "provenance_refs": provenance_refs or [],
        "display_aliases": display_aliases or [],
    }
    if properties:
        props.update(properties)

    return SemanticGraphNode(
        node_id=f"metric:{metric_id}",
        node_type=GraphNodeType.METRIC,
        label=metric_name,
        properties=props,
        evidence_ref=evidence_ref,
    )


def create_time_node(
    time_id: str,
    column_name: str,
    temporal_grain: str,
    *,
    table_id: str | None = None,
    provenance_ref: str | None = None,
    properties: dict[str, Any] | None = None,
) -> SemanticGraphNode:
    props: dict[str, Any] = {
        "time_id": time_id,
        "column_name": column_name,
        "temporal_grain": temporal_grain.upper(),
    }
    if table_id:
        props["table_id"] = table_id
    if provenance_ref:
        props["provenance_ref"] = provenance_ref
    if properties:
        props.update(properties)

    return SemanticGraphNode(
        node_id=f"time:{time_id}",
        node_type=GraphNodeType.TIME,
        label=f"{column_name} ({temporal_grain.upper()})",
        properties=props,
    )


def create_semantic_family_node(
    family_id: str,
    family_name: str,
    concept_type: str,
    *,
    metric_ids: list[str] | None = None,
    dimension_ids: list[str] | None = None,
    entity_types: list[str] | None = None,
    grain_scope: str | None = None,
    description: str | None = None,
    properties: dict[str, Any] | None = None,
) -> SemanticGraphNode:
    props: dict[str, Any] = {
        "family_id": family_id,
        "family_name": family_name,
        "concept_type": concept_type.upper(),
        "metric_ids": metric_ids or [],
        "dimension_ids": dimension_ids or [],
        "entity_types": entity_types or [],
        "grain_scope": grain_scope,
        "description": description,
    }
    if properties:
        props.update(properties)

    return SemanticGraphNode(
        node_id=f"family:{family_id}",
        node_type=GraphNodeType.SEMANTIC_FAMILY,
        label=family_name,
        properties=props,
    )
