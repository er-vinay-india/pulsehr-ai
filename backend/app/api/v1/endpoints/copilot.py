"""V1 API Endpoints alias for copilot router."""
from app.routers.copilot import (
    router,
    CopilotQueryRequest,
    ask_copilot,
    ask_generic_copilot,
    ask_copilot_stream,
    list_models,
    get_query_suggestions,
    calculation_columns,
)

__all__ = [
    "router",
    "CopilotQueryRequest",
    "ask_copilot",
    "ask_generic_copilot",
    "ask_copilot_stream",
    "list_models",
    "get_query_suggestions",
    "calculation_columns",
]
