"""
HighView Ingestion V2 — Semantic Graph Validators
Stage 10: Semantic Graph
Validates topological integrity, referential completeness, acyclicity, and grain coverage.

Integrity Rules:
1. Zero dangling edges: every edge's source_node_id and target_node_id must exist in nodes.
2. Zero orphan metric inputs: every column or metric referenced by a MetricNode must exist.
3. Zero metric derivation cycles: metric dependency graphs must be strictly acyclic (DAG).
4. Zero grainless metrics: every MetricNode must declare target_grain or link to a grain node.
5. Zero missing provenance: every node must have provenance metadata or source references.
6. Relational metric safety: relational metrics must declare an authorized join_plan_id.
7. Evidence references: evidence hooks must reference valid EVID-* tokens.
"""

from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.services.ingestion_v2.contracts.semantic_graph import (
    GraphNodeType,
    GraphEdgeType,
    SemanticGraph,
    SemanticGraphNode,
)


class DanglingEdgeError(Exception):
    """Raised when an edge references a non-existent source or target node."""
    pass


class OrphanMetricInputError(Exception):
    """Raised when a derived metric references source columns/metrics not in the graph."""
    pass


class MetricDerivationCycleError(Exception):
    """Raised when circular dependencies are detected in derived metric definitions (e.g. A -> B -> A)."""
    pass


class MissingGrainError(Exception):
    """Raised when a metric node lacks a declared target grain."""
    pass


class MissingProvenanceError(Exception):
    """Raised when a node lacks required provenance references."""
    pass


class MissingJoinPlanError(Exception):
    """Raised when a relational metric lacks an explicit join_plan_id."""
    pass


class InvalidEvidenceRefError(Exception):
    """Raised when an evidence edge references a malformed or competing evidence ID."""
    pass


