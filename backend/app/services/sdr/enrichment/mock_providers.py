"""
HighView Semantic Data Refinery — Phase SDR-4
Deterministic Mock & Reference Enrichment Providers for Framework Verification
"""

from __future__ import annotations

import datetime
from typing import Any, Sequence

from app.services.sdr.contracts.enrichment import (
    EnrichmentCandidate,
    EnrichmentProviderMetadata,
    EnrichmentProviderType,
    EnrichmentStatus,
    compute_enrichment_candidate_fingerprint,
)
from app.services.sdr.contracts.profiles import (
    PrivacyClassification,
    ProfilingAmbiguityState,
    SemanticColumnProfile,
    SemanticDtype,
)
from app.services.sdr.enrichment.provider import EnrichmentProvider


class DatePartProvider(EnrichmentProvider):
    """
    Deterministic rule provider for calendar date decomposition.
    Extracts year, month, and standard calendar quarter.
    STRICT BOUNDARY: Does NOT invent fiscal quarters without explicit fiscal rules.
    """

    def __init__(self, version: str = "1.0.0", reference_version: str = "2026.1"):
        metadata = EnrichmentProviderMetadata(
            provider_id="provider_date_part",
            provider_name="Calendar Date Part Decomposer",
            provider_version=version,
            provider_type=EnrichmentProviderType.DETERMINISTIC_RULE,
            supported_input_semantics=[
                SemanticDtype.DATE,
                SemanticDtype.DATETIME,
            ],
            supported_output_semantics=[
                SemanticDtype.INTEGER_NUMBER,
                SemanticDtype.CATEGORICAL_CODE,
            ],
            is_offline=True,
            is_deterministic=True,
            reference_data_version=reference_version,
            license_or_provenance="HighView Standard Built-in Calendar Rule",
        )
        super().__init__(metadata)

    def can_handle(self, profile: SemanticColumnProfile) -> bool:
        return profile.semantic_dtype in (SemanticDtype.DATE, SemanticDtype.DATETIME)

    def generate_candidates(
        self,
        dataset_id: str,
        sheet_id: str,
        profile: SemanticColumnProfile,
        sample_values: Sequence[Any] | None = None,
        policy_fingerprint: str = "",
        depth: int = 1,
        parent_enrichment_id: str | None = None,
    ) -> list[EnrichmentCandidate]:
        candidates: list[EnrichmentCandidate] = []
        val_fp = profile.artifact_fingerprint

        parts = [
            ("year", "INTEGER_NUMBER", SemanticDtype.INTEGER_NUMBER, 0.95, "Calendar Year"),
            ("month", "INTEGER_NUMBER", SemanticDtype.INTEGER_NUMBER, 0.90, "Calendar Month (1-12)"),
            ("quarter", "CATEGORICAL_CODE", SemanticDtype.CATEGORICAL_CODE, 0.85, "Standard Calendar Quarter (Q1-Q4)"),
        ]

        for part_suffix, _dtype_str, out_dtype, conf, desc in parts:
            cand_id = f"cand_date_{sheet_id}_{profile.column_id}_{part_suffix}"
            out_name = f"{profile.source_name}_{part_suffix}"
            fp = compute_enrichment_candidate_fingerprint(
                dataset_id=dataset_id,
                sheet_id=sheet_id,
                source_column_ids=[profile.column_id],
                source_values_fingerprint=val_fp,
                proposed_output_name=out_name,
                proposed_output_semantic_type=out_dtype,
                provider_id=self.provider_id,
                provider_version=self.provider_version,
                reference_data_version=self.reference_data_version,
                policy_fingerprint=policy_fingerprint,
            )

            cand = EnrichmentCandidate(
                candidate_id=cand_id,
                dataset_id=dataset_id,
                sheet_id=sheet_id,
                source_column_ids=[profile.column_id],
                source_column_names=[profile.source_name],
                source_semantic_type=profile.semantic_dtype,
                source_values_fingerprint=val_fp,
                proposed_enrichment_type=f"DATE_PART_{part_suffix.upper()}",
                proposed_output_name=out_name,
                proposed_output_semantic_type=out_dtype,
                provider_id=self.provider_id,
                provider_version=self.provider_version,
                reference_data_version=self.reference_data_version,
                confidence=conf,
                ambiguity_state=ProfilingAmbiguityState.CLEAR,
                information_gain_record={"target": part_suffix, "description": desc, "base_utility": 0.90},
                privacy_classification=PrivacyClassification.GENERAL_ATTRIBUTE,
                validation_status=EnrichmentStatus.CANDIDATE,
                depth=depth,
                parent_enrichment_id=parent_enrichment_id,
                provenance=profile.source_lineage,
                artifact_fingerprint=fp,
            )
            candidates.append(cand)

        return candidates

    def resolve(self, candidate: EnrichmentCandidate, values: Sequence[Any] | None = None) -> Any:
        col = candidate.source_column_names[0]
        if "year" in candidate.proposed_output_name:
            expr = f"EXTRACT(YEAR FROM CAST({col} AS DATE))"
            if values is not None:
                resolved = []
                for v in values:
                    if v is None:
                        resolved.append(None)
                    else:
                        s = str(v)[:10]
                        try:
                            resolved.append(int(s[:4]))
                        except Exception:
                            resolved.append(None)
                return resolved
            return expr
        elif "month" in candidate.proposed_output_name:
            expr = f"EXTRACT(MONTH FROM CAST({col} AS DATE))"
            if values is not None:
                resolved = []
                for v in values:
                    if v is None:
                        resolved.append(None)
                    else:
                        s = str(v)[:10]
                        try:
                            resolved.append(int(s[5:7]))
                        except Exception:
                            resolved.append(None)
                return resolved
            return expr
        elif "quarter" in candidate.proposed_output_name:
            expr = f"'Q' || CAST(CEIL(EXTRACT(MONTH FROM CAST({col} AS DATE)) / 3.0) AS INT)"
            if values is not None:
                resolved = []
                for v in values:
                    if v is None:
                        resolved.append(None)
                    else:
                        s = str(v)[:10]
                        try:
                            m = int(s[5:7])
                            q = (m - 1) // 3 + 1
                            resolved.append(f"Q{q}")
                        except Exception:
                            resolved.append(None)
                return resolved
            return expr
        return f"PROJECTION({col})"


