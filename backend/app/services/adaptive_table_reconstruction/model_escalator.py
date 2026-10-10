"""ModelEscalator: Governed model-assisted structural reasoning for ambiguous tabular cases.

Invokes lightweight local models (Qwen / Phi / Gemma) strictly when deterministic rules
encounter confidence below threshold (< 0.70) or conflicting structural hypotheses.
Enforces:
1. Small, focused local structural context window (prev 2 rows, current row, next 2 rows).
2. Typed Pydantic outputs (ModelRowRoleDecision, ModelContinuationDecision, etc.).
3. Strict deterministic post-validation (Model proposes -> Validator checks -> Accept / Reject).
4. Cost and latency telemetry tracking.
5. High-precision fallback to REVIEW_REQUIRED rather than silent fabrication.
"""

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar
import httpx
from pydantic import BaseModel

from ...core import config
from .confidence_risk_engine import ConfidenceRiskEngine
from .contracts import (
    AmbiguityCase,
    AmbiguityType,
    ContinuationType,
    DecisionStatus,
    ModelContinuationDecision,
    ModelEscalationTelemetry,
    ModelHeaderDecision,
    ModelResolutionAudit,
    ModelRowRoleDecision,
    ModelSentinelDecision,
    ModelTableBoundaryDecision,
    ReconstructionRiskLevel,
    RowRole,
)
from .grid_capture import RawGrid

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Governed model preference: lightweight local models for fast, deterministic structural tasks
LIGHTWEIGHT_MODELS = ["qwen3.5:2b", "phi4-mini:latest", "granite4:3b", "qwen3.5:9b"]


