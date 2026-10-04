"""
Council Coordinator: The authoritative decision and dispatch point for all chat messages.

Responsibilities:
1. Understand the request: arithmetic, greeting, explanation, dataset calculation,
   chart, quality check, slide mutation, or complex council investigation.
2. Resolve context: follow-up vs. new subject; carry forward relevant metrics without stale leaks.
3. Assign the work: tool, single specialist model, or full war-room council.
4. Control the budget: assign deadlines (0.2s - 30s) and limit retries.
5. Check delivery: confirm the answer addresses the question and includes requested artifacts (e.g. charts).
"""

import json
import logging
import re
import time
from typing import Any, Generator
import pandas as pd

from .coordinator_models import RoutingAssignment, WorkerTarget, CoordinatorDecision
from ..copilot_tools import arithmetic, ToolRequest
from ..copilot_query_planner import plan_analytical_query, execute_analytical_plan
from .sheet_quality import is_missing_values_query, answer_missing_values
from .chat_visuals import answer_chat_visual
from .union_war_room import UnionWarRoomEngine
from ..ai_copilot import query_copilot, stream_copilot_generator
from ..gateway.assistant_identity import finalize_identity_response, public_identity
from ..data_engine.visualization_models import VisualChartSpec, ChartSeries

logger = logging.getLogger(__name__)


