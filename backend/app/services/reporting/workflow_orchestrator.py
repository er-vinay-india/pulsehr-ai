"""Explicit Workflow Orchestrator implementing the full end-to-end reporting state machine."""

import logging
from typing import Any, Callable
from uuid import uuid4
import pandas as pd
from pydantic import BaseModel, Field

from ..data_engine.validator import DatasetValidator, DataQualityReport
from ..data_engine.profiler import DatasetProfiler, DatasetProfile
from ..data_engine.metric_engine import MetricEngine, CandidateFact
from ..evidence.evidence_store import EvidenceStore
from ..analyst.analyst_agent import AnalystAgent
from .report_planner import ReportPlanner, ReportPlan
from .writer_agent import WriterAgent, GeneratedReport, WrittenSection
from ..critic.critic_agent import CriticAgent, SectionAuditResult
from ..gateway.observability import trace_registry, ExecutionTrace, LineageRecord

logger = logging.getLogger(__name__)


class WorkflowExecutionResult(BaseModel):
    """Holistic execution artifact returned by the WorkflowOrchestrator."""
    report_id: str
    status: str  # "COMPLETED", "DATA_QUALITY_REJECTED", "ERROR"
    quality_report: DataQualityReport | None = None
    profile: DatasetProfile | None = None
    finding_count: int = 0
    plan: ReportPlan | None = None
    report: GeneratedReport | None = None
    critic_audit_summary: list[dict[str, Any]] = Field(default_factory=list)
    deck_spec: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None


