"""
HighView Ingestion Intelligence V2 — Phase I3
Service: Grain Inferencer
Stage 5: Grain Inference
Boundary: Determination of row-level observational grain.
Rules:
- Grain answers: "WHAT DOES ONE ROW REPRESENT?".
- Analytical Grain != Primary Key (surrogate keys like 'row_id' do not define business grain).
- Supports single-entity, periodic snapshot composite grains, and event/transaction grains.
- Zero cross-table relationship discovery or join creation.
- Zero analytical claims or business stories.
- 100% deterministic stage fingerprints.
"""

from __future__ import annotations

from app.services.ingestion_v2.contracts.base import compute_stage_fingerprint
from app.services.ingestion_v2.contracts.grain import (
    CanonicalGrain,
    GrainProfile,
    TableGrainProfile,
    TemporalGrain,
)
from app.services.ingestion_v2.contracts.normalization import (
    NormalizedDataset,
    NormalizedTable,
)
from app.services.ingestion_v2.contracts.profiling import (
    ColumnStructuralProfile,
    StructuralProfile,
    TableStructuralProfile,
)
from app.services.ingestion_v2.contracts.semantics import (
    SemanticColumnAssignment,
    SemanticColumnRole,
    SemanticEntityType,
    SemanticModel,
    TableSemanticModel,
)
from app.services.ingestion_v2.grain.grain_confidence import (
    calculate_grain_confidence,
)
from app.services.ingestion_v2.grain.grain_rules import (
    COMPOSITE_GRAIN_UNIQUENESS_THRESHOLD,
    ENTITY_TO_GRAIN_MAP,
    MIN_GRAIN_KEY_UNIQUENESS,
    map_temporal_frequency,
)


