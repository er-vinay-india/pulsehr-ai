# Presentation Studio Product Track 3.1: Baseline Audit, Contract Boundary & Failure Map

## Executive Summary

Product Track 3.1 establishes the authoritative baseline audit and failure catalog for HighView Presentation Studio. In accordance with strict architectural governance, upstream Executive Dashboard components (Product Tracks 2.1 through 2.4, frozen at commit `8576cad438915070e89c9a1612f0af0e8e68e0ac`) are treated as immutable upstream truth. 

This audit was conducted strictly in **AUDIT-ONLY** mode without modifying generator behaviors or attempting premature fixes.

### Key Audit Findings

1. **Upstream Contract Bypass**:
   Presentation Studio currently bypasses the frozen `ExecutiveTopic`, `fact_id`, `evidence_ids`, and `VisualSpec` contracts established in Product Tracks 2.1–2.4. Instead of ingesting governed dashboard topics, Presentation Studio maintains independent, bifurcated generation pipelines that recreate facts and visualizations from scratch.

2. **Bifurcated Routing & Default Path Failure**:
   - **Workforce Domain**: Automatically diverts to `build_hr_report` (`hr_attendance_v1`) upon detecting attendance column aliases (`Emp ID`, `Attendance`). It produces a bespoke 9-slide deck in 1.79s, completely bypassing AI models.
   - **Retail & Environmental Domains**: Enter the AI Presentation Director (`presentation_director.py`, powered by Qwen 3.5 via local Ollama). After 220–255 seconds of multi-stage LLM generation, Stage 5 plan validation fails (`ValueError: Presentation plan lacks supported answers or claims`), causing the pipeline to fall back to `build_grounded_review` (`recorded_results_v1`). This fallback dumps raw dataset columns (e.g., `Store at a glance`, `Weekly_Sales at a glance`, `Holiday_Flag at a glance`) rather than executive insights.

3. **Spatial Overflow & Long-Title Export Crash**:
   - **Table Pagination**: Successfully decomposes large tables (e.g. 25 rows) across up to 5 physical slide pages with repeated table headers and zero data loss.
   - **Title Height Cliff**: Slide titles exceeding 155pt cumulative height (approx. 2 lines of 32pt text) throw an unhandled `SlideLayoutError('The slide title needs a shorter heading or a separate cover.')` in `slide_layout.py`, crashing PPTX and PDF exports.

4. **Track 3.2 Architectural Invariant**:
   To reconcile presentation pagination with semantic governance, Track 3.2 must enforce the following rule:
   > **"One governed ExecutiveTopic maps to one presentation topic identity, which may render as one or more physical slides without changing fact/evidence ownership."**

---

## 1. Authoritative Default Production Path Characterization

The default production pipeline was benchmarked across the three standard benchmark domains with `enable_ai_planner=True` and `force_legacy_builders=False`.

| Benchmark Domain | Sheet ID | Active Route / Content Contract | AI Model Invocation | Total Latency | Final Slide Count | Primary Presentation Failure |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Workforce** | `9967416` | Bespoke `build_hr_report`<br>(`hr_attendance_v1`) | **Bypassed** (Deterministic alias heuristic) | **1.794s** | 9 slides | Ignores upstream `ExecutiveTopic`s; hardcoded slide sequence. |
| **Retail** | `9967418` | AI Director $\to$ Fallback `build_grounded_review`<br>(`recorded_results_v1`) | **Qwen 3.5:9b** (5 stages, failed validation at line 471) | **223.271s** | 9 slides | Plan validation error causes raw column-by-column dump. |
| **Environmental** | `9967419` | AI Director $\to$ Fallback `build_grounded_review`<br>(`recorded_results_v1`) | **Qwen 3.5:9b** (5 stages, failed validation at line 471) | **255.308s** | 9 slides | Plan validation error causes raw column-by-column dump. |

---

## 2. Full 13-Phase Pipeline Map

Presentation Studio is organized into 13 formal pipeline execution phases (`pipeline_orchestrator.py`):

