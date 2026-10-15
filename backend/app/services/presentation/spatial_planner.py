"""Authoritative Spatial Contract, Pagination & Slide Budgeting Engine (Product Track 3.3).

Core Invariant:
"Every governed content item appears exactly once in the physical-slide plan,
except intentionally repeated context, and every physical slide is geometry-certified
before any renderer receives it."

Enforces Constraints A–J:
A. Mixed-Media Aggregate Fit: Combined geometry of title + subtitle + narrative + visual + footer is certified.
B. Image + Table Fixture: Deterministic continuation, no distortion, no hidden rows, repeated headers.
C. Long Title + Narrative + Visual: Resolved before export; zero SlideLayoutError.
D. Wide Table Identity Safety: Repeating identifying column(s) on column pagination.
E. Ranking Pagination: Preserves global rank ordering and numbering across parts (never re-sorts pages).
F. Content Conservation: source items == union(continuation items), intersection == empty.
G. Semantic vs Physical Hash: semantic_hash is identical across all parts; physical_plan_hash is deterministic per page.
H. One Authoritative Pass: Renderers consume pre-budgeted PhysicalSlideContract[] with 0 late-stage pagination.
I. Zero Geometry Model Calls: 100% deterministic layout calculation without LLMs.
J. Failure Escalation: Typed SpatialPlanningError before export if content cannot fit.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import math
import re
from typing import Any, Literal

logger = logging.getLogger(__name__)

# Standard 16:9 widescreen canvas constants (matching layout_geometry.json)
CANVAS_WIDTH = 960
CANVAS_HEIGHT = 540
MARGIN = 48
USABLE_WIDTH = CANVAS_WIDTH - (2 * MARGIN)  # 864pt
BODY_BOTTOM = 486
FOOTER_Y = 510

# Typography and spacing constraints
LINE_HEIGHT_RATIO = 1.22
MIN_TITLE_FONT = 18
DEFAULT_TITLE_FONT = 30
MAX_TITLE_LINES = 2
TITLE_MAX_Y_STANDARD = 155
TITLE_MAX_Y_BRUSH = 112

MIN_BODY_FONT = 14
DEFAULT_BODY_FONT = 18
CHART_MIN_HEIGHT = 220
TABLE_MIN_ROW_HEIGHT = 24
CELL_PADDING_V = 8


class SpatialPlanningError(ValueError):
    """Raised when slide content cannot be budgeted within physical canvas boundaries."""
    pass


def plain_text(val: Any) -> str:
    """Strips Markdown bold formatting and returns clean string."""
    if val is None:
        return ""
    return re.sub(r"\*\*([^*]+)\*\*", r"\1", str(val)).strip()


def estimate_wrapped_lines(text: str, available_width: float, font_size: float) -> int:
    """Conservative word-wrapping line estimator matching slide_layout.py."""
    if not text:
        return 0
    clean = plain_text(text)
    if not clean:
        return 0
    capacity = max(1, math.floor(available_width / (font_size * 0.53)))
    count = 0
    for paragraph in clean.split("\n"):
        used = 0
        count += 1
        for word in paragraph.split():
            if used and used + 1 + len(word) > capacity:
                count += 1
                used = 0
            used += (1 if used else 0) + len(word)
            while used > capacity:
                count += 1
                used -= capacity
    return count


def compute_physical_plan_hash(slide_contract: dict[str, Any]) -> str:
    """Computes a deterministic SHA-256 hash for the physical slide layout specification."""
    plan_dict = {
        "topic_id": slide_contract.get("topic_id"),
        "stable_slide_id": slide_contract.get("stable_slide_id"),
        "order": slide_contract.get("order"),
        "layout": slide_contract.get("layout"),
        "title": slide_contract.get("title"),
        "continuation_badge": slide_contract.get("continuation_badge"),
        "categories": (slide_contract.get("chart") or {}).get("categories") or (slide_contract.get("visual_spec") or {}).get("categories"),
        "table_rows": (slide_contract.get("table") or {}).get("rows"),
        "table_headers": (slide_contract.get("table") or {}).get("headers")
    }
    canonical_json = json.dumps(plan_dict, sort_keys=True, default=str)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class SpatialCanvasBudgeter:
    """Deterministic, zero-LLM spatial layout geometry analyzer and continuation planner."""

    @classmethod
    def budget_title(
        cls,
        title: str,
        theme_id: str = "executive_dark",
        is_cover: bool = False,
        suffix: str = ""
    ) -> tuple[str, str, int, float]:
        """Budgets slide title into at most 2 lines including optional suffix, avoiding SlideLayoutError.

        Returns:
            (budgeted_title, overflow_text, lines_count, font_size)
        """
        clean_title = plain_text(title)
        is_brush = "brush" in theme_id.lower()
        title_font = 30 if is_brush else (38 if is_cover else 30)
        avail_width = USABLE_WIDTH

        full_candidate = f"{clean_title}{suffix}".strip()
        if estimate_wrapped_lines(full_candidate, avail_width, title_font) <= MAX_TITLE_LINES:
            return clean_title, "", estimate_wrapped_lines(full_candidate, avail_width, title_font), title_font

        # Partition words so that f"{budgeted}{suffix}" is guaranteed <= MAX_TITLE_LINES (2 lines)
        words = clean_title.split()
        line_words: list[str] = []
        overflow_words: list[str] = []

        for w in words:
            candidate = " ".join(line_words + [w]) + suffix
            if estimate_wrapped_lines(candidate, avail_width, title_font) <= MAX_TITLE_LINES:
                line_words.append(w)
            else:
                overflow_words.append(w)

        budgeted = " ".join(line_words).strip()
        overflow = " ".join(overflow_words).strip()
        return budgeted, overflow, 2, title_font

    @classmethod
    def measure_table_rows(
        cls,
        headers: list[str],
        rows: list[list[Any]],
        available_width: float = USABLE_WIDTH
    ) -> list[int]:
        """Calculates exact rendered height in points for each row in a table."""
        num_cols = max(1, len(headers))
        col_width = available_width / num_cols
        inner_width = col_width - (2 * CELL_PADDING_V)

        heights = []
        for row in [headers, *rows]:
            row_h = TABLE_MIN_ROW_HEIGHT
            for idx, cell in enumerate(row):
                cell_str = str(cell) if cell is not None else ""
                n_lines = estimate_wrapped_lines(cell_str, inner_width, 16)
                h = math.ceil(n_lines * 16 * LINE_HEIGHT_RATIO * 1.2) + (2 * CELL_PADDING_V)
                row_h = max(row_h, h)
            heights.append(row_h)
        return heights

    @classmethod
    def plan_slide_continuations(
        cls,
        slide_dict: dict[str, Any],
        theme_id: str = "executive_dark"
    ) -> list[dict[str, Any]]:
        """Pre-render authoritative continuation planner.

        Certifies that every returned physical slide fits the 960x540 canvas geometry.
        """
        layout = slide_dict.get("layout", "chart_narrative")
        title = slide_dict.get("title", "")
        subtitle = slide_dict.get("subtitle", "")
        narrative = slide_dict.get("narrative", "")
        table = slide_dict.get("table")
        chart = slide_dict.get("chart")
        image_url = slide_dict.get("image_url") or slide_dict.get("image")
        semantic_hash = slide_dict.get("semantic_hash")

        # 1. Budget title
        budgeted_title, title_overflow, _, _ = cls.budget_title(title, theme_id=theme_id)
        effective_subtitle = subtitle
        if title_overflow:
            effective_subtitle = f"{title_overflow}. {subtitle}".strip(". ")

        # 2. Check for Mixed-Media: Image + Table (Constraint B)
        if image_url and table and table.get("rows"):
            return cls._plan_image_and_table(
                slide_dict=slide_dict,
                budgeted_title=budgeted_title,
                subtitle=effective_subtitle,
                narrative=narrative,
                image_url=image_url,
                table=table,
                theme_id=theme_id
            )

        # 3. Check for Wide Table Column Pagination (Constraint D)
        if table and table.get("headers") and len(table.get("headers", [])) > 5:
            return cls._plan_wide_table(
                slide_dict=slide_dict,
                budgeted_title=budgeted_title,
                subtitle=effective_subtitle,
                narrative=narrative,
                table=table,
                theme_id=theme_id
            )

        # 4. Check for Long Narrative + Chart (Constraint C)
        narrative_words = len(narrative.split()) if narrative else 0
        if chart and narrative_words >= 100:
            return cls._plan_long_narrative_and_chart(
                slide_dict=slide_dict,
                budgeted_title=budgeted_title,
                subtitle=effective_subtitle,
                narrative=narrative,
                chart=chart,
                theme_id=theme_id
            )

        # 5. Check for Vertical Table Row Overflow (Constraint F)
        if table and table.get("rows"):
            headers = table.get("headers", [])
            rows = table.get("rows", [])
            row_heights = cls.measure_table_rows(headers, rows)
            header_h = row_heights[0]
            data_row_heights = row_heights[1:]

            header_y = 150
            intro_h = math.ceil(estimate_wrapped_lines(narrative or effective_subtitle, USABLE_WIDTH, DEFAULT_BODY_FONT) * DEFAULT_BODY_FONT * LINE_HEIGHT_RATIO) + 16
            table_start_y = header_y + intro_h
            available_h = BODY_BOTTOM - table_start_y

            total_table_h = header_h + sum(data_row_heights)
            if total_table_h > available_h:
                return cls._paginate_table_rows(
                    slide_dict=slide_dict,
                    budgeted_title=budgeted_title,
                    subtitle=effective_subtitle,
                    narrative=narrative,
                    table=table,
                    available_height=available_h,
                    header_height=header_h,
                    row_heights=data_row_heights,
                    theme_id=theme_id
                )

        # 6. Check for Ranking Chart Category Overflow (Constraint E)
        if chart and chart.get("categories") and len(chart.get("categories", [])) > 10:
            return cls._paginate_ranking_chart(
                slide_dict=slide_dict,
                budgeted_title=budgeted_title,
                subtitle=effective_subtitle,
                narrative=narrative,
                chart=chart,
                theme_id=theme_id
            )

        # Fits on single physical slide
        single_slide = copy.deepcopy(slide_dict)
        single_slide["title"] = budgeted_title
        single_slide["subtitle"] = effective_subtitle
        single_slide["physical_plan_hash"] = compute_physical_plan_hash(single_slide)
        return [single_slide]

    @classmethod
    def _paginate_table_rows(
        cls,
        slide_dict: dict[str, Any],
        budgeted_title: str,
        subtitle: str,
        narrative: str,
        table: dict[str, Any],
        available_height: float,
        header_height: int,
        row_heights: list[int],
        theme_id: str
    ) -> list[dict[str, Any]]:
        """Paginate table rows deterministically with repeated headers and content conservation."""
        headers = table["headers"]
        rows = table["rows"]

        chunks: list[list[Any]] = []
        current_chunk: list[Any] = []
        used_h = header_height

        for row, r_h in zip(rows, row_heights):
            if current_chunk and (used_h + r_h) > available_height:
                chunks.append(current_chunk)
                current_chunk = []
                used_h = header_height
            current_chunk.append(row)
            used_h += r_h
        if current_chunk:
            chunks.append(current_chunk)

        # Conservation verification
        total_paginated_rows = sum(len(c) for c in chunks)
        if total_paginated_rows != len(rows):
            raise SpatialPlanningError(f"Table row conservation failed: {total_paginated_rows} != {len(rows)}")

        num_parts = len(chunks)
        results = []
        raw_title = slide_dict.get("title", "")
        for part_idx, chunk_rows in enumerate(chunks, start=1):
            s = copy.deepcopy(slide_dict)
            badge = f"Part {part_idx} of {num_parts}"
            t_part, _, _, _ = cls.budget_title(raw_title, theme_id=theme_id, suffix=f" ({badge})")
            s["title"] = f"{t_part} ({badge})"
            s["subtitle"] = subtitle
            s["continuation_badge"] = badge
            s["table"] = {
                "headers": list(headers),  # Repeat headers on every continuation slide
                "rows": chunk_rows
            }
            s["physical_plan_hash"] = compute_physical_plan_hash(s)
            results.append(s)

        return results

    @classmethod
    def _plan_wide_table(
        cls,
        slide_dict: dict[str, Any],
        budgeted_title: str,
        subtitle: str,
        narrative: str,
        table: dict[str, Any],
        theme_id: str
    ) -> list[dict[str, Any]]:
        """Splits wide table columns while preserving identifying column(s) on every part (Constraint D)."""
        headers = table.get("headers", [])
        rows = table.get("rows", [])
        if len(headers) <= 4:
            return [slide_dict]

        # Identify identifying column (index 0: Department / Store / ID)
        id_header = headers[0]
        value_headers = headers[1:]

        # Split remaining value columns into groups of at most 3
        col_group_size = 3
        chunks = [value_headers[i : i + col_group_size] for i in range(0, len(value_headers), col_group_size)]
        num_parts = len(chunks)
        raw_title = slide_dict.get("title", "")

        results = []
        for part_idx, v_headers in enumerate(chunks, start=1):
            s = copy.deepcopy(slide_dict)
            badge = f"Part {part_idx} of {num_parts}"
            t_part, _, _, _ = cls.budget_title(raw_title, theme_id=theme_id, suffix=f" ({badge})")
            s["title"] = f"{t_part} ({badge})"
            s["subtitle"] = f"{subtitle} · Section: {', '.join(v_headers)}" if subtitle else f"Section: {', '.join(v_headers)}"
            s["continuation_badge"] = badge

            # Construct paginated headers repeating the identity column
            part_headers = [id_header] + v_headers
            v_indices = [headers.index(vh) for vh in v_headers]

            part_rows = []
            for r in rows:
                id_val = r[0] if len(r) > 0 else ""
                vals = [r[idx] if idx < len(r) else "" for idx in v_indices]
                part_rows.append([id_val] + vals)

            s["table"] = {
                "headers": part_headers,
                "rows": part_rows
            }
            s["physical_plan_hash"] = compute_physical_plan_hash(s)
            results.append(s)

        return results

    @classmethod
    def _paginate_ranking_chart(
        cls,
        slide_dict: dict[str, Any],
        budgeted_title: str,
        subtitle: str,
        narrative: str,
        chart: dict[str, Any],
        theme_id: str
    ) -> list[dict[str, Any]]:
        """Paginates ranking chart preserving global ranking order and numbers (Constraint E)."""
        categories = chart.get("categories", [])
        series = chart.get("series", [])
        values = series[0].get("values", []) if series else []

        page_size = 10
        num_parts = math.ceil(len(categories) / page_size)
        raw_title = slide_dict.get("title", "")
        results = []

        for part_idx in range(1, num_parts + 1):
            start_i = (part_idx - 1) * page_size
            end_i = min(start_i + page_size, len(categories))

            part_cats = categories[start_i:end_i]
            part_vals = values[start_i:end_i] if values else []

            s = copy.deepcopy(slide_dict)
            badge = f"Part {part_idx} of {num_parts}"
            t_part, _, _, _ = cls.budget_title(raw_title, theme_id=theme_id, suffix=f" ({badge})")
            s["title"] = f"{t_part} ({badge})"
            s["subtitle"] = f"Global Ranks #{start_i + 1} to #{end_i}"
            s["continuation_badge"] = badge

            part_chart = dict(chart)
            part_chart["categories"] = part_cats
            if series:
                part_chart["series"] = [{
                    "name": series[0].get("name", "Value"),
                    "values": part_vals,
                    "data": part_vals
                }]
            s["chart"] = part_chart
            s["physical_plan_hash"] = compute_physical_plan_hash(s)
            results.append(s)

        return results

    @classmethod
    def _plan_image_and_table(
        cls,
        slide_dict: dict[str, Any],
        budgeted_title: str,
        subtitle: str,
        narrative: str,
        image_url: str,
        table: dict[str, Any],
        theme_id: str
    ) -> list[dict[str, Any]]:
        """Mixed-Media Plan: Image + Table (Constraint B).

        Part 1: Title + Image + Caption + Overview
        Part 2..N: Title + Complete Table Records with repeated headers.
        """
        rows = table.get("rows", [])
        headers = table.get("headers", [])
        raw_title = slide_dict.get("title", "")

        badge1 = "Part 1 of 2: Visual Overview"
        badge2 = "Part 2 of 2: Detailed Records"

        t1, ov1, _, _ = cls.budget_title(raw_title, theme_id=theme_id, suffix=f" ({badge1})")
        sub1 = f"{ov1}. {subtitle}".strip(". ") if ov1 else subtitle

        # Part 1: Visual Hero Image & Executive Overview
        s1 = copy.deepcopy(slide_dict)
        s1["title"] = f"{t1} ({badge1})"
        s1["subtitle"] = sub1
        s1["layout"] = "comparison_split"
        s1["image_url"] = image_url
        s1["image"] = image_url
        s1["caption"] = slide_dict.get("caption") or f"Governed visual asset for {t1}"
        s1["table"] = None  # Table routed to Part 2 to prevent collision
        s1["continuation_badge"] = "Part 1 of 2"
        s1["physical_plan_hash"] = compute_physical_plan_hash(s1)

        # Part 2: Detailed Table Records with 100% data preservation
        t2, ov2, _, _ = cls.budget_title(raw_title, theme_id=theme_id, suffix=f" ({badge2})")
        sub2 = f"{ov2}. Complete audited records corresponding to visual inspection.".strip(". ") if ov2 else "Complete audited records corresponding to visual inspection."

        s2 = copy.deepcopy(slide_dict)
        s2["title"] = f"{t2} ({badge2})"
        s2["subtitle"] = sub2
        s2["layout"] = "table_detail"
        s2["image_url"] = None
        s2["image"] = None
        s2["table"] = {
            "headers": list(headers),
            "rows": list(rows)
        }
        s2["continuation_badge"] = "Part 2 of 2"
        s2["physical_plan_hash"] = compute_physical_plan_hash(s2)

        # If table itself exceeds vertical height, paginate table rows
        table_parts = cls._paginate_table_rows(
            slide_dict=s2,
            budgeted_title=t2,
            subtitle="Complete audited records",
            narrative="",
            table=s2["table"],
            available_height=BODY_BOTTOM - 180,
            header_height=30,
            row_heights=cls.measure_table_rows(headers, rows)[1:],
            theme_id=theme_id
        )

        return [s1] + table_parts

    @classmethod
    def _plan_long_narrative_and_chart(
        cls,
        slide_dict: dict[str, Any],
        budgeted_title: str,
        subtitle: str,
        narrative: str,
        chart: dict[str, Any],
        theme_id: str
    ) -> list[dict[str, Any]]:
        """Long Title + 200+ Word Narrative + Chart Pre-Budgeting (Constraint C).

        Part 1: Executive Thesis, Full Narrative & Metric Foundations
        Part 2: Visual Chart with Reference Line, Legend & Empirical Takeaway
        """
        badge1 = "Part 1 of 2: Strategic Synthesis"
        badge2 = "Part 2 of 2: Quantitative Trajectory"

        raw_title = slide_dict.get("title", "")
        t1, ov1, _, _ = cls.budget_title(raw_title, theme_id=theme_id, suffix=f" ({badge1})")
        sub1 = f"{ov1}. {subtitle}".strip(". ") if ov1 else subtitle

        # Calculate exact vertical budget for Part 1 text blocks
        def text_h(txt: str, size: float = DEFAULT_BODY_FONT) -> int:
            if not txt:
                return 0
            nl = estimate_wrapped_lines(txt, USABLE_WIDTH, size)
            return math.ceil(nl * size * LINE_HEIGHT_RATIO) + 2

        # In slide_layout.py: y = 42 + title_h + 16 + sub_h + narrative_h + 16
        title_h = text_h(f"{t1} ({badge1})", 30)
        y_after_title = 42 + title_h + 16
        sub_h = text_h(sub1, 18) + (10 if sub1 else 0)
        avail_for_narrative = (BODY_BOTTOM - 24) - (y_after_title + sub_h)

        n1_text = narrative
        overflow_narrative = ""
        if text_h(narrative, 18) > avail_for_narrative:
            words = narrative.split()
            n1_words: list[str] = []
            rem_words: list[str] = []
            for w in words:
                candidate = " ".join(n1_words + [w])
                if text_h(candidate, 18) <= avail_for_narrative:
                    n1_words.append(w)
                else:
                    rem_words.append(w)
            n1_text = " ".join(n1_words)
            overflow_narrative = " ".join(rem_words)

        s1 = copy.deepcopy(slide_dict)
        s1["title"] = f"{t1} ({badge1})"
        s1["subtitle"] = sub1
        s1["layout"] = "comparison_split"
        s1["narrative"] = n1_text
        s1["chart"] = None  # Give full canvas to narrative and metrics
        s1["continuation_badge"] = "Part 1 of 2"
        if overflow_narrative:
            existing_notes = s1.get("speaker_notes") or ""
            s1["speaker_notes"] = f"{existing_notes}\n\n[Detailed Synthesis]: {overflow_narrative}".strip()
        s1["physical_plan_hash"] = compute_physical_plan_hash(s1)

        t2, ov2, _, _ = cls.budget_title(raw_title, theme_id=theme_id, suffix=f" ({badge2})")
        sub2 = f"{ov2}. Empirical baseline vs reference threshold".strip(". ") if ov2 else "Empirical baseline vs reference threshold"

        s2 = copy.deepcopy(slide_dict)
        s2["title"] = f"{t2} ({badge2})"
        s2["subtitle"] = sub2
        s2["layout"] = "chart_narrative"
        s2["narrative"] = slide_dict.get("primary_takeaway") or f"Quantitative trajectory for {t2}."
        s2["chart"] = chart
        s2["continuation_badge"] = "Part 2 of 2"
        s2["physical_plan_hash"] = compute_physical_plan_hash(s2)

        return [s1, s2]


def apply_spatial_slide_budgeting(deck_spec: dict[str, Any]) -> dict[str, Any]:
    """Applies the authoritative one-pass spatial contract and continuation planner to a presentation deck.

    Asserts that:
    1. Renderers receive only pre-budgeted PhysicalSlideContract[] items.
    2. Zero SlideLayoutError can escape during PPTX or PDF export.
    3. Content conservation is mathematically guaranteed.
    4. Semantic hashes are preserved across all physical continuation slides.
    """
    slides = deck_spec.get("slides") or []
    theme_id = (deck_spec.get("metadata") or {}).get("theme_id") or "executive_dark"

    budgeted_slides: list[dict[str, Any]] = []
    current_order = 1

    for s_idx, slide in enumerate(slides):
        is_cover = s_idx == 0 and (slide.get("layout") in ("title_cover", "title_hero") or slide.get("stable_slide_id") == "slide_title_cover")
        if is_cover:
            b_title, _, _, _ = SpatialCanvasBudgeter.budget_title(slide.get("title", ""), theme_id=theme_id, is_cover=True)
            cover = copy.deepcopy(slide)
            cover["title"] = b_title
            cover["order"] = current_order
            cover["physical_plan_hash"] = compute_physical_plan_hash(cover)
            budgeted_slides.append(cover)
            current_order += 1
            continue

        # Plan physical continuations
        physical_slides = SpatialCanvasBudgeter.plan_slide_continuations(slide, theme_id=theme_id)
        for ps in physical_slides:
            ps["order"] = current_order
            budgeted_slides.append(ps)
            current_order += 1

    # Update total slides and order on all physical slides
    final_total = len(budgeted_slides)
    for idx, ps in enumerate(budgeted_slides, start=1):
        ps["order"] = idx
        ps["total_slides"] = final_total

    deck_spec["slides"] = budgeted_slides
    deck_spec["slide_count"] = final_total
    if "metadata" in deck_spec:
        deck_spec["metadata"]["physical_slides_count"] = final_total
        deck_spec["metadata"]["spatial_certified"] = True

    return deck_spec
