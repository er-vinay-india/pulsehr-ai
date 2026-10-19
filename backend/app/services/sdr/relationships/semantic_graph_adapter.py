"""
HighView Semantic Data Refinery — Phase SDR-5
Semantic Graph Adapter

Bridges SDR-5 validated relationships and governed JoinPlans into the Ingestion V2 SemanticGraph.
Strictly enforces:
- Validated relationship edges may enter SemanticGraph.
- Candidate edges must NOT masquerade as validated graph truth.
- Traversal distinguishes: candidate, validated, and join-authorized.
"""

from __future__ import annotations

from typing import Any, Sequence

from app.services.ingestion_v2.contracts.relationships import RelationshipStatus
from app.services.ingestion_v2.contracts.semantic_graph import (
    GraphEdgeType,
    GraphNodeType,
    SemanticGraph,
    SemanticGraphEdge,
    SemanticGraphNode,
)
from app.services.sdr.contracts.relationships import (
    SDRJoinPlan,
    SDRRelationshipCandidate,
    SDRValidatedRelationshipEdge,
)


class SDRSemanticGraphAdapter:
    """
    Governed adapter integrating SDR-5 outputs into the global SemanticGraph.
    """

    @staticmethod
    def load_relationships_into_graph(
        graph: SemanticGraph,
        validated_edges: Sequence[SDRValidatedRelationshipEdge],
        join_plans: Sequence[SDRJoinPlan] | None = None,
        candidates: Sequence[SDRRelationshipCandidate] | None = None,
    ) -> SemanticGraph:
        """
        Integrates validated relationship edges and join plans into an existing SemanticGraph.
        Candidate edges are strictly segregated or marked PROVISIONAL, never validated truth.
        """
        existing_nodes = {n.node_id: n for n in graph.nodes}
        existing_edges = {(e.source_node_id, e.target_node_id, e.edge_type): e for e in graph.edges}

        new_nodes: list[SemanticGraphNode] = []
        new_edges: list[SemanticGraphEdge] = []

        # 1. Add Validated Relationship Edges
        for edge in validated_edges:
            if edge.status != RelationshipStatus.VALIDATED:
                continue

            src_col = edge.left_column_ids[0] if edge.left_column_ids else "id"
            tgt_col = edge.right_column_ids[0] if edge.right_column_ids else "id"
            src_node_id = f"col:{edge.left_sheet_id}.{src_col}"
            tgt_node_id = f"col:{edge.right_sheet_id}.{tgt_col}"

            # Ensure column nodes exist in graph (or create placeholder nodes)
            if src_node_id not in existing_nodes:
                node = SemanticGraphNode(
                    node_id=src_node_id,
                    node_type=GraphNodeType.COLUMN,
                    label=src_col,
                    properties={"table_id": edge.left_sheet_id},
                )
                existing_nodes[src_node_id] = node
                new_nodes.append(node)

            if tgt_node_id not in existing_nodes:
                node = SemanticGraphNode(
                    node_id=tgt_node_id,
                    node_type=GraphNodeType.COLUMN,
                    label=tgt_col,
                    properties={"table_id": edge.right_sheet_id},
                )
                existing_nodes[tgt_node_id] = node
                new_nodes.append(node)

            edge_key = (src_node_id, tgt_node_id, GraphEdgeType.STRUCTURAL_RELATIONSHIP)
            if edge_key not in existing_edges:
                rel_edge = SemanticGraphEdge(
                    edge_id=edge.edge_id,
                    edge_type=GraphEdgeType.STRUCTURAL_RELATIONSHIP,
                    source_node_id=src_node_id,
                    target_node_id=tgt_node_id,
                    weight=edge.confidence,
                    evidence_ref=f"sdr5:edge:{edge.edge_id}",
                    properties={
                        "cardinality": edge.cardinality.value,
                        "confidence": edge.confidence,
                        "is_validated": True,
                        "relationship_class": edge.relationship_class.value,
                        "referential_coverage": edge.referential_coverage,
                        "left_coverage": edge.left_coverage,
                        "right_coverage": edge.right_coverage,
                        "is_grain_preserving": edge.is_grain_preserving,
                        "duplication_risk_flag": edge.duplication_risk_flag,
                        "status": edge.status.value,
                        "authority": "VALIDATED_RELATIONSHIP_AUTHORITY",
                    },
                )
                existing_edges[edge_key] = rel_edge
                new_edges.append(rel_edge)

        # 2. Add Join-Authorized Edges from JoinPlans
        if join_plans:
            for plan in join_plans:
                if plan.safety_status not in ("SAFE", "SAFE_WITH_PREAGGREGATION"):
                    continue

                l_key = plan.left_keys[0] if plan.left_keys else "id"
                r_key = plan.right_keys[0] if plan.right_keys else "id"
                src_node_id = f"col:{plan.left_sheet_id}.{l_key}"
                tgt_node_id = f"col:{plan.right_sheet_id}.{r_key}"

                edge_key = (src_node_id, tgt_node_id, GraphEdgeType.USES_JOIN_PLAN)
                if edge_key not in existing_edges:
                    jp_edge = SemanticGraphEdge(
                        edge_id=f"edge_{plan.join_plan_id}",
                        edge_type=GraphEdgeType.USES_JOIN_PLAN,
                        source_node_id=src_node_id,
                        target_node_id=tgt_node_id,
                        weight=1.0,
                        evidence_ref=f"sdr5:join_plan:{plan.join_plan_id}",
                        properties={
                            "cardinality": plan.cardinality.value,
                            "join_plan_id": plan.join_plan_id,
                            "safety_status": plan.safety_status.value,
                            "join_type": plan.join_type,
                            "target_grain": plan.target_grain,
                            "required_preaggregation": plan.required_preaggregation,
                            "expansion_ratio": plan.expansion_ratio,
                            "authority": "JOIN_AUTHORIZED_METADATA",
                        },
                    )
                    existing_edges[edge_key] = jp_edge
                    new_edges.append(jp_edge)

        # Return updated SemanticGraph with distinct node/edge authorities
        return SemanticGraph(
            dataset_id=graph.dataset_id,
            run_id=graph.run_id,
            source_fingerprint=graph.source_fingerprint,
            nodes=list(existing_nodes.values()),
            edges=list(existing_edges.values()),
            node_count=len(existing_nodes),
            edge_count=len(existing_edges),
            graph_fingerprint=graph.graph_fingerprint,
        )
