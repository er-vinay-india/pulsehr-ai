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
from app.services.sdr.contracts.relationships import (
    SDRJoinPlan,
    SDRRelationshipCandidate,
    SDRValidatedRelationshipEdge,
)
from app.services.sdr.contracts.views import (
    SDRAnalyticalExecutionResult,
    SDRAnalyticalFact,
    SDRAnalyticalViewSpec,
)
from app.services.sdr.geo.contracts import CanonicalGeoEntity, GeoResolutionCandidate


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

    def write_sdr4g_artifacts(
        self,
        dataset_id: str,
        geo_resolution_candidates: Sequence[GeoResolutionCandidate] | None = None,
        canonical_geo_resolutions: Sequence[CanonicalGeoEntity] | None = None,
        geo_enrichments: Sequence[ValidatedEnrichment] | None = None,
        resolutions: Sequence[GeoResolutionCandidate] | None = None,
        canonical_entities: Sequence[CanonicalGeoEntity] | None = None,
        sheet_id: str | None = None,
        policy_suite: SDRPolicySuite | None = None,
        manifest: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """
        Writes canonical SDR-4G artifacts:
        - geo_resolution_candidates.json
        - canonical_geo_resolutions.json
        - geo_enrichments.json
        - geo_manifest.json
        """
        sdr_dir = self.get_dataset_sdr_dir(dataset_id)
        policy = policy_suite or SDRPolicySuite()
        policy_fp = policy.compute_policy_fingerprint()

        actual_cands = list(geo_resolution_candidates or resolutions or [])
        actual_ents = list(canonical_geo_resolutions or canonical_entities or [])
        actual_enrich = list(geo_enrichments or [])

        # 1. Geo Resolution Candidates
        sorted_cands = sorted(actual_cands, key=lambda c: (c.source_column_id, c.source_value))
        cand_data = [c.model_dump() for c in sorted_cands]
        cand_json = json.dumps(cand_data, indent=2, sort_keys=True)
        cand_path = sdr_dir / "geo_resolution_candidates.json"
        cand_path.write_text(cand_json, encoding="utf-8")
        cand_hash = hashlib.sha256(cand_json.encode("utf-8")).hexdigest()

        # 2. Canonical Geo Resolutions
        sorted_ents = sorted(actual_ents, key=lambda e: e.geo_entity_id)
        ent_data = [e.model_dump() for e in sorted_ents]
        ent_json = json.dumps(ent_data, indent=2, sort_keys=True)
        ent_path = sdr_dir / "canonical_geo_resolutions.json"
        ent_path.write_text(ent_json, encoding="utf-8")
        ent_hash = hashlib.sha256(ent_json.encode("utf-8")).hexdigest()

        # 3. Geo Enrichments
        sorted_enrich = sorted(actual_enrich, key=lambda e: (e.sheet_id, e.enrichment_id))
        enrich_data = [e.model_dump() for e in sorted_enrich]
        enrich_json = json.dumps(enrich_data, indent=2, sort_keys=True)
        enrich_path = sdr_dir / "geo_enrichments.json"
        enrich_path.write_text(enrich_json, encoding="utf-8")
        enrich_hash = hashlib.sha256(enrich_json.encode("utf-8")).hexdigest()

        # 4. Geo Manifest
        geo_manifest = {
            "dataset_id": dataset_id,
            "policy_fingerprint": policy_fp,
            "geo_candidates_count": len(sorted_cands),
            "canonical_resolutions_count": len(sorted_ents),
            "geo_enrichments_count": len(sorted_enrich),
            "geo_candidates_hash": cand_hash,
            "canonical_resolutions_hash": ent_hash,
            "geo_enrichments_hash": enrich_hash,
        }
        if sheet_id:
            geo_manifest["sheet_id"] = sheet_id
        if manifest:
            geo_manifest["engine_manifest"] = manifest

        manifest_json = json.dumps(geo_manifest, indent=2, sort_keys=True)
        manifest_path = sdr_dir / "geo_manifest.json"
        manifest_path.write_text(manifest_json, encoding="utf-8")
        manifest_hash = hashlib.sha256(manifest_json.encode("utf-8")).hexdigest()

        return {
            "geo_resolution_candidates": str(cand_path),
            "canonical_geo_resolutions": str(ent_path),
            "geo_resolutions": str(cand_path),
            "canonical_geo_entities": str(ent_path),
            "geo_enrichments": str(enrich_path),
            "geo_manifest": str(manifest_path),
            "manifest_fingerprint": manifest_hash,
        }

    def write_sdr5_artifacts(
        self,
        dataset_id: str,
        candidates: Sequence[SDRRelationshipCandidate],
        validated_edges: Sequence[SDRValidatedRelationshipEdge],
        join_plans: Sequence[SDRJoinPlan],
        policy_suite: SDRPolicySuite | None = None,
        discovery_stats: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """
        Writes canonical SDR-5 artifacts:
        - relationship_candidates.json
        - validated_relationships.json
        - join_plans.json
        - sdr5_manifest.json
        Returns a dict of file paths to their deterministic SHA-256 hashes.
        """
        sdr_dir = self.get_dataset_sdr_dir(dataset_id)
        policy = policy_suite or SDRPolicySuite()
        policy_fp = policy.compute_policy_fingerprint()

        # 1. Relationship Candidates
        sorted_cands = sorted(candidates, key=lambda c: c.candidate_id)
        cand_data = [c.model_dump() for c in sorted_cands]
        cand_json = json.dumps(cand_data, indent=2, sort_keys=True)
        cand_path = sdr_dir / "relationship_candidates.json"
        cand_path.write_text(cand_json, encoding="utf-8")
        cand_hash = hashlib.sha256(cand_json.encode("utf-8")).hexdigest()

        # 2. Validated Relationships
        sorted_edges = sorted(validated_edges, key=lambda e: e.edge_id)
        edge_data = [e.model_dump() for e in sorted_edges]
        edge_json = json.dumps(edge_data, indent=2, sort_keys=True)
        edge_path = sdr_dir / "validated_relationships.json"
        edge_path.write_text(edge_json, encoding="utf-8")
        edge_hash = hashlib.sha256(edge_json.encode("utf-8")).hexdigest()

        # 3. Governed JoinPlans
        sorted_plans = sorted(join_plans, key=lambda p: p.join_plan_id)
        plan_data = [p.model_dump() for p in sorted_plans]
        plan_json = json.dumps(plan_data, indent=2, sort_keys=True)
        plan_path = sdr_dir / "join_plans.json"
        plan_path.write_text(plan_json, encoding="utf-8")
        plan_hash = hashlib.sha256(plan_json.encode("utf-8")).hexdigest()

        # 4. SDR-5 Manifest
        safe_joins_count = sum(1 for p in sorted_plans if p.safety_status == "SAFE")
        preagg_joins_count = sum(1 for p in sorted_plans if p.safety_status == "SAFE_WITH_PREAGGREGATION")
        ambiguous_joins_count = sum(1 for p in sorted_plans if p.safety_status == "AMBIGUOUS")
        unsafe_joins_count = sum(1 for p in sorted_plans if p.safety_status == "UNSAFE")

        manifest = {
            "dataset_id": dataset_id,
            "policy_fingerprint": policy_fp,
            "candidates_count": len(sorted_cands),
            "validated_edges_count": len(sorted_edges),
            "join_plans_count": len(sorted_plans),
            "join_safety_summary": {
                "safe": safe_joins_count,
                "safe_with_preaggregation": preagg_joins_count,
                "ambiguous": ambiguous_joins_count,
                "unsafe": unsafe_joins_count,
            },
            "candidates_hash": cand_hash,
            "validated_relationships_hash": edge_hash,
            "join_plans_hash": plan_hash,
        }
        if discovery_stats:
            manifest["discovery_stats"] = discovery_stats

        manifest_json = json.dumps(manifest, indent=2, sort_keys=True)
        manifest_path = sdr_dir / "sdr5_manifest.json"
        manifest_path.write_text(manifest_json, encoding="utf-8")
        manifest_hash = hashlib.sha256(manifest_json.encode("utf-8")).hexdigest()

        return {
            "relationship_candidates": str(cand_path),
            "validated_relationships": str(edge_path),
            "join_plans": str(plan_path),
            "sdr5_manifest": str(manifest_path),
            "manifest_fingerprint": manifest_hash,
        }

    def write_sdr6_artifacts(
        self,
        dataset_id: str,
        views: Sequence[SDRAnalyticalViewSpec],
        facts: Sequence[SDRAnalyticalFact],
        execution_results: Sequence[SDRAnalyticalExecutionResult] | None = None,
        policy_suite: SDRPolicySuite | None = None,
        stats: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """
        Writes canonical SDR-6 artifacts:
        - analytical_views.json
        - analytical_facts.json
        - analytical_execution_manifest.json
        - sdr6_manifest.json
        Returns a dict of file paths to their deterministic SHA-256 hashes.
        """
        sdr_dir = self.get_dataset_sdr_dir(dataset_id)
        policy = policy_suite or SDRPolicySuite()
        policy_fp = policy.compute_policy_fingerprint()

        # 1. Analytical Views
        sorted_views = sorted(views, key=lambda v: v.analytical_view_id)
        view_data = [v.model_dump() for v in sorted_views]
        view_json = json.dumps(view_data, indent=2, sort_keys=True)
        view_path = sdr_dir / "analytical_views.json"
        view_path.write_text(view_json, encoding="utf-8")
        view_hash = hashlib.sha256(view_json.encode("utf-8")).hexdigest()

        # 2. Analytical Facts
        sorted_facts = sorted(facts, key=lambda f: f.fact_id)
        fact_data = [f.model_dump() for f in sorted_facts]
        fact_json = json.dumps(fact_data, indent=2, sort_keys=True)
        fact_path = sdr_dir / "analytical_facts.json"
        fact_path.write_text(fact_json, encoding="utf-8")
        fact_hash = hashlib.sha256(fact_json.encode("utf-8")).hexdigest()

        # 3. Execution Results
        exec_list = list(execution_results or [])
        sorted_execs = sorted(exec_list, key=lambda r: r.view_id)
        exec_data = [r.model_dump() for r in sorted_execs]
        exec_json = json.dumps(exec_data, indent=2, sort_keys=True)
        exec_path = sdr_dir / "analytical_execution_manifest.json"
        exec_path.write_text(exec_json, encoding="utf-8")
        exec_hash = hashlib.sha256(exec_json.encode("utf-8")).hexdigest()

        # 4. SDR-6 Manifest
        valid_views_count = sum(1 for v in sorted_views if v.status == "VALID")
        preagg_views_count = sum(1 for v in sorted_views if v.status == "VALID_WITH_PREAGGREGATION")
        ambiguous_views_count = sum(1 for v in sorted_views if v.status == "AMBIGUOUS")
        unsafe_views_count = sum(1 for v in sorted_views if v.status == "UNSAFE")
        stale_views_count = sum(1 for v in sorted_views if v.status == "STALE")

        manifest = {
            "dataset_id": dataset_id,
            "policy_fingerprint": policy_fp,
            "views_count": len(sorted_views),
            "facts_count": len(sorted_facts),
            "executions_count": len(sorted_execs),
            "view_status_summary": {
                "valid": valid_views_count,
                "valid_with_preaggregation": preagg_views_count,
                "ambiguous": ambiguous_views_count,
                "unsafe": unsafe_views_count,
                "stale": stale_views_count,
            },
            "analytical_views_hash": view_hash,
            "analytical_facts_hash": fact_hash,
            "analytical_execution_manifest_hash": exec_hash,
        }
        if stats:
            manifest["stats"] = stats

        manifest_json = json.dumps(manifest, indent=2, sort_keys=True)
        manifest_path = sdr_dir / "sdr6_manifest.json"
        manifest_path.write_text(manifest_json, encoding="utf-8")
        manifest_hash = hashlib.sha256(manifest_json.encode("utf-8")).hexdigest()

        return {
            "analytical_views": str(view_path),
            "analytical_facts": str(fact_path),
            "analytical_execution_manifest": str(exec_path),
            "sdr6_manifest": str(manifest_path),
            "manifest_fingerprint": manifest_hash,
        }




