"""Coordinator-owned interpretation; workers execute the resulting plan unchanged."""
import json
import re

import pandas as pd

from .. import copilot_query_planner as planner
from ..semantic_mapping import ATTENDANCE_ALIASES, SemanticField, infer_semantic_catalog, is_identity_header
from ..hr_period_analytics import extract_normalized_periods
from .coordinator_models import EnrichedAnalyticalRequest, ExecutionRoute
from .response_formatter import decide_response_detail


def normalize(text):
    words = re.findall(r'[a-z0-9]+', str(text).lower())
    return ' '.join(w for w in words if w not in {'the', 'a', 'an'})


def generated_column(name):
    return str(name).lower().startswith('interact_')


def field_definition(field):
    # Keep interpretation prompts small; records and numerical profiles are not
    # needed to choose a measure and must not become model-computed evidence.
    return {key: value for key, value in field.to_dict().items() if key in
            ('name', 'field_role', 'business_label', 'aliases', 'units', 'unresolved_definition')}


def _matched_field(query, fields):
    text = f' {normalize(query)} '
    matches = []
    for field in fields:
        for alias in [field.name, field.business_label, *field.aliases]:
            term = normalize(alias)
            if term and f' {term} ' in text:
                matches.append((len(term.split()), field))
    if not matches:
        return None
    longest = max(length for length, _ in matches)
    winners = {f.name: f for length, f in matches if length == longest}
    return next(iter(winners.values())) if len(winners) == 1 else None


def _metric_key(field):
    aliases = {normalize(a) for a in field.aliases}
    if field.units == 'days':
        if 'final attendance' in aliases:
            return 'final_attendance'
        if 'attendance' in aliases:
            return 'attendance'
        if 'approved leaves' in aliases:
            return 'leaves'
    return field.name