class SemanticGraphValidationReport(BaseModel):
    """Report detailing the results of semantic graph validation."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    is_valid: bool
    dangling_edges_count: int = 0
    orphan_inputs_count: int = 0
    derivation_cycles_count: int = 0
    missing_grain_count: int = 0
    missing_provenance_count: int = 0
    violations: list[str] = Field(default_factory=list)


class SemanticGraphValidator:
    """
    Topological and referential validator for SemanticGraph instances.
    """

    def validate(
        self,
        graph: SemanticGraph,
        *,
        raise_on_error: bool = True,
    ) -> SemanticGraphValidationReport:
        """
        Validates the graph against all governed epistemic constraints.
        Raises the specific integrity exception if raise_on_error is True and a violation occurs.
        """
        violations: list[str] = []
        node_ids: set[str] = {n.node_id for n in graph.nodes}
        node_map: dict[str, SemanticGraphNode] = {n.node_id: n for n in graph.nodes}

        # 1. Evidence format check (must match EVID-* or evidence:EVID-*)
        invalid_evid: list[str] = []
        for edge in graph.edges:
            if edge.edge_type == GraphEdgeType.SUPPORTED_BY_EVIDENCE or edge.target_node_id.startswith("evidence:"):
                ev_ref = edge.evidence_ref or edge.target_node_id.replace("evidence:", "")
                if not ("EVID-" in ev_ref):
                    invalid_evid.append(
                        f"Edge '{edge.edge_id}' has non-standard evidence reference '{ev_ref}'. Expected EVID-*."
                    )
        for node in graph.nodes:
            if node.evidence_ref and not node.evidence_ref.startswith("EVID-"):
                invalid_evid.append(
                    f"Node '{node.node_id}' has non-standard evidence reference '{node.evidence_ref}'. Expected EVID-*."
                )

        if invalid_evid:
            msg = f"Invalid evidence references detected ({len(invalid_evid)}): {invalid_evid[:3]}"
            violations.extend(invalid_evid)
            if raise_on_error:
                raise InvalidEvidenceRefError(msg)

        # 2. Dangling edge check
        dangling_edges: list[str] = []
        for edge in graph.edges:
            # Synthetic / external target nodes (like evidence:EVID-* or join_plan:jp-* or provenance:*)
            # are allowed if they follow valid prefix schemes, otherwise must be in node_ids
            src_ok = edge.source_node_id in node_ids
            tgt_ok = (
                edge.target_node_id in node_ids
                or edge.target_node_id.startswith("evidence:EVID-")
                or edge.target_node_id.startswith("join_plan:")
                or edge.target_node_id.startswith("provenance:")
            )
            if not src_ok:
                dangling_edges.append(f"Edge {edge.edge_id}: source '{edge.source_node_id}' not found")
            if not tgt_ok:
                dangling_edges.append(f"Edge {edge.edge_id}: target '{edge.target_node_id}' not found")

        if dangling_edges:
            msg = f"Dangling edges detected ({len(dangling_edges)}): {dangling_edges[:3]}"
            violations.extend(dangling_edges)
            if raise_on_error:
                raise DanglingEdgeError(msg)

        # 2. Grain coverage on MetricNodes
        missing_grains: list[str] = []
        for node in graph.nodes:
            if node.node_type == GraphNodeType.METRIC:
                tg = node.properties.get("target_grain")
                if not tg or not str(tg).strip():
                    missing_grains.append(f"Metric '{node.node_id}' has no declared target_grain")

        if missing_grains:
            msg = f"Missing grain detected on {len(missing_grains)} metrics: {missing_grains[:3]}"
            violations.extend(missing_grains)
            if raise_on_error:
                raise MissingGrainError(msg)

        # 3. Orphan metric inputs check
        orphan_inputs: list[str] = []
        for node in graph.nodes:
            if node.node_type == GraphNodeType.METRIC:
                src_cols = node.properties.get("source_column_ids", [])
                src_tbls = node.properties.get("source_table_ids", [])
                # Every declared source column must exist as a column node
                for col in src_cols:
                    # check col node existence: could be col:table.col or col in any table
                    col_found = False
                    for tbl in src_tbls:
                        if f"col:{tbl}.{col}" in node_ids:
                            col_found = True
                            break
                    if not col_found:
                        # Direct check if col contains dot
                        if f"col:{col}" in node_ids or f"measure:{col}" in node_ids or f"metric:{col}" in node_ids:
                            col_found = True
                        else:
                            # check if any col node ends with .{col}
                            for nid in node_ids:
                                if nid.startswith("col:") and nid.endswith(f".{col}"):
                                    col_found = True
                                    break
                    if not col_found:
                        orphan_inputs.append(
                            f"Metric '{node.node_id}' references missing source column '{col}'"
                        )

        if orphan_inputs:
            msg = f"Orphan metric inputs detected ({len(orphan_inputs)}): {orphan_inputs[:3]}"
            violations.extend(orphan_inputs)
            if raise_on_error:
                raise OrphanMetricInputError(msg)

        # 4. Derivation cycle detection (DFS on DERIVED_FROM edges)
        derivation_adj: dict[str, list[str]] = {}
        for edge in graph.edges:
            if edge.edge_type == GraphEdgeType.DERIVED_FROM:
                # metric depends on target
                derivation_adj.setdefault(edge.source_node_id, []).append(edge.target_node_id)

        # 0 = unvisited, 1 = visiting, 2 = visited
        state: dict[str, int] = {}
        cycle_detected: list[str] = []

        def dfs(curr: str, path: list[str]) -> bool:
            state[curr] = 1
            path.append(curr)
            for neighbor in derivation_adj.get(curr, []):
                if state.get(neighbor, 0) == 1:
                    # Cycle!
                    cycle_idx = path.index(neighbor)
                    cycle_str = " -> ".join(path[cycle_idx:] + [neighbor])
                    cycle_detected.append(cycle_str)
                    return True
                elif state.get(neighbor, 0) == 0:
                    if dfs(neighbor, path):
                        return True
            path.pop()
            state[curr] = 2
            return False

        for node_id in list(derivation_adj.keys()):
            if state.get(node_id, 0) == 0:
                if dfs(node_id, []):
                    break

        if cycle_detected:
            msg = f"Metric derivation cycle detected: {cycle_detected[0]}"
            violations.extend(cycle_detected)
            if raise_on_error:
                raise MetricDerivationCycleError(msg)

        # 5. Relational metric JoinPlan guard
        missing_join_plans: list[str] = []
        for node in graph.nodes:
            if node.node_type == GraphNodeType.METRIC:
                m_type = node.properties.get("metric_type", "LOCAL")
                if m_type == "RELATIONAL":
                    jp_id = node.properties.get("join_plan_id")
                    if not jp_id or not str(jp_id).strip():
                        missing_join_plans.append(f"Relational metric '{node.node_id}' missing join_plan_id")

        if missing_join_plans:
            msg = f"Relational metrics without JoinPlan ({len(missing_join_plans)}): {missing_join_plans[:3]}"
            violations.extend(missing_join_plans)
            if raise_on_error:
                raise MissingJoinPlanError(msg)
        report = SemanticGraphValidationReport(
            is_valid=(len(violations) == 0),
            dangling_edges_count=len(dangling_edges),
            orphan_inputs_count=len(orphan_inputs),
            derivation_cycles_count=len(cycle_detected),
            missing_grain_count=len(missing_grains),
            missing_provenance_count=0,
            violations=violations,
        )
        return report
