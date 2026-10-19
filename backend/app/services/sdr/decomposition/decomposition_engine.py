"""
HighView Semantic Data Refinery — Phase SDR-1
Non-Destructive Decomposition Candidate Engine
"""

from __future__ import annotations

import re
from typing import Sequence

from app.services.ingestion_v2.contracts.semantics import (
    SemanticColumnRole,
    SemanticConcept,
)
from app.services.sdr.contracts.decomposition import (
    CompositePatternType,
    DecompositionComponent,
    DecompositionValidationStatus,
    SemanticDecompositionCandidate,
    compute_candidate_fingerprint,
)
from app.services.sdr.contracts.profiles import (
    SemanticColumnProfile,
    SemanticDtype,
)
from app.services.sdr.decomposition.false_split_guards import (
    evaluate_false_split_rejection,
    is_date_or_quarter_literal,
    is_formatted_number_literal,
    is_phone_number,
)

# Geographic tokens for hierarchical string detection
GEO_LEVEL_NAMES_3 = ["city", "state", "country"]
GEO_LEVEL_NAMES_2 = ["city_or_region", "country"]

RE_CURRENCY_EXTRACT = re.compile(r"^([$€£₹¥]?)\s*([0-9,]+(?:\.[0-9]+)?)\s*([A-Za-z]{3})?$")


