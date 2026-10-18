"""
HighView Ingestion V2 — Finding Registry & Stable Fingerprinting
Stage 8: Analytical EDA-B
Manages stable semantic identities, deduplication, and EVID-* compatibility for analytical findings.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any
from app.services.ingestion_v2.contracts.analytics import AnalyticalFinding, FindingType


def generate_finding_fingerprint(
    dataset_id: str,
    finding_type: FindingType | str,
    metric_definition: str | None,
    dimension_definition: str | None,
    target_grain: str | None,
    population_definition: str | None = None,
    filter_dict: dict[str, Any] | None = None,
    analysis_method: str | None = None,
) -> str:
    """
    Generate a deterministic SHA-256 fingerprint for an analytical finding.
    Excludes volatile fields: timestamps, run_id, wording/descriptions.
    Same underlying data + same analytical definition = same fingerprint.
    """
    f_type_str = finding_type.value if isinstance(finding_type, FindingType) else str(finding_type)
    norm_filters = json.dumps(filter_dict or {}, sort_keys=True)
    
    payload = "|".join([
        str(dataset_id).strip(),
        f_type_str.strip().upper(),
        (metric_definition or "").strip().lower(),
        (dimension_definition or "").strip().lower(),
        (target_grain or "").strip().upper(),
        (population_definition or "ALL").strip().upper(),
        norm_filters,
        (analysis_method or "DEFAULT").strip().upper(),
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class FindingRegistry:
    """
    Registry for deduplicating findings and managing EVID-* references.
    """

    def __init__(self, dataset_id: str):
        self.dataset_id = dataset_id
        self._seen_fingerprints: set[str] = set()
        self._findings: list[AnalyticalFinding] = []
        self._counter: int = 1

    def register(
        self,
        finding_type: FindingType | str,
        description: str,
        source_table_ids: list[str],
        source_column_ids: list[str],
        target_grain: str | None,
        result: Any,
        metric_definition: str | None = None,
        dimension_definition: str | None = None,
        population_definition: str | None = "ALL",
        numerator_definition: str | None = None,
        denominator_definition: str | None = None,
        join_plan_ids: list[str] | None = None,
        effect_size: float | None = None,
        confidence: float = 1.0,
        limitations: list[str] | None = None,
        filter_provenance: dict[str, Any] | None = None,
        analysis_method: str | None = None,
        tukey_evidence: Any = None,
        hypothesis_evidence: Any = None,
        statistical_evidence: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> AnalyticalFinding | None:
        """
        Register a new finding if its semantic fingerprint is unique.
        Returns the created AnalyticalFinding, or None if deduplicated.
        """
        f_type_val = finding_type.value if isinstance(finding_type, FindingType) else str(finding_type)
        fingerprint = generate_finding_fingerprint(
            dataset_id=self.dataset_id,
            finding_type=f_type_val,
            metric_definition=metric_definition,
            dimension_definition=dimension_definition,
            target_grain=target_grain,
            population_definition=population_definition,
            filter_dict=filter_provenance,
            analysis_method=analysis_method,
        )

        if fingerprint in self._seen_fingerprints:
            return None  # Deduplicated

        self._seen_fingerprints.add(fingerprint)

        # Generate canonical EVID-* ID
        finding_id = f"find_{fingerprint}"
        evidence_id = f"EVID-{self._counter:04d}"
        self._counter += 1

        finding = AnalyticalFinding(
            finding_id=finding_id,
            finding_type=f_type_val,
            affected_tables=source_table_ids,
            affected_columns=source_column_ids,
            evidence_ref=evidence_id,
            description=description,
            dataset_id=self.dataset_id,
            source_table_ids=source_table_ids,
            source_column_ids=source_column_ids,
            target_grain=target_grain,
            join_plan_ids=join_plan_ids or [],
            metric_definition=metric_definition,
            dimension_definition=dimension_definition,
            population_definition=population_definition,
            numerator_definition=numerator_definition,
            denominator_definition=denominator_definition,
            result=result,
            effect_size=effect_size,
            confidence=confidence,
            evidence_refs=[evidence_id],
            provenance_refs=source_table_ids + source_column_ids,
            limitations=limitations or [],
            finding_fingerprint=fingerprint,
            filter_provenance=filter_provenance or {},
            tukey_outlier_evidence=tukey_evidence,
            hypothesis_test_evidence=hypothesis_evidence,
            statistical_test_evidence=statistical_evidence,
            metadata=metadata or {},
        )
        self._findings.append(finding)
        return finding

    @property
    def findings(self) -> list[AnalyticalFinding]:
        return list(self._findings)
