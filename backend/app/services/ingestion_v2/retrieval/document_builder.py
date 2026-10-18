"""
HighView Ingestion V2 — Phase I7 Retrieval Document Builder
Stage 11: Multi-Namespace Hybrid Retrieval

Transforms frozen I1–I6 artifacts into four strictly isolated retrieval namespaces:
- RAW_SCHEMA_INDEX: Physical tables, columns, profiles, candidate keys
- SEMANTIC_INDEX: Entities, dimensions, measures, metrics, grains, families, aliases
- RELATIONSHIP_INDEX: Validated edges, cardinalities, governed JoinPlans
- ANALYTICAL_INDEX: Observed EDA-B analytical findings with EVID-* tokens

Critical Epistemic Guards:
1. Zero unvalidated candidates in normal RELATIONSHIP_INDEX.
2. Zero recommendations or ExecutiveTopics in ANALYTICAL_INDEX.
3. Zero observed values copied into SEMANTIC_INDEX metric definitions.
4. Canonical structured_metadata is 100% authoritative.
"""

import hashlib
import json
from typing import Any, Sequence

from app.services.ingestion_v2.contracts.normalization import NormalizedDataset
from app.services.ingestion_v2.contracts.profiling import StructuralProfile
from app.services.ingestion_v2.contracts.relationships import ValidatedRelationshipGraph, RelationshipStatus
from app.services.ingestion_v2.contracts.analytics import AnalyticalProfile, AnalyticalFinding
from app.services.ingestion_v2.contracts.grain import GrainProfile
from app.services.ingestion_v2.joins.join_planner import JoinPlan
from app.services.ingestion_v2.contracts.enrichment import (
    EnrichedDataset,
    LocalDerivedMetric,
    RelationalDerivedMetric,
    SemanticFamily,
)
from app.services.ingestion_v2.contracts.semantic_graph import SemanticGraph
from app.services.ingestion_v2.retrieval.namespaces import AuthorityClass, RetrievalNamespace
from app.services.ingestion_v2.retrieval.documents import RetrievalDocument


