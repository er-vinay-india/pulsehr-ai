"""Explicit Workflow Orchestrator implementing the full end-to-end generic reporting state machine."""

import hashlib
import logging
from typing import Any, Callable
from uuid import uuid4
import pandas as pd
from pydantic import BaseModel, Field

from ..data_engine.validator import DatasetValidator, DataQualityReport
from ..data_engine.semantic_classifier import SemanticClassifier, SemanticDatasetProfile
from ..data_engine.opportunity_map import OpportunityMapGenerator, AnalysisOpportunityMap
from ..data_engine.candidate_fact_discovery import CandidateFactDiscoveryEngine
from ..data_engine.candidate_fact import CandidateFact
from ..data_engine.interestingness_ranker import FactInterestingnessRanker, RankedFact
from ..data_engine.fact_visualizer import FactVisualizer
from ..data_engine.visualization_models import VisualChartSpec
from ..analyst.analyst_agent import AnalystAgent
from ..analyst.interpretation_models import InterpretationResponse, InterpretationInsight
from ..analyst.interpretation_validator import InterpretationClaimValidator, InterpretationAuditResult
from .writer_agent import GeneratedReport, WrittenSection

logger = logging.getLogger(__name__)

# Single source of truth cache: maps dataset SHA256 fingerprint -> WorkflowExecutionResult
_GENERIC_WORKFLOW_CACHE: dict[str, "WorkflowExecutionResult"] = {}


class WorkflowExecutionResult(BaseModel):
    """Holistic execution artifact returned by the WorkflowOrchestrator."""
    report_id: str
    status: str  # "COMPLETED", "DATA_QUALITY_REJECTED", "ERROR"
    quality_report: DataQualityReport | None = None
    semantic_profile: SemanticDatasetProfile | None = None
    candidate_fact_count: int = 0
    ranked_fact_count: int = 0
    interpretation: InterpretationResponse | None = None
    audit_result: InterpretationAuditResult | None = None
    visual_charts: list[VisualChartSpec] = Field(default_factory=list)
    deck_spec: dict[str, Any] = Field(default_factory=dict)
    analysis_context: Any | None = None
    error_message: str | None = None

    # Backwards compatibility accessors
    @property
    def finding_count(self) -> int:
        return self.candidate_fact_count

    @property
    def profile(self) -> SemanticDatasetProfile | None:
        return self.semantic_profile


