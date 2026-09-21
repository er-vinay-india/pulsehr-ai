import hashlib
import json
import logging
import pandas as pd
from typing import Any

from ..executive_story import detect_sheet_domain, profile_sheet_data
from ..shared_evidence_package import build_shared_evidence_package
from ..visual_intelligence import build_workspace_visual_dashboard

logger = logging.getLogger(__name__)


def detect_sheet_date_range(records: list[dict], columns: list[str]) -> dict[str, Any]:
    """Scans for chronological columns and detects date boundaries and partial-year disclosures.
    Spans < 330 days (~11 months) are flagged with is_partial_year=True."""
    if not records or not columns:
        return {
            "has_date": False,
            "period_label": "No chronological date columns detected",
            "is_partial_year": False,
            "date_col": None,
            "min_date": None,
            "max_date": None,
            "min_label": None,
            "max_label": None,
            "days_span": 0,
            "months_span": 0.0
        }

    df = pd.DataFrame(records)
    candidate_cols = []
    for c in columns:
        c_clean = str(c).lower().replace("_", "").replace(" ", "")
        if any(k in c_clean for k in ("date", "period", "week", "month", "year", "time", "timestamp", "dt")):
            candidate_cols.append(c)

    cols_to_check = candidate_cols if candidate_cols else columns

    for col in cols_to_check:
        if col not in df.columns:
            continue
        s = df[col].dropna()
        if len(s) < 2:
            continue
        try:
            converted = pd.to_datetime(s, errors="coerce", format="mixed")
            valid_dates = converted.dropna()
            if len(valid_dates) >= max(2, int(len(s) * 0.35)):
                min_dt = valid_dates.min()
                max_dt = valid_dates.max()
                days_span = max(0, (max_dt - min_dt).days)
                months_span = round(days_span / 30.4375, 1)

                is_partial_year = days_span < 330  # Under 11 months is a partial year

                min_str = min_dt.strftime("%Y-%m-%d")
                max_str = max_dt.strftime("%Y-%m-%d")
                min_label = min_dt.strftime("%b %Y")
                max_label = max_dt.strftime("%b %Y")

                if is_partial_year:
                    m_count = max(1, int(round(months_span)))
                    period_label = f"{min_label} – {max_label} ({m_count} Months · Partial Year)"
                elif days_span > 730:
                    years_span = round(days_span / 365.25, 1)
                    period_label = f"{min_label} – {max_label} ({years_span} Years)"
                else:
                    period_label = f"{min_label} – {max_label} (Annual Cycle)"

                return {
                    "has_date": True,
                    "date_col": col,
                    "min_date": min_str,
                    "max_date": max_str,
                    "min_label": min_label,
                    "max_label": max_label,
                    "period_label": period_label,
                    "is_partial_year": is_partial_year,
                    "days_span": days_span,
                    "months_span": months_span
                }
        except Exception:
            continue

    return {
        "has_date": False,
        "period_label": f"{len(records):,} Recorded Observations",
        "is_partial_year": False,
        "date_col": None,
        "min_date": None,
        "max_date": None,
        "min_label": None,
        "max_label": None,
        "days_span": 0,
        "months_span": 0.0
    }


def get_connected_sheet_groups(conn) -> list[dict[str, Any]]:
    """Identifies connected clusters of sheets based on validated key relationships."""
    sheet_rows = conn.execute(
        "SELECT s.id, s.name, s.row_count, s.columns_json, d.original_name "
        "FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id ORDER BY s.id ASC"
    ).fetchall()
    sheets_by_id = {r["id"]: dict(r) for r in sheet_rows}

    rels = conn.execute(
        "SELECT * FROM sheet_relationships WHERE status='linked' ORDER BY matching_pairs DESC"
    ).fetchall()

    adj: dict[int, set[int]] = {sid: set() for sid in sheets_by_id}
    rel_map = []
    for r in rels:
        ls, rs = r["left_sheet"], r["right_sheet"]
        if ls in adj and rs in adj:
            adj[ls].add(rs)
            adj[rs].add(ls)
            rel_map.append(dict(r))

    visited = set()
    groups = []
    group_idx = 1

    for sid in sorted(sheets_by_id.keys()):
        if sid not in visited:
            component = []
            queue = [sid]
            visited.add(sid)
            while queue:
                curr = queue.pop(0)
                component.append(curr)
                for neighbor in sorted(adj[curr]):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)

            if len(component) >= 2:
                comp_sheets = [sheets_by_id[s] for s in component]
                comp_sheet_ids = [s["id"] for s in comp_sheets]
                comp_rels = [
                    r for r in rel_map
                    if r["left_sheet"] in comp_sheet_ids and r["right_sheet"] in comp_sheet_ids
                ]
                group_name = f"{comp_sheets[0]['name']} & {comp_sheets[1]['name']} Network"
                if len(comp_sheets) > 2:
                    group_name = f"{comp_sheets[0]['name']} + {len(comp_sheets)-1} Linked Sheets"

                groups.append({
                    "group_id": f"group_{group_idx}",
                    "group_name": group_name,
                    "sheet_ids": comp_sheet_ids,
                    "sheet_names": [s["name"] for s in comp_sheets],
                    "sheets": comp_sheets,
                    "relationships": comp_rels,
                    "total_rows": sum(s["row_count"] for s in comp_sheets)
                })
                group_idx += 1

    return groups


