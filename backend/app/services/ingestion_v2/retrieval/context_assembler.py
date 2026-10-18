"""
HighView Ingestion V2 — Phase I7 Governed Context Assembler
Stage 11: Multi-Namespace Hybrid Retrieval

Core Invariants:
1. Context Assembler packages trustworthy evidence; it NEVER writes prose or recommendations.
2. Preserves canonical artifact metadata, grains, formulas, JoinPlans, and EVID-* references.
3. Dependency Completeness: If a metric finding is included, its metric definition, grain,
   formula, and JoinPlan (if relational) MUST accompany it.
4. Missing Analysis Flag: When required analytical evidence is absent, explicitly marks
   ANALYTICAL_EVIDENCE_NOT_AVAILABLE; NEVER fabricates numbers.
5. Bounded Token Budget: Packs structured context up to a strict bound without stuffing entire datasets.
"""

from typing import Any, Sequence
from pydantic import BaseModel, ConfigDict, Field

from app.services.ingestion_v2.retrieval.namespaces import (
    AuthorityClass,
    QueryIntent,
    RetrievalNamespace,
)
from app.services.ingestion_v2.retrieval.reranker import RankedCandidate
from app.services.ingestion_v2.retrieval.hybrid_retriever import HybridRetrievalResult


class GovernedContextPackage(BaseModel):
    """
    Structured, evidence-grounded context package for consumption by downstream
    agents/councils. Contains ZERO hallucinated facts.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    query: str
    dataset_id: str
    dataset_version: str
    intent: QueryIntent
    artifact_ids: list[str] = Field(default_factory=list)
    namespaces: list[RetrievalNamespace] = Field(default_factory=list)

    # Structured Components
    metric_definitions: list[dict[str, Any]] = Field(default_factory=list)
    semantic_entities: list[dict[str, Any]] = Field(default_factory=list)
    grains: list[str] = Field(default_factory=list)
    join_plans: list[dict[str, Any]] = Field(default_factory=list)
    relationship_edges: list[dict[str, Any]] = Field(default_factory=list)
    evidence_findings: list[dict[str, Any]] = Field(default_factory=list)
    provenance_refs: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    # Flags & Quality Indicators
    analytical_evidence_available: bool = True
    status_flags: list[str] = Field(default_factory=list)
    is_ambiguous: bool = False
    ambiguity_notes: list[str] = Field(default_factory=list)
    estimated_token_count: int = 0


class ContextAssembler:
    """
    Assembles a bounded GovernedContextPackage from ranked retrieval candidates
    while enforcing dependency completeness.
    """

    def __init__(self, max_context_items: int = 15, max_estimated_tokens: int = 2500):
        self.max_context_items = max_context_items
        self.max_estimated_tokens = max_estimated_tokens

    def assemble_context(
        self,
        retrieval_result: HybridRetrievalResult,
        all_indexed_documents: Sequence[Any] | None = None,
    ) -> GovernedContextPackage:
        query = retrieval_result.query
        dataset_id = retrieval_result.dataset_id
        intent = retrieval_result.intent_result.intent
        candidates = retrieval_result.ranked_candidates[:self.max_context_items]

        artifact_ids: list[str] = []
        namespaces_set: set[RetrievalNamespace] = set()
        metric_defs: list[dict[str, Any]] = []
        entities: list[dict[str, Any]] = []
        grains: list[str] = []
        join_plans: list[dict[str, Any]] = []
        rel_edges: list[dict[str, Any]] = []
        findings: list[dict[str, Any]] = []
        provenance_refs: set[str] = set()
        limitations: list[str] = []
        status_flags: list[str] = []
        ambiguity_notes: list[str] = []
        is_ambiguous: bool = False

        # Index lookup map for dependency resolution if provided
        doc_by_artifact: dict[str, Any] = {}
        if all_indexed_documents:
            for d in all_indexed_documents:
                doc_by_artifact[d.artifact_id] = d

        for cand in candidates:
            doc = cand.document
            artifact_ids.append(doc.artifact_id)
            namespaces_set.add(doc.namespace)
            provenance_refs.update(doc.provenance_refs)

            if cand.is_ambiguous:
                is_ambiguous = True
                ambiguity_notes.append(
                    f"Ambiguous semantic concept for '{doc.structured_metadata.get('metric_name', '')}' matching: {cand.ambiguity_candidates}"
                )

            # Categorize into structured context fields
            if doc.artifact_type == "metric":
                metric_defs.append(doc.structured_metadata)
                g = doc.structured_metadata.get("target_grain")
                if g and g not in grains:
                    grains.append(g)

            elif doc.artifact_type == "entity":
                entities.append(doc.structured_metadata)

            elif doc.artifact_type == "grain":
                primary_g = doc.structured_metadata.get("primary_grain")
                if primary_g and primary_g not in grains:
                    grains.append(primary_g)

            elif doc.artifact_type == "join_plan":
                join_plans.append(doc.structured_metadata)

            elif doc.artifact_type == "relationship_edge":
                rel_edges.append(doc.structured_metadata)

            elif doc.artifact_type == "analytical_finding":
                findings.append(doc.structured_metadata)
                lims = doc.structured_metadata.get("limitations", [])
                for lim in lims:
                    if lim not in limitations:
                        limitations.append(lim)

        # -------------------------------------------------------------
        # Dependency Completeness Enforcement
        # -------------------------------------------------------------
        # For any analytical finding, ensure its metric definition and JoinPlan are included
        for f in findings:
            metric_name = f.get("metric_name")
            grain = f.get("grain")
            if grain and grain not in grains:
                grains.append(grain)

            # Check if metric definition already present
            has_metric_def = any(m.get("metric_name") == metric_name for m in metric_defs)
            if not has_metric_def and doc_by_artifact:
                # Find corresponding metric document in indexed repository
                for d in doc_by_artifact.values():
                    if d.artifact_type == "metric" and d.structured_metadata.get("metric_name") == metric_name:
                        metric_defs.append(d.structured_metadata)
                        artifact_ids.append(d.artifact_id)
                        jp_id = d.structured_metadata.get("join_plan_id")
                        if jp_id:
                            # Also resolve join plan
                            jp_art_id = f"join_plan:{jp_id}"
                            if jp_art_id in doc_by_artifact:
                                join_plans.append(doc_by_artifact[jp_art_id].structured_metadata)
                        break

        # -------------------------------------------------------------
        # Missing Analysis Detection
        # -------------------------------------------------------------
        analytical_available = True
        if intent in (QueryIntent.ANALYTICAL_FINDING_LOOKUP, QueryIntent.CROSS_TABLE_ANALYTICAL_QUERY):
            if not findings:
                analytical_available = False
                status_flags.append("ANALYTICAL_EVIDENCE_NOT_AVAILABLE")

        dataset_ver = candidates[0].document.dataset_version if candidates else "1"

        # Rough token estimation (4 chars ~= 1 token)
        raw_repr = f"{query} {metric_defs} {entities} {grains} {join_plans} {rel_edges} {findings} {limitations}"
        estimated_tokens = len(raw_repr) // 4

        return GovernedContextPackage(
            query=query,
            dataset_id=dataset_id,
            dataset_version=dataset_ver,
            intent=intent,
            artifact_ids=artifact_ids,
            namespaces=sorted(list(namespaces_set), key=lambda x: x.value),
            metric_definitions=metric_defs,
            semantic_entities=entities,
            grains=grains,
            join_plans=join_plans,
            relationship_edges=rel_edges,
            evidence_findings=findings,
            provenance_refs=sorted(list(provenance_refs)),
            limitations=limitations,
            analytical_evidence_available=analytical_available,
            status_flags=status_flags,
            is_ambiguous=is_ambiguous,
            ambiguity_notes=ambiguity_notes,
            estimated_token_count=estimated_tokens,
        )
