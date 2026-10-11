"""Lightweight, deterministic StateGraph execution engine for HRIDAY (Phase C).

Implements the LangGraph execution model:
- Explicit node registration (add_node)
- Static transitions (add_edge)
- Dynamic branch routing (add_conditional_edges)
- State immutability & validation (HighviewAgentState)
- Human-in-the-loop interrupt and resumption (GraphInterrupt, resume)
- Hard step count limits to prevent infinite loops (WorkflowLoopLimits)
"""
from __future__ import annotations

import logging
from typing import Any, Callable
from .guards import WorkflowLoopLimits, evaluate_loop_guards
from .state import HighviewAgentState

logger = logging.getLogger(__name__)

START = "__start__"
END = "__end__"


class GraphInterrupt(Exception):
    """Raised when a workflow node pauses for human confirmation or external review."""
    def __init__(self, state: HighviewAgentState, reason: str = "Human approval required"):
        super().__init__(reason)
        self.state = state
        self.reason = reason


class CompiledGraph:
    """Compiled state graph ready for workflow execution."""

    def __init__(
        self,
        nodes: dict[str, Callable[[HighviewAgentState], HighviewAgentState | dict[str, Any]]],
        edges: dict[str, str],
        conditional_edges: dict[str, tuple[Callable[[HighviewAgentState], str], dict[str, str] | None]],
        entry_point: str,
    ):
        self.nodes = nodes
        self.edges = edges
        self.conditional_edges = conditional_edges
        self.entry_point = entry_point

    def invoke(self, state: HighviewAgentState) -> HighviewAgentState:
        """Executes the workflow graph starting from the entry point until END or GraphInterrupt."""
        current_node = self.entry_point
        current_state = state.model_copy(deep=True)

        while current_node != END:
            # 1. Enforce step limit guard
            is_valid, violation = evaluate_loop_guards(current_state)
            if not is_valid:
                logger.warning(f"Workflow hit loop boundary: {violation}. Diverting to FAIL_SAFE.")
                current_state.workflow_status = "FAILED_SAFE"
                current_state.error = violation
                if not current_state.final_answer:
                    current_state.final_answer = (
                        f"Execution paused safely: {violation}. "
                        f"Verified {len(current_state.evidence_ids)} empirical evidence items."
                    )
                break

            current_state.step_count += 1
            node_fn = self.nodes.get(current_node)
            if not node_fn:
                raise ValueError(f"Graph node '{current_node}' is not registered.")

            logger.debug(f"[LangGraph] Executing node '{current_node}' (step {current_state.step_count})")

            # 2. Execute node action
            try:
                res = node_fn(current_state)
                if isinstance(res, HighviewAgentState):
                    current_state = res
                elif isinstance(res, dict):
                    # Partial state update
                    current_state = current_state.model_copy(update=res, deep=True)
            except GraphInterrupt:
                # Re-raise for approval or human intervention
                raise
            except Exception as exc:
                logger.exception(f"Error executing graph node '{current_node}': {exc}")
                current_state.error = str(exc)
                current_state.workflow_status = "PARTIAL"
                break

            # 3. Check if node requested human approval pause
            if current_state.pending_approval and current_state.workflow_status == "REVIEW_REQUIRED":
                logger.info(f"Node '{current_node}' requested approval. Pausing graph execution.")
                raise GraphInterrupt(current_state, "Paused for human approval")

            # 4. Resolve next transition
            if current_node in self.conditional_edges:
                cond_fn, path_map = self.conditional_edges[current_node]
                decision = cond_fn(current_state)
                next_node = path_map.get(decision, decision) if path_map else decision
            elif current_node in self.edges:
                next_node = self.edges[current_node]
            else:
                next_node = END

            current_node = next_node

        if current_state.workflow_status == "IN_PROGRESS":
            current_state.workflow_status = "COMPLETED"

        return current_state

    def resume(self, paused_state: HighviewAgentState, approval_granted: bool) -> HighviewAgentState:
        """Resumes a paused workflow following a human approval decision."""
        resumed_state = paused_state.model_copy(deep=True)
        resumed_state.pending_approval = None

        if approval_granted:
            resumed_state.workflow_status = "IN_PROGRESS"
            # Route to next action following approval
            next_entry = self.edges.get("approval", END)
            # Re-compile mini graph from next entry
            sub_graph = CompiledGraph(
                nodes=self.nodes,
                edges=self.edges,
                conditional_edges=self.conditional_edges,
                entry_point=next_entry,
            )
            return sub_graph.invoke(resumed_state)
        else:
            resumed_state.workflow_status = "DENIED"
            resumed_state.final_answer = "Action denied by human approver. Workflow terminated safely."
            return resumed_state


class StateGraph:
    """Builder class for defining typed workflow graphs."""

    def __init__(self, state_schema: type[HighviewAgentState] = HighviewAgentState):
        self.state_schema = state_schema
        self.nodes: dict[str, Callable[[HighviewAgentState], Any]] = {}
        self.edges: dict[str, str] = {}
        self.conditional_edges: dict[str, tuple[Callable[[HighviewAgentState], str], dict[str, str] | None]] = {}
        self.entry_point: str = START

    def add_node(self, name: str, func: Callable[[HighviewAgentState], Any]) -> StateGraph:
        """Registers a named node function."""
        self.nodes[name] = func
        return self

    def add_edge(self, from_node: str, to_node: str) -> StateGraph:
        """Registers a deterministic transition between nodes."""
        if from_node == START:
            self.entry_point = to_node
        else:
            self.edges[from_node] = to_node
        return self

    def add_conditional_edges(
        self,
        source: str,
        condition: Callable[[HighviewAgentState], str],
        path_map: dict[str, str] | None = None,
    ) -> StateGraph:
        """Registers dynamic conditional transitions out of a node."""
        self.conditional_edges[source] = (condition, path_map)
        return self

    def set_entry_point(self, node_name: str) -> StateGraph:
        """Designates the starting node of the graph."""
        self.entry_point = node_name
        return self

    def compile(self) -> CompiledGraph:
        """Compiles the defined nodes and transitions into an executable CompiledGraph."""
        return CompiledGraph(
            nodes=self.nodes,
            edges=self.edges,
            conditional_edges=self.conditional_edges,
            entry_point=self.entry_point,
        )
