"""Drift Monitoring, Schema Anomaly Detection, and Evidence Arbitration.

Provides automated detection for:
- Structural Data Drift (missing/unexpected columns, null spikes, broken joins, duplicate entities)
- Semantic Drift (type/grain/role shifts in catalogued business concepts)
- Evidence Staleness (tracking TTL on EVID nodes)
- Conflicting Evidence Arbitration (reconciling contradictory findings across sheets)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from .contracts import (
    DataDriftReport,
    SemanticDriftReport,
    EvidenceStalenessReport,
    ConflictingEvidenceReport,
)


class DataDriftDetector:
    """Monitors incoming tabular batches for structural anomalies and schema drift."""

    @classmethod
    def audit_dataset_integrity(
        cls,
        dataset_id: str | int,
        records: list[dict[str, Any]],
        baseline_columns: list[str] | None = None,
        entity_key: str = "Employee ID",
        expected_date_cols: list[str] | None = None,
    ) -> DataDriftReport:
        """Runs comprehensive integrity check across tabular dataset."""
        report = DataDriftReport(dataset_id=dataset_id)
        if not records:
            report.has_drift = True
            report.remediation_required = True
            return report

        current_cols = list(records[0].keys())

        # 1. Schema Column Drift
        if baseline_columns:
            base_set = set(baseline_columns)
            curr_set = set(current_cols)
            missing = sorted(list(base_set - curr_set))
            unexpected = sorted(list(curr_set - base_set))
            report.missing_columns = missing
            report.unexpected_columns = unexpected
            if missing:
                report.has_drift = True
                report.remediation_required = True

        # 2. Duplicate Entity Detection
        seen_entities = set()
        duplicates = set()
        for r in records:
            e_id = r.get(entity_key)
            if e_id:
                e_str = str(e_id).strip()
                if e_str in seen_entities:
                    duplicates.add(e_str)
                seen_entities.add(e_str)

        if duplicates:
            report.duplicate_entities = sorted(list(duplicates))
            report.has_drift = True

        # 3. Missing Dates / Date Completeness
        if expected_date_cols:
            for dc in expected_date_cols:
                if dc in current_cols:
                    null_date_count = sum(1 for r in records if r.get(dc) in (None, "", "NaT", "nan"))
                    if null_date_count / len(records) > 0.2:
                        report.null_ratio_spikes[dc] = round(null_date_count / len(records), 3)
                        report.has_drift = True

        # 4. Null Ratio Spikes (> 50% missing values)
        total_rows = len(records)
        for col in current_cols:
            nulls = sum(1 for r in records if r.get(col) in (None, "", "null", "None", "nan"))
            null_ratio = nulls / total_rows
            if null_ratio > 0.5:
                report.null_ratio_spikes[col] = round(null_ratio, 3)
                report.has_drift = True

        if report.missing_columns or report.duplicate_entities:
            report.remediation_required = True

        return report

    @classmethod
    def audit_join_integrity(
        cls,
        left_records: list[dict[str, Any]],
        right_records: list[dict[str, Any]],
        join_key: str,
    ) -> list[str]:
        """Detects orphan records across relational sheet joins."""
        right_keys = {str(r.get(join_key, "")).strip() for r in right_records if r.get(join_key)}
        broken_keys = []
        for r in left_records:
            lk = str(r.get(join_key, "")).strip()
            if lk and lk not in right_keys:
                broken_keys.append(lk)
        return sorted(list(set(broken_keys)))


class SemanticDriftDetector:
    """Monitors semantic concept stability (e.g. attendance percentage shifting to day count)."""

    @classmethod
    def audit_semantic_drift(
        cls,
        dataset_id: str | int,
        column_profiles: list[dict[str, Any]],
    ) -> SemanticDriftReport:
        """Audits column types, domains, and semantic concepts against canonical catalog."""
        report = SemanticDriftReport(dataset_id=dataset_id)
        drifted = []

        for prof in column_profiles:
            col_name = prof.get("name", "")
            inferred_type = prof.get("inferred_type", "")
            historical_type = prof.get("historical_type", "")

            # Check if an expected numeric metric drifted into text
            if historical_type in ("numeric", "float", "integer") and inferred_type in ("string", "text"):
                drifted.append({
                    "column": col_name,
                    "expected_type": historical_type,
                    "actual_type": inferred_type,
                    "reason": "Numerical metric mapped to freeform text",
                })

            # Check if domain was expected between 0-1 (percentage) but has values > 100
            min_val = prof.get("min")
            max_val = prof.get("max")
            concept = prof.get("concept", "")
            if concept == "compliance_percentage" and max_val is not None and max_val > 100:
                drifted.append({
                    "column": col_name,
                    "concept": concept,
                    "reason": f"Value out of bounds for percentage: max={max_val}",
                })

        if drifted:
            report.has_drift = True
            report.drifted_concepts = drifted
            report.severity = "critical" if any("Numerical metric" in d["reason"] for d in drifted) else "medium"

        return report


class EvidenceStalenessGovernor:
    """Tracks and enforces Time-To-Live (TTL) on cached analytical evidence nodes."""

    @classmethod
    def evaluate_staleness(
        cls,
        dataset_id: str | int,
        evidence_nodes: list[dict[str, Any]],
        max_age_hours: float = 24.0,
    ) -> EvidenceStalenessReport:
        """Audits age of evidence items, returning items requiring re-computation."""
        report = EvidenceStalenessReport(dataset_id=dataset_id, max_age_hours=max_age_hours)
        now = datetime.now(timezone.utc)
        stale = []
        fresh = []
        max_age = 0.0

        for node in evidence_nodes:
            nid = node.get("id") or node.get("finding_id", "EVID-UNKNOWN")
            ts_str = node.get("timestamp") or node.get("computed_at")
            if not ts_str:
                stale.append(nid)
                continue

            try:
                ts = datetime.fromisoformat(ts_str)
                age_hours = (now - ts).total_seconds() / 3600.0
                if age_hours > max_age:
                    max_age = age_hours
                if age_hours > max_age_hours:
                    stale.append(nid)
                else:
                    fresh.append(nid)
            except Exception:
                stale.append(nid)

        report.stale_node_ids = stale
        report.fresh_node_ids = fresh
        report.max_age_hours = round(max_age, 2)
        total = len(stale) + len(fresh)
        report.staleness_ratio = round(len(stale) / total, 3) if total > 0 else 0.0
        report.recomputation_needed = len(stale) > 0

        return report


class ConflictingEvidenceArbitrator:
    """Reconciles and flags contradictory assertions between different sheets/findings."""

    @classmethod
    def reconcile(cls, findings: list[dict[str, Any]]) -> ConflictingEvidenceReport:
        """Detects if two findings assert conflicting values for the same metric/cohort."""
        report = ConflictingEvidenceReport()
        cohort_metrics: dict[tuple[str, str], list[dict[str, Any]]] = {}

        for f in findings:
            metric = f.get("metric_name") or f.get("metric", "")
            segment = f.get("segment") or "all"
            key = (str(metric).lower(), str(segment).lower())
            cohort_metrics.setdefault(key, []).append(f)

        conflicts = []
        for (metric, segment), matches in cohort_metrics.items():
            if len(matches) > 1:
                vals = [m.get("numeric_value") for m in matches if m.get("numeric_value") is not None]
                if len(vals) > 1 and max(vals) - min(vals) > 5.0:  # Material divergence > 5 percentage points / units
                    conflicts.append({
                        "metric": metric,
                        "segment": segment,
                        "competing_values": vals,
                        "sources": [m.get("source_sheet") or m.get("finding_id") for m in matches],
                        "divergence": round(max(vals) - min(vals), 2),
                    })

        if conflicts:
            report.conflict_detected = True
            report.conflicting_pairs = conflicts
            report.arbitration_route = "council_arbitration"
            report.arbitration_summary = (
                f"Detected {len(conflicts)} empirical conflicts between sheets. "
                "Escalated to multi-perspective arbitration instead of silent arbitrary picking."
            )

        return report
