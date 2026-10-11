"""ToolSelectionQualityEvaluator: Evaluates tool precision, recall, and unnecessary calls (Phase D)."""
from __future__ import annotations

import logging
from typing import Any
from ..contracts import ToolSelectionQuality

logger = logging.getLogger(__name__)


class ToolSelectionQualityEvaluator:
    """Computes precision, recall, duplicate rates, and retry counts across workflow tools."""

    @classmethod
    def evaluate(
        cls,
        workflow_name: str,
        tools_executed: list[str],
        expected_tools: list[str] | None = None,
    ) -> ToolSelectionQuality:
        total = len(tools_executed)
        if total == 0:
            return ToolSelectionQuality(
                workflow_name=workflow_name,
                total_tool_calls=0,
                useful_tool_calls=0,
                tool_precision=1.0,
                tool_recall=1.0,
            )

        # Count duplicates
        seen = set()
        duplicates = 0
        for t in tools_executed:
            if t in seen:
                duplicates += 1
            seen.add(t)

        duplicate_rate = round(duplicates / total, 3)

        # Useful tools matching expected
        exp_set = set(expected_tools) if expected_tools else seen
        useful = sum(1 for t in tools_executed if t in exp_set)
        unnecessary = total - useful

        precision = round(useful / total, 3) if total > 0 else 1.0
        recall = round(len(seen.intersection(exp_set)) / len(exp_set), 3) if exp_set else 1.0
        unnecessary_rate = round(unnecessary / total, 3) if total > 0 else 0.0

        return ToolSelectionQuality(
            workflow_name=workflow_name,
            total_tool_calls=total,
            useful_tool_calls=useful,
            tool_precision=precision,
            tool_recall=recall,
            unnecessary_tool_rate=unnecessary_rate,
            duplicate_tool_rate=duplicate_rate,
            same_tool_retry_rate=duplicate_rate,
        )
