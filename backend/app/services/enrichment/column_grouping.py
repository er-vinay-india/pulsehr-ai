"""Semantic Column Grouping Engine (Stage 4).

Builds a relationship graph where columns are nodes and strong dependencies are edges.
Clusters related columns into isolated semantic groups (G1...Gf) to bound formula discovery
and eliminate combinatorial cartesian explosion.
"""

from __future__ import annotations

import collections
import itertools
import logging
from typing import Any

from .models import ColumnRelationship, EnrichmentColumnProfile, SemanticColumnGroup, SemanticRole

logger = logging.getLogger(__name__)


class ColumnGroupingEngine:
    """Clusters dataset columns into coherent semantic groups using graph component analysis."""

    @classmethod
    def group_columns(
        cls,
        columns: list[str],
        relationships: list[ColumnRelationship],
        profiles: dict[str, EnrichmentColumnProfile],
        min_relationship_score: float = 0.60
    ) -> list[SemanticColumnGroup]:
        """Builds relationship graph and clusters nodes into semantic groups G1...Gf."""
        if not columns:
            return []

        # Build adjacency map and edge weights
        adj: dict[str, set[str]] = {col: set() for col in columns}
        edge_weights: dict[tuple[str, str], float] = {}

        for rel in relationships:
            if rel.relationship_score >= min_relationship_score:
                u, v = rel.left_column, rel.right_column
                if u in adj and v in adj:
                    adj[u].add(v)
                    adj[v].add(u)
                    pair = (min(u, v), max(u, v))
                    edge_weights[pair] = rel.relationship_score

        # Connected components via BFS
        visited: set[str] = set()
        components: list[list[str]] = []

        for col in columns:
            if col not in visited:
                comp: list[str] = []
                queue = collections.deque([col])
                visited.add(col)
                while queue:
                    curr = queue.popleft()
                    comp.append(curr)
                    for neighbor in adj[curr]:
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append(neighbor)
                components.append(comp)

        semantic_groups: list[SemanticColumnGroup] = []
        group_counter = 1

        for comp_cols in components:
            # If component is very large (> 8 columns), partition by strongest mutual connections
            if len(comp_cols) > 8:
                clusters = cls._partition_large_component(comp_cols, edge_weights, profiles, min_relationship_score)
            else:
                clusters = [comp_cols]

            for cluster in clusters:
                g_id = f"G{group_counter}"
                interpretation, g_name = cls._infer_group_domain(cluster, profiles)
                cohesion = cls._calculate_cohesion(cluster, edge_weights)

                # Gather primary roles
                role_counts = collections.Counter()
                for c in cluster:
                    prof = profiles.get(c)
                    if prof:
                        for r in prof.roles:
                            role_counts[r] += 1
                primary_roles = [r for r, _ in role_counts.most_common(3)]

                semantic_groups.append(
                    SemanticColumnGroup(
                        group_id=g_id,
                        group_name=g_name,
                        domain_interpretation=interpretation,
                        columns=cluster,
                        primary_roles=primary_roles,
                        cohesion_score=cohesion
                    )
                )
                group_counter += 1

        recall_stats = cls.measure_relationship_recall(semantic_groups, relationships, min_relationship_score)
        logger.info(
            "Semantic grouping complete: %d groups created. Relationship recall: %.2f (%d/%d edges preserved)",
            len(semantic_groups),
            recall_stats["recall"],
            recall_stats["captured_edges"],
            recall_stats["total_eligible_edges"],
        )

        return semantic_groups

    @classmethod
    def measure_relationship_recall(
        cls,
        semantic_groups: list[SemanticColumnGroup],
        relationships: list[ColumnRelationship],
        min_relationship_score: float = 0.60
    ) -> dict[str, Any]:
        """Measures the candidate relationship recall preserved within the semantic groups.

        Recall is the fraction of eligible relationships (relationship_score >= min_relationship_score)
        where both endpoint columns appear together in at least one semantic column group.
        """
        eligible = [
            rel for rel in relationships
            if rel.relationship_score >= min_relationship_score
        ]
        if not eligible:
            return {
                "recall": 1.0,
                "total_eligible_edges": 0,
                "captured_edges": 0,
                "missed_edges": [],
            }

        group_col_sets = [set(g.columns) for g in semantic_groups]

        captured = 0
        missed = []
        for rel in eligible:
            u, v = rel.left_column, rel.right_column
            if any(u in s and v in s for s in group_col_sets):
                captured += 1
            else:
                missed.append({
                    "left_column": u,
                    "right_column": v,
                    "score": rel.relationship_score,
                    "type": rel.relationship_type,
                })

        recall = captured / len(eligible)
        return {
            "recall": round(float(recall), 4),
            "total_eligible_edges": len(eligible),
            "captured_edges": captured,
            "missed_edges": missed,
        }

    @classmethod
    def _partition_large_component(
        cls,
        columns: list[str],
        edge_weights: dict[tuple[str, str], float],
        profiles: dict[str, EnrichmentColumnProfile] | None = None,
        min_relationship_score: float = 0.60,
    ) -> list[list[str]]:
        """Partitions large components into tighter subclusters while preserving bridge pathways."""
        clusters: list[list[str]] = []
        unassigned = set(columns)

        while unassigned:
            seed = unassigned.pop()
            cluster = [seed]
            candidates = sorted(
                list(unassigned),
                key=lambda c: edge_weights.get((min(seed, c), max(seed, c)), 0.0),
                reverse=True
            )
            for cand in candidates[:5]:
                w = edge_weights.get((min(seed, cand), max(seed, cand)), 0.0)
                if w > 0.5:
                    cluster.append(cand)
                    unassigned.remove(cand)
            clusters.append(cluster)

        # Bridge preservation: identify strong edges cut across clusters and bridge them
        cluster_sets = [set(c) for c in clusters]
        for (u, v), w in edge_weights.items():
            if w >= min_relationship_score and u in columns and v in columns:
                u_in = [i for i, cs in enumerate(cluster_sets) if u in cs]
                v_in = [i for i, cs in enumerate(cluster_sets) if v in cs]
                shared = set(u_in).intersection(set(v_in))
                if not shared and u_in and v_in:
                    c_idx = u_in[0] if len(clusters[u_in[0]]) <= len(clusters[v_in[0]]) else v_in[0]
                    target_to_add = v if c_idx == u_in[0] else u
                    if len(clusters[c_idx]) < 12 and target_to_add not in cluster_sets[c_idx]:
                        clusters[c_idx].append(target_to_add)
                        cluster_sets[c_idx].add(target_to_add)

        return clusters

    @classmethod
    def _calculate_cohesion(
        cls,
        columns: list[str],
        edge_weights: dict[tuple[str, str], float]
    ) -> float:
        """Calculates average edge weight within the cluster."""
        if len(columns) <= 1:
            return 1.0
        weights: list[float] = []
        for i in range(len(columns)):
            for j in range(i + 1, len(columns)):
                pair = (min(columns[i], columns[j]), max(columns[i], columns[j]))
                if pair in edge_weights:
                    weights.append(edge_weights[pair])
        return round(float(sum(weights) / max(1, len(weights))), 4) if weights else 0.5

    @classmethod
    def _infer_group_domain(
        cls,
        columns: list[str],
        profiles: dict[str, EnrichmentColumnProfile]
    ) -> tuple[str, str]:
        """Infers an interpretable domain description and title for a semantic group."""
        col_text = " ".join([c.lower() for c in columns])
        units = {profiles[c].detected_unit.lower() for c in columns if profiles.get(c) and profiles[c].detected_unit}
        roles = {r for c in columns if profiles.get(c) for r in profiles[c].roles}

        if any(w in col_text for w in ("distance", "speed", "trip", "travel", "fuel", "mileage", "route")) or ("km" in units or "mph" in units):
            return "Transportation / Motion Dynamics", "Transportation & Motion"

        if any(w in col_text for w in ("mass", "volume", "density", "weight", "material", "area", "temperature")) or ("kg" in units or "l" in units):
            return "Physical & Material Properties", "Physical Properties"

        if any(w in col_text for w in ("price", "cost", "revenue", "sales", "margin", "profit", "discount", "tax")) or ("$" in units or "inr" in units or "eur" in units):
            return "Financial & Economic Margins", "Financial Economics"

        if any(w in col_text for w in ("employee", "overtime", "headcount", "salary", "shift", "attendance", "absent")):
            return "Workforce & Operational Capacity", "Workforce Operations"

        if any(w in col_text for w in ("order", "ship", "delivery", "transit", "warehouse", "inventory")):
            return "Supply Chain Logistics", "Supply Chain"

        if SemanticRole.TIME in roles:
            return "Temporal Timeline & Event Progression", "Temporal Progression"

        if SemanticRole.SCIENTIFIC_MEASURE in roles:
            return "Scientific Quantitative Metrics", "Scientific Measures"

        if SemanticRole.CATEGORY in roles:
            return "Categorical & Organizational Dimensions", "Organizational Dimensions"

        return "General Analytical Segment", f"Analytical Group ({', '.join(columns[:2])})"
