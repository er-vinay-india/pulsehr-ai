# Layer 4: Visual Grammar & Spatial Contract

> **Parent:** [README.md](../../README.md) &rsaquo; [System Architecture](../system-architecture.md) &rsaquo; **Layer 4**

---

## 1. Architectural Mission: Spatial & Visual Invariants

Layer 4 governs the visual presentation layer across all rendering surfaces (React browser components, headless PDF exporter, and native Microsoft PowerPoint decks). It enforces strict WCAG AAA contrast standards, an immutable 16:9 spatial layout contract, a cohesive typography scale, and a **truthful visual intent grammar** where chart types strictly mirror analytical intent.

```mermaid
flowchart TD
    DeckSpec[Layer 3 Deck & Dashboard Specs] --> Layout[1. 16:9 Baseline Geometry 960x540]
    Layout --> Tokens[2. HighView Design Tokens _tokens.scss]
    Tokens --> Type[3. Standardized Typography Scale]
    Type --> VisualGrammar[4. Truthful Visual Intent Grammar & ECharts]
    VisualGrammar --> TableGuard[5. Dense Table Wrapping & Continuation]
    TableGuard --> Target1[React Web Studio & Dashboard]
    TableGuard --> Target2[Native Python-PPTX Exporter]
    TableGuard --> Target3[Headless Chrome PDF Exporter]
```

---

## 2. Core Subsystems & Codebase Proof

### A. HighView Design Tokens (`frontend/src/styles/_tokens.scss`)
Defined canonically in SCSS; JavaScript chart tokens and presentation themes inherit directly from this file:
- **Palette Identity**: Calm navy, emerald, and warm neutral surfaces.
- **Accessibility Standard**: Text tokens target &ge; 7:1 contrast ratio across semantic surfaces (WCAG AAA).
- **Theme Validation**: Verified via `npm run test:theme` in `frontend/`.

| Token Variable | Light Mode (`:root`) | Dark Mode (`[data-theme="dark"]`) | Semantic Usage |
| :--- | :---: | :---: | :--- |
| `--color-bg-page` | `#F6F5F0` | `#101B27` | Canvas and viewport background |
| `--color-bg-surface` | `#FFFFFF` | `#172635` | Card panels, slide canvas, modal dialogs |
| `--color-bg-elevated` | `#FFFFFF` | `#203445` | Dropdowns, popovers, floating menus |
| `--color-bg-subtle` | `#EEEFE9` | `#1C2E3E` | Table header fills, neutral badges |
| `--color-text-primary` | `#172B3A` | `#F4F5EF` | Headings, table cells, active labels |
| `--color-text-secondary`| `#334B57` | `#D3DED9` | Subtitles, field labels, metadata notes |
| `--color-text-muted` | `#3C5059` | `#BDCBC5` | Timestamp notes, inactive captions |
| `--color-brand-primary` | `#183B56` | `#A9CAE8` | HighView brand navy; primary navigation |
| `--color-brand-secondary`| `#075443`| `#82D9B5` | Emerald action buttons, active focus |
| `--color-border` | `#D4DDD6` | `#3B4E5A` | Standard structural borders & dividers |
| `--color-border-strong` | `#78877F` | `#82968F` | Form input borders, high-contrast boundaries |
| `--color-success` | `#075443` | `#82D9B5` | Positive indicators, healthy benchmarks |
| `--color-warning` | `#65470C` | `#E8C675` | Restrained gold; caution & moderate volatility |
| `--color-error` | `#8E1938` | `#FFB3C0` | Deep crimson; critical headwinds, high turnover |

### B. Truthful Visual Intent Grammar & ECharts Renderers
Implemented in `backend/app/services/adaptive_dashboard/composition_planner.py`, `visual_portfolio_optimizer.py`, and `frontend/src/components/adaptive/VisualSpecRenderer.jsx`:
1. **`RELATIONSHIP` Intent &rarr; True Scatter Plots**:
   - Correlation and bivariate measures render as native **ECharts scatter plots**.
   - Plotted coordinates: $X$-axis = measure 1, $Y$-axis = measure 2.
   - Point metadata: Carries entity identifier (e.g. city name) into interactive tooltips.
   - Strictly replaces legacy synthetic categorical bar charts. Gate: requires 2 continuous numeric measures and $N \ge 3$ points.
2. **`DISTRIBUTION` Intent &rarr; Five-Number Summary Box Plots**:
   - Renders median, upper/lower quartiles (Q1, Q3), and min/max whiskers.
   - Gate: requires numeric measure with $\ge 5$ observations (prefers $\ge 10$).
