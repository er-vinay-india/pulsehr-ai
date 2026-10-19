"""
HighView Semantic Data Refinery — Phase SDR-1
Semantic Column Profiler
"""

from __future__ import annotations

import re
from typing import Any, Sequence

from app.services.ingestion_v2.contracts.provenance import SourceCoordinateRef
from app.services.ingestion_v2.contracts.semantics import (
    ClassificationSource,
    MeasureClass,
    SemanticColumnRole,
    SemanticConcept,
    SemanticEntityType,
)
from app.services.ingestion_v2.semantics.semantic_rules import (
    detect_adversarial_contradiction,
    infer_lexical_entity,
    infer_lexical_role,
    infer_measure_class,
    infer_semantic_concept,
    normalize_tokens,
)
from app.services.sdr.contracts.policies import SemanticConfidencePolicy
from app.services.sdr.contracts.profiles import (
    DeterministicColumnFeatures,
    PrivacyClassification,
    ProfilingAmbiguityState,
    SemanticColumnProfile,
    SemanticDtype,
    compute_profile_fingerprint,
)
from app.services.sdr.decomposition.false_split_guards import is_phone_number
from app.services.sdr.profiling.deterministic_features import extract_deterministic_features

# Common currency tokens for detection
CURRENCY_MARKERS = {"$", "€", "£", "₹", "¥", "usd", "inr", "eur", "gbp"}
SENSITIVE_TOKENS = {"salary", "compensation", "wage", "bonus", "equity", "medical", "health", "disability"}


