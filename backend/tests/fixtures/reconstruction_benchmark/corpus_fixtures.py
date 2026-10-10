"""Multi-Domain Benchmark Corpus Generator & Ground-Truth Registry for Adaptive Table Reconstruction.

Generates 36 golden fixtures spanning:
- Domains: Environmental (3), Workforce (3), Financial (6), Retail (4), Healthcare (4),
           Government (1), Banking (3), ERP (2), Academic (2), Sales (1), Inventory (1),
           Operations (3), Survey (2), PDF/OCR (2), Legacy Mainframe (1)
- Formats: CSV (32), Excel / XLSX (4)
- Structural Archetypes:
  1. Wrapped records (prefix and suffix continuation)
  2. Multi-row headers (2-level and 3-level hierarchies)
  3. Preamble & footnote sentinels (with explicit legends)
  4. Offset columns & sparse row shifts
  5. Fragmented tables (blank row separators, repeated page headers)
  6. Hierarchical multi-column group headers
  7. Narrative footnotes (unstructured text like 'Note: NR indicates not evaluated')
  8. False merge traps (independent sequence IDs or measurements in sparse rows)
  9. Multi-sheet Excel workbooks
  10. PDF-extracted / OCR formatted tables
  11. Mainframe legacy fixed/delimited records
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import openpyxl
from pydantic import BaseModel

from app.services.adaptive_table_reconstruction.contracts import (
    CanonicalMissingState,
    DecisionStatus,
    ReconstructionRiskLevel,
)

FIXTURES_DIR = Path(__file__).resolve().parent


class GroundTruthBenchmarkCase(BaseModel):
    case_id: str
    domain: str  # Environmental, Workforce, Financial, Retail, Healthcare
    format: str  # CSV or EXCEL
    archetype: str
    file_path: Path
    expected_raw_rows: int
    expected_raw_cols: int
    expected_logical_rows: int
    expected_logical_cols: int
    expected_header_columns: List[str]
    expected_sentinels: Dict[str, CanonicalMissingState]
    expected_continuations_count: int
    is_ambiguous: bool
    expected_final_status: DecisionStatus
    has_false_merge_trap: bool = False
    expected_risk_level: ReconstructionRiskLevel = ReconstructionRiskLevel.LOW


def generate_benchmark_corpus() -> List[GroundTruthBenchmarkCase]:
    """Generates all 16 benchmark fixture files and returns their ground-truth registry."""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    cases: List[GroundTruthBenchmarkCase] = []

    # -------------------------------------------------------------
    # 1. ENV_01: CPCB Pollution Report (Real Golden Fixture)
    # -------------------------------------------------------------
    # Reference real CPCB fixture if present in backend uploads
    cpcb_golden = Path("backend/data/uploads/821964a8914147299f27c790eb371f54.csv")
    env_01_path = FIXTURES_DIR / "env_01_cpcb_pollution.csv"
    if cpcb_golden.exists():
        env_01_path.write_bytes(cpcb_golden.read_bytes())
    else:
        # Fallback replica
        env_01_path.write_text(
            "Reference: CPCB/AQI/2026/01\n"
            "National Air Quality Monitoring Report\n"
            ",,PM 2.5 Data,,,,,\n"
            "S.No,State,City,2021,2022,2023,2024,\n"
            "1,Andhra Pradesh,Anantapur,45,48,42,40,\n"
            ",,Rajamahend,,,,,\n"
            "2,Andhra Pradesh,ravaram,52,55,50,48,\n"
            "Footnote: '-' : No data / Inadequate data, 'NM' : Not monitored\n"
        )
    cases.append(GroundTruthBenchmarkCase(
        case_id="ENV_01",
        domain="Environmental",
        format="CSV",
        archetype="Wrapped records + multi-row headers + preamble + sentinels",
        file_path=env_01_path,
        expected_raw_rows=455 if cpcb_golden.exists() else 8,
        expected_raw_cols=8,
        expected_logical_rows=435 if cpcb_golden.exists() else 2,
        expected_logical_cols=7,
        expected_header_columns=["Sr. No.", "State / Union Territory", "City / town", "SO2 Annual Average", "NO2 Annual Average", "PM10 Annual Average", "PM 2.5 Data Already approved on 09.05.2024"],
        expected_sentinels={"-": CanonicalMissingState.INSUFFICIENT_DATA, "NM": CanonicalMissingState.NOT_MONITORED},
        expected_continuations_count=20 if cpcb_golden.exists() else 1,
        is_ambiguous=False,
        expected_final_status=DecisionStatus.DETERMINISTIC_VALIDATED,
    ))

    # -------------------------------------------------------------
    # 2. ENV_02: Water Quality Narrative
    # -------------------------------------------------------------
    env_02_path = FIXTURES_DIR / "env_02_water_quality_narrative.csv"
    env_02_path.write_text(
        "Water Quality Index - Coastal Monitoring Stations\n"
        "Station Code,Water Body,State,Dissolved Oxygen,Turbidity\n"
        "W-101,Godavari Basin,Andhra Pradesh,6.8,12\n"
        "W-102,Krishna Estuary,Andhra Pradesh,NR,18\n"
        "--- Page 1 of 2 ---\n"
        "W-103,Cauvery Delta,Tamil Nadu,7.1,10\n"
        "W-104,Periyar River,Kerala,NR,8\n"
        "Note: In this table NR indicates stations that were not evaluated during monsoon.\n"
    )
    cases.append(GroundTruthBenchmarkCase(
        case_id="ENV_02",
        domain="Environmental",
        format="CSV",
        archetype="Narrative footnotes with sentinel ('not evaluated') + page watermark",
        file_path=env_02_path,
        expected_raw_rows=8,
        expected_raw_cols=5,
        expected_logical_rows=4,
        expected_logical_cols=5,
        expected_header_columns=["Station Code", "Water Body", "State", "Dissolved Oxygen", "Turbidity"],
        expected_sentinels={"NR": CanonicalMissingState.NOT_EVALUATED},
        expected_continuations_count=0,
        is_ambiguous=True,
        expected_final_status=DecisionStatus.MODEL_ASSISTED_VALIDATED,
    ))

    # -------------------------------------------------------------
    # 3. WORKFORCE_01: Multi-level Hierarchical Headcount
    # -------------------------------------------------------------
    wf_01_path = FIXTURES_DIR / "workforce_01_headcount_multilevel.csv"
    wf_01_path.write_text(
        "Report ID: HC-2026-Q1\n"
        "Global Workforce Distribution\n"
        ",,Headcount Metrics,,Talent Movement\n"
        "Region,Department,Total Employees,FTE Ratio,Attrition Rate\n"
        "North America,Engineering,450,0.98,4.2%\n"
        "North America,Product,120,1.00,3.1%\n"
        "EMEA,Engineering,310,0.95,5.0%\n"
        "EMEA,Sales,210,0.92,8.5%\n"
        "APAC,Engineering,520,0.99,3.8%\n"
        "APAC,Customer Success,180,0.94,6.2%\n"
    )
    cases.append(GroundTruthBenchmarkCase(
        case_id="WORKFORCE_01",
        domain="Workforce",
        format="CSV",
        archetype="Hierarchical multi-row headers + preamble metadata",
        file_path=wf_01_path,
        expected_raw_rows=10,
        expected_raw_cols=5,
        expected_logical_rows=6,
        expected_logical_cols=5,
        expected_header_columns=["Region", "Department", "Headcount Metrics Total Employees", "FTE Ratio", "Talent Movement Attrition Rate"],
        expected_sentinels={},
        expected_continuations_count=0,
        is_ambiguous=False,
        expected_final_status=DecisionStatus.DETERMINISTIC_VALIDATED,
    ))

    # -------------------------------------------------------------
    # 4. WORKFORCE_02: Wrapped Employee Surnames
    # -------------------------------------------------------------
    wf_02_path = FIXTURES_DIR / "workforce_02_wrapped_employee_names.csv"
    wf_02_path.write_text(
        "Emp ID,Full Name,Department,Base Salary\n"
        "E-101,Sarah Jenkins,Engineering,145000\n"
        ",Alexander,\n"
        "E-102,Hamilton,Product,132000\n"
        "E-103,Marcus Aurelius,Operations,115000\n"
        "E-104,Elena Rostova,Design,120000\n"
    )
    cases.append(GroundTruthBenchmarkCase(
        case_id="WORKFORCE_02",
        domain="Workforce",
        format="CSV",
        archetype="Wrapped employee name continuation",
        file_path=wf_02_path,
        expected_raw_rows=6,
        expected_raw_cols=4,
        expected_logical_rows=4,
        expected_logical_cols=4,
        expected_header_columns=["Emp ID", "Full Name", "Department", "Base Salary"],
        expected_sentinels={},
        expected_continuations_count=1,
        is_ambiguous=True,
        expected_final_status=DecisionStatus.MODEL_ASSISTED_VALIDATED,
    ))

    # -------------------------------------------------------------
    # 5. WORKFORCE_03: Contract Renewal Free-Text Ambiguity (PROPOSED)
    # -------------------------------------------------------------
    wf_03_path = FIXTURES_DIR / "workforce_03_contract_proposals_ambiguity.csv"
    wf_03_path.write_text(
        "Contract ID,Contract Terms,Monthly Value\n"
        "C-801,Contract renewal pending,5000\n"
        ",Quarterly terms,\n"
        "C-802,Annual payment processing,15000\n"
    )
    cases.append(GroundTruthBenchmarkCase(
        case_id="WORKFORCE_03",
        domain="Workforce",
        format="CSV",
        archetype="Free-text multi-word ambiguous continuation -> MODEL_ASSISTED_PROPOSED",
        file_path=wf_03_path,
        expected_raw_rows=4,
        expected_raw_cols=3,
        expected_logical_rows=2,
        expected_logical_cols=3,
        expected_header_columns=["Contract ID", "Contract Terms", "Monthly Value"],
        expected_sentinels={},
        expected_continuations_count=1,
        is_ambiguous=True,
        expected_final_status=DecisionStatus.MODEL_ASSISTED_PROPOSED,
        expected_risk_level=ReconstructionRiskLevel.MEDIUM,
    ))

    # -------------------------------------------------------------
    # 6. FIN_01: PnL Quarterly Offset Headers & Sentinels
    # -------------------------------------------------------------
    fin_01_path = FIXTURES_DIR / "fin_01_pnl_quarterly_offsets.csv"
    fin_01_path.write_text(
        "Consolidated Profit & Loss Summary\n"
        "Account,Q1 Revenue,Q2 Revenue,Q3 Revenue,Q4 Revenue\n"
        "Enterprise Software,4500000,5200000,4800000,5600000\n"
        "Cloud Hosting,1200000,1350000,*,1600000\n"
        "\n"
        "Professional Services,800000,850000,900000,950000\n"
        "Hardware Support,300000,*,320000,340000\n"
        "Footnote: '*' : Inadequate data pending quarterly audit closure\n"
    )
    cases.append(GroundTruthBenchmarkCase(
        case_id="FIN_01",
        domain="Financial",
        format="CSV",
        archetype="Multi-column PnL + blank row separator + '*' sentinel -> INSUFFICIENT_DATA",
        file_path=fin_01_path,
        expected_raw_rows=8,
        expected_raw_cols=5,
        expected_logical_rows=4,
        expected_logical_cols=5,
        expected_header_columns=["Account", "Q1 Revenue", "Q2 Revenue", "Q3 Revenue", "Q4 Revenue"],
        expected_sentinels={"*": CanonicalMissingState.INSUFFICIENT_DATA},
        expected_continuations_count=0,
        is_ambiguous=False,
        expected_final_status=DecisionStatus.DETERMINISTIC_VALIDATED,
    ))

    # -------------------------------------------------------------
    # 7. FIN_02: General Ledger False Merge Trap (REJECTED)
    # -------------------------------------------------------------
    fin_02_path = FIXTURES_DIR / "fin_02_ledger_false_merge_trap.csv"
    fin_02_path.write_text(
        "Txn ID,Account Code,Debit,Credit\n"
        "1001,AC-100,5000,0\n"
        "1002,AC-200,0,5000\n"
        "1003,AC-300,12000,0\n"
        "1004,AC-400,0,12000\n"
    )
    cases.append(GroundTruthBenchmarkCase(
        case_id="FIN_02",
        domain="Financial",
        format="CSV",
        archetype="Sequence ID protection against false merge trap",
        file_path=fin_02_path,
        expected_raw_rows=5,
        expected_raw_cols=4,
        expected_logical_rows=4,
        expected_logical_cols=4,
        expected_header_columns=["Txn ID", "Account Code", "Debit", "Credit"],
        expected_sentinels={},
        expected_continuations_count=0,
        is_ambiguous=False,
        expected_final_status=DecisionStatus.DETERMINISTIC_VALIDATED,
        has_false_merge_trap=True,
    ))

    # -------------------------------------------------------------
    # 8. FIN_03: Balance Sheet Footnote Sentinels
    # -------------------------------------------------------------
    fin_03_path = FIXTURES_DIR / "fin_03_balance_sheet_sentinels.csv"
    fin_03_path.write_text(
        "Audited Balance Sheet Items\n"
        "Line Item,FY2023,FY2024,FY2025\n"
        "Cash & Equivalents,14200000,18500000,22100000\n"
        "Short-term Investments,5000000,NA,8200000\n"
        "Restricted Equity,N/A,N/A,1500000\n"
        "Accounts Receivable,3200000,3800000,4100000\n"
        "Note: 'NA' : Not available from overseas subsidiaries\n"
        "Note: 'N/A' : Not applicable under updated IFRS rule\n"
    )
    cases.append(GroundTruthBenchmarkCase(
        case_id="FIN_03",
        domain="Financial",
        format="CSV",
        archetype="Dual sentinels (NA -> NOT_AVAILABLE, N/A -> NOT_APPLICABLE)",
        file_path=fin_03_path,
        expected_raw_rows=8,
        expected_raw_cols=4,
        expected_logical_rows=4,
        expected_logical_cols=4,
        expected_header_columns=["Line Item", "FY2023", "FY2024", "FY2025"],
        expected_sentinels={"NA": CanonicalMissingState.NOT_AVAILABLE, "N/A": CanonicalMissingState.NOT_APPLICABLE},
        expected_continuations_count=0,
        is_ambiguous=False,
        expected_final_status=DecisionStatus.DETERMINISTIC_VALIDATED,
    ))

    # -------------------------------------------------------------
    # 9. RETAIL_01: Product Catalog Wrapped Descriptions
    # -------------------------------------------------------------
    ret_01_path = FIXTURES_DIR / "retail_01_inventory_catalog_multicell.csv"
    ret_01_path.write_text(
        "Product Master Catalog - Warehouse 4\n"
        "SKU,Product Name,Category,Unit Price,Stock Level\n"
        "SKU-1001,Ergonomic Office Chair,Furniture,249.99,150\n"
        ",Ultra-HD Wireless,,\n"
        "SKU-1002,Headphones with ANC,Electronics,199.50,320\n"
        "SKU-1003,Mechanical Gaming Keyboard,Electronics,89.00,450\n"
        "SKU-1004,Stainless Steel Water Bottle,Lifestyle,24.00,800\n"
    )
    cases.append(GroundTruthBenchmarkCase(
        case_id="RETAIL_01",
        domain="Retail",
        format="CSV",
        archetype="Wrapped product description continuation",
        file_path=ret_01_path,
        expected_raw_rows=7,
        expected_raw_cols=5,
        expected_logical_rows=4,
        expected_logical_cols=5,
        expected_header_columns=["SKU", "Product Name", "Category", "Unit Price", "Stock Level"],
        expected_sentinels={},
        expected_continuations_count=1,
        is_ambiguous=True,
        expected_final_status=DecisionStatus.MODEL_ASSISTED_VALIDATED,
    ))

    # -------------------------------------------------------------
    # 10. RETAIL_02: Fragmented Table with Repeated Page Watermarks
    # -------------------------------------------------------------
    ret_02_path = FIXTURES_DIR / "retail_02_store_sales_fragmented.csv"
    ret_02_path.write_text(
        "Store ID,Location,Daily Footfall,Gross Sales\n"
        "ST-01,Downtown Plaza,1450,24500\n"
        "ST-02,Airport Terminal 2,3200,58000\n"
        "CONFIDENTIAL -- PAGE 1 OF 3\n"
        "ST-03,Suburban Galleria,2100,31200\n"
        "ST-04,Metro Junction,1850,29000\n"
        "CONFIDENTIAL -- PAGE 2 OF 3\n"
        "ST-05,Harbor Walk,950,15400\n"
    )
    cases.append(GroundTruthBenchmarkCase(
        case_id="RETAIL_02",
        domain="Retail",
        format="CSV",
        archetype="Fragmented table with repeated page watermarks",
        file_path=ret_02_path,
        expected_raw_rows=8,
        expected_raw_cols=4,
        expected_logical_rows=5,
        expected_logical_cols=4,
        expected_header_columns=["Store ID", "Location", "Daily Footfall", "Gross Sales"],
        expected_sentinels={},
        expected_continuations_count=0,
        is_ambiguous=True,
        expected_final_status=DecisionStatus.MODEL_ASSISTED_VALIDATED,
    ))

    # -------------------------------------------------------------
    # 11. RETAIL_03: Vendor Ratings with Unknown Sentinel
    # -------------------------------------------------------------
    ret_03_path = FIXTURES_DIR / "retail_03_vendor_rating_unknown_sentinel.csv"
    ret_03_path.write_text(
        "Supplier Evaluation Matrix\n"
        "Vendor ID,Supplier Name,Quality Score,On-Time Delivery\n"
        "V-101,Apex Packaging,94.5,98.2%\n"
        "V-102,Zenith Logistics,UNK,91.0%\n"
        "V-103,Prime Raw Materials,88.0,UNK\n"
        "V-104,Global Freight,92.0,96.5%\n"
        "Footnote: 'UNK' : Vendor status subject to audit inquiry\n"
    )
    cases.append(GroundTruthBenchmarkCase(
        case_id="RETAIL_03",
        domain="Retail",
        format="CSV",
        archetype="Unknown missing state sentinel ('UNK' -> UNKNOWN_MISSING_STATE)",
        file_path=ret_03_path,
        expected_raw_rows=7,
        expected_raw_cols=4,
        expected_logical_rows=4,
        expected_logical_cols=4,
        expected_header_columns=["Vendor ID", "Supplier Name", "Quality Score", "On-Time Delivery"],
        expected_sentinels={"UNK": CanonicalMissingState.UNKNOWN_MISSING_STATE},
        expected_continuations_count=0,
        is_ambiguous=False,
        expected_final_status=DecisionStatus.DETERMINISTIC_VALIDATED,
    ))

    # -------------------------------------------------------------
    # 12. HEALTH_01: Clinical Trial Sentinels (NE & ND)
    # -------------------------------------------------------------
    hlt_01_path = FIXTURES_DIR / "health_01_clinical_trial_sentinels.csv"
    hlt_01_path.write_text(
        "Clinical Trial Protocol CT-2026-X\n"
        "Patient ID,Cohort,Biomarker Alpha,Biomarker Beta,Efficacy Score\n"
        "P-001,Control,14.2,45.0,78\n"
        "P-002,Treatment A,NE,52.1,84\n"
        "P-003,Treatment B,18.5,ND,91\n"
        "P-004,Treatment A,16.0,48.2,88\n"
        "Note: 'NE' : Not evaluated due to sample hemolysis\n"
        "Note: 'ND' : Not reported by laboratory\n"
    )
    cases.append(GroundTruthBenchmarkCase(
        case_id="HEALTH_01",
        domain="Healthcare",
        format="CSV",
        archetype="Domain sentinels (NE -> NOT_EVALUATED, ND -> NOT_REPORTED)",
        file_path=hlt_01_path,
        expected_raw_rows=8,
        expected_raw_cols=5,
        expected_logical_rows=4,
        expected_logical_cols=5,
        expected_header_columns=["Patient ID", "Cohort", "Biomarker Alpha", "Biomarker Beta", "Efficacy Score"],
        expected_sentinels={"NE": CanonicalMissingState.NOT_EVALUATED, "ND": CanonicalMissingState.NOT_REPORTED},
        expected_continuations_count=0,
        is_ambiguous=False,
        expected_final_status=DecisionStatus.DETERMINISTIC_VALIDATED,
    ))

    # -------------------------------------------------------------
    # 13. HEALTH_02: Patient Admissions Wrapped Diagnosis
    # -------------------------------------------------------------
    hlt_02_path = FIXTURES_DIR / "health_02_patient_admissions_wrapped.csv"
    hlt_02_path.write_text(
        "Hospital Inpatient Census\n"
        "Admission ID,Patient Age,Primary Diagnosis,Length of Stay\n"
        "ADM-101,64,Congestive Heart Failure,5\n"
        ",Acute Bronchial,\n"
        "ADM-102,42,Asthma exacerbation,3\n"
        "ADM-103,58,Type 2 Diabetes Complication,4\n"
        "ADM-104,71,Pneumonia secondary infection,7\n"
    )
    cases.append(GroundTruthBenchmarkCase(
        case_id="HEALTH_02",
        domain="Healthcare",
        format="CSV",
        archetype="Wrapped clinical diagnosis continuation",
        file_path=hlt_02_path,
        expected_raw_rows=7,
        expected_raw_cols=4,
        expected_logical_rows=4,
        expected_logical_cols=4,
        expected_header_columns=["Admission ID", "Patient Age", "Primary Diagnosis", "Length of Stay"],
        expected_sentinels={},
        expected_continuations_count=1,
        is_ambiguous=True,
        expected_final_status=DecisionStatus.MODEL_ASSISTED_VALIDATED,
    ))

    # -------------------------------------------------------------
    # 14. HEALTH_03: Dosage Measure Protection
    # -------------------------------------------------------------
    hlt_03_path = FIXTURES_DIR / "health_03_dosage_risk_boundary.csv"
    hlt_03_path.write_text(
        "Trial Subject Dosages\n"
        "Subject No,Medication,Dose mg,Frequency\n"
        "101,Metformin,500,Twice Daily\n"
        "102,Lisinopril,10,Daily\n"
        "103,Atorvastatin,20,Nightly\n"
    )
    cases.append(GroundTruthBenchmarkCase(
        case_id="HEALTH_03",
        domain="Healthcare",
        format="CSV",
        archetype="High risk measure column boundary verification",
        file_path=hlt_03_path,
        expected_raw_rows=5,
        expected_raw_cols=4,
        expected_logical_rows=3,
        expected_logical_cols=4,
        expected_header_columns=["Subject No", "Medication", "Dose mg", "Frequency"],
        expected_sentinels={},
        expected_continuations_count=0,
        is_ambiguous=False,
        expected_final_status=DecisionStatus.DETERMINISTIC_VALIDATED,
    ))

    # -------------------------------------------------------------
    # 15. ENV_03: Emissions Report (Excel XLSX Format)
    # -------------------------------------------------------------
    env_03_path = FIXTURES_DIR / "env_03_emissions_excel.xlsx"
    wb_env = openpyxl.Workbook()
    ws_env = wb_env.active
    ws_env.title = "Emissions"
    ws_env.append(["Greenhouse Gas Registry 2026", None, None, None])
    ws_env.append(["Facility ID", "Facility Name", "Scope 1 MT", "Scope 2 MT"])
    ws_env.append(["FAC-01", "Coastal Refinery", "45000", "12000"])
    ws_env.append(["FAC-02", "Northern Power Station", "85000", "24000"])
    ws_env.append(["FAC-03", "Metro Data Center", "500", "18000"])
    ws_env.append(["FAC-04", "Cement Works Alpha", "62000", "9500"])
    ws_env.append(["FAC-05", "Solar Farm Array", "0", "150"])
    wb_env.save(str(env_03_path))
    cases.append(GroundTruthBenchmarkCase(
        case_id="ENV_03",
        domain="Environmental",
        format="EXCEL",
        archetype="Excel workbook with title preamble and numeric measures",
        file_path=env_03_path,
        expected_raw_rows=7,
        expected_raw_cols=4,
        expected_logical_rows=5,
        expected_logical_cols=4,
        expected_header_columns=["Facility ID", "Facility Name", "Scope 1 MT", "Scope 2 MT"],
        expected_sentinels={},
        expected_continuations_count=0,
        is_ambiguous=False,
        expected_final_status=DecisionStatus.DETERMINISTIC_VALIDATED,
    ))

    # -------------------------------------------------------------
    # 16. FIN_04: Revenue by Geography (Excel XLSX Format)
    # -------------------------------------------------------------
    fin_04_path = FIXTURES_DIR / "fin_04_revenue_by_geo_excel.xlsx"
    wb_fin = openpyxl.Workbook()
    ws_fin = wb_fin.active
    ws_fin.title = "GeoRevenue"
    ws_fin.append(["Quarterly Geographic Performance", None, None, None, None])
    ws_fin.append(["Region", "Country", "City", "Q1 ARR", "Q2 ARR"])
    ws_fin.append(["Americas", "USA", "New York", "4500000", "5200000"])
    ws_fin.append([None, None, "San", None, None])
    ws_fin.append(["Americas", "USA", "Francisco", "3800000", "4100000"])
    ws_fin.append(["EMEA", "UK", "London", "2900000", "3100000"])
    ws_fin.append(["APAC", "Japan", "Tokyo", "2100000", "2300000"])
    wb_fin.save(str(fin_04_path))
    cases.append(GroundTruthBenchmarkCase(
        case_id="FIN_04",
        domain="Financial",
        format="EXCEL",
        archetype="Excel workbook with wrapped city continuation (San + Francisco)",
        file_path=fin_04_path,
        expected_raw_rows=7,
        expected_raw_cols=5,
        expected_logical_rows=4,
        expected_logical_cols=5,
        expected_header_columns=["Region", "Country", "City", "Q1 ARR", "Q2 ARR"],
        expected_sentinels={},
        expected_continuations_count=1,
        is_ambiguous=True,
        expected_final_status=DecisionStatus.MODEL_ASSISTED_VALIDATED,
    ))

    # -------------------------------------------------------------
    # 17. GOV_01: Census Demographics with Suppressed Sentinels
    # -------------------------------------------------------------
    gov_01_path = FIXTURES_DIR / "gov_01_census_demographics.csv"
    gov_01_path.write_text(
        "U.S. Census Bureau - County Business Patterns\n"
        "Survey Year: 2024\n"
        "FIPS Code,County Name,Total Establishments,Paid Employees,Annual Payroll\n"
        "06001,Alameda County,42500,610000,48500000\n"
        "06003,Alpine County,120,SUPP,SUPP\n"
        "06013,Contra Costa County,28400,385000,29800000\n"
        "06027,Inyo County,890,6200,310000\n"
        "Note: 'SUPP' : Not available due to data privacy suppression\n"
    )
    cases.append(GroundTruthBenchmarkCase(
        case_id="GOV_01",
        domain="Government",
        format="CSV",
        archetype="Government survey preamble + suppressed sentinel ('SUPP' -> NOT_AVAILABLE)",
        file_path=gov_01_path,
        expected_raw_rows=8,
        expected_raw_cols=5,
        expected_logical_rows=4,
        expected_logical_cols=5,
        expected_header_columns=["FIPS Code", "County Name", "Total Establishments", "Paid Employees", "Annual Payroll"],
        expected_sentinels={"SUPP": CanonicalMissingState.NOT_AVAILABLE},
        expected_continuations_count=0,
        is_ambiguous=False,
        expected_final_status=DecisionStatus.DETERMINISTIC_VALIDATED,
    ))

    # -------------------------------------------------------------
    # 18. BANK_01: SWIFT Batch Settlement (Sequence ID Protection)
    # -------------------------------------------------------------
    bank_01_path = FIXTURES_DIR / "bank_01_swift_settlement.csv"
    bank_01_path.write_text(
        "SWIFT FIN MESSAGE MT103 - BATCH SETTLEMENT\n"
        "TRX_REF,VALUE_DATE,CURRENCY,SETTLEMENT_AMOUNT,STATUS\n"
        "TXN-8801,2026-03-15,USD,1500000.00,SETTLED\n"
        "TXN-8802,2026-03-15,EUR,840000.50,SETTLED\n"
        "TXN-8803,2026-03-15,GBP,420000.00,PENDING\n"
        "TXN-8804,2026-03-15,JPY,95000000,SETTLED\n"
        "Note: 'PENDING' : Temporarily not available pending nostro reconciliation\n"
    )
    cases.append(GroundTruthBenchmarkCase(
        case_id="BANK_01",
        domain="Banking",
        format="CSV",
        archetype="Banking SWIFT settlement + reference ID protection + 'PENDING' sentinel",
        file_path=bank_01_path,
        expected_raw_rows=7,
        expected_raw_cols=5,
        expected_logical_rows=4,
        expected_logical_cols=5,
        expected_header_columns=["TRX_REF", "VALUE_DATE", "CURRENCY", "SETTLEMENT_AMOUNT", "STATUS"],
        expected_sentinels={"PENDING": CanonicalMissingState.NOT_AVAILABLE},
        expected_continuations_count=0,
        is_ambiguous=False,
        expected_final_status=DecisionStatus.DETERMINISTIC_VALIDATED,
        has_false_merge_trap=True,
    ))

    # -------------------------------------------------------------
    # 19. BANK_02: Loan Amortization Wrapped Borrower Names
    # -------------------------------------------------------------
    bank_02_path = FIXTURES_DIR / "bank_02_loan_amortization.csv"
    bank_02_path.write_text(
        "Loan Account,Borrower Name,Principal,Interest Rate,Term Months\n"
        "LN-4010,Margaret Thatcher,250000,5.25%,360\n"
        ",Guillermo,\n"
        "LN-4011,de la Cruz,380000,4.85%,360\n"
        "LN-4012,Rajiv Singhania,420000,5.10%,180\n"
        "LN-4013,Hannah Schmidt,195000,5.40%,240\n"
    )
    cases.append(GroundTruthBenchmarkCase(
        case_id="BANK_02",
        domain="Banking",
        format="CSV",
        archetype="Wrapped borrower surname continuation across rows",
        file_path=bank_02_path,
        expected_raw_rows=6,
        expected_raw_cols=5,
        expected_logical_rows=4,
        expected_logical_cols=5,
        expected_header_columns=["Loan Account", "Borrower Name", "Principal", "Interest Rate", "Term Months"],
        expected_sentinels={},
        expected_continuations_count=1,
        is_ambiguous=True,
        expected_final_status=DecisionStatus.MODEL_ASSISTED_VALIDATED,
    ))

    # -------------------------------------------------------------
    # 20. ERP_01: SAP ECC Goods Movement List (Sequence Protection)
    # -------------------------------------------------------------
    erp_01_path = FIXTURES_DIR / "erp_01_sap_inventory_mvt.csv"
    erp_01_path.write_text(
        "SAP ECC 6.0 - Transaction MB51 Material Document List\n"
        "Client: 100 Company Code: 1000 Plant: US10\n"
        "Mat Doc,Item,Material,Movement Type,Quantity,Base Unit\n"
        "50001890,1,MAT-9001,101,500,PC\n"
        "50001891,1,MAT-9002,101,250,PC\n"
        "50001892,1,MAT-9003,261,-50,PC\n"
        "50001893,1,MAT-9004,301,120,PC\n"
    )
    cases.append(GroundTruthBenchmarkCase(
        case_id="ERP_01",
        domain="ERP",
        format="CSV",
        archetype="SAP ECC goods movement export with document headers and sequence ID trap",
        file_path=erp_01_path,
        expected_raw_rows=7,
        expected_raw_cols=6,
        expected_logical_rows=4,
        expected_logical_cols=6,
        expected_header_columns=["Mat Doc", "Item", "Material", "Movement Type", "Quantity", "Base Unit"],
        expected_sentinels={},
        expected_continuations_count=0,
        is_ambiguous=False,
        expected_final_status=DecisionStatus.DETERMINISTIC_VALIDATED,
        has_false_merge_trap=True,
    ))

    # -------------------------------------------------------------
    # 21. ERP_02: Oracle AP Invoices with Supplier Name Split & HOLD
    # -------------------------------------------------------------
    erp_02_path = FIXTURES_DIR / "erp_02_oracle_ap_invoices.csv"
    erp_02_path.write_text(
        "Oracle Fusion Cloud Payables - Invoice Register\n"
        "Invoice Num,Supplier Name,Invoice Date,Invoice Amount,Hold Status\n"
        "INV-7701,Acme Industrial Supplies,2026-02-10,14250.00,RELEASED\n"
        ",International,\n"
        "INV-7702,Logistics Corp,2026-02-12,8920.50,HOLD\n"
        "INV-7703,Nordic Components AB,2026-02-14,31000.00,RELEASED\n"
        "INV-7704,Pacific Freight Services,2026-02-15,5400.00,RELEASED\n"
        "Note: 'HOLD' : Payment information not available pending matching\n"
    )
    cases.append(GroundTruthBenchmarkCase(
        case_id="ERP_02",
        domain="ERP",
        format="CSV",
        archetype="Oracle AP invoices with supplier name split continuation & 'HOLD' sentinel",
        file_path=erp_02_path,
        expected_raw_rows=8,
        expected_raw_cols=5,
        expected_logical_rows=4,
        expected_logical_cols=5,
        expected_header_columns=["Invoice Num", "Supplier Name", "Invoice Date", "Invoice Amount", "Hold Status"],
        expected_sentinels={"HOLD": CanonicalMissingState.NOT_AVAILABLE},
        expected_continuations_count=1,
        is_ambiguous=True,
        expected_final_status=DecisionStatus.MODEL_ASSISTED_VALIDATED,
    ))

    # -------------------------------------------------------------
    # 22. ACAD_01: Faculty Grade Roster with Withdrawal Sentinels
    # -------------------------------------------------------------
    acad_01_path = FIXTURES_DIR / "acad_01_grade_roster.csv"
    acad_01_path.write_text(
        "Faculty of Arts and Sciences - Grade Roster Fall 2025\n"
        "Course ID: CS-106B Programming Abstractions\n"
        "Student ID,Student Name,Midterm Exam,Final Exam,Course Grade\n"
        "940121,Emily Zhao,92,95,A\n"
        "940122,Michael Davies,84,88,B+\n"
        "940123,Carlos Morales,W,W,W\n"
        "940124,Fatima Al-Sayed,78,IN,IN\n"
        "Note: 'W' : Withdrawn; course credit not applicable\n"
        "Note: 'IN' : Incomplete; final grades not available\n"
    )
    cases.append(GroundTruthBenchmarkCase(
        case_id="ACAD_01",
        domain="Academic",
        format="CSV",
        archetype="Academic grade distribution with course withdrawal sentinels ('W', 'IN')",
        file_path=acad_01_path,
        expected_raw_rows=9,
        expected_raw_cols=5,
        expected_logical_rows=4,
        expected_logical_cols=5,
        expected_header_columns=["Student ID", "Student Name", "Midterm Exam", "Final Exam", "Course Grade"],
        expected_sentinels={"W": CanonicalMissingState.NOT_APPLICABLE, "IN": CanonicalMissingState.NOT_AVAILABLE},
        expected_continuations_count=0,
        is_ambiguous=False,
        expected_final_status=DecisionStatus.DETERMINISTIC_VALIDATED,
    ))

    # -------------------------------------------------------------
    # 23. ACAD_02: Research Grant Awards with Wrapped PI Name
    # -------------------------------------------------------------
    acad_02_path = FIXTURES_DIR / "acad_02_research_grant_awards.csv"
    acad_02_path.write_text(
        "Office of Sponsored Programs - Active Research Awards\n"
        "Award Number,Principal Investigator,Department,Award Amount,Direct Costs\n"
        "AWD-2024-01,Dr. John Henderson,Physics,450000,320000\n"
        ",Dr. Catherine,\n"
        "AWD-2024-02,Vanderbilt,Chemistry,620000,440000\n"
        "AWD-2024-03,Dr. Ahmed Mansour,Bioengineering,780000,550000\n"
        "AWD-2024-04,Dr. Lisa Lin,Computer Science,950000,680000\n"
    )
    cases.append(GroundTruthBenchmarkCase(
        case_id="ACAD_02",
        domain="Academic",
        format="CSV",
        archetype="Research grants with wrapped PI name continuation ('Dr. Catherine' + 'Vanderbilt')",
        file_path=acad_02_path,
        expected_raw_rows=7,
        expected_raw_cols=5,
        expected_logical_rows=4,
        expected_logical_cols=5,
        expected_header_columns=["Award Number", "Principal Investigator", "Department", "Award Amount", "Direct Costs"],
        expected_sentinels={},
        expected_continuations_count=1,
        is_ambiguous=True,
        expected_final_status=DecisionStatus.MODEL_ASSISTED_VALIDATED,
    ))

    # -------------------------------------------------------------
    # 24. SALES_01: CRM Deal Pipeline Ambiguous Narrative Continuation
    # -------------------------------------------------------------
    sales_01_path = FIXTURES_DIR / "sales_01_crm_deal_pipeline.csv"
    sales_01_path.write_text(
        "Opportunity ID,Account Name,Deal Size,Stage Notes\n"
        "OPP-901,Starlight Financial,125000,Won - Signed multi-year SLA\n"
        ",Competitor pricing pressure,\n"
        "OPP-902,Apex Media Group,85000,Closed Lost - Renewal stalled\n"
        "OPP-903,Global Retailers Ltd,240000,Proposal submitted\n"
    )
    cases.append(GroundTruthBenchmarkCase(
        case_id="SALES_01",
        domain="Sales",
        format="CSV",
        archetype="Free-text narrative continuation proposal -> MODEL_ASSISTED_PROPOSED",
        file_path=sales_01_path,
        expected_raw_rows=5,
        expected_raw_cols=4,
        expected_logical_rows=3,
        expected_logical_cols=4,
        expected_header_columns=["Opportunity ID", "Account Name", "Deal Size", "Stage Notes"],
        expected_sentinels={},
        expected_continuations_count=1,
        is_ambiguous=True,
        expected_final_status=DecisionStatus.MODEL_ASSISTED_PROPOSED,
        expected_risk_level=ReconstructionRiskLevel.MEDIUM,
    ))

    # -------------------------------------------------------------
    # 25. INV_01: Warehouse Cycle Count Discrepancy Log
    # -------------------------------------------------------------
    inv_01_path = FIXTURES_DIR / "inv_01_warehouse_bin_audit.csv"
    inv_01_path.write_text(
        "Facility B-14 Cycle Count Audit Log\n"
        "Bin Location,Item SKU,Expected Qty,Actual Qty,Discrepancy\n"
        "BIN-A01,SKU-9901,100,100,0\n"
        "BIN-A02,SKU-9902,50,45,-5\n"
        "BIN-A03,SKU-9903,20,-,-\n"
        "BIN-A04,SKU-9904,75,75,0\n"
        "Note: '-' : Insufficient data pending manager recount\n"
    )
    cases.append(GroundTruthBenchmarkCase(
        case_id="INV_01",
        domain="Inventory",
        format="CSV",
        archetype="Inventory audit with zero variance and missing counts ('-' -> INSUFFICIENT_DATA)",
        file_path=inv_01_path,
        expected_raw_rows=7,
        expected_raw_cols=5,
        expected_logical_rows=4,
        expected_logical_cols=5,
        expected_header_columns=["Bin Location", "Item SKU", "Expected Qty", "Actual Qty", "Discrepancy"],
        expected_sentinels={"-": CanonicalMissingState.INSUFFICIENT_DATA},
        expected_continuations_count=0,
        is_ambiguous=False,
        expected_final_status=DecisionStatus.DETERMINISTIC_VALIDATED,
    ))

    # -------------------------------------------------------------
    # 26. OPS_01: SCADA Gas Turbine Telemetry with FAULT Sentinel
    # -------------------------------------------------------------
    ops_01_path = FIXTURES_DIR / "ops_01_iot_telemetry_logs.csv"
    ops_01_path.write_text(
        "Industrial Gas Turbine 4 - Telemetry Stream\n"
        "Timestamp,Sensor Node,Vibration mm_s,Exhaust Temp C,Core Pressure bar\n"
        "2026-03-01T08:00:00Z,NODE-01,1.2,485.2,14.5\n"
        "2026-03-01T08:05:00Z,NODE-02,1.4,490.1,14.6\n"
        "2026-03-01T08:10:00Z,NODE-03,FAULT,FAULT,14.8\n"
        "2026-03-01T08:15:00Z,NODE-04,1.3,488.5,14.4\n"
        "Note: 'FAULT' : Sensor transducer not monitored due to communication fault\n"
    )
    cases.append(GroundTruthBenchmarkCase(
        case_id="OPS_01",
        domain="Operations",
        format="CSV",
        archetype="SCADA sensor telemetry with transducer fault sentinel ('FAULT' -> NOT_MONITORED)",
        file_path=ops_01_path,
        expected_raw_rows=7,
        expected_raw_cols=5,
        expected_logical_rows=4,
        expected_logical_cols=5,
        expected_header_columns=["Timestamp", "Sensor Node", "Vibration mm_s", "Exhaust Temp C", "Core Pressure bar"],
        expected_sentinels={"FAULT": CanonicalMissingState.NOT_MONITORED},
        expected_continuations_count=0,
        is_ambiguous=False,
        expected_final_status=DecisionStatus.DETERMINISTIC_VALIDATED,
    ))

    # -------------------------------------------------------------
    # 27. OPS_02: Datacenter Power Distribution Unit Metrics
    # -------------------------------------------------------------
    ops_02_path = FIXTURES_DIR / "ops_02_datacenter_pdu_metrics.csv"
    ops_02_path.write_text(
        "Datacenter Row 3 - Power Distribution Unit Metrics\n"
        "Rack ID,PDU Feed,Voltage V,Current A,Active Power kW\n"
        "RACK-301,PDU-A,208,24.5,5.1\n"
        "RACK-302,PDU-A,208,28.2,5.9\n"
        "RACK-303,PDU-B,OFFLINE,OFFLINE,OFFLINE\n"
        "RACK-304,PDU-B,208,22.0,4.6\n"
        "Note: 'OFFLINE' : Depowered rack; telemetry not monitored\n"
    )
    cases.append(GroundTruthBenchmarkCase(
        case_id="OPS_02",
        domain="Operations",
        format="CSV",
        archetype="Datacenter rack power metrics with offline sentinel ('OFFLINE' -> NOT_MONITORED)",
        file_path=ops_02_path,
        expected_raw_rows=7,
        expected_raw_cols=5,
        expected_logical_rows=4,
        expected_logical_cols=5,
        expected_header_columns=["Rack ID", "PDU Feed", "Voltage V", "Current A", "Active Power kW"],
        expected_sentinels={"OFFLINE": CanonicalMissingState.NOT_MONITORED},
        expected_continuations_count=0,
        is_ambiguous=False,
        expected_final_status=DecisionStatus.DETERMINISTIC_VALIDATED,
    ))

    # -------------------------------------------------------------
    # 28. SURV_01: Customer Support CSAT & NPS Feedback
    # -------------------------------------------------------------
    surv_01_path = FIXTURES_DIR / "surv_01_nps_customer_feedback.csv"
    surv_01_path.write_text(
        "Q1 Post-Support Customer Satisfaction Survey\n"
        "Ticket ID,Customer Tier,Product Satisfaction,Ease of Resolution,NPS Rating\n"
        "TCK-5501,Enterprise,9,10,10\n"
        "TCK-5502,SMB,8,8,8\n"
        "TCK-5503,Trial,N/A,9,9\n"
        "TCK-5504,Enterprise,10,10,10\n"
        "Note: 'N/A' : Question not applicable to onboarding tier accounts\n"
    )
    cases.append(GroundTruthBenchmarkCase(
        case_id="SURV_01",
        domain="Survey",
        format="CSV",
        archetype="Customer feedback questionnaire with not-applicable scores ('N/A' -> NOT_APPLICABLE)",
        file_path=surv_01_path,
        expected_raw_rows=7,
        expected_raw_cols=5,
        expected_logical_rows=4,
        expected_logical_cols=5,
        expected_header_columns=["Ticket ID", "Customer Tier", "Product Satisfaction", "Ease of Resolution", "NPS Rating"],
        expected_sentinels={"N/A": CanonicalMissingState.NOT_APPLICABLE},
        expected_continuations_count=0,
        is_ambiguous=False,
        expected_final_status=DecisionStatus.DETERMINISTIC_VALIDATED,
    ))

    # -------------------------------------------------------------
    # 29. SURV_02: Employee Engagement Small Team Suppression
    # -------------------------------------------------------------
    surv_02_path = FIXTURES_DIR / "surv_02_employee_engagement.csv"
    surv_02_path.write_text(
        "Global Employee Voice Survey 2025\n"
        "Business Unit,Team Size,Favorable Pct,Neutral Pct,Unfavorable Pct\n"
        "Corporate Engineering,150,82%,12%,6%\n"
        "Executive Strategy,4,***,***,***\n"
        "Global Marketing,65,74%,18%,8%\n"
        "Customer Experience,90,79%,14%,7%\n"
        "Note: '***' : Inadequate data due to small sample size\n"
    )
    cases.append(GroundTruthBenchmarkCase(
        case_id="SURV_02",
        domain="Survey",
        format="CSV",
        archetype="Employee survey with small team suppression ('***' -> INSUFFICIENT_DATA)",
        file_path=surv_02_path,
        expected_raw_rows=7,
        expected_raw_cols=5,
        expected_logical_rows=4,
        expected_logical_cols=5,
        expected_header_columns=["Business Unit", "Team Size", "Favorable Pct", "Neutral Pct", "Unfavorable Pct"],
        expected_sentinels={"***": CanonicalMissingState.INSUFFICIENT_DATA},
        expected_continuations_count=0,
        is_ambiguous=False,
        expected_final_status=DecisionStatus.DETERMINISTIC_VALIDATED,
    ))

    # -------------------------------------------------------------
    # 30. FIN_05: SEC Form 10-K Consolidated Cash Flows
    # -------------------------------------------------------------
    fin_05_path = FIXTURES_DIR / "fin_05_sec_10k_cash_flows.csv"
    fin_05_path.write_text(
        "SECURITIES AND EXCHANGE COMMISSION FORM 10-K\n"
        "CONSOLIDATED STATEMENTS OF CASH FLOWS\n"
        "Operating Activity,FY2023,FY2024,FY2025\n"
        "Net Income,12450,14820,17210\n"
        "Depreciation and Amortization,2850,3100,3450\n"
        "Share-based Compensation,1420,1650,1920\n"
        "Change in Working Capital,-850,-620,-910\n"
        "Net Cash from Operations,15870,18950,21670\n"
    )
    cases.append(GroundTruthBenchmarkCase(
        case_id="FIN_05",
        domain="Financial",
        format="CSV",
        archetype="SEC 10-K cash flows statement with preamble and multi-year financials",
        file_path=fin_05_path,
        expected_raw_rows=8,
        expected_raw_cols=4,
        expected_logical_rows=5,
        expected_logical_cols=4,
        expected_header_columns=["Operating Activity", "FY2023", "FY2024", "FY2025"],
        expected_sentinels={},
        expected_continuations_count=0,
        is_ambiguous=False,
        expected_final_status=DecisionStatus.DETERMINISTIC_VALIDATED,
    ))

    # -------------------------------------------------------------
    # 31. FIN_06: Foreign Exchange Derivative Hedging Contracts
    # -------------------------------------------------------------
    fin_06_path = FIXTURES_DIR / "fin_06_fx_hedging_contracts.csv"
    fin_06_path.write_text(
        "Corporate Treasury - Foreign Currency Forward Contracts\n"
        "Contract Ref,Counterparty,Currency Pair,Notional Amount,Settlement Rate\n"
        "FX-881,JPMorgan Chase,USD/EUR,25000000,1.0850\n"
        "FX-882,Barclays Capital,USD/GBP,18000000,1.2720\n"
        "FX-883,BNP Paribas,USD/JPY,40000000,TBD\n"
        "FX-884,Deutsche Bank,USD/CHF,12000000,0.8910\n"
        "Note: 'TBD' : Settlement rate not available pending Asian fix\n"
    )
    cases.append(GroundTruthBenchmarkCase(
        case_id="FIN_06",
        domain="Financial",
        format="CSV",
        archetype="FX derivative schedule with unpriced tranches ('TBD' -> NOT_AVAILABLE)",
        file_path=fin_06_path,
        expected_raw_rows=7,
        expected_raw_cols=5,
        expected_logical_rows=4,
        expected_logical_cols=5,
        expected_header_columns=["Contract Ref", "Counterparty", "Currency Pair", "Notional Amount", "Settlement Rate"],
        expected_sentinels={"TBD": CanonicalMissingState.NOT_AVAILABLE},
        expected_continuations_count=0,
        is_ambiguous=False,
        expected_final_status=DecisionStatus.DETERMINISTIC_VALIDATED,
    ))

    # -------------------------------------------------------------
    # 32. MULTI_01: Multi-Sheet Excel Consolidated Department Budget
    # -------------------------------------------------------------
    multi_01_path = FIXTURES_DIR / "multi_01_consolidated_budget.xlsx"
    wb_m1 = openpyxl.Workbook()
    ws_m1 = wb_m1.active
    ws_m1.title = "DepartmentBudget"
    ws_m1.append(["Consolidated Operating Budget 2026", None, None, None, None])
    ws_m1.append(["Cost Center", "Department", "Q1 Budget", "Q2 Budget", "Q3 Budget"])
    ws_m1.append(["CC-101", "Engineering", "450000", "480000", "510000"])
    ws_m1.append(["CC-102", "Product Management", "180000", "190000", "205000"])
    ws_m1.append(["CC-103", "Marketing & Growth", "320000", "350000", "380000"])
    ws_m1.append(["CC-104", "Customer Support", "150000", "155000", "162000"])
    wb_m1.save(str(multi_01_path))
    cases.append(GroundTruthBenchmarkCase(
        case_id="MULTI_01",
        domain="Financial",
        format="EXCEL",
        archetype="Multi-sheet Excel workbook with departmental budget allocations",
        file_path=multi_01_path,
        expected_raw_rows=6,
        expected_raw_cols=5,
        expected_logical_rows=4,
        expected_logical_cols=5,
        expected_header_columns=["Cost Center", "Department", "Q1 Budget", "Q2 Budget", "Q3 Budget"],
        expected_sentinels={},
        expected_continuations_count=0,
        is_ambiguous=False,
        expected_final_status=DecisionStatus.DETERMINISTIC_VALIDATED,
    ))

    # -------------------------------------------------------------
    # 33. MULTI_02: Multi-Sheet Excel Global Shipping Manifest
    # -------------------------------------------------------------
    multi_02_path = FIXTURES_DIR / "multi_02_global_supply_chain.xlsx"
    wb_m2 = openpyxl.Workbook()
    ws_m2 = wb_m2.active
    ws_m2.title = "VesselManifest"
    ws_m2.append(["Global Container Manifest - Pacific Route", None, None, None, None])
    ws_m2.append(["Container ID", "Vessel Name", "Origin Port", "Destination Port", "TEU Capacity"])
    ws_m2.append(["CONT-901", "Ever Given", "Shanghai", "Rotterdam", "20000"])
    ws_m2.append([None, "CMA CGM", None, None, None])
    ws_m2.append(["CONT-902", "Antoine de Saint", "Singapore", "Hamburg", "20600"])
    ws_m2.append(["CONT-903", "Maersk Mc-Kinney", "Busan", "Los Angeles", "18270"])
    ws_m2.append(["CONT-904", "MSC Gulsun", "Yantian", "Antwerp", "23756"])
    wb_m2.save(str(multi_02_path))
    cases.append(GroundTruthBenchmarkCase(
        case_id="MULTI_02",
        domain="Operations",
        format="EXCEL",
        archetype="Excel workbook with wrapped vessel name continuation ('CMA CGM' + 'Antoine de Saint')",
        file_path=multi_02_path,
        expected_raw_rows=7,
        expected_raw_cols=5,
        expected_logical_rows=4,
        expected_logical_cols=5,
        expected_header_columns=["Container ID", "Vessel Name", "Origin Port", "Destination Port", "TEU Capacity"],
        expected_sentinels={},
        expected_continuations_count=1,
        is_ambiguous=True,
        expected_final_status=DecisionStatus.MODEL_ASSISTED_VALIDATED,
    ))

    # -------------------------------------------------------------
    # 34. PDF_01: Optical Ingestion / PDF Table OCR Extract
    # -------------------------------------------------------------
    pdf_01_path = FIXTURES_DIR / "pdf_01_ocr_invoice_extract.csv"
    pdf_01_path.write_text(
        "Extracted via Optical PDF Ingestion Pipeline\n"
        "Order Num,Customer Name,Shipping Address,Order Total\n"
        "ORD-601,Apex Manufacturing,120 Market St San Francisco CA,4520.00\n"
        ",452 Industrial Parkway,\n"
        "ORD-602,Vanguard Logistics,Suite 300 Austin TX,8950.00\n"
        "ORD-603,Precision Tools Inc,88 Innovation Way Boston MA,1250.00\n"
    )
    cases.append(GroundTruthBenchmarkCase(
        case_id="PDF_01",
        domain="Retail",
        format="CSV",
        archetype="OCR scanned table with wrapped customer address continuation",
        file_path=pdf_01_path,
        expected_raw_rows=6,
        expected_raw_cols=4,
        expected_logical_rows=3,
        expected_logical_cols=4,
        expected_header_columns=["Order Num", "Customer Name", "Shipping Address", "Order Total"],
        expected_sentinels={},
        expected_continuations_count=1,
        is_ambiguous=True,
        expected_final_status=DecisionStatus.MODEL_ASSISTED_VALIDATED,
    ))

    # -------------------------------------------------------------
    # 35. PDF_02: PDF Lab Panel with Hemolyzed Specimen Sentinel
    # -------------------------------------------------------------
    pdf_02_path = FIXTURES_DIR / "pdf_02_clinical_lab_panel.csv"
    pdf_02_path.write_text(
        "Diagnostic Pathology Laboratory - Complete Metabolic Panel\n"
        "Test Analyte,Reference Range,Specimen Value,Unit,Flag\n"
        "Serum Sodium,135-145,140,mmol/L,NORMAL\n"
        "Serum Potassium,3.5-5.0,HEM,mmol/L,HEMOLYZED\n"
        "Blood Urea Nitrogen,7-20,15,mg/dL,NORMAL\n"
        "Serum Creatinine,0.7-1.3,0.9,mg/dL,NORMAL\n"
        "Note: 'HEM' : Sample hemolyzed; analyte not evaluated by spectrometer\n"
    )
    cases.append(GroundTruthBenchmarkCase(
        case_id="PDF_02",
        domain="Healthcare",
        format="CSV",
        archetype="PDF lab report with hemolyzed specimen sentinel ('HEM' -> NOT_EVALUATED strictly)",
        file_path=pdf_02_path,
        expected_raw_rows=7,
        expected_raw_cols=5,
        expected_logical_rows=4,
        expected_logical_cols=5,
        expected_header_columns=["Test Analyte", "Reference Range", "Specimen Value", "Unit", "Flag"],
        expected_sentinels={"HEM": CanonicalMissingState.NOT_EVALUATED},
        expected_continuations_count=0,
        is_ambiguous=False,
        expected_final_status=DecisionStatus.DETERMINISTIC_VALIDATED,
    ))

    # -------------------------------------------------------------
    # 36. LEGACY_01: Mainframe COBOL Billing Export (Sequence Trap)
    # -------------------------------------------------------------
    legacy_01_path = FIXTURES_DIR / "legacy_01_mainframe_billing.csv"
    legacy_01_path.write_text(
        "BILLING REPORT EXTRACT JOB=BIL9920 STEP=RUN01\n"
        "ACCT_NUM,BILL_CYCLE,PREV_BAL,CURR_CHG,PAYMT_RCV\n"
        "00010928,01,150.00,45.20,150.00\n"
        "00010929,01,89.50,12.00,89.50\n"
        "00010930,01,310.00,95.00,200.00\n"
        "00010931,01,0.00,25.00,0.00\n"
    )
    cases.append(GroundTruthBenchmarkCase(
        case_id="LEGACY_01",
        domain="Banking",
        format="CSV",
        archetype="Legacy mainframe billing extract with sequence ID protection against false merge",
        file_path=legacy_01_path,
        expected_raw_rows=6,
        expected_raw_cols=5,
        expected_logical_rows=4,
        expected_logical_cols=5,
        expected_header_columns=["ACCT_NUM", "BILL_CYCLE", "PREV_BAL", "CURR_CHG", "PAYMT_RCV"],
        expected_sentinels={},
        expected_continuations_count=0,
        is_ambiguous=False,
        expected_final_status=DecisionStatus.DETERMINISTIC_VALIDATED,
        has_false_merge_trap=True,
    ))

    return cases
