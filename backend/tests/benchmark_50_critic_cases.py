"""50-Case Comprehensive Benchmark for Factual Claim Validation.

Compares:
1. Legacy DeepSeek-R1 Critic
2. DeterministicClaimValidator (Tier 1 only)
3. Phi-4 Mini Semantic Critic (Tier 2 only)
4. Two-Tier Hybrid Validator (Deterministic Tier 1 -> Ambiguous Tier 2)

Evaluates:
- F1, Precision, Recall, Accuracy, Specificity
- P50 & P95 Latency (ms)
- LLM bypass rate (%)
- Schema failure rate (%)
- Total LLM calls
"""

import json
import logging
import math
import os
import re
import sys
import time
from typing import Any
import httpx
import numpy as np

from app.core import config
from app.services.evidence.evidence_models import Finding, FindingType, Importance, EvidenceReference
from app.services.evidence.evidence_store import EvidenceStore
from app.services.reporting.writer_agent import WrittenSection
from app.services.critic.deterministic_claim_validator import (
    DeterministicClaimValidator,
    ClaimValidationStatus,
    ToleranceConfig
)
from app.services.critic.critic_agent import (
    CriticAgent,
    ClaimVerdict,
    SectionAuditResult,
    telemetry_tracker
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# 1. GROUND TRUTH EVIDENCE STORE
def build_benchmark_evidence() -> EvidenceStore:
    store = EvidenceStore()
    
    # F-001: Attendance Rate (higher is better)
    store.add_finding(Finding(
        finding_id="F-001",
        type=FindingType.OUTPERFORMER,
        metric="Attendance Rate",
        segment="Engineering",
        segment_value=94.25,
        overall_value=88.0,
        difference=6.25,
        difference_percentage_points=6.25,
        importance=Importance.HIGH,
        headline="Engineering attendance reached 94.25%, outperforming benchmark.",
        business_implication="Engineering maintains exceptional attendance discipline.",
        evidence=[EvidenceReference(
            source_sheet="Sheet1",
            metric="Attendance Rate",
            segment="Engineering",
            row_count=150
        )]
    ))
    
    # F-002: Overtime Hours (lower is better)
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
        headline="Operations logged 14.5 overtime hours, 6.5 above benchmark.",
        business_implication="Operations is under staffing and operational pressure.",
        evidence=[EvidenceReference(
            source_sheet="Sheet1",
            metric="Overtime Hours",
            segment="Operations",
            row_count=200
        )]
    ))
    
    # F-003: Turnover Rate (lower is better, dropped significantly)
    store.add_finding(Finding(
        finding_id="F-003",
        type=FindingType.TREND_SHIFT,
        metric="Turnover Rate",
        segment="Sales",
        segment_value=11.2,
        overall_value=17.5,
        difference=-6.3,
        difference_percentage_points=-36.0,
        importance=Importance.HIGH,
        headline="Sales turnover rate decreased to 11.2%, down 6.3 points.",
        business_implication="Retention improved markedly in the Sales department.",
        evidence=[EvidenceReference(
            source_sheet="Sheet1",
            metric="Turnover Rate",
            segment="Sales",
            row_count=120
        )]
    ))
    
    # F-004: Training Completion (higher is better, dropped)
    store.add_finding(Finding(
        finding_id="F-004",
        type=FindingType.PERFORMANCE_GAP,
        metric="Training Completion",
        segment="Support",
        segment_value=62.0,
        overall_value=85.0,
        difference=-23.0,
        difference_percentage_points=-27.06,
        importance=Importance.HIGH,
        headline="Support training completion dropped to 62.0%, trailing baseline.",
        business_implication="Compliance risk due to delayed mandatory certifications.",
        evidence=[EvidenceReference(
            source_sheet="Sheet1",
            metric="Training Completion",
            segment="Support",
            row_count=80
        )]
    ))
    
    return store


