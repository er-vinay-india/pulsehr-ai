import hashlib
import json
import time
from typing import Literal
import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..db.database import get_connection
from ..services.copilot_tools import ToolRequest, CalculationRequest, load_frame
from ..services.ai_copilot import query_copilot, get_available_models, stream_copilot_generator
from ..services.data_engine.semantic_classifier import SemanticClassifier
from ..services.copilot.generic_copilot_engine import GenericCopilotEngine
from ..services.data_engine.analysis_context import AnalysisContext
from ..services.reporting.workflow_orchestrator import _GENERIC_WORKFLOW_CACHE

router = APIRouter(prefix="/api/copilot", tags=["copilot"])


class CopilotQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    model: str | None = None
    tool: ToolRequest | None = None
    dataset_id: int | None = None
    sheet_id: int | None = None
    prior_context: dict | None = None
    snapshot_id: str | None = None
    page: str | None = None
    engine: Literal["generic", "legacy", "auto"] = "auto"


def _load_active_sheet_dataframe(sheet_id: int | None = None, dataset_id: int | None = None) -> tuple[pd.DataFrame | None, str | None, AnalysisContext | None]:
    """Loads active or requested tabular sheet as DataFrame and associated AnalysisContext from database."""
    with get_connection() as conn:
        sheet = None
        if sheet_id is not None:
            sheet = conn.execute(
                'SELECT s.*, d.original_name, d.analysis_context_json as d_ctx FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id WHERE s.id=?',
                (sheet_id,)
            ).fetchone()
        elif dataset_id is not None:
            sheet = conn.execute(
                'SELECT s.*, d.original_name, d.analysis_context_json as d_ctx FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id WHERE s.dataset_id=? ORDER BY s.id ASC LIMIT 1',
                (dataset_id,)
            ).fetchone()
        else:
            sheet = conn.execute(
                'SELECT s.*, d.original_name, d.analysis_context_json as d_ctx FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id ORDER BY s.id DESC LIMIT 1'
            ).fetchone()

        if sheet:
            rows = conn.execute('SELECT data_json FROM sheet_rows WHERE sheet_id=? ORDER BY row_index', (sheet['id'],)).fetchall()
            records = [json.loads(r['data_json']) for r in rows]
            if records:
                ctx = None
                ctx_raw = None
                try:
                    ctx_raw = sheet['analysis_context_json'] or sheet['d_ctx']
                except Exception:
                    pass
                if ctx_raw:
                    try:
                        ctx = AnalysisContext.model_validate_json(ctx_raw)
                    except Exception:
                        pass
                return pd.DataFrame(records), sheet['display_name'] or sheet['name'], ctx
    return None, None, None


def _execute_generic_copilot(req: CopilotQueryRequest, df: pd.DataFrame, dataset_name: str, context: AnalysisContext | None = None) -> dict:
    """Executes query strictly via GenericCopilotEngine with 0 legacy code invocation."""
    t_start = time.perf_counter()
    profile = SemanticClassifier.profile_dataset(df, dataset_name=dataset_name)

    # Check if existing workflow execution is cached for this dataset
    cache_key = hashlib.sha256(
        f"{dataset_name}_Executive Leadership Briefing_{df.shape}_{list(df.columns)}_{df.iloc[:5].to_dict() if len(df) else ''}".encode()
    ).hexdigest()
    cached = _GENERIC_WORKFLOW_CACHE.get(cache_key)
    existing_interp = cached.interpretation if cached else None

    grounded = GenericCopilotEngine.answer_query(
        df=df,
        profile=profile,
        user_query=req.query,
        existing_interpretation=existing_interp,
        context=context
    )
    duration_ms = (time.perf_counter() - t_start) * 1000

    return {
        "query": req.query,
        "answer": grounded.answer_markdown,
        "model_used": "generic_copilot_engine" if grounded.metadata.get("llm_calls", 0) == 0 else "qwen2.5:latest",
        "citations": [{"fact_id": f.fact_id, "type": "verified_candidate_fact"} for f in grounded.cited_facts],
        "exact_matches": [],
        "suggested_questions": grounded.followup_questions,
        "visual_charts": [grounded.recommended_chart.model_dump()] if grounded.recommended_chart else [],
        "related_rows": len(df),
        "timings": {
            "total_ms": round(duration_ms, 1),
            "llm_calls": grounded.metadata.get("llm_calls", 0),
            "is_deterministic": grounded.metadata.get("llm_calls", 0) == 0
        },
        "engine": "generic",
        "metadata": grounded.metadata
    }


