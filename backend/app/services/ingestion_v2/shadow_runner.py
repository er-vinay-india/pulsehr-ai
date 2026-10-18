"""
HighView Ingestion V2 — Shadow Runner & Isolated Storage Harness
Component: Shadow Orchestration Engine
Responsibilities:
1. Orchestrates shadow pipeline runs in complete isolation from production V1 consumers.
2. Enforces P0 Database Isolation: Zero writes to production pulsehr.sqlite3 database.
3. Enforces Consumer Cutover Firewall: consumer_cutover_allowed is locked to False in Phase I1.
4. Manages the PipelineDisagreementLedger across shadow executions.
5. Tracks deterministic stage fingerprints across all 12 internal stages.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.ingestion_v2.contracts import (
    InternalStage,
    PublicProgressGroup,
    INTERNAL_TO_PUBLIC_STAGE_MAP,
    ShadowExecutionStatus,
    ShadowPipelineRun,
    ComparisonClass,
    DisagreementType,
    Severity,
    ReviewStatus,
    PipelineDisagreementRecord,
    PipelineDisagreementLedger,
    compute_stage_fingerprint,
)


class ShadowStorageManager:
    """
    Isolated file-based storage for Shadow V2 pipeline runs and disagreement ledgers.
    Guarantees 100% decoupling from pulsehr.sqlite3.
    """

    def __init__(self, base_dir: Path | str | None = None):
        if base_dir:
            self.base_dir = Path(base_dir)
        else:
            self.base_dir = Path(__file__).resolve().parent / "shadow_store"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir = self.base_dir / "runs"
        self.ledgers_dir = self.base_dir / "ledgers"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.ledgers_dir.mkdir(parents=True, exist_ok=True)

    def save_run(self, run: ShadowPipelineRun) -> Path:
        target_path = self.runs_dir / f"{run.shadow_run_id}.json"
        target_path.write_text(run.model_dump_json(indent=2), encoding="utf-8")
        return target_path

    def load_run(self, shadow_run_id: str) -> ShadowPipelineRun | None:
        target_path = self.runs_dir / f"{shadow_run_id}.json"
        if not target_path.exists():
            return None
        data = json.loads(target_path.read_text(encoding="utf-8"))
        return ShadowPipelineRun(**data)

    def save_ledger(self, ledger: PipelineDisagreementLedger) -> Path:
        target_path = self.ledgers_dir / f"{ledger.shadow_run_id}_ledger.json"
        target_path.write_text(ledger.model_dump_json(indent=2), encoding="utf-8")
        return target_path

    def load_ledger(self, shadow_run_id: str) -> PipelineDisagreementLedger | None:
        target_path = self.ledgers_dir / f"{shadow_run_id}_ledger.json"
        if not target_path.exists():
            return None
        data = json.loads(target_path.read_text(encoding="utf-8"))
        return PipelineDisagreementLedger(**data)


class ShadowWriteFirewallViolation(PermissionError):
    """Raised when a shadow execution attempts to publish or mutate production consumer stores."""
    pass


PROHIBITED_PRODUCTION_STORES: set[str] = {
    "production_relationship_tables",
    "production_semantic_evidence_stores",
    "executive_topics",
    "production_vector_indexes",
    "dashboard_cache",
    "presentation_context",
    "hriday_retrieval_state",
    "pulsehr_sqlite3",
}


class ShadowHarness:
    """
    Harness executing shadow runs against V1 outputs.
    Enforces Phase I1 safety invariants:
    - Zero model calls (LLM calls strictly forbidden).
    - Zero production database mutation (P0 isolation).
    - Consumer cutover locked to False.
    - Zero writes to production consumer stores.
    """

    def __init__(self, storage_manager: ShadowStorageManager | None = None):
        self.storage = storage_manager or ShadowStorageManager()

    def attempt_publish_to_production(self, store_name: str, payload: Any = None) -> None:
        """
        P0 Shadow Write Firewall:
        Explicitly intercepts and blocks any attempt by shadow execution to write to
        production consumer stores, database tables, or caches.
        """
        normalized_name = store_name.strip().lower()
        raise ShadowWriteFirewallViolation(
            f"P0 Shadow Write Firewall: Attempted write to production store '{store_name}' is BLOCKED. "
            f"V2 shadow execution is isolated and forbidden from mutating production state."
        )

    def create_shadow_run(
        self,
        v1_dataset_id: str,
        v1_run_id: str,
        consumer_cutover_attempt: bool = False,
    ) -> ShadowPipelineRun:
        """
        Initializes a new shadow pipeline execution.
        Raises RuntimeError if any attempt is made to enable consumer cutover in Phase I1.
        """
        if consumer_cutover_attempt:
            raise RuntimeError(
                "Consumer cutover is strictly prohibited in Phase I1. "
                "Ingestion V2 must execute in SHADOW mode only with zero consumer disruption."
            )

        shadow_run_id = f"shadow-{uuid.uuid4().hex[:12]}"
        now_utc = datetime.now(timezone.utc).isoformat()

        run = ShadowPipelineRun(
            shadow_run_id=shadow_run_id,
            v1_dataset_id=v1_dataset_id,
            v1_run_id=v1_run_id,
            status=ShadowExecutionStatus.RUNNING,
            current_internal_stage=InternalStage.RAW_INGESTION,
            completed_internal_stages=[],
            consumer_cutover_allowed=False,
            stage_fingerprints={},
            execution_start_utc=now_utc,
        )
        self.storage.save_run(run)
        return run

    def record_stage_execution(
        self,
        shadow_run_id: str,
        stage: InternalStage,
        stage_payload: Any,
    ) -> ShadowPipelineRun:
        """
        Records the completion of an internal stage, calculating its deterministic fingerprint.
        """
        run = self.storage.load_run(shadow_run_id)
        if not run:
            raise ValueError(f"Shadow run {shadow_run_id} not found.")

        fingerprint = compute_stage_fingerprint(stage_payload)
        updated_fingerprints = dict(run.stage_fingerprints)
        updated_fingerprints[stage.value] = fingerprint

        completed = list(run.completed_internal_stages)
        if stage not in completed:
            completed.append(stage)

        updated_run = run.model_copy(
            update={
                "current_internal_stage": stage,
                "completed_internal_stages": completed,
                "stage_fingerprints": updated_fingerprints,
            }
        )
        self.storage.save_run(updated_run)
        return updated_run

    def audit_comparison(
        self,
        shadow_run_id: str,
        dataset_id: str,
        disagreements: list[PipelineDisagreementRecord],
    ) -> PipelineDisagreementLedger:
        """
        Generates and persists a PipelineDisagreementLedger from audit comparisons.
        Categorizes differences into UNCHANGED, EXPECTED_IMPROVEMENT, and EXPECTED_DIFFERENCE.
        """
        unchanged_violations = sum(
            1 for d in disagreements if d.comparison_class == ComparisonClass.UNCHANGED
        )
        expected_improvements = sum(
            1 for d in disagreements if d.comparison_class == ComparisonClass.EXPECTED_IMPROVEMENT
        )
        expected_differences = sum(
            1 for d in disagreements if d.comparison_class == ComparisonClass.EXPECTED_DIFFERENCE
        )

        total_expected_fixes = sum(
            1 for d in disagreements if d.disagreement_type == DisagreementType.EXPECTED_FIX
        )
        total_expected_refactors = sum(
            1 for d in disagreements if d.disagreement_type == DisagreementType.EXPECTED_REFACTOR
        )
        total_regressions = sum(
            1 for d in disagreements if d.disagreement_type == DisagreementType.REGRESSION
        )
        total_unresolved = sum(
            1 for d in disagreements if d.disagreement_type == DisagreementType.UNRESOLVED
        )

        critical_regressions_or_unresolved = any(
            d.severity in {Severity.CRITICAL, Severity.BLOCKER}
            and d.disagreement_type in {DisagreementType.REGRESSION, DisagreementType.UNRESOLVED}
            for d in disagreements
        )
        blocks_cutover = unchanged_violations > 0 or critical_regressions_or_unresolved

        requires_review = blocks_cutover or any(
            d.severity in {Severity.CRITICAL, Severity.BLOCKER} for d in disagreements
        )

        source_fp = compute_stage_fingerprint({"shadow_run_id": shadow_run_id, "dataset_id": dataset_id})

        ledger = PipelineDisagreementLedger(
            dataset_id=dataset_id,
            run_id=shadow_run_id,
            source_fingerprint=source_fp,
            shadow_run_id=shadow_run_id,
            records=disagreements,
            total_unchanged_violations=unchanged_violations,
            total_expected_improvements=expected_improvements,
            total_expected_differences=expected_differences,
            total_expected_fixes=total_expected_fixes,
            total_expected_refactors=total_expected_refactors,
            total_regressions=total_regressions,
            total_unresolved=total_unresolved,
            blocks_cutover=blocks_cutover,
            requires_human_review=requires_review,
        ).with_fingerprint()

        self.storage.save_ledger(ledger)

        # Update run status
        run = self.storage.load_run(shadow_run_id)
        if run:
            final_status = (
                ShadowExecutionStatus.DISAGREEMENT_DETECTED
                if requires_review
                else ShadowExecutionStatus.COMPLETED
            )
            updated_run = run.model_copy(
                update={
                    "status": final_status,
                    "execution_end_utc": datetime.now(timezone.utc).isoformat(),
                }
            )
            self.storage.save_run(updated_run)

        return ledger
