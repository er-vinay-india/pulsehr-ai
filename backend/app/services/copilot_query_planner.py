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
import hashlib
import html
import json
import re
import sqlite3
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
from .hr_period_analytics import analyze_hr_attendance_sheet, parse_period_column, extract_normalized_periods, find_column_by_role

QueryIntent = Literal[
    'ranking',
    'breakdown',
    'ambiguity_clarification',
    'correlation_causation',
    'period_unavailable',
    'summary_positives',
    'summary_concerns',
    'summary_actions',
    'followup_why',
    'ranking_followup',
    'threshold_filter'
]
SortDirection = Literal['lowest', 'highest', 'all']

MONTH_NAMES = (
    'january', 'february', 'march', 'april', 'may', 'june',
    'july', 'august', 'september', 'october', 'november', 'december'
)


from pydantic import BaseModel, ConfigDict, Field


class AnalyticalQueryPlan(BaseModel):
    """Pydantic model representing a validated analytical execution plan."""
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

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
    snapshot_id: str | None = None
    prior_context: dict[str, Any] | None = None
    explanation: str = ''
    available_metrics: list[str] = Field(default_factory=list)
    available_dimensions: list[str] = Field(default_factory=list)
    clarification_question: str | None = None
    entity_grain: Literal['department', 'employee'] = 'department'
    identifier_col: str | None = None
    additional_fields: list[str] = Field(default_factory=list)
    threshold_operator: str | None = None
    threshold_value: float | None = None