def enrich_analytical_request(query, prior_context, df, dataset_id, sheet_id, route_contract, resolve_model, model_already_used=False):
    """Resolve field meanings against server metadata, with at most one model mapping.

    The model receives definitions, never records or authority to change the source.
    Existing deterministic parsing handles filters, periods, limits and operations.
    """
    frame = df
    if sheet_id is not None and dataset_id is None:
        with planner.get_connection() as conn:
            source = conn.execute('SELECT dataset_id FROM sheets WHERE id=?', (sheet_id,)).fetchone()
            if source:
                dataset_id = source['dataset_id']
    if frame is None and (sheet_id is not None or dataset_id is not None):
        with planner.get_connection() as conn:
            sources = planner._resolve_candidate_sheets(conn, dataset_id, sheet_id)
            if sources:
                source = sources[0]
                sheet_id, dataset_id = source['id'], source['dataset_id']
                rows = conn.execute('SELECT data_json FROM sheet_rows WHERE sheet_id=? ORDER BY row_index LIMIT 200', (sheet_id,)).fetchall()
                frame = pd.DataFrame([json.loads(r[0]) for r in rows], columns=json.loads(source['columns_json']))

    fields = []
    schema_hash = None
    if frame is not None:
        columns = [c for c in frame.columns if not generated_column(c)]
        catalog = infer_semantic_catalog(columns, records=frame[columns].head(200).to_dict('records'))
        schema_hash = catalog.get_catalog_hash()
        fields = list(catalog.fields.values())
    measures = [f for f in fields if f.field_role in ('measure', 'derived_total') and not is_identity_header(f.name)]
    dimensions = [f for f in fields if f.field_role == 'dimension' and not is_identity_header(f.name)]
    periods = extract_normalized_periods(list(frame.columns)) if frame is not None else []
    attendance_columns = [p.attendance_col for p in periods if p.attendance_col]
    if attendance_columns and not any(_metric_key(f) == 'attendance' for f in measures):
        measures.append(SemanticField(name='Recorded period attendance', field_role='measure',
            business_label='Recorded attendance days from period totals', aliases=list(ATTENDANCE_ALIASES),
            units='days', aggregation_rule='mean', grain='employee_month'))
    measure = _matched_field(query, measures)
    dimension = _matched_field(query, dimensions)
    prior = dict(prior_context or {})
    if ((prior.get('sheet_id') is not None and sheet_id is not None and prior['sheet_id'] != sheet_id)
            or (prior.get('dataset_id') is not None and dataset_id is not None and prior['dataset_id'] != dataset_id)):
        prior = {}
    if measure:
        # An explicit current measure takes precedence over conversational history.
        prior.pop('metric', None)
        prior.pop('visualization_context', None)
    elif prior.get('metric') and fields:
        valid_metrics = {normalize(_metric_key(f)) for f in measures} | {normalize(f.name) for f in measures} | {'headcount'}
        if normalize(prior['metric']) not in valid_metrics:
            prior = {}

    plan = planner.plan_analytical_query(query, dataset_id=dataset_id, sheet_id=sheet_id,
        prior_context=prior or None, allow_model_planning=False)
    if plan and fields:
        plan = plan.model_copy(update={'available_metrics': [f.name for f in measures],
                                      'available_dimensions': [f.name for f in dimensions]})
    method = 'deterministic'
    bindings = {}

    def field_for(value, candidates):
        return next((f for f in candidates if normalize(value) in {
            normalize(f.name), normalize(f.business_label), *[normalize(a) for a in f.aliases],
            normalize(_metric_key(f))
        }), None) if isinstance(value, str) else None

    if plan and plan.intent in ('ranking', 'breakdown', 'ambiguity_clarification'):
        if measure and dimension:
            plan = plan.model_copy(update={'intent': 'ranking' if plan.intent == 'ambiguity_clarification' else plan.intent,
                'metric': _metric_key(measure), 'entity_dimension': dimension.name,
                'clarification_question': None})
            bindings = {'metric': measure.name, 'grouping': dimension.name}
            method = 'semantic_catalog'

        # A bare "best department" has no measure meaning to enrich. A model
        # must not supply a default just because several metrics are available.
        cue_words = set(normalize(query).split())
        for f in dimensions:
            cue_words -= set(normalize(f.name).split())
        cue_words -= {'which', 'what', 'who', 'has', 'have', 'is', 'are', 'had', 'department', 'dept',
            'best', 'worst', 'highest', 'lowest', 'most', 'least', 'top', 'bottom', 'performing',
            'performance', 'overall', 'in', 'of', 'our', 'by', 'and', 'please', 'show', 'me'}
        cue_words = {w for w in cue_words if not w.isdigit()}
        if (plan.intent == 'ambiguity_clarification' or not plan.metric) and cue_words and measures:
            compact = {
                'source': {'sheet_id': sheet_id, 'dataset_id': dataset_id},
                'measures': [field_definition(f) for f in measures],
                'dimensions': [field_definition(f) for f in dimensions],
                'draft_plan': {k: v for k, v in plan.model_dump().items() if k != 'prior_context'},
                'required_resolution': 'Map the requested measure and grouping to available fields. Do not choose a default business performance measure.',
            }
            if route_contract and route_contract.entities:
                contract = route_contract
            elif model_already_used:
                contract = None
            else:
                contract = resolve_model(query, prior or None, [f.name for f in fields], compact)
            if contract and contract.route == ExecutionRoute.DATASET_ENGINE and contract.confidence >= .8:
                entities = contract.entities
                proposed_measure = field_for(entities.get('metric'), measures)
                proposed_dimension = field_for(entities.get('group_by', entities.get('dimension')), dimensions) or dimension
                if proposed_measure and proposed_dimension and not proposed_measure.unresolved_definition:
                    plan = plan.model_copy(update={'intent': 'ranking', 'metric': _metric_key(proposed_measure),
                        'entity_dimension': proposed_dimension.name, 'clarification_question': None})
                    bindings = {'metric': proposed_measure.name, 'grouping': proposed_dimension.name}
                    method = 'coordinator_model'

        if plan.metric and measures:
            resolved_measure = field_for(plan.metric, measures)
            resolved_dimension = field_for(plan.entity_dimension, dimensions)
            # Headcount is a verified count capability, not an invented measure.
            if (not resolved_measure and plan.metric != 'headcount') or not resolved_dimension:
                plan = plan.model_copy(update={'intent': 'ambiguity_clarification', 'metric': None})
            elif resolved_measure:
                bindings = {'metric': resolved_measure.name, 'grouping': resolved_dimension.name}

    if plan is None:
        return None
    if plan.intent == 'ambiguity_clarification':
        method = 'clarification'
        bindings = {}
        plan = plan.model_copy(update={'available_metrics': [f.name for f in measures],
            'clarification_question': 'Which recorded measure should I compare? Available measures: '
                + (', '.join(f.name for f in measures) or 'none in this scope') + '.'})
    basis = 'Average recorded attendance days per employee; ties share rank.' if plan.metric == 'attendance' else None
    if bindings and method in ('semantic_catalog', 'coordinator_model'):
        plan = plan.model_copy(update={'explanation': f"Coordinator resolved {bindings['metric']} grouped by {bindings['grouping']} ({plan.direction} first). " + (basis or '')})
    source_columns = attendance_columns if bindings.get('metric') == 'Recorded period attendance' else list(bindings.values())
    if plan.metric == 'attendance' and not plan.time_window and len({p.month for p in periods}) == 1:
        plan = plan.model_copy(update={'time_window': periods[0].month})

    detail_setting = decide_response_detail(
        query=query,
        plan_intent=plan.intent if plan else None,
        ranking_limit=getattr(plan, 'ranking_limit', 1) if plan else 1
    )
    plan = plan.model_copy(update={'response_detail': detail_setting})

    return EnrichedAnalyticalRequest(
        original_query=query,
        plan=plan.model_dump(),
        response_detail=detail_setting,
        field_bindings=bindings,
        available_measures=[f.name for f in measures],
        resolution_method=method,
        schema_hash=schema_hash,
        aggregation_basis=basis,
        source_columns=source_columns
    )


def routing_semantics(df, dataset_id, sheet_id):
    """Compact business definitions for the first and only control-plane call."""
    if df is None:
        return {'source': {'dataset_id': dataset_id, 'sheet_id': sheet_id}}
    columns = [c for c in df.columns if not generated_column(c)]
    catalog = infer_semantic_catalog(columns, records=df[columns].head(200).to_dict('records'))
    return {'source': {'dataset_id': dataset_id, 'sheet_id': sheet_id},
            'field_definitions': [field_definition(f) for f in catalog.fields.values()],
            'record_count': len(df)}