# 2. 50 REPRESENTATIVE TEST CASES
# ground_truth_error = True means there is a factual/semantic violation (SHOULD FAIL)
# ground_truth_error = False means statement is sound and truthful (SHOULD PASS)
BENCHMARK_CASES = [
    # Category 1: Correct claims with exact figures (1-5)
    {"id": 1, "cat": "correct_exact", "is_err": False, "sentence": "Engineering attendance reached 94.25%, exceeding the 88.0% benchmark by 6.25 points [F-001]."},
    {"id": 2, "cat": "correct_exact", "is_err": False, "sentence": "Operations averaged 14.5 overtime hours per person, 6.5 hours above baseline [F-002]."},
    {"id": 3, "cat": "correct_exact", "is_err": False, "sentence": "Sales turnover rate dropped to 11.2%, trailing baseline turnover by 6.3 points [F-003]."},
    {"id": 4, "cat": "correct_exact", "is_err": False, "sentence": "Support training completion stood at 62.0% versus an 85.0% target [F-004]."},
    {"id": 5, "cat": "correct_exact", "is_err": False, "sentence": "Engineering recorded 94.25% attendance across a cohort of 150 team members [F-001]."},

    # Category 2: Rounding within reasonable tolerance (6-10)
    {"id": 6, "cat": "rounding_valid", "is_err": False, "sentence": "Engineering attendance stood at approximately 94.3%, topping the 88% benchmark [F-001]."},
    {"id": 7, "cat": "rounding_valid", "is_err": False, "sentence": "Sales turnover was roughly 11% compared to 17.5% across the organization [F-003]."},
    {"id": 8, "cat": "rounding_valid", "is_err": False, "sentence": "Operations overtime reached ~15 hours, approximately 6.5 hours above baseline [F-002]."},
    {"id": 9, "cat": "rounding_valid", "is_err": False, "sentence": "Sales reduced turnover by approximately 36% relative to benchmark [F-003]."},
    {"id": 10, "cat": "rounding_valid", "is_err": False, "sentence": "Support compliance lagged with 62% training completion [F-004]."},

    # Category 3: Executive paraphrases / qualitative without numbers (11-15)
    {"id": 11, "cat": "executive_paraphrase", "is_err": False, "sentence": "Engineering maintains leading attendance discipline across the organization [F-001]."},
    {"id": 12, "cat": "executive_paraphrase", "is_err": False, "sentence": "Operations continues to experience substantial capacity strain and staffing pressure [F-002]."},
    {"id": 13, "cat": "executive_paraphrase", "is_err": False, "sentence": "Retention in Sales improved markedly during the evaluation window [F-003]."},
    {"id": 14, "cat": "executive_paraphrase", "is_err": False, "sentence": "Support team poses compliance risk due to lagging mandatory certifications [F-004]."},
    {"id": 15, "cat": "executive_paraphrase", "is_err": False, "sentence": "Engineering demonstrated superior commitment compared to the broader enterprise [F-001]."},

    # Category 4: Multiple valid citations & numbers (16-18)
    {"id": 16, "cat": "multiple_citations_valid", "is_err": False, "sentence": "While Engineering attendance led at 94.25% [F-001], Operations logged 14.5 overtime hours [F-002]."},
    {"id": 17, "cat": "multiple_citations_valid", "is_err": False, "sentence": "Sales turnover dropped to 11.2% [F-003], while Support training completion trailed at 62.0% [F-004]."},
    {"id": 18, "cat": "multiple_citations_valid", "is_err": False, "sentence": "Operations exceeded overtime benchmark by 81.25% [F-002] as Sales turnover fell 36.0% [F-003]."},

    # Category 5: Negative metric where decrease is beneficial (19-20)
    {"id": 19, "cat": "polarity_beneficial_decrease", "is_err": False, "sentence": "Sales turnover decreased to 11.2%, representing a welcome improvement in retention [F-003]."},
    {"id": 20, "cat": "polarity_beneficial_decrease", "is_err": False, "sentence": "The reduction in Sales turnover by 6.3 points strengthened organizational stability [F-003]."},

    # Category 6: Wrong values / Alien numbers (21-25) - ERRORS
    {"id": 21, "cat": "wrong_number", "is_err": True, "sentence": "Engineering attendance reached an incredible 99.8% this quarter [F-001]."},
    {"id": 22, "cat": "wrong_number", "is_err": True, "sentence": "Operations reported 28.5 overtime hours per person [F-002]."},
    {"id": 23, "cat": "wrong_number", "is_err": True, "sentence": "Sales turnover escalated to 44.0%, prompting executive concern [F-003]."},
    {"id": 24, "cat": "wrong_number", "is_err": True, "sentence": "Support training completion fell to an alarming 31.5% [F-004]."},
    {"id": 25, "cat": "wrong_number", "is_err": True, "sentence": "Engineering attendance outpaced baseline by 18.4 percentage points [F-001]."},

    # Category 7: Invented / Non-existent Evidence IDs (26-29) - ERRORS
    {"id": 26, "cat": "invented_id", "is_err": True, "sentence": "Executive retention fell by 12% across headquarters [F-999]."},
    {"id": 27, "cat": "invented_id", "is_err": True, "sentence": "Product defect rates increased by 4.2 points in manufacturing [F-404]."},
    {"id": 28, "cat": "invented_id", "is_err": True, "sentence": "Remote worker satisfaction hit an all-time low of 54% [F-888]."},
    {"id": 29, "cat": "invented_id", "is_err": True, "sentence": "Engineering attendance exceeded benchmark [F-042]."},

    # Category 8: Uncited quantitative claims (30-33) - ERRORS
    {"id": 30, "cat": "uncited_quant", "is_err": True, "sentence": "Turnover increased by 17.5% across all operational departments."},
    {"id": 31, "cat": "uncited_quant", "is_err": True, "sentence": "Overtime expenditure surpassed $1.4M over the past six months."},
    {"id": 32, "cat": "uncited_quant", "is_err": True, "sentence": "Attendance slipped 8.2 points in customer support divisions."},
    {"id": 33, "cat": "uncited_quant", "is_err": True, "sentence": "Training completion rate fell 25% organization-wide."},

    # Category 9: Numerical Direction Contradictions (34-38) - ERRORS
    {"id": 34, "cat": "direction_contradiction", "is_err": True, "sentence": "Engineering attendance decreased to 94.25%, falling below benchmark [F-001]."},
    {"id": 35, "cat": "direction_contradiction", "is_err": True, "sentence": "Operations overtime dropped to 14.5 hours, falling 6.5 hours below benchmark [F-002]."},
    {"id": 36, "cat": "direction_contradiction", "is_err": True, "sentence": "Sales turnover increased significantly to 11.2% [F-003]."},
    {"id": 37, "cat": "direction_contradiction", "is_err": True, "sentence": "Support training completion rose to 62.0%, outperforming the organization [F-004]."},
    {"id": 38, "cat": "direction_contradiction", "is_err": True, "sentence": "Sales turnover climbed by 36% relative to peers [F-003]."},

    # Category 10: Sentiment / Outcome Contradictions (39-41) - ERRORS
    {"id": 39, "cat": "sentiment_contradiction", "is_err": True, "sentence": "Support training completion improved to 62.0%, delivering strong compliance results [F-004]."},
    {"id": 40, "cat": "sentiment_contradiction", "is_err": True, "sentence": "The reduction in Sales turnover worsened employee retention and destabilized teams [F-003]."},
    {"id": 41, "cat": "sentiment_contradiction", "is_err": True, "sentence": "Operations overtime rose to 14.5 hours, representing a healthy and favorable staffing balance [F-002]."},

    # Category 11: Denominator / Sample size distortion (42-43) - ERRORS
    {"id": 42, "cat": "denominator_distortion", "is_err": True, "sentence": "Engineering attendance was 94.25% across 15000 surveyed employees [F-001]."},
    {"id": 43, "cat": "denominator_distortion", "is_err": True, "sentence": "Support training completion of 62.0% affected 5000 customer representatives [F-004]."},

    # Category 12: Unsupported Alien Metrics (44-45) - ERRORS
    {"id": 44, "cat": "alien_metric", "is_err": True, "sentence": "Engineering eNPS reached +48 based on attendance data [F-001]."},
    {"id": 45, "cat": "alien_metric", "is_err": True, "sentence": "Operations employee burnout score reached 8.4/10 [F-002]."},

    # Category 13: Causal Overreach / Leaps (46-48) - ERRORS
    {"id": 46, "cat": "causal_overreach", "is_err": True, "sentence": "Heavy overtime in Operations caused defect counts to spike in assembly [F-002]."},
    {"id": 47, "cat": "causal_overreach", "is_err": True, "sentence": "Sales turnover dropped because executive compensation was restructured [F-003]."},
    {"id": 48, "cat": "causal_overreach", "is_err": True, "sentence": "Lax management caused Support training completion to fall to 62.0% [F-004]."},

    # Category 14: Subtle Semantic Distortions / Catastrophic Exaggeration (49-50) - ERRORS
    {"id": 49, "cat": "semantic_distortion", "is_err": True, "sentence": "Operations is in complete operational collapse and total chaos due to overtime [F-002]."},
    {"id": 50, "cat": "semantic_distortion", "is_err": True, "sentence": "Engineering experienced disastrous attendance failure trailing organizational peers [F-001]."}
]


