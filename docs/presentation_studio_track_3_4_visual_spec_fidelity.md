# Presentation Studio Track 3.4: VisualSpec-to-Presentation Visual Translation & Chart Fidelity

**Status**: 100% Complete & Certified  
**Baseline**: Track 3.1 (Audit), Track 3.2 (Contract Binding), Track 3.3 (Spatial Contract) Frozen  
**Core Invariant**: Visual representation may adapt to presentation geometry; analytical meaning may not.

---

## 1. Executive Summary

Product Track 3.4 establishes a deterministic, mathematically invariant translation pipeline from upstream governed `VisualSpec` analytics to high-fidelity presentation visual specifications across all three Presentation Studio consumers:
1. **Interactive Web Studio** (`ECharts` via `SlideChart.jsx`)
2. **Native Editable PowerPoint** (`python-pptx` with Office Open XML drawingML)
3. **High-DPI PDF Documents** (`ReportLab` vector graphics via `resolved_pdf.py`)

### What Track 3.4 Closed
- **Cross-Renderer Semantic Disconnect**: Previously, Studio, PPTX, and PDF rendered charts with differing series counts, axis bounds, and label handling. Track 3.4 enforces identical `PresentationVisualSpec` and `visual_semantic_fingerprint` parity across all 3 rendering consumers.
- **Reference Line & Benchmark Invariance**: Static dashed reference lines and leader callouts are now natively plotted across Studio (`markLine`), PPTX (native shape overlay with auto-scaled coordinate alignment), and PDF (ReportLab dashed paths with callout text badges).
- **Missing Chart Families**: Implemented native PPTX and PDF rendering for `XY_SCATTER`, `BAR_STACKED`, and `COLUMN_STACKED`, expanding native editability without image fallbacks.
- **Office Open XML Compliance**: Verified that all chart axis IDs (`axId`, `crossAx`) strictly comply with signed 32-bit XML bounds (`0 <= val < 2^31 - 1`) and number formatting (`<c:numFmt>`) is scoped exclusively to value axes, completely eliminating PowerPoint `-9074` XML corruption repair alerts.
- **Zero Model Calls**: Visual translation across all 13 chart families requires **0 model calls**, executing deterministically in `< 1ms` per visual and `< 25ms` for an entire presentation deck.

---

## 2. Presentation Chart Capability Registry

The `CHART_CAPABILITY_REGISTRY` serves as the authoritative single source of truth for visual rendering capabilities across Presentation Studio. It classifies visuals into 13 formal analytical visual families:

| VisualFamily | Web Studio (ECharts) | Native PPTX (python-pptx) | Document PDF (ReportLab) | Native Editable | Ref Line Support | Data Label Support | Multi-Series |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| `RANKED_BAR` | Horizontal bar with rank badges | Native `BAR_CLUSTERED` (inverted) | Horizontal canvas rects + gutter | **Yes** | Yes | Yes | No |
| `HORIZONTAL_BAR`| Clustered horizontal bars | Native `BAR_CLUSTERED` | Clustered horizontal rects | **Yes** | Yes | Yes | Yes |
| `BAR` | Vertical column chart | Native `COLUMN_CLUSTERED` | High-DPI vertical canvas rects | **Yes** | Yes | Yes | Yes |
| `GROUPED_BAR` | Multi-series clustered columns | Native `COLUMN_CLUSTERED` multi-series | Offset clustered rects with legend | **Yes** | Yes | Yes | Yes |
| `STACKED_BAR` | Stacked bars (`stack: 'total'`) | Native `BAR_STACKED` / `COLUMN_STACKED`| Cumulative stacked rect segments | **Yes** | Yes | Yes | Yes |
| `LINE` | Multi-series connected polyline | Native `LINE_MARKERS` | Anti-aliased canvas polyline path | **Yes** | Yes | Yes | Yes |
| `TREND` | Time-series line with area fill | Native `LINE_MARKERS` | Vector polyline with gradient area | **Yes** | Yes | Yes | Yes |
| `SCATTER` | XY coordinate scatter with grid | Native `XY_SCATTER` (`XyChartData`) | Canvas point markers at $(X_i, Y_i)$ | **Yes** | Yes | Yes | Yes |
| `CORRELATION` | Paired coordinate scatter | Native `XY_SCATTER` (`XyChartData`) | Canvas point markers + trendline | **Yes** | Yes | Yes | Yes |
| `PIE` | Proportional radial pie slices | Native `PIE` with percent callouts | Trigonometric vector pie wedges | **Yes** | No | Yes | No |
| `DONUT` | Radial ring with center metric | Native `DOUGHNUT` | Trigonometric donut rings + hole | **Yes** | No | Yes | No |
| `KPI_CARD` | Large-type stat hero badge | Native styled shape container | Padded card border + stat layout | **Yes** | Yes | Yes | No |
| `DATA_TABLE` | High-density grid table | Native PowerPoint table shape | ReportLab Platypus `Table` grid | **Yes** | No | Yes | Yes |

