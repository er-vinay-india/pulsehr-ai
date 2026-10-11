"""Gateway package initialization for HighView AI Model Gateway."""

from ...core.models_config import ModelRole, RoleModelConfig, get_role_config
from .contracts import (
    AIExecutionRecord,
    AIRequest,
    AIResponse,
    AITaskType,
    ModelHealthState,
    ReasoningLevel,
    compute_hash,
)
from .model_gateway import GatewayResult, HighviewModelGateway, ModelGateway
from .model_health import ModelHealthService, model_health_service
from .model_router import ModelRouter, TASK_MODEL_CASCADES
from .observability import ExecutionTrace, LineageRecord, trace_registry

__all__ = [
    "ModelRole",
    "RoleModelConfig",
    "get_role_config",
    "AITaskType",
    "ReasoningLevel",
    "ModelHealthState",
    "AIRequest",
    "AIResponse",
    "AIExecutionRecord",
    "compute_hash",
    "ModelGateway",
    "HighviewModelGateway",
    "GatewayResult",
    "ModelRouter",
    "TASK_MODEL_CASCADES",
    "ModelHealthService",
    "model_health_service",
    "ExecutionTrace",
    "LineageRecord",
    "trace_registry",
]
