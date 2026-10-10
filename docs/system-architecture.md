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
  │     - 5-KPI strip, 3 visual stories (Hero, Outlier, Scatter), Top 3/Bottom 3 ranking        │
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
5. **Dashboard vs. Explorer Separation Guarantee:** Level 1 Executive Dashboard is restricted to executive briefing, 5 KPIs, 3 visual stories, and compact Top 3/Bottom 3; full analytics and evidence live in the Data Explorer.
6. **Capability Entitlement Guarantee:** Specialized domain modules (Scenario Explorer) are strictly hidden on non-entitled domains.
7. **Direct Inheritance Guarantee:** Downstream presentation decks, dashboards, and conversational answers inherit directly from the same evidence store.
8. **Permutation-Only Prioritization Guarantee:** AI models can only reorder verified finding IDs; they cannot mutate mathematical values or invent ungrounded assertions.
9. **Worker Resilience Guarantee:** Background generation jobs survive server reloads through PID-aware SQLite job recovery with bounded retries.
10. **Dataset Boundary & Isolation Invariant:** Analytical artifacts and relationship joins must strictly satisfy `artifact.dataset_id == active_dataset_id`. Cross-dataset joins are permanently barred, deletion cascades bidirectionally with verified zero-orphan checks (`orphan_check="PASS"`), and all in-memory snapshot caches are completely purged upon source deletion.
