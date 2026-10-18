"""
HighView Ingestion V2 — Phase I7 Query Intent Router
Stage 11: Multi-Namespace Hybrid Retrieval

Core Invariants:
1. Lightweight deterministic pattern classification (< 1ms, zero LLM calls).
2. Maps query intent to targeted namespaces and authority boost priorities.
3. AnalysisIntent (dataset objective) is strictly separated from QueryIntent (retrieval query).
4. Neither intent type may alter factual truth.
"""

import re
from pydantic import BaseModel, ConfigDict, Field

from app.services.ingestion_v2.retrieval.namespaces import (
    AuthorityClass,
    QueryIntent,
    RetrievalNamespace,
)


class QueryIntentResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    intent: QueryIntent
    target_namespaces: list[RetrievalNamespace]
    namespace_weights: dict[str, float] = Field(default_factory=dict)
    suggested_authority_boost: dict[str, float] = Field(default_factory=dict)
    requires_graph_expansion: bool = False
    confidence: float = 1.0


class QueryIntentRouter:
    """
    Deterministic rule-based query intent classifier and namespace router.
    """

    def route_query(self, query: str) -> QueryIntentResult:
        q = query.strip().casefold()

        # 1. Technical Provenance Lookup
        if any(term in q for term in ["where did", "source file", "provenance", "origin", "which sheet", "file location", "raw header"]):
            return QueryIntentResult(
                intent=QueryIntent.TECHNICAL_PROVENANCE_LOOKUP,
                target_namespaces=[RetrievalNamespace.RAW_SCHEMA, RetrievalNamespace.SEMANTIC],
                namespace_weights={
                    RetrievalNamespace.RAW_SCHEMA.value: 1.0,
                    RetrievalNamespace.SEMANTIC.value: 0.6,
                },
                suggested_authority_boost={
                    AuthorityClass.STRUCTURAL.value: 1.5,
                },
                requires_graph_expansion=False,
            )

        # 2. Relationship / Join Lookup
        if any(term in q for term in ["join", "related", "relationship", "foreign key", "connect", "link between", "can employees join", "cardinality", "fanout"]):
            return QueryIntentResult(
                intent=QueryIntent.RELATIONSHIP_LOOKUP,
                target_namespaces=[RetrievalNamespace.RELATIONSHIP, RetrievalNamespace.SEMANTIC],
                namespace_weights={
                    RetrievalNamespace.RELATIONSHIP.value: 1.0,
                    RetrievalNamespace.SEMANTIC.value: 0.7,
                },
                suggested_authority_boost={
                    AuthorityClass.RELATIONSHIP.value: 1.8,
                    AuthorityClass.SEMANTIC.value: 1.2,
                },
                requires_graph_expansion=True,
            )

        # 3. Cross-Table Analytical Query
        if any(term in q for term in ["across tables", "joined attendance", "department attendance", "sales per employee"]):
            return QueryIntentResult(
                intent=QueryIntent.CROSS_TABLE_ANALYTICAL_QUERY,
                target_namespaces=[RetrievalNamespace.ANALYTICAL, RetrievalNamespace.RELATIONSHIP, RetrievalNamespace.SEMANTIC],
                namespace_weights={
                    RetrievalNamespace.ANALYTICAL.value: 1.0,
                    RetrievalNamespace.RELATIONSHIP.value: 0.9,
                    RetrievalNamespace.SEMANTIC.value: 0.8,
                },
                suggested_authority_boost={
                    AuthorityClass.ANALYTICAL_EVIDENCE.value: 1.8,
                    AuthorityClass.RELATIONSHIP.value: 1.5,
                },
                requires_graph_expansion=True,
            )

        # 4. Analytical Finding Lookup (e.g. "Highest attendance department", "What was attendance rate last month?")
        # Distinguish: "what was / who had / highest / top / bottom / trend / average / last month" vs "what is / define"
        if any(term in q for term in [
            "highest", "lowest", "top", "bottom", "trend", "increased", "decreased",
            "outlier", "anomaly", "concentration", "what was", "last month", "last quarter",
            "distribution", "which department", "which store", "which city", "breakdown"
        ]):
            return QueryIntentResult(
                intent=QueryIntent.ANALYTICAL_FINDING_LOOKUP,
                target_namespaces=[RetrievalNamespace.ANALYTICAL, RetrievalNamespace.SEMANTIC, RetrievalNamespace.RELATIONSHIP],
                namespace_weights={
                    RetrievalNamespace.ANALYTICAL.value: 1.0,
                    RetrievalNamespace.SEMANTIC.value: 0.7,
                    RetrievalNamespace.RELATIONSHIP.value: 0.5,
                },
                suggested_authority_boost={
                    AuthorityClass.ANALYTICAL_EVIDENCE.value: 2.0,
                    AuthorityClass.SEMANTIC.value: 1.0,
                },
                requires_graph_expansion=True,
            )

        # 5. Schema Lookup (e.g. "What does worker_number mean?", "columns in attendance", "data type of employee_id")
        if any(term in q for term in ["column", "columns", "table", "tables", "data type", "physical type", "schema", "fields", "worker_number", "staff_identifier", "raw header"]):
            return QueryIntentResult(
                intent=QueryIntent.SCHEMA_LOOKUP,
                target_namespaces=[RetrievalNamespace.RAW_SCHEMA, RetrievalNamespace.SEMANTIC],
                namespace_weights={
                    RetrievalNamespace.RAW_SCHEMA.value: 1.0,
                    RetrievalNamespace.SEMANTIC.value: 0.7,
                },
                suggested_authority_boost={
                    AuthorityClass.STRUCTURAL.value: 1.8,
                    AuthorityClass.SEMANTIC.value: 1.0,
                },
                requires_graph_expansion=False,
            )

        # 6. Metric Lookup (e.g. "What is attendance rate?", "formula for gross margin", "how is attendance rate calculated")
        if any(term in q for term in [
            "what is", "how is", "formula", "definition", "defined", "calculate",
            "calculation", "rate", "percentage", "margin", "ratio"
        ]) and not any(term in q for term in ["what was", "last month", "last year"]):
            return QueryIntentResult(
                intent=QueryIntent.METRIC_LOOKUP,
                target_namespaces=[RetrievalNamespace.SEMANTIC, RetrievalNamespace.RAW_SCHEMA],
                namespace_weights={
                    RetrievalNamespace.SEMANTIC.value: 1.0,
                    RetrievalNamespace.RAW_SCHEMA.value: 0.4,
                },
                suggested_authority_boost={
                    AuthorityClass.SEMANTIC.value: 2.0,
                    AuthorityClass.STRUCTURAL.value: 0.5,
                },
                requires_graph_expansion=True,
            )

        # 7. Semantic Lookup (Entities, Dimensions, Concepts)
        if any(term in q for term in ["entity", "dimension", "concept", "grain", "family", "headcount", "person", "store"]):
            return QueryIntentResult(
                intent=QueryIntent.SEMANTIC_LOOKUP,
                target_namespaces=[RetrievalNamespace.SEMANTIC, RetrievalNamespace.RAW_SCHEMA],
                namespace_weights={
                    RetrievalNamespace.SEMANTIC.value: 1.0,
                    RetrievalNamespace.RAW_SCHEMA.value: 0.5,
                },
                suggested_authority_boost={
                    AuthorityClass.SEMANTIC.value: 1.8,
                },
                requires_graph_expansion=True,
            )

        # 8. General Dataset Query (Default fallback)
        return QueryIntentResult(
            intent=QueryIntent.GENERAL_DATASET_QUERY,
            target_namespaces=[
                RetrievalNamespace.SEMANTIC,
                RetrievalNamespace.ANALYTICAL,
                RetrievalNamespace.RAW_SCHEMA,
                RetrievalNamespace.RELATIONSHIP,
            ],
            namespace_weights={
                RetrievalNamespace.SEMANTIC.value: 1.0,
                RetrievalNamespace.ANALYTICAL.value: 0.9,
                RetrievalNamespace.RAW_SCHEMA.value: 0.7,
                RetrievalNamespace.RELATIONSHIP.value: 0.6,
            },
            suggested_authority_boost={
                AuthorityClass.SEMANTIC.value: 1.2,
                AuthorityClass.ANALYTICAL_EVIDENCE.value: 1.2,
            },
            requires_graph_expansion=False,
        )
