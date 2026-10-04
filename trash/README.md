# Archived & Replaced Documentation (Trash Archive)

This directory contains legacy, uncompacted, or temporary documentation files moved during the documentation compaction on **4 October 2026**.

> **Safety Notice:** None of these files are permanently deleted. If any historical detail, raw fixture trace, or uncompacted reference is needed, it can be restored directly back to `docs/` from this folder.

---

## Manifest of Archived Files & Active Replacements

| Archived File in `trash/` | Original Size | Reason for Archiving | Active Compact Node in `docs/` |
| :--- | :---: | :--- | :--- |
| `ACCESSIBLE_THEME.md` | 77 lines | Compacted into standard design token spec | [`docs/design-system/theme-tokens.md`](../docs/design-system/theme-tokens.md) |
| `AI_REPORT_GENERATION_ARCHITECTURE.md` | 166 lines | Merged into modular architecture & presentation specs | [`docs/architecture/presentation-engine.md`](../docs/architecture/presentation-engine.md) |
| `DECISION_INTELLIGENCE_DELIVERY.md` | 78 lines | Compacted into decision intelligence architecture | [`docs/architecture/decision-intelligence.md`](../docs/architecture/decision-intelligence.md) |
| `GENERIC_ANALYTICS_PIPELINE.md` | 151 lines | Compacted into analytics pipeline architecture | [`docs/architecture/analytics-pipeline.md`](../docs/architecture/analytics-pipeline.md) |
| `MODULAR_TEST_ARCHITECTURE_AND_POLICY.md` | 132 lines | Compacted into engineering test architecture | [`docs/engineering/test-architecture.md`](../docs/engineering/test-architecture.md) |
| `PRESENTATION_ENGINE_SPEC_AND_UNDERSTANDING.md` | 90 lines | Compacted into presentation engine & visual analytics | [`docs/architecture/presentation-engine.md`](../docs/architecture/presentation-engine.md) |
| `PROJECT_AST_GRAPH.md` | 866 lines | Static, unmaintainable AST syntax dump from Sept 2026 | *Codebase AST available via runtime scripts in `scratch/`* |
| `adaptive-dashboard-design.md` | 1161 lines | 12 historical iterative revisions consolidated into core spec | [`docs/features/adaptive-dashboard.md`](../docs/features/adaptive-dashboard.md) |
| `gemini-hriday-analytical-query-prompt.md` | 245 lines | One-off implementation prompt for an AI agent on Oct 2 | Core acceptance principle in [`docs/features/hriday-copilot.md`](../docs/features/hriday-copilot.md) |
| `hriday-identity-layer.md` | 176 lines | Compacted into HRIDAY copilot feature spec | [`docs/features/hriday-copilot.md`](../docs/features/hriday-copilot.md) |
| `presentation-hr-readability-rca.md` | 154 lines | One-off historical RCA comparison against external deck | Invariants in [`docs/design-system/slide-layouts.md`](../docs/design-system/slide-layouts.md) |
| `presentation-job-recovery.md` | 51 lines | Compacted into background worker lifecycle doc | [`docs/engineering/job-recovery.md`](../docs/engineering/job-recovery.md) |
| `presentation-pipeline-phases.md` | 102 lines | Commit-by-commit changelog of past fixes | Active flow in [`docs/architecture/presentation-engine.md`](../docs/architecture/presentation-engine.md) |
| `presentation-space-usage-review.md` | 150 lines | Visual review notes and margin experiments | Standard geometry in [`docs/design-system/slide-layouts.md`](../docs/design-system/slide-layouts.md) |
| `presentation-studio-handoff.md` | 28 lines | Temporary UI handoff notes from Sept 2026 | Current UI invariants in presentation engine docs |
| `reviews/` | 19 assets | PNG screenshots, test PPTX/PDF layout fixtures | Moved to preserve git repo lightness |

---

## How to Restore a File

To restore any archived file back to `docs/`:

```bash
# Example: Restore adaptive-dashboard-design.md
mv trash/adaptive-dashboard-design.md docs/
```
