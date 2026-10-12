"""Evidence Integrity Guards and Policy Validators.

Enforces:
1. EvidenceNamespaceIntegrity: Strict partition across:
   - EVID-* (Observed empirical truth)
   - CTX-*  (Policy, context, baseline exposure)
   - SCEN-* (Counterfactual, simulated outcome)
2. EvidenceOwnershipIntegrity: Fail-closed dataset and topic alignment:
   - fact.dataset_id == evidence.dataset_id
   - story.topic_id == visual_spec.topic_id == evidence_binding.topic_id == composition_item.topic_id
   - Grain isolation: Personnel/employee grain cannot bind to department/aggregate evidence and vice versa.
"""
from __future__ import annotations

import re
from typing import Any, Literal
from .contracts import AnalyticalFact, BoundEvidence, EvidenceBinding


class EvidenceOwnershipMismatchError(ValueError):
    """Raised when an analytical fact or topic attempts to bind evidence from an unrelated dataset or grain."""
    pass


class EvidenceNamespaceIntegrity:
    """Guards evidence identifier namespaces and ensures semantic isolation."""

    VALID_NAMESPACES = {"EVID", "CTX", "SCEN"}
    PATTERN = re.compile(r"^(EVID|CTX|SCEN)-[A-Za-z0-9_-]+$")

    @classmethod
    def parse_namespace(cls, evidence_id: str) -> str:
        """Extracts the namespace prefix from an evidence identifier."""
        if not evidence_id or not isinstance(evidence_id, str):
            return "UNKNOWN"
        parts = evidence_id.split("-", 1)
        if len(parts) >= 2 and parts[0] in cls.VALID_NAMESPACES:
            return parts[0]
        return "UNKNOWN"

    @classmethod
    def validate_id_format(cls, evidence_id: str) -> bool:
        """Verifies that an evidence ID follows canonical namespaced formatting."""
        return bool(cls.PATTERN.match(evidence_id.strip()))

    @classmethod
    def validate_namespaces(cls, evidence_ids: list[str]) -> list[str]:
        """Audits a collection of evidence IDs for format or unknown namespace violations."""
        violations: list[str] = []
        for eid in evidence_ids:
            if not cls.validate_id_format(eid):
                violations.append(
                    f"Evidence identifier '{eid}' does not conform to governed namespace standards (EVID-*, CTX-*, SCEN-*)."
                )
        return violations

    @classmethod
    def audit_claim_semantics(cls, claim_text: str, evidence_ids: list[str]) -> list[str]:
        """Audits whether claim terminology conflicts with the referenced evidence namespaces."""
        violations: list[str] = []
        low_text = claim_text.lower()
        namespaces = {cls.parse_namespace(eid) for eid in evidence_ids}

        # SCEN- evidence should not make pure empirical claims
        if "SCEN" in namespaces and "EVID" not in namespaces:
            for term in ["empirically observed", "recorded fact", "reconciled record", "measured reality"]:
                if term in low_text:
                    violations.append(
                        f"Counterfactual scenario evidence cited while claiming empirical reality with '{term}'."
                    )

        # Pure EVID evidence should not use simulation terminology without scenario reference
        if "EVID" in namespaces and "SCEN" not in namespaces and "CTX" not in namespaces:
            for term in ["under this simulation", "hypothetical projection", "counterfactual model"]:
                if term in low_text:
                    violations.append(
                        f"Empirical evidence cited with counterfactual simulation language '{term}' without SCEN reference."
                    )

        return violations


class EvidenceOwnershipIntegrity:
    """Enforces strict dataset ownership, topic parity, and grain isolation."""

    @classmethod
    def verify_dataset_ownership(
        cls,
        fact: AnalyticalFact,
        evidence: BoundEvidence,
        fail_closed: bool = True,
    ) -> bool:
        """Ensures an analytical fact only binds to evidence originating from the identical dataset."""
        if evidence.dataset_id is not None and fact.dataset_id != evidence.dataset_id:
            msg = (
                f"Cross-dataset evidence contamination detected: Fact (dataset {fact.dataset_id}) "
                f"cannot bind Evidence '{evidence.evidence_id}' belonging to dataset {evidence.dataset_id}."
            )
            if fail_closed:
                raise EvidenceOwnershipMismatchError(msg)
            return False
        return True

    @classmethod
    def verify_topic_ownership(
        cls,
        topic_id: str,
        visual_spec_topic_id: str | None = None,
        story_topic_id: str | None = None,
        evidence_topic_id: str | None = None,
        fail_closed: bool = True,
    ) -> bool:
        """Enforces that all facets of a topic (story, visual spec, evidence binding) share the exact topic_id."""
        mismatches: list[str] = []
        if visual_spec_topic_id and visual_spec_topic_id != topic_id:
            mismatches.append(f"VisualSpec topic '{visual_spec_topic_id}' != Topic '{topic_id}'")
        if story_topic_id and story_topic_id != topic_id:
            mismatches.append(f"Story topic '{story_topic_id}' != Topic '{topic_id}'")
        if evidence_topic_id and evidence_topic_id != topic_id:
            mismatches.append(f"EvidenceBinding topic '{evidence_topic_id}' != Topic '{topic_id}'")

        if mismatches:
            msg = f"Topic ownership integrity violation: {'; '.join(mismatches)}"
            if fail_closed:
                raise EvidenceOwnershipMismatchError(msg)
            return False
        return True

    @classmethod
    def verify_grain_isolation(
        cls,
        fact_grain: str,
        evidence_grain: str,
        evidence_id: str,
        fail_closed: bool = True,
    ) -> bool:
        """Prevents personnel-level (employee) grain from binding to department-level or aggregate evidence and vice-versa."""
        if not fact_grain or not evidence_grain:
            return True

        fg = fact_grain.strip().lower()
        eg = evidence_grain.strip().lower()

        if fg != eg and (fg in ("employee", "personnel", "individual") or eg in ("employee", "personnel", "individual")):
            msg = (
                f"Grain contamination detected: Fact grain '{fg}' cannot bind to evidence '{evidence_id}' "
                f"with grain '{eg}'."
            )
            if fail_closed:
                raise EvidenceOwnershipMismatchError(msg)
            return False
        return True

    @classmethod
    def validate_binding(
        cls,
        binding: EvidenceBinding,
        fail_closed: bool = True,
    ) -> bool:
        """Validates all bound facts inside an EvidenceBinding."""
        for bf in binding.bound_facts:
            cls.verify_dataset_ownership(bf.fact, bf.evidence, fail_closed=fail_closed)
            cls.verify_grain_isolation(bf.fact.grain, bf.evidence.grain, bf.evidence.evidence_id, fail_closed=fail_closed)
            if bf.topic_id != binding.topic_id:
                msg = f"BoundFact topic '{bf.topic_id}' does not match EvidenceBinding topic '{binding.topic_id}'."
                if fail_closed:
                    raise EvidenceOwnershipMismatchError(msg)
                return False
        return True
