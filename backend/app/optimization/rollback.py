"""Automated anomaly inspection and rollback manager for Governed Adaptive Optimization (Phase E).

Enforces that when live telemetry degrades under an active policy (e.g. Grounding drop,
critical latency spikes, or failed-safe halts), a rollback advisory is raised and
governance can immediately restore the previous immutable baseline policy.
"""
from __future__ import annotations

import logging
import time
from typing import Any
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field

from app.observability.contracts import AITrace, RuntimeAnomaly
from .policy_registry import PolicyRegistry, policy_registry

logger = logging.getLogger(__name__)


class RollbackAdvisory(BaseModel):
    """Advisory recommending rollback of active policy due to detected degradation."""
    model_config = ConfigDict(extra="ignore")

    advisory_id: str = Field(default_factory=lambda: f"adv-rb-{uuid4().hex[:8]}")
    current_policy_id: str
    target_policy_id: str
    anomaly_triggers: list[str] = Field(default_factory=list)
    severity: str = "HIGH"
    reason: str
    recommended_action: str = "Rollback to previous verified policy"
    created_at: float = Field(default_factory=time.time)


class RollbackManager:
    """Monitors telemetry anomalies and coordinates safe rollbacks to previous policy versions."""

    CRITICAL_ANOMALIES = {
        "GROUNDING_DROP",
        "SCENARIO_EVIDENCE_CONTAMINATION",
        "FAILED_SAFE_HALT",
        "LATENCY_SPIKE",
    }

    def __init__(self, registry: PolicyRegistry | None = None):
        self._registry = registry or policy_registry
        self._active_advisories: list[RollbackAdvisory] = []

    def inspect_telemetry(
        self,
        traces: list[AITrace],
        anomalies: list[RuntimeAnomaly] | None = None,
    ) -> RollbackAdvisory | None:
        """Evaluates traces and anomalies against rollback thresholds."""
        active_policy = self._registry.get_active_policy()
        policy_history = self._registry.get_history()

        if len(policy_history) < 2:
            # No prior policy to roll back to
            return None

        prior_policy_id = policy_history[-2]
        detected_triggers: list[str] = []

        # Check explicit anomalies
        if anomalies:
            for a in anomalies:
                if a.anomaly_type in self.CRITICAL_ANOMALIES:
                    detected_triggers.append(f"{a.anomaly_type}: {a.message}")

        # Check trace-level degradation directly
        critical_grounding_drops = 0
        failed_safes = 0
        latency_violations = 0

        for t in traces:
            g_eval = t.evaluation_summary.get("grounding", {})
            g_rate = g_eval.get("grounding_rate", 1.0)
            if g_rate < 0.95:
                critical_grounding_drops += 1
            if t.status == "FAILED_SAFE":
                failed_safes += 1
            if t.total_latency_ms > 12000:
                latency_violations += 1

        if critical_grounding_drops > 0:
            detected_triggers.append(f"Grounding rate fell below 95% in {critical_grounding_drops} traces.")
        if failed_safes > 1:
            detected_triggers.append(f"Excessive FAILED_SAFE halts detected ({failed_safes} traces).")
        if latency_violations >= 3:
            detected_triggers.append(f"Severe latency SLA violations in {latency_violations} traces.")

        if not detected_triggers:
            return None

        severity = "CRITICAL" if (critical_grounding_drops > 0 or any("SCENARIO" in tr for tr in detected_triggers)) else "HIGH"
        advisory = RollbackAdvisory(
            current_policy_id=active_policy.policy_id,
            target_policy_id=prior_policy_id,
            anomaly_triggers=detected_triggers,
            severity=severity,
            reason=f"Active policy '{active_policy.policy_id}' exhibited runtime degradation: " + "; ".join(detected_triggers[:3]),
        )

        self._active_advisories.append(advisory)
        logger.warning(f"[RollbackManager] Raised rollback advisory {advisory.advisory_id} for policy '{active_policy.policy_id}' -> target '{prior_policy_id}'")
        return advisory

    def execute_rollback(
        self,
        to_policy_id: str | None = None,
        advisory: RollbackAdvisory | None = None,
        operator: str = "governance_safety",
    ) -> tuple[bool, str]:
        """Restores previous verified policy in PolicyRegistry."""
        target_id = to_policy_id or (advisory.target_policy_id if advisory else None)
        success, msg = self._registry.rollback(to_policy_id=target_id)
        if success:
            logger.info(f"[RollbackManager] Rollback succeeded by '{operator}': {msg}")
        else:
            logger.error(f"[RollbackManager] Rollback failed: {msg}")
        return success, msg

    def get_advisories(self) -> list[RollbackAdvisory]:
        """Returns recorded rollback advisories."""
        return list(self._active_advisories)


rollback_manager = RollbackManager()
