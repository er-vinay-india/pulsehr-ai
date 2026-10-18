"""
HighView Ingestion V2 — Phase I8.2 Consumer Readiness Evaluator
Stage: Governed Consumer Gateway & Readiness Guards
Inspects V2 dataset manifests, artifact completeness, freshness, version matching,
and evidence grounding before authorizing any V2 route.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.ingestion_v2.contracts.cutover import (
    FallbackReason,
    ReadinessAssessment,
)


class ConsumerReadinessEvaluator:
    """
    Evaluates whether a dataset and its V2 pipeline artifacts are valid, fresh,
    grounded, and version-aligned for consumer consumption.
    """

    @classmethod
    def evaluate(
        cls,
        dataset_id: str,
        requested_version: str | None = None,
        manifest_data: dict[str, Any] | None = None,
        required_artifacts: list[str] | None = None,
        required_evidence_refs: list[str] | None = None,
        available_evidence_ids: set[str] | None = None,
    ) -> ReadinessAssessment:
        """
        Performs comprehensive, hermetic readiness evaluation for a V2 dataset.
        Fails closed with explicit FallbackReason if any check fails.
        """
        failure_reasons: list[FallbackReason] = []
        missing_artifacts: list[str] = []

        # 1. Manifest Existence Guard
        if manifest_data is None:
            failure_reasons.append(FallbackReason.V2_ARTIFACT_MISSING)
            return ReadinessAssessment(
                is_ready=False,
                dataset_id=dataset_id,
                dataset_version=requested_version or "unknown",
                manifest_exists=False,
                manifest_fresh=False,
                missing_artifacts=["v2_manifest.json"],
                failure_reasons=failure_reasons,
                notes="V2 manifest does not exist for dataset",
            )

        manifest_version = str(manifest_data.get("dataset_version", "1"))
        manifest_fresh = bool(manifest_data.get("is_fresh", True))
        manifest_fp = manifest_data.get("manifest_fingerprint")
        semantic_graph_fp = manifest_data.get("semantic_graph_fingerprint")

        # 2. Manifest Freshness Guard
        if not manifest_fresh:
            failure_reasons.append(FallbackReason.V2_ARTIFACT_STALE)

        # 3. Dataset Version Guard
        if requested_version and str(requested_version) != manifest_version:
            failure_reasons.append(FallbackReason.V2_DATASET_VERSION_MISMATCH)

        # 4. Required Artifacts Completeness Guard
        available_artifacts = set(manifest_data.get("available_artifacts", []))
        if required_artifacts:
            for art in required_artifacts:
                if art not in available_artifacts:
                    missing_artifacts.append(art)
            if missing_artifacts:
                failure_reasons.append(FallbackReason.V2_ARTIFACT_MISSING)

        # 5. Evidence Grounding Guard
        evidence_valid = True
        if required_evidence_refs:
            ev_pool = available_evidence_ids if available_evidence_ids is not None else set(manifest_data.get("evidence_ids", []))
            for ref in required_evidence_refs:
                # Must match valid syntactic pattern AND actually exist in the evidence graph pool
                if not re.match(r"^EVID-[A-Za-z0-9_-]+$", ref):
                    evidence_valid = False
                    break
                if ref not in ev_pool:
                    evidence_valid = False
                    break
            if not evidence_valid:
                failure_reasons.append(FallbackReason.V2_CONTEXT_GROUNDING_FAILURE)

        is_ready = len(failure_reasons) == 0

        return ReadinessAssessment(
            is_ready=is_ready,
            dataset_id=dataset_id,
            dataset_version=manifest_version,
            manifest_exists=True,
            manifest_fresh=manifest_fresh,
            manifest_fingerprint=manifest_fp,
            semantic_graph_fingerprint=semantic_graph_fp,
            missing_artifacts=missing_artifacts,
            evidence_grounding_valid=evidence_valid,
            failure_reasons=failure_reasons,
            notes="Dataset readiness checks passed" if is_ready else f"Readiness checks failed: {[r.value for r in failure_reasons]}",
        )
