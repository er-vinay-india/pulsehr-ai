"""Bounded factual input for presentation writers; references are not findings."""
from __future__ import annotations

from .director_models import InformationSourceType, InformationUnit, PresentationPlanningContext


def evidence_context(ctx: PresentationPlanningContext, units: list[InformationUnit]) -> dict:
    fields = (
        'evidence_id', 'title', 'finding', 'statement', 'metric_name', 'metric_value',
        'numeric_value', 'unit', 'denominator', 'comparison', 'date_range',
        'source_sheets', 'calculation_methodology', 'what_it_establishes',
        'what_it_does_not_establish', 'limitations', 'finding_type',
    )
    facts = []
    for item in ctx.current_evidence[:24]:
        fact = {key: item[key] for key in fields if key in item and item[key] is not None}
        facts.append({key: value[:1200] if isinstance(value, str) else value for key, value in fact.items()})
    return {
        'dataset': ctx.dataset_label, 'reporting_period': ctx.reporting_period,
        'records': ctx.total_records, 'non_empty_cells_pct': ctx.completeness_pct,
        'findings': facts,
        'information_units': [
            {'id': unit.id, 'title': unit.title, 'statement': unit.statement[:1200],
             'metrics': unit.metrics, 'evidence_id': unit.evidence_id,
             'source': unit.source_type.value, 'destination': unit.destination.value}
            for unit in units[:24]
        ],
    }


def factual_thesis(ctx: PresentationPlanningContext) -> str:
    for fact in ctx.current_evidence:
        if fact.get('numeric_value') is not None and fact.get('finding_type', 'measured_fact') == 'measured_fact':
            label = fact.get('metric_name') or fact.get('title')
            value = fact.get('metric_value')
            if label and value is not None:
                return f"{label}: {value}"
    return f"{ctx.dataset_label or ctx.domain} review for {ctx.reporting_period or 'the available reporting period'}"