class WorkflowOrchestrator:
    """Explicit state machine coordinating generic profiling, fact discovery, ranking, interpretation, and visualization."""

    @classmethod
    def execute(
        cls,
        df: pd.DataFrame,
        dataset_name: str = "Uploaded Dataset",
        objective: str = "Executive Leadership Briefing",
        on_progress: Callable[[str, int], None] | None = None,
        report_id: str | None = None,
        use_cache: bool = True,
        context: Any | None = None
    ) -> WorkflowExecutionResult:
        rid = report_id or f"report-{uuid4().hex[:8]}"

        effective_objective = (context.user_objective if (context and getattr(context, "user_objective", None)) else objective) or "Executive Leadership Briefing"

        # Compute dataset fingerprint for single-source-of-truth artifact reuse
        cache_key = hashlib.sha256(
            f"{dataset_name}_{effective_objective}_{df.shape}_{list(df.columns)}_{df.iloc[:5].to_dict() if len(df) else ''}".encode()
        ).hexdigest()
        if use_cache and cache_key in _GENERIC_WORKFLOW_CACHE:
            logger.info(f"Reusing cached workflow execution result for key {cache_key[:12]}")
            return _GENERIC_WORKFLOW_CACHE[cache_key]

        def _progress(msg: str, pct: int):
            if on_progress:
                on_progress(msg, pct)
            logger.info(f"[Workflow {rid}] {pct}%: {msg}")

        try:
            # 1. VALIDATE DATASET
            _progress("Validating dataset integrity and structure", 10)
            quality = DatasetValidator.validate(df, dataset_name=dataset_name)
            if not quality.is_valid:
                logger.warning(f"Workflow {rid} halted due to critical data quality failures: {quality.critical_errors}")
                return WorkflowExecutionResult(
                    report_id=rid,
                    status="DATA_QUALITY_REJECTED",
                    quality_report=quality,
                    error_message="; ".join(quality.critical_errors)
                )

            # 2. GENERIC SEMANTIC PROFILING & GRAIN DETECTION
            _progress("Profiling semantic roles, grain, and distributions", 25)
            semantic_profile = SemanticClassifier.profile_dataset(df, dataset_name=dataset_name)

            # 3. GENERATE ANALYSIS OPPORTUNITY MAP
            _progress("Mapping mathematical analysis opportunities (User Priorities & Discovery)", 40)
            opp_map = OpportunityMapGenerator.generate(semantic_profile, context=context)

            # 4. DISCOVER DETERMINISTIC CANDIDATE FACTS
            _progress("Discovering mathematically defensible candidate facts", 55)
            reliable_facts, skipped_facts = CandidateFactDiscoveryEngine.discover_facts(
                df, semantic_profile, opp_map, max_facts_per_opportunity=4
            )
            facts_lookup = {f.fact_id: f for f in reliable_facts}

            # 5. RANK FACTS BY MULTI-SIGNAL INTERESTINGNESS (User Priorities First)
            _progress("Ranking verified findings by user priority and surprise magnitude", 65)
            ranked_facts = FactInterestingnessRanker.rank_interesting_facts(reliable_facts, limit=8)

            # 6. EVIDENCE-GROUNDED AI INTERPRETATION (AnalystAgent Qwen 3.5)
            _progress("Synthesizing evidence-grounded strategic interpretation via Analyst role", 78)
            interpretation, gateway_result = AnalystAgent.interpret(
                semantic_profile, ranked_facts, max_facts=6, report_id=rid
            )

            # 7. DETERMINISTIC INTERPRETATION CLAIM AUDIT
            _progress("Auditing interpretation assertions for strict factual fidelity", 88)
            audit_result = InterpretationClaimValidator.audit_response(
                interpretation, facts_lookup, profile=semantic_profile
            )

            # 8. INTELLIGENT VISUALIZATION RECOMMENDATION
            _progress("Synthesizing zero-hallucination chart specifications for findings", 92)
            charts = FactVisualizer.visualize_insights(
                interpretation.insights, facts_lookup, df=df, profile=semantic_profile
            )
            chart_by_fact_id = {c.supporting_fact_id: c for c in charts if c.supporting_fact_id}

            # 9. MATERIALIZE EVIDENCE-GOVERNED SLIDE SPECIFICATION
            _progress("Materializing presentation deck specification", 96)
            deck_spec = cls._materialize_deck_spec(
                semantic_profile, interpretation, ranked_facts, facts_lookup, charts, chart_by_fact_id, effective_objective, context=context
            )

            _progress("Generic reporting workflow completed successfully", 100)
            res = WorkflowExecutionResult(
                report_id=rid,
                status="COMPLETED",
                quality_report=quality,
                semantic_profile=semantic_profile,
                candidate_fact_count=len(reliable_facts),
                ranked_fact_count=len(ranked_facts),
                interpretation=interpretation,
                audit_result=audit_result,
                visual_charts=charts,
                deck_spec=deck_spec,
                analysis_context=context.model_dump() if (context and hasattr(context, "model_dump")) else context
            )
            if use_cache:
                _GENERIC_WORKFLOW_CACHE[cache_key] = res
            return res

        except Exception as exc:
            logger.exception(f"Workflow {rid} encountered an unexpected fatal error: {exc}")
            return WorkflowExecutionResult(
                report_id=rid,
                status="ERROR",
                error_message=str(exc)
            )

    @classmethod
    def _materialize_deck_spec(
        cls,
        profile: SemanticDatasetProfile,
        interpretation: InterpretationResponse,
        ranked_facts: list[RankedFact],
        facts_lookup: dict[str, CandidateFact],
        charts: list[VisualChartSpec],
        chart_by_fact_id: dict[str, VisualChartSpec],
        objective: str,
        context: Any | None = None
    ) -> dict[str, Any]:
        """Translates generic insights, verified facts, and charts into a presentation deck specification."""
        slides = []

        has_intent = context and getattr(context, "has_user_intent", False)
        hero_subtitle = f"Targeted Analysis Brief: {context.user_objective}" if (has_intent and context.user_objective) else f"Empirical findings across {profile.row_count:,} records (Grain: {profile.inferred_grain})"

        # Slide 1: Hero Executive Summary
        slides.append({
            "order": 1,
            "category": "USER OBJECTIVE" if has_intent else "EXECUTIVE SUMMARY",
            "layout": "title_hero",
            "title": f"Executive Intelligence: {profile.dataset_name}",
            "subtitle": hero_subtitle,
            "narrative": interpretation.executive_synthesis,
            "visual_hook": "none",
            "finding_ids": [ins.supporting_fact_ids[0] for ins in interpretation.insights if ins.supporting_fact_ids]
        })

        # Sort insights: user-priority insights first, then discovery insights
        def _ins_priority(ins):
            for fid in ins.supporting_fact_ids:
                f = facts_lookup.get(fid)
                if f and getattr(f, "priority_type", "") == "USER_PRIORITY":
                    return 0
            return 1

        sorted_insights = sorted(interpretation.insights, key=_ins_priority)

        # Slides 2+: Individual Analytical Insight Slides with Linked Charts
        for idx, ins in enumerate(sorted_insights, start=2):
            primary_fid = ins.supporting_fact_ids[0] if ins.supporting_fact_ids else None
            chart = chart_by_fact_id.get(primary_fid)

            is_priority = False
            for fid in ins.supporting_fact_ids:
                fact = facts_lookup.get(fid)
                if fact and getattr(fact, "priority_type", "") == "USER_PRIORITY":
                    is_priority = True
                    break

            slide_metrics = []
            for fid in ins.supporting_fact_ids:
                fact = facts_lookup.get(fid)
                if fact and fact.value is not None:
                    diff_str = f"{fact.relative_difference:+.1f}%" if fact.relative_difference is not None else ""
                    slide_metrics.append({
                        "label": fact.metric.replace('_', ' ').title(),
                        "value": f"{fact.value:,.2f}",
                        "change": diff_str,
                        "evidence_id": fid,
                        "provenance": getattr(fact, "provenance", "DATA_INFERRED")
                    })

            slide_dict = {
                "order": idx,
                "category": "USER PRIORITY FINDING" if is_priority else "ADDITIONAL DISCOVERY",
                "layout": "chart_narrative" if chart else "kpi_summary",
                "title": ins.title[:78],
                "subtitle": ins.observation,
                "narrative": ins.interpretation,
                "bullet_points": ins.questions_to_investigate,
                "action_vector": ins.questions_to_investigate[0] if ins.questions_to_investigate else None,
                "visual_hook": chart.chart_type if chart else "none",
                "metrics": slide_metrics,
                "finding_ids": ins.supporting_fact_ids,
                "evidence_id": primary_fid,
                "is_user_priority": is_priority
            }
            if chart:
                slide_dict["chart"] = chart.model_dump()

            slides.append(slide_dict)

        return {
            "deck_title": f"Executive Intelligence: {profile.dataset_name}",
            "metadata": {
                "dataset_name": profile.dataset_name,
                "inferred_grain": profile.inferred_grain,
                "total_records": profile.row_count,
                "column_count": profile.column_count,
                "domain": getattr(profile, "domain", "general"),
                "deck_style": "evidence_governed"
            },
            "slides": slides
        }
