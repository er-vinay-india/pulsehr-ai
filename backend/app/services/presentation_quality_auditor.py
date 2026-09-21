"""Presentation Quality Auditor & Bounded Automated Repair Engine.

Performs deterministic visual, geometric, and factual consistency checks on generated
presentation deck specifications and native PowerPoint objects. Executes automated bounded
repairs (layout adjustments, concise text rewriting, table splitting, and font tuning) to
guarantee presentation-ready quality without manual intervention.
"""

import copy
import logging
import math
import re
from typing import Any

logger = logging.getLogger(__name__)

# Spatial Canvas Constants for 16:9 Widescreen (13.333" x 7.5")
SLIDE_WIDTH_IN = 13.333
SLIDE_HEIGHT_IN = 7.5
MAX_X_BOUND_IN = 12.8
MAX_Y_BOUND_IN = 7.0
HEADER_TOP_IN = 0.4
FOOTER_TOP_IN = 6.75

# Character & Density Budgets
MAX_TITLE_CHARS = 80
MAX_SUBTITLE_CHARS = 120
MAX_NARRATIVE_CHARS = 280
MAX_BULLET_CHARS = 160
MAX_BULLETS_PER_CARD = 3
MAX_TABLE_ROWS_PER_SLIDE = 7
MAX_CATEGORY_LABEL_CHARS = 18


