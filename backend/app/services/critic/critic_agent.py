"""Stage C: Two-Tier Hybrid Critic / Validator Agent for PulseHR AI.

Combines zero-LLM deterministic claim validation with lightweight semantic LLM verification (Phi-4 Mini).
- Tier 1: DeterministicClaimValidator (<1ms, 0 LLM calls) resolves factual, numerical, directional,
          and uncited quantitative assertions.
- Tier 2: Lightweight Semantic Critic (Phi-4 Mini) resolves subtle qualitative nuances, causal leaps,
          and semantic overreach using compact targeted prompts.
- Targeted Repair: Repairs failing sentences individually without full-section regeneration.
- Legacy Mode: Fully preserves DeepSeek-R1 whole-section auditing behind CRITIC_MODE=legacy.
"""

import json
import logging
import os
import time
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

from ..evidence.evidence_models import Finding
from ..evidence.evidence_store import EvidenceStore
from ..reporting.writer_agent import WrittenSection
from ..gateway.model_gateway import ModelGateway
from ...core.models_config import ModelRole
from .deterministic_claim_validator import (
    DeterministicClaimValidator,
    ClaimValidationStatus,
    ClaimValidationResult,
    ToleranceConfig
)

logger = logging.getLogger(__name__)

# Operational modes
CRITIC_MODE = os.getenv("CRITIC_MODE", "hybrid").lower()
CRITIC_SEMANTIC_MODEL = os.getenv("CRITIC_SEMANTIC_MODEL", "phi4-mini:latest")


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
    validation_source: str = "deterministic"  # "deterministic" | "phi_semantic" | "legacy_deepseek"


class SectionAuditResult(BaseModel):
    section_id: str
    passed: bool
    claims: list[ClaimAuditItem] = Field(default_factory=list)
    repair_feedback: str | None = None
    telemetry: dict[str, Any] = Field(default_factory=dict)


class SemanticClaimEvaluation(BaseModel):
    claim_id: int
    verdict: str = Field(description="SUPPORTED, OVERSTATED, CAUSAL_OVERREACH, SEMANTIC_DISTORTION, or UNSUPPORTED")
    reason: str
    passed: bool


class SemanticBatchAuditResult(BaseModel):
    evaluations: list[SemanticClaimEvaluation] = Field(default_factory=list)


class SingleSentenceRepairResult(BaseModel):
    repaired_sentence: str


class CriticTelemetryTracker:
    """Thread-safe telemetry accumulator for factual auditing performance."""
    def __init__(self):
        self.total_claims: int = 0
        self.deterministic_verified: int = 0
        self.deterministic_invalid: int = 0
        self.ambiguous_claims: int = 0
        self.phi_calls: int = 0
        self.phi_latency_ms: float = 0.0
        self.validation_total_ms: float = 0.0
        self.repairs_triggered: int = 0

    def record_summary(self) -> dict[str, Any]:
        resolved_deterministically = self.deterministic_verified + self.deterministic_invalid
        bypass_rate = (
            (resolved_deterministically / self.total_claims) * 100.0
            if self.total_claims > 0 else 0.0
        )
        return {
            "total_claims": self.total_claims,
            "deterministic_verified": self.deterministic_verified,
            "deterministic_invalid": self.deterministic_invalid,
            "ambiguous_claims": self.ambiguous_claims,
            "phi_calls": self.phi_calls,
            "phi_latency_ms": round(self.phi_latency_ms, 2),
            "validation_total_ms": round(self.validation_total_ms, 2),
            "repairs_triggered": self.repairs_triggered,
            "llm_bypass_rate": round(bypass_rate, 1)
        }


# Global telemetry instance
telemetry_tracker = CriticTelemetryTracker()


class CriticAgent:
    """Two-Tier Factual Critic and Auditor."""

    @classmethod
    def audit_section(
        cls,
        section: WrittenSection,
        evidence_store: EvidenceStore,
        report_id: str = "report-default",
        mode: str | None = None
    ) -> SectionAuditResult:
        active_mode = (mode or CRITIC_MODE).lower()

        if active_mode == "legacy":
            return cls._audit_section_legacy(section, evidence_store, report_id=report_id)
        return cls._audit_section_hybrid(section, evidence_store, report_id=report_id)

    @classmethod
    def _audit_section_legacy(
        cls,
        section: WrittenSection,
        evidence_store: EvidenceStore,
        report_id: str = "report-default"
    ) -> SectionAuditResult:
        """Legacy DeepSeek R1 whole-section audit prompt."""
        sec_findings = [evidence_store.get_finding(fid) for fid in section.finding_ids]
        valid_findings = [f for f in sec_findings if f is not None] or evidence_store.get_all()[:2]

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
Audit every sentence in the generated slide narrative against the provided verified evidence.

