"""
HighView Deterministic Analytics Cache Package (Phase G2).
"""
from .contracts import (
    DashboardCacheKey,
    CacheEntryMetadata,
    CacheStats,
    SEMANTIC_SCHEMA_VERSION,
    ANALYTICS_ENGINE_VERSION,
    COMPOSITION_ENGINE_VERSION,
    POLICY_VERSION,
    CONTEXT_VERSION,
)
from .key_builder import build_cache_key, canonicalize_filters
from .integrity import CacheIsolationIntegrity, CacheIntegrityViolation
from .repository import DashboardCacheRepository
from .dashboard_cache import DashboardCacheService, dashboard_cache
from .metrics import cache_metrics

__all__ = [
    "DashboardCacheKey",
    "CacheEntryMetadata",
    "CacheStats",
    "SEMANTIC_SCHEMA_VERSION",
    "ANALYTICS_ENGINE_VERSION",
    "COMPOSITION_ENGINE_VERSION",
    "POLICY_VERSION",
    "CONTEXT_VERSION",
    "build_cache_key",
    "canonicalize_filters",
    "CacheIsolationIntegrity",
    "CacheIntegrityViolation",
    "DashboardCacheRepository",
    "DashboardCacheService",
    "dashboard_cache",
    "cache_metrics",
]
