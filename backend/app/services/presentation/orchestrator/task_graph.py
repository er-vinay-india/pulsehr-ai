"""Execution Task Graph (DAG) for Presentation Execution Orchestration."""

from __future__ import annotations

import datetime
import logging
from typing import Any
from .orchestrator_models import (
    ErrorCategory,
    ExecutionPlan,
    ExecutionTask,
    TaskResult,
    TaskStatus,
)

logger = logging.getLogger(__name__)


class ExecutionTaskGraph:
    """Manages an explicit Directed Acyclic Graph (DAG) of execution tasks with dependency resolution."""

    def __init__(self, tasks: list[ExecutionTask] | None = None):
        self._tasks: dict[str, ExecutionTask] = {}
        self._results: dict[str, TaskResult] = {}
        if tasks:
            for t in tasks:
                self.add_task(t)

    @property
    def tasks(self) -> dict[str, ExecutionTask]:
        return self._tasks

    @classmethod
    def from_execution_plan(cls, plan: ExecutionPlan) -> ExecutionTaskGraph:
        """Constructs an ExecutionTaskGraph instance from an ExecutionPlan."""
        return cls(tasks=plan.tasks)

    def add_task(self, task: ExecutionTask):
        self._tasks[task.task_id] = task

    def get_task(self, task_id: str) -> ExecutionTask | None:
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> list[ExecutionTask]:
        return list(self._tasks.values())

    def get_result(self, task_id: str) -> TaskResult | None:
        return self._results.get(task_id)

    def get_all_results(self) -> dict[str, TaskResult]:
        return dict(self._results)

    def get_ready_tasks(self, completed_results: dict[str, TaskResult] | None = None) -> list[ExecutionTask]:
        """Returns all PENDING tasks whose dependencies have successfully completed."""
        res_pool = completed_results if completed_results is not None else self._results
        ready = []
        for t in self._tasks.values():
            if t.status != TaskStatus.PENDING:
                continue

            dependencies_satisfied = True
            for dep_id in t.dependencies:
                dep_res = res_pool.get(dep_id)
                if not dep_res or dep_res.status != TaskStatus.SUCCESS:
                    dependencies_satisfied = False
                    break

            if dependencies_satisfied:
                ready.append(t)
        return ready

    def mark_completed(self, task_id: str, result: TaskResult):
        if task_id in self._tasks:
            self._tasks[task_id].status = TaskStatus.SUCCESS
            self._tasks[task_id].execution_time_ms = result.execution_time_ms
        self._results[task_id] = result

    def mark_failed(self, task_id: str, error: str, category: ErrorCategory):
        if task_id in self._tasks:
            self._tasks[task_id].status = TaskStatus.FAILED
            self._tasks[task_id].error = error
            self._tasks[task_id].error_category = category

        self.mark_downstream_blocked(task_id)

    def mark_downstream_blocked(self, failed_task_id: str) -> list[str]:
        """Cascades failure: marks downstream tasks dependent on failed_task_id as BLOCKED."""
        blocked = []
        queue = [failed_task_id]
        while queue:
            curr = queue.pop(0)
            for t in self._tasks.values():
                if curr in t.dependencies and t.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                    t.status = TaskStatus.BLOCKED
                    t.error = f"Blocked by failure in dependency task '{curr}'."
                    t.error_category = ErrorCategory.TOOL_FAILURE
                    if t.task_id not in blocked:
                        blocked.append(t.task_id)
                        queue.append(t.task_id)
        return blocked

    def resume_from_completed(self, completed_results: dict[str, TaskResult]):
        """Hydrates the graph with previously completed task results to enable resumability."""
        for tid, res in completed_results.items():
            if tid in self._tasks and res.status == TaskStatus.SUCCESS:
                self._tasks[tid].status = TaskStatus.SUCCESS
                self._results[tid] = res

    def is_complete(self) -> bool:
        """Evaluates whether all tasks have reached a terminal state (SUCCESS, FAILED, BLOCKED, SKIPPED)."""
        return all(t.status in (TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.BLOCKED, TaskStatus.SKIPPED) for t in self._tasks.values())

    def has_failures(self) -> bool:
        return any(t.status in (TaskStatus.FAILED, TaskStatus.BLOCKED) for t in self._tasks.values())

    def detect_cycles(self) -> bool:
        """Kahn's algorithm to verify the graph is a valid DAG and contains no cycles."""
        in_degree: dict[str, int] = {tid: 0 for tid in self._tasks}
        for t in self._tasks.values():
            for dep in t.dependencies:
                if dep in in_degree:
                    in_degree[t.task_id] += 1

        queue = [tid for tid, deg in in_degree.items() if deg == 0]
        visited_count = 0
        while queue:
            curr = queue.pop(0)
            visited_count += 1
            for t in self._tasks.values():
                if curr in t.dependencies:
                    in_degree[t.task_id] -= 1
                    if in_degree[t.task_id] == 0:
                        queue.append(t.task_id)

        return visited_count != len(self._tasks)

    def validate(self) -> None:
        """Raises ValueError if a cycle is detected or if an undefined dependency exists."""
        if self.detect_cycles():
            raise ValueError("Cyclic dependency detected in task graph.")

    def get_topological_order(self) -> list[str]:
        """Returns task IDs in valid topological dependency order using Kahn's algorithm."""
        in_degree: dict[str, int] = {tid: 0 for tid in self._tasks}
        for t in self._tasks.values():
            for dep in t.dependencies:
                if dep in in_degree:
                    in_degree[t.task_id] += 1

        queue = [tid for tid, deg in in_degree.items() if deg == 0]
        order: list[str] = []
        while queue:
            curr = queue.pop(0)
            order.append(curr)
            for t in self._tasks.values():
                if curr in t.dependencies:
                    in_degree[t.task_id] -= 1
                    if in_degree[t.task_id] == 0:
                        queue.append(t.task_id)

        if len(order) != len(self._tasks):
            raise ValueError("Cyclic dependency detected in task graph.")

        return order

    def get_execution_waves(self) -> list[list[ExecutionTask]]:
        """Groups tasks into parallel execution waves where each wave contains mutually independent tasks."""
        if self.detect_cycles():
            raise ValueError("Cannot compute execution waves: Cycle detected in task graph.")

        assigned_wave: dict[str, int] = {}

        def get_task_wave(tid: str, visited: set[str]) -> int:
            if tid in assigned_wave:
                return assigned_wave[tid]
            visited.add(tid)
            t = self._tasks[tid]
            if not t.dependencies:
                wave = 0
            else:
                wave = max(get_task_wave(dep, visited.copy()) for dep in t.dependencies if dep in self._tasks) + 1
            assigned_wave[tid] = wave
            return wave

        for tid in self._tasks:
            get_task_wave(tid, set())

        max_wave = max(assigned_wave.values()) if assigned_wave else -1
        waves: list[list[ExecutionTask]] = [[] for _ in range(max_wave + 1)]
        for tid, w in assigned_wave.items():
            waves[w].append(self._tasks[tid])

        return waves

    def get_tasks_for_slide(self, slide_id: str) -> list[ExecutionTask]:
        return [t for t in self._tasks.values() if t.slide_id == slide_id]

    def to_execution_plan(self, execution_id: str, orchestrator_model: str = "granite4:3b-h") -> ExecutionPlan:
        status = "COMPLETED" if self.is_complete() and not self.has_failures() else ("FAILED" if self.has_failures() else "EXECUTING")
        return ExecutionPlan(
            execution_id=execution_id,
            plan_spec_version="2.0",
            orchestrator_model=orchestrator_model,
            tasks=self.get_all_tasks(),
            status=status,
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            metadata={"total_tasks": len(self._tasks), "completed_tasks": len(self._results)}
        )
