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

Evaluated across 6 canonical domains (Workforce, Retail, Environmental, Finance, SaaS, Supply Chain) with 24 distinct queries:

| Namespace | Recall@1 | Recall@3 | Recall@5 | MRR | nDCG@5 | Forbidden Result Rate | Wrong-Dataset Leakage | Stale-Artifact Rate | Orphan Document Rate |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `RAW_SCHEMA` | **1.000** | **1.000** | **1.000** | **1.000** | **1.000** | **0.000** | **0.000** | **0.000** | **0.000** |
| `SEMANTIC` | **1.000** | **1.000** | **1.000** | **1.000** | **1.000** | **0.000** | **0.000** | **0.000** | **0.000** |
| `RELATIONSHIP` | **1.000** | **1.000** | **1.000** | **1.000** | **1.000** | **0.000** | **0.000** | **0.000** | **0.000** |
| `ANALYTICAL` | **1.000** | **1.000** | **1.000** | **1.000** | **1.000** | **0.000** | **0.000** | **0.000** | **0.000** |
| **AGGREGATE (24 queries)** | **1.000** | **1.000** | **1.000** | **1.000** | **1.000** | **0.000** | **0.000** | **0.000** | **0.000** |

*Note: Recall@1 and MRR are computed and reported as independent metrics.*

---

## 5. Embedding Telemetry & Cache Certification

### 5.1 Deterministic Cache Key
Embedding vectors are cached using a deterministic four-part composite key:
```
f"{content_fingerprint}:{embedding_model_id}:{embedding_model_version}:{normalization_policy}"
```
- **Content Change**: Content hash mutation forces an immediate cache miss.
- **Model Change**: Upgrading or swapping the embedding model ID/version forces a complete cache invalidation.
- **Normalization Policy**: Changing vector normalization policy (`l2`, `none`) forces re-computation.

### 5.2 Telemetry Tracking
Telemetry counters are tracked separately between document ingestion and query requests:
- `document_embedding_requests`: Total documents requested for embedding.
- `document_embedding_cache_hits`: Ingestion documents resolved from memory cache.
- `document_embedding_cache_misses`: Ingestion documents requiring vector calculation.
- `query_embedding_requests`: Total search queries embedded.
- `query_embedding_failures`: Query embedding errors leading to degraded BM25 fallback.
- `llm_calls`: Strictly **0** (no generative LLM models are invoked anywhere in the retrieval path).

---

## 6. Cold Build vs. Warm Rebuild Telemetry

Measured across independent Small, Medium, and Large fixture scales (15 iterations each):

### 6.1 Cold Index Build (First Ingestion, Zero Cache)
| Stage | Small (2 tbl, 20 docs) | Medium (6 tbl, 74 docs) | Large (16 tbl, 184 docs) | Target SLA |
| :--- | :--- | :--- | :--- | :--- |
| **Document Builder (P50 / P95)** | 0.180 ms / 0.752 ms | 0.634 ms / 0.874 ms | 1.545 ms / 1.738 ms | $< 50$ ms |
| **BM25 Build (P50 / P95)** | 0.142 ms / 0.328 ms | 0.204 ms / 0.244 ms | 0.501 ms / 0.568 ms | $< 50$ ms |
| **Vector Build (P50 / P95)** | 0.077 ms / 0.129 ms | 0.123 ms / 0.145 ms | 0.306 ms / 0.356 ms | $< 50$ ms |
| **Graph Prep (P50 / P95)** | 0.000 ms / 0.003 ms | 0.000 ms / 0.001 ms | 0.000 ms / 0.001 ms | $< 5$ ms |
| **Manifest Build (P50 / P95)** | 0.010 ms / 0.042 ms | 0.023 ms / 0.044 ms | 0.051 ms / 0.085 ms | $< 5$ ms |
| **Total Cold Build (P50 / P95)**| **0.409 ms / 1.254 ms** | **0.984 ms / 1.308 ms** | **2.403 ms / 2.748 ms** | $< 50$ ms |

### 6.2 Warm Index Rebuild (100% Cache Hits)
| Stage | Small (20 docs) | Medium (74 docs) | Large (184 docs) | Target SLA |
| :--- | :--- | :--- | :--- | :--- |
| **BM25 Warm Rebuild (P50 / P95)** | 0.060 ms / 0.088 ms | 0.208 ms / 0.244 ms | 0.502 ms / 0.606 ms | $< 25$ ms |
| **Vector Warm Rebuild (P50 / P95)**| 0.003 ms / 0.007 ms | 0.012 ms / 0.016 ms | 0.033 ms / 0.038 ms | $< 10$ ms |
| **Vector Cache Hit Rate** | **100.0%** | **100.0%** | **100.0%** | 100% |
| **Total Warm Rebuild (P50 / P95)** | **0.063 ms / 0.095 ms** | **0.220 ms / 0.260 ms** | **0.535 ms / 0.644 ms** | $< 25$ ms |