def infer_table_grain(
    table_norm: NormalizedTable,
    table_prof: TableStructuralProfile,
    table_sem: TableSemanticModel,
) -> TableGrainProfile:
    """
    Infers the observational grain for an individual table.
    Distinguishes business analytical grain from technical primary keys.
    """
    row_count = table_prof.row_count
    if row_count == 0 or len(table_sem.columns) == 0:
        return TableGrainProfile(
            table_id=table_norm.table_id,
            table_name=table_norm.table_name,
            primary_entity=CanonicalGrain.UNKNOWN,
            temporal_grain=TemporalGrain.NONE,
            key_columns=[],
            grain_dimensions=[],
            grain_expression="UNKNOWN",
            is_unique=False,
            uniqueness_ratio=0.0,
            grain_confidence=0.0,
            duplicate_key_rows=0,
            candidate_grains=[],
            grain_status="UNKNOWN",
            rationale="Table contains 0 rows or 0 columns; grain cannot be inferred.",
        )

    col_prof_map = {c.column_name: c for c in table_prof.columns}
    col_sem_map = {c.column_name: c for c in table_sem.columns}

    # Step 1: Identify Entity Identifier & Dimension Candidates
    entity_id_cols: list[tuple[SemanticColumnAssignment, ColumnStructuralProfile]] = []
    dimension_cols: list[tuple[SemanticColumnAssignment, ColumnStructuralProfile]] = []
    time_cols: list[tuple[SemanticColumnAssignment, ColumnStructuralProfile]] = []
    surrogate_id_cols: list[str] = []

    for name, sem in col_sem_map.items():
        prof = col_prof_map.get(name)
        if not prof:
            continue

        if sem.role == SemanticColumnRole.ENTITY_IDENTIFIER:
            # Check if it's a generic surrogate key (row_id, id, seq, index)
            if name.lower() in ("row_id", "rowid", "id", "_id", "index", "seq", "surrogate_key"):
                surrogate_id_cols.append(name)
            else:
                entity_id_cols.append((sem, prof))
        elif sem.role == SemanticColumnRole.TIME:
            time_cols.append((sem, prof))
        elif sem.role in (SemanticColumnRole.DIMENSION, SemanticColumnRole.CATEGORY, SemanticColumnRole.LOCATION):
            dimension_cols.append((sem, prof))

    has_surrogate = len(surrogate_id_cols) > 0

    # Step 2: Event / Transaction Detection
    # If table has a transaction/order/event identifier, it is an Event/Transaction table
    for sem, prof in entity_id_cols:
        if sem.entity_type in (SemanticEntityType.TRANSACTION, SemanticEntityType.EVENT):
            primary_entity = CanonicalGrain.TRANSACTION if sem.entity_type == SemanticEntityType.TRANSACTION else CanonicalGrain.EVENT
            temporal = TemporalGrain.NONE
            time_names = []
            if time_cols:
                t_sem, t_prof = time_cols[0]
                temporal = map_temporal_frequency(t_prof.column_name, t_prof.date_span_days, t_prof.distinct_count)
                time_names.append(t_prof.column_name)

            conf = calculate_grain_confidence(prof.uniqueness_ratio, sem.confidence, 1.0)
            return TableGrainProfile(
                table_id=table_norm.table_id,
                table_name=table_norm.table_name,
                primary_entity=primary_entity,
                temporal_grain=temporal,
                key_columns=[prof.column_name],
                grain_dimensions=time_names,
                grain_expression=primary_entity.value,
                is_unique=prof.uniqueness_ratio >= MIN_GRAIN_KEY_UNIQUENESS,
                uniqueness_ratio=prof.uniqueness_ratio,
                grain_confidence=conf,
                duplicate_key_rows=row_count - prof.distinct_count,
                candidate_grains=[primary_entity.value],
                grain_status="RESOLVED",
                rationale=f"Event/Transaction grain identified by '{prof.column_name}' ({sem.entity_type.value}).",
            )

    # Step 3: Entity Snapshot (Single Entity Grain)
    # If an entity identifier column is uniquely keying the table and there is NO periodic time column
    if entity_id_cols:
        best_id_sem, best_id_prof = max(entity_id_cols, key=lambda x: x[1].uniqueness_ratio)
        if best_id_prof.uniqueness_ratio >= MIN_GRAIN_KEY_UNIQUENESS and not time_cols:
            primary_grain = ENTITY_TO_GRAIN_MAP.get(best_id_sem.entity_type, CanonicalGrain.PERSON)
            conf = calculate_grain_confidence(best_id_prof.uniqueness_ratio, best_id_sem.confidence, 1.0)
            return TableGrainProfile(
                table_id=table_norm.table_id,
                table_name=table_norm.table_name,
                primary_entity=primary_grain,
                temporal_grain=TemporalGrain.NONE,
                key_columns=[best_id_prof.column_name],
                grain_dimensions=[],
                grain_expression=primary_grain.value,
                is_unique=True,
                uniqueness_ratio=best_id_prof.uniqueness_ratio,
                grain_confidence=conf,
                duplicate_key_rows=row_count - best_id_prof.distinct_count,
                candidate_grains=[primary_grain.value],
                grain_status="RESOLVED",
                rationale=f"Single entity observational grain: 1 row represents one {primary_grain.value} keyed by '{best_id_prof.column_name}'.",
            )

    # Step 4: Composite Grain (Entity x Temporal Periodic Snapshot)
    # e.g., PERSON x DAY, DEPARTMENT x MONTH, STORE x WEEK
    if time_cols:
        best_time_sem, best_time_prof = time_cols[0]
        temporal_freq = map_temporal_frequency(
            best_time_prof.column_name,
            best_time_prof.date_span_days,
            best_time_prof.distinct_count,
        )

        # Candidate entities: either from entity_id_cols or dimension_cols (e.g. Department, Store, Product)
        entity_candidates = entity_id_cols if entity_id_cols else dimension_cols
        if entity_candidates:
            best_ent_sem, best_ent_prof = entity_candidates[0]
            ent_grain = ENTITY_TO_GRAIN_MAP.get(best_ent_sem.entity_type, CanonicalGrain.PERSON)
            if ent_grain in (CanonicalGrain.UNKNOWN, CanonicalGrain.AMBIGUOUS):
                # Fallback to department or person if naming suggests
                if "dept" in best_ent_prof.column_name.lower():
                    ent_grain = CanonicalGrain.DEPARTMENT
                elif "store" in best_ent_prof.column_name.lower():
                    ent_grain = CanonicalGrain.STORE
                elif "prod" in best_ent_prof.column_name.lower():
                    ent_grain = CanonicalGrain.PRODUCT
                else:
                    ent_grain = CanonicalGrain.PERSON

            # Check composite uniqueness from I2 pre-evaluated candidate pairs
            composite_unique = False
            comp_uniqueness = 0.95
            for pair in table_prof.candidate_composite_keys:
                names = pair.get("column_names", [])
                if best_ent_prof.column_name in names and best_time_prof.column_name in names:
                    comp_uniqueness = pair.get("pair_uniqueness_ratio", 0.95)
                    composite_unique = pair.get("is_composite_unique", False)
                    break

            grain_expr = f"{ent_grain.value} x {temporal_freq.value}"
            conf = calculate_grain_confidence(comp_uniqueness, best_ent_sem.confidence, 0.90, has_surrogate)
            return TableGrainProfile(
                table_id=table_norm.table_id,
                table_name=table_norm.table_name,
                primary_entity=ent_grain,
                temporal_grain=temporal_freq,
                key_columns=[best_ent_prof.column_name, best_time_prof.column_name],
                grain_dimensions=[best_time_prof.column_name],
                grain_expression=grain_expr,
                is_unique=comp_uniqueness >= COMPOSITE_GRAIN_UNIQUENESS_THRESHOLD,
                uniqueness_ratio=comp_uniqueness,
                grain_confidence=conf,
                duplicate_key_rows=0 if composite_unique else int(row_count * (1.0 - comp_uniqueness)),
                candidate_grains=[grain_expr],
                grain_status="RESOLVED",
                rationale=f"Periodic snapshot grain: 1 row represents {grain_expr} keyed by ('{best_ent_prof.column_name}', '{best_time_prof.column_name}').",
            )

    # Step 5: Multi-Entity Composite (e.g. PRODUCT x LOCATION)
    all_entity_cols = entity_id_cols + dimension_cols
    if len(all_entity_cols) >= 2:
        names = [p.column_name for _, p in all_entity_cols[:2]]
        entities = [s.entity_type.value for s, _ in all_entity_cols[:2]]
        grain_expr = " x ".join(entities)
        return TableGrainProfile(
            table_id=table_norm.table_id,
            table_name=table_norm.table_name,
            primary_entity=CanonicalGrain.COMPOSITE,
            temporal_grain=TemporalGrain.NONE,
            key_columns=names,
            grain_dimensions=names,
            grain_expression=grain_expr,
            is_unique=True,
            uniqueness_ratio=0.90,
            grain_confidence=0.85,
            duplicate_key_rows=0,
            candidate_grains=[grain_expr],
            grain_status="RESOLVED",
            rationale=f"Multi-entity composite grain: {grain_expr} keyed by {names}.",
        )

    # Step 6: Ambiguous / Unknown Grain Fallback
    if surrogate_id_cols:
        # Table only has a surrogate key like 'row_id' with no business entity
        return TableGrainProfile(
            table_id=table_norm.table_id,
            table_name=table_norm.table_name,
            primary_entity=CanonicalGrain.UNKNOWN,
            temporal_grain=TemporalGrain.NONE,
            key_columns=surrogate_id_cols,
            grain_dimensions=[],
            grain_expression="AMBIGUOUS",
            is_unique=True,
            uniqueness_ratio=1.0,
            grain_confidence=0.50,
            duplicate_key_rows=0,
            candidate_grains=["TRANSACTION", "ROW_SNAPSHOT"],
            grain_status="AMBIGUOUS",
            rationale="Table contains surrogate primary key but lacks conclusive business entity or temporal observational structure. Marked AMBIGUOUS.",
        )

    return TableGrainProfile(
        table_id=table_norm.table_id,
        table_name=table_norm.table_name,
        primary_entity=CanonicalGrain.UNKNOWN,
        temporal_grain=TemporalGrain.NONE,
        key_columns=[],
        grain_dimensions=[],
        grain_expression="UNKNOWN",
        is_unique=False,
        uniqueness_ratio=0.0,
        grain_confidence=0.0,
        duplicate_key_rows=0,
        candidate_grains=[],
        grain_status="UNKNOWN",
        rationale="Insufficient structural or semantic evidence to infer table grain.",
    )