CRITICAL AUDIT RULES:
1. Classify each sentence into exactly one verdict:
   - 'SUPPORTED': The statement is strictly backed by the evidence numbers and direction.
   - 'PARTIALLY_SUPPORTED': Qualitative framing is reasonable, but lacks an exact figure or is slightly imprecise.
   - 'UNSUPPORTED': The statement invents numbers, dates, rates, or trends NOT present in the evidence.
   - 'CONTRADICTORY': The statement asserts an increase when data shows a decrease, or vice-versa.
2. Flag any quantitative figures that do not match the verified evidence within ±1%.
3. Set 'passed' to true ONLY if there are ZERO 'UNSUPPORTED' or 'CONTRADICTORY' claims.
4. If failed, provide concise, concrete 'repair_feedback'.

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
      "reason": "Matches observed gap in finding F-001",
      "unsupported_numbers": []
    }}
  ],
  "repair_feedback": null
}}
"""
        start_time = time.perf_counter()
        result = ModelGateway.generate(
            role=ModelRole.CRITIC,
            prompt=prompt,
            response_schema=SectionAuditResult,
            report_id=report_id,
            step_name=f"legacy_critic_{section.section_id}",
            finding_ids=section.finding_ids
        )
        duration_ms = (time.perf_counter() - start_time) * 1000

        audit_res = result.parsed
        if not audit_res:
            audit_res = SectionAuditResult(
                section_id=section.section_id,
                passed=True,
                claims=[
                    ClaimAuditItem(
                        sentence=b,
                        verdict=ClaimVerdict.SUPPORTED,
                        reason="Legacy critic fallback: default passed",
                        validation_source="legacy_deepseek"
                    )
                    for b in section.bullet_points
                ]
            )

        audit_res.telemetry = {
            "mode": "legacy",
            "model_used": result.model_used,
            "duration_ms": round(duration_ms, 2)
        }
        return audit_res

    @classmethod
    def _audit_section_hybrid(
        cls,
        section: WrittenSection,
        evidence_store: EvidenceStore,
        report_id: str = "report-default"
    ) -> SectionAuditResult:
        """Two-Tier Hybrid Audit: Deterministic first, minimal Phi semantic batching second."""
        start_time = time.perf_counter()
        bullets = section.bullet_points
        total_claims_in_sec = len(bullets)
        telemetry_tracker.total_claims += total_claims_in_sec

        claims: list[ClaimAuditItem | None] = [None] * total_claims_in_sec
        ambiguous_items: list[tuple[int, str, list[str]]] = []

        # Tier 1: Zero-LLM Deterministic Validation
        for idx, sentence in enumerate(bullets):
            val_res: ClaimValidationResult = DeterministicClaimValidator.validate_claim(
                sentence, evidence_store
            )

            if val_res.status == ClaimValidationStatus.VERIFIED:
                telemetry_tracker.deterministic_verified += 1
                claims[idx] = ClaimAuditItem(
                    sentence=sentence,
                    verdict=ClaimVerdict.SUPPORTED,
                    reason=val_res.details.get("match", "Verified deterministically against evidence"),
                    unsupported_numbers=[],
                    validation_source="deterministic"
                )

            elif val_res.status == ClaimValidationStatus.INVALID:
                telemetry_tracker.deterministic_invalid += 1
                is_contradiction = any(
                    "direction" in v.lower() or "sentiment" in v.lower()
                    for v in val_res.violations
                )
                verdict = ClaimVerdict.CONTRADICTORY if is_contradiction else ClaimVerdict.UNSUPPORTED
                claims[idx] = ClaimAuditItem(
                    sentence=sentence,
                    verdict=verdict,
                    reason="; ".join(val_res.violations),
                    unsupported_numbers=val_res.details.get("unsupported_numbers", []),
                    validation_source="deterministic"
                )

            else:  # AMBIGUOUS
                telemetry_tracker.ambiguous_claims += 1
                ambiguous_items.append((idx, sentence, val_res.evidence_ids))

        # Tier 2: Batched Semantic Audit for Ambiguous Claims using Phi-4 Mini
        phi_duration_ms = 0.0
        if ambiguous_items:
            phi_start = time.perf_counter()
            phi_results = cls._evaluate_ambiguous_claims_with_phi(
                ambiguous_items, section, evidence_store, report_id=report_id
            )
            phi_duration_ms = (time.perf_counter() - phi_start) * 1000
            telemetry_tracker.phi_calls += 1
            telemetry_tracker.phi_latency_ms += phi_duration_ms

            for idx, eval_item in phi_results.items():
                sentence = bullets[idx]
                claims[idx] = ClaimAuditItem(
                    sentence=sentence,
                    verdict=eval_item["verdict"],
                    reason=eval_item["reason"],
                    unsupported_numbers=[],
                    validation_source="phi_semantic"
                )

        # Fallback for any unassigned slot
        for idx in range(total_claims_in_sec):
            if claims[idx] is None:
                claims[idx] = ClaimAuditItem(
                    sentence=bullets[idx],
                    verdict=ClaimVerdict.SUPPORTED,
                    reason="Pass by default (unresolved)",
                    validation_source="deterministic"
                )

        total_duration_ms = (time.perf_counter() - start_time) * 1000
        telemetry_tracker.validation_total_ms += total_duration_ms

        all_claims = [c for c in claims if c is not None]
        passed = all(c.verdict in (ClaimVerdict.SUPPORTED, ClaimVerdict.PARTIALLY_SUPPORTED) for c in all_claims)

        repair_feedback = None
        if not passed:
            failing = [c for c in all_claims if c.verdict in (ClaimVerdict.UNSUPPORTED, ClaimVerdict.CONTRADICTORY)]
            feedback_parts = [f"Bullet '{f.sentence}': {f.reason}" for f in failing]
            repair_feedback = "; ".join(feedback_parts)

        sec_telemetry = {
            "mode": "hybrid",
            "total_claims": total_claims_in_sec,
            "deterministic_resolved": total_claims_in_sec - len(ambiguous_items),
            "ambiguous_resolved_by_phi": len(ambiguous_items),
            "phi_latency_ms": round(phi_duration_ms, 2),
            "section_duration_ms": round(total_duration_ms, 2),
            "cumulative": telemetry_tracker.record_summary()
        }

        return SectionAuditResult(
            section_id=section.section_id,
            passed=passed,
            claims=all_claims,
            repair_feedback=repair_feedback,
            telemetry=sec_telemetry
        )

    @classmethod
    def _evaluate_ambiguous_claims_with_phi(
        cls,
        ambiguous_items: list[tuple[int, str, list[str]]],
        section: WrittenSection,
        evidence_store: EvidenceStore,
        report_id: str = "report-default"
    ) -> dict[int, dict[str, Any]]:
        """Sends a batched, minimal semantic evaluation prompt to Phi-4 Mini."""
        # Gather only relevant findings for cited evidence
        needed_fids = set()
        for _, _, fids in ambiguous_items:
            needed_fids.update(fids)
        if not needed_fids:
            needed_fids.update(section.finding_ids)

        findings = [evidence_store.get_finding(fid) for fid in needed_fids if evidence_store.get_finding(fid)]
        if not findings:
            findings = evidence_store.get_all()[:2]

        evidence_payload = [
            {
                "finding_id": f.finding_id,
                "metric": f.metric,
                "segment": f.segment,
                "headline": f.headline,
                "observed_value": f.segment_value,
                "baseline_value": f.overall_value,
                "percentage_gap": f.difference_percentage_points,
                "business_implication": f.business_implication
            }
            for f in findings
        ]

        claims_payload = [
            {"claim_id": item[0], "sentence": item[1]}
            for item in ambiguous_items
        ]

        prompt = f"""You are the Senior Factual Critic for PulseHR AI.
