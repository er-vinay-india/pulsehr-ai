"""Central ModelRouter providing task-based model selection, latency prioritization, and confidence escalation."""

import logging
from typing import Any
from ...core.models_config import ModelRole
from ..decision_engine.base import DecisionResult

logger = logging.getLogger(__name__)


class ModelRouter:
    """Intelligently routes inference tasks across installed local models based on workload characteristics."""

    @staticmethod
    def route_task(
        task_type: str,
        query: str = "",
        context: dict[str, Any] | None = None,
        latency_priority: bool = False,
        decision_result: DecisionResult | None = None
    ) -> ModelRole:
        """Determines the optimal logical ModelRole for a given workload."""
        # 1. If DecisionEngine already suggested a role, honor it
        if decision_result and decision_result.suggested_role:
            try:
                return ModelRole(decision_result.suggested_role.upper())
            except ValueError:
                pass

        t = task_type.lower().strip()

        # 2. Fast edge tasks: quick metadata, sheet naming, title generation, JSON schema validation
        if t in ("naming", "sheet_naming", "title", "metadata", "schema", "quick", "classification"):
            return ModelRole.FAST

        # 3. Narrative & presentation synthesis: executive summaries, slide narratives, storytelling
        if t in ("narrative", "story", "presentation", "presentation_slide", "writer", "voiceover_script"):
            if latency_priority:
                return ModelRole.FAST
            return ModelRole.WRITER

        # 4. Deep reasoning & root-cause analysis: anomaly investigations, strategic trade-offs, causal reasoning
        if t in ("root_cause", "deep_reasoning", "reasoner", "tradeoff", "critic", "anomaly_escalation"):
            return ModelRole.REASONER

        # 5. Complex text query inspection if task is general copilot
        if t in ("copilot", "chat", "general"):
            q_lower = query.lower()
            if any(k in q_lower for k in ("why", "cause", "trade-off", "tradeoff", "root cause", "explain deeply")):
                return ModelRole.REASONER
            if any(k in q_lower for k in ("draft", "write", "summary email", "memo", "presentation")):
                return ModelRole.WRITER
            if any(k in q_lower for k in ("columns", "schema", "sheets", "dataset name")):
                return ModelRole.FAST

        # 6. Default to ANALYST for structured calculations, rankings, distributions, correlations
        if latency_priority:
            return ModelRole.FAST
        return ModelRole.ANALYST

    @staticmethod
    def should_escalate(
        current_role: ModelRole,
        confidence: float,
        valid_schema: bool = True
    ) -> ModelRole | None:
        """Evaluates whether output from a lightweight model warrants confidence-based escalation to a larger model."""
        if current_role == ModelRole.FAST:
            if not valid_schema or confidence < 0.65:
                logger.info(
                    f"Escalating task from FAST to ANALYST (confidence={confidence:.2f}, valid_schema={valid_schema})"
                )
                return ModelRole.ANALYST

        elif current_role == ModelRole.ANALYST:
            if not valid_schema or confidence < 0.50:
                logger.info(
                    f"Escalating task from ANALYST to REASONER (confidence={confidence:.2f}, valid_schema={valid_schema})"
                )
                return ModelRole.REASONER

        return None