class SDRColumnProfiler:
    """
    Orchestrates deterministic structural profiling and governed semantic hypothesis generation.
    Decouples physical storage types from domain semantic types.
    Enforces responsible abstention: ambiguous signals yield UNKNOWN/AMBIGUOUS rather than false certitude.
    """

    def __init__(self, policy: SemanticConfidencePolicy | None = None):
        self.policy = policy or SemanticConfidencePolicy()

    def profile_column(
        self,
        dataset_id: str,
        sheet_id: str,
        column_id: str,
        source_name: str,
        physical_dtype: str,
        raw_values: Sequence[Any],
        source_file_hash: str = "unknown",
        policy_fingerprint: str = "default_policy",
    ) -> SemanticColumnProfile:
        """
        Generates a frozen, deterministic SemanticColumnProfile from raw column data.
        """
        # 1. Deterministic structural feature extraction
        features = extract_deterministic_features(raw_values)
        tokens = normalize_tokens(source_name)
        lex_role, lex_score = infer_lexical_role(tokens)
        lex_entity, entity_score = infer_lexical_entity(tokens)

        # 2. Derive Semantic Dtype
        semantic_dtype, unit, currency = self._infer_semantic_dtype(features, tokens, physical_dtype)

        # 3. Derive Semantic Role & Confidence
        role, concept, measure_class, confidence, ambiguity_state = self._infer_role_and_concept(
            features=features,
            tokens=tokens,
            lex_role=lex_role,
            lex_score=lex_score,
            semantic_dtype=semantic_dtype,
            unit=unit,
        )

        # 4. Privacy & Governance Classification
        privacy_class = self._classify_privacy(tokens, role, semantic_dtype)

        # 5. Composite Candidate Detection Flag
        is_composite = self._check_composite_candidate(features, semantic_dtype, tokens)

        # 6. Source Lineage & Fingerprint
        profile_id = f"sdr_prof_{dataset_id}_{sheet_id}_{column_id}"
        lineage = SourceCoordinateRef(
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            column_ids=[column_id],
            source_file_hash=source_file_hash,
        )

        artifact_fingerprint = compute_profile_fingerprint(
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            column_id=column_id,
            source_name=source_name,
            physical_dtype=physical_dtype,
            semantic_dtype=semantic_dtype,
            semantic_role=role,
            features_sample_fingerprint=features.sample_fingerprint,
            policy_fingerprint=policy_fingerprint,
        )

        return SemanticColumnProfile(
            profile_id=profile_id,
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            column_id=column_id,
            source_name=source_name,
            canonical_name="_".join(tokens) if tokens else source_name.lower(),
            physical_dtype=physical_dtype,
            semantic_dtype=semantic_dtype,
            semantic_role=role,
            semantic_concept=concept,
            entity_type_hypothesis=lex_entity,
            measure_class=measure_class,
            unit=unit,
            currency=currency,
            privacy_classification=privacy_class,
            features=features,
            confidence=round(confidence, 4),
            authority="DETERMINISTIC",
            classification_source=ClassificationSource.STATISTICAL if confidence >= self.policy.promotion_threshold else ClassificationSource.FALLBACK,
            ambiguity_state=ambiguity_state,
            is_composite_candidate=is_composite,
            source_lineage=lineage,
            artifact_fingerprint=artifact_fingerprint,
        )

    def _infer_semantic_dtype(
        self,
        features: DeterministicColumnFeatures,
        tokens: list[str],
        physical_dtype: str,
    ) -> tuple[SemanticDtype, str | None, str | None]:
        """Infers logical semantic data type from deterministic observations."""
        unit: str | None = None
        currency: str | None = None

        # Guard against phone numbers
        if any(is_phone_number(s) for s in features.sample_values):
            return SemanticDtype.UNKNOWN, None, None

        # Check for currency
        if features.currency_symbol_ratio >= self.policy.currency_symbol_threshold or any(
            t in ("salary", "revenue", "cost", "price", "spend", "budget", "amount") for t in tokens
        ) and features.numeric_parseable_ratio >= self.policy.numeric_parseable_threshold:
            # Check currency symbol in sample
            detected_curr = None
            for s in features.sample_values:
                for sym in ("$", "€", "£", "₹", "¥"):
                    if sym in s:
                        detected_curr = sym
                        break
                lower = s.lower()
                for code in ("usd", "inr", "eur", "gbp"):
                    if code in lower:
                        detected_curr = code.upper()
                        break
                if detected_curr:
                    break
            return SemanticDtype.CURRENCY_AMOUNT, unit, detected_curr or "USD"

        # Check for percentage
        if features.percentage_symbol_ratio >= self.policy.percentage_symbol_threshold or (
            any(t in ("pct", "percent", "rate", "ratio") for t in tokens) and features.numeric_parseable_ratio >= self.policy.numeric_parseable_threshold
        ):
            return SemanticDtype.PERCENTAGE_RATE, "%", None

        # Check for date / time
        if features.date_parseable_ratio >= self.policy.date_parseable_threshold or (
            any(t in ("date", "time", "created_at", "updated_at", "year", "month", "day") for t in tokens)
            and features.date_parseable_ratio >= 0.50
        ):
            return SemanticDtype.DATE, None, None

        # Check for boolean
        if features.boolean_vocabulary_ratio >= self.policy.boolean_threshold and features.distinct_count <= 4:
            return SemanticDtype.BOOLEAN_FLAG, None, None

        # Check for pure numbers
        if features.numeric_parseable_ratio >= self.policy.numeric_parseable_threshold:
            if features.integer_ratio >= 0.95:
                return SemanticDtype.INTEGER_NUMBER, None, None
            return SemanticDtype.DECIMAL_NUMBER, None, None

        # Check for composite text (structured multi-token)
        if any(v > (features.row_count - features.null_count) * self.policy.min_composite_consistency_ratio for v in features.delimiter_counts.values()):
            return SemanticDtype.COMPOSITE_TEXT, None, None

        # Check for identifier code
        if features.identifier_pattern_ratio >= 0.70 and features.distinct_ratio >= self.policy.min_distinct_ratio_for_identifier:
            return SemanticDtype.IDENTIFIER_CODE, None, None

        # Check for geographic location
        if any(t in ("city", "state", "country", "region", "zip", "postal", "location", "territory") for t in tokens):
            return SemanticDtype.GEOGRAPHIC_LOCATION, None, None

        # Categorical vs Free Text
        has_cat_token = any(t in ("department", "dept", "team", "division", "status", "category", "type", "role", "title", "grade", "band", "unit") for t in tokens)
        has_repeats = features.distinct_count < features.row_count
        if features.distinct_count > 0 and (
            (has_repeats and features.distinct_ratio < 0.40)
            or has_cat_token
        ):
            return SemanticDtype.CATEGORICAL_CODE, None, None

        if features.avg_value_length > 60:
            return SemanticDtype.NATURAL_LANGUAGE_TEXT, None, None

        if physical_dtype.lower() in ("object", "string", "str"):
            return SemanticDtype.UNKNOWN, None, None

        return SemanticDtype.UNKNOWN, None, None

    def _infer_role_and_concept(
        self,
        features: DeterministicColumnFeatures,
        tokens: list[str],
        lex_role: SemanticColumnRole | None,
        lex_score: float,
        semantic_dtype: SemanticDtype,
        unit: str | None,
    ) -> tuple[SemanticColumnRole, SemanticConcept, MeasureClass | None, float, ProfilingAmbiguityState]:
        """
        Determines semantic role and concept using deterministic evidence and lexical alignment.
        """
        # 1. Contradiction check: Name says IDENTIFIER, but values are clearly a small categorical dimension
        if lex_role == SemanticColumnRole.ENTITY_IDENTIFIER:
            if features.row_count >= 10 and features.distinct_count <= 5 and features.distinct_ratio < 0.20:
                # Contradiction! Value structure wins.
                return (
                    SemanticColumnRole.DIMENSION,
                    SemanticConcept.CATEGORICAL,
                    None,
                    0.70,
                    ProfilingAmbiguityState.CONTRADICTORY_SIGNALS,
                )

        # 2. Currency or Percentage -> MEASURE
        if semantic_dtype == SemanticDtype.CURRENCY_AMOUNT:
            return (
                SemanticColumnRole.MEASURE,
                SemanticConcept.MEASURE,
                MeasureClass.FINANCIAL,
                0.95,
                ProfilingAmbiguityState.CLEAR,
            )

        if semantic_dtype == SemanticDtype.PERCENTAGE_RATE:
            return (
                SemanticColumnRole.MEASURE,
                SemanticConcept.MEASURE,
                MeasureClass.PERCENTAGE,
                0.90,
                ProfilingAmbiguityState.CLEAR,
            )

        # 3. Date / Time -> TIME
        if semantic_dtype == SemanticDtype.DATE:
            return (
                SemanticColumnRole.TIME,
                SemanticConcept.TIME_SPAN,
                None,
                0.92,
                ProfilingAmbiguityState.CLEAR,
            )

        # 4. Boolean -> BOOLEAN
        if semantic_dtype == SemanticDtype.BOOLEAN_FLAG:
            return (
                SemanticColumnRole.BOOLEAN,
                SemanticConcept.STATUS,
                None,
                0.90,
                ProfilingAmbiguityState.CLEAR,
            )

        # Phone guard: Contact phone numbers must not be classified as ENTITY_IDENTIFIER
        if any(is_phone_number(s) for s in features.sample_values):
            return (
                SemanticColumnRole.UNKNOWN,
                SemanticConcept.UNKNOWN,
                None,
                0.35,
                ProfilingAmbiguityState.UNKNOWN_DISTRIBUTION,
            )

        # Composite Text handling
        if semantic_dtype == SemanticDtype.COMPOSITE_TEXT:
            if lex_role == SemanticColumnRole.LOCATION or any(t in ("location", "geo", "city", "address", "office") for t in tokens):
                return (
                    SemanticColumnRole.LOCATION,
                    SemanticConcept.LOCATION_ATTRIBUTE,
                    None,
                    0.85,
                    ProfilingAmbiguityState.CLEAR,
                )
            elif any(t in ("dept", "department", "team", "unit", "org", "code", "assignment") for t in tokens):
                return (
                    SemanticColumnRole.DIMENSION,
                    SemanticConcept.CATEGORICAL,
                    None,
                    0.80,
                    ProfilingAmbiguityState.CLEAR,
                )
            else:
                return (
                    SemanticColumnRole.DIMENSION,
                    SemanticConcept.CATEGORICAL,
                    None,
                    0.75,
                    ProfilingAmbiguityState.CLEAR,
                )

        # 5. Identifier hypothesis
        has_id_name = any(t in ("id", "code", "key", "uuid", "sku", "badge") for t in tokens) or lex_role == SemanticColumnRole.ENTITY_IDENTIFIER
        if (
            (has_id_name and (features.distinct_ratio >= self.policy.min_distinct_ratio_for_identifier or semantic_dtype == SemanticDtype.IDENTIFIER_CODE))
            or (semantic_dtype == SemanticDtype.IDENTIFIER_CODE and features.identifier_pattern_ratio >= 0.85 and features.distinct_ratio >= self.policy.min_distinct_ratio_for_identifier)
        ):
            conf = 0.90 if has_id_name else 0.78
            return (
                SemanticColumnRole.ENTITY_IDENTIFIER,
                SemanticConcept.IDENTIFIER,
                None,
                conf,
                ProfilingAmbiguityState.CLEAR,
            )

        # 6. Geographic Location
        if semantic_dtype == SemanticDtype.GEOGRAPHIC_LOCATION or lex_role == SemanticColumnRole.LOCATION:
            return (
                SemanticColumnRole.LOCATION,
                SemanticConcept.LOCATION_ATTRIBUTE,
                None,
                0.85,
                ProfilingAmbiguityState.CLEAR,
            )

        # 7. Numeric Measure
        if semantic_dtype in (SemanticDtype.INTEGER_NUMBER, SemanticDtype.DECIMAL_NUMBER):
            # Check if name indicates measure
            m_class = infer_measure_class(tokens, unit)
            if m_class or lex_role == SemanticColumnRole.MEASURE:
                return (
                    SemanticColumnRole.MEASURE,
                    SemanticConcept.MEASURE,
                    m_class or MeasureClass.QUANTITY,
                    0.85,
                    ProfilingAmbiguityState.CLEAR,
                )
            # If high cardinality pure float, likely a continuous measure
            if semantic_dtype == SemanticDtype.DECIMAL_NUMBER and features.distinct_ratio > 0.40:
                return (
                    SemanticColumnRole.MEASURE,
                    SemanticConcept.MEASURE,
                    MeasureClass.QUANTITY,
                    0.75,
                    ProfilingAmbiguityState.CLEAR,
                )

        # 8. Categorical Dimension
        if semantic_dtype == SemanticDtype.CATEGORICAL_CODE or (lex_role in (SemanticColumnRole.DIMENSION, SemanticColumnRole.CATEGORY)):
            return (
                SemanticColumnRole.DIMENSION,
                SemanticConcept.CATEGORICAL,
                None,
                0.80,
                ProfilingAmbiguityState.CLEAR,
            )

        # 9. Free text
        if semantic_dtype == SemanticDtype.NATURAL_LANGUAGE_TEXT:
            return (
                SemanticColumnRole.FREE_TEXT,
                SemanticConcept.FREE_TEXT,
                None,
                0.80,
                ProfilingAmbiguityState.CLEAR,
            )

        # 10. Lexical fallback if score is confident enough
        if lex_role and lex_score >= self.policy.promotion_threshold:
            concept = infer_semantic_concept(lex_role)
            m_class = infer_measure_class(tokens, unit) if lex_role == SemanticColumnRole.MEASURE else None
            return lex_role, concept, m_class, lex_score, ProfilingAmbiguityState.CLEAR

        # 11. Low confidence / ambiguous signals -> Responsible Abstention
        return (
            SemanticColumnRole.UNKNOWN,
            SemanticConcept.UNKNOWN,
            None,
            0.30,
            ProfilingAmbiguityState.UNKNOWN_DISTRIBUTION,
        )

    def _classify_privacy(
        self,
        tokens: list[str],
        role: SemanticColumnRole,
        semantic_dtype: SemanticDtype,
    ) -> PrivacyClassification:
        """
        Classifies columns under the Identifier / Privacy Governance model.
        Direct workforce identifiers are recognized for join authorization.
        Sensitive attributes are tagged for aggregation governance.
        """
        joined = "_".join(tokens)

        # Check for sensitive attributes
        if any(st in joined for st in SENSITIVE_TOKENS):
            return PrivacyClassification.SENSITIVE_ATTRIBUTE

        # Check for direct identifiers
        if role == SemanticColumnRole.ENTITY_IDENTIFIER or semantic_dtype == SemanticDtype.IDENTIFIER_CODE:
            return PrivacyClassification.DIRECT_IDENTIFIER

        if any(t in ("emp_id", "employee_id", "user_id", "customer_id", "ssn", "badge_id") for t in tokens):
            return PrivacyClassification.DIRECT_IDENTIFIER

        return PrivacyClassification.GENERAL_ATTRIBUTE

    def _check_composite_candidate(
        self,
        features: DeterministicColumnFeatures,
        semantic_dtype: SemanticDtype,
        tokens: list[str],
    ) -> bool:
        """Determines if the column qualifies for candidate decomposition evaluation."""
        if semantic_dtype == SemanticDtype.COMPOSITE_TEXT:
            return True

        # Check if delimiter consistency is elevated
        effective_rows = features.row_count - features.null_count
        if effective_rows >= self.policy.min_sample_rows_for_decomposition:
            for d, count in features.delimiter_counts.items():
                if count / effective_rows >= self.policy.min_composite_consistency_ratio:
                    return True

        return False