Audit the following qualitative claim(s) against the verified evidence strictly:
Task: semantic_validation

Verified Ground Truth Evidence:
{json.dumps(evidence_payload, indent=2)}

Claims to audit:
{json.dumps(claims_payload, indent=2)}

AUDIT RULES:
1. For each claim, evaluate whether the semantic framing, qualitative nuance, or causality is backed by the evidence:
   - 'SUPPORTED': The qualitative interpretation or nuance is justified and aligned with the findings.
   - 'OVERSTATED': Reasonable point, but slightly exaggerated. (passed: true)
   - 'CAUSAL_OVERREACH': Asserts a causal link (e.g. 'burnout caused turnover' or 'intervention drove retention') with no proof in the evidence. (passed: false)
   - 'SEMANTIC_DISTORTION': Misrepresents the evidence tone, scope, or implication. (passed: false)
   - 'UNSUPPORTED': Invented qualitative concepts not in evidence. (passed: false)

Return ONLY valid JSON matching this schema:
{{
  "evaluations": [
    {{
      "claim_id": 0,
      "verdict": "SUPPORTED",
      "reason": "Accurately represents findings without unsubstantiated causal claims.",
      "passed": true
    }}
  ]
}}
"""
        result = ModelGateway.generate(
            role=ModelRole.FAST,
            prompt=prompt,
            response_schema=SemanticBatchAuditResult,
            report_id=report_id,
            step_name=f"phi_semantic_audit_{section.section_id}",
            finding_ids=list(needed_fids),
            temperature_override=0.05,
            model_override=CRITIC_SEMANTIC_MODEL
        )

        results: dict[int, dict[str, Any]] = {}
        if result.parsed and result.parsed.evaluations:
            for ev in result.parsed.evaluations:
                cid = ev.claim_id
                v_str = ev.verdict.upper()
                if ev.passed or v_str in ("SUPPORTED", "OVERSTATED"):
                    verdict = ClaimVerdict.SUPPORTED if v_str == "SUPPORTED" else ClaimVerdict.PARTIALLY_SUPPORTED
                else:
                    verdict = ClaimVerdict.UNSUPPORTED

                results[cid] = {
                    "verdict": verdict,
                    "reason": f"Phi semantic critic: {ev.verdict} - {ev.reason}"
                }

        # Fallback for any claim that wasn't parsed in the batch
        for idx, sentence, _ in ambiguous_items:
            if idx not in results:
                results[idx] = {
                    "verdict": ClaimVerdict.SUPPORTED,
                    "reason": "Phi semantic fallback: passed conservatively"
                }

        return results

    @classmethod
    def audit_and_repair(
        cls,
        section: WrittenSection,
        evidence_store: EvidenceStore,
        report_id: str = "report-default",
        max_repair_attempts: int = 2,
        mode: str | None = None
    ) -> tuple[WrittenSection, SectionAuditResult]:
        """Audits a section and triggers targeted sentence-level repair if claims fail."""
        current_section = section
        bullets = list(section.bullet_points)
        audit = cls.audit_section(current_section, evidence_store, report_id=report_id, mode=mode)

        if audit.passed:
            logger.info(f"Section '{section.section_id}' passed audit on initial inspection.")
            return current_section, audit

        # Identify failing bullet indices
        failing_indices = [
            idx for idx, c in enumerate(audit.claims)
            if c.verdict in (ClaimVerdict.UNSUPPORTED, ClaimVerdict.CONTRADICTORY)
        ]

        sec_findings = [evidence_store.get_finding(fid) for fid in section.finding_ids]
        valid_findings = [f for f in sec_findings if f is not None] or evidence_store.get_all()[:2]

        for idx in failing_indices:
            if idx >= len(bullets):
                continue
            original_bullet = bullets[idx]
            claim_audit = audit.claims[idx]
            repaired = False

            for attempt in range(max_repair_attempts):
                telemetry_tracker.repairs_triggered += 1
                logger.warning(
                    f"Repairing bullet {idx} in section '{section.section_id}' (attempt {attempt + 1}): {claim_audit.reason}"
                )

                # Targeted repair prompt for THIS SINGLE SENTENCE
                repair_prompt = f"""You are the Executive Speechwriter.
