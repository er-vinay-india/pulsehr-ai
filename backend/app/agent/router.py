"""HRIDAY Orchestrator and Intent Router (Phase C).

Routes user inquiries to bounded LangGraph workflows:
1. Quick Answer: Direct analytical queries (ranking, comparison, trend, lookup).
2. Analytical Investigation: Multi-step diagnostic investigations ('why', root cause).
3. Scenario Analysis: Counterfactual policy simulations.
4. Presentation Creation: Grounded slide deck creation.

Records every workflow execution in the thread-safe WorkflowExecutionLedger.
"""
from __future__ import annotations

import logging
import time
from typing import Any
from uuid import uuid4

from .execution_record import (
    WorkflowExecutionLedger,
    WorkflowExecutionRecord,
    WorkflowStatus,
    workflow_execution_ledger,
)
from .graph import CompiledGraph, GraphInterrupt
from .nodes.classify_intent import classify_intent_node
from .state import HighviewAgentState
from .workflows import (
    build_analytical_investigation_graph,
    build_presentation_creation_graph,
    build_quick_answer_graph,
    build_scenario_analysis_graph,
)

logger = logging.getLogger(__name__)


class HRIDAYOrchestrator:
    """Master orchestrator for HRIDAY agentic workflows."""

    def __init__(self, ledger: WorkflowExecutionLedger = workflow_execution_ledger):
        self.ledger = ledger
        self._quick_graph = build_quick_answer_graph()
        self._investigation_graph = build_analytical_investigation_graph()
        self._scenario_graph = build_scenario_analysis_graph()
        self._presentation_graph = build_presentation_creation_graph()

    def select_graph(self, intent: str) -> tuple[str, CompiledGraph]:
        """Routes intent to the designated bounded workflow graph."""
        if intent == "SCENARIO_ANALYSIS":
            return "scenario_analysis", self._scenario_graph
        elif intent == "PRESENTATION_CREATION":
            return "presentation_creation", self._presentation_graph
        elif intent == "MULTI_STEP_ANALYSIS":
            return "analytical_investigation", self._investigation_graph
        else:
            return "quick_answer", self._quick_graph

    def orchestrate(
        self,
        user_query: str,
        dataset_id: int | str = 99767,
        caller: str = "hriday",
        conversation_id: str | None = None,
        active_filters: dict[str, Any] | None = None,
    ) -> HighviewAgentState:
        """Executes the full HRIDAY LangGraph workflow for an inquiry."""
        start_time = time.time()
        req_id = f"req-{uuid4().hex[:10]}"

        filters = dict(active_filters or {})
        filters["caller"] = caller

        state = HighviewAgentState(
            conversation_id=conversation_id or f"conv-{uuid4().hex[:10]}",
            request_id=req_id,
            dataset_id=dataset_id,
            user_query=user_query,
            active_filters=filters,
        )

        # 1. Classify initial intent
        state = classify_intent_node(state)
        wf_name, graph = self.select_graph(state.intent)

        logger.info(f"[HRIDAYOrchestrator] Dispatching query '{user_query}' to workflow '{wf_name}' (intent={state.intent})")

        # 2. Invoke workflow with interrupt safety
        paused = False
        try:
            state = graph.invoke(state)
        except GraphInterrupt as gi:
            logger.info(f"[HRIDAYOrchestrator] Graph execution interrupted for approval: {gi.reason}")
            state = gi.state
            paused = True
        except Exception as exc:
            logger.exception(f"[HRIDAYOrchestrator] Unhandled graph execution failure: {exc}")
            state.workflow_status = "FAILED_SAFE"
            state.error = str(exc)
            state.final_answer = f"Execution paused safely: {exc}"

        end_time = time.time()
        latency_ms = (end_time - start_time) * 1000

        # 3. Record audit trail in execution ledger
        tools_called = [t.get("tool_name") for t in state.tool_history]
        status_enum = (
            WorkflowStatus.REVIEW_REQUIRED if paused
            else WorkflowStatus[state.workflow_status] if state.workflow_status in WorkflowStatus.__members__
            else WorkflowStatus.COMPLETED
        )

        rec = WorkflowExecutionRecord(
            workflow_name=wf_name,
            request_id=state.request_id,
            dataset_id=state.dataset_id,
            tools_called=tools_called,
            evidence_ids=list(state.evidence_ids),
            scenario_ids=list(state.scenario_ids),
            models_used=["gateway-fallback-deterministic"],
            total_latency_ms=latency_ms,
            tool_call_count=len(tools_called),
            final_status=status_enum,
            started_at=start_time,
            completed_at=end_time,
        )
        self.ledger.record_workflow(rec)

        return state

    def resume_workflow(
        self,
        paused_state: HighviewAgentState,
        approval_granted: bool,
    ) -> HighviewAgentState:
        """Resumes a paused workflow after human approval resolution."""
        start_time = time.time()
        wf_name, graph = self.select_graph(paused_state.intent)

        resumed_state = graph.resume(paused_state, approval_granted=approval_granted)
        end_time = time.time()

        tools_called = [t.get("tool_name") for t in resumed_state.tool_history]
        status_enum = (
            WorkflowStatus[resumed_state.workflow_status]
            if resumed_state.workflow_status in WorkflowStatus.__members__
            else WorkflowStatus.COMPLETED
        )

        rec = WorkflowExecutionRecord(
            workflow_name=f"{wf_name}_resumed",
            request_id=resumed_state.request_id,
            dataset_id=resumed_state.dataset_id,
            tools_called=tools_called,
            evidence_ids=list(resumed_state.evidence_ids),
            scenario_ids=list(resumed_state.scenario_ids),
            approvals=[{"granted": approval_granted}],
            total_latency_ms=(end_time - start_time) * 1000,
            tool_call_count=len(tools_called),
            final_status=status_enum,
            started_at=start_time,
            completed_at=end_time,
        )
        self.ledger.record_workflow(rec)

        return resumed_state


hriday_orchestrator = HRIDAYOrchestrator()
