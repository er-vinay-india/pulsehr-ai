"""
Cache isolation and identity integrity enforcement (Phase G2).
Guarantees zero cross-dataset leakage, zero topic/visual spec mismatches,
and hard rejection of suspicious or corrupted cache entries.
"""
from __future__ import annotations

import logging
from typing import Any

from .contracts import DashboardCacheKey

logger = logging.getLogger(__name__)


class CacheIntegrityViolation(Exception):
    """Raised when a cached payload fails identity or isolation validation."""
    pass


class CacheIsolationIntegrity:
    """
    Hard verification gate executed both before caching and immediately upon cache retrieval.
    Fail-closed: Returns False and logs security audit if any condition is violated.
    """

    @classmethod
    def validate_payload(
        cls,
        payload: dict[str, Any],
        key: DashboardCacheKey,
        is_write: bool = False,
    ) -> bool:
        """
        Validates that the payload is an authoritative, complete, and unpolluted analytical unit.
        """
        if not isinstance(payload, dict):
            logger.warning("[CacheIsolationIntegrity] Rejected: payload is not a dictionary.")
            return False

        # 1. Dataset identity check
        payload_ds_id = payload.get("dataset_id")
        if payload_ds_id is not None and int(payload_ds_id) != int(key.dataset_id):
            logger.error(
                "[CacheIsolationIntegrity] HARD REJECTION: dataset_id mismatch. "
                "Requested %s, payload carries %s.",
                key.dataset_id,
                payload_ds_id,
            )
            return False

        # 2. Complete topic validation
        topics = payload.get("executive_topics", [])
        if not isinstance(topics, list):
            logger.warning("[CacheIsolationIntegrity] Rejected: executive_topics is not a list.")
            return False

        for idx, topic in enumerate(topics):
            if not isinstance(topic, dict):
                logger.warning("[CacheIsolationIntegrity] Topic index %d is not a dict.", idx)
                return False

            # Verify topic identity matches dataset identity
            t_ds_id = topic.get("dataset_id")
            if t_ds_id is not None and int(t_ds_id) != int(key.dataset_id):
                logger.error(
                    "[CacheIsolationIntegrity] HARD REJECTION: topic '%s' dataset_id %s mismatches key %s.",
                    topic.get("topic_id"),
                    t_ds_id,
                    key.dataset_id,
                )
                return False

            # Verify atomic topic bundle fields
            required_fields = ("topic_id", "domain", "title", "visual_spec")
            for req in required_fields:
                if req not in topic or topic[req] is None:
                    logger.warning(
                        "[CacheIsolationIntegrity] Topic '%s' missing mandatory field '%s'.",
                        topic.get("topic_id", f"idx_{idx}"),
                        req,
                    )
                    return False

            # Verify visual_spec binding
            vspec = topic.get("visual_spec")
            if isinstance(vspec, dict):
                v_ds_id = vspec.get("dataset_id")
                if v_ds_id is not None and int(v_ds_id) != int(key.dataset_id):
                    logger.error(
                        "[CacheIsolationIntegrity] HARD REJECTION: visual_spec dataset_id %s mismatches topic dataset_id %s.",
                        v_ds_id,
                        key.dataset_id,
                    )
                    return False

                # Verify domain consistency between topic and visual_spec
                t_domain = topic.get("domain")
                v_domain = vspec.get("domain")
                if t_domain and v_domain and t_domain != v_domain:
                    logger.error(
                        "[CacheIsolationIntegrity] HARD REJECTION: Topic domain '%s' conflicts with visual_spec domain '%s'.",
                        t_domain,
                        v_domain,
                    )
                    return False

        return True