class CodeLabelProvider(EnrichmentProvider):
    """
    Local reference dictionary provider for standard corporate codes (e.g. ENG -> Engineering).
    """

    REFERENCE_MAP: dict[str, str] = {
        "ENG": "Engineering",
        "SAL": "Sales",
        "HR": "Human Resources",
        "FIN": "Finance",
        "MKT": "Marketing",
        "OPS": "Operations",
    }

    def __init__(self, version: str = "1.0.0", reference_version: str = "2026.1"):
        metadata = EnrichmentProviderMetadata(
            provider_id="provider_code_label",
            provider_name="Local Code Label Dictionary",
            provider_version=version,
            provider_type=EnrichmentProviderType.LOCAL_REFERENCE,
            supported_input_semantics=[
                SemanticDtype.CATEGORICAL_CODE,
                SemanticDtype.IDENTIFIER_CODE,
            ],
            supported_output_semantics=[
                SemanticDtype.NATURAL_LANGUAGE_TEXT,
            ],
            is_offline=True,
            is_deterministic=True,
            reference_data_version=reference_version,
            license_or_provenance="Internal Enterprise Code Dictionary",
        )
        super().__init__(metadata)

    def can_handle(self, profile: SemanticColumnProfile) -> bool:
        if profile.semantic_dtype in (SemanticDtype.CATEGORICAL_CODE, SemanticDtype.IDENTIFIER_CODE):
            name_lower = profile.source_name.lower()
            return "dept" in name_lower or "code" in name_lower or "department" in name_lower
        return False

    def generate_candidates(
        self,
        dataset_id: str,
        sheet_id: str,
        profile: SemanticColumnProfile,
        sample_values: Sequence[Any] | None = None,
        policy_fingerprint: str = "",
        depth: int = 1,
        parent_enrichment_id: str | None = None,
    ) -> list[EnrichmentCandidate]:
        out_name = f"{profile.source_name}_name"
        out_dtype = SemanticDtype.NATURAL_LANGUAGE_TEXT
        val_fp = profile.artifact_fingerprint

        fp = compute_enrichment_candidate_fingerprint(
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            source_column_ids=[profile.column_id],
            source_values_fingerprint=val_fp,
            proposed_output_name=out_name,
            proposed_output_semantic_type=out_dtype,
            provider_id=self.provider_id,
            provider_version=self.provider_version,
            reference_data_version=self.reference_data_version,
            policy_fingerprint=policy_fingerprint,
        )

        cand = EnrichmentCandidate(
            candidate_id=f"cand_code_{sheet_id}_{profile.column_id}_label",
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            source_column_ids=[profile.column_id],
            source_column_names=[profile.source_name],
            source_semantic_type=profile.semantic_dtype,
            source_values_fingerprint=val_fp,
            proposed_enrichment_type="CODE_LABEL_LOOKUP",
            proposed_output_name=out_name,
            proposed_output_semantic_type=out_dtype,
            provider_id=self.provider_id,
            provider_version=self.provider_version,
            reference_data_version=self.reference_data_version,
            confidence=0.98,
            ambiguity_state=ProfilingAmbiguityState.CLEAR,
            information_gain_record={"description": "Standard departmental expansion", "base_utility": 0.85},
            privacy_classification=PrivacyClassification.GENERAL_ATTRIBUTE,
            validation_status=EnrichmentStatus.CANDIDATE,
            depth=depth,
            parent_enrichment_id=parent_enrichment_id,
            provenance=profile.source_lineage,
            artifact_fingerprint=fp,
        )
        return [cand]

    def resolve(self, candidate: EnrichmentCandidate, values: Sequence[Any] | None = None) -> Any:
        col = candidate.source_column_names[0]
        if values is not None:
            return [self.REFERENCE_MAP.get(str(v).strip().upper(), str(v)) if v is not None else None for v in values]
        return f"MAP_LOOKUP({col}, 'dept_code_map')"