def resolve_metric_direction(metric_name: str | None, cols: list[str] | None = None, rows: list[dict] | None = None) -> str:
    """Returns 'lower_is_worse', 'higher_is_worse', 'unresolved_definition', or 'neutral'."""
    if not metric_name:
        return 'neutral'
    m_clean = str(metric_name).lower().replace('_', ' ').strip()
    if 'final attendance' in m_clean or 'net attendance' in m_clean:
        return 'unresolved_definition'
    if any(k in m_clean for k in (
        'attendance', 'attendance rate', 'weekly sales', 'sales', 'revenue',
        'profit', 'rating', 'performance', 'punctuality', 'retention'
    )):
        return 'lower_is_worse'
    if any(k in m_clean for k in (
        'leave', 'leaves', 'absent', 'absence', 'overtime', 'turnover',
        'attrition', 'churn', 'incident', 'defect', 'error', 'delay',
        'strain', 'burnout', 'disruption', 'resolution time'
    )):
        return 'higher_is_worse'
    if cols:
        try:
            from .semantic_mapping import infer_semantic_catalog
            catalog = infer_semantic_catalog(cols, records=rows)
            f_meta = catalog.get_field(metric_name)
            if f_meta:
                if f_meta.unresolved_definition:
                    return 'unresolved_definition'
                if f_meta.direction_of_concern != 'neutral':
                    return f_meta.direction_of_concern
        except Exception:
            pass
    return 'neutral'



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
            "SELECT s.*, d.original_name FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id WHERE s.dataset_id=? ORDER BY s.row_count DESC, s.id ASC",
            (dataset_id,)
        ).fetchall()
        return rows
    else:
        rows = conn.execute(
            "SELECT s.*, d.original_name FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id ORDER BY s.row_count DESC, s.id ASC"
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

    profile_map = {}
    try:
        if "profile_json" in sheet_record.keys() and sheet_record["profile_json"]:
            p_list = json.loads(sheet_record["profile_json"])
            if isinstance(p_list, list):
                profile_map = {item.get("column"): item for item in p_list if isinstance(item, dict) and "column" in item}
    except Exception:
        profile_map = {}

    dim_pattern = re.compile(
        r'department|dept|team|division|region|channel|campaign|category|status|product|store|location|severity|priority|system|'
        r'make|model|brand|car|vehicle|type|segment|color|colour|role|group|class|gender|country|city|state',
        re.I
    )

    for c in cols:
        if identity(c):
            continue
        c_norm = c.lower()
        p_item = profile_map.get(c, {})
        is_numeric = bool(p_item.get("numeric"))
        has_cats = bool(p_item.get("category_labels"))
        distinct_count = p_item.get("distinct", 0)

        if re.search(r'\b(date|timestamp|datetime|week|month|year|day)\b', c_norm):
            date_cols.append(c)
        elif not c.startswith("interact_") and (dim_pattern.search(c_norm) or (has_cats and not is_numeric and 1 < distinct_count <= 250)):
            dimensions.append(c)
        elif not period_header(c):
            measures.append(c)

    return measures, dimensions, date_cols, has_wide_periods, domain


def plan_with_council_qwen(
    query: str,
    all_measures: list[str],
    all_dimensions: list[str],
    dataset_id: int | None = None,
    sheet_id: int | None = None,
    prior_context: dict[str, Any] | None = None
) -> AnalyticalQueryPlan | None:
    """Uses Qwen 3.5 via ModelGateway with CouncilPlan Pydantic schema when heuristics fall through."""
    if not all_measures and not all_dimensions and dataset_id is None and sheet_id is None:
        return None
    try:
        from .gateway.model_gateway import ModelGateway
        from ..core.models_config import ModelRole
        from .copilot.council_contracts import CouncilPlan, TaskType

        measures_str = ", ".join(all_measures[:12]) if all_measures else "None"
        dimensions_str = ", ".join(all_dimensions[:6]) if all_dimensions else "None"

        prompt = f"""You are the Qwen 3.5 Analytical Query Planner on the Executive AI Council.
Analyze the user's natural language question and extract a strictly typed CouncilPlan.

Available measures: {measures_str}
Available grouping dimensions: {dimensions_str}
Prior context: {prior_context or 'None'}

User Question: "{query}"

Rules:
1. If the user asks about people, staff, workers, individuals (e.g. 'worst employee', 'who came less', 'who slacked off'), entity_grain MUST be 'employee'.
2. If the user asks about teams, departments, units, entity_grain MUST be 'department'.
3. Metric should be one of the available measures or a recognized standard (e.g. 'Attendance', 'Approved Leaves', 'Sales').
4. Return ONLY valid JSON matching the CouncilPlan schema.
"""
        res = ModelGateway.generate(
            role=ModelRole.ANALYST,
            prompt=prompt,
            response_schema=CouncilPlan,
            step_name="qwen_council_plan_extraction",
            temperature_override=0.0,
            max_retries=1
        )
        if res.parsed:
            cp: CouncilPlan = res.parsed
            if cp.task_type in (TaskType.CONCEPTUAL_EXPLANATION, TaskType.GENERAL_CHAT):
                return None
            grain = cp.entity_grain.value if cp.entity_grain.value in ("employee", "department") else "department"
            return AnalyticalQueryPlan(
                intent=cp.operation.value if cp.operation else "ranking",
                metric=cp.metric,
                secondary_metric=cp.secondary_metric,
                entity_dimension="Department" if grain == "department" else "Employee",
                direction=cp.direction,
                ranking_limit=cp.ranking_limit,
                additional_fields=cp.additional_fields,
                threshold_operator=cp.threshold_operator,
                threshold_value=cp.threshold_value,
                entity_grain=grain,
                dataset_id=dataset_id,
                sheet_id=sheet_id,
                prior_context=prior_context,
                explanation=cp.explanation or f"Qwen 3.5 extracted CouncilPlan: {cp.operation} on {cp.metric} at {grain} grain."
            )
    except Exception:
        pass
    return None


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

    # 0. Context validation & dataset switch protection:
    # Purge prior context if user switched dataset or sheet scope
    active_prior = dict(prior_context) if prior_context else None
    if active_prior:
        p_ds = active_prior.get('dataset_id')
        p_sh = active_prior.get('sheet_id')
        if (p_ds is not None and dataset_id is not None and p_ds != dataset_id) or \
           (p_sh is not None and sheet_id is not None and p_sh != sheet_id):
            active_prior = None

    # Check for follow-up "why?" queries
    is_why_followup = q.strip('?!. ') in ('why', 'why is that', 'why did that happen', 'why is this', 'explain why', 'tell me why', 'can you explain why') or \
                      (q.startswith('why') and len(q.split()) <= 4 and active_prior and (active_prior.get('last_finding') or active_prior.get('last_ranking') or active_prior.get('metric')))
    if is_why_followup:
        return AnalyticalQueryPlan(
            intent='followup_why',
            prior_context=active_prior,
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            explanation="Explains underlying factors for preceding finding or ranking with strict non-causal disclaimer."
        )

    # Exclude definitional, general conversational, or calculation-only queries
    if any(k in q for k in ('what does', 'definition', 'policy', 'meaning', 'how do i', 'how many days was')) or (q.startswith('explain') and not is_why_followup):
        return None

    # Check Business Summary: Positives ("give me 3 good points", "positive points", "highlights", "strengths")
    count_match_pos = re.search(r'\b(\d+|three|two|four|five|one)\s+(?:good|positive|strength|highlight)', q)
    num_map = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5}
    is_summary_pos = bool(count_match_pos) or any(k in q for k in (
        '3 good points', 'three good points', 'good points', 'positive points', 'positive findings',
        'what is going well', "what's going well", 'key strengths', 'highlights', 'positive highlights'
    ))
    if is_summary_pos:
        req_count = 3
        if count_match_pos:
            token = count_match_pos.group(1).lower()
            req_count = int(token) if token.isdigit() else num_map.get(token, 3)
        return AnalyticalQueryPlan(
            intent='summary_positives',
            ranking_limit=req_count,
            prior_context=active_prior,
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            explanation=f"Resolves up to {req_count} verified positive findings from the decision brief."
        )

    # Check Business Summary: Concerns / Problems ("main problems", "significant concerns", "key risks", "what's wrong?")
    count_match_conc = re.search(r'\b(\d+|three|two|four|five|one)\s+(?:main\s+problems?|problems?|concerns?|significant\s+concerns?|key\s+risks?|issues?|risks?)', q)
    is_summary_concerns = bool(count_match_conc) or any(k in q for k in (
        'main problems', 'problems', 'concerns', 'significant concerns', 'key risks',
        "what's wrong", 'what is wrong', 'biggest issues', 'areas of concern', 'red flags'
    ))
    if is_summary_concerns:
        req_count = 3
        if count_match_conc:
            token = count_match_conc.group(1).lower()
            req_count = int(token) if token.isdigit() else num_map.get(token, 3)
        return AnalyticalQueryPlan(
            intent='summary_concerns',
            ranking_limit=req_count,
            prior_context=active_prior,
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            explanation=f"Resolves up to {req_count} significant concerns and risk findings from the decision brief."
        )

    # Check Business Summary: Actions ("what should we do?", "recommended actions", "next steps")
    is_summary_actions = any(k in q for k in (
        'what should we do', 'what actions', 'recommended actions', 'recommendations',
        'next steps', 'what do you recommend', 'action plan', 'what action should'
    ))
    if is_summary_actions:
        return AnalyticalQueryPlan(
            intent='summary_actions',
            prior_context=active_prior,
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            explanation="Extracts proposed next steps and actions supported by verified findings."
        )

    # Extract requested time window / month early
    time_window = None
    for m in MONTH_NAMES:
        if re.search(rf'\b{m}\b', q):
            time_window = m.title()
            break

    # 1. Follow-up for Employee ID ("i need employee id", "give me employee id", "show id")
    is_id_followup = any(p in q for p in (
        'employee id', 'show id', 'need id', 'need employee id', 'give me id',
        'give me employee id', 'emp id', 'i need id', 'show emp id'
    ))
    if is_id_followup and not any(k in q for k in ('who is', 'coming', 'calculate and')):
        if active_prior and (active_prior.get('last_ranking') or active_prior.get('metric') or active_prior.get('last_intent')):
            return AnalyticalQueryPlan(
                intent='ranking',
                metric=active_prior.get('metric', 'attendance'),
                entity_grain='employee',
                identifier_col='ID',
                direction=active_prior.get('direction', 'lowest'),
                time_window=active_prior.get('time_window'),
                ranking_limit=active_prior.get('ranking_limit', 10),
                additional_fields=list(active_prior.get('additional_fields', [])),
                threshold_operator=active_prior.get('threshold_operator'),
                threshold_value=active_prior.get('threshold_value'),
                prior_context=active_prior,
                dataset_id=dataset_id,
                sheet_id=sheet_id,
                explanation="Refines previous ranking to employee ID grain."
            )
        else:
            return AnalyticalQueryPlan(
                intent='ambiguity_clarification',
                clarification_question="Please specify which metric or evaluation you would like employee IDs for (for example: attendance ranking or approved leaves).",
                dataset_id=dataset_id,
                sheet_id=sheet_id,
                prior_context=active_prior,
                explanation="Identifier requested without prior analytical question; prompts for clarification."
            )

    # 2. Follow-up for adding department to employee ranking ("show department also", "add department")
    is_dept_field_followup = any(p in q for p in (
        'show department also', 'add department', 'with department', 'include department',
        'department also', 'show department as well', 'and department', 'department too'
    ))
    if is_dept_field_followup and active_prior and (active_prior.get('metric') or active_prior.get('last_ranking')):
        add_fields = list(active_prior.get('additional_fields', []))
        if 'Department' not in add_fields:
            add_fields.append('Department')
        return AnalyticalQueryPlan(
            intent='ranking',
            metric=active_prior.get('metric', 'attendance'),
            entity_grain=active_prior.get('entity_grain', 'employee'),
            identifier_col=active_prior.get('identifier_col', 'ID'),
            direction=active_prior.get('direction', 'lowest'),
            time_window=active_prior.get('time_window'),
            ranking_limit=active_prior.get('ranking_limit', 10),
            additional_fields=add_fields,
            threshold_operator=active_prior.get('threshold_operator'),
            threshold_value=active_prior.get('threshold_value'),
            prior_context=active_prior,
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            explanation="Adds Department descriptive field while preserving employee grain."
        )

    # 3. Limit refinement ("only top 3", "top 3", "show bottom 3", "limit to 5")
    # Requires explicit ranking intent keywords so unrelated numbers (e.g., 'square root of 9') are not hijacked.
    limit_match = re.search(r'\b(?:(?:only\s+)?(?:show\s+(?:the\s+)?)?(top|bottom|worst|best)\s*(\d+|three|two|four|five|six|seven|eight|nine|ten)|(?:limit\s+to|only)\s+(\d+|three|two|four|five|six|seven|eight|nine|ten))\b', q)
    if limit_match and active_prior and (active_prior.get('metric') or active_prior.get('last_ranking')):
        dir_word = limit_match.group(1)
        cnt_token = limit_match.group(2) or limit_match.group(3)
        if cnt_token:
            count = int(cnt_token) if cnt_token.isdigit() else num_map.get(cnt_token, 3)
            prior_dir = active_prior.get('direction', 'lowest')
            metric = active_prior.get('metric', 'attendance')
            m_dir = resolve_metric_direction(metric)
            if dir_word == 'top' or (not dir_word and 'only' in q):
                direction = prior_dir
            elif dir_word in ('bottom', 'worst'):
                direction = 'highest' if m_dir == 'higher_is_worse' else 'lowest'
            elif dir_word in ('best', 'highest'):
                direction = 'lowest' if m_dir == 'higher_is_worse' else 'highest'
            else:
                direction = prior_dir

            return AnalyticalQueryPlan(
                intent='ranking',
                metric=metric,
                entity_grain=active_prior.get('entity_grain', 'employee'),
                entity_dimension=active_prior.get('dimension'),
                identifier_col=active_prior.get('identifier_col', 'ID'),
                direction=direction,
                ranking_limit=count,
                time_window=active_prior.get('time_window'),
                additional_fields=list(active_prior.get('additional_fields', [])),
                threshold_operator=active_prior.get('threshold_operator'),
                threshold_value=active_prior.get('threshold_value'),
                prior_context=active_prior,
                dataset_id=dataset_id,
                sheet_id=sheet_id,
                explanation=f"Followup ranking query limiting to {count} while preserving context."
            )

    # 4. Threshold queries ("who came less than 10 days?", "less than 10 days")
    thresh_match = re.search(r'\b(?:who\s+came\s+|who\s+attended\s+|who\s+has\s+)?(?:less than|<|under|fewer than|more than|>|at least|greater than)\s*(\d+(?:\.\d+)?)\s*(?:days?|times?)?\b', q)
    if thresh_match:
        val = float(thresh_match.group(1))
        op = '<' if any(k in q for k in ('less than', '<', 'under', 'fewer than')) else '>='
        return AnalyticalQueryPlan(
            intent='threshold_filter',
            metric='attendance',
            entity_grain='employee',
            identifier_col='ID',
            direction='lowest',
            time_window=time_window,
            ranking_limit=50,
            threshold_operator=op,
            threshold_value=val,
            prior_context=active_prior,
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            explanation=f"Filters employees with attendance {op} {val} days."
        )

    # 5. Low/infrequent attendance employee queries ("who is not coming regularly", "worst employee details", "how much he absent")
    is_person_grain = bool(re.search(r'\b(who|whom|employee|employees|person|people|staff|worker|workers)\b', q))
    has_id_signal = bool(re.search(r'\b(employee id|emp id|id)\b', q))
    has_details_signal = any(k in q for k in ('detail', 'details', 'department', 'dept', 'absent', 'absence', 'how much', 'which department'))

    is_low_att_phrase = any(phrase in q for phrase in (
        'not coming regularly', 'coming very less', 'came very less', 'came least',
        'least attendance', 'lowest attendance', 'not regular', 'irregular attendance',
        'attended least', 'attended lowest', 'who is not coming', 'who came least', 'who is coming very less',
        'worst employee', 'worst staff', 'worst worker', 'poorest attendance', 'underperforming employee',
        'most absent', 'highest absent', 'how much he absent', 'how much she absent', 'how much they absent',
        'absent most', 'most absence', 'highest absence', 'absenteeism'
    )) or bool(re.search(r'\bwho\b.*\b(?:not coming|coming less|came less|least|lowest|absent|worst)\b', q)) \
       or (is_person_grain and any(w in q for w in ('worst', 'lowest', 'least', 'bottom', 'absent', 'absence', 'poorest', 'lagging')) and not any(k in q for k in ('how many employees', 'total employees', 'by department', 'in each department')))

    if is_low_att_phrase and is_person_grain:
        limit = 10
        word_num_map = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}
        limit_m = re.search(r'\b(?:top|bottom|worst|least|first)\s*(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b', q)
        if not limit_m:
            limit_m = re.search(r'\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:employees?|people|staff|workers?|person)\b', q)
        if not limit_m:
            limit_m = re.search(r'\b(?:which|show|give|limit to|only)\s*(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b', q)
        if limit_m:
            tok = limit_m.group(1).lower()
            limit = int(tok) if tok.isdigit() else word_num_map.get(tok, 10)
        add_fields = list(active_prior.get('additional_fields', [])) if active_prior else []
        if has_details_signal and 'Department' not in add_fields:
            add_fields.append('Department')
        return AnalyticalQueryPlan(
            intent='ranking',
            metric='attendance',
            entity_grain='employee',
            identifier_col='ID' if has_id_signal else None,
            direction='lowest',
            time_window=time_window,
            ranking_limit=limit,
            additional_fields=add_fields,
            prior_context=active_prior,
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            explanation="Evaluates full population across employees to identify lowest recorded attendance and absence details."
        )

    # 6. High attendance employee queries
    is_high_att_phrase = any(phrase in q for phrase in (
        'coming most', 'came most', 'highest attendance', 'most attendance',
        'best attendance', 'attended most', 'attended highest', 'best employee',
        'top employee', 'highest performing employee'
    )) or bool(re.search(r'\bwho\b.*\b(?:most attendance|highest attendance|came most|best)\b', q)) \
       or (is_person_grain and any(w in q for w in ('best', 'highest', 'most', 'top', 'peak', 'premier', 'leading')) and not any(k in q for k in ('how many employees', 'total employees', 'by department', 'in each department')))

    if is_high_att_phrase and is_person_grain:
        limit = 10
        limit_m = re.search(r'\b(?:top|best|first)\s*(\d+)\b', q)
        if limit_m:
            limit = int(limit_m.group(1))
        add_fields = list(active_prior.get('additional_fields', [])) if active_prior else []
        if has_details_signal and 'Department' not in add_fields:
            add_fields.append('Department')
        return AnalyticalQueryPlan(
            intent='ranking',
            metric='attendance',
            entity_grain='employee',
            identifier_col='ID' if has_id_signal else None,
            direction='highest',
            time_window=time_window,
            ranking_limit=limit,
            additional_fields=add_fields,
            prior_context=active_prior,
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            explanation="Evaluates full population across employees to identify highest recorded attendance."
        )

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
                prior_context=active_prior,
                explanation=f"Evaluates association between {matched_measures[0]} and {matched_measures[1]} while strictly refusing causal claims."
            )
        elif len(matched_measures) == 1 and any(k in q for k in ('why', 'cause', 'reason')):
            return AnalyticalQueryPlan(
                intent='correlation_causation',
                metric=matched_measures[0],
                dataset_id=dataset_id,
                sheet_id=sheet_id,
                prior_context=active_prior,
                explanation=f"Evaluates statistical associations with {matched_measures[0]} and refuses unverified causal claims."
            )

    # 2. RESOLVE GROUPING DIMENSION
    entity_dimension = None
    if all_dimensions:
        for dim in all_dimensions:
            d_norm = dim.lower()
            if d_norm in q or (d_norm == 'department' and any(k in q for k in ('dept', 'department'))) or \
               (d_norm == 'store' and 'store' in q) or (d_norm == 'team' and 'team' in q) or \
               (d_norm == 'severity' and 'severity' in q) or \
               (d_norm in ('make', 'car', 'model', 'brand', 'vehicle') and any(k in q for k in ('car', 'cars', 'make', 'brand', 'model', 'vehicle', 'vehicles'))):
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
            elif any(k in q for k in ('car', 'cars', 'vehicle', 'vehicles', 'automobile')):
                car_dim = next((d for d in all_dimensions if d.lower() in ('make', 'model', 'brand', 'car', 'vehicle')), None)
                entity_dimension = car_dim or all_dimensions[0]
            elif any(k in q for k in ('dept', 'department', 'by department', 'which department')):
                dept_dim = next((d for d in all_dimensions if 'dept' in d.lower()), None)
                entity_dimension = dept_dim
            elif detected_domain == "People operations" and any('dept' in d.lower() for d in all_dimensions) and any(w in q for w in ('group', 'by', 'across', 'each', 'breakdown')):
                entity_dimension = next(d for d in all_dimensions if 'dept' in d.lower())
            elif any(w in q for w in ('group', 'by', 'across', 'each', 'breakdown')):
                entity_dimension = all_dimensions[0]
            else:
                entity_dimension = None
    else:
        if 'store' in q:
            entity_dimension = 'Store'
        elif 'team' in q:
            entity_dimension = 'Team'
        elif 'division' in q:
            entity_dimension = 'Division'
        elif 'severity' in q:
            entity_dimension = 'Severity'
        elif any(k in q for k in ('car', 'cars', 'vehicle', 'make')):
            entity_dimension = 'Make'
        elif any(k in q for k in ('dept', 'department')):
            entity_dimension = 'Department'
        else:
            entity_dimension = None

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

    # 4. AMBIGUOUS "WORST" / "BEST" & EXPLICIT SORTING HANDLING
    is_subjective_worst = any(w in q for w in ('worst', 'poorest', 'lagging', 'underperforming'))
    is_subjective_best = any(w in q for w in ('best', 'leading', 'outperforming', 'premier'))
    is_explicit_lowest = any(w in q for w in ('lowest', 'least', 'bottom'))
    is_explicit_highest = any(w in q for w in ('highest', 'most', 'top', 'peak'))

    is_worst = is_subjective_worst or is_explicit_lowest
    is_best = is_subjective_best or is_explicit_highest
    is_breakdown = any(w in q for w in ('breakdown', 'by department', 'across department', 'each department',
                                        'by store', 'across stores', 'by severity', 'breakdown by'))

    if not (is_worst or is_best or is_breakdown):
        # Having a preceding metric does not make every new question a ranking
        # refinement. Explicit ID/limit/why follow-ups are handled above.
        if active_prior and active_prior.get('metric'):
            return None
        council_res = plan_with_council_qwen(
            query=q,
            all_measures=all_measures,
            all_dimensions=all_dimensions,
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            prior_context=active_prior
        )
        if council_res:
            return council_res
        return None

    # Context inheritance: If metric is absent, check prior context
    if not metric:
        if active_prior and active_prior.get('metric'):
            metric = active_prior['metric']
        elif is_worst or is_best:
            # Only trigger ambiguity clarification if user explicitly asked about an entity/dimension grain
            # (e.g. 'which department is worst?', 'which store is worst?', 'which team is worst?').
            # Do NOT hijack general domain questions (like 'which car is worst performing') where Council deliberation is expected!
            is_explicit_dim_query = False
            if any(k in q for k in ('department', 'dept', 'team', 'division', 'store', 'severity')):
                is_explicit_dim_query = True
            elif entity_dimension and entity_dimension.lower() in q:
                is_explicit_dim_query = True

            if is_explicit_dim_query and all_measures:
                if any(k in q for k in ('dept', 'department')):
                    disp_dim = 'department'
                elif 'store' in q:
                    disp_dim = 'store'
                elif 'team' in q:
                    disp_dim = 'team'
                elif 'severity' in q:
                    disp_dim = 'severity'
                else:
                    disp_dim = entity_dimension.lower() if entity_dimension else 'department'
                avail = [m for m in all_measures if not identity(m)][:5]
                if not avail and has_wide_periods:
                    avail = ['Attendance', 'Approved Leaves']
                elif not avail:
                    avail = ['Attendance', 'Approved Leaves']

                label_dir = "worst" if is_worst else "best"
                measures_str = ", ".join(f"**{m}**" for m in avail)
                clarification = (
                    f"To identify the {label_dir}-performing **{disp_dim}**, please specify which metric you would like to evaluate "
                    f"(for example: {measures_str}). Different metrics represent different operational dimensions, "
                    f"so HighView (powered by HRIDAY) does not assume a default metric or combine measures into an unverified composite score."
                )
                return AnalyticalQueryPlan(
                    intent='ambiguity_clarification',
                    metric=None,
                    entity_dimension=entity_dimension or 'Department',
                    direction='lowest' if is_worst else 'highest',
                    dataset_id=dataset_id,
                    sheet_id=sheet_id,
                    prior_context=active_prior,
                    explanation="Ambiguous performance query without metric specification; prompts for clarification.",
                    available_metrics=avail,
                    clarification_question=clarification
                )
            else:
                council_res = plan_with_council_qwen(
                    query=q,
                    all_measures=all_measures,
                    all_dimensions=all_dimensions,
                    dataset_id=dataset_id,
                    sheet_id=sheet_id,
                    prior_context=active_prior
                )
                if council_res:
                    return council_res
                return None
        else:
            council_res = plan_with_council_qwen(
                query=q,
                all_measures=all_measures,
                all_dimensions=all_dimensions,
                dataset_id=dataset_id,
                sheet_id=sheet_id,
                prior_context=active_prior
            )
            if council_res:
                return council_res
            return None

    # Determine direction / intent respecting metric direction of concern
    direction: SortDirection = 'all'
    intent: QueryIntent = 'ranking'
    ranking_limit = 1

    m_dir = resolve_metric_direction(metric, all_measures)
    if is_subjective_worst:
        direction = 'highest' if m_dir == 'higher_is_worse' else 'lowest'
        intent = 'ranking'
        m_limit = re.search(r'(?:top|bottom|worst)\s*(\d+)', q)
        ranking_limit = int(m_limit.group(1)) if m_limit else 1
    elif is_subjective_best:
        direction = 'lowest' if m_dir == 'higher_is_worse' else 'highest'
        intent = 'ranking'
        m_limit = re.search(r'(?:top|bottom|best|highest)\s*(\d+)', q)
        ranking_limit = int(m_limit.group(1)) if m_limit else 1
    elif is_explicit_lowest:
        direction = 'lowest'
        intent = 'ranking'
        m_limit = re.search(r'(?:bottom|lowest|least)\s*(\d+)', q)
        ranking_limit = int(m_limit.group(1)) if m_limit else 1
    elif is_explicit_highest:
        direction = 'highest'
        intent = 'ranking'
        m_limit = re.search(r'(?:top|highest|most)\s*(\d+)', q)
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
        prior_context=active_prior,
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
            if plan.entity_grain == 'employee':
                if any(k in c for k in ('id', 'employee', 'name') for c in cols):
                    score += 150
                if any('attendance' in c or 'attended' in c for c in cols):
                    score += 120
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

        # 2. HANDLE SUMMARY POSITIVES INTENT ("give me 3 good points")
        if plan.intent == 'summary_positives':
            return _execute_summary_positives_query(plan, candidate_sheets, cols, rows, brief, snapshot_hash)

        # 3. HANDLE SUMMARY CONCERNS INTENT ("main problems", "key risks")
        if plan.intent == 'summary_concerns':
            return _execute_summary_concerns_query(plan, candidate_sheets, cols, rows, brief, snapshot_hash)

        # 4. HANDLE SUMMARY ACTIONS INTENT ("what should we do?", "recommended actions")
        if plan.intent == 'summary_actions':
            return _execute_summary_actions_query(plan, candidate_sheets, cols, rows, brief, snapshot_hash)

        # 5. HANDLE FOLLOWUP WHY INTENT ("why?", "explain why")
        if plan.intent == 'followup_why':
            return _execute_followup_why_query(plan, candidate_sheets, cols, rows, brief, snapshot_hash)

        # 6. HANDLE CORRELATION / CAUSATION INTENT
        if plan.intent == 'correlation_causation':
            return _execute_correlation_causation_query(plan, sheet, cols, rows, brief, snapshot_hash)

        # 7. ROUTE TO HR PERIOD/ATTENDANCE ANALYTICS IF APPLICABLE
        is_hr_attendance_metric = plan.metric in ('attendance', 'leaves', 'final_attendance', 'headcount')
        has_attendance_cols = any(re.search(r'attendance|attended|leave|absent', c, re.I) for c in cols)
        if (has_wide_periods or has_attendance_cols) and is_hr_attendance_metric:
            if plan.entity_grain == 'employee':
                res = _execute_employee_attendance_query(plan, sheet, cols, rows, conn, snapshot_hash)
            else:
                res = _execute_hr_period_attendance_query(plan, sheet, cols, rows, conn, snapshot_hash)
            # Enforce grain consistency validation
            if plan.entity_grain == 'employee' and res.get('evidence', {}).get('result_grain') == 'department':
                raise ValueError("Grain mismatch: Expected employee-level evidence but received department aggregate.")
            return res

        # 8. GENERAL TABULAR ANALYTICAL EXECUTION (Sales, IT, Marketing, General HR)
        return _execute_general_tabular_query(plan, sheet, cols, rows, brief, snapshot_hash)

    finally:
        if should_close:
            conn.close()


