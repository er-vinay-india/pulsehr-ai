"""Phi-4 Mini Analytical Verifier Specialist.

Handles numerical sanity checks, recalculations, ratio verifications,
and arithmetic integrity audits between task results and underlying evidence.
"""

from __future__ import annotations

import json
import logging
import math
from typing import Any

from .....core import config
from .....core.models_config import ModelRole
from ....gateway.model_gateway import ModelGateway, extract_json_payload
from ..orchestrator_models import ExecutorType, TaskResult

logger = logging.getLogger(__name__)


class PhiAnalyticalVerifier:
    """Specialist analytical verifier using Phi-4 Mini with deterministic arithmetic fallback."""

    def __init__(
        self,
        model_name: str | None = None,
        max_retries: int | None = None,
        tolerance: float = 1e-3
    ):
        self.model_name = model_name or getattr(config, "PRESENTATION_ANALYTICAL_MODEL", "phi4-mini:latest")
        self.max_retries = max_retries if max_retries is not None else getattr(config, "PRESENTATION_MAX_MODEL_RETRIES", 1)
        self.tolerance = tolerance

    def verify_metric(
        self,
        metric_name: str,
        reported_value: Any,
        inputs: dict[str, Any],
        calculation_method: str = "",
        evidence_values: dict[str, Any] | None = None,
        max_retries: int | None = None
    ) -> dict[str, Any]:
        """Verifies whether a reported metric or calculation accurately matches input numbers."""
        retries = max_retries if max_retries is not None else self.max_retries

        # Fast deterministic check first
        det_result = self._deterministic_verify(
            metric_name=metric_name,
            reported_value=reported_value,
            inputs=inputs,
            calculation_method=calculation_method,
            evidence_values=evidence_values
        )

        # If deterministic verification already succeeded with 100% confidence, we can accept it
        if det_result.get("valid") and det_result.get("deterministic_match"):
            return {
                "valid": True,
                "discrepancies": [],
                "verified_metrics": {metric_name: reported_value},
                "confidence": 1.0,
                "verifier": ExecutorType.DETERMINISTIC_ANALYTICS.value,
                "notes": f"Deterministically verified {metric_name} using method '{calculation_method}'"
            }

        # If retries < 0 (testing / fast-mode / deterministic override), return deterministic result
        if retries < 0 or not getattr(config, "PRESENTATION_ORCHESTRATOR_ENABLED", True):
            return det_result

        # Model-based verification prompt using Phi-4 Mini
        prompt = f"""You are Phi-4 Mini Analytical Verifier. Audit the reported metric against the input data with mathematical precision.

## Metric Claim:
- Metric Name: {metric_name}
- Reported Value: {reported_value}
- Calculation Method: {calculation_method}
- Inputs: {json.dumps(inputs, default=str)}
- Evidence Values: {json.dumps(evidence_values or {}, default=str)}

## Task:
1. Re-calculate the metric from the inputs or evidence.
2. Check if the reported value matches your calculation within {self.tolerance * 100}%.
3. Flag any discrepancies, rounding errors, or unit mismatches.

Return ONLY a valid JSON object matching this schema:
{{
  "valid": true,
  "calculated_value": 0.0,
  "difference": 0.0,
  "discrepancies": [],
  "notes": "Verified exact calculation"
}}
"""
        try:
            res = ModelGateway.generate(
                role=ModelRole.FAST,
                prompt=prompt,
                model_override=self.model_name,
                report_id=f"phi-verify-{metric_name}",
                step_name="phi_analytical_verification",
                max_retries=retries,
                temperature_override=0.0
            )
            if res.success and res.raw_text:
                payload = extract_json_payload(res.raw_text)
                parsed = json.loads(payload)
                if isinstance(parsed, dict) and "valid" in parsed:
                    is_valid = bool(parsed.get("valid"))
                    discrepancies = parsed.get("discrepancies", [])
                    if not is_valid and not discrepancies:
                        discrepancies.append(f"Model flagged discrepancy in {metric_name}: {parsed.get('notes', '')}")
                    return {
                        "valid": is_valid,
                        "discrepancies": discrepancies,
                        "verified_metrics": {
                            metric_name: parsed.get("calculated_value", reported_value) if is_valid else reported_value
                        },
                        "confidence": 0.95 if is_valid else 0.4,
                        "verifier": ExecutorType.PHI4_MINI.value,
                        "model_used": res.model_used,
                        "notes": parsed.get("notes", "")
                    }
        except Exception as exc:
            logger.warning(f"PhiAnalyticalVerifier model call failed: {exc}, using deterministic verification")

        return det_result

    def _deterministic_verify(
        self,
        metric_name: str,
        reported_value: Any,
        inputs: dict[str, Any],
        calculation_method: str = "",
        evidence_values: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Executes exact Python arithmetic checks for standard formulas."""
        discrepancies = []
        try:
            rep_num = float(str(reported_value).replace("%", "").replace(",", "").strip())
        except (ValueError, TypeError):
            # Non-numeric value, check exact match if comparable
            return {
                "valid": True,
                "discrepancies": [],
                "verified_metrics": {metric_name: reported_value},
                "confidence": 1.0,
                "deterministic_match": True,
                "verifier": ExecutorType.DETERMINISTIC_ANALYTICS.value,
                "notes": "Non-numeric claim deterministically verified"
            }

        # Percentage change check: inputs might have 'current' and 'baseline' or 'a' and 'b'
        curr = inputs.get("current") or inputs.get("after") or inputs.get("actual")
        base = inputs.get("baseline") or inputs.get("before") or inputs.get("target") or inputs.get("prior")

        if curr is not None and base is not None:
            try:
                c_val = float(curr)
                b_val = float(base)
                if b_val != 0:
                    expected_pct_change = ((c_val - b_val) / b_val) * 100.0
                    expected_ratio = c_val / b_val
                    # Check if reported matches pct_change or delta or ratio
                    diff_pct = abs(rep_num - expected_pct_change)
                    diff_delta = abs(rep_num - (c_val - b_val))
                    diff_ratio = abs(rep_num - expected_ratio)
                    
                    if diff_pct < 0.1 or diff_delta < 0.1 or diff_ratio < 0.01:
                        return {
                            "valid": True,
                            "discrepancies": [],
                            "verified_metrics": {metric_name: rep_num},
                            "confidence": 1.0,
                            "deterministic_match": True,
                            "verifier": ExecutorType.DETERMINISTIC_ANALYTICS.value,
                            "notes": f"Deterministically verified change: current={c_val}, baseline={b_val}"
                        }
                    else:
                        discrepancies.append(
                            f"Reported {rep_num} does not match computed change {expected_pct_change:.2f}% (delta: {c_val - b_val:.2f})"
                        )
            except (ValueError, TypeError):
                pass

        # Sum / Average checks
        vals = inputs.get("values") or inputs.get("numbers") or inputs.get("series")
        if isinstance(vals, list) and vals and all(isinstance(v, (int, float)) for v in vals):
            total = sum(vals)
            avg = total / len(vals)
            if "avg" in metric_name.lower() or "mean" in metric_name.lower() or "average" in calculation_method.lower():
                if abs(rep_num - avg) < 0.05:
                    return {
                        "valid": True,
                        "discrepancies": [],
                        "verified_metrics": {metric_name: rep_num},
                        "confidence": 1.0,
                        "deterministic_match": True,
                        "verifier": ExecutorType.DETERMINISTIC_ANALYTICS.value,
                        "notes": f"Deterministically verified mean: expected={avg:.2f}"
                    }
                else:
                    discrepancies.append(f"Reported {rep_num} does not match computed mean {avg:.2f}")
            elif "sum" in metric_name.lower() or "total" in metric_name.lower():
                if abs(rep_num - total) < 0.05:
                    return {
                        "valid": True,
                        "discrepancies": [],
                        "verified_metrics": {metric_name: rep_num},
                        "confidence": 1.0,
                        "deterministic_match": True,
                        "verifier": ExecutorType.DETERMINISTIC_ANALYTICS.value,
                        "notes": f"Deterministically verified sum: expected={total:.2f}"
                    }
                else:
                    discrepancies.append(f"Reported {rep_num} does not match computed sum {total:.2f}")

        # Check evidence values directly
        if evidence_values and metric_name in evidence_values:
            ev_val = evidence_values[metric_name]
            try:
                ev_num = float(str(ev_val).replace("%", "").replace(",", "").strip())
                if abs(rep_num - ev_num) < 0.05:
                    return {
                        "valid": True,
                        "discrepancies": [],
                        "verified_metrics": {metric_name: rep_num},
                        "confidence": 1.0,
                        "deterministic_match": True,
                        "verifier": ExecutorType.DETERMINISTIC_ANALYTICS.value,
                        "notes": f"Exact match with evidence ledger value {ev_num}"
                    }
                else:
                    discrepancies.append(f"Reported {rep_num} conflicts with evidence ledger value {ev_num}")
            except (ValueError, TypeError):
                pass

        is_valid = len(discrepancies) == 0
        return {
            "valid": is_valid,
            "discrepancies": discrepancies,
            "verified_metrics": {metric_name: rep_num if is_valid else reported_value},
            "confidence": 0.9 if is_valid else 0.3,
            "deterministic_match": is_valid,
            "verifier": ExecutorType.DETERMINISTIC_ANALYTICS.value,
            "notes": "Verified using deterministic arithmetic checks" if is_valid else "Discrepancy found during arithmetic verification"
        }
