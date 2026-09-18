from fastapi import APIRouter
from pydantic import BaseModel
from ..services.ai_copilot import query_copilot, get_available_models

router = APIRouter(prefix="/api/copilot", tags=["copilot"])

class CopilotQueryRequest(BaseModel):
    query: str
    model: str | None = None

@router.post("/query")
def ask_copilot(req: CopilotQueryRequest):
    return query_copilot(req.query, req.model)

@router.get("/models")
def list_models():
    return {"models": get_available_models()}

@router.get("/suggestions")
def get_query_suggestions():
    return {
        "suggestions": [
            "How many absent days were recorded in employee_absent_data.csv?",
            "Who has severe overtime in the latest performance sheet?",
            "Which employees have performance notes or attendance disconnects?",
            "Compare attendance rates across Engineering, Product, and Sales",
            "Who are the top candidates for recognition bonuses?",
            "Summarize workforce punctuality trends and key recommendations"
        ]
    }