def _execute_summary_positives_query(
    plan: AnalyticalQueryPlan,
    candidate_sheets: list[sqlite3.Row],
    cols: list[str],
    rows: list[dict[str, Any]],
    brief: dict[str, Any],
    snapshot_hash: str
) -> dict[str, Any]:
    """Resolves up to N verified positive findings directly from the server's cryptographic decision brief."""
    sheet = candidate_sheets[0]
    findings = brief.get("findings", [])
    profiles = brief.get("profiles", [])
    req_limit = plan.ranking_limit or 3

    positives = []
    seen_keys = set()

    for f in findings:
        kind = f.get("kind")
        metric = f.get("metric")
        m_dir = resolve_metric_direction(metric)
        detail = f.get("detail", {})

        is_pos = False
        if kind == "comparison":
            fg_name = detail.get("focus_group")
            groups = detail.get("groups", [])
            fg = next((g for g in groups if g.get("group") == fg_name), None)
            gap = fg.get("gap") if fg else None
            if gap is not None:
                if m_dir == "lower_is_worse" and gap > 0:
                    is_pos = True
                elif m_dir == "higher_is_worse" and gap < 0:
                    is_pos = True
        elif kind == "movement":
            points = detail.get("points", [])
            if len(points) >= 2:
                change = points[-1]["value"] - points[-2]["value"]
                if m_dir == "lower_is_worse" and change > 0:
                    is_pos = True
                elif m_dir == "higher_is_worse" and change < 0:
                    is_pos = True

        if is_pos:
            key = (f.get("title"), f.get("observation"))
            if key not in seen_keys:
                seen_keys.add(key)
                positives.append(f)
                if len(positives) >= req_limit:
                    break

    # If brief headline findings didn't reach requested count, check all evaluated group comparisons
    if len(positives) < req_limit:
        for p in profiles:
            for comp in p.get("comparisons", []):
                metric = comp.get("metric")
                m_dir = resolve_metric_direction(metric)
                baseline = comp.get("baseline")
                for g in comp.get("groups", []):
                    if g.get("group") in ("(missing)", "All selected rows") or g.get("used_rows", 0) < 5:
                        continue
                    gap = g.get("gap")
                    if gap is None:
                        continue
                    is_pos = (m_dir == "lower_is_worse" and gap > 0) or (m_dir == "higher_is_worse" and gap < 0)
                    if is_pos:
                        direction_str = "above" if gap > 0 else "below"
                        title = f"{g['group']}: {label(metric)} is {direction_str} baseline"
                        obs = f"{g['value']:,.2f} versus {baseline:,.2f} across this sheet ({abs(gap):,.2f} {direction_str}); {g['used_rows']} valid records in the group."
                        key = (title, obs)
                        if key not in seen_keys:
                            seen_keys.add(key)
                            positives.append({
                                "id": hashlib.sha256(f"{sheet['id']}:comp:{metric}:{title}".encode()).hexdigest()[:12],
                                "kind": "comparison",
                                "title": title,
                                "observation": obs,
                                "implication": f"This segment demonstrates favorable relative performance compared to the {baseline:,.2f} sheet average.",
                                "action": f"Review operating practices in {g['group']} with leadership to identify repeatable patterns.",
                                "owner": "Department owner",
                                "metric": metric,
                                "source": {"sheet_id": sheet["id"], "sheet": sheet["name"], "file": sheet["original_name"]},
                                "method": comp.get("method", "Unweighted group mean vs sheet baseline."),
                                "detail": {**comp, "focus_group": g["group"]}
                            })
                            if len(positives) >= req_limit:
                                break
                if len(positives) >= req_limit:
                    break
            if len(positives) >= req_limit:
                break

    lines = []
    lines.append("### Executive Overview: Verified Positive Findings")
    lines.append(f"Evaluated against Decision Brief snapshot `{snapshot_hash}` using full-population data.\n")

    if not positives:
        lines.append(
            "> **Evidentiary Notice**: Under verified statistical evaluation, **no segments currently exhibit positive variance** "
            "meeting statistical criteria (all observed segments are either at baseline, display adverse gaps, have incomplete coverage, "
            "or have unresolved definitions like leave accounting balances). HighView (powered by HRIDAY) does not invent or assume positive findings."
        )
    else:
        for idx, f in enumerate(positives, start=1):
            lines.append(f"#### {idx}. {_sanitize_untrusted_text(f['title'])}")
            lines.append(f"- **What happened**: {f['observation']}")
            lines.append(f"- **Why it matters**: {f['implication']}")
            lines.append(f"- **Proposed Action**: {f['action']} _({f.get('owner', 'Operations owner')})_")
            lines.append("")

        if len(positives) < req_limit:
            lines.append(
                f"> **Honest Limitation**: You requested {req_limit} points, but only **{len(positives)}** positive finding(s) "
                f"are supported by the data without lowering statistical standards or inventing claims."
            )

    answer_text = "\n".join(lines).strip()
    primary_finding = positives[0] if positives else None

    updated_context = {
        "dataset_id": sheet["dataset_id"],
        "sheet_id": sheet["id"],
        "snapshot_hash": snapshot_hash,
        "last_intent": "summary_positives",
        "last_finding": primary_finding,
        "metric": primary_finding.get("metric") if primary_finding else None,
        "dimension": "Department"
    }

    return {
        "status": "success",
        "query_plan": {
            "intent": "summary_positives",
            "ranking_limit": req_limit,
            "source_sheet": sheet["name"],
            "dataset_id": sheet["dataset_id"],
            "sheet_id": sheet["id"]
        },
        "answer": answer_text,
        "evidence": {
            "source_ids": [sheet["id"]],
            "snapshot_hash": snapshot_hash,
            "findings_evaluated": len(findings),
            "positives_returned": len(positives),
            "calculation_method": "Extracted from server-side decision brief snapshot. Never client-derived.",
            "caveats": ["Unweighted comparisons; differences in group exposure or record mix may explain variances."]
        },
        "prior_context": updated_context,
        "citations": [
            {
                "source": f"{sheet['original_name']} / {sheet['name']}",
                "text": f"Verified {len(positives)} positive finding(s) from cryptographic snapshot {snapshot_hash}.",
                "type": "decision_brief_snapshot"
            }
        ],
        "suggested_questions": [
            "Why is this the case?",
            "What are the main problems?",
            "What should we do?"
        ]
    }


