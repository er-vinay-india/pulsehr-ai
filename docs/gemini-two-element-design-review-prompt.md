# Design Review & Execution Prompt — Multi-Disciplinary Critique of the First Two Adaptive Dashboard Elements

**Review Date**: September 25, 2026
**Project**: `/Users/vinayksharma/Developer/pulsehr-ai`
**Review Target**: Adaptive Decision Dashboard (`http://localhost:5175/#adaptive`)
**Datasets Evaluated**:
1. Commercial / Retail Dataset: Sheet 64 (`Walmart Weekly Sales`, 6,435 rows across 45 stores, 2010–2012)
2. Workforce / Attendance Dataset: Sheet 63 (Wide attendance matrix with clock intervals across 100 employees)

---

## 1. Cross-Functional Design Team Roster & Independent Evaluations

### 1.1 UX Researcher (User Mental Models & Decision Clarity)
- **Primary Tile**: Users immediately grasp the dominant `$6.74B` headline number and the `Across 45 stores · 2010–2012` context. It prevents misinterpretation of multi-year cumulative totals as single-year figures.
- **Secondary Chart**: The middle 80% distribution band ($P_{10}–P_{90}$) provides vital context that an average alone conceals. Users understand that store performance varies widely ($442K to $2.02M) even though the national monthly average is steady around $1.05M.
- **Key Friction**: In the Inspect modal, scrolling through 33 monthly observation rows causes users to lose track of column headers. Sticky table headers are essential.

### 1.2 UX Writer (Microcopy, Clarity & Voice)
- **Title Row & Caption**: The caption in the chart card previously generated `"Monthly average Weekly Sales with middle 80% distribution band..."`. The capitalized column name `"Weekly Sales"` looked like an unformatted database field. It must be formatted naturally in sentence case (`"weekly sales"`).
- **Audit Button Affordance**: Button `aria-label` should say `"View calculation and source audit for Total sales"` rather than generic `"About Total sales"`.
- **Persona Badge Copy**: The persona badge (`● Retail Sales Data Analyst`) gives clear reassurance of the AI's analytical lens, but needs an explicit tooltip/title explaining its role: `"AI analytical lens calibrated for retail store sales and revenue metrics"`.

### 1.3 Content Strategist (Information Hierarchy & Vocabulary Governance)
- **Domain Decoupling**: Approved the elimination of "Workforce coverage" on retail data.
- **Hierarchy of Metadata**: The chart card header was attempting to display title, qualifier pill, terminal pill, caption, legend, and info button all at once. The qualifier (`Per store-week · Monthly`) should be prominent near the title, while technical sample details (`Based on 6,435 valid records...`) should sit gracefully in secondary metadata or details to avoid visual noise.

### 1.4 Interaction Designer (Touch Ergonomics, Modals & States)
- **Touch Target Compliance**: Mobile buttons (`.glance-info-btn`) must maintain a minimum 40x40px (preferably 44x44px) tap target to comply with Apple HIG and WCAG 2.5.5.
- **Crosshair / Pointer Feedback**: In the ECharts line chart, adding an axis pointer (subtle vertical line) on hover grounds the user's cursor to the exact month across both the line and the distribution band.
- **Modal Keyboard Dismissal**: ESC key dismisses the modal and restores focus smoothly to the trigger button. Retain this behavior.

### 1.5 Information Architect (Taxonomy & Progressive Disclosure)
- **Three-Layer Disclosure Model**:
  - *Layer 1 (Glance)*: Dominant number + concise qualifier + trend line + distribution area.
  - *Layer 2 (Explain)*: Instant hover/focus preview with exact definitions.
  - *Layer 3 (Inspect)*: Audited evidence dialog with exact values, math formulas, completeness metrics, and the full monthly distribution table.
- **Taxonomy Continuity**: Ensure that when switching between different sheets, the semantic hierarchy remains uniform across commercial, workforce, census, and personal finance datasets.