class MockLowUtilityProvider(EnrichmentProvider):
    """
    Mock provider that generates technically derivable but analytically useless attributes.
    Used to verify that information gain filtering rejects or defers low-utility candidates.
    """

    def __init__(self):
        metadata = EnrichmentProviderMetadata(
            provider_id="provider_low_utility",
            provider_name="Trivial String Metrics",
            provider_version="1.0.0",
            provider_type=EnrichmentProviderType.DETERMINISTIC_RULE,
            supported_input_semantics=[
                SemanticDtype.NATURAL_LANGUAGE_TEXT,
                SemanticDtype.CATEGORICAL_CODE,
            ],
            supported_output_semantics=[
                SemanticDtype.INTEGER_NUMBER,
            ],
            is_offline=True,
            is_deterministic=True,
            reference_data_version="1.0.0",
        )
        super().__init__(metadata)

    def can_handle(self, profile: SemanticColumnProfile) -> bool:
        return profile.semantic_dtype in (SemanticDtype.NATURAL_LANGUAGE_TEXT, SemanticDtype.CATEGORICAL_CODE)

    def generate_candidates(
        self,
        dataset_id: str,
        sheet_id: str,
        profile: SemanticColumnProfile,
        sample_values: Sequence[Any] | None = None,
        policy_fingerprint: str = "",
        depth: int = 1,
        parent_enrichment_id: str | None = None,
    ) -> list[EnrichmentCandidate]:
        out_name = f"{profile.source_name}_char_count"
        out_dtype = SemanticDtype.INTEGER_NUMBER
        val_fp = profile.artifact_fingerprint

        fp = compute_enrichment_candidate_fingerprint(
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            source_column_ids=[profile.column_id],
            source_values_fingerprint=val_fp,
            proposed_output_name=out_name,
            proposed_output_semantic_type=out_dtype,
            provider_id=self.provider_id,
            provider_version=self.provider_version,
            reference_data_version=self.reference_data_version,
            policy_fingerprint=policy_fingerprint,
        )

        cand = EnrichmentCandidate(
            candidate_id=f"cand_low_util_{sheet_id}_{profile.column_id}_len",
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            source_column_ids=[profile.column_id],
            source_column_names=[profile.source_name],
            source_semantic_type=profile.semantic_dtype,
            source_values_fingerprint=val_fp,
            proposed_enrichment_type="TRIVIAL_STRING_LENGTH",
            proposed_output_name=out_name,
            proposed_output_semantic_type=out_dtype,
            provider_id=self.provider_id,
            provider_version=self.provider_version,
            reference_data_version=self.reference_data_version,
            confidence=0.99,
            ambiguity_state=ProfilingAmbiguityState.CLEAR,
            information_gain_record={"description": "String character count", "base_utility": 0.15},  # Low utility
            privacy_classification=PrivacyClassification.GENERAL_ATTRIBUTE,
            validation_status=EnrichmentStatus.CANDIDATE,
            depth=depth,
            parent_enrichment_id=parent_enrichment_id,
            provenance=profile.source_lineage,
            artifact_fingerprint=fp,
        )
        return [cand]

    def resolve(self, candidate: EnrichmentCandidate, values: Sequence[Any] | None = None) -> Any:
        col = candidate.source_column_names[0]
        if values is not None:
            return [len(str(v)) if v is not None else 0 for v in values]
        return f"LENGTH({col})"


