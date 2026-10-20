"""
HighView Semantic Data Refinery — Phase SDR-8
Seed SDR-8 Certification Datasets (Hermetic file-based JSON, Zero SQLite writes)

Creates:
1. sdr8_wfo:
   - Sheets: Employees, AttendanceDaily, EmployeeMonthly, Departments
   - Governed facts, join plans, analytical views
2. sdr8_retail:
   - Sheets: Stores, Sales, InventoryDaily, Locations
   - Governed facts, join plans, analytical views, GEO enrichments
"""

import json
from pathlib import Path


def seed_sdr8_datasets(base_dir: Path | str | None = None) -> None:
    root = Path(base_dir) if base_dir else Path(__file__).resolve().parents[1] / "data"
    ds_root = root / "datasets"

    # =========================================================================
    # 1. SDR8 WFO DATASET
    # =========================================================================
    wfo_dir = ds_root / "sdr8_wfo" / "sdr"
    wfo_dir.mkdir(parents=True, exist_ok=True)

    # Manifest
    manifest_wfo = {
        "dataset_id": "sdr8_wfo",
        "dataset_name": "WFO and Attendance Dataset",
        "dataset_version": "v1",
        "sheets": [
            {"sheet_id": "Employees", "name": "Employees", "row_count": 42},
            {"sheet_id": "AttendanceDaily", "name": "AttendanceDaily", "row_count": 210},
            {"sheet_id": "EmployeeMonthly", "name": "EmployeeMonthly", "row_count": 42},
            {"sheet_id": "Departments", "name": "Departments", "row_count": 5},
        ],
    }
    (ds_root / "sdr8_wfo" / "manifest.json").write_text(json.dumps(manifest_wfo, indent=2), encoding="utf-8")

    # Analytical Views
    views_wfo = [
        {
            "analytical_view_id": "view_wfo_dept_attendance",
            "dataset_id": "sdr8_wfo",
            "name": "Department Attendance Rate View",
            "source_sheet_ids": ["Employees", "AttendanceDaily", "Departments"],
            "join_plan_ids": ["JP-EMP-ATT", "JP-EMP-DEPT"],
            "base_grain": "EMPLOYEE x DAY",
            "result_grain": "DEPARTMENT",
            "status": "VALID",
            "materialization_mode": "VIRTUAL",
            "formula_fingerprint": "fp_dept_att",
        },
        {
            "analytical_view_id": "view_wfo_monthly_preagg",
            "dataset_id": "sdr8_wfo",
            "name": "Preaggregated Monthly Attendance View",
            "source_sheet_ids": ["AttendanceDaily", "EmployeeMonthly"],
            "join_plan_ids": ["JP-ATT-MONTHLY"],
            "base_grain": "EMPLOYEE x DAY",
            "result_grain": "EMPLOYEE x MONTH",
            "status": "VALID_WITH_PREAGGREGATION",
            "materialization_mode": "VIRTUAL",
            "formula_fingerprint": "fp_monthly_preagg",
        },
        {
            "analytical_view_id": "view_wfo_unsafe_blocked",
            "dataset_id": "sdr8_wfo",
            "name": "Unsafe Cartesian Attendance View",
            "source_sheet_ids": ["AttendanceDaily", "Employees"],
            "join_plan_ids": ["JP-UNSAFE-JOIN"],
            "base_grain": "EMPLOYEE x DAY",
            "result_grain": "DATASET",
            "status": "UNSAFE",
            "materialization_mode": "VIRTUAL",
            "formula_fingerprint": "fp_unsafe",
        },
        {
            "analytical_view_id": "view_wfo_stale_blocked",
            "dataset_id": "sdr8_wfo",
            "name": "Stale Attendance View",
            "source_sheet_ids": ["Employees"],
            "join_plan_ids": [],
            "base_grain": "EMPLOYEE",
            "result_grain": "EMPLOYEE",
            "status": "STALE",
            "materialization_mode": "VIRTUAL",
            "formula_fingerprint": "fp_stale",
        },
    ]
    (wfo_dir / "analytical_views.json").write_text(json.dumps(views_wfo, indent=2), encoding="utf-8")

    # Join Plans
    join_plans_wfo = [
        {
            "join_plan_id": "JP-EMP-ATT",
            "dataset_id": "sdr8_wfo",
            "left_sheet": "Employees",
            "right_sheet": "AttendanceDaily",
            "join_type": "LEFT",
            "safety_status": "SAFE",
            "cardinality": "ONE_TO_MANY",
            "left_keys": ["employee_id"],
            "right_keys": ["employee_id"],
        },
        {
            "join_plan_id": "JP-ATT-MONTHLY",
            "dataset_id": "sdr8_wfo",
            "left_sheet": "AttendanceDaily",
            "right_sheet": "EmployeeMonthly",
            "join_type": "LEFT",
            "safety_status": "SAFE_WITH_PREAGGREGATION",
            "cardinality": "MANY_TO_ONE",
            "left_keys": ["employee_id", "month"],
            "right_keys": ["employee_id", "month"],
        },
        {
            "join_plan_id": "JP-EMP-DEPT",
            "dataset_id": "sdr8_wfo",
            "left_sheet": "Employees",
            "right_sheet": "Departments",
            "join_type": "LEFT",
            "safety_status": "SAFE",
            "cardinality": "MANY_TO_ONE",
            "left_keys": ["department_id"],
            "right_keys": ["department_id"],
        },
        {
            "join_plan_id": "JP-UNSAFE-JOIN",
            "dataset_id": "sdr8_wfo",
            "left_sheet": "AttendanceDaily",
            "right_sheet": "Employees",
            "join_type": "CROSS",
            "safety_status": "UNSAFE",
            "cardinality": "MANY_TO_MANY",
            "left_keys": [],
            "right_keys": [],
        },
        {
            "join_plan_id": "JP-AMBIGUOUS-JOIN",
            "dataset_id": "sdr8_wfo",
            "left_sheet": "EmployeeMonthly",
            "right_sheet": "Unvalidated",
            "join_type": "LEFT",
            "safety_status": "AMBIGUOUS",
            "cardinality": "UNKNOWN",
            "left_keys": ["id"],
            "right_keys": ["id"],
        },
    ]
    (wfo_dir / "join_plans.json").write_text(json.dumps(join_plans_wfo, indent=2), encoding="utf-8")

    # Analytical Facts
    facts_wfo = [
        {
            "fact_id": "fact_wfo_1",
            "metric": "total_active_employees",
            "value": 42,
            "formatted_value": "42 employees",
            "unit": "count",
            "grain": "DATASET",
            "denominator_value": None,
            "dataset_id": "sdr8_wfo",
            "dataset_version": "v1",
            "source_evidence_ids": ["EVID-EMP-COUNT"],
            "analytical_view_id": "view_wfo_dept_attendance",
            "join_plan_ids": [],
            "provenance_type": "OBSERVED",
        },
        {
            "fact_id": "fact_wfo_2",
            "metric": "total_attendance_hours",
            "value": 1680.0,
            "formatted_value": "1,680.0 hrs",
            "unit": "hours",
            "grain": "DATASET",
            "denominator_value": None,
            "dataset_id": "sdr8_wfo",
            "dataset_version": "v1",
            "source_evidence_ids": ["EVID-ATT-HOURS"],
            "analytical_view_id": "view_wfo_monthly_preagg",
            "join_plan_ids": ["JP-ATT-MONTHLY"],
            "provenance_type": "DERIVED_LOCAL",
        },
        {
            "fact_id": "fact_wfo_3",
            "metric": "overall_attendance_rate",
            "value": 0.892157,
            "formatted_value": "89.2%",
            "unit": "percentage",
            "grain": "DATASET",
            "denominator_value": 102,
            "dataset_id": "sdr8_wfo",
            "dataset_version": "v1",
            "source_evidence_ids": ["EVID-ATT-RATE"],
            "analytical_view_id": "view_wfo_dept_attendance",
            "join_plan_ids": ["JP-EMP-ATT"],
            "provenance_type": "DERIVED_RELATIONAL",
        },
        {
            "fact_id": "fact_wfo_4",
            "metric": "department_attendance_rate_eng",
            "value": 0.94,
            "formatted_value": "94.0%",
            "unit": "percentage",
            "grain": "DEPARTMENT",
            "denominator_value": 50,
            "dataset_id": "sdr8_wfo",
            "dataset_version": "v1",
            "source_evidence_ids": ["EVID-DEPT-RATE"],
            "analytical_view_id": "view_wfo_dept_attendance",
            "join_plan_ids": ["JP-EMP-ATT", "JP-EMP-DEPT"],
            "provenance_type": "DERIVED_RELATIONAL",
        },
        {
            "fact_id": "fact_wfo_5",
            "metric": "average_daily_hours",
            "value": 8.0,
            "formatted_value": "8.0 hrs/day",
            "unit": "hours",
            "grain": "EMPLOYEE x DAY",
            "denominator_value": None,
            "dataset_id": "sdr8_wfo",
            "dataset_version": "v1",
            "source_evidence_ids": ["EVID-AVG-HOURS"],
            "analytical_view_id": "view_wfo_dept_attendance",
            "join_plan_ids": [],
            "provenance_type": "OBSERVED",
        },
    ]
    (wfo_dir / "analytical_facts.json").write_text(json.dumps(facts_wfo, indent=2), encoding="utf-8")

    # =========================================================================
    # 2. SDR8 RETAIL DATASET
    # =========================================================================
    retail_dir = ds_root / "sdr8_retail" / "sdr"
    retail_dir.mkdir(parents=True, exist_ok=True)

    manifest_retail = {
        "dataset_id": "sdr8_retail",
        "dataset_name": "Retail and Sales Dataset",
        "dataset_version": "v1",
        "sheets": [
            {"sheet_id": "Stores", "name": "Stores", "row_count": 12},
            {"sheet_id": "Sales", "name": "Sales", "row_count": 500},
            {"sheet_id": "InventoryDaily", "name": "InventoryDaily", "row_count": 360},
            {"sheet_id": "Locations", "name": "Locations", "row_count": 12},
        ],
    }
    (ds_root / "sdr8_retail" / "manifest.json").write_text(json.dumps(manifest_retail, indent=2), encoding="utf-8")

    views_retail = [
        {
            "analytical_view_id": "view_retail_regional_sales",
            "dataset_id": "sdr8_retail",
            "name": "Regional Sales Summary View",
            "source_sheet_ids": ["Sales", "Stores"],
            "join_plan_ids": ["JP-SALES-STORES"],
            "base_grain": "SALE",
            "result_grain": "REGION",
            "status": "VALID",
            "materialization_mode": "VIRTUAL",
            "formula_fingerprint": "fp_regional_sales",
        },
        {
            "analytical_view_id": "view_retail_geo_enrichment",
            "dataset_id": "sdr8_retail",
            "name": "Geo-Enriched Country Sales View",
            "source_sheet_ids": ["Sales", "Stores", "Locations"],
            "join_plan_ids": ["JP-SALES-STORES", "JP-STORES-GEO"],
            "base_grain": "SALE",
            "result_grain": "COUNTRY",
            "status": "VALID",
            "materialization_mode": "VIRTUAL",
            "formula_fingerprint": "fp_geo_sales",
        },
        {
            "analytical_view_id": "view_retail_unsafe_cartesian",
            "dataset_id": "sdr8_retail",
            "name": "Unsafe Cartesian Inventory View",
            "source_sheet_ids": ["Sales", "InventoryDaily"],
            "join_plan_ids": ["JP-UNSAFE-RETAIL"],
            "base_grain": "SALE",
            "result_grain": "DATASET",
            "status": "UNSAFE",
            "materialization_mode": "VIRTUAL",
            "formula_fingerprint": "fp_unsafe_retail",
        },
        {
            "analytical_view_id": "view_retail_stale",
            "dataset_id": "sdr8_retail",
            "name": "Stale Retail View",
            "source_sheet_ids": ["Stores"],
            "join_plan_ids": [],
            "base_grain": "STORE",
            "result_grain": "STORE",
            "status": "STALE",
            "materialization_mode": "VIRTUAL",
            "formula_fingerprint": "fp_stale_retail",
        },
    ]
    (retail_dir / "analytical_views.json").write_text(json.dumps(views_retail, indent=2), encoding="utf-8")

    join_plans_retail = [
        {
            "join_plan_id": "JP-SALES-STORES",
            "dataset_id": "sdr8_retail",
            "left_sheet": "Sales",
            "right_sheet": "Stores",
            "join_type": "LEFT",
            "safety_status": "SAFE",
            "cardinality": "MANY_TO_ONE",
            "left_keys": ["store_id"],
            "right_keys": ["store_id"],
        },
        {
            "join_plan_id": "JP-STORES-GEO",
            "dataset_id": "sdr8_retail",
            "left_sheet": "Stores",
            "right_sheet": "Locations",
            "join_type": "LEFT",
            "safety_status": "SAFE",
            "cardinality": "MANY_TO_ONE",
            "left_keys": ["city"],
            "right_keys": ["city"],
        },
        {
            "join_plan_id": "JP-UNSAFE-RETAIL",
            "dataset_id": "sdr8_retail",
            "left_sheet": "Sales",
            "right_sheet": "InventoryDaily",
            "join_type": "CROSS",
            "safety_status": "UNSAFE",
            "cardinality": "MANY_TO_MANY",
            "left_keys": [],
            "right_keys": [],
        },
    ]
    (retail_dir / "join_plans.json").write_text(json.dumps(join_plans_retail, indent=2), encoding="utf-8")

    facts_retail = [
        {
            "fact_id": "fact_ret_1",
            "metric": "total_revenue",
            "value": 1200000.0,
            "formatted_value": "$1,200,000",
            "unit": "usd",
            "grain": "DATASET",
            "denominator_value": None,
            "dataset_id": "sdr8_retail",
            "dataset_version": "v1",
            "source_evidence_ids": ["EVID-REV-TOTAL"],
            "analytical_view_id": "view_retail_regional_sales",
            "join_plan_ids": [],
            "provenance_type": "OBSERVED",
        },
        {
            "fact_id": "fact_ret_2",
            "metric": "total_units_sold",
            "value": 45000,
            "formatted_value": "45,000 units",
            "unit": "count",
            "grain": "DATASET",
            "denominator_value": None,
            "dataset_id": "sdr8_retail",
            "dataset_version": "v1",
            "source_evidence_ids": ["EVID-UNITS-TOTAL"],
            "analytical_view_id": "view_retail_regional_sales",
            "join_plan_ids": [],
            "provenance_type": "OBSERVED",
        },
        {
            "fact_id": "fact_ret_3",
            "metric": "regional_sales_apac",
            "value": 450000.0,
            "formatted_value": "$450,000",
            "unit": "usd",
            "grain": "REGION",
            "denominator_value": None,
            "dataset_id": "sdr8_retail",
            "dataset_version": "v1",
            "source_evidence_ids": ["EVID-APAC-SALES"],
            "analytical_view_id": "view_retail_regional_sales",
            "join_plan_ids": ["JP-SALES-STORES"],
            "provenance_type": "DERIVED_RELATIONAL",
        },
        {
            "fact_id": "fact_ret_4",
            "metric": "geo_enriched_sales_country",
            "value": 1200000.0,
            "formatted_value": "$1.2M",
            "unit": "usd",
            "grain": "COUNTRY",
            "denominator_value": None,
            "dataset_id": "sdr8_retail",
            "dataset_version": "v1",
            "source_evidence_ids": ["EVID-GEO-SALES"],
            "analytical_view_id": "view_retail_geo_enrichment",
            "join_plan_ids": ["JP-SALES-STORES", "JP-STORES-GEO"],
            "provenance_type": "DERIVED_ENRICHMENT",
        },
        {
            "fact_id": "fact_ret_5",
            "metric": "average_order_value",
            "value": 125.50,
            "formatted_value": "$125.50",
            "unit": "usd",
            "grain": "SALE",
            "denominator_value": None,
            "dataset_id": "sdr8_retail",
            "dataset_version": "v1",
            "source_evidence_ids": ["EVID-AOV"],
            "analytical_view_id": "view_retail_regional_sales",
            "join_plan_ids": [],
            "provenance_type": "OBSERVED",
        },
    ]
    (retail_dir / "analytical_facts.json").write_text(json.dumps(facts_retail, indent=2), encoding="utf-8")


if __name__ == "__main__":
    seed_sdr8_datasets()
    print("SDR-8 Certification Datasets seeded successfully outside P0.")