def _is_explicit_legacy_hr_request(req: CopilotQueryRequest) -> bool:
    """Determines whether a query specifically targets legacy HR functionality."""
    if req.page == "employees":
        return True
    if req.tool and getattr(req.tool, "operation", "") in ("headcount", "attendance", "absenteeism", "overtime_matrix"):
        return True
    q_lower = req.query.lower()
    explicit_hr_terms = ["headcount", "absenteeism", "overtime matrix", "employee directory", "punch in", "shift attendance", "attrition risk"]
    if any(term in q_lower for term in explicit_hr_terms) and req.sheet_id is None and req.dataset_id is None:
        return True
    return False


@router.post("/generic")
def ask_generic_copilot(req: CopilotQueryRequest):
    """GENERIC route: strictly executes via GenericCopilotEngine."""
    df, name, ctx = _load_active_sheet_dataframe(req.sheet_id, req.dataset_id)
    if df is None or df.empty:
        raise HTTPException(400, "No active tabular dataset found. Please upload a dataset first.")
    return _execute_generic_copilot(req, df, name or "Uploaded Dataset", context=ctx)


@router.post("/query")
def ask_copilot(req: CopilotQueryRequest):
    """
    SHARED route:
    - If engine == 'generic': routes strictly through GenericCopilotEngine.
    - If engine == 'legacy': routes to legacy query_copilot.
    - If engine == 'auto': deterministically checks for legacy HR terms vs active tabular sheet.
    """
    if req.engine == "generic":
        df, name, ctx = _load_active_sheet_dataframe(req.sheet_id, req.dataset_id)
        if df is not None and not df.empty:
            return _execute_generic_copilot(req, df, name or "Uploaded Dataset", context=ctx)
        raise HTTPException(400, "No active tabular dataset found. Please upload a dataset first.")

    if req.engine == "auto" and not _is_explicit_legacy_hr_request(req):
        df, name, ctx = _load_active_sheet_dataframe(req.sheet_id, req.dataset_id)
        if df is not None and not df.empty:
            return _execute_generic_copilot(req, df, name or "Uploaded Dataset", context=ctx)

    # Explicit legacy HR route or fallback
    return query_copilot(
        user_query=req.query,
        selected_model=req.model,
        tool=req.tool,
        dataset_id=req.dataset_id,
        sheet_id=req.sheet_id,
        prior_context=req.prior_context,
        snapshot_id=req.snapshot_id,
        page=req.page
    )


@router.post("/query/stream")
def ask_copilot_stream(req: CopilotQueryRequest):
    """
    SHARED route: Streams token chunks and status updates as Server-Sent Events.
    Uses GenericCopilotEngine if targeting generic tabular data, otherwise legacy stream generator.
    """
    if req.engine == "generic" or (req.engine == "auto" and not _is_explicit_legacy_hr_request(req)):
        df, name, ctx = _load_active_sheet_dataframe(req.sheet_id, req.dataset_id)
        if df is not None and not df.empty:
            result = _execute_generic_copilot(req, df, name or "Uploaded Dataset", context=ctx)
            def _generic_stream():
                yield f"event: status\ndata: {json.dumps({'status': 'Grounded in verified candidate facts', 'step': 'ready'})}\n\n"
                # Stream the markdown answer in small chunks
                answer = result["answer"]
                words = answer.split(" ")
                for i in range(0, len(words), 4):
                    chunk = " ".join(words[i:i+4]) + " "
                    yield f"event: token\ndata: {json.dumps({'token': chunk})}\n\n"
                yield f"event: done\ndata: {json.dumps(result)}\n\n"
            return StreamingResponse(
                _generic_stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
            )

    return StreamingResponse(
        stream_copilot_generator(
            user_query=req.query,
            selected_model=req.model,
            tool=req.tool,
            dataset_id=req.dataset_id,
            sheet_id=req.sheet_id,
            prior_context=req.prior_context,
            snapshot_id=req.snapshot_id,
            page=req.page
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
