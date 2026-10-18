"""
HighView Ingestion V2 — Finding Registry & Stable Fingerprinting
Stage 8: Analytical EDA-B
Manages stable semantic identities, deduplication, and EVID-* compatibility for analytical findings.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any
from app.services.ingestion_v2.contracts.analytics import AnalyticalFinding, FindingType, NullPolicy


def generate_finding_fingerprint(
    dataset_id: str,
    finding_type: FindingType | str,
    metric_definition: str | None,
    dimension_definition: str | None,
    target_grain: str | None,
    population_definition: str | None = None,
    filter_dict: dict[str, Any] | None = None,
    analysis_method: str | None = None,
    time_range: str | None = None,
    null_policy: NullPolicy | str | None = NullPolicy.EXCLUDE_NULL,
) -> str:
    """
    Generate a deterministic SHA-256 fingerprint for an analytical finding.
    Strictly based on semantic analytical definition:
    - dataset_id
    - finding_type
    - metric_definition
    - dimension_definition
    - target_grain
    - population_definition
    - filter_dict
    - time_range
    - analysis_method
    - null_policy

    Excludes volatile fields:
    - display wording / description
    - timestamps / created_at
    - run_id
    - presentation wording
    """
    f_type_str = finding_type.value if isinstance(finding_type, FindingType) else str(finding_type)
    np_str = null_policy.value if isinstance(null_policy, NullPolicy) else str(null_policy or "EXCLUDE_NULL")
    norm_filters = json.dumps(filter_dict or {}, sort_keys=True)

    payload = "|".join([
        str(dataset_id).strip(),
        f_type_str.strip().upper(),
        (metric_definition or "").strip().lower(),
        (dimension_definition or "").strip().lower(),
        (target_grain or "").strip().upper(),
        (population_definition or "ALL").strip().upper(),
        norm_filters,
        (time_range or "").strip().upper(),
        (analysis_method or "DEFAULT").strip().upper(),
        np_str.strip().upper(),
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class FindingRegistry:
    """
    Registry for deduplicating findings and managing EVID-* references.
    Ensures semantically equivalent findings resolve to a single canonical finding
    with alias and provenance tracking.
    """

    def __init__(self, dataset_id: str):
        self.dataset_id = dataset_id
        self._seen_fingerprints: set[str] = set()
        self._fingerprint_to_finding: dict[str, AnalyticalFinding] = {}
        self._findings: list[AnalyticalFinding] = []
        self._counter: int = 1
        self._deduplication_events: list[dict[str, Any]] = []

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
        time_range: str | None = None,
        null_policy: NullPolicy | str = NullPolicy.EXCLUDE_NULL,
        eligible_population: str | None = None,
        imputation_method: str | None = None,
        tukey_evidence: Any = None,
        hypothesis_evidence: Any = None,
        statistical_evidence: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> AnalyticalFinding:
        """
        Register a new finding if its semantic fingerprint is unique.
        If a semantically identical finding already exists, records the incoming description
        as an alias/provenance on the canonical finding and returns the canonical finding.
        """
        f_type_val = finding_type.value if isinstance(finding_type, FindingType) else str(finding_type)
        np_val = null_policy if isinstance(null_policy, NullPolicy) else NullPolicy(str(null_policy))

        fingerprint = generate_finding_fingerprint(
            dataset_id=self.dataset_id,
            finding_type=f_type_val,
            metric_definition=metric_definition,
            dimension_definition=dimension_definition,
            target_grain=target_grain,
            population_definition=population_definition,
            filter_dict=filter_provenance,
            analysis_method=analysis_method,
            time_range=time_range,
            null_policy=np_val,
        )

        if fingerprint in self._seen_fingerprints:
            canonical = self._fingerprint_to_finding[fingerprint]
            # Record alias if description is different
            aliases = canonical.metadata.setdefault("aliases", [])
            if description not in aliases and description != canonical.description:
                aliases.append(description)
            self._deduplication_events.append({
                "fingerprint": fingerprint,
                "canonical_id": canonical.finding_id,
                "alias_description": description,
            })
            return canonical

        self._seen_fingerprints.add(fingerprint)

        # Generate canonical EVID-* ID
        finding_id = f"find_{fingerprint}"
        evidence_id = f"EVID-{self._counter:04d}"
        self._counter += 1

        finding_meta = dict(metadata or {})
        finding_meta.setdefault("aliases", [])

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
            null_policy=np_val,
            time_range=time_range,
            eligible_population=eligible_population or population_definition,
            imputation_method=imputation_method,
            tukey_outlier_evidence=tukey_evidence,
            hypothesis_test_evidence=hypothesis_evidence,
            statistical_test_evidence=statistical_evidence,
            metadata=finding_meta,
        )
        self._fingerprint_to_finding[fingerprint] = finding
        self._findings.append(finding)
        return finding

    @property
    def findings(self) -> list[AnalyticalFinding]:
        return list(self._findings)

    @property
    def deduplication_events(self) -> list[dict[str, Any]]:
        return list(self._deduplication_events)
