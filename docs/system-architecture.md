# HighView & HRIDAY: System Architecture & Layer Integration

> **Parent:** [README.md](../README.md) &rsaquo; **System Architecture**

## 1. System Vision & Core Architectural Axioms

**HighView** is a local-first enterprise analytics and presentation automation platform powered by the **HRIDAY** AI assistant. It eliminates AI calculation hallucinations by strictly decoupling deterministic mathematical computation from language model narrative generation.

---

## 2. Integrated Layer Architecture

Rather than fragmenting functionality across disconnected silos, the codebase is architected into **5 cohesive, integrated layers**:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   HIGHVIEW SYSTEM ARCHITECTURE                                  │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

  LAYER 1: DETERMINISTIC TRUTH & EVIDENCE ENGINE
  ┌─────────────────────────────────────────────────────────────────────────────────────────────┐
  │ • Ingestion, SQLite Storage, Data Hygiene & Schemas (upload.py, sheet_catalog.py)           │
  │ • Generic Semantic Profiling & Grain Inference (semantic_classifier.py)                     │
  │ • Mathematical Opportunity Mapping (opportunity_map.py)                                    │
  │ • Candidate Fact Discovery (candidate_fact_discovery.py -> FACT-XXX)                        │
  │ • Industrial Models: McKinsey 9-Box, Bradford Factor (B=S²*D), Burnout Strain, Holt Forecast│
  │ • Cryptographic Evidence Ledger & SHA-256 Snapshot Seal (shared_evidence_package.py)        │
  └──────────────────────────────────────┬──────────────────────────────────────────────────────┘
                                         │  Contracts: list[CandidateFact], Evidence Ledger
                                         ▼
  LAYER 2: COGNITIVE ROUTING & GOVERNANCE LAYER
  ┌─────────────────────────────────────────────────────────────────────────────────────────────┐
  │ • Sub-Millisecond Intent Routing: RuleDecisionEngine (<1ms), EmbeddingDecisionEngine (<15ms)│
  │ • Dynamic ModelRouter with Confidence Escalation (FAST -> ANALYST -> REASONER)              │
  │ • Role-Based Gateway (FAST: phi4, ANALYST: qwen3.5, REASONER: deepseek-r1, WRITER: gemma4) │
  │ • Assistant Identity Layer (assistant_identity.py -> HRIDAY persona, identity_leak guard)   │
  │ • Deterministic Claim Audit & Verification (critic_agent.py, interpretation_validator.py)   │
  │ • Permutation-Only Finding Prioritization Invariant                                         │
  └──────────────────────────────────────┬──────────────────────────────────────────────────────┘
                                         │  Contracts: InterpretationResponse, Audited Insights
                                         ▼
  LAYER 3: MULTI-SURFACE CONSUMER DELIVERY ENGINE
  ┌─────────────────────────────────────────────────────────────────────────────────────────────┐
  │ • Consumer 3A: Adaptive Multi-Domain Decision Dashboard (7 domains, 3 disclosure tiers)     │
  │ • Consumer 3B: Automated Presentation Engine (13-phase orchestrator, 7 layouts, notes)      │
  │ • Consumer 3C: HRIDAY Copilot & Multi-Model Council War Room (0-LLM math, grain integrity)  │
  │ • Consumer 3D: Executive Decision Brief API (GET/POST /api/analytics/decision-brief)        │
  └──────────────────────────────────────┬──────────────────────────────────────────────────────┘
                                         │  Contracts: Slide Specs, Visual Cards, Table Specs
                                         ▼
  LAYER 4: VISUAL GRAMMAR & SPATIAL CONTRACT
  ┌─────────────────────────────────────────────────────────────────────────────────────────────┐
  │ • HighView Design Tokens (_tokens.scss -> Navy/Emerald/Ivory, Light/Dark, WCAG AAA)         │
  │ • Unified 16:9 Spatial Baseline (960×540 pt baseline, 864×460 pt content zone)             │
  │ • Standard Typography Hierarchy (38pt cover, 30pt header, 18pt body, 16pt table, 14pt chart)│
  │ • Dense Table Safety & Multi-Page Continuation (weighted columns, overflow row protection)   │
  │ • Native Multi-Format Exporters (python-pptx native shapes/charts, headless PDF, HTML viewer)│
  └─────────────────────────────────────────────────────────────────────────────────────────────┘

  LAYER 5: PLATFORM RELIABILITY & TEST OPERATIONS (Cross-Cutting Foundation)
  ┌─────────────────────────────────────────────────────────────────────────────────────────────┐
  │ • Process-Aware Worker Recovery (recover_presentation_jobs, PID validation, max 3 retries)  │
  │ • 3-Tier Test Pyramid (Unit <50ms, Integration 0.5-5s, Benchmark quarantined)              │
  │ • Pre-Push Impact Analyzer (run_impacted_tests.py, git diff module detection)               │
  └─────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Layer Directory & Document Map

Each layer is comprehensively documented in its own dedicated, cohesive document:

| Layer Node | Title | Key Architectural Responsibilities |
| :--- | :--- | :--- |
| [Layer 1](layers/01-deterministic-truth-engine.md) | **Deterministic Truth & Evidence Engine** | Data ingestion, semantic profiling, `FACT-XXX` discovery, 9-Box, Bradford Factor, evidence ledger. |
| [Layer 2](layers/02-cognitive-routing-governance.md) | **Cognitive Routing & Governance** | Decision routing (<1ms), model roles, HRIDAY identity guard, claim verification, permutation rule. |
| [Layer 3](layers/03-consumer-delivery-engine.md) | **Consumer Delivery Engine** | Adaptive dashboard (7 domains, 3 tiers), 13-phase presentation engine, copilot, decision briefs. |
| [Layer 4](layers/04-visual-grammar-spatial.md) | **Visual Grammar & Spatial Contract** | Design tokens (`_tokens.scss`), 16:9 geometry (960×540 pt), typography hierarchy, table safety. |
| [Layer 5](layers/05-platform-reliability-ops.md) | **Platform Reliability & Test Ops** | Background worker PID recovery, 3-tier test pyramid, pre-push impact runner. |

---

## 4. End-to-End Inter-Layer Contracts

```
[Raw Tabular Dataset]
         │
         ▼ (Layer 1: Deterministic Engine)
[CandidateFact (FACT-XXX) + SharedEvidencePackage (EVID-XXX, SHA-256)]
         │
         ▼ (Layer 2: Cognitive Routing & Governance)
[Audited Insights (InterpretationResponse) + Prioritized Findings]
         │
         ▼ (Layer 3: Consumer Delivery Engine)
[Presentation Deck Spec + Adaptive Dashboard Cards + Copilot Answers]
         │
         ▼ (Layer 4: Visual Grammar & Spatial Contract)
[Native PPTX + High-DPI PDF + Interactive React Studio Viewer]
```

1. **Zero LLM Math Guarantee**: Only code computes numbers. Models receive verified numbers as context and generate narratives; they never compute sums, averages, or deltas.
2. **100% Direct Inheritance Guarantee**: Downstream presentation decks and dashboards inherit directly from the same evidence store. Discrepancies between views are architecturally impossible.
3. **Grain Integrity Guarantee**: Analytical queries maintain requested grain; an aggregate department average is never accepted as proof for an individual employee fact.
4. **Permutation-Only Prioritization Guarantee**: AI models can only reorder verified finding IDs; they cannot mutate mathematical values or invent ungrounded assertions.
5. **Worker Resilience Guarantee**: Background generation jobs survive server reloads through PID-aware SQLite job recovery with bounded retries.
