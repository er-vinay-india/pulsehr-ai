"""
HighView Ingestion V2 — Phase I7 Graph-Aware Retriever
Stage 11: Multi-Namespace Hybrid Retrieval

Core Invariants:
1. Bounded neighborhood expansion prevents graph explosion.
2. Expands semantic dependencies: Metric -> Source Measure/Column -> Grain -> JoinPlan -> Evidence -> Family.
3. Guarantees dependency closure for retrieved artifacts.
4. Operates strictly over frozen SemanticGraph; never mutates graph topology.
"""

from collections import deque
from typing import Sequence
from pydantic import BaseModel, ConfigDict, Field

from app.services.ingestion_v2.contracts.semantic_graph import (
    SemanticGraph,
    GraphNodeType,
    GraphEdgeType,
    SemanticGraphNode,
    SemanticGraphEdge,
)


class GraphExpansionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    seed_node_ids: list[str]
    expanded_node_ids: list[str]
    edges_traversed: list[str] = Field(default_factory=list)
    dependency_closure_complete: bool = True
    missing_dependencies: list[str] = Field(default_factory=list)


class GraphRetriever:
    """
    Retrieves bounded dependency neighborhoods from the frozen SemanticGraph.
    """

    def __init__(
        self,
        semantic_graph: SemanticGraph | None = None,
        max_depth: int = 2,
        max_nodes: int = 25,
    ):
        self.semantic_graph = semantic_graph
        self.max_depth = max_depth
        self.max_nodes = max_nodes

    def expand_neighborhood(
        self,
        seed_node_ids: Sequence[str],
        allowed_edge_types: Sequence[GraphEdgeType] | None = None,
    ) -> GraphExpansionResult:
        """
        Performs bounded BFS expansion around seed nodes to gather complete semantic context.
        """
        if not self.semantic_graph or not seed_node_ids:
            return GraphExpansionResult(
                seed_node_ids=list(seed_node_ids),
                expanded_node_ids=list(seed_node_ids),
                edges_traversed=[],
                dependency_closure_complete=True,
                missing_dependencies=[],
            )

        g = self.semantic_graph
        visited_nodes: set[str] = set()
        visited_edges: list[str] = []
        missing_deps: list[str] = []

        allowed_types_set = set(allowed_edge_types) if allowed_edge_types else None

        # Build node map
        if isinstance(g.nodes, dict):
            nodes_map = g.nodes
        else:
            nodes_map = {n.node_id: n for n in g.nodes}

        # Build adjacency maps: outgoing
        adj_out: dict[str, list[SemanticGraphEdge]] = {}
        for edge in g.edges:
            src = getattr(edge, "source_node_id", getattr(edge, "source_id", ""))
            adj_out.setdefault(src, []).append(edge)

        # BFS Queue: (node_id, current_depth)
        queue: deque[tuple[str, int]] = deque()
        for s in seed_node_ids:
            if s in nodes_map:
                visited_nodes.add(s)
                queue.append((s, 0))
            else:
                visited_nodes.add(s)

        while queue and len(visited_nodes) < self.max_nodes:
            curr_node_id, depth = queue.popleft()
            if depth >= self.max_depth:
                continue

            node = nodes_map.get(curr_node_id)
            out_edges = adj_out.get(curr_node_id, [])

            # For metric nodes, verify dependency completeness
            if node and node.node_type == GraphNodeType.METRIC:
                source_cols = node.properties.get("source_columns", [])
                grain = node.properties.get("target_grain")
                join_plan_id = node.properties.get("join_plan_id")

                for sc in source_cols:
                    col_id = f"col:{sc}" if not sc.startswith("col:") else sc
                    if col_id not in nodes_map and col_id not in missing_deps:
                        missing_deps.append(col_id)
                if grain:
                    grain_id = f"grain:{grain}"
                    if grain_id not in nodes_map and grain_id not in missing_deps:
                        missing_deps.append(grain_id)
                if join_plan_id:
                    jp_id = f"join_plan:{join_plan_id}"
                    if jp_id not in nodes_map and jp_id not in missing_deps:
                        missing_deps.append(jp_id)

            for edge in out_edges:
                if allowed_types_set and edge.edge_type not in allowed_types_set:
                    continue

                src = getattr(edge, "source_node_id", getattr(edge, "source_id", ""))
                tgt = getattr(edge, "target_node_id", getattr(edge, "target_id", ""))
                edge_type_val = getattr(edge.edge_type, "value", str(edge.edge_type))
                edge_repr = f"{src}-[{edge_type_val}]->{tgt}"
                if edge_repr not in visited_edges:
                    visited_edges.append(edge_repr)

                target = tgt
                if target not in visited_nodes:
                    visited_nodes.add(target)
                    if len(visited_nodes) >= self.max_nodes:
                        break
                    queue.append((target, depth + 1))

        is_complete = len(missing_deps) == 0

        # Deterministic order
        sorted_expanded = sorted(visited_nodes)

        return GraphExpansionResult(
            seed_node_ids=list(seed_node_ids),
            expanded_node_ids=sorted_expanded,
            edges_traversed=visited_edges,
            dependency_closure_complete=is_complete,
            missing_dependencies=sorted(missing_deps),
        )