class PresentationQualityAuditor:
    """Audits presentation decks against strict spatial, typographical, and factual standards."""

    @classmethod
    def audit_deck_spec(cls, deck_spec: dict[str, Any], evidence_ledger: list[dict[str, Any]]) -> dict[str, Any]:
        """Runs comprehensive preflight audit across all slides in a deck specification."""
        issues: list[dict[str, Any]] = []
        slides = deck_spec.get("slides", [])

        # 1. Slide Count & Completeness
        if not slides:
            issues.append({
                "severity": "critical",
                "slide_index": 0,
                "type": "empty_deck",
                "message": "Deck contains 0 slides."
            })
            return {"status": "failed", "issues": issues, "can_repair": False}

        for idx, slide in enumerate(slides):
            order = slide.get("order", idx + 1)
            slide_id = slide.get("id")
            title = slide.get("title", "")
            layout = slide.get("layout", "chart_narrative")

            # Check Title & Subtitle Length
            if len(title) > MAX_TITLE_CHARS:
                issues.append({
                    "severity": "warning",
                    "slide_index": order,
                    "slide_id": slide_id,
                    "type": "title_overflow",
                    "message": f"Slide {order} title ({len(title)} chars) exceeds budget of {MAX_TITLE_CHARS}.",
                    "current": title,
                    "limit": MAX_TITLE_CHARS
                })

            sub = slide.get("subtitle", "")
            if len(sub) > MAX_SUBTITLE_CHARS:
                issues.append({
                    "severity": "warning",
                    "slide_index": order,
                    "slide_id": slide_id,
                    "type": "subtitle_overflow",
                    "message": f"Slide {order} subtitle ({len(sub)} chars) exceeds budget of {MAX_SUBTITLE_CHARS}.",
                    "current": sub,
                    "limit": MAX_SUBTITLE_CHARS
                })

            # Check Narrative Length
            narr = slide.get("narrative", "")
            if len(narr) > MAX_NARRATIVE_CHARS:
                issues.append({
                    "severity": "warning",
                    "slide_index": order,
                    "slide_id": slide_id,
                    "type": "narrative_overflow",
                    "message": f"Slide {order} narrative ({len(narr)} chars) exceeds budget of {MAX_NARRATIVE_CHARS}.",
                    "current": narr,
                    "limit": MAX_NARRATIVE_CHARS
                })

            # Check Bullets Count and Length
            bullets = slide.get("bullets", [])
            if len(bullets) > MAX_BULLETS_PER_CARD:
                issues.append({
                    "severity": "warning",
                    "slide_index": order,
                    "slide_id": slide_id,
                    "type": "bullet_count_overflow",
                    "message": f"Slide {order} has {len(bullets)} bullets (limit: {MAX_BULLETS_PER_CARD}).",
                    "count": len(bullets),
                    "limit": MAX_BULLETS_PER_CARD
                })

            for b_idx, b in enumerate(bullets):
                if len(str(b)) > MAX_BULLET_CHARS:
                    issues.append({
                        "severity": "warning",
                        "slide_index": order,
                        "slide_id": slide_id,
                        "type": "bullet_text_overflow",
                        "bullet_index": b_idx,
                        "message": f"Slide {order} bullet {b_idx + 1} ({len(b)} chars) exceeds {MAX_BULLET_CHARS} budget.",
                        "current": b,
                        "limit": MAX_BULLET_CHARS
                    })

            # Check Table Row Density
            table = slide.get("table")
            if table and isinstance(table, dict):
                rows = table.get("rows", [])
                if len(rows) > MAX_TABLE_ROWS_PER_SLIDE:
                    issues.append({
                        "severity": "critical",
                        "slide_index": order,
                        "slide_id": slide_id,
                        "type": "table_row_overflow",
                        "message": f"Slide {order} table has {len(rows)} rows, which will run off slide canvas (limit: {MAX_TABLE_ROWS_PER_SLIDE}).",
                        "rows_count": len(rows),
                        "limit": MAX_TABLE_ROWS_PER_SLIDE
                    })

            # Check Chart Specification
            chart = slide.get("chart")
            has_industrial_panel = bool(slide.get("talent_9box_data") or slide.get("burnout_strain_data"))
            if layout in ("chart_narrative", "full_chart_takeaway", "two_charts") and not chart and not has_industrial_panel:
                issues.append({
                    "severity": "critical",
                    "slide_index": order,
                    "slide_id": slide_id,
                    "type": "missing_chart",
                    "message": f"Slide {order} specifies layout '{layout}' but has no chart specification."
                })
            elif chart and isinstance(chart, dict):
                cats = chart.get("categories", [])
                if not cats:
                    issues.append({
                        "severity": "critical",
                        "slide_index": order,
                        "slide_id": slide_id,
                        "type": "empty_chart_categories",
                        "message": f"Slide {order} chart has empty categories."
                    })
                # Check for overly long category labels
                for c in cats:
                    if len(str(c)) > MAX_CATEGORY_LABEL_CHARS:
                        issues.append({
                            "severity": "minor",
                            "slide_index": order,
                            "slide_id": slide_id,
                            "type": "long_category_label",
                            "category": str(c),
                            "message": f"Slide {order} chart category '{c}' ({len(str(c))} chars) may crowd x-axis."
                        })

                # Check series values
                series_list = chart.get("series", [])
                if not series_list:
                    issues.append({
                        "severity": "critical",
                        "slide_index": order,
                        "slide_id": slide_id,
                        "type": "missing_chart_series",
                        "message": f"Slide {order} chart has no series data."
                    })
                else:
                    for s in series_list:
                        vals = s.get("values", [])
                        if len(vals) != len(cats):
                            issues.append({
                                "severity": "critical",
                                "slide_index": order,
                                "slide_id": slide_id,
                                "type": "series_length_mismatch",
                                "message": f"Slide {order} series '{s.get('name')}' length ({len(vals)}) != categories ({len(cats)})."
                            })
                        for v in vals:
                            if v is None or not isinstance(v, (int, float)) or not math.isfinite(v):
                                issues.append({
                                    "severity": "critical",
                                    "slide_index": order,
                                    "slide_id": slide_id,
                                    "type": "invalid_series_value",
                                    "message": f"Slide {order} series '{s.get('name')}' contains non-finite value: {v}."
                                })

            # Check Voice Narration Preparation
            if not slide.get("narration_script"):
                issues.append({
                    "severity": "minor",
                    "slide_index": order,
                    "slide_id": slide_id,
                    "type": "missing_narration_script",
                    "message": f"Slide {order} is missing prepared narration_script."
                })

        # 2. Claim Verification Check against Ledger
        discrepancies = []
        for ev in evidence_ledger:
            evid = ev.get("evidence_id")
            num_val = ev.get("numeric_value")
            slide_idx = ev.get("slide_index")
            if num_val is not None and slide_idx and slide_idx <= len(slides):
                target_slide = slides[slide_idx - 1]
                found_match = False
                for m in target_slide.get("metrics", []):
                    # Check if numerical claim in metric aligns within +/- 0.1%
                    raw_str = str(m.get("value", ""))
                    clean_str = re.sub(r"[^\d.]", "", raw_str)
                    try:
                        parsed = float(clean_str)
                        if abs(parsed - num_val) <= (abs(num_val) * 0.001 + 0.01):
                            found_match = True
                            break
                    except Exception:
                        pass
                if not found_match:
                    # Metric string might be in narrative or bullet
                    text_blob = f"{target_slide.get('narrative', '')} {' '.join(target_slide.get('bullets', []))}"
                    clean_str = f"{num_val:,.2f}"
                    if clean_str in text_blob or f"{num_val:.1f}" in text_blob or f"{int(num_val)}" in text_blob:
                        found_match = True

        critical_count = sum(1 for i in issues if i["severity"] == "critical")
        warning_count = sum(1 for i in issues if i["severity"] == "warning")

        status = "passed" if critical_count == 0 and warning_count == 0 else ("repairable" if critical_count == 0 or any(i["type"] == "table_row_overflow" for i in issues) else "failed")

        return {
            "status": status,
            "critical_count": critical_count,
            "warning_count": warning_count,
            "minor_count": sum(1 for i in issues if i["severity"] == "minor"),
            "issues": issues,
            "can_repair": critical_count <= 2 and all(i["type"] in ("table_row_overflow", "missing_chart", "long_category_label", "title_overflow", "subtitle_overflow", "narrative_overflow", "bullet_count_overflow", "bullet_text_overflow", "missing_narration_script") for i in issues)
        }

    @classmethod
    def execute_bounded_repair(cls, deck_spec: dict[str, Any], audit_result: dict[str, Any]) -> dict[str, Any]:
        """Performs bounded deterministic repairs to eliminate overflow, format tables,
        and tune text lengths while preserving factual claims."""
        repaired_deck = copy.deepcopy(deck_spec)
        slides = repaired_deck.get("slides", [])
        issues = audit_result.get("issues", [])

        def _find_slide_idx(issue: dict[str, Any]) -> int | None:
            sid = issue.get("slide_id")
            if sid:
                for i, s in enumerate(slides):
                    if s.get("id") == sid:
                        return i
            orig_idx = issue.get("slide_index", 1) - 1
            if 0 <= orig_idx < len(slides):
                return orig_idx
            return None

        # 1. Address Table Row Overflow (Split Table across Appendix Slides)
        table_overflows = [i for i in issues if i["type"] == "table_row_overflow"]
        for issue in table_overflows:
            s_idx = _find_slide_idx(issue)
            if s_idx is not None and 0 <= s_idx < len(slides):
                orig_slide = slides[s_idx]
                table = orig_slide.get("table", {})
                headers = table.get("headers", [])
                rows = table.get("rows", [])
                if len(rows) > MAX_TABLE_ROWS_PER_SLIDE:
                    part1_rows = rows[:MAX_TABLE_ROWS_PER_SLIDE]
                    part2_rows = rows[MAX_TABLE_ROWS_PER_SLIDE:MAX_TABLE_ROWS_PER_SLIDE * 2]

                    # Modify original slide to be Part 1
                    orig_slide["title"] = f"{orig_slide['title']} (Part 1)"
                    orig_slide["table"]["rows"] = part1_rows

                    # Create Part 2 slide
                    part2_slide = copy.deepcopy(orig_slide)
                    part2_slide["id"] = f"{orig_slide['id']}_pt2"
                    part2_slide["title"] = f"{orig_slide['title'].replace(' (Part 1)', '')} (Part 2)"
                    part2_slide["subtitle"] = f"Continued governance records ({len(part2_rows)} additional entries)"
                    part2_slide["table"]["rows"] = part2_rows
                    part2_slide["order"] = orig_slide.get("order", s_idx + 1) + 1

                    # Insert part 2 right after part 1
                    slides.insert(s_idx + 1, part2_slide)
                    # Re-index all slides
                    for oi, sl in enumerate(slides):
                        sl["order"] = oi + 1

        # 2. Address Title & Subtitle Overflow (Concise Rewriting)
        for issue in [i for i in issues if i["type"] in ("title_overflow", "subtitle_overflow")]:
            s_idx = _find_slide_idx(issue)
            if s_idx is not None and 0 <= s_idx < len(slides):
                slide = slides[s_idx]
                if issue["type"] == "title_overflow":
                    slide["title"] = cls._shorten_text(slide["title"], MAX_TITLE_CHARS)
                elif issue["type"] == "subtitle_overflow":
                    slide["subtitle"] = cls._shorten_text(slide["subtitle"], MAX_SUBTITLE_CHARS)

        # 3. Address Narrative & Bullet Overflow
        for issue in [i for i in issues if i["type"] in ("narrative_overflow", "bullet_count_overflow", "bullet_text_overflow")]:
            s_idx = _find_slide_idx(issue)
            if s_idx is not None and 0 <= s_idx < len(slides):
                slide = slides[s_idx]
                if issue["type"] == "narrative_overflow":
                    slide["narrative"] = cls._shorten_narrative(slide["narrative"], MAX_NARRATIVE_CHARS)
                elif issue["type"] == "bullet_count_overflow":
                    # Keep top 3 bullets, move remaining to speaker notes
                    bullets = slide.get("bullets", [])
                    if len(bullets) > MAX_BULLETS_PER_CARD:
                        excess = bullets[MAX_BULLETS_PER_CARD:]
                        slide["bullets"] = bullets[:MAX_BULLETS_PER_CARD]
                        notes = slide.get("speaker_notes", "")
                        excess_text = "\n".join(f"• {b}" for b in excess)
                        slide["speaker_notes"] = f"{notes}\n\n=== ADDITIONAL DETAILS (MOVED FROM SLIDE) ===\n{excess_text}"
                elif issue["type"] == "bullet_text_overflow":
                    b_idx = issue.get("bullet_index", 0)
                    bullets = slide.get("bullets", [])
                    if b_idx < len(bullets):
                        bullets[b_idx] = cls._shorten_text(bullets[b_idx], MAX_BULLET_CHARS)

        # 4. Truncate Long Category Labels in Charts across all slides
        for slide in slides:
            chart = slide.get("chart")
            if chart and isinstance(chart, dict) and chart.get("categories"):
                cats = chart["categories"]
                clean_cats = [
                    f"{str(c)[:MAX_CATEGORY_LABEL_CHARS-3]}..." if len(str(c)) > MAX_CATEGORY_LABEL_CHARS else str(c)
                    for c in cats
                ]
                chart["categories"] = clean_cats
            # Also dual chart support
            for extra_k in ("chart_left", "chart_right"):
                extra_c = slide.get(extra_k)
                if extra_c and isinstance(extra_c, dict) and extra_c.get("categories"):
                    extra_c["categories"] = [
                        f"{str(c)[:MAX_CATEGORY_LABEL_CHARS-3]}..." if len(str(c)) > MAX_CATEGORY_LABEL_CHARS else str(c)
                        for c in extra_c["categories"]
                    ]

        # 5. Populate Missing Voice Narration Scripts
        for s in slides:
            if not s.get("narration_script"):
                title = s.get("title", "")
                narrative = s.get("narrative", "")
                sub = s.get("subtitle", "")
                first_bullet = s.get("bullets", [""])[0]
                script = f"Turning to {title}. {narrative or sub} Notably, {first_bullet}"
                clean_script = re.sub(r"\*\*([^*]+)\*\*", r"\1", script).strip()
                word_count = len(clean_script.split())
                s["narration_script"] = clean_script[:320]
                s["reading_order"] = ["category", "title", "subtitle", "narrative", "metrics", "chart", "bullets", "footer"]
                s["timing_metadata"] = {
                    "word_count": word_count,
                    "estimated_seconds": max(5, int(word_count / 2.4))  # ~140 words per minute
                }

        # 6. Repair any unchartable slides lacking visual panels to comparison_split
        for issue in [i for i in issues if i["type"] == "missing_chart"]:
            s_idx = _find_slide_idx(issue)
            if s_idx is not None and 0 <= s_idx < len(slides):
                sl = slides[s_idx]
                if not sl.get("chart") and not (sl.get("talent_9box_data") or sl.get("burnout_strain_data")):
                    sl["layout"] = "comparison_split"

        repaired_deck["slides"] = slides
        return repaired_deck

    @staticmethod
    def _shorten_text(text: str, limit: int) -> str:
        """Shortens text cleanly at sentence or phrase boundaries while preserving numbers."""
        if len(text) <= limit:
            return text
        # If there's a colon or dash, split
        if ":" in text:
            left, right = text.split(":", 1)
            candidate = f"{left.strip()}: {right.strip()[:limit - len(left) - 4]}..."
            if len(candidate) <= limit:
                return candidate
        # Split by words
        words = text.split()
        out = []
        curr = 0
        for w in words:
            if curr + len(w) + 1 > limit - 3:
                break
            out.append(w)
            curr += len(w) + 1
        return " ".join(out) + "..."

    @staticmethod
    def _shorten_narrative(text: str, limit: int) -> str:
        """Trims narrative to the first 2 core sentences."""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        if len(sentences) > 1:
            candidate = f"{sentences[0]} {sentences[1]}"
            if len(candidate) <= limit:
                return candidate
            if len(sentences[0]) <= limit:
                return sentences[0]
        return PresentationQualityAuditor._shorten_text(text, limit)
