"""
HighView Ingestion V2 — Semantic Graph Identity & Deterministic Serialization
Stage 10: Semantic Graph
Provides deterministic SHA-256 fingerprinting and canonical serialization for SemanticGraph.

Invariants:
1. 10-run serialization is byte-for-byte identical.
2. Fingerprint is strictly invariant to timestamps, run_ids, memory addresses, or non-deterministic dictionary orderings.
3. Any semantic change in nodes, edges, grain, metrics, or relationships produces a new fingerprint.
"""

import hashlib
import json
from typing import Any
from app.services.ingestion_v2.contracts.semantic_graph import SemanticGraph

VOLATILE_KEYS = {
    "run_id",
    "timestamp",
    "created_at",
    "updated_at",
    "latency_ms",
    "execution_time",
    "cache_hit",
}


def _clean_properties(props: dict[str, Any]) -> dict[str, Any]:
    """Removes volatile runtime keys from node or edge properties."""
    cleaned: dict[str, Any] = {}
    for k, v in sorted(props.items()):
        if k.lower() in VOLATILE_KEYS:
            continue
        if isinstance(v, dict):
            cleaned[k] = _clean_properties(v)
        elif isinstance(v, (list, tuple, set)):
            # Deterministically sort collections where possible
            try:
                cleaned[k] = sorted(list(v))
            except TypeError:
                cleaned[k] = list(v)
        else:
            cleaned[k] = v
    return cleaned


def serialize_graph_canonical(graph: SemanticGraph) -> bytes:
    """
    Serializes a SemanticGraph into deterministic canonical UTF-8 JSON bytes.
    guarantees identical byte output across multiple runs.
    """
    # 1. Canonical sort nodes by node_id
    sorted_nodes = []
    for node in sorted(graph.nodes, key=lambda n: n.node_id):
        sorted_nodes.append({
            "node_id": node.node_id,
            "node_type": node.node_type.value,
            "label": node.label,
            "properties": _clean_properties(node.properties),
            "evidence_ref": node.evidence_ref,
        })

    # 2. Canonical sort edges by (source_node_id, target_node_id, edge_type, edge_id)
    sorted_edges = []
    for edge in sorted(
        graph.edges,
        key=lambda e: (e.source_node_id, e.target_node_id, e.edge_type.value, e.edge_id),
    ):
        sorted_edges.append({
            "edge_id": edge.edge_id,
            "source_node_id": edge.source_node_id,
            "target_node_id": edge.target_node_id,
            "edge_type": edge.edge_type.value,
            "weight": edge.weight,
            "properties": _clean_properties(edge.properties),
            "evidence_ref": edge.evidence_ref,
        })

    payload = {
        "dataset_id": graph.dataset_id,
        "nodes": sorted_nodes,
        "edges": sorted_edges,
    }

    canonical_json_str = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return canonical_json_str.encode("utf-8")


def compute_graph_fingerprint(graph: SemanticGraph) -> str:
    """
    Computes a deterministic SHA-256 fingerprint for a SemanticGraph.
    """
    canonical_bytes = serialize_graph_canonical(graph)
    return hashlib.sha256(canonical_bytes).hexdigest()
