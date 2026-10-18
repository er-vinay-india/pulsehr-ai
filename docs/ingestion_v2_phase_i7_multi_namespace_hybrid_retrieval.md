# HighView Ingestion Intelligence V2 — Phase I7: Multi-Namespace Hybrid Retrieval, Graph-Aware Search & Governed Context Assembly

## 1. Architectural Mandate & Permanent Epistemic Law

```
+-------------------------------------------------------------------------------+
|                               PERMANENT LAW                                    |
|          RETRIEVAL FINDS CANDIDATES. RETRIEVAL DOES NOT ESTABLISH TRUTH.       |
|                                                                               |
|   1. Vector similarity NEVER establishes a relationship (I4 is authoritative)  |
|   2. BM25 match NEVER defines a metric (I6 is authoritative)                   |
|   3. Graph proximity NEVER establishes causation (I5 is authoritative)         |
|   4. Low-confidence findings are NEVER hidden or suppressed                    |
|   5. Competing metric formulas are NEVER arbitrarily merged                    |
|   6. Unexecuted analysis is NEVER hallucinated or computed on the fly          |
+-------------------------------------------------------------------------------+
```

Phase I7 introduces multi-namespace hybrid search and governed context assembly as a strictly isolated layer above frozen Phase I1–I6 artifacts. Retrieval is strictly epistemic: it surfaces candidate artifacts according to user query intent, attaches their validated governance metadata and reliability tiers, and assembles them into bounded, hallucination-resistant context packages.

---

## 2. Multi-Namespace Architecture

Ingestion V2 retrieval operates across four strictly isolated namespaces. Crossing namespace boundaries without explicit authority evaluation is strictly forbidden.

| Namespace | Authority Class | Ingestion Artifact Source | Permitted Content | Strictly Forbidden Content |
| :--- | :--- | :--- | :--- | :--- |
| `RAW_SCHEMA` | `STRUCTURAL` (Tier 1) | `NormalizedDataset`, `StructuralProfile` | Tables, columns, canonical types, physical null counts, lineage | Business semantic roles, grain assumptions, metrics |
| `SEMANTIC` | `SEMANTIC` (Tier 2) | `SemanticModel`, `GrainProfile`, `EnrichedDataset` | Real-world entities, grains, metric formulas, semantic families | Observed numerical values, p-values, raw unvalidated joins |
| `RELATIONSHIP` | `RELATIONSHIP` (Tier 3) | `ValidatedRelationshipGraph`, `JoinPlan`s | Validated foreign key edges, governed JoinPlans, additivity rules | Rejected candidate joins, arbitrary cross-table traversals |
| `ANALYTICAL` | `ANALYTICAL_EVIDENCE` (Tier 4) | `AnalyticalProfile` | Governed findings with exact `EVID-*` tokens, reliability tiers | Executive recommendations, narrative prose, uncalculated claims |

### Authority Tiers
1. **STRUCTURAL (Tier 1)**: Authoritative for column existence, physical types, null counts, and raw source lineage.
2. **SEMANTIC (Tier 2)**: Authoritative for entity classification, table grain, metric definitions, and semantic families.
3. **RELATIONSHIP (Tier 3)**: Authoritative for foreign-key validity, cardinality, and JoinPlan pre-aggregation safety.
4. **ANALYTICAL_EVIDENCE (Tier 4)**: Authoritative for observed statistical findings and empirical distributions.

---

## 3. Retrieval Components

### 3.1 RetrievalDocument & Canonical Grounding
Every indexed item is converted into a unified `RetrievalDocument` containing:
- `document_id`: Deterministic namespace-prefixed identifier (`{namespace}:{artifact_type}:{dataset_id}:{artifact_id}`)
- `source_fingerprint`: Provenance hash linking back to raw source inputs
- `semantic_graph_version`: Binding document to the underlying semantic graph
- `content_fingerprint`: SHA-256 hash calculated exclusively over semantic content (excluding timestamps and run IDs)
- `structured_metadata`: Machine-readable parameters preserved without vector dilution

