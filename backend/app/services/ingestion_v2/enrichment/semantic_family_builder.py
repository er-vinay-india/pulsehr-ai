"""
HighView Ingestion V2 — Semantic Family Builder
Stage 9: Controlled Enrichment
Groups semantically related validated metrics, dimensions, and concepts into domain-neutral families.

Invariants:
1. Pure organizational metadata. NEVER alters formulas, results, grains, or provenance.
2. Domain-neutral typed architecture: supports Workforce, Retail, Environmental, Finance, SaaS, Supply Chain.
3. AnalysisIntent influence is strictly confined to family priority ordering/emphasis metadata;
   it NEVER alters membership, formulas, grains, or graph truth.
4. Does not invent missing members. Only validated metrics and columns may be included.
"""

import hashlib
import json
import re
from typing import Sequence
from pydantic import BaseModel, ConfigDict, Field

from app.services.ingestion_v2.contracts.enrichment import (
    LocalDerivedMetric,
    RelationalDerivedMetric,
    SemanticFamily,
)
from app.services.ingestion_v2.contracts.intent import AnalysisIntent


class SemanticFamilySpec(BaseModel):
    """Specification for defining a governed semantic family."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    family_id: str
    family_name: str
    concept_type: str
    metric_ids: list[str] = Field(default_factory=list)
    dimension_ids: list[str] = Field(default_factory=list)
    entity_types: list[str] = Field(default_factory=list)
    grain_scope: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    provenance_refs: list[str] = Field(default_factory=list)
    description: str | None = None


class SemanticFamilyBuilder:
    """
    Governed builder for semantic families.
    Organizes validated metrics and dimensions into cohesive domain-neutral families.
    """

    def __init__(self) -> None:
        self._families: dict[str, SemanticFamily] = {}

    @property
    def families(self) -> list[SemanticFamily]:
        return list(self._families.values())

    def create_family(
        self,
        spec: SemanticFamilySpec,
        *,
        intent: AnalysisIntent | None = None,
    ) -> SemanticFamily:
        """
        Creates a governed SemanticFamily from a spec.
        AnalysisIntent may only influence metadata priority, never members or semantics.
        """
        # Deterministic sorting of references
        sorted_metrics = sorted(list(set(spec.metric_ids)))
        sorted_dims = sorted(list(set(spec.dimension_ids)))
        sorted_entities = sorted(list(set(spec.entity_types)))
        sorted_evid = sorted(list(set(spec.evidence_refs)))
        sorted_prov = sorted(list(set(spec.provenance_refs)))

        family = SemanticFamily(
            family_id=spec.family_id,
            family_name=spec.family_name,
            concept_type=spec.concept_type.strip().upper(),
            metric_ids=sorted_metrics,
            dimension_ids=sorted_dims,
            entity_types=sorted_entities,
            grain_scope=spec.grain_scope,
            evidence_refs=sorted_evid,
            provenance_refs=sorted_prov,
            description=spec.description,
        )

        self._families[family.family_id] = family
        return family

    def auto_group_metrics(
        self,
        metrics: Sequence[LocalDerivedMetric | RelationalDerivedMetric],
        *,
        dimensions: Sequence[str] | None = None,
        entity_types: Sequence[str] | None = None,
        intent: AnalysisIntent | None = None,
    ) -> list[SemanticFamily]:
        """
        Groups metrics into domain-neutral families based on their semantic concept
        or shared entity/grain characteristics. Does not invent missing members.
        """
        # Group metrics by concept or normalized keyword
        concept_groups: dict[str, list[LocalDerivedMetric | RelationalDerivedMetric]] = {}
        for m in metrics:
            # Determine concept keyword from name
            name_lower = m.metric_name.lower()
            if any(k in name_lower for k in ["attend", "absent", "present", "leave"]):
                c = "ATTENDANCE"
            elif any(k in name_lower for k in ["revenue", "sales", "margin", "profit"]):
                c = "REVENUE_FINANCIAL"
            elif any(k in name_lower for k in ["emission", "carbon", "energy", "waste"]):
                c = "ENVIRONMENTAL_SUSTAINABILITY"
            elif any(k in name_lower for k in ["ticket", "incident", "resolution", "defect", "closure"]):
                c = "OPERATIONAL_EFFICIENCY"
            elif any(k in name_lower for k in ["headcount", "employee", "tenure", "turnover", "attrition"]):
                c = "WORKFORCE_DYNAMICS"
            elif any(k in name_lower for k in ["license", "churn", "mrr", "arr", "user"]):
                c = "SAAS_GROWTH"
            elif any(k in name_lower for k in ["shipment", "inventory", "delivery", "order", "lead_time"]):
                c = "SUPPLY_CHAIN_FULFILLMENT"
            else:
                c = "GENERAL_PERFORMANCE"

            concept_groups.setdefault(c, []).append(m)

        result_families: list[SemanticFamily] = []
        for concept, group in sorted(concept_groups.items(), key=lambda x: x[0]):
            m_ids = sorted([m.metric_id for m in group])
            all_evid: set[str] = set()
            all_prov: set[str] = set()
            grains: set[str] = set()
            for m in group:
                for ev in m.evidence_refs:
                    all_evid.add(ev)
                for pr in m.provenance_refs:
                    all_prov.add(pr)
                target_g = m.target_grain if hasattr(m, "target_grain") and m.target_grain else getattr(m, "grain", None)
                if target_g:
                    grains.add(target_g)

            family_id = f"family-{concept.lower()}"
            name_title = " ".join(w.capitalize() for w in concept.replace("_", " ").split())
            grain_scope = " / ".join(sorted(list(grains))) if grains else None

            fam = SemanticFamily(
                family_id=family_id,
                family_name=f"{name_title} Family",
                concept_type=concept,
                metric_ids=m_ids,
                dimension_ids=sorted(list(set(dimensions or []))),
                entity_types=sorted(list(set(entity_types or []))),
                grain_scope=grain_scope,
                evidence_refs=sorted(list(all_evid)),
                provenance_refs=sorted(list(all_prov)),
                description=f"Governed semantic grouping of validated metrics and dimensions for {name_title}",
            )
            self._families[fam.family_id] = fam
            result_families.append(fam)

        return result_families
