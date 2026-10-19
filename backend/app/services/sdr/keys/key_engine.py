"""
HighView Semantic Data Refinery — Phase SDR-3
Key Intelligence & Candidate Key Discovery Engine
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.services.ingestion_v2.contracts.grain import CanonicalGrain, TemporalGrain
from app.services.ingestion_v2.contracts.semantics import SemanticEntityType
from app.services.sdr.contracts.grain import GrainStatus, SDRGrainProfile
from app.services.sdr.contracts.keys import (
    KeyCandidateStatus,
    KeyCandidateType,
    ObservedFunctionalDependency,
    SDRKeyCandidate,
)
from app.services.sdr.contracts.policies import KeyConfidencePolicy, SDRPolicySuite
from app.services.sdr.contracts.profiles import (
    SemanticColumnProfile,
)
from app.services.sdr.keys.candidate_evaluator import (
    SDRCandidateKeyEvaluator,
    SDRKeyCandidateEvaluator,
)
from app.services.sdr.keys.fd_engine import SDRFunctionalDependencyEngine


class SDRKeyIntelligenceResult:
    """
    Result container for SDR-3 Key Intelligence Engine.
    Supports tuple unpacking, dictionary indexing, and direct attribute access.
    """

    def __init__(
        self,
        candidates: list[SDRKeyCandidate],
        functional_dependencies: list[ObservedFunctionalDependency],
        manifest: dict[str, Any],
    ):
        self.candidates = candidates
        self.functional_dependencies = functional_dependencies
        self.manifest = manifest

    def __iter__(self):
        return iter((self.candidates, self.functional_dependencies))

    def __getitem__(self, item: str) -> Any:
        if item == "candidates":
            return self.candidates
        elif item in ("functional_dependencies", "fds"):
            return self.functional_dependencies
        elif item == "manifest":
            return self.manifest
        raise KeyError(item)

    def get(self, item: str, default: Any = None) -> Any:
        try:
            return self[item]
        except KeyError:
            return default

    def __contains__(self, item: str) -> bool:
        return item in ("candidates", "functional_dependencies", "fds", "manifest")


class SDRKeyIntelligenceEngine:
    """
    SDR-3 Governed Key Intelligence Engine.
    Discovers candidate keys and observed local functional dependencies
    grounded in SDR-1 semantic profiles and SDR-2 table grain.

    CORE GOVERNANCE INVARIANTS:
    1. A good key candidate is not merely unique; it must be semantically appropriate,
       grain-compatible, minimal, and supported by observable identity evidence.
    2. Statistical uniqueness != Primary Key Confirmed.
    3. Foreign-key-like columns are local hypotheses only; cross-table relationships
       and JoinPlans remain strictly deferred to SDR-5.
    """

    def __init__(self, policy: KeyConfidencePolicy | None = None):
        self.policy = policy or KeyConfidencePolicy()
        self.candidate_evaluator = SDRCandidateKeyEvaluator(self.policy)
        self.fd_engine = SDRFunctionalDependencyEngine(self.policy)

    def analyze_keys(
        self,
        dataset_id: str,
        sheet_id: str,
        profiles: Sequence[SemanticColumnProfile],
        grain_profile: SDRGrainProfile | None = None,
        column_data: Mapping[str, Sequence[Any]] | None = None,
        rows: Sequence[Mapping[str, Any]] | None = None,
        row_count: int | None = None,
        policy_suite: SDRPolicySuite | None = None,
        source_declared_pk_columns: Sequence[str] | None = None,
        source_declared_pk: Sequence[str] | None = None,
    ) -> SDRKeyIntelligenceResult:
        """
        Executes candidate key discovery and local functional dependency observation.
        """
        policy_fp = policy_suite.compute_policy_fingerprint() if policy_suite else ""

        # Normalize rows to column_data if provided
        if rows is not None:
            norm_col_data: dict[str, list[Any]] = {}
            for p in profiles:
                vals = [r.get(p.source_name, r.get(p.column_id, r.get(p.canonical_name))) for r in rows]
                norm_col_data[p.column_id] = vals
                norm_col_data[p.source_name] = vals
                norm_col_data[p.canonical_name] = vals
            column_data = norm_col_data
            row_count = len(rows)
        elif column_data is not None:
            # Also ensure column_data has both column_id and source_name keys
            norm_col_data = dict(column_data)
            for p in profiles:
                if p.source_name in norm_col_data and p.column_id not in norm_col_data:
                    norm_col_data[p.column_id] = norm_col_data[p.source_name]
                elif p.column_id in norm_col_data and p.source_name not in norm_col_data:
                    norm_col_data[p.source_name] = norm_col_data[p.column_id]
            column_data = norm_col_data
            if row_count is None:
                row_count = max((len(v) for v in column_data.values()), default=0)
        else:
            column_data = {}
            row_count = 0

        # Normalize grain profile if omitted
        if grain_profile is None:
            grain_profile = SDRGrainProfile(
                dataset_id=dataset_id,
                sheet_id=sheet_id,
                primary_entity=CanonicalGrain.UNKNOWN,
                temporal_grain=TemporalGrain.NONE,
                resolved_grain_expression="UNKNOWN",
                grain_status=GrainStatus.PROVISIONAL,
                grain_confidence=0.5,
                is_unique=False,
                rationale="Default inferred grain profile",
                profile_id=f"grain_{dataset_id}_{sheet_id}",
                artifact_fingerprint="fp_default_grain",
            )

        # Normalize declared PK
        declared_pk = list(source_declared_pk_columns or source_declared_pk or [])

        # 1. Check for Event / No-Key archetype:
        is_event_stream = (
            (grain_profile.primary_entity in (CanonicalGrain.EVENT, SemanticEntityType.EVENT)
             or "EVENT" in grain_profile.resolved_grain_expression.upper()
             or grain_profile.resolved_grain_expression == "EVENT_OCCURRENCE")
        )

        # 2. Discover and evaluate key candidates
        key_candidates = self.candidate_evaluator.evaluate_all_candidates(
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            profiles=profiles,
            grain_profile=grain_profile,
            column_data=column_data,
            row_count=row_count,
            policy_fingerprint=policy_fp,
            source_declared_pk_columns=declared_pk,
        )

        # If event stream, ensure no natural candidate is marked HIGH_CONFIDENCE
        if is_event_stream:
            for i, cand in enumerate(key_candidates):
                if cand.candidate_type != KeyCandidateType.SYSTEM_ROW_ID:
                    key_candidates[i] = cand.model_copy(
                        update={
                            "status": KeyCandidateStatus.UNKNOWN,
                            "key_confidence": min(cand.key_confidence, 0.40),
                            "evidence": (
                                "Event occurrence stream with no natural business key. "
                                "HighView system row coordinates provide immutable lineage; "
                                "natural primary key candidate is absent."
                            ),
                        }
                    )

        # 3. Discover observed local functional dependencies
        functional_dependencies = self.fd_engine.discover_functional_dependencies(
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            profiles=profiles,
            column_data=column_data,
            row_count=row_count,
            key_candidates=key_candidates,
            policy_fingerprint=policy_fp,
        )

        manifest = {
            "dataset_id": dataset_id,
            "sheet_id": sheet_id,
            "candidates_count": len(key_candidates),
            "high_confidence_candidates_count": sum(1 for c in key_candidates if c.status == KeyCandidateStatus.HIGH_CONFIDENCE),
            "primary_keys_confirmed": sum(1 for c in key_candidates if c.status == KeyCandidateStatus.PRIMARY_KEY_CONFIRMED),
            "functional_dependencies_count": len(functional_dependencies),
            "foreign_keys_authorized": 0,
            "join_plans_created": 0,
        }

        return SDRKeyIntelligenceResult(
            candidates=key_candidates,
            functional_dependencies=functional_dependencies,
            manifest=manifest,
        )
