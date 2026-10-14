# HighView & HRIDAY: System Architecture & Layer Integration

> **Parent:** [README.md](../README.md) &rsaquo; **System Architecture**

---

## 1. System Vision & Core Architectural Axioms

**HighView** is a local-first enterprise analytics, cross-domain decision intelligence, and presentation automation platform powered by the **HRIDAY** AI assistant. It eliminates AI calculation hallucinations and analytical distortions by strictly decoupling deterministic mathematical computation from language model narrative generation.

Spreadsheet and CSV reports frequently violate textbook relational formats. HighView enforces an immutable pre-semantic reconstruction stage that transforms semi-structured physical documents into verified logical tables before database persistence or semantic profiling.

---

## 2. Integrated Layer Architecture

The platform is architected into **5 cohesive, integrated layers** supported by dedicated cross-cutting specifications:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   HIGHVIEW SYSTEM ARCHITECTURE                                  │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

  LAYER 1: DETERMINISTIC TRUTH & EVIDENCE ENGINE
  ┌─────────────────────────────────────────────────────────────────────────────────────────────┐
  │ • Adaptive Table Reconstruction: Physical-to-logical transformation (GridCapture, Stitcher) │
  │ • Governed Model Escalator: Deterministic-first with typed Pydantic proposals & 3D confidence│
  │ • Source-Faithful Sentinels: Preserves NM, -, NR, BDL; strictly bans coercion to 0.0        │
  │ • SQLite Storage & Provenance: Reconstructed tables stored in pulsehr.sqlite3 with lineage  │
  │ • Generic Semantic Profiling: Ordinal/identifier exclusion; non-additive measure detection  │
  │ • Dataset Boundary & Isolation: DatasetIsolationIntegrity; strict intra-dataset joins only  │
  │ • Transactional Cascaded Deletion: Bidirectional relationship purge, cache wipe, orphan test│
  │ • Mathematical Opportunity Mapping: Univariate, bivariate, correlations, cohorts            │
  │ • Candidate Fact Discovery: Pure code computation (FACT-XXX), minimum sample size gates     │
  │ • Cryptographic Evidence Ledger: SHA-256 sealed shared evidence package (EVID-XXX)          │
  └──────────────────────────────────────┬──────────────────────────────────────────────────────┘
                                         │  Contracts: list[CandidateFact], Evidence Ledger, DatasetIsolationIntegrity
                                         ▼
  LAYER 2: COGNITIVE ROUTING & GOVERNANCE LAYER
  ┌─────────────────────────────────────────────────────────────────────────────────────────────┐
  │ • Sub-Millisecond Intent Routing: RuleDecisionEngine (<1ms), EmbeddingDecisionEngine (<15ms)│
  │ • Dynamic ModelRouter & Escalator: Task-specific model assignment with confidence escalation│
  │ • Role-Based Gateway: FAST (phi4), ANALYST (qwen3.5), REASONER (deepseek-r1), WRITER (gemma4)│
  │ • Assistant Identity Layer: HRIDAY persona, identity_leak scanner, bounded retries         │
  │ • Narrative & Temporal Integrity: DomainNarrativeIntegrity (strips HR copy), TemporalLabel  │
  │ • Deterministic Claim Audit: CriticAgent, interpretation_validator (zero math mutations)    │
  └──────────────────────────────────────┬──────────────────────────────────────────────────────┘
                                         │  Contracts: InterpretationResponse, Audited Insights
                                         ▼
  LAYER 3: MULTI-SURFACE CONSUMER DELIVERY ENGINE
  ┌─────────────────────────────────────────────────────────────────────────────────────────────┐
  │ • Consumer 3A: Executive Dashboard ("What requires my attention?")                         │
  │     - 5-KPI strip, 8–15 visual portfolio (Hero, Box Plot, Scatter, Podium, Bullet, etc.)   │
  │     - VisualPortfolioOptimizer & SpatialCompositionOptimizer (zero-orphan balanced rows)   │
  │ • Consumer 3B: Data Explorer ("Show me the analysis behind it?")                            │
  │     - 7 deep analytical tabs: Overview, Rankings, Trends, Relationships, Distributions,     │
  │       Evidence, Technical (Reconstruction safety radar, confidence scores, provenance)      │
  │ • Consumer 3C: Capability Entitlement Gating: Workforce Scenario Explorer gated by domain   │
  │ • Consumer 3D: Automated 13-Phase Presentation Engine & Live SlideMutator (16:9 decks)      │
  │ • Consumer 3E: HRIDAY Copilot & War Room: 0-LLM math Q&A, chat charts, SSE streaming       │
  └──────────────────────────────────────┬──────────────────────────────────────────────────────┘
                                         │  Contracts: Slide Specs, Visual Cards, Table Specs
                                         ▼
  LAYER 4: VISUAL GRAMMAR & SPATIAL CONTRACT
  ┌─────────────────────────────────────────────────────────────────────────────────────────────┐
  │ • HighView Design Tokens: _tokens.scss -> Navy/Emerald/Ivory, Light/Dark, WCAG AAA (>=7:1)  │
  │ • Unified 16:9 Spatial Baseline: 960×540 pt baseline, 864×460 pt usable content area       │
  │ • Standard Typography Hierarchy: 38pt cover, 30pt header, 20pt panel, 18pt body, 16pt table│
  │ • Truthful Visual Intent Grammar: True ECharts scatter plots for bivariate relationships,   │
  │   ban on synthetic time labels, horizontal bars for benchmarks, variance bars for anomalies │
  │ • Intelligent Spatial Composition: server-driven 12-col packing, synchronized row heights  │
  │ • Native Multi-Format Exporters: python-pptx native vector charts, headless PDF, React UI   │
  └─────────────────────────────────────────────────────────────────────────────────────────────┘

  LAYER 5: PLATFORM RELIABILITY & TEST OPERATIONS (Cross-Cutting Foundation)
  ┌─────────────────────────────────────────────────────────────────────────────────────────────┐
  │ • Process-Aware Worker Recovery: recover_presentation_jobs, PID validation, max 3 retries   │
  │ • Reconstruction Safety Benchmark: Boundary accuracy, header accuracy, record accuracy    │
  │ • 3-Tier Test Pyramid: Unit <50ms, Integration 0.5-5s, Benchmark quarantined                │
  │ • Pre-Push Impact Analyzer: run_impacted_tests.py, git diff module detection                │
  └─────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Layer Directory & Document Map