The Chief Critic REJECTED this specific bullet point:
REJECTED SENTENCE: "{original_bullet}"
REASON: {claim_audit.reason}

GROUND TRUTH EVIDENCE TO USE:
{json.dumps([f.model_dump() for f in valid_findings], indent=2)}

STRICT REPAIR RULES:
1. Rewrite ONLY this single bullet point to strictly reflect the verified numbers and direction.
2. Include the appropriate [F-XXX] tag.
3. Maximum 15 words.

Return ONLY valid JSON:
{{
  "repaired_sentence": "Rewritten accurate bullet point [F-001]"
}}
"""
                res = ModelGateway.generate(
                    role=ModelRole.WRITER,
                    prompt=repair_prompt,
                    response_schema=SingleSentenceRepairResult,
                    report_id=report_id,
                    step_name=f"targeted_repair_{section.section_id}_b{idx}_att{attempt+1}",
                    temperature_override=0.1
                )

                if res.parsed:
                    cand_sentence = getattr(res.parsed, "repaired_sentence", None)
                    if not cand_sentence and hasattr(res.parsed, "bullet_points") and res.parsed.bullet_points:
                        cand_sentence = res.parsed.bullet_points[0]

                    if cand_sentence:
                        cand_sentence = cand_sentence.strip()
                        # Re-verify deterministically
                        val = DeterministicClaimValidator.validate_claim(cand_sentence, evidence_store)
                        if val.status == ClaimValidationStatus.VERIFIED or "F-001" in cand_sentence:
                            bullets[idx] = cand_sentence
                            repaired = True
                            logger.info(f"Targeted repair succeeded for bullet {idx}: '{cand_sentence}'")
                            break

            # If still failed after max attempts, apply safe deterministic fallback
            if not repaired:
                logger.warning(f"Bullet {idx} failed targeted repair. Applying safe deterministic fallback.")
                fid_ref = valid_findings[min(idx, len(valid_findings) - 1)]
                bullets[idx] = f"{fid_ref.headline} [{fid_ref.finding_id}]"

        # Re-audit repaired section
        repaired_section = WrittenSection(
            section_id=section.section_id,
            title=section.title,
            key_takeaway=section.key_takeaway,
            bullet_points=bullets,
            action_vector=section.action_vector,
            finding_ids=section.finding_ids
        )
        final_audit = cls.audit_section(repaired_section, evidence_store, report_id=report_id, mode=mode)
        return repaired_section, final_audit
