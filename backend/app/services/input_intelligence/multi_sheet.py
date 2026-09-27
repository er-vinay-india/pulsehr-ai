"""Multi-Sheet Excel Intelligence, Multi-File Understanding, and Join Relationship Discovery.

Provides:
- WorkbookContext generation across multi-sheet workbooks
- Join relationship candidate detection (shared keys, ID patterns, foreign keys)
- Cardinality analysis (ONE_TO_ONE, ONE_TO_MANY, MANY_TO_ONE, MANY_TO_MANY)
- Primary dataset and primary sheet detection based on analytical centrality
- Source role classification (PRIMARY_DATA, SUPPORTING_DATA, REFERENCE_DOCUMENT, etc.)
"""

from __future__ import annotations

import os
from typing import Any
import pandas as pd

from .models import (
    DatasetProfile,
    JoinCardinality,
    RelationshipCandidate,
    SourceItem,
    SourceRole,
    SourceType,
    WorkbookContext,
)


class MultiSheetIntelligence:
    """Discovers relationships, joins, and primary analytical sheets across files and workbooks."""

    @classmethod
    def classify_source_role(
        cls,
        source: SourceItem,
        profiles: list[DatasetProfile] | None = None
    ) -> SourceRole:
        """Classifies the analytical role of an ingested file or document."""
        fname = source.original_name.lower()

        if any(k in fname for k in ("target", "quota", "budget", "benchmark")):
            return SourceRole.SUPPORTING_DATA
        if any(k in fname for k in ("policy", "guideline", "standard", "sop")):
            return SourceRole.POLICY_DOCUMENT
        if any(k in fname for k in ("dictionary", "codebook", "schema", "reference")):
            return SourceRole.REFERENCE_DOCUMENT
        if any(k in fname for k in ("prior", "previous", "historical", "archive", "old_")):
            return SourceRole.HISTORICAL_REPORT
        if any(k in fname for k in ("brand", "theme", "palette", "logo")):
            return SourceRole.BRAND_GUIDELINE
        if any(k in fname for k in ("notes", "readme", "instructions")):
            return SourceRole.USER_NOTES

        if source.source_type == SourceType.PPTX:
            return SourceRole.PREVIOUS_PRESENTATION

        if source.source_type in (SourceType.PDF, SourceType.DOCX) and any(k in fname for k in ("report", "review", "summary", "q1", "q2", "q3", "q4")):
            return SourceRole.HISTORICAL_REPORT

        # Default for tabular data files
        if source.source_type in (SourceType.CSV, SourceType.EXCEL, SourceType.MULTI_SHEET_EXCEL):
            return SourceRole.PRIMARY_DATA

        return SourceRole.UNKNOWN

    @classmethod
    def build_workbook_context(
        cls,
        workbook_name: str,
        source_id: str,
        sheet_profiles: list[DatasetProfile]
    ) -> WorkbookContext:
        """Constructs WorkbookContext with sheet-level roles and relationship candidates."""
        primary_candidates: list[str] = []
        reference_candidates: list[str] = []

        # Triage sheets: transaction/fact tables vs reference/master/summary tables
        for p in sheet_profiles:
            s_name = p.name.lower()
            if any(k in s_name for k in ("summary", "metadata", "readme", "dictionary", "ref", "lookup")):
                reference_candidates.append(p.dataset_id)
            elif p.row_count > 50 or any(k in s_name for k in ("data", "fact", "transactions", "records", "log")):
                primary_candidates.append(p.dataset_id)
            else:
                primary_candidates.append(p.dataset_id)

        # Ensure at least one primary candidate exists (highest row count)
        if not primary_candidates and sheet_profiles:
            top_sheet = max(sheet_profiles, key=lambda s: s.row_count)
            primary_candidates.append(top_sheet.dataset_id)

        # Detect cross-sheet relationships
        relationships = cls.detect_relationships(sheet_profiles)

        return WorkbookContext(
            workbook_name=workbook_name,
            source_id=source_id,
            sheet_profiles=sheet_profiles,
            relationship_candidates=relationships,
            primary_sheet_candidates=primary_candidates,
            reference_sheet_candidates=reference_candidates
        )

    @classmethod
    def detect_relationships(
        cls,
        profiles: list[DatasetProfile]
    ) -> list[RelationshipCandidate]:
        """Detects candidate join keys between datasets/sheets using name matching and key patterns."""
        relationships: list[RelationshipCandidate] = []
        seen_pairs: set[tuple[str, str, str, str]] = set()

        for i, left in enumerate(profiles):
            for j, right in enumerate(profiles):
                if i >= j:
                    continue  # Compare each distinct pair once

                for left_col in left.columns:
                    l_clean = left_col.name.lower().replace(" ", "_").replace("-", "_")

                    for right_col in right.columns:
                        r_clean = right_col.name.lower().replace(" ", "_").replace("-", "_")

                        is_match = False
                        confidence = 0.0
                        rationale = ""

                        # Exact name match on an identifier-like column or shared dimension
                        if l_clean == r_clean:
                            is_match = True
                            if (left_col.is_identifier_candidate or right_col.is_identifier_candidate) or any(k in l_clean for k in ("id", "code", "key", "num", "no", "ref", "tag")):
                                confidence = 0.95 if (left_col.is_identifier_candidate and right_col.is_identifier_candidate) else 0.85
                                rationale = f"Exact column name match '{left_col.name}' with identifier characteristics."
                            else:
                                confidence = 0.80
                                rationale = f"Exact column name match '{left_col.name}' across datasets."

                        # Key suffix match: e.g. CustomerID <-> ID
                        elif (l_clean.endswith(f"_{r_clean}") or r_clean.endswith(f"_{l_clean}")) and ("id" in l_clean or "id" in r_clean):
                            is_match = True
                            confidence = 0.80
                            rationale = f"Primary/foreign key pattern match: '{left_col.name}' ↔ '{right_col.name}'."

                        if is_match:
                            pair_key = (left.dataset_id, left_col.name, right.dataset_id, right_col.name)
                            if pair_key not in seen_pairs:
                                seen_pairs.add(pair_key)

                                # Determine cardinality
                                left_unique = left_col.unique_count == left.row_count and left.row_count >= 1
                                right_unique = right_col.unique_count == right.row_count and right.row_count >= 1

                                if left_unique and right_unique:
                                    cardinality = JoinCardinality.ONE_TO_ONE
                                    is_safe = True
                                elif left_unique and not right_unique:
                                    cardinality = JoinCardinality.ONE_TO_MANY
                                    is_safe = True
                                elif not left_unique and right_unique:
                                    cardinality = JoinCardinality.MANY_TO_ONE
                                    is_safe = True
                                else:
                                    cardinality = JoinCardinality.MANY_TO_MANY
                                    is_safe = False  # Many-to-many is unsafe for automatic merging

                                relationships.append(
                                    RelationshipCandidate(
                                        relationship_id=f"rel_{left.dataset_id}_{right.dataset_id}_{len(relationships)+1}",
                                        left_dataset_id=left.dataset_id,
                                        left_column=left_col.name,
                                        right_dataset_id=right.dataset_id,
                                        right_column=right_col.name,
                                        cardinality=cardinality,
                                        confidence=confidence,
                                        is_safe=is_safe,
                                        evidence=rationale
                                    )
                                )

        return relationships

    @classmethod
    def detect_primary_dataset(
        cls,
        profiles: list[DatasetProfile],
        user_instruction: str = ""
    ) -> tuple[str, float]:
        """Identifies the primary analytical dataset or sheet based on volume, instruction cues, and centrality."""
        if not profiles:
            return "", 0.0
        if len(profiles) == 1:
            return profiles[0].dataset_id, 1.0

        scores: dict[str, float] = {}
        max_rows = max(p.row_count for p in profiles) or 1
        inst_lower = user_instruction.lower()

        for p in profiles:
            score = 0.0

            # 1. Row volume factor (up to 40 pts)
            volume_factor = (p.row_count / max_rows) * 40.0
            score += volume_factor

            # 2. User instruction cue (up to 30 pts)
            if p.name.lower() in inst_lower or p.original_name.lower() in inst_lower:
                score += 30.0

            # 3. Column richness and metrics (up to 20 pts)
            metric_factor = min(20.0, len(p.metric_candidates) * 5.0)
            score += metric_factor

            # 4. Penalty for obvious reference sheets (-25 pts)
            if any(k in p.name.lower() for k in ("summary", "metadata", "dictionary", "ref")):
                score -= 25.0

            scores[p.dataset_id] = max(0.0, score)

        top_id = max(scores, key=scores.get)
        confidence = min(0.98, max(0.60, round(scores[top_id] / 90.0, 2)))
        return top_id, confidence
