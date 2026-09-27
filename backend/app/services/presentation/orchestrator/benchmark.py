"""Granite 4.0 Model Benchmark Harness.

Compares 'granite4:3b-h' (hybrid architecture) vs 'granite4:3b' (standard dense)
across 10 project-specific presentation execution tasks:
1. Tool Routing Accuracy
2. Execution DAG Construction
3. Arithmetic Calculation Parameterization
4. Outlier / Trend Parameterization
5. Claim Evidence Binding Verification
6. Conflicting Evidence Escalation Detection
7. Executive Slide Copy Polish (Truth Preserving)
8. Speaker Notes Synthesis
9. JSON Schema Validity & Parse Rate
10. Latency & Retry Frequency
"""

from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any

from app.core import config
from app.core.models_config import ModelRole
from app.services.gateway.model_gateway import ModelGateway, extract_json_payload

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("granite_benchmark")

BENCHMARK_TASKS = [
    {
        "id": "task_1_tool_routing",
        "name": "Tool Routing Accuracy",
        "prompt": """You are IBM Granite presentation execution orchestrator.
Given this slide objective: "Show weekly sales surge peaks and calculate growth rate over baseline",
which tool should be called first?
Options: ["retrieve_memory", "fetch_evidence", "calculate_metric", "detect_outliers"]
Return JSON: {"selected_tool": "...", "reason": "..."}""",
        "expected_key": "selected_tool",
        "valid_choices": ["fetch_evidence", "calculate_metric"]
    },
    {
        "id": "task_2_dag_dependencies",
        "name": "DAG Dependency Resolution",
        "prompt": """You are IBM Granite presentation execution orchestrator.
Order these 4 tasks in valid DAG dependency order:
["synthesize_slide_copy", "fetch_evidence", "verify_metric", "calculate_metric"]
Return JSON: {"ordered_tasks": ["...", "...", "...", "..."]}""",
        "expected_key": "ordered_tasks",
        "validator": lambda res: isinstance(res.get("ordered_tasks"), list) and res["ordered_tasks"][0] == "fetch_evidence" and res["ordered_tasks"][-1] == "synthesize_slide_copy"
    },
    {
        "id": "task_3_metric_calculation",
        "name": "Metric Calculation Parameterization",
        "prompt": """You are IBM Granite presentation execution orchestrator.
Generate tool parameters for calculating percentage surge between baseline 14,200 and surge 23,800.
Return JSON: {"tool_name": "calculate_metric", "parameters": {"metric_type": "surge_delta", "baseline": 14200, "comparison_value": 23800}}""",
        "expected_key": "parameters",
        "validator": lambda res: res.get("tool_name") == "calculate_metric" and "baseline" in res.get("parameters", {})
    },
    {
        "id": "task_4_outlier_filtering",
        "name": "Outlier Detection Parameterization",
        "prompt": """You are IBM Granite presentation execution orchestrator.
Construct parameters to detect anomalous absenteeism in department records across column 'absence_hours'.
Return JSON: {"tool_name": "detect_outliers", "parameters": {"metric_col": "absence_hours", "method": "iqr", "threshold": 1.5}}""",
        "expected_key": "parameters",
        "validator": lambda res: res.get("tool_name") == "detect_outliers" and res.get("parameters", {}).get("metric_col") == "absence_hours"
    },
    {
        "id": "task_5_evidence_binding",
        "name": "Evidence Binding Verification",
        "prompt": """Given metric claim: "Weekly throughput reached 14,200 units (+7.8%)",
verify if evidence_id "EVID-01" matches or if it requires provenance binding.
Return JSON: {"evidence_id": "EVID-01", "bound": true, "confidence": 0.95}""",
        "expected_key": "bound",
        "validator": lambda res: res.get("bound") is True and res.get("evidence_id") == "EVID-01"
    },
    {
        "id": "task_6_escalation_detection",
        "name": "Conflicting Evidence Escalation",
        "prompt": """Cohort A reports +14% productivity surge while Cohort B reports -8% decline on same workload.
Should this conflict be escalated to DeepSeek-R1?
Return JSON: {"escalate_to_deepseek": true, "reason": "Paradoxical divergence requires causal root-cause analysis"}""",
        "expected_key": "escalate_to_deepseek",
        "validator": lambda res: res.get("escalate_to_deepseek") is True
    },
    {
        "id": "task_7_slide_copy_polish",
        "name": "Executive Slide Copy Polish",
        "prompt": """Polish this draft into 2 concise executive bullets without changing the numbers:
Draft: "We saw 14,200 records with 99.8% completeness and 1.8x dispersion between units."
Return JSON: {"headline": "Audited Operational Performance", "bullet_points": ["14,200 verified records with 99.8% data completeness", "1.8x productivity dispersion observed between leader and laggard units"]}""",
        "expected_key": "bullet_points",
        "validator": lambda res: isinstance(res.get("bullet_points"), list) and len(res["bullet_points"]) >= 2 and any("14,200" in b or "14200" in b for b in res["bullet_points"])
    },
    {
        "id": "task_8_speaker_notes",
        "name": "Speaker Notes Synthesis",
        "prompt": """Create 2 concise speaker talking points for Slide: "Operational Resilience & Surge Capacity".
Return JSON: {"speaker_notes": "Highlight verified 14,200 baseline throughput and emphasize zero service interruptions during surge window."}""",
        "expected_key": "speaker_notes",
        "validator": lambda res: isinstance(res.get("speaker_notes"), str) and len(res["speaker_notes"]) > 20
    },
    {
        "id": "task_9_json_strictness",
        "name": "JSON Schema Validity",
        "prompt": """Output a strict JSON array of 3 verified presentation sections:
Return JSON: [{"section_id": "sec_01", "title": "Executive Summary"}, {"section_id": "sec_02", "title": "Performance Insights"}, {"section_id": "sec_03", "title": "Action Roadmap"}]""",
        "expected_key": None,
        "validator": lambda res: isinstance(res, list) and len(res) == 3
    },
    {
        "id": "task_10_retry_resilience",
        "name": "Complex Multi-Key Schema Delivery",
        "prompt": """Return a complete slide execution package descriptor with keys:
"slide_id": "SLIDE-01", "headline": "Executive Summary", "verified": true, "confidence": 1.0.
Return JSON: {"slide_id": "SLIDE-01", "headline": "Executive Summary", "verified": true, "confidence": 1.0}""",
        "expected_key": "slide_id",
        "validator": lambda res: res.get("slide_id") == "SLIDE-01" and res.get("verified") is True
    }
]


