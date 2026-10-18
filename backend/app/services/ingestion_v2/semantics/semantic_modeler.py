"""
HighView Ingestion Intelligence V2 — Phase I3
Service: Semantic Modeler
Stage 5: Semantic Modeling
Boundary: Column semantic role & entity classification.
Rules:
- Deterministic classification first.
- Precision over recall: low confidence (< 0.65) strictly yields AMBIGUOUS.
- Value structure overrides contradictory lexical naming.
- Zero relationship discovery, zero join planning, zero EDA-B analytical claims.
- Model escalation strictly guarded: optional, schema validated, cached, fail-soft fallback.
- 100% deterministic stage fingerprints.
"""

from __future__ import annotations

import hashlib
from typing import Any, Protocol

from app.services.ingestion_v2.contracts.base import compute_stage_fingerprint
from app.services.ingestion_v2.contracts.normalization import (
    CanonicalPhysicalType,
    NormalizedColumn,
    NormalizedDataset,
    NormalizedTable,
)
from app.services.ingestion_v2.contracts.profiling import (
    ColumnStructuralProfile,
    StructuralProfile,
    TableStructuralProfile,
)
from app.services.ingestion_v2.contracts.semantics import (
    ClassificationSource,
    MeasureClass,
    SemanticColumnAssignment,
    SemanticColumnRole,
    SemanticConcept,
    SemanticEntityType,
    SemanticModel,
    TableSemanticModel,
)
from app.services.ingestion_v2.semantics.confidence import (
    calculate_semantic_confidence,
)
from app.services.ingestion_v2.semantics.semantic_rules import (
    detect_adversarial_contradiction,
    infer_lexical_entity,
    infer_lexical_role,
    infer_measure_class,
    infer_semantic_concept,
    normalize_tokens,
)

# Governed Thresholds
AMBIGUOUS_CONFIDENCE_THRESHOLD: float = 0.65
MODEL_ESCALATION_LOWER_BOUND: float = 0.40
MODEL_ESCALATION_UPPER_BOUND: float = 0.65