def _execute_summary_concerns_query(
    plan: AnalyticalQueryPlan,
    candidate_sheets: list[sqlite3.Row],
    cols: list[str],
    rows: list[dict[str, Any]],
    brief: dict[str, Any],
    snapshot_hash: str
) -> dict[str, Any]:
    """Resolves up to N significant operational concerns from verified brief findings."""
    sheet = candidate_sheets[0]
    findings = brief.get("findings", [])
    req_limit = plan.ranking_limit or 3

    concerns = []
    seen_keys = set()

    for f in findings:
        kind = f.get("kind")
        metric = f.get("metric")
        m_dir = resolve_metric_direction(metric)
        detail = f.get("detail", {})

        is_concern = False
        if kind == "quality":
            is_concern = True
        elif kind == "comparison":
            fg_name = detail.get("focus_group")
            groups = detail.get("groups", [])
            fg = next((g for g in groups if g.get("group") == fg_name), None)
            gap = fg.get("gap") if fg else None
            if gap is not None:
                if m_dir == "lower_is_worse" and gap < 0:
                    is_concern = True
                elif m_dir == "higher_is_worse" and gap > 0:
                    is_concern = True
        elif kind == "movement":
            points = detail.get("points", [])
            if len(points) >= 2:
                change = points[-1]["value"] - points[-2]["value"]
                if m_dir == "lower_is_worse" and change < 0:
                    is_concern = True
                elif m_dir == "higher_is_worse" and change > 0:
                    is_concern = True

        if is_concern:
            key = (f.get("title"), f.get("observation"))
            if key not in seen_keys:
                seen_keys.add(key)
                concerns.append(f)
                if len(concerns) >= req_limit:
                    break

    lines = []
    lines.append("### Executive Overview: Significant Operational Concerns & Risks")
    lines.append(f"Evaluated against Decision Brief snapshot `{snapshot_hash}` using full-population data.\n")

    if not concerns:
        lines.append(
            "> Under verified statistical evaluation, **no significant operational concerns or data quality anomalies** "
            "exceeded priority thresholds in this dataset."
        )
    else:
        for idx, f in enumerate(concerns, start=1):
            badge = "⚠️ Data Quality" if f.get("kind") == "quality" else "🔻 Operational Variance"
            lines.append(f"#### {idx}. {_sanitize_untrusted_text(f['title'])} ({badge})")
            lines.append(f"- **Finding**: {f['observation']}")
            lines.append(f"- **Implication**: {f['implication']}")
            lines.append(f"- **Recommended Action**: {f['action']} _({f.get('owner', 'Review team')})_")
            lines.append("")

        if len(concerns) < req_limit:
            lines.append(
                f"> **Honest Limitation**: You requested {req_limit} concerns, but only **{len(concerns)}** "
                f"meet verified statistical significance thresholds."
            )

    answer_text = "\n".join(lines).strip()
    primary_finding = concerns[0] if concerns else None

    updated_context = {
        "dataset_id": sheet["dataset_id"],
        "sheet_id": sheet["id"],
        "snapshot_hash": snapshot_hash,
        "last_intent": "summary_concerns",
        "last_finding": primary_finding,
        "metric": primary_finding.get("metric") if primary_finding else None,
        "dimension": "Department"
    }

    return {
        "status": "success",
        "query_plan": {
            "intent": "summary_concerns",
            "ranking_limit": req_limit,
            "source_sheet": sheet["name"],
            "dataset_id": sheet["dataset_id"],
            "sheet_id": sheet["id"]
        },
        "answer": answer_text,
        "evidence": {
            "source_ids": [sheet["id"]],
            "snapshot_hash": snapshot_hash,
            "concerns_returned": len(concerns),
            "calculation_method": "Extracted from server-side decision brief snapshot.",
            "caveats": ["Missing records excluded without zero-substitution."]
        },
        "prior_context": updated_context,
        "citations": [
            {
                "source": f"{sheet['original_name']} / {sheet['name']}",
                "text": f"Identified {len(concerns)} verified concern(s) from cryptographic snapshot {snapshot_hash}.",
                "type": "decision_brief_snapshot"
            }
        ],
        "suggested_questions": [
            "Why did this happen?",
            "What should we do?",
            "Which department is worst?"
        ]
    }