def get_validated_relationships_for_sheets(conn, sheet_ids: list[int]) -> list[dict[str, Any]]:
    """Fetches validated relationships where both endpoints belong to the target sheet IDs."""
    if not sheet_ids or len(sheet_ids) < 2:
        return []
    placeholders = ",".join("?" * len(sheet_ids))
    sql = f"""
        SELECT r.*, 
               l.name as left_sheet_name, ld.original_name as left_file,
               rg.name as right_sheet_name, rd.original_name as right_file
        FROM sheet_relationships r
        JOIN sheets l ON l.id = r.left_sheet
        JOIN dataset_uploads ld ON ld.id = l.dataset_id
        JOIN sheets rg ON rg.id = r.right_sheet
        JOIN dataset_uploads rd ON rd.id = rg.dataset_id
        WHERE r.status = 'linked'
          AND r.left_sheet IN ({placeholders})
          AND r.right_sheet IN ({placeholders})
        ORDER BY r.matching_pairs DESC
    """
    params = list(sheet_ids) + list(sheet_ids)
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def preview_presentation_scope(conn, scope: dict[str, Any]) -> dict[str, Any]:
    """Generates a preflight summary showing sources, reporting periods, partial-year disclosure,
    exclusions, and relationship coverage before presentation generation."""
    sheet_query = (
        "SELECT s.id, s.name, s.columns_json, s.row_count, s.profile_json, d.id as dataset_id, d.original_name, d.filename "
        "FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id ORDER BY s.id ASC"
    )
    all_sheets = [dict(r) for r in conn.execute(sheet_query).fetchall()]
    if not all_sheets:
        return {
            "eligible": False,
            "message": "No sheets uploaded in workspace.",
            "included_sheets": [],
            "excluded_sheets": [],
            "validated_relationships": [],
            "relationship_coverage_pct": 0,
            "is_partial_year": False,
            "reporting_period_summary": "No data",
            "disconnected_boundary_note": "No active data sources available."
        }

    scope_type = scope.get("scope_type") or "workspace"
    target_sheet_id = scope.get("sheet_id")
    target_sheet_ids = scope.get("sheet_ids") or []
    target_group_id = scope.get("group_id")

    connected_groups = get_connected_sheet_groups(conn)

    included_sheet_ids: set[int] = set()
    exclusion_reasons: dict[int, str] = {}

    if scope_type == "workspace":
        for s in all_sheets:
            included_sheet_ids.add(s["id"])
    elif scope_type == "connected_group":
        selected_group = None
        if target_group_id:
            selected_group = next((g for g in connected_groups if g["group_id"] == target_group_id), None)
        if not selected_group and connected_groups:
            selected_group = connected_groups[0]

        if selected_group:
            for sid in selected_group["sheet_ids"]:
                included_sheet_ids.add(sid)
            for s in all_sheets:
                if s["id"] not in included_sheet_ids:
                    exclusion_reasons[s["id"]] = f"Excluded: not part of '{selected_group['group_name']}'"
        else:
            for s in all_sheets:
                included_sheet_ids.add(s["id"])
    elif scope_type == "custom_sheets":
        sids = set(int(x) for x in target_sheet_ids if str(x).isdigit())
        if not sids and target_sheet_id:
            sids.add(int(target_sheet_id))
        if not sids and all_sheets:
            sids.add(all_sheets[0]["id"])
        included_sheet_ids = sids
        for s in all_sheets:
            if s["id"] not in included_sheet_ids:
                exclusion_reasons[s["id"]] = "Excluded: unselected in custom selection"
    elif scope_type in ("single_sheet", "sheet"):
        sid = int(target_sheet_id) if target_sheet_id else all_sheets[0]["id"]
        included_sheet_ids.add(sid)
        for s in all_sheets:
            if s["id"] != sid:
                exclusion_reasons[s["id"]] = "Excluded: single-sheet generation scope selected"
    elif scope_type == "dataset":
        target_dataset_id = scope.get("dataset_id")
        for s in all_sheets:
            if target_dataset_id and s["dataset_id"] == int(target_dataset_id):
                included_sheet_ids.add(s["id"])
            elif not target_dataset_id:
                included_sheet_ids.add(s["id"])
            else:
                exclusion_reasons[s["id"]] = f"Excluded: not part of dataset {target_dataset_id}"

    included_sheets_info = []
    all_is_partial = []
    period_labels = []

    for s in all_sheets:
        if s["id"] in included_sheet_ids:
            rows = conn.execute(
                "SELECT data_json FROM sheet_rows WHERE sheet_id=? ORDER BY row_index LIMIT 400",
                (s["id"],)
            ).fetchall()
            recs = [json.loads(r["data_json"]) for r in rows]
            cols = json.loads(s["columns_json"] or "[]")
            dom, _ = detect_sheet_domain(cols)
            date_info = detect_sheet_date_range(recs, cols)
            if date_info["has_date"]:
                all_is_partial.append(date_info["is_partial_year"])
                period_labels.append(f"{s['name']}: {date_info['period_label']}")

            included_sheets_info.append({
                "id": s["id"],
                "name": s["name"],
                "original_name": s["original_name"],
                "row_count": s["row_count"],
                "column_count": len(cols),
                "domain": dom,
                "date_info": date_info,
                "period_label": date_info["period_label"],
                "is_partial_year": date_info["is_partial_year"]
            })

    validated_rels = get_validated_relationships_for_sheets(conn, list(included_sheet_ids))
    linked_sheet_ids = set()
    for r in validated_rels:
        linked_sheet_ids.add(r["left_sheet"])
        linked_sheet_ids.add(r["right_sheet"])

    total_inc = len(included_sheets_info)
    coverage_pct = round((len(linked_sheet_ids) / total_inc) * 100, 1) if total_inc > 1 else 100.0

    excluded_sheets_info = [
        {
            "id": s["id"],
            "name": s["name"],
            "original_name": s["original_name"],
            "row_count": s["row_count"],
            "reason": exclusion_reasons.get(s["id"], "Excluded by scope selection")
        }
        for s in all_sheets if s["id"] not in included_sheet_ids
    ]

    has_partial_year = any(all_is_partial)

    if total_inc > 1 and len(linked_sheet_ids) < total_inc:
        disconnected_note = (
            "Disconnected datasets remain isolated and are evaluated independently without synthetic joins."
        )
    elif total_inc > 1:
        disconnected_note = "All selected datasets are interconnected by verified key relationships."
    else:
        disconnected_note = "Single dataset evaluated on verified empirical records."

    period_summary = (
        " · ".join(period_labels)
        if period_labels
        else f"{sum(s['row_count'] for s in included_sheets_info):,} Recorded Observations"
    )

    return {
        "eligible": total_inc > 0,
        "scope_type": scope_type,
        "total_included_sheets": total_inc,
        "total_included_rows": sum(s["row_count"] for s in included_sheets_info),
        "included_sheets": included_sheets_info,
        "excluded_sheets": excluded_sheets_info,
        "validated_relationships": validated_rels,
        "relationship_coverage_pct": coverage_pct,
        "is_partial_year": has_partial_year,
        "disconnected_boundary_note": disconnected_note,
        "reporting_period_summary": period_summary,
        "connected_groups": connected_groups
    }


