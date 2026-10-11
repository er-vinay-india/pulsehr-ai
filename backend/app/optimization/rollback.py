"""Automated anomaly inspection, containment, and rollback manager for Governed Adaptive Optimization (Phase E).

Governance invariant:
- NORMAL performance degradation (LATENCY_SPIKE, MODEL_FAILURE_SPIKE, TOOL_COUNT_SPIKE):
  -> Recommends RollbackAdvisory
  -> Strictly REQUIRES Human Approval before executing rollback.
  -> Highview never silently rolls back for performance issues.
- CRITICAL SAFETY breaches (DATASET_ISOLATION_VIOLATION, EVID_SCEN_CONTAMINATION, UNAUTHORIZED_ACTION, GROUNDING_SAFETY_FAILURE):
  -> Governed by explicit EmergencyContainmentPolicy.
  -> Deactivates / reverts the problematic candidate policy immediately under pre-authorized safety containment.
"""
from __future__ import annotations

import logging
import time
from typing import Any
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field

from app.observability.contracts import AITrace, RuntimeAnomaly
from .contracts import AdvisorySeverity, EmergencyContainmentPolicy
from .policy_registry import PolicyRegistry, policy_registry

logger = logging.getLogger(__name__)


class RollbackAdvisory(BaseModel):
    """Advisory recommending rollback of active policy due to detected degradation."""
    model_config = ConfigDict(extra="ignore")

    advisory_id: str = Field(default_factory=lambda: f"adv-rb-{uuid4().hex[:8]}")
    current_policy_id: str
    target_policy_id: str
    anomaly_triggers: list[str] = Field(default_factory=list)
    severity: AdvisorySeverity = AdvisorySeverity.NORMAL
    requires_human_approval: bool = True
    emergency_containment_authorized: bool = False
    reason: str
    recommended_action: str = "Rollback to previous verified policy"
    created_at: float = Field(default_factory=time.time)


