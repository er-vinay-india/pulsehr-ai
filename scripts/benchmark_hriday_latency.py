#!/usr/bin/env python3
"""
HRIDAY Copilot Latency Characterization Benchmark
Measures planning time, execution time, and end-to-end response time across 50 representative queries:
1. Direct Facts (Aggregate, Single-Entity)
2. Rankings (Top-N, Bottom-N across grains)
3. Comparisons & Breakdowns
4. Correlation & Relationship (with causal refusal disclaimers)
5. Multi-turn Follow-ups (Why, Count shift, Cohort filter, Dimension shift)
6. Grounded Negative Refusals (Unrecorded metrics, Non-existent entities, Forward projections)

Computes P50, P90, P95, Mean, and Max latencies.
"""

import sys
import time
import statistics
from pathlib import Path

# Ensure backend is on sys.path
backend_path = Path(__file__).resolve().parents[1] / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.db.database import get_connection
from app.services.copilot_query_planner import (
    plan_analytical_query,
    execute_analytical_plan
)

# Benchmark Datasets
DS_WORKFORCE = 99770
SHEET_WORKFORCE_MAIN = 9967416

DS_RETAIL = 99771
SHEET_RETAIL_MAIN = 9967418

DS_ENV = 99772
SHEET_ENV_MAIN = 9967419


def seed_test_database():
    real_db = backend_path / "data" / "db" / "pulsehr.sqlite3"
    with get_connection() as conn:
        has_99770 = conn.execute("SELECT 1 FROM dataset_uploads WHERE id = 99770").fetchone()
        if not has_99770 and real_db.exists():
            conn.execute(f'ATTACH DATABASE "{real_db}" AS real_source')
            conn.execute("INSERT OR REPLACE INTO dataset_uploads (id, filename, original_name, file_type, display_name) SELECT id, filename, original_name, file_type, display_name FROM real_source.dataset_uploads WHERE id IN (99770, 99771, 99772)")
            conn.execute("INSERT OR REPLACE INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, row_count) SELECT id, dataset_id, name, display_name, columns_json, profile_json, row_count FROM real_source.sheets WHERE dataset_id IN (99770, 99771, 99772)")
            conn.execute("INSERT OR REPLACE INTO sheet_rows (id, sheet_id, row_index, data_json) SELECT id, sheet_id, row_index, data_json FROM real_source.sheet_rows WHERE sheet_id IN (SELECT id FROM real_source.sheets WHERE dataset_id IN (99770, 99771, 99772))")
            try:
                conn.execute("INSERT OR REPLACE INTO sheet_relationships SELECT * FROM real_source.sheet_relationships WHERE left_sheet_id IN (SELECT id FROM real_source.sheets WHERE dataset_id IN (99770, 99771, 99772))")
            except Exception:
                pass
            conn.commit()
            conn.execute("DETACH DATABASE real_source")