def infer_grain(
    normalized_dataset: NormalizedDataset,
    structural_profile: StructuralProfile,
    semantic_model: SemanticModel,
) -> GrainProfile:
    """
    Main Entry Point: Infer observational grains for all tables in NormalizedDataset.
    """
    table_grains: list[TableGrainProfile] = []
    norm_tbl_map = {t.table_id: t for t in normalized_dataset.tables}
    prof_tbl_map = {t.table_id: t for t in structural_profile.tables}
    sem_tbl_map = {t.table_id: t for t in semantic_model.tables}

    for tbl_id, norm_tbl in norm_tbl_map.items():
        prof_tbl = prof_tbl_map.get(tbl_id)
        sem_tbl = sem_tbl_map.get(tbl_id)
        if not prof_tbl or not sem_tbl:
            continue

        grain = infer_table_grain(norm_tbl, prof_tbl, sem_tbl)
        table_grains.append(grain)

    raw_dict = {
        "dataset_id": normalized_dataset.dataset_id,
        "table_grains": [g.model_dump() for g in table_grains],
    }
    stage_fp = compute_stage_fingerprint(raw_dict)

    return GrainProfile(
        dataset_id=normalized_dataset.dataset_id,
        run_id=normalized_dataset.run_id,
        stage_name="grain_inference",
        source_fingerprint=stage_fp,
        provenance=list(normalized_dataset.provenance),
        table_grains=table_grains,
    )
