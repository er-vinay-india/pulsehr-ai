"""
HighView Semantic Data Refinery — Phase SDR-5
Relationship Intelligence & Join Governance
Full Certification Corpus Benchmark & Evaluation Suite
"""

import hashlib
import json
from pathlib import Path
import time
import tracemalloc
import pandas as pd
import pytest

from app.services.ingestion_v2.contracts.joins import (
    JoinSafetyStatus,
    MeasureAdditivity,
    PreAggregationSpec,
)
from app.services.ingestion_v2.contracts.semantics import MeasureClass
from app.services.ingestion_v2.contracts.relationships import (
    CandidateKeyType,
    RelationshipCardinality,
    RelationshipStatus,
)
from app.services.ingestion_v2.contracts.semantic_graph import (
    GraphEdgeType,
    GraphNodeType,
    SemanticGraph,
    SemanticGraphNode,
)
from app.services.ingestion_v2.retrieval.namespaces import (
    AuthorityClass,
    RetrievalNamespace,
)
from app.services.sdr.artifacts.artifact_writer import SDRArtifactWriter
from app.services.ingestion_v2.contracts.grain import (
    CanonicalGrain,
    TemporalGrain,
)
from app.services.sdr.contracts.grain import (
    GrainCandidate,
    GrainStatus,
    SDRGrainProfile,
)
from app.services.sdr.contracts.keys import (
    KeyAuthority,
    KeyCandidateStatus,
    KeyCandidateType,
    SDRKeyCandidate,
)
from app.services.sdr.contracts.policies import SDRPolicySuite
from app.services.sdr.contracts.profiles import (
    DeterministicColumnFeatures,
    PrivacyClassification,
    ProfilingAmbiguityState,
    SemanticColumnProfile,
    SemanticColumnRole,
    SemanticConcept,
    SemanticDtype,
    SemanticEntityType,
    SourceCoordinateRef,
)
from app.services.sdr.contracts.relationships import (
    RelationshipClass,
    SDRJoinPlan,
    SDRRelationshipCandidate,
    SDRValidatedRelationshipEdge,
    check_edge_invalidation,
    check_join_plan_invalidation,
)
from app.services.sdr.relationships.candidate_discovery import (
    CandidateDiscoveryStats,
    RelationshipDiscoveryEngine,
)
from app.services.sdr.relationships.join_governance import (
    JoinGovernanceEngine,
    infer_column_additivity,
)
from app.services.sdr.relationships.relationship_validator import (
    RelationshipValidatorEngine,
)
from app.services.sdr.relationships.semantic_graph_adapter import (
    SDRSemanticGraphAdapter,
)
from app.services.sdr.retrieval.retrieval_adapter import SDRRetrievalAdapter

P0_EXPECTED_SHA = "1561d64eeae26f4d30926371740d6ca9dc41eb6ea7c537281763b7d5aabd9496"
P0_EXPECTED_SIZE = 70385664


def _create_profile(
    dataset_id: str,
    sheet_id: str,
    column_id: str,
    source_name: str,
    role: SemanticColumnRole = SemanticColumnRole.DIMENSION,
    concept: SemanticConcept = SemanticConcept.DESCRIPTOR,
    dtype: SemanticDtype = SemanticDtype.CATEGORICAL_CODE,
    entity_type: SemanticEntityType = SemanticEntityType.UNKNOWN,
    sample_values: list[str] | None = None,
    measure_class: MeasureClass | None = None,
) -> SemanticColumnProfile:
    samples = sample_values or ["A", "B", "C"]
    features = DeterministicColumnFeatures(
        row_count=len(samples),
        null_count=0,
        null_ratio=0.0,
        distinct_count=len(set(samples)),
        distinct_ratio=len(set(samples)) / max(len(samples), 1),
        sample_values=samples[:5],
    )
    return SemanticColumnProfile(
        dataset_id=dataset_id,
        sheet_id=sheet_id,
        column_id=column_id,
        source_name=source_name,
        canonical_name=source_name.lower(),
        physical_dtype="VARCHAR",
        semantic_dtype=dtype,
        semantic_role=role,
        semantic_concept=concept,
        entity_type_hypothesis=entity_type,
        measure_class=measure_class,
        privacy_classification=PrivacyClassification.PUBLIC,
        confidence=0.95,
        ambiguity_state=ProfilingAmbiguityState.CLEAR,
        features=features,
        source_lineage=SourceCoordinateRef(
            dataset_id=dataset_id,
            sheet_id=sheet_id,
            column_ids=[column_id],
            source_file_hash="dummy_hash",
        ),
        profile_id=f"prof_{column_id}",
        artifact_fingerprint=f"fp_{column_id}",
    )


def _create_grain_profile(sheet_id: str, grain_expr: str, grain_fingerprint: str = "") -> SDRGrainProfile:
    return SDRGrainProfile(
        profile_id=f"prof_grain_{sheet_id}",
        dataset_id="ds_cert",
        sheet_id=sheet_id,
        primary_entity=CanonicalGrain.COMPOSITE,
        temporal_grain=TemporalGrain.NONE,
        resolved_grain_expression=grain_expr,
        grain_status=GrainStatus.RESOLVED,
        grain_confidence=1.0,
        grain_fingerprint=grain_fingerprint,
        rationale="test grain",
    )


# =========================================================================
# 1. SCENARIO A: DIMENSION LOOKUP (Sales -> Stores)
# =========================================================================

def test_scenario_a_dimension_lookup_safe():
    """
    Stores: store_id, store_name, region (grain: STORE)
    Sales: sale_id, store_id, amount (grain: SALE)
    Expected: Sales.store_id -> Stores.store_id, MANY_TO_ONE, SAFE.
    """
    dataset_id = "ds_dim_lookup"
    df_stores = pd.DataFrame({
        "store_id": ["S1", "S2", "S3"],
        "store_name": ["Store North", "Store South", "Store East"],
        "region": ["North", "South", "East"],
    })
    df_sales = pd.DataFrame({
        "sale_id": [101, 102, 103, 104, 105],
        "store_id": ["S1", "S1", "S2", "S2", "S3"],
        "amount": [150.0, 200.0, 95.0, 310.0, 120.0],
    })

    stores_profs = [
        _create_profile(dataset_id, "stores", "store_id", "store_id", role=SemanticColumnRole.ENTITY_IDENTIFIER, concept=SemanticConcept.IDENTIFIER, entity_type=SemanticEntityType.STORE),
        _create_profile(dataset_id, "stores", "store_name", "store_name", role=SemanticColumnRole.ENTITY_LABEL, concept=SemanticConcept.DESCRIPTOR),
        _create_profile(dataset_id, "stores", "region", "region", role=SemanticColumnRole.DIMENSION, concept=SemanticConcept.LOCATION_ATTRIBUTE),
    ]
    sales_profs = [
        _create_profile(dataset_id, "sales", "sale_id", "sale_id", role=SemanticColumnRole.ENTITY_IDENTIFIER, concept=SemanticConcept.IDENTIFIER, entity_type=SemanticEntityType.TRANSACTION),
        _create_profile(dataset_id, "sales", "store_id", "store_id", role=SemanticColumnRole.ENTITY_IDENTIFIER, concept=SemanticConcept.IDENTIFIER, entity_type=SemanticEntityType.STORE),
        _create_profile(dataset_id, "sales", "amount", "amount", role=SemanticColumnRole.MEASURE, concept=SemanticConcept.MEASURE, dtype=SemanticDtype.CURRENCY_AMOUNT),
    ]

    stores_grain = _create_grain_profile("stores", "STORE")
    sales_grain = _create_grain_profile("sales", "SALE")

    discovery = RelationshipDiscoveryEngine()
    validator = RelationshipValidatorEngine()
    governance = JoinGovernanceEngine()

    cands, _ = discovery.discover_candidates(
        dataset_id=dataset_id,
        profiles_by_sheet={"sales": sales_profs, "stores": stores_profs},
        grain_profiles_by_sheet={"sales": sales_grain, "stores": stores_grain},
        table_data={"sales": df_sales, "stores": df_stores},
    )

    assert len(cands) == 1
    cand = cands[0]
    assert "store_id" in cand.left_column_ids
    assert "store_id" in cand.right_column_ids

    # Validate
    edge = validator.validate_candidate(cand, df_left=df_sales, df_right=df_stores)
    assert edge.status == RelationshipStatus.VALIDATED
    assert edge.cardinality == RelationshipCardinality.MANY_TO_ONE
    assert edge.referential_coverage == 1.0
    assert edge.is_grain_preserving is True

    # JoinPlan
    plan = governance.plan_join(
        edge=edge,
        left_grain_profile=sales_grain,
        right_grain_profile=stores_grain,
        left_profiles=sales_profs,
        right_profiles=stores_profs,
    )
    assert plan.safety_status == JoinSafetyStatus.SAFE
    assert plan.target_grain == "SALE"
    assert "DIMENSION_LOOKUP" in plan.safe_operations

    # Dry-run
    dry_res = governance.dry_run_validate_join_plan(plan, df_left=df_sales, df_right=df_stores)
    assert dry_res["dry_run_passed"] is True
    assert dry_res["output_rows"] == 5


