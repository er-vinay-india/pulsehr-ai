"""Stage A: Analyst Agent.
Interprets deterministic candidate facts and dataset profile to surface material findings.
The Analyst model determines what matters without calculating numbers from scratch."""

import json
import logging
from typing import Any
from pydantic import BaseModel, Field

from ..data_engine.metric_engine import CandidateFact
from ..data_engine.profiler import DatasetProfile
from ..evidence.evidence_models import Finding, FindingType, Importance, EvidenceReference
from ..evidence.evidence_store import EvidenceStore
from ..gateway.model_gateway import ModelGateway
from ...core.models_config import ModelRole

logger = logging.getLogger(__name__)


class AnalystFindingItem(BaseModel):
    candidate_fact_id: str
    finding_id: str
    finding_type: str  # "performance_gap", "outperformer", "headwind", "baseline_benchmark", "trend_shift"
    importance: str    # "high", "medium", "low"
    headline: str
    business_implication: str


class AnalystOutputSchema(BaseModel):
    findings: list[AnalystFindingItem] = Field(default_factory=list)


class AnalystAgent:
    """Agent representing the ANALYST role (backed by Qwen 3.5)."""

    @classmethod
    def analyze(
        cls,
        candidate_facts: list[CandidateFact],
        profile: DatasetProfile,
        report_id: str = "report-default"
    ) -> EvidenceStore:
        store = EvidenceStore()
        if not candidate_facts:
            return store

        facts_lookup = {f.fact_id: f for f in candidate_facts}
        facts_payload = [
            {
                "fact_id": f.fact_id,
                "type": f.fact_type,
                "metric": f.metric,
                "segment": f.segment,
                "observed_value": f.observed_value,
                "baseline_value": f.baseline_value,
                "difference": f.difference,
                "percentage_gap": f.percentage_gap,
                "sample_size": f.sample_size
            }
            for f in candidate_facts[:12]
        ]

        prompt = f"""You are the Principal Lead Data Analyst.
Your responsibility: Review the pre-calculated empirical facts from '{profile.dataset_name}' ({profile.business_domain}) and identify the 4 to 8 most material findings.

CRITICAL RULES:
1. DO NOT recalculate numbers. Rely strictly on the supplied observed values, differences, and percentage gaps.
2. Filter out trivial variance; prioritize high-impact operational gaps, outperforming leaders, and severe headwinds.
3. Every headline must be a concise, assertive executive takeaway under 15 words.
4. Classify each finding into: 'outperformer', 'headwind', 'performance_gap', 'baseline_benchmark', or 'trend_shift'.
5. Assign importance: 'high', 'medium', or 'low'.

## Verified Candidate Facts:
{json.dumps(facts_payload, indent=2)}

Return a valid JSON object matching this schema:
{{
  "findings": [
    {{
      "candidate_fact_id": "FACT-001",
      "finding_id": "F-001",
      "finding_type": "outperformer",
      "importance": "high",
      "headline": "Engineering leads all departments with 92.4% on-time project completion",
      "business_implication": "Engineering operational benchmarks can be replicated across slower divisions"
    }}
  ]
}}
"""

        result = ModelGateway.generate(
            role=ModelRole.ANALYST,
            prompt=prompt,
            response_schema=AnalystOutputSchema,
            report_id=report_id,
            step_name="analyst_finding_discovery"
        )

        parsed_items: list[AnalystFindingItem] = []
        if result.success and result.parsed and result.parsed.findings:
            parsed_items = result.parsed.findings

        # If LLM returned valid findings, map them to EvidenceStore
        if parsed_items:
            for item in parsed_items:
                fact = facts_lookup.get(item.candidate_fact_id) or candidate_facts[0]
                try:
                    ftype = FindingType(item.finding_type.lower())
                except ValueError:
                    ftype = FindingType.PERFORMANCE_GAP

                try:
                    imp = Importance(item.importance.lower())
                except ValueError:
                    imp = Importance.MEDIUM

                finding = Finding(
                    finding_id=item.finding_id or f"F-{len(store.get_all())+1:03d}",
                    type=ftype,
                    metric=fact.metric,
                    segment=fact.segment,
                    segment_value=fact.observed_value,
                    overall_value=fact.baseline_value,
                    difference=fact.difference,
                    difference_percentage_points=fact.percentage_gap,
                    importance=imp,
                    headline=item.headline,
                    business_implication=item.business_implication,
                    evidence=[
                        EvidenceReference(
                            source_sheet=profile.dataset_name,
                            metric=fact.metric,
                            segment=fact.segment,
                            row_count=fact.sample_size,
                            proof=fact.raw_proof
                        )
                    ]
                )
                store.add_finding(finding)

        # Fallback if LLM failed or returned 0 findings: deterministic mapping
        if len(store.get_all()) == 0:
            logger.info("Using deterministic fallback to populate EvidenceStore.")
            for idx, fact in enumerate(candidate_facts[:6], start=1):
                ftype = (
                    FindingType.OUTPERFORMER if (fact.difference or 0) > 0 and fact.fact_type == "segment_gap"
                    else (FindingType.HEADWIND if (fact.difference or 0) < 0 and fact.fact_type == "segment_gap"
                    else FindingType.BASELINE_BENCHMARK)
                )
                finding_id = f"F-{idx:03d}"
                diff_str = f" ({fact.percentage_gap:+.1f}% vs baseline)" if fact.percentage_gap is not None else ""
                headline = f"{fact.segment or fact.metric}: {fact.observed_value}{diff_str}"
                implication = f"Statistical monitoring required for {fact.metric} across operating segments."

                finding = Finding(
                    finding_id=finding_id,
                    type=ftype,
                    metric=fact.metric,
                    segment=fact.segment,
                    segment_value=fact.observed_value,
                    overall_value=fact.baseline_value,
                    difference=fact.difference,
                    difference_percentage_points=fact.percentage_gap,
                    importance=Importance.HIGH if idx <= 2 else Importance.MEDIUM,
                    headline=headline,
                    business_implication=implication,
                    evidence=[
                        EvidenceReference(
                            source_sheet=profile.dataset_name,
                            metric=fact.metric,
                            segment=fact.segment,
                            row_count=fact.sample_size,
                            proof=fact.raw_proof
                        )
                    ]
                )
                store.add_finding(finding)

        return store