| Document Node | Title | Key Architectural Responsibilities |
| :--- | :--- | :--- |
| [Reconstruction Subsystem](adaptive-table-reconstruction.md) | **Adaptive Table Reconstruction** | Pre-semantic ingestion, multi-row header repair, wrapped record stitching, sentinel preservation, 3D confidence, and CPCB regression benchmark. |
| [Governance & Boundaries](domain-governance-and-dashboards.md) | **Domain Governance & Boundaries** | Executive Dashboard vs. Data Explorer boundary, capability entitlement gating, generic ranking polarity, non-additive aggregation rules. |
| [Layer 1](layers/01-deterministic-truth-engine.md) | **Deterministic Truth & Evidence Engine** | Physical-to-logical pipeline, semantic profiling, ordinals exclusion, `FACT-XXX` discovery, cross-domain models, cryptographic evidence ledger. |
| [Layer 2](layers/02-cognitive-routing-governance.md) | **Cognitive Routing & Governance** | Decision routing (<1ms), model roles, HRIDAY identity guard, narrative & temporal integrity, claim verification, permutation invariant. |
| [Layer 3](layers/03-consumer-delivery-engine.md) | **Consumer Delivery Engine** | Executive Dashboard, 7-tab Data Explorer, 13-phase presentation engine, slide mutator, scenario entitlement, copilot. |
| [Layer 4](layers/04-visual-grammar-spatial.md) | **Visual Grammar & Spatial Contract** | Design tokens (`_tokens.scss`), 16:9 geometry (960×540 pt), visual intent grammar, scatter rendering, table overflow safety. |
| [Layer 5](layers/05-platform-reliability-ops.md) | **Platform Reliability & Test Ops** | Worker PID recovery, reconstruction safety benchmarks, 3-tier test pyramid, pre-push impact runner. |

---

## 4. End-to-End Inter-Layer Contracts & System Invariants

```text
[Raw Physical File (CSV / XLSX / SQLite)]
         │
         ▼ (Layer 1: Adaptive Table Reconstruction)
[Clean Logical Table (Reconstructed Dataframe + Lineage Ledger)]
         │
         ▼ (Layer 1: Semantic Profiling & Opportunity Mapping)
[CandidateFact (FACT-XXX) + SharedEvidencePackage (EVID-XXX, SHA-256)]
         │
         ▼ (Layer 2: Cognitive Routing & Governance)
[Audited Insights (InterpretationResponse) + Prioritized Findings]
         │
         ▼ (Layer 3: Multi-Surface Delivery Engine)
[Executive Dashboard + Data Explorer + Slide Specs + Copilot Answers]
         │
         ▼ (Layer 4: Visual Grammar & Spatial Contract)
[Native PPTX + High-DPI PDF + Interactive React ECharts Views]
```

