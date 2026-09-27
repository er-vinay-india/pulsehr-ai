"""Phase 1 Semantic Memory Integration Bridge.

Selectively indexes reusable high-level workspace context into semantic vector memory:
- Dataset schema, metric candidates, and column summaries
- Inferred business domain and data characteristics
- Explicit user preferences and objectives
Strictly enforces privacy: zero sensitive PII or raw row values are ever indexed.
"""

from __future__ import annotations

import datetime
import hashlib
import logging
from typing import Any

from .models import WorkspaceContext
from ..presentation.memory.memory_models import (
    EvidenceStatus,
    MemoryRecord,
    MemoryType,
)
from ..presentation.memory.memory_store import memory_store
from ..presentation.memory.embedding_service import embedding_service

logger = logging.getLogger(__name__)


class MemoryIntegrationBridge:
    """Safely bridges WorkspaceContext into Phase 1 Semantic Memory vector store."""

    @classmethod
    def index_workspace_context(
        cls,
        context: WorkspaceContext,
        force: bool = False
    ) -> int:
        """Indexes reusable domain, profile, and instruction metadata into semantic memory."""
        records_to_index: list[MemoryRecord] = []
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        ws_id = context.workspace_id

        # 1. Dataset Profile Summary Chunk (No sensitive row values)
        for ds in context.datasets:
            col_list = [f"{c.name} ({c.semantic_role.value})" for c in ds.columns if not c.is_sensitive]
            metrics_str = ", ".join(ds.metric_candidates[:8]) or "None"
            dims_str = ", ".join(ds.dimension_candidates[:8]) or "None"

            profile_text = (
                f"Dataset: {ds.name}\n"
                f"Domain: {context.context_summary.domain}\n"
                f"Records: {ds.row_count:,} rows across {ds.col_count} columns\n"
                f"Key Metrics: {metrics_str}\n"
                f"Key Dimensions: {dims_str}\n"
                f"Reporting Period: {context.time_intelligence.reporting_period}\n"
                f"Columns: {', '.join(col_list[:20])}"
            )

            rec_hash = hashlib.sha256(profile_text.encode("utf-8")).hexdigest()
            mem_id = f"mem-profile-{ws_id}-{ds.dataset_id}"

            if not force:
                existing = memory_store.get_by_id(mem_id)
                if existing and existing.content_hash == rec_hash and existing.embedding:
                    continue

            emb = embedding_service.embed_text(profile_text)
            records_to_index.append(
                MemoryRecord(
                    memory_id=mem_id,
                    memory_type=MemoryType.DATASET_PROFILE,
                    text=profile_text,
                    embedding=emb,
                    source_id=ds.dataset_id,
                    source_type="dataset_profile",
                    workspace_id=ws_id,
                    domain=context.context_summary.domain,
                    audience=context.user_request.audience or "Executive Leadership",
                    evidence_status=EvidenceStatus.CURRENT,
                    content_hash=rec_hash,
                    provenance={"origin": "input_intelligence", "dataset_name": ds.name},
                    metadata={"row_count": ds.row_count, "metrics": ds.metric_candidates[:5]},
                    created_at=now_iso,
                    updated_at=now_iso
                )
            )

        # 2. User Intent & Objective Chunk (If explicit)
        if context.user_request.intent_status.value == "EXPLICIT" and context.user_request.raw_instruction:
            intent_text = (
                f"User Goal: {context.user_request.normalized_objective}\n"
                f"Target Audience: {context.user_request.audience or 'Executive'}\n"
                f"Output: {context.user_request.expected_output.value}\n"
                f"Key Questions: {'; '.join(context.user_request.explicit_questions)}"
            )
            i_hash = hashlib.sha256(intent_text.encode("utf-8")).hexdigest()
            mem_id = f"mem-intent-{ws_id}"

            if force or not (memory_store.get_by_id(mem_id) and memory_store.get_by_id(mem_id).content_hash == i_hash):
                emb = embedding_service.embed_text(intent_text)
                records_to_index.append(
                    MemoryRecord(
                        memory_id=mem_id,
                        memory_type=MemoryType.USER_INSTRUCTION,
                        text=intent_text,
                        embedding=emb,
                        source_id=ws_id,
                        source_type="user_instruction",
                        workspace_id=ws_id,
                        domain=context.context_summary.domain,
                        audience=context.user_request.audience,
                        evidence_status=EvidenceStatus.CURRENT,
                        content_hash=i_hash,
                        provenance={"origin": "user_instruction"},
                        metadata={"questions_count": len(context.user_request.explicit_questions)},
                        created_at=now_iso,
                        updated_at=now_iso
                    )
                )

        if records_to_index:
            indexed = memory_store.upsert_batch(records_to_index)
            logger.info(f"Indexed {indexed} high-level reusable context items into semantic memory for workspace '{ws_id}'.")
            return indexed

        return 0
