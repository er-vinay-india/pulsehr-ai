"""
Deterministic cache key builder for HighView Analytics Cache (Phase G2).
Guarantees canonicalization, version awareness, and theme independence.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any

from ..db.database import session_scope
from .contracts import (
    DashboardCacheKey,
    SEMANTIC_SCHEMA_VERSION,
    ANALYTICS_ENGINE_VERSION,
    COMPOSITION_ENGINE_VERSION,
    POLICY_VERSION,
    CONTEXT_VERSION,
)


def canonicalize_filters(filters: dict[str, Any] | None) -> str:
    """
    Normalizes query/explorer filter parameters into a deterministic hash.
    Rules:
    - Sort keys alphabetically
    - Normalize string values (strip whitespace)
    - Normalize list/set values (sort elements)
    - Discard None or empty values
    """
    if not filters:
        return ""

    normalized: dict[str, Any] = {}
    for k in sorted(filters.keys()):
        v = filters[k]
        if v is None or v == "" or v == [] or v == {}:
            continue
        if isinstance(v, (list, set, tuple)):
            normalized[k] = sorted([str(item).strip() for item in v if item is not None])
        elif isinstance(v, dict):
            normalized[k] = json.loads(canonicalize_filters(v)) if v else {}
        elif isinstance(v, str):
            normalized[k] = v.strip()
        else:
            normalized[k] = v

    if not normalized:
        return ""

    canonical_str = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()[:16]


def resolve_dataset_fingerprint(dataset_id: int, conn: sqlite3.Connection) -> tuple[str, int]:
    """
    Resolves authoritative content hash and version for a dataset.
    If content_hash is not yet materialized on the dataset_uploads row,
    computes a deterministic fingerprint from sheet metadata, schema, and row counts.
    """
    row = conn.execute(
        "SELECT id, filename, row_count, col_count, columns_json, content_hash FROM dataset_uploads WHERE id = ?",
        (dataset_id,),
    ).fetchone()

    if not row:
        # Fallback hash for test or virtual dataset IDs
        return (f"v1_dataset_{dataset_id}_empty", 1)

    existing_hash = row["content_hash"]
    if existing_hash:
        return (existing_hash, 1)

    # Compute deterministic fingerprint from dataset and sheets
    sheet_rows = conn.execute(
        "SELECT id, name, row_count, columns_json FROM sheets WHERE dataset_id = ? ORDER BY id ASC",
        (dataset_id,),
    ).fetchall()

    fingerprint_components = [
        str(row["id"]),
        str(row["filename"]),
        str(row["row_count"]),
        str(row["col_count"]),
        str(row["columns_json"] or ""),
    ]

    for s in sheet_rows:
        fingerprint_components.extend([
            str(s["id"]),
            str(s["name"]),
            str(s["row_count"]),
            str(s["columns_json"] or ""),
        ])

    computed_hash = hashlib.sha256("|".join(fingerprint_components).encode("utf-8")).hexdigest()

    # Backfill dataset_uploads.content_hash so future lookups are instantaneous
    try:
        conn.execute("UPDATE dataset_uploads SET content_hash = ? WHERE id = ?", (computed_hash, dataset_id))
    except Exception:
        pass

    return (computed_hash, 1)


def build_cache_key(
    dataset_id: int,
    cache_type: str = "dataset_intelligence",
    filters: dict[str, Any] | None = None,
    tenant_id: str | None = None,
    conn: sqlite3.Connection | None = None,
    semantic_graph_fingerprint: str | None = None,
    analytical_profile_fingerprint: str | None = None,
    consumer_contract_version: str = "1.0.0",
) -> DashboardCacheKey:
    """
    Builds a canonical DashboardCacheKey.
    NOTE: Theme is intentionally omitted to keep analytics payloads theme-agnostic.
    """
    filter_hash = canonicalize_filters(filters)

    if conn is not None:
        content_hash, version = resolve_dataset_fingerprint(dataset_id, conn)
    else:
        with session_scope() as active_conn:
            content_hash, version = resolve_dataset_fingerprint(dataset_id, active_conn)

    return DashboardCacheKey(
        dataset_id=dataset_id,
        dataset_version=version,
        dataset_content_hash=content_hash,
        semantic_schema_version=SEMANTIC_SCHEMA_VERSION,
        context_version=CONTEXT_VERSION,
        policy_version=POLICY_VERSION,
        analytics_engine_version=ANALYTICS_ENGINE_VERSION,
        composition_engine_version=COMPOSITION_ENGINE_VERSION,
        filter_hash=filter_hash,
        tenant_id=tenant_id,
        cache_type=cache_type,
        semantic_graph_fingerprint=semantic_graph_fingerprint,
        analytical_profile_fingerprint=analytical_profile_fingerprint,
        consumer_contract_version=consumer_contract_version,
    )
