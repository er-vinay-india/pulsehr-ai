"""8 Distinct Real-World Presentation Scenarios for Pipeline Validation & Hardening.

Covers:
- Scenario A: Workforce / HR (Attendance, Department Compliance, Leave, Risks)
- Scenario B: Sales (Regional Sales, Categories, Growth, Margin, Target Attainment)
- Scenario C: Finance (Budget vs Actual, Variance, Cost Categories, Margins)
- Scenario D: Software / Tech Architecture (Latency, Dependencies, Throughput, Incidents)
- Scenario E: Educational (Transformer Attention vs RNNs, Low Cognitive Load)
- Scenario F: Research (Empirical Study, Methodology to Appendix, Limitations)
- Scenario G: Sparse Data (Tiny sample, Cautious language, No hallucinations, Small deck)
- Scenario H: Dense Multi-Sheet Data (High volume, Triage, Appendix routing, Context budget)
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from ..director.director_models import (
    PresentationPlanningContext,
    SlideCountConstraint,
    SlideCountMode,
)
from ..builders import build_default_evidence_ledger


class ScenarioDefinition(BaseModel):
    """Specification of an empirical validation scenario."""
    scenario_id: str
    scenario_name: str
    domain: str
    objective: str
    audience: str
    instructions: str
    dataset_label: str
    total_records: int
    completeness_pct: float
    baseline_benchmark: str
    dispersion_metric: str
    reporting_period: str
    is_partial_year: bool
    theme_id: str = "bold_signal"
    target_slides: int | None = None
    slide_count_mode: SlideCountMode = SlideCountMode.ADAPTIVE
    dataset_context: dict[str, Any]
    workspace_evidence: dict[str, Any]
    expected_characteristics: dict[str, Any] = Field(default_factory=dict)
    unacceptable_failures: list[str] = Field(default_factory=list)


def create_scenario_a_workforce() -> ScenarioDefinition:
    """SCENARIO A — WORKFORCE / HR: Office attendance, department compliance, leave patterns, workforce risks."""
    total_records = 3450
    evidence_ledger = [
        {"evidence_id": "EVID-HR-01", "metric_name": "Average Attendance Rate", "metric_value": "84.2%", "numeric_value": 84.2, "claim_text": "Company-wide in-office attendance averaged 84.2% across evaluated quarters.", "source_label": "HRIS Attendance Logs", "provenance": "HR_Q3_Records.csv"},
        {"evidence_id": "EVID-HR-02", "metric_name": "Peak Department Compliance", "metric_value": "94.6%", "numeric_value": 94.6, "claim_text": "Engineering led in-office policy compliance at 94.6%.", "source_label": "Department Roster", "provenance": "HR_Q3_Records.csv"},
        {"evidence_id": "EVID-HR-03", "metric_name": "Unscheduled Leave Surge", "metric_value": "+18.4%", "numeric_value": 18.4, "claim_text": "Customer Support exhibited an 18.4% surge in unplanned leave during peak release cycles.", "source_label": "Leave Tracking Table", "provenance": "HR_Q3_Records.csv"},
        {"evidence_id": "EVID-HR-04", "metric_name": "Burnout Risk Index", "metric_value": "2.3x Spread", "numeric_value": 2.3, "claim_text": "Cross-department overtime dispersion showed a 2.3x disparity between teams.", "source_label": "Workforce Analytics", "provenance": "HR_Q3_Records.csv"}
    ]
    records = [
        {"department": "Engineering", "attendance_pct": 94.6, "overtime_hours": 12.4, "headcount": 1200},
        {"department": "Product", "attendance_pct": 88.1, "overtime_hours": 9.1, "headcount": 450},
        {"department": "Customer Support", "attendance_pct": 74.3, "overtime_hours": 21.8, "headcount": 800},
        {"department": "Sales", "attendance_pct": 85.0, "overtime_hours": 15.2, "headcount": 600},
        {"department": "Operations", "attendance_pct": 82.5, "overtime_hours": 11.5, "headcount": 400},
    ]
    charts = {
        "bar_chart": {
            "title": "Department Attendance & Compliance",
            "categories": ["Engineering", "Product", "Sales", "Operations", "Customer Support"],
            "series": [{"name": "Attendance %", "data": [94.6, 88.1, 85.0, 82.5, 74.3]}]
        },
        "line_chart": {
            "title": "Quarterly Attendance Trend",
            "categories": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep"],
            "series": [{"name": "Attendance %", "data": [81.0, 82.5, 83.0, 84.1, 85.0, 84.8, 83.5, 84.0, 84.2]}]
        }
    }
    return ScenarioDefinition(
        scenario_id="scenario_a_workforce",
        scenario_name="Workforce Operational Attendance & Risk Review",
        domain="Workforce Operations",
        objective="Executive Workforce Attendance, Compliance & Leave Risk Assessment",
        audience="CHRO & Executive Operating Committee",
        instructions="Provide executive management narrative, department rankings, compliance charting, and workforce action recommendations.",
        dataset_label="Workforce_Attendance_Q3.csv",
        total_records=total_records,
        completeness_pct=99.4,
        baseline_benchmark="84.2% Attendance",
        dispersion_metric="2.3x Spread",
        reporting_period="Q1 - Q3 2026",
        is_partial_year=False,
        theme_id="bold_signal",
        target_slides=6,
        slide_count_mode=SlideCountMode.FIXED,
        dataset_context={
            "domain": "Workforce Operations",
            "target_sheet": {"id": "sheet_hr_01", "name": "Attendance", "original_name": "Workforce_Attendance_Q3.csv"},
            "records": records,
            "columns": ["department", "attendance_pct", "overtime_hours", "headcount"],
            "ground_truth": {"mean_attendance": 84.2, "peak_compliance_dept": "Engineering"},
            "snapshot_hash": "sha256:hr9483a17e0b",
            "visuals": charts
        },
        workspace_evidence={
            "evidence_ledger": evidence_ledger,
            "candidate_findings": evidence_ledger,
            "included_sheets": [{"id": "sheet_hr_01", "name": "Attendance", "original_name": "Workforce_Attendance_Q3.csv", "row_count": total_records}],
            "total_records": total_records,
            "snapshot_hash": "sha256:hr9483a17e0b"
        },
        expected_characteristics={
            "min_slides": 5,
            "max_slides": 7,
            "required_visual_families": ["bar_chart", "summary_card", "ranking_table"],
            "must_preserve_instructions": ["executive tone", "rankings", "compliance"]
        },
        unacceptable_failures=["THEME_REGRESSION", "MISSING_EVIDENCE", "UNSUPPORTED_CLAIM"]
    )


def create_scenario_b_sales() -> ScenarioDefinition:
    """SCENARIO B — SALES: Regional sales, product categories, growth, margin, target attainment."""
    total_records = 8240
    evidence_ledger = [
        {"evidence_id": "EVID-SALES-01", "metric_name": "Total Gross Revenue", "metric_value": "$48.61M", "numeric_value": 48.61, "claim_text": "Total gross sales across all territories reached $48.61M.", "source_label": "CRM Deal Flow", "provenance": "Global_Sales_2026.xlsx"},
        {"evidence_id": "EVID-SALES-02", "metric_name": "Top Territory Volume", "metric_value": "$18.4M", "numeric_value": 18.4, "claim_text": "North America contributed $18.4M representing 37.8% of global volume.", "source_label": "Territory Reports", "provenance": "Global_Sales_2026.xlsx"},
        {"evidence_id": "EVID-SALES-03", "metric_name": "Product Margin Spread", "metric_value": "3.1x Spread", "numeric_value": 3.1, "claim_text": "Software subscriptions achieved 72% gross margin vs 23% in hardware services.", "source_label": "Product Margin Ledger", "provenance": "Global_Sales_2026.xlsx"},
        {"evidence_id": "EVID-SALES-04", "metric_name": "Target Attainment", "metric_value": "104.3%", "numeric_value": 104.3, "claim_text": "Global sales achieved 104.3% of the Q3 operational target quota.", "source_label": "Quota Master", "provenance": "Global_Sales_2026.xlsx"}
    ]
    records = [
        {"region": "North America", "revenue_m": 18.4, "margin_pct": 64.0, "quota_pct": 106.2},
        {"region": "EMEA", "revenue_m": 14.2, "margin_pct": 58.5, "quota_pct": 102.1},
        {"region": "APAC", "revenue_m": 11.5, "margin_pct": 49.2, "quota_pct": 105.0},
        {"region": "LATAM", "revenue_m": 4.51, "margin_pct": 42.0, "quota_pct": 98.4},
    ]
    charts = {
        "bar_chart": {
            "title": "Regional Revenue Contribution",
            "categories": ["North America", "EMEA", "APAC", "LATAM"],
            "series": [{"name": "Revenue ($M)", "data": [18.4, 14.2, 11.5, 4.51]}]
        },
        "line_chart": {
            "title": "Monthly Revenue Trajectory",
            "categories": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep"],
            "series": [{"name": "Monthly ($M)", "data": [4.8, 5.1, 5.4, 5.2, 5.6, 5.9, 5.3, 5.5, 5.81]}]
        }
    }
    return ScenarioDefinition(
        scenario_id="scenario_b_sales",
        scenario_name="Commercial Sales Performance & Regional Margin Review",
        domain="Commercial Sales",
        objective="Analyze Q1-Q3 Regional Revenue, Product Margins, and Quota Attainment",
        audience="Chief Revenue Officer & Regional Directors",
        instructions="Exactly 6 slides. Highlight regional variance, ranked commercial performance, and target attainment.",
        dataset_label="Global_Sales_2026.xlsx",
        total_records=total_records,
        completeness_pct=100.0,
        baseline_benchmark="$48.61M Revenue",
        dispersion_metric="3.1x Spread",
        reporting_period="Q1 - Q3 2026",
        is_partial_year=False,
        theme_id="bold_signal",
        target_slides=6,
        slide_count_mode=SlideCountMode.FIXED,
        dataset_context={
            "domain": "Commercial Sales",
            "target_sheet": {"id": "sheet_sales_01", "name": "Global_Sales", "original_name": "Global_Sales_2026.xlsx"},
            "records": records,
            "columns": ["region", "revenue_m", "margin_pct", "quota_pct"],
            "ground_truth": {"total_revenue": 48.61, "mean_weekly_sales": 1.28},
            "snapshot_hash": "sha256:sl82710bcf32",
            "visuals": charts
        },
        workspace_evidence={
            "evidence_ledger": evidence_ledger,
            "candidate_findings": evidence_ledger,
            "included_sheets": [{"id": "sheet_sales_01", "name": "Global_Sales", "original_name": "Global_Sales_2026.xlsx", "row_count": total_records}],
            "total_records": total_records,
            "snapshot_hash": "sha256:sl82710bcf32"
        },
        expected_characteristics={
            "exact_slide_count": 6,
            "required_visual_families": ["bar_chart", "kpi_card", "line_chart"],
            "must_preserve_instructions": ["Exactly 6 slides", "regional variance"]
        },
        unacceptable_failures=["THEME_REGRESSION", "OVERLOADED_SLIDE", "MISSED_USER_QUESTION"]
    )


def create_scenario_c_finance() -> ScenarioDefinition:
    """SCENARIO C — FINANCE: Budget vs actual, variance, cost categories, margin movement."""
    total_records = 5120
    evidence_ledger = [
        {"evidence_id": "EVID-FIN-01", "metric_name": "Approved Operating Budget", "metric_value": "$24.50M", "numeric_value": 24.50, "claim_text": "Operating budget allocation totaled $24.50M for the fiscal year.", "source_label": "Budget Model", "provenance": "FY26_Budget_Actuals.xlsx"},
        {"evidence_id": "EVID-FIN-02", "metric_name": "Actual Operating Spend", "metric_value": "$23.85M", "numeric_value": 23.85, "claim_text": "Actual expenditure came in at $23.85M, reflecting a favorable $0.65M variance.", "source_label": "General Ledger", "provenance": "FY26_Budget_Actuals.xlsx"},
        {"evidence_id": "EVID-FIN-03", "metric_name": "Net Favorable Variance", "metric_value": "+2.65%", "numeric_value": 2.65, "claim_text": "Net expenditures were 2.65% under budget, driven by deferred cloud infrastructure expansion.", "source_label": "Variance Analysis", "provenance": "FY26_Budget_Actuals.xlsx"},
        {"evidence_id": "EVID-FIN-04", "metric_name": "EBITDA Margin Movement", "metric_value": "+140 bps", "numeric_value": 1.40, "claim_text": "EBITDA margin expanded by 140 bps year-over-year to 21.8%.", "source_label": "P&L Summary", "provenance": "FY26_Budget_Actuals.xlsx"}
    ]
    records = [
        {"category": "Personnel & Payroll", "budget_m": 12.0, "actual_m": 11.8, "variance_m": -0.2},
        {"category": "Cloud Infrastructure", "budget_m": 5.5, "actual_m": 5.1, "variance_m": -0.4},
        {"category": "Marketing & Customer Acquisition", "budget_m": 4.0, "actual_m": 4.2, "variance_m": 0.2},
        {"category": "Facilities & G&A", "budget_m": 3.0, "actual_m": 2.75, "variance_m": -0.25},
    ]
    charts = {
        "bar_chart": {
            "title": "Cost Category Budget vs Actual",
            "categories": ["Personnel", "Cloud Infra", "Marketing", "Facilities"],
            "series": [
                {"name": "Budget ($M)", "data": [12.0, 5.5, 4.0, 3.0]},
                {"name": "Actual ($M)", "data": [11.8, 5.1, 4.2, 2.75]}
            ]
        }
    }
    return ScenarioDefinition(
        scenario_id="scenario_c_finance",
        scenario_name="Fiscal Variance & EBITDA Margin Review",
        domain="Corporate Finance",
        objective="Fiscal Budget vs Actual Spend and Margin Movement Review",
        audience="Chief Financial Officer & Board Audit Committee",
        instructions="Focus only on cost category variance and margin movement. Maintain exact numerical integrity.",
        dataset_label="FY26_Budget_Actuals.xlsx",
        total_records=total_records,
        completeness_pct=100.0,
        baseline_benchmark="$23.85M Actual Spend",
        dispersion_metric="+2.65% Variance",
        reporting_period="FY2026",
        is_partial_year=False,
        theme_id="bold_signal",
        target_slides=5,
        slide_count_mode=SlideCountMode.FIXED,
        dataset_context={
            "domain": "Corporate Finance",
            "target_sheet": {"id": "sheet_fin_01", "name": "FY26_Variance", "original_name": "FY26_Budget_Actuals.xlsx"},
            "records": records,
            "columns": ["category", "budget_m", "actual_m", "variance_m"],
            "ground_truth": {"budget_total": 24.50, "actual_total": 23.85, "favorable_variance": 0.65},
            "snapshot_hash": "sha256:fn93810acd42",
            "visuals": charts
        },
        workspace_evidence={
            "evidence_ledger": evidence_ledger,
            "candidate_findings": evidence_ledger,
            "included_sheets": [{"id": "sheet_fin_01", "name": "FY26_Variance", "original_name": "FY26_Budget_Actuals.xlsx", "row_count": total_records}],
            "total_records": total_records,
            "snapshot_hash": "sha256:fn93810acd42"
        },
        expected_characteristics={
            "exact_slide_count": 5,
            "required_visual_families": ["bar_chart", "variance_table", "kpi_card"],
            "numerical_integrity_tolerance": 0.001
        },
        unacceptable_failures=["THEME_REGRESSION", "UNSUPPORTED_CLAIM", "WRONG_VISUAL"]
    )


def create_scenario_d_software_tech() -> ScenarioDefinition:
    """SCENARIO D — SOFTWARE / TECH ARCHITECTURE: Components, latency, service dependencies, throughput, incidents."""
    total_records = 24000
    evidence_ledger = [
        {"evidence_id": "EVID-TECH-01", "metric_name": "P99 API Latency", "metric_value": "42.8 ms", "numeric_value": 42.8, "claim_text": "P99 gateway latency across all microservices averaged 42.8 ms under peak load.", "source_label": "Prometheus Metrics", "provenance": "Service_Telemetry_Q3.log"},
        {"evidence_id": "EVID-TECH-02", "metric_name": "Peak Ingestion Throughput", "metric_value": "128,400 rps", "numeric_value": 128400, "claim_text": "Kafka streaming clusters sustained 128,400 requests/sec with zero packet loss.", "source_label": "Kafka Cluster State", "provenance": "Service_Telemetry_Q3.log"},
        {"evidence_id": "EVID-TECH-03", "metric_name": "Service Availability", "metric_value": "99.991%", "numeric_value": 99.991, "claim_text": "Platform availability reached 99.991% across 14 active production microservices.", "source_label": "SLA Monitor", "provenance": "Service_Telemetry_Q3.log"},
        {"evidence_id": "EVID-TECH-04", "metric_name": "Critical Incidents", "metric_value": "1 Incident", "numeric_value": 1, "claim_text": "Only one Sev-1 incident recorded during Q3 (resolved within 11 minutes).", "source_label": "PagerDuty Log", "provenance": "Service_Telemetry_Q3.log"}
    ]
    records = [
        {"service": "API Gateway", "p99_ms": 14.2, "rps": 128400, "status": "Healthy"},
        {"service": "Auth Service", "p99_ms": 22.1, "rps": 45000, "status": "Healthy"},
        {"service": "Embedding Vector DB", "p99_ms": 38.5, "rps": 18200, "status": "Healthy"},
        {"service": "Analytics Engine", "p99_ms": 78.4, "rps": 12000, "status": "Elevated Latency"},
    ]
    charts = {
        "bar_chart": {
            "title": "Service P99 Latency Comparison",
            "categories": ["API Gateway", "Auth", "Vector DB", "Analytics Engine"],
            "series": [{"name": "P99 (ms)", "data": [14.2, 22.1, 38.5, 78.4]}]
        }
    }
    return ScenarioDefinition(
        scenario_id="scenario_d_tech_architecture",
        scenario_name="Microservices Architecture Latency & SLA Review",
        domain="Cloud Engineering & Distributed Systems",
        objective="Quarterly Microservices Latency, Throughput, and Architectural Trade-off Review",
        audience="Chief Technology Officer & Principal Systems Architects",
        instructions="Maximum 7 slides. Include component latency trade-offs, architecture dependencies, and SLA metrics.",
        dataset_label="Service_Telemetry_Q3.log",
        total_records=total_records,
        completeness_pct=100.0,
        baseline_benchmark="42.8 ms P99 Latency",
        dispersion_metric="5.5x Latency Spread",
        reporting_period="Q3 2026",
        is_partial_year=False,
        theme_id="bold_signal",
        target_slides=6,
        slide_count_mode=SlideCountMode.MAXIMUM,
        dataset_context={
            "domain": "Cloud Engineering",
            "target_sheet": {"id": "sheet_tech_01", "name": "Microservices", "original_name": "Service_Telemetry_Q3.log"},
            "records": records,
            "columns": ["service", "p99_ms", "rps", "status"],
            "ground_truth": {"p99_mean": 42.8, "availability": 99.991},
            "snapshot_hash": "sha256:tc72849da10f",
            "visuals": charts
        },
        workspace_evidence={
            "evidence_ledger": evidence_ledger,
            "candidate_findings": evidence_ledger,
            "included_sheets": [{"id": "sheet_tech_01", "name": "Microservices", "original_name": "Service_Telemetry_Q3.log", "row_count": total_records}],
            "total_records": total_records,
            "snapshot_hash": "sha256:tc72849da10f"
        },
        expected_characteristics={
            "max_slides": 7,
            "required_visual_families": ["diagram", "bar_chart", "kpi_card"]
        },
        unacceptable_failures=["THEME_REGRESSION", "OVERLOADED_SLIDE", "MISSED_USER_QUESTION"]
    )


def create_scenario_e_educational() -> ScenarioDefinition:
    """SCENARIO E — EDUCATIONAL: Machine learning topic (Transformer Attention vs RNNs), progressive explanation, low cognitive load."""
    total_records = 1200
    evidence_ledger = [
        {"evidence_id": "EVID-EDU-01", "metric_name": "Parallel Training Speedup", "metric_value": "8.4x Faster", "numeric_value": 8.4, "claim_text": "Transformer self-attention enables 8.4x faster training through batch parallel token processing.", "source_label": "Benchmark Study", "provenance": "Attention_vs_RNN_Bench.json"},
        {"evidence_id": "EVID-EDU-02", "metric_name": "Long-Range Memory Retention", "metric_value": "96.2%", "numeric_value": 96.2, "claim_text": "Self-attention retains 96.2% contextual dependency over 8,000 tokens vs 22% in standard LSTM.", "source_label": "Context Length Study", "provenance": "Attention_vs_RNN_Bench.json"},
        {"evidence_id": "EVID-EDU-03", "metric_name": "Computational Complexity", "metric_value": "O(N²) Complexity", "numeric_value": 2.0, "claim_text": "Standard dot-product attention scales quadratically with sequence length N.", "source_label": "Algorithmic Analysis", "provenance": "Attention_vs_RNN_Bench.json"}
    ]
    records = [
        {"architecture": "Recurrent (LSTM)", "parallelizable": "No (Sequential)", "long_context_retention_pct": 22.4, "speedup": 1.0},
        {"architecture": "Convolutional (1D)", "parallelizable": "Partial", "long_context_retention_pct": 54.1, "speedup": 3.2},
        {"architecture": "Self-Attention (Transformer)", "parallelizable": "Fully Parallel", "long_context_retention_pct": 96.2, "speedup": 8.4},
    ]
    charts = {
        "bar_chart": {
            "title": "Context Retention across 8K Tokens",
            "categories": ["LSTM", "1D ConvNet", "Transformer Attention"],
            "series": [{"name": "Retention %", "data": [22.4, 54.1, 96.2]}]
        }
    }
    return ScenarioDefinition(
        scenario_id="scenario_e_educational",
        scenario_name="Introduction to Transformer Attention & Scalable Sequence Models",
        domain="Artificial Intelligence Education",
        objective="Explain Modern Transformer Attention Mechanisms with High Clarity and Low Cognitive Load",
        audience="Graduate Engineering Students & Junior AI Practitioners",
        instructions="Make it beginner-friendly with low cognitive load. Use progressive explanation, conceptual analogies, and intuitive diagrams.",
        dataset_label="Attention_vs_RNN_Bench.json",
        total_records=total_records,
        completeness_pct=100.0,
        baseline_benchmark="8.4x Parallel Speedup",
        dispersion_metric="4.3x Retention Gain",
        reporting_period="Academic Year 2026",
        is_partial_year=False,
        theme_id="bold_signal",
        target_slides=5,
        slide_count_mode=SlideCountMode.FIXED,
        dataset_context={
            "domain": "Artificial Intelligence Education",
            "target_sheet": {"id": "sheet_edu_01", "name": "Architectures", "original_name": "Attention_vs_RNN_Bench.json"},
            "records": records,
            "columns": ["architecture", "parallelizable", "long_context_retention_pct", "speedup"],
            "ground_truth": {"speedup": 8.4, "retention_pct": 96.2},
            "snapshot_hash": "sha256:ed84920bda33",
            "visuals": charts
        },
        workspace_evidence={
            "evidence_ledger": evidence_ledger,
            "candidate_findings": evidence_ledger,
            "included_sheets": [{"id": "sheet_edu_01", "name": "Architectures", "original_name": "Attention_vs_RNN_Bench.json", "row_count": total_records}],
            "total_records": total_records,
            "snapshot_hash": "sha256:ed84920bda33"
        },
        expected_characteristics={
            "exact_slide_count": 5,
            "required_visual_families": ["diagram", "comparison_matrix", "bar_chart"]
        },
        unacceptable_failures=["OVERLOADED_SLIDE", "THEME_REGRESSION", "WRONG_VISUAL"]
    )


def create_scenario_f_research() -> ScenarioDefinition:
    """SCENARIO F — RESEARCH: Findings, methodology placement, appendix usage, limitations, conclusions."""
    total_records = 4800
    evidence_ledger = [
        {"evidence_id": "EVID-RES-01", "metric_name": "Sample Cohort Size", "metric_value": "N = 4,800", "numeric_value": 4800, "claim_text": "Double-blind evaluation conducted across 4,800 randomized enterprise participants.", "source_label": "Methodology Protocol", "provenance": "Study_Protocol_2026.pdf"},
        {"evidence_id": "EVID-RES-02", "metric_name": "Observed Treatment Effect", "metric_value": "+14.2% (p < 0.001)", "numeric_value": 14.2, "claim_text": "Treatment cohort demonstrated a statistically significant 14.2% performance gain (p < 0.001).", "source_label": "Statistical Regression", "provenance": "Study_Protocol_2026.pdf"},
        {"evidence_id": "EVID-RES-03", "metric_name": "Identified Study Limitation", "metric_value": "Single-Region Bias", "numeric_value": 1.0, "claim_text": "Evaluation restricted to North American geographic zones, limiting immediate global generalization.", "source_label": "Study Limitations Section", "provenance": "Study_Protocol_2026.pdf"},
        {"evidence_id": "EVID-RES-04", "metric_name": "Inter-Rater Reliability", "metric_value": "κ = 0.89", "numeric_value": 0.89, "claim_text": "Fleiss' Kappa of 0.89 confirms strong annotator agreement across findings.", "source_label": "Annotation Metrics", "provenance": "Study_Protocol_2026.pdf"}
    ]
    records = [
        {"cohort": "Control Group", "participants": 2400, "mean_score": 71.4, "std_dev": 8.2},
        {"cohort": "Treatment Group", "participants": 2400, "mean_score": 85.6, "std_dev": 6.8},
    ]
    charts = {
        "bar_chart": {
            "title": "Treatment Effect Comparison",
            "categories": ["Control Group", "Treatment Group"],
            "series": [{"name": "Mean Score", "data": [71.4, 85.6]}]
        }
    }
    return ScenarioDefinition(
        scenario_id="scenario_f_research",
        scenario_name="Empirical Research Study: Intervention Efficacy & Methodological Protocol",
        domain="Academic & Clinical Research",
        objective="Present Empirical Clinical Findings, Evidence Citations, Limitations, and Route Methodology to Appendix",
        audience="Scientific Advisory Board & Institutional Review Panel",
        instructions="Do not include methodology in main deck; route detailed evidence and methodology to appendix. Highlight explicit limitations and evidence citations.",
        dataset_label="Study_Protocol_2026.pdf",
        total_records=total_records,
        completeness_pct=100.0,
        baseline_benchmark="+14.2% Effect Size",
        dispersion_metric="p < 0.001",
        reporting_period="Q2 - Q3 2026",
        is_partial_year=False,
        theme_id="bold_signal",
        target_slides=6,
        slide_count_mode=SlideCountMode.FIXED,
        dataset_context={
            "domain": "Academic Research",
            "target_sheet": {"id": "sheet_res_01", "name": "TrialData", "original_name": "Study_Protocol_2026.pdf"},
            "records": records,
            "columns": ["cohort", "participants", "mean_score", "std_dev"],
            "ground_truth": {"effect_size": 14.2, "p_value": 0.001},
            "snapshot_hash": "sha256:rs73820a11ff",
            "visuals": charts
        },
        workspace_evidence={
            "evidence_ledger": evidence_ledger,
            "candidate_findings": evidence_ledger,
            "included_sheets": [{"id": "sheet_res_01", "name": "TrialData", "original_name": "Study_Protocol_2026.pdf", "row_count": total_records}],
            "total_records": total_records,
            "snapshot_hash": "sha256:rs73820a11ff"
        },
        expected_characteristics={
            "has_limitation_slide": True,
            "has_appendix": True,
            "required_visual_families": ["bar_chart", "callout_box", "kpi_card"]
        },
        unacceptable_failures=["POOR_APPENDIX_ROUTING", "UNSUPPORTED_CLAIM", "THEME_REGRESSION"]
    )


def create_scenario_g_sparse_data() -> ScenarioDefinition:
    """SCENARIO G — SPARSE DATA: Few rows / weak evidence, no fabricated insights, cautious language, limited slide count."""
    total_records = 6
    evidence_ledger = [
        {"evidence_id": "EVID-SPARSE-01", "metric_name": "Pilot Sample Records", "metric_value": "N = 6", "numeric_value": 6, "claim_text": "Pilot exploratory study encompasses exactly 6 enterprise trial customer accounts.", "source_label": "Pilot Onboarding Sheet", "provenance": "Alpha_Trial_Accounts.csv"},
        {"evidence_id": "EVID-SPARSE-02", "metric_name": "Reported Net Promoter Score", "metric_value": "+33 NPS", "numeric_value": 33, "claim_text": "Observed pilot NPS is +33 across 6 respondents; statistical significance is non-conclusive.", "source_label": "Customer Survey", "provenance": "Alpha_Trial_Accounts.csv"}
    ]
    records = [
        {"account_id": "CUST-001", "nps_rating": 8, "onboarded_days": 14},
        {"account_id": "CUST-002", "nps_rating": 9, "onboarded_days": 21},
        {"account_id": "CUST-003", "nps_rating": 7, "onboarded_days": 10},
        {"account_id": "CUST-004", "nps_rating": 10, "onboarded_days": 30},
        {"account_id": "CUST-005", "nps_rating": 6, "onboarded_days": 7},
        {"account_id": "CUST-006", "nps_rating": 8, "onboarded_days": 18},
    ]
    return ScenarioDefinition(
        scenario_id="scenario_g_sparse_data",
        scenario_name="Alpha Pilot Feasibility: Sparse Sample Evaluation",
        domain="Product Exploratory Research",
        objective="Assess Early Pilot Feedback from Limited Alpha Customer Cohort",
        audience="Product Steering Group",
        instructions="Input contains very sparse data (only 6 rows). Do NOT fabricate insights or project nationwide statistical significance. Produce a concise deck with explicit sample size limitations and cautious language.",
        dataset_label="Alpha_Trial_Accounts.csv",
        total_records=total_records,
        completeness_pct=100.0,
        baseline_benchmark="6 Pilot Accounts",
        dispersion_metric="Small Sample Size Warning",
        reporting_period="September 2026",
        is_partial_year=True,
        theme_id="bold_signal",
        target_slides=4,
        slide_count_mode=SlideCountMode.MAXIMUM,
        dataset_context={
            "domain": "Product Exploratory",
            "target_sheet": {"id": "sheet_sparse_01", "name": "Alpha_Pilot", "original_name": "Alpha_Trial_Accounts.csv"},
            "records": records,
            "columns": ["account_id", "nps_rating", "onboarded_days"],
            "ground_truth": {"mean_nps": 8.0, "total_records": 6},
            "snapshot_hash": "sha256:sp009182aa11",
            "visuals": {}
        },
        workspace_evidence={
            "evidence_ledger": evidence_ledger,
            "candidate_findings": evidence_ledger,
            "included_sheets": [{"id": "sheet_sparse_01", "name": "Alpha_Pilot", "original_name": "Alpha_Trial_Accounts.csv", "row_count": total_records}],
            "total_records": total_records,
            "snapshot_hash": "sha256:sp009182aa11"
        },
        expected_characteristics={
            "max_slides": 4,
            "must_preserve_instructions": ["explicit limitations", "cautious language"]
        },
        unacceptable_failures=["UNSUPPORTED_CLAIM", "OVERLOADED_SLIDE", "THEME_REGRESSION"]
    )


def create_scenario_h_dense_multi_sheet() -> ScenarioDefinition:
    """SCENARIO H — DENSE MULTI-SHEET DATA: Multiple sheets, 18,500 records, prioritization, triage, appendix routing."""
    total_records = 18500
    evidence_ledger = [
        {"evidence_id": "EVID-DENSE-01", "metric_name": "Global Active SKUs", "metric_value": "18,500 SKUs", "numeric_value": 18500, "claim_text": "Warehouse network tracks 18,500 distinct inventory units across 5 distribution hubs.", "source_label": "Warehouse ERP", "provenance": "Global_Supply_Chain_Multi.xlsx"},
        {"evidence_id": "EVID-DENSE-02", "metric_name": "On-Time Dispatch Rate", "metric_value": "97.4%", "numeric_value": 97.4, "claim_text": "Primary distribution nodes achieved a 97.4% on-time shipping fulfillment rate.", "source_label": "Logistics Dispatch", "provenance": "Global_Supply_Chain_Multi.xlsx"},
        {"evidence_id": "EVID-DENSE-03", "metric_name": "Freight Bottleneck Disparity", "metric_value": "4.2x Cost Ratio", "numeric_value": 4.2, "claim_text": "Air freight express expediting ran at 4.2x standard multimodal ocean transport cost.", "source_label": "Freight Ledger", "provenance": "Global_Supply_Chain_Multi.xlsx"},
        {"evidence_id": "EVID-DENSE-04", "metric_name": "Inventory Carrying Cost", "metric_value": "$6.20M", "numeric_value": 6.20, "claim_text": "Annualized holding costs across regional facilities stabilized at $6.20M.", "source_label": "Finance Audit", "provenance": "Global_Supply_Chain_Multi.xlsx"}
    ]
    records = [
        {"facility": "Hub Chicago", "active_skus": 5400, "on_time_pct": 98.1, "freight_cost_m": 1.4},
        {"facility": "Hub Dallas", "active_skus": 4200, "on_time_pct": 97.8, "freight_cost_m": 1.1},
        {"facility": "Hub Rotterdam", "active_skus": 3900, "on_time_pct": 96.5, "freight_cost_m": 1.6},
        {"facility": "Hub Singapore", "active_skus": 3100, "on_time_pct": 97.9, "freight_cost_m": 1.3},
        {"facility": "Hub Sao Paulo", "active_skus": 1900, "on_time_pct": 94.2, "freight_cost_m": 0.8},
    ]
    charts = {
        "bar_chart": {
            "title": "Facility Active SKUs & Fulfillment",
            "categories": ["Chicago", "Dallas", "Rotterdam", "Singapore", "Sao Paulo"],
            "series": [{"name": "Active SKUs", "data": [5400, 4200, 3900, 3100, 1900]}]
        }
    }
    return ScenarioDefinition(
        scenario_id="scenario_h_dense_multi_sheet",
        scenario_name="Global Enterprise Supply Chain & Inventory Triage",
        domain="Supply Chain & Logistics",
        objective="Prioritize High-Impact Supply Chain Bottlenecks and Route Multi-Sheet Granular Data to Appendix",
        audience="Chief Operating Officer & Supply Chain Leadership",
        instructions="Dense multi-sheet dataset. Perform rigorous information triage: focus main deck on top 3 supply chain bottlenecks; route detailed sheet rosters to appendix. Maximum 7 main slides.",
        dataset_label="Global_Supply_Chain_Multi.xlsx",
        total_records=total_records,
        completeness_pct=99.8,
        baseline_benchmark="97.4% Fulfillment",
        dispersion_metric="4.2x Cost Ratio",
        reporting_period="Q1 - Q3 2026",
        is_partial_year=False,
        theme_id="bold_signal",
        target_slides=7,
        slide_count_mode=SlideCountMode.MAXIMUM,
        dataset_context={
            "domain": "Supply Chain & Logistics",
            "target_sheet": {"id": "sheet_supply_01", "name": "Warehouse_Summary", "original_name": "Global_Supply_Chain_Multi.xlsx"},
            "records": records,
            "columns": ["facility", "active_skus", "on_time_pct", "freight_cost_m"],
            "ground_truth": {"total_skus": 18500, "on_time_pct": 97.4},
            "snapshot_hash": "sha256:sc918230bb84",
            "visuals": charts
        },
        workspace_evidence={
            "evidence_ledger": evidence_ledger,
            "candidate_findings": evidence_ledger,
            "included_sheets": [
                {"id": "sheet_supply_01", "name": "Warehouse_Summary", "original_name": "Global_Supply_Chain_Multi.xlsx", "row_count": 5400},
                {"id": "sheet_supply_02", "name": "Freight_Carriers", "original_name": "Global_Supply_Chain_Multi.xlsx", "row_count": 6800},
                {"id": "sheet_supply_03", "name": "Customs_Tariffs", "original_name": "Global_Supply_Chain_Multi.xlsx", "row_count": 6300}
            ],
            "total_records": total_records,
            "snapshot_hash": "sha256:sc918230bb84"
        },
        expected_characteristics={
            "max_slides": 7,
            "has_appendix": True,
            "required_visual_families": ["bar_chart", "kpi_card", "ranking_table"]
        },
        unacceptable_failures=["POOR_APPENDIX_ROUTING", "OVERLOADED_SLIDE", "THEME_REGRESSION"]
    )


def get_all_validation_scenarios() -> list[ScenarioDefinition]:
    """Returns the full suite of 8 distinct real-world validation scenarios."""
    return [
        create_scenario_a_workforce(),
        create_scenario_b_sales(),
        create_scenario_c_finance(),
        create_scenario_d_software_tech(),
        create_scenario_e_educational(),
        create_scenario_f_research(),
        create_scenario_g_sparse_data(),
        create_scenario_h_dense_multi_sheet()
    ]
