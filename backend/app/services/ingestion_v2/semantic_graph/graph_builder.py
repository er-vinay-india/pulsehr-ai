"""
HighView Ingestion V2 — Semantic Graph Builder
Stage 10: Semantic Graph
Orchestrates the assembly of the governed SemanticGraph from validated upstream stages.

Inputs:
- NormalizedDataset (Stage 3)
- StructuralProfile (Stage 4)
- SemanticModel & GrainProfile (Stage 5)
- ValidatedRelationshipGraph & JoinPlans (Stage 7)
- AnalyticalProfile (Stage 8)
- EnrichedDataset (Stage 9)
- AnalysisIntent (Stage 12, optional metadata, strictly topology-neutral)

Invariants:
1. Organizes validated meaning; does not invent facts or numbers.
2. Permanent distinction: SemanticGraph owns business model structure; EvidenceGraph owns observed facts.
3. Zero new competing evidence IDs; strictly reuses upstream EVID-* tokens.
4. Metric derivation dependencies must be strictly acyclic (DAG).
5. Zero dangling edges and zero orphan metric inputs.
6. Deterministic: 10-run serialization is byte-for-byte identical.
7. AnalysisIntent neutrality: different objectives produce identical graph topology and metric definitions.
"""

from typing import Any, Sequence
from app.services.ingestion_v2.contracts.base import SourceCoordinateRef
from app.services.ingestion_v2.contracts.normalization import NormalizedDataset
from app.services.ingestion_v2.contracts.profiling import StructuralProfile
from app.services.ingestion_v2.contracts.semantics import (
    SemanticModel,
    SemanticColumnRole,
    TableSemanticModel,
    SemanticColumnAssignment,
)
from app.services.ingestion_v2.contracts.grain import GrainProfile
from app.services.ingestion_v2.contracts.relationships import (
    ValidatedRelationshipGraph,
    ValidatedRelationshipEdge,
)
from app.services.ingestion_v2.contracts.joins import GovernedJoinPlanSet, JoinPlan
from app.services.ingestion_v2.contracts.analytics import AnalyticalProfile
from app.services.ingestion_v2.contracts.enrichment import EnrichedDataset, SemanticFamily
from app.services.ingestion_v2.contracts.intent import AnalysisIntent
from app.services.ingestion_v2.contracts.semantic_graph import (
    GraphNodeType,
    GraphEdgeType,
    SemanticGraphNode,
    SemanticGraphEdge,
    SemanticGraph,
)
from app.services.ingestion_v2.semantic_graph.nodes import (
    create_table_node,
    create_column_node,
    create_entity_node,
    create_grain_node,
    create_dimension_node,
    create_measure_node,
    create_metric_node,
    create_time_node,
    create_semantic_family_node,
)
from app.services.ingestion_v2.semantic_graph.edges import (
    create_contains_edge,
    create_structural_relationship_edge,
    create_semantic_relationship_edge,
    create_derived_from_edge,
    create_measured_at_grain_edge,
    create_uses_join_plan_edge,
    create_supported_by_evidence_edge,
    create_has_dimension_edge,
    create_belongs_to_family_edge,
)
from app.services.ingestion_v2.semantic_graph.validators import SemanticGraphValidator
from app.services.ingestion_v2.semantic_graph.graph_identity import compute_graph_fingerprint


