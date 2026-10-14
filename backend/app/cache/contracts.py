"""
Contracts, versions, and key schemas for HighView Deterministic Analytics Cache (Phase G2).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from typing import Any
from pydantic import BaseModel, Field

# -----------------------------------------------------------------------------
# Engine and Schema Version Invariants
# Any change to these versions deterministically invalidates stale cache keys
# without requiring dynamic source-code hashing.
# -----------------------------------------------------------------------------
SEMANTIC_SCHEMA_VERSION: str = "7"
ANALYTICS_ENGINE_VERSION: str = "2026.10.1"
COMPOSITION_ENGINE_VERSION: str = "2026.10.4"
POLICY_VERSION: str = "1.2.0"
CONTEXT_VERSION: str = "2.4.0"


class DashboardCacheKey(BaseModel):
    """
    Canonical cache key contract.
    Theme is STRICTLY EXCLUDED: dark/light theme is presentation state,
    and the analytical payload remains 100% theme-agnostic.
    """
    dataset_id: int
    dataset_version: int = 1
    dataset_content_hash: str
    semantic_schema_version: str = SEMANTIC_SCHEMA_VERSION
    context_version: str = CONTEXT_VERSION
    policy_version: str = POLICY_VERSION
    analytics_engine_version: str = ANALYTICS_ENGINE_VERSION
    composition_engine_version: str = COMPOSITION_ENGINE_VERSION
    filter_hash: str = ""
    tenant_id: str | None = None
    cache_type: str = "dataset_intelligence"  # e.g., 'primary_element' or 'dataset_intelligence'

    def canonical_dict(self) -> dict[str, Any]:
        """Returns sorted, normalized canonical dictionary for deterministic hashing."""
        return {
            "analytics_engine_version": self.analytics_engine_version,
            "cache_type": self.cache_type,
            "composition_engine_version": self.composition_engine_version,
            "context_version": self.context_version,
            "dataset_content_hash": self.dataset_content_hash,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "filter_hash": self.filter_hash or "",
            "policy_version": self.policy_version,
            "semantic_schema_version": self.semantic_schema_version,
            "tenant_id": self.tenant_id or "",
        }

    def compute_key(self) -> str:
        """Computes deterministic SHA-256 hash over canonical JSON."""
        canonical_str = json.dumps(self.canonical_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


@dataclass
class CacheEntryMetadata:
    cache_key: str
    dataset_id: int
    dataset_version: int
    content_hash: str
    semantic_schema_version: str
    context_version: str
    policy_version: str
    analytics_engine_version: str
    composition_engine_version: str
    filter_hash: str
    created_at: str
    last_accessed_at: str
    hit_count: int
    size_bytes: int


@dataclass
class CacheStats:
    total_entries: int
    total_bytes: int
    hit_count: int
    miss_count: int
    invalid_count: int
    write_count: int
    invalidation_count: int
    cold_p50_ms: float
    cold_p95_ms: float
    warm_p50_ms: float
    warm_p95_ms: float
