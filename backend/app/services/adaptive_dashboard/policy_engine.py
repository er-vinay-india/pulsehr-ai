"""Policy Calendar Engine for Phase 9.11: Policy & Business-Semantics Gate.

Implements governed corporate workforce policy evaluation:
- Underlying rule: Compulsory 3 days/week work from office.
- Dynamic period calendar evaluation (e.g., 5 reporting cycles / weeks in July).
- Personalized target deduction for approved leave exemptions, holidays, and partial eligibility.

Mathematical Formulation:
    RequiredOfficeDays(employee, period) = max(0.0, eligible_work_weeks × target_days_per_week - applicable_policy_exemptions)
    PolicyCompliance = count(employees meeting their eligible target) / eligible_employees × 100
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class PolicyCalendarRule:
    """Governed corporate policy parameters."""
    rule_id: str = "POL-WFO-3D"
    name: str = "Compulsory 3-Day In-Office Policy"
    target_days_per_week: float = 3.0
    default_period_work_weeks: float = 5.0
    working_days_per_month: float = 22.0
    allow_leave_exemptions: bool = True
    exemption_credit_ratio: float = 1.0  # 1 approved leave day reduces requirement by 1 day
    min_required_days: float = 0.0


@dataclass
class EmployeeComplianceRecord:
    """Individual employee policy compliance evaluation."""
    employee_id: str
    department: str
    actual_attendance_days: float
    approved_leave_days: float
    eligible_work_weeks: float
    gross_target_days: float
    applicable_exemptions: float
    net_required_days: float
    is_compliant: bool
    compliance_margin: float  # actual - net_required (positive = surplus, negative = deficit)


@dataclass
class PolicyComplianceResult:
    """Aggregate result from the Policy Calendar Engine."""
    rule: PolicyCalendarRule
    eligible_count: int
    compliant_count: int
    compliance_rate: float  # Percentage (0.0 to 100.0)
    baseline_benchmark_days: float  # Standard unadjusted benchmark (e.g. 15.0 days)
    average_net_target_days: float
    total_exemptions_granted: float
    rule_description: str
    formula_label: str
    calculation_summary: str
    records: list[EmployeeComplianceRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule.rule_id,
            "rule_name": self.rule.name,
            "target_days_per_week": self.rule.target_days_per_week,
            "baseline_benchmark_days": self.baseline_benchmark_days,
            "eligible_count": self.eligible_count,
            "compliant_count": self.compliant_count,
            "compliance_rate": self.compliance_rate,
            "formatted_compliance_rate": f"{self.compliance_rate:.1f}%",
            "average_net_target_days": self.average_net_target_days,
            "total_exemptions_granted": self.total_exemptions_granted,
            "rule_description": self.rule_description,
            "formula_label": self.formula_label,
            "calculation_summary": self.calculation_summary,
        }


class PolicyCalendarEngine:
    """Governed engine that evaluates workforce compliance against in-office attendance rules."""

    def __init__(self, rule: Optional[PolicyCalendarRule] = None):
        self.rule = rule or PolicyCalendarRule()

    @property
    def target_days_per_week(self) -> float:
        return self.rule.target_days_per_week

    @property
    def period_work_weeks(self) -> float:
        return self.rule.default_period_work_weeks

    def compute_baseline_benchmark(self, period_weeks: Optional[float] = None) -> float:
        """Returns the unadjusted baseline corporate benchmark days (e.g. 5 weeks * 3 days = 15.0 days)."""
        weeks = period_weeks if period_weeks is not None else self.rule.default_period_work_weeks
        return round(weeks * self.rule.target_days_per_week, 1)

    def calculate_employee_target(
        self,
        eligible_weeks: float,
        approved_leaves: float = 0.0,
        custom_exemptions: float = 0.0,
    ) -> tuple[float, float, float]:
        """Calculates (gross_target, total_exemptions, net_required_days) for an individual employee.

        Formula:
            gross = eligible_weeks * target_days_per_week
            exemptions = approved_leaves * exemption_credit_ratio + custom_exemptions
            net = max(0.0, gross - exemptions)
        """
        gross = eligible_weeks * self.rule.target_days_per_week
        exemptions = 0.0
        if self.rule.allow_leave_exemptions:
            exemptions += approved_leaves * self.rule.exemption_credit_ratio
        exemptions += custom_exemptions

        net = max(self.rule.min_required_days, round(gross - exemptions, 1))
        return round(gross, 1), round(exemptions, 1), round(net, 1)

    def evaluate_workforce(
        self,
        employees: list[dict[str, Any]],
        att_key: str = "Total Attendance",
        leave_key: str = "Approved Leaves",
        dept_key: str = "Department",
        id_key: str = "Employee ID",
        period_weeks: Optional[float] = None,
    ) -> PolicyComplianceResult:
        """Evaluates workforce compliance across all eligible records.

        Args:
            employees: List of employee row dictionaries.
            att_key: Key for actual attendance days.
            leave_key: Key for approved leave days.
            dept_key: Key for department name.
            id_key: Key for employee identifier.
            period_weeks: Override for number of working weeks in reporting cycle.
        """
        weeks = period_weeks if period_weeks is not None else self.rule.default_period_work_weeks
        baseline_benchmark = self.compute_baseline_benchmark(weeks)

        records: list[EmployeeComplianceRecord] = []
        compliant_count = 0
        total_exemptions = 0.0
        net_targets_sum = 0.0

        for idx, row in enumerate(employees):
            emp_id = str(row.get(id_key) or row.get("ID") or f"EMP-{idx+1}")
            dept = str(row.get(dept_key) or "General")

            # Extract attendance
            att_val = 0.0
            raw_att = row.get(att_key)
            if raw_att is not None:
                try:
                    att_val = float(raw_att)
                except (ValueError, TypeError):
                    att_val = 0.0

            # Extract approved leaves
            leave_val = 0.0
            raw_leave = row.get(leave_key)
            if raw_leave is not None:
                try:
                    leave_val = float(raw_leave)
                except (ValueError, TypeError):
                    leave_val = 0.0

            gross_target, exemptions, net_required = self.calculate_employee_target(
                eligible_weeks=weeks,
                approved_leaves=leave_val,
            )

            is_compliant = att_val >= net_required
            if is_compliant:
                compliant_count += 1

            margin = round(att_val - net_required, 1)
            total_exemptions += exemptions
            net_targets_sum += net_required

            records.append(
                EmployeeComplianceRecord(
                    employee_id=emp_id,
                    department=dept,
                    actual_attendance_days=att_val,
                    approved_leave_days=leave_val,
                    eligible_work_weeks=weeks,
                    gross_target_days=gross_target,
                    applicable_exemptions=exemptions,
                    net_required_days=net_required,
                    is_compliant=is_compliant,
                    compliance_margin=margin,
                )
            )

        eligible_count = len(records)
        compliance_rate = round(compliant_count / eligible_count * 100.0, 1) if eligible_count > 0 else 0.0
        avg_net_target = round(net_targets_sum / eligible_count, 1) if eligible_count > 0 else baseline_benchmark

        rule_desc = (
            f"Compulsory {self.rule.target_days_per_week:g} days/week in-office target across "
            f"{weeks:g} tracking cycles ({baseline_benchmark:g}d baseline), with approved leave exemptions."
        )

        formula = (
            f"COUNT(actual_attendance >= max(0, {weeks:g} × {self.rule.target_days_per_week:g} - approved_leave)) "
            f"/ {eligible_count} * 100"
        )

        calc_summary = (
            f"{compliant_count} of {eligible_count} eligible employees met their net required in-office target "
            f"(baseline {baseline_benchmark:g} days less approved leave exemptions). "
            f"Average net target: {avg_net_target:.1f} days."
        )

        return PolicyComplianceResult(
            rule=self.rule,
            eligible_count=eligible_count,
            compliant_count=compliant_count,
            compliance_rate=compliance_rate,
            baseline_benchmark_days=baseline_benchmark,
            average_net_target_days=avg_net_target,
            total_exemptions_granted=round(total_exemptions, 1),
            rule_description=rule_desc,
            formula_label=formula,
            calculation_summary=calc_summary,
            records=records,
        )