### 6.3 Query Execution Telemetry
| Stage | Small | Medium | Large | Target SLA |
| :--- | :--- | :--- | :--- | :--- |
| **BM25 Query (P50 / P95)** | 0.030 ms / 0.116 ms | 0.043 ms / 0.086 ms | 0.062 ms / 0.096 ms | $< 10$ ms |
| **Vector Query (P50 / P95)** | 0.031 ms / 0.050 ms | 0.094 ms / 0.109 ms | 0.226 ms / 0.249 ms | $< 20$ ms |
| **Graph Traversal (P50 / P95)** | 0.001 ms / 0.007 ms | 0.001 ms / 0.005 ms | 0.001 ms / 0.006 ms | $< 10$ ms |
| **Hybrid Fusion (P50 / P95)** | 0.094 ms / 0.143 ms | 0.185 ms / 0.217 ms | 0.339 ms / 0.373 ms | $< 25$ ms |
| **Reranking (P50 / P95)** | 0.010 ms / 0.012 ms | 0.010 ms / 0.012 ms | 0.010 ms / 0.015 ms | $< 10$ ms |
| **Context Assembly (P50 / P95)**| 0.011 ms / 0.037 ms | 0.013 ms / 0.059 ms | 0.015 ms / 0.041 ms | $< 25$ ms |
| **Total Query Latency (P50 / P95)** | **0.177 ms / 0.365 ms** | **0.346 ms / 0.488 ms** | **0.653 ms / 0.780 ms** | $< 50$ ms |
| **Peak Build / Query Memory** | 0.10 MB / 0.05 MB | 0.10 MB / 0.05 MB | **0.11 MB / 0.02 MB** | $< 25$ MB |

---

## 7. Invalidation & Deletion Cascade Certification

1. **Dataset Deletion Cascade**:
   - Calling `delete_dataset(dataset_id)` removes all associated documents from all BM25 namespace partitions and vector storage.
   - Subsequent queries for the deleted dataset return strictly 0 candidates and empty context packages.
   - Associated retrieval manifest is flagged as stale.
2. **Version Replacement (v1 -> v2)**:
   - Ingesting v2 invalidates and replaces v1 documents in-place.
   - Queries targeting the dataset return 100% v2 artifacts; zero v1 documents leak into search results.
3. **Artifact Dependency Invalidation**:
   - Fingerprint mutations in either the `SemanticGraph` (`graph_fingerprint`) or `AnalyticalProfile` (`source_fingerprint`) immediately flag the manifest as stale (`is_stale() == True`), preventing stale cache reads.

---

## 8. Shadow Operation Verification

1. **Consumer Insulation**: HRIDAY, Presentation, and Dashboard pipelines continue consuming canonical V1 data structures with 0 modifications.
2. **Zero Ingestion V1 Regressions**: Baseline consumer regression suites passed at 100%.
3. **Database Immutability**: Production SQLite database (`pulsehr.sqlite3`) verified bit-for-bit unchanged (70,385,664 bytes).
4. **Zero LLM Calls**: System runs completely deterministic search without invoking LLMs during index construction or context assembly (`llm_calls = 0`).

---

## 9. Embedding Telemetry & Hermetic Test Certification

### 9.1 Embedding Telemetry Counters (Canonical 24-Query 6-Domain Benchmark)

| Telemetry Field | Benchmark Value | Description |
| :--- | :--- | :--- |
| `document_embedding_requests` (Cold Build) | **24** | 24 canonical documents across 6 domains (4 per domain across 4 namespaces) |
| `document_embedding_cache_hits` (Cold Build) | **0** | Initial cold index construction |
| `document_embedding_cache_misses` (Cold Build) | **24** | 100% computed on cold build |
| `query_embedding_requests` | **24** | Exactly 1 per retrieval benchmark query |
| `query_embedding_failures` | **0** | Zero embedding failures during evaluation |
| `llm_calls` | **0** | Zero generative model or council calls during retrieval |
| `embedding_model_id` | `"nomic-embed-text"` | Dedicated local embedding model identifier |
| `embedding_model_version` | `"v1.5"` | Pinned model weight version |
| `normalization_policy` | `"l2"` | Euclidean unit length normalization |

### 9.2 Warm Index Rebuild Cache Invariant
- **Reusable Documents Evaluated**: **24**
- **Document Embedding Cache Hits**: **24** (`document_embedding_cache_hits == reusable_documents`)
- **New Embedding Computations**: **0**

### 9.3 Hermetic Network Isolation & Offline Graceful Degradation
1. **Network Firewall Guard**: Socket connection to port 11434 intercepted in test environment; unmocked attempts raise `ConnectionRefusedError("HERMETIC TEST FIREWALL: Connection to port 11434 is blocked in test environment. Tests must mock embedding/model HTTP requests.")`.
2. **HTTP Transport Mocking**: `test_text_embedding_works` explicitly mocks `httpx.Client.post` transport, verifying exact endpoint, vector dimensionality (768), and memory cache hit behavior without network I/O.
3. **Offline Graceful Degradation**: `NomicEmbeddingService.embed_text` catches connection errors and returns `None`, degrading gracefully to keyword/BM25 without unhandled exceptions.

