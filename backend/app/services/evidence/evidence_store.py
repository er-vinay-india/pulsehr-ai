"""Evidence Store managing verified analytical findings and traceability backlinks."""

import logging
from typing import Any
from .evidence_models import Finding, FindingType, Importance

logger = logging.getLogger(__name__)


class EvidenceStore:
    """In-memory structured repository for analytical findings and their deterministic proofs."""

    def __init__(self):
        self._findings: dict[str, Finding] = {}

    def add_finding(self, finding: Finding):
        self._findings[finding.finding_id] = finding

    def get_finding(self, finding_id: str) -> Finding | None:
        return self._findings.get(finding_id)

    def get_all(self) -> list[Finding]:
        return list(self._findings.values())

    def filter_by_importance(self, importance: Importance | str) -> list[Finding]:
        imp_str = importance.value if isinstance(importance, Importance) else str(importance).lower()
        return [f for f in self._findings.values() if f.importance.value == imp_str]

    def filter_by_type(self, finding_type: FindingType | str) -> list[Finding]:
        ft_str = finding_type.value if isinstance(finding_type, FindingType) else str(finding_type).lower()
        return [f for f in self._findings.values() if f.type.value == ft_str]

    def validate_ids(self, ids: list[str]) -> tuple[list[str], list[str]]:
        """Returns tuple of (valid_ids, invalid_ids)."""
        valid = [fid for fid in ids if fid in self._findings]
        invalid = [fid for fid in ids if fid not in self._findings]
        return valid, invalid

    def export_ledger(self) -> list[dict[str, Any]]:
        """Exports ground-truth evidence ledger compatible with presentation claim auditing."""
        ledger = []
        for f in self._findings.values():
            ledger.append({
                "evidence_id": f.finding_id,
                "finding_id": f.finding_id,
                "type": f.type.value,
                "metric_name": f.metric,
                "segment": f.segment,
                "numeric_value": f.segment_value if f.segment_value is not None else f.overall_value,
                "baseline_value": f.overall_value,
                "difference": f.difference,
                "percentage_gap": f.difference_percentage_points,
                "importance": f.importance.value,
                "headline": f.headline,
                "implication": f.business_implication,
                "proof": [e.model_dump() for e in f.evidence]
            })
        return ledger

    def to_analyst_summary(self) -> list[dict[str, Any]]:
        """Summary array passed into the Report Planner and Writer models."""
        return [
            {
                "finding_id": f.finding_id,
                "type": f.type.value,
                "headline": f.headline,
                "metric": f.metric,
                "segment": f.segment,
                "segment_value": f.segment_value,
                "overall_value": f.overall_value,
                "difference_percentage_points": f.difference_percentage_points,
                "implication": f.business_implication
            }
            for f in self._findings.values()
        ]

    def clear(self):
        self._findings.clear()
