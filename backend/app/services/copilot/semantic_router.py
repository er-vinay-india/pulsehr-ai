"""Semantic Intent Router and Prototype Bank for Council Coordinator (Layer 1).

Uses local Ollama embeddings (nomic-embed-text) with multi-anchor prototype clusters
to classify user queries across confidence bands:
- >= 0.86: Direct specialist route without LLM invocation (<15ms)
- 0.70 - 0.86: High-confidence prior passed to Layer 2 Coordinator
- < 0.70: Ambiguous; Coordinator LLM disambiguation required
"""

import logging
import math
import time
from typing import Any
import httpx

from ...core import config
from .coordinator_models import ExecutionRoute, UserIntent, ContextRelation, RouteContract

logger = logging.getLogger(__name__)

# Multi-anchor prototype clusters representing core user intents
SEMANTIC_PROTOTYPES: dict[UserIntent, dict[str, Any]] = {
    UserIntent.CALCULATE: {
        "route": ExecutionRoute.MATH_ENGINE,
        "context_relation": ContextRelation.NEW_TOPIC,
        "anchors": [
            "what is the square root of 9",
            "what is the log of 10 base 2",
            "calculate log 100",
            "what is 2 to the power of 8",
            "compute 15 percent of 850",
            "calculate 45 times 12",
            "what is 144 divided by 12",
            "solve math expression 25 plus 75",
            "what is the cube root of 27",
            "evaluate arithmetic expression"
        ]
    },
    UserIntent.VISUALIZE: {
        "route": ExecutionRoute.CHART_ENGINE,
        "context_relation": ContextRelation.FOLLOW_UP,
        "anchors": [
            "draw the chart based on students by gender",
            "draw the chart based on cohort average math score",
            "show that in chart format",
            "display a bar chart of performance",
            "plot attendance by department",
            "make a pie chart for gender distribution",
            "visualize this data as a line graph",
            "render a chart for this metric",
            "plot the results in a visual graph"
        ]
    },
    UserIntent.QUERY_DATASET: {
        "route": ExecutionRoute.DATASET_ENGINE,
        "context_relation": ContextRelation.FOLLOW_UP,
        "anchors": [
            "cohort average math score",
            "average math score by cohort",
            "which department has the lowest attendance",
            "top 10 employees by salary",
            "how many students scored above 80",
            "sum of sales by region",
            "filter records where status is active",
            "breakdown of attendance by department",
            "what is the highest score in the sheet",
            "how much records we have here",
            "how many records are in this dataset",
            "what is the total row count",
            "how many rows in the sheet",
            "what columns are in this sheet",
            "list all columns in the dataset",
            "how many columns do we have"
        ]
    },
    UserIntent.GREET: {
        "route": ExecutionRoute.EXPLANATION_WORKER,
        "context_relation": ContextRelation.NEW_TOPIC,
        "anchors": [
            "hello",
            "hi there",
            "good morning",
            "who are you",
            "what can you do",
            "introduce yourself",
            "help me understand what this tool does"
        ]
    },
    UserIntent.EXPLAIN: {
        "route": ExecutionRoute.EXPLANATION_WORKER,
        "context_relation": ContextRelation.NEW_TOPIC,
        "anchors": [
            "what is p-value in statistics",
            "explain standard deviation",
            "define attrition rate",
            "what does cohort analysis mean",
            "what does bradford factor mean",
            "explain the meaning of variance",
            "how does correlation differ from causation"
        ]
    },
    UserIntent.DELIBERATE: {
        "route": ExecutionRoute.COUNCIL_WAR_ROOM,
        "context_relation": ContextRelation.FOLLOW_UP,
        "anchors": [
            "why are attrition rates rising",
            "what is the root cause of sales drop",
            "what interventions should we take to reduce turnover",
            "strategic trade-offs between retention and hiring costs",
            "assemble council to investigate performance issues",
            "convene war room for deep causal analysis",
            "what strategic policy changes should leadership implement"
        ]
    }
}


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Computes cosine similarity between two float vectors."""
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


class SemanticIntentRouter:
    """Prototype-based semantic intent classifier with confidence band routing."""

    _prototype_embeddings: dict[UserIntent, list[list[float]]] = {}
    _initialized: bool = False

    @classmethod
    def get_embedding(cls, text: str, model: str = "nomic-embed-text:latest") -> list[float] | None:
        """Fetches vector embedding for text from local Ollama instance."""
        try:
            with httpx.Client(timeout=3.0) as client:
                resp = client.post(
                    f"{config.OLLAMA_BASE_URL}/api/embeddings",
                    json={"model": model, "prompt": text}
                )
                if resp.status_code == 200:
                    return resp.json().get("embedding")
        except Exception as exc:
            logger.debug(f"Ollama embedding fetch failed: {exc}")
        return None

    @classmethod
    def ensure_prototype_embeddings(cls) -> bool:
        """Initializes and caches vector embeddings for all prototype anchors."""
        if cls._initialized and cls._prototype_embeddings:
            return True

        for intent, data in SEMANTIC_PROTOTYPES.items():
            vectors = []
            for anchor in data["anchors"]:
                vec = cls.get_embedding(anchor)
                if vec:
                    vectors.append(vec)
            if vectors:
                cls._prototype_embeddings[intent] = vectors

        cls._initialized = bool(cls._prototype_embeddings)
        return cls._initialized

    @classmethod
    def route_query(cls, query: str) -> tuple[RouteContract | None, float]:
        """
        Evaluates query against prototype bank.
        Returns:
            (RouteContract, max_similarity)
            - If max_similarity >= 0.86: returns binding RouteContract.
            - If 0.70 <= max_similarity < 0.86: returns tentative RouteContract (needs Layer 2 check or prior).
            - If < 0.70: returns (None, max_similarity).
        """
        query_vec = cls.get_embedding(query)
        if not query_vec or not cls.ensure_prototype_embeddings():
            return None, 0.0

        best_intent = UserIntent.UNKNOWN
        best_sim = -1.0

        for intent, proto_vecs in cls._prototype_embeddings.items():
            for p_vec in proto_vecs:
                sim = cosine_similarity(query_vec, p_vec)
                if sim > best_sim:
                    best_sim = sim
                    best_intent = intent

        if best_sim < 0.70 or best_intent == UserIntent.UNKNOWN:
            return None, round(best_sim, 3)

        proto_meta = SEMANTIC_PROTOTYPES[best_intent]
        contract = RouteContract(
            intent=best_intent,
            route=proto_meta["route"],
            context_relation=proto_meta["context_relation"],
            confidence=round(best_sim, 3),
            rationale=f"Semantic Prototype Match (similarity={best_sim:.3f})"
        )
        return contract, round(best_sim, 3)