class SemanticModelGateway(Protocol):
    """Protocol for optional model-assisted semantic classification."""
    def classify_column(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        ...


# In-memory session cache for model-assisted classifications
_MODEL_SEMANTIC_CACHE: dict[str, dict[str, Any]] = {}


def _compute_column_semantic_fingerprint(col_name: str, prof: ColumnStructuralProfile) -> str:
    """Computes a deterministic cache key for model classification requests."""
    payload = f"{col_name}:{prof.physical_type}:{prof.uniqueness_ratio}:{prof.null_ratio}:{prof.dominant_pattern}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def classify_column_deterministic(
    col_norm: NormalizedColumn,
    col_prof: ColumnStructuralProfile,
    table_prof: TableStructuralProfile,
) -> SemanticColumnAssignment:
    """
    Step 1: Deterministic semantic classification based on structure, lexical signals, and units.
    """
    col_name = col_norm.column_name
    tokens = normalize_tokens(col_name)
    lex_role, lex_score = infer_lexical_role(tokens)
    lex_entity, entity_score = infer_lexical_entity(tokens)

    # 1. Structural Checks
    is_contradiction = detect_adversarial_contradiction(
        lexical_role=lex_role,
        uniqueness_ratio=col_prof.uniqueness_ratio,
        distinct_count=col_prof.distinct_count,
        candidate_identifier_score=col_prof.candidate_identifier_score,
        candidate_dimension_score=col_prof.candidate_dimension_score,
        row_count=col_prof.row_count,
    )

    if is_contradiction:
        return SemanticColumnAssignment(
            column_id=col_norm.column_id,
            table_id=col_norm.table_id,
            column_name=col_name,
            role=SemanticColumnRole.AMBIGUOUS,
            entity_type=SemanticEntityType.UNKNOWN,
            semantic_concept=SemanticConcept.AMBIGUOUS,
            measure_class=None,
            confidence=0.20,
            is_ambiguous=True,
            classification_source=ClassificationSource.HEURISTIC,
            rationale=f"Adversarial contradiction detected: column '{col_name}' suggests {lex_role.value if lex_role else 'identifier'} but structural distribution has low distinct count ({col_prof.distinct_count}/{col_prof.row_count}).",
        )

    # Handle All-Null or Constant
    if col_prof.null_ratio == 1.0 or col_prof.non_null_count == 0:
        return SemanticColumnAssignment(
            column_id=col_norm.column_id,
            table_id=col_norm.table_id,
            column_name=col_name,
            role=SemanticColumnRole.UNKNOWN,
            entity_type=SemanticEntityType.UNKNOWN,
            semantic_concept=SemanticConcept.UNKNOWN,
            measure_class=None,
            confidence=1.0,
            is_ambiguous=False,
            classification_source=ClassificationSource.STATISTICAL,
            rationale="Column contains 100% null values. Structurally empty.",
        )

    # Technical metadata rule
    if lex_role == SemanticColumnRole.TECHNICAL_METADATA:
        conf = calculate_semantic_confidence(0.95, lex_score, 0.85)
        return SemanticColumnAssignment(
            column_id=col_norm.column_id,
            table_id=col_norm.table_id,
            column_name=col_name,
            role=SemanticColumnRole.TECHNICAL_METADATA,
            entity_type=SemanticEntityType.UNKNOWN,
            semantic_concept=SemanticConcept.TECHNICAL,
            measure_class=None,
            confidence=conf,
            is_ambiguous=False,
            classification_source=ClassificationSource.DICTIONARY,
            rationale=f"Lexical match to pipeline technical metadata keyword in '{col_name}'.",
        )

    # 2. Time Role
    if col_prof.logical_type_candidate in ("DATE", "DATETIME") or col_prof.date_span_days is not None or lex_role == SemanticColumnRole.TIME:
        struct_score = 0.95 if col_prof.logical_type_candidate in ("DATE", "DATETIME") else 0.75
        conf = calculate_semantic_confidence(struct_score, max(0.50, lex_score), 0.80)
        return SemanticColumnAssignment(
            column_id=col_norm.column_id,
            table_id=col_norm.table_id,
            column_name=col_name,
            role=SemanticColumnRole.TIME,
            entity_type=SemanticEntityType.UNKNOWN,
            semantic_concept=SemanticConcept.TIME_SPAN,
            measure_class=None,
            confidence=conf,
            is_ambiguous=False,
            classification_source=ClassificationSource.STATISTICAL,
            rationale=f"Temporal structure validated (logical type: {col_prof.logical_type_candidate}, date span: {col_prof.date_span_days} days).",
        )

    # 3. Entity Label Rule (e.g. employee_name, store_name, customer_name)
    if lex_role == SemanticColumnRole.ENTITY_LABEL:
        ent = lex_entity if lex_entity != SemanticEntityType.UNKNOWN else SemanticEntityType.PERSON
        conf = calculate_semantic_confidence(0.85, 0.85, 0.80)
        return SemanticColumnAssignment(
            column_id=col_norm.column_id,
            table_id=col_norm.table_id,
            column_name=col_name,
            role=SemanticColumnRole.ENTITY_LABEL,
            entity_type=ent,
            semantic_concept=SemanticConcept.DESCRIPTOR,
            measure_class=None,
            confidence=conf,
            is_ambiguous=False,
            classification_source=ClassificationSource.DICTIONARY,
            rationale=f"Entity descriptive label associated with {ent.value}.",
        )

    # 4. Free Text / Notes Rule
    if any(t in col_name.lower() for t in ("note", "comment", "text", "message", "remark", "memo")):
        return SemanticColumnAssignment(
            column_id=col_norm.column_id,
            table_id=col_norm.table_id,
            column_name=col_name,
            role=SemanticColumnRole.FREE_TEXT,
            entity_type=SemanticEntityType.UNKNOWN,
            semantic_concept=SemanticConcept.FREE_TEXT,
            measure_class=None,
            confidence=0.85,
            is_ambiguous=False,
            classification_source=ClassificationSource.DICTIONARY,
            rationale="Unstructured textual notes/comments field.",
        )

    # 5. Measure Rule (Checked before identifier for numeric columns without explicit ID naming)
    is_numeric = col_prof.physical_type in ("INTEGER", "FLOAT") or col_prof.logical_type_candidate in ("INTEGER", "FLOAT")
    has_unit = col_norm.inferred_unit is not None
    is_measure_lexical = lex_role == SemanticColumnRole.MEASURE

    if is_numeric:
        # If numeric and has measure tokens, unit, or lacks identifier naming: it's a MEASURE
        has_id_name = any(t in tokens for t in ("id", "code", "key", "uuid", "sku", "badge"))
        if is_measure_lexical or has_unit or (not has_id_name and col_prof.leading_zero_ratio == 0.0):
            struct_score = 0.90 if (has_unit or col_prof.quantiles or is_measure_lexical) else 0.80
            m_class = infer_measure_class(tokens, col_norm.inferred_unit) or MeasureClass.QUANTITY
            conf = calculate_semantic_confidence(struct_score, max(0.70, lex_score if is_measure_lexical else 0.60), 0.80)
            return SemanticColumnAssignment(
                column_id=col_norm.column_id,
                table_id=col_norm.table_id,
                column_name=col_name,
                role=SemanticColumnRole.MEASURE,
                entity_type=SemanticEntityType.UNKNOWN,
                semantic_concept=SemanticConcept.MEASURE,
                measure_class=m_class,
                confidence=conf,
                is_ambiguous=False,
                classification_source=ClassificationSource.HEURISTIC,
                rationale=f"Numeric measure structure (class: {m_class.value}, unit: {col_norm.inferred_unit or 'numeric'}, quantiles: {list(col_prof.quantiles.keys())}).",
            )

    # 6. Entity Identifier Rule
    # Requires identifier lexical naming OR leading zeros OR structured alphanumeric ID pattern OR strong uniqueness
    has_id_signal = any(t in tokens for t in ("id", "code", "num", "number", "key", "uuid", "hash", "badge", "sku")) or col_prof.leading_zero_ratio > 0.0
    is_valid_id_candidate = (
        (col_prof.candidate_identifier_score >= 0.75 or col_prof.is_unique_candidate)
        and (has_id_signal or (col_prof.row_count >= 20 and col_prof.uniqueness_ratio >= 0.95))
        and not is_contradiction
    )

    if is_valid_id_candidate:
        struct_score = col_prof.candidate_identifier_score
        ent = lex_entity if lex_entity != SemanticEntityType.UNKNOWN else SemanticEntityType.UNKNOWN
        conf = calculate_semantic_confidence(struct_score, max(0.60, lex_score), 0.80)
        evidence = f"Candidate identifier score: {col_prof.candidate_identifier_score:.2f}, uniqueness: {col_prof.uniqueness_ratio:.2f}"
        if col_prof.leading_zero_ratio > 0.0:
            evidence += f", leading zero ratio: {col_prof.leading_zero_ratio:.2f} (identifier text fidelity preserved)"
        return SemanticColumnAssignment(
            column_id=col_norm.column_id,
            table_id=col_norm.table_id,
            column_name=col_name,
            role=SemanticColumnRole.ENTITY_IDENTIFIER,
            entity_type=ent,
            semantic_concept=SemanticConcept.IDENTIFIER,
            measure_class=None,
            confidence=conf,
            is_ambiguous=False,
            classification_source=ClassificationSource.HEURISTIC,
            rationale=f"High structural identifier likelihood. {evidence}.",
        )

    # 7. Boolean / Status Rule
    if col_prof.logical_type_candidate == "BOOLEAN" or (col_prof.distinct_count == 2 and col_prof.row_count >= 10):
        conf = calculate_semantic_confidence(0.90, max(0.50, lex_score), 0.80)
        return SemanticColumnAssignment(
            column_id=col_norm.column_id,
            table_id=col_norm.table_id,
            column_name=col_name,
            role=SemanticColumnRole.BOOLEAN,
            entity_type=SemanticEntityType.UNKNOWN,
            semantic_concept=SemanticConcept.STATUS,
            measure_class=None,
            confidence=conf,
            is_ambiguous=False,
            classification_source=ClassificationSource.STATISTICAL,
            rationale="Binary boolean distribution confirmed.",
        )

    if lex_role == SemanticColumnRole.STATUS or (col_prof.distinct_count <= 10 and any(w in col_name.lower() for w in ("status", "state", "stage"))):
        conf = calculate_semantic_confidence(0.85, 0.85, 0.80)
        return SemanticColumnAssignment(
            column_id=col_norm.column_id,
            table_id=col_norm.table_id,
            column_name=col_name,
            role=SemanticColumnRole.STATUS,
            entity_type=SemanticEntityType.UNKNOWN,
            semantic_concept=SemanticConcept.STATUS,
            measure_class=None,
            confidence=conf,
            is_ambiguous=False,
            classification_source=ClassificationSource.DICTIONARY,
            rationale="Status code structure with discrete workflow states.",
        )

    # 8. Entity Label Rule (fallback)
    if lex_role == SemanticColumnRole.ENTITY_LABEL:
        ent = lex_entity if lex_entity != SemanticEntityType.UNKNOWN else SemanticEntityType.PERSON
        conf = calculate_semantic_confidence(0.80, 0.85, 0.80)
        return SemanticColumnAssignment(
            column_id=col_norm.column_id,
            table_id=col_norm.table_id,
            column_name=col_name,
            role=SemanticColumnRole.ENTITY_LABEL,
            entity_type=ent,
            semantic_concept=SemanticConcept.DESCRIPTOR,
            measure_class=None,
            confidence=conf,
            is_ambiguous=False,
            classification_source=ClassificationSource.DICTIONARY,
            rationale=f"Entity descriptive label associated with {ent.value}.",
        )

    # 9. Dimension / Category Rule
    if col_prof.candidate_dimension_score >= 0.40 or col_prof.distinct_count <= 50:
        ent = lex_entity if lex_entity != SemanticEntityType.UNKNOWN else SemanticEntityType.UNKNOWN
        conf = calculate_semantic_confidence(col_prof.candidate_dimension_score, max(0.50, lex_score), 0.70)
        return SemanticColumnAssignment(
            column_id=col_norm.column_id,
            table_id=col_norm.table_id,
            column_name=col_name,
            role=SemanticColumnRole.DIMENSION,
            entity_type=ent,
            semantic_concept=SemanticConcept.CATEGORICAL,
            measure_class=None,
            confidence=conf,
            is_ambiguous=False,
            classification_source=ClassificationSource.STATISTICAL,
            rationale=f"Discrete categorical dimension (distinct count: {col_prof.distinct_count}, normalized entropy: {col_prof.normalized_entropy}).",
        )

    # 10. Fallback: If confidence is low, assign AMBIGUOUS
    return SemanticColumnAssignment(
        column_id=col_norm.column_id,
        table_id=col_norm.table_id,
        column_name=col_name,
        role=SemanticColumnRole.AMBIGUOUS,
        entity_type=SemanticEntityType.UNKNOWN,
        semantic_concept=SemanticConcept.AMBIGUOUS,
        measure_class=None,
        confidence=0.45,
        is_ambiguous=True,
        classification_source=ClassificationSource.STATISTICAL,
        rationale=f"Column '{col_name}' lacks conclusive structural or lexical evidence. Safely marked AMBIGUOUS.",
    )