QUERIES = [
    # Category 1: Direct Facts (10)
    ("Direct Fact", DS_WORKFORCE, SHEET_WORKFORCE_MAIN, "Which department has the highest attendance?", None),
    ("Direct Fact", DS_WORKFORCE, SHEET_WORKFORCE_MAIN, "which department has highest attendance rate?", None),
    ("Direct Fact", DS_WORKFORCE, SHEET_WORKFORCE_MAIN, "Which department had the lowest approved leaves?", None),
    ("Direct Fact", DS_WORKFORCE, SHEET_WORKFORCE_MAIN, "department with lowest leaves", None),
    ("Direct Fact", DS_RETAIL, SHEET_RETAIL_MAIN, "Which store has the highest weekly sales?", None),
    ("Direct Fact", DS_RETAIL, SHEET_RETAIL_MAIN, "store with highest sales", None),
    ("Direct Fact", DS_RETAIL, SHEET_RETAIL_MAIN, "which store had the most sales?", None),
    ("Direct Fact", DS_ENV, SHEET_ENV_MAIN, "which city has the highest SO2 level?", None),
    ("Direct Fact", DS_ENV, SHEET_ENV_MAIN, "city with highest SO2", None),
    ("Direct Fact", DS_ENV, SHEET_ENV_MAIN, "where is SO2 highest across cities?", None),

    # Category 2: Rankings (10)
    ("Ranking", DS_WORKFORCE, SHEET_WORKFORCE_MAIN, "Which department has the lowest attendance?", None),
    ("Ranking", DS_WORKFORCE, SHEET_WORKFORCE_MAIN, "which department has lowest attendance rate?", None),
    ("Ranking", DS_WORKFORCE, SHEET_WORKFORCE_MAIN, "department with worst attendance", None),
    ("Ranking", DS_WORKFORCE, SHEET_WORKFORCE_MAIN, "Who is not coming regularly?", None),
    ("Ranking", DS_WORKFORCE, SHEET_WORKFORCE_MAIN, "Who comes to office the least?", None),
    ("Ranking", DS_WORKFORCE, SHEET_WORKFORCE_MAIN, "who came least", None),
    ("Ranking", DS_WORKFORCE, SHEET_WORKFORCE_MAIN, "top 5 employees by attendance", None),
    ("Ranking", DS_RETAIL, SHEET_RETAIL_MAIN, "which are the bottom 2 stores by weekly sales?", None),
    ("Ranking", DS_RETAIL, SHEET_RETAIL_MAIN, "lowest 2 stores in weekly sales", None),
    ("Ranking", DS_ENV, SHEET_ENV_MAIN, "which are the top 5 cities with highest NO2?", None),

    # Category 3: Comparisons & Breakdowns (8)
    ("Comparison", DS_WORKFORCE, SHEET_WORKFORCE_MAIN, "compare attendance across departments", None),
    ("Comparison", DS_WORKFORCE, SHEET_WORKFORCE_MAIN, "breakdown attendance by department", None),
    ("Comparison", DS_WORKFORCE, SHEET_WORKFORCE_MAIN, "compare attendance between Operations and Engineering", None),
    ("Comparison", DS_RETAIL, SHEET_RETAIL_MAIN, "breakdown sales across stores", None),
    ("Comparison", DS_RETAIL, SHEET_RETAIL_MAIN, "show sales breakdown by store", None),
    ("Comparison", DS_RETAIL, SHEET_RETAIL_MAIN, "compare weekly sales on holidays vs non-holidays", None),
    ("Comparison", DS_ENV, SHEET_ENV_MAIN, "breakdown SO2 by city", None),
    ("Comparison", DS_ENV, SHEET_ENV_MAIN, "compare SO2 across cities", None),

    # Category 4: Correlation & Relationship (6)
    ("Correlation", DS_WORKFORCE, SHEET_WORKFORCE_MAIN, "Is attendance related to leaves?", None),
    ("Correlation", DS_WORKFORCE, SHEET_WORKFORCE_MAIN, "Are leaves and attendance correlated?", None),
    ("Correlation", DS_WORKFORCE, SHEET_WORKFORCE_MAIN, "Does higher approved leave cause lower attendance?", None),
    ("Correlation", DS_RETAIL, SHEET_RETAIL_MAIN, "Does higher unemployment lead to lower weekly sales?", None),
    ("Correlation", DS_ENV, SHEET_ENV_MAIN, "Is SO2 correlated with NO2?", None),
    ("Correlation", DS_ENV, SHEET_ENV_MAIN, "examine relationship of SO2 vs NO2", None),

    # Category 5: Multi-turn Follow-ups (8)
    ("Follow-up (Why)", DS_WORKFORCE, SHEET_WORKFORCE_MAIN, "Why?", {"last_intent": "ranking", "metric": "attendance", "dimension": "Department", "last_ranking": [{"name": "Operations", "val": 0.72}]}),
    ("Follow-up (Why)", DS_WORKFORCE, SHEET_WORKFORCE_MAIN, "Why is this the case?", {"last_intent": "ranking", "metric": "attendance", "dimension": "Department", "last_ranking": [{"name": "Operations", "val": 0.72}]}),
    ("Follow-up (Limit)", DS_WORKFORCE, SHEET_WORKFORCE_MAIN, "Show me the bottom 3", {"last_intent": "ranking", "metric": "attendance", "entity_grain": "employee", "direction": "lowest", "ranking_limit": 5}),
    ("Follow-up (Limit)", DS_WORKFORCE, SHEET_WORKFORCE_MAIN, "what about the lowest 3?", {"last_intent": "ranking", "metric": "attendance", "entity_grain": "employee", "direction": "lowest", "ranking_limit": 5}),
    ("Follow-up (Cohort)", DS_WORKFORCE, SHEET_WORKFORCE_MAIN, "What about Operations only?", {"last_intent": "ranking", "metric": "attendance", "entity_grain": "employee", "direction": "lowest"}),
    ("Follow-up (Cohort)", DS_WORKFORCE, SHEET_WORKFORCE_MAIN, "just Operations department", {"last_intent": "ranking", "metric": "attendance", "entity_grain": "employee", "direction": "lowest"}),
    ("Follow-up (Fields)", DS_WORKFORCE, SHEET_WORKFORCE_MAIN, "include employee ID", {"last_intent": "ranking", "metric": "attendance", "entity_grain": "employee", "direction": "lowest", "ranking_limit": 5}),
    ("Follow-up (Fields)", DS_WORKFORCE, SHEET_WORKFORCE_MAIN, "I need their employee ID and department", {"last_intent": "ranking", "metric": "attendance", "entity_grain": "employee", "direction": "lowest", "ranking_limit": 5}),

    # Category 6: Grounded Negative Refusals (8)
    ("Refusal", DS_WORKFORCE, SHEET_WORKFORCE_MAIN, "Why did this employee take leave?", None),
    ("Refusal", DS_WORKFORCE, SHEET_WORKFORCE_MAIN, "Will attendance improve next month?", None),
    ("Refusal", DS_WORKFORCE, SHEET_WORKFORCE_MAIN, "Did the WFO policy cause attendance to increase?", None),
    ("Refusal", DS_WORKFORCE, SHEET_WORKFORCE_MAIN, "What is our company valuation?", None),
    ("Refusal", DS_WORKFORCE, SHEET_WORKFORCE_MAIN, "Which department is happiest?", None),
    ("Refusal", DS_WORKFORCE, SHEET_WORKFORCE_MAIN, "What is the profitability of employees?", None),
    ("Refusal", DS_RETAIL, SHEET_RETAIL_MAIN, "Forecast store sales for Q4 next year", None),
    ("Refusal", DS_ENV, SHEET_ENV_MAIN, "Will air quality improve next week?", None),
]


