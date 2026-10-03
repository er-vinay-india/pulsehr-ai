"""Dataset intent/evidence boundary over HighView's existing analytical services."""
from dataclasses import dataclass
import logging
import math
import re
from .dataset_context import DatasetContextProvider
from ..gateway.assistant_identity import identity_intent
from ..data_engine.semantic_classifier import SemanticClassifier
from ..data_engine.candidate_fact_discovery import CandidateFactDiscoveryEngine
from ..data_engine.opportunity_map import OpportunityMapGenerator
from ..data_engine.interestingness_ranker import FactInterestingnessRanker
from ..data_engine.analysis_context import AnalysisContext, BusinessRule, IntentDataReconciler
from .generic_copilot_engine import GenericCopilotEngine
from ..copilot_query_planner import plan_analytical_query, execute_analytical_plan

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DatasetIntent:
    intent: str = 'GENERAL_CHAT'
    requested_fact_count: int = 5

    @property
    def requires_dataset(self):
        return self.intent != 'GENERAL_CHAT'


def classify_dataset_intent(query):
    q = query.lower().strip().rstrip('?! .')
    if identity_intent(query) or re.match(r'(?:what is|explain|define) (?:machine learning|artificial intelligence|deepseek|qwen|gemma|a neural network|regression)\b', q):
        return DatasetIntent()
    anchor = bool(re.search(r'\b(?:data|dataset|sheet|records|columns?|department|employees?|attendance|compliance|office|overtime|sales|revenue|profit|stores?|region|scrap|defects?)\b', q))
    facts = re.search(r'\b(?:(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+)?(?:facts|findings|insights)\b', q)
    if facts and (anchor or not re.search(r'\babout\b', q)) or q in ('what stands out', 'what should i know', 'surprise me', 'top findings', 'key facts'):
        count = facts.group(1) if facts else None
        words = dict(zip(['one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'], range(1, 11)))
        n = int(count) if count and count.isdigit() else words.get(count, 5)
        return DatasetIntent('DATASET_FACT_QUERY', min(10, max(1, n)))
    if re.search(r'\b(?:summari[sz]e|summary|overview)\b', q) and (anchor or q in ('summary', 'overview', 'summarize', 'summarise')):
        return DatasetIntent('DATASET_SUMMARY')
    if re.search(r'\b(?:columns?|schema|data types)\b', q):
        return DatasetIntent('DATASET_COLUMN_QUERY')
    if not anchor:
        return DatasetIntent()
    if re.search(r'\b(?:chart|plot|visuali[sz]e|graph)\b', q):
        return DatasetIntent('DATASET_VISUAL_QUERY')
    if re.search(r'\b(?:where|filter|only|at least)\b|[<>]=?', q):
        return DatasetIntent('DATASET_FILTER_QUERY')
    if re.search(r'\b(?:compare|comparison|versus|vs|difference)\b', q):
        return DatasetIntent('DATASET_COMPARISON')
    if re.search(r'\b(?:highest|lowest|average|mean|total|sum|count|how many|maximum|minimum|median|compliance)\b', q):
        return DatasetIntent('DATASET_AGGREGATION')
    return DatasetIntent('DATASET_DRILLDOWN')


def _safe_text(value):
    # Dataset labels are untrusted content, not Markdown or executable instructions.
    return str(value).replace('\n', ' ').replace('\r', ' ').replace('`', '').replace('*', '').replace('<', '&lt;').replace('>', '&gt;')