### 1.6 Product Designer (Executive Scannability & Aesthetic Utility)
- **Visual Rhythm**: Card 1 (KPI) and Card 2 (Chart) currently look like two distinct cards. The vertical spacing between them (20px) is clean.
- **Color Discipline**: The dark theme (`#12100e` background, `#1c1815` card surface, `#ffb089` primary coral line, `rgba(255, 176, 137, 0.16)` band fill) looks executive and understated. Avoid adding bright saturated colors.

### 1.7 Design Systems Designer (Tokens, Spacing & Theming)
- **Grid & Tokens**: Align all padding to the 4px/8px modular grid (`8px`, `12px`, `16px`, `20px`, `24px`).
- **Contrast Ratios**: Check that tick labels (`#c9bdb0` on `#1c1815`) exceed WCAG AA 4.5:1 contrast for 11px/12px text.
- **Border Radii**: Standardize cards to `8px` and pills/badges to `6px` or `20px` pill-capsules consistently.

### 1.8 UX Engineer (Accessibility, ARIA & Performance)
- **Chart Screen Reader Experience**: The chart canvas has `role="img"` and dynamic `aria-label`. We should ensure the `aria-label` summarizes the overall finding (e.g. *"Monthly chart of average weekly sales from Feb 2010 to Oct 2012. Monthly averages stayed around $1.05M with middle 80% store sales ranging from $442K to $2.02M."*).
- **Table Accessibility**: In the Inspect modal, table headers must have `scope="col"`, and row headers must have `scope="row"` with bold period labels.
- **Reduced Motion**: Verify that charts load with `animation: false` or respect `prefers-reduced-motion`.

### 1.9 UI Developer (CSS Architecture & Canvas Robustness)
- **Y-Axis Margin Safety**: On large currency values (`$3.0M`), ensure grid `left: 64` or dynamic calculation to prevent any digit truncation on narrow screens.
- **Flexbox & Overflow**: Prevent unwanted horizontal scrollbars by enforcing `overflow-x: hidden` on cards and `overflow-x: auto` strictly inside the Inspect data table container.

### 1.10 Design Manager (Delivery Gate & Scope Control)
- **Scope Invariants**:
  - Exactly TWO elements delivered (Primary KPI Card + Secondary Trend Chart).
  - Do NOT introduce a 3rd element without user review and sign-off.
  - Retain 100% backward compatibility for the approved attendance sheet (Sheet 63).

### 1.11 Design Director (Executive Design Vision & Strategic Integrity)
- **Defensibility Above All**: An adaptive dashboard must look and feel like a seasoned analyst prepared it.
- **Persona Context**: The persona badge (`● Retail Sales Data Analyst`) validates why the numbers make sense. Keep this front-and-center.
- **Actionable Verdict**: Implement the team's top consensus refinements immediately.

---

## 2. Consolidated Team Action Items (Prioritized for Execution)

1. **Copy Polish (UX Writer & Content Strategist)**:
   - Fix caption text in `engine.py` to ensure measure names are formatted naturally in sentence case (`"weekly sales"`, `"revenue"` instead of raw column identifiers like `"Weekly Sales"`).
   - Enhance the persona badge with an explanatory title/tooltip attribute explaining the analyst persona.
   - Refine button accessibility labels to clearly state `"View calculation and source audit for [Metric]"`.

2. **Visual & Interaction Refinement (Interaction Designer & Systems Designer)**:
   - Add ECharts `axisPointer: { type: "line", lineStyle: { color: "rgba(255, 176, 137, 0.3)", width: 1, type: "dashed" } }` on tooltip hover to ground cursor position.
   - Increase chart grid left margin from `58` to `66` to ensure large currency labels like `$3.0M` and `$2.5M` have ample breathing room.
   - Ensure mobile tap targets for info triggers meet 40px minimum.

3. **Inspect Modal Enhancements (UX Researcher & UI Developer)**:
   - Add `position: sticky; top: 0;` with background `#1c1815` to the Inspect modal table header (`<thead>`) so column headers remain visible while scrolling 33+ months.
   - Format row header cells with `scope="row"`.

4. **Preservation & Verification Gate**:
   - Verify that Sheet 63 (Attendance) and Sheet 64 (Sales) both pass all automated tests and render cleanly.