class RetrievalDocumentBuilder:
    """
    Builds strongly-typed retrieval documents from frozen I1–I6 artifacts across
    the four canonical namespaces.
    """

    def __init__(self, index_version: str = "v1", embedding_model: str = "nomic-embed-text:latest"):
        self.index_version = index_version
        self.embedding_model = embedding_model

    def build_documents(
        self,
        normalized_dataset: NormalizedDataset,
        structural_profile: StructuralProfile | None = None,
        semantic_model: Any | None = None,
        grain_profile: GrainProfile | None = None,
        relationship_graph: ValidatedRelationshipGraph | None = None,
        join_plans: Sequence[JoinPlan] | None = None,
        analytical_profile: AnalyticalProfile | None = None,
        enriched_dataset: EnrichedDataset | None = None,
        semantic_graph: SemanticGraph | None = None,
        **kwargs: Any,
    ) -> list[RetrievalDocument]:
        """
        Builds all documents across the four namespaces.
        """
        docs: list[RetrievalDocument] = []
        dataset_id = str(normalized_dataset.dataset_id)
        dataset_version = getattr(normalized_dataset, "dataset_version", "1")
        source_fp = getattr(normalized_dataset, "source_fingerprint", "source_fp_default")
        graph_version = getattr(semantic_graph, "graph_fingerprint", None)

        rel_graph = relationship_graph or kwargs.get("relationships")

        # ---------------------------------------------------------
        # 1. RAW_SCHEMA_INDEX
        # ---------------------------------------------------------
        docs.extend(
            self._build_raw_schema_docs(
                normalized_dataset=normalized_dataset,
                structural_profile=structural_profile,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                source_fp=source_fp,
                graph_version=graph_version,
            )
        )

        # ---------------------------------------------------------
        # 2. SEMANTIC_INDEX
        # ---------------------------------------------------------
        docs.extend(
            self._build_semantic_docs(
                semantic_model=semantic_model,
                grain_profile=grain_profile,
                enriched_dataset=enriched_dataset,
                semantic_graph=semantic_graph,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                source_fp=source_fp,
                graph_version=graph_version,
            )
        )

        # ---------------------------------------------------------
        # 3. RELATIONSHIP_INDEX
        # ---------------------------------------------------------
        docs.extend(
            self._build_relationship_docs(
                relationship_graph=rel_graph,
                join_plans=join_plans,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                source_fp=source_fp,
                graph_version=graph_version,
            )
        )

        # ---------------------------------------------------------
        # 4. ANALYTICAL_INDEX
        # ---------------------------------------------------------
        docs.extend(
            self._build_analytical_docs(
                analytical_profile=analytical_profile,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                source_fp=source_fp,
                graph_version=graph_version,
            )
        )

        return docs

    def _build_raw_schema_docs(
        self,
        normalized_dataset: NormalizedDataset,
        structural_profile: StructuralProfile | None,
        dataset_id: str,
        dataset_version: str,
        source_fp: str,
        graph_version: str | None,
    ) -> list[RetrievalDocument]:
        docs: list[RetrievalDocument] = []
        profile_map = {}
        if structural_profile:
            raw_prof = getattr(structural_profile, "table_profiles", {})
            if isinstance(raw_prof, list):
                profile_map = {p.table_id: p for p in raw_prof}
            elif isinstance(raw_prof, dict):
                profile_map = raw_prof

        for table in normalized_dataset.tables:
            table_id = table.table_id
            t_prof = profile_map.get(table_id)

            # Table document
            row_count = getattr(t_prof, "row_count", getattr(table, "row_count", len(getattr(table, "rows", []))))
            col_count = len(table.columns)
            candidate_keys = getattr(t_prof, "candidate_primary_keys", [])

            t_name = getattr(table, "table_name", getattr(table, "sheet_name", table.table_id))
            table_text = f"Table {table_id} {t_name} with {col_count} columns and {row_count} rows. "
            if candidate_keys:
                table_text += f"Candidate primary keys: {', '.join(candidate_keys)}. "

            docs.append(
                RetrievalDocument.create(
                    document_id=f"raw:table:{dataset_id}:{table_id}",
                    namespace=RetrievalNamespace.RAW_SCHEMA,
                    authority_class=AuthorityClass.STRUCTURAL,
                    dataset_id=dataset_id,
                    dataset_version=dataset_version,
                    source_fingerprint=source_fp,
                    semantic_graph_version=graph_version,
                    artifact_type="table",
                    artifact_id=f"table:{table_id}",
                    text_for_retrieval=table_text,
                    structured_metadata={
                        "table_id": table_id,
                        "table_name": t_name,
                        "row_count": row_count,
                        "column_count": col_count,
                        "candidate_primary_keys": candidate_keys,
                    },
                    provenance_refs=[f"prov:table:{table_id}"],
                    index_version=self.index_version,
                )
            )

            # Column documents
            for col in table.columns:
                col_name = getattr(col, "column_name", getattr(col, "name", "unknown"))
                phys_type = getattr(col, "canonical_type", getattr(col, "physical_type", "string"))
                phys_str = getattr(phys_type, "value", str(phys_type))
                null_pct = getattr(col, "null_percentage", getattr(col, "null_ratio", 0.0))
                col_doc_id = f"raw:col:{dataset_id}:{table_id}.{col_name}"

                col_text = f"Column {col_name} in table {table_id}. Physical type: {phys_str}. Nulls: {null_pct:.1f}%."

                docs.append(
                    RetrievalDocument.create(
                        document_id=col_doc_id,
                        namespace=RetrievalNamespace.RAW_SCHEMA,
                        authority_class=AuthorityClass.STRUCTURAL,
                        dataset_id=dataset_id,
                        dataset_version=dataset_version,
                        source_fingerprint=source_fp,
                        semantic_graph_version=graph_version,
                        artifact_type="column",
                        artifact_id=f"col:{table_id}.{col_name}",
                        text_for_retrieval=col_text,
                        structured_metadata={
                            "table_id": table_id,
                            "column_name": col_name,
                            "physical_type": str(phys_type),
                            "null_percentage": null_pct,
                        },
                        provenance_refs=[f"prov:col:{table_id}.{col_name}"],
                        index_version=self.index_version,
                    )
                )
        return docs

    def _build_semantic_docs(
        self,
        semantic_model: Any | None,
        grain_profile: GrainProfile | None,
        enriched_dataset: EnrichedDataset | None,
        semantic_graph: SemanticGraph | None,
        dataset_id: str,
        dataset_version: str,
        source_fp: str,
        graph_version: str | None,
    ) -> list[RetrievalDocument]:
        docs: list[RetrievalDocument] = []

        # 1. Entities & Semantic Columns from SemanticModel
        if semantic_model:
            entities = getattr(semantic_model, "entity_assignments", {})
            if isinstance(entities, dict):
                for entity_type, members in entities.items():
                    e_type_str = getattr(entity_type, "value", str(entity_type))
                    entity_text = f"Entity {e_type_str} mapped to columns: {', '.join(members)}."
                    docs.append(
                        RetrievalDocument.create(
                            document_id=f"semantic:entity:{dataset_id}:{e_type_str}",
                            namespace=RetrievalNamespace.SEMANTIC,
                            authority_class=AuthorityClass.SEMANTIC,
                            dataset_id=dataset_id,
                            dataset_version=dataset_version,
                            source_fingerprint=source_fp,
                            semantic_graph_version=graph_version,
                            artifact_type="entity",
                            artifact_id=f"entity:{e_type_str}",
                            text_for_retrieval=entity_text,
                            structured_metadata={
                                "entity_type": e_type_str,
                                "assigned_columns": list(members),
                            },
                            index_version=self.index_version,
                        )
                    )

            # Columns / Measures / Dimensions from TableSemanticModel list or dict
            sm_tables = getattr(semantic_model, "tables", [])
            if isinstance(sm_tables, list):
                for t_sm in sm_tables:
                    t_id = t_sm.table_id
                    for c_sm in getattr(t_sm, "columns", []):
                        col_name = getattr(c_sm, "column_name", "")
                        col_key = f"{t_id}.{col_name}"
                        concept = getattr(c_sm, "semantic_concept", None)
                        concept_str = getattr(concept, "value", str(concept)) if concept else ""
                        measure_cls = getattr(c_sm, "measure_class", None)
                        measure_str = getattr(measure_cls, "value", str(measure_cls)) if measure_cls else ""
                        unit = getattr(c_sm, "unit", "") or getattr(c_sm, "inferred_unit", "")

                        col_text = f"Semantic attribute {col_key} concept: {concept_str} measure: {measure_str} unit: {unit}."
                        docs.append(
                            RetrievalDocument.create(
                                document_id=f"semantic:col:{dataset_id}:{col_key}",
                                namespace=RetrievalNamespace.SEMANTIC,
                                authority_class=AuthorityClass.SEMANTIC,
                                dataset_id=dataset_id,
                                dataset_version=dataset_version,
                                source_fingerprint=source_fp,
                                semantic_graph_version=graph_version,
                                artifact_type="semantic_column",
                                artifact_id=f"sem_col:{col_key}",
                                text_for_retrieval=col_text,
                                structured_metadata={
                                    "column_key": col_key,
                                    "semantic_concept": concept_str,
                                    "measure_class": measure_str,
                                    "unit": unit,
                                },
                                index_version=self.index_version,
                            )
                        )
            elif isinstance(sm_tables, dict):
                for col_key, col_spec in getattr(semantic_model, "columns", {}).items():
                    concept = getattr(col_spec, "semantic_concept", None)
                    concept_str = getattr(concept, "value", str(concept)) if concept else ""
                    measure_cls = getattr(col_spec, "measure_class", None)
                    measure_str = getattr(measure_cls, "value", str(measure_cls)) if measure_cls else ""
                    unit = getattr(col_spec, "unit", "")

                    col_text = f"Semantic attribute {col_key} concept: {concept_str} measure: {measure_str} unit: {unit}."
                    docs.append(
                        RetrievalDocument.create(
                            document_id=f"semantic:col:{dataset_id}:{col_key}",
                            namespace=RetrievalNamespace.SEMANTIC,
                            authority_class=AuthorityClass.SEMANTIC,
                            dataset_id=dataset_id,
                            dataset_version=dataset_version,
                            source_fingerprint=source_fp,
                            semantic_graph_version=graph_version,
                            artifact_type="semantic_column",
                            artifact_id=f"sem_col:{col_key}",
                            text_for_retrieval=col_text,
                            structured_metadata={
                                "column_key": col_key,
                                "semantic_concept": concept_str,
                                "measure_class": measure_str,
                                "unit": unit,
                            },
                            index_version=self.index_version,
                        )
                    )

        # 2. Grain Profiles
        if grain_profile:
            raw_grains = getattr(grain_profile, "table_grains", {})
            table_grain_items = []
            if isinstance(raw_grains, list):
                for tg in raw_grains:
                    g_expr = getattr(tg, "grain_expression", None)
                    p_ent = getattr(tg, "primary_entity", None)
                    p_ent_str = getattr(p_ent, "value", str(p_ent)) if p_ent else "UNKNOWN"
                    grain_val = g_expr or p_ent_str
                    table_grain_items.append((tg.table_id, grain_val))
            elif isinstance(raw_grains, dict):
                for t_id, tg in raw_grains.items():
                    p_grain = getattr(tg, "primary_grain", str(tg))
                    p_grain_str = getattr(p_grain, "value", str(p_grain))
                    table_grain_items.append((t_id, p_grain_str))

            for t_id, primary_grain in table_grain_items:
                grain_text = f"Table {t_id} evaluated at grain {primary_grain}."
                docs.append(
                    RetrievalDocument.create(
                        document_id=f"semantic:grain:{dataset_id}:{t_id}",
                        namespace=RetrievalNamespace.SEMANTIC,
                        authority_class=AuthorityClass.SEMANTIC,
                        dataset_id=dataset_id,
                        dataset_version=dataset_version,
                        source_fingerprint=source_fp,
                        semantic_graph_version=graph_version,
                        artifact_type="grain",
                        artifact_id=f"grain:{t_id}",
                        text_for_retrieval=grain_text,
                        structured_metadata={
                            "table_id": t_id,
                            "primary_grain": primary_grain,
                        },
                        index_version=self.index_version,
                    )
                )

        # 3. Governed Metrics (Local and Relational)
        if enriched_dataset:
            for m in getattr(enriched_dataset, "local_metrics", []):
                aliases_str = ", ".join(m.display_aliases) if m.display_aliases else ""
                m_text = (
                    f"Local Metric {m.metric_name} ({aliases_str}) formula: {m.formula} "
                    f"grain: {m.target_grain} unit: {m.unit} additivity: {getattr(m.additivity, 'value', str(m.additivity))}."
                )
                docs.append(
                    RetrievalDocument.create(
                        document_id=f"semantic:metric:{dataset_id}:{m.metric_id}",
                        namespace=RetrievalNamespace.SEMANTIC,
                        authority_class=AuthorityClass.SEMANTIC,
                        dataset_id=dataset_id,
                        dataset_version=dataset_version,
                        source_fingerprint=source_fp,
                        semantic_graph_version=graph_version,
                        artifact_type="metric",
                        artifact_id=f"metric:{m.metric_id}",
                        text_for_retrieval=m_text,
                        structured_metadata={
                            "metric_id": m.metric_id,
                            "metric_name": m.metric_name,
                            "formula": m.formula,
                            "target_grain": m.target_grain,
                            "unit": m.unit,
                            "additivity": getattr(m.additivity, "value", str(m.additivity)),
                            "aliases": m.display_aliases,
                            "source_tables": getattr(m, "source_tables", [m.source_table_id] if getattr(m, "source_table_id", None) else ([m.table_id] if getattr(m, "table_id", None) else [])),
                            "source_columns": getattr(m, "source_columns", getattr(m, "source_column_ids", [])),
                            "is_relational": False,
                        },
                        provenance_refs=m.provenance_refs,
                        index_version=self.index_version,
                    )
                )

            for rm in getattr(enriched_dataset, "relational_metrics", []):
                aliases_str = ", ".join(rm.display_aliases) if rm.display_aliases else ""
                rm_text = (
                    f"Relational Metric {rm.metric_name} ({aliases_str}) formula: {rm.formula} "
                    f"grain: {rm.target_grain} join_plan: {rm.join_plan_id} unit: {rm.unit}."
                )
                docs.append(
                    RetrievalDocument.create(
                        document_id=f"semantic:metric:{dataset_id}:{rm.metric_id}",
                        namespace=RetrievalNamespace.SEMANTIC,
                        authority_class=AuthorityClass.SEMANTIC,
                        dataset_id=dataset_id,
                        dataset_version=dataset_version,
                        source_fingerprint=source_fp,
                        semantic_graph_version=graph_version,
                        artifact_type="metric",
                        artifact_id=f"metric:{rm.metric_id}",
                        text_for_retrieval=rm_text,
                        structured_metadata={
                            "metric_id": rm.metric_id,
                            "metric_name": rm.metric_name,
                            "formula": rm.formula,
                            "target_grain": rm.target_grain,
                            "join_plan_id": rm.join_plan_id,
                            "unit": rm.unit,
                            "additivity": getattr(rm.additivity, "value", str(rm.additivity)),
                            "aliases": rm.display_aliases,
                            "source_tables": getattr(rm, "source_tables", getattr(rm, "source_table_ids", [])),
                            "source_columns": getattr(rm, "source_columns", getattr(rm, "source_column_ids", [])),
                            "is_relational": True,
                        },
                        provenance_refs=rm.provenance_refs,
                        index_version=self.index_version,
                    )
                )

            for fam in getattr(enriched_dataset, "semantic_families", []):
                fam_text = (
                    f"Semantic Family {fam.family_name} concept: {getattr(fam.concept_type, 'value', str(fam.concept_type))} "
                    f"metrics: {', '.join(fam.metric_ids)} grain_scope: {fam.grain_scope or ''}."
                )
                docs.append(
                    RetrievalDocument.create(
                        document_id=f"semantic:family:{dataset_id}:{fam.family_id}",
                        namespace=RetrievalNamespace.SEMANTIC,
                        authority_class=AuthorityClass.SEMANTIC,
                        dataset_id=dataset_id,
                        dataset_version=dataset_version,
                        source_fingerprint=source_fp,
                        semantic_graph_version=graph_version,
                        artifact_type="semantic_family",
                        artifact_id=f"family:{fam.family_id}",
                        text_for_retrieval=fam_text,
                        structured_metadata={
                            "family_id": fam.family_id,
                            "family_name": fam.family_name,
                            "concept_type": getattr(fam.concept_type, "value", str(fam.concept_type)),
                            "metric_ids": fam.metric_ids,
                            "dimension_ids": fam.dimension_ids,
                            "grain_scope": fam.grain_scope,
                        },
                        provenance_refs=fam.provenance_refs,
                        evidence_refs=fam.evidence_refs,
                        index_version=self.index_version,
                    )
                )

        return docs

    def _build_relationship_docs(
        self,
        relationship_graph: ValidatedRelationshipGraph | None,
        join_plans: Sequence[JoinPlan] | None,
        dataset_id: str,
        dataset_version: str,
        source_fp: str,
        graph_version: str | None,
    ) -> list[RetrievalDocument]:
        docs: list[RetrievalDocument] = []

        # 1. Validated Relationship Edges (NEVER unvalidated/rejected candidates)
        if relationship_graph:
            for edge in getattr(relationship_graph, "edges", []):
                status = getattr(edge, "status", None)
                status_val = getattr(status, "value", str(status))
                if status_val not in ("VALIDATED", "ACCEPTED", "CONFIRMED"):
                    continue

                card = getattr(edge, "cardinality", None)
                card_str = getattr(card, "value", str(card)) if card else "UNKNOWN"
                from_tbl = getattr(edge, "source_table_id", getattr(edge, "from_table", ""))
                to_tbl = getattr(edge, "target_table_id", getattr(edge, "to_table", ""))
                src_cols = getattr(edge, "source_column_ids", [])
                from_col = src_cols[0] if src_cols else getattr(edge, "from_column", "")
                tgt_cols = getattr(edge, "target_column_ids", [])
                to_col = tgt_cols[0] if tgt_cols else getattr(edge, "to_column", "")

                edge_id = f"{from_tbl}.{from_col}->{to_tbl}.{to_col}"
                edge_text = (
                    f"Validated relationship between {from_tbl}.{from_col} and {to_tbl}.{to_col}. "
                    f"Cardinality: {card_str}. Status: {status_val}."
                )

                docs.append(
                    RetrievalDocument.create(
                        document_id=f"relationship:edge:{dataset_id}:{edge_id}",
                        namespace=RetrievalNamespace.RELATIONSHIP,
                        authority_class=AuthorityClass.RELATIONSHIP,
                        dataset_id=dataset_id,
                        dataset_version=dataset_version,
                        source_fingerprint=source_fp,
                        semantic_graph_version=graph_version,
                        artifact_type="relationship_edge",
                        artifact_id=f"rel_edge:{edge_id}",
                        text_for_retrieval=edge_text,
                        structured_metadata={
                            "edge_id": edge_id,
                            "from_table": from_tbl,
                            "to_table": to_tbl,
                            "from_column": from_col,
                            "to_column": to_col,
                            "cardinality": card_str,
                            "status": status_val,
                            "confidence": getattr(edge, "confidence", 1.0),
                        },
                        provenance_refs=[f"prov:edge:{edge_id}"],
                        index_version=self.index_version,
                    )
                )

        # 2. Governed JoinPlans
        if join_plans:
            for jp in join_plans:
                safety = getattr(jp, "safety_status", None)
                safety_str = getattr(safety, "value", str(safety)) if safety else "UNKNOWN"
                pre_agg = getattr(jp, "pre_aggregation", None)
                pre_agg_str = "Pre-aggregation required" if pre_agg else "Direct join"
                safe_ops = ", ".join(getattr(jp, "safe_operations", []))
                forb_ops = ", ".join(getattr(jp, "forbidden_operations", []))

                jp_text = (
                    f"JoinPlan {jp.join_plan_id} joining {jp.left_table_id} and {jp.right_table_id}. "
                    f"Safety: {safety_str} ({pre_agg_str}). Target grain: {jp.target_grain}. "
                    f"Safe operations: [{safe_ops}]. Forbidden operations: [{forb_ops}]."
                )

                docs.append(
                    RetrievalDocument.create(
                        document_id=f"relationship:join_plan:{dataset_id}:{jp.join_plan_id}",
                        namespace=RetrievalNamespace.RELATIONSHIP,
                        authority_class=AuthorityClass.RELATIONSHIP,
                        dataset_id=dataset_id,
                        dataset_version=dataset_version,
                        source_fingerprint=source_fp,
                        semantic_graph_version=graph_version,
                        artifact_type="join_plan",
                        artifact_id=f"join_plan:{jp.join_plan_id}",
                        text_for_retrieval=jp_text,
                        structured_metadata={
                            "join_plan_id": jp.join_plan_id,
                            "left_table_id": jp.left_table_id,
                            "right_table_id": jp.right_table_id,
                            "safety_status": safety_str,
                            "target_grain": jp.target_grain,
                            "pre_aggregation": bool(pre_agg),
                            "safe_operations": list(getattr(jp, "safe_operations", [])),
                            "forbidden_operations": list(getattr(jp, "forbidden_operations", [])),
                        },
                        provenance_refs=getattr(jp, "provenance_refs", []),
                        index_version=self.index_version,
                    )
                )

        return docs

    def _build_analytical_docs(
        self,
        analytical_profile: AnalyticalProfile | None,
        dataset_id: str,
        dataset_version: str,
        source_fp: str,
        graph_version: str | None,
    ) -> list[RetrievalDocument]:
        docs: list[RetrievalDocument] = []
        if not analytical_profile:
            return docs

        findings = getattr(analytical_profile, "findings", [])
        for f in findings:
            evid_id = getattr(f, "finding_id", "")
            ftype = getattr(f, "finding_type", "observation")
            metric_name = getattr(f, "metric_definition", None) or getattr(f, "metric_name", "") or getattr(f, "column_name", "")
            grain_val = getattr(f, "target_grain", None) or getattr(f, "grain", "")
            rel = getattr(f, "analytical_reliability", None) or getattr(f, "reliability", None)
            rel_str = getattr(rel, "reliability_level", getattr(rel, "value", str(rel))) if rel else "HIGH"
            filters = getattr(f, "filters", {})
            filter_str = f" filters: {filters}" if filters else ""
            effect_size = getattr(f, "effect_size", None)
            effect_str = f" effect size: {effect_size}" if effect_size is not None else ""
            limitations = getattr(f, "limitations", [])

            # Summary text strictly based on observed findings (NO recommendations, NO narrative prose)
            f_text = (
                f"Analytical Finding {evid_id} type: {ftype} metric: {metric_name} "
                f"population: {getattr(f, 'population', 'all')} grain: {grain_val}"
                f"{filter_str}{effect_str} reliability: {rel_str}."
            )

            ev_refs = list(getattr(f, "evidence_refs", []))
            if not ev_refs and evid_id.startswith("EVID-"):
                ev_refs = [evid_id]

            docs.append(
                RetrievalDocument.create(
                    document_id=f"analytical:finding:{dataset_id}:{evid_id}",
                    namespace=RetrievalNamespace.ANALYTICAL,
                    authority_class=AuthorityClass.ANALYTICAL_EVIDENCE,
                    dataset_id=dataset_id,
                    dataset_version=dataset_version,
                    source_fingerprint=source_fp,
                    semantic_graph_version=graph_version,
                    artifact_type="analytical_finding",
                    artifact_id=f"finding:{evid_id}",
                    text_for_retrieval=f_text,
                    structured_metadata={
                        "finding_id": evid_id,
                        "finding_type": str(ftype),
                        "metric_name": metric_name,
                        "table_id": getattr(f, "table_id", ""),
                        "column_name": getattr(f, "column_name", ""),
                        "grain": grain_val,
                        "population": getattr(f, "population", "all"),
                        "filters": filters,
                        "effect_size": effect_size,
                        "result_value": getattr(f, "result_value", getattr(f, "result", None)),
                        "reliability": rel_str,
                        "sample_size": getattr(f, "sample_size", None),
                        "limitations": list(limitations),
                    },
                    provenance_refs=getattr(f, "provenance_refs", []),
                    evidence_refs=ev_refs,
                    index_version=self.index_version,
                )
            )

        return docs
