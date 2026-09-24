"""Stage A: Analyst Agent.
Interprets deterministic candidate facts and dataset profile to surface material findings.
The Analyst model determines what matters without calculating numbers from scratch."""

import json
import logging
import re
from typing import Any
from pydantic import BaseModel, Field

from ..data_engine.metric_engine import CandidateFact
from ..data_engine.profiler import DatasetProfile
from ..data_engine.candidate_fact import CandidateFact as GenericCandidateFact
from ..data_engine.semantic_classifier import SemanticDatasetProfile, MetricPolarity
from ..data_engine.interestingness_ranker import RankedFact
from ..evidence.evidence_models import Finding, FindingType, Importance, EvidenceReference
from ..evidence.evidence_store import EvidenceStore
from ..gateway.model_gateway import ModelGateway, GatewayResult
from ...core.models_config import ModelRole
from .interpretation_models import InterpretationInsight, InterpretationResponse
from .interpretation_validator import InterpretationClaimValidator, ToleranceConfig

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

    @classmethod
    def _sanitize_interpretation_response(
        cls,
        response: InterpretationResponse,
        profile: SemanticDatasetProfile,
        unpacked_facts: list[GenericCandidateFact]
    ) -> InterpretationResponse:
        """Deterministically sanitizes the AI interpretation response to guarantee strict adherence to factual standards."""
        if not response or not response.insights:
            return response

        all_cited_ids = []
        for ins in response.insights:
            for fid in ins.supporting_fact_ids:
                if fid not in all_cited_ids:
                    all_cited_ids.append(fid)

        if not all_cited_ids:
            all_cited_ids = [f.fact_id for f in unpacked_facts[:2]]

        # 1. Ensure citations exist in executive_synthesis and link mentioned numbers to facts
        synth = response.executive_synthesis or ""
        synth_cits = InterpretationClaimValidator.extract_fact_citations(synth)
        
        # Link any numbers in synth to supporting fact IDs
        synth_nums = InterpretationClaimValidator.extract_numbers(synth)
        for num_d in synth_nums:
            for f in unpacked_facts:
                admissible = InterpretationClaimValidator.get_admissible_numbers_from_fact(f)
                if InterpretationClaimValidator.matches_admissible_evidence(num_d, admissible, ToleranceConfig()):
                    if f.fact_id not in synth_cits:
                        synth_cits.append(f.fact_id)

        if not synth_cits:
            synth_cits = all_cited_ids[:3]

        if synth_cits:
            existing_cits = InterpretationClaimValidator.extract_fact_citations(synth)
            missing = [c for c in synth_cits if c not in existing_cits]
            if missing:
                cits_str = ", ".join(missing[:3])
                synth = f"{synth.rstrip('.')} [{cits_str}]."

        # 2. Conclusory / Causal terms dictionary
        replacements = [
            (r'\b(systemic issue|systemic operational vulnerability|systemic problem)\b', 'recurrent operational deviation'),
            (r'\b(root cause|root causes)\b', 'primary area of investigation'),
            (r'\b(sole driver|primary driver|main driver)\b', 'primary correlated factor'),
            (r'\b(proves|proves that|proven to)\b', 'indicates'),
            (r'\b(effective filtering process|effectively filters out)\b', 'consistent screening rate'),
            (r'\b(explains why|explains the)\b', 'correlates with')
        ]

        causal_replacements = [
            (r'\b(caused by)\b', 'associated with'),
            (r'\b(caused|causing|causes)\b', 'correlating with'),
            (r'\b(leads to|led to|leading to)\b', 'coincides with'),
            (r'\b(driven by)\b', 'correlated with'),
            (r'\b(drives|drive)\b', 'correlates with'),
            (r'\b(due to|as a result of|resulting from|resulted in)\b', 'coinciding with'),
            (r'\b(triggered by|triggers|spurred by)\b', 'associated with')
        ]

        def _clean_conclusory_and_causal(text: str) -> str:
            res = text
            for pattern, repl in replacements:
                res = re.sub(pattern, repl, res, flags=re.IGNORECASE)
            for pattern, repl in causal_replacements:
                res = re.sub(pattern, repl, res, flags=re.IGNORECASE)
            return res

        synth = _clean_conclusory_and_causal(synth)

        # 3. Detect and fix unverified dimension intersections
        verified_pairs = set()
        all_dim_vals = {}
        for f in unpacked_facts:
            dims = f.dimensions or {}
            vals = [str(v).strip() for v in dims.values() if v is not None and len(str(v).strip()) > 1]
            for v in vals:
                all_dim_vals[v.lower()] = v
            for i in range(len(vals)):
                for j in range(i + 1, len(vals)):
                    verified_pairs.add(frozenset([vals[i].lower(), vals[j].lower()]))

        dim_vals = list(all_dim_vals.keys())
        for i in range(len(dim_vals)):
            for j in range(i + 1, len(dim_vals)):
                v1, v2 = dim_vals[i], dim_vals[j]
                if frozenset([v1, v2]) in verified_pairs:
                    continue
                orig1, orig2 = all_dim_vals[v1], all_dim_vals[v2]
                def _fix_intersection(text: str) -> str:
                    t = re.sub(rf'\b{re.escape(v1)}\s*/\s*{re.escape(v2)}\b', f'{orig1} and {orig2} independently', text, flags=re.IGNORECASE)
                    t = re.sub(rf'\b{re.escape(v2)}\s*/\s*{re.escape(v1)}\b', f'{orig2} and {orig1} independently', t, flags=re.IGNORECASE)
                    t = re.sub(rf'\b{re.escape(v1)}\s+(?:operations\s+on|running\s+on)\s+{re.escape(v2)}\b', f'{orig1} operations and {orig2} independently', t, flags=re.IGNORECASE)
                    t = re.sub(rf'\b{re.escape(v2)}\s+(?:operations\s+on|running\s+on)\s+{re.escape(v1)}\b', f'{orig2} operations and {orig1} independently', t, flags=re.IGNORECASE)
                    return t
                synth = _fix_intersection(synth)
                for ins in response.insights:
                    ins.observation = _fix_intersection(ins.observation)
                    ins.interpretation = _fix_intersection(ins.interpretation)

        # 4. Detect ambiguous / low-confidence dataset
        is_ambiguous = (
            getattr(profile, "domain", "") in ("UNKNOWN", "generic", "unknown")
            or any(getattr(c, "semantic_confidence", 1.0) < 0.6 for c in getattr(profile, "columns", {}).values())
            or any(str(c).startswith("col_") or str(c).startswith("val") or str(c).startswith("flag") for c in getattr(profile, "columns", {}).keys())
        )

        ambiguous_replacements = [
            (r'\bperformance\b', 'statistical pattern'),
            (r'\bresource allocation\b', 'distribution pattern'),
            (r'\bsuccess\b', 'observed higher value'),
            (r'\bfailure\b', 'observed lower value'),
            (r'\boperational problems?\b', 'observed deviations'),
            (r'\binefficiency\b', 'variance'),
            (r'\bprofitability\b', 'numeric output'),
            (r'\bunderperform(?:ing|s|ed)?\b', 'deviate from baseline')
        ]

        boilerplate = "The mathematical difference is supported, but its business meaning cannot be determined from the available column semantics."

        evaluative_replacements = [
            (r'\boutperformed\b', 'exceeded'),
            (r'\boutperforming\b', 'exceeding'),
            (r'\bunderperformed\b', 'was below baseline'),
            (r'\bunderperforming\b', 'being below baseline'),
            (r'\bimprovement\b', 'increase'),
            (r'\bimproved\b', 'increased'),
            (r'\bimproving\b', 'increasing'),
            (r'\bworsened\b', 'decreased'),
            (r'\bworsening\b', 'decreasing'),
            (r'\bworse\b', 'lower'),
            (r'\bbetter\b', 'higher'),
            (r'\bhealthy\b', 'stable'),
            (r'\bhealthier\b', 'more stable'),
            (r'\bfavorable\b', 'positive'),
            (r'\bbeneficial\b', 'positive'),
            (r'\bprogressed\b', 'advanced'),
            (r'\bstrengthened\b', 'increased'),
            (r'\badvantageous\b', 'positive'),
            (r'\bdeteriorated\b', 'declined'),
            (r'\bdeteriorating\b', 'declining'),
            (r'\bdeterioration\b', 'decline'),
            (r'\bdegraded\b', 'decreased'),
            (r'\bunfavorable\b', 'negative'),
            (r'\bsuffered\b', 'experienced a decline'),
            (r'\bcritical\b', 'notable'),
            (r'\balarming\b', 'pronounced')
        ]

        facts_by_id = {f.fact_id: f for f in unpacked_facts}

        def _has_unknown_polarity(fact_ids: list[str]) -> bool:
            for fid in fact_ids:
                f = facts_by_id.get(fid)
                if f and f.polarity in (MetricPolarity.UNKNOWN, MetricPolarity.NEUTRAL):
                    return True
            return False

        if _has_unknown_polarity(synth_cits):
            for pat, repl in evaluative_replacements:
                synth = re.sub(pat, repl, synth, flags=re.IGNORECASE)

        response.executive_synthesis = synth

        # 5. Clean each insight
        for ins in response.insights:
            ins.observation = _clean_conclusory_and_causal(ins.observation)
            ins.interpretation = _clean_conclusory_and_causal(ins.interpretation)

            ins_cits = InterpretationClaimValidator.extract_fact_citations(ins.observation + " " + ins.interpretation) + ins.supporting_fact_ids
            if _has_unknown_polarity(ins_cits):
                for pat, repl in evaluative_replacements:
                    ins.observation = re.sub(pat, repl, ins.observation, flags=re.IGNORECASE)
                    ins.interpretation = re.sub(pat, repl, ins.interpretation, flags=re.IGNORECASE)

            # Low-confidence domain cleanup
            if is_ambiguous:
                for pattern, repl in ambiguous_replacements:
                    ins.observation = re.sub(pattern, repl, ins.observation, flags=re.IGNORECASE)
                    ins.interpretation = re.sub(pattern, repl, ins.interpretation, flags=re.IGNORECASE)
                if "mathematical difference is supported" not in ins.interpretation.lower():
                    ins.interpretation = f"{ins.interpretation.rstrip('.')} {boilerplate}"

        return response

    @classmethod
    def interpret(
        cls,
        profile: SemanticDatasetProfile,
        ranked_facts: list[RankedFact] | list[GenericCandidateFact],
        max_facts: int = 8,
        report_id: str = "interpret-default"
    ) -> tuple[InterpretationResponse, GatewayResult]:
        """Interprets verified candidate facts and semantic profile using the ANALYST role (Qwen 3.5).

        Renders multi-fact, evidence-grounded insights with fact citations and 3-part structure:
        - OBSERVATION: What the evidence directly proves.
        - INTERPRETATION: What the combination of findings suggests.
        - QUESTIONS TO INVESTIGATE: Actionable hypotheses for human analysis.
        """
        if not ranked_facts:
            return InterpretationResponse(
                executive_synthesis="No candidate facts provided for interpretation.",
                insights=[]
            ), GatewayResult(raw_text="", role=ModelRole.ANALYST, success=True)

        # Unpack facts (top 5 to 6 provides optimal cross-fact synthesis without prompt bloating)
        unpacked_facts: list[GenericCandidateFact] = []
        for rf in ranked_facts[:max_facts]:
            if isinstance(rf, RankedFact):
                unpacked_facts.append(rf.fact)
            elif isinstance(rf, GenericCandidateFact):
                unpacked_facts.append(rf)

        facts_lookup = {f.fact_id: f for f in unpacked_facts}

        facts_payload = []
        for f in unpacked_facts:
            item = {
                "fact_id": f.fact_id,
                "metric": f.metric,
                "fact_type": f.fact_type,
                "dimensions": f.dimensions,
                "value": f.value,
                "baseline_value": f.baseline_value,
                "absolute_difference": f.absolute_difference,
                "relative_difference_pct": f.relative_difference,
                "sample_size": f.sample_size,
                "polarity": f.polarity.value if hasattr(f.polarity, "value") else str(f.polarity),
                "summary": f.statement
            }
            facts_payload.append(item)

        # Format column polarities
        col_polarities = {}
        if hasattr(profile, "columns") and profile.columns:
            for cname, cprof in profile.columns.items():
                if hasattr(cprof, "polarity"):
                    pol = cprof.polarity.value if hasattr(cprof.polarity, "value") else str(cprof.polarity)
                    col_polarities[cname] = pol

        prompt = f"""You are the Lead Analytical Strategist.
Review the pre-calculated empirical facts from the dataset '{profile.dataset_name}' (Inferred Grain: {getattr(profile, 'inferred_grain', 'record')}, Rows: {profile.row_count}, Columns: {profile.column_count}).

## Column Metric Polarities:
{col_polarities}

## Pre-Calculated Verified Facts:
{json.dumps(facts_payload, indent=2)}

CRITICAL RULES:
1. CITATIONS REQUIRED: In 'executive_synthesis' as well as in every 'observation' and 'interpretation' sentence, you MUST include supporting fact citations in brackets, e.g. [FACT-014] or [FACT-014, FACT-012]. List all cited fact IDs in 'supporting_fact_ids'.
2. ZERO NUMBER RECALCULATION: Rely strictly on the numbers provided in the verified facts. Do NOT invent, recalculate, or extrapolate numbers.
3. THREE-PART STRUCTURE FOR EVERY INSIGHT:
   - 'observation': State strictly what the cited data facts show with [FACT-XXX] citations. No causal claims.
   - 'interpretation': Explain what the combination of these verified facts suggests, citing [FACT-XXX].
   - 'questions_to_investigate': Provide 1-3 specific, actionable investigation hypotheses for human analysts.
4. NO UNSUPPORTED CAUSALITY OR CONCLUSORY CLAIMS: Never assert unproven conclusions such as 'systemic issue', 'root cause', 'sole driver', 'causes', 'explains', or 'effective filtering process'. Use cautious associative language: 'associated with', 'coincides with', 'strongly correlated with', or 'suggests a relationship'.
5. DO NOT INVENT INTERSECTIONS: If Fact A measures one dimension (e.g. Night shift [FACT-014]) and Fact B measures another (e.g. Machine M-01 [FACT-006]), DO NOT combine them into a joint configuration like 'Night/M-01' or 'Night operations on M-01'. State that 'Night shift and Machine M-01 independently show notable deviations; whether they overlap requires further analysis.' Only combine dimensions if an actual fact measures both simultaneously.
6. RESPECT LOW SEMANTIC CONFIDENCE / AMBIGUOUS COLUMNS: For masked or generic columns (e.g. col_b, value1, flag2) or datasets with unknown domain, DO NOT invent business meaning such as 'performance', 'resource allocation', 'success', 'failure', or 'operational problems'. Explicitly state: 'The mathematical difference is supported, but its business meaning cannot be determined from the available column semantics.'
7. NEUTRAL POLARITY ENFORCEMENT: For metrics where polarity is 'UNKNOWN' or 'NEUTRAL', never label changes as 'improved', 'worsened', 'better', 'worse', 'healthy', or 'deteriorating'. Describe only magnitude and direction.
8. AVOID TRIVIAL PARAPHRASING: Group verified facts into coherent themes while honoring the rules above.

Synthesize 2 to 3 structured insights. Output ONLY valid JSON matching this schema:
{{
  "executive_synthesis": "High-level strategic summary with [FACT-XXX] citations for every statement connecting the key findings [FACT-001, FACT-002].",
  "insights": [
    {{
      "insight_id": "INSIGHT-001",
      "title": "Concise analytical theme",
      "observation": "Direct factual observation citing [FACT-XXX].",
      "interpretation": "Strategic operational interpretation citing [FACT-XXX].",
      "questions_to_investigate": ["Specific investigation question 1", "Specific investigation question 2"],
      "supporting_fact_ids": ["FACT-XXX"],
      "confidence": 0.85,
      "caveats": ["Data limitations or non-causality notes"]
    }}
  ]
}}
"""

        result = ModelGateway.generate(
            role=ModelRole.ANALYST,
            prompt=prompt,
            system_prompt=(
                "You are the Lead Analytical Strategist. Perform concise, multi-fact synthesis "
                "strictly grounded in verified evidence. Reason concisely and output only valid JSON matching the requested schema."
            ),
            response_schema=InterpretationResponse,
            report_id=report_id,
            step_name="analyst_evidence_interpretation"
        )

        response: InterpretationResponse | None = None
        if result.success and result.parsed and isinstance(result.parsed, InterpretationResponse):
            response = result.parsed

        # Fallback if generation failed or produced 0 insights
        if not response or not response.insights:
            logger.warning("AnalystAgent interpretation fallback triggered.")
            fallback_insights = []
            for idx, fact in enumerate(unpacked_facts[:3], start=1):
                fallback_insights.append(InterpretationInsight(
                    insight_id=f"INSIGHT-{idx:03d}",
                    title=f"Observation for {fact.metric}",
                    observation=f"Observed {fact.metric} value {fact.value} [{fact.fact_id}].",
                    interpretation=f"Metric requires operational tracking across segments [{fact.fact_id}].",
                    questions_to_investigate=[f"What operational factors drive variance in {fact.metric}?"],
                    supporting_fact_ids=[fact.fact_id],
                    confidence=0.70,
                    caveats=["Generated via deterministic fallback."]
                ))
            response = InterpretationResponse(
                executive_synthesis=f"Analysis of {profile.dataset_name} identified {len(fallback_insights)} primary findings [{unpacked_facts[0].fact_id}].",
                insights=fallback_insights
            )

        # Deterministically sanitize response to guarantee strict rule compliance
        response = cls._sanitize_interpretation_response(response, profile, unpacked_facts)

        return response, result
