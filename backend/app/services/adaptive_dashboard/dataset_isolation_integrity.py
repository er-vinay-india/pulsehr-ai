"""Dataset Isolation Integrity & Cross-Domain Provenance Guard.

Enforces strict mathematical and provenance isolation across datasets:
1. Hard invariant: artifact.dataset_id == active_dataset_id.
2. Two-sheet relationships: left_sheet.dataset_id == right_sheet.dataset_id == active_dataset_id.
3. Cross-Domain Semantic Guard: Prevents environmental pollutants (SO2, NO2, PM10) from leaking
   into workforce datasets, and workforce concepts from leaking into environmental datasets.
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class DatasetIsolationViolation(Exception):
    """Raised when an analytical artifact violates dataset provenance or boundary isolation."""
    pass


class DatasetIsolationIntegrity:
    """Guards dataset boundaries and prevents cross-dataset contamination and leakage."""

    ENVIRONMENTAL_POLLUTANT_TOKENS = {
        "so2", "no2", "pm10", "pm2.5", "pm25", "aqi", "cpcb", "pollutant",
        "jharia", "brynihat", "amravati", "katihar", "saharsa"
    }

    WORKFORCE_TOKENS = {
        "attendance", "leaves", "employee", "wfo", "absenteeism", "headcount",
        "clock_in", "clock_out", "present_days", "leave_days"
    }

    @classmethod
    def validate_sheet_relationship(
        cls,
        rel_id: Any,
        left_sheet_id: int,
        right_sheet_id: int,
        sheet_dataset_map: dict[int, int],
        active_dataset_id: int,
    ) -> tuple[bool, str | None]:
        """Validates that a sheet relationship is strictly intra-dataset for active_dataset_id."""
        left_ds = sheet_dataset_map.get(left_sheet_id)
        right_ds = sheet_dataset_map.get(right_sheet_id)

        if left_ds != active_dataset_id or right_ds != active_dataset_id:
            reason = (
                f"DATASET_ISOLATION_VIOLATION: Relationship {rel_id} spans foreign datasets "
                f"(left_sheet={left_sheet_id} ds={left_ds}, right_sheet={right_sheet_id} ds={right_ds}, active={active_dataset_id})"
            )
            logger.error(reason)
            return False, reason

        if left_ds != right_ds:
            reason = (
                f"DATASET_ISOLATION_VIOLATION: Cross-dataset relationship {rel_id} between "
                f"dataset {left_ds} and {right_ds} is forbidden."
            )
            logger.error(reason)
            return False, reason

        return True, None

    @classmethod
    def validate_relationships(
        cls,
        relationships: list[dict[str, Any]],
        active_dataset_id: int,
        sheet_dataset_map: dict[int, int] | None = None,
    ) -> list[dict[str, Any]]:
        """Filters relationships to retain only those strictly intra-dataset for active_dataset_id."""
        valid = []
        for rel in relationships:
            left_ds = rel.get("left_dataset_id")
            right_ds = rel.get("right_dataset_id")
            if sheet_dataset_map:
                if left_ds is None:
                    left_ds = sheet_dataset_map.get(rel.get("left_sheet_id") or rel.get("left_sheet"))
                if right_ds is None:
                    right_ds = sheet_dataset_map.get(rel.get("right_sheet_id") or rel.get("right_sheet"))

            if left_ds == active_dataset_id and right_ds == active_dataset_id:
                valid.append(rel)
        return valid

    @classmethod
    def validate_evidence_node(
        cls,
        node: Any,
        active_dataset_id: int,
        active_domain: str,
        sheet_dataset_map: dict[int, int] | None = None,
    ) -> tuple[bool, str | None]:
        """Validates that an EvidenceItem belongs to active_dataset_id and active_domain."""
        tokens = getattr(node, "tokens", {}) or {}
        provenance = getattr(node, "provenance", "") or ""

        # 1. Dataset ID Scoping Check
        node_ds = tokens.get("dataset_id")
        if node_ds is not None and node_ds != active_dataset_id:
            reason = (
                f"DATASET_ISOLATION_VIOLATION: Evidence node '{node.evidence_id}' has dataset_id={node_ds}, "
                f"expected active_dataset_id={active_dataset_id}."
            )
            logger.warning(reason)
            return False, reason

        # 2. Source Sheet ID Check
        source_sids = tokens.get("source_sheet_ids", [])
        if sheet_dataset_map and source_sids:
            for sid in source_sids:
                s_ds = sheet_dataset_map.get(sid)
                if s_ds is not None and s_ds != active_dataset_id:
                    reason = (
                        f"DATASET_ISOLATION_VIOLATION: Evidence node '{node.evidence_id}' references "
                        f"foreign sheet {sid} (dataset {s_ds} != {active_dataset_id})."
                    )
                    logger.warning(reason)
                    return False, reason

        # 3. Cross-Domain Semantic Purity Check
        domain_norm = (active_domain or "").lower()
        node_text = " ".join([
            str(getattr(node, "subject", "") or ""),
            str(getattr(node, "metric", "") or ""),
            str(getattr(node, "calculation", "") or ""),
            str(tokens.get("x_measure", "") or ""),
            str(tokens.get("y_measure", "") or ""),
            " ".join(str(c) for c in tokens.get("source_columns", [])),
        ]).lower()

        if domain_norm in ("workforce", "workforce_hr", "hr"):
            for bad_tok in cls.ENVIRONMENTAL_POLLUTANT_TOKENS:
                if re.search(r'\b' + re.escape(bad_tok) + r'\b', node_text):
                    reason = f"FOREIGN_DATASET_EVIDENCE: Pollutant token '{bad_tok}' detected in workforce evidence '{node.evidence_id}'."
                    logger.warning(reason)
                    return False, reason

        elif "environmental" in domain_norm or "air" in domain_norm:
            for bad_tok in cls.WORKFORCE_TOKENS:
                if re.search(r'\b' + re.escape(bad_tok) + r'\b', node_text):
                    reason = f"FOREIGN_DATASET_EVIDENCE: Workforce token '{bad_tok}' detected in environmental evidence '{node.evidence_id}'."
                    logger.warning(reason)
                    return False, reason

        return True, None

    @classmethod
    def filter_evidence_graph(
        cls,
        nodes: list[Any],
        active_dataset_id: int,
        active_domain: str,
        sheet_dataset_map: dict[int, int] | None = None,
    ) -> list[Any]:
        """Filters a collection of evidence nodes to retain strictly isolated, unpolluted nodes."""
        valid_nodes = []
        for n in nodes:
            ok, reason = cls.validate_evidence_node(
                node=n,
                active_dataset_id=active_dataset_id,
                active_domain=active_domain,
                sheet_dataset_map=sheet_dataset_map,
            )
            if ok:
                valid_nodes.append(n)
            else:
                logger.info("DatasetIsolationIntegrity: Suppressed contaminated node '%s': %s", getattr(n, "evidence_id", "?"), reason)
        return valid_nodes

    @classmethod
    def validate_story_purity(
        cls,
        story: Any,
        active_domain: str,
    ) -> tuple[bool, str | None]:
        """Ensures an AnalyticalStory does not emit foreign cross-domain tokens."""
        domain_norm = (active_domain or "").lower()
        if isinstance(story, dict):
            title = str(story.get("title", "") or "")
            question = str(story.get("business_question", "") or "")
            takeaway = str(story.get("takeaway", "") or "")
            narrative = str(story.get("narrative", "") or "")
            s_tokens = story.get("tokens", {}) or {}
            x_m = str(s_tokens.get("x_measure", "") or "")
            y_m = str(s_tokens.get("y_measure", "") or "")
            text_corpus = f"{title} {question} {takeaway} {narrative} {x_m} {y_m}".lower()
            story_title = title or "dict_story"
        else:
            title = (getattr(story, "title", "") or "").lower()
            question = (getattr(story, "business_question", "") or "").lower()
            takeaway = (getattr(story, "takeaway", "") or "").lower()
            s_tokens = getattr(story, "tokens", {}) or {}
            x_m = str(s_tokens.get("x_measure", "") or "").lower()
            y_m = str(s_tokens.get("y_measure", "") or "").lower()
            text_corpus = f"{title} {question} {takeaway} {x_m} {y_m}"
            story_title = getattr(story, "title", "story")

        if domain_norm in ("workforce", "workforce_hr", "hr"):
            for bad_tok in cls.ENVIRONMENTAL_POLLUTANT_TOKENS:
                if re.search(r'\b' + re.escape(bad_tok) + r'\b', text_corpus):
                    return False, f"FOREIGN_DATASET_EVIDENCE: Story '{story_title}' contains pollutant signature '{bad_tok}'."

        elif "environmental" in domain_norm or "air" in domain_norm:
            for bad_tok in cls.WORKFORCE_TOKENS:
                if re.search(r'\b' + re.escape(bad_tok) + r'\b', text_corpus):
                    return False, f"FOREIGN_DATASET_EVIDENCE: Story '{story_title}' contains workforce signature '{bad_tok}'."

        return True, None
