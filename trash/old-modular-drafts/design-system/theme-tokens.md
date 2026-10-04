# HighView Theme & Accessible Design Tokens

> **Parent:** [README.md](../../README.md) &rsaquo; Design System

## 1. Single Source of Truth (`frontend/src/styles/_tokens.scss`)

The HighView visual system is defined in `_tokens.scss`. JavaScript chart palettes, slide exporters, and UI components inherit directly from these canonical tokens.

- **Primary Metaphor**: Navy / emerald theme with warm neutral surfaces.
- **Target Accessibility**: Text tokens target &ge; 7:1 contrast ratio across semantic surfaces (WCAG AAA).
- **Validation**: Automated theme tests run via `npm run test:theme` in `frontend/`.

---

## 2. Canonical Token Specification

| CSS Token Variable | Light Mode (`:root`) | Dark Mode (`[data-theme="dark"]`) | Description |
| :--- | :---: | :---: | :--- |
| `--color-bg-page` | `#F6F5F0` | `#101B27` | Viewport & outer canvas background |
| `--color-bg-surface` | `#FFFFFF` | `#172635` | Main card panels, slide canvas, modal dialogs |
| `--color-bg-elevated` | `#FFFFFF` | `#203445` | Dropdowns, popovers, floating toolbars |
| `--color-bg-subtle` | `#EEEFE9` | `#1C2E3E` | Table header fills, neutral pill badges |
| `--color-text-primary` | `#172B3A` | `#F4F5EF` | Primary headings, table data, active labels |
| `--color-text-secondary`| `#334B57` | `#D3DED9` | Secondary subtitles, axis labels, field names |
| `--color-text-muted` | `#3C5059` | `#BDCBC5` | Timestamp notes, breadcrumbs, inactive captions |
| `--color-brand-primary` | `#183B56` | `#A9CAE8` | HighView brand navy, primary navigation accents |
| `--color-brand-secondary`| `#075443`| `#82D9B5` | Emerald action buttons, active interactive focus |
| `--color-border` | `#D4DDD6` | `#3B4E5A` | Standard structural borders and card dividers |
| `--color-border-strong` | `#78877F` | `#82968F` | Input field borders, high-contrast boundaries |
| `--color-success` | `#075443` | `#82D9B5` | Positive indicators, healthy benchmarks |
| `--color-info` | `#234E70` | `#A9CAE8` | Informational callouts, neutral metrics |
| `--color-warning` | `#65470C` | `#E8C675` | Restrained gold; caution & moderate volatility |
| `--color-error` | `#8E1938` | `#FFB3C0` | Deep crimson; critical headwinds, high attrition |

---

## 3. HighView Accent Tokens

- `--color-gold`: `#65470C` (Light) / `#E8C675` (Dark)
- `--color-violet`: `#513B72` (Light) / `#D2C1E9` (Dark)
- `--color-brand-blue`: `#234E70` (Light) / `#A9CAE8` (Dark)