def capture_dataset_context(conn, sheet_id: int | None = None, dataset_id: int | None = None) -> dict[str, Any]:
    """Captures a consistent data snapshot for presentation generation."""
    sheet_query = (
        "SELECT s.id, s.name, s.columns_json, s.row_count, s.profile_json, d.id as dataset_id, d.original_name, d.filename "
        "FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id ORDER BY s.id ASC"
    )
    all_sheets = [dict(r) for r in conn.execute(sheet_query).fetchall()]
    if not all_sheets:
        raise ValueError("No uploaded sheets found. Please upload a dataset first.")

    target_sheet = None
    if sheet_id:
        target_sheet = next((s for s in all_sheets if s["id"] == sheet_id), None)
    elif dataset_id:
        target_sheet = next((s for s in all_sheets if s["dataset_id"] == dataset_id), None)

    if not target_sheet:
        target_sheet = all_sheets[0]

    sid = target_sheet["id"]
    rows = conn.execute("SELECT row_index, data_json FROM sheet_rows WHERE sheet_id=? ORDER BY row_index", (sid,)).fetchall()
    records = [json.loads(r["data_json"]) for r in rows]
    cols = json.loads(target_sheet["columns_json"] or "[]")

    domain, domain_desc = detect_sheet_domain(cols)
    profile_info = profile_sheet_data(records, cols, sheet_name=target_sheet["name"])
    ground_truth = profile_info.get("ground_truth", {})

    # Compute snapshot hash
    sample_text = f"{target_sheet['original_name']}:{len(records)}:{','.join(cols)}"
    snapshot_hash = hashlib.sha256(sample_text.encode("utf-8")).hexdigest()[:12]

    # Visual analytics candidates
    visual_dashboard = build_workspace_visual_dashboard(conn, sheet_id=sid)
    visuals = visual_dashboard.get("visualizations", [])

    return {
        "target_sheet": target_sheet,
        "all_sheets": all_sheets,
        "records": records,
        "columns": cols,
        "domain": domain,
        "domain_desc": domain_desc,
        "ground_truth": ground_truth,
        "snapshot_hash": snapshot_hash,
        "visual_dashboard": visual_dashboard,
        "visuals": visuals
    }


