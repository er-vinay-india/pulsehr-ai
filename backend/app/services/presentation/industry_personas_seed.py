"""
Industry-Standard Executive Personas & Report Blueprint Catalogue.
Stores 20+ distinct industry executive personas across diverse sectors:
HR, Talent Acquisition, Compensation, Shift Operations, Retail, Supply Chain,
Manufacturing, Sales, Finance, Quality, Healthcare, Education, IT, Risk, etc.
"""

from typing import Any

INDUSTRY_PERSONAS: list[dict[str, Any]] = [
    {
        "persona_key": "cpo_workforce_auditor",
        "role_title": "Chief People Officer & Workforce Auditor",
        "industry_domain": "Human Resources & Workforce",
        "target_audience": "C-Suite, Executive Committee & HR Leadership",
        "standard_report_name": "Workforce Attendance, Leave & Compliance Audit",
        "report_description": "Audited review of employee attendance rates, leave entitlement balances, overtime burnout thresholds, and localized attendance dispersion.",
        "identifying_keywords": [
            "attendance", "leaves", "absenteeism", "overtime", "employee", "headcount",
            "shift", "clock_in", "clock_out", "punctuality", "workforce", "attrition", "rating"
        ],
        "required_metrics": ["attendance_rate", "leave_utilization", "overtime_hours", "attrition_risk"],
        "core_kpis": [
            {"label": "Average Attendance", "metric_key": "mean_attendance", "format": "pct"},
            {"label": "Overtime Intensity", "metric_key": "overtime_hours", "format": "hours"},
            {"label": "Attrition Risk Population", "metric_key": "high_risk_count", "format": "count"},
            {"label": "Unit Dispersion Ratio", "metric_key": "dispersion_ratio", "format": "ratio"}
        ],
        "slide_outline": [
            "Executive Audit Briefing & Compliance Scope",
            "Workforce Attendance Baselines & Leave Consumption",
            "Overtime Concentration & Burnout Strain Diagnostics",
            "Inter-Departmental Variance & Dispersion Analysis",
            "Workforce Stabilization & Attendance Action Plan",
            "Operational Governance & Escalation SLA Matrix",
            "Cryptographic Evidence Ledger & Audit Verification"
        ],
        "tone_guidelines": "Empirical, audit-grade, focused on operational risk mitigation, statutory adherence, and workforce health."
    },
    {
        "persona_key": "talent_acquisition_planner",
        "role_title": "Head of Talent Acquisition & Workforce Planning",
        "industry_domain": "Talent Acquisition",
        "target_audience": "Executive Leadership & Business Unit Leaders",
        "standard_report_name": "Strategic Headcount Capacity & Talent Acquisition Velocity Report",
        "report_description": "Evaluation of requisition pipelines, offer acceptance yields, requisition aging, and talent intake velocity against business plan.",
        "identifying_keywords": [
            "requisition", "recruiting", "hire", "candidate", "offer", "time_to_fill",
            "applicant", "sourcing", "onboarding", "tenure", "openings", "intake"
        ],
        "required_metrics": ["time_to_hire", "offer_acceptance_rate", "cost_per_hire", "requisition_velocity"],
        "core_kpis": [
            {"label": "Requisition Fill Rate", "metric_key": "fill_rate", "format": "pct"},
            {"label": "Average Time to Fill", "metric_key": "avg_time_to_fill", "format": "days"},
            {"label": "Offer Acceptance", "metric_key": "offer_acceptance", "format": "pct"},
            {"label": "Net Headcount Delta", "metric_key": "net_headcount", "format": "count"}
        ],
        "slide_outline": [
            "Talent Acquisition & Headcount Capacity Executive Review",
            "Recruiting Pipeline Velocity & Offer Yields",
            "Time-to-Fill Trajectory Across Strategic Departments",
            "Hiring Pipeline Bottlenecks & Sourcing Efficiency",
            "Capacity Expansion Roadmap & Hiring Priorities",
            "Talent SLA Governance & Hiring Manager Matrix",
            "Audited Hiring Evidence & Pipeline Ledger"
        ],
        "tone_guidelines": "Strategic, velocity-focused, highlighting growth bottlenecks, recruiter throughput, and talent supply constraints."
    },
    {
        "persona_key": "total_rewards_director",
        "role_title": "Total Rewards & Compensation Director",
        "industry_domain": "Compensation & Benefits",
        "target_audience": "Compensation Committee, CFO & C-Suite",
        "standard_report_name": "Executive Compensation Equity, Pay Bands & Benefits Utilization Review",
        "report_description": "Benchmarking of compa-ratios, salary equity across job levels, benefits cost run-rate, and incentive payout variance.",
        "identifying_keywords": [
            "salary", "compensation", "compa_ratio", "bonus", "benefits", "equity",
            "payroll", "allowance", "incentive", "grade", "pay_band", "wage"
        ],
        "required_metrics": ["compa_ratio", "pay_equity_gap", "incentive_utilization", "benefits_cost_ratio"],
        "core_kpis": [
            {"label": "Average Compa-Ratio", "metric_key": "avg_compa_ratio", "format": "ratio"},
            {"label": "Pay Band Alignment", "metric_key": "band_alignment", "format": "pct"},
            {"label": "Incentive Budget Variance", "metric_key": "incentive_variance", "format": "currency"},
            {"label": "Benefits Utilization", "metric_key": "benefits_util", "format": "pct"}
        ],
        "slide_outline": [
            "Total Rewards & Compensation Equity Executive Summary",
            "Pay Band Distribution & Compa-Ratio Parity",
            "Incentive & Bonus Allocation Against Department Performance",
            "Benefits Cost Analysis & Retention Impact",
            "Reward Calibration & Band Adjustment Roadmap",
            "Compensation Governance & Audit Compliance Framework",
            "Audited Total Rewards Verification Ledger"
        ],
        "tone_guidelines": "Fiduciary, precise, equity-centric, focused on market competitiveness and fiscal discipline."
    },
    {
        "persona_key": "shift_scheduling_manager",
        "role_title": "Workforce Scheduling & Shift Operations Manager",
        "industry_domain": "Shift Operations & Rostering",
        "target_audience": "Operations VP, Plant Managers & Floor Supervisors",
        "standard_report_name": "Workforce Shift Coverage, Overtime Burnout & Roster Adherence Analysis",
        "report_description": "Deep diagnostic of shift attendance, unscheduled shift gaps, overtime distribution among rostered teams, and punctuality.",
        "identifying_keywords": [
            "roster", "shift_pattern", "coverage", "undermanned", "late_days",
            "shift_adherence", "burnout", "duration_hours", "schedule", "overtime", "clock_in"
        ],
        "required_metrics": ["shift_coverage_pct", "late_arrival_rate", "overtime_hours_per_worker", "unplanned_absence"],
        "core_kpis": [
            {"label": "Roster Fill Rate", "metric_key": "roster_coverage", "format": "pct"},
            {"label": "Late Arrival Incidence", "metric_key": "late_rate", "format": "pct"},
            {"label": "Overtime Concentration", "metric_key": "ot_concentration", "format": "ratio"},
            {"label": "Punctuality Index", "metric_key": "punctuality_score", "format": "pct"}
        ],
        "slide_outline": [
            "Shift Operations & Roster Coverage Executive Review",
            "Shift Fill Integrity & Undermanned Station Analysis",
            "Overtime Spikes & High-Burnout Squad Identification",
            "Late Arrivals & Punctuality Variance Across Rosters",
            "Shift Optimization & Schedule Balancing Action Plan",
            "Floor Supervisor SLA & Roster Adherence Matrix",
            "Audited Shift Timesheet & Adherence Ledger"
        ],
        "tone_guidelines": "Operational, tactical, grounded in shift logs, punctuality metrics, and labor efficiency."
    },
    {
        "persona_key": "retail_regional_director",
        "role_title": "Retail Regional Operations Director",
        "industry_domain": "Retail Operations",
        "target_audience": "Chief Commercial Officer, Regional GMs & Store Ops",
        "standard_report_name": "Multi-Store Performance, Footfall & Unit Sales Executive Review",
        "report_description": "Cross-store comparison of weekly sales volumes, customer basket size, store footfall conversion, and markdown impact.",
        "identifying_keywords": [
            "store", "store_sales", "footfall", "basket_size", "pos", "retail",
            "shrinkage", "same_store", "sku", "merchandising", "checkout", "weekly_sales"
        ],
        "required_metrics": ["weekly_sales", "sales_per_sqft", "basket_size", "conversion_rate"],
        "core_kpis": [
            {"label": "Average Store Sales", "metric_key": "mean_store_sales", "format": "currency"},
            {"label": "Top Store Multiple", "metric_key": "store_dispersion", "format": "ratio"},
            {"label": "Basket Size Benchmark", "metric_key": "basket_size", "format": "currency"},
            {"label": "Same-Store Trajectory", "metric_key": "comp_store_growth", "format": "pct"}
        ],
        "slide_outline": [
            "Regional Retail Performance & Multi-Store Overview",
            "Store Revenue Distribution & Top Quartile Drivers",
            "Footfall Conversion & Average Basket Size Diagnostics",
            "Underperforming Store Variance & Markdown Leakage",
            "Store Turnaround Initiatives & Merchandising Roadmap",
            "Store Manager Execution Governance & Weekly Targets",
            "Audited Store Transaction & Revenue Evidence Ledger"
        ],
        "tone_guidelines": "Commercial, revenue-driven, comparative, highlighting store-to-store variance and retail throughput."
    },
    {
        "persona_key": "store_general_manager",
        "role_title": "Store General Manager & Floor Operations Lead",
        "industry_domain": "Store Operations",
        "target_audience": "Store Leadership, District Managers & Department Heads",
        "standard_report_name": "Store Daily Trading, Department Turnover & Shrinkage Diagnostic",
        "report_description": "Detailed store-level analysis of departmental sales, cashier checkout throughput, inventory loss/shrinkage, and customer traffic.",
        "identifying_keywords": [
            "register", "cashier", "floor_traffic", "daily_sales", "return_rate",
            "shrinkage", "store_id", "department_sales", "units_per_transaction"
        ],
        "required_metrics": ["daily_turnover", "shrinkage_pct", "units_per_transaction", "return_ratio"],
        "core_kpis": [
            {"label": "Daily Floor Turnover", "metric_key": "daily_turnover", "format": "currency"},
            {"label": "Shrinkage Rate", "metric_key": "shrinkage_rate", "format": "pct"},
            {"label": "Department Top Seller", "metric_key": "top_department", "format": "string"},
            {"label": "Checkout Velocity", "metric_key": "checkout_rate", "format": "number"}
        ],
        "slide_outline": [
            "Store Daily Trading & Departmental Performance Briefing",
            "Department Sales Contribution & High-Velocity Categories",
            "Inventory Shrinkage & Loss Prevention Diagnostics",
            "Register Throughput & Peak Trading Hour Bottlenecks",
            "Floor Recovery & Loss Mitigation Action Plan",
            "Department Supervisor Accountability & Daily Checklists",
            "Audited Register Receipts & Inventory Audit Ledger"
        ],
        "tone_guidelines": "Floor-level, actionable, immediate, emphasizing daily inventory control and department accountability."
    },
    {
        "persona_key": "supply_chain_vp",
        "role_title": "Supply Chain & Logistics Network VP",
        "industry_domain": "Supply Chain & Logistics",
        "target_audience": "COO, Head of Procurement & Carrier Partners",
        "standard_report_name": "End-to-End Supply Chain OTIF Delivery & Freight Logistics Assessment",
        "report_description": "Analysis of on-time, in-full (OTIF) fulfillment rates, carrier transit dwell times, supplier lead time reliability, and freight costs.",
        "identifying_keywords": [
            "otif", "on_time", "shipment", "freight", "transit_time", "carrier",
            "customs", "fulfillment", "lead_time", "logistics", "consignment", "order_fulfillment"
        ],
        "required_metrics": ["otif_rate", "dwell_time_hours", "freight_cost_per_unit", "supplier_lead_time_days"],
        "core_kpis": [
            {"label": "OTIF Delivery Rate", "metric_key": "otif_pct", "format": "pct"},
            {"label": "Carrier Dwell Time", "metric_key": "avg_dwell_time", "format": "hours"},
            {"label": "Lead Time Variance", "metric_key": "lead_time_spread", "format": "days"},
            {"label": "Expedited Freight Cost", "metric_key": "expedited_cost", "format": "currency"}
        ],
        "slide_outline": [
            "Supply Chain Network Performance & Fulfillment Executive Review",
            "Carrier OTIF Reliability & Route Performance",
            "Freight Dwell Bottlenecks & Transit Delay Hotspots",
            "Supplier Lead Time Dispersion & Stockout Exposure",
            "Logistics Optimization & Route Stabilization Initiatives",
            "Carrier SLA Governance & Penalty Enforcement Matrix",
            "Audited Consignment & Delivery Verification Ledger"
        ],
        "tone_guidelines": "Systemic, bottleneck-oriented, measured in service level agreements and supply reliability."
    },
    {
        "persona_key": "warehouse_operations_lead",
        "role_title": "Warehouse Operations & Distribution Center Director",
        "industry_domain": "Warehouse Operations",
        "target_audience": "VP Logistics, DC Operations & Shift Leads",
        "standard_report_name": "Distribution Center Pick-Pack Efficiency & Inventory Turn Audit",
        "report_description": "Comprehensive review of warehouse putaway velocity, pick-pack line efficiency, pallet space utilization, and stock accuracy.",
        "identifying_keywords": [
            "warehouse", "pick_pack", "putaway", "inventory_turn", "stockout",
            "bin_location", "pallet", "throughput_pallets", "cycle_time", "fulfillment_center"
        ],
        "required_metrics": ["units_picked_per_hour", "putaway_cycle_time", "bin_accuracy_pct", "dock_to_stock_hours"],
        "core_kpis": [
            {"label": "Pick-Pack Velocity", "metric_key": "pick_rate", "format": "number"},
            {"label": "Dock-to-Stock Time", "metric_key": "dock_to_stock", "format": "hours"},
            {"label": "Inventory Accuracy", "metric_key": "stock_accuracy", "format": "pct"},
            {"label": "Space Utilization", "metric_key": "bin_utilization", "format": "pct"}
        ],
        "slide_outline": [
            "Distribution Center Velocity & Warehouse Throughput Summary",
            "Pick-Pack Productivity & Labor Line Output",
            "Dock-to-Stock Lag & High-Density Bin Congestion",
            "Cycle Count Variance & Physical Inventory Discrepancies",
            "Warehouse Modernization & Slotting Optimization Plan",
            "DC Shift Supervision Matrix & Safety Compliance Controls",
            "Audited Pick Logs & Inventory Reconciliation Ledger"
        ],
        "tone_guidelines": "Throughput-driven, space-conscious, focused on line efficiency and order fulfillment velocity."
    },
    {
        "persona_key": "plant_reliability_engineer",
        "role_title": "Plant Reliability & Manufacturing Maintenance Engineer",
        "industry_domain": "Manufacturing & Industrial Maintenance",
        "target_audience": "VP Manufacturing, Plant Managers & Operations Engineers",
        "standard_report_name": "Plant Equipment Reliability, MTBF & Overall Equipment Effectiveness (OEE) Report",
        "report_description": "Evaluation of line breakdown frequencies, mean time between failures (MTBF), mean time to repair (MTTR), and OEE production yield loss.",
        "identifying_keywords": [
            "oee", "mtbf", "mttr", "downtime", "maintenance", "machine",
            "production_line", "yield", "scrap_rate", "unplanned_stop", "equipment"
        ],
        "required_metrics": ["oee_pct", "mtbf_hours", "mttr_hours", "unplanned_downtime_pct"],
        "core_kpis": [
            {"label": "Overall Equipment Effectiveness", "metric_key": "oee", "format": "pct"},
            {"label": "Mean Time Between Failures", "metric_key": "mtbf", "format": "hours"},
            {"label": "Mean Time to Repair", "metric_key": "mttr", "format": "hours"},
            {"label": "Unplanned Stoppages", "metric_key": "unplanned_stops", "format": "count"}
        ],
        "slide_outline": [
            "Plant Reliability & OEE Executive Review",
            "Equipment Availability & Unplanned Downtime Breakdown",
            "MTBF vs MTTR Trajectory Across Critical Production Lines",
            "Scrap Generation & Production Yield Degradation",
            "Preventive Maintenance & Equipment Overhaul Schedule",
            "Plant Maintenance RACI & Maintenance Work Order Governance",
            "Audited Equipment Downtime Logs & Telemetry Ledger"
        ],
        "tone_guidelines": "Engineering-grade, root-cause focused, zero-defect oriented, measuring uptime resilience."
    },
    {
        "persona_key": "commercial_sales_vp",
        "role_title": "Commercial Sales VP & Chief Revenue Officer",
        "industry_domain": "Enterprise Sales & Commercial Operations",
        "target_audience": "Board of Directors, CEO, CRO & Regional Sales Directors",
        "standard_report_name": "Executive Revenue Attainment, Pipeline Velocity & Deal Win-Loss Analysis",
        "report_description": "Strategic analysis of revenue quota attainment, deal progression stages, sales pipeline coverage, and account win rates.",
        "identifying_keywords": [
            "pipeline", "quota", "arr", "acv", "deal_stage", "win_rate",
            "sales_rep", "bookings", "closed_won", "forecast_category", "revenue", "sales"
        ],
        "required_metrics": ["quota_attainment_pct", "deal_win_rate", "average_deal_size", "pipeline_coverage_ratio"],
        "core_kpis": [
            {"label": "Quota Attainment", "metric_key": "quota_attainment", "format": "pct"},
            {"label": "Closed-Won Volume", "metric_key": "bookings_total", "format": "currency"},
            {"label": "Win Rate Benchmark", "metric_key": "win_rate", "format": "pct"},
            {"label": "Pipeline Coverage", "metric_key": "pipeline_multiple", "format": "ratio"}
        ],
        "slide_outline": [
            "Commercial Revenue Performance & Quota Attainment Executive Review",
            "Pipeline Coverage Multiples & Quarterly Bookings Velocity",
            "Win/Loss Rates & Competitor Dispersion Diagnostics",
            "Underperforming Territory Gaps & Deal Slippage Hotspots",
            "Revenue Acceleration Initiatives & Target Account Strategy",
            "Commercial Governance, Quota Rules & Sales Territory RACI",
            "Audited CRM Opportunity & Revenue Proof Ledger"
        ],
        "tone_guidelines": "High-conviction, executive, revenue-centered, focused on quarterly growth and closing pipeline gaps."
    },
    {
        "persona_key": "inside_sales_lead",
        "role_title": "Inside Sales & Business Development Manager",
        "industry_domain": "Sales Development & Inside Sales",
        "target_audience": "Sales Operations VP, SDR Leadership & Account Executives",
        "standard_report_name": "Outbound Lead Qualification, Pipeline Conversion & SDR Performance Scorecard",
        "report_description": "Operational tracking of outbound call/email activity, lead conversion rates, demo completion ratios, and SDR quota attainment.",
        "identifying_keywords": [
            "leads", "mql", "sql", "opportunity", "qualification_rate", "demos",
            "conversion_rate", "outreach", "call_volume", "pipeline_generated"
        ],
        "required_metrics": ["lead_conversion_rate", "mql_to_sql_velocity", "demo_hold_rate", "pipeline_per_rep"],
        "core_kpis": [
            {"label": "Lead-to-Opp Conversion", "metric_key": "lead_conversion", "format": "pct"},
            {"label": "Qualified Opportunities", "metric_key": "sql_count", "format": "count"},
            {"label": "Average SDR Attainment", "metric_key": "sdr_attainment", "format": "pct"},
            {"label": "Activity per Qualified Deal", "metric_key": "touches_per_deal", "format": "number"}
        ],
        "slide_outline": [
            "Sales Development Velocity & Outbound Conversion Overview",
            "Lead Stage Funnel: MQL to Opportunity Velocity",
            "SDR Output Dispersion & High-Performing Pitch Patterns",
            "Lead Disqualification Root Causes & Channel Drop-offs",
            "Outbound Playbook Upgrades & SDR Quota Ramp Strategy",
            "Lead Handoff SLA & AE Acceptance Governance",
            "Audited Lead Activity Logs & Opportunity Ledger"
        ],
        "tone_guidelines": "Action-oriented, pipeline-focused, tracking funnel friction and sales development velocity."
    },
    {
        "persona_key": "customer_success_vp",
        "role_title": "VP of Customer Success & Client Retention",
        "industry_domain": "Customer Success & SaaS Retention",
        "target_audience": "Executive Leadership, Chief Customer Officer & C-Suite",
        "standard_report_name": "Net Retention, Churn Risk & Customer Health Executive Scorecard",
        "report_description": "Portfolio assessment of Net Revenue Retention (NRR), gross churn, customer health scores, usage expansion, and NPS trends.",
        "identifying_keywords": [
            "nps", "churn", "net_retention", "mrr", "renewal", "csat",
            "health_score", "active_users", "expansion_arr", "customer_tier", "tickets"
        ],
        "required_metrics": ["net_retention_rate", "gross_churn_rate", "nps_score", "customer_health_index"],
        "core_kpis": [
            {"label": "Net Revenue Retention", "metric_key": "nrr", "format": "pct"},
            {"label": "Gross Churn Rate", "metric_key": "gross_churn", "format": "pct"},
            {"label": "At-Risk Account Value", "metric_key": "at_risk_mrr", "format": "currency"},
            {"label": "Average Health Score", "metric_key": "health_score", "format": "number"}
        ],
        "slide_outline": [
            "Customer Retention, NRR & Portfolio Health Executive Briefing",
            "Expansion Revenue Velocity vs Churn Drag",
            "Customer Health Score Distributions & At-Risk Account Tiers",
            "Renewal Cohort Vulnerabilities & Product Adoption Gaps",
            "Proactive Retention Playbooks & Customer Success Roadmap",
            "Customer Escalation Governance & Executive Sponsor Matrix",
            "Audited Customer Renewal & Contract Evidence Ledger"
        ],
        "tone_guidelines": "Relationship-focused, proactive, centered on lifetime value preservation and customer satisfaction."
    },
    {
        "persona_key": "cfo_controller",
        "role_title": "Chief Financial Officer & Corporate Controller",
        "industry_domain": "Corporate Finance & Treasury",
        "target_audience": "Board of Directors, Audit Committee, CEO & Finance Leadership",
        "standard_report_name": "Financial Operating Performance, Margin Variance & Capital Allocation Review",
        "report_description": "Rigorous financial review of EBITDA margins, operating expenses vs budget, capital expenditure run-rate, and cash flow predictability.",
        "identifying_keywords": [
            "ebitda", "operating_margin", "revenue", "capex", "opex", "cogs",
            "variance", "budget", "cash_flow", "balance_sheet", "pnl", "gross_margin"
        ],
        "required_metrics": ["ebitda_margin_pct", "budget_variance_pct", "operating_cash_flow", "gross_profit_margin"],
        "core_kpis": [
            {"label": "Operating Margin", "metric_key": "operating_margin", "format": "pct"},
            {"label": "Budget Variance", "metric_key": "budget_variance", "format": "pct"},
            {"label": "EBITDA Actual vs Plan", "metric_key": "ebitda_actual", "format": "currency"},
            {"label": "Opex Run-Rate Efficiency", "metric_key": "opex_ratio", "format": "ratio"}
        ],
        "slide_outline": [
            "Financial Performance & Executive Operating Review",
            "Revenue Realization, Gross Margin & EBITDA Trajectory",
            "Budget vs Actual Variance Across Operating Units",
            "Discretionary Spend Concentration & Capital Allocation Drag",
            "Fiscal Optimization Initiatives & Budget Target Roadmap",
            "Financial Controls, Signing Limits & Approval Matrix",
            "Audited General Ledger Reconciliation & Balance Ledger"
        ],
        "tone_guidelines": "Strict, fiduciary, audit-verified, conservative, emphasizing fiscal discipline and GAAP integrity."
    },
    {
        "persona_key": "qa_compliance_auditor",
        "role_title": "Quality Assurance & Regulatory Compliance Auditor",
        "industry_domain": "Quality Management & Regulatory Affairs",
        "target_audience": "Chief Quality Officer, VP Compliance & External Regulators",
        "standard_report_name": "Operational Quality Audit, Defect PPM & Regulatory Compliance Briefing",
        "report_description": "Comprehensive audit of product/service non-conformances, parts-per-million (PPM) defects, CAPA resolution velocity, and regulatory standards.",
        "identifying_keywords": [
            "defect", "ppm", "compliance", "audit", "non_conformance", "capa",
            "inspection", "iso_standard", "pass_rate", "regulatory", "deviation", "audit_score"
        ],
        "required_metrics": ["defect_ppm", "audit_pass_rate_pct", "capa_closure_rate", "critical_non_conformance_count"],
        "core_kpis": [
            {"label": "Audit Compliance Pass Rate", "metric_key": "pass_rate", "format": "pct"},
            {"label": "Defect Concentration", "metric_key": "defect_ppm", "format": "number"},
            {"label": "Open CAPA Investigations", "metric_key": "open_capa", "format": "count"},
            {"label": "Audit Non-Conformances", "metric_key": "deviations", "format": "count"}
        ],
        "slide_outline": [
            "Quality Assurance & Regulatory Compliance Executive Briefing",
            "Audit Pass Rates & Statutory Standards Conformance",
            "Defect PPM Trends & Failure Mode Effects Analysis",
            "Non-Conformance Root Causes & Repeat Deviation Findings",
            "Corrective Action Prevention Plan (CAPA) Roadmap",
            "Regulatory Ownership, Audit Readiness & Accountability Matrix",
            "Audited Compliance Inspection & Verification Ledger"
        ],
        "tone_guidelines": "Rigorous, evidentiary, standards-based, uncompromising on protocol compliance."
    },
    {
        "persona_key": "hospital_operations_lead",
        "role_title": "Clinical Healthcare & Hospital Operations Director",
        "industry_domain": "Healthcare & Clinical Operations",
        "target_audience": "Hospital Board, Chief Medical Officer & Clinical Chairs",
        "standard_report_name": "Clinical Operations, Bed Occupancy & Patient Care Velocity Audit",
        "report_description": "Evaluation of inpatient bed occupancy, emergency department triage wait times, nurse-to-patient staffing ratios, and readmission rates.",
        "identifying_keywords": [
            "patient", "admission", "bed_occupancy", "length_of_stay", "nurse_ratio",
            "readmission", "clinic", "diagnosis", "triage", "inpatient", "discharge", "hospital"
        ],
        "required_metrics": ["bed_occupancy_rate", "average_length_of_stay", "readmission_rate_pct", "triage_wait_time_minutes"],
        "core_kpis": [
            {"label": "Bed Occupancy Rate", "metric_key": "bed_occupancy", "format": "pct"},
            {"label": "Average Length of Stay", "metric_key": "alos_days", "format": "days"},
            {"label": "30-Day Readmissions", "metric_key": "readmission_pct", "format": "pct"},
            {"label": "Clinical Staffing Ratio", "metric_key": "staffing_ratio", "format": "ratio"}
        ],
        "slide_outline": [
            "Hospital Clinical Operations & Patient Flow Executive Briefing",
            "Inpatient Bed Capacity & Ward Utilization Trends",
            "Emergency Department Triage & Length of Stay Diagnostics",
            "Staffing Coverage Ratios & Clinical Care Bottlenecks",
            "Patient Flow Optimization & Care Coordination Roadmap",
            "Clinical Governance, Physician Oversight & Triage Protocols",
            "Audited Patient Census & Clinical Delivery Ledger"
        ],
        "tone_guidelines": "Clinical, patient-welfare focused, safety-oriented, balancing care standards and operational efficiency."
    },
    {
        "persona_key": "academic_affairs_dean",
        "role_title": "Higher Education Academic Dean & Registrar",
        "industry_domain": "Higher Education & Academic Affairs",
        "target_audience": "University Provost, Academic Senate & Department Chairs",
        "standard_report_name": "Academic Enrollment Yield, Student Retention & Graduation Velocity Report",
        "report_description": "Evaluation of applicant enrollment yields, term-to-term student retention, credit accumulation rates, and graduation velocity.",
        "identifying_keywords": [
            "student", "enrollment", "gpa", "course", "credits", "retention_rate",
            "graduation", "faculty", "semester", "tuition", "admissions", "academic"
        ],
        "required_metrics": ["enrollment_yield_pct", "retention_rate_pct", "average_gpa", "credit_completion_pct"],
        "core_kpis": [
            {"label": "First-Year Retention", "metric_key": "retention_rate", "format": "pct"},
            {"label": "Enrollment Yield", "metric_key": "enrollment_yield", "format": "pct"},
            {"label": "Credit Completion Rate", "metric_key": "completion_rate", "format": "pct"},
            {"label": "Cohort Graduation Benchmark", "metric_key": "grad_rate", "format": "pct"}
        ],
        "slide_outline": [
            "Academic Affairs & Enrollment Velocity Executive Summary",
            "Student Enrollment Distribution & Program Capacity",
            "Term-over-Term Retention Trajectory & Drop-out Indicators",
            "Academic Course Pass Rates & GPA Dispersion",
            "Student Success Interventions & Academic Advising Roadmap",
            "Faculty Academic Governance & Course Ownership Matrix",
            "Audited Academic Registrar & Degree Progress Ledger"
        ],
        "tone_guidelines": "Scholarly, institution-building, student-success focused, evaluating educational outcomes."
    },
    {
        "persona_key": "devops_infrastructure_lead",
        "role_title": "IT Service Delivery & DevOps Infrastructure Director",
        "industry_domain": "IT Operations & Cloud Infrastructure",
        "target_audience": "CTO, VP Engineering, InfoSec & SRE Team Leads",
        "standard_report_name": "IT Infrastructure Reliability, MTTR & Incident SLA Governance Briefing",
        "report_description": "Operational audit of cloud uptime percentages, P1/P2 incident MTTR, change failure rates, and service SLA compliance.",
        "identifying_keywords": [
            "uptime", "sla", "incident", "severity_1", "change_failure",
            "ticket_resolution", "latency", "server", "cloud_cost", "p1_incident", "deployments"
        ],
        "required_metrics": ["system_uptime_pct", "incident_mttr_minutes", "change_failure_rate", "sla_attainment_pct"],
        "core_kpis": [
            {"label": "Platform Availability", "metric_key": "uptime", "format": "pct"},
            {"label": "Severity 1 MTTR", "metric_key": "mttr_mins", "format": "minutes"},
            {"label": "SLA Compliance Rate", "metric_key": "sla_rate", "format": "pct"},
            {"label": "Change Failure Rate", "metric_key": "cfr_pct", "format": "pct"}
        ],
        "slide_outline": [
            "IT Infrastructure Reliability & Service Availability Executive Review",
            "Uptime SLA Attainment & Critical Service Uptime",
            "Incident Mean Time to Resolution (MTTR) Trends",
            "Change Failure Analysis & Deployment Bottlenecks",
            "Infrastructure Hardening & SRE Automation Roadmap",
            "On-Call Incident Escalation & Engineering Accountability Matrix",
            "Audited Telemetry Logs & Incident Resolution Ledger"
        ],
        "tone_guidelines": "Technical, reliability-first, incident-resilient, measured in nines of uptime and recovery speed."
    },
    {
        "persona_key": "risk_internal_controls_officer",
        "role_title": "Enterprise Risk & Internal Controls Officer",
        "industry_domain": "Enterprise Risk Management",
        "target_audience": "Board Audit Committee, CEO, General Counsel & External Auditors",
        "standard_report_name": "Enterprise Risk Heatmap, Policy Exceptions & Internal Controls Audit",
        "report_description": "Systemic analysis of internal audit deficiencies, segregation of duties exceptions, policy non-compliance, and risk remediation progress.",
        "identifying_keywords": [
            "risk_score", "internal_audit", "deficiency", "policy_exception", "fraud",
            "sox", "control_gap", "audit_finding", "governance_risk", "mitigation", "controls"
        ],
        "required_metrics": ["material_weakness_count", "control_exception_rate", "audit_deficiency_remediation_pct", "risk_index"],
        "core_kpis": [
            {"label": "Audit Deficiency Count", "metric_key": "deficiency_count", "format": "count"},
            {"label": "Remediation Velocity", "metric_key": "remediation_rate", "format": "pct"},
            {"label": "High-Risk Exposure Areas", "metric_key": "high_risk_units", "format": "count"},
            {"label": "Policy Exception Rate", "metric_key": "exception_rate", "format": "pct"}
        ],
        "slide_outline": [
            "Enterprise Risk Heatmap & Internal Controls Executive Briefing",
            "Control Framework Coverage & Testing Completion",
            "Audit Deficiency Severity Breakdown & Repeat Findings",
            "Cross-Departmental Policy Non-Compliance Hotspots",
            "Risk Remediation Milestones & Control Hardening Roadmap",
            "Internal Controls Accountability & Business Unit Ownership Matrix",
            "Audited Risk Register & Testing Evidence Ledger"
        ],
        "tone_guidelines": "Objective, defensive, regulatory-aligned, prioritizing vulnerability exposure and mitigation."
    },
    {
        "persona_key": "contact_center_cx_lead",
        "role_title": "Contact Center & BPO Customer Experience Director",
        "industry_domain": "Customer Support Operations & BPO",
        "target_audience": "VP Customer Service, BPO Site Directors & Operations Managers",
        "standard_report_name": "Omnichannel Support Velocity, First Contact Resolution & CSAT Review",
        "report_description": "Operational analysis of contact center queue abandonments, Average Handle Time (AHT), First Contact Resolution (FCR), and agent CSAT scores.",
        "identifying_keywords": [
            "first_contact_resolution", "aht", "csat", "handle_time", "agent",
            "call_queue", "abandonment_rate", "tickets_resolved", "customer_effort", "sla_breach"
        ],
        "required_metrics": ["fcr_pct", "aht_seconds", "call_abandonment_pct", "csat_score"],
        "core_kpis": [
            {"label": "First Contact Resolution", "metric_key": "fcr", "format": "pct"},
            {"label": "Average Handle Time", "metric_key": "aht", "format": "seconds"},
            {"label": "Queue Abandonment Rate", "metric_key": "abandon_rate", "format": "pct"},
            {"label": "Customer Satisfaction Score", "metric_key": "csat", "format": "score"}
        ],
        "slide_outline": [
            "Contact Center Velocity & Omnichannel Operations Briefing",
            "Volume Intake, Queue Abandonment & Service Level Adherence",
            "First Contact Resolution & Average Handle Time Trajectory",
            "Agent Performance Dispersion & Ticket Escalation Hotspots",
            "Workforce Optimization & CX Quality Enhancement Plan",
            "Queue Supervisor SLA Governance & Escalation Protocols",
            "Audited Ticket Telemetry & Contact Center Quality Ledger"
        ],
        "tone_guidelines": "Customer-centric, velocity-driven, balancing agent efficiency with customer satisfaction."
    },
    {
        "persona_key": "fleet_transport_director",
        "role_title": "Fleet & Commercial Transport Logistics Director",
        "industry_domain": "Fleet Logistics & Transportation",
        "target_audience": "VP Logistics, Operations Director & Dispatch Leadership",
        "standard_report_name": "Fleet Utilization, Cost Per Mile & Driver Safety Telematics Audit",
        "report_description": "Telemetry audit of vehicle idle time, fleet cost-per-mile, preventive maintenance adherence, and route delivery efficiency.",
        "identifying_keywords": [
            "fleet", "vehicle", "mileage", "fuel_efficiency", "driver_safety",
            "dwell_time", "cost_per_mile", "telematics", "route_efficiency", "cargo", "trips"
        ],
        "required_metrics": ["fleet_utilization_pct", "cost_per_mile", "idle_fuel_waste_pct", "telematics_safety_score"],
        "core_kpis": [
            {"label": "Fleet Asset Utilization", "metric_key": "fleet_utilization", "format": "pct"},
            {"label": "Cost Per Mile Benchmark", "metric_key": "cost_per_mile", "format": "currency"},
            {"label": "Driver Safety Score", "metric_key": "safety_score", "format": "score"},
            {"label": "Idle Time Reduction", "metric_key": "idle_time_pct", "format": "pct"}
        ],
        "slide_outline": [
            "Fleet Operations & Commercial Transport Executive Review",
            "Asset Utilization Trajectory & Vehicle Out-of-Service Rates",
            "Cost Per Mile & Fuel Efficiency Dispersion Across Routes",
            "Telematics Safety Alerts & Dwell Delay Hotspots",
            "Route Optimization & Fleet Modernization Roadmap",
            "Dispatch RACI, Driver Accountability & Safety Governance",
            "Audited Vehicle Telematics & Trip Proof Ledger"
        ],
        "tone_guidelines": "Asset-centric, safety-focused, cost-conscious, balancing fleet maintenance with dispatch efficiency."
    },
    {
        "persona_key": "executive_strategist_generic",
        "role_title": "Executive Business Strategist & General Manager",
        "industry_domain": "Enterprise General Management",
        "target_audience": "C-Suite, Executive Committee & Operating Board",
        "standard_report_name": "Executive Operational Review & Strategic Performance Diagnostic",
        "report_description": "Structured executive analysis evaluating central tendencies, dispersion ratios, category concentrations, and operational stabilization.",
        "identifying_keywords": [
            "performance", "records", "metrics", "benchmark", "operations", "strategic", "summary", "data"
        ],
        "required_metrics": ["central_benchmark", "dispersion_ratio", "completeness_pct"],
        "core_kpis": [
            {"label": "Performance Benchmark", "metric_key": "central_benchmark", "format": "number"},
            {"label": "Dispersion Multiple", "metric_key": "dispersion_ratio", "format": "ratio"},
            {"label": "Evaluated Population", "metric_key": "total_records", "format": "count"},
            {"label": "Data Completeness", "metric_key": "completeness", "format": "pct"}
        ],
        "slide_outline": [
            "Executive Operational Review & Core Performance",
            "Analysis Scope & Dataset Governance Baseline",
            "Operational Strengths & Primary Throughput Surge",
            "Operational Headwinds & Unit Dispersion Analysis",
            "Distribution Concentration & Key Cohort Breakdown",
            "Strategic Roadmap: Performance Stabilization Initiatives",
            "Execution Governance & RACI Responsibility Matrix",
            "Audited Evidence Ledger: Cryptographic Verification"
        ],
        "tone_guidelines": "Executive, objective, data-grounded, strategic, delivering clear decision-grade insights."
    }
]
