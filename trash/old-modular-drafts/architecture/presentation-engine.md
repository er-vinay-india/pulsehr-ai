# Presentation Engine Architecture

> **Parent:** [README.md](../../README.md) &rsaquo; [Architecture](system-overview.md)

## 1. Automated 13-Phase Pipeline (`PIPELINE_PHASES`)

Presentation generation is managed by `backend/app/services/presentation/pipeline_orchestrator.py` through 13 discrete phases:

| Phase # | Phase Key | Description / Purpose |
| :---: | :--- | :--- |
| **0** | `brief_setup` | Sets objective, target audience, decision scope, and constraints. |
| **1** | `evidence_audit` | Content inventory and evidence validation against source dataset. |
| **2** | `narrative_arc` | Establishes strategic narrative architecture and slide sequencing. |
| **3** | `headlines` | Formulates executive slide headlines and descriptive subheadings. |
| **4** | `layout_selection` | Selects wireframe layouts based on data density (`chart_narrative`, `kpi_summary`, etc.). |
| **5** | `math_reconciliation` | Reconciles numbers, metrics, and denominators against the evidence store. |
| **6** | `graphics_charts` | Synthesizes native chart models, series data, and structured tables. |
| **7** | `executive_polish` | Polishes executive phrasing via the `WRITER` model role. |
| **8** | `visual_qa` | Evaluates contrast, padding, visual balance, and layout density (`SpatialOverflowMonitor`). |
| **9** | `animation` | Configures optional subtle slide transitions and entrance animations. |
| **10** | `speaker_notes` | Generates 5-part structured presenter briefing notes for rehearsal. |
| **11** | `export_qa` | WCAG contrast audit, table overflow checks, and export formatting. |
| **12** | `ready` | Final deck persistence, memory indexing, and human rehearsal readiness. |

---

## 2. Structured Speaker Notes Contract

Every generated slide includes structured speaker notes computed by `generate_structured_speaker_notes()`:

1. **WHAT TO NOTICE**: Key title focus and highlighted KPI metric values.
2. **WHY IT MATTERS**: Strategic executive implications and operational context.
3. **SUPPORTING EVIDENCE**: Source sheet provenance, `EVID-XXX` citations, and known data limitations.
4. **TIME BUDGET**: Estimated delivery seconds compared against total presentation time target.
5. **TRANSITION**: Logical bridge narrative connecting to the next slide.

---

## 3. Supported Slide Layout Primitives

| Layout Key | Structure | Best Used For |
| :--- | :--- | :--- |
| `title_hero` | Full-width title, metadata tags, narrative block | Deck cover slide, major section dividers |
| `kpi_summary` | 3 or 4 metric cards with labels, deltas, and trends | Executive overview, headline organizational metrics |
| `full_chart_takeaway` | Full-width high-resolution chart + takeaway callout | Longitudinal trendlines, macroeconomic trajectories |
| `chart_narrative` | 66% visual chart (col-8) + 33% strategic facts panel (col-4) | Core departmental deep-dives, burnout strain |
| `comparison_split` | 50/50 paired cards with comparative metrics | 9-Box talent matrix, Strengths vs Headwinds |
| `table_detail` | Multi-column structured data table with paging | Distribution profiles, cryptographic audit ledgers |
| `action_plan` | 3 prioritized initiatives with owners and timelines | Strategic roadmap, executive recommendations |

---

## 4. Multi-Model Presentation Pipeline Roles

Configured in `backend/app/core/config.py`:
- **Orchestrator**: `granite4:3b-h` (fallback: `granite4:3b`)
- **Analytical Engine**: `phi4-mini:latest`
- **Deep Reasoning**: `deepseek-r1:7b`
- **Visual QA Critic**: `gemma4:12b`
- **Chart Engine**: `echarts` + native `python-pptx` chart objects
