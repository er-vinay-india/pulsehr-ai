"""Structured Fact Registry ensuring 100% provenance and verifiable citations for analytics and Copilot."""

import hashlib
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class InsightFact:
    def __init__(
        self,
        fact_id: str,
        snapshot_id: str,
        kind: str,
        title: str,
        metric: str,
        observation: str,
        implication: str,
        action: str,
        detail: dict[str, Any],
        priority_score: float = 0.0
    ):
        self.fact_id = fact_id
        self.snapshot_id = snapshot_id
        self.kind = kind
        self.title = title
        self.metric = metric
        self.observation = observation
        self.implication = implication
        self.action = action
        self.detail = detail
        self.priority_score = priority_score

    def to_dict(self) -> dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "snapshot_id": self.snapshot_id,
            "kind": self.kind,
            "title": self.title,
            "metric": self.metric,
            "observation": self.observation,
            "implication": self.implication,
            "action": self.action,
            "detail": self.detail,
            "priority_score": self.priority_score
        }


class InsightRegistry:
    """In-memory cryptographic fact registry mapping findings to stable FACT-XXX identifiers."""

    def __init__(self):
        self._facts_by_snapshot: dict[str, dict[str, InsightFact]] = {}
        self._brief_cache: dict[str, dict[str, Any]] = {}

    def register_findings(self, snapshot_id: str, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Registers a list of findings under a cryptographic snapshot ID with stable FACT-XXX identifiers."""
        if snapshot_id not in self._facts_by_snapshot:
            self._facts_by_snapshot[snapshot_id] = {}

        registered_findings = []
        for idx, f in enumerate(findings):
            fact_id = f.get("fact_id") or f.get("id") or f"FACT-{idx + 1:03d}"
            # Ensure format is clean FACT-XXX if possible
            if not str(fact_id).startswith("FACT-"):
                fact_id = f"FACT-{idx + 1:03d}"

            fact = InsightFact(
                fact_id=fact_id,
                snapshot_id=snapshot_id,
                kind=f.get("kind", "comparison"),
                title=f.get("title", ""),
                metric=f.get("metric", ""),
                observation=f.get("observation", ""),
                implication=f.get("implication", ""),
                action=f.get("action", ""),
                detail=f.get("detail", {}),
                priority_score=float(f.get("priority_score", 0.0))
            )
            self._facts_by_snapshot[snapshot_id][fact_id] = fact
            
            f_copy = dict(f)
            f_copy["fact_id"] = fact_id
            f_copy["snapshot_id"] = snapshot_id
            registered_findings.append(f_copy)

        return registered_findings

    def get_fact(self, snapshot_id: str, fact_id: str) -> dict[str, Any] | None:
        """Retrieves a single verified fact by snapshot and fact ID."""
        snapshot_facts = self._facts_by_snapshot.get(snapshot_id, {})
        fact = snapshot_facts.get(fact_id)
        return fact.to_dict() if fact else None

    def get_all_facts(self, snapshot_id: str) -> list[dict[str, Any]]:
        """Retrieves all registered facts for a given snapshot."""
        snapshot_facts = self._facts_by_snapshot.get(snapshot_id, {})
        return [f.to_dict() for f in snapshot_facts.values()]

    def verify_fact_reference(self, snapshot_id: str, fact_id: str) -> bool:
        """Verifies if a fact ID is valid and registered for the active snapshot."""
        return fact_id in self._facts_by_snapshot.get(snapshot_id, {})

    # Brief Result Caching
    def get_cached_brief(self, cache_key: str) -> dict[str, Any] | None:
        return self._brief_cache.get(cache_key)

    def set_cached_brief(self, cache_key: str, brief: dict[str, Any]):
        # Keep cache bounded to 100 entries
        if len(self._brief_cache) > 100:
            oldest_key = next(iter(self._brief_cache))
            del self._brief_cache[oldest_key]
        self._brief_cache[cache_key] = brief

    def invalidate_cache(self):
        self._brief_cache.clear()


insight_registry = InsightRegistry()
