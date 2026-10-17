from ...core import config
from .base import DecisionEngine
from .rule_engine import RuleDecisionEngine
from .embedding_engine import EmbeddingDecisionEngine

_INSTANCE: DecisionEngine | None = None


def get_decision_engine(engine_type: str | None = None) -> DecisionEngine:
    """Acquires a DecisionEngine based on configuration or explicit argument.
    
    Supported types: 'rules' (default), 'embedding'
    """
    global _INSTANCE
    selected = (engine_type or config.DECISION_ENGINE).lower().strip()
    if selected in ("embedding", "embeddings", "vector"):
        return EmbeddingDecisionEngine()
    if _INSTANCE is None:
        _INSTANCE = RuleDecisionEngine()
    return _INSTANCE