---

## 3. Visual Semantic Invariance & Fingerprinting

Visual representations may change geometry, margins, font sizes, and layout orientation depending on whether the output is a web viewport, a 16:9 PowerPoint slide, or an A4/Letter PDF document. However, **analytical meaning may never change**.

### Protected Semantic Fields
Under `PresentationVisualSpec`, the following 11 analytical attributes are mathematically frozen:
1. `analytical_intent`: High-level business inquiry (`RANKING`, `COMPARISON`, `TREND`, `COMPOSITION`, `CORRELATION`, etc.)
2. `metric`: Key quantitative measure name
3. `dimension`: Categorical slice attribute
4. `grain`: Granularity of the observation
5. `categories`: Exact category labels in identical sequential order
6. `series_values`: Exact numerical values preserved to 6 significant digits
7. `series_identity`: Named series structure and color roles
8. `ranking_direction`: Upstream sorting direction (`ASC` / `DESC`)
9. `reference_line`: Quantitative threshold, benchmark, or goal
10. `leader` & `leader_value`: Dominant entity and verified value
11. `unit`: Scale of measure (`%`, `days`, `USD`, `ppm`, `µg/m³`, etc.)

### Visual Semantic Fingerprint (`compute_visual_semantic_fingerprint`)
Every `PresentationVisualSpec` and presentation slide contract carries an SHA-256 fingerprint calculated over canonical analytical values, stripping all presentation-specific styling (such as colors, padding, font size, and canvas coordinates):

$$\text{Fingerprint} = \text{SHA-256}\Big(\text{JSON}_{\text{canonical}}\big(\text{morphology}, \text{intent}, \text{metric}, \text{unit}, \text{grain}, \text{categories}, \text{series}, \text{ref\_line}, \text{leader}, \text{binding}\big)\Big)$$

---

## 4. Multi-Consumer Render Manifest Parity

To prevent divergent visual interpretations across output formats, `PresentationVisualSpec.build_render_manifest(consumer)` generates a standardized manifest for the rendering adapter:

```json
{
  "consumer": "canonical",
  "chart_type": "bar",
  "categories": ["Operations", "Engineering", "Functions", "Design"],
  "series_names": ["Attendance Rate"],
  "series_values": [["88.5", "84.2", "79.1", "72.4"]],
  "unit": "%",
  "reference_line": "80",
  "leader": "Operations",
  "leader_value": "88.5"
}
```

The test suite (`test_three_consumer_cross_manifest_parity`) asserts that across all benchmark datasets:
$$\text{Manifest}_{\text{Studio}} \equiv \text{Manifest}_{\text{PPTX}} \equiv \text{Manifest}_{\text{PDF}} \equiv \text{Manifest}_{\text{Canonical}}$$
- Categories match in exact identity and order.
- Series names, values, and units match to 6 significant figures.
- Reference lines and leaders match upstream governance facts.
- **Zero phantom series and zero dropped data points**.

---

## 5. Reference Lines and Leader Annotations

### Native PowerPoint Reference Line Overlay
Because python-pptx charts do not feature a built-in horizontal/vertical threshold line primitive, Track 3.4 implements a native shape overlay calculation in `backend/app/services/pptx/pptx_charts.py`:
1. **Value Axis Auto-scaling**: Evaluates $\max(\text{values}, \text{reference\_line})$ to compute appropriate `maximum_scale`.
2. **Geometric Interpolation**: Calculates the exact coordinate on the chart plot area:
   $$y_{\text{line}} = y_{\text{plot\_bottom}} - \left(\frac{\text{ref\_value} - \text{axis\_min}}{\text{axis\_max} - \text{axis\_min}}\right) \times h_{\text{plot}}$$
3. **Connector Line**: Inserts a native `MSO_CONNECTOR.STRAIGHT` line styled with dashed lines (`dash_style = MSO_LINE_DASH_STYLE.DASH`).
4. **Callout Badge**: Places a high-contrast text label above the line indicating `Target: {value}`.

