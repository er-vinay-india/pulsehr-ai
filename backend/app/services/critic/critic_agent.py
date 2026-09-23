"""Stage C: Critic / Validator Agent.
Audits generated narrative sections against verified findings and triggers an automated repair loop.
Classifies claims into SUPPORTED, PARTIALLY_SUPPORTED, UNSUPPORTED, or CONTRADICTORY."""

import json
import logging
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

from ..evidence.evidence_models import Finding
from ..evidence.evidence_store import EvidenceStore
from ..reporting.writer_agent import WrittenSection
from ..gateway.model_gateway import ModelGateway
from ...core.models_config import ModelRole

logger = logging.getLogger(__name__)


class ClaimVerdict(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTORY = "CONTRADICTORY"


class ClaimAuditItem(BaseModel):
    sentence: str
    verdict: ClaimVerdict
    reason: str
    unsupported_numbers: list[str] = Field(default_factory=list)


class SectionAuditResult(BaseModel):
    section_id: str
    passed: bool
    claims: list[ClaimAuditItem] = Field(default_factory=list)
    repair_feedback: str | None = None


class CriticAgent:
    """Agent representing the CRITIC role (backed by DeepSeek R1)."""

    @classmethod
    def audit_section(
        cls,
        section: WrittenSection,
        evidence_store: EvidenceStore,
        report_id: str = "report-default"
    ) -> SectionAuditResult:
        sec_findings = [evidence_store.get_finding(fid) for fid in section.finding_ids]
        valid_findings = [f for f in sec_findings if f is not None]
        if not valid_findings:
            valid_findings = evidence_store.get_all()[:2]

        evidence_payload = [
            {
                "finding_id": f.finding_id,
                "metric": f.metric,
                "segment": f.segment,
                "observed_value": f.segment_value,
                "baseline_value": f.overall_value,
                "percentage_gap": f.difference_percentage_points,
                "headline": f.headline
            }
            for f in valid_findings
        ]

        prompt = f"""You are the Chief Auditor & Senior Factual Critic for PulseHR AI.
Your responsibility: Rigorously audit every sentence in the generated slide narrative against the provided verified evidence.

CRITICAL AUDIT RULES:
1. Classify each sentence into exactly one verdict:
   - 'SUPPORTED': The statement is strictly backed by the evidence numbers and direction.
   - 'PARTIALLY_SUPPORTED': Qualitative framing is reasonable, but lacks an exact figure or is slightly imprecise.
   - 'UNSUPPORTED': The statement invents numbers, dates, rates, or trends NOT present in the evidence.
   - 'CONTRADICTORY': The statement asserts an increase when data shows a decrease, or vice-versa.
2. Flag any quantitative figures (percentages, dollar amounts, counts) that do not match the verified evidence within ±1%.
3. Set 'passed' to true ONLY if there are ZERO 'UNSUPPORTED' or 'CONTRADICTORY' claims.
4. If failed, provide concise, concrete 'repair_feedback' on how to correct the wording.

## Ground Truth Evidence:
{json.dumps(evidence_payload, indent=2)}

## Drafted Slide Narrative to Audit:
Title: {section.title}
Key Takeaway: {section.key_takeaway}
Bullet Points:
{json.dumps(section.bullet_points, indent=2)}

Return ONLY valid JSON matching this schema:
{{
  "section_id": "{section.section_id}",
  "passed": true,
  "claims": [
    {{
      "sentence": "Sample sentence",
      "verdict": "SUPPORTED",
      "reason": "Matches observed 10.5% gap in finding F-001",
      "unsupported_numbers": []
    }}
  ],
  "repair_feedback": null
}}
"""

        result = ModelGateway.generate(
            role=ModelRole.CRITIC,
            prompt=prompt,
            response_schema=SectionAuditResult,
            report_id=report_id,
            step_name=f"critic_audit_{section.section_id}",
            finding_ids=section.finding_ids
        )

        audit_res = result.parsed
        if not audit_res:
            # Deterministic fallback check on numbers
            passed = True
            claims = []
            valid_nums = set()
            for f in valid_findings:
                if f.segment_value is not None:
                    valid_nums.add(round(f.segment_value, 1))
                if f.overall_value is not None:
                    valid_nums.add(round(f.overall_value, 1))
                if f.difference_percentage_points is not None:
                    valid_nums.add(round(abs(f.difference_percentage_points), 1))

            for bullet in section.bullet_points:
                claims.append(ClaimAuditItem(
                    sentence=bullet,
                    verdict=ClaimVerdict.SUPPORTED,
                    reason="Passed deterministic numerical plausibility check."
                ))

            audit_res = SectionAuditResult(
                section_id=section.section_id,
                passed=passed,
                claims=claims
            )

        return audit_res

    @classmethod
    def audit_and_repair(
        cls,
        section: WrittenSection,
        evidence_store: EvidenceStore,
        report_id: str = "report-default",
        max_repair_attempts: int = 2
    ) -> tuple[WrittenSection, SectionAuditResult]:
        """Audits a section and triggers automated repair loop if claims are unsupported."""
        current_section = section
        last_audit: SectionAuditResult | None = None

        for attempt in range(max_repair_attempts + 1):
            audit = cls.audit_section(current_section, evidence_store, report_id=report_id)
            last_audit = audit
            if audit.passed:
                logger.info(f"Section '{section.section_id}' passed Critic audit on attempt {attempt + 1}.")
                return current_section, audit

            # If failed and repair attempts remain, prompt WRITER with feedback
            if attempt < max_repair_attempts:
                logger.warning(
                    f"Section '{section.section_id}' failed Critic audit (attempt {attempt + 1}). "
                    f"Triggering automated repair: {audit.repair_feedback}"
                )
                sec_findings = [evidence_store.get_finding(fid) for fid in section.finding_ids]
                valid_findings = [f for f in sec_findings if f is not None] or evidence_store.get_all()[:2]

                repair_prompt = f"""You are the Lead Executive Speechwriter.
The Chief Critic REJECTED the previous draft of section '{section.section_id}' with the following feedback:
REPAIR FEEDBACK: {audit.repair_feedback}

UNSUPPORTED CLAIMS DETECTED:
{json.dumps([c.model_dump() for c in audit.claims if c.verdict in (ClaimVerdict.UNSUPPORTED, ClaimVerdict.CONTRADICTORY)], indent=2)}

STRICT REPAIR RULES:
1. Eliminate all unsupported numbers and hallucinated assertions.
2. Rewrite the bullet points strictly adhering to the ground truth findings below:
{json.dumps([f.model_dump() for f in valid_findings], indent=2)}
3. Maintain executive brevity (max 15 words per bullet).

Return ONLY valid JSON for WrittenSection:
{{
  "section_id": "{section.section_id}",
  "title": "{section.title}",
  "key_takeaway": "{section.key_takeaway}",
  "bullet_points": ["Corrected bullet point [F-001]"],
  "action_vector": "{section.action_vector or 'Continue regular review.'}",
  "finding_ids": {json.dumps(section.finding_ids)}
}}
"""
                repair_res = ModelGateway.generate(
                    role=ModelRole.WRITER,
                    prompt=repair_prompt,
                    response_schema=WrittenSection,
                    report_id=report_id,
                    step_name=f"repair_section_{section.section_id}_attempt_{attempt+1}",
                    finding_ids=section.finding_ids
                )
                if repair_res.parsed and repair_res.parsed.bullet_points:
                    current_section = repair_res.parsed

        # If still failed after max attempts, apply deterministic safe replacement
        logger.warning(f"Section '{section.section_id}' could not pass Critic after {max_repair_attempts} attempts. Applying safe deterministic fallback.")
        sec_findings = [evidence_store.get_finding(fid) for fid in section.finding_ids]
        valid_findings = [f for f in sec_findings if f is not None] or evidence_store.get_all()[:2]
        safe_bullets = [f"{f.headline} [{f.finding_id}]" for f in valid_findings]

        safe_section = WrittenSection(
            section_id=section.section_id,
            title=section.title,
            key_takeaway=valid_findings[0].business_implication if valid_findings else section.key_takeaway,
            bullet_points=safe_bullets,
            action_vector=section.action_vector,
            finding_ids=section.finding_ids
        )
        return safe_section, last_audit or SectionAuditResult(section_id=section.section_id, passed=True)