def _execute_summary_actions_query(
    plan: AnalyticalQueryPlan,
    candidate_sheets: list[sqlite3.Row],
    cols: list[str],
    rows: list[dict[str, Any]],
    brief: dict[str, Any],
    snapshot_hash: str
) -> dict[str, Any]:
    """Resolves recommended actions backed by verified findings."""
    sheet = candidate_sheets[0]
    findings = brief.get("findings", [])

    actions = []
    seen_actions = set()

    for f in findings:
        action_text = f.get("action")
        if action_text and action_text not in seen_actions:
            seen_actions.add(action_text)
            actions.append({
                "action": action_text,
                "title": f.get("title"),
                "owner": f.get("owner", "Department leadership"),
                "review": f.get("review", "Proposed: review at the next operating meeting"),
                "metric": f.get("metric"),
                "finding": f
            })

    lines = []
    lines.append("### Recommended Actions Supported by Verified Evidence")
    lines.append(f"Based on Decision Brief snapshot `{snapshot_hash}`.\n")

    if not actions:
        lines.append("No specific operational interventions are currently mandated by the data.")
    else:
        for idx, a in enumerate(actions[:5], start=1):
            lines.append(f"#### {idx}. {_sanitize_untrusted_text(a['action'])}")
            lines.append(f"- **Rationale**: Grounded in finding _{_sanitize_untrusted_text(a['title'])}_")
            lines.append(f"- **Owner**: **{a['owner']}**")
            lines.append(f"- **Review Timeline**: {a['review']}")
            lines.append("")

    answer_text = "\n".join(lines).strip()
    primary_finding = actions[0]["finding"] if actions else None

    updated_context = {
        "dataset_id": sheet["dataset_id"],
        "sheet_id": sheet["id"],
        "snapshot_hash": snapshot_hash,
        "last_intent": "summary_actions",
        "last_finding": primary_finding,
        "metric": primary_finding.get("metric") if primary_finding else None,
        "dimension": "Department"
    }

    return {
        "status": "success",
        "query_plan": {
            "intent": "summary_actions",
            "source_sheet": sheet["name"],
            "dataset_id": sheet["dataset_id"],
            "sheet_id": sheet["id"]
        },
        "answer": answer_text,
        "evidence": {
            "source_ids": [sheet["id"]],
            "snapshot_hash": snapshot_hash,
            "actions_count": len(actions),
            "calculation_method": "Actions derived deterministically from verified findings and owner assignments.",
            "caveats": ["All actions require domain owner consultation before policy changes."]
        },
        "prior_context": updated_context,
        "citations": [
            {
                "source": f"{sheet['original_name']} / {sheet['name']}",
                "text": f"Grounded actions in findings from snapshot {snapshot_hash}.",
                "type": "decision_brief_snapshot"
            }
        ],
        "suggested_questions": [
            "Why is this action recommended?",
            "What are the main problems?",
            "Give me 3 good points"
        ]
    }


