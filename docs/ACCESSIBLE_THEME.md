# HighView theme

The application uses navy, emerald and warm neutral surfaces, with restrained
gold, crimson and violet for highlights, status messages and chart series.
The personal colour preferences informed the palette; accessibility and a calm
analytical interface determined the actual shades and foreground/background pairs.

| Role | Light | Dark |
| --- | --- | --- |
| Page | Warm ivory `#F6F5F0` | Deep navy `#101B27` |
| Surface | White `#FFFFFF` | Slate navy `#172635` |
| Primary text | Ink `#172B3A` | Warm white `#F4F5EF` |
| Actions / success | Emerald `#075443` | Mint emerald `#82D9B5` |
| Information | Navy blue `#234E70` | Soft blue `#A9CAE8` |
| Gold / warning | Deep gold `#65470C` | Warm gold `#E8C675` |
| Error | Crimson `#8E1938` | Soft crimson `#FFB3C0` |

## One palette source

Edit **frontend/src/styles/_tokens.scss**. It defines both themes and preserves
the existing CSS custom property aliases used throughout the application.
Component SCSS and inline styles should reference named properties, for example:

```scss
.card {
  background: var(--color-bg-surface);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border);
}
.action {
  background: var(--btn-primary-bg);
  color: var(--btn-primary-fg);
}
```

ECharts requires resolved colours. **scripts/generate_theme_tokens.mjs** compiles
the canonical SCSS and resolves its aliases into **src/theme/tokens.generated.js**.
Do not edit the generated file. Vite generates it on startup/build and refreshes
it when the SCSS palette changes during development. **src/theme/tokens.js**
provides the existing `getThemeTokens(isDark)` and `getChartTokens(isDark)` API.
JavaScript chart options should use those named tokens.

## Contrast verification

Run from **frontend**:

```sh
npm run test:theme
npm run build
```

The theme test regenerates the chart adapter and verifies 1,374 contrast pairs
and gradient samples without rounding pass/fail thresholds:

- Normal text and semantic/chart colours against eight permitted surfaces: >= 7:1.
- Primary and secondary action labels, including hover states: >= 7:1.
- Upload step labels (active/pending) and arrows using the actual component SCSS: >= 7:1.
- Heatmap labels across interpolated cells and launcher labels across gradients: >= 7:1.
- Input boundaries and focus indicators against permitted surfaces: >= 3:1.
- CSS and generated JavaScript palette parity.

Minimum tested text contrast: **7.25:1 light**, **7.23:1 dark**.
Quiet dividers are decorative; interactive controls use stronger borders.
Status labels and chart legends retain text descriptions alongside colour.

These checks cover the shared palette and specified colour pairs. They do not
certify complete WCAG AAA conformance, which also includes keyboard operation,
content, assistive technology support and other requirements. Existing exported
slide template palettes are separate from the application's light/dark themes.

Reference: [WCAG 2.2 Contrast (Enhanced)](https://www.w3.org/WAI/WCAG22/Understanding/contrast-enhanced.html)
and [Non-text Contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html).