### 3.2 Dual-Index Architecture
1. **MultiNamespaceBM25Index**:
   - Built via `rank_bm25.BM25Plus` for robustness against term frequency saturation.
   - Exact tokenization preserving punctuation-critical identifiers (`emp_id`, `EVID-001`, `PERSON x DAY`).
   - Strict namespace filtering and deterministic tie-breaking by `document_id`.
2. **MultiNamespaceVectorIndex**:
   - Content-fingerprint embedding cache: Identical document text across runs reuses cached vectors.
   - Separate telemetry: `llm_calls = 0` (strictly enforced); embedding provider calls tracked independently.
   - Graceful offline fallback: If embedding provider is unavailable or fails, index reports `VECTOR_INDEX_UNAVAILABLE` and retrieval falls back seamlessly to BM25 + Graph traversal.

### 3.3 Graph-Aware Search (`GraphRetriever`)
- Performs bounded Breadth-First Search (BFS) starting from seed nodes.
- Enforces strict depth (`max_depth = 2`) and expansion (`max_nodes = 25`) bounds to prevent traversal explosion.
- **Dependency Closure**: For any retrieved derived metric, automatically traverses and verifies the existence of all input columns, source tables, target grains, and required JoinPlans.

### 3.4 Query Intent Routing (`QueryIntentRouter`)
Sub-millisecond pattern-based classifier mapping incoming queries to one of eight `QueryIntent` categories:
1. `SCHEMA_LOOKUP`: Routes to `RAW_SCHEMA` + `SEMANTIC`
2. `SEMANTIC_LOOKUP`: Routes to `SEMANTIC`
3. `METRIC_LOOKUP`: Routes to `SEMANTIC` + `RAW_SCHEMA`
4. `RELATIONSHIP_LOOKUP`: Routes to `RELATIONSHIP` + `SEMANTIC`
5. `ANALYTICAL_FINDING_LOOKUP`: Routes to `ANALYTICAL` + `SEMANTIC`
6. `CROSS_TABLE_ANALYTICAL_QUERY`: Routes to `ANALYTICAL` + `RELATIONSHIP` + `SEMANTIC`
7. `TECHNICAL_PROVENANCE_LOOKUP`: Routes to `RAW_SCHEMA` + `SEMANTIC`
8. `EXPLORATORY`: Routes across all namespaces

### 3.5 Governed Reranking (`GovernedReranker`)
Merges BM25, vector, and graph candidate lists using Reciprocal Rank Fusion:
$$\text{RRF}(d) = \sum_{m \in M} \frac{w_m}{k + \text{rank}_m(d)}$$
Subject to:
- **Authority Boosting**: Boosts documents matching query intent authority requirements.
- **Reliability Weighting**: For analytical findings, multiplies final score by reliability level (`HIGH` = 1.0, `MEDIUM` = 0.85, `LOW` = 0.65). Low-reliability findings are never suppressed; their confidence tier is preserved in metadata.
- **Ambiguity Preservation**: When competing definitions share a metric name with distinct formulas, both are preserved with `is_ambiguous = True`.
- **Deterministic Tie-Breaking**: Final ranking sorts on `(-score, document_id)`.

### 3.6 Governed Context Assembly (`ContextAssembler`)
Formats retrieved documents into a structured, bounded `GovernedContextPackage`:
- Deduplicated schema references, metric definitions, grains, and JoinPlans.
- Hard token budget enforcement (< 2,500 tokens).
- Missing Analysis Flag: When user queries analytical findings for uncomputed relationships or unprofiled metrics, sets `analytical_evidence_available = False` and status `ANALYTICAL_EVIDENCE_NOT_AVAILABLE`. Never fabricates findings on the fly.

---

## 4. Multi-Domain Retrieval Benchmark Results

