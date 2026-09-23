"""Gateway package initialization."""

from ...core.models_config import ModelRole, RoleModelConfig, get_role_config
from .model_gateway import ModelGateway, GatewayResult
from .observability import ExecutionTrace, LineageRecord, trace_registry

__all__ = [
    "ModelRole",
    "RoleModelConfig",
    "get_role_config",
    "ModelGateway",
    "GatewayResult",
    "ExecutionTrace",
    "LineageRecord",
    "trace_registry",
]
