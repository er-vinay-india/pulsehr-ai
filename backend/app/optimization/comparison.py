"""PolicyComparator: Compares baseline and candidate policies under hard safety gates (Phase E)."""
from __future__ import annotations

import logging
from typing import Any
from app.observability.benchmark.runner import BenchmarkReport
from .contracts import HighviewPolicy, PolicyComparisonResult

logger = logging.getLogger(__name__)


class PolicyComparator:
    """Evaluates candidate benchmark reports against active baseline under strict safety gates."""

    @classmethod
    def compare_policies(
        cls,
        baseline_policy: HighviewPolicy,
        candidate_policy: HighviewPolicy,
        baseline_report: BenchmarkReport,
        candidate_report: BenchmarkReport,
        safety_override_flags: dict[str, Any] | None = None,
    ) -> PolicyComparisonResult:
        flags = safety_override_flags or {}

        # 1. Evaluate Hard Safety Gates
        isolation_violations = flags.get("dataset_isolation_violations", 0)
        ungrounded_claims = flags.get("ungrounded_factual_claims", candidate_report.ungrounded_claim_count)
        evid_scen_contamination = flags.get("evid_scen_contamination", 0)
        bypass_violations = flags.get("bypass_violations", 0)
        unauthorized_actions = flags.get("unauthorized_actions", 0)
        causal_regressions = flags.get("causal_regressions", 0)

        safety_passed = (
            isolation_violations == 0
            and ungrounded_claims == 0
            and evid_scen_contamination == 0
            and bypass_violations == 0
            and unauthorized_actions == 0
            and causal_regressions == 0
        )

        regressions: list[str] = []
        improvements: list[str] = []

        if isolation_violations > 0:
            regressions.append(f"HARD SAFETY BREACH: {isolation_violations} dataset isolation violation(s) detected.")
        if ungrounded_claims > 0:
            regressions.append(f"HARD SAFETY BREACH: {ungrounded_claims} ungrounded factual claim(s) produced.")
        if evid_scen_contamination > 0:
            regressions.append(f"HARD SAFETY BREACH: {evid_scen_contamination} EVID/SCEN contamination event(s) detected.")
        if bypass_violations > 0:
            regressions.append(f"HARD SAFETY BREACH: {bypass_violations} architectural bypass violation(s) detected.")
        if unauthorized_actions > 0:
            regressions.append(f"HARD SAFETY BREACH: {unauthorized_actions} unauthorized critical action(s) attempted.")

        # 2. Compute Metric Deltas
        quality_delta = round(candidate_report.overall_runtime_quality_score - baseline_report.overall_runtime_quality_score, 3)
        latency_delta = round(candidate_report.average_latency_ms - baseline_report.average_latency_ms, 2)
        tool_delta = round(baseline_report.average_tool_calls - candidate_report.average_tool_calls, 2)
        grounding_delta = round(candidate_report.grounding_rate - baseline_report.grounding_rate, 3)
        gov_delta = round((candidate_report.governance_denial_count - baseline_report.governance_denial_count), 2)

        if grounding_delta < 0.0:
            regressions.append(f"Grounding rate regressed by {abs(grounding_delta) * 100:.1f}%.")
        elif grounding_delta > 0.0:
            improvements.append(f"Grounding rate improved by {grounding_delta * 100:.1f}%.")

        if latency_delta < 0.0:
            improvements.append(f"Average latency reduced by {abs(latency_delta):.1f}ms.")
        elif latency_delta > 200.0:
            regressions.append(f"Average latency increased by {latency_delta:.1f}ms.")

        if tool_delta > 0.0:
            improvements.append(f"Tool call count reduced by {tool_delta:.2f} calls/query.")
        elif tool_delta < -0.5:
            regressions.append(f"Tool call count increased by {abs(tool_delta):.2f} calls/query.")

        if quality_delta > 0.0:
            improvements.append(f"Composite runtime quality score improved (+{quality_delta:.3f}).")
        elif quality_delta < -0.05:
            regressions.append(f"Composite runtime quality score dropped ({quality_delta:.3f}).")

        # 3. Determine Recommendation
        if not safety_passed or grounding_delta < -0.001:
            rec = "REJECT"
            rationale = "Candidate policy rejected: hard safety gates failed or grounding regressed."
        elif len(improvements) > 0 and len(regressions) == 0:
            rec = "PROMOTE"
            rationale = "Candidate policy verified: all safety gates passed and measurable performance improvements demonstrated."
        else:
            rec = "REVIEW"
            rationale = "Candidate policy requires human review due to mixed metric variations."

        return PolicyComparisonResult(
            baseline_policy_id=baseline_policy.policy_id,
            candidate_policy_id=candidate_policy.policy_id,
            quality_delta=quality_delta,
            latency_delta_ms=latency_delta,
            compute_delta=round(-latency_delta * 0.5, 2),
            tool_efficiency_delta=tool_delta,
            grounding_delta=grounding_delta,
            governance_delta=gov_delta,
            hard_safety_gates_passed=safety_passed,
            regressions=regressions,
            improvements=improvements,
            recommendation=rec,
            rationale=rationale,
        )