def _execute_followup_why_query(
    plan: AnalyticalQueryPlan,
    candidate_sheets: list[sqlite3.Row],
    cols: list[str],
    rows: list[dict[str, Any]],
    brief: dict[str, Any],
    snapshot_hash: str
) -> dict[str, Any]:
    """Explains underlying data factors for preceding finding/ranking with strict non-causal disclaimer."""
    sheet = candidate_sheets[0]
    p_ctx = plan.prior_context or {}
    last_f = p_ctx.get("last_finding")
    last_rank = p_ctx.get("last_ranking")

    lines = []
    lines.append("### Analytical Context & Non-Causal Explanation")

    if last_f:
        title = last_f.get("title", "")
        detail = last_f.get("detail", {})
        baseline = detail.get("baseline")
        fg = detail.get("focus_group")
        used_rows = detail.get("used_rows")
        total_rows = detail.get("total_rows")
        method = last_f.get("method", detail.get("method", ""))

        lines.append(f"Regarding preceding finding: **{_sanitize_untrusted_text(title)}**\n")
        lines.append("**Underlying Data Factors**:")
        if fg and baseline is not None:
            groups = detail.get("groups", [])
            fg_obj = next((g for g in groups if g.get("group") == fg), None)
            val = fg_obj.get("value") if fg_obj else None
            gap = fg_obj.get("gap") if fg_obj else None
            g_rows = fg_obj.get("used_rows") if fg_obj else None
            if val is not None and gap is not None:
                lines.append(
                    f"- **Group Record Mean**: Recorded **{val:,.2f}** across **{g_rows} valid records** "
                    f"versus the dataset baseline of **{baseline:,.2f}** ({gap:+,.2f} variance)."
                )
            if fg_obj and fg_obj.get("small_sample"):
                lines.append(f"- **Sample Sensitivity**: Group size ({g_rows} records) is small (<5), meaning individual values exert high leverage on the group mean.")
        elif used_rows and total_rows:
            lines.append(f"- **Coverage**: Evaluated across {used_rows} valid records out of {total_rows} total rows.")

        if method:
            lines.append(f"- **Calculation Basis**: {method}")
        lines.append(
            "\n> **Refusal of Causal Inference**:\n"
            "> HighView (powered by HRIDAY) strictly refuses unverified causal claims. Observational data shows *what* occurred, "
            "but cannot establish cause-and-effect (such as employee motivation, managerial competence, or external pressures). "
            "Differences in workload, shift allocation, record completeness, or employee mix may account for this pattern."
        )
        if last_f.get("action"):
            lines.append(f"\n- **Next Investigative Step**: {last_f.get('action')}")

    elif last_rank:
        lines.append("Regarding the preceding ranking evaluation:\n")
        top_d = last_rank[0] if isinstance(last_rank, list) and last_rank else {}
        d_name = top_d.get("department") or top_d.get("group") or "Top target"
        lines.append("- **Ranking Composition**: Evaluated across all distinct segments using dense ranking for ties.")
        lines.append(
            f"\n> **Refusal of Causal Inference**:\n"
            f"> Observational rankings show relative position across observed records, not causation. "
            f"Do not assume {d_name}'s ranking stems from intrinsic underperformance without examining shift schedules, "
            "operational exposure, and baseline comparability."
        )
    else:
        lines.append(
            "To explain *why* a particular variance occurred, please specify which metric or department you are investigating "
            "(for example: 'Why is attendance lower in Engineering?' or 'Why did leaves increase in March?')."
        )

    answer_text = "\n".join(lines).strip()
    return {
        "status": "success",
        "query_plan": {
            "intent": "followup_why",
            "source_sheet": sheet["name"],
            "dataset_id": sheet["dataset_id"],
            "sheet_id": sheet["id"]
        },
        "answer": answer_text,
        "evidence": {
            "source_ids": [sheet["id"]],
            "snapshot_hash": snapshot_hash,
            "preceding_finding_id": last_f.get("id") if last_f else None,
            "calculation_method": "Descriptive variance decomposition. Causal attribution refused.",
            "caveats": ["Descriptive correlation does not prove causation."]
        },
        "prior_context": p_ctx,
        "citations": [
            {
                "source": f"{sheet['original_name']} / {sheet['name']}",
                "text": "Evaluated underlying variance factors while refusing causal claims.",
                "type": "non_causal_statistical_evidence"
            }
        ],
        "suggested_questions": [
            "What should we do?",
            "Show the bottom three",
            "What are the main problems?"
        ]
    }


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
            f"> HighView (powered by HRIDAY) strictly separates descriptive statistical associations from causal explanations. "
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
            f"\n> **Governance Statement**: HighView (powered by HRIDAY) refuses unverified causal claims and does not infer cause-and-effect relationships from observational data."
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
    primary_finding = None
    if dense_ranked:
        first_d = dense_ranked[0]
        primary_finding = {
            "title": f"{first_d['department']}: {metric_display_name} is {label_adjective}",
            "observation": f"{first_d[metric_key]:.2f}{unit_suffix} vs benchmark {org_val:.2f}{unit_suffix}",
            "implication": f"Identifies {first_d['department']} as having the {label_adjective} {metric_display_name}.",
            "action": first_d.get('proposed_action') or f"Review {metric_display_name} with {first_d['department']} leadership.",
            "detail": {
                "groups": dense_ranked,
                "baseline": org_val,
                "focus_group": first_d['department'],
                "used_rows": first_d['headcount'],
                "total_rows": res["total_evaluated_records"]
            }
        }

    updated_context = {
        "dataset_id": sheet["dataset_id"],
        "sheet_id": sheet["id"],
        "snapshot_hash": snapshot_hash,
        "last_intent": plan.intent,
        "metric": plan.metric,
        "dimension": plan.entity_dimension,
        "last_ranking": dense_ranked,
        "last_finding": primary_finding,
        "time_window": period_lbl
    }

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
            "result_grain": "department",
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
        "prior_context": updated_context,
        "citations": [
            {
                "source": f"{sheet['original_name']} / {sheet['name']}",
                "text": f"Evaluated all {res['total_evaluated_records']} records ({distinct_emp} distinct employees) across {len(depts)} departments.",
                "type": "deterministic_full_population"
            }
        ]
    }