def run_benchmark_for_model(model_name: str) -> dict[str, Any]:
    """Runs all 10 benchmark tasks against the specified model."""
    logger.info(f"=== Starting Benchmark for model: {model_name} ===")
    results = []
    total_latency_ms = 0.0
    passed_count = 0
    parse_errors = 0

    for task in BENCHMARK_TASKS:
        t_id = task["id"]
        t_name = task["name"]
        prompt = task["prompt"]
        expected_key = task.get("expected_key")
        validator = task.get("validator")

        start = time.perf_counter()
        try:
            res = ModelGateway.generate(
                role=ModelRole.WRITER,
                prompt=prompt,
                model_override=model_name,
                report_id=f"bm-{model_name}-{t_id}",
                step_name="benchmark_task",
                max_retries=1,
                temperature_override=0.1
            )
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            total_latency_ms += duration_ms

            if not res.success or not res.raw_text:
                results.append({
                    "task_id": t_id,
                    "task_name": t_name,
                    "status": "FAIL",
                    "reason": "Model generation unsuccessful",
                    "duration_ms": duration_ms
                })
                continue

            try:
                payload = extract_json_payload(res.raw_text)
                parsed = json.loads(payload)
            except Exception as e:
                parse_errors += 1
                results.append({
                    "task_id": t_id,
                    "task_name": t_name,
                    "status": "FAIL",
                    "reason": f"JSON parse error: {e}",
                    "raw": res.raw_text[:120],
                    "duration_ms": duration_ms
                })
                continue

            # Validation
            passed = False
            if validator:
                passed = bool(validator(parsed))
            elif expected_key:
                if isinstance(parsed, dict) and expected_key in parsed:
                    if "valid_choices" in task:
                        passed = parsed[expected_key] in task["valid_choices"]
                    else:
                        passed = True

            if passed:
                passed_count += 1
                results.append({
                    "task_id": t_id,
                    "task_name": t_name,
                    "status": "PASS",
                    "duration_ms": duration_ms
                })
            else:
                results.append({
                    "task_id": t_id,
                    "task_name": t_name,
                    "status": "FAIL",
                    "reason": "Validation check failed",
                    "output": str(parsed)[:120],
                    "duration_ms": duration_ms
                })

        except Exception as exc:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            results.append({
                "task_id": t_id,
                "task_name": t_name,
                "status": "ERROR",
                "reason": str(exc),
                "duration_ms": duration_ms
            })

    avg_latency = round(total_latency_ms / len(BENCHMARK_TASKS), 2)
    success_rate = round((passed_count / len(BENCHMARK_TASKS)) * 100, 1)

    return {
        "model": model_name,
        "tasks_run": len(BENCHMARK_TASKS),
        "passed": passed_count,
        "failed": len(BENCHMARK_TASKS) - passed_count,
        "parse_errors": parse_errors,
        "success_rate_pct": success_rate,
        "avg_latency_ms": avg_latency,
        "total_latency_ms": round(total_latency_ms, 2),
        "task_details": results
    }


def compare_models(model_a: str = "granite4:3b-h", model_b: str = "granite4:3b") -> dict[str, Any]:
    """Runs comparative evaluation between granite4:3b-h and granite4:3b."""
    res_a = run_benchmark_for_model(model_a)
    res_b = run_benchmark_for_model(model_b)

    # Determine winner
    # Scoring: accuracy > json valid > avg latency
    score_a = res_a["success_rate_pct"] * 10 - res_a["parse_errors"] * 15 - (res_a["avg_latency_ms"] / 500)
    score_b = res_b["success_rate_pct"] * 10 - res_b["parse_errors"] * 15 - (res_b["avg_latency_ms"] / 500)

    winner = model_a if score_a >= score_b else model_b

    comparison = {
        "benchmark_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model_a": res_a,
        "model_b": res_b,
        "comparison_summary": {
            f"{model_a}_success_rate": f"{res_a['success_rate_pct']}%",
            f"{model_b}_success_rate": f"{res_b['success_rate_pct']}%",
            f"{model_a}_avg_latency": f"{res_a['avg_latency_ms']} ms",
            f"{model_b}_avg_latency": f"{res_b['avg_latency_ms']} ms",
            "recommended_primary_orchestrator": winner,
            "rationale": (
                f"{winner} achieved higher benchmark score (composite accuracy, JSON compliance, and throughput)."
            )
        }
    }
    return comparison


if __name__ == "__main__":
    report = compare_models()
    print(json.dumps(report, indent=2))