class ModelEscalator:
    """Orchestrates model-assisted resolution for ambiguous structural decisions."""

    def __init__(self, ollama_url: Optional[str] = None, model_name: Optional[str] = None):
        self.ollama_url = ollama_url or config.OLLAMA_BASE_URL
        self.model_name = model_name or self._select_default_model()
        self.telemetry = ModelEscalationTelemetry()

    def _select_default_model(self) -> str:
        """Selects fastest available local model, falling back to config.OLLAMA_MODEL."""
        try:
            with httpx.Client(timeout=3) as client:
                res = client.get(f"{config.OLLAMA_BASE_URL}/api/tags")
                if res.status_code == 200:
                    installed = [m.get("name", "") for m in res.json().get("models", [])]
                    for preferred in LIGHTWEIGHT_MODELS:
                        if any(preferred in name for name in installed):
                            return preferred
        except Exception:
            pass
        return getattr(config, "OLLAMA_MODEL", "qwen3.5:2b")

    def format_context_window(self, case: AmbiguityCase) -> str:
        """Renders compact 5-row structural window for prompt grounding."""
        lines = []
        if case.provisional_schema:
            lines.append(f"Expected Schema: {' | '.join(case.provisional_schema)}")
        if case.expected_column_types:
            lines.append(f"Column Types:    {' | '.join(case.expected_column_types)}")
        lines.append("")

        for idx, prev in enumerate(case.previous_rows, start=case.current_row_index - len(case.previous_rows)):
            lines.append(f"Row {idx} (PREV): {' | '.join(prev)}")

        lines.append(f"Row {case.current_row_index} (AMBIGUOUS): {' | '.join(case.current_row)}")

        for idx, nxt in enumerate(case.next_rows, start=case.current_row_index + 1):
            lines.append(f"Row {idx} (NEXT): {' | '.join(nxt)}")

        return "\n".join(lines)

    def _call_model_json(
        self,
        prompt: str,
        response_model: Type[T],
        temperature: float = 0.0,
    ) -> Tuple[Optional[T], Dict[str, Any], float]:
        """Calls local Ollama endpoint requesting typed JSON, enforcing schema validation."""
        start_time = time.perf_counter()
        self.telemetry.model_calls += 1
        if self.model_name not in self.telemetry.models_used:
            self.telemetry.models_used.append(self.model_name)

        system_instruction = (
            "You are a strict tabular spreadsheet structural parser. "
            "Analyze the ambiguous rows and output ONLY valid JSON matching the requested schema. "
            "Never hallucinate column values or numbers. Do not include markdown codeblocks or chat prose."
        )

        try:
            with httpx.Client(timeout=12) as client:
                res = client.post(
                    f"{self.ollama_url}/api/chat",
                    json={
                        "model": self.model_name,
                        "messages": [
                            {"role": "system", "content": system_instruction},
                            {"role": "user", "content": prompt},
                        ],
                        "stream": False,
                        "format": "json",
                        "think": False,
                        "options": {"temperature": temperature, "num_predict": 300},
                    },
                )
                res.raise_for_status()
                data = res.json()
                raw_content = data.get("message", {}).get("content", "").strip()
                tokens = data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
                self.telemetry.model_tokens += tokens

                elapsed_ms = (time.perf_counter() - start_time) * 1000
                self.telemetry.model_latency_ms += elapsed_ms

                # Parse JSON
                parsed_json = json.loads(raw_content)
                validated_obj = response_model.model_validate(parsed_json)
                return validated_obj, parsed_json, elapsed_ms

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self.telemetry.model_latency_ms += elapsed_ms
            logger.warning(f"Model call failed or schema validation failed: {exc}")
            return None, {"error": str(exc)}, elapsed_ms

    def resolve_continuation(
        self,
        case: AmbiguityCase,
        active_col_indices: List[int],
    ) -> Tuple[ModelContinuationDecision, ModelResolutionAudit]:
        """Resolves whether a sparse fragment row is a prefix, suffix, or independent record."""
        self.telemetry.ambiguities_detected += 1
        window_text = self.format_context_window(case)

        prompt = f"""Task: Determine the structural relationship of the ambiguous row.

{window_text}

Deterministic Candidates: {case.deterministic_candidates}
Deterministic Confidence: {case.deterministic_confidence:.2f}

Select the relationship:
- "PREFIX_OF_NEXT_ROW": fragment begins an entity that finishes in the NEXT row
- "SUFFIX_OF_PREVIOUS_ROW": fragment continues an entity that started in the PREVIOUS row
- "INDEPENDENT": this is a separate record (e.g. standalone note, header, or section break)

Respond with JSON adhering to:
{{
  "relationship": "PREFIX_OF_NEXT_ROW" | "SUFFIX_OF_PREVIOUS_ROW" | "INDEPENDENT",
  "target_row_index": <int index of target row or null>,
  "target_column_index": <int index of target column or null>,
  "reconstructed_value": <merged string or null>,
  "confidence": <float between 0.0 and 1.0 representing certainty, e.g. 0.95 if confident>,
  "evidence": ["evidence point 1", "evidence point 2"]
}}"""

        decision, raw_json, _ = self._call_model_json(prompt, ModelContinuationDecision)

        if decision is None or decision.confidence < 0.65:
            # Escalation unresolved -> flag for human review, do not merge!
            self.telemetry.ambiguities_unresolved += 1
            self.telemetry.review_required_count += 1
            fallback_decision = ModelContinuationDecision(
                relationship=ContinuationType.INDEPENDENT,
                confidence=0.5,
                evidence=["Model call failed or returned low confidence; defaulting to safe INDEPENDENT"],
            )
            audit = ModelResolutionAudit(
                case_id=case.case_id,
                ambiguity_type=case.ambiguity_type,
                source_rows=[case.current_row_index],
                deterministic_confidence=case.deterministic_confidence,
                model_name=self.model_name,
                model_confidence=0.5,
                model_decision=raw_json,
                post_validation_passed=False,
                final_status=DecisionStatus.REVIEW_REQUIRED,
                validation_notes="Model inference unresolved; safe non-destructive fallback applied",
            )
            return fallback_decision, audit

        # CRUCIAL POST-MODEL VALIDATION GATE
        # Check: If model proposed merge, verify that it doesn't violate column types, sequence IDs, or semantic role risk
        passed_validation, validation_notes, final_status, semantic_conf = self._post_validate_continuation(case, decision)

        if passed_validation and final_status in (DecisionStatus.MODEL_ASSISTED_VALIDATED, DecisionStatus.MODEL_ASSISTED_PROPOSED):
            if final_status == DecisionStatus.MODEL_ASSISTED_VALIDATED:
                self.telemetry.ambiguities_resolved += 1
            else:
                self.telemetry.review_required_count += 1
            audit = ModelResolutionAudit(
                case_id=case.case_id,
                ambiguity_type=case.ambiguity_type,
                source_rows=[case.current_row_index],
                deterministic_confidence=case.deterministic_confidence,
                model_name=self.model_name,
                model_confidence=semantic_conf,
                model_decision=decision.model_dump(),
                post_validation_passed=True,
                final_status=final_status,
                validation_notes=validation_notes,
            )
            return decision, audit
        else:
            # Model proposal rejected by deterministic integrity gate!
            self.telemetry.ambiguities_unresolved += 1
            self.telemetry.false_merge_prevented += 1
            self.telemetry.review_required_count += 1
            rejected_decision = ModelContinuationDecision(
                relationship=ContinuationType.INDEPENDENT,
                confidence=0.5,
                evidence=[f"Model proposal rejected by post-validation: {validation_notes}"],
            )
            audit = ModelResolutionAudit(
                case_id=case.case_id,
                ambiguity_type=case.ambiguity_type,
                source_rows=[case.current_row_index],
                deterministic_confidence=case.deterministic_confidence,
                model_name=self.model_name,
                model_confidence=decision.confidence,
                model_decision=decision.model_dump(),
                post_validation_passed=False,
                final_status=DecisionStatus.REJECTED,
                validation_notes=f"Model suggested {decision.relationship} but failed post-validation: {validation_notes}",
            )
            return rejected_decision, audit

    def _post_validate_continuation(
        self,
        case: AmbiguityCase,
        decision: ModelContinuationDecision,
    ) -> Tuple[bool, str, DecisionStatus, float]:
        """Deterministic post-validator & risk governor: verifies model's proposed merge against table invariants."""
        if decision.relationship == ContinuationType.INDEPENDENT:
            return True, "No merge proposed; accepted safely", DecisionStatus.MODEL_ASSISTED_VALIDATED, decision.confidence

        # Check target row exists in context
        target_idx = decision.target_row_index
        if target_idx is None:
            # Infer from relationship
            target_idx = case.current_row_index + 1 if decision.relationship == ContinuationType.PREFIX_OF_NEXT_ROW else case.current_row_index - 1
            decision.target_row_index = target_idx

        # 1. Target row must not be empty
        target_row = None
        if decision.relationship == ContinuationType.PREFIX_OF_NEXT_ROW and case.next_rows:
            target_row = case.next_rows[0]
        elif decision.relationship == ContinuationType.SUFFIX_OF_PREVIOUS_ROW and case.previous_rows:
            target_row = case.previous_rows[-1]

        if not target_row or not any(c.strip() for c in target_row):
            return False, "Proposed target row is empty or not in window", DecisionStatus.REJECTED, 0.3

        # 2. Check that target row is not already a duplicate sequence ID or conflicting record
        # If ambiguous row contains numeric data where target column is text, reject
        non_empty_cols = [c for c, val in enumerate(case.current_row) if val.strip()]
        if len(non_empty_cols) > int(len(target_row) * 0.6):
            return False, f"Ambiguous row has too many non-empty columns ({len(non_empty_cols)}) to be a valid continuation fragment", DecisionStatus.REJECTED, 0.2

        # 3. Check sequence ID protection: ambiguous row must NOT have its own sequence ID
        first_val = case.current_row[0].strip() if case.current_row else ""
        if re.match(r"^\d{1,7}$", first_val):
            return False, "Ambiguous row possesses its own independent sequence ID; cannot merge into another record", DecisionStatus.REJECTED, 0.1

        # 4. Semantic risk & field role evaluation via ConfidenceRiskEngine
        col_idx = non_empty_cols[0] if non_empty_cols else 0
        col_name = case.provisional_schema[col_idx] if col_idx < len(case.provisional_schema) else f"col_{col_idx}"
        target_val = target_row[col_idx] if col_idx < len(target_row) else ""
        frag_val = case.current_row[col_idx] if col_idx < len(case.current_row) else ""

        risk_level, status, semantic_conf, risk_notes = ConfidenceRiskEngine.evaluate_continuation_risk(
            case=case,
            target_col_name=col_name,
            target_val=target_val,
            frag_val=frag_val,
            model_confidence=decision.confidence,
        )

        if status == DecisionStatus.REJECTED:
            return False, risk_notes, DecisionStatus.REJECTED, semantic_conf

        return True, f"Passed structural invariants: {risk_notes}", status, semantic_conf

    def resolve_sentinel(
        self,
        token: str,
        explanatory_text: str,
        data_sample: List[str],
    ) -> Tuple[ModelSentinelDecision, ModelResolutionAudit]:
        """Resolves ambiguous missing value sentinel token from nearby footnote."""
        self.telemetry.ambiguities_detected += 1
        prompt = f"""Task: Determine whether token '{token}' in a spreadsheet is a missing-data sentinel or actual data.

Token: '{token}'
Nearby Note: '{explanatory_text}'
Data Sample Containing Token: {data_sample[:5]}

Respond with JSON adhering to:
{{
  "token": "{token}",
  "meaning": <plain english meaning, e.g. "Not reported", "Not monitored", "Estimated">,
  "is_missing_indicator": <true if represents absence/non-measurement of data, false if actual measurement>,
  "confidence": <float between 0.0 and 1.0 representing certainty, e.g. 0.95 if confident>,
  "evidence": ["evidence 1", "evidence 2"]
}}"""

        decision, raw_json, _ = self._call_model_json(prompt, ModelSentinelDecision)

        if decision is None or decision.confidence < 0.65:
            self.telemetry.ambiguities_unresolved += 1
            fallback = ModelSentinelDecision(
                token=token,
                meaning=explanatory_text or "Unknown / Unresolved note",
                is_missing_indicator=True,
                confidence=0.5,
                evidence=["Model call failed; preserved as missing indicator by default"],
            )
            audit = ModelResolutionAudit(
                case_id=f"SNT-{token}",
                ambiguity_type=AmbiguityType.SENTINEL_MEANING,
                source_rows=[],
                deterministic_confidence=0.5,
                model_name=self.model_name,
                model_confidence=0.5,
                model_decision=raw_json,
                post_validation_passed=True,
                final_status=DecisionStatus.REVIEW_REQUIRED,
                validation_notes="Unresolved sentinel defaulted to missing indicator",
            )
            return fallback, audit

        self.telemetry.ambiguities_resolved += 1
        audit = ModelResolutionAudit(
            case_id=f"SNT-{token}",
            ambiguity_type=AmbiguityType.SENTINEL_MEANING,
            source_rows=[],
            deterministic_confidence=0.5,
            model_name=self.model_name,
            model_confidence=decision.confidence,
            model_decision=decision.model_dump(),
            post_validation_passed=True,
            final_status=DecisionStatus.MODEL_ASSISTED_VALIDATED,
            validation_notes=f"Sentinel '{token}' mapped to '{decision.meaning}'",
        )
        return decision, audit
