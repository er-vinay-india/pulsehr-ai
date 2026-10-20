"""
HighView Semantic Data Refinery — Phase SDR-9
Presentation Studio SDR Controlled Adoption Bridge
Binds governed SDR facts and cross-sheet evidence into slide topics and chart data
while strictly preserving PPTX rendering, PDF rendering, Track3 spatial fidelity, and layout engines.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.ingestion_v2.contracts.cutover import Route
from app.services.sdr.shadow.shadow_evaluator import SDRShadowArtifactLoader

logger = logging.getLogger(__name__)


def build_sdr_presentation_evidence(
    dataset_id: str,
    v2_evidence: dict[str, Any],
    manifest_data: dict[str, Any] | None = None,
    loader: SDRShadowArtifactLoader | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Builds SDR-adopted presentation evidence dictionary.
    Supplements slide topic candidates and charts with governed SDR facts
    while keeping the Track3 deck generator and layout engine untouched.
    """
    artifact_loader = loader or SDRShadowArtifactLoader()
    sdr_facts, safety_meta = artifact_loader.load_governed_facts(str(dataset_id))

    adopted = dict(v2_evidence)
    topics = list(adopted.get("topics", []))

    # Add governed SDR facts to topic candidates
    existing_topic_ids = {t.get("topic_id") for t in topics if isinstance(t, dict)}
    for fact in sdr_facts:
        if fact.metric_id not in existing_topic_ids:
            topics.append({
                "topic_id": fact.metric_id,
                "title": fact.metric_id.replace("_", " ").title(),
                "primary_metric_value": fact.value,
                "unit": fact.unit or "",
                "grain": fact.grain or "DATASET",
                "evidence_id": fact.evidence_id,
                "provenance": fact.provenance_type,
            })
            existing_topic_ids.add(fact.metric_id)

    adopted["topics"] = topics

    # Update metadata and route provenance
    meta = dict(adopted.get("metadata", {}))
    if "route_provenance" not in meta or not isinstance(meta["route_provenance"], dict):
        meta["route_provenance"] = {}
    meta["route_provenance"]["selected_route"] = Route.SDR.value
    meta["route_provenance"]["sdr_adoption_state"] = "SDR_ADOPTED"
    adopted["metadata"] = meta

    return adopted
