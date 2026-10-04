# Slide Layout & Spatial Geometry

> **Parent:** [README.md](../../README.md) &rsaquo; Design System

## 1. Unified 16:9 Geometry Baseline

Implemented across React (`resolved-slides.scss`), `.pptx` (`pptx_layouts.py`), and `.pdf` (`resolved_pdf.py`):

- **Baseline Resolution**: `960 × 540 pt` (scales to `1920 × 1080 px` for 1080p high-DPI displays).
- **Usable Content Width**: `864 pt` (48 pt left/right margins).
- **Usable Content Height**: `460 pt` (40 pt top header, 40 pt bottom footer).
- **Full-Width Hero Reclamation**: Standard text and cover slides reclaim the entire 864 pt content width when side metrics are absent.

---

## 2. Standardized Typography Hierarchy

| Element | Size | Weight | Line Height | Purpose |
| :--- | :---: | :---: | :---: | :--- |
| **Cover Title** | `38 pt` | Bold (700) | `1.15` | Hero title on deck cover slide |
| **Slide Header** | `30 pt` | Bold (700) | `1.20` | Main slide title across all interior slides |
| **Panel Title** | `20 pt` | Semi-bold (600) | `1.30` | Section headings, KPI card titles |
| **Body Narrative** | `18 pt` | Regular (400) | `1.40` | Strategic takeaway paragraphs, bullet points |
| **Table Cells** | `16 pt` | Regular (400) | `1.22` | Structured data table rows |
| **Chart Labels** | `14 pt` | Medium (500) | `1.20` | Category axis labels, legend keys, datalabels |
| **Footnotes & Provenance** | `11 pt` | Regular (400) | `1.20` | `EVID-XXX` evidence citations and dataset source |

---

## 3. Dense Table Protection & Overflow Handling

To eliminate layout clipping and footer overlap:
1. **Weighted Column Widths**: Column widths are estimated based on column semantic role (e.g. narrow for short IDs/percentages, wide for descriptions).
2. **Multi-Page Continuation**: Tables exceeding the 460 pt content boundary automatically split across numbered continuation pages with repeated column headers.
3. **Accessible Page Controls**: Slide viewer provides keyboard-accessible page controls outside the slide canvas (`.resolved-table-pages`).
4. **Hard Row Safety**: Any single row exceeding maximum allowable height fails gracefully with an actionable diagnostic rather than clipping off-slide.