class MockSensitiveInferenceProvider(EnrichmentProvider):
    """
    Mock provider attempting prohibited sensitive inference (e.g. predicting health risk or religion).
    Used to verify that hard governance gates strictly block the candidate.
    """

    def __init__(self):
        metadata = EnrichmentProviderMetadata(
            provider_id="provider_sensitive_inference",
            provider_name="Probabilistic Health Inference Engine",
            provider_version="1.0.0",
            provider_type=EnrichmentProviderType.MODEL_ASSISTED,
            supported_input_semantics=[
                SemanticDtype.IDENTIFIER_CODE,
                SemanticDtype.NATURAL_LANGUAGE_TEXT,
            ],
            supported_output_semantics=[
                SemanticDtype.CATEGORICAL_CODE,
            ],
            is_offline=True,
            is_deterministic=False,
            reference_data_version="1.0.0",
        )
        super().__init__(metadata)

    def can_handle(self, profile: SemanticColumnProfile) -> bool:
        return True

    def generate_candidates(
        self,
        dataset_id: str,
        sheet_id: str,
        profile: SemanticColumnProfile,
        sample_values: Sequence[Any] | None = None,
        policy_fingerprint: str = "",
        depth: int = 1,
        parent_enrichment_id: str | None = None,
    ) -> list[EnrichmentCandidate]:
        out_name = f"{profile.source_name}_predicted_health_risk"
        out_dtype = SemanticDtype.CATEGORICAL_CODE
        val_fp = profile.artifact_fingerprint

        fp = compute_enrichment_candidate_fingerprint(
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            source_column_ids=[profile.column_id],
            source_values_fingerprint=val_fp,
            proposed_output_name=out_name,
            proposed_output_semantic_type=out_dtype,
            provider_id=self.provider_id,
            provider_version=self.provider_version,
            reference_data_version=self.reference_data_version,
            policy_fingerprint=policy_fingerprint,
        )

        cand = EnrichmentCandidate(
            candidate_id=f"cand_sens_{sheet_id}_{profile.column_id}_health",
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            source_column_ids=[profile.column_id],
            source_column_names=[profile.source_name],
            source_semantic_type=profile.semantic_dtype,
            source_values_fingerprint=val_fp,
            proposed_enrichment_type="PROBABILISTIC_HEALTH_RISK",
            proposed_output_name=out_name,
            proposed_output_semantic_type=out_dtype,
            provider_id=self.provider_id,
            provider_version=self.provider_version,
            reference_data_version=self.reference_data_version,
            confidence=0.85,
            ambiguity_state=ProfilingAmbiguityState.CLEAR,
            information_gain_record={"description": "Predicted personal health risk", "base_utility": 0.80},
            privacy_classification=PrivacyClassification.INFERRED_SENSITIVE_ATTRIBUTE,  # PROHIBITED!
            validation_status=EnrichmentStatus.CANDIDATE,
            depth=depth,
            parent_enrichment_id=parent_enrichment_id,
            provenance=profile.source_lineage,
            artifact_fingerprint=fp,
        )
        return [cand]

    def resolve(self, candidate: EnrichmentCandidate, values: Sequence[Any] | None = None) -> Any:
        raise PermissionError("Execution of prohibited sensitive inference provider is forbidden.")


