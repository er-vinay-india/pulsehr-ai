import hashlib
import json
import logging
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

logger = logging.getLogger(__name__)

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


def _load_active_sheet_dataframe(sheet_id: int | None = None, dataset_id: int | None = None) -> tuple[pd.DataFrame | None, str | None, AnalysisContext | None, int | None]:
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
                return pd.DataFrame(records), sheet['display_name'] or sheet['name'], ctx, sheet['id']
    return None, None, None, None


def _answer_from_shared_findings(query: str, sheet_id: int, dataset_name: str) -> dict | None:
    """Answers high-level management questions directly from the authoritative Shared Findings Store (T30, T31)."""
    q_low = query.lower()
    is_top_points = any(phrase in q_low for phrase in ["top 3", "top three", "top points", "top findings", "key findings", "summary", "overview"])
    is_worst_dept = any(phrase in q_low for phrase in ["worst department", "worst team", "worst unit", "lowest department", "which department"])

    if not (is_top_points or is_worst_dept):
        return None

    try:
        from ..services.adaptive_dashboard.findings import get_shared_findings_for_sheet
        findings = get_shared_findings_for_sheet(sheet_id)
        if not findings:
            return None

        if is_top_points:
            top_3 = findings[:3]
            lines = [f"### Top 3 Verified Findings for {dataset_name}\n"]
            citations = []
            for i, f in enumerate(top_3, 1):
                lines.append(f"{i}. **{f.short_business_title}** ({f.formatted_value}): {f.evidence_bound_observation}")
                lines.append(f"   - *Action*: {f.one_next_check_or_action}")
                citations.append({
                    "fact_id": f.finding_id,
                    "type": "unified_finding",
                    "calculation_id": f.calculation_id,
                })
            return {
                "query": query,
                "answer": "\n".join(lines),
                "model_used": "shared_findings_store",
                "citations": citations,
                "exact_matches": [],
                "suggested_questions": [
                    "Which department has the lowest attendance rate?",
                    "What are the verified ledger reconciliation findings?",
                ],
                "visual_charts": [],
                "related_rows": len(findings),
                "timings": {"total_ms": 1.0, "llm_calls": 0, "is_deterministic": True},
                "engine": "shared_findings",
                "metadata": {"source": "shared_findings_store", "sheet_id": sheet_id},
            }

        if is_worst_dept:
            focus = next((f for f in findings if f.decision_category == "segment_disparity"), None)
            if focus:
                ans = (
                    f"### Department Attendance Reliability Priority\n\n"
                    f"**Focus Unit**: {focus.short_business_title}\n\n"
                    f"- **Observation**: {focus.evidence_bound_observation}\n"
                    f"- **Context & Benchmark**: {focus.comparison_and_effect or 'Workforce benchmark comparison'}\n"
                    f"- **Population**: {focus.population_or_exposure}\n"
                    f"- **Recommended Next Step**: {focus.one_next_check_or_action}\n\n"
                    f"*Note: This prioritization reflects the greatest verified rate disparity below the workforce benchmark. "
                    f"It does not imply an individual performance deficit or policy violation.*"
                )
                return {
                    "query": query,
                    "answer": ans,
                    "model_used": "shared_findings_store",
                    "citations": [{
                        "fact_id": focus.finding_id,
                        "type": "unified_finding",
                        "calculation_id": focus.calculation_id,
                    }],
                    "exact_matches": [],
                    "suggested_questions": ["What are the top 3 overall points?"],
                    "visual_charts": [],
                    "related_rows": 1,
                    "timings": {"total_ms": 1.0, "llm_calls": 0, "is_deterministic": True},
                    "engine": "shared_findings",
                    "metadata": {"source": "shared_findings_store", "sheet_id": sheet_id},
                }
    except Exception as exc:
        logger.warning(f"Could not retrieve shared findings for copilot: {exc}")
        return None

    return None


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

    try:
        grounded = GenericCopilotEngine.answer_query(
            df=df,
            profile=profile,
            user_query=req.query,
            existing_interpretation=existing_interp,
            context=context
        )
    except Exception as exc:
        logger.warning(f"Generic copilot execution failed, applying deterministic fallback per T29: {exc}")
        return {
            "query": req.query,
            "answer": f"Evaluated {len(df)} records across {len(profile.columns)} columns in {dataset_name}. Analysis completed with deterministic summary fallback.",
            "model_used": "deterministic_fallback",
            "citations": [],
            "exact_matches": [],
            "suggested_questions": ["What are the summary statistics of this dataset?"],
            "visual_charts": [],
            "related_rows": len(df),
            "timings": {"total_ms": round((time.perf_counter() - t_start) * 1000, 1), "llm_calls": 0, "is_deterministic": True},
            "engine": "generic_fallback",
            "metadata": {"fallback": True, "error": str(exc)},
        }

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
    df, name, ctx, sid = _load_active_sheet_dataframe(req.sheet_id, req.dataset_id)
    if df is None or df.empty:
        raise HTTPException(400, "No active tabular dataset found. Please upload a dataset first.")
    if sid is not None:
        direct_ans = _answer_from_shared_findings(req.query, sid, name or "Uploaded Dataset")
        if direct_ans is not None:
            return direct_ans
    return _execute_generic_copilot(req, df, name or "Uploaded Dataset", context=ctx)


@router.post("/query")
def ask_copilot(req: CopilotQueryRequest):
    """
    SHARED route:
    - If engine == 'generic': routes strictly through GenericCopilotEngine.
    - If engine == 'legacy': routes to legacy query_copilot.
    - If engine == 'auto': deterministically checks for legacy HR terms vs active tabular sheet.
    """
    df, name, ctx, sid = _load_active_sheet_dataframe(req.sheet_id, req.dataset_id)
    if sid is not None:
        direct_ans = _answer_from_shared_findings(req.query, sid, name or "Uploaded Dataset")
        if direct_ans is not None:
            return direct_ans

    if req.engine == "generic":
        if df is not None and not df.empty:
            return _execute_generic_copilot(req, df, name or "Uploaded Dataset", context=ctx)
        raise HTTPException(400, "No active tabular dataset found. Please upload a dataset first.")

    if req.engine == "auto" and not _is_explicit_legacy_hr_request(req):
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
    df, name, ctx, sid = _load_active_sheet_dataframe(req.sheet_id, req.dataset_id)
    if sid is not None:
        direct_ans = _answer_from_shared_findings(req.query, sid, name or "Uploaded Dataset")
        if direct_ans is not None:
            def _direct_stream():
                yield f"event: status\ndata: {json.dumps({'status': 'Authoritative shared findings loaded', 'step': 'ready'})}\n\n"
                answer = direct_ans["answer"]
                words = answer.split(" ")
                for i in range(0, len(words), 4):
                    chunk = " ".join(words[i:i+4]) + " "
                    yield f"event: token\ndata: {json.dumps({'token': chunk})}\n\n"
                yield f"event: done\ndata: {json.dumps(direct_ans)}\n\n"
            return StreamingResponse(
                _direct_stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
            )

    if req.engine == "generic" or (req.engine == "auto" and not _is_explicit_legacy_hr_request(req)):
        if df is not None and not df.empty:
            result = _execute_generic_copilot(req, df, name or "Uploaded Dataset", context=ctx)
            def _generic_stream():
                yield f"event: status\ndata: {json.dumps({'status': 'Grounded in verified candidate facts', 'step': 'ready'})}\n\n"
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
