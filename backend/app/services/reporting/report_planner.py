"""Report Planning Engine.
Generates an explicit, evidence-backed ReportPlan before slide/report writing begins."""

import json
import logging
from typing import Any
from pydantic import BaseModel, Field

from ..evidence.evidence_store import EvidenceStore
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
    """Produces a structured ReportPlan linking all narrative sections to verified findings."""

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

        findings_summary = evidence_store.to_analyst_summary()
        all_finding_ids = [f.finding_id for f in findings]

        prompt = f"""You are the Executive Presentation & Reporting Architect.
Your task: Build a rigorous, structured ReportPlan for '{profile.dataset_name}' ({profile.business_domain}).

CRITICAL GUARDRAILS:
1. Every section MUST reference 1 to 3 valid finding IDs strictly from the Available Finding IDs list below.
2. DO NOT invent fake finding IDs. Only choose from: {json.dumps(all_finding_ids)}
3. Plan {target_section_count} logical narrative sections covering:
   - Executive Summary
   - Operational Baselines
   - Operational Strengths / Outperformers
   - Critical Headwinds / Performance Gaps
   - Strategic Recommendations & Governance

## Available Verified Findings:
{json.dumps(findings_summary, indent=2)}

Return ONLY a valid JSON object matching this schema:
{{
  "report_title": "Executive Review: Operational Performance",
  "objective": "{objective}",
  "executive_summary_finding_ids": ["{all_finding_ids[0]}"],
  "sections": [
    {{
      "section_id": "SEC-01",
      "name": "Executive Summary & Key Vectors",
      "category": "EXECUTIVE",
      "purpose": "High-level leadership briefing on key operational trends",
      "finding_ids": ["{all_finding_ids[0]}"],
      "visual_hook": "none"
    }}
  ]
}}
"""

        result = ModelGateway.generate(
            role=ModelRole.ANALYST,
            prompt=prompt,
            response_schema=ReportPlan,
            report_id=report_id,
            step_name="report_planning"
        )

        plan = result.parsed
        if not plan or not plan.sections:
            # Deterministic plan fallback
            logger.info("Using deterministic fallback ReportPlan.")
            sections = []
            f_ids = [f.finding_id for f in findings]

            sections.append(SectionPlan(
                section_id="SEC-01",
                name="Executive Overview & Key Telemetry",
                category="EXECUTIVE",
                purpose="Establish macro operational context and audited record count",
                finding_ids=f_ids[:2],
                visual_hook="none"
            ))

            if len(f_ids) >= 2:
                sections.append(SectionPlan(
                    section_id="SEC-02",
                    name="Primary Operating Strengths",
                    category="STRENGTHS",
                    purpose="Analyze leading cohorts and peak operational segments",
                    finding_ids=[f_ids[1]],
                    visual_hook="bar_chart"
                ))

            if len(f_ids) >= 3:
                sections.append(SectionPlan(
                    section_id="SEC-03",
                    name="Operational Headwinds & Gaps",
                    category="HEADWINDS",
                    purpose="Highlight segments trailing the organization-wide baseline",
                    finding_ids=[f_ids[2]],
                    visual_hook="bar_chart"
                ))

            if len(f_ids) >= 4:
                sections.append(SectionPlan(
                    section_id="SEC-04",
                    name="Empirical Action Vectors",
                    category="RECOMMENDATIONS",
                    purpose="Actionable leadership interventions to mitigate variance",
                    finding_ids=f_ids[3:],
                    visual_hook="none"
                ))

            plan = ReportPlan(
                report_title=f"Executive Brief: {profile.dataset_name}",
                objective=objective,
                executive_summary_finding_ids=f_ids[:2],
                sections=sections
            )

        # Enforce guardrail: filter out hallucinated finding IDs
        valid_set = set(all_finding_ids)
        plan.executive_summary_finding_ids = [fid for fid in plan.executive_summary_finding_ids if fid in valid_set]
        for sec in plan.sections:
            sec.finding_ids = [fid for fid in sec.finding_ids if fid in valid_set]
            if not sec.finding_ids and all_finding_ids:
                sec.finding_ids = [all_finding_ids[0]]  # Fallback to primary finding

        return plan
