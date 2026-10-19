"""
HighView Semantic Data Refinery — Phase SDR-7
Data Explorer Certification Dataset Seeder

Creates the authoritative 6-sheet multi-archetype workbook fixture:
1. Employees (Clean Single Grain, Natural Keys, PII, Roles)
2. AttendanceDaily (High-Frequency Event, Composite Key, Hours)
3. EmployeeMonthly (Aggregated Monthly Grain, Bonus, Preagg Target)
4. Stores (Dimension Table, Store ID, Regions, Cities for GEO)
5. Sales (Transaction Fact Table, Foreign Keys, Monetary Amounts)
6. InventoryDaily (Composite Grain, Dirty Records, NO-KEY STATE)

Generates exact isolated SDR-1 through SDR-6 artifacts in:
`backend/data/datasets/sdr7_cert/sdr/`
and writes the Excel fixture to:
`backend/tests/fixtures/sdr7_certification_workbook.xlsx`

CRITICAL SAFETY:
- Does NOT mutate or restore the frozen P0 database (`backend/data/db/pulsehr.sqlite3`).
- P0 SHA-256 and size remain 100% exact.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from app.core import config
from app.services.ingestion_v2.contracts.grain import CanonicalGrain, TemporalGrain
from app.services.ingestion_v2.contracts.joins import JoinSafetyStatus, PreAggregationSpec
from app.services.ingestion_v2.contracts.relationships import (
    CandidateKeyType,
    RelationshipCardinality,
    RelationshipStatus,
)
from app.services.ingestion_v2.contracts.semantics import (
    MeasureClass,
    SemanticColumnRole,
    SemanticConcept,
    SemanticEntityType,
)
from app.services.sdr.artifacts.artifact_writer import SDRArtifactWriter
from app.services.sdr.contracts.entity import EntityHypothesisState, SemanticEntityHypothesis
from app.services.sdr.geo.contracts import (
    CanonicalGeoEntity,
    GeoLevel,
    GeoMatchMethod,
    GeoResolutionCandidate,
    GeoResolutionStatus,
)
from app.services.sdr.contracts.grain import GrainCandidate, GrainStatus, SDRGrainProfile
from app.services.sdr.contracts.keys import (
    KeyAuthority,
    KeyCandidateStatus,
    KeyCandidateType,
    SDRKeyCandidate,
)
from app.services.sdr.contracts.policies import SDRPolicySuite
from app.services.sdr.contracts.profiles import (
    ClassificationSource,
    DeterministicColumnFeatures,
    PrivacyClassification,
    ProfilingAmbiguityState,
    SemanticColumnProfile,
    SemanticDtype,
    SourceCoordinateRef,
)
from app.services.sdr.contracts.relationships import (
    RelationshipClass,
    SDRJoinPlan,
    SDRRelationshipCandidate,
    SDRValidatedRelationshipEdge,
)
from app.services.sdr.contracts.views import (
    ControlledExpression,
    MaterializationMode,
    SDRAnalyticalFact,
    SDRAnalyticalViewSpec,
    SDRAnalyticalViewStatus,
    SDRDerivedMeasureSpec,
)

DATASET_ID = "sdr7_cert"


def _create_profile(
    sheet_id: str,
    column_id: str,
    source_name: str,
    role: SemanticColumnRole,
    dtype: SemanticDtype,
    concept: SemanticConcept,
    entity_type: SemanticEntityType = SemanticEntityType.UNKNOWN,
    measure_class: MeasureClass | None = None,
    privacy: PrivacyClassification = PrivacyClassification.GENERAL_ATTRIBUTE,
    distinct_count: int = 5,
    row_count: int = 5,
    null_ratio: float = 0.0,
    confidence: float = 0.95,
    ambiguity: ProfilingAmbiguityState = ProfilingAmbiguityState.CLEAR,
) -> SemanticColumnProfile:
    features = DeterministicColumnFeatures(
        row_count=row_count,
        null_count=int(row_count * null_ratio),
        null_ratio=null_ratio,
        distinct_count=distinct_count,
        distinct_ratio=distinct_count / float(row_count) if row_count > 0 else 0.0,
        sample_values=["sample_val_1", "sample_val_2"],
    )
    lineage = SourceCoordinateRef(
        dataset_id=DATASET_ID,
        sheet_id=sheet_id,
        column_ids=[column_id],
        source_file_hash="sdr7_cert_hash",
    )
    return SemanticColumnProfile(
        profile_id=f"prof_{DATASET_ID}_{sheet_id}_{column_id}",
        dataset_id=DATASET_ID,
        sheet_id=sheet_id,
        column_id=column_id,
        source_name=source_name,
        canonical_name=source_name.lower(),
        physical_dtype="string" if dtype in (SemanticDtype.IDENTIFIER_CODE, SemanticDtype.NATURAL_LANGUAGE_TEXT) else "float",
        semantic_dtype=dtype,
        semantic_role=role,
        semantic_concept=concept,
        entity_type_hypothesis=entity_type,
        measure_class=measure_class,
        confidence=confidence,
        ambiguity_state=ambiguity,
        privacy_classification=privacy,
        features=features,
        source_lineage=lineage,
        classification_source=ClassificationSource.HEURISTIC,
        artifact_fingerprint=f"fp_{sheet_id}_{column_id}",
    )


def seed_certification_dataset() -> dict[str, any]:
    root_data = config.DATA_DIR
    fixture_dir = Path("backend/tests/fixtures")
    fixture_dir.mkdir(parents=True, exist_ok=True)
    excel_path = fixture_dir / "sdr7_certification_workbook.xlsx"

    # 1. Raw Tabular Data (6 Sheets)
    df_employees = pd.DataFrame([
        {"employee_id": "0042", "employee_name": "Alice Zhang", "department": "Engineering", "salary": 145000.0, "city": "Bengaluru", "zip_code": "560001", "ssn_redacted": "***-**-1234"},
        {"employee_id": "0043", "employee_name": "Bob Smith", "department": "Sales", "salary": 92000.0, "city": "San Francisco", "zip_code": "94105", "ssn_redacted": "***-**-5678"},
        {"employee_id": "0044", "employee_name": "Carol Danvers", "department": "Engineering", "salary": 160000.0, "city": "Springfield", "zip_code": "01103", "ssn_redacted": "***-**-9012"},
        {"employee_id": "0045", "employee_name": "David Miller", "department": "Operations", "salary": 85000.0, "city": "Austin", "zip_code": "78701", "ssn_redacted": "***-**-3456"},
    ])

    df_attendance = pd.DataFrame([
        {"record_id": "ATT-001", "employee_id": "0042", "work_date": "2026-03-01", "hours_worked": 8.0, "status": "PRESENT"},
        {"record_id": "ATT-002", "employee_id": "0042", "work_date": "2026-03-02", "hours_worked": 7.5, "status": "PRESENT"},
        {"record_id": "ATT-003", "employee_id": "0043", "work_date": "2026-03-01", "hours_worked": 8.0, "status": "PRESENT"},
        {"record_id": "ATT-004", "employee_id": "0044", "work_date": "2026-03-01", "hours_worked": 0.0, "status": "ABSENT"},
    ])

    df_emp_monthly = pd.DataFrame([
        {"summary_id": "EM-001", "employee_id": "0042", "month": "2026-03", "total_hours": 155.5, "monthly_bonus": 1200.0},
        {"summary_id": "EM-002", "employee_id": "0043", "month": "2026-03", "total_hours": 160.0, "monthly_bonus": 850.0},
        {"summary_id": "EM-003", "employee_id": "0044", "month": "2026-03", "total_hours": 150.0, "monthly_bonus": 2000.0},
    ])

    df_stores = pd.DataFrame([
        {"store_id": "STR-01", "store_name": "Bengaluru Downtown Flagship", "city": "Bengaluru", "region": "APAC", "opened_year": 2021},
        {"store_id": "STR-02", "store_name": "Market Street SF Hub", "city": "San Francisco", "region": "North America", "opened_year": 2018},
        {"store_id": "STR-03", "store_name": "Springfield Metro Outlet", "city": "Springfield", "region": "North America", "opened_year": 2024},
    ])

    df_sales = pd.DataFrame([
        {"sale_id": "TX-1001", "store_id": "STR-01", "employee_id": "0042", "amount": 124.50, "sale_date": "2026-03-05"},
        {"sale_id": "TX-1002", "store_id": "STR-01", "employee_id": "0042", "amount": 310.00, "sale_date": "2026-03-06"},
        {"sale_id": "TX-1003", "store_id": "STR-02", "employee_id": "0043", "amount": 89.90, "sale_date": "2026-03-05"},
    ])

    df_inventory = pd.DataFrame([
        {"store_id": "STR-01", "item_id": "SKU-990", "quantity_on_hand": 45, "last_restock": "2026-02-28"},
        {"store_id": "STR-01", "item_id": "SKU-990", "quantity_on_hand": 42, "last_restock": "2026-03-01"}, # duplicate on store_id + item_id! NO clean key!
        {"store_id": "STR-02", "item_id": "SKU-881", "quantity_on_hand": 12, "last_restock": "2026-03-02"},
    ])

    tables = {
        "Employees": df_employees,
        "AttendanceDaily": df_attendance,
        "EmployeeMonthly": df_emp_monthly,
        "Stores": df_stores,
        "Sales": df_sales,
        "InventoryDaily": df_inventory,
    }

    # Write Excel file
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer_xl:
        for sheet_name, df in tables.items():
            df.to_excel(writer_xl, sheet_name=sheet_name, index=False)

    # 2. SDR-1 Profiles
    profiles = [
        # Employees
        _create_profile("Employees", "employee_id", "employee_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticDtype.IDENTIFIER_CODE, SemanticConcept.IDENTIFIER, entity_type=SemanticEntityType.PERSON, privacy=PrivacyClassification.DIRECT_IDENTIFIER, distinct_count=4, row_count=4),
        _create_profile("Employees", "employee_name", "employee_name", SemanticColumnRole.ENTITY_LABEL, SemanticDtype.NATURAL_LANGUAGE_TEXT, SemanticConcept.DESCRIPTOR, entity_type=SemanticEntityType.PERSON, privacy=PrivacyClassification.DIRECT_IDENTIFIER, distinct_count=4, row_count=4),
        _create_profile("Employees", "department", "department", SemanticColumnRole.DIMENSION, SemanticDtype.CATEGORICAL_CODE, SemanticConcept.DESCRIPTOR, entity_type=SemanticEntityType.DEPARTMENT, distinct_count=3, row_count=4),
        _create_profile("Employees", "salary", "salary", SemanticColumnRole.MEASURE, SemanticDtype.DECIMAL_NUMBER, SemanticConcept.MEASURE, measure_class=MeasureClass.FINANCIAL, privacy=PrivacyClassification.SENSITIVE_ATTRIBUTE, distinct_count=4, row_count=4),
        _create_profile("Employees", "city", "city", SemanticColumnRole.LOCATION, SemanticDtype.GEOGRAPHIC_LOCATION, SemanticConcept.LOCATION_ATTRIBUTE, entity_type=SemanticEntityType.LOCATION, distinct_count=4, row_count=4),
        _create_profile("Employees", "zip_code", "zip_code", SemanticColumnRole.LOCATION, SemanticDtype.CATEGORICAL_CODE, SemanticConcept.LOCATION_ATTRIBUTE, entity_type=SemanticEntityType.LOCATION, distinct_count=4, row_count=4),
        _create_profile("Employees", "ssn_redacted", "ssn_redacted", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticDtype.IDENTIFIER_CODE, SemanticConcept.IDENTIFIER, privacy=PrivacyClassification.SENSITIVE_ATTRIBUTE, distinct_count=4, row_count=4),

        # AttendanceDaily
        _create_profile("AttendanceDaily", "record_id", "record_id", SemanticColumnRole.TECHNICAL_METADATA, SemanticDtype.IDENTIFIER_CODE, SemanticConcept.IDENTIFIER, distinct_count=4, row_count=4),
        _create_profile("AttendanceDaily", "employee_id", "employee_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticDtype.IDENTIFIER_CODE, SemanticConcept.IDENTIFIER, entity_type=SemanticEntityType.PERSON, distinct_count=3, row_count=4),
        _create_profile("AttendanceDaily", "work_date", "work_date", SemanticColumnRole.TIME, SemanticDtype.DATE, SemanticConcept.TIME_SPAN, distinct_count=2, row_count=4),
        _create_profile("AttendanceDaily", "hours_worked", "hours_worked", SemanticColumnRole.MEASURE, SemanticDtype.DECIMAL_NUMBER, SemanticConcept.MEASURE, measure_class=MeasureClass.DURATION, distinct_count=3, row_count=4),
        _create_profile("AttendanceDaily", "status", "status", SemanticColumnRole.STATUS, SemanticDtype.CATEGORICAL_CODE, SemanticConcept.STATUS, distinct_count=2, row_count=4),

        # EmployeeMonthly
        _create_profile("EmployeeMonthly", "summary_id", "summary_id", SemanticColumnRole.TECHNICAL_METADATA, SemanticDtype.IDENTIFIER_CODE, SemanticConcept.IDENTIFIER, distinct_count=3, row_count=3),
        _create_profile("EmployeeMonthly", "employee_id", "employee_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticDtype.IDENTIFIER_CODE, SemanticConcept.IDENTIFIER, entity_type=SemanticEntityType.PERSON, distinct_count=3, row_count=3),
        _create_profile("EmployeeMonthly", "month", "month", SemanticColumnRole.TIME, SemanticDtype.DATE, SemanticConcept.TIME_SPAN, distinct_count=1, row_count=3),
        _create_profile("EmployeeMonthly", "total_hours", "total_hours", SemanticColumnRole.MEASURE, SemanticDtype.DECIMAL_NUMBER, SemanticConcept.MEASURE, measure_class=MeasureClass.DURATION, distinct_count=3, row_count=3),
        _create_profile("EmployeeMonthly", "monthly_bonus", "monthly_bonus", SemanticColumnRole.MEASURE, SemanticDtype.DECIMAL_NUMBER, SemanticConcept.MEASURE, measure_class=MeasureClass.FINANCIAL, distinct_count=3, row_count=3),

        # Stores
        _create_profile("Stores", "store_id", "store_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticDtype.IDENTIFIER_CODE, SemanticConcept.IDENTIFIER, entity_type=SemanticEntityType.STORE, distinct_count=3, row_count=3),
        _create_profile("Stores", "store_name", "store_name", SemanticColumnRole.ENTITY_LABEL, SemanticDtype.NATURAL_LANGUAGE_TEXT, SemanticConcept.DESCRIPTOR, entity_type=SemanticEntityType.STORE, distinct_count=3, row_count=3),
        _create_profile("Stores", "city", "city", SemanticColumnRole.LOCATION, SemanticDtype.GEOGRAPHIC_LOCATION, SemanticConcept.LOCATION_ATTRIBUTE, entity_type=SemanticEntityType.LOCATION, distinct_count=3, row_count=3),
        _create_profile("Stores", "region", "region", SemanticColumnRole.LOCATION, SemanticDtype.CATEGORICAL_CODE, SemanticConcept.LOCATION_ATTRIBUTE, entity_type=SemanticEntityType.LOCATION, distinct_count=2, row_count=3),
        _create_profile("Stores", "opened_year", "opened_year", SemanticColumnRole.TIME, SemanticDtype.INTEGER_NUMBER, SemanticConcept.TIME_SPAN, distinct_count=3, row_count=3),

        # Sales
        _create_profile("Sales", "sale_id", "sale_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticDtype.IDENTIFIER_CODE, SemanticConcept.IDENTIFIER, entity_type=SemanticEntityType.TRANSACTION, distinct_count=3, row_count=3),
        _create_profile("Sales", "store_id", "store_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticDtype.IDENTIFIER_CODE, SemanticConcept.IDENTIFIER, entity_type=SemanticEntityType.STORE, distinct_count=2, row_count=3),
        _create_profile("Sales", "employee_id", "employee_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticDtype.IDENTIFIER_CODE, SemanticConcept.IDENTIFIER, entity_type=SemanticEntityType.PERSON, distinct_count=2, row_count=3),
        _create_profile("Sales", "amount", "amount", SemanticColumnRole.MEASURE, SemanticDtype.DECIMAL_NUMBER, SemanticConcept.MEASURE, measure_class=MeasureClass.FINANCIAL, distinct_count=3, row_count=3),
        _create_profile("Sales", "sale_date", "sale_date", SemanticColumnRole.TIME, SemanticDtype.DATE, SemanticConcept.TIME_SPAN, distinct_count=2, row_count=3),

        # InventoryDaily
        _create_profile("InventoryDaily", "store_id", "store_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticDtype.IDENTIFIER_CODE, SemanticConcept.IDENTIFIER, entity_type=SemanticEntityType.STORE, distinct_count=2, row_count=3),
        _create_profile("InventoryDaily", "item_id", "item_id", SemanticColumnRole.ENTITY_IDENTIFIER, SemanticDtype.IDENTIFIER_CODE, SemanticConcept.IDENTIFIER, entity_type=SemanticEntityType.PRODUCT, distinct_count=2, row_count=3),
        _create_profile("InventoryDaily", "quantity_on_hand", "quantity_on_hand", SemanticColumnRole.MEASURE, SemanticDtype.INTEGER_NUMBER, SemanticConcept.MEASURE, measure_class=MeasureClass.QUANTITY, distinct_count=3, row_count=3),
        _create_profile("InventoryDaily", "last_restock", "last_restock", SemanticColumnRole.TIME, SemanticDtype.DATE, SemanticConcept.TIME_SPAN, distinct_count=3, row_count=3),
    ]

    # 3. SDR-2 Entities & Grain
    entities = [
        SemanticEntityHypothesis(
            entity_hypothesis_id="hyp_emp",
            dataset_id=DATASET_ID,
            sheet_id="Employees",
            entity_type=SemanticEntityType.PERSON,
            canonical_name="EMPLOYEE",
            supporting_column_ids=["employee_id", "employee_name"],
            entity_confidence=1.0,
            evidence="Single unambiguous person entity cluster",
            state=EntityHypothesisState.CONFIRMED,
        ),
        SemanticEntityHypothesis(
            entity_hypothesis_id="hyp_att",
            dataset_id=DATASET_ID,
            sheet_id="AttendanceDaily",
            entity_type=SemanticEntityType.EVENT,
            canonical_name="DAILY_ATTENDANCE",
            supporting_column_ids=["employee_id", "work_date"],
            entity_confidence=0.95,
            evidence="Daily time attendance event cluster",
            state=EntityHypothesisState.CONFIRMED,
        ),
        SemanticEntityHypothesis(
            entity_hypothesis_id="hyp_monthly",
            dataset_id=DATASET_ID,
            sheet_id="EmployeeMonthly",
            entity_type=SemanticEntityType.PERSON,
            canonical_name="MONTHLY_EMPLOYEE_SUMMARY",
            supporting_column_ids=["employee_id", "month"],
            entity_confidence=0.95,
            evidence="Monthly employee summary rollup",
            state=EntityHypothesisState.CONFIRMED,
        ),
        SemanticEntityHypothesis(
            entity_hypothesis_id="hyp_store",
            dataset_id=DATASET_ID,
            sheet_id="Stores",
            entity_type=SemanticEntityType.STORE,
            canonical_name="STORE",
            supporting_column_ids=["store_id", "store_name"],
            entity_confidence=1.0,
            evidence="Physical retail store location master",
            state=EntityHypothesisState.CONFIRMED,
        ),
        SemanticEntityHypothesis(
            entity_hypothesis_id="hyp_sales",
            dataset_id=DATASET_ID,
            sheet_id="Sales",
            entity_type=SemanticEntityType.TRANSACTION,
            canonical_name="SALES_TRANSACTION",
            supporting_column_ids=["sale_id"],
            entity_confidence=1.0,
            evidence="Customer sales transaction record",
            state=EntityHypothesisState.CONFIRMED,
        ),
        SemanticEntityHypothesis(
            entity_hypothesis_id="hyp_inv",
            dataset_id=DATASET_ID,
            sheet_id="InventoryDaily",
            entity_type=SemanticEntityType.PRODUCT,
            canonical_name="INVENTORY_SNAPSHOT",
            supporting_column_ids=["store_id", "item_id"],
            entity_confidence=0.88,
            evidence="Multi-attribute inventory observation",
            state=EntityHypothesisState.PROVISIONAL,
        ),
    ]

    grain_cand_emp = GrainCandidate(
        candidate_id="gc_emp",
        determinant_column_ids=["employee_id"],
        determinant_column_names=["employee_id"],
        grain_expression="EMPLOYEE_ID",
        width=1,
        row_count=4,
        unique_combination_count=4,
        uniqueness_ratio=1.0,
        confidence=1.0,
        rationale="100% unique natural identifier",
    )
    grain_cand_att = GrainCandidate(
        candidate_id="gc_att",
        determinant_column_ids=["employee_id", "work_date"],
        determinant_column_names=["employee_id", "work_date"],
        grain_expression="EMPLOYEE_ID x WORK_DATE",
        width=2,
        row_count=4,
        unique_combination_count=4,
        uniqueness_ratio=1.0,
        confidence=0.95,
        rationale="Composite width 2 temporal attendance grain",
    )
    grain_cand_monthly = GrainCandidate(
        candidate_id="gc_monthly",
        determinant_column_ids=["employee_id", "month"],
        determinant_column_names=["employee_id", "month"],
        grain_expression="EMPLOYEE_ID x MONTH",
        width=2,
        row_count=3,
        unique_combination_count=3,
        uniqueness_ratio=1.0,
        confidence=0.95,
        rationale="Monthly employee summary grain",
    )
    grain_cand_stores = GrainCandidate(
        candidate_id="gc_stores",
        determinant_column_ids=["store_id"],
        determinant_column_names=["store_id"],
        grain_expression="STORE_ID",
        width=1,
        row_count=3,
        unique_combination_count=3,
        uniqueness_ratio=1.0,
        confidence=1.0,
        rationale="Unique retail store identifier",
    )
    grain_cand_sales = GrainCandidate(
        candidate_id="gc_sales",
        determinant_column_ids=["sale_id"],
        determinant_column_names=["sale_id"],
        grain_expression="SALE_ID",
        width=1,
        row_count=3,
        unique_combination_count=3,
        uniqueness_ratio=1.0,
        confidence=1.0,
        rationale="Transaction primary receipt grain",
    )
    grain_cand_inv = GrainCandidate(
        candidate_id="gc_inv",
        determinant_column_ids=["store_id", "item_id"],
        determinant_column_names=["store_id", "item_id"],
        grain_expression="STORE_ID x ITEM_ID",
        width=2,
        row_count=3,
        unique_combination_count=2,
        uniqueness_ratio=0.667,
        confidence=0.6,
        rationale="Sub-unique composite grain; contains duplicates",
    )

    grains = [
        SDRGrainProfile(
            profile_id="gp_emp",
            dataset_id=DATASET_ID,
            sheet_id="Employees",
            primary_entity=CanonicalGrain.PERSON,
            temporal_grain=TemporalGrain.NONE,
            resolved_grain_expression="EMPLOYEE_ID",
            grain_status=GrainStatus.RESOLVED,
            best_candidate=grain_cand_emp,
            ranked_candidates=[grain_cand_emp],
            is_unique=True,
            grain_confidence=1.0,
            rationale="100% unique natural employee entity grain",
        ),
        SDRGrainProfile(
            profile_id="gp_att",
            dataset_id=DATASET_ID,
            sheet_id="AttendanceDaily",
            primary_entity=CanonicalGrain.EVENT,
            temporal_grain=TemporalGrain.DAY,
            resolved_grain_expression="EMPLOYEE_ID x WORK_DATE",
            grain_status=GrainStatus.RESOLVED,
            best_candidate=grain_cand_att,
            ranked_candidates=[grain_cand_att],
            is_unique=True,
            grain_confidence=0.95,
            rationale="Composite width 2 temporal attendance grain",
        ),
        SDRGrainProfile(
            profile_id="gp_monthly",
            dataset_id=DATASET_ID,
            sheet_id="EmployeeMonthly",
            primary_entity=CanonicalGrain.PERSON,
            temporal_grain=TemporalGrain.MONTH,
            resolved_grain_expression="EMPLOYEE_ID x MONTH",
            grain_status=GrainStatus.RESOLVED,
            best_candidate=grain_cand_monthly,
            ranked_candidates=[grain_cand_monthly],
            is_unique=True,
            grain_confidence=0.95,
            rationale="Monthly employee summary grain",
        ),
        SDRGrainProfile(
            profile_id="gp_stores",
            dataset_id=DATASET_ID,
            sheet_id="Stores",
            primary_entity=CanonicalGrain.STORE,
            temporal_grain=TemporalGrain.NONE,
            resolved_grain_expression="STORE_ID",
            grain_status=GrainStatus.RESOLVED,
            best_candidate=grain_cand_stores,
            ranked_candidates=[grain_cand_stores],
            is_unique=True,
            grain_confidence=1.0,
            rationale="Unique retail store identifier",
        ),
        SDRGrainProfile(
            profile_id="gp_sales",
            dataset_id=DATASET_ID,
            sheet_id="Sales",
            primary_entity=CanonicalGrain.TRANSACTION,
            temporal_grain=TemporalGrain.DAY,
            resolved_grain_expression="SALE_ID",
            grain_status=GrainStatus.RESOLVED,
            best_candidate=grain_cand_sales,
            ranked_candidates=[grain_cand_sales],
            is_unique=True,
            grain_confidence=1.0,
            rationale="Transaction primary receipt grain",
        ),
        SDRGrainProfile(
            profile_id="gp_inv",
            dataset_id=DATASET_ID,
            sheet_id="InventoryDaily",
            primary_entity=CanonicalGrain.PRODUCT,
            temporal_grain=TemporalGrain.NONE,
            resolved_grain_expression="STORE_ID x ITEM_ID",
            grain_status=GrainStatus.AMBIGUOUS,
            best_candidate=grain_cand_inv,
            ranked_candidates=[grain_cand_inv],
            is_unique=False,
            grain_confidence=0.6,
            rationale="Sub-unique composite grain; contains duplicate observations",
        ),
    ]

    # 4. SDR-3 Keys
    keys = [
        SDRKeyCandidate(
            candidate_id="key_emp",
            dataset_id=DATASET_ID,
            sheet_id="Employees",
            column_ids=["employee_id"],
            column_names=["employee_id"],
            candidate_type=KeyCandidateType.HIGH_CONFIDENCE_CANDIDATE_KEY,
            entity_type=SemanticEntityType.PERSON,
            grain_expression="EMPLOYEE_ID",
            width=1,
            row_count=4,
            unique_combination_count=4,
            uniqueness_ratio=1.0,
            key_confidence=1.0,
            authority=KeyAuthority.INFERRED,
            status=KeyCandidateStatus.HIGH_CONFIDENCE,
            evidence="100% unique natural identifier without nulls",
        ),
        SDRKeyCandidate(
            candidate_id="key_monthly",
            dataset_id=DATASET_ID,
            sheet_id="EmployeeMonthly",
            column_ids=["employee_id", "month"],
            column_names=["employee_id", "month"],
            candidate_type=KeyCandidateType.COMPOSITE_CANDIDATE_KEY,
            entity_type=SemanticEntityType.PERSON,
            grain_expression="EMPLOYEE_ID x MONTH",
            width=2,
            row_count=3,
            unique_combination_count=3,
            uniqueness_ratio=1.0,
            key_confidence=0.98,
            authority=KeyAuthority.INFERRED,
            status=KeyCandidateStatus.HIGH_CONFIDENCE,
            evidence="Composite natural key matching monthly grain",
        ),
        SDRKeyCandidate(
            candidate_id="key_stores",
            dataset_id=DATASET_ID,
            sheet_id="Stores",
            column_ids=["store_id"],
            column_names=["store_id"],
            candidate_type=KeyCandidateType.HIGH_CONFIDENCE_CANDIDATE_KEY,
            entity_type=SemanticEntityType.STORE,
            grain_expression="STORE_ID",
            width=1,
            row_count=3,
            unique_combination_count=3,
            uniqueness_ratio=1.0,
            key_confidence=1.0,
            authority=KeyAuthority.INFERRED,
            status=KeyCandidateStatus.HIGH_CONFIDENCE,
            evidence="100% unique retail store key",
        ),
        SDRKeyCandidate(
            candidate_id="key_sales",
            dataset_id=DATASET_ID,
            sheet_id="Sales",
            column_ids=["sale_id"],
            column_names=["sale_id"],
            candidate_type=KeyCandidateType.HIGH_CONFIDENCE_CANDIDATE_KEY,
            entity_type=SemanticEntityType.TRANSACTION,
            grain_expression="SALE_ID",
            width=1,
            row_count=3,
            unique_combination_count=3,
            uniqueness_ratio=1.0,
            key_confidence=1.0,
            authority=KeyAuthority.INFERRED,
            status=KeyCandidateStatus.HIGH_CONFIDENCE,
            evidence="Unique transaction receipt identifier",
        ),
        # Notice: InventoryDaily has NO candidate key included here to demonstrate NO-KEY STATE!
    ]

    # 5. SDR-4G Canonical Geo Entities & Resolutions
    geo_blr = CanonicalGeoEntity(
        geo_entity_id="GEO_BLR",
        level=GeoLevel.CITY,
        canonical_name="Bengaluru",
        display_name="Bengaluru, Karnataka, India",
        country_code="IN",
        country_code_alpha3="IND",
        admin1_code="KA",
        latitude=12.9716,
        longitude=77.5946,
        timezone="Asia/Kolkata",
        reference_source="GeoNames+NaturalEarth",
        reference_version="2026.1",
        aliases=["Bangalore", "BLR", "Bengaluru City"],
        confidence=1.0,
    )
    geo_sfo = CanonicalGeoEntity(
        geo_entity_id="GEO_SFO",
        level=GeoLevel.CITY,
        canonical_name="San Francisco",
        display_name="San Francisco, California, United States",
        country_code="US",
        country_code_alpha3="USA",
        admin1_code="CA",
        latitude=37.7749,
        longitude=-122.4194,
        timezone="America/Los_Angeles",
        reference_source="GeoNames+NaturalEarth",
        reference_version="2026.1",
        aliases=["SF", "San Fran"],
        confidence=1.0,
    )

    geo_resolutions = [
        GeoResolutionCandidate(
            source_value="Bengaluru",
            normalized_input="bengaluru",
            candidate_geo_entity_ids=["GEO_BLR"],
            resolved_entity_id="GEO_BLR",
            candidate_count=1,
            resolution_status=GeoResolutionStatus.RESOLVED,
            confidence=0.98,
            match_method=GeoMatchMethod.EXACT_CANONICAL,
            disambiguation_evidence=["Exact match against canonical entity name"],
            source_column_id="city",
        ),
        GeoResolutionCandidate(
            source_value="San Francisco",
            normalized_input="san francisco",
            candidate_geo_entity_ids=["GEO_SFO"],
            resolved_entity_id="GEO_SFO",
            candidate_count=1,
            resolution_status=GeoResolutionStatus.RESOLVED,
            confidence=0.99,
            match_method=GeoMatchMethod.EXACT_CANONICAL,
            disambiguation_evidence=["Exact match against canonical entity name"],
            source_column_id="city",
        ),
        GeoResolutionCandidate(
            source_value="Springfield",
            normalized_input="springfield",
            candidate_geo_entity_ids=["GEO_SPRINGFIELD_IL", "GEO_SPRINGFIELD_MA", "GEO_SPRINGFIELD_MO"],
            resolved_entity_id=None,
            candidate_count=3,
            resolution_status=GeoResolutionStatus.AMBIGUOUS,
            confidence=0.35,
            match_method=GeoMatchMethod.NONE,
            disambiguation_evidence=["Ambiguous location: multiple administrative matches across IL, MA, MO without regional context."],
            source_column_id="city",
        ),
    ]

    # 6. SDR-5 Relationships & JoinPlans
    # Relationship 1: Sales -> Stores (SAFE Dimension Lookup)
    edge_sales_stores = SDRValidatedRelationshipEdge(
        edge_id="edge_sales_stores",
        candidate_id="cand_sales_stores",
        dataset_id=DATASET_ID,
        left_sheet_id="Sales",
        left_column_ids=["store_id"],
        right_sheet_id="Stores",
        right_column_ids=["store_id"],
        relationship_class=RelationshipClass.STRUCTURAL_RELATIONSHIP,
        cardinality=RelationshipCardinality.MANY_TO_ONE,
        status=RelationshipStatus.VALIDATED,
        referential_coverage=1.0,
        left_coverage=1.0,
        right_coverage=1.0,
        is_grain_preserving=True,
        left_grain="SALE",
        right_grain="STORE",
    )
    plan_sales_stores = SDRJoinPlan(
        join_plan_id="JP-SALES-STORES",
        relationship_edge_id="edge_sales_stores",
        dataset_id=DATASET_ID,
        left_sheet_id="Sales",
        right_sheet_id="Stores",
        left_keys=["store_id"],
        right_keys=["store_id"],
        join_type="INNER",
        safety_status=JoinSafetyStatus.SAFE,
        left_grain="SALE",
        right_grain="STORE",
        target_grain="SALE",
        preaggregation_steps=[],
        safe_operations=["DIRECT_JOIN"],
        risk_flags=[],
    )

    # Relationship 2: AttendanceDaily -> EmployeeMonthly (SAFE WITH PREAGGREGATION)
    edge_att_monthly = SDRValidatedRelationshipEdge(
        edge_id="edge_att_monthly",
        candidate_id="cand_att_monthly",
        dataset_id=DATASET_ID,
        left_sheet_id="AttendanceDaily",
        left_column_ids=["employee_id"],
        right_sheet_id="EmployeeMonthly",
        right_column_ids=["employee_id"],
        relationship_class=RelationshipClass.STRUCTURAL_RELATIONSHIP,
        cardinality=RelationshipCardinality.MANY_TO_ONE,
        status=RelationshipStatus.VALIDATED,
        referential_coverage=1.0,
        left_coverage=1.0,
        right_coverage=1.0,
        is_grain_preserving=False,
        left_grain="EMPLOYEE × DAY",
        right_grain="EMPLOYEE × MONTH",
    )
    plan_att_monthly = SDRJoinPlan(
        join_plan_id="JP-ATT-MONTHLY",
        relationship_edge_id="edge_att_monthly",
        dataset_id=DATASET_ID,
        left_sheet_id="AttendanceDaily",
        right_sheet_id="EmployeeMonthly",
        left_keys=["employee_id"],
        right_keys=["employee_id"],
        join_type="INNER",
        safety_status=JoinSafetyStatus.SAFE_WITH_PREAGGREGATION,
        left_grain="EMPLOYEE × DAY",
        right_grain="EMPLOYEE × MONTH",
        target_grain="EMPLOYEE × MONTH",
        required_preaggregation=True,
        preaggregation_side="LEFT",
        preaggregation_spec=PreAggregationSpec(
            source_table_id="AttendanceDaily",
            group_by_columns=["employee_id"],
            aggregations={"hours_worked": "SUM"},
            target_grain="EMPLOYEE × MONTH",
        ),
        safe_operations=["AGGREGATE_AND_JOIN"],
        risk_flags=[],
    )

    # Relationship 3: Employees -> AttendanceDaily (UNSAFE Measure Multiplication)
    edge_emp_att = SDRValidatedRelationshipEdge(
        edge_id="edge_emp_att",
        candidate_id="cand_emp_att",
        dataset_id=DATASET_ID,
        left_sheet_id="Employees",
        left_column_ids=["employee_id"],
        right_sheet_id="AttendanceDaily",
        right_column_ids=["employee_id"],
        relationship_class=RelationshipClass.STRUCTURAL_RELATIONSHIP,
        cardinality=RelationshipCardinality.ONE_TO_MANY,
        status=RelationshipStatus.REJECTED,
        referential_coverage=1.0,
        left_coverage=1.0,
        right_coverage=1.0,
        is_grain_preserving=False,
        left_grain="EMPLOYEE",
        right_grain="EMPLOYEE × DAY",
    )
    plan_emp_att = SDRJoinPlan(
        join_plan_id="JP-EMP-ATT",
        relationship_edge_id="edge_emp_att",
        dataset_id=DATASET_ID,
        left_sheet_id="Employees",
        right_sheet_id="AttendanceDaily",
        left_keys=["employee_id"],
        right_keys=["employee_id"],
        join_type="INNER",
        safety_status=JoinSafetyStatus.UNSAFE,
        left_grain="EMPLOYEE",
        right_grain="EMPLOYEE × DAY",
        target_grain="EMPLOYEE × DAY",
        risk_flags=["MEASURE_MULTIPLICATION_RISK", "SALARY_INFLATION_HAZARD"],
        safe_operations=[],
    )

    # 7. SDR-6 Analytical Views & Facts
    expr_revenue = ControlledExpression.col("amount", unit="USD")
    expr_total_hours = ControlledExpression.col("total_hours", unit="hours")

    view_sales = SDRAnalyticalViewSpec(
        analytical_view_id="view_monthly_store_sales",
        dataset_id=DATASET_ID,
        name="Store Performance & Regional Sales",
        source_sheet_ids=["Sales", "Stores"],
        join_plan_ids=["JP-SALES-STORES"],
        base_grain="SALE",
        result_grain="STORE",
        dimension_columns=["store_id", "store_name", "region"],
        measure_columns=["amount"],
        derived_measure_specs=[
            SDRDerivedMeasureSpec(
                measure_name="total_revenue",
                expression=expr_revenue,
                unit="USD",
                measure_class="ADDITIVE",
                formula_repr="SUM(amount)",
            )
        ],
        unit_metadata={"total_revenue": "USD", "amount": "USD"},
        materialization_mode=MaterializationMode.VIRTUAL,
        status=SDRAnalyticalViewStatus.VALID,
    )

    view_attendance = SDRAnalyticalViewSpec(
        analytical_view_id="view_monthly_attendance_summary",
        dataset_id=DATASET_ID,
        name="Employee Monthly Attendance & Bonus",
        source_sheet_ids=["AttendanceDaily", "EmployeeMonthly"],
        join_plan_ids=["JP-ATT-MONTHLY"],
        base_grain="EMPLOYEE × DAY",
        result_grain="EMPLOYEE × MONTH",
        dimension_columns=["employee_id", "month"],
        measure_columns=["total_hours", "monthly_bonus"],
        derived_measure_specs=[
            SDRDerivedMeasureSpec(
                measure_name="aggregated_hours",
                expression=expr_total_hours,
                unit="hours",
                measure_class="ADDITIVE",
                formula_repr="SUM(hours_worked)",
            )
        ],
        unit_metadata={"aggregated_hours": "hours", "monthly_bonus": "USD"},
        materialization_mode=MaterializationMode.VIRTUAL,
        status=SDRAnalyticalViewStatus.VALID_WITH_PREAGGREGATION,
    )

    view_stale = SDRAnalyticalViewSpec(
        analytical_view_id="view_stale_legacy_compensation",
        dataset_id=DATASET_ID,
        name="Deprecated Compensation Rollup (Legacy)",
        source_sheet_ids=["Employees"],
        base_grain="EMPLOYEE",
        result_grain="DEPARTMENT",
        status=SDRAnalyticalViewStatus.STALE,
        rejection_reason="Upstream formula drift: bonus tier calculation invalidated.",
    )

    fact_revenue = SDRAnalyticalFact(
        fact_id="fact_total_rev_flagship",
        metric="total_revenue",
        value=434.50,
        formatted_value="$434.50",
        unit="USD",
        grain="STORE",
        dataset_id=DATASET_ID,
        analytical_view_id="view_monthly_store_sales",
        join_plan_ids=["JP-SALES-STORES"],
        provenance_type="DERIVED_RELATIONAL",
    )

    fact_hours = SDRAnalyticalFact(
        fact_id="fact_emp_001_hours",
        metric="aggregated_hours",
        value=168.0,
        formatted_value="168.0 hrs",
        unit="hours",
        grain="EMPLOYEE × MONTH",
        dataset_id=DATASET_ID,
        analytical_view_id="view_monthly_attendance_summary",
        join_plan_ids=["JP-ATT-MONTHLY"],
        provenance_type="DERIVED_RELATIONAL",
    )

    # 8. Write all artifacts via SDRArtifactWriter
    writer = SDRArtifactWriter(base_data_dir=root_data)
    writer.write_artifacts(DATASET_ID, profiles, [])
    writer.write_sdr2_artifacts(DATASET_ID, entities, grains, [grain_cand_emp, grain_cand_att, grain_cand_monthly, grain_cand_stores, grain_cand_sales, grain_cand_inv])
    writer.write_sdr3_artifacts(DATASET_ID, keys, [])
    writer.write_sdr4_artifacts(DATASET_ID, [], [], [])
    writer.write_sdr4g_artifacts(DATASET_ID, geo_resolutions, [geo_blr, geo_sfo])
    writer.write_sdr5_artifacts(DATASET_ID, [], [edge_sales_stores, edge_att_monthly, edge_emp_att], [plan_sales_stores, plan_att_monthly, plan_emp_att])
    writer.write_sdr6_artifacts(DATASET_ID, [view_sales, view_attendance, view_stale], [fact_revenue, fact_hours], [])

    # Also save raw sheet json for exact source row serving without touching P0 SQLite
    sdr_dir = root_data / "datasets" / DATASET_ID / "sdr"
    raw_source = {name: df.to_dict(orient="records") for name, df in tables.items()}
    (sdr_dir / "raw_source_tables.json").write_text(json.dumps(raw_source, indent=2), encoding="utf-8")

    return {
        "dataset_id": DATASET_ID,
        "excel_path": str(excel_path),
        "sheets_count": len(tables),
        "total_rows": sum(len(df) for df in tables.values()),
    }


if __name__ == "__main__":
    res = seed_certification_dataset()
    print("Seeded SDR-7 certification dataset:", res)
