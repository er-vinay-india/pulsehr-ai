"""Comprehensive Benchmark and Analysis Script for CriticAgent Bottleneck Investigation.

Evaluates 4 Candidates on the identical 10-case factual audit test set:
- Candidate A: Current DeepSeek-R1 (baseline)
- Candidate B: DeepSeek-R1 with minimum reasoning/output configuration
- Candidate C: Qwen 3.5 9B
- Candidate D: Phi-4 Mini

Also measures:
- Model residency effect (Qwen -> Gemma -> DeepSeek vs Qwen -> Gemma -> Qwen)
- Reasoning tokens generated vs discarded
- Identification of deterministic validation opportunities
"""

import json
import re
import time
import httpx
from pydantic import BaseModel, Field

from app.core import config
from app.services.evidence.evidence_models import Finding, FindingType, Importance
from app.services.evidence.evidence_store import EvidenceStore

# 1. DEFINE GROUND TRUTH EVIDENCE STORE
def build_ground_truth_evidence() -> EvidenceStore:
    store = EvidenceStore()
    store.add_finding(Finding(
        finding_id="F-001",
        type=FindingType.OUTPERFORMER,
        metric="Attendance Rate",
        segment="Engineering",
        segment_value=94.2,
        overall_value=88.0,
        difference=6.2,
        difference_percentage_points=6.2,
        importance=Importance.HIGH,
        headline="Engineering attendance is 6.2 points above organizational baseline.",
        business_implication="Engineering demonstrates leading workforce discipline."
    ))
    store.add_finding(Finding(
        finding_id="F-002",
        type=FindingType.HEADWIND,
        metric="Overtime Hours",
        segment="Operations",
        segment_value=14.5,
        overall_value=8.0,
        difference=6.5,
        difference_percentage_points=81.25,
        importance=Importance.HIGH,
        headline="Operations logs 14.5 overtime hours per employee, exceeding benchmark.",
        business_implication="Operations experiences heavy workload and capacity strain."
    ))
    store.add_finding(Finding(
        finding_id="F-003",
        type=FindingType.TREND_SHIFT,
        metric="Defect Count",
        segment="Assembly",
        segment_value=3.2,
        overall_value=1.0,
        difference=2.2,
        difference_percentage_points=220.0,
        importance=Importance.MEDIUM,
        headline="Assembly defect count elevated above baseline.",
        business_implication="Quality control intervention required in assembly."
    ))
    return store

# 2. DEFINE THE 10 REAL-WORLD CRITIC TEST CASES
TEST_CASES = [
    {
        "id": 1,
        "name": "Correct supported numerical claim",
        "sentence": "Engineering attendance reached 94.2%, outperforming the 88.0% baseline by 6.2 percentage points [F-001].",
        "finding_ids": ["F-001"],
        "ground_truth_error": False,  # Should be SUPPORTED
        "error_type": None
    },
    {
        "id": 2,
        "name": "Incorrect percentage",
        "sentence": "Engineering attendance outpaced the company benchmark by an extraordinary 25.0% [F-001].",
        "finding_ids": ["F-001"],
        "ground_truth_error": True,  # UNSUPPORTED: actual is 6.2%
        "error_type": "incorrect_percentage"
    },
    {
        "id": 3,
        "name": "Incorrect absolute number",
        "sentence": "Operations recorded an average of 28.0 overtime hours per team member [F-002].",
        "finding_ids": ["F-002"],
        "ground_truth_error": True,  # UNSUPPORTED: actual is 14.5
        "error_type": "incorrect_number"
    },
    {
        "id": 4,
        "name": "Invented finding ID",
        "sentence": "Turnover in customer service surged by 15.0% according to verified data [F-999].",
        "finding_ids": ["F-999"],
        "ground_truth_error": True,  # UNSUPPORTED: F-999 doesn't exist
        "error_type": "invented_id"
    },
    {
        "id": 5,
        "name": "Claim unsupported by EvidenceStore",
        "sentence": "Employee satisfaction in Engineering dropped to historic lows during the review cycle [F-001].",
        "finding_ids": ["F-001"],
        "ground_truth_error": True,  # UNSUPPORTED: metric not in F-001
        "error_type": "unsupported_claim"
    },
    {
        "id": 6,
        "name": "Correct finding but wrong interpretation",
        "sentence": "Operations recording 14.5 overtime hours per employee represents outstanding operational efficiency and health [F-002].",
        "finding_ids": ["F-002"],
        "ground_truth_error": True,  # CONTRADICTORY: headwind, not health
        "error_type": "wrong_interpretation"
    },
    {
        "id": 7,
        "name": "Reversed positive/negative direction",
        "sentence": "Operations reduced employee overtime by 6.5 hours below organizational norms [F-002].",
        "finding_ids": ["F-002"],
        "ground_truth_error": True,  # CONTRADICTORY: 6.5 above, not below
        "error_type": "reversed_direction"
    },
    {
        "id": 8,
        "name": "Unsupported causal claim",
        "sentence": "High overtime in operations directly triggered customer churn across the business [F-002].",
        "finding_ids": ["F-002"],
        "ground_truth_error": True,  # UNSUPPORTED: causal assertion without proof
        "error_type": "causal_overstatement"
    },
    {
        "id": 9,
        "name": "Missing denominator/context",
        "sentence": "Over 5,000 operations employees worked excessive overtime shifts [F-002].",
        "finding_ids": ["F-002"],
        "ground_truth_error": True,  # UNSUPPORTED: scale/count invented
        "error_type": "missing_denominator"
    },
    {
        "id": 10,
        "name": "Valid executive-language paraphrase",
        "sentence": "Engineering maintained leading operational discipline while Operations experienced heavy overtime demand [F-001, F-002].",
        "finding_ids": ["F-001", "F-002"],
        "ground_truth_error": False,  # Should be SUPPORTED (Valid synthesis)
        "error_type": None
    }
]