def run_benchmark():
    seed_test_database()
    print("=" * 70)
    print("HRIDAY Copilot Latency Characterization Benchmark (50 Queries)")
    print("=" * 70)

    # Warmup
    _ = plan_analytical_query("which department has the highest attendance?", dataset_id=DS_WORKFORCE, sheet_id=SHEET_WORKFORCE_MAIN, allow_model_planning=False)

    plan_times = []
    exec_times = []
    total_times = []
    category_times = {}

    for cat, ds_id, sheet_id, query, prior in QUERIES:
        # Time planning
        t0 = time.perf_counter()
        plan = plan_analytical_query(query, dataset_id=ds_id, sheet_id=sheet_id, prior_context=prior, allow_model_planning=False)
        t1 = time.perf_counter()
        plan_ms = (t1 - t0) * 1000.0

        # Time execution
        if plan is not None:
            t2 = time.perf_counter()
            res = execute_analytical_plan(plan)
            t3 = time.perf_counter()
            exec_ms = (t3 - t2) * 1000.0
            status = res.get("status", "unknown")
        else:
            exec_ms = 0.0
            status = "unplanned"

        total_ms = plan_ms + exec_ms
        plan_times.append(plan_ms)
        exec_times.append(exec_ms)
        total_times.append(total_ms)

        if cat not in category_times:
            category_times[cat] = []
        category_times[cat].append(total_ms)

        print(f"[{cat:18}] {total_ms:6.2f} ms (plan: {plan_ms:5.2f} ms, exec: {exec_ms:5.2f} ms) | status={status:10} | Q: {query[:40]}")

    def get_stats(data):
        s_data = sorted(data)
        n = len(s_data)
        p50 = statistics.median(s_data)
        p90 = s_data[int(0.90 * n)]
        p95 = s_data[int(0.95 * n)]
        mean = statistics.mean(s_data)
        max_val = max(s_data)
        min_val = min(s_data)
        return {"min": min_val, "p50": p50, "p90": p90, "p95": p95, "mean": mean, "max": max_val}

    tot_stats = get_stats(total_times)
    plan_stats = get_stats(plan_times)
    exec_stats = get_stats(exec_times)

    print("\n" + "=" * 70)
    print("OVERALL LATENCY CHARACTERIZATION SUMMARY (50 Queries)")
    print("=" * 70)
    print(f"{'Metric':<18} | {'Min (ms)':<9} | {'P50 (ms)':<9} | {'P90 (ms)':<9} | {'P95 (ms)':<9} | {'Mean (ms)':<9} | {'Max (ms)':<9}")
    print("-" * 70)
    print(f"{'Planning':<18} | {plan_stats['min']:9.2f} | {plan_stats['p50']:9.2f} | {plan_stats['p90']:9.2f} | {plan_stats['p95']:9.2f} | {plan_stats['mean']:9.2f} | {plan_stats['max']:9.2f}")
    print(f"{'Execution':<18} | {exec_stats['min']:9.2f} | {exec_stats['p50']:9.2f} | {exec_stats['p90']:9.2f} | {exec_stats['p95']:9.2f} | {exec_stats['mean']:9.2f} | {exec_stats['max']:9.2f}")
    print(f"{'Total End-to-End':<18} | {tot_stats['min']:9.2f} | {tot_stats['p50']:9.2f} | {tot_stats['p90']:9.2f} | {tot_stats['p95']:9.2f} | {tot_stats['mean']:9.2f} | {tot_stats['max']:9.2f}")
    print("-" * 70)

    print("\nLATENCY BY INTENT CATEGORY (P50 / P95):")
    for cat, times in category_times.items():
        c_stats = get_stats(times)
        print(f"  • {cat:<22}: P50 = {c_stats['p50']:6.2f} ms | P90 = {c_stats['p90']:6.2f} ms | P95 = {c_stats['p95']:6.2f} ms | Max = {c_stats['max']:6.2f} ms (N={len(times)})")

    p50_val = tot_stats['p50']
    p95_val = tot_stats['p95']
    p50_msg = "PASS" if p50_val < 10.0 else f"CURRENT: {p50_val:.2f} ms"
    p95_msg = "PASS" if p95_val < 50.0 else f"CURRENT: {p95_val:.2f} ms"
    print("\nTARGET SPECIFICATION AUDIT:")
    print(f"  [x] Deterministic P50 < 10.0 ms:  {p50_msg} (Target < 50ms)")
    print(f"  [x] Deterministic P95 < 50.0 ms:  {p95_msg} (Target < 100ms)")
    print(f"  [x] Zero Unplanned Queries:       {'PASS' if all(t > 0 for t in exec_times) else 'FAIL'}")
    print("=" * 70)


if __name__ == "__main__":
    run_benchmark()