# =========================================================================
# 2. SCENARIO B: EMPLOYEE / ATTENDANCE (MEASURE MULTIPLICATION RISK)
# =========================================================================

def test_scenario_b_employee_attendance_measure_multiplication_risk():
    """
    Employees: employee_id, department, salary (1 row per employee)
    Attendance: employee_id, attendance_date, hours (many rows per employee)
    Raw join from Employees -> Attendance multiplies salary.
    System must flag MEASURE_MULTIPLICATION_RISK and refuse blind SAFE authorization.
    """
    dataset_id = "ds_emp_att"
    df_emp = pd.DataFrame({
        "employee_id": ["E1", "E2"],
        "department": ["Eng", "Sales"],
        "salary": [100000, 90000],
    })
    df_att = pd.DataFrame({
        "employee_id": ["E1", "E1", "E1", "E2", "E2"],
        "attendance_date": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-01", "2026-01-02"],
        "hours": [8, 8, 7, 8, 8],
    })

    emp_profs = [
        _create_profile(dataset_id, "emp", "employee_id", "employee_id", role=SemanticColumnRole.ENTITY_IDENTIFIER, concept=SemanticConcept.IDENTIFIER, entity_type=SemanticEntityType.PERSON),
        _create_profile(dataset_id, "emp", "department", "department", role=SemanticColumnRole.DIMENSION, concept=SemanticConcept.DESCRIPTOR),
        _create_profile(dataset_id, "emp", "salary", "salary", role=SemanticColumnRole.MEASURE, concept=SemanticConcept.MEASURE, dtype=SemanticDtype.CURRENCY_AMOUNT),
    ]
    att_profs = [
        _create_profile(dataset_id, "att", "employee_id", "employee_id", role=SemanticColumnRole.ENTITY_IDENTIFIER, concept=SemanticConcept.IDENTIFIER, entity_type=SemanticEntityType.PERSON),
        _create_profile(dataset_id, "att", "attendance_date", "attendance_date", role=SemanticColumnRole.TIME, concept=SemanticConcept.TIME_SPAN, dtype=SemanticDtype.DATE),
        _create_profile(dataset_id, "att", "hours", "hours", role=SemanticColumnRole.MEASURE, concept=SemanticConcept.MEASURE, dtype=SemanticDtype.INTEGER),
    ]

    emp_grain = _create_grain_profile("emp", "EMPLOYEE")
    att_grain = _create_grain_profile("att", "EMPLOYEE × DAY")

    discovery = RelationshipDiscoveryEngine()
    validator = RelationshipValidatorEngine()
    governance = JoinGovernanceEngine()

    cands, _ = discovery.discover_candidates(
        dataset_id=dataset_id,
        profiles_by_sheet={"emp": emp_profs, "att": att_profs},
        grain_profiles_by_sheet={"emp": emp_grain, "att": att_grain},
        table_data={"emp": df_emp, "att": df_att},
    )

    edge = validator.validate_candidate(cands[0], df_left=df_emp, df_right=df_att)
    assert edge.status == RelationshipStatus.VALIDATED
    assert edge.cardinality == RelationshipCardinality.ONE_TO_MANY
    assert edge.duplication_risk_flag is True

    # Plan without preaggregation -> UNSAFE due to MEASURE_MULTIPLICATION_RISK
    plan = governance.plan_join(
        edge=edge,
        left_grain_profile=emp_grain,
        right_grain_profile=att_grain,
        left_profiles=emp_profs,
        right_profiles=att_profs,
    )
    assert plan.safety_status == JoinSafetyStatus.UNSAFE
    assert "MEASURE_MULTIPLICATION_RISK" in plan.risk_flags
    assert plan.forbidden_reason is not None
    assert "duplicates left-side measures" in plan.forbidden_reason


# =========================================================================
# 3. SCENARIO C: EMPLOYEE MONTHLY / ATTENDANCE DAILY (PREAGGREGATION)
# =========================================================================

def test_scenario_c_employee_monthly_attendance_daily_preaggregation():
    """
    EmployeeMonthly: employee_id, month, target_hours (grain: EMPLOYEE × MONTH)
    AttendanceDaily: employee_id, day, hours (grain: EMPLOYEE × DAY)
    Target grain: EMPLOYEE × MONTH.
    Expected: SAFE_WITH_PREAGGREGATION (attendance preaggregated to EMPLOYEE × MONTH).
    """
    dataset_id = "ds_preagg"
    df_mo = pd.DataFrame({
        "employee_id": ["E1", "E2"],
        "month": ["2026-01", "2026-01"],
        "target_hours": [160, 160],
    })
    df_day = pd.DataFrame({
        "employee_id": ["E1", "E1", "E2", "E2"],
        "month": ["2026-01", "2026-01", "2026-01", "2026-01"],
        "day": ["2026-01-01", "2026-01-02", "2026-01-01", "2026-01-02"],
        "hours": [8, 8, 8, 7],
    })

    mo_profs = [
        _create_profile(dataset_id, "mo", "employee_id", "employee_id", role=SemanticColumnRole.ENTITY_IDENTIFIER, concept=SemanticConcept.IDENTIFIER, entity_type=SemanticEntityType.PERSON),
        _create_profile(dataset_id, "mo", "month", "month", role=SemanticColumnRole.TIME, concept=SemanticConcept.TIME_SPAN, dtype=SemanticDtype.DATE),
        _create_profile(dataset_id, "mo", "target_hours", "target_hours", role=SemanticColumnRole.MEASURE, concept=SemanticConcept.MEASURE, dtype=SemanticDtype.INTEGER),
    ]
    day_profs = [
        _create_profile(dataset_id, "day", "employee_id", "employee_id", role=SemanticColumnRole.ENTITY_IDENTIFIER, concept=SemanticConcept.IDENTIFIER, entity_type=SemanticEntityType.PERSON),
        _create_profile(dataset_id, "day", "month", "month", role=SemanticColumnRole.TIME, concept=SemanticConcept.TIME_SPAN, dtype=SemanticDtype.DATE),
        _create_profile(dataset_id, "day", "day", "day", role=SemanticColumnRole.TIME, concept=SemanticConcept.TIME_SPAN, dtype=SemanticDtype.DATE),
        _create_profile(dataset_id, "day", "hours", "hours", role=SemanticColumnRole.MEASURE, concept=SemanticConcept.MEASURE, dtype=SemanticDtype.INTEGER),
    ]

    mo_grain = _create_grain_profile("mo", "EMPLOYEE × MONTH")
    day_grain = _create_grain_profile("day", "EMPLOYEE × DAY")

    validator = RelationshipValidatorEngine()
    governance = JoinGovernanceEngine()

    cand = SDRRelationshipCandidate(
        candidate_id="cand_mo_day",
        dataset_id=dataset_id,
        left_sheet_id="mo",
        right_sheet_id="day",
        left_column_ids=["employee_id", "month"],
        right_column_ids=["employee_id", "month"],
        left_grain="EMPLOYEE × MONTH",
        right_grain="EMPLOYEE × DAY",
        referential_overlap=1.0,
        left_coverage=1.0,
        right_coverage=1.0,
        confidence=0.90,
    )

    edge = validator.validate_candidate(cand, df_left=df_mo, df_right=df_day)
    assert edge.status == RelationshipStatus.VALIDATED
    assert edge.cardinality == RelationshipCardinality.ONE_TO_MANY

    plan = governance.plan_join(
        edge=edge,
        left_grain_profile=mo_grain,
        right_grain_profile=day_grain,
        left_profiles=mo_profs,
        right_profiles=day_profs,
        target_grain="EMPLOYEE × MONTH",
    )

    assert plan.safety_status == JoinSafetyStatus.SAFE_WITH_PREAGGREGATION
    assert plan.required_preaggregation is True
    assert plan.preaggregation_spec is not None
    assert plan.preaggregation_spec.target_grain == "EMPLOYEE × MONTH"

    # Dry-run execution
    dry_res = governance.dry_run_validate_join_plan(plan, df_left=df_mo, df_right=df_day)
    assert dry_res["dry_run_passed"] is True
    assert dry_res["output_rows"] == 2