### ReportLab PDF Reference Line Overlay
In `backend/app/services/presentation/resolved_pdf.py`:
1. Value axis bounds expand to encompass the reference value: $\text{v\_max} = \max(\text{values}, \text{ref\_val}) \times 1.15$.
2. Dashed vector path drawn via `canvas.setDash([4, 3])` at the computed canvas coordinate.
3. Callout text badge positioned with `drawRightString` or `drawString` in secondary accent color.

### ECharts Studio Reference Line
In `frontend/src/components/presentation/slides/SlideChart.jsx`:
- Vertical charts (Bar, Column, Line) use `yAxis: reference_line`.
- Horizontal bar charts use `xAxis: reference_line`.
- Rendered using ECharts native `markLine` with `type: 'dashed'` and styled label formatters.

---

## 6. Native PowerPoint Editability & Headless Roundtrip

Track 3.4 enforces that slides containing charts export as native, fully editable Microsoft Office shapes (`has_chart == True`), rather than flattened bitmap screenshots.

### Test Results (`test_native_powerpoint_editability_and_roundtrip`)
Across all benchmark presentations (Workforce, Retail, Environmental):
- **Native Editability Ratio**: **$100\%$** (Exceeds the $\ge 85\%$ threshold; 7/7 visual slides contain native OOXML charts).
- **axId XML Compliance**: $100\%$ compliant. Every `<c:axId>` and `<c:crossAx>` is normalized to $< 2^{31} - 1$, preventing 64-bit integer overflow.
- **Number Format Scoping**: Category string axes (`<c:catAx>`) are strictly stripped of `<c:numFmt>`, preventing Office schema validation halts.
- **Headless PowerPoint Roundtrip**: Executed via AppleScript on macOS (`Microsoft PowerPoint.app`). Presentations open cleanly and export to PDF without any repair prompt dialogs (`code == 0`).

---

## 7. Number Formatting Contract

The centralized number formatting contract (`format_presentation_number`) provides deterministic string representations across all renderers while preserving numerical value:

| Format Type | Raw Input | Formatted Output | Unit Policy |
| :--- | :--- | :--- | :--- |
| `PERCENTAGE` | `88.5` | `88.5%` | Appends `%` symbol |
| `PERCENTAGE` (ratio) | `0.885` | `88.5%` | Automatically scales by 100 |
| `CURRENCY` | `1500000` | `$1.5M` | Compares scale ($K, M, B) |
| `LARGE_INTEGER` | `142500` | `142,500` | Thousand separators |
| `DECIMAL` | `12.3456` | `12.35` | 2 decimal places |
| `TIME_DAYS` | `4.2` | `4.2 days` | Appends temporal unit |
| `SCIENTIFIC` | `0.0000125` | `1.25e-05` | Standard scientific format |
| `ENVIRONMENTAL` | `54.2` | `54.2 µg/m³` | Preserves micro-units and superscripts |

---

## 8. Latency and Zero Model Calls

Visual translation operates as a pure, deterministic function of upstream contracts:
- **Model Invocations**: **$0$** model calls across all visual spec generations.
- **Per-Visual Latency**: $< 1.0\text{ ms}$ (Threshold: $< 50\text{ ms}$).
- **10-Slide Deck Visual Translation**: $< 10.0\text{ ms}$ (Threshold: $< 250\text{ ms}$).

---

## 9. Comprehensive Test Suite Summary

All 7 test fixtures in `backend/tests/test_track3_4_visual_spec_fidelity.py` pass with $100\%$ compliance:
1. `test_canonical_24_topics_visual_spec_fidelity`: **PASSED** (All 24 topics match on all 11 protected fields with certified visual specs).
2. `test_six_unseen_analytical_domains_fidelity`: **PASSED** (SaaS, Supply Chain, Financial Operations, Cloud Infrastructure, Commercial Aviation, Healthcare Quality).
3. `test_visual_fixture_matrix_a_to_l`: **PASSED** (All 12 visual edge-case fixtures A through L certified).
4. `test_three_consumer_cross_manifest_parity`: **PASSED** (Studio == PPTX == PDF == Canonical).
5. `test_native_powerpoint_editability_and_roundtrip`: **PASSED** (Native editability 100%, OOXML compliant, PowerPoint roundtrip verified).
6. `test_zero_model_calls_and_performance_latency`: **PASSED** (0 model calls, sub-millisecond execution).
7. `test_number_formatting_contract`: **PASSED** (Underlying numeric conservation across all format types).

**Regression Suites**:
- `test_track3_2_contract_binding.py`: **9 / 9 PASSED** (100%).
- `test_track3_3_spatial_contract.py`: **45 / 45 PASSED** (100%).
- **Combined Acceptance Suite**: **61 / 61 tests PASSED**.
