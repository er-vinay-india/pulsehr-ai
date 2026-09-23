from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from ..services.copilot_tools import ToolRequest, CalculationRequest, load_frame
from ..services.ai_copilot import query_copilot, get_available_models, stream_copilot_generator

router = APIRouter(prefix="/api/copilot", tags=["copilot"])

class CopilotQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    model: str | None = None
    tool: ToolRequest | None = None
    dataset_id: int | None = None
    sheet_id: int | None = None
    prior_context: dict | None = None

@router.post("/query")
def ask_copilot(req: CopilotQueryRequest):
    return query_copilot(req.query, req.model, req.tool, req.dataset_id, req.sheet_id, req.prior_context)

@router.post("/query/stream")
def ask_copilot_stream(req: CopilotQueryRequest):
    """Streams token chunks and status updates as Server-Sent Events."""
    return StreamingResponse(
        stream_copilot_generator(
            user_query=req.query,
            selected_model=req.model,
            tool=req.tool,
            dataset_id=req.dataset_id,
            sheet_id=req.sheet_id,
            prior_context=req.prior_context
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.get("/models")
def list_models():
    return {"models": get_available_models()}

@router.get("/suggestions")
def get_query_suggestions():
    return {
        "suggestions": [
            "Summarize the uploaded sheets and their available metrics",
            "Which sheets have related records?",
            "Create a presentation",
            "Calculate (12 + 8) / 4"
        ]
    }


@router.get("/calculation-columns")
def calculation_columns(dataset_id: int | None = None, sheet: str | None = None, relationship_id: int | None = None):
    try:
        frame, source = load_frame(CalculationRequest(dataset_id=dataset_id, sheet=sheet, relationship_id=relationship_id))
        return {"columns": list(frame.columns), "source": source, "rows": len(frame)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