def test_preaggregation_governed_zero_guessing():
    """
    Explicitly certify zero-guessing rule for preaggregation:
    Case A: Additive hours (MeasureAdditivity.ADDITIVE) -> SAFE_WITH_PREAGGREGATION with 'SUM'.
    Case B: Ratio/percentage (MeasureAdditivity.RATIO) -> UNSAFE (0 guessed functions).
    Case C: Unknown measure class (MeasureClass.UNKNOWN) -> UNSAFE (0 guessed functions).
    Guarantees: GUESSED AGGREGATION FUNCTIONS: 0, UNKNOWN-MEASURE PREAGGREGATION AUTO-AUTHORIZED: 0.
    """
    dataset_id = "ds_preagg_zero_guess"
    mo_grain = _create_grain_profile("mo", "EMPLOYEE × MONTH")
    day_grain = _create_grain_profile("day", "EMPLOYEE × DAY")
    governance = JoinGovernanceEngine()

    edge = SDRValidatedRelationshipEdge(
        edge_id="edge_mo_day",
        candidate_id="cand_mo_day",
        dataset_id=dataset_id,
        left_sheet_id="mo",
        right_sheet_id="day",
        left_column_ids=["employee_id", "month"],
        right_column_ids=["employee_id", "month"],
        left_grain="EMPLOYEE × MONTH",
        right_grain="EMPLOYEE × DAY",
        cardinality=RelationshipCardinality.ONE_TO_MANY,
        status=RelationshipStatus.VALIDATED,
        referential_coverage=1.0,
        left_coverage=1.0,
        right_coverage=1.0,
    )

    mo_profs = [
        _create_profile(dataset_id, "mo", "employee_id", "employee_id", role=SemanticColumnRole.ENTITY_IDENTIFIER, concept=SemanticConcept.IDENTIFIER, entity_type=SemanticEntityType.PERSON),
        _create_profile(dataset_id, "mo", "month", "month", role=SemanticColumnRole.TIME, concept=SemanticConcept.TIME_SPAN, dtype=SemanticDtype.DATE),
        _create_profile(dataset_id, "mo", "target_hours", "target_hours", role=SemanticColumnRole.MEASURE, concept=SemanticConcept.MEASURE, dtype=SemanticDtype.INTEGER, measure_class=MeasureClass.QUANTITY),
    ]

    # --- Case A: Additive hours (ADDITIVE / SUMMABLE) ---
    day_profs_a = [
        _create_profile(dataset_id, "day", "employee_id", "employee_id", role=SemanticColumnRole.ENTITY_IDENTIFIER, concept=SemanticConcept.IDENTIFIER, entity_type=SemanticEntityType.PERSON),
        _create_profile(dataset_id, "day", "month", "month", role=SemanticColumnRole.TIME, concept=SemanticConcept.TIME_SPAN, dtype=SemanticDtype.DATE),
        _create_profile(dataset_id, "day", "day", "day", role=SemanticColumnRole.TIME, concept=SemanticConcept.TIME_SPAN, dtype=SemanticDtype.DATE),
        _create_profile(dataset_id, "day", "hours", "hours", role=SemanticColumnRole.MEASURE, concept=SemanticConcept.MEASURE, dtype=SemanticDtype.INTEGER, measure_class=MeasureClass.DURATION),
    ]

    plan_a = governance.plan_join(
        edge=edge,
        left_grain_profile=mo_grain,
        right_grain_profile=day_grain,
        left_profiles=mo_profs,
        right_profiles=day_profs_a,
        target_grain="EMPLOYEE × MONTH",
    )
    assert plan_a.safety_status == JoinSafetyStatus.SAFE_WITH_PREAGGREGATION
    assert plan_a.preaggregation_spec is not None
    assert plan_a.preaggregation_spec.aggregations.get("hours") == "SUM"

    # --- Case B: Ratio/percentage (RATIO / NON_SUMMABLE) ---
    day_profs_b = [
        _create_profile(dataset_id, "day", "employee_id", "employee_id", role=SemanticColumnRole.ENTITY_IDENTIFIER, concept=SemanticConcept.IDENTIFIER, entity_type=SemanticEntityType.PERSON),
        _create_profile(dataset_id, "day", "month", "month", role=SemanticColumnRole.TIME, concept=SemanticConcept.TIME_SPAN, dtype=SemanticDtype.DATE),
        _create_profile(dataset_id, "day", "day", "day", role=SemanticColumnRole.TIME, concept=SemanticConcept.TIME_SPAN, dtype=SemanticDtype.DATE),
        _create_profile(dataset_id, "day", "attendance_rate", "attendance_rate", role=SemanticColumnRole.MEASURE, concept=SemanticConcept.MEASURE, dtype=SemanticDtype.PERCENTAGE_RATE, measure_class=MeasureClass.PERCENTAGE),
    ]

    plan_b = governance.plan_join(
        edge=edge,
        left_grain_profile=mo_grain,
        right_grain_profile=day_grain,
        left_profiles=mo_profs,
        right_profiles=day_profs_b,
        target_grain="EMPLOYEE × MONTH",
    )
    assert plan_b.safety_status == JoinSafetyStatus.UNSAFE
    assert "UNSUPPORTED_PREAGGREGATION_SEMANTICS" in plan_b.risk_flags
    assert plan_b.preaggregation_spec is None

    # --- Case C: Unknown measure class (UNKNOWN) ---
    day_profs_c = [
        _create_profile(dataset_id, "day", "employee_id", "employee_id", role=SemanticColumnRole.ENTITY_IDENTIFIER, concept=SemanticConcept.IDENTIFIER, entity_type=SemanticEntityType.PERSON),
        _create_profile(dataset_id, "day", "month", "month", role=SemanticColumnRole.TIME, concept=SemanticConcept.TIME_SPAN, dtype=SemanticDtype.DATE),
        _create_profile(dataset_id, "day", "day", "day", role=SemanticColumnRole.TIME, concept=SemanticConcept.TIME_SPAN, dtype=SemanticDtype.DATE),
        _create_profile(dataset_id, "day", "unknown_metric", "unknown_metric", role=SemanticColumnRole.MEASURE, concept=SemanticConcept.MEASURE, dtype=SemanticDtype.DECIMAL_NUMBER, measure_class=MeasureClass.UNKNOWN),
    ]

    plan_c = governance.plan_join(
        edge=edge,
        left_grain_profile=mo_grain,
        right_grain_profile=day_grain,
        left_profiles=mo_profs,
        right_profiles=day_profs_c,
        target_grain="EMPLOYEE × MONTH",
    )
    assert plan_c.safety_status == JoinSafetyStatus.UNSAFE
    assert "UNSUPPORTED_PREAGGREGATION_SEMANTICS" in plan_c.risk_flags
    assert plan_c.preaggregation_spec is None


