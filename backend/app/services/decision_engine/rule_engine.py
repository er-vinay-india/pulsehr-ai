"""Rule-based, high-speed deterministic decision engine for PulseHR AI Copilot."""

import re
from typing import Any
from .base import DecisionEngine, DecisionResult


class RuleDecisionEngine(DecisionEngine):
    """Zero-latency rule engine classifying analytical queries using compiled regex and entity parsers."""

    def __init__(self):
        self.num_map = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5}

    def classify(self, query: str, context: dict[str, Any] | None = None) -> DecisionResult:
        q = query.strip().lower()
        active_context = context or {}

        # 1. Follow-up "why?" queries
        if q.strip('?!. ') in ('why', 'why is that', 'why did that happen', 'why is this', 'explain why', 'tell me why') or \
           (q.startswith('why') and len(q.split()) <= 4 and (active_context.get('last_finding') or active_context.get('last_ranking') or active_context.get('metric'))):
            return DecisionResult(
                intent='followup_why',
                confidence=0.96,
                extracted_entities={'query': query},
                reasoning_required=False,  # Answered from verified factors/Simpson's paradox
                suggested_role=None,       # Deterministic resolution first
                engine_name='rule_engine',
                metadata={'matched_pattern': 'followup_why'}
            )

        # 2. Business Summary: Positives ("give me 3 good points", "strengths", "highlights")
        count_match_pos = re.search(r'\b(\d+|three|two|four|five|one)\s+(?:good|positive|strength|highlight)', q)
        if count_match_pos or any(k in q for k in (
            '3 good points', 'three good points', 'good points', 'positive points', 'positive findings',
            'what is going well', "what's going well", 'key strengths', 'highlights', 'positive highlights'
        )):
            count = 3
            if count_match_pos:
                raw_c = count_match_pos.group(1)
                count = int(raw_c) if raw_c.isdigit() else self.num_map.get(raw_c, 3)
            return DecisionResult(
                intent='summary_positives',
                confidence=0.95,
                extracted_entities={'count': count},
                reasoning_required=False,
                suggested_role=None,  # Pure deterministic snapshot resolution
                engine_name='rule_engine',
                metadata={'matched_pattern': 'summary_positives'}
            )

        # 3. Business Summary: Concerns / Problems ("main problems", "critical issues", "risk points")
        count_match_neg = re.search(r'\b(\d+|three|two|four|five|one)\s+(?:problem|concern|issue|risk|weakness|challenge|headwind)', q)
        if count_match_neg or any(k in q for k in (
            'main problems', 'problems', 'main issues', 'key issues', 'critical issues',
            'concerns', 'main concerns', 'risk points', 'weaknesses', 'what is going poorly',
            "what's going poorly", 'challenges', 'headwinds'
        )):
            count = 3
            if count_match_neg:
                raw_c = count_match_neg.group(1)
                count = int(raw_c) if raw_c.isdigit() else self.num_map.get(raw_c, 3)
            return DecisionResult(
                intent='summary_concerns',
                confidence=0.95,
                extracted_entities={'count': count},
                reasoning_required=False,
                suggested_role=None,
                engine_name='rule_engine',
                metadata={'matched_pattern': 'summary_concerns'}
            )

        # 4. Business Summary: Actions ("what should we do?", "recommended actions", "next steps")
        if any(k in q for k in (
            'what should we do', 'what do we do', 'recommended actions', 'recommended action',
            'recommendations', 'what are the next steps', 'next steps', 'how to fix', 'how should we respond',
            'action items', 'actionable insights'
        )):
            return DecisionResult(
                intent='summary_actions',
                confidence=0.94,
                extracted_entities={},
                reasoning_required=False,
                suggested_role=None,
                engine_name='rule_engine',
                metadata={'matched_pattern': 'summary_actions'}
            )

        # 5. Correlation / Causation Queries
        if any(k in q for k in ('does', 'cause', 'lead to', 'impact of', 'affect', 'correlation between', 'relationship between')):
            return DecisionResult(
                intent='correlation',
                confidence=0.88,
                extracted_entities={'query': query},
                reasoning_required=True,
                suggested_role='ANALYST',
                engine_name='rule_engine',
                metadata={'matched_pattern': 'correlation'}
            )

        # 6. Evaluative Worst / Best Queries
        is_worst = bool(re.search(r'\b(worst|lowest|bottom|lagging|least)\b', q))
        is_best = bool(re.search(r'\b(best|highest|top|leading|most)\b', q))
        if is_worst or is_best:
            intent = 'ranking_lowest' if is_worst else 'ranking_highest'
            return DecisionResult(
                intent=intent,
                confidence=0.90,
                extracted_entities={'direction': 'lowest' if is_worst else 'highest'},
                reasoning_required=False,
                suggested_role='ANALYST',
                engine_name='rule_engine',
                metadata={'matched_pattern': intent}
            )

        # 7. Breakdown / Distribution Queries
        if any(k in q for k in ('breakdown', 'distribution', 'by department', 'by store', 'by region', 'per role')):
            return DecisionResult(
                intent='breakdown',
                confidence=0.86,
                extracted_entities={},
                reasoning_required=False,
                suggested_role='ANALYST',
                engine_name='rule_engine',
                metadata={'matched_pattern': 'breakdown'}
            )

        # 8. Metadata / Schema Queries
        if any(k in q for k in ('list columns', 'show schema', 'what sheets', 'column names', 'field names', 'available metrics')):
            return DecisionResult(
                intent='metadata_lookup',
                confidence=0.92,
                extracted_entities={},
                reasoning_required=False,
                suggested_role='FAST',
                engine_name='rule_engine',
                metadata={'matched_pattern': 'metadata_lookup'}
            )

        # 9. General Query Fallback
        return DecisionResult(
            intent='general_query',
            confidence=0.50,
            extracted_entities={},
            reasoning_required=True,
            suggested_role='ANALYST',
            engine_name='rule_engine',
            metadata={'matched_pattern': 'fallback'}
        )