def build_table_semantic_model(
    table_norm: NormalizedTable,
    table_prof: TableStructuralProfile,
    model_gateway: SemanticModelGateway | None = None,
) -> TableSemanticModel:
    """Builds semantic assignments for all columns in a logical table."""
    norm_col_map = {c.column_name: c for c in table_norm.columns}
    prof_col_map = {c.column_name: c for c in table_prof.columns}

    assignments: list[SemanticColumnAssignment] = []

    for col_name, col_norm in norm_col_map.items():
        col_prof = prof_col_map.get(col_name)
        if not col_prof:
            continue

        assignment = classify_column_deterministic(col_norm, col_prof, table_prof)

        # Model Escalation Check
        if assignment.is_ambiguous and MODEL_ESCALATION_LOWER_BOUND <= assignment.confidence < MODEL_ESCALATION_UPPER_BOUND:
            if model_gateway is not None:
                cache_key = _compute_column_semantic_fingerprint(col_name, col_prof)
                if cache_key in _MODEL_SEMANTIC_CACHE:
                    cached = _MODEL_SEMANTIC_CACHE[cache_key]
                    assignment = SemanticColumnAssignment(**cached)
                else:
                    try:
                        prompt = (
                            f"Classify semantic role and entity for column '{col_name}' with type {col_prof.physical_type}, "
                            f"distinct_count {col_prof.distinct_count}, uniqueness {col_prof.uniqueness_ratio:.2f}."
                        )
                        schema = {
                            "role": [r.value for r in SemanticColumnRole],
                            "entity_type": [e.value for e in SemanticEntityType],
                        }
                        res = model_gateway.classify_column(prompt, schema)
                        cand_role = SemanticColumnRole(res["role"])
                        cand_ent = SemanticEntityType(res["entity_type"])
                        cand_conf = float(res.get("confidence", 0.75))

                        # Arbitration: Model cannot override structural contradiction
                        if col_prof.null_ratio == 1.0 or (cand_role == SemanticColumnRole.ENTITY_IDENTIFIER and col_prof.uniqueness_ratio < 0.75):
                            assignment = assignment.model_copy(
                                update={"rationale": f"{assignment.rationale} (Model escalation contradicted structural truth; rejected)."}
                            )
                        else:
                            assignment = SemanticColumnAssignment(
                                column_id=col_norm.column_id,
                                table_id=col_norm.table_id,
                                column_name=col_name,
                                role=cand_role,
                                entity_type=cand_ent,
                                semantic_concept=infer_semantic_concept(cand_role),
                                measure_class=infer_measure_class(normalize_tokens(col_name), col_norm.inferred_unit) if cand_role == SemanticColumnRole.MEASURE else None,
                                confidence=cand_conf,
                                is_ambiguous=cand_conf < AMBIGUOUS_CONFIDENCE_THRESHOLD,
                                classification_source=ClassificationSource.MODEL_ASSISTED,
                                rationale=f"Model-assisted classification validated by structural guard. {res.get('rationale', '')}",
                            )
                            _MODEL_SEMANTIC_CACHE[cache_key] = assignment.model_dump()
                    except Exception:
                        # Fail-soft offline fallback
                        assignment = assignment.model_copy(
                            update={
                                "classification_source": ClassificationSource.FALLBACK,
                                "rationale": f"{assignment.rationale} (Model assistance unavailable; safely preserved AMBIGUOUS).",
                            }
                        )

        assignments.append(assignment)

    # Infer Primary Entity Type for Table
    primary_entity = SemanticEntityType.UNKNOWN
    # Priority: Person > Store > Department > Organization > Product > Transaction > Event
    entity_priority = [
        SemanticEntityType.PERSON,
        SemanticEntityType.STORE,
        SemanticEntityType.DEPARTMENT,
        SemanticEntityType.PRODUCT,
        SemanticEntityType.TRANSACTION,
        SemanticEntityType.ORGANIZATION,
        SemanticEntityType.FACILITY,
        SemanticEntityType.LOCATION,
        SemanticEntityType.DEVICE,
    ]

    assigned_entities = {a.entity_type for a in assignments if a.role == SemanticColumnRole.ENTITY_IDENTIFIER and a.entity_type not in (SemanticEntityType.UNKNOWN, SemanticEntityType.AMBIGUOUS)}
    if not assigned_entities:
        assigned_entities = {a.entity_type for a in assignments if a.entity_type not in (SemanticEntityType.UNKNOWN, SemanticEntityType.AMBIGUOUS)}

    for ep in entity_priority:
        if ep in assigned_entities:
            primary_entity = ep
            break

    return TableSemanticModel(
        table_id=table_norm.table_id,
        table_name=table_norm.table_name,
        primary_entity_type=primary_entity,
        columns=assignments,
    )