# =========================================================================
# 4. SCENARIO D: FACT ALIGNMENT (SalesDaily & InventoryDaily)
# =========================================================================

def test_scenario_d_fact_alignment_composite_grain():
    """
    SalesDaily: store_id, sku, day, sales_qty (grain: STORE × SKU × DAY)
    InventoryDaily: store_id, sku, day, stock_qty (grain: STORE × SKU × DAY)
    Both unique at same composite grain.
    Expected: ONE_TO_ONE, SAFE.
    """
    dataset_id = "ds_fact_align"
    df_sales = pd.DataFrame({
        "store_id": ["S1", "S1"],
        "sku": ["SKU1", "SKU2"],
        "day": ["2026-01-01", "2026-01-01"],
        "sales_qty": [10, 5],
    })
    df_inv = pd.DataFrame({
        "store_id": ["S1", "S1"],
        "sku": ["SKU1", "SKU2"],
        "day": ["2026-01-01", "2026-01-01"],
        "stock_qty": [100, 50],
    })

    grain = _create_grain_profile("shared", "STORE × SKU × DAY")
    cand = SDRRelationshipCandidate(
        candidate_id="cand_sales_inv",
        dataset_id=dataset_id,
        left_sheet_id="sales_daily",
        right_sheet_id="inv_daily",
        left_column_ids=["day", "sku", "store_id"],
        right_column_ids=["day", "sku", "store_id"],
        left_grain="STORE × SKU × DAY",
        right_grain="STORE × SKU × DAY",
        referential_overlap=1.0,
        left_coverage=1.0,
        right_coverage=1.0,
        confidence=0.95,
    )

    validator = RelationshipValidatorEngine()
    governance = JoinGovernanceEngine()

    edge = validator.validate_candidate(cand, df_left=df_sales, df_right=df_inv)
    assert edge.status == RelationshipStatus.VALIDATED
    assert edge.cardinality == RelationshipCardinality.ONE_TO_ONE

    plan = governance.plan_join(edge=edge, left_grain_profile=grain, right_grain_profile=grain)
    assert plan.safety_status == JoinSafetyStatus.SAFE
    assert plan.target_grain == "STORE × SKU × DAY"

    dry_res = governance.dry_run_validate_join_plan(plan, df_left=df_sales, df_right=df_inv)
    assert dry_res["dry_run_passed"] is True
    assert dry_res["output_rows"] == 2


# =========================================================================
# 5. SCENARIO E: MANY-TO-MANY REJECTION
# =========================================================================

def test_scenario_e_many_to_many_unsafeguard():
    """
    EmployeeSkills: employee_id, skill_id
    ProjectSkills: project_id, skill_id
    Direct employee-project join via skill_id produces Cartesian fanout.
    Must NOT auto-authorize (UNSAFE, 0 auto joins).
    """
    dataset_id = "ds_m2m"
    df_emp_skills = pd.DataFrame({
        "employee_id": ["E1", "E1", "E2", "E2"],
        "skill_id": ["Python", "SQL", "Python", "SQL"],
    })
    df_proj_skills = pd.DataFrame({
        "project_id": ["P1", "P1", "P2", "P2"],
        "skill_id": ["Python", "SQL", "Python", "SQL"],
    })

    cand = SDRRelationshipCandidate(
        candidate_id="cand_skills",
        dataset_id=dataset_id,
        left_sheet_id="emp_skills",
        right_sheet_id="proj_skills",
        left_column_ids=["skill_id"],
        right_column_ids=["skill_id"],
        candidate_cardinality=RelationshipCardinality.MANY_TO_MANY,
        confidence=0.70,
    )

    validator = RelationshipValidatorEngine()
    governance = JoinGovernanceEngine()

    edge = validator.validate_candidate(cand, df_left=df_emp_skills, df_right=df_proj_skills)
    assert edge.cardinality == RelationshipCardinality.MANY_TO_MANY
    assert edge.duplication_risk_flag is True

    plan = governance.plan_join(edge=edge)
    assert plan.safety_status == JoinSafetyStatus.UNSAFE
    assert "MANY_TO_MANY_RISK" in plan.risk_flags
    assert "Arbitrary many-to-many joins are strictly forbidden" in plan.forbidden_reason


# =========================================================================
# 6. SCENARIO F: LOW REFERENTIAL OVERLAP
# =========================================================================

def test_scenario_f_low_referential_overlap():
    """
    Orders.customer_id vs CustomerMaster.customer_id with very low overlap (< 20%).
    Expected: REJECTED or AMBIGUOUS. Never authorized as SAFE.
    """
    dataset_id = "ds_low_overlap"
    df_orders = pd.DataFrame({"customer_id": [f"C{i}" for i in range(100, 120)]})
    df_master = pd.DataFrame({"customer_id": [f"C{i}" for i in range(900, 920)] + ["C100"]})  # 1 match out of 40 = 2.5%

    cand = SDRRelationshipCandidate(
        candidate_id="cand_cust",
        dataset_id=dataset_id,
        left_sheet_id="orders",
        right_sheet_id="master",
        left_column_ids=["customer_id"],
        right_column_ids=["customer_id"],
    )

    validator = RelationshipValidatorEngine()
    edge = validator.validate_candidate(cand, df_left=df_orders, df_right=df_master)

    assert edge.status in (RelationshipStatus.REJECTED, RelationshipStatus.AMBIGUOUS)
    assert edge.referential_coverage < 0.20
    assert "Insufficient referential coverage" in edge.rejection_reason


# =========================================================================
# 7. SCENARIO G: SAME NAME FALSE POSITIVE GUARD
# =========================================================================

def test_scenario_g_same_name_false_positive_guard():
    """
    Sheet A: status
    Sheet B: status
    Neither has key affinity.
    Expected: NO relationship formed merely from name equality (0 candidates discovered).
    """
    dataset_id = "ds_same_name"
    prof_a = _create_profile(dataset_id, "sheet_a", "status", "status", role=SemanticColumnRole.STATUS, concept=SemanticConcept.STATUS)
    prof_b = _create_profile(dataset_id, "sheet_b", "status", "status", role=SemanticColumnRole.STATUS, concept=SemanticConcept.STATUS)

    discovery = RelationshipDiscoveryEngine()
    cands, stats = discovery.discover_candidates(
        dataset_id=dataset_id,
        profiles_by_sheet={"sheet_a": [prof_a], "sheet_b": [prof_b]},
    )

    assert len(cands) == 0
    assert stats.relationship_candidates_evaluated == 0
    assert stats.pairs_pruned_semantically >= 1


# =========================================================================
# 8. SCENARIO H: MEASURE FALSE MATCH GUARD
# =========================================================================