def build_critic_prompt(sentence: str, finding_ids: list[str], evidence_store: EvidenceStore) -> str:
    valid_findings = [evidence_store.get_finding(fid) for fid in finding_ids if evidence_store.get_finding(fid) is not None]
    if not valid_findings:
        valid_findings = evidence_store.get_all()

    evidence_payload = [
        {
            "finding_id": f.finding_id,
            "metric": f.metric,
            "segment": f.segment,
            "observed_value": f.segment_value,
            "baseline_value": f.overall_value,
            "percentage_gap": f.difference_percentage_points,
            "headline": f.headline,
            "implication": f.business_implication
        }
        for f in valid_findings
    ]

    return f"""You are the Chief Auditor & Senior Factual Critic for PulseHR AI.
Your responsibility: Rigorously audit the following generated sentence against verified evidence.

CRITICAL AUDIT RULES:
1. Classify the sentence into exactly one verdict:
   - 'SUPPORTED': Strictly backed by the evidence numbers and direction.
   - 'PARTIALLY_SUPPORTED': Qualitative framing is reasonable, but lacks exact numbers.
   - 'UNSUPPORTED': Invents numbers, metrics, dates, rates, or finding IDs NOT present in evidence.
   - 'CONTRADICTORY': Asserts an increase when data shows decrease, or claims positive when data shows negative headwind.
2. Flag any quantitative figures that do not match verified evidence within ±1%.
3. Set 'passed' to true ONLY if the verdict is 'SUPPORTED' or 'PARTIALLY_SUPPORTED'.
4. If failed, provide concise 'repair_feedback'.

## Ground Truth Evidence:
{json.dumps(evidence_payload, indent=2)}

## Drafted Sentence to Audit:
"{sentence}"

Return ONLY valid JSON matching this schema:
{{
  "passed": true,
  "verdict": "SUPPORTED",
  "reason": "Matches observed evidence...",
  "unsupported_numbers": []
}}
"""

