"""
HighView Ingestion V2 — Semantic Graph Contract
Stage 10: Semantic Graph
Boundary: Structured knowledge graph integrating schema, semantics, relationships, and metrics.
Preserves Silver-level provenance coordinates and HighView Evidence references across all nodes and edges.
"""

from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from app.services.ingestion_v2.contracts.base import IngestionContractBase


class GraphNodeType(str, Enum):
    TABLE = "TABLE"
    COLUMN = "COLUMN"
    ENTITY = "ENTITY"
    GRAIN = "GRAIN"
    METRIC = "METRIC"
    FINDING = "FINDING"
    DIMENSION = "DIMENSION"
    MEASURE = "MEASURE"
    TIME = "TIME"
    SEMANTIC_FAMILY = "SEMANTIC_FAMILY"


class GraphEdgeType(str, Enum):
    CONTAINS = "CONTAINS"
    HAS_ROLE = "HAS_ROLE"
    IDENTIFIES_GRAIN = "IDENTIFIES_GRAIN"
    RELATES_TO = "RELATES_TO"
    MEASURES = "MEASURES"
    SUPPORTS_FINDING = "SUPPORTS_FINDING"
    STRUCTURAL_RELATIONSHIP = "STRUCTURAL_RELATIONSHIP"
    SEMANTIC_RELATIONSHIP = "SEMANTIC_RELATIONSHIP"
    DERIVED_FROM = "DERIVED_FROM"
    MEASURED_AT_GRAIN = "MEASURED_AT_GRAIN"
    USES_JOIN_PLAN = "USES_JOIN_PLAN"
    SUPPORTED_BY_EVIDENCE = "SUPPORTED_BY_EVIDENCE"
    HAS_DIMENSION = "HAS_DIMENSION"
    SOURCE_PROVENANCE = "SOURCE_PROVENANCE"
    BELONGS_TO_FAMILY = "BELONGS_TO_FAMILY"


class SemanticGraphNode(BaseModel):
    """
    Typed node in the semantic graph.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    node_id: str
    node_type: GraphNodeType
    label: str
    properties: dict[str, Any] = Field(default_factory=dict)
    evidence_ref: str | None = None


class SemanticGraphEdge(BaseModel):
    """
    Typed directed edge in the semantic graph.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    edge_id: str
    source_node_id: str
    target_node_id: str
    edge_type: GraphEdgeType
    weight: float = 1.0
    properties: dict[str, Any] = Field(default_factory=dict)
    evidence_ref: str | None = None


class SemanticGraph(IngestionContractBase):
    """
    Stage 10 Contract: Semantic Graph.
    """
    stage_name: str = "semantic_graph"

    nodes: list[SemanticGraphNode] = Field(default_factory=list)
    edges: list[SemanticGraphEdge] = Field(default_factory=list)
    node_count: int = 0
    edge_count: int = 0
    metrics_count: int = 0
    families_count: int = 0
    graph_fingerprint: str = ""