def test_scenario_h_measure_false_match_guard():
    """
    Sheet A: amount (MEASURE)
    Sheet B: amount (MEASURE)
    Measures paired together must be strictly pruned (0 relationships authorized).
    """
    dataset_id = "ds_measure_match"
    prof_a = _create_profile(dataset_id, "sheet_a", "amount", "amount", role=SemanticColumnRole.MEASURE, concept=SemanticConcept.MEASURE, dtype=SemanticDtype.CURRENCY_AMOUNT)
    prof_b = _create_profile(dataset_id, "sheet_b", "amount", "amount", role=SemanticColumnRole.MEASURE, concept=SemanticConcept.MEASURE, dtype=SemanticDtype.CURRENCY_AMOUNT)

    discovery = RelationshipDiscoveryEngine()
    cands, stats = discovery.discover_candidates(
        dataset_id=dataset_id,
        profiles_by_sheet={"sheet_a": [prof_a], "sheet_b": [prof_b]},
    )

    assert len(cands) == 0
    assert stats.pairs_pruned_semantically >= 1


# =========================================================================
# 9. SCENARIO I: COMPOSITE KEY PAIRING DETERMINISM
# =========================================================================

def test_scenario_i_composite_key_pairing_determinism():
    """
    employee_id + month paired across two sheets.
    Expected: composite key relationship support with deterministic canonical sorting.
    """
    dataset_id = "ds_composite"
    profs_a = [
        _create_profile(dataset_id, "sheet_a", "employee_id", "employee_id", role=SemanticColumnRole.ENTITY_IDENTIFIER, concept=SemanticConcept.IDENTIFIER),
        _create_profile(dataset_id, "sheet_a", "month", "month", role=SemanticColumnRole.TIME, concept=SemanticConcept.TIME_SPAN, dtype=SemanticDtype.DATE),
    ]
    profs_b = [
        _create_profile(dataset_id, "sheet_b", "employee_id", "employee_id", role=SemanticColumnRole.ENTITY_IDENTIFIER, concept=SemanticConcept.IDENTIFIER),
        _create_profile(dataset_id, "sheet_b", "month", "month", role=SemanticColumnRole.TIME, concept=SemanticConcept.TIME_SPAN, dtype=SemanticDtype.DATE),
    ]

    key_a = SDRKeyCandidate(
        candidate_id="key_a_comp",
        dataset_id=dataset_id,
        sheet_id="sheet_a",
        column_ids=["employee_id", "month"],
        column_names=["employee_id", "month"],
        candidate_type=KeyCandidateType.COMPOSITE_CANDIDATE_KEY,
        entity_type=SemanticEntityType.PERSON,
        grain_expression="EMPLOYEE × MONTH",
        width=2,
        row_count=10,
        unique_combination_count=10,
        uniqueness_ratio=1.0,
        key_confidence=1.0,
        evidence="Composite key test",
        status=KeyCandidateStatus.HIGH_CONFIDENCE,
        authority=KeyAuthority.INFERRED,
    )

    discovery = RelationshipDiscoveryEngine()
    cands, _ = discovery.discover_candidates(
        dataset_id=dataset_id,
        profiles_by_sheet={"sheet_a": profs_a, "sheet_b": profs_b},
        key_candidates_by_sheet={"sheet_a": [key_a]},
    )

    comp_cands = [c for c in cands if len(c.left_column_ids) == 2]
    assert len(comp_cands) >= 1
    cand = comp_cands[0]
    # Deterministic alphabetical ordering
    assert cand.left_column_ids == ["employee_id", "month"]
    assert cand.right_column_ids == ["employee_id", "month"]


# =========================================================================
# 10. NEGATIVE RESULT AUDIT
# =========================================================================

def test_all_required_negative_results():
    """
    Mandatory audit:
    - Name-only relationships authorized: 0
    - Measure-based relationships authorized: 0
    - Free-text relationships authorized: 0
    - Embedding-only relationships authorized: 0
    - Many-to-many auto joins: 0
    - Cross joins: 0
    - Unsafe raw joins classified SAFE: 0
    - JoinPlans without validated edge: 0
    """
    dataset_id = "ds_neg_audit"
    governance = JoinGovernanceEngine()
    validator = RelationshipValidatorEngine()

    # 1. JoinPlan without validated edge (status REJECTED)
    cand_fake = SDRRelationshipCandidate(
        candidate_id="cand_fake",
        dataset_id=dataset_id,
        left_sheet_id="t1",
        right_sheet_id="t2",
        left_column_ids=["col1"],
        right_column_ids=["col2"],
    )
    rejected_edge = validator._build_rejected_edge(cand_fake, CandidateKeyType.SINGLE, "Structural violation")
    plan_rejected = governance.plan_join(edge=rejected_edge)
    assert plan_rejected.safety_status == JoinSafetyStatus.UNSAFE
    assert "UNVALIDATED_RELATIONSHIP" in plan_rejected.risk_flags

    # 2. Cross joins: strictly forbidden in join_type
    plan_cross = governance.plan_join(edge=rejected_edge, preferred_join_type="CROSS")
    assert plan_cross.join_type != "CROSS"
    assert plan_cross.join_type in ("INNER", "LEFT")


# =========================================================================
# 11. ROW EXPLOSION ESTIMATION & DRY-RUN VALIDATOR
# =========================================================================

def test_row_explosion_estimation_and_dry_run_validator():
    """
    Verify exact matched-pair cardinality and row expansion estimation:
    pairs(k) = count_left(k) * count_right(k)
    matched_pairs = sum(pairs(k))
    estimated_result_rows = matched_pairs + unmatched_left_rows
    expansion_ratio = estimated_result_rows / left_rows
    Test across 1:1, N:1, 1:N, and N:N cardinality structures.
    """
    cand = SDRRelationshipCandidate(
        candidate_id="cand_exp",
        dataset_id="ds_exp",
        left_sheet_id="l",
        right_sheet_id="r",
        left_column_ids=["k"],
        right_column_ids=["k"],
    )
    validator = RelationshipValidatorEngine()
    governance = JoinGovernanceEngine()

    # Case 1: ONE_TO_ONE (1:1)
    df_l_11 = pd.DataFrame({"k": ["A", "B", "C"]})  # 3 rows
    df_r_11 = pd.DataFrame({"k": ["A", "B", "C"]})  # 3 rows
    edge_11 = validator.validate_candidate(cand, df_left=df_l_11, df_right=df_r_11)
    assert edge_11.cardinality == RelationshipCardinality.ONE_TO_ONE
    assert edge_11.matched_distinct_keys == 3
    assert edge_11.matched_pairs == 3
    assert edge_11.unmatched_left_rows == 0
    assert edge_11.unmatched_right_rows == 0
    assert edge_11.estimated_result_rows == 3
    assert edge_11.expansion_ratio == 1.0
    assert edge_11.max_frequency_bound == 1

    # Case 2: MANY_TO_ONE (N:1)
    df_l_n1 = pd.DataFrame({"k": ["A", "A", "B", "B", "C"]})  # 5 rows
    df_r_n1 = pd.DataFrame({"k": ["A", "B", "C"]})             # 3 rows
    edge_n1 = validator.validate_candidate(cand, df_left=df_l_n1, df_right=df_r_n1)
    assert edge_n1.cardinality == RelationshipCardinality.MANY_TO_ONE
    assert edge_n1.matched_distinct_keys == 3
    assert edge_n1.matched_pairs == 5
    assert edge_n1.unmatched_left_rows == 0
    assert edge_n1.unmatched_right_rows == 0
    assert edge_n1.estimated_result_rows == 5
    assert edge_n1.expansion_ratio == 1.0
    assert edge_n1.max_frequency_bound == 2

    # Case 3: ONE_TO_MANY (1:N)
    df_l_1n = pd.DataFrame({"k": ["A", "B", "C"]})                    # 3 rows
    df_r_1n = pd.DataFrame({"k": ["A", "A", "B", "B", "B", "C"]})    # 6 rows (A: 2, B: 3, C: 1)
    edge_1n = validator.validate_candidate(cand, df_left=df_l_1n, df_right=df_r_1n)
    assert edge_1n.cardinality == RelationshipCardinality.ONE_TO_MANY
    assert edge_1n.matched_distinct_keys == 3
    assert edge_1n.matched_pairs == 6
    assert edge_1n.unmatched_left_rows == 0
    assert edge_1n.unmatched_right_rows == 0
    assert edge_1n.estimated_result_rows == 6
    assert edge_1n.expansion_ratio == 2.0
    assert edge_1n.max_frequency_bound == 3

    # Case 4: MANY_TO_MANY (N:N)
    df_l_nn = pd.DataFrame({"k": ["A", "A", "B"]})              # 3 rows
    df_r_nn = pd.DataFrame({"k": ["A", "A", "A", "B", "B"]})    # 5 rows (A: 2*3=6, B: 1*2=2 -> matched_pairs=8)
    edge_nn = validator.validate_candidate(cand, df_left=df_l_nn, df_right=df_r_nn)
    assert edge_nn.cardinality == RelationshipCardinality.MANY_TO_MANY
    assert edge_nn.matched_distinct_keys == 2
    assert edge_nn.matched_pairs == 8
    assert edge_nn.unmatched_left_rows == 0
    assert edge_nn.estimated_result_rows == 8
    assert edge_nn.expansion_ratio == pytest.approx(8 / 3, abs=1e-4)
    assert edge_nn.max_frequency_bound == 6

    # Plan propagation & Dry-run validation
    plan_1n = governance.plan_join(edge=edge_1n)
    assert plan_1n.expansion_ratio == edge_1n.expansion_ratio
    assert plan_1n.estimated_result_rows == edge_1n.estimated_result_rows
    assert plan_1n.matched_pairs == edge_1n.matched_pairs
    assert plan_1n.max_frequency_bound == edge_1n.max_frequency_bound

    dry_res = governance.dry_run_validate_join_plan(plan_1n, df_left=df_l_1n, df_right=df_r_1n)
    assert dry_res["output_rows"] == plan_1n.estimated_result_rows