class SDRDecompositionEngine:
    """
    Generates non-destructive candidate decompositions for composite physical columns.
    Mandatory Invariant: is_destructive = False. Source columns are never mutated or replaced.
    """

    def generate_candidates(
        self,
        profile: SemanticColumnProfile,
        sample_values: Sequence[str] | None = None,
    ) -> list[SemanticDecompositionCandidate]:
        """
        Analyzes profile features and sample values to propose safe decomposition candidates.
        """
        samples = sample_values if sample_values is not None else profile.features.sample_values
        if not samples:
            return []

        candidates: list[SemanticDecompositionCandidate] = []

        # 1. Evaluate Currency with Unit (Single formatted monetary concept)
        curr_cand = self._try_currency_with_unit(profile, samples)
        if curr_cand:
            candidates.append(curr_cand)
            return candidates

        # 2. Check each candidate delimiter from features
        for delim, count in profile.features.delimiter_counts.items():
            # False-split rejection filter
            rejected, reason = evaluate_false_split_rejection(samples, delim)
            if rejected:
                continue

            # Check consistency of splitting
            cand = self._evaluate_delimiter_candidate(profile, samples, delim)
            if cand:
                candidates.append(cand)

        return candidates

    def _try_currency_with_unit(
        self,
        profile: SemanticColumnProfile,
        samples: Sequence[str],
    ) -> SemanticDecompositionCandidate | None:
        """
        Detects formatted monetary values like '₹1,25,000 INR' or '$5,000 USD'.
        Classifies as CURRENCY_WITH_UNIT (formatted monetary concept).
        """
        matching = 0
        extractions: list[dict[str, str]] = []

        for s in samples:
            val_s = str(s).strip()
            m = RE_CURRENCY_EXTRACT.match(val_s)
            if m:
                sym, amt, code = m.groups()
                # Decompose only compound values with explicit code (e.g. '₹1,25,000 INR' or '5000 USD')
                if code and amt:
                    matching += 1
                    curr_repr = code.upper()
                    extractions.append({"amount": amt, "currency": curr_repr})

        if len(samples) > 0 and (matching / len(samples)) >= 0.75:
            components = [
                DecompositionComponent(
                    position=1,
                    candidate_name="amount",
                    proposed_semantic_role=SemanticColumnRole.MEASURE,
                    proposed_semantic_dtype=SemanticDtype.DECIMAL_NUMBER,
                    proposed_concept=SemanticConcept.MEASURE,
                    sample_extractions=[e["amount"] for e in extractions[:5]],
                    extraction_rule="REGEX_EXTRACT_AMOUNT",
                ),
                DecompositionComponent(
                    position=2,
                    candidate_name="currency",
                    proposed_semantic_role=SemanticColumnRole.ATTRIBUTE,
                    proposed_semantic_dtype=SemanticDtype.CATEGORICAL_CODE,
                    proposed_concept=SemanticConcept.TECHNICAL,
                    sample_extractions=[e["currency"] for e in extractions[:5]],
                    extraction_rule="REGEX_EXTRACT_CURRENCY",
                ),
            ]

            cid = f"decomp_{profile.dataset_id}_{profile.sheet_id}_{profile.column_id}_curr"
            c_fingerprint = compute_candidate_fingerprint(
                dataset_id=profile.dataset_id,
                sheet_id=profile.sheet_id,
                source_column_id=profile.column_id,
                pattern_type=CompositePatternType.CURRENCY_WITH_UNIT,
                component_names=["amount", "currency"],
                source_profile_fingerprint=profile.artifact_fingerprint,
            )

            return SemanticDecompositionCandidate(
                candidate_id=cid,
                dataset_id=profile.dataset_id,
                sheet_id=profile.sheet_id,
                source_column_id=profile.column_id,
                source_column_name=profile.source_name,
                pattern_type=CompositePatternType.CURRENCY_WITH_UNIT,
                delimiter=None,
                components=components,
                sample_extractions=extractions[:5],
                confidence=0.92,
                validation_status=DecompositionValidationStatus.VALIDATED,
                source_profile_fingerprint=profile.artifact_fingerprint,
                is_destructive=False,
                candidate_fingerprint=c_fingerprint,
            )

        return None

    def _evaluate_delimiter_candidate(
        self,
        profile: SemanticColumnProfile,
        samples: Sequence[str],
        delimiter: str,
    ) -> SemanticDecompositionCandidate | None:
        """Evaluates structured split on consistent delimiters."""
        split_samples: list[list[str]] = []
        part_counts: set[int] = set()

        for s in samples:
            parts = [p.strip() for p in str(s).split(delimiter) if p.strip()]
            if len(parts) >= 2:
                split_samples.append(parts)
                part_counts.add(len(parts))

        # Must have consistent number of parts across at least 70% of non-null samples
        if not split_samples or len(split_samples) / len(samples) < 0.70:
            return None

        # Prefer dominant part length
        common_len = max(part_counts, key=lambda n: sum(1 for parts in split_samples if len(parts) == n))
        if common_len < 2:
            return None

        valid_splits = [parts for parts in split_samples if len(parts) == common_len]
        sample_extractions = [
            {f"component_{i+1}": p for i, p in enumerate(parts)}
            for parts in valid_splits[:5]
        ]

        # Check for Geographic Hierarchy
        is_geo_name = any(t in profile.source_name.lower() for t in ("location", "geo", "city", "region", "address"))
        if is_geo_name and common_len in (2, 3):
            names = GEO_LEVEL_NAMES_3 if common_len == 3 else GEO_LEVEL_NAMES_2
            components = [
                DecompositionComponent(
                    position=i + 1,
                    candidate_name=names[i],
                    proposed_semantic_role=SemanticColumnRole.LOCATION,
                    proposed_semantic_dtype=SemanticDtype.GEOGRAPHIC_LOCATION,
                    proposed_concept=SemanticConcept.LOCATION_ATTRIBUTE,
                    sample_extractions=[parts[i] for parts in valid_splits[:5]],
                    extraction_rule=f"SPLIT_BY('{delimiter}')[{i}]",
                )
                for i in range(common_len)
            ]
            pattern_type = CompositePatternType.GEOGRAPHIC_HIERARCHY
            status = DecompositionValidationStatus.VALIDATED
            confidence = 0.90
        # Check for Code + Label (e.g. EMP001 | Engineering)
        elif common_len == 2 and any(re.match(r"^[A-Za-z0-9_]{2,10}$", parts[0]) for parts in valid_splits):
            components = [
                DecompositionComponent(
                    position=1,
                    candidate_name="code",
                    proposed_semantic_role=SemanticColumnRole.ENTITY_IDENTIFIER,
                    proposed_semantic_dtype=SemanticDtype.IDENTIFIER_CODE,
                    proposed_concept=SemanticConcept.IDENTIFIER,
                    sample_extractions=[parts[0] for parts in valid_splits[:5]],
                    extraction_rule=f"SPLIT_BY('{delimiter}')[0]",
                ),
                DecompositionComponent(
                    position=2,
                    candidate_name="label",
                    proposed_semantic_role=SemanticColumnRole.DIMENSION,
                    proposed_semantic_dtype=SemanticDtype.CATEGORICAL_CODE,
                    proposed_concept=SemanticConcept.CATEGORICAL,
                    sample_extractions=[parts[1] for parts in valid_splits[:5]],
                    extraction_rule=f"SPLIT_BY('{delimiter}')[1]",
                ),
            ]
            pattern_type = CompositePatternType.CODE_LABEL_PAIR
            status = DecompositionValidationStatus.VALIDATED
            confidence = 0.88
        else:
            components = [
                DecompositionComponent(
                    position=i + 1,
                    candidate_name=f"{profile.canonical_name}_part_{i+1}",
                    proposed_semantic_role=SemanticColumnRole.DIMENSION,
                    proposed_semantic_dtype=SemanticDtype.CATEGORICAL_CODE,
                    proposed_concept=SemanticConcept.CATEGORICAL,
                    sample_extractions=[parts[i] for parts in valid_splits[:5]],
                    extraction_rule=f"SPLIT_BY('{delimiter}')[{i}]",
                )
                for i in range(common_len)
            ]
            pattern_type = CompositePatternType.DELIMITER_SPLIT
            status = DecompositionValidationStatus.PROVISIONAL
            confidence = 0.72

        cid = f"decomp_{profile.dataset_id}_{profile.sheet_id}_{profile.column_id}_{pattern_type.value.lower()}"
        c_fingerprint = compute_candidate_fingerprint(
            dataset_id=profile.dataset_id,
            sheet_id=profile.sheet_id,
            source_column_id=profile.column_id,
            pattern_type=pattern_type,
            component_names=[c.candidate_name for c in components],
            source_profile_fingerprint=profile.artifact_fingerprint,
        )

        return SemanticDecompositionCandidate(
            candidate_id=cid,
            dataset_id=profile.dataset_id,
            sheet_id=profile.sheet_id,
            source_column_id=profile.column_id,
            source_column_name=profile.source_name,
            pattern_type=pattern_type,
            delimiter=delimiter,
            components=components,
            sample_extractions=sample_extractions,
            confidence=confidence,
            validation_status=status,
            source_profile_fingerprint=profile.artifact_fingerprint,
            is_destructive=False,
            candidate_fingerprint=c_fingerprint,
        )