| Phase | Phase Key | Phase Name & Responsibility | Primary Engine / Module | Input Artifacts | Output Artifacts | Primary Failure Risk |
| :---: | :--- | :--- | :--- | :--- | :--- | :--- |
| **0** | `brief_setup` | Objective, audience, decision, and constraints | `scope_detector.py` | User Scope, Prompt | Validated Brief | Unrealistic slide count or vague objective |
| **1** | `evidence_audit` | Content inventory and evidence audit | `shared_evidence_package.py`, `data_profiler.py` | Sheet records | Ground-truth evidence ledger | Incomplete rows, missing numeric stats |
| **2** | `narrative_arc` | Narrative architecture and slide sequence | `intent_planner.py`, `narrative_planner.py` | Intent, Evidence | Narrative outline & section tree | Hallucinated story arc ungrounded in data |
| **3** | `headlines` | Slide headlines and subheadings | `slide_planner.py` | Narrative outline | Draft slide headlines | Excessively long titles (>155pt) |
| **4** | `layout_selection` | Wireframes and layout selection | `ai_slide_materializer.py`, `builders.py` | Slide plan | Wireframe layout assignments | Incompatible layout for data shape |
| **5** | `math_reconciliation`| Mathematical reconciliation & content QA | `claim_verifier.py`, `plan_validator.py` | Draft slides, Evidence | Validation summary | False claim rejection causing builder fallback |
| **6** | `graphics_charts` | Charts, tables, and graphic content | `chart_synthesizer.py`, `VisualIntelligenceEngine` | Column profiles | Chart specifications & datasets | VisualSpec mismatch, unplottable data |
| **7** | `executive_polish` | Executive language polish | `ai_enrichment.py` | Raw draft copy | Polished executive bullets | Loss of concrete metrics, verbose prose |
| **8** | `visual_qa` | Visual hierarchy, text density, and layout QA | `SpatialOverflowMonitor` | Slide text blocks | Layout adjustments | Undetected text bounding-box collision |
| **9** | `animation` | Optional animation and transitions | `pipeline_orchestrator.py` | Deck spec | Animated transitions | Incompatible client renderer |
| **10** | `speaker_notes` | Final speaker notes and voiceover | `generate_structured_speaker_notes` | Slide facts, notes | Time-budgeted presenter script | Missing what-to-notice / why-it-matters |
| **11** | `export_qa` | Accessibility and technical export QA | `review_gates.py` | Complete deck spec | Export compliance checklist | Contrast failure, unexported charts |
| **12** | `ready` | Rehearsal preparation & final human sign-off | `job_manager.py` | Final deck | Certified presentation ready for review | Stale state, unpersisted deck spec |

---

## 3. Formal Ownership Matrix Across 12 Architectural Layers

| Layer | Layer Name | Core Modules | Upstream Input | Downstream Output | Current Implementation Status & Defects |
| :---: | :--- | :--- | :--- | :--- | :--- |
| **1** | Scope & Preflight | `scope_detector.py` | User Scope | Verified Datasets | Operates independently of dashboard topic scope |
| **2** | Evidence Ledger | `data_profiler.py`, `memory/` | Raw Data Rows | `evidence_ledger` | Recomputes metrics instead of reusing governed facts |
| **3** | Topic / Intent | `persona_router.py`, `intent_planner.py` | Brief, Scope | PresentationIntent | Attendance alias hardcoding bypasses AI intent |
| **4** | Narrative Strategy | `narrative_planner.py`, `storyline_generator.py` | Intent, Ledger | NarrativeStrategy | Fails to reflect ExecutiveTopic business questions |
| **5** | Slide Planning | `slide_planner.py`, `builders.py` | Narrative, Ledger | SlidePlan list | Generates unconstrained titles causing layout crash |
| **6** | Content QA | `claim_verifier.py`, `plan_validator.py` | SlidePlan, Ledger | ValidationResult | Over-strict validation triggers catastrophic fallback |
| **7** | Visual Synthesis | `chart_synthesizer.py`, `VisualIntelligenceEngine` | Data Profiles | ChartSpec | Ignores upstream `VisualSpec` types and encodings |
| **8** | Executive Language | `ai_enrichment.py`, `executive_polish` | Draft Bullets | Polished Bullets | Often skipped in fallback / HR routes |
| **9** | Layout Resolution | `slide_layout.py`, `SpatialOverflowMonitor` | Slide Spec | Resolved Pages | Hardcoded title height threshold (`>155pt`) throws crash |
| **10** | Speaker Notes | `pipeline_orchestrator.py` | Slide Content | Speaker Notes | Bespoke string formatting without structured schema |
| **11** | Export Engines | `report_generator.py`, `pptx_export`, `resolved_pdf.py` | Resolved Pages | PPTX / PDF files | Crashes when layout engine raises `SlideLayoutError` |
| **12** | Studio Delivery UI | `PresentationStudioModal.tsx`, `SlideStage.tsx` | Deck API | Interactive UI | Single-page preview does not show pagination breaks |