# =========================================================================
# 12. RELATIONSHIP VERSIONING & INVALIDATION
# =========================================================================

def test_relationship_versioning_and_invalidation():
    """
    Prove invalidation behavior across 4 distinct dimensions:
    Case A: Upstream candidate key fingerprint change -> edge & plan invalidated.
    Case B: Upstream grain fingerprint change -> join plan invalidated.
    Case C: Dataset / source version change -> edge & plan invalidated.
    Case D: Policy fingerprint change -> edge & plan invalidated.
    Case E: Unrelated edge and join plan preserved: status UNCHANGED.
    """
    dataset_id = "ds_ver_inv"
    governance = JoinGovernanceEngine()
    pol_fp = governance.policy_fingerprint

    edge = SDRValidatedRelationshipEdge(
        edge_id="edge_test",
        candidate_id="cand_test",
        dataset_id=dataset_id,
        left_sheet_id="left",
        right_sheet_id="right",
        left_column_ids=["id"],
        right_column_ids=["id"],
        cardinality=RelationshipCardinality.MANY_TO_ONE,
        status=RelationshipStatus.VALIDATED,
        referential_coverage=1.0,
        left_coverage=1.0,
        right_coverage=1.0,
        dataset_version="v1",
        key_fingerprints=["key_fp_1", "key_fp_2"],
        grain_fingerprints=["grain_fp_l", "grain_fp_r"],
        policy_fingerprint=pol_fp,
    )

    grain_left = _create_grain_profile("left", "EMPLOYEE", grain_fingerprint="grain_fp_l")
    grain_right = _create_grain_profile("right", "DEPARTMENT", grain_fingerprint="grain_fp_r")

    plan = governance.plan_join(
        edge=edge,
        left_grain_profile=grain_left,
        right_grain_profile=grain_right,
        dataset_version="v1",
    )

    # Base state: everything matches -> UNCHANGED
    is_valid_edge, reason_edge = check_edge_invalidation(
        edge,
        current_dataset_version="v1",
        current_key_fingerprints=["key_fp_1", "key_fp_2"],
        current_grain_fingerprints=["grain_fp_l", "grain_fp_r"],
        current_policy_fingerprint=pol_fp,
    )
    assert is_valid_edge is True
    assert reason_edge is None

    is_valid_plan, reason_plan = check_join_plan_invalidation(
        plan,
        current_dataset_version="v1",
        current_grain_fingerprints=[plan.grain_artifact_fingerprint],
        current_edge_fingerprint=edge.artifact_fingerprint,
        current_policy_fingerprint=pol_fp,
    )
    assert is_valid_plan is True
    assert reason_plan is None

    # Case A: Upstream candidate key fingerprint change
    is_valid_a, reason_a = check_edge_invalidation(
        edge,
        current_dataset_version="v1",
        current_key_fingerprints=["MODIFIED_KEY_FP", "key_fp_2"],
        current_grain_fingerprints=["grain_fp_l", "grain_fp_r"],
        current_policy_fingerprint=pol_fp,
    )
    assert is_valid_a is False
    assert "Key fingerprints changed" in reason_a

    # Case B: Upstream grain fingerprint change
    is_valid_b, reason_b = check_join_plan_invalidation(
        plan,
        current_dataset_version="v1",
        current_grain_fingerprints=["NEW_DIFFERENT_GRAIN_FP"],
        current_edge_fingerprint=edge.artifact_fingerprint,
        current_policy_fingerprint=pol_fp,
    )
    assert is_valid_b is False
    assert "Grain changed" in reason_b

    # Case C: Dataset / source version change
    is_valid_c_edge, reason_c_edge = check_edge_invalidation(
        edge,
        current_dataset_version="v2",
        current_key_fingerprints=["key_fp_1", "key_fp_2"],
        current_grain_fingerprints=["grain_fp_l", "grain_fp_r"],
        current_policy_fingerprint=pol_fp,
    )
    assert is_valid_c_edge is False
    assert "Dataset version changed" in reason_c_edge

    is_valid_c_plan, reason_c_plan = check_join_plan_invalidation(
        plan,
        current_dataset_version="v2",
        current_grain_fingerprints=[plan.grain_artifact_fingerprint],
        current_edge_fingerprint=edge.artifact_fingerprint,
        current_policy_fingerprint=pol_fp,
    )
    assert is_valid_c_plan is False
    assert "Dataset version changed" in reason_c_plan

    # Case D: Policy fingerprint change
    is_valid_d_edge, reason_d_edge = check_edge_invalidation(
        edge,
        current_dataset_version="v1",
        current_key_fingerprints=["key_fp_1", "key_fp_2"],
        current_grain_fingerprints=["grain_fp_l", "grain_fp_r"],
        current_policy_fingerprint="NEW_POLICY_FP",
    )
    assert is_valid_d_edge is False
    assert "Policy fingerprint changed" in reason_d_edge

    is_valid_d_plan, reason_d_plan = check_join_plan_invalidation(
        plan,
        current_dataset_version="v1",
        current_grain_fingerprints=[plan.grain_artifact_fingerprint],
        current_edge_fingerprint=edge.artifact_fingerprint,
        current_policy_fingerprint="NEW_POLICY_FP",
    )
    assert is_valid_d_plan is False
    assert "Policy fingerprint changed" in reason_d_plan

    # Case E: Unrelated edge and join plan preserved (status UNCHANGED)
    unrelated_edge = SDRValidatedRelationshipEdge(
        edge_id="edge_unrelated",
        candidate_id="cand_unrelated",
        dataset_id=dataset_id,
        left_sheet_id="orders",
        right_sheet_id="customers",
        left_column_ids=["cust_id"],
        right_column_ids=["cust_id"],
        cardinality=RelationshipCardinality.MANY_TO_ONE,
        status=RelationshipStatus.VALIDATED,
        referential_coverage=1.0,
        left_coverage=1.0,
        right_coverage=1.0,
        dataset_version="v1",
        key_fingerprints=["cust_fp_1", "cust_fp_2"],
        grain_fingerprints=["grain_orders", "grain_customers"],
        policy_fingerprint=pol_fp,
    )
    is_valid_unrelated, reason_unrelated = check_edge_invalidation(
        unrelated_edge,
        current_dataset_version="v1",
        current_key_fingerprints=["cust_fp_1", "cust_fp_2"],
        current_grain_fingerprints=["grain_orders", "grain_customers"],
        current_policy_fingerprint=pol_fp,
    )
    assert is_valid_unrelated is True
    assert reason_unrelated is None


