"""
HighView Semantic Data Refinery — Phase SDR-9
Cache Safety & Route Partitioning
Guarantees that cache keys partition across route, dataset version, consumer contract,
and artifact fingerprints to prevent route collision or stale truth leakage.
"""

from __future__ import annotations

import hashlib
from typing import Any

from app.services.ingestion_v2.contracts.cutover import ConsumerName, Route


def compute_sdr_cache_key(
    consumer: ConsumerName | str,
    route: Route | str,
    dataset_id: str,
    dataset_version: str,
    artifact_fingerprint: str | None,
    contract_fingerprint: str | None = None,
    query_or_topic: str | None = None,
) -> str:
    """
    Computes a strongly partitioned, collision-proof cache key.
    Enforces that:
    - V2 and SDR responses have distinct namespace prefixes.
    - Dataset version updates invalidate cached items.
    - Contract updates invalidate cached items.
    - Artifact updates invalidate cached items.
    """
    c_str = consumer.value if isinstance(consumer, ConsumerName) else str(consumer)
    r_str = route.value if isinstance(route, Route) else str(route)
    ds_str = str(dataset_id)
    ver_str = str(dataset_version)
    art_str = str(artifact_fingerprint or "NO_ART_FP")
    con_str = str(contract_fingerprint or "NO_CON_FP")
    q_str = str(query_or_topic or "")

    raw = f"{c_str}|{r_str}|{ds_str}|{ver_str}|{art_str}|{con_str}|{q_str}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"cache:{c_str}:{r_str}:{ds_str}:{ver_str}:{digest[:16]}"