def build_semantic_model(
    normalized_dataset: NormalizedDataset,
    structural_profile: StructuralProfile,
    model_gateway: SemanticModelGateway | None = None,
) -> SemanticModel:
    """
    Main Entry Point: Build Stage 5 SemanticModel from NormalizedDataset and StructuralProfile.
    """
    table_models: list[TableSemanticModel] = []
    norm_tbl_map = {t.table_id: t for t in normalized_dataset.tables}
    prof_tbl_map = {t.table_id: t for t in structural_profile.tables}

    for tbl_id, norm_tbl in norm_tbl_map.items():
        prof_tbl = prof_tbl_map.get(tbl_id)
        if not prof_tbl:
            continue
        tbl_model = build_table_semantic_model(norm_tbl, prof_tbl, model_gateway)
        table_models.append(tbl_model)

    raw_dict = {
        "dataset_id": normalized_dataset.dataset_id,
        "tables": [t.model_dump() for t in table_models],
    }
    stage_fp = compute_stage_fingerprint(raw_dict)

    return SemanticModel(
        dataset_id=normalized_dataset.dataset_id,
        run_id=normalized_dataset.run_id,
        stage_name="semantic_modeling",
        source_fingerprint=stage_fp,
        provenance=list(normalized_dataset.provenance),
        tables=table_models,
    )