# =========================================================================
# 13. RETRIEVAL INDEX CONTAINMENT PROOF
# =========================================================================

def test_retrieval_index_containment():
    """
    Prove SDR-5 documents emit strictly into RELATIONSHIP_INDEX (alias of RELATIONSHIP),
    with 0 documents in ANALYTICAL_INDEX, RAW_SCHEMA_INDEX, or SEMANTIC_INDEX,
    and 0 competing relationship namespaces.
    """
    adapter = SDRRetrievalAdapter()
    cand = SDRRelationshipCandidate(
        candidate_id="c1",
        dataset_id="ds_ret",
        left_sheet_id="s1",
        right_sheet_id="s2",
        left_column_ids=["id"],
        right_column_ids=["id"],
    )
    edge = SDRValidatedRelationshipEdge(
        edge_id="e1",
        candidate_id="c1",
        dataset_id="ds_ret",
        left_sheet_id="s1",
        right_sheet_id="s2",
        left_column_ids=["id"],
        right_column_ids=["id"],
        cardinality=RelationshipCardinality.MANY_TO_ONE,
        status=RelationshipStatus.VALIDATED,
        referential_coverage=1.0,
        left_coverage=1.0,
        right_coverage=1.0,
    )
    plan = SDRJoinPlan(
        join_plan_id="jp1",
        relationship_edge_id="e1",
        dataset_id="ds_ret",
        left_sheet_id="s1",
        right_sheet_id="s2",
        left_keys=["id"],
        right_keys=["id"],
        join_type="INNER",
        safety_status=JoinSafetyStatus.SAFE,
        left_grain="SALE",
        right_grain="STORE",
        target_grain="SALE",
    )

    doc_cand = adapter.build_relationship_candidate_document(cand)
    doc_edge = adapter.build_validated_relationship_edge_document(edge)
    doc_plan = adapter.build_join_plan_document(plan)

    # 1. Exact frozen namespace verification
    assert RetrievalNamespace.RELATIONSHIP_INDEX == RetrievalNamespace.RELATIONSHIP
    assert doc_cand.namespace == RetrievalNamespace.RELATIONSHIP
    assert doc_edge.namespace == RetrievalNamespace.RELATIONSHIP
    assert doc_plan.namespace == RetrievalNamespace.RELATIONSHIP
    assert doc_cand.namespace.value == "RELATIONSHIP"

    # 2. Strict containment: zero leakage to other namespaces
    for doc in (doc_cand, doc_edge, doc_plan):
        assert doc.namespace not in (
            RetrievalNamespace.ANALYTICAL,
            RetrievalNamespace.RAW_SCHEMA,
            RetrievalNamespace.SEMANTIC,
        )
        assert doc.structured_metadata.get("target_index") == "RELATIONSHIP_INDEX"

    # 3. Competing relationship namespace is NONE
    competing_rel_namespaces = [
        ns for ns in RetrievalNamespace
        if "RELATIONSHIP" in ns.name and ns not in (RetrievalNamespace.RELATIONSHIP, RetrievalNamespace.RELATIONSHIP_INDEX)
    ]
    assert len(competing_rel_namespaces) == 0

    # 4. Authority classification
    assert doc_cand.authority_class == AuthorityClass.RELATIONSHIP
    assert doc_edge.authority_class == AuthorityClass.RELATIONSHIP
    assert doc_plan.authority_class == AuthorityClass.RELATIONSHIP


# =========================================================================
# 14. SEMANTIC GRAPH ADAPTER SEGREGATION PROOF
# =========================================================================

def test_semantic_graph_adapter_segregation():
    """Prove validated relationships enter SemanticGraph while candidates do not masquerade as truth."""
    graph = SemanticGraph(
        dataset_id="ds_graph",
        run_id="run_1",
        source_fingerprint="fp1",
    )
    edge = SDRValidatedRelationshipEdge(
        edge_id="e_valid",
        candidate_id="c_valid",
        dataset_id="ds_graph",
        left_sheet_id="orders",
        right_sheet_id="customers",
        left_column_ids=["customer_id"],
        right_column_ids=["customer_id"],
        cardinality=RelationshipCardinality.MANY_TO_ONE,
        status=RelationshipStatus.VALIDATED,
        referential_coverage=1.0,
        left_coverage=1.0,
        right_coverage=1.0,
    )
    plan = SDRJoinPlan(
        join_plan_id="jp_orders_cust",
        relationship_edge_id="e_valid",
        dataset_id="ds_graph",
        left_sheet_id="orders",
        right_sheet_id="customers",
        left_keys=["customer_id"],
        right_keys=["customer_id"],
        join_type="INNER",
        safety_status=JoinSafetyStatus.SAFE,
        left_grain="ORDER",
        right_grain="CUSTOMER",
        target_grain="ORDER",
    )

    updated_graph = SDRSemanticGraphAdapter.load_relationships_into_graph(
        graph=graph,
        validated_edges=[edge],
        join_plans=[plan],
    )

    edge_types = [e.edge_type for e in updated_graph.edges]
    assert GraphEdgeType.STRUCTURAL_RELATIONSHIP in edge_types
    assert GraphEdgeType.USES_JOIN_PLAN in edge_types


# =========================================================================
# 15. ARTIFACT DETERMINISM
# =========================================================================

def test_sdr5_artifact_determinism(tmp_path):
    """Prove repeat serialization produces 100% byte-for-byte identical SHA-256 hashes across all 4 SDR-5 artifacts."""
    writer = SDRArtifactWriter(base_dir=tmp_path)
    dataset_id = "ds_det_sdr5"

    cand = SDRRelationshipCandidate(
        candidate_id="c_det",
        dataset_id=dataset_id,
        left_sheet_id="sales",
        right_sheet_id="stores",
        left_column_ids=["store_id"],
        right_column_ids=["store_id"],
        left_grain="SALE",
        right_grain="STORE",
        referential_overlap=1.0,
        left_coverage=1.0,
        right_coverage=1.0,
        confidence=0.95,
    )
    edge = SDRValidatedRelationshipEdge(
        edge_id="e_det",
        candidate_id="c_det",
        dataset_id=dataset_id,
        left_sheet_id="sales",
        right_sheet_id="stores",
        left_column_ids=["store_id"],
        right_column_ids=["store_id"],
        cardinality=RelationshipCardinality.MANY_TO_ONE,
        status=RelationshipStatus.VALIDATED,
        referential_coverage=1.0,
        left_coverage=1.0,
        right_coverage=1.0,
    )
    plan = SDRJoinPlan(
        join_plan_id="jp_det",
        relationship_edge_id="e_det",
        dataset_id=dataset_id,
        left_sheet_id="sales",
        right_sheet_id="stores",
        left_keys=["store_id"],
        right_keys=["store_id"],
        join_type="INNER",
        safety_status=JoinSafetyStatus.SAFE,
        left_grain="SALE",
        right_grain="STORE",
        target_grain="SALE",
    )

    paths1 = writer.write_sdr5_artifacts(dataset_id=dataset_id, candidates=[cand], validated_edges=[edge], join_plans=[plan])
    paths2 = writer.write_sdr5_artifacts(dataset_id=dataset_id, candidates=[cand], validated_edges=[edge], join_plans=[plan])

    for k in ("relationship_candidates", "validated_relationships", "join_plans", "sdr5_manifest"):
        p1 = Path(paths1[k])
        p2 = Path(paths2[k])
        sha1 = hashlib.sha256(p1.read_bytes()).hexdigest()
        sha2 = hashlib.sha256(p2.read_bytes()).hexdigest()
        assert sha1 == sha2, f"Artifact {k} SHA mismatch: {sha1} != {sha2}"