class MockAmbiguousProvider(EnrichmentProvider):
    """
    Mock provider generating an ambiguous candidate where input meaning is uncertain.
    Used to verify that the framework marks AMBIGUOUS without guessing.
    """

    def __init__(self):
        metadata = EnrichmentProviderMetadata(
            provider_id="provider_ambiguous_mock",
            provider_name="Ambiguous Signal Provider",
            provider_version="1.0.0",
            provider_type=EnrichmentProviderType.LOCAL_REFERENCE,
            supported_input_semantics=[
                SemanticDtype.NATURAL_LANGUAGE_TEXT,
                SemanticDtype.CATEGORICAL_CODE,
            ],
            supported_output_semantics=[
                SemanticDtype.CATEGORICAL_CODE,
            ],
            is_offline=True,
            is_deterministic=True,
            reference_data_version="1.0.0",
        )
        super().__init__(metadata)

    def can_handle(self, profile: SemanticColumnProfile) -> bool:
        return True

    def generate_candidates(
        self,
        dataset_id: str,
        sheet_id: str,
        profile: SemanticColumnProfile,
        sample_values: Sequence[Any] | None = None,
        policy_fingerprint: str = "",
        depth: int = 1,
        parent_enrichment_id: str | None = None,
    ) -> list[EnrichmentCandidate]:
        out_name = f"{profile.source_name}_ambiguous_target"
        out_dtype = SemanticDtype.CATEGORICAL_CODE
        val_fp = profile.artifact_fingerprint

        fp = compute_enrichment_candidate_fingerprint(
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            source_column_ids=[profile.column_id],
            source_values_fingerprint=val_fp,
            proposed_output_name=out_name,
            proposed_output_semantic_type=out_dtype,
            provider_id=self.provider_id,
            provider_version=self.provider_version,
            reference_data_version=self.reference_data_version,
            policy_fingerprint=policy_fingerprint,
        )

        cand = EnrichmentCandidate(
            candidate_id=f"cand_ambig_{sheet_id}_{profile.column_id}",
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            source_column_ids=[profile.column_id],
            source_column_names=[profile.source_name],
            source_semantic_type=profile.semantic_dtype,
            source_values_fingerprint=val_fp,
            proposed_enrichment_type="AMBIGUOUS_MULTI_TARGET",
            proposed_output_name=out_name,
            proposed_output_semantic_type=out_dtype,
            provider_id=self.provider_id,
            provider_version=self.provider_version,
            reference_data_version=self.reference_data_version,
            confidence=0.50,
            ambiguity_state=ProfilingAmbiguityState.AMBIGUOUS_TYPE,  # Explicit ambiguity
            information_gain_record={"description": "Conflicting entity targets detected", "base_utility": 0.70},
            privacy_classification=PrivacyClassification.GENERAL_ATTRIBUTE,
            validation_status=EnrichmentStatus.AMBIGUOUS,
            depth=depth,
            parent_enrichment_id=parent_enrichment_id,
            provenance=profile.source_lineage,
            artifact_fingerprint=fp,
        )
        return [cand]

    def resolve(self, candidate: EnrichmentCandidate, values: Sequence[Any] | None = None) -> Any:
        return None


class MockFailingProvider(EnrichmentProvider):
    """
    Mock provider that throws an unexpected error or becomes unavailable.
    Used to verify graceful degradation where source datasets remain completely intact.
    """

    def __init__(self):
        metadata = EnrichmentProviderMetadata(
            provider_id="provider_failing_mock",
            provider_name="Failing Network Simulator",
            provider_version="1.0.0",
            provider_type=EnrichmentProviderType.LOCAL_REFERENCE,
            supported_input_semantics=[
                SemanticDtype.NATURAL_LANGUAGE_TEXT,
            ],
            supported_output_semantics=[
                SemanticDtype.NATURAL_LANGUAGE_TEXT,
            ],
            is_offline=False,
            is_deterministic=False,
            reference_data_version="1.0.0",
        )
        super().__init__(metadata)

    def can_handle(self, profile: SemanticColumnProfile) -> bool:
        return True

    def generate_candidates(
        self,
        dataset_id: str,
        sheet_id: str,
        profile: SemanticColumnProfile,
        sample_values: Sequence[Any] | None = None,
        policy_fingerprint: str = "",
        depth: int = 1,
        parent_enrichment_id: str | None = None,
    ) -> list[EnrichmentCandidate]:
        raise RuntimeError("Enrichment service connection timeout: provider unavailable.")

    def resolve(self, candidate: EnrichmentCandidate, values: Sequence[Any] | None = None) -> Any:
        raise RuntimeError("Provider failed during resolution.")
