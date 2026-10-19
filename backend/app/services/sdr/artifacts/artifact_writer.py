"""
HighView Semantic Data Refinery — Phase SDR-1
Deterministic Artifact Writer & Persistence
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

from app.services.sdr.contracts.decomposition import SemanticDecompositionCandidate
from app.services.sdr.contracts.enrichment import (
    EnrichmentCandidate,
    EnrichmentDecisionRecord,
    ValidatedEnrichment,
)
from app.services.sdr.contracts.keys import (
    ObservedFunctionalDependency,
    SDRKeyCandidate,
)
from app.services.sdr.contracts.policies import SDRPolicySuite
from app.services.sdr.contracts.profiles import SemanticColumnProfile


class SDRArtifactWriter:
    """
    Persists SDR-1 profiling and decomposition artifacts into dataset-isolated JSON stores.
    Guarantees deterministic serialization and byte-identical P0 database isolation.
    """

    def __init__(self, base_data_dir: Path | str | None = None, base_dir: Path | str | None = None):
        chosen = base_dir if base_dir is not None else base_data_dir
        if chosen is None:
            # Default to backend/data
            self.base_dir = Path(__file__).resolve().parents[4] / "data"
        else:
            self.base_dir = Path(chosen)

    def get_dataset_sdr_dir(self, dataset_id: str) -> Path:
        """Returns isolated SDR directory for a dataset."""
        sdr_dir = self.base_dir / "datasets" / dataset_id / "sdr"
        sdr_dir.mkdir(parents=True, exist_ok=True)
        return sdr_dir

    def write_artifacts(
        self,
        dataset_id: str,
        profiles: Sequence[SemanticColumnProfile],
        candidates: Sequence[SemanticDecompositionCandidate],
        policy_suite: SDRPolicySuite | None = None,
    ) -> dict[str, str]:
        """
        Writes canonical JSON artifacts:
        - semantic_column_profiles.json
        - decomposition_candidates.json
        - profiling_manifest.json
        Returns a dict of file paths to their deterministic SHA-256 hashes.
        """
        sdr_dir = self.get_dataset_sdr_dir(dataset_id)
        policy = policy_suite or SDRPolicySuite()
        policy_fp = policy.compute_policy_fingerprint()

        # 1. Serialize semantic column profiles
        sorted_profiles = sorted(profiles, key=lambda p: (p.sheet_id, p.column_id))
        profiles_data = [p.model_dump() for p in sorted_profiles]
        profiles_json = json.dumps(profiles_data, indent=2, sort_keys=True)
        profiles_path = sdr_dir / "semantic_column_profiles.json"
        profiles_path.write_text(profiles_json, encoding="utf-8")
        profiles_hash = hashlib.sha256(profiles_json.encode("utf-8")).hexdigest()

        # 2. Serialize decomposition candidates
        sorted_candidates = sorted(candidates, key=lambda c: (c.sheet_id, c.source_column_id, c.pattern_type.value))
        candidates_data = [c.model_dump() for c in sorted_candidates]
        candidates_json = json.dumps(candidates_data, indent=2, sort_keys=True)
        candidates_path = sdr_dir / "decomposition_candidates.json"
        candidates_path.write_text(candidates_json, encoding="utf-8")
        candidates_hash = hashlib.sha256(candidates_json.encode("utf-8")).hexdigest()

        # 3. Create and serialize manifest
        manifest_payload = {
            "dataset_id": dataset_id,
            "policy_fingerprint": policy_fp,
            "profiles_count": len(sorted_profiles),
            "candidates_count": len(sorted_candidates),
            "profiles_hash": profiles_hash,
            "candidates_hash": candidates_hash,
        }
        manifest_json = json.dumps(manifest_payload, indent=2, sort_keys=True)
        manifest_path = sdr_dir / "profiling_manifest.json"
        manifest_path.write_text(manifest_json, encoding="utf-8")
        manifest_hash = hashlib.sha256(manifest_json.encode("utf-8")).hexdigest()

        return {
            "semantic_column_profiles": str(profiles_path),
            "decomposition_candidates": str(candidates_path),
            "profiling_manifest": str(manifest_path),
            "manifest_fingerprint": manifest_hash,
        }

    def write_sdr2_artifacts(
        self,
        dataset_id: str,
        entity_hypotheses: Sequence[Any],
        grain_profiles: Sequence[Any],
        grain_candidates: Sequence[Any],
        policy_suite: SDRPolicySuite | None = None,
    ) -> dict[str, str]:
        """
        Writes canonical SDR-2 artifacts:
        - entity_hypotheses.json
        - grain_profiles.json
        - grain_candidates.json
        - sdr2_manifest.json
        """
        sdr_dir = self.get_dataset_sdr_dir(dataset_id)
        policy = policy_suite or SDRPolicySuite()
        policy_fp = policy.compute_policy_fingerprint()

        # 1. Entity Hypotheses
        sorted_hypotheses = sorted(entity_hypotheses, key=lambda h: (h.sheet_id, h.canonical_name))
        hyp_data = [h.model_dump() for h in sorted_hypotheses]
        hyp_json = json.dumps(hyp_data, indent=2, sort_keys=True)
        hyp_path = sdr_dir / "entity_hypotheses.json"
        hyp_path.write_text(hyp_json, encoding="utf-8")
        hyp_hash = hashlib.sha256(hyp_json.encode("utf-8")).hexdigest()

        # 2. Grain Profiles
        sorted_grain_profiles = sorted(grain_profiles, key=lambda g: g.sheet_id)
        grain_data = [g.model_dump() for g in sorted_grain_profiles]
        grain_json = json.dumps(grain_data, indent=2, sort_keys=True)
        grain_path = sdr_dir / "grain_profiles.json"
        grain_path.write_text(grain_json, encoding="utf-8")
        grain_hash = hashlib.sha256(grain_json.encode("utf-8")).hexdigest()

        # 3. Grain Candidates
        sorted_candidates = sorted(grain_candidates, key=lambda c: (c.candidate_id, c.confidence))
        cand_data = [c.model_dump() for c in sorted_candidates]
        cand_json = json.dumps(cand_data, indent=2, sort_keys=True)
        cand_path = sdr_dir / "grain_candidates.json"
        cand_path.write_text(cand_json, encoding="utf-8")
        cand_hash = hashlib.sha256(cand_json.encode("utf-8")).hexdigest()

        # 4. SDR-2 Manifest
        sdr2_manifest = {
            "dataset_id": dataset_id,
            "policy_fingerprint": policy_fp,
            "entity_hypotheses_count": len(sorted_hypotheses),
            "grain_profiles_count": len(sorted_grain_profiles),
            "grain_candidates_count": len(sorted_candidates),
            "entity_hypotheses_hash": hyp_hash,
            "grain_profiles_hash": grain_hash,
            "grain_candidates_hash": cand_hash,
        }
        manifest_json = json.dumps(sdr2_manifest, indent=2, sort_keys=True)
        manifest_path = sdr_dir / "sdr2_manifest.json"
        manifest_path.write_text(manifest_json, encoding="utf-8")
        manifest_hash = hashlib.sha256(manifest_json.encode("utf-8")).hexdigest()

        return {
            "entity_hypotheses": str(hyp_path),
            "grain_profiles": str(grain_path),
            "grain_candidates": str(cand_path),
            "sdr2_manifest": str(manifest_path),
            "manifest_fingerprint": manifest_hash,
        }

    def write_sdr3_artifacts(
        self,
        dataset_id: str,
        key_candidates: Sequence[SDRKeyCandidate] | None = None,
        functional_dependencies: Sequence[ObservedFunctionalDependency] | None = None,
        policy_suite: SDRPolicySuite | None = None,
        sheet_id: str | None = None,
        candidates: Sequence[SDRKeyCandidate] | None = None,
        dependencies: Sequence[ObservedFunctionalDependency] | None = None,
        manifest: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """
        Writes canonical SDR-3 artifacts:
        - key_candidates.json
        - functional_dependencies.json
        - sdr3_manifest.json
        """
        sdr_dir = self.get_dataset_sdr_dir(dataset_id)
        policy = policy_suite or SDRPolicySuite()
        policy_fp = policy.compute_policy_fingerprint()

        actual_keys = list(key_candidates if key_candidates is not None else (candidates or []))
        actual_fds = list(functional_dependencies if functional_dependencies is not None else (dependencies or []))

        # 1. Key Candidates
        sorted_keys = sorted(actual_keys, key=lambda k: (k.sheet_id, k.candidate_id))
        key_data = [k.model_dump() for k in sorted_keys]
        key_json = json.dumps(key_data, indent=2, sort_keys=True)
        key_path = sdr_dir / "key_candidates.json"
        key_path.write_text(key_json, encoding="utf-8")
        key_hash = hashlib.sha256(key_json.encode("utf-8")).hexdigest()

        # 2. Functional Dependencies
        sorted_fds = sorted(actual_fds, key=lambda f: (f.sheet_id, f.fd_id))
        fd_data = [f.model_dump() for f in sorted_fds]
        fd_json = json.dumps(fd_data, indent=2, sort_keys=True)
        fd_path = sdr_dir / "functional_dependencies.json"
        fd_path.write_text(fd_json, encoding="utf-8")
        fd_hash = hashlib.sha256(fd_json.encode("utf-8")).hexdigest()

        # 3. SDR-3 Manifest
        sdr3_manifest = {
            "dataset_id": dataset_id,
            "policy_fingerprint": policy_fp,
            "key_candidates_count": len(sorted_keys),
            "functional_dependencies_count": len(sorted_fds),
            "key_candidates_hash": key_hash,
            "functional_dependencies_hash": fd_hash,
        }
        manifest_json = json.dumps(sdr3_manifest, indent=2, sort_keys=True)
        manifest_path = sdr_dir / "sdr3_manifest.json"
        manifest_path.write_text(manifest_json, encoding="utf-8")
        manifest_hash = hashlib.sha256(manifest_json.encode("utf-8")).hexdigest()

        return {
            "key_candidates": str(key_path),
            "functional_dependencies": str(fd_path),
            "sdr3_manifest": str(manifest_path),
            "manifest_fingerprint": manifest_hash,
        }

    def write_sdr4_artifacts(
        self,
        dataset_id: str,
        candidates: Sequence[EnrichmentCandidate] | None = None,
        validated_enrichments: Sequence[ValidatedEnrichment] | None = None,
        decisions: Sequence[EnrichmentDecisionRecord] | None = None,
        policy_suite: SDRPolicySuite | None = None,
        sheet_id: str | None = None,
        manifest: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """
        Writes canonical SDR-4 artifacts:
        - enrichment_candidates.json
        - validated_enrichments.json
        - enrichment_decisions.json
        - sdr4_manifest.json
        """
        sdr_dir = self.get_dataset_sdr_dir(dataset_id)
        policy = policy_suite or SDRPolicySuite()
        policy_fp = policy.compute_policy_fingerprint()

        actual_candidates = list(candidates or [])
        actual_validated = list(validated_enrichments or [])
        actual_decisions = list(decisions or [])

        # 1. Enrichment Candidates
        sorted_candidates = sorted(actual_candidates, key=lambda c: (c.sheet_id, c.candidate_id))
        cand_data = [c.model_dump() for c in sorted_candidates]
        cand_json = json.dumps(cand_data, indent=2, sort_keys=True)
        cand_path = sdr_dir / "enrichment_candidates.json"
        cand_path.write_text(cand_json, encoding="utf-8")
        cand_hash = hashlib.sha256(cand_json.encode("utf-8")).hexdigest()

        # 2. Validated Enrichments
        sorted_val = sorted(actual_validated, key=lambda v: (v.sheet_id, v.enrichment_id))
        val_data = [v.model_dump() for v in sorted_val]
        val_json = json.dumps(val_data, indent=2, sort_keys=True)
        val_path = sdr_dir / "validated_enrichments.json"
        val_path.write_text(val_json, encoding="utf-8")
        val_hash = hashlib.sha256(val_json.encode("utf-8")).hexdigest()

        # 3. Enrichment Decisions
        sorted_dec = sorted(actual_decisions, key=lambda d: (d.sheet_id, d.decision_id))
        dec_data = [d.model_dump() for d in sorted_dec]
        dec_json = json.dumps(dec_data, indent=2, sort_keys=True)
        dec_path = sdr_dir / "enrichment_decisions.json"
        dec_path.write_text(dec_json, encoding="utf-8")
        dec_hash = hashlib.sha256(dec_json.encode("utf-8")).hexdigest()

        # 4. SDR-4 Manifest
        sdr4_manifest = {
            "dataset_id": dataset_id,
            "policy_fingerprint": policy_fp,
            "candidates_count": len(sorted_candidates),
            "validated_enrichments_count": len(sorted_val),
            "decisions_count": len(sorted_dec),
            "candidates_hash": cand_hash,
            "validated_enrichments_hash": val_hash,
            "decisions_hash": dec_hash,
        }
        if manifest:
            sdr4_manifest["engine_manifest"] = manifest

        manifest_json = json.dumps(sdr4_manifest, indent=2, sort_keys=True)
        manifest_path = sdr_dir / "sdr4_manifest.json"
        manifest_path.write_text(manifest_json, encoding="utf-8")
        manifest_hash = hashlib.sha256(manifest_json.encode("utf-8")).hexdigest()

        return {
            "enrichment_candidates": str(cand_path),
            "validated_enrichments": str(val_path),
            "enrichment_decisions": str(dec_path),
            "sdr4_manifest": str(manifest_path),
            "manifest_fingerprint": manifest_hash,
        }


