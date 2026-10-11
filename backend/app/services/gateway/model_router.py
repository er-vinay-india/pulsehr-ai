"""Central ModelRouter providing task-based model selection, latency prioritization, and confidence escalation."""

import logging
from typing import Any
from ...core import config
from ...core.models_config import ModelRole, get_role_config
from ..decision_engine.base import DecisionResult
from .contracts import AIRequest, AITaskType, ReasoningLevel
from .model_health import model_health_service

logger = logging.getLogger(__name__)


# Default model candidates per governed AI task taxonomy
TASK_MODEL_CASCADES: dict[AITaskType, list[str]] = {
    AITaskType.STRUCTURAL_AI: [
        "phi4-mini:latest",
        "qwen3.5:2b",
        "llama3.1:8b"
    ],
    AITaskType.SEMANTIC_AI: [
        "qwen3.5:2b",
        "phi4-mini:latest",
        "qwen3.5:9b"
    ],
    AITaskType.NARRATIVE_AI: [
        "gemma4:12b",
        "qwen3.5:9b",
        "phi4-mini:latest"
    ],
    AITaskType.AGENTIC_AI: [
        "qwen3.5:9b",
        "gemma4:12b",
        "phi4-mini:latest"
    ],
    AITaskType.PRESENTATION_AI: [
        "gemma4:12b",
        "qwen3.5:9b",
        "phi4-mini:latest"
    ],
    AITaskType.DETERMINISTIC_CALCULATION: []  # 100% bypass - no model needed
}


class ModelRouter:
    """Intelligently routes inference tasks across installed local models based on workload characteristics."""

    @staticmethod
    def route_ai_request(request: AIRequest) -> list[str]:
        """Returns ordered, health-aware candidate model cascade for a typed AIRequest."""
        # 1. Deterministic calculation strictly returns empty list (NO MODEL)
        if request.task_type == AITaskType.DETERMINISTIC_CALCULATION:
            return []

        # 2. Start with user/request override if specified
        candidates: list[str] = []
        if request.model_override:
            candidates.append(request.model_override)

        # 3. High reasoning level or deep investigative queries promote DeepSeek-R1
        if request.reasoning_level == ReasoningLevel.HIGH:
            deepseek_model = getattr(config, "MODEL_ROLE_REASONER_PRIMARY", "deepseek-r1:7b")
            if deepseek_model not in candidates:
                candidates.append(deepseek_model)
            qwen_model = getattr(config, "MODEL_ROLE_ANALYST_PRIMARY", "qwen3.5:9b")
            if qwen_model not in candidates:
                candidates.append(qwen_model)

        # 4. Pull base cascade for the assigned AITaskType
        base_cascade = TASK_MODEL_CASCADES.get(request.task_type, ["qwen3.5:9b", "phi4-mini:latest"])
        for m in base_cascade:
            if m not in candidates:
                candidates.append(m)

        # 5. Low latency budget prioritization: if budget < 12 seconds, ensure fast model is upfront
        if request.max_latency_ms < 12000.0 and request.reasoning_level != ReasoningLevel.HIGH:
            fast_model = "phi4-mini:latest"
            if fast_model in candidates:
                candidates.remove(fast_model)
                candidates.insert(0, fast_model)

        # 6. Append system default model as ultimate fallback if not present
        sys_default = getattr(config, "OLLAMA_MODEL", "qwen3.5:2b")
        if sys_default not in candidates:
            candidates.append(sys_default)

        # 7. Health-aware re-ordering: sort healthy models ahead of degraded models
        healthy: list[str] = []
        degraded: list[str] = []
        for m in candidates:
            if model_health_service.is_healthy(m):
                healthy.append(m)
            else:
                degraded.append(m)

        # Retain healthy first; keep degraded at the tail as a last-resort fallback
        ordered = healthy + degraded
        return ordered

    @staticmethod
    def route_task(
        task_type: str,
        query: str = "",
        context: dict[str, Any] | None = None,
        latency_priority: bool = False,
        decision_result: DecisionResult | None = None
    ) -> ModelRole:
        """Determines the optimal logical ModelRole for a given workload (legacy compatibility)."""
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
