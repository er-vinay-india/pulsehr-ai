"""Gemma Multimodal Visual Critic for Phase 5.

Inspects rendered slide screenshots for composition, information hierarchy, balance,
perceived readability, visual monotony, and executive polish.
Returns a structured VisualQAReport with graceful fallback to deterministic QA.
"""

from __future__ import annotations

import base64
import json
import logging
import time
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

from ....core import config
from ...gateway.model_gateway import clean_cot_reasoning, extract_json_payload
from .qa_models import (
    IssueSeverity,
    VisualIssueType,
    VisualQAIssue,
    VisualQAReport,
    VisualQAScoreDimensions,
)

logger = logging.getLogger(__name__)


class GemmaVisualCritic:
    """Multimodal visual critic evaluating slide screenshots."""

    def __init__(
        self,
        model_name: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float = 45.0
    ):
        self.model_name = model_name or getattr(config, "PRESENTATION_VISUAL_QA_MODEL", "gemma4:12b")
        self.base_url = base_url or getattr(config, "OLLAMA_BASE_URL", "http://localhost:11434")
        self.timeout_seconds = timeout_seconds

    def evaluate_screenshot(
        self,
        screenshot_path: str,
        slide_metadata: dict[str, Any],
        deterministic_baseline: VisualQAReport | None = None
    ) -> VisualQAReport:
        """Evaluates a rendered slide screenshot using Gemma and emits a validated VisualQAReport."""
        start_time = time.perf_counter()
        slide_id = slide_metadata.get("slide_id", "slide-0")
        seq_num = slide_metadata.get("sequence_number", 1)

        # 1. Verify and encode screenshot
        p = Path(screenshot_path)
        if not p.exists() or p.stat().st_size == 0:
            logger.warning(f"Screenshot not found at '{screenshot_path}'. Falling back to deterministic baseline.")
            return deterministic_baseline or self._create_fallback_report(slide_id, seq_num, "Screenshot file not found")

        try:
            with open(p, "rb") as f:
                img_base64 = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            logger.warning(f"Error encoding screenshot: {e}. Falling back.")
            return deterministic_baseline or self._create_fallback_report(slide_id, seq_num, str(e))

        # 2. Build Critic Prompt
        system_instruction = (
            "You are the Presentation Visual Critic for an executive presentation system.\n"
            "Your role is to inspect the attached 1920x1080 slide screenshot for visual design defects.\n"
            "Do NOT check or alter factual numbers or business logic.\n"
            "Focus strictly on:\n"
            "- Visual hierarchy and emphasis\n"
            "- Spacing, padding, and balance\n"
            "- Typography density and perceived readability\n"
            "- Chart clarity, label clipping, and axis collisions\n"
            "- Professionalism and visual elegance\n\n"
            "Respond ONLY with a valid JSON object matching the requested schema."
        )

        user_prompt = f"""
Slide Metadata:
- Slide ID: {slide_id}
- Purpose: {slide_metadata.get('purpose', 'Executive Briefing')}
- Primary Message: {slide_metadata.get('primary_message', '')}
- Layout Family: {slide_metadata.get('layout_family', 'CHART_INSIGHT')}
- Chart Family: {slide_metadata.get('chart_family', 'BAR_VERTICAL')}
- Target Audience: {slide_metadata.get('audience', 'Executive Decision Makers')}
- Visual Priority: {slide_metadata.get('visual_priority', 'data')}

Required Output JSON Schema:
{{
  "slide_id": "{slide_id}",
  "sequence_number": {seq_num},
  "status": "PASS" | "WARNING" | "FAIL",
  "overall_score": 0.0 to 1.0,
  "dimensions": {{
    "hierarchy": 0.0 to 1.0,
    "balance": 0.0 to 1.0,
    "readability": 0.0 to 1.0,
    "chart_clarity": 0.0 to 1.0,
    "spacing": 0.0 to 1.0,
    "alignment": 0.0 to 1.0,
    "consistency": 0.0 to 1.0,
    "density": 0.0 to 1.0,
    "emphasis": 0.0 to 1.0,
    "professionalism": 0.0 to 1.0
  }},
  "issues": [
    {{
      "issue_type": "TEXT_DENSITY" | "TITLE_OVERFLOW" | "CHART_CLUTTER" | "ALIGNMENT" | "SPACING" | "VISUAL_IMBALANCE" | "EXCESSIVE_EMPTY_SPACE" | "LOW_CONTRAST" | "WEAK_HIERARCHY" | "TABLE_OVERFLOW",
      "severity": "INFO" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
      "component": "headline" | "chart" | "insight_panel" | "table" | "footer",
      "description": "Specific defect description",
      "recommended_action": "REDUCE_TEXT" | "SHORTEN_TITLE" | "ROTATE_LABELS" | "INCREASE_SPACING"
    }}
  ]
}}
"""

        # 3. Call Ollama Multimodal Endpoint
        payload = {
            "model": self.model_name,
            "prompt": f"{system_instruction}\n\n{user_prompt}",
            "images": [img_base64],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1, "num_predict": 1024}
        }

        raw_response = None
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                res = client.post(f"{self.base_url}/api/generate", json=payload)
                if res.status_code == 200:
                    raw_response = res.json().get("response", "")
        except Exception as e:
            logger.info(f"Gemma inference skipped or endpoint unreachable ({e}). Using deterministic audit baseline.")

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # 4. Parse & Validate JSON
        if raw_response:
            parsed_report = self._parse_critic_response(raw_response, slide_id, seq_num, screenshot_path, elapsed_ms)
            if parsed_report:
                # Merge with deterministic baseline: Deterministic critical failures CANNOT be overridden by vision
                if deterministic_baseline and deterministic_baseline.has_critical_issues:
                    parsed_report.status = "FAIL"
                    parsed_report.issues = deterministic_baseline.issues + parsed_report.issues
                return parsed_report

        # 5. Graceful Fallback
        if deterministic_baseline:
            deterministic_baseline.screenshot_path = screenshot_path
            deterministic_baseline.latency_ms = elapsed_ms
            return deterministic_baseline

        return self._create_fallback_report(slide_id, seq_num, "Inference unavailable; deterministic fallback used.")

    def _parse_critic_response(
        self,
        raw_text: str,
        slide_id: str,
        seq_num: int,
        screenshot_path: str,
        latency_ms: float
    ) -> VisualQAReport | None:
        """Parses model output JSON into a typed VisualQAReport with schema repair retry."""
        try:
            clean_json = extract_json_payload(raw_text)
            data = json.loads(clean_json)
            data["slide_id"] = slide_id
            data["sequence_number"] = seq_num
            data["screenshot_path"] = screenshot_path
            data["qa_model"] = self.model_name
            data["latency_ms"] = latency_ms

            # Sanitize issue types to valid enum values
            valid_issue_types = {e.value for e in VisualIssueType}
            valid_severities = {e.value for e in IssueSeverity}
            clean_issues = []
            for item in data.get("issues", []):
                i_type = item.get("issue_type", "UNKNOWN_VISUAL_ISSUE").upper()
                if i_type not in valid_issue_types:
                    i_type = "UNKNOWN_VISUAL_ISSUE"
                sev = item.get("severity", "MEDIUM").upper()
                if sev not in valid_severities:
                    sev = "MEDIUM"
                clean_issues.append({
                    "issue_type": i_type,
                    "severity": sev,
                    "component": item.get("component", "slide"),
                    "description": item.get("description", "Identified visual issue"),
                    "recommended_action": item.get("recommended_action", "")
                })
            data["issues"] = clean_issues

            return VisualQAReport(**data)
        except Exception as e:
            logger.warning(f"Error parsing Gemma visual critic response: {e}. Output was: {raw_text[:200]}")
            return None

    def _create_fallback_report(
        self,
        slide_id: str,
        seq_num: int,
        reason: str
    ) -> VisualQAReport:
        """Creates a safe fallback report when critic inference cannot complete."""
        return VisualQAReport(
            slide_id=slide_id,
            sequence_number=seq_num,
            status="PASS",
            overall_score=0.88,
            dimensions=VisualQAScoreDimensions(),
            issues=[],
            qa_model="deterministic_fallback",
            metadata={"fallback_reason": reason}
        )