### Core System Invariants
1. **Physical File &ne; Logical Table Invariant:** No analytical computation touches a physical spreadsheet directly. All documents pass through `AdaptiveTableReconstructionEngine` to resolve headers, preambles, and wrapped records.
2. **Zero LLM Math Guarantee:** Code computes all numbers deterministically. Models receive verified numbers as context and generate narratives; they never compute sums, averages, or deltas.
3. **Non-Additive Aggregation Guarantee:** Concentration and rate metrics cannot be summed. Averages, medians, or distributions are enforced.
4. **Ordinal Exclusion Guarantee:** Sequence numbers and document codes (e.g. `Sr. No.`) are excluded from numeric rankings and KPI rollups.
5. **Dashboard vs. Explorer Separation Guarantee:** Level 1 Executive Dashboard is restricted to executive briefing, 5 KPIs, governed 8–15 visual portfolio (target 10–12) with perceptual morphology capping and semantic visual microcopy, and compact Top 3/Bottom 3; full analytics and evidence live in the Data Explorer.
6. **Capability Entitlement Guarantee:** Specialized domain modules (Scenario Explorer) are strictly hidden on non-entitled domains.
7. **Direct Inheritance Guarantee:** Downstream presentation decks, dashboards, and conversational answers inherit directly from the same evidence store.
8. **Permutation-Only Prioritization Guarantee:** AI models can only reorder verified finding IDs; they cannot mutate mathematical values or invent ungrounded assertions.
9. **Worker Resilience Guarantee:** Background generation jobs survive server reloads through PID-aware SQLite job recovery with bounded retries.
10. **Dataset Boundary & Isolation Invariant:** Analytical artifacts and relationship joins must strictly satisfy `artifact.dataset_id == active_dataset_id`. Cross-dataset joins are permanently barred, deletion cascades bidirectionally with verified zero-orphan checks (`orphan_check="PASS"`), and all in-memory snapshot caches are completely purged upon source deletion.

---

## 5. Modernization & Strangler Architecture (Phases G1 – G5)

To decouple HighView's deterministic core from monolithic engine dependencies, the platform implements a disciplined strangler refactoring model:

```text
AnalyticalFact
      ↓  (app/services/adaptive_dashboard/evidence/)
BoundFact / EvidenceBinding
      ↓  (app/services/adaptive_dashboard/narrative/)
NarrativeResult / Executive Briefing
      ↓  (app/services/adaptive_dashboard/composition_planner.py)
ExecutiveTopic (Immutable Aggregate)
      ↓  (app/services/adaptive_dashboard/visuals/)
VisualSpec (Theme-Agnostic)
      ↓  (app/services/adaptive_dashboard/spatial_composition_optimizer.py)
Spatial Composition (12-Col Responsive Grid)
      ↓
React Frontend Presentation (ECharts / SCSS Tokens)
```

### Strangler Milestone Highlights

* **Phase G1 — Scoped Lifecycle & Idempotent Migrations:**
  - Guaranteed deterministic connection scoping via `session_scope()` context managers.
  - Numbered, idempotent forward schema migrations (`0001` to `0006`) managed via SQLite PRAGMA checks.
  - Explicit CORS governance and strongly typed Pydantic application settings.

* **Phase G2 — Deterministic Version-Aware Analytics Cache:**
  - Low-latency (`~10ms` warm P50) caching layer via `DashboardCacheService`.
  - Version-aware canonical cache keys (`dataset_id`, `version`, `topic_id`, `intent`).
  - Strict theme independence: dark/light theme switching never bypasses or pollutes cached data.
  - Single-flight thundering-herd protection and fail-closed cross-dataset guards.

* **Phase G3 — Columnar Parquet Data Plane & DuckDB Query Engine:**
  - Immutable versioned storage: `data/datasets/<id>/v<ver>/<logical_table>.parquet`.
  - Process-safe in-memory read-only DuckDB analytical sessions via `AnalyticalQueryService`.
  - Source provenance and sentinel fidelity (NM, NR, BDL) preserved throughout analytical queries.
  - High-concurrency query execution with significant Python heap decompression.

* **Phase G4 — Slow-Path Worker Plane & Request-Execution Decoupling:**
  - Long-running presentation and export generation detached from HTTP request lifecycles.
  - Immediate `202 Accepted` response with asynchronous job tracking (`/api/jobs/{job_id}`).
  - Strict path confinement on artifact downloads preventing directory traversal.