Evaluated across 6 canonical domains (Workforce, Retail, Healthcare, Finance, SaaS, Environmental):

| Metric | Target | Result | Status |
| :--- | :--- | :--- | :--- |
| **Recall@1** | $\ge 0.80$ | **1.000** | PASS |
| **Recall@3** | $\ge 0.90$ | **1.000** | PASS |
| **Recall@5** | $\ge 0.95$ | **1.000** | PASS |
| **MRR (Mean Reciprocal Rank)** | $\ge 0.85$ | **1.000** | PASS |
| **nDCG@5** | $\ge 0.90$ | **1.000** | PASS |
| **Orphan Documents** | $0$ | **0** | PASS |
| **Fabricated Metrics / Joins** | $0$ | **0** | PASS |

---

## 5. Component-Level Performance & Scalability Telemetry

Measured across independent Small, Medium, and Large fixtures (10 iterations each):

| Component | Small (2 tbl, 8 col, 2 mtr) | Medium (6 tbl, 30 col, 6 mtr) | Large (16 tbl, 128 col, 24 mtr) | Target Bound |
| :--- | :--- | :--- | :--- | :--- |
| **Document Build (P50 / P95)** | 0.12 ms / 0.21 ms | 0.41 ms / 0.46 ms | 1.54 ms / 1.87 ms | $< 50$ ms |
| **BM25 Build (P50 / P95)** | 0.04 ms / 0.13 ms | 0.14 ms / 0.33 ms | 0.50 ms / 0.64 ms | $< 50$ ms |
| **Vector Build (P50 / P95)** | 0.002 ms / 0.04 ms | 0.01 ms / 0.10 ms | 0.15 ms / 3.48 ms | $< 50$ ms |
| **Graph Prep (P50 / P95)** | 0.00 ms / 0.00 ms | 0.00 ms / 0.00 ms | 0.00 ms / 0.001 ms | $< 5$ ms |
| **BM25 Query (P50 / P95)** | 0.02 ms / 0.07 ms | 0.03 ms / 0.07 ms | 0.05 ms / 0.10 ms | $< 10$ ms |
| **Vector Query (P50 / P95)** | 0.02 ms / 0.03 ms | 0.06 ms / 0.08 ms | 0.22 ms / 0.35 ms | $< 20$ ms |
| **Graph Traversal (P50 / P95)**| 0.001 ms / 0.004 ms | 0.001 ms / 0.004 ms | 0.001 ms / 0.005 ms | $< 10$ ms |
| **Hybrid Fusion (P50 / P95)** | 0.08 ms / 0.12 ms | 0.15 ms / 0.18 ms | 0.34 ms / 0.48 ms | $< 25$ ms |
| **Reranking (P50 / P95)** | 0.02 ms / 0.03 ms | 0.02 ms / 0.03 ms | 0.02 ms / 0.02 ms | $< 10$ ms |
| **Context Assembly (P50 / P95)**| 0.01 ms / 0.04 ms | 0.03 ms / 0.05 ms | 0.61 ms / 0.71 ms | $< 25$ ms |
| **Peak Build Memory** | 0.10 MB | 0.10 MB | **0.11 MB** | $< 25$ MB |
| **Peak Query Memory** | 0.05 MB | 0.05 MB | **0.02 MB** | $< 25$ MB |

---

## 6. Shadow Operation Verification

1. **Consumer Insulation**: HRIDAY, Presentation, and Dashboard pipelines continue consuming canonical V1 data structures with 0 modifications.
2. **Zero Ingestion V1 Regressions**: Baseline consumer regression suites passed at 100%.
3. **Database Immutability**: Production SQLite database (`pulsehr.sqlite3`) verified bit-for-bit unchanged (70,385,664 bytes).
4. **Zero LLM Calls**: System runs completely deterministic search without invoking LLMs during index construction or context assembly (`llm_calls = 0`).
