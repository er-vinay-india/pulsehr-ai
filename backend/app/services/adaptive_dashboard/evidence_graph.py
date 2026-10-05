"""Evidence Graph Store and EvidenceItem Models.

Provides an authoritative evidence repository where every metric, claim,
dashboard card, and narrative statement binds back to a unique, immutable
evidence node (`EVID-xxx`).
"""
from __future__ import annotations

import re
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from .contracts import UnifiedFinding


class EvidenceItem(BaseModel):
    """Governed evidence unit bound to immutable data calculations."""
    model_config = ConfigDict(extra="forbid")

    evidence_id: str  # e.g., "EVID-001"
    claim_type: Literal[
        "segment_difference",
        "trend_change",
        "concentration",
        "outlier",
        "distribution_skew",
        "capacity_gap",
        "backlog_aging",
        "retention_decay",
        "target_gap",
        "general_fact",
    ] = "general_fact"
    subject: str
    metric: str
    value: float | int | None = None
    formatted_value: str
    comparison_value: float | int | None = None
    formatted_comparison: str | None = None
    difference_pct: float | None = None
    population: int = 0
    period: str | None = None
    source_table: str
    calculation: str
    confidence: Literal["HIGH", "MEDIUM", "LOW"] = "HIGH"
    causal_classification: Literal["OBSERVED", "ASSOCIATED", "INFERRED", "HYPOTHESIS"] = "OBSERVED"
    sample_warning: bool = False
    provenance: str
    tokens: dict[str, Any] = Field(default_factory=dict)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class EvidenceGraph(BaseModel):
    """Governed graph of verified evidence objects for a dataset sheet."""
    model_config = ConfigDict(extra="forbid")

    sheet_id: int
    snapshot: str
    nodes: list[EvidenceItem] = Field(default_factory=list)

    def get_by_id(self, evidence_id: str) -> EvidenceItem | None:
        """Fetch node by EVID ID."""
        for item in self.nodes:
            if item.evidence_id == evidence_id:
                return item
        return None

    def find_by_subject_or_metric(self, query: str) -> list[EvidenceItem]:
        """Find evidence items matching subject or metric."""
        q = query.lower()
        return [
            item for item in self.nodes
            if q in item.subject.lower() or q in item.metric.lower()
        ]

    def hydrate_template(self, template: str, evidence_ids: list[str]) -> str:
        """Deterministically hydrates a narrative template using tokens from referenced evidence IDs.
        
        Prevents LLM numeric hallucination by strictly injecting verified calculations.
        Example template: "{subject} recorded {value} {unit}, which is {difference_pct}% above baseline."
        """
        if not evidence_ids:
            return template

        primary = self.get_by_id(evidence_ids[0])
        if not primary:
            return template

        rendered = template
        for k, v in primary.tokens.items():
            placeholder = f"{{{k}}}"
            if placeholder in rendered:
                rendered = rendered.replace(placeholder, str(v))
        return rendered


def findings_to_evidence_graph(
    findings: list[UnifiedFinding],
    sheet_id: int,
    snapshot: str,
    source_table: str = "sheet_curated_rows",
) -> EvidenceGraph:
    """Converts a collection of UnifiedFindings into a governed EvidenceGraph with EVID-xxx IDs."""
    nodes: list[EvidenceItem] = []

    for idx, f in enumerate(findings, start=1):
        evid_id = f"EVID-{idx:03d}"

        # Classify claim type
        claim_type: Literal[
            "segment_difference",
            "trend_change",
            "concentration",
            "outlier",
            "distribution_skew",
            "capacity_gap",
            "backlog_aging",
            "retention_decay",
            "target_gap",
            "general_fact",
        ] = "general_fact"

        rec = f.recipe_id.lower()
        if "segment" in rec or "disparity" in rec:
            claim_type = "segment_difference"
        elif "change" in rec or "trend" in rec or "shift" in rec:
            claim_type = "trend_change"
        elif "reasons" in rec or "concentration" in rec:
            claim_type = "concentration"
        elif "capacity" in rec or "demand" in rec:
            claim_type = "capacity_gap"
        elif "backlog" in rec or "aging" in rec:
            claim_type = "backlog_aging"
        elif "cohort" in rec or "retention" in rec:
            claim_type = "retention_decay"
        elif "target" in rec:
            claim_type = "target_gap"
        elif "tail" in rec or "spread" in rec:
            claim_type = "distribution_skew"

        # Determine causal classification
        causal: Literal["OBSERVED", "ASSOCIATED", "INFERRED", "HYPOTHESIS"] = "OBSERVED"
        if f.allowed_claim_level == "statistical_association":
            causal = "ASSOCIATED"
        elif f.allowed_claim_level in ("non_causal_forecast", "exploratory_pattern"):
            causal = "INFERRED"
        elif f.allowed_claim_level == "policy_exposure":
            causal = "HYPOTHESIS"

        # Parse population number
        population = 0
        pop_match = re.search(r"(\d+)\s*(?:records|employees|observations|rows|units|items)", f.population_or_exposure, re.IGNORECASE)
        if pop_match:
            try:
                population = int(pop_match.group(1))
            except ValueError:
                population = 0

        # Confidence heuristic
        confidence: Literal["HIGH", "MEDIUM", "LOW"] = "HIGH"
        sample_warning = False
        if population > 0 and population < 15:
            confidence = "LOW"
            sample_warning = True
        elif population >= 15 and population < 30:
            confidence = "MEDIUM"

        # Difference pct heuristic
        diff_pct: float | None = None
        if f.comparison_and_effect:
            pct_match = re.search(r"([+-]?\d+(?:\.\d+)?)\s*%", f.comparison_and_effect)
            if pct_match:
                try:
                    diff_pct = float(pct_match.group(1))
                except ValueError:
                    diff_pct = None

        tokens = {
            "evidence_id": evid_id,
            "subject": f.short_business_title,
            "metric": f.recipe_id.replace("recipe_", "").replace("_", " "),
            "value": f.typed_value if f.typed_value is not None else f.formatted_value,
            "formatted_value": f.formatted_value,
            "unit": f.unit,
            "comparison": f.comparison_and_effect or "benchmark",
            "difference_pct": diff_pct if diff_pct is not None else 0.0,
            "population": population or f.population_or_exposure,
        }

        nodes.append(
            EvidenceItem(
                evidence_id=evid_id,
                claim_type=claim_type,
                subject=f.short_business_title,
                metric=f.recipe_id,
                value=f.typed_value,
                formatted_value=f.formatted_value,
                difference_pct=diff_pct,
                population=population,
                source_table=source_table,
                calculation=f.evidence_bound_observation,
                confidence=confidence,
                causal_classification=causal,
                sample_warning=sample_warning,
                provenance=f.snapshot,
                tokens=tokens,
                supporting_evidence_ids=[],
                limitations=f.limitations,
            )
        )

    return EvidenceGraph(
        sheet_id=sheet_id,
        snapshot=snapshot,
        nodes=nodes,
    )