def calculate_metrics(y_true: list[bool], y_pred: list[bool]) -> dict[str, Any]:
    """Calculates classification metrics for error detection (True = Error detected)."""
    tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt and yp)
    fp = sum(1 for yt, yp in zip(y_true, y_pred) if not yt and yp)
    fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt and not yp)
    tn = sum(1 for yt, yp in zip(y_true, y_pred) if not yt and not yp)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / len(y_true) if len(y_true) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0

    return {
        "TP": tp, "FP": fp, "FN": fn, "TN": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
        "specificity": round(specificity, 4)
    }


def run_benchmark():
    evidence_store = build_benchmark_evidence()
    total_cases = len(BENCHMARK_CASES)
    ground_truth_errors = [c["is_err"] for c in BENCHMARK_CASES]

    logger.info(f"Loaded {total_cases} benchmark cases ({sum(ground_truth_errors)} errors, {total_cases - sum(ground_truth_errors)} sound statements).")

    # ----------------------------------------------------
    # RUNNER 1: DETERMINISTIC CLAIM VALIDATOR ALONE
    # ----------------------------------------------------
    logger.info("=== Running Runner 1: DeterministicClaimValidator (Tier 1 Alone) ===")
    det_latencies = []
    det_predictions = []  # True if flagged as error (INVALID)

    for case in BENCHMARK_CASES:
        t0 = time.perf_counter()
        res = DeterministicClaimValidator.validate_claim(case["sentence"], evidence_store)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        det_latencies.append(elapsed_ms)
        # In Tier 1 alone, INVALID = error detected; VERIFIED/AMBIGUOUS = not flagged as error
        is_flagged_error = (res.status == ClaimValidationStatus.INVALID)
        det_predictions.append(is_flagged_error)

    det_metrics = calculate_metrics(ground_truth_errors, det_predictions)

    # ----------------------------------------------------
    # RUNNER 2: TWO-TIER HYBRID VALIDATOR (Deterministic + Phi-4 Mini)
    # ----------------------------------------------------
    logger.info("=== Running Runner 2: Two-Tier Hybrid Validator (Deterministic + Phi-4 Mini) ===")
    hybrid_latencies = []
    hybrid_predictions = []
    hybrid_llm_calls = 0
    hybrid_det_bypassed = 0
    hybrid_schema_failures = 0

    for idx, case in enumerate(BENCHMARK_CASES):
        t0 = time.perf_counter()
        # Create a mock single-claim section
        mock_sec = WrittenSection(
            section_id=f"CASE-{case['id']}",
            title="Validation Case",
            key_takeaway="Benchmark audit",
            bullet_points=[case["sentence"]],
            finding_ids=["F-001", "F-002", "F-003", "F-004"]
        )
        audit_res = CriticAgent.audit_section(mock_sec, evidence_store, report_id=f"bench-{case['id']}", mode="hybrid")
        elapsed_ms = (time.perf_counter() - t0) * 1000
        hybrid_latencies.append(elapsed_ms)

        # Flagged as error if not passed or has UNSUPPORTED/CONTRADICTORY claims
        is_flagged_error = not audit_res.passed
        hybrid_predictions.append(is_flagged_error)

        if audit_res.telemetry.get("ambiguous_resolved_by_phi", 0) > 0:
            hybrid_llm_calls += 1
        else:
            hybrid_det_bypassed += 1

    hybrid_metrics = calculate_metrics(ground_truth_errors, hybrid_predictions)
    hybrid_bypass_pct = (hybrid_det_bypassed / total_cases) * 100.0

    # ----------------------------------------------------
    # RUNNER 3: LEGACY DEEPSEEK R1 (Measured on all 50 cases)
    # ----------------------------------------------------
    logger.info("=== Running Runner 3: Legacy DeepSeek R1 Whole-Section Audit ===")
    legacy_latencies = []
    legacy_predictions = []
    legacy_llm_calls = 0
    legacy_schema_failures = 0

    for idx, case in enumerate(BENCHMARK_CASES):
        t0 = time.perf_counter()
        mock_sec = WrittenSection(
            section_id=f"CASE-{case['id']}",
            title="Validation Case",
            key_takeaway="Benchmark audit",
            bullet_points=[case["sentence"]],
            finding_ids=["F-001", "F-002", "F-003", "F-004"]
        )
        audit_res = CriticAgent.audit_section(mock_sec, evidence_store, report_id=f"legacy-{case['id']}", mode="legacy")
        elapsed_ms = (time.perf_counter() - t0) * 1000
        legacy_latencies.append(elapsed_ms)
        legacy_llm_calls += 1

        is_flagged_error = not audit_res.passed
        legacy_predictions.append(is_flagged_error)

    legacy_metrics = calculate_metrics(ground_truth_errors, legacy_predictions)

    # ----------------------------------------------------
    # REPORTING AND SUMMARY TABLES
    # ----------------------------------------------------
    print("\n" + "=" * 80)
    print("50-CASE BENCHMARK RESULTS: LEGACY DEEPSEEK vs TWO-TIER HYBRID VALIDATOR")
    print("=" * 80)

    def _p50(arr): return float(np.percentile(arr, 50))
    def _p95(arr): return float(np.percentile(arr, 95))

    print(f"\n{'Metric':<30} | {'Deterministic Only':<18} | {'Legacy DeepSeek':<18} | {'Hybrid (Two-Tier)':<18}")
    print("-" * 92)
    print(f"{'Precision':<30} | {det_metrics['precision']:<18.4f} | {legacy_metrics['precision']:<18.4f} | {hybrid_metrics['precision']:<18.4f}")
    print(f"{'Recall':<30} | {det_metrics['recall']:<18.4f} | {legacy_metrics['recall']:<18.4f} | {hybrid_metrics['recall']:<18.4f}")
    print(f"{'F1 Score':<30} | {det_metrics['f1']:<18.4f} | {legacy_metrics['f1']:<18.4f} | {hybrid_metrics['f1']:<18.4f}")
    print(f"{'Accuracy':<30} | {det_metrics['accuracy']:<18.4f} | {legacy_metrics['accuracy']:<18.4f} | {hybrid_metrics['accuracy']:<18.4f}")
    print(f"{'True Positives (TP)':<30} | {det_metrics['TP']:<18} | {legacy_metrics['TP']:<18} | {hybrid_metrics['TP']:<18}")
    print(f"{'False Positives (FP)':<30} | {det_metrics['FP']:<18} | {legacy_metrics['FP']:<18} | {hybrid_metrics['FP']:<18}")
    print(f"{'True Negatives (TN)':<30} | {det_metrics['TN']:<18} | {legacy_metrics['TN']:<18} | {hybrid_metrics['TN']:<18}")
    print(f"{'False Negatives (FN)':<30} | {det_metrics['FN']:<18} | {legacy_metrics['FN']:<18} | {hybrid_metrics['FN']:<18}")
    print("-" * 92)
    print(f"{'Mean Latency (ms)':<30} | {np.mean(det_latencies):<18.2f} | {np.mean(legacy_latencies):<18.2f} | {np.mean(hybrid_latencies):<18.2f}")
    print(f"{'P50 Latency (ms)':<30} | {_p50(det_latencies):<18.2f} | {_p50(legacy_latencies):<18.2f} | {_p50(hybrid_latencies):<18.2f}")
    print(f"{'P95 Latency (ms)':<30} | {_p95(det_latencies):<18.2f} | {_p95(legacy_latencies):<18.2f} | {_p95(hybrid_latencies):<18.2f}")
    print("-" * 92)
    print(f"{'Total LLM Calls':<30} | {'0':<18} | {legacy_llm_calls:<18} | {hybrid_llm_calls:<18}")
    print(f"{'LLM Bypass Rate (%)':<30} | {'100.0%':<18} | {'0.0%':<18} | {hybrid_bypass_pct:<17.1f}%")
    print("=" * 80)

    # Save benchmark json artifact
    summary_data = {
        "total_cases": total_cases,
        "ground_truth_errors": sum(ground_truth_errors),
        "ground_truth_sound": total_cases - sum(ground_truth_errors),
        "deterministic": {
            "metrics": det_metrics,
            "mean_latency_ms": float(np.mean(det_latencies)),
            "p50_latency_ms": _p50(det_latencies),
            "p95_latency_ms": _p95(det_latencies),
            "llm_bypass_rate": 100.0
        },
        "legacy_deepseek": {
            "metrics": legacy_metrics,
            "mean_latency_ms": float(np.mean(legacy_latencies)),
            "p50_latency_ms": _p50(legacy_latencies),
            "p95_latency_ms": _p95(legacy_latencies),
            "llm_calls": legacy_llm_calls,
            "llm_bypass_rate": 0.0
        },
        "hybrid_two_tier": {
            "metrics": hybrid_metrics,
            "mean_latency_ms": float(np.mean(hybrid_latencies)),
            "p50_latency_ms": _p50(hybrid_latencies),
            "p95_latency_ms": _p95(hybrid_latencies),
            "llm_calls": hybrid_llm_calls,
            "llm_bypass_rate": hybrid_bypass_pct
        }
    }
    with open("backend/tests/benchmark_50_results.json", "w") as f:
        json.dump(summary_data, f, indent=2)

    logger.info("Saved benchmark results to backend/tests/benchmark_50_results.json")
    return summary_data


if __name__ == "__main__":
    run_benchmark()