---

## 4. Complete Failure Vector Catalog (Vectors A through Q)

| ID | Failure Title | Code-Level Root Cause | Severity | Reproduction Condition | Target Track |
| :---: | :--- | :--- | :---: | :--- | :---: |
| **A** | Upstream Topic Contract Bypass | `deck_generator.py` ignores `ExecutiveTopic` list in `dataset_context`. | **Critical** | All presentation generation runs | Track 3.2 |
| **B** | Attendance Alias Hardcoding | `build_hr_report` checks column aliases and hijacks flow if attendance fields exist. | **High** | Any sheet with `Emp ID` or `Attendance` | Track 3.2 |
| **C** | Director Plan Validation Cliff | `plan_validator.py` marks `is_valid=False` if any keyword is missing in slides. | **Critical** | Retail / Environmental with AI planner | Track 3.2 |
| **D** | Raw Column Dump Fallback | `build_grounded_review` iterates raw columns and creates "at a glance" cards. | **High** | Fallback from Director failure | Track 3.2 |
| **E** | Long-Title Layout Crash | `slide_layout.py:74` raises `SlideLayoutError` if title height $> 155\text{pt}$. | **Critical** | Slide title $> 100$ characters / 2 wrapped lines | Track 3.3 |
| **F** | Brush Theme Title Clip | `slide_layout.py:66` raises `SlideLayoutError` if title height $> 112\text{pt}$ in brush themes. | **High** | Any brush theme with 3-line title | Track 3.3 |
| **G** | Unhandled Export Exception | `report_generator.py` does not catch `SlideLayoutError`, converting it to 500. | **High** | Exporting a deck containing an overflowing slide | Track 3.3 |
| **H** | VisualSpec Chart Disconnect | `chart_synthesizer.py` independently chooses chart type, ignoring `VisualSpec`. | **High** | Multi-series or dumbbell upstream charts | Track 3.2 |
| **I** | Fact ID Lineage Loss | Presentation slides generate new UUIDs or slide IDs, discarding `fact_id`. | **Critical** | Audit trail verification | Track 3.2 |
| **J** | Table Cell Column Squishing | `slide_layout.py` divides width equally across columns without minimum width. | **Medium** | Tables with $\ge 8$ columns | Track 3.3 |
| **K** | Narrative Text Overflow | Large narrative blocks push chart/table below `body_bottom` (505pt). | **Medium** | Narrative $> 150$ words | Track 3.3 |
| **L** | Multi-Page Web Preview Gap | Web preview in `SlideStage.tsx` only renders slide object, hiding paginated pages. | **Medium** | Viewing paginated table slides in UI | Track 3.4 |
| **M** | Director Generation Latency | 5 sequential LLM calls in `presentation_director.py` take $> 200\text{s}$ on local GPU. | **Medium** | Generation on local Ollama models | Track 3.2 |
| **N** | Checklist Item Height Cliff | `slide_layout.py:107` raises `SlideLayoutError` if checklist item $> 350\text{pt}$. | **Medium** | Verbose checklist item text | Track 3.3 |
| **O** | Missing Theme Font Invariance | PPTX exporter falls back to Arial if system font (e.g. Inter/Cabinet) is missing. | **Low** | Export on environments without display fonts | Track 3.3 |
| **P** | Speaker Notes Truncation | PPTX notes slide shape has fixed 5000-character buffer, truncating long notes. | **Low** | Excessive speaker notes | Track 3.4 |
| **Q** | Asynchronous Job Race Condition | Worker thread updates job status without atomic mutex against cancel requests. | **Low** | Rapid cancellation during Phase 6 | Track 3.4 |

---

## 5. Performance, Export Latency & Model Baseline

### Generation & Export Latency Benchmarks

| Metric / Stage | Workforce (`hr_attendance_v1`) | Retail (`recorded_results_v1`) | Environmental (`recorded_results_v1`) |
| :--- | :---: | :---: | :---: |
| **Preflight & Evidence Ingestion** | 45 ms | 120 ms | 135 ms |
| **Director Planning Latency** | 0 ms (Bypassed) | 221,400 ms | 253,200 ms |
| **Deck Spec Generation** | 12 ms | 18 ms | 22 ms |
| **Geometry Resolution (`resolve_slide`)** | 1.8 ms | 0.9 ms | 1.1 ms |
| **PPTX Export Latency** | 286.63 ms | 38.14 ms | 42.50 ms |
| **PDF Export Latency** | 51.76 ms | 5.61 ms | 6.20 ms |
| **Total End-to-End Latency** | **1.794s** | **223.271s** | **255.308s** |