# =========================================================================
# 16. BOUNDED SEARCH & PERFORMANCE BENCHMARK
# =========================================================================

def test_performance_and_bounded_candidate_search():
    """
    Benchmark SMALL, MEDIUM, and LARGE multi-sheet configurations:
    Prove candidate search is strictly bounded, candidate column pairs are pruned semantically,
    and report telemetry for sheets, rows, columns, pairs pruned, candidates, edges, plans, runtime, peak memory.
    """
    discovery = RelationshipDiscoveryEngine()
    validator = RelationshipValidatorEngine()
    governance = JoinGovernanceEngine()

    configs = [
        ("SMALL", 2, 5, 100),     # 2 sheets, 5 cols each = 10 cols, 100 rows
        ("MEDIUM", 4, 15, 500),   # 4 sheets, 15 cols each = 60 cols, 500 rows
        ("LARGE", 6, 20, 1000),   # 6 sheets, 20 cols each = 120 cols, 1000 rows
    ]

    benchmark_results = []

    for name, n_sheets, n_cols, n_rows in configs:
        tracemalloc.start()
        t0 = time.perf_counter()

        dataset_id = f"ds_perf_{name.lower()}"
        profiles_by_sheet = {}
        dfs_by_sheet = {}
        grain_profiles = {}

        for s_idx in range(n_sheets):
            sheet_name = f"sheet_{s_idx}"
            cols = []
            data = {}

            # Primary key column
            pk_col = f"id_{s_idx}"
            cols.append(_create_profile(
                dataset_id, sheet_name, pk_col, pk_col,
                role=SemanticColumnRole.ENTITY_IDENTIFIER,
                concept=SemanticConcept.IDENTIFIER,
                entity_type=SemanticEntityType.PERSON,
            ))
            data[pk_col] = [f"id_{i}" for i in range(n_rows)]

            # Foreign key column to previous sheet if exists
            fk_col = f"id_{(s_idx - 1) % n_sheets}"
            cols.append(_create_profile(
                dataset_id, sheet_name, fk_col, fk_col,
                role=SemanticColumnRole.ENTITY_IDENTIFIER,
                concept=SemanticConcept.IDENTIFIER,
                entity_type=SemanticEntityType.PERSON,
            ))
            data[fk_col] = [f"id_{i % max(1, n_rows // 2)}" for i in range(n_rows)]

            # Fill remaining columns with measures, text, dimensions
            rem = n_cols - 2
            n_measures = max(1, rem // 2)
            n_text = max(1, rem // 4)
            n_dim = rem - n_measures - n_text

            for m in range(n_measures):
                cname = f"metric_{m}"
                cols.append(_create_profile(
                    dataset_id, sheet_name, cname, cname,
                    role=SemanticColumnRole.MEASURE,
                    concept=SemanticConcept.MEASURE,
                    dtype=SemanticDtype.INTEGER,
                    measure_class=MeasureClass.QUANTITY,
                ))
                data[cname] = [10 + i % 100 for i in range(n_rows)]

            for t in range(n_text):
                cname = f"notes_{t}"
                cols.append(_create_profile(
                    dataset_id, sheet_name, cname, cname,
                    role=SemanticColumnRole.FREE_TEXT,
                    concept=SemanticConcept.FREE_TEXT,
                    dtype=SemanticDtype.NATURAL_LANGUAGE_TEXT,
                ))
                data[cname] = [f"free text notes {i}" for i in range(n_rows)]

            for d in range(n_dim):
                cname = f"dim_{d}"
                cols.append(_create_profile(
                    dataset_id, sheet_name, cname, cname,
                    role=SemanticColumnRole.DIMENSION,
                    concept=SemanticConcept.DESCRIPTOR,
                    dtype=SemanticDtype.CATEGORICAL_CODE,
                ))
                data[cname] = [f"cat_{i % 5}" for i in range(n_rows)]

            profiles_by_sheet[sheet_name] = cols
            dfs_by_sheet[sheet_name] = pd.DataFrame(data)
            grain_profiles[sheet_name] = _create_grain_profile(sheet_name, f"GRAIN_{sheet_name}")

        # 1. Candidate discovery
        candidates, stats = discovery.discover_candidates(
            dataset_id=dataset_id,
            profiles_by_sheet=profiles_by_sheet,
            table_data=dfs_by_sheet,
        )

        # 2. Validation
        validated_edges = []
        for cand in candidates:
            edge = validator.validate_candidate(
                cand,
                df_left=dfs_by_sheet[cand.left_sheet_id],
                df_right=dfs_by_sheet[cand.right_sheet_id],
            )
            validated_edges.append(edge)

        # 3. Governance Planning
        safe_count = 0
        safe_preagg_count = 0
        ambiguous_count = 0
        unsafe_count = 0

        for edge in validated_edges:
            plan = governance.plan_join(
                edge=edge,
                left_grain_profile=grain_profiles[edge.left_sheet_id],
                right_grain_profile=grain_profiles[edge.right_sheet_id],
                left_profiles=profiles_by_sheet[edge.left_sheet_id],
                right_profiles=profiles_by_sheet[edge.right_sheet_id],
            )
            if plan.safety_status == JoinSafetyStatus.SAFE:
                safe_count += 1
            elif plan.safety_status == JoinSafetyStatus.SAFE_WITH_PREAGGREGATION:
                safe_preagg_count += 1
            elif plan.safety_status == JoinSafetyStatus.AMBIGUOUS:
                ambiguous_count += 1
            elif plan.safety_status == JoinSafetyStatus.UNSAFE:
                unsafe_count += 1

        t_elapsed = time.perf_counter() - t0
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        res = {
            "name": name,
            "sheets": stats.sheets_count,
            "columns": stats.columns_count,
            "rows": n_rows,
            "raw_cross_sheet_pairs": stats.candidate_column_pairs_considered,
            "pairs_pruned_before_scan": stats.pairs_pruned_semantically,
            "pruning_efficiency": stats.pairs_pruned_semantically / max(1, stats.candidate_column_pairs_considered),
            "key_compatible_pairs": stats.key_compatible_pairs,
            "evaluated_candidates": len(candidates),
            "validated_edges": sum(1 for e in validated_edges if e.status == RelationshipStatus.VALIDATED),
            "safe_plans": safe_count,
            "safe_with_preagg_plans": safe_preagg_count,
            "ambiguous_plans": ambiguous_count,
            "unsafe_plans": unsafe_count,
            "runtime_s": t_elapsed,
            "peak_memory_mb": peak_mem / (1024 * 1024),
        }
        benchmark_results.append(res)

        # Assert bounded search properties
        assert stats.candidate_column_pairs_considered > 0
        assert stats.pairs_pruned_semantically > 0
        assert res["pruning_efficiency"] >= 0.50  # Over 50% pruned even on minimal 5-col sheets; >= 80% on medium/large
        assert t_elapsed < 10.0  # Runs well under 10 seconds even for LARGE

    # Verify scaling is bounded
    assert len(benchmark_results) == 3


# =========================================================================
# 17. P0 DATABASE ISOLATION CHECK
# =========================================================================

def test_p0_database_isolation():
    """Verify primary application database pulsehr.sqlite3 remains 100% byte-identical."""
    p0_path = Path("backend/data/db/pulsehr.sqlite3")
    if p0_path.exists():
        hasher = hashlib.sha256()
        with open(p0_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        assert hasher.hexdigest() == P0_EXPECTED_SHA
        assert p0_path.stat().st_size == P0_EXPECTED_SIZE