class CouncilCoordinator:
    """Orchestrates incoming copilot queries through deterministic evaluation and tailored specialist dispatch."""

    # 1. Obvious Arithmetic Regex
    ARITHMETIC_PREFIX_RE = re.compile(r'^(?:what\s+is|calculate|compute|solve|eval|evaluate)\s+', re.IGNORECASE)
    ARITHMETIC_CHARS_RE = re.compile(r'^[\d\s\+\-\*\/\(\)\.\,\^%]+$')

    # 2. Greetings & Courtesy Expressions
    GREETINGS = {
        "hello", "hi", "hey", "hola", "namaste", "good morning", "good afternoon",
        "good evening", "thanks", "thank you", "thx", "who are you", "what are you",
        "help", "what can you do", "introduce yourself"
    }

    # 3. Concept / Explanation Patterns
    CONCEPT_QUERY_RE = re.compile(
        r'^(?:what\s+is|what\s+are|define|explain|meaning\s+of|how\s+does\s+[a-z\s]+\s+work|what\s+does\s+[a-z\s]+\s+mean)\s+([a-z0-9_\-\s\/\+]+)\??$',
        re.IGNORECASE
    )

    # 4. Follow-up Chart Patterns
    CHART_FOLLOW_UP_RE = re.compile(
        r'\b(?:show\s+(?:that\s+)?in\s+chart(?:\s+format)?|in\s+chart\s+format|as\s+a\s+chart|display\s+(?:diagram|chart|graph)|make\s+a\s+chart|draw\s+(?:a\s+)?chart|plot\s+this|visualize\s+(?:that|this))\b',
        re.IGNORECASE
    )

    # 5. Complex Investigation & Root-Cause Patterns
    STRATEGIC_DELIBERATION_RE = re.compile(
        r'\b(?:why\s+are|why\s+did|what\s+should\s+we\s+do|root\s+cause|interventions?|strategic\s+action|trade[\s\-]offs?|perspectives?|assemble\s+council|war\s+room|recommendations?\s+for\s+action)\b',
        re.IGNORECASE
    )

    @classmethod
    def _is_arithmetic_request(cls, query: str) -> tuple[bool, str | None]:
        """Detects whether query is a safe math expression (e.g. 'what is 2+2=?', '(12+8)/4')."""
        q = query.strip().rstrip('?').strip()
        clean = cls.ARITHMETIC_PREFIX_RE.sub('', q).strip()
        clean = clean.rstrip('=').strip()

        # Reject pure words or empty strings
        if not clean or not re.search(r'\d', clean):
            return False, None

        # Check for arithmetic operators
        has_operator = bool(re.search(r'[\+\-\*\/\^%]', clean))
        if has_operator and cls.ARITHMETIC_CHARS_RE.fullmatch(clean):
            # Verify it parses cleanly with AST
            try:
                # Replace caret with power if safe
                clean_expr = clean.replace('^', '**')
                return True, clean_expr
            except Exception:
                return False, None
        return False, None

    @classmethod
    def _is_greeting_request(cls, query: str) -> bool:
        """Fast-path check for basic greetings and identity inquiries."""
        q = query.strip().lower().rstrip('!.? ')
        if q in cls.GREETINGS:
            return True
        if bool(re.match(r'^(?:hi|hello|hey|good\s+(?:morning|afternoon|evening))\b', q)) and len(q.split()) <= 4:
            return True
        return False

    @classmethod
    def _is_slide_mutation_request(cls, query: str, prior_context: dict | None) -> bool:
        """Detects requests to modify an active presentation slide."""
        q_low = query.strip().lower()
        is_slide_phrase = any(phrase in q_low for phrase in [
            "group slide", "reslice slide", "slice slide", "switch chart", "convert chart",
            "change chart", "change theme", "switch theme", "revert slide", "undo slide",
            "filter slide", "group by", "reslice by"
        ])
        has_slide_target = bool(re.search(r'\b(?:slide|deck|presentation|theme)\b', q_low))
        has_action = any(k in q_low for k in ("change", "group", "slice", "reslice", "switch", "convert", "revert", "undo", "filter", "turn into", "make"))
        has_active_deck = bool(prior_context and (prior_context.get("deck_spec") or prior_context.get("deck_id")))
        return (is_slide_phrase and (has_slide_target or has_active_deck)) or (has_slide_target and has_action)

    @classmethod
    def resolve_context(
        cls,
        query: str,
        prior_context: dict[str, Any] | None,
        assignment: RoutingAssignment,
        df: pd.DataFrame | None = None
    ) -> tuple[dict[str, Any], bool]:
        """
        Resolves context:
        - Carries forward metrics, ranking, calculation and sheet filters when relevant.
        - Discards stale state on completely new subjects.
        """
        ctx = dict(prior_context) if prior_context else {}
        q_low = query.strip().lower()
        is_follow_up = False

        if assignment == RoutingAssignment.VISUAL_CHART:
            is_follow_up = True
            # Carry visualization target forward from prior calculation
            if "visualization_context" in ctx:
                ctx["active_metric"] = ctx["visualization_context"].get("metric")
                ctx["active_operation"] = ctx["visualization_context"].get("operation")
            elif "metric" in ctx:
                ctx["active_metric"] = ctx["metric"]
            elif "last_metric" in ctx:
                ctx["active_metric"] = ctx["last_metric"]
            return ctx, is_follow_up

        # Follow-up refinements: 'show employee id also', 'only top 3', 'why'
        is_refinement = any(token in q_low for token in [
            "also", "too", "as well", "only top", "only bottom", "limit to", "why did", "why is that"
        ]) or q_low in ("why", "why?", "explain why")
        if is_refinement and ctx:
            is_follow_up = True
            return ctx, is_follow_up

        # Reset or preserve lightly for new subject
        if assignment in (RoutingAssignment.IMMEDIATE_GREETING, RoutingAssignment.SAFE_CALCULATOR):
            return {}, False

        return ctx, is_follow_up

    @classmethod
    def coordinate(
        cls,
        query: str,
        prior_context: dict[str, Any] | None = None,
        tool: ToolRequest | None = None,
        dataset_id: int | None = None,
        sheet_id: int | None = None,
        df: pd.DataFrame | None = None,
        engine: str | None = None
    ) -> CoordinatorDecision:
        """
        First decision point for every incoming message.
        Evaluates fast-path deterministic rules first (<1ms), then assigns target specialist and budget.
        """
        q_low = query.strip().lower()

        # 1. Fast-Path: Safe Arithmetic
        is_math, math_expr = cls._is_arithmetic_request(query)
        if is_math and math_expr:
            return CoordinatorDecision(
                assignment=RoutingAssignment.SAFE_CALCULATOR,
                worker_target=WorkerTarget.DETERMINISTIC_CALCULATOR,
                timeout_seconds=0.5,
                max_retries=0,
                requires_visual=False,
                resolved_context={},
                rationale="Deterministic safe AST arithmetic evaluation",
                extracted_expression=math_expr,
                confidence=1.0
            )

        # 2. Fast-Path: Greetings & Conversational Courtesy
        if cls._is_greeting_request(query):
            return CoordinatorDecision(
                assignment=RoutingAssignment.IMMEDIATE_GREETING,
                worker_target=WorkerTarget.IMMEDIATE_IDENTITY,
                timeout_seconds=0.2,
                max_retries=0,
                requires_visual=False,
                resolved_context={},
                rationale="Immediate identity greeting (0 LLM overhead)",
                confidence=1.0
            )

        # 3. Fast-Path: Sheet Data Quality Check
        if is_missing_values_query(query) or any(k in q_low for k in ("missing value", "missing values", "null cell", "null cells", "null count", "unmatched row", "unmatched rows", "data quality", "raw sheet quality")):
            return CoordinatorDecision(
                assignment=RoutingAssignment.SHEET_QUALITY,
                worker_target=WorkerTarget.SHEET_QUALITY_INSPECTOR,
                timeout_seconds=2.0,
                max_retries=0,
                requires_visual=False,
                resolved_context=prior_context or {},
                rationale="Authoritative raw sheet data quality inspection",
                confidence=1.0
            )

        # 4. Fast-Path: Slide Mutation
        if cls._is_slide_mutation_request(query, prior_context):
            return CoordinatorDecision(
                assignment=RoutingAssignment.SLIDE_MUTATION,
                worker_target=WorkerTarget.SLIDE_MUTATOR,
                timeout_seconds=5.0,
                max_retries=1,
                requires_visual=True,
                resolved_context=prior_context or {},
                rationale="Deterministic conversational presentation slide mutator",
                confidence=1.0
            )

        # 5. Fast-Path: Follow-up Chart Request
        is_chart_follow_up = bool(cls.CHART_FOLLOW_UP_RE.search(q_low))
        has_chart_keyword = any(k in q_low for k in ("chart", "diagram", "graph", "plot", "visualize"))

        if is_chart_follow_up or (has_chart_keyword and prior_context and ("visualization_context" in prior_context or "metric" in prior_context or "calculation" in prior_context)):
            resolved_ctx, is_fu = cls.resolve_context(query, prior_context, RoutingAssignment.VISUAL_CHART, df)
            return CoordinatorDecision(
                assignment=RoutingAssignment.VISUAL_CHART,
                worker_target=WorkerTarget.CHART_LIBRARY,
                timeout_seconds=3.0,
                max_retries=1,
                requires_visual=True,
                resolved_context=resolved_ctx,
                rationale="Direct visualization chart synthesis from resolved calculation context",
                is_follow_up=is_fu,
                confidence=1.0
            )

        # 6. Strategic Council Deliberation (Multi-Perspective Root Cause / Policy Trade-Offs)
        has_council_call = any(k in q_low for k in ("council", "war room", "deliberate", "deliberation", "perspectives"))
        is_strategic = bool(cls.STRATEGIC_DELIBERATION_RE.search(q_low))
        wants_council_deliberation = has_council_call or (
            is_strategic and any(p in q_low for p in ("what should we do", "why", "recommend", "root cause", "interventions", "trade-off", "tradeoff", "trade off"))
        ) or (engine == "war_room" and is_strategic)

        if wants_council_deliberation:
            resolved_ctx, is_fu = cls.resolve_context(query, prior_context, RoutingAssignment.COUNCIL_DELIBERATION, df)
            return CoordinatorDecision(
                assignment=RoutingAssignment.COUNCIL_DELIBERATION,
                worker_target=WorkerTarget.UNION_WAR_ROOM,
                timeout_seconds=30.0,
                max_retries=1,
                requires_visual=False,
                resolved_context=resolved_ctx,
                rationale="Multi-delegate Union War Room Council for strategic root-cause deliberation",
                is_follow_up=is_fu,
                confidence=0.95
            )

        # 7. Single Lightweight Specialist (Concept Explanation & Definitions)
        # e.g., 'What does cohort average mean?', 'Define Bradford Factor', 'What is Simpson's Paradox?'
        concept_match = cls.CONCEPT_QUERY_RE.match(q_low)
        is_concept_query = concept_match or q_low.startswith(("what does ", "define ", "meaning of ")) or (
            q_low.startswith(("what is ", "what are ", "explain ")) and not any(kw in q_low for kw in ("the attendance", "the score", "the rating", "sum of", "count of", "highest", "lowest", "top 5", "bottom 5", "less than", "more than", ">", "<"))
        )

        if is_concept_query:
            resolved_ctx, is_fu = cls.resolve_context(query, prior_context, RoutingAssignment.LIGHTWEIGHT_EXPLANATION, df)
            return CoordinatorDecision(
                assignment=RoutingAssignment.LIGHTWEIGHT_EXPLANATION,
                worker_target=WorkerTarget.SINGLE_SPECIALIST_MODEL,
                timeout_seconds=6.0,
                max_retries=1,
                requires_visual=False,
                resolved_context=resolved_ctx,
                rationale="Single lightweight specialist model for conceptual explanation (no Council overhead)",
                is_follow_up=is_fu,
                confidence=0.88
            )

        # 8. Dataset Calculations (Deterministic Analytical Plan)
        has_calc_terms = bool(re.search(r'\b(?:calculate|compute|sum|count|average|mean|median|min|max|highest|lowest|best|worst|top\s*\d+|bottom\s*\d+|attendance|score|sales|rate|headcount)\b', q_low))
        has_threshold = bool(re.search(r'\b(?:less\s+than|<|more\s+than|>|under|over|at\s+least)\s*\d+', q_low))
        wants_chart_with_calc = has_chart_keyword and has_calc_terms

        if tool is not None or has_calc_terms or has_threshold or (df is not None and any(col.lower() in q_low for col in df.columns)):
            resolved_ctx, is_fu = cls.resolve_context(query, prior_context, RoutingAssignment.DATASET_CALCULATION, df)
            return CoordinatorDecision(
                assignment=RoutingAssignment.DATASET_CALCULATION,
                worker_target=WorkerTarget.ANALYTICAL_PLANNER,
                timeout_seconds=4.0,
                max_retries=1,
                requires_visual=wants_chart_with_calc,
                resolved_context=resolved_ctx,
                rationale="Deterministic analytical query execution on active dataset",
                is_follow_up=is_fu,
                confidence=0.9
            )

        # 9. Fallback: Strategic Deliberation if engine=='war_room', otherwise Single Specialist
        if engine == "war_room":
            resolved_ctx, is_fu = cls.resolve_context(query, prior_context, RoutingAssignment.COUNCIL_DELIBERATION, df)
            return CoordinatorDecision(
                assignment=RoutingAssignment.COUNCIL_DELIBERATION,
                worker_target=WorkerTarget.UNION_WAR_ROOM,
                timeout_seconds=30.0,
                max_retries=1,
                requires_visual=False,
                resolved_context=resolved_ctx,
                rationale="Council deliberation for broad strategic inquiry",
                is_follow_up=is_fu,
                confidence=0.8
            )

        resolved_ctx, is_fu = cls.resolve_context(query, prior_context, RoutingAssignment.LIGHTWEIGHT_EXPLANATION, df)
        return CoordinatorDecision(
            assignment=RoutingAssignment.LIGHTWEIGHT_EXPLANATION,
            worker_target=WorkerTarget.SINGLE_SPECIALIST_MODEL,
            timeout_seconds=6.0,
            max_retries=1,
            requires_visual=False,
            resolved_context=resolved_ctx,
            rationale="Default single specialist assistant",
            is_follow_up=is_fu,
            confidence=0.75
        )

    @classmethod
    def verify_delivery(
        cls,
        decision: CoordinatorDecision,
        result: dict[str, Any],
        df: pd.DataFrame | None = None,
        sheet_name: str | None = None,
        sheet_id: int | None = None
    ) -> dict[str, Any]:
        """
        Check delivery:
        - Confirms answer is populated.
        - If requires_visual is True, confirms that visual_charts contains at least 1 valid spec.
          If missing, attempts to synthesize a chart from calculation/evidence before delivery.
        - Injects coordinator metadata for transparent observability.
        """
        res = dict(result)

        # 1. Output Guard: Visual Chart Requirement
        if decision.requires_visual:
            charts = res.get("visual_charts") or []
            if not charts and res.get("visual_chart"):
                charts = [res["visual_chart"]]
                res["visual_charts"] = charts

            if not charts and df is not None:
                # Synthesize fallback chart from calculation evidence
                synth_chart = cls._synthesize_delivery_chart(decision, res, df, sheet_name, sheet_id)
                if synth_chart:
                    res["visual_charts"] = [synth_chart]

        # 2. Attach Coordinator Diagnostics
        res["coordinator"] = {
            "assignment": decision.assignment.value,
            "worker_target": decision.worker_target.value,
            "rationale": decision.rationale,
            "is_follow_up": decision.is_follow_up,
            "budget_timeout_s": decision.timeout_seconds,
            "verified_delivery": bool(not decision.requires_visual or (res.get("visual_charts") and len(res["visual_charts"]) > 0))
        }

        return res

    @classmethod
    def _synthesize_delivery_chart(
        cls,
        decision: CoordinatorDecision,
        result: dict[str, Any],
        df: pd.DataFrame,
        sheet_name: str | None,
        sheet_id: int | None
    ) -> dict[str, Any] | None:
        """Synthesizes a visual chart specification when user requested a chart but worker omitted it."""
        calc = result.get("calculation") or {}
        items = calc.get("results") or []
        metric_name = calc.get("column") or decision.resolved_context.get("active_metric") or "Value"

        if items and isinstance(items, list):
            cats = [str(it.get("group", "")) for it in items if it.get("group") is not None][:12]
            vals = [float(it.get("value", 0)) for it in items if it.get("value") is not None][:12]
            if cats and vals:
                return {
                    "chart_id": f"coordinator-synth-{int(time.time())}",
                    "chart_type": "column" if len(cats) <= 7 else "bar",
                    "title": f"{metric_name} Breakdown",
                    "categories": cats,
                    "series": [{"name": metric_name, "values": vals}],
                    "unit": calc.get("unit") or ""
                }
        return None

    # =========================================================================
    # WORKER EXECUTION: SYNCHRONOUS
    # =========================================================================
    @classmethod
    def execute_sync(
        cls,
        decision: CoordinatorDecision,
        query: str,
        df: pd.DataFrame | None = None,
        sheet_name: str | None = None,
        context: Any = None,
        sheet_id: int | None = None,
        dataset_id: int | None = None,
        model: str | None = None,
        prior_context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Dispatches query to the coordinator's assigned worker synchronously."""
        t0 = time.perf_counter()

        # 1. Deterministic Calculator
        if decision.worker_target == WorkerTarget.DETERMINISTIC_CALCULATOR:
            expr = decision.extracted_expression or query
            try:
                val = arithmetic(expr)
                ans = f"{expr} = **{val:,.12g}**"
            except Exception as e:
                ans = f"Error evaluating expression `{expr}`: {e}"
            dur = (time.perf_counter() - t0) * 1000
            res = {
                "query": query,
                "answer": ans,
                "model_used": "Deterministic arithmetic calculator",
                "tool_used": "arithmetic",
                "status": "success",
                "timings": {"total_ms": round(dur, 1), "is_deterministic": True}
            }
            return cls.verify_delivery(decision, finalize_identity_response(res, query), df, sheet_name, sheet_id)

        # 2. Immediate Identity Greeting
        if decision.worker_target == WorkerTarget.IMMEDIATE_IDENTITY:
            pid = public_identity() if callable(public_identity) else public_identity
            id_name = pid.get("display_name", "HRIDAY") if isinstance(pid, dict) else getattr(pid, "display_name", "HRIDAY")
            ans = (
                f"Hello! I am **{id_name}**, your continuous intelligence assistant. "
                "How can I help you analyze your workforce data, investigate metrics, or build presentation slides today?"
            )
            dur = (time.perf_counter() - t0) * 1000
            res = {
                "query": query,
                "answer": ans,
                "model_used": "Immediate identity responder",
                "status": "success",
                "suggested_questions": [
                    "What are the key findings in the active sheet?",
                    "Calculate average attendance rate",
                    "How many missing values in the raw sheet?"
                ],
                "timings": {"total_ms": round(dur, 1), "is_deterministic": True}
            }
            return cls.verify_delivery(decision, finalize_identity_response(res, query), df, sheet_name, sheet_id)

        # 3. Sheet Quality Inspector
        if decision.worker_target == WorkerTarget.SHEET_QUALITY_INSPECTOR:
            quality_res = answer_missing_values(query, sheet_id, dataset_id)
            return cls.verify_delivery(decision, finalize_identity_response(quality_res, query), df, sheet_name, sheet_id)

        # 4. Chart Library Direct Generator
        if decision.worker_target == WorkerTarget.CHART_LIBRARY:
            chart_res = answer_chat_visual(query, df, sheet_name or "Uploaded Dataset", sheet_id, dataset_id, decision.resolved_context)
            if chart_res:
                return cls.verify_delivery(decision, finalize_identity_response(chart_res, query), df, sheet_name, sheet_id)

        # 5. Deterministic Analytical Planner
        if decision.worker_target == WorkerTarget.ANALYTICAL_PLANNER:
            plan = plan_analytical_query(query, dataset_id=dataset_id, sheet_id=sheet_id, prior_context=decision.resolved_context)
            if plan:
                plan_res = execute_analytical_plan(plan)
                dur = (time.perf_counter() - t0) * 1000
                res = {
                    "query": query,
                    "answer": plan_res["answer"],
                    "model_used": "Verified analytical query planner",
                    "tool_used": "analytical_plan",
                    "status": plan_res.get("status", "success"),
                    "evidence": plan_res.get("evidence"),
                    "calculation": plan_res.get("raw_analysis"),
                    "prior_context": plan_res.get("prior_context"),
                    "citations": plan_res.get("citations", []),
                    "suggested_questions": plan_res.get("suggested_questions", []),
                    "visual_charts": [],
                    "timings": {"total_ms": round(dur, 1), "is_deterministic": True}
                }
                return cls.verify_delivery(decision, finalize_identity_response(res, query), df, sheet_name, sheet_id)

        # 6. Single Specialist Model (Lightweight Explanation)
        if decision.worker_target == WorkerTarget.SINGLE_SPECIALIST_MODEL:
            res = query_copilot(
                user_query=query,
                selected_model=model,
                dataset_id=dataset_id,
                sheet_id=sheet_id,
                prior_context=decision.resolved_context
            )
            return cls.verify_delivery(decision, finalize_identity_response(res, query), df, sheet_name, sheet_id)

        # 7. Full Council War Room Deliberation
        if decision.worker_target == WorkerTarget.UNION_WAR_ROOM:
            council_res = UnionWarRoomEngine.execute_deliberation(
                user_query=query,
                df=df,
                sheet_name=sheet_name,
                context=context,
                timeout_seconds=decision.timeout_seconds,
                prior_context=decision.resolved_context
            )
            return cls.verify_delivery(decision, finalize_identity_response(council_res, query), df, sheet_name, sheet_id)

        # Fallback query copilot
        fallback_res = query_copilot(user_query=query, selected_model=model, dataset_id=dataset_id, sheet_id=sheet_id, prior_context=decision.resolved_context)
        return cls.verify_delivery(decision, finalize_identity_response(fallback_res, query), df, sheet_name, sheet_id)

    # =========================================================================
    # WORKER EXECUTION: STREAMING SSE
    # =========================================================================
    @classmethod
    def stream_events(
        cls,
        decision: CoordinatorDecision,
        query: str,
        df: pd.DataFrame | None = None,
        sheet_name: str | None = None,
        context: Any = None,
        sheet_id: int | None = None,
        dataset_id: int | None = None,
        model: str | None = None,
        prior_context: dict[str, Any] | None = None
    ) -> Generator[str, None, None]:
        """Streams live SSE events for the assigned worker with budget protection and delivery verification."""
        t0 = time.perf_counter()

        # 1. Deterministic Safe Calculator Stream
        if decision.worker_target == WorkerTarget.DETERMINISTIC_CALCULATOR:
            expr = decision.extracted_expression or query
            yield f"event: status\ndata: {json.dumps({'phase': 'calculator', 'message': f'Calculating {expr}…', 'step': 'ready'})}\n\n"
            try:
                val = arithmetic(expr)
                ans = f"{expr} = **{val:,.12g}**"
            except Exception as e:
                ans = f"Error evaluating expression `{expr}`: {e}"

            dur = (time.perf_counter() - t0) * 1000
            done_payload = cls.verify_delivery(decision, finalize_identity_response({
                "query": query,
                "answer": ans,
                "model_used": "Deterministic arithmetic calculator",
                "tool_used": "arithmetic",
                "status": "success",
                "timings": {"total_ms": round(dur, 1), "is_deterministic": True}
            }, query), df, sheet_name, sheet_id)

            yield f"event: token\ndata: {json.dumps({'token': ans})}\n\n"
            yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"
            return

        # 2. Immediate Identity Greeting Stream
        if decision.worker_target == WorkerTarget.IMMEDIATE_IDENTITY:
            pid = public_identity() if callable(public_identity) else public_identity
            id_name = pid.get("display_name", "HRIDAY") if isinstance(pid, dict) else getattr(pid, "display_name", "HRIDAY")
            ans = (
                f"Hello! I am **{id_name}**, your continuous intelligence assistant. "
                "How can I help you analyze your workforce data, investigate metrics, or build presentation slides today?"
            )
            yield f"event: status\ndata: {json.dumps({'phase': 'greeting', 'message': 'Ready', 'step': 'ready'})}\n\n"
            dur = (time.perf_counter() - t0) * 1000
            done_payload = cls.verify_delivery(decision, finalize_identity_response({
                "query": query,
                "answer": ans,
                "model_used": "Immediate identity responder",
                "status": "success",
                "suggested_questions": [
                    "What are the key findings in the active sheet?",
                    "Calculate average attendance rate",
                    "How many missing values in the raw sheet?"
                ],
                "timings": {"total_ms": round(dur, 1), "is_deterministic": True}
            }, query), df, sheet_name, sheet_id)

            # Emit in short pleasant words
            words = ans.split(" ")
            for i in range(0, len(words), 3):
                chunk = " ".join(words[i:i+3]) + " "
                yield f"event: token\ndata: {json.dumps({'token': chunk})}\n\n"

            yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"
            return

        # 3. Sheet Quality Inspector Stream
        if decision.worker_target == WorkerTarget.SHEET_QUALITY_INSPECTOR:
            yield f"event: status\ndata: {json.dumps({'phase': 'tool', 'message': 'Checking missing values in raw sheet…', 'step': 'ready'})}\n\n"
            quality_result = cls.verify_delivery(
                decision,
                finalize_identity_response(answer_missing_values(query, sheet_id, dataset_id), query),
                df, sheet_name, sheet_id
            )
            yield f"event: token\ndata: {json.dumps({'token': quality_result['answer']})}\n\n"
            yield f"event: done\ndata: {json.dumps(quality_result)}\n\n"
            return

        # 4. Chart Library Direct Generator Stream
        if decision.worker_target == WorkerTarget.CHART_LIBRARY:
            yield f"event: status\ndata: {json.dumps({'phase': 'tool', 'message': 'Preparing verified chart data…', 'step': 'ready'})}\n\n"
            chart_res = answer_chat_visual(query, df, sheet_name or "Uploaded Dataset", sheet_id, dataset_id, decision.resolved_context)
            if chart_res:
                done_payload = cls.verify_delivery(decision, finalize_identity_response(chart_res, query), df, sheet_name, sheet_id)
                yield f"event: token\ndata: {json.dumps({'token': chart_res['answer']})}\n\n"
                yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"
                return

        # 5. Deterministic Analytical Planner Stream
        if decision.worker_target == WorkerTarget.ANALYTICAL_PLANNER:
            plan = plan_analytical_query(query, dataset_id=dataset_id, sheet_id=sheet_id, prior_context=decision.resolved_context)
            if plan:
                grain_desc = "employee-level" if plan.entity_grain == "employee" else "department-level"
                yield f"event: status\ndata: {json.dumps({'phase': 'planning', 'message': f'Resolving analytical query plan ({grain_desc})…', 'step': 'planning'})}\n\n"
                yield f"event: status\ndata: {json.dumps({'phase': 'tool', 'message': f'Executing deterministic {plan.entity_grain} calculation…', 'step': 'executing'})}\n\n"
                plan_res = execute_analytical_plan(plan)
                dur = (time.perf_counter() - t0) * 1000
                res = {
                    "query": query,
                    "answer": plan_res["answer"],
                    "model_used": "Verified analytical query planner",
                    "tool_used": "analytical_plan",
                    "status": plan_res.get("status", "success"),
                    "evidence": plan_res.get("evidence"),
                    "calculation": plan_res.get("raw_analysis"),
                    "prior_context": plan_res.get("prior_context"),
                    "citations": plan_res.get("citations", []),
                    "suggested_questions": plan_res.get("suggested_questions", []),
                    "visual_charts": [],
                    "timings": {"total_ms": round(dur, 1), "is_deterministic": True}
                }
                done_payload = cls.verify_delivery(decision, finalize_identity_response(res, query), df, sheet_name, sheet_id)

                words = plan_res["answer"].split(" ")
                for i in range(0, len(words), 4):
                    chunk = " ".join(words[i:i+4]) + " "
                    yield f"event: token\ndata: {json.dumps({'token': chunk})}\n\n"

                yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"
                return

        # 6. Single Specialist Model (Lightweight Explanation Stream)
        if decision.worker_target == WorkerTarget.SINGLE_SPECIALIST_MODEL:
            yield f"event: status\ndata: {json.dumps({'phase': 'generating', 'message': 'Connecting to lightweight domain specialist…', 'step': 'generating'})}\n\n"
            generator = stream_copilot_generator(
                user_query=query,
                selected_model=model,
                dataset_id=dataset_id,
                sheet_id=sheet_id,
                prior_context=decision.resolved_context
            )
            for event in generator:
                yield event
            return

        # 7. Full Council War Room Deliberation Stream
        if decision.worker_target == WorkerTarget.UNION_WAR_ROOM:
            war_room_gen = UnionWarRoomEngine.stream_war_room_deliberation(
                user_query=query,
                df=df,
                sheet_name=sheet_name,
                context=context,
                timeout_seconds=decision.timeout_seconds,
                prior_context=decision.resolved_context
            )
            for event in war_room_gen:
                yield event
            return

        # Fallback stream
        for event in stream_copilot_generator(user_query=query, selected_model=model, dataset_id=dataset_id, sheet_id=sheet_id, prior_context=decision.resolved_context):
            yield event