class SemanticGraphBuilder:
    """
    Governed builder for HighView Stage 10 SemanticGraph.
    """

    def __init__(self, validator: SemanticGraphValidator | None = None) -> None:
        self.validator = validator or SemanticGraphValidator()

    def build_graph(
        self,
        *,
        dataset_id: str,
        run_id: str,
        source_fingerprint: str,
        normalized_dataset: NormalizedDataset,
        structural_profile: StructuralProfile,
        semantic_model: SemanticModel,
        grain_profile: GrainProfile,
        relationships: ValidatedRelationshipGraph | Sequence[ValidatedRelationshipEdge] | None = None,
        join_plans: GovernedJoinPlanSet | Sequence[JoinPlan] | None = None,
        analytical_profile: AnalyticalProfile | None = None,
        enriched_dataset: EnrichedDataset | None = None,
        intent: AnalysisIntent | None = None,
        provenance: list[SourceCoordinateRef] | None = None,
        evidence_registry: set[str] | Sequence[str] | None = None,
    ) -> SemanticGraph:
        """
        Assembles and validates a complete SemanticGraph.
        """
        nodes_dict: dict[str, SemanticGraphNode] = {}
        edges_dict: dict[str, SemanticGraphEdge] = {}

        def add_node(node: SemanticGraphNode) -> None:
            nodes_dict[node.node_id] = node

        def add_edge(edge: SemanticGraphEdge) -> None:
            edges_dict[edge.edge_id] = edge

        # 1. Tables & Grains
        table_grains_map: dict[str, str] = {}
        for tg in grain_profile.table_grains:
            table_grains_map[tg.table_id] = tg.grain_expression
            grain_node = create_grain_node(
                grain_expression=tg.grain_expression,
                table_id=tg.table_id,
                key_columns=tg.key_columns,
            )
            add_node(grain_node)

        # Build table nodes from normalized_dataset and structural_profile
        table_meta_map = {t.table_id: t for t in structural_profile.tables}
        for norm_table in normalized_dataset.tables:
            t_id = norm_table.table_id
            t_name = norm_table.table_name
            t_meta = table_meta_map.get(t_id)
            row_count = t_meta.row_count if t_meta else norm_table.row_count
            col_count = t_meta.column_count if t_meta else getattr(norm_table, "column_count", 0)

            t_node = create_table_node(
                table_id=t_id,
                table_name=t_name,
                row_count=row_count,
                column_count=col_count,
            )
            add_node(t_node)

            # Link Table -> Grain
            t_grain = table_grains_map.get(t_id) or "UNKNOWN"
            if f"grain:{t_grain.upper()}" in nodes_dict:
                add_edge(create_measured_at_grain_edge(t_node.node_id, f"grain:{t_grain.upper()}"))

        # 2. Columns, Entities, Dimensions, Measures, Time Nodes
        # Map semantic columns by (table_id, column_name)
        sem_col_map: dict[tuple[str, str], Any] = {}
        if hasattr(semantic_model, "tables") and semantic_model.tables:
            for t_model in semantic_model.tables:
                for sc in t_model.columns:
                    tbl_id = getattr(sc, "table_id", None) or t_model.table_id
                    sem_col_map[(tbl_id, sc.column_name)] = sc
        elif hasattr(semantic_model, "columns") and semantic_model.columns:
            for sc in semantic_model.columns:
                sem_col_map[(sc.table_id, sc.column_name)] = sc

        for norm_table in normalized_dataset.tables:
            t_id = norm_table.table_id
            cols_info: list[tuple[str, str]] = []
            if hasattr(norm_table, "columns") and norm_table.columns:
                for nc in norm_table.columns:
                    c_type = nc.canonical_type.value if hasattr(nc.canonical_type, "value") else str(nc.canonical_type)
                    cols_info.append((nc.column_name, c_type))
            elif hasattr(norm_table, "schema") and isinstance(norm_table.schema, dict):
                for col_name, col_meta in norm_table.schema.get("columns", {}).items():
                    c_type = col_meta.get("data_type", "STRING") if isinstance(col_meta, dict) else str(col_meta)
                    cols_info.append((col_name, c_type))

            for col_name, col_type in cols_info:
                sem_col = sem_col_map.get((t_id, col_name))

                sem_role = (
                    sem_col.role.value if hasattr(sem_col, "role") and hasattr(sem_col.role, "value")
                    else str(sem_col.role) if hasattr(sem_col, "role")
                    else sem_col.semantic_role.value if hasattr(sem_col, "semantic_role") and hasattr(sem_col.semantic_role, "value")
                    else str(sem_col.semantic_role) if hasattr(sem_col, "semantic_role")
                    else None
                ) if sem_col else None

                concept = (
                    sem_col.semantic_concept.value if hasattr(sem_col, "semantic_concept") and hasattr(sem_col.semantic_concept, "value")
                    else str(sem_col.semantic_concept) if hasattr(sem_col, "semantic_concept")
                    else sem_col.concept.value if hasattr(sem_col, "concept") and hasattr(sem_col.concept, "value")
                    else str(sem_col.concept) if hasattr(sem_col, "concept")
                    else None
                ) if sem_col else None

                entity_t = (
                    sem_col.entity_type.value if hasattr(sem_col, "entity_type") and hasattr(sem_col.entity_type, "value")
                    else str(sem_col.entity_type) if hasattr(sem_col, "entity_type")
                    else None
                ) if sem_col and getattr(sem_col, "entity_type", None) not in ("UNKNOWN", None) else None

                col_node = create_column_node(
                    table_id=t_id,
                    column_name=col_name,
                    data_type=col_type,
                    semantic_role=sem_role,
                    concept=concept,
                    entity_type=entity_t,
                )
                add_node(col_node)

                # Table CONTAINS Column
                add_edge(create_contains_edge(f"table:{t_id}", col_node.node_id))

                # If Entity
                if entity_t:
                    e_node_id = f"entity:{entity_t.upper()}"
                    if e_node_id not in nodes_dict:
                        add_node(create_entity_node(entity_type=entity_t, primary_table_id=t_id, key_column=col_name))

                # If Measure
                if sem_role in (SemanticColumnRole.MEASURE.value, "MEASURE", "METRIC"):
                    m_id = f"{t_id}.{col_name}"
                    unit = getattr(sem_col, "unit", None)
                    additivity_val = getattr(sem_col, "additivity", "ADDITIVE")
                    if hasattr(additivity_val, "value"):
                        additivity_val = additivity_val.value
                    measure_node = create_measure_node(
                        measure_id=m_id,
                        name=col_name,
                        table_id=t_id,
                        source_column=col_name,
                        unit=unit,
                        additivity=str(additivity_val),
                    )
                    add_node(measure_node)
                    add_edge(create_derived_from_edge(measure_node.node_id, col_node.node_id))

                # If Dimension
                elif sem_role in (SemanticColumnRole.DIMENSION.value, "DIMENSION", "CATEGORY", "ATTRIBUTE"):
                    dim_id = f"{t_id}.{col_name}"
                    dim_node = create_dimension_node(
                        dimension_id=dim_id,
                        name=col_name,
                        table_id=t_id,
                        source_column=col_name,
                        entity_type=entity_t,
                    )
                    add_node(dim_node)
                    add_edge(create_has_dimension_edge(f"table:{t_id}", dim_node.node_id))

                # If Temporal
                elif sem_role in (SemanticColumnRole.TIME.value, "TIME", "TIMESTAMP", "TEMPORAL"):
                    time_id = f"{t_id}.{col_name}"
                    time_node = create_time_node(
                        time_id=time_id,
                        column_name=col_name,
                        temporal_grain="TEMPORAL",
                        table_id=t_id,
                    )
                    add_node(time_node)

        # 3. Relationships & JoinPlans
        rel_edges: Sequence[ValidatedRelationshipEdge] = []
        if isinstance(relationships, ValidatedRelationshipGraph):
            rel_edges = relationships.edges
        elif isinstance(relationships, (list, tuple)):
            rel_edges = relationships

        for re in rel_edges:
            src_table_node = f"table:{re.source_table_id}"
            tgt_table_node = f"table:{re.target_table_id}"
            if src_table_node in nodes_dict and tgt_table_node in nodes_dict:
                weight_val = getattr(re, "confidence", getattr(re, "confidence_score", 1.0))
                card_val = re.cardinality.value if hasattr(re.cardinality, "value") else str(re.cardinality)
                status_val = re.status.value if hasattr(re, "status") and hasattr(re.status, "value") else str(getattr(re, "status", "VALIDATED"))
                str_edge = create_structural_relationship_edge(
                    edge_id=re.edge_id,
                    source_node_id=src_table_node,
                    target_node_id=tgt_table_node,
                    cardinality=card_val,
                    weight=weight_val,
                    properties={"status": status_val},
                )
                add_edge(str_edge)

        # Build join plan lookup map
        jp_map: dict[str, JoinPlan] = {}
        if isinstance(join_plans, GovernedJoinPlanSet):
            jp_map = {jp.join_plan_id: jp for jp in join_plans.plans}
        elif isinstance(join_plans, (list, tuple)):
            jp_map = {jp.join_plan_id: jp for jp in join_plans}

        # 4. Metrics from Stage 9 EnrichedDataset
        if enriched_dataset:
            # Local Metrics
            for lm in enriched_dataset.local_metrics:
                m_node = create_metric_node(
                    metric_id=lm.metric_id,
                    metric_name=lm.metric_name,
                    formula=lm.formula,
                    target_grain=lm.target_grain or lm.grain,
                    metric_type="LOCAL",
                    source_table_ids=[lm.source_table_id or lm.table_id],
                    source_column_ids=lm.source_column_ids or lm.source_columns,
                    unit=lm.unit,
                    additivity=lm.additivity.value if hasattr(lm.additivity, "value") else str(lm.additivity),
                    numerator_definition=lm.numerator_definition,
                    denominator_definition=lm.denominator_definition,
                    fingerprint=lm.fingerprint,
                    provenance_refs=lm.provenance_refs,
                    display_aliases=lm.display_aliases,
                    evidence_ref=lm.evidence_refs[0] if lm.evidence_refs else None,
                )
                add_node(m_node)

                # Link Metric -> Grain
                g_key = (lm.target_grain or lm.grain).strip().upper()
                g_node_id = f"grain:{g_key}"
                if g_node_id not in nodes_dict:
                    add_node(create_grain_node(grain_expression=g_key))
                add_edge(create_measured_at_grain_edge(m_node.node_id, g_node_id))

                # Link Metric DERIVED_FROM source columns
                s_tbl = lm.source_table_id or lm.table_id
                for s_col in (lm.source_column_ids or lm.source_columns):
                    col_target_id = f"col:{s_tbl}.{s_col}"
                    if col_target_id in nodes_dict:
                        add_edge(create_derived_from_edge(m_node.node_id, col_target_id))

                # Link Metric -> Evidence
                for ev in lm.evidence_refs:
                    add_edge(create_supported_by_evidence_edge(m_node.node_id, ev))

            # Relational Metrics
            for rm in enriched_dataset.relational_metrics:
                rm_node = create_metric_node(
                    metric_id=rm.metric_id,
                    metric_name=rm.metric_name,
                    formula=rm.formula,
                    target_grain=rm.target_grain,
                    metric_type="RELATIONAL",
                    source_table_ids=rm.source_table_ids,
                    source_column_ids=rm.source_column_ids,
                    unit=rm.unit,
                    additivity=rm.additivity.value if hasattr(rm.additivity, "value") else str(rm.additivity),
                    numerator_definition=rm.numerator_definition,
                    denominator_definition=rm.denominator_definition,
                    join_plan_id=rm.join_plan_id,
                    fingerprint=rm.fingerprint,
                    provenance_refs=rm.provenance_refs,
                    display_aliases=rm.display_aliases,
                    evidence_ref=rm.evidence_refs[0] if rm.evidence_refs else None,
                )
                add_node(rm_node)

                # Link Metric -> Grain
                g_key = rm.target_grain.strip().upper()
                g_node_id = f"grain:{g_key}"
                if g_node_id not in nodes_dict:
                    add_node(create_grain_node(grain_expression=g_key))
                add_edge(create_measured_at_grain_edge(rm_node.node_id, g_node_id))

                # Link Metric USES_JOIN_PLAN
                matched_jp = jp_map.get(rm.join_plan_id)
                jp_props = {}
                if matched_jp:
                    jp_props["safety_status"] = (
                        matched_jp.safety_status.value
                        if hasattr(matched_jp.safety_status, "value")
                        else str(matched_jp.safety_status)
                    )
                    if matched_jp.pre_aggregation:
                        jp_props["pre_aggregation"] = {
                            "source_table_id": matched_jp.pre_aggregation.source_table_id,
                            "target_grain": matched_jp.pre_aggregation.target_grain,
                            "group_by_columns": matched_jp.pre_aggregation.group_by_columns,
                        }
                add_edge(create_uses_join_plan_edge(
                    rm_node.node_id,
                    rm.join_plan_id,
                    target_grain=rm.target_grain,
                    properties=jp_props or None,
                ))

                # Link Metric DERIVED_FROM source columns / tables
                for s_tbl in rm.source_table_ids:
                    for s_col in rm.source_column_ids:
                        col_target_id = f"col:{s_tbl}.{s_col}"
                        if col_target_id in nodes_dict:
                            add_edge(create_derived_from_edge(rm_node.node_id, col_target_id))

                # Link Metric -> Evidence
                for ev in rm.evidence_refs:
                    add_edge(create_supported_by_evidence_edge(rm_node.node_id, ev))

            # Semantic Families
            for fam in enriched_dataset.semantic_families:
                fam_node = create_semantic_family_node(
                    family_id=fam.family_id,
                    family_name=fam.family_name,
                    concept_type=fam.concept_type,
                    metric_ids=fam.metric_ids,
                    dimension_ids=fam.dimension_ids,
                    entity_types=fam.entity_types,
                    grain_scope=fam.grain_scope,
                    description=fam.description,
                )
                add_node(fam_node)

                # Edges: Metric BELONGS_TO_FAMILY
                for m_id in fam.metric_ids:
                    m_nid = f"metric:{m_id}"
                    if m_nid in nodes_dict:
                        add_edge(create_belongs_to_family_edge(m_nid, fam_node.node_id))

                # Edges: Dimension BELONGS_TO_FAMILY
                for d_id in fam.dimension_ids:
                    d_nid = f"dim:{d_id}"
                    if d_nid in nodes_dict:
                        add_edge(create_belongs_to_family_edge(d_nid, fam_node.node_id))

        # 5. Upstream Evidence Integration (I5 findings linking to columns or metrics)
        if analytical_profile and analytical_profile.findings:
            for finding in analytical_profile.findings:
                ev_token = (
                    finding.evidence_ref if hasattr(finding, "evidence_ref") and finding.evidence_ref
                    else getattr(finding, "evidence_id", None)
                    or (finding.evidence_refs[0] if hasattr(finding, "evidence_refs") and finding.evidence_refs else None)
                )
                if not ev_token:
                    continue
                t_id = (
                    finding.affected_tables[0] if getattr(finding, "affected_tables", None)
                    else getattr(finding, "table_id", None)
                )
                c_name = (
                    finding.affected_columns[0] if getattr(finding, "affected_columns", None)
                    else getattr(finding, "column_name", None)
                )
                if t_id and c_name:
                    c_nid = f"col:{t_id}.{c_name}"
                    if c_nid in nodes_dict:
                        add_edge(create_supported_by_evidence_edge(c_nid, ev_token, finding_type=str(finding.finding_type)))

        nodes_list = sorted(list(nodes_dict.values()), key=lambda n: n.node_id)
        edges_list = sorted(list(edges_dict.values()), key=lambda e: (e.source_node_id, e.target_node_id, e.edge_type.value, e.edge_id))

        metric_count = sum(1 for n in nodes_list if n.node_type == GraphNodeType.METRIC)
        family_count = sum(1 for n in nodes_list if n.node_type == GraphNodeType.SEMANTIC_FAMILY)

        # Preliminary graph for fingerprinting and validation
        temp_graph = SemanticGraph(
            dataset_id=dataset_id,
            run_id=run_id,
            source_fingerprint=source_fingerprint,
            provenance=provenance or [SourceCoordinateRef(dataset_id=dataset_id, source_file_hash=source_fingerprint)],
            nodes=nodes_list,
            edges=edges_list,
            node_count=len(nodes_list),
            edge_count=len(edges_list),
            metrics_count=metric_count,
            families_count=family_count,
        )

        # Resolve evidence registry for existence verification
        active_evidence_registry: set[str] | None = None
        if evidence_registry is not None:
            active_evidence_registry = set(evidence_registry)
        elif analytical_profile and analytical_profile.findings:
            active_evidence_registry = set()
            for finding in analytical_profile.findings:
                ev = (
                    finding.evidence_ref if hasattr(finding, "evidence_ref") and finding.evidence_ref
                    else getattr(finding, "evidence_id", None)
                    or (finding.evidence_refs[0] if hasattr(finding, "evidence_refs") and finding.evidence_refs else None)
                )
                if ev:
                    active_evidence_registry.add(ev)
                if hasattr(finding, "evidence_refs") and finding.evidence_refs:
                    active_evidence_registry.update(finding.evidence_refs)

        # Validate topological integrity and evidence existence
        self.validator.validate(
            temp_graph,
            evidence_registry=active_evidence_registry,
            raise_on_error=True,
        )

        # Compute deterministic graph fingerprint
        graph_fp = compute_graph_fingerprint(temp_graph)

        final_graph = temp_graph.model_copy(update={"graph_fingerprint": graph_fp})
        return final_graph
