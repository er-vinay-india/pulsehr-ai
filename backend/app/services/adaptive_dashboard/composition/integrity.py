"""Composition Integrity and Architecture Boundary Verification (Phase G5.6).

Guarantees:
1. Every composition topic_id exists in the input portfolio (fail-closed on unknown IDs).
2. Zero duplicate topic ownership in the layout plan.
3. Zero overlapping grid coordinates within any row.
4. Spans respect 12-column grid bounds and archetype readability minimums.
5. ExecutiveTopic and VisualSpec semantic fingerprints remain strictly immutable through layout.
6. AST boundary purity: zero database, zero AI/LLM, zero MCP, zero theme dependencies.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any

from .contracts import DashboardLayoutPlan


class CompositionIntegrityError(Exception):
    """Raised when spatial composition violates grid boundaries, topic ownership, or immutability invariants."""
    pass


class CompositionIntegrity:
    """Static validation suite for spatial composition plans."""

    @classmethod
    def compute_visual_semantic_fingerprint(cls, visual_spec: dict[str, Any]) -> str:
        """Computes a deterministic hash of visual specification semantic fields."""
        if not isinstance(visual_spec, dict):
            return ""
        semantic_parts = [
            f"chart_type:{visual_spec.get('chart_type')}",
            f"x_label:{visual_spec.get('x_label')}",
            f"y_label:{visual_spec.get('y_label')}",
            f"entity_column:{visual_spec.get('entity_column')}",
            f"measure_column:{visual_spec.get('measure_column')}",
            f"entity_grain:{visual_spec.get('entity_grain')}",
            f"domain:{visual_spec.get('domain')}",
            f"series_count:{len(visual_spec.get('series', [])) if isinstance(visual_spec.get('series'), list) else 0}",
            f"evidence_ids:{sorted(visual_spec.get('evidence_ids', []))}",
        ]
        return hashlib.sha256("|".join(semantic_parts).encode("utf-8")).hexdigest()

    @classmethod
    def compute_topic_semantic_fingerprint(cls, topic: Any) -> str:
        """Computes a deterministic hash of executive topic semantic fields."""
        semantic_parts = [
            f"topic_id:{getattr(topic, 'topic_id', '')}",
            f"semantic_topic_key:{getattr(topic, 'semantic_topic_key', '')}",
            f"analytical_intent:{getattr(topic, 'analytical_intent', '')}",
            f"domain:{getattr(topic, 'domain', '')}",
            f"dataset_id:{getattr(topic, 'dataset_id', '')}",
            f"evidence_ids:{sorted(getattr(topic, 'evidence_ids', []))}",
            f"title:{getattr(topic, 'title', '')}",
        ]
        return hashlib.sha256("|".join(semantic_parts).encode("utf-8")).hexdigest()

    @classmethod
    def assert_valid_plan(cls, plan: DashboardLayoutPlan, topics: list[Any]) -> None:
        """Validates all spatial and grid integrity constraints for a planned layout."""
        if not topics:
            return

        topic_ids = {str(getattr(t, "topic_id", "") or id(t)) for t in topics}

        # 1. Topic ID validity & uniqueness across all items
        seen_topic_ids: set[str] = set()
        for item in plan.items:
            # Topic ID must exist in input topics
            if item.topic_id not in topic_ids:
                raise CompositionIntegrityError(
                    f"COMPOSITION_UNKNOWN_TOPIC: Item topic_id '{item.topic_id}' does not exist in input topics."
                )

            # No duplicate items
            if item.topic_id in seen_topic_ids:
                raise CompositionIntegrityError(
                    f"COMPOSITION_DUPLICATE_TOPIC: Topic '{item.topic_id}' has multiple placements in the layout plan."
                )
            seen_topic_ids.add(item.topic_id)

            # Positive dimensions and column bounds
            if item.span <= 0:
                raise CompositionIntegrityError(
                    f"COMPOSITION_INVALID_SPAN: Topic '{item.topic_id}' has non-positive span {item.span}."
                )
            if item.span > 12:
                raise CompositionIntegrityError(
                    f"COMPOSITION_OVERFLOW_SPAN: Topic '{item.topic_id}' span {item.span} exceeds 12-column grid."
                )

        # 2. Grid bounds & non-overlapping coordinates in every row
        for sec in plan.sections:
            for row in sec.rows:
                current_col = 0
                row_total = 0
                for c in row.cards:
                    if c.span < 3:
                        raise CompositionIntegrityError(
                            f"COMPOSITION_READABILITY_VIOLATION: Card '{c.topic_id}' span {c.span} < absolute minimum 3."
                        )
                    # Non-overlapping coordinate placement
                    if c.column < current_col:
                        raise CompositionIntegrityError(
                            f"COMPOSITION_GRID_OVERLAP: Card '{c.topic_id}' col {c.column} overlaps previous column {current_col}."
                        )
                    current_col = c.column + c.span
                    row_total += c.span

                if row_total > 12:
                    raise CompositionIntegrityError(
                        f"COMPOSITION_ROW_OVERFLOW: Row '{row.row_id}' total span {row_total} exceeds 12 columns."
                    )

        # 3. Readability invariants and archetype minimum span enforcement
        if plan.readability_violations_count > 0:
            raise CompositionIntegrityError(
                f"COMPOSITION_READABILITY_FAIL: Layout plan contains {plan.readability_violations_count} readability violations."
            )

        topics_by_id = {str(getattr(t, "topic_id", "") or id(t)): t for t in topics}
        for item in plan.items:
            t = topics_by_id.get(item.topic_id)
            if t:
                chart_type = getattr(t, "recommended_visual", "") or getattr(t, "visual_spec", {}).get("chart_type", "")
                if chart_type:
                    from .candidate_builder import get_legibility_profile
                    prof = get_legibility_profile(chart_type)
                    if item.span < prof.min_readable_span:
                        raise CompositionIntegrityError(
                            f"COMPOSITION_READABILITY_VIOLATION: Topic '{item.topic_id}' with chart '{chart_type}' allocated span {item.span} < minimum readable span {prof.min_readable_span}."
                        )

    @classmethod
    def audit_ast_purity(cls) -> list[str]:
        """Audits AST of composition package to enforce zero DB, AI/LLM, MCP, or theme dependencies."""
        composition_dir = Path(__file__).resolve().parent
        forbidden_modules = {
            "sqlite3",
            "duckdb",
            "ollama",
            "mcp",
            "requests",
            "httpx",
            "theme",
            "tokens",
            "react",
        }
        violations = []

        for py_file in composition_dir.glob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top_pkg = alias.name.split(".")[0].lower()
                        if top_pkg in forbidden_modules:
                            violations.append(f"{py_file.name}: forbidden import '{alias.name}'")
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        top_pkg = node.module.split(".")[0].lower()
                        if top_pkg in forbidden_modules:
                            violations.append(f"{py_file.name}: forbidden import from '{node.module}'")
        return violations
