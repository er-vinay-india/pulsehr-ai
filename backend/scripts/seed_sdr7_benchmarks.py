"""
SDR-7 Benchmark Datasets Seeder (Medium & Large)

Generates isolated JSON artifacts for:
1. sdr7_med: 3 sheets, 1,000 rows across sheets
2. sdr7_large: 3 sheets, 20,000 rows across sheets (e.g. 5,000 employees, 1,000 stores, 14,000 sales)

SAFETY GUARANTEE:
- Zero writes to primary production database pulsehr.sqlite3.
- Hermetically isolated to backend/data/datasets/{dataset_id}/sdr/.
"""

import json
from pathlib import Path
import shutil

ROOT_DATA = Path(__file__).resolve().parent.parent / "data"

def create_benchmark_dataset(dataset_id: str, row_multiplier: int):
    cert_sdr = ROOT_DATA / "datasets" / "sdr7_cert" / "sdr"
    target_sdr = ROOT_DATA / "datasets" / dataset_id / "sdr"
    target_sdr.mkdir(parents=True, exist_ok=True)

    # Copy SDR-1 through SDR-6 JSON metadata files from sdr7_cert
    for json_file in cert_sdr.glob("*.json"):
        if json_file.name != "raw_source_tables.json":
            shutil.copy(json_file, target_sdr / json_file.name)

    # Now create scaled raw source tables
    raw_tables = {}
    
    # 1. Employees (50 * multiplier)
    n_emp = max(10, 50 * row_multiplier)
    raw_tables["Employees"] = [
        {
            "employee_id": f"{i:04d}",
            "employee_name": f"Employee {i}",
            "department": ["Engineering", "Sales", "Operations", "HR", "Finance"][i % 5],
            "salary": 50000.0 + (i * 125.0) % 100000.0,
            "city": ["Bengaluru", "San Francisco", "Springfield", "Austin", "London"][i % 5],
            "zip_code": f"{560000 + (i % 100):06d}",
            "ssn_redacted": f"***-**-{1000 + (i % 9000)}"
        }
        for i in range(1, n_emp + 1)
    ]

    # 2. Stores (10 * multiplier)
    n_stores = max(5, 10 * row_multiplier)
    raw_tables["Stores"] = [
        {
            "store_id": f"STR-{s:03d}",
            "store_name": f"Store {s}",
            "city": ["Bengaluru", "San Francisco", "Springfield", "Austin", "London"][s % 5],
            "region": ["South", "West", "Midwest", "Southwest", "EMEA"][s % 5],
            "opened_year": 2015 + (s % 10)
        }
        for s in range(1, n_stores + 1)
    ]

    # 3. Sales / Transactions (balance to reach target rows)
    target_total = 1000 if row_multiplier <= 5 else 20000
    n_sales = max(10, target_total - (n_emp + n_stores))
    raw_tables["Sales"] = [
        {
            "sale_id": f"TXN-{t:06d}",
            "store_id": f"STR-{(t % n_stores) + 1:03d}",
            "employee_id": f"{(t % n_emp) + 1:04d}",
            "amount": round(15.50 + ((t * 7.75) % 850.0), 2),
            "sale_date": f"2024-{(t % 12) + 1:02d}-{(t % 28) + 1:02d}"
        }
        for t in range(1, n_sales + 1)
    ]

    # Save raw_source_tables.json
    (target_sdr / "raw_source_tables.json").write_text(json.dumps(raw_tables, indent=2), encoding="utf-8")
    total_generated = sum(len(v) for v in raw_tables.values())
    print(f"Created {dataset_id}: {len(raw_tables)} sheets, {total_generated} rows at {target_sdr}")
    return total_generated

if __name__ == "__main__":
    create_benchmark_dataset("sdr7_med", row_multiplier=5)      # 1,000 rows
    create_benchmark_dataset("sdr7_large", row_multiplier=100)   # 20,000 rows
