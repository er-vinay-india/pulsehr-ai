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
from app.services.sdr.contracts.policies import SDRPolicySuite
from app.services.sdr.contracts.profiles import SemanticColumnProfile


class SDRArtifactWriter:
    """
    Persists SDR-1 profiling and decomposition artifacts into dataset-isolated JSON stores.
    Guarantees deterministic serialization and byte-identical P0 database isolation.
    """

    def __init__(self, base_data_dir: Path | str | None = None):
        if base_data_dir is None:
            # Default to backend/data
            self.base_dir = Path(__file__).resolve().parents[4] / "data"
        else:
            self.base_dir = Path(base_data_dir)

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
