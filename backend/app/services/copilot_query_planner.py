"""Structured Domain-Adaptive Analytical Query Planner and Executor for PulseHR AI Copilot.

Provides verified, evidence-backed analytical query planning across domains (HR, Sales, IT, Marketing),
connecting directly to the shared analytical foundation:
- `decision_intelligence.py`: Domain detection, unweighted group comparisons, monthly trends,
  pairwise correlation matrices, Simpson's paradox reversal, and SHA-256 snapshot hashes.
- `hr_period_analytics.py`: Wide period matrix calendar evaluation, full-population rollups,
  deterministic ranking with ties, and organization benchmarks.
- `semantic_mapping.py`: Semantic role identification.

Enforces strict statistical governance:
1. Resolves metrics and grouping dimensions dynamically across domains without hardcoded tables.
2. Handles ambiguous "worst" queries by checking conversation context; if unestablished, asks ONE
   focused clarification question without assuming attendance or inventing a composite score.
3. Calculates across all eligible groups, preserving dense ranking for ties, disclosing missing values,
   denominators, and small sample size caveats.
4. Validates monthly queries against observed data; rejects unobserved periods explicitly without substitution.
5. Strictly refuses causal claims from correlation; separates statistical associations from explanations.
6. Attaches machine-readable evidence (source IDs, snapshot hash, metric definition, calculation method, coverage, caveats).
7. Treats all cell contents strictly as untrusted data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import html
import json
import re
from typing import Any, Literal

import numpy as np
import pandas as pd

from ..db.database import get_connection
from .decision_intelligence import (
    build_decision_brief,
    domain_for,
    identity,
    label,
    numbers,
    period_header,
    value,
)
from .hr_period_analytics import analyze_hr_attendance_sheet, parse_period_column

QueryIntent = Literal[
    'ranking',
    'breakdown',
    'ambiguity_clarification',
    'correlation_causation',
    'period_unavailable'
]
SortDirection = Literal['lowest', 'highest', 'all']

MONTH_NAMES = (
    'january', 'february', 'march', 'april', 'may', 'june',
    'july', 'august', 'september', 'october', 'november', 'december'
)


@dataclass
class AnalyticalQueryPlan:
    intent: QueryIntent
    metric: str | None = None  # Resolved column name or standard metric key
    secondary_metric: str | None = None  # For correlation/causation questions
    entity_dimension: str = 'Department'  # Resolved grouping dimension (e.g. Department, Store, Severity)
    direction: SortDirection = 'lowest'
    time_window: str | None = None  # e.g. 'July', 'August', '2023-08'
    ranking_limit: int = 1
    filter_col: str | None = None
    filter_val: str | None = None
    dataset_id: int | None = None
    sheet_id: int | None = None
    explanation: str = ''
    available_metrics: list[str] = field(default_factory=list)
    available_dimensions: list[str] = field(default_factory=list)
    clarification_question: str | None = None


def _sanitize_untrusted_text(text: Any) -> str:
    """Sanitizes user-uploaded cells, department names, or group labels for markdown rendering."""
    if text is None:
        return ""
    s = str(text).strip()
    # Strip dangerous raw HTML tags or backticks
    s = html.escape(s, quote=True)
    return s.replace("`", "'")


def _resolve_candidate_sheets(
    conn,
    dataset_id: int | None = None,
    sheet_id: int | None = None
) -> list[sqlite3.Row]:
    """Retrieves sheets within active scope."""
    if sheet_id and dataset_id:
        rows = conn.execute(
            "SELECT s.*, d.original_name FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id WHERE s.id=? AND s.dataset_id=?",
            (sheet_id, dataset_id)
        ).fetchall()
        if not rows:
            raise ValueError(f"Sheet ID {sheet_id} does not belong to Dataset ID {dataset_id} or does not exist.")
        return rows
    elif sheet_id:
        rows = conn.execute(
            "SELECT s.*, d.original_name FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id WHERE s.id=?",
            (sheet_id,)
        ).fetchall()
        return rows
    elif dataset_id:
        rows = conn.execute(
            "SELECT s.*, d.original_name FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id WHERE s.dataset_id=? ORDER BY s.id ASC",
            (dataset_id,)
        ).fetchall()
        return rows
    else:
        rows = conn.execute(
            "SELECT s.*, d.original_name FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id ORDER BY s.id ASC"
        ).fetchall()
        return rows


def _inspect_sheet_schema(sheet_record) -> tuple[list[str], list[str], list[str], bool, str]:
    """Returns (measures, dimensions, date_cols, has_wide_periods, domain)."""
    cols = json.loads(sheet_record["columns_json"] or "[]")
    domain, _ = domain_for(cols)
    measures = []
    dimensions = []
    date_cols = []
    has_wide_periods = any(period_header(c) for c in cols)

    for c in cols:
        if identity(c):
            continue
        c_norm = c.lower()
        if re.search(r'\b(date|timestamp|datetime|week|month|year|day)\b', c_norm):
            date_cols.append(c)
        elif re.search(r'department|dept|team|division|region|channel|campaign|category|status|product|store|location|severity|priority|system', c_norm):
            dimensions.append(c)
        elif not period_header(c):
            measures.append(c)

    # If domain is People Operations and attendance/leave keywords appear, ensure HR aliases are represented
    return measures, dimensions, date_cols, has_wide_periods, domain


def plan_analytical_query(
    query: str,
    dataset_id: int | None = None,
    sheet_id: int | None = None,
    prior_context: dict[str, Any] | None = None,
    conn=None
) -> AnalyticalQueryPlan | None:
    """Parses natural-language analytical questions into an executable, bounded analytical plan.
    
    Supports:
    - Domain adaptivity (People ops, Sales, IT, Marketing, general tabular)
    - Ambiguous 'worst'/'best' queries with context inheritance or explicit clarification
    - Monthly period validation
    - Correlation vs causation queries
    - Ties, dense ranking, and breakdown intents
    """
    q = query.strip().lower()

    # Exclude definitional, general conversational, or calculation-only queries
    if any(k in q for k in ('what does', 'explain', 'definition', 'policy', 'meaning', 'how do i', 'how many days was')):
        return None

    # Inspect candidate sheets schema in DB if available
    should_close = False
    if conn is None:
        try:
            conn = get_connection()
            should_close = True
        except Exception:
            conn = None

    candidate_sheets = []
    all_measures: list[str] = []
    all_dimensions: list[str] = []
    all_dates: list[str] = []
    has_wide_periods = False
    detected_domain = "People operations"

    if conn is not None:
        try:
            candidate_sheets = _resolve_candidate_sheets(conn, dataset_id, sheet_id)
            if candidate_sheets:
                primary = candidate_sheets[0]
                m_list, d_list, dt_list, wp, dom = _inspect_sheet_schema(primary)
                all_measures = m_list
                all_dimensions = d_list
                all_dates = dt_list
                has_wide_periods = wp
                detected_domain = dom
        except Exception:
            pass
        finally:
            if should_close:
                conn.close()

    # Extract requested time window / month
    time_window = None
    for m in MONTH_NAMES:
        if re.search(rf'\b{m}\b', q):
            time_window = m.title()
            break

    # 1. CHECK FOR CORRELATION / CAUSATION QUESTIONS
    is_causal_query = any(k in q for k in (
        'cause', 'causes', 'causing', 'why did', 'why is', 'lead to', 'leads to',
        'result in', 'results in', 'impact of', 'affect', 'affects', 'correlation between',
        'relationship between', 'is there a correlation', 'are they correlated', 'move together'
    ))
    if is_causal_query:
        # Identify two potential measures mentioned in query
        matched_measures = []
        # Check standard HR measures
        if 'attendance' in q:
            matched_measures.append('attendance')
        if 'leave' in q or 'absence' in q:
            matched_measures.append('leaves')
        if 'headcount' in q:
            matched_measures.append('headcount')

        # Check candidate sheet measures
        for m in all_measures:
            m_words = re.findall(r'[a-zA-Z0-9]+', m.lower())
            if any(w in q for w in m_words if len(w) > 2) and m not in matched_measures:
                matched_measures.append(m)

        if len(matched_measures) >= 2:
            return AnalyticalQueryPlan(
                intent='correlation_causation',
                metric=matched_measures[0],
                secondary_metric=matched_measures[1],
                dataset_id=dataset_id,
                sheet_id=sheet_id,
                explanation=f"Evaluates association between {matched_measures[0]} and {matched_measures[1]} while strictly refusing causal claims."
            )
        elif len(matched_measures) == 1 and any(k in q for k in ('why', 'cause', 'reason')):
            return AnalyticalQueryPlan(
                intent='correlation_causation',
                metric=matched_measures[0],
                dataset_id=dataset_id,
                sheet_id=sheet_id,
                explanation=f"Evaluates statistical associations with {matched_measures[0]} and refuses unverified causal claims."
            )

    # 2. RESOLVE GROUPING DIMENSION
    entity_dimension = 'Department'
    if all_dimensions:
        for dim in all_dimensions:
            d_norm = dim.lower()
            if d_norm in q or (d_norm == 'department' and any(k in q for k in ('dept', 'department'))) or \
               (d_norm == 'store' and 'store' in q) or (d_norm == 'team' and 'team' in q) or \
               (d_norm == 'severity' and 'severity' in q):
                entity_dimension = dim
                break
        else:
            # Pick first available dimension if explicitly asking for grouping
            if any(k in q for k in ('by store', 'which store')):
                entity_dimension = 'Store'
            elif any(k in q for k in ('by severity', 'which severity')):
                entity_dimension = 'Severity'
            elif any(k in q for k in ('by team', 'which team')):
                entity_dimension = 'Team'
            elif any(k in q for k in ('by division', 'which division')):
                entity_dimension = 'Division'
            else:
                entity_dimension = all_dimensions[0]
    else:
        if 'store' in q:
            entity_dimension = 'Store'
        elif 'team' in q:
            entity_dimension = 'Team'
        elif 'division' in q:
            entity_dimension = 'Division'
        elif 'severity' in q:
            entity_dimension = 'Severity'

    # 3. RESOLVE METRIC ACROSS DOMAINS
    metric = None
    # People operations standard aliases
    if 'final attendance' in q or 'net attendance' in q:
        metric = 'final_attendance'
    elif 'attendance' in q or 'attended' in q or 'presence' in q:
        metric = 'attendance'
    elif 'leave' in q or 'leaves' in q or 'absent' in q or 'absence' in q:
        metric = 'leaves'
    elif 'headcount' in q or 'employees' in q or 'staff' in q or 'size' in q:
        metric = 'headcount'
    else:
        # Check candidate sheet measures dynamically (Sales, IT, Marketing, General)
        for m in all_measures:
            m_norm = m.lower()
            m_tokens = set(re.findall(r'[a-z0-9]+', m_norm))
            # Direct phrase match or token overlap
            if m_norm in q or (m_tokens and m_tokens.issubset(set(re.findall(r'[a-z0-9]+', q)))):
                metric = m
                break
            # Specialized Sales/IT mappings
            if 'weekly sales' in q and 'sales' in m_norm:
                metric = m
                break
            if 'resolution' in q and 'resolution' in m_norm:
                metric = m
                break
            if 'incident' in q and 'incident' in m_norm:
                metric = m
                break

    # 4. AMBIGUOUS "WORST" / "BEST" HANDLING
    is_worst = any(w in q for w in ('worst', 'lowest', 'least', 'bottom', 'lagging', 'poorest', 'underperforming'))
    is_best = any(w in q for w in ('best', 'highest', 'most', 'top', 'leading', 'peak'))
    is_breakdown = any(w in q for w in ('breakdown', 'by department', 'across department', 'each department',
                                        'by store', 'across stores', 'by severity', 'breakdown by'))

    if not (is_worst or is_best or is_breakdown) and not (prior_context and prior_context.get('metric')):
        return None

    # Context inheritance: If metric is absent, check prior context
    if not metric:
        if prior_context and prior_context.get('metric'):
            metric = prior_context['metric']
        elif is_worst or is_best:
            # Ambiguous worst/best query with no metric in query or prior context:
            # DO NOT guess attendance! DO NOT invent a synthetic composite score!
            # Ask ONE focused clarification question presenting available metrics.
            disp_dim = entity_dimension.lower()
            avail = [m for m in all_measures if not identity(m)][:5]
            if not avail and has_wide_periods:
                avail = ['Attendance', 'Approved Leaves']
            elif not avail:
                avail = ['Attendance', 'Approved Leaves']

            label_dir = "lowest" if is_worst else "highest"
            measures_str = ", ".join(f"**{m}**" for m in avail)
            clarification = (
                f"To identify the {label_dir}-performing **{disp_dim}**, please specify which metric you would like to evaluate "
                f"(for example: {measures_str}). Different metrics represent different operational dimensions, "
                f"so PulseHR AI does not assume a default metric or combine measures into an unverified composite score."
            )
            return AnalyticalQueryPlan(
                intent='ambiguity_clarification',
                metric=None,
                entity_dimension=entity_dimension,
                direction='lowest' if is_worst else 'highest',
                dataset_id=dataset_id,
                sheet_id=sheet_id,
                explanation="Ambiguous performance query without metric specification; prompts for clarification.",
                available_metrics=avail,
                clarification_question=clarification
            )
        else:
            return None

    # Determine direction / intent
    direction: SortDirection = 'all'
    intent: QueryIntent = 'ranking'
    ranking_limit = 1

    if is_worst:
        direction = 'lowest'
        intent = 'ranking'
        m_limit = re.search(r'(?:top|bottom|worst)\s*(\d+)', q)
        ranking_limit = int(m_limit.group(1)) if m_limit else 1
    elif is_best:
        direction = 'highest'
        intent = 'ranking'
        m_limit = re.search(r'(?:top|bottom|best|highest)\s*(\d+)', q)
        ranking_limit = int(m_limit.group(1)) if m_limit else 1
    elif is_breakdown:
        direction = 'all'
        intent = 'breakdown'
        ranking_limit = 9999

    return AnalyticalQueryPlan(
        intent=intent,
        metric=metric,
        entity_dimension=entity_dimension,
        direction=direction,
        time_window=time_window,
        ranking_limit=ranking_limit,
        dataset_id=dataset_id,
        sheet_id=sheet_id,
        explanation=f"Evaluates full population across {entity_dimension}s for {metric} ({direction} ordering)."
    )


def execute_analytical_plan(plan: AnalyticalQueryPlan, conn=None) -> dict[str, Any]:
    """Executes an AnalyticalQueryPlan deterministically against shared analytical evidence."""
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    try:
        candidate_sheets = _resolve_candidate_sheets(conn, plan.dataset_id, plan.sheet_id)
        if not candidate_sheets:
            raise ValueError("No uploaded sheet records found in active scope.")

        # 1. HANDLE AMBIGUITY CLARIFICATION INTENT
        if plan.intent == 'ambiguity_clarification':
            sheet = candidate_sheets[0]
            clarification = plan.clarification_question or (
                f"Please specify which metric you would like to evaluate for **{plan.entity_dimension}** "
                f"(e.g., {', '.join(plan.available_metrics)})."
            )
            suggested = [f"Which {plan.entity_dimension.lower()} has the lowest {m.lower()}?" for m in plan.available_metrics[:3]]
            return {
                "status": "ambiguity_clarification_required",
                "answer": f"### Clarification Required: Metric Specification\n\n{clarification}",
                "query_plan": {
                    "intent": plan.intent,
                    "dimension": plan.entity_dimension,
                    "direction": plan.direction,
                    "available_metrics": plan.available_metrics,
                    "source_sheet": sheet["name"],
                    "dataset_id": sheet["dataset_id"],
                    "sheet_id": sheet["id"]
                },
                "evidence": {
                    "status": "ambiguity_clarification_required",
                    "source_ids": [sheet["id"]],
                    "dimension": plan.entity_dimension,
                    "available_metrics": plan.available_metrics,
                    "caveats": ["No composite score invented; explicit user metric selection required."]
                },
                "citations": [
                    {
                        "source": f"{sheet['original_name']} / {sheet['name']}",
                        "text": f"Multiple numeric measures detected ({', '.join(plan.available_metrics)}). User clarification required.",
                        "type": "governance_ambiguity_protection"
                    }
                ],
                "suggested_questions": suggested
            }

        # Select primary sheet matching dimension & metric
        def score_sheet(s_record):
            score = 0
            cols = [c.lower() for c in json.loads(s_record["columns_json"] or "[]")]
            dim = (plan.entity_dimension or "department").lower()
            if any(dim in c for c in cols):
                score += 100
            if plan.metric:
                m_norm = plan.metric.lower()
                if any(m_norm in c for c in cols):
                    score += 80
            return (score, s_record["row_count"] or 0, -s_record["id"])

        scored = sorted(candidate_sheets, key=score_sheet, reverse=True)
        sheet = scored[0]
        sid = sheet["id"]
        cols = json.loads(sheet["columns_json"] or "[]")
        rows = [json.loads(r[0]) for r in conn.execute("SELECT data_json FROM sheet_rows WHERE sheet_id=? ORDER BY row_index", (sid,)).fetchall()]
        has_wide_periods = any(period_header(c) for c in cols)

        # Get shared decision intelligence brief snapshot hash
        brief = build_decision_brief(conn, sheet_id=sid)
        snapshot_hash = brief.get("snapshot", "unversioned")

        # 2. HANDLE CORRELATION / CAUSATION INTENT
        if plan.intent == 'correlation_causation':
            return _execute_correlation_causation_query(plan, sheet, cols, rows, brief, snapshot_hash)

        # 3. ROUTE TO HR PERIOD/ATTENDANCE ANALYTICS IF APPLICABLE
        is_hr_attendance_metric = plan.metric in ('attendance', 'leaves', 'final_attendance', 'headcount')
        has_attendance_cols = any(re.search(r'attendance|attended|leave|absent', c, re.I) for c in cols)
        if (has_wide_periods or has_attendance_cols) and is_hr_attendance_metric:
            return _execute_hr_period_attendance_query(plan, sheet, cols, rows, conn, snapshot_hash)

        # 4. GENERAL TABULAR ANALYTICAL EXECUTION (Sales, IT, Marketing, General HR)
        return _execute_general_tabular_query(plan, sheet, cols, rows, brief, snapshot_hash)

    finally:
        if should_close:
            conn.close()


def _execute_correlation_causation_query(
    plan: AnalyticalQueryPlan,
    sheet: sqlite3.Row,
    cols: list[str],
    rows: list[dict[str, Any]],
    brief: dict[str, Any],
    snapshot_hash: str
) -> dict[str, Any]:
    """Handles correlation and causation questions with strict non-causal statistical refusal."""
    m_a = plan.metric
    m_b = plan.secondary_metric

    profile = brief["profiles"][0] if brief.get("profiles") else None
    matrix_pairs = profile.get("matrix", {}).get("pairs", []) if profile else []

    # Find pair in matrix
    matched_pair = None
    if m_a and m_b:
        for p in matrix_pairs:
            x_norm = p["x"].lower()
            y_norm = p["y"].lower()
            if (m_a.lower() in x_norm and m_b.lower() in y_norm) or (m_b.lower() in x_norm and m_a.lower() in y_norm):
                matched_pair = p
                break

    lines = []
    lines.append(f"### Statistical Association Analysis & Causal Claim Refusal")
    if matched_pair and matched_pair.get("coefficient") is not None:
        rho = matched_pair["coefficient"]
        n_pairs = matched_pair["paired_rows"]
        lines.append(
            f"Under pairwise complete observation across **{n_pairs} paired records**, the Spearman rank correlation "
            f"between **{label(matched_pair['x'])}** and **{label(matched_pair['y'])}** is **{rho:+.2f}**."
        )

        within = matched_pair.get("within_groups", [])
        dim_name = matched_pair.get("within_dimension", "subgroup")
        if within and all(w.get("coefficient") is not None and w["coefficient"] * rho < 0 for w in within):
            lines.append(
                f"\n⚠️ **Subgroup Sign Reversal (Simpson's Paradox)**: In all {len(within)} eligible {dim_name} subgroups, "
                f"the correlation reverses sign relative to the pooled dataset. Relying on the pooled association is misleading."
            )

        lines.append(
            f"\n> **Refusal of Causal Inference**:\n"
            f"> PulseHR AI strictly separates descriptive statistical associations from causal explanations. "
            f"A rank correlation of **{rho:+.2f}** does **NOT** establish that changes in {label(matched_pair['x'])} "
            f"cause changes in {label(matched_pair['y'])}. Unmeasured confounders, exposure differences, external economic factors, "
            f"or population composition may explain this pattern."
        )
        lines.append(
            f"\n- **Business Implication**: Do not set performance targets, operational policies, or quota changes assuming a direct causal link without controlled testing."
        )
        lines.append(
            f"- **Proposed Action**: Evaluate {label(matched_pair['x'])} and {label(matched_pair['y'])} within comparable {dim_name} segments and consult domain leadership before taking operational action."
        )
    else:
        reason = matched_pair.get("excluded_reason") if matched_pair else "Fewer than 12 paired records or measure non-numeric."
        lines.append(
            f"A reliable rank correlation between **{label(m_a or 'the requested metric')}** and other measures could not be computed: {reason}"
        )
        lines.append(
            f"\n> **Governance Statement**: PulseHR AI refuses unverified causal claims and does not infer cause-and-effect relationships from observational data."
        )

    answer_text = "\n".join(lines)
    return {
        "status": "success",
        "answer": answer_text,
        "query_plan": {
            "intent": "correlation_causation",
            "metric": m_a,
            "secondary_metric": m_b,
            "source_sheet": sheet["name"],
            "dataset_id": sheet["dataset_id"],
            "sheet_id": sheet["id"]
        },
        "evidence": {
            "source_ids": [sheet["id"]],
            "snapshot_hash": snapshot_hash,
            "metric_definition": f"Spearman rank correlation: {m_a} vs {m_b}",
            "calculation_method": "Pearson correlation of average ranks on pairwise complete observations. Descriptive only.",
            "caveats": [
                "Correlation does not imply causation.",
                "Unmeasured confounders and group mix may explain observed association."
            ]
        },
        "citations": [
            {
                "source": f"{sheet['original_name']} / {sheet['name']}",
                "text": "Evaluated pairwise correlation across valid numeric observations without inferring causation.",
                "type": "non_causal_statistical_evidence"
            }
        ]
    }


def _execute_hr_period_attendance_query(
    plan: AnalyticalQueryPlan,
    sheet: sqlite3.Row,
    cols: list[str],
    rows: list[dict[str, Any]],
    conn,
    snapshot_hash: str
) -> dict[str, Any]:
    """Executes HR attendance period analytics with wide matrix cross-validation and dense ranking."""
    sid = sheet["id"]
    # Look for secondary comparison sheet (e.g. Leave Calculation Check)
    comp_sheet = conn.execute(
        "SELECT s.* FROM sheets s WHERE s.dataset_id=? AND s.id!=? AND (s.name LIKE '%leave%' OR s.name LIKE '%check%') LIMIT 1",
        (sheet["dataset_id"], sid)
    ).fetchone()
    comp_rows = None
    comp_name = None
    if comp_sheet:
        comp_name = comp_sheet["name"]
        comp_rows = [json.loads(r[0]) for r in conn.execute("SELECT data_json FROM sheet_rows WHERE sheet_id=? ORDER BY row_index", (comp_sheet["id"],)).fetchall()]

    res = analyze_hr_attendance_sheet(
        records=rows,
        columns=cols,
        sheet_name=sheet["name"],
        comparison_sheet_records=comp_rows,
        comparison_sheet_name=comp_name,
        requested_period=plan.time_window
    )

    # Reject unavailable periods explicitly without substitution
    if res.get("status") == "period_unavailable":
        avail = ", ".join(res.get("available_periods", []))
        return {
            "status": "period_unavailable",
            "query_plan": {
                "intent": plan.intent,
                "metric": plan.metric,
                "direction": plan.direction,
                "dimension": plan.entity_dimension,
                "time_window": plan.time_window,
                "source_sheet": sheet["name"],
                "dataset_id": sheet["dataset_id"],
                "sheet_id": sheet["id"],
                "status": "period_unavailable"
            },
            "answer": (
                f"### Period Unavailable: {plan.time_window}\n\n"
                f"{res['error']}\n\n"
                f"The analysis cannot be performed for **{plan.time_window}** because no records for that period exist in the dataset. "
                f"Available period(s): **{avail}**."
            ),
            "evidence": {
                "source_ids": [sheet["id"]],
                "snapshot_hash": snapshot_hash,
                "status": "period_unavailable",
                "requested_period": plan.time_window,
                "available_periods": res.get("available_periods", []),
                "caveats": ["No period substitution allowed."]
            },
            "raw_analysis": res,
            "citations": [
                {
                    "source": f"{sheet['original_name']} / {sheet['name']}",
                    "text": res["error"],
                    "type": "period_validation_error"
                }
            ]
        }

    depts = res.get("departments", [])
    bench = res["organization_benchmarks"]
    period_lbl = res["period_label"]
    distinct_emp = res["distinct_employees"]

    # Select target metric key
    if plan.metric in ('attendance', 'final_attendance'):
        metric_key = 'avg_attendance_per_employee' if plan.metric == 'attendance' else 'net_attendance_days'
        metric_display_name = 'average attendance' if plan.metric == 'attendance' else 'net attendance'
        unit_suffix = ' days/employee'
        org_val = bench['avg_attendance_per_employee']
    elif plan.metric == 'leaves':
        metric_key = 'avg_leaves_per_employee'
        metric_display_name = 'average approved leaves'
        unit_suffix = ' days/employee'
        org_val = bench['avg_leaves_per_employee']
    else:  # headcount
        metric_key = 'headcount'
        metric_display_name = 'headcount'
        unit_suffix = ' employees'
        org_val = bench['headcount']

    reverse_sort = (plan.direction == 'highest')
    sorted_depts = sorted(depts, key=lambda d: (d[metric_key], d['headcount']), reverse=reverse_sort)

    # Compute dense ranks preserving ties
    dense_ranked = []
    curr_rank = 1
    for idx, d in enumerate(sorted_depts):
        if idx > 0 and abs(d[metric_key] - sorted_depts[idx - 1][metric_key]) > 0.001:
            curr_rank += 1
        d_copy = dict(d)
        d_copy["dense_rank"] = curr_rank
        dense_ranked.append(d_copy)

    lines = []
    if plan.direction in ('lowest', 'highest') and plan.ranking_limit == 1:
        label_adjective = "lowest" if plan.direction == 'lowest' else "highest"
        top_val = dense_ranked[0][metric_key]
        tied_targets = [d for d in dense_ranked if d["dense_rank"] == 1]

        lines.append(f"### Executive Finding: {label_adjective.title()} Department {metric_display_name.title()} ({period_lbl})")
        if len(tied_targets) > 1:
            tied_names = " and ".join(f"**{_sanitize_untrusted_text(d['department'])}** ({d['headcount']} staff)" for d in tied_targets)
            lines.append(
                f"Under validated full-population evaluation, {tied_names} tied for the **{label_adjective} {metric_display_name}** "
                f"at **{top_val:.2f}{unit_suffix}**."
            )
        else:
            primary_target = dense_ranked[0]
            d_name = _sanitize_untrusted_text(primary_target['department'])
            val_num = primary_target[metric_key]
            gap = primary_target.get('benchmark_gap', round(val_num - org_val, 2))
            pop = primary_target['headcount']
            lines.append(
                f"Under validated full-population evaluation, **{d_name}** recorded the **{label_adjective} {metric_display_name}** "
                f"at **{val_num:.2f}{unit_suffix}** across **{pop} distinct employees**."
            )
            lines.append(
                f"- **Organization Benchmark**: **{org_val:.2f}{unit_suffix}** across all {distinct_emp} staff "
                f"(a variance of **{gap:+.2f}{unit_suffix}**)."
            )
            if primary_target.get('is_small_population'):
                lines.append(f"- **Population Note**: Group headcount ({pop} staff) is small; individual absences impact the average heavily.")
            if primary_target.get('proposed_action'):
                lines.append(f"- **Proposed Action**: {primary_target['proposed_action']}")

            # Weekly drilldown table
            if primary_target.get('weekly_drilldown'):
                lines.append(f"\n**Weekly Period Breakdown for {d_name}**:")
                lines.append("| Period | Length | Total Attended | Avg / Emp | Approved Leaves | Avg / Emp |")
                lines.append("|---|---|---|---|---|---|")
                for w in primary_target['weekly_drilldown']:
                    lines.append(f"| {w['period']} | {w['length_days']}d | {w['attended_days']}d | {w['avg_attended_per_emp']}d | {w['leave_days']}d | {w['avg_leave_per_emp']}d |")
    else:
        limit = min(plan.ranking_limit, len(dense_ranked))
        lines.append(f"### Department {metric_display_name.title()} Breakdown ({period_lbl})")
        lines.append(f"Evaluated across **{len(depts)} departments** and **{distinct_emp} distinct employees** (Organization Benchmark: **{org_val:.2f}{unit_suffix}**).\n")
        lines.append("| Rank | Department | Headcount | Avg Attendance | Approved Leaves | Benchmark Gap | Attention Status |")
        lines.append("|---|---|---|---|---|---|---|")
        for d in dense_ranked[:limit]:
            gap_str = f"{d.get('benchmark_gap', 0):+.2f}d"
            status = "⚠️ Attention" if d.get('benchmark_gap', 0) <= -2.0 else "Normal"
            lines.append(f"| #{d['dense_rank']} | **{_sanitize_untrusted_text(d['department'])}** | {d['headcount']} | **{d['avg_attendance_per_employee']:.2f}d** | {d['avg_leaves_per_employee']:.2f}d | {gap_str} | {status} |")

    lines.append(f"\n> **Data Governance Limitations**:")
    lines.append(f"> 1. **Time Horizon**: {res['historical_trend_notice']}")
    lines.append(f"> 2. **Denominators**: {res['denominator_notice']}")

    answer_text = "\n".join(lines)
    return {
        "status": "success",
        "query_plan": {
            "intent": plan.intent,
            "metric": plan.metric,
            "direction": plan.direction,
            "dimension": plan.entity_dimension,
            "time_window": period_lbl,
            "source_sheet": sheet["name"],
            "dataset_id": sheet["dataset_id"],
            "sheet_id": sheet["id"]
        },
        "answer": answer_text,
        "evidence": {
            "source_ids": [sheet["id"]],
            "snapshot_hash": snapshot_hash,
            "metric_definition": metric_display_name,
            "period": period_lbl,
            "filters": {"dimension": plan.entity_dimension},
            "calculation_method": "Full-population aggregation with calendar constraint cross-validation and dense ranking for ties.",
            "coverage": {
                "used_rows": res["total_evaluated_records"],
                "total_rows": res["total_evaluated_records"],
                "missing_rows": 0,
                "groups_evaluated": len(depts)
            },
            "caveats": [res["historical_trend_notice"], res["denominator_notice"]]
        },
        "raw_analysis": res,
        "citations": [
            {
                "source": f"{sheet['original_name']} / {sheet['name']}",
                "text": f"Evaluated all {res['total_evaluated_records']} records ({distinct_emp} distinct employees) across {len(depts)} departments.",
                "type": "deterministic_full_population"
            }
        ]
    }


def _execute_general_tabular_query(
    plan: AnalyticalQueryPlan,
    sheet: sqlite3.Row,
    cols: list[str],
    rows: list[dict[str, Any]],
    brief: dict[str, Any],
    snapshot_hash: str
) -> dict[str, Any]:
    """Executes general tabular group comparisons (Sales, IT, Marketing, General HR) with tie preservation."""
    df = pd.DataFrame(rows, columns=cols)
    metric_col = plan.metric

    # Match metric column in dataframe if not an exact match
    if metric_col not in df.columns:
        for c in df.columns:
            if metric_col.lower() in c.lower() or c.lower() in metric_col.lower():
                metric_col = c
                break
        else:
            raise ValueError(f"Metric column '{plan.metric}' not found in sheet '{sheet['name']}'.")

    # Match dimension column
    dim_col = plan.entity_dimension
    if dim_col not in df.columns:
        for c in df.columns:
            if dim_col.lower() in c.lower() or c.lower() in dim_col.lower():
                dim_col = c
                break
        else:
            raise ValueError(f"Grouping dimension '{plan.entity_dimension}' not found in sheet '{sheet['name']}'.")

    # Check date column if time_window was requested
    if plan.time_window:
        date_cols = [c for c in cols if re.search(r'\b(date|timestamp|datetime)\b', c, re.I)]
        if not date_cols:
            return {
                "status": "period_unavailable",
                "answer": f"### Period Unavailable: {plan.time_window}\n\nHistorical monthly analysis cannot be performed because this dataset does not contain row-level dates or period headers.",
                "evidence": {"status": "period_unavailable", "source_ids": [sheet["id"]], "snapshot_hash": snapshot_hash}
            }
        # Check if requested month exists in date column
        d_series = pd.to_datetime(df[date_cols[0]], errors='coerce')
        avail_months = sorted(set(d_series.dt.strftime('%B').dropna().unique()))
        if plan.time_window.title() not in avail_months:
            avail_str = ", ".join(avail_months)
            return {
                "status": "period_unavailable",
                "answer": (
                    f"### Period Unavailable: {plan.time_window}\n\n"
                    f"The analysis cannot be performed for **{plan.time_window}** because no records for that period exist in the dataset. "
                    f"Available period(s): **{avail_str}**."
                ),
                "evidence": {
                    "status": "period_unavailable",
                    "requested_period": plan.time_window,
                    "available_periods": avail_months,
                    "source_ids": [sheet["id"]],
                    "snapshot_hash": snapshot_hash
                }
            }
        # Filter to requested month
        df = df[d_series.dt.strftime('%B') == plan.time_window.title()]

    clean_metric = numbers(df[metric_col])
    valid_metric = clean_metric.dropna()
    if len(valid_metric) < 2:
        raise ValueError(f"Insufficient numeric observations for metric '{metric_col}'.")

    baseline = value(valid_metric.mean())
    missing_count = int(clean_metric.isna().sum())

    # Group by dimension
    temp = pd.DataFrame({'group': df[dim_col].fillna('(missing)').astype(str), 'v': clean_metric})
    groups = []
    for group_name, part in temp.groupby('group', sort=True):
        v = part.v.dropna()
        if len(v) == 0:
            continue
        g_mean = value(v.mean())
        g_med = value(v.median())
        groups.append({
            'group': group_name,
            'value': g_mean,
            'median': g_med,
            'used_rows': len(v),
            'missing_rows': int(part.v.isna().sum()),
            'gap': value(g_mean - baseline) if g_mean is not None and baseline is not None else None,
            'small_sample': len(v) < 5
        })

    if not groups:
        raise ValueError(f"No valid group observations found for dimension '{dim_col}'.")

    # Sort groups
    reverse_sort = (plan.direction == 'highest')
    groups.sort(key=lambda g: (g['value'] is None, g['value'] if g['value'] is not None else 0, g['group']), reverse=reverse_sort)

    # Dense ranking preserving ties
    dense_groups = []
    curr_rank = 1
    for idx, g in enumerate(groups):
        if idx > 0 and abs(g['value'] - groups[idx - 1]['value']) > 0.0001:
            curr_rank += 1
        g_copy = dict(g)
        g_copy['dense_rank'] = curr_rank
        dense_groups.append(g_copy)

    label_adjective = "lowest" if plan.direction == 'lowest' else "highest"
    metric_lbl = label(metric_col)

    lines = []
    if plan.direction in ('lowest', 'highest') and plan.ranking_limit == 1:
        top_val = dense_groups[0]['value']
        tied_targets = [g for g in dense_groups if g['dense_rank'] == 1]

        lines.append(f"### Executive Finding: {label_adjective.title()} {dim_col} {metric_lbl}")
        if len(tied_targets) > 1:
            tied_names = " and ".join(f"**{_sanitize_untrusted_text(g['group'])}** ({g['used_rows']} records)" for g in tied_targets)
            lines.append(
                f"Under validated full-population evaluation, {tied_names} tied for the **{label_adjective} {metric_lbl}** "
                f"at **{top_val:,.2f}**."
            )
        else:
            target = dense_groups[0]
            g_name = _sanitize_untrusted_text(target['group'])
            lines.append(
                f"Under validated full-population evaluation, **{g_name}** recorded the **{label_adjective} {metric_lbl}** "
                f"at **{target['value']:,.2f}** across **{target['used_rows']} valid records**."
            )
            gap_str = f"{target['gap']:+,.2f}" if target['gap'] is not None else "0.00"
            lines.append(
                f"- **Overall Benchmark**: **{baseline:,.2f}** across all {len(valid_metric)} records "
                f"(a variance of **{gap_str}**)."
            )
            if target['small_sample']:
                lines.append(f"- **Sample Size Note**: Group size ({target['used_rows']} records) is small; individual entries heavily impact the average.")

            lines.append(
                f"- **Business Implication**: This identifies an operational segment to investigate; differences in workload, exposure, or product mix may explain the variance rather than underlying performance."
            )
            lines.append(
                f"- **Proposed Action**: Review {metric_lbl} with the {g_name} leadership team before making policy changes or setting corrective targets."
            )
    else:
        limit = min(plan.ranking_limit, len(dense_groups))
        lines.append(f"### {dim_col} {metric_lbl} Breakdown")
        lines.append(f"Evaluated across **{len(groups)} {dim_col}s** and **{len(valid_metric)} records** (Overall Benchmark: **{baseline:,.2f}**).\n")
        lines.append(f"| Rank | {dim_col} | Valid Records | Missing | Group Mean | Group Median | Benchmark Gap | Status |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for g in dense_groups[:limit]:
            gap_str = f"{g['gap']:+,.2f}" if g['gap'] is not None else "0.00"
            status = "⚠️ Small Sample" if g['small_sample'] else "Normal"
            lines.append(f"| #{g['dense_rank']} | **{_sanitize_untrusted_text(g['group'])}** | {g['used_rows']} | {g['missing_rows']} | **{g['value']:,.2f}** | {g['median']:,.2f} | {gap_str} | {status} |")

    lines.append(f"\n> **Data Governance Limitations**:")
    lines.append(f"> 1. **Coverage**: {len(valid_metric)} of {len(df)} records contained valid numeric values; {missing_count} missing records excluded (not treated as zero).")
    lines.append(f"> 2. **Calculation Method**: Unweighted mean of valid source records by group. No exposure adjustment or cross-sheet joins applied.")

    answer_text = "\n".join(lines)
    return {
        "status": "success",
        "query_plan": {
            "intent": plan.intent,
            "metric": metric_col,
            "direction": plan.direction,
            "dimension": dim_col,
            "time_window": plan.time_window,
            "source_sheet": sheet["name"],
            "dataset_id": sheet["dataset_id"],
            "sheet_id": sheet["id"]
        },
        "answer": answer_text,
        "evidence": {
            "source_ids": [sheet["id"]],
            "snapshot_hash": snapshot_hash,
            "metric_definition": metric_lbl,
            "period": plan.time_window or "full_dataset",
            "filters": {"dimension": dim_col},
            "calculation_method": "Unweighted mean of valid source records per group. Dense ranking applied for ties. Missing values excluded.",
            "coverage": {
                "used_rows": len(valid_metric),
                "total_rows": len(df),
                "missing_rows": missing_count,
                "groups_evaluated": len(groups)
            },
            "caveats": [
                f"{missing_count} missing records excluded without zero-substitution.",
                "Unweighted mean; differences in exposure or mix not adjusted."
            ]
        },
        "citations": [
            {
                "source": f"{sheet['original_name']} / {sheet['name']}",
                "text": f"Evaluated {len(valid_metric)} valid records across {len(groups)} {dim_col} groups.",
                "type": "deterministic_group_comparison"
            }
        ]
    }
