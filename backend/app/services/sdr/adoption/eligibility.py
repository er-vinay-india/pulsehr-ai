"""
HighView Semantic Data Refinery — Phase SDR-9
SDR Adoption Eligibility & Safety Evaluator
Enforces multi-layer safety invariants before allowing any consumer to route to SDR.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from app.core import config
from app.services.ingestion_v2.contracts.cutover import FallbackReason
from app.services.sdr.adoption.contracts import SDREligibilityAssessment

logger = logging.getLogger(__name__)

REQUIRED_SDR_ARTIFACTS = [
    "analytical_views.json",
    "analytical_facts.json",
    "join_plans.json",
]


class SDREligibilityEvaluator:
    """
    Evaluates dataset readiness, version alignment, contract compatibility,
    and semantic safety before authorizing an SDR route.
    """

    @classmethod
    def evaluate(
        cls,
        dataset_id: str,
        requested_version: str | None = None,
        expected_contract_fingerprint: str | None = None,
        manifest_data: dict[str, Any] | None = None,
        base_data_dir: Path | str | None = None,
    ) -> SDREligibilityAssessment:
        base_dir = Path(base_data_dir) if base_data_dir else getattr(config, "DATA_DIR", Path("data"))
        sdr_dir = base_dir / "datasets" / str(dataset_id) / "sdr"

        rejections: list[str] = []
        fallback_reason: FallbackReason | None = None

        if not sdr_dir.exists():
            return SDREligibilityAssessment(
                is_eligible=False,
                dataset_id=str(dataset_id),
                dataset_version=requested_version or "unknown",
                missing_artifacts=["sdr_directory"],
                rejection_reasons=["SDR artifact directory does not exist for dataset"],
                fallback_reason=FallbackReason.V2_ARTIFACT_MISSING,
                notes="Dataset lacks SDR directory",
            )

        # 1. Check artifact presence
        missing: list[str] = []
        for art in REQUIRED_SDR_ARTIFACTS:
            if not (sdr_dir / art).exists():
                missing.append(art)

        if missing:
            return SDREligibilityAssessment(
                is_eligible=False,
                dataset_id=str(dataset_id),
                dataset_version=requested_version or "unknown",
                missing_artifacts=missing,
                rejection_reasons=[f"Missing required SDR artifacts: {missing}"],
                fallback_reason=FallbackReason.V2_ARTIFACT_MISSING,
                notes="Missing required artifacts",
            )

        # Compute artifact fingerprint
        art_hashes: list[str] = []
        for art in REQUIRED_SDR_ARTIFACTS:
            art_hashes.append(hashlib.sha256((sdr_dir / art).read_bytes()).hexdigest()[:16])
        sdr_fingerprint = hashlib.sha256(":".join(art_hashes).encode("utf-8")).hexdigest()

        # 2. Dataset Version & Manifest Check
        if manifest_data is None:
            m_path = base_dir / "datasets" / str(dataset_id) / "manifest.json"
            if m_path.exists():
                try:
                    with open(m_path, "r", encoding="utf-8") as f:
                        manifest_data = json.load(f)
                except Exception:
                    pass

        actual_version = "v1"
        if manifest_data and "dataset_version" in manifest_data:
            actual_version = str(manifest_data["dataset_version"])

        if requested_version and requested_version != actual_version:
            return SDREligibilityAssessment(
                is_eligible=False,
                dataset_id=str(dataset_id),
                dataset_version=actual_version,
                sdr_artifact_fingerprint=sdr_fingerprint,
                rejection_reasons=[f"Dataset version mismatch: requested={requested_version} vs actual={actual_version}"],
                fallback_reason=FallbackReason.V2_DATASET_VERSION_MISMATCH,
                notes="Version mismatch detected",
            )

        # 3. Consumer Contract Fingerprint Check
        if expected_contract_fingerprint:
            # Hash expected contract against active SDR schema fingerprint
            if expected_contract_fingerprint != sdr_fingerprint and expected_contract_fingerprint != "MATCH":
                return SDREligibilityAssessment(
                    is_eligible=False,
                    dataset_id=str(dataset_id),
                    dataset_version=actual_version,
                    sdr_artifact_fingerprint=sdr_fingerprint,
                    consumer_contract_fingerprint=expected_contract_fingerprint,
                    rejection_reasons=["Consumer contract fingerprint mismatch with SDR artifacts"],
                    fallback_reason=FallbackReason.V2_SCHEMA_CONTRACT_FAILURE,
                    notes="Contract mismatch detected",
                )

        # 4. View Staleness & JoinPlan Safety Checks
        valid_views = 0
        stale_views = 0
        valid_plans = 0
        unsafe_joins = 0
        ambiguous_joins = 0
        missing_evidence = 0
        invalid_units = 0
        invalid_grains = 0
        invalid_denominators = 0
        artifact_not_current = False
        sdr8_uncertified = False
        critical_unresolved = False

        # Check metadata/manifest currentness
        if manifest_data:
            if manifest_data.get("artifact_current") is False or manifest_data.get("is_current") is False:
                artifact_not_current = True
            if manifest_data.get("sdr8_certified") is False:
                sdr8_uncertified = True
            if manifest_data.get("shadow_status") in ("REGRESSION", "UNRESOLVED") or manifest_data.get("critical_regression") is True:
                critical_unresolved = True

        views_path = sdr_dir / "analytical_views.json"
        try:
            with open(views_path, "r", encoding="utf-8") as f:
                views_data = json.load(f)
                if isinstance(views_data, dict):
                    if views_data.get("artifact_current") is False or views_data.get("is_current") is False:
                        artifact_not_current = True
                    if views_data.get("sdr8_certified") is False:
                        sdr8_uncertified = True
                    views_list = views_data.get("views", [])
                elif isinstance(views_data, list):
                    views_list = views_data
                else:
                    views_list = []

                for v in views_list:
                    status = v.get("status")
                    if status in ("VALID", "VALID_WITH_PREAGGREGATION", "SAFE"):
                        valid_views += 1
                    elif status == "STALE" or v.get("is_stale") is True:
                        stale_views += 1
                    elif status == "UNSAFE":
                        unsafe_joins += 1
                    elif status == "AMBIGUOUS":
                        ambiguous_joins += 1

                    if v.get("artifact_current") is False or v.get("is_current") is False:
                        artifact_not_current = True
                    if v.get("missing_evidence") is True or v.get("has_evidence") is False:
                        missing_evidence += 1
                    if v.get("invalid_unit") is True or v.get("unit_conflict") is True or v.get("unit") == "CONFLICT":
                        invalid_units += 1
                    if v.get("invalid_grain") is True or v.get("grain") == "INVALID":
                        invalid_grains += 1
                    if v.get("invalid_denominator") is True or v.get("denominator_valid") is False:
                        invalid_denominators += 1
        except Exception as exc:
            logger.warning("Failed to parse analytical views for %s: %s", dataset_id, exc)

        plans_path = sdr_dir / "join_plans.json"
        try:
            with open(plans_path, "r", encoding="utf-8") as f:
                plans_data = json.load(f)
                plans_list = plans_data if isinstance(plans_data, list) else plans_data.get("join_plans", [])
                for p in plans_list:
                    status = p.get("safety_status") or p.get("status")
                    if status in ("SAFE", "SAFE_WITH_PREAGGREGATION", "VALID"):
                        valid_plans += 1
                    elif status == "UNSAFE":
                        unsafe_joins += 1
                    elif status == "AMBIGUOUS":
                        ambiguous_joins += 1
        except Exception as exc:
            logger.warning("Failed to parse join plans for %s: %s", dataset_id, exc)

        facts_path = sdr_dir / "analytical_facts.json"
        try:
            with open(facts_path, "r", encoding="utf-8") as f:
                facts_data = json.load(f)
                facts_list = facts_data if isinstance(facts_data, list) else facts_data.get("facts", [])
                if not facts_list:
                    missing_evidence += 1
                for ft in facts_list:
                    has_ev = bool(ft.get("evidence_id") or ft.get("source_evidence_ids"))
                    if not has_ev or ft.get("missing_evidence") is True:
                        missing_evidence += 1
                    if ft.get("invalid_unit") is True or ft.get("unit") == "CONFLICT":
                        invalid_units += 1
                    if ft.get("invalid_grain") is True or ft.get("grain") == "INVALID":
                        invalid_grains += 1
                    if ft.get("invalid_denominator") is True or ft.get("denominator_valid") is False:
                        invalid_denominators += 1
                    if ft.get("status") in ("REGRESSION", "UNRESOLVED") or ft.get("critical_regression") is True:
                        critical_unresolved = True
        except Exception as exc:
            logger.warning("Failed to parse analytical facts for %s: %s", dataset_id, exc)

        if artifact_not_current:
            rejections.append("Blocked due to artifact current = false")
            fallback_reason = fallback_reason or FallbackReason.V2_ARTIFACT_STALE

        if sdr8_uncertified:
            rejections.append("Blocked due to missing SDR-8 certification")
            fallback_reason = fallback_reason or FallbackReason.STATE_NOT_V2_ELIGIBLE

        if critical_unresolved:
            rejections.append("Blocked due to critical or unresolved shadow comparison")
            fallback_reason = fallback_reason or FallbackReason.V2_CONTEXT_GROUNDING_FAILURE

        if missing_evidence > 0:
            rejections.append(f"Blocked due to {missing_evidence} facts with missing analytical evidence")
            fallback_reason = fallback_reason or FallbackReason.V2_ANALYTICAL_EVIDENCE_MISSING

        if invalid_units > 0:
            rejections.append(f"Blocked due to {invalid_units} metrics with invalid unit or unit conflicts")
            fallback_reason = fallback_reason or FallbackReason.V2_SCHEMA_CONTRACT_FAILURE

        if invalid_grains > 0:
            rejections.append(f"Blocked due to {invalid_grains} metrics with invalid grain")
            fallback_reason = fallback_reason or FallbackReason.V2_SCHEMA_CONTRACT_FAILURE

        if invalid_denominators > 0:
            rejections.append(f"Blocked due to {invalid_denominators} metrics with invalid denominator")
            fallback_reason = fallback_reason or FallbackReason.V2_SCHEMA_CONTRACT_FAILURE

        # A dataset is blocked if it has 0 valid views and at least 1 stale view
        if valid_views == 0 and stale_views > 0:
            rejections.append(f"Blocked due to {stale_views} STALE analytical views with 0 valid views")
            fallback_reason = fallback_reason or FallbackReason.V2_ARTIFACT_STALE

        # A dataset is blocked if it has 0 valid plans and at least 1 unsafe join
        if valid_plans == 0 and unsafe_joins > 0:
            rejections.append(f"Blocked due to {unsafe_joins} UNSAFE JoinPlans with 0 valid plans")
            fallback_reason = fallback_reason or FallbackReason.V2_JOIN_PLAN_UNAVAILABLE

        # A dataset is blocked if it has 0 valid plans and at least 1 ambiguous join
        if valid_plans == 0 and ambiguous_joins > 0:
            rejections.append(f"Blocked due to {ambiguous_joins} AMBIGUOUS JoinPlans with 0 valid plans")
            fallback_reason = fallback_reason or FallbackReason.V2_RELATIONSHIP_AMBIGUOUS

        is_eligible = (len(rejections) == 0)

        return SDREligibilityAssessment(
            is_eligible=is_eligible,
            dataset_id=str(dataset_id),
            dataset_version=actual_version,
            sdr_artifact_fingerprint=sdr_fingerprint,
            consumer_contract_fingerprint=expected_contract_fingerprint or sdr_fingerprint,
            stale_views_count=stale_views,
            unsafe_joins_count=unsafe_joins,
            ambiguous_joins_count=ambiguous_joins,
            rejection_reasons=rejections,
            fallback_reason=fallback_reason,
            notes="Eligibility evaluation completed",
        )
