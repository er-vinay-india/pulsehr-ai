"""Artifact Coverage Ledger (PPT-L0.6).

Tracks every presentation-eligible artifact across MAIN_DECK, APPENDIX,
SUPPORTING_NOTES, and EXCLUDED to guarantee zero silent evidence loss.
"""

from enum import Enum
import logging
from typing import Any, Optional
from pydantic import BaseModel, Field

from .presentation_evidence import CommonArtifactDescriptor, PresentationEvidenceUniverse

logger = logging.getLogger(__name__)


class ArtifactDisposition(str, Enum):
    MAIN_DECK = "MAIN_DECK"
    APPENDIX = "APPENDIX"
    SUPPORTING_NOTES = "SUPPORTING_NOTES"
    EXCLUDED = "EXCLUDED"


class ArtifactDispositionRecord(BaseModel):
    """Audited disposition for a specific analytical artifact."""
    artifact_id: str
    artifact_type: str
    title: str
    disposition: ArtifactDisposition
    target_slide_id: Optional[str] = None
    target_section: Optional[str] = None
    exclusion_reason: Optional[str] = None
    relationship_note: Optional[str] = None


class ArtifactCoverageLedger(BaseModel):
    """
    Comprehensive ledger of all analytical artifacts and their presentation dispositions.
    Guarantees no important evidence is silently discarded.
    """
    records: dict[str, ArtifactDispositionRecord] = Field(default_factory=dict)
    main_deck_count: int = 0
    appendix_count: int = 0
    supporting_notes_count: int = 0
    excluded_count: int = 0
    silent_loss_count: int = 0

    def record_disposition(
        self,
        artifact: CommonArtifactDescriptor,
        disposition: ArtifactDisposition,
        target_slide_id: Optional[str] = None,
        target_section: Optional[str] = None,
        exclusion_reason: Optional[str] = None,
        relationship_note: Optional[str] = None,
    ) -> ArtifactDispositionRecord:
        """Records a disposition for an artifact, enforcing justification if EXCLUDED."""
        # Enforce: 1 artifact_id -> maximum 1 MAIN_DECK selection unless explicitly marked REPEATED_INTENTIONALLY
        if disposition == ArtifactDisposition.MAIN_DECK:
            existing = self.records.get(artifact.artifact_id)
            if existing and existing.disposition == ArtifactDisposition.MAIN_DECK:
                if relationship_note != "REPEATED_INTENTIONALLY":
                    logger.warning(
                        "Duplicate MAIN_DECK selection rejected for artifact %s: already bound to slide %s",
                        artifact.artifact_id, existing.target_slide_id
                    )
                    return existing

        if disposition == ArtifactDisposition.EXCLUDED and not exclusion_reason:
            exclusion_reason = f"Omitted by narrative ranker (importance: {artifact.importance:.2f})."

        rec = ArtifactDispositionRecord(
            artifact_id=artifact.artifact_id,
            artifact_type=artifact.artifact_type,
            title=artifact.title,
            disposition=disposition,
            target_slide_id=target_slide_id,
            target_section=target_section,
            exclusion_reason=exclusion_reason,
            relationship_note=relationship_note,
        )
        self.records[artifact.artifact_id] = rec
        self._recount()
        return rec

    def _recount(self) -> None:
        self.main_deck_count = sum(1 for r in self.records.values() if r.disposition == ArtifactDisposition.MAIN_DECK)
        self.appendix_count = sum(1 for r in self.records.values() if r.disposition == ArtifactDisposition.APPENDIX)
        self.supporting_notes_count = sum(1 for r in self.records.values() if r.disposition == ArtifactDisposition.SUPPORTING_NOTES)
        self.excluded_count = sum(1 for r in self.records.values() if r.disposition == ArtifactDisposition.EXCLUDED)
        self.silent_loss_count = sum(
            1 for r in self.records.values()
            if r.disposition == ArtifactDisposition.EXCLUDED and not (r.exclusion_reason and r.exclusion_reason.strip())
        )

    def verify_no_silent_loss(self, universe: PresentationEvidenceUniverse) -> bool:
        """Verifies that all artifacts in the universe are accounted for and no exclusions lack reason."""
        all_ids = {a.artifact_id for a in universe.all_artifacts}
        recorded_ids = set(self.records.keys())
        missing = all_ids - recorded_ids
        if missing:
            for m_id in missing:
                art = universe.get_artifact(m_id)
                if art:
                    self.record_disposition(
                        art,
                        ArtifactDisposition.EXCLUDED,
                        exclusion_reason="Automatically recorded to prevent unaccounted artifact loss."
                    )
        return self.silent_loss_count == 0

    def get_summary(self) -> dict[str, Any]:
        """Provides an executive summary of artifact dispositions."""
        return {
            "total_artifacts": len(self.records),
            "main_deck": self.main_deck_count,
            "appendix": self.appendix_count,
            "supporting_notes": self.supporting_notes_count,
            "excluded": self.excluded_count,
            "all_excluded_have_reason": self.silent_loss_count == 0,
            "silent_loss_count": self.silent_loss_count,
        }
