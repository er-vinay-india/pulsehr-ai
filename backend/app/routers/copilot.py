from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from ..services.copilot_tools import ToolRequest, CalculationRequest, load_frame
from ..services.ai_copilot import query_copilot, get_available_models

router = APIRouter(prefix="/api/copilot", tags=["copilot"])

class CopilotQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    model: str | None = None
    tool: ToolRequest | None = None

@router.post("/query")
def ask_copilot(req: CopilotQueryRequest):
    return query_copilot(req.query, req.model, req.tool)

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
