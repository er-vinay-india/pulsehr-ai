"""Central immutable PolicyRegistry for Governed Adaptive Optimization (Phase E)."""
from __future__ import annotations

import logging
import threading
import time
from typing import Any
from .contracts import HighviewPolicy, PolicyStatus

logger = logging.getLogger(__name__)

DEFAULT_POLICY_ID = "POLICY-DEFAULT-001"


class PolicyRegistry:
    """Thread-safe registry indexing active, candidate, and historical Highview policies."""

    def __init__(self):
        self._lock = threading.Lock()
        self._policies: dict[str, HighviewPolicy] = {}
        self._active_policy_id: str = DEFAULT_POLICY_ID
        self._policy_history: list[str] = [DEFAULT_POLICY_ID]

        # Initialize default baseline policy
        default_policy = HighviewPolicy(
            policy_id=DEFAULT_POLICY_ID,
            version_number=1,
            name="Baseline Production Policy",
            description="Initial governed Highview baseline execution policy",
            status=PolicyStatus.ACTIVE,
            created_by="system",
            approval_status="APPROVED",
            approved_by="governance_board",
            approved_at=time.time(),
        )
        self._policies[DEFAULT_POLICY_ID] = default_policy

    def get_active_policy(self) -> HighviewPolicy:
        """Retrieves current active immutable production policy."""
        with self._lock:
            return self._policies[self._active_policy_id]

    def get_policy(self, policy_id: str) -> HighviewPolicy | None:
        """Retrieves a policy by its ID."""
        with self._lock:
            return self._policies.get(policy_id)

    def register_candidate(self, candidate: HighviewPolicy) -> HighviewPolicy:
        """Registers a candidate policy without affecting production execution."""
        with self._lock:
            candidate.status = PolicyStatus.CANDIDATE
            candidate.parent_policy_id = self._active_policy_id
            self._policies[candidate.policy_id] = candidate
        logger.info(f"[PolicyRegistry] Registered candidate policy '{candidate.policy_id}' (v{candidate.version_number})")
        return candidate

    def activate_policy(self, policy_id: str, approved_by: str = "human_admin") -> tuple[bool, str]:
        """Promotes an approved candidate policy to ACTIVE status."""
        with self._lock:
            target = self._policies.get(policy_id)
            if not target:
                return False, f"Policy '{policy_id}' not found."

            if target.status == PolicyStatus.REJECTED:
                return False, f"Cannot activate rejected policy '{policy_id}'."

            old_active_id = self._active_policy_id
            old_active = self._policies.get(old_active_id)
            if old_active:
                old_active.status = PolicyStatus.RETIRED

            target.status = PolicyStatus.ACTIVE
            target.approved_by = approved_by
            target.approved_at = time.time()
            target.approval_status = "APPROVED"

            self._active_policy_id = target.policy_id
            self._policy_history.append(target.policy_id)

        logger.info(f"[PolicyRegistry] Successfully activated policy '{policy_id}' (retired '{old_active_id}')")
        return True, f"Policy '{policy_id}' is now ACTIVE."

    def reject_policy(self, policy_id: str, reason: str = "Rejected by governance") -> None:
        """Marks a candidate policy as REJECTED."""
        with self._lock:
            target = self._policies.get(policy_id)
            if target and target.status == PolicyStatus.CANDIDATE:
                target.status = PolicyStatus.REJECTED
                target.approval_status = f"REJECTED: {reason}"
                logger.info(f"[PolicyRegistry] Candidate policy '{policy_id}' rejected: {reason}")

    def rollback(self, to_policy_id: str | None = None) -> tuple[bool, str]:
        """Rolls back active policy to previous version."""
        with self._lock:
            if len(self._policy_history) < 2 and not to_policy_id:
                return False, "No prior policy available in history for rollback."

            current_id = self._active_policy_id
            target_id = to_policy_id or self._policy_history[-2]

            target_policy = self._policies.get(target_id)
            if not target_policy:
                return False, f"Rollback target policy '{target_id}' does not exist."

            current_policy = self._policies.get(current_id)
            if current_policy:
                current_policy.status = PolicyStatus.RETIRED

            target_policy.status = PolicyStatus.ACTIVE
            self._active_policy_id = target_policy.policy_id
            self._policy_history.append(target_policy.policy_id)

        logger.warning(f"[PolicyRegistry] ROLLED BACK from '{current_id}' to '{target_id}'")
        return True, f"Successfully rolled back to policy '{target_id}'."

    def get_history(self) -> list[str]:
        """Returns sequence of active policy IDs."""
        with self._lock:
            return list(self._policy_history)

    def list_policies(self, status: PolicyStatus | None = None) -> list[HighviewPolicy]:
        """Lists registered policies, optionally filtered by status."""
        with self._lock:
            policies = list(self._policies.values())
        if status:
            policies = [p for p in policies if p.status == status]
        return policies

    def clear_for_test(self) -> None:
        """Resets the registry to clean baseline for tests."""
        with self._lock:
            self._policies.clear()
            self._active_policy_id = DEFAULT_POLICY_ID
            self._policy_history = [DEFAULT_POLICY_ID]

            default_policy = HighviewPolicy(
                policy_id=DEFAULT_POLICY_ID,
                version_number=1,
                name="Baseline Production Policy",
                description="Initial governed Highview baseline execution policy",
                status=PolicyStatus.ACTIVE,
                created_by="system",
                approval_status="APPROVED",
                approved_by="governance_board",
                approved_at=time.time(),
            )
            self._policies[DEFAULT_POLICY_ID] = default_policy


policy_registry = PolicyRegistry()