class DatasetQueryEngine:
    @classmethod
    def execute(cls, query, intent, dataset, *, prior_context=None, conversation_id=None):
        binding = dataset.binding() if dataset else None
        metadata = {'intent': intent.intent, 'requested_fact_count': intent.requested_fact_count,
                    'dataset_context_found': dataset is not None, 'evidence_retrieval_failed': False,
                    'conversation_id': conversation_id, **(binding or {})}
        evidence = []
        charts = []
        prior = None
        runtime = None
        status = 'success'
        try:
            if dataset is None:
                answer = 'There is currently no active dataset. Open or upload a dataset in HighView, then ask your question again.'
                status = 'no_active_dataset'
            elif dataset.context_error:
                raise ValueError(dataset.context_error)
            elif intent.intent in ('DATASET_FACT_QUERY', 'DATASET_SUMMARY'):
                evidence = cls.facts(dataset, intent.requested_fact_count)
                n = len(evidence)
                if n:
                    opening = f'Here are {n} verified facts from {_safe_text(dataset.name)}:' if n == intent.requested_fact_count else f'I found {n} reliable facts from the current analysis of {_safe_text(dataset.name)}:'
                    answer = opening + '\n\n' + '\n'.join(f"{i}. {e['statement']} [{e['fact_id']}]" for i, e in enumerate(evidence, 1))
                else:
                    answer = 'The dataset is attached, but the current analysis contains no reliable facts for this request.'
                    status = 'insufficient_evidence'
            elif intent.intent == 'DATASET_COLUMN_QUERY':
                answer = f'{_safe_text(dataset.name)} has {len(dataset.columns)} columns:\n\n' + '\n'.join(f'- {_safe_text(c)}' for c in dataset.columns)
                evidence = [{'fact_id': 'schema', 'statement': answer, 'source': 'persisted_schema', 'source_sheet_ids': [dataset.sheet_id]}]
            else:
                result = cls.query_existing_analytics(query, dataset, prior_context)
                answer = result['answer']
                evidence = result.get('evidence_items', [])
                charts = result.get('visual_charts', [])
                prior = result.get('prior_context')
                runtime = result.get('runtime_model')
                status = result.get('status', status)
        except Exception as exc:
            # Log type/status only; raw rows and exception values can contain sensitive cells.
            metadata.update(evidence_retrieval_failed=True, reason=type(exc).__name__)
            answer = 'The dataset is attached, but I could not retrieve its analytical context. Please try again or refresh the analysis.'
            status = 'analytical_context_unavailable'
        metadata.update(evidence_items=len(evidence), model=runtime)
        logger.info('Dataset chat request: %s', metadata)
        return {'query': query, 'answer': answer, 'engine': 'dataset_query', 'intent': intent.intent,
                'dataset_context': binding, 'evidence': evidence, 'runtime_model': runtime,
                'model_used': runtime or 'HighView verified analytics', 'status': status, 'metadata': metadata,
                'citations': [{'fact_id': e['fact_id'], 'type': e.get('source', 'verified_analytics'), 'sheet_id': dataset.sheet_id} for e in evidence],
                'visual_charts': charts, 'prior_context': prior, 'suggested_questions': [],
                'timings': {'is_deterministic': runtime is None}, 'exact_matches': [], 'related_rows': dataset.record_count if dataset else 0}

    @staticmethod
    def _candidate(fact, dataset):
        return {'fact_id': fact.fact_id, 'statement': _safe_text(fact.statement), 'metric': fact.metric,
                'value': fact.value, 'source': 'candidate_fact', 'source_columns': fact.source_columns,
                'source_sheet_ids': [dataset.sheet_id], 'snapshot': dataset.snapshot_id,
                'calculation_method': fact.calculation_method}

    @classmethod
    def facts(cls, dataset, count):
        # Prefer persisted numeric profiles/EDA first. No row loading or LLM is needed.
        evidence = []
        for p in dataset.column_profiles:
            numeric = p.get('numeric', {})
            mean = numeric.get('mean')
            if isinstance(mean, (int, float)) and math.isfinite(mean) and p.get('nonempty', 0) > 0:
                col = p['column']
                evidence.append({'fact_id': f'profile:{col}:mean', 'statement': f"The average {_safe_text(p.get('display_name') or col)} is {mean:,.2f} across {p['nonempty']} nonempty records.",
                    'metric': col, 'value': mean, 'source': 'persisted_column_profile', 'source_columns': [col], 'source_sheet_ids': [dataset.sheet_id],
                    'snapshot': dataset.snapshot_id, 'calculation_method': 'stored mean of valid source values'})
            if len(evidence) >= count:
                return evidence
        if dataset.record_count > 20000:
            return evidence  # Do not materialize a large dataset just to reach a requested count.
        from ..adaptive_dashboard.findings import get_shared_findings_for_sheet
        findings = get_shared_findings_for_sheet(dataset.sheet_id)
        for f in findings:
            if f.status != 'available' or dataset.sheet_id not in f.source_sheet_ids or f.allowed_claim_level not in ('descriptive_fact', 'reconciled_ledger'):
                continue
            evidence.append({'fact_id': f.finding_id, 'statement': _safe_text(f.evidence_bound_observation),
                'value': f.typed_value, 'source': 'shared_findings', 'source_sheet_ids': f.source_sheet_ids,
                'snapshot': f.snapshot, 'calculation_id': f.calculation_id, 'limitations': f.limitations})
            if len(evidence) >= count:
                return evidence
        # Reuse the existing discovery engine when pre-existing analytical output is insufficient.
        frame = dataset.frame()
        if frame.empty:
            return evidence
        profile = SemanticClassifier.profile_dataset(frame, dataset.name)
        facts, _ = CandidateFactDiscoveryEngine.discover_facts(frame, profile, OpportunityMapGenerator.generate(profile, context=dataset.analysis_context))
        for ranked in FactInterestingnessRanker.rank_interesting_facts(facts, limit=count):
            f = ranked.fact
            if f.statement and f.reliability_status == 'reliable' and f.sample_size > 0 and not any(e.get('metric') == f.metric and e.get('value') == f.value for e in evidence):
                evidence.append(cls._candidate(f, dataset))
            if len(evidence) >= count:
                break
        return evidence[:count]

    @classmethod
    def query_existing_analytics(cls, query, dataset, prior_context):
        q = query.lower()
        # Existing planner handles exact group comparisons, trends and contextual drilldowns.
        # Compliance requires an explicit threshold or existing business rule; never treat days as a percentage.
        if 'compliance' not in q:
            plan = plan_analytical_query(query, dataset_id=dataset.dataset_id, sheet_id=dataset.sheet_id, prior_context=prior_context)
            if plan:
                result = execute_analytical_plan(plan)
                raw = result.get('evidence') or {}
                return {**result, 'evidence_items': [{'fact_id': raw.get('calculation_id', 'analytical_query'), 'statement': result['answer'],
                    'source': 'analytical_query_planner', 'source_sheet_ids': [dataset.sheet_id], 'detail': raw}]}
        frame = dataset.frame()
        profile = SemanticClassifier.profile_dataset(frame, dataset.name)
        context = dataset.analysis_context
        if 'compliance' in q:
            metric = IntentDataReconciler._find_matching_column('office', profile) or IntentDataReconciler._find_matching_column('wfo', profile)
            threshold = re.search(r'\b(\d+(?:\.\d+)?)[ -]days?\b', q)
            if threshold and metric:
                context = (context or AnalysisContext()).model_copy(deep=True)
                context.business_rules = [BusinessRule(metric=metric, threshold=float(threshold.group(1)), description='Threshold explicitly requested in this question')]
            if not context or not context.business_rules:
                return {'answer': 'Which office-compliance threshold should I use? The dataset is attached, but a compliance rule is not defined.', 'status': 'clarification_required'}
        facts, _ = CandidateFactDiscoveryEngine.discover_facts(frame, profile, OpportunityMapGenerator.generate(profile, context=context))
        grounded = GenericCopilotEngine.answer_query(frame, profile, user_query=query, facts=facts, context=context)
        return {'answer': grounded.answer_markdown, 'evidence_items': [cls._candidate(f, dataset) for f in grounded.cited_facts],
                'runtime_model': grounded.metadata.get('runtime_model'),
                'visual_charts': [grounded.recommended_chart.model_dump()] if grounded.recommended_chart else []}