def _execute_employee_attendance_query(
    plan: AnalyticalQueryPlan,
    sheet: sqlite3.Row,
    cols: list[str],
    rows: list[dict[str, Any]],
    conn,
    snapshot_hash: str
) -> dict[str, Any]:
    """Executes deterministic employee-level attendance analytics and rankings."""
    df = pd.DataFrame(rows, columns=cols)
    total_records = len(df)

    # 1. Identify primary columns
    id_col = None
    for c in cols:
        c_clean = c.strip().lower().replace(' ', '').replace('_', '')
        if c_clean in ('id', 'employeeid', 'empid', 'staffid'):
            id_col = c
            break
    if not id_col:
        for c in cols:
            if 'id' in c.strip().lower() and not any(k in c.lower() for k in ('valid', 'guid', 'mid', 'paid')):
                id_col = c
                break

    name_col = None
    for c in cols:
        c_clean = c.strip().lower().replace(' ', '').replace('_', '')
        if c_clean in ('fullname', 'employeename', 'name', 'staffname'):
            name_col = c
            break

    dept_col = None
    for c in cols:
        if 'department' in c.strip().lower() or 'dept' in c.strip().lower():
            dept_col = c
            break

    # If no identifier column exists, return specific limitation
    target_id_col = id_col or name_col
    if not target_id_col:
        return {
            "status": "identifier_missing",
            "query_plan": {
                "intent": plan.intent,
                "metric": plan.metric,
                "entity_grain": "employee",
                "source_sheet": sheet["name"],
                "dataset_id": sheet["dataset_id"],
                "sheet_id": sheet["id"]
            },
            "answer": (
                f"### Employee Identifier Not Available\n\n"
                f"Sheet **{sheet['name']}** does not contain an identifiable Employee ID or Name column. "
                "Employee-level calculations require an explicit entity identifier."
            ),
            "evidence": {
                "source_ids": [sheet["id"]],
                "snapshot_hash": snapshot_hash,
                "status": "identifier_missing",
                "result_grain": "employee",
                "caveats": ["No usable employee identifier column found."]
            },
            "citations": []
        }

    # Preserve string ID representation to prevent dropping leading zeros
    if id_col and id_col in df.columns:
        df[id_col] = df[id_col].astype(str).str.strip()

    # 2. Extract periods and resolve attendance measure
    clean_cols = [c for c in cols if not (c.startswith(('interact_', 'interact_mean', 'interact_ratio')) or '+' in c or '_over_' in c or '/' in c)]
    periods = extract_normalized_periods(clean_cols)

    # Validate requested period if specified
    if plan.time_window:
        req_clean = plan.time_window.strip().lower()
        req_month = next((m for m in MONTH_NAMES if m in req_clean), req_clean)
        req_year_m = re.search(r'\b(20\d\d)\b', req_clean)
        req_year = int(req_year_m.group(1)) if req_year_m else None

        avail_periods = []
        for p in periods:
            if req_month not in p.month.lower() and p.month.lower() not in req_clean:
                continue
            if req_year is not None and p.year is not None and p.year != req_year:
                continue
            avail_periods.append(p)
        if not avail_periods:
            avail_months = {p.month for p in periods}
            avail_str = ", ".join(sorted(avail_months)) if avail_months else "None"
            return {
                "status": "period_unavailable",
                "query_plan": {
                    "intent": plan.intent,
                    "metric": plan.metric,
                    "entity_grain": "employee",
                    "time_window": plan.time_window,
                    "source_sheet": sheet["name"],
                    "dataset_id": sheet["dataset_id"],
                    "sheet_id": sheet["id"]
                },
                "answer": (
                    f"### Period Unavailable: {plan.time_window}\n\n"
                    f"The analysis cannot be performed for **{plan.time_window}** because no records for that period exist in the dataset. "
                    f"Available period(s): **{avail_str}**."
                ),
                "evidence": {
                    "source_ids": [sheet["id"]],
                    "snapshot_hash": snapshot_hash,
                    "status": "period_unavailable",
                    "result_grain": "employee",
                    "requested_period": plan.time_window,
                    "available_periods": list(avail_months),
                    "caveats": ["No period substitution allowed."]
                },
                "citations": []
            }
        periods = avail_periods

    # Calculate attendance
    tot_att_col = find_column_by_role(df, ('total attendance', 'total attended', 'monthly attendance'))
    att_cols = [p.attendance_col for p in periods if p.attendance_col and p.attendance_col in df.columns]

    if att_cols:
        for ac in att_cols:
            df[f'__num_{ac}'] = pd.to_numeric(df[ac], errors='coerce')
        df['__calc_att'] = df[[f'__num_{ac}' for ac in att_cols]].sum(axis=1, min_count=1)
    elif tot_att_col:
        df['__calc_att'] = pd.to_numeric(df[tot_att_col], errors='coerce')
    else:
        att_cand = next((c for c in cols if 'attendance' in c.lower() and not c.startswith(('interact', 'leave'))), None)
        if att_cand:
            df['__calc_att'] = pd.to_numeric(df[att_cand], errors='coerce')
        else:
            return {
                "status": "metric_missing",
                "query_plan": {
                    "intent": plan.intent,
                    "metric": plan.metric,
                    "entity_grain": "employee",
                    "source_sheet": sheet["name"],
                    "dataset_id": sheet["dataset_id"],
                    "sheet_id": sheet["id"]
                },
                "answer": (
                    f"### Attendance Metric Not Found\n\n"
                    f"Sheet **{sheet['name']}** does not contain verified attendance columns."
                ),
                "evidence": {
                    "source_ids": [sheet["id"]],
                    "snapshot_hash": snapshot_hash,
                    "status": "metric_missing",
                    "result_grain": "employee",
                    "caveats": ["No attendance metric found."]
                },
                "citations": []
            }

    if tot_att_col and tot_att_col in df.columns:
        df['__tot_num'] = pd.to_numeric(df[tot_att_col], errors='coerce')
        df['__att_days'] = df['__tot_num'].combine_first(df['__calc_att'])
    else:
        df['__att_days'] = df['__calc_att']

    # Calculate approved leaves / absence if present
    tot_leave_col = next((c for c in cols if (any(k == c.strip().lower() or k == c.strip().lower().replace('_', ' ') for k in ('approved leaves', 'approved leave', 'total approved leaves', 'total leaves', 'total leave')) or (any(k in c.strip().lower() for k in ('approved leave', 'approved leaves', 'total leave', 'total leaves')) and not parse_period_column(c)))), None)
    leave_cols = [p.leave_col for p in periods if p.leave_col and p.leave_col in df.columns]

    if leave_cols:
        for lc in leave_cols:
            df[f'__num_{lc}'] = pd.to_numeric(df[lc], errors='coerce')
        df['__calc_leaves'] = df[[f'__num_{lc}' for lc in leave_cols]].sum(axis=1, min_count=1)
    elif tot_leave_col:
        df['__calc_leaves'] = pd.to_numeric(df[tot_leave_col], errors='coerce')
    else:
        leave_cand = next((c for c in cols if ('leave' in c.lower() or 'absent' in c.lower()) and not c.startswith(('interact', 'attendance'))), None)
        if leave_cand:
            df['__calc_leaves'] = pd.to_numeric(df[leave_cand], errors='coerce')
        else:
            df['__calc_leaves'] = pd.Series([None] * len(df), dtype=float)

    if plan.time_window and leave_cols:
        df['__leave_days'] = df['__calc_leaves']
    elif tot_leave_col and tot_leave_col in df.columns:
        df['__tot_leave_num'] = pd.to_numeric(df[tot_leave_col], errors='coerce')
        df['__leave_days'] = df['__tot_leave_num'].combine_first(df['__calc_leaves'])
    else:
        df['__leave_days'] = df['__calc_leaves']

    # Filter out records without usable identifiers
    valid_id_mask = df[target_id_col].notna() & (df[target_id_col].astype(str).str.strip() != '') & (df[target_id_col].astype(str).str.strip() != 'nan')
    df_eval = df[valid_id_mask].copy()

    # Deduplicate employee records if duplicates exist
    if id_col:
        df_eval = df_eval.drop_duplicates(subset=[id_col], keep='first')

    # Exclude non-numeric attendance cells from calculation (do not treat NaN as 0)
    missing_count = int(df_eval['__att_days'].isna().sum())
    valid_df = df_eval.dropna(subset=['__att_days']).copy()
    eligible_count = len(valid_df)
    has_leave_data = bool(valid_df['__leave_days'].notna().any())

    # 3. Apply threshold filtering if specified
    if plan.threshold_operator and plan.threshold_value is not None:
        op = plan.threshold_operator
        val = plan.threshold_value
        if op == '<':
            valid_df = valid_df[valid_df['__att_days'] < val]
        elif op == '<=':
            valid_df = valid_df[valid_df['__att_days'] <= val]
        elif op == '>':
            valid_df = valid_df[valid_df['__att_days'] > val]
        elif op == '>=':
            valid_df = valid_df[valid_df['__att_days'] >= val]
        elif op == '==':
            valid_df = valid_df[valid_df['__att_days'] == val]

    # 4. Deterministic sorting and dense ranking
    reverse_sort = (plan.direction == 'highest')
    sort_cols = ['__att_days']
    ascending_flags = [not reverse_sort]
    if id_col:
        sort_cols.append(id_col)
        ascending_flags.append(True)

    valid_df = valid_df.sort_values(by=sort_cols, ascending=ascending_flags)
    records_list = valid_df.to_dict('records')

    dense_ranked = []
    curr_rank = 1
    for idx, r in enumerate(records_list):
        if idx > 0 and abs(r['__att_days'] - records_list[idx - 1]['__att_days']) > 0.001:
            curr_rank += 1
        r_copy = dict(r)
        r_copy['dense_rank'] = curr_rank
        dense_ranked.append(r_copy)

    # Slice according to ranking limit
    limit = min(plan.ranking_limit or 10, len(dense_ranked))
    sliced = dense_ranked[:limit]

    # 5. Format markdown output
    period_str = f" ({plan.time_window})" if plan.time_window else (f" ({periods[0].month})" if periods else "")
    show_dept = 'Department' in plan.additional_fields and dept_col is not None

    lines = []
    if plan.threshold_operator and plan.threshold_value is not None:
        lines.append(f"### Employees with Attendance {plan.threshold_operator} {plan.threshold_value:.0f} Days{period_str}\n")
        lines.append(f"Evaluated across **{eligible_count} distinct employees** ({len(valid_df)} employees matched threshold).\n")
    elif plan.direction == 'lowest':
        lines.append(f"### Lowest Recorded Attendance Employees{period_str}\n")
        lines.append(f"Evaluated across **{eligible_count} distinct employees** under validated full-population evaluation.\n")
    else:
        lines.append(f"### Highest Recorded Attendance Employees{period_str}\n")
        lines.append(f"Evaluated across **{eligible_count} distinct employees** under validated full-population evaluation.\n")

    if not sliced:
        lines.append("No employees matched the specified criteria.")
    else:
        # Build Markdown table
        headers = ["Rank", "Employee ID"]
        if name_col and name_col != id_col:
            headers.append("Full Name")
        if show_dept:
            headers.append("Department")
        headers.append("Recorded Attendance")
        if has_leave_data:
            headers.append("Approved Leaves")

        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "|".join(["---"] * len(headers)) + "|")

        for r in sliced:
            emp_id = _sanitize_untrusted_text(str(r.get(id_col, 'N/A')))
            row_items = [f"#{r['dense_rank']}", f"**{emp_id}**"]
            if name_col and name_col != id_col:
                emp_name = _sanitize_untrusted_text(str(r.get(name_col, '')))
                row_items.append(emp_name)
            if show_dept:
                d_val = _sanitize_untrusted_text(str(r.get(dept_col, 'N/A')))
                row_items.append(d_val)
            att_val = f"{r['__att_days']:.0f} days" if r['__att_days'] == int(r['__att_days']) else f"{r['__att_days']:.2f} days"
            row_items.append(att_val)
            if has_leave_data:
                lv = r.get('__leave_days')
                if pd.isna(lv):
                    leave_val = "N/A"
                else:
                    leave_val = f"{lv:.0f} days" if lv == int(lv) else f"{lv:.2f} days"
                row_items.append(leave_val)
            lines.append("| " + " | ".join(row_items) + " |")

    lines.append("\n> **Data Governance Limitations**:")
    lines.append("> 1. **Denominators**: Scheduled workday denominators unavailable in source workbook; calculations report validated attended days without fabricated absence percentages.")
    lines.append(f"> 2. **Coverage**: {eligible_count} valid employee records evaluated; {missing_count} missing records excluded.")
    if has_leave_data:
        lines.append("> 3. **Absence Records**: Approved leaves represent formal recorded leave days in source data; unrecorded absences cannot be inferred without scheduled workdays.")

    answer_text = "\n".join(lines)

    # Format updated prior context
    updated_context = {
        "dataset_id": sheet["dataset_id"],
        "sheet_id": sheet["id"],
        "snapshot_hash": snapshot_hash,
        "last_intent": plan.intent,
        "entity_grain": "employee",
        "identifier_col": id_col or target_id_col,
        "metric": "attendance",
        "direction": plan.direction,
        "ranking_limit": plan.ranking_limit or 10,
        "time_window": plan.time_window,
        "additional_fields": plan.additional_fields,
        "threshold_operator": plan.threshold_operator,
        "threshold_value": plan.threshold_value,
        "last_ranking": [{
            "id": str(r.get(id_col, '')),
            "rank": r["dense_rank"],
            "attendance": float(r["__att_days"]),
            **({"approved_leaves": float(r["__leave_days"])} if has_leave_data and pd.notna(r.get("__leave_days")) else {}),
            **({"department": str(r.get(dept_col, ''))} if show_dept else {})
        } for r in sliced]
    }

    return {
        "status": "success",
        "query_plan": {
            "intent": plan.intent,
            "metric": "attendance",
            "direction": plan.direction,
            "entity_grain": "employee",
            "identifier_col": id_col or target_id_col,
            "time_window": plan.time_window,
            "ranking_limit": plan.ranking_limit,
            "additional_fields": plan.additional_fields,
            "threshold_operator": plan.threshold_operator,
            "threshold_value": plan.threshold_value,
            "source_sheet": sheet["name"],
            "dataset_id": sheet["dataset_id"],
            "sheet_id": sheet["id"]
        },
        "answer": answer_text,
        "evidence": {
            "source_ids": [sheet["id"]],
            "snapshot_hash": snapshot_hash,
            "metric_definition": "Recorded attendance days",
            "result_grain": "employee",
            "calculation_method": "Full-population sum of period attendance and total attendance per employee record.",
            "coverage": {
                "total_records": total_records,
                "distinct_employees": eligible_count,
                "missing_records": missing_count,
                "displayed_rows": len(sliced)
            },
            "caveats": [
                "Scheduled workday denominators unavailable; calculations report validated attended days.",
                "Dense ranking preserves ties; identifier tiebreaker used for deterministic ordering."
            ]
        },
        "raw_analysis": {
            "entity_grain": "employee",
            "metric": "attendance",
            "direction": plan.direction,
            "rows": [{
                "id": str(r.get(id_col, '')),
                "rank": r["dense_rank"],
                "attendance": float(r["__att_days"]),
                **({"approved_leaves": float(r["__leave_days"])} if has_leave_data and pd.notna(r.get("__leave_days")) else {}),
                **({"department": str(r.get(dept_col, ''))} if show_dept else {})
            } for r in sliced]
        },
        "prior_context": updated_context,
        "citations": [
            {
                "source": f"{sheet['original_name']} / {sheet['name']}",
                "text": f"Evaluated {eligible_count} distinct employees across source records.",
                "type": "deterministic_employee_evaluation"
            }
        ],
        "suggested_questions": [
            "i need employee id",
            "only top 3",
            "show department also",
            "who came less than 10 days?"
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
    primary_finding = None
    if dense_groups:
        first_g = dense_groups[0]
        primary_finding = {
            "title": f"{first_g['group']}: {metric_lbl} is {label_adjective}",
            "observation": f"{first_g['value']:,.2f} vs benchmark {baseline:,.2f} ({first_g.get('gap', 0):+,.2f} gap)",
            "implication": "Identifies an operational segment to investigate.",
            "action": f"Review {metric_lbl} with {first_g['group']} leadership.",
            "detail": {
                "groups": dense_groups,
                "baseline": baseline,
                "focus_group": first_g['group'],
                "used_rows": first_g['used_rows'],
                "total_rows": len(df)
            }
        }

    updated_context = {
        "dataset_id": sheet["dataset_id"],
        "sheet_id": sheet["id"],
        "snapshot_hash": snapshot_hash,
        "last_intent": plan.intent,
        "metric": metric_col,
        "dimension": dim_col,
        "last_ranking": dense_groups,
        "last_finding": primary_finding,
        "time_window": plan.time_window
    }

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
        "raw_analysis": {"groups": dense_groups, "baseline": baseline, "metric": metric_col},
        "prior_context": updated_context,
        "citations": [
            {
                "source": f"{sheet['original_name']} / {sheet['name']}",
                "text": f"Evaluated {len(valid_metric)} valid records across {len(groups)} {dim_col} groups.",
                "type": "deterministic_group_comparison"
            }
        ]
    }
