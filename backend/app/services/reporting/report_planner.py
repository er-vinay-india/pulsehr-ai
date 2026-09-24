"""Report Planning Engine.
Generates an explicit, evidence-backed ReportPlan before slide/report writing begins."""

import json
import logging
from typing import Any
from pydantic import BaseModel, Field

from ..evidence.evidence_store import EvidenceStore
from ..evidence.evidence_models import Finding, FindingType, Importance
from ..data_engine.profiler import DatasetProfile
from ..gateway.model_gateway import ModelGateway
from ...core.models_config import ModelRole

logger = logging.getLogger(__name__)


class SectionPlan(BaseModel):
    """Blueprint for a single report section or slide."""
    section_id: str
    name: str
    category: str
    purpose: str
    finding_ids: list[str] = Field(default_factory=list)
    visual_hook: str = "none"  # "line_chart", "bar_chart", "donut_chart", "heatmap", "none"


class ReportPlan(BaseModel):
    """The complete structural blueprint governing report generation."""
    report_title: str
    objective: str
    executive_summary_finding_ids: list[str] = Field(default_factory=list)
    sections: list[SectionPlan] = Field(default_factory=list)


class ReportPlanner:
    """Produces a structured ReportPlan linking all narrative sections to verified findings deterministically.
    Eliminates expensive generative LLM calls (<1ms latency) while guaranteeing zero hallucinated IDs.
    """

    @classmethod
    def plan(
        cls,
        evidence_store: EvidenceStore,
        profile: DatasetProfile,
        objective: str = "Quarterly Leadership Performance Review",
        target_section_count: int = 6,
        report_id: str = "report-default"
    ) -> ReportPlan:
        findings = evidence_store.get_all()
        if not findings:
            # Empty fallback
            return ReportPlan(
                report_title=f"Executive Brief: {profile.dataset_name}",
                objective=objective,
                executive_summary_finding_ids=[],
                sections=[]
            )

        all_finding_ids = [f.finding_id for f in findings]

        # Categorize findings by category, severity/importance, and polarity/direction
        strengths = [
            f for f in findings
            if f.type in (FindingType.OUTPERFORMER, "outperformer")
            or (f.difference is not None and f.difference > 0 and f.type not in (FindingType.HEADWIND, FindingType.RISK_ALERT))
        ]
        headwinds = [
            f for f in findings
            if f.type in (FindingType.HEADWIND, FindingType.RISK_ALERT, FindingType.PERFORMANCE_GAP, "headwind", "risk_alert", "performance_gap")
            or (f.difference is not None and f.difference < 0)
        ]
        trends = [
            f for f in findings
            if f.type in (FindingType.TREND_SHIFT, "trend_shift")
            or any(w in f.headline.lower() for w in ("trend", "month", "quarter", "timeline", "period", "lift", "change"))
        ]
        concentrations = [
            f for f in findings
            if f.type in (FindingType.CONCENTRATION, "concentration")
            or "concentration" in f.headline.lower()
        ]

        # Sort each group by importance (HIGH > MEDIUM > LOW) and magnitude
        def sort_key(f):
            imp_val = 3 if str(f.importance).lower() in ("high", "importance.high") else (
                2 if str(f.importance).lower() in ("medium", "importance.medium") else 1
            )
            mag = abs(f.difference or 0.0)
            return (-imp_val, -mag)

        strengths.sort(key=sort_key)
        headwinds.sort(key=sort_key)
        trends.sort(key=sort_key)
        concentrations.sort(key=sort_key)

        sections: list[SectionPlan] = []
        sec_num = 1

        # Section 1: Executive Overview & Baseline Telemetry (Always first)
        exec_ids = [findings[0].finding_id]
        if len(findings) > 1 and findings[1].finding_id not in exec_ids:
            exec_ids.append(findings[1].finding_id)

        domain_label = profile.business_domain or "Operational"
        sections.append(SectionPlan(
            section_id=f"SEC-{sec_num:02d}",
            name=f"Executive Overview & {domain_label} Telemetry",
            category="EXECUTIVE",
            purpose=f"Establish macro operational context across {profile.row_count:,} audited records and highlight key organizational benchmarks.",
            finding_ids=exec_ids,
            visual_hook="none"
        ))
        sec_num += 1

        # Section 2: Operational Strengths & Leading Drivers (if present)
        if strengths:
            str_ids = [f.finding_id for f in strengths[:3]]
            sections.append(SectionPlan(
                section_id=f"SEC-{sec_num:02d}",
                name="Operational Strengths & Leading Drivers",
                category="STRENGTHS",
                purpose="Evaluate leading cohorts and high-performing segments exceeding organizational baseline.",
                finding_ids=str_ids,
                visual_hook="bar_chart"
            ))
            sec_num += 1

        # Section 3: Operational Headwinds & Performance Gaps (if present)
        if headwinds:
            hw_ids = [f.finding_id for f in headwinds[:3]]
            sections.append(SectionPlan(
                section_id=f"SEC-{sec_num:02d}",
                name="Operational Headwinds & Variance Gaps",
                category="HEADWINDS",
                purpose="Highlight critical operational friction points and trailing cohorts requiring leadership intervention.",
                finding_ids=hw_ids,
                visual_hook="bar_chart"
            ))
            sec_num += 1

        # Section 4: Longitudinal Trends & Momentum (if present and distinct)
        assigned_ids = {fid for s in sections for fid in s.finding_ids}
        distinct_trends = [f for f in trends if f.finding_id not in assigned_ids]
        if distinct_trends:
            tr_ids = [f.finding_id for f in distinct_trends[:3]]
            sections.append(SectionPlan(
                section_id=f"SEC-{sec_num:02d}",
                name="Longitudinal Trends & Temporal Shifts",
                category="TRENDS",
                purpose="Analyze historical trajectory, period-over-period momentum, and longitudinal variance.",
                finding_ids=tr_ids,
                visual_hook="line_chart"
            ))
            sec_num += 1

        # Section 5: Cohort Concentration & Distribution Variance (if present and distinct)
        assigned_ids = {fid for s in sections for fid in s.finding_ids}
        distinct_conc = [f for f in concentrations if f.finding_id not in assigned_ids]
        if distinct_conc:
            conc_ids = [f.finding_id for f in distinct_conc[:3]]
            sections.append(SectionPlan(
                section_id=f"SEC-{sec_num:02d}",
                name="Cohort Concentration & Distribution Variance",
                category="CONCENTRATION",
                purpose="Assess cohort concentration and variance across organizational dimensions.",
                finding_ids=conc_ids,
                visual_hook="donut_chart"
            ))
            sec_num += 1

        # Section 6: Empirical Action Vectors & Governance (Always closing section)
        rec_candidates = headwinds if headwinds else findings
        rec_ids = [f.finding_id for f in rec_candidates[:2]]
        sections.append(SectionPlan(
            section_id=f"SEC-{sec_num:02d}",
            name="Empirical Action Vectors & Governance",
            category="RECOMMENDATIONS",
            purpose="Actionable leadership interventions and targeted mitigations supported by verified empirical findings.",
            finding_ids=rec_ids,
            visual_hook="none"
        ))

        # Enforce guardrails: filter out any invalid finding IDs
        valid_set = set(all_finding_ids)
        plan_exec_ids = [fid for fid in exec_ids if fid in valid_set]
        for sec in sections:
            sec.finding_ids = [fid for fid in sec.finding_ids if fid in valid_set]
            if not sec.finding_ids and all_finding_ids:
                sec.finding_ids = [all_finding_ids[0]]

        return ReportPlan(
            report_title=f"Executive Review: {profile.dataset_name}",
            objective=objective,
            executive_summary_finding_ids=plan_exec_ids,
            sections=sections
        )