def collect_workspace_evidence(conn, scope: dict[str, Any]) -> dict[str, Any]:
    """Freezes a reproducible evidence snapshot, collects ground-truth profiles,
    and builds an audit ledger with stable evidence IDs (EVID-xxx) using the shared package."""
    if scope.get("deck_style") == "decision_brief":
        from ..decision_intelligence import build_decision_brief
        preflight = preview_presentation_scope(conn, scope)
        if not preflight["eligible"]:
            raise ValueError("No eligible sources in the selected scope.")
        ids = [s["id"] for s in preflight["included_sheets"]]
        brief = build_decision_brief(conn, sheet_ids=ids)
        return {"decision_brief": brief, "primary_ctx": {}, "preflight": preflight, "evidence_ledger": []}
    shared_pkg = build_shared_evidence_package(conn, scope)
    preflight = shared_pkg["preflight"]
    included_sheets = shared_pkg["included_sheets"]
    primary_sheet_id = shared_pkg["primary_sheet_id"]
    primary_ctx = capture_dataset_context(conn, sheet_id=primary_sheet_id)

    tot_rows = shared_pkg["total_records"]
    source_names = shared_pkg["source_names"]
    period_summary = shared_pkg["reporting_period_summary"]
    is_partial = shared_pkg["is_partial_year"]
    snapshot_hash = shared_pkg["snapshot_hash"]

    # Build frozen evidence ledger from candidate findings
    ledger = []
    for cand in shared_pkg["candidate_findings"]:
        ev_id = cand.get("evidence_id")
        if not ev_id:
            continue
        ledger.append({
            "evidence_id": ev_id,
            "slide_index": cand.get("slide_index", 1),
            "title": cand["title"],
            "finding_type": cand.get("evidence_strength", "measured_fact"),
            "source_sheets": cand.get("source_sheets", source_names),
            "row_count": cand.get("row_count", tot_rows),
            "date_range": cand.get("date_range", period_summary),
            "is_partial_year": cand.get("is_partial_year", is_partial),
            "metric_name": cand.get("metric_name", "Primary Metric"),
            "metric_value": cand.get("metric_value", ""),
            "numeric_value": cand.get("numeric_value"),
            "calculation_methodology": cand.get("calculation_methodology", ""),
            "what_it_establishes": cand.get("what_it_establishes", ""),
            "what_it_does_not_establish": cand.get("what_it_does_not_establish", ""),
            "likely_questions": cand.get("likely_questions", [])
        })

    return {
        "preflight": preflight,
        "primary_ctx": primary_ctx,
        "sheet_contexts": shared_pkg["sheet_contexts"],
        "included_sheets": included_sheets,
        "exec_story": shared_pkg["executive_story"],
        "rel_story": shared_pkg["relational_story"],
        "snapshot_hash": snapshot_hash,
        "evidence_ledger": ledger,
        "candidate_findings": shared_pkg["candidate_findings"],
        "shared_package": shared_pkg,
        "workspace_visuals": shared_pkg.get("workspace_visuals", []),
        "industrial_models": shared_pkg.get("industrial_models", {}),
        "total_records": tot_rows,
        "reporting_period_summary": period_summary,
        "is_partial_year": is_partial,
        "disconnected_boundary_note": shared_pkg["disconnected_boundary_note"]
    }
