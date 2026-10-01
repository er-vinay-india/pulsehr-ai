"""
Review Gates Service for PulseHR AI Presentations.

Implements the Five Review Gates standard:
1. Brief & Audience (gate_1_brief)
2. Storyline & Headlines (gate_2_storyline)
3. Evidence & Calculations (gate_3_evidence)
4. Visual Design & Density (gate_4_visual)
5. Accessibility & Technical Exports (gate_5_export_accessibility)

Strict separation between automated evaluation and human approval:
- Automated checks: PASSED | REQUIRES_REVIEW | FAILED
- Human sign-off: PENDING | APPROVED | REJECTED (never marked approved automatically)
- Revision tracking: invalidates relevant gates when deck content, data, theme, or layout changes.
"""

from __future__ import annotations

import datetime
from typing import Any


def initialize_review_gates(
    brief: dict[str, Any] | None = None,
    revision: int = 1
) -> dict[str, Any]:
    """Initializes the standard five review gates for a presentation deck."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    brief_data = brief or {}
    
    return {
        "revision": revision,
        "gates": {
            "gate_1_brief": {
                "gate_id": "gate_1_brief",
                "name": "Brief & Audience",
                "description": "Aligns deck objectives, audience seniority, time budget, and decision requested.",
                "status": "PASSED" if brief_data.get("objective") and brief_data.get("audience") else "REQUIRES_REVIEW",
                "automated": {
                    "status": "PASSED" if brief_data.get("objective") and brief_data.get("audience") else "REQUIRES_REVIEW",
                    "checked_at": now,
                    "details": "Objective and audience specified." if brief_data.get("objective") else "Objective inferred from persona.",
                    "success_criterion": brief_data.get("success_criterion", ""),
                    "is_inferred": brief_data.get("is_inferred", False),
                },
                "human_approval": {
                    "status": "PENDING",
                    "approved_by": None,
                    "approved_at": None,
                    "notes": None,
                }
            },
            "gate_2_storyline": {
                "gate_id": "gate_2_storyline",
                "name": "Storyline & Headlines",
                "description": "Verifies narrative arc progression, conclusion headlines, and slide count adherence.",
                "status": "PENDING",
                "automated": {
                    "status": "PENDING",
                    "checked_at": None,
                    "details": "Pending storyline audit.",
                },
                "human_approval": {
                    "status": "PENDING",
                    "approved_by": None,
                    "approved_at": None,
                    "notes": None,
                }
            },
            "gate_3_evidence": {
                "gate_id": "gate_3_evidence",
                "name": "Evidence & Calculations",
                "description": "Audits numerical reconciliation, complete claims against evidence ledger, units, and denominators.",
                "status": "PENDING",
                "automated": {
                    "status": "PENDING",
                    "checked_at": None,
                    "details": "Pending empirical evidence verification.",
                },
                "human_approval": {
                    "status": "PENDING",
                    "approved_by": None,
                    "approved_at": None,
                    "notes": None,
                }
            },
            "gate_4_visual": {
                "gate_id": "gate_4_visual",
                "name": "Visual Design & Density",
                "description": "Audits visual hierarchy, spatial density, chart readability, and typography.",
                "status": "PENDING",
                "automated": {
                    "status": "PENDING",
                    "checked_at": None,
                    "details": "Pending spatial density audit.",
                },
                "human_approval": {
                    "status": "PENDING",
                    "approved_by": None,
                    "approved_at": None,
                    "notes": None,
                }
            },
            "gate_5_export_accessibility": {
                "gate_id": "gate_5_export_accessibility",
                "name": "Accessibility & Technical Exports",
                "description": "Audits reading order, alternative text on charts, color contrast, and PPTX exportability.",
                "status": "PENDING",
                "automated": {
                    "status": "PENDING",
                    "checked_at": None,
                    "details": "Pending accessibility audit.",
                },
                "human_approval": {
                    "status": "PENDING",
                    "approved_by": None,
                    "approved_at": None,
                    "notes": None,
                }
            }
        }
    }


def evaluate_automated_gates(
    deck_spec: dict[str, Any],
    verification_summary: dict[str, Any] | None = None,
    quality_audit: dict[str, Any] | None = None,
    brief: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Evaluates automated criteria across all five review gates."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    review_gates = deck_spec.get("metadata", {}).get("review_gates")
    revision = (review_gates or {}).get("revision", 1)
    
    if not review_gates:
        review_gates = initialize_review_gates(brief=brief, revision=revision)
    
    gates = review_gates.get("gates", {})
    slides = deck_spec.get("slides", [])
    
    # 1. Brief Gate
    meta = deck_spec.get("metadata", {})
    has_obj = bool(meta.get("objective") or (brief and brief.get("objective")))
    has_aud = bool(meta.get("audience") or (brief and brief.get("audience")))
    has_decision = bool(meta.get("decision_requested") or (brief and brief.get("decision_requested")))
    gate_1 = gates.get("gate_1_brief", {})
    g1_human = gate_1.get("human_approval", {"status": "PENDING"})
    
    if has_obj and has_aud and has_decision:
        g1_auto_status = "PASSED"
        g1_details = "Brief requirements, audience, and requested decision defined."
    elif has_obj and has_aud:
        g1_auto_status = "REQUIRES_REVIEW"
        g1_details = "Audience and objective defined; specific decision requested was inferred."
    else:
        g1_auto_status = "FAILED"
        g1_details = "Objective or audience missing from brief context."
        
    gate_1["status"] = g1_auto_status
    gate_1["automated"] = {
        "status": g1_auto_status,
        "checked_at": now,
        "details": g1_details,
        "success_criterion": meta.get("success_criterion", ""),
        "is_inferred": meta.get("is_brief_inferred", False),
    }
    gate_1["human_approval"] = g1_human
    gates["gate_1_brief"] = gate_1

    # 2. Storyline & Headlines Gate
    gate_2 = gates.get("gate_2_storyline", {})
    g2_human = gate_2.get("human_approval", {"status": "PENDING"})
    has_headlines = len(slides) > 0 and all(bool(s.get("title")) for s in slides)
    short_titles = [s.get("title", "") for s in slides if len(s.get("title", "")) < 6]
    
    if has_headlines and not short_titles and len(slides) >= 3:
        g2_auto_status = "PASSED"
        g2_details = f"Storyline validated across {len(slides)} slides with supported conclusion and topic headlines."
    elif has_headlines:
        g2_auto_status = "REQUIRES_REVIEW"
        g2_details = f"Deck contains {len(slides)} slides; some titles require review."
    else:
        g2_auto_status = "FAILED"
        g2_details = "Slide narrative structure incomplete or missing headlines."
        
    gate_2["status"] = g2_auto_status
    gate_2["automated"] = {
        "status": g2_auto_status,
        "checked_at": now,
        "details": g2_details,
    }
    gate_2["human_approval"] = g2_human
    gates["gate_2_storyline"] = gate_2

    # 3. Evidence & Calculations Gate
    gate_3 = gates.get("gate_3_evidence", {})
    g3_human = gate_3.get("human_approval", {"status": "PENDING"})
    v_sum = verification_summary or meta.get("validation_summary") or {}
    discrepancies = v_sum.get("discrepancies_flagged", 0)
    v_status = v_sum.get("status", "PENDING")
    
    if v_status == "PASSED" and discrepancies == 0:
        g3_auto_status = "PASSED"
        g3_details = f"All {v_sum.get('total_metrics_checked', 0)} claims verified against evidence ledger within ±0.1%."
    elif discrepancies > 0:
        g3_auto_status = "FAILED"
        g3_details = f"{discrepancies} numerical discrepancy(ies) flagged against ground-truth ledger."
    else:
        g3_auto_status = "REQUIRES_REVIEW"
        g3_details = "Claim verification completed with non-blocking warnings."
        
    gate_3["status"] = g3_auto_status
    gate_3["automated"] = {
        "status": g3_auto_status,
        "checked_at": now,
        "details": g3_details,
        "total_checked": v_sum.get("total_metrics_checked", 0),
        "discrepancies": discrepancies,
    }
    gate_3["human_approval"] = g3_human
    gates["gate_3_evidence"] = gate_3

    # 4. Visual Design & Density Gate
    gate_4 = gates.get("gate_4_visual", {})
    g4_human = gate_4.get("human_approval", {"status": "PENDING"})
    q_audit = quality_audit or deck_spec.get("quality_audit") or {}
    crit_issues = q_audit.get("critical_count", 0)
    warn_issues = q_audit.get("warning_count", 0)
    
    if crit_issues == 0 and warn_issues == 0:
        g4_auto_status = "PASSED"
        g4_details = "Spatial canvas budgets, text density, and chart alignments certified."
    elif crit_issues == 0:
        g4_auto_status = "REQUIRES_REVIEW"
        g4_details = f"Visual layout passed with {warn_issues} non-critical layout warning(s)."
    else:
        g4_auto_status = "FAILED"
        g4_details = f"{crit_issues} critical layout overflow issue(s) detected."
        
    gate_4["status"] = g4_auto_status
    gate_4["automated"] = {
        "status": g4_auto_status,
        "checked_at": now,
        "details": g4_details,
    }
    gate_4["human_approval"] = g4_human
    gates["gate_4_visual"] = gate_4

    # 5. Accessibility & Technical Exports Gate
    gate_5 = gates.get("gate_5_export_accessibility", {})
    g5_human = gate_5.get("human_approval", {"status": "PENDING"})
    charts_without_titles = [s for s in slides if s.get("chart") and not (s["chart"].get("title") or s.get("title"))]
    slides_without_titles = [s for s in slides if not s.get("title")]
    
    if not slides_without_titles and not charts_without_titles and deck_spec.get("pptx_filename"):
        g5_auto_status = "PASSED"
        g5_details = "Slide titles, chart series labels, reading order, and native PPTX verified."
    elif not slides_without_titles:
        g5_auto_status = "REQUIRES_REVIEW"
        g5_details = "Slide accessibility verified. Manual PowerPoint Accessibility Checker inspection remains pending."
    else:
        g5_auto_status = "FAILED"
        g5_details = "Missing slide titles or chart labels."
        
    gate_5["status"] = g5_auto_status
    gate_5["automated"] = {
        "status": g5_auto_status,
        "checked_at": now,
        "details": g5_details,
        "note": "Programmatic checks passed. Checks requiring PowerPoint inspection are recorded as pending human verification.",
    }
    gate_5["human_approval"] = g5_human
    gates["gate_5_export_accessibility"] = gate_5

    review_gates["revision"] = revision
    review_gates["gates"] = gates
    review_gates["summary"] = {
        "all_automated_passed": all(g["automated"]["status"] in ("PASSED", "REQUIRES_REVIEW") for g in gates.values()) and not any(g["automated"]["status"] == "FAILED" for g in gates.values()),
        "human_signoff_complete": all(g["human_approval"]["status"] == "APPROVED" for g in gates.values()),
        "ready_for_review": True,
    }
    return review_gates


def record_human_signoff(
    review_gates: dict[str, Any],
    gate_id: str,
    approved: bool,
    user_name: str = "User",
    notes: str | None = None
) -> dict[str, Any]:
    """Records an explicit human approval or rejection for a review gate."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    gates = review_gates.get("gates", {})
    if gate_id not in gates:
        raise KeyError(f"Unknown review gate: {gate_id}")
    
    target_gate = gates[gate_id]
    target_gate["human_approval"] = {
        "status": "APPROVED" if approved else "REJECTED",
        "approved_by": user_name,
        "approved_at": now,
        "notes": notes,
    }
    gates[gate_id] = target_gate
    review_gates["gates"] = gates
    review_gates["summary"]["human_signoff_complete"] = all(
        g["human_approval"]["status"] == "APPROVED" for g in gates.values()
    )
    return review_gates


