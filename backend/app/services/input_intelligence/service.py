"""Input & Context Intelligence Master Service.

The central entry point executing:
Files / Data / Instructions
→ Source Canonicalization
→ Deterministic Profiling
→ Semantic Classification
→ Domain & Time Intelligence
→ Multi-Sheet Join Discovery
→ User Intent & Question Mapping
→ Ingestion Snapshotting
→ Canonical WorkspaceContext Synthesis
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any
import pandas as pd

from .classifier import SemanticClassifier
from .intent_engine import UserIntentEngine
from .models import (
    ContextSummary,
    DatasetProfile,
    SourceItem,
    SourceRole,
    SourceType,
    WorkspaceContext,
)
from .multi_sheet import MultiSheetIntelligence
from .profiler import DataProfiler
from .snapshot_manager import SnapshotManager

logger = logging.getLogger(__name__)


class InputIntelligenceService:
    """Master engine for synthesizing the canonical WorkspaceContext from raw user inputs."""

    @classmethod
    def process_workspace_input(
        cls,
        workspace_id: str,
        files_or_data: list[dict[str, Any]],
        user_instruction: str = "",
        user_overrides: dict[str, Any] | None = None
    ) -> WorkspaceContext:
        """Processes tabular sources, documents, and user instructions into a canonical WorkspaceContext."""
        start_time = time.perf_counter()
        overrides = user_overrides or {}

        sources: list[SourceItem] = []
        dataset_profiles: list[DatasetProfile] = []
        workbook_contexts = []
        all_quality_profiles = []

        # ---------------------------------------------------------------------
        # 1. PROCESS EACH INPUT SOURCE
        # ---------------------------------------------------------------------
        for idx, item in enumerate(files_or_data):
            src_id = str(item.get("id", f"src_{idx+1}"))
            filename = str(item.get("filename", f"file_{idx+1}.csv"))
            original_name = str(item.get("original_name", filename))

            # Determine source type
            lower_name = filename.lower()
            if lower_name.endswith(".csv"):
                src_type = SourceType.CSV
            elif lower_name.endswith(".xlsx") or lower_name.endswith(".xls"):
                src_type = SourceType.MULTI_SHEET_EXCEL if len(item.get("sheets", [])) > 1 else SourceType.EXCEL
            elif lower_name.endswith(".json"):
                src_type = SourceType.JSON
            elif lower_name.endswith(".pdf"):
                src_type = SourceType.PDF
            elif lower_name.endswith(".docx"):
                src_type = SourceType.DOCX
            elif lower_name.endswith(".pptx"):
                src_type = SourceType.PPTX
            else:
                src_type = SourceType.CSV

            # Compute hash
            records = item.get("records") or []
            file_hash = hashlib.sha256(f"{filename}_{len(records)}_{idx}".encode("utf-8")).hexdigest()

            source_item = SourceItem(
                source_id=src_id,
                source_type=src_type,
                filename=filename,
                original_name=original_name,
                file_hash=file_hash,
                size_bytes=item.get("size_bytes", len(records) * 100),
                sheet_count=max(1, len(item.get("sheets", [])))
            )
            # Classify role
            source_item.role = MultiSheetIntelligence.classify_source_role(source_item)
            sources.append(source_item)

            # Profile data if tabular
            if records:
                df = pd.DataFrame(records)
                d_prof, q_prof = DataProfiler.profile_dataframe(
                    df=df,
                    dataset_id=src_id,
                    dataset_name=original_name
                )

                # Enrich column semantics
                for col in d_prof.columns:
                    col_series = df[col.name] if col.name in df.columns else None
                    SemanticClassifier.enrich_column_semantics(col, col_series)

                dataset_profiles.append(d_prof)
                all_quality_profiles.append(q_prof)

        # ---------------------------------------------------------------------
        # 2. MULTI-SHEET WORKBOOK INTELLIGENCE & RELATIONSHIPS
        # ---------------------------------------------------------------------
        relationships = MultiSheetIntelligence.detect_relationships(dataset_profiles)
        if len(dataset_profiles) > 1:
            wb_ctx = MultiSheetIntelligence.build_workbook_context(
                workbook_name=sources[0].original_name if sources else "Workbook",
                source_id=sources[0].source_id if sources else "src_1",
                sheet_profiles=dataset_profiles
            )
            workbook_contexts.append(wb_ctx)

        # ---------------------------------------------------------------------
        # 3. PRIMARY DATASET DETECTION
        # ---------------------------------------------------------------------
        primary_id, primary_conf = MultiSheetIntelligence.detect_primary_dataset(
            profiles=dataset_profiles,
            user_instruction=user_instruction
        )
        if "primary_dataset_id" in overrides:
            primary_id = overrides["primary_dataset_id"]

        # ---------------------------------------------------------------------
        # 4. DOMAIN & TIME INTELLIGENCE
        # ---------------------------------------------------------------------
        inferred_domain, domain_conf, signals = SemanticClassifier.infer_domain(
            profiles=dataset_profiles,
            dataset_name=sources[0].original_name if sources else "",
            user_instruction=user_instruction
        )
        resolved_domain = inferred_domain.value
        # User override takes absolute precedence
        if "domain" in overrides:
            resolved_domain = overrides["domain"]

        time_intel = SemanticClassifier.extract_time_intelligence(dataset_profiles)

        # ---------------------------------------------------------------------
        # 5. USER INTENT & QUESTION ALIGNMENT
        # ---------------------------------------------------------------------
        intent_ctx = UserIntentEngine.parse_user_intent(
            raw_instruction=user_instruction,
            dataset_profiles=dataset_profiles,
            user_overrides=overrides
        )

        question_mappings = UserIntentEngine.reconcile_questions_against_data(
            questions=intent_ctx.explicit_questions,
            profiles=dataset_profiles
        )

        readiness = UserIntentEngine.evaluate_readiness(
            profiles=dataset_profiles,
            intent=intent_ctx,
            question_mappings=question_mappings
        )

        # ---------------------------------------------------------------------
        # 6. INGESTION SNAPSHOT & CONTEXT SUMMARY
        # ---------------------------------------------------------------------
        snapshot = SnapshotManager.create_snapshot(workspace_id=workspace_id, sources=sources)

        primary_profile = next((p for p in dataset_profiles if p.dataset_id == primary_id), dataset_profiles[0] if dataset_profiles else None)
        total_rows = sum(p.row_count for p in dataset_profiles)

        key_dims = primary_profile.dimension_candidates[:5] if primary_profile else []
        key_mets = primary_profile.metric_candidates[:5] if primary_profile else []

        summary = ContextSummary(
            domain=resolved_domain,
            primary_dataset=primary_profile.name if primary_profile else (sources[0].original_name if sources else ""),
            record_count=total_rows,
            reporting_period=time_intel.reporting_period,
            key_dimensions=key_dims,
            key_metrics=key_mets,
            user_goal=intent_ctx.normalized_objective,
            readiness_summary=readiness.status.value
        )

        # Aggregate data quality profile
        combined_quality = all_quality_profiles[0] if all_quality_profiles else None

        workspace_context = WorkspaceContext(
            workspace_id=workspace_id,
            user_request=intent_ctx,
            sources=sources,
            datasets=dataset_profiles,
            documents=[],
            workbook_contexts=workbook_contexts,
            relationships=relationships,
            primary_dataset_id=primary_id,
            time_intelligence=time_intel,
            context_summary=summary,
            quality=combined_quality,
            readiness=readiness,
            question_mappings=question_mappings,
            user_overrides=overrides,
            provenance=snapshot
        )

        # Cache in memory
        SnapshotManager.cache_context(workspace_context)

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(
            f"Input Intelligence successfully synthesized WorkspaceContext for '{workspace_id}' "
            f"in {elapsed_ms}ms (Domain: {resolved_domain}, Readiness: {readiness.status.value}, Intent: {intent_ctx.intent_status.value})"
        )

        return workspace_context
