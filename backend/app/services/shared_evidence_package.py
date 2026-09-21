"""Shared Versioned Evidence Package & Coverage Manifest Engine for PulseHR AI.

Guarantees 100% analytical parity between Executive Overview and Presentations by providing
an authoritative, reproducible evidence foundation with cryptographic snapshot hashing and
transparent coverage accounting (main deck, appendix, excluded with reason).
"""

import hashlib
import json
import logging
from typing import Any

from ..db.database import get_connection
from .executive_story import (
    detect_sheet_domain,
    get_or_generate_executive_story,
    profile_sheet_data,
    compute_relational_story,
)
from .industrial_analytics import run_ingestion_industrial_pipeline
from .visual_intelligence import build_workspace_visual_dashboard

from .evidence import (
    inventory_candidate_findings,
    generate_coverage_manifest,
    convert_visual_to_chart_spec,
)

logger = logging.getLogger(__name__)

__all__ = [
    "build_shared_evidence_package",
    "generate_coverage_manifest",
    "inventory_candidate_findings",
    "convert_visual_to_chart_spec",
]


def build_shared_evidence_package(conn, scope: dict[str, Any]) -> dict[str, Any]:
    """Assembles a shared, versioned evidence package containing:
    - Preflight scope and data integrity boundaries.
    - Ground-truth statistics across all scoped sheets.
    - Industrial People Analytics models (9-Box, Bradford, Burnout strain, Elasticity).
    - Longitudinal trends and forecasts.
    - Cross-sheet relational dynamics.
    - Candidate material findings prioritized by evidence strength.
    - Cryptographic SHA-256 snapshot seal.
    """
    from .presentation_service import (
        detect_sheet_date_range,
        preview_presentation_scope,
    )

    preflight = preview_presentation_scope(conn, scope)
    if not preflight["eligible"]:
        raise ValueError("Cannot assemble evidence package: No eligible datasets in presentation scope.")

    included_sheets = preflight["included_sheets"]
    primary_sheet_id = included_sheets[0]["id"]

    # 1. Pull sheet contexts and deterministic profiles
    sheet_contexts = {}
    for s in included_sheets:
        sid = s["id"]
        rows = conn.execute(
            "SELECT row_index, data_json FROM sheet_rows WHERE sheet_id=? ORDER BY row_index",
            (sid,)
        ).fetchall()
        recs = [json.loads(r["data_json"]) for r in rows]
        cols = json.loads(
            conn.execute("SELECT columns_json FROM sheets WHERE id=?", (sid,)).fetchone()["columns_json"] or "[]"
        )
        dom, _ = detect_sheet_domain(cols)
        p_info = profile_sheet_data(recs, cols, sheet_name=s["name"])
        d_range = detect_sheet_date_range(recs, cols)
        sheet_contexts[sid] = {
            "sheet": s,
            "records": recs,
            "columns": cols,
            "domain": dom,
            "profile": p_info,
            "ground_truth": p_info.get("ground_truth", {}),
            "date_range": d_range,
        }

    # 2. Pull industrial analytics models
    industrial_res = {}
    try:
        industrial_res = run_ingestion_industrial_pipeline(conn)
    except Exception as exc:
        logger.warning(f"Could not compute industrial analytics pipeline: {exc}")

    # 3. Pull visual dashboard visualizations
    workspace_visuals = []
    try:
        ws_dash = build_workspace_visual_dashboard(conn, sheet_id=None if len(included_sheets) > 1 else primary_sheet_id)
        workspace_visuals = ws_dash.get("visualizations", [])
    except Exception as exc:
        logger.warning(f"Could not build workspace visual dashboard: {exc}")

    # 4. Pull AI Executive Story narrative
    exec_story = None
    try:
        exec_story = get_or_generate_executive_story(
            sheet_id=None if len(included_sheets) > 1 else primary_sheet_id
        )
    except Exception as exc:
        logger.warning(f"Could not load executive story: {exc}")

    # 5. Pull cross-sheet relational dynamics
    rel_story = None
    if preflight["validated_relationships"]:
        try:
            rel_story = compute_relational_story(conn)
        except Exception as exc:
            logger.warning(f"Could not compute relational story: {exc}")

    # 6. Run domain HR attendance & period analytics if applicable
    hr_analytics = None
    try:
        from .hr_period_analytics import analyze_hr_attendance_sheet
        p_ctx = sheet_contexts[primary_sheet_id]
        comp_sheet_ctx = next((ctx for sid, ctx in sheet_contexts.items() if sid != primary_sheet_id and 'leave' in ctx['sheet']['name'].lower()), None)
        hr_analytics = analyze_hr_attendance_sheet(
            records=p_ctx["records"],
            columns=p_ctx["columns"],
            sheet_name=p_ctx["sheet"]["name"],
            comparison_sheet_records=comp_sheet_ctx["records"] if comp_sheet_ctx else None,
            comparison_sheet_name=comp_sheet_ctx["sheet"]["name"] if comp_sheet_ctx else None
        )
    except Exception as exc:
        logger.debug(f"HR period analytics evaluation skipped: {exc}")

    # 7. Compute stable cryptographic SHA-256 snapshot hash seal from actual cell contents and schema
    hasher = hashlib.sha256()
    hasher.update(f"scope_sheets:{len(included_sheets)}".encode("utf-8"))
    for s in included_sheets:
        sid = s["id"]
        ctx = sheet_contexts[sid]
        cols_str = ",".join(ctx.get("columns", []))
        hasher.update(f"sheet:{sid}:{s['name']}:{cols_str}:{s['row_count']}".encode("utf-8"))
        for r in ctx.get("records", []):
            hasher.update(json.dumps(r, sort_keys=True).encode("utf-8"))
        for k, v in sorted(ctx.get("ground_truth", {}).items()):
            if not k.startswith("semantic_"):
                hasher.update(f"{k}:{v}".encode("utf-8"))
    snapshot_hash = hasher.hexdigest()[:12]

    # 8. Synthesize Candidate Material Findings Inventory
    candidate_findings = inventory_candidate_findings(
        included_sheets=included_sheets,
        sheet_contexts=sheet_contexts,
        preflight=preflight,
        industrial_res=industrial_res,
        workspace_visuals=workspace_visuals,
        exec_story=exec_story,
        rel_story=rel_story,
        snapshot_hash=snapshot_hash,
        hr_analytics=hr_analytics,
    )

    return {
        "preflight": preflight,
        "included_sheets": included_sheets,
        "sheet_contexts": sheet_contexts,
        "hr_analytics": hr_analytics,
        "primary_sheet_id": primary_sheet_id,
        "industrial_models": industrial_res,
        "workspace_visuals": workspace_visuals,
        "executive_story": exec_story,
        "relational_story": rel_story,
        "candidate_findings": candidate_findings,
        "snapshot_hash": snapshot_hash,
        "total_records": sum(s["row_count"] for s in included_sheets),
        "source_names": [s["original_name"] for s in included_sheets],
        "reporting_period_summary": preflight["reporting_period_summary"],
        "is_partial_year": preflight["is_partial_year"],
        "disconnected_boundary_note": preflight["disconnected_boundary_note"],
    }