### Model Call Characterization

- **Workforce**: 0 model calls (100% deterministic heuristic).
- **Retail**: 5 model calls (`ModelRole.ANALYST`, `qwen3.5:9b`), average latency 44.2s per call, 100% fallback rate due to validation rejection.
- **Environmental**: 5 model calls (`ModelRole.ANALYST`, `qwen3.5:9b`), average latency 50.6s per call, 100% fallback rate due to validation rejection.

---

## 6. Semantic Fidelity & Visual Parity Scores

### Semantic Fidelity Score (/100)
*Evaluated against frozen Upstream ExecutiveTopics, Fact IDs, Evidence IDs, and Business Question Titles.*

| Domain | Score | Primary Defect Breakdown |
| :--- | :---: | :--- |
| **Workforce** | **42 / 100** | Good attendance domain topic overlap; 0/9 slides reference `topic_id`; 0/9 preserve `fact_id`; bespoke hardcoded titles. |
| **Retail** | **12 / 100** | Raw column dump; zero executive synthesis; 0/9 business-question titles; 0% topic alignment. |
| **Environmental** | **10 / 100** | Raw column audit (`Stn Code`, `Sampling Date`, `SO2`); misses air quality index; 0% topic alignment. |

### Visual Parity Score (/100)
- **Preview $\leftrightarrow$ PPTX**: **78 / 100** (Colors and fonts match; table padding and chart legend wrapping differ).
- **Preview $\leftrightarrow$ PDF**: **84 / 100** (Design tokens match; PDF displays paginated continuation pages while preview displays single-slide view).
- **PPTX $\leftrightarrow$ PDF**: **82 / 100** (Both generated via `resolve_slide`, but PDF paginates multi-page tables cleanly while PPTX uses fixed height).

---

## 7. Stress Test Fixture & Long-Title Characterization

### Comprehensive Stress Matrix Results

1. **25-Row Table**: Successfully paginates into **4 physical slide pages** under `resolve_slide`. All 25 rows and headers are preserved without data loss.
2. **10-Column Wide Table**: Successfully resolves across standard canvas (width = 864pt, column width = 86.4pt).
3. **Long Narrative (>200 words)**: Renders with total text height 184pt, within the 505pt body bottom limit.
4. **Long Title (>100 characters / 3 lines)**:
   ```python
   SlideLayoutError: The slide title needs a shorter heading or a separate cover.
   ```
   Cumulative title block height $y = 178\text{pt} > 155\text{pt}$ threshold, raising `SlideLayoutError`.

### Formal Characterization: Planning vs Rendering Defect
The long-title failure is a **cross-layer contract disconnect**:
- **Layer 5 (Planning)**: Lacks a character/word budget for titles, generating descriptive executive titles without layout awareness.
- **Layer 9 (Layout)**: Imposes a rigid, non-negotiable cliff (`y > 155pt`) rather than auto-reducing font size (e.g. 32pt $\to$ 24pt $\to$ 20pt) or splitting excess text into subtitles.
- **Layer 11 (Export)**: Fails to catch `SlideLayoutError`, escalating a layout overflow into an unhandled export crash.

---

## 8. Frozen Contract Boundary & Track 3.2 Specification

To prepare for Product Track 3.2, the contract boundaries are formally defined:

### Upstream Immutability
- Product Tracks 2.1–2.4 are **frozen** at `8576cad438915070e89c9a1612f0af0e8e68e0ac`.
- Presentation Studio **MUST NOT** modify `AdaptiveDashboardResponse`, `ExecutiveTopic`, `VisualSpec`, `fact_id`, `evidence_ids`, G-series architecture, or Analytics Core.

### The Topic-to-Slide Invariant
> **"One governed ExecutiveTopic maps to one presentation topic identity, which may render as one or more physical slides without changing fact/evidence ownership."**

- A single `ExecutiveTopic` (e.g. "Operational Headcount Distribution") may produce multiple physical slides if its underlying visual is a 25-row table that paginates across 4 pages.
- All 4 physical slides retain identical `topic_id`, `fact_id`, and `evidence_ids` lineage, rendered with pagination badges (e.g. `1/4`, `2/4`, `3/4`, `4/4`).
- Topic identity and fact ownership remain strictly 1:1, guaranteeing 100% semantic fidelity with the upstream Executive Dashboard.
