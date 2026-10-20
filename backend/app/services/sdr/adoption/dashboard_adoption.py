"""
HighView Semantic Data Refinery — Phase SDR-9
Executive Dashboard SDR Controlled Adoption Bridge
Binds governed SDR facts and cross-sheet metrics into dashboard KPIs and candidate pools
while strictly preserving card structures, charts, themes, layouts, and ranking logic.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.adaptive_dashboard.dataset_orchestrator import (
    DatasetIntelligenceResponse,
)
from app.services.ingestion_v2.contracts.cutover import Route
from app.services.sdr.shadow.shadow_evaluator import SDRShadowArtifactLoader

logger = logging.getLogger(__name__)


def build_sdr_dashboard_response(
    dataset_id: str,
    v2_response: DatasetIntelligenceResponse,
    manifest_data: dict[str, Any] | None = None,
    loader: SDRShadowArtifactLoader | None = None,
    **kwargs: Any,
) -> DatasetIntelligenceResponse:
    """
    Builds an SDR-adopted DatasetIntelligenceResponse.
    Replaces/enriches executive KPIs with governed SDR facts (including cross-sheet metrics).
    Leaves visual presentation, card counts, and layout constraints 100% intact.
    """
    artifact_loader = loader or SDRShadowArtifactLoader()
    sdr_facts, safety_meta = artifact_loader.load_governed_facts(str(dataset_id))

    if not sdr_facts:
        return v2_response

    # Convert SDR facts to executive KPIs format
    new_kpis: list[dict[str, Any]] = []
    seen = set()

    for fact in sdr_facts:
        if fact.metric_id not in seen:
            new_kpis.append({
                "kpi_id": fact.metric_id,
                "title": fact.metric_id.replace("_", " ").title(),
                "value": fact.value,
                "formatted_value": fact.formatted_value,
                "unit": fact.unit or "",
                "grain": fact.grain or "DATASET",
                "evidence_id": fact.evidence_id,
                "provenance": fact.provenance_type,
            })
            seen.add(fact.metric_id)

    # Copy integrity and update route provenance
    integrity = dict(v2_response.executive_integrity or {})
    if "route_provenance" not in integrity:
        integrity["route_provenance"] = {}
    if isinstance(integrity["route_provenance"], dict):
        integrity["route_provenance"]["selected_route"] = Route.SDR.value
        integrity["route_provenance"]["sdr_adoption_state"] = "SDR_ADOPTED"

    return v2_response.model_copy(
        update={
            "executive_kpis": new_kpis[:6],  # Respect existing glanceability card cap (max 6)
            "executive_integrity": integrity,
            "relationship_count": v2_response.relationship_count + safety_meta.get("valid_relationships_count", 0),
            "cross_sheet_evidence_count": v2_response.cross_sheet_evidence_count + safety_meta.get("relational_facts_count", 0),
        }
    )