class WorkflowOrchestrator:
    """Explicit state machine coordinating data validation, metrics, analyst discovery, writing, and critic verification."""

    @classmethod
    def execute(
        cls,
        df: pd.DataFrame,
        dataset_name: str = "Uploaded Dataset",
        objective: str = "Executive Leadership Briefing",
        on_progress: Callable[[str, int], None] | None = None,
        report_id: str | None = None
    ) -> WorkflowExecutionResult:
        rid = report_id or f"report-{uuid4().hex[:8]}"

        def _progress(msg: str, pct: int):
            if on_progress:
                on_progress(msg, pct)
            logger.info(f"[Workflow {rid}] {pct}%: {msg}")

        try:
            # 1. VALIDATE DATASET
            _progress("Validating dataset integrity and column schemas", 10)
            quality = DatasetValidator.validate(df, dataset_name=dataset_name)
            if not quality.is_valid:
                logger.warning(f"Workflow {rid} halted due to critical data quality failures: {quality.critical_errors}")
                return WorkflowExecutionResult(
                    report_id=rid,
                    status="DATA_QUALITY_REJECTED",
                    quality_report=quality,
                    error_message="; ".join(quality.critical_errors)
                )

            # 2. PROFILE DATASET
            _progress("Profiling data types, measures, and observation window", 20)
            profile = DatasetProfiler.profile(df, dataset_name=dataset_name)

            # 3. CALCULATE DETERMINISTIC METRICS
            _progress("Computing deterministic distributions, segment variances & trends", 35)
            candidate_facts = MetricEngine.discover_candidate_facts(df, max_candidates=16)

            # 4. DISCOVER & RANK FINDINGS (Stage A: Analyst Agent)
            _progress("Surfacing and prioritizing material findings via Analyst model", 50)
            evidence_store = AnalystAgent.analyze(candidate_facts, profile, report_id=rid)

            # 5. BUILD REPORT PLAN
            _progress("Synthesizing evidence-backed ReportPlan", 65)
            plan = ReportPlanner.plan(evidence_store, profile, objective=objective, report_id=rid)

            # 6. WRITE REPORT NARRATIVE (Stage B: Writer Agent)
            _progress("Generating executive narrative sections via Writer model", 78)
            draft_report = WriterAgent.write_report(plan, evidence_store, profile, report_id=rid)

            # 7. VALIDATE CLAIMS & EXECUTE REPAIR LOOP (Stage C: Critic Agent)
            _progress("Auditing claims and executing automated correction loop via Critic model", 88)
            verified_sections: list[WrittenSection] = []
            audit_summaries: list[dict[str, Any]] = []

            for section in draft_report.sections:
                repaired_section, audit_result = CriticAgent.audit_and_repair(
                    section,
                    evidence_store,
                    report_id=rid,
                    max_repair_attempts=2
                )
                verified_sections.append(repaired_section)
                audit_summaries.append(audit_result.model_dump())

            final_report = GeneratedReport(
                report_title=draft_report.report_title,
                objective=draft_report.objective,
                sections=verified_sections
            )

            # 8. MATERIALIZE EVIDENCE-AWARE SLIDE SPECIFICATION
            _progress("Materializing evidence-aware presentation deck specification", 95)
            deck_spec = cls._materialize_deck_spec(final_report, plan, evidence_store, profile)

            _progress("Workflow completed successfully", 100)
            return WorkflowExecutionResult(
                report_id=rid,
                status="COMPLETED",
                quality_report=quality,
                profile=profile,
                finding_count=len(evidence_store.get_all()),
                plan=plan,
                report=final_report,
                critic_audit_summary=audit_summaries,
                deck_spec=deck_spec
            )

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
        report: GeneratedReport,
        plan: ReportPlan,
        evidence_store: EvidenceStore,
        profile: DatasetProfile
    ) -> dict[str, Any]:
        """Translates the verified GeneratedReport and EvidenceStore into a fully compatible deck_spec."""
        slides = []
        evidence_ledger = evidence_store.export_ledger()
        findings_by_id = {f.finding_id: f for f in evidence_store.get_all()}

        # Slide 1: Hero Title Slide
        first_finding = evidence_store.get_all()[0] if evidence_store.get_all() else None
        slides.append({
            "order": 1,
            "category": "EXECUTIVE REVIEW",
            "layout": "title_hero",
            "title": report.report_title[:78],
            "subtitle": f"Evidence-Based Performance Architecture across {profile.row_count:,} records in {profile.dataset_name}",
            "narrative": first_finding.headline if first_finding else "Empirical analysis across operating divisions.",
            "visual_hook": "none",
            "finding_ids": [first_finding.finding_id] if first_finding else []
        })

        # Slides 2+: Materialize each section into an evidence-aware slide
        for idx, (sec_plan, sec_text) in enumerate(zip(plan.sections, report.sections), start=2):
            slide_metrics = []
            for fid in sec_text.finding_ids:
                f_obj = findings_by_id.get(fid)
                if f_obj and f_obj.segment_value is not None:
                    diff_str = f"{f_obj.difference_percentage_points:+.1f}%" if f_obj.difference_percentage_points is not None else ""
                    slide_metrics.append({
                        "label": f"{f_obj.segment or f_obj.metric}",
                        "value": f"{f_obj.segment_value:,.2f}",
                        "change": diff_str,
                        "evidence_id": fid
                    })

            layout = "chart_narrative" if sec_plan.visual_hook in ("line_chart", "bar_chart", "donut_chart") else "kpi_summary"

            slides.append({
                "order": idx,
                "category": sec_plan.category.upper(),
                "layout": layout,
                "title": sec_text.title[:78],
                "subtitle": sec_text.key_takeaway,
                "narrative": " ".join(sec_text.bullet_points),
                "bullet_points": sec_text.bullet_points,
                "action_vector": sec_text.action_vector,
                "visual_hook": sec_plan.visual_hook,
                "metrics": slide_metrics,
                "finding_ids": sec_text.finding_ids,
                "evidence_id": sec_text.finding_ids[0] if sec_text.finding_ids else None
            })

        return {
            "deck_title": report.report_title,
            "metadata": {
                "generated_at": profile.observation_window,
                "dataset_name": profile.dataset_name,
                "domain": profile.business_domain,
                "total_records": profile.row_count,
                "deck_style": "evidence_governed"
            },
            "slides": slides,
            "evidence_ledger": evidence_ledger
        }