def run_single_inference(
    model: str,
    prompt: str,
    system_prompt: str | None = None,
    options_override: dict | None = None
) -> dict:
    """Invokes Ollama /api/generate directly and captures detailed execution metrics."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": options_override or {"temperature": 0.05}
    }
    if system_prompt:
        payload["system"] = system_prompt

    t0 = time.perf_counter()
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(f"{config.OLLAMA_BASE_URL}/api/generate", json=payload)
        resp.raise_for_status()
        data = resp.json()
    wall_ms = (time.perf_counter() - t0) * 1000

    raw_response = data.get("response", "")
    
    # Calculate reasoning tokens vs output tokens
    think_match = re.search(r"<think>([\s\S]*?)</think>", raw_response, re.IGNORECASE)
    reasoning_text = think_match.group(1).strip() if think_match else ""
    cleaned_json_text = re.sub(r"<think>[\s\S]*?</think>", "", raw_response, flags=re.IGNORECASE).strip()

    # Ollama nanosecond telemetry
    load_ms = data.get("load_duration", 0) / 1_000_000.0
    eval_ms = data.get("eval_duration", 0) / 1_000_000.0
    total_ollama_ms = data.get("total_duration", 0) / 1_000_000.0
    total_tokens = data.get("eval_count", len(raw_response) // 4)
    reasoning_tokens_approx = len(reasoning_text) // 4 if reasoning_text else 0

    # Parse JSON
    parsed = None
    schema_valid = False
    try:
        # Extract json object { ... }
        match = re.search(r"\{[\s\S]*\}", cleaned_json_text)
        if match:
            parsed = json.loads(match.group(0))
            if "passed" in parsed or "verdict" in parsed:
                schema_valid = True
    except Exception:
        schema_valid = False

    return {
        "wall_ms": wall_ms,
        "load_ms": load_ms,
        "eval_ms": eval_ms,
        "total_ollama_ms": total_ollama_ms,
        "total_tokens": total_tokens,
        "reasoning_tokens": reasoning_tokens_approx,
        "raw_response": raw_response,
        "cleaned_text": cleaned_json_text,
        "parsed": parsed,
        "schema_valid": schema_valid
    }

def benchmark_candidate(
    candidate_name: str,
    model: str,
    system_prompt: str | None = None,
    options: dict | None = None
) -> dict:
    evidence_store = build_ground_truth_evidence()
    
    tp = 0  # Correctly flagged error
    fp = 0  # Valid claim incorrectly flagged as error
    fn = 0  # Error incorrectly passed as valid
    tn = 0  # Valid claim correctly passed
    
    total_load_ms = 0.0
    total_eval_ms = 0.0
    total_wall_ms = 0.0
    total_tokens = 0
    total_reasoning_tokens = 0
    valid_schemas = 0

    details = []

    print(f"\n==========================================")
    print(f"BENCHMARKING: {candidate_name} ({model})")
    print(f"==========================================")

    for case in TEST_CASES:
        prompt = build_critic_prompt(case["sentence"], case["finding_ids"], evidence_store)
        res = run_single_inference(model, prompt, system_prompt=system_prompt, options_override=options)
        
        total_load_ms += res["load_ms"]
        total_eval_ms += res["eval_ms"]
        total_wall_ms += res["wall_ms"]
        total_tokens += res["total_tokens"]
        total_reasoning_tokens += res["reasoning_tokens"]
        if res["schema_valid"]:
            valid_schemas += 1

        # Determine whether model flagged an error
        parsed = res["parsed"] or {}
        passed = parsed.get("passed", True)
        verdict = str(parsed.get("verdict", "")).upper()
        if verdict in ("UNSUPPORTED", "CONTRADICTORY"):
            model_flagged_error = True
        elif verdict in ("SUPPORTED", "PARTIALLY_SUPPORTED"):
            model_flagged_error = False
        else:
            model_flagged_error = not passed

        # Confusion matrix
        ground_truth_error = case["ground_truth_error"]
        if ground_truth_error:
            if model_flagged_error:
                tp += 1
                result_cat = "TP (Error Caught)"
            else:
                fn += 1
                result_cat = "FN (Error Missed)"
        else:
            if model_flagged_error:
                fp += 1
                result_cat = "FP (Valid Claim Wrongly Flagged)"
            else:
                tn += 1
                result_cat = "TN (Valid Claim Passed)"

        print(f"Case {case['id']:02d}: {case['name']:<42} -> {result_cat:<28} ({res['wall_ms']:.1f}ms, {res['total_tokens']} tok, {res['reasoning_tokens']} CoT)")
        details.append({
            "case_id": case["id"],
            "name": case["name"],
            "result_cat": result_cat,
            "wall_ms": res["wall_ms"],
            "verdict": verdict,
            "passed": passed,
            "reason": parsed.get("reason", "")
        })

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    schema_rate = valid_schemas / len(TEST_CASES)
    avg_latency = total_wall_ms / len(TEST_CASES)

    return {
        "candidate": candidate_name,
        "model": model,
        "avg_latency_ms": round(avg_latency, 1),
        "total_wall_ms": round(total_wall_ms, 1),
        "avg_load_ms": round(total_load_ms / len(TEST_CASES), 1),
        "avg_eval_ms": round(total_eval_ms / len(TEST_CASES), 1),
        "total_tokens": total_tokens,
        "total_reasoning_tokens": total_reasoning_tokens,
        "schema_validity_rate": round(schema_rate, 2),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "details": details
    }

def test_model_residency_effect():
    """Measures load times when chaining models in sequence."""
    print("\n==========================================")
    print("MEASURING MODEL RESIDENCY & SWAPPING OVERHEAD")
    print("==========================================")
    
    dummy_prompt = "Output JSON: {\"status\": \"ok\"}"

    # Pipeline A: Qwen -> Gemma -> DeepSeek
    print("\nSimulating Pipeline A: Qwen (Analyst) -> Gemma (Writer) -> DeepSeek (Critic)")
    res_q1 = run_single_inference("qwen3.5:9b", dummy_prompt)
    print(f"  Step 1: Qwen 3.5 9B   -> Total: {res_q1['wall_ms']:.1f}ms (Load: {res_q1['load_ms']:.1f}ms, Eval: {res_q1['eval_ms']:.1f}ms)")
    res_g1 = run_single_inference("gemma4:12b", dummy_prompt)
    print(f"  Step 2: Gemma 4 12B   -> Total: {res_g1['wall_ms']:.1f}ms (Load: {res_g1['load_ms']:.1f}ms, Eval: {res_g1['eval_ms']:.1f}ms)")
    res_d1 = run_single_inference("deepseek-r1:7b", dummy_prompt)
    print(f"  Step 3: DeepSeek-R1   -> Total: {res_d1['wall_ms']:.1f}ms (Load: {res_d1['load_ms']:.1f}ms, Eval: {res_d1['eval_ms']:.1f}ms)")
    
    pipeline_a_load_total = res_q1['load_ms'] + res_g1['load_ms'] + res_d1['load_ms']
    pipeline_a_total = res_q1['wall_ms'] + res_g1['wall_ms'] + res_d1['wall_ms']

    # Pipeline B: Qwen -> Gemma -> Qwen
    print("\nSimulating Pipeline B: Qwen (Analyst) -> Gemma (Writer) -> Qwen (Critic)")
    res_q2 = run_single_inference("qwen3.5:9b", dummy_prompt)
    print(f"  Step 1: Qwen 3.5 9B   -> Total: {res_q2['wall_ms']:.1f}ms (Load: {res_q2['load_ms']:.1f}ms, Eval: {res_q2['eval_ms']:.1f}ms)")
    res_g2 = run_single_inference("gemma4:12b", dummy_prompt)
    print(f"  Step 2: Gemma 4 12B   -> Total: {res_g2['wall_ms']:.1f}ms (Load: {res_g2['load_ms']:.1f}ms, Eval: {res_g2['eval_ms']:.1f}ms)")
    res_q3 = run_single_inference("qwen3.5:9b", dummy_prompt)
    print(f"  Step 3: Qwen 3.5 9B   -> Total: {res_q3['wall_ms']:.1f}ms (Load: {res_q3['load_ms']:.1f}ms, Eval: {res_q3['eval_ms']:.1f}ms)")

    pipeline_b_load_total = res_q2['load_ms'] + res_g2['load_ms'] + res_q3['load_ms']
    pipeline_b_total = res_q2['wall_ms'] + res_g2['wall_ms'] + res_q3['wall_ms']

    return {
        "pipeline_a": {
            "name": "Qwen -> Gemma -> DeepSeek",
            "qwen_load_ms": res_q1['load_ms'],
            "gemma_load_ms": res_g1['load_ms'],
            "deepseek_load_ms": res_d1['load_ms'],
            "total_load_ms": pipeline_a_load_total,
            "total_wall_ms": pipeline_a_total
        },
        "pipeline_b": {
            "name": "Qwen -> Gemma -> Qwen",
            "qwen_load_ms": res_q2['load_ms'],
            "gemma_load_ms": res_g2['load_ms'],
            "qwen_reentry_load_ms": res_q3['load_ms'],
            "total_load_ms": pipeline_b_load_total,
            "total_wall_ms": pipeline_b_total
        }
    }

if __name__ == "__main__":
    results = {}

    # Candidate A: Baseline DeepSeek-R1
    results["Candidate A (DeepSeek-R1 Baseline)"] = benchmark_candidate(
        "Candidate A: DeepSeek-R1 (Baseline)",
        "deepseek-r1:7b"
    )

    # Candidate B: DeepSeek-R1 with minimum reasoning / output constraint
    results["Candidate B (DeepSeek-R1 Fast/Constrained)"] = benchmark_candidate(
        "Candidate B: DeepSeek-R1 (Constrained num_predict=512)",
        "deepseek-r1:7b",
        system_prompt="You are a factual audit engine. Output JSON directly without preamble or conversational reasoning.",
        options={"temperature": 0.05, "num_predict": 512}
    )

    # Candidate C: Qwen 3.5 9B
    results["Candidate C (Qwen 3.5 9B)"] = benchmark_candidate(
        "Candidate C: Qwen 3.5 9B",
        "qwen3.5:9b",
        options={"temperature": 0.05, "num_predict": 512}
    )

    # Candidate D: Phi-4 Mini (Lightweight Validator)
    results["Candidate D (Phi-4 Mini)"] = benchmark_candidate(
        "Candidate D: Phi-4 Mini (3.8B)",
        "phi4-mini:latest",
        options={"temperature": 0.05, "num_predict": 512}
    )

    # Model Residency Experiment
    residency_results = test_model_residency_effect()

    print("\n\n==========================================")
    print("FINAL SUMMARY JSON RESULTS")
    print("==========================================")
    print(json.dumps({
        "candidates": results,
        "residency": residency_results
    }, indent=2))
