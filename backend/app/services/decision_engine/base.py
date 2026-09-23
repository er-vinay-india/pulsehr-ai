"""Base classes and data structures for pluggable DecisionEngine."""

from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel, Field


class DecisionResult(BaseModel):
    """Standardized decision classification output."""
    intent: str
    confidence: float = Field(ge=0.0, le=1.0)
    extracted_entities: dict[str, Any] = Field(default_factory=dict)
    reasoning_required: bool = False
    suggested_role: str | None = None
    engine_name: str = "base"
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecisionEngine(ABC):
    """Abstract interface for query intent classification and routing decisions."""

    @abstractmethod
    def classify(self, query: str, context: dict[str, Any] | None = None) -> DecisionResult:
        """Classifies a user query into an intent with confidence and entity extraction."""
        pass
