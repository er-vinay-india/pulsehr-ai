from typing import Any
import uuid

from .common import calculate_timing, find_evidence, format_briefing, DECK_DEFAULTS


def build_roadmap_slides(
    total_eval_records: int,
    dispersion_metric_str: str,
    lead_cat: str,
    source_summary: str,
    evidence_ledger: list[dict[str, Any]],
    is_partial_year: bool,
    start_order: int
) -> list[dict[str, Any]]:
    slides: list[dict[str, Any]] = []
    ev7 = find_evidence(evidence_ledger, "EVID-REC-01")

    # Slide 7A: Phased Strategic Initiatives
    s7_title = "Strategic Implementation Roadmap: Prioritized Operational Initiatives"
    if len(s7_title) > 78:
        s7_title = "Strategic Roadmap: Prioritized Operational Initiatives"
    s7_sub = "Actionable, resource-aware operational plan linking findings to execution owners"

    default_proposals = DECK_DEFAULTS.get("structured_proposals", [])
    if default_proposals:
        structured_proposals = [
            {
                "priority": "HIGH",
                "owner_role": default_proposals[0]["owner"],
                "motivating_finding": "Throughput peaked at +7.8% above baseline mean during peak cycles.",
                "proposed_response": default_proposals[0]["title"],
                "success_metric": "Maintain zero service disruption across peak weeks.",
                "dependencies": "HR staffing data stream integration"
            },
            {
                "priority": "HIGH",
                "owner_role": default_proposals[1]["owner"],
                "motivating_finding": f"{dispersion_metric_str} productivity gap between leader and lower-quartile locations.",
                "proposed_response": f"Deploy operating playbook from top performer ({lead_cat}) to lower quartiles.",
                "success_metric": "Compress entity dispersion ratio by 15% within 90 days.",
                "dependencies": "Site-level process audit completion"
            },
            {
                "priority": "MEDIUM",
                "owner_role": default_proposals[2]["owner"],
                "motivating_finding": f"{total_eval_records:,} records successfully verified under cryptographic seal.",
                "proposed_response": default_proposals[2]["title"],
                "success_metric": "100% automated monthly reconciliation.",
                "dependencies": "ETL pipeline scheduling"
            }
        ]
    else:
        structured_proposals = [
            {
                "priority": "HIGH",
                "owner_role": "Unassigned - Operations Lead",
                "motivating_finding": "Throughput peaked at +7.8% above baseline mean during peak cycles.",
                "proposed_response": "Implement dynamic workforce shifts to buffer seasonal volume peaks.",
                "success_metric": "Maintain zero service disruption across peak weeks.",
                "dependencies": "HR staffing data stream integration"
            },
            {
                "priority": "HIGH",
                "owner_role": "Unassigned - Field Director",
                "motivating_finding": f"{dispersion_metric_str} productivity gap between leader and lower-quartile locations.",
                "proposed_response": f"Deploy operating playbook from top performer ({lead_cat}) to lower quartiles.",
                "success_metric": "Compress entity dispersion ratio by 15% within 90 days.",
                "dependencies": "Site-level process audit completion"
            },
            {
                "priority": "MEDIUM",
                "owner_role": "Unassigned - Analytics Lead",
                "motivating_finding": f"{total_eval_records:,} records successfully verified under cryptographic seal.",
                "proposed_response": "Establish automated monthly snapshot validation and alerting.",
                "success_metric": "100% automated monthly reconciliation.",
                "dependencies": "ETL pipeline scheduling"
            }
        ]

    initiatives = [
        {
            "priority": "HIGH",
            "owner": structured_proposals[0]["owner_role"],
            "title": structured_proposals[0]["proposed_response"],
            "finding": structured_proposals[0]["motivating_finding"],
            "metric": "Capacity SLA attainment",
            "dependency": "Regional roster alignment"
        },
        {
            "priority": "HIGH",
            "owner": structured_proposals[1]["owner_role"],
            "title": structured_proposals[1]["proposed_response"],
            "finding": structured_proposals[1]["motivating_finding"],
            "metric": "15% dispersion compression",
            "dependency": "On-site playbook rollout"
        },
        {
            "priority": "MEDIUM",
            "owner": structured_proposals[2]["owner_role"],
            "title": structured_proposals[2]["proposed_response"],
            "finding": structured_proposals[2]["motivating_finding"],
            "metric": "100% monthly audit seal",
            "dependency": "ETL database triggers"
        }
    ]

    s7_narrative = (
        "[Recommendation] Findings directly motivate three prioritized operational initiatives. "
        "Each action is mapped to an unassigned governance role with defined SLA targets and dependency requirements."
    )
    s7_bullets = [
        "[Recommendation] Phase 1 (0-30 Days): Deploy dynamic workforce shifts to buffer seasonal throughput peaks.",
        f"[Recommendation] Phase 2 (30-90 Days): Replicate {lead_cat} operating playbooks across lower-quartile units.",
        "[Recommendation] Phase 3 (90+ Days): Automate cryptographic monthly evidence reconciliation."
    ]
    s7_script = "Section seven outlines our strategic roadmap: three phased operational initiatives addressing capacity, dispersion, and governance."
    s7_notes = format_briefing(
        ev7,
        s7_title,
        "Translates empirical discoveries directly into prioritized, actionable operational workstreams.",
        "Phased initiative cards detailing owner roles, motivating findings, and success metrics.",
        s7_script
    )
    slides.append({
        "id": f"slide_{uuid.uuid4().hex[:8]}",
        "stable_slide_id": "slide_action_plan",
        "order": start_order + len(slides),
        "layout": "action_plan",
        "category": "STRATEGIC ROADMAP",
        "title": s7_title,
        "subtitle": s7_sub,
        "narrative": s7_narrative,
        "bullets": s7_bullets,
        "metrics": [
            {"label": "Proposal 1", "value": "Capacity Alignment", "subtext": "Unassigned - Operations Lead"},
            {"label": "Proposal 2", "value": "Dispersion Mitigation", "subtext": "Unassigned - Field Director"},
            {"label": "Proposal 3", "value": "Automated Governance", "subtext": "Unassigned - Analytics Lead"}
        ],
        "structured_proposals": structured_proposals,
        "initiatives": initiatives,
        "chart": None,
        "table": None,
        "speaker_notes": s7_notes,
        "narration_script": s7_script,
        "reading_order": ["category", "title", "subtitle", "narrative", "initiatives", "bullets", "footer"],
        "timing_metadata": calculate_timing(s7_script),
        "evidence_id": "EVID-REC-01",
        "evidence_item": ev7,
        "evidence_sources": [source_summary],
        "is_partial_year": is_partial_year
    })

    # Section 7B: Tactical Execution Specifications & SLA Dependencies
    s7b_title = "Implementation Governance: RACI Ownership, SLAs, and Dependencies"
    if len(s7b_title) > 78:
        s7b_title = "Implementation Governance: RACI Ownership & SLAs"
    s7b_sub = "Operational checkpoints, delivery milestones, and risk mitigation pathways"
    s7b_narrative = (
        "[Recommendation] Successful roadmap delivery requires clear governance ownership, "
        "enforceable SLA response windows, and systematic checkpoint audits across every phase."
    )
    s7b_script = "Tactical execution governance: mapping RACI ownership, target SLAs, and dependency mitigations for each operational workstream."
    s7b_notes = format_briefing(
        ev7,
        s7b_title,
        "Defines implementation governance structures to ensure predictable project delivery.",
        "Execution governance matrix showing workstreams, RACI owners, SLA windows, and risk controls.",
        s7b_script
    )
    sla_matrix = DECK_DEFAULTS.get("execution_sla_matrix", {})
    s7b_headers = sla_matrix.get("headers", ["Phase", "Workstream Focus", "Governance Role", "Target SLA", "Risk Control"])
    s7b_rows = sla_matrix.get("rows", [
        ["Phase 1 (0-30d)", "Capacity & Shift Rebalancing", "Operations Lead", "<14 Days", "Deploy dynamic shift buffer"],
        ["Phase 2 (30-90d)", "Playbook Standardization", "Field Director", "<45 Days", "Peer mentorship & unit audits"],
        ["Phase 3 (90+d)", "Continuous Verification", "Analytics Lead", "Continuous", "Automated SHA-256 evidence pipeline"]
    ])
    slides.append({
        "id": f"slide_{uuid.uuid4().hex[:8]}",
        "stable_slide_id": "slide_action_plan_execution",
        "order": start_order + len(slides),
        "layout": "table_detail",
        "category": "OPERATIONAL GOVERNANCE",
        "title": s7b_title,
        "subtitle": s7b_sub,
        "narrative": s7b_narrative,
        "bullets": [
            "[Recommendation] Designate unassigned lead roles with defined execution accountability.",
            "[Recommendation] Enforce quantitative SLA windows to prevent workstream slippage.",
            "[Recommendation] Institutionalize automated data auditing as recurring operating procedure."
        ],
        "metrics": None,
        "chart": None,
        "table": {
            "headers": s7b_headers,
            "rows": s7b_rows
        },
        "speaker_notes": s7b_notes,
        "narration_script": s7b_script,
        "reading_order": ["category", "title", "subtitle", "narrative", "table", "footer"],
        "timing_metadata": calculate_timing(s7b_script),
        "evidence_id": "EVID-REC-01",
        "evidence_item": ev7,
        "evidence_sources": [source_summary],
        "is_partial_year": is_partial_year
    })

    return slides