3. **`RANKING` Intent &rarr; Directional Bar Charts & Podium Top 3**:
   - Ranked horizontal bars with polarity-aware color rendering (`HIGHER_IS_BETTER` vs `LOWER_IS_BETTER`) and benchmark reference lines (e.g. NAAQS statutory $60\ \mu\text{g/m}^3$ annual standard).
   - Olympic Podium (`podium_top_3`): Gold (#1), Silver (#2), and Bronze (#3) pedestals with medal badges. Strict label truncation ($\le 20$ chars, $\le 2$ lines, full label in hover tooltip).
4. **`TARGET_VS_ACTUAL` Intent &rarr; Bullet Charts**:
   - Horizontal performance bars with benchmark threshold indicators and gap badges.
5. **`COMPARISON` Intent &rarr; Lollipop & Dumbbell Charts**:
   - Lollipops for clean entity-level measure comparisons without heavy ink.
   - Dumbbells for pairwise disparity spreads (e.g. SO2 vs NO2 gap across urban centers).
6. **`COMPOSITION` Intent &rarr; 100% Stacked Bars & Treemaps**:
   - Capacity breakdown across categorical cohorts or multi-sheet reconciliation.
7. **`ANOMALY` / `OUTLIER` Intent &rarr; Variance Bars**:
   - Diverging or baseline-anchored variance bars highlighting statistical outlier distance.
8. **`TemporalLabelIntegrity`**:
   - Synthetic time labels (`Week 1...5`, `Month 1...`, `Quarter 1...`) are permanently banned when the source table lacks a true `temporal_point` column. Line/trend charts are only permitted when genuine temporal dimensions exist.

### C. Unified 16:9 Spatial Baseline
Implemented in `backend/app/services/presentation/slide_layout.py`, `resolved_slides.scss`, and `resolved_pdf.py`:
- **Baseline Resolution**: `960 × 540 pt` (scaled $2\times$ to `1920 × 1080 px` for high-DPI displays).
- **Usable Content Area**: `864 pt` width ($48\mathrm{pt}$ left/right margins), `460 pt` height ($40\mathrm{pt}$ top header, $40\mathrm{pt}$ footer).
- **Full-Width Hero Reclamation**: Text and cover layouts reclaim the full 864 pt width; side metrics only allocate space when explicitly present.

### D. Standardized Typography Hierarchy

| Element | Size | Weight | Line Height | Usage Target |
| :--- | :---: | :---: | :---: | :--- |
| **Cover Title** | `38 pt` | Bold (700) | `1.15` | Hero title on deck cover slide |
| **Slide Header** | `30 pt` | Bold (700) | `1.20` | Main slide title across all interior slides |
| **Panel Title** | `20 pt` | Semi-bold (600) | `1.30` | Section headings, KPI card titles |
| **Body Narrative** | `18 pt` | Regular (400) | `1.40` | Strategic takeaway paragraphs, bullet points |
| **Table Cells** | `16 pt` | Regular (400) | `1.22` | Structured data table rows |
| **Chart Labels** | `14 pt` | Medium (500) | `1.20` | Category axis labels, legend keys, datalabels |
| **Footnotes & Provenance** | `11 pt` | Regular (400) | `1.20` | `EVID-XXX` evidence citations & source labels |

### E. Dense Table Protection & Overflow Handling
Implemented in `backend/app/services/presentation/slide_layout.py` and `resolved-slides.scss`:
1. **Weighted Column Widths**: Allocated based on semantic content types (compact for IDs, currencies, dates; wide for strings).
2. **Multi-Page Continuation**: Tables exceeding the 460 pt content boundary generate continuation slides with repeated column headers.
3. **Hard Row Safety**: Single rows exceeding maximum allowable height fail gracefully with actionable diagnostics rather than clipping off-slide.

### F. Native Multi-Format Exporters
- **Native PowerPoint (`python-pptx`)**: Generates real editable shape tables and native vector chart objects—never low-resolution screenshots.
- **Executive PDF (`resolved_pdf.py`)**: Headless browser render enforcing identical 960×540 pt geometry and print CSS rules.
- **Interactive Web Studio (`FrontendSlidesDeck.jsx`, `DeckStudioView.jsx`)**: Responsive slider navigation, live conversational slide mutation with rollback, and speaker notes drawer.

### G. Executive Visual Diversity & Density Engine (8–15 Visual Envelope)
Implemented in `backend/app/services/adaptive_dashboard/visual_portfolio_optimizer.py`, `composition_planner.py`, and `frontend/src/styles/executive-cockpit.scss`:

1. **Dashboard Visual Budget Contract (`DashboardVisualBudget`)**:
   ```python
   min_visuals: int = 8
   target_visuals: int = 10
   max_visuals: int = 15
   max_same_intent: int = 3
   max_same_family: int = 2
   max_same_morphology: int = 2   # Strictly caps same geometric visual structure
   min_distinct_morphologies: int = 5
   min_distinct_families: int = 5
   min_distinct_intents: int = 4
   ```
2. **Visual Morphology Classification (`VisualMorphology`)**:
   Prevents length-based bar chart perceptual monotony across the dashboard:
   - `LENGTH`: `ranked_bar`, `horizontal_bar`, `bullet`, `waterfall`, `variance_bar`
   - `POINT`: `lollipop`, `scatter`, `dot_plot`
   - `RANGE`: `dumbbell`, `range_plot`
   - `AREA`: `100_percent_stacked_bar`, `stacked_bar`, `donut`, `pie`
   - `TEMPORAL_PATH`: `line`, `area`, `slope` (gated by real temporal dimension)
   - `MATRIX`: `heatmap` (2D categorical cross-tabulation)
   - `DISTRIBUTION`: `box_plot`, `histogram`
   - `ICONIC`: `podium_top_3`
   - `HIERARCHICAL`: `treemap`, `dendrogram`
   - `FLOW`: `sankey`
3. **Multi-Factor Portfolio Optimization**:
   The optimizer ranks candidate stories using a balanced utility score:
   $$\text{Score} = w_{\text{bus}} \cdot \text{business\_value} + w_{\text{imp}} \cdot \text{importance} + w_{\text{conf}} \cdot \text{confidence} + w_{\text{dec}} \cdot \text{domain\_decision\_value} + \text{Bonuses} - \text{Penalties}$$
   - **Bonuses**: `new_morphology_bonus` (+0.40), `new_intent_bonus` (+0.25), `new_family_bonus` (+0.20), `hero_anchor_bonus` (+0.15).
   - **Penalties**: `same_morphology_penalty` (-0.25), `same_family_penalty` (-0.30), `same_intent_penalty` (-0.20), `redundancy_penalty` (-0.50).
4. **Semantic Visual Compression Layer (`SemanticVisualCompressionLayer`)**:
   Transforms Level-1 cards into high-density, minimal-chrome decision surfaces:
   - `short_title`: $\le 7$ words (executive noun phrase).
   - `short_context`: $\le 8$ words (cohort context & scope).
   - `short_finding`: $\le 12$ words (single clear takeaway sentence).
   - `cta`: $\le 3$ words (e.g. "Inspect →").
   - `SemanticIconRegistry`: Deterministic SVG icons (`target`, `trophy`, `users`, `calendar`, `alert`, `trend`, `distribution`, `compare`, `relationship`, `shield`, `matrix`, `wind`).
   - **Reduced Card Chrome**: Never permanently renders `recommended_action` inside Level-1 cards. Visual area takes > 85% of card space. Full business questions, unabridged explanations, recommended action steps, and evidence citations live inside the Quick Inspect Drawer and Data Explorer.
5. **Responsive 12-Column Spatial Grid & Semantic Landmarks**:
   - `HERO` (`layout-hint-hero`, `visual-card--hero`): `span 12` (full row prominence).
   - `LARGE` (`layout-hint-large`, `visual-card--large`): `span 12`.
   - `MEDIUM` (`layout-hint-medium`, `visual-card--medium`): `span 6` (half width on desktop).
   - `COMPACT` (`layout-hint-compact`, `visual-card--compact`): `span 4` (1/3 width on desktop).
   - `MICRO` (`layout-hint-micro`, `visual-card--micro`): `span 3` (1/4 width on desktop).
   - **CSS Grid vs Flexbox Boundary**: CSS Grid exclusively governs page sections and visual card portfolios (`ExecutiveVisualGrid`). Flexbox exclusively governs component internals (card headers, metric wrappers, button groups).
   - **DOM Order Equals Reading Order**: DOM elements are rendered in strict order of analytical importance (Priority &rarr; Diagnostic &rarr; Supporting). CSS `order:` properties are permanently barred.
   - **Breakpoints**:
     - Desktop ($\ge 1025\mathrm{px}$): Full multi-column grid density.
     - Tablet ($\le 1024\mathrm{px}$): Compact and micro cards collapse to `span 6`.
     - Mobile ($\le 768\mathrm{px}$): All cards collapse to `span 1` (single column 100% width) with zero horizontal clipping or overflow.