class RollbackManager:
    """Monitors telemetry anomalies, coordinates containment, and enforces approval boundaries."""

    CRITICAL_SAFETY_ANOMALIES = {
        "GROUNDING_DROP",
        "SCENARIO_EVIDENCE_CONTAMINATION",
        "DATASET_ISOLATION_VIOLATION",
        "UNAUTHORIZED_ACTION",
    }

    PERFORMANCE_ANOMALIES = {
        "LATENCY_SPIKE",
        "TOOL_COUNT_SPIKE",
        "FAILED_SAFE_HALT",
        "MODEL_FAILURE_SPIKE",
    }

    def __init__(self, registry: PolicyRegistry | None = None):
        self._registry = registry or policy_registry
        self._active_advisories: list[RollbackAdvisory] = []
        self._containment_audit_log: list[dict[str, Any]] = []

    def inspect_telemetry(
        self,
        traces: list[AITrace],
        anomalies: list[RuntimeAnomaly] | None = None,
    ) -> RollbackAdvisory | None:
        """Evaluates traces and anomalies against rollback and containment criteria."""
        active_policy = self._registry.get_active_policy()
        policy_history = self._registry.get_history()

        if len(policy_history) < 2:
            return None

        prior_policy_id = policy_history[-2]
        containment_policy: EmergencyContainmentPolicy = getattr(
            active_policy, "containment_policy", EmergencyContainmentPolicy()
        )

        detected_safety_triggers: list[str] = []
        detected_perf_triggers: list[str] = []

        # 1. Inspect explicit anomalies
        if anomalies:
            for a in anomalies:
                if a.anomaly_type in self.CRITICAL_SAFETY_ANOMALIES:
                    detected_safety_triggers.append(f"{a.anomaly_type}: {a.message}")
                elif a.anomaly_type in self.PERFORMANCE_ANOMALIES:
                    detected_perf_triggers.append(f"{a.anomaly_type}: {a.message}")

        # 2. Inspect trace metrics directly
        grounding_drops = 0
        contamination_events = 0
        failed_safes = 0
        latency_violations = 0

        for t in traces:
            g_eval = t.evaluation_summary.get("grounding", {})
            g_rate = g_eval.get("grounding_rate", 1.0)
            if g_rate < 0.95:
                grounding_drops += 1

            if any(eid.startswith("SCEN-") for eid in t.evidence_ids):
                contamination_events += 1

            if t.status == "FAILED_SAFE":
                failed_safes += 1
            if t.total_latency_ms > 12000:
                latency_violations += 1

        if grounding_drops > 0:
            detected_safety_triggers.append(f"Factual grounding fell below 95% threshold in {grounding_drops} trace(s).")
        if contamination_events > 0:
            detected_safety_triggers.append(f"EVID/SCEN cross-contamination detected in {contamination_events} trace(s).")

        if failed_safes > 1:
            detected_perf_triggers.append(f"Excessive FAILED_SAFE halts detected ({failed_safes} traces).")
        if latency_violations >= 2:
            detected_perf_triggers.append(f"SLA latency violations in {latency_violations} trace(s).")

        if not detected_safety_triggers and not detected_perf_triggers:
            return None

        # 3. Classify Severity and Containment Rules
        if detected_safety_triggers:
            severity = AdvisorySeverity.CRITICAL_SAFETY
            triggers = detected_safety_triggers + detected_perf_triggers
            emergency_auth = containment_policy.enabled
            requires_approval = not emergency_auth
            action_desc = "Emergency containment: immediate policy revert pre-authorized by EmergencyContainmentPolicy" if emergency_auth else "Requires urgent human approval for safety containment"
        else:
            severity = AdvisorySeverity.NORMAL
            triggers = detected_perf_triggers
            emergency_auth = False
            requires_approval = True
            action_desc = "Requires human review and approval before executing performance rollback"

        advisory = RollbackAdvisory(
            current_policy_id=active_policy.policy_id,
            target_policy_id=prior_policy_id,
            anomaly_triggers=triggers,
            severity=severity,
            requires_human_approval=requires_approval,
            emergency_containment_authorized=emergency_auth,
            reason=f"Active policy '{active_policy.policy_id}' degraded: " + "; ".join(triggers[:3]),
            recommended_action=action_desc,
        )

        self._active_advisories.append(advisory)
        logger.warning(
            f"[RollbackManager] Raised advisory '{advisory.advisory_id}' (severity={severity.value}, "
            f"requires_approval={requires_approval}, emergency_authorized={emergency_auth}) for policy '{active_policy.policy_id}'"
        )
        return advisory

    def execute_rollback(
        self,
        to_policy_id: str | None = None,
        advisory: RollbackAdvisory | None = None,
        human_approved: bool = False,
        operator: str = "governance_safety",
    ) -> tuple[bool, str]:
        """Executes policy rollback enforcing approval gates based on advisory severity."""
        adv = advisory
        if not adv and self._active_advisories:
            adv = self._active_advisories[-1]

        target_id = to_policy_id or (adv.target_policy_id if adv else None)

        # Enforce governance rule:
        # NORMAL performance issues MUST have human approval
        if adv and adv.severity == AdvisorySeverity.NORMAL and not human_approved:
            msg = f"Rollback refused: Advisory '{adv.advisory_id}' has severity NORMAL and requires explicit human approval."
            logger.warning(f"[RollbackManager] {msg}")
            return False, msg

        # CRITICAL SAFETY containment:
        is_emergency = adv and adv.severity == AdvisorySeverity.CRITICAL_SAFETY and adv.emergency_containment_authorized

        success, msg = self._registry.rollback(to_policy_id=target_id)
        if success:
            audit_entry = {
                "timestamp": time.time(),
                "action": "EMERGENCY_CONTAINMENT" if is_emergency else "GOVERNED_ROLLBACK",
                "target_policy_id": target_id,
                "advisory_id": adv.advisory_id if adv else None,
                "human_approved": human_approved,
                "operator": operator,
            }
            self._containment_audit_log.append(audit_entry)
            logger.info(f"[RollbackManager] Rollback succeeded ({audit_entry['action']}): {msg}")
        else:
            logger.error(f"[RollbackManager] Rollback failed: {msg}")

        return success, msg

    def get_advisories(self) -> list[RollbackAdvisory]:
        """Returns recorded rollback advisories."""
        return list(self._active_advisories)

    def get_audit_log(self) -> list[dict[str, Any]]:
        """Returns emergency containment and rollback audit log."""
        return list(self._containment_audit_log)

    def clear_for_test(self) -> None:
        """Resets advisories and audit logs for testing."""
        self._active_advisories.clear()
        self._containment_audit_log.clear()


rollback_manager = RollbackManager()