* **Phase G5.1 — Presentation Formatting & Labels Strangler Decoupling:**
  - Isolated zero-dependency presentation label and title utilities (`formatting/presentation_labels.py`).
  - Guaranteed elimination of underscores and kebab-case in human-facing titles.
  - Multi-domain characterization baseline protecting workforce, retail, and environmental boundaries.

* **Phase G5.2 — Evidence Binding & Lineage Provenance:**
  - Hard boundary establishing typed contracts (`BoundFact`, `BoundEvidence`, `ProvenanceRecord`).
  - Complete decoupling from visual and presentation specifications (`EvidenceOwnershipIntegrity`).
  - Absolute local filesystem paths sanitized from lineage citations.
  - Protected by executable AST boundary purity tests preventing DB, AI, or visual leakage.

* **Phase G5.3 — Briefing & Narrative Extraction:**
  - Dedicated business wording package (`narrative/`): `NarrativeInput`, `NarrativeResult`, `TitleBuilder`, `FindingBuilder`, `NarrativeDeduplicationIntegrity`, `ExecutiveBriefingService`.
  - **Narrative Invariant:** *"Evidence establishes what is true. Narrative explains that truth. Narrative may simplify wording, but it may never create, alter, or reclassify analytical truth."*
  - Complete elimination of internal machine taxonomy (*"Semantic Family"*, *"Visual Morphology"*, *"Distributions & Variance"*).
  - Numeric entitlement audits preventing hallucinated or recomputed numbers in narrative text.

* **Phase G5.4 — Visual Specification Boundary & ExecutiveTopic Assembly Hardening:**
  - Theme-agnostic visual specification domain (`visuals/`): `VisualInput`, `VisualSpec`, `VisualSpecFactory`, `VisualCapabilityRegistry`.
  - **Visual Invariant:** Answers *"How should this already-understood analytical story be shown?"* without inventing business meaning, narrative, or evidence.
  - Strict title-axis semantic consistency preventing cross-domain contamination (e.g. retail axes with workforce titles).
  - Immutability guarantee (`VisualSemanticsMutationIntegrity`): composition may adjust layout/span, but cannot mutate chart type, series, axes, or measures.
  - Full titles preserved alongside responsive display titles.

* **Phase G5.5 — Analytical Story / ExecutiveTopic Factory & Semantic Identity Boundary:**
  - Dedicated story and topic assembly package (`topics/`): `TopicIdentitySeed`, `TopicIdentityFactory`, `ExecutiveTopicDraft`, `ExecutiveTopic`, `ExecutiveTopicFactory`, `TopicIdGenerator`, `StoryAssemblyIntegrity`.
  - **Story Assembly Invariant:** *"A story does not calculate facts, create evidence, choose chart mechanics, or decide layout. It assembles already-governed meaning into one immutable topic identity."*
  - **Semantic Identity Invariant:** *"Topic identity represents semantic ownership, not construction or execution order."*
  - Pure, deterministic semantic hashing (`TopicIdentityFactory.create_topic_id(seed)` &rarr; `TOPIC-[hash[:8]]`, e.g. `TOPIC-a503738a`) deriving version-scoped canonical IDs from dataset, version, domain, analytical intent, entity grain, metric family, measures, dimensions, and opportunity ID.
  - Distinct separation of semantic identity from presentation sequencing: `display_order`, `rank`, and `portfolio_position` track portfolio layout order, completely decoupled from `topic_id`.
  - Version-independent logical topic tracking via `semantic_topic_key` (`domain:intent:grain:family`).
  - Runtime immutability guard: mutating semantic fields (`topic_id`, `semantic_topic_key`, `analytical_intent`, `domain`, `dataset_id`, `evidence_ids`) on `ExecutiveTopic` raises `AttributeError: IMMUTABILITY_VIOLATION`.
  - Strict identity-based assembly: `ExecutiveTopicFactory.bind_visual_spec(topic, visual_spec)` validates topic identity match (`topic.topic_id == visual_spec.topic_id`) with zero visual decision logic.
  - Fail-closed validation: any mismatch across `narrative.topic_id`, `evidence_binding.topic_id`, `executive_topic.topic_id`, or `visual_spec.topic_id` raises `StoryAssemblyIntegrityError`.
  - Verified across 20-thread concurrency, portfolio permutation invariance (`[A, B, C]` vs `[C, A, B]`), insertion invariance (`[A, B, C]` vs `[A, X, B, C]`), cold/warm cache consistency, AST purity, and full multi-viewport browser testing.

