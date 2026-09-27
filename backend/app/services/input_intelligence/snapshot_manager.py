"""Ingestion Snapshot, Incremental Updates, and Invalidation Engine.

Provides:
- Immutable IngestionSnapshot generation and hashing
- Stale context cache invalidation on file replacement / deletion
- Incremental multi-file additions without full re-profiling
- Fast instruction-only updates without re-reading physical data
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
from typing import Any

from .models import (
    IngestionSnapshot,
    SourceItem,
    UserIntentContext,
    WorkspaceContext,
)

logger = logging.getLogger(__name__)


class SnapshotManager:
    """Manages immutable snapshots, cache invalidation, and incremental state updates."""

    _SNAPSHOT_CACHE: dict[str, WorkspaceContext] = {}

    @classmethod
    def compute_snapshot_hash(
        cls,
        workspace_id: str,
        sources: list[SourceItem]
    ) -> str:
        """Computes a deterministic SHA-256 fingerprint from workspace_id and source file hashes."""
        hasher = hashlib.sha256()
        hasher.update(workspace_id.encode("utf-8"))
        for s in sorted(sources, key=lambda x: x.source_id):
            hasher.update(s.source_id.encode("utf-8"))
            hasher.update(s.file_hash.encode("utf-8"))
            hasher.update(str(s.size_bytes).encode("utf-8"))
        return f"sha256:{hasher.hexdigest()[:16]}"

    @classmethod
    def create_snapshot(
        cls,
        workspace_id: str,
        sources: list[SourceItem]
    ) -> IngestionSnapshot:
        """Creates an immutable IngestionSnapshot metadata record."""
        snap_hash = cls.compute_snapshot_hash(workspace_id, sources)
        src_hashes = {s.source_id: s.file_hash for s in sources}
        versions = {s.source_id: "v1.0" for s in sources}

        return IngestionSnapshot(
            workspace_id=workspace_id,
            snapshot_hash=snap_hash,
            ingested_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            source_hashes=src_hashes,
            dataset_versions=versions,
            profile_version="1.0"
        )

    @classmethod
    def get_cached_context(cls, workspace_id: str) -> WorkspaceContext | None:
        """Retrieves active cached WorkspaceContext if present."""
        return cls._SNAPSHOT_CACHE.get(workspace_id)

    @classmethod
    def cache_context(cls, context: WorkspaceContext):
        """Caches WorkspaceContext indexed by workspace_id."""
        cls._SNAPSHOT_CACHE[context.workspace_id] = context

    @classmethod
    def invalidate_workspace(cls, workspace_id: str):
        """Invalidates all cached profiles, joins, and presentation planning contexts for a workspace."""
        if workspace_id in cls._SNAPSHOT_CACHE:
            logger.info(f"Invalidating cached context for workspace '{workspace_id}' due to file mutation.")
            del cls._SNAPSHOT_CACHE[workspace_id]

    @classmethod
    def update_user_instructions_only(
        cls,
        current_context: WorkspaceContext,
        new_instruction: str,
        new_audience: str | None = None
    ) -> WorkspaceContext:
        """Updates user intent and re-evaluates question mappings WITHOUT re-profiling datasets."""
        from .intent_engine import UserIntentEngine

        logger.info(f"Incrementally updating instructions for workspace '{current_context.workspace_id}' without re-profiling.")
        new_intent = UserIntentEngine.parse_user_intent(
            raw_instruction=new_instruction,
            dataset_profiles=current_context.datasets,
            user_overrides=current_context.user_overrides
        )
        if new_audience:
            new_intent.audience = new_audience

        # Re-evaluate question mappings against existing profiles
        new_mappings = UserIntentEngine.reconcile_questions_against_data(
            questions=new_intent.explicit_questions,
            profiles=current_context.datasets
        )
        new_readiness = UserIntentEngine.evaluate_readiness(
            profiles=current_context.datasets,
            intent=new_intent,
            question_mappings=new_mappings
        )

        updated = current_context.model_copy(deep=True)
        updated.user_request = new_intent
        updated.question_mappings = new_mappings
        updated.readiness = new_readiness
        updated.context_summary.user_goal = new_intent.normalized_objective

        cls.cache_context(updated)
        return updated

    @classmethod
    def apply_user_overrides(
        cls,
        current_context: WorkspaceContext,
        overrides: dict[str, Any]
    ) -> WorkspaceContext:
        """Applies partial user overrides incrementally without re-reading physical datasets.
        
        Records provenance audit entries, bumps workspace_context_version, and re-evaluates
        affected question mappings and readiness.
        """
        from .intent_engine import UserIntentEngine
        from .models import (
            JoinCardinality,
            OutputIntent,
            OverrideAuditRecord,
            ProvenanceOrigin,
            SemanticColumnRole,
        )

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        updated = current_context.model_copy(deep=True)
        audit_records: list[OverrideAuditRecord] = []

        recompute_alignment = False

        # 1. Domain Override
        if "domain" in overrides and overrides["domain"]:
            new_domain = str(overrides["domain"]).strip()
            old_domain = updated.context_summary.domain
            if new_domain != old_domain:
                updated.context_summary.domain = new_domain
                audit_records.append(
                    OverrideAuditRecord(
                        field="domain",
                        old_value=old_domain,
                        new_value=new_domain,
                        origin=ProvenanceOrigin.USER_OVERRIDE,
                        timestamp=now_iso
                    )
                )

        # 2. Primary Dataset Override
        if "primary_dataset_id" in overrides and overrides["primary_dataset_id"]:
            new_p_id = str(overrides["primary_dataset_id"]).strip()
            old_p_id = updated.primary_dataset_id
            if new_p_id != old_p_id:
                updated.primary_dataset_id = new_p_id
                target_p = next((d for d in updated.datasets if d.dataset_id == new_p_id), None)
                if target_p:
                    updated.context_summary.primary_dataset = target_p.name
                audit_records.append(
                    OverrideAuditRecord(
                        field="primary_dataset_id",
                        old_value=old_p_id,
                        new_value=new_p_id,
                        origin=ProvenanceOrigin.USER_OVERRIDE,
                        timestamp=now_iso
                    )
                )

        # 3. Column Semantic Roles Override
        if "column_roles" in overrides and isinstance(overrides["column_roles"], dict):
            for col_key, role_str in overrides["column_roles"].items():
                try:
                    new_role = SemanticColumnRole(role_str.upper())
                except Exception:
                    continue

                for ds in updated.datasets:
                    for col in ds.columns:
                        if col.name.lower() == col_key.lower() or f"{ds.dataset_id}.{col.name}".lower() == col_key.lower():
                            old_role = col.semantic_role.value
                            if old_role != new_role.value:
                                col.semantic_role = new_role
                                col.provenance = ProvenanceOrigin.USER_OVERRIDE
                                # Update candidates
                                if new_role in (SemanticColumnRole.METRIC, SemanticColumnRole.CURRENCY, SemanticColumnRole.PERCENTAGE):
                                    if col.name not in ds.metric_candidates:
                                        ds.metric_candidates.append(col.name)
                                    if col.name in ds.dimension_candidates:
                                        ds.dimension_candidates.remove(col.name)
                                elif new_role in (SemanticColumnRole.CATEGORY, SemanticColumnRole.STATUS, SemanticColumnRole.LOCATION, SemanticColumnRole.ORGANIZATION, SemanticColumnRole.PERSON):
                                    if col.name not in ds.dimension_candidates:
                                        ds.dimension_candidates.append(col.name)
                                    if col.name in ds.metric_candidates:
                                        ds.metric_candidates.remove(col.name)

                                audit_records.append(
                                    OverrideAuditRecord(
                                        field=f"column_role:{col.name}",
                                        old_value=old_role,
                                        new_value=new_role.value,
                                        origin=ProvenanceOrigin.USER_OVERRIDE,
                                        timestamp=now_iso
                                    )
                                )
                                recompute_alignment = True

        # 4. User Objective / Instruction Override
        if "user_objective" in overrides or "raw_instruction" in overrides:
            new_text = str(overrides.get("user_objective") or overrides.get("raw_instruction", "")).strip()
            old_text = updated.user_request.raw_instruction or updated.user_request.normalized_objective
            if new_text and new_text != old_text:
                new_intent = UserIntentEngine.parse_user_intent(
                    raw_instruction=new_text,
                    dataset_profiles=updated.datasets,
                    user_overrides={**updated.user_overrides, **overrides}
                )
                updated.user_request = new_intent
                updated.context_summary.user_goal = new_intent.normalized_objective
                audit_records.append(
                    OverrideAuditRecord(
                        field="user_objective",
                        old_value=old_text,
                        new_value=new_text,
                        origin=ProvenanceOrigin.USER_OVERRIDE,
                        timestamp=now_iso
                    )
                )
                recompute_alignment = True

        # 5. Explicit Questions Override
        if "explicit_questions" in overrides and isinstance(overrides["explicit_questions"], list):
            new_q = [str(q).strip() for q in overrides["explicit_questions"] if str(q).strip()]
            old_q = list(updated.user_request.explicit_questions)
            if new_q != old_q:
                updated.user_request.explicit_questions = new_q
                audit_records.append(
                    OverrideAuditRecord(
                        field="explicit_questions",
                        old_value=old_q,
                        new_value=new_q,
                        origin=ProvenanceOrigin.USER_OVERRIDE,
                        timestamp=now_iso
                    )
                )
                recompute_alignment = True

        # 6. Audience Override
        if "audience" in overrides and overrides["audience"]:
            new_aud = str(overrides["audience"]).strip()
            old_aud = updated.user_request.audience
            if new_aud != old_aud:
                updated.user_request.audience = new_aud
                audit_records.append(
                    OverrideAuditRecord(
                        field="audience",
                        old_value=old_aud,
                        new_value=new_aud,
                        origin=ProvenanceOrigin.USER_OVERRIDE,
                        timestamp=now_iso
                    )
                )

        # 7. Output Intent Override
        if "expected_output" in overrides and overrides["expected_output"]:
            try:
                new_out = OutputIntent(str(overrides["expected_output"]).upper())
                old_out = updated.user_request.expected_output.value
                if new_out.value != old_out:
                    updated.user_request.expected_output = new_out
                    audit_records.append(
                        OverrideAuditRecord(
                            field="expected_output",
                            old_value=old_out,
                            new_value=new_out.value,
                            origin=ProvenanceOrigin.USER_OVERRIDE,
                            timestamp=now_iso
                        )
                    )
            except Exception:
                pass

        # 8. Reporting Period Override
        if "reporting_period" in overrides and overrides["reporting_period"]:
            new_period = str(overrides["reporting_period"]).strip()
            old_period = updated.time_intelligence.reporting_period
            if new_period != old_period:
                updated.time_intelligence.reporting_period = new_period
                updated.context_summary.reporting_period = new_period
                audit_records.append(
                    OverrideAuditRecord(
                        field="reporting_period",
                        old_value=old_period,
                        new_value=new_period,
                        origin=ProvenanceOrigin.USER_OVERRIDE,
                        timestamp=now_iso
                    )
                )

        # 9. Candidate Join Acceptance / Rejection
        if "join_decisions" in overrides and isinstance(overrides["join_decisions"], dict):
            for rel_id, decision in overrides["join_decisions"].items():
                for rel in updated.relationships:
                    if rel.relationship_id == rel_id:
                        old_val = rel.is_safe
                        # Safeguard: many-to-many joins CANNOT be made safe automatically
                        if rel.cardinality == JoinCardinality.MANY_TO_MANY:
                            rel.is_safe = False
                            rel.evidence += " (User requested enable, but many-to-many automatic join remains disabled for integrity)"
                        else:
                            rel.is_safe = bool(decision)

                        audit_records.append(
                            OverrideAuditRecord(
                                field=f"join_decision:{rel_id}",
                                old_value=old_val,
                                new_value=rel.is_safe,
                                origin=ProvenanceOrigin.USER_OVERRIDE,
                                timestamp=now_iso,
                                notes="Safeguarded: many-to-many remains unsafe" if rel.cardinality == JoinCardinality.MANY_TO_MANY else None
                            )
                        )

        # Re-evaluate question alignment & readiness if needed
        if recompute_alignment:
            new_mappings = UserIntentEngine.reconcile_questions_against_data(
                questions=updated.user_request.explicit_questions,
                profiles=updated.datasets
            )
            new_readiness = UserIntentEngine.evaluate_readiness(
                profiles=updated.datasets,
                intent=updated.user_request,
                question_mappings=new_mappings
            )
            updated.question_mappings = new_mappings
            updated.readiness = new_readiness
            updated.context_summary.readiness_summary = new_readiness.status.value

        # Update metadata, version, and audit trail
        updated.workspace_context_version += 1
        updated.user_overrides.update(overrides)
        updated.override_history.extend(audit_records)

        cls.cache_context(updated)
        logger.info(
            f"Incrementally applied {len(audit_records)} overrides to workspace '{current_context.workspace_id}' "
            f"(version: {updated.workspace_context_version})."
        )
        return updated

