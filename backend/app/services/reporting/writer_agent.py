"""Stage B: Writer Agent.
Generates management-ready narrative strictly grounded in verified EvidenceStore findings.
The Writer model determines how to explain findings without calculating or inventing values."""

import json
import logging
from typing import Any
from pydantic import BaseModel, Field

from ..evidence.evidence_store import EvidenceStore
from ..data_engine.profiler import DatasetProfile
from .report_planner import ReportPlan, SectionPlan
from ..gateway.model_gateway import ModelGateway
from ..gateway.observability import LineageRecord, trace_registry
from ...core.models_config import ModelRole

logger = logging.getLogger(__name__)


class WrittenSection(BaseModel):
    """Generated narrative for a single report section or slide."""
    section_id: str
    title: str
    key_takeaway: str
    bullet_points: list[str] = Field(default_factory=list)
    action_vector: str | None = None
    finding_ids: list[str] = Field(default_factory=list)


class GeneratedReport(BaseModel):
    """Complete drafted report ready for Critic audit."""
    report_title: str
    objective: str
    sections: list[WrittenSection] = Field(default_factory=list)


class WriterAgent:
    """Agent representing the WRITER role (backed by Gemma 4)."""

    @classmethod
    def write_report(
        cls,
        plan: ReportPlan,
        evidence_store: EvidenceStore,
        profile: DatasetProfile,
        report_id: str = "report-default"
    ) -> GeneratedReport:
        findings_by_id = {f.finding_id: f for f in evidence_store.get_all()}
        written_sections: list[WrittenSection] = []

        for sec in plan.sections:
            sec_findings = [findings_by_id[fid] for fid in sec.finding_ids if fid in findings_by_id]
            if not sec_findings:
                sec_findings = evidence_store.get_all()[:2]

            findings_payload = [
                {
                    "finding_id": f.finding_id,
                    "headline": f.headline,
                    "metric": f.metric,
                    "segment": f.segment,
                    "value": f.segment_value,
                    "baseline": f.overall_value,
                    "gap": f.difference_percentage_points,
                    "implication": f.business_implication
                }
                for f in sec_findings
            ]

            prompt = f"""You are the Lead Executive Speechwriter & Visual Presentation Author.
Your task: Write an executive-ready slide narrative for section '{sec.name}'.
Purpose: {sec.purpose}
Audience: Executive Board & Operational Directors

CRITICAL RULES:
1. BREVITY: Maximum 15 words per bullet point. No walls of text.
2. ABSOLUTE FACTUAL GROUNDING: Rely strictly on the supplied metrics and gaps. DO NOT invent dates, rates, or figures.
3. Assertive Headlines: Craft a conclusion-driven headline under 78 characters.
4. Reference the finding IDs in brackets (e.g. '[F-001]') when stating figures.
5. Provide 2 to 3 crisp bullet points and 1 concrete action vector.

## Approved Verified Findings for this Section:
{json.dumps(findings_payload, indent=2)}

Return ONLY a valid JSON object matching this schema:
{{
  "section_id": "{sec.section_id}",
  "title": "Assertive Headline Under 78 Chars",
  "key_takeaway": "One clear executive takeaway summarizing this section",
  "bullet_points": [
    "Leading segment outpaced baseline by 10.5 percentage points [F-001]",
    "Observation window shows stable performance across 712 audited records [F-002]"
  ],
  "action_vector": "Operational review scheduled for underperforming segments by next sprint",
  "finding_ids": {json.dumps(sec.finding_ids)}
}}
"""

            result = ModelGateway.generate(
                role=ModelRole.WRITER,
                prompt=prompt,
                response_schema=WrittenSection,
                report_id=report_id,
                step_name=f"write_section_{sec.section_id}",
                finding_ids=sec.finding_ids
            )

            written = result.parsed
            if not written or not written.bullet_points:
                # Deterministic writer fallback
                f_lead = sec_findings[0]
                diff_text = f" ({f_lead.difference_percentage_points:+.1f}% vs baseline)" if f_lead.difference_percentage_points is not None else ""
                bullets = [
                    f"{f_lead.headline} [{f_lead.finding_id}]",
                    f"Audited across {f_lead.metric} in {profile.dataset_name}{diff_text}."
                ]
                written = WrittenSection(
                    section_id=sec.section_id,
                    title=f_lead.headline[:78],
                    key_takeaway=f_lead.business_implication,
                    bullet_points=bullets,
                    action_vector="Track weekly operational variance across primary cohorts.",
                    finding_ids=sec.finding_ids
                )

            # Record lineage
            for sentence in written.bullet_points:
                for fid in sec.finding_ids:
                    f_obj = findings_by_id.get(fid)
                    if f_obj:
                        trace_registry.record_lineage(LineageRecord(
                            report_id=report_id,
                            section_id=sec.section_id,
                            sentence_text=sentence,
                            finding_id=fid,
                            metric_name=f_obj.metric,
                            source_sheet=profile.dataset_name,
                            source_columns=[f_obj.metric] + ([f_obj.segment.split(':')[0]] if f_obj.segment and ':' in f_obj.segment else [])
                        ))

            written_sections.append(written)

        return GeneratedReport(
            report_title=plan.report_title,
            objective=plan.objective,
            sections=written_sections
        )
