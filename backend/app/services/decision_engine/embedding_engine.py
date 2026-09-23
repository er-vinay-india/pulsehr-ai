"""Vector embedding-based decision engine using local Ollama embeddings with rule fallback."""

import logging
import math
from typing import Any
import httpx

from ...core import config
from .base import DecisionEngine, DecisionResult
from .rule_engine import RuleDecisionEngine

logger = logging.getLogger(__name__)

INTENT_PROTOTYPES = {
    'summary_positives': [
        'give me 3 good points',
        'what are our main positive highlights and strengths',
        'what is going well across departments',
        'show positive business findings'
    ],
    'summary_concerns': [
        'what are the main problems and headwinds',
        'critical business risks and warning areas',
        'key concerns and underperforming segments',
        'where are we experiencing losses or friction'
    ],
    'summary_actions': [
        'what should we do next to improve this',
        'recommended management actions and interventions',
        'what are the concrete next steps for leadership',
        'how do we solve this issue'
    ],
    'followup_why': [
        'why did that happen',
        'why is that the case',
        'can you explain why this metric changed',
        'what is the reason behind this trend'
    ],
    'ranking_lowest': [
        'which department is the worst',
        'lowest performing segment or store',
        'bottom ranked units by metric'
    ],
    'ranking_highest': [
        'which department is the best',
        'top performing store or team',
        'highest ranked entities'
    ],
    'correlation': [
        'does this metric cause that outcome',
        'is there a correlation between x and y',
        'relationship between two business factors'
    ],
    'metadata_lookup': [
        'list all available columns and fields',
        'what sheets and datasets are uploaded',
        'display dataset schema and structure'
    ]
}


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Computes cosine similarity between two float vectors."""
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


class EmbeddingDecisionEngine(DecisionEngine):
    """Vector similarity classification against intent prototypes with seamless rule fallback."""

    def __init__(self, embedding_model: str = "nomic-embed-text:latest"):
        self.embedding_model = embedding_model
        self.fallback_engine = RuleDecisionEngine()
        self._prototype_cache: dict[str, list[list[float]]] = {}

    def _get_embedding(self, text: str) -> list[float] | None:
        """Fetches vector embedding for text from local Ollama instance."""
        try:
            with httpx.Client(timeout=3.0) as client:
                resp = client.post(
                    f"{config.OLLAMA_BASE_URL}/api/embeddings",
                    json={"model": self.embedding_model, "prompt": text}
                )
                if resp.status_code == 200:
                    return resp.json().get("embedding")
        except Exception as exc:
            logger.debug(f"Ollama embedding fetch failed: {exc}")
        return None

    def _ensure_prototypes(self) -> bool:
        """Ensures prototypes are embedded and cached."""
        if self._prototype_cache:
            return True
        for intent, examples in INTENT_PROTOTYPES.items():
            vectors = []
            for ex in examples:
                vec = self._get_embedding(ex)
                if vec:
                    vectors.append(vec)
            if vectors:
                self._prototype_cache[intent] = vectors
        return bool(self._prototype_cache)

    def classify(self, query: str, context: dict[str, Any] | None = None) -> DecisionResult:
        # 1. Try vector classification
        query_vec = self._get_embedding(query)
        if query_vec and self._ensure_prototypes():
            best_intent = 'general_query'
            best_sim = -1.0
            for intent, proto_vecs in self._prototype_cache.items():
                for p_vec in proto_vecs:
                    sim = cosine_similarity(query_vec, p_vec)
                    if sim > best_sim:
                        best_sim = sim
                        best_intent = intent

            if best_sim >= 0.70:
                is_summary = best_intent.startswith('summary_')
                return DecisionResult(
                    intent=best_intent,
                    confidence=round(best_sim, 3),
                    extracted_entities={},
                    reasoning_required=not is_summary and best_intent not in ('ranking_lowest', 'ranking_highest'),
                    suggested_role=None if is_summary else 'ANALYST',
                    engine_name='embedding_engine',
                    metadata={'best_similarity': round(best_sim, 3), 'embedding_model': self.embedding_model}
                )

        # 2. Fallback to rule engine
        fallback_res = self.fallback_engine.classify(query, context)
        fallback_res.metadata['vector_fallback_used'] = True
        return fallback_res