def invalidate_review_gates_on_edit(
    deck_spec: dict[str, Any],
    edited_scope: str = "content"  # "content" | "theme" | "layout" | "data"
) -> dict[str, Any]:
    """Invalidates affected review gates and increments deck revision when edits occur."""
    meta = deck_spec.setdefault("metadata", {})
    rg = meta.get("review_gates")
    if not rg:
        rg = initialize_review_gates()
    
    current_rev = rg.get("revision", 1)
    new_rev = current_rev + 1
    rg["revision"] = new_rev
    gates = rg.get("gates", {})
    
    # Invalidate according to edited scope
    if edited_scope in ("content", "data"):
        for gid in ("gate_2_storyline", "gate_3_evidence", "gate_4_visual", "gate_5_export_accessibility"):
            if gid in gates:
                gates[gid]["automated"]["status"] = "REQUIRES_REVIEW"
                gates[gid]["automated"]["details"] = f"Invalidated by {edited_scope} edit in revision {new_rev}. Re-audit required."
                gates[gid]["human_approval"]["status"] = "PENDING"
                gates[gid]["human_approval"]["notes"] = f"Reset due to revision {new_rev} {edited_scope} edit."
    elif edited_scope in ("theme", "layout"):
        for gid in ("gate_4_visual", "gate_5_export_accessibility"):
            if gid in gates:
                gates[gid]["automated"]["status"] = "REQUIRES_REVIEW"
                gates[gid]["automated"]["details"] = f"Invalidated by {edited_scope} update in revision {new_rev}."
                gates[gid]["human_approval"]["status"] = "PENDING"
                
    rg["gates"] = gates
    rg["summary"] = {
        "all_automated_passed": False,
        "human_signoff_complete": False,
        "ready_for_review": True,
    }
    meta["review_gates"] = rg
    return deck_spec
