from fastapi import APIRouter
from pydantic import BaseModel
from ..services.ai_copilot import query_copilot

router = APIRouter(prefix="/api/copilot", tags=["copilot"])

class CopilotQueryRequest(BaseModel):
    query: str

@router.post("/query")
def ask_copilot(req: CopilotQueryRequest):
    return query_copilot(req.query)

@router.get("/suggestions")
def get_query_suggestions():
    return {
        "suggestions": [
            "Which employees are at severe burnout risk due to excessive overtime?",
            "Identify top performers with attendance under 85%",
            "Compare attendance rates across Engineering, Product, and Sales",
            "Who are the top 5 candidates for recognition bonuses?",
            "Summarize workforce punctuality trends and key recommendations",
            "Generate an executive review summary for the VP of HR"
        ]
    }
