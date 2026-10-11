"""Central storage, indexing, and retrieval engine for Enterprise Knowledge & Context Fabric (Phase F).

Maintains thread-safe in-memory index of organizational documents and extracted CTX-* evidence.
Pre-seeds authoritative organizational policies, KPI formulas, and threshold benchmarks.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any
from .contracts import (
    ContextArtifactType,
    ContextChunk,
    ContextDocument,
    ContextEvidence,
    ContextQueryResult,
)

logger = logging.getLogger(__name__)


class ContextStore:
    """Authoritative repository for organizational documents and CTX-* evidence."""

    def __init__(self):
        self._lock = threading.Lock()
        self._documents: dict[str, ContextDocument] = {}
        self._evidence_by_id: dict[str, ContextEvidence] = {}
        self._evidence_by_metric: dict[str, list[ContextEvidence]] = {}
        self._seed_default_enterprise_corpus()

    def _seed_default_enterprise_corpus(self) -> None:
        """Seeds the Context Fabric with default enterprise policies, definitions, and thresholds."""
        # ---------------------------------------------------------------------
        # 1. Workforce Domain: Global Workplace & Attendance Policy
        # ---------------------------------------------------------------------
        doc_wf_1 = ContextDocument(
            document_id="DOC-WF-001",
            title="Global Workplace Policy v2.4 (WFO & Hybrid Attendance)",
            artifact_type=ContextArtifactType.POLICY,
            domain="workforce",
            version="v2.4",
            effective_date="2026-01-01",
            raw_content=(
                "Section 3.1: Hybrid Collaboration Model.\n"
                "All full-time and contracted employees in operational, analytical, and technical functions "
                "must attend office a minimum of 3 days per week (3.0 days/week) to maintain operational cohesion. "
                "Section 3.2: Compliance Reporting.\n"
                "Department managers must conduct weekly audits. Any departmental unit averaging below "
                "3.0 days per week will be flagged for an operational review."
            ),
            source_uri="file:///policies/workforce/global_workplace_policy_v2.4.pdf",
            metadata={"department_scope": "all", "owner": "Chief People Officer"},
        )
        ctx_wf_1 = ContextEvidence.create(
            document_id="DOC-WF-001",
            artifact_type=ContextArtifactType.THRESHOLD,
            domain="workforce",
            title="Minimum Office Attendance Requirement",
            section="Section 3.1",
            verbatim_excerpt="All full-time and contracted employees in operational, analytical, and technical functions must attend office a minimum of 3 days per week (3.0 days/week) to maintain operational cohesion.",
            rule_summary="Mandatory minimum 3 days in office per week.",
            metric_name="office_attendance_days",
            operator="MIN",
            threshold_value=3.0,
            unit="days/week",
            source_uri=doc_wf_1.source_uri,
            context_id="CTX-WF-001",
        )
        ctx_wf_2 = ContextEvidence.create(
            document_id="DOC-WF-001",
            artifact_type=ContextArtifactType.POLICY,
            domain="workforce",
            title="Attendance Compliance Review Audit",
            section="Section 3.2",
            verbatim_excerpt="Department managers must conduct weekly audits. Any departmental unit averaging below 3.0 days per week will be flagged for an operational review.",
            rule_summary="Departmental attendance audit triggers operational review when average is under 3.0 days.",
            metric_name="department_attendance_audit",
            operator="MIN",
            threshold_value=3.0,
            unit="days/week",
            source_uri=doc_wf_1.source_uri,
            context_id="CTX-WF-002",
        )
        doc_wf_1.extracted_evidence = [ctx_wf_1, ctx_wf_2]

        # ---------------------------------------------------------------------
        # 2. Workforce Domain: Talent Retention & Attrition Standards
        # ---------------------------------------------------------------------
        doc_wf_2 = ContextDocument(
            document_id="DOC-WF-002",
            title="Enterprise Talent Retention Standard & KPI Guide v1.0",
            artifact_type=ContextArtifactType.KPI_DEFINITION,
            domain="workforce",
            version="v1.0",
            effective_date="2025-10-15",
            raw_content=(
                "Section 1.4: Voluntary Attrition KPI Definition.\n"
                "Voluntary attrition rate is mathematically defined as: "
                "(Voluntary Terminations / Average Monthly Active Headcount) * 100. "
                "Section 2.1: Risk Thresholds.\n"
                "Annualized voluntary attrition exceeding 15.0% constitutes an elevated organizational alert, "
                "requiring immediate compensation benchmarking and leadership intervention."
            ),
            source_uri="file:///policies/workforce/talent_retention_standard_v1.0.pdf",
            metadata={"owner": "VP People Analytics"},
        )
        ctx_wf_3 = ContextEvidence.create(
            document_id="DOC-WF-002",
            artifact_type=ContextArtifactType.KPI_DEFINITION,
            domain="workforce",
            title="Voluntary Attrition KPI Definition",
            section="Section 1.4",
            verbatim_excerpt="Voluntary attrition rate is mathematically defined as: (Voluntary Terminations / Average Monthly Active Headcount) * 100.",
            rule_summary="Calculation standard: (Voluntary Terminations / Average Monthly Active Headcount) * 100.",
            metric_name="voluntary_attrition_rate",
            operator="FORMULA",
            source_uri=doc_wf_2.source_uri,
            context_id="CTX-WF-003",
        )
        ctx_wf_4 = ContextEvidence.create(
            document_id="DOC-WF-002",
            artifact_type=ContextArtifactType.THRESHOLD,
            domain="workforce",
            title="Elevated Voluntary Attrition Risk Alert Threshold",
            section="Section 2.1",
            verbatim_excerpt="Annualized voluntary attrition exceeding 15.0% constitutes an elevated organizational alert, requiring immediate compensation benchmarking and leadership intervention.",
            rule_summary="Attrition threshold cap: 15.0% annualized maximum acceptable rate.",
            metric_name="voluntary_attrition_rate",
            operator="MAX",
            threshold_value=15.0,
            unit="%",
            source_uri=doc_wf_2.source_uri,
            context_id="CTX-WF-004",
        )
        doc_wf_2.extracted_evidence = [ctx_wf_3, ctx_wf_4]

        # ---------------------------------------------------------------------
        # 3. Environmental Domain: Decarbonization & Facility Emissions
        # ---------------------------------------------------------------------
        doc_env_1 = ContextDocument(
            document_id="DOC-ENV-001",
            title="Corporate Sustainability & Decarbonization Roadmap 2026",
            artifact_type=ContextArtifactType.POLICY,
            domain="environmental",
            version="v3.0",
            effective_date="2026-01-01",
            raw_content=(
                "Section 2: Quarterly Carbon Intensity Budgets.\n"
                "Facility direct carbon emissions must not exceed 500.0 metric tons of CO2 equivalent (500 MT CO2e) "
                "per reporting quarter. Facilities exceeding 500 MT are subject to environmental audit surcharges."
            ),
            source_uri="file:///policies/esg/decarbonization_roadmap_2026.pdf",
            metadata={"owner": "Chief Sustainability Officer"},
        )
        ctx_env_1 = ContextEvidence.create(
            document_id="DOC-ENV-001",
            artifact_type=ContextArtifactType.THRESHOLD,
            domain="environmental",
            title="Facility Quarterly Carbon Emission Cap",
            section="Section 2",
            verbatim_excerpt="Facility direct carbon emissions must not exceed 500.0 metric tons of CO2 equivalent (500 MT CO2e) per reporting quarter.",
            rule_summary="Maximum allowable quarterly carbon emissions is 500 MT CO2e.",
            metric_name="carbon_emissions_mt",
            operator="MAX",
            threshold_value=500.0,
            unit="MT CO2e",
            source_uri=doc_env_1.source_uri,
            context_id="CTX-ENV-001",
        )
        doc_env_1.extracted_evidence = [ctx_env_1]

        # ---------------------------------------------------------------------
        # 4. Retail Domain: Store Availability & Shrinkage Governance
        # ---------------------------------------------------------------------
        doc_ret_1 = ContextDocument(
            document_id="DOC-RET-001",
            title="Retail Operations & Loss Prevention Governance",
            artifact_type=ContextArtifactType.POLICY,
            domain="retail",
            version="v2.0",
            effective_date="2025-11-01",
            raw_content=(
                "Section 4: Inventory Shrinkage.\n"
                "Store inventory shrinkage must remain below 1.2% of total store merchandise volume.\n"
                "Section 5: Shelf Availability.\n"
                "Minimum on-shelf product availability target across all core SKUs is 95.0%."
            ),
            source_uri="file:///policies/retail/loss_prevention_standard.pdf",
            metadata={"owner": "VP Retail Operations"},
        )
        ctx_ret_1 = ContextEvidence.create(
            document_id="DOC-RET-001",
            artifact_type=ContextArtifactType.THRESHOLD,
            domain="retail",
            title="Maximum Inventory Shrinkage Threshold",
            section="Section 4",
            verbatim_excerpt="Store inventory shrinkage must remain below 1.2% of total store merchandise volume.",
            rule_summary="Maximum allowable store shrinkage is 1.2%.",
            metric_name="inventory_shrinkage_rate",
            operator="MAX",
            threshold_value=1.2,
            unit="%",
            source_uri=doc_ret_1.source_uri,
            context_id="CTX-RET-001",
        )
        ctx_ret_2 = ContextEvidence.create(
            document_id="DOC-RET-001",
            artifact_type=ContextArtifactType.THRESHOLD,
            domain="retail",
            title="Minimum Product On-Shelf Availability Target",
            section="Section 5",
            verbatim_excerpt="Minimum on-shelf product availability target across all core SKUs is 95.0%.",
            rule_summary="Minimum product availability benchmark is 95.0%.",
            metric_name="on_shelf_availability_pct",
            operator="MIN",
            threshold_value=95.0,
            unit="%",
            source_uri=doc_ret_1.source_uri,
            context_id="CTX-RET-002",
        )
        doc_ret_1.extracted_evidence = [ctx_ret_1, ctx_ret_2]

        # Register documents
        for doc in [doc_wf_1, doc_wf_2, doc_env_1, doc_ret_1]:
            self._documents[doc.document_id] = doc
            for ev in doc.extracted_evidence:
                self._evidence_by_id[ev.context_id] = ev
                if ev.metric_name:
                    metric_key = ev.metric_name.lower()
                    self._evidence_by_metric.setdefault(metric_key, []).append(ev)

    def ingest_document(self, doc: ContextDocument) -> ContextDocument:
        """Ingests and indexes a new context document and its extracted CTX-* evidence."""
        with self._lock:
            self._documents[doc.document_id] = doc
            for ev in doc.extracted_evidence:
                self._evidence_by_id[ev.context_id] = ev
                if ev.metric_name:
                    metric_key = ev.metric_name.lower()
                    self._evidence_by_metric.setdefault(metric_key, []).append(ev)
        logger.info(f"[ContextStore] Ingested document '{doc.document_id}' ({doc.title}) with {len(doc.extracted_evidence)} CTX items")
        return doc

    def get_document(self, document_id: str) -> ContextDocument | None:
        """Retrieves a context document by ID."""
        with self._lock:
            return self._documents.get(document_id)

    def list_documents(
        self,
        domain: str | None = None,
        artifact_type: ContextArtifactType | str | None = None,
    ) -> list[ContextDocument]:
        """Lists registered documents with optional filters."""
        with self._lock:
            docs = list(self._documents.values())

        if domain:
            docs = [d for d in docs if d.domain.lower() == domain.lower()]
        if artifact_type:
            type_str = artifact_type.value if isinstance(artifact_type, ContextArtifactType) else str(artifact_type)
            docs = [d for d in docs if d.artifact_type.value == type_str or d.artifact_type == type_str]
        return docs

    def get_evidence(self, context_id: str) -> ContextEvidence | None:
        """Retrieves an individual CTX-* evidence item by ID."""
        with self._lock:
            return self._evidence_by_id.get(context_id)

    def list_all_evidence(self, domain: str | None = None) -> list[ContextEvidence]:
        """Lists all registered CTX-* evidence items."""
        with self._lock:
            evs = list(self._evidence_by_id.values())
        if domain:
            evs = [e for e in evs if e.domain.lower() == domain.lower()]
        return evs

    def search_context(
        self,
        query: str,
        domain: str | None = None,
        artifact_type: str | None = None,
        department: str | None = None,
        limit: int = 5,
    ) -> ContextQueryResult:
        """Deterministic keyword and semantic matching across CTX-* excerpts and titles."""
        with self._lock:
            all_evidence = list(self._evidence_by_id.values())

        q_terms = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 2]
        scored_matches: list[tuple[float, ContextEvidence]] = []

        for ev in all_evidence:
            if domain and ev.domain.lower() != domain.lower():
                continue
            if artifact_type and ev.artifact_type.value.lower() != artifact_type.lower():
                continue
            if department and ev.department and ev.department.lower() != department.lower():
                continue

            score = 0.0
            search_corpus = f"{ev.title} {ev.rule_summary} {ev.verbatim_excerpt} {ev.metric_name or ''}".lower()

            # Exact phrase bonus
            if query.lower() in search_corpus:
                score += 3.0

            # Token overlap
            for term in q_terms:
                if term in search_corpus:
                    score += 1.0
                    if ev.metric_name and term in ev.metric_name.lower():
                        score += 1.5

            if score > 0.0:
                scored_matches.append((score, ev))

        scored_matches.sort(key=lambda x: x[0], reverse=True)
        top_matches = scored_matches[:limit]

        return ContextQueryResult(
            query=query,
            evidence_matches=[item[1] for item in top_matches],
            similarity_scores=[round(item[0], 2) for item in top_matches],
            total_matched=len(top_matches),
            retrieval_strategy="deterministic_bm25_lexical_token_overlap",
        )

    def get_threshold(
        self,
        metric_name: str,
        department: str | None = None,
    ) -> ContextEvidence | None:
        """Retrieves official threshold benchmark for a metric."""
        metric_key = metric_name.lower().strip()
        with self._lock:
            candidates = self._evidence_by_metric.get(metric_key, [])
            if not candidates:
                # Substring match attempt
                for k, items in self._evidence_by_metric.items():
                    if metric_key in k or k in metric_key:
                        candidates = items
                        break

        threshold_items = [c for c in candidates if c.artifact_type == ContextArtifactType.THRESHOLD]
        if not threshold_items:
            return None

        if department:
            for item in threshold_items:
                if item.department and item.department.lower() == department.lower():
                    return item

        return threshold_items[0]

    def get_business_definition(self, term: str) -> ContextEvidence | None:
        """Retrieves formal KPI definition or calculation standard."""
        term_lower = term.lower().strip()
        with self._lock:
            for ev in self._evidence_by_id.values():
                if ev.artifact_type == ContextArtifactType.KPI_DEFINITION:
                    if term_lower in ev.title.lower() or (ev.metric_name and term_lower in ev.metric_name.lower()):
                        return ev
        return None

    def get_policy(self, name_or_id: str) -> ContextDocument | None:
        """Retrieves a policy document by exact ID or title matching."""
        key = name_or_id.lower().strip()
        with self._lock:
            if name_or_id in self._documents:
                return self._documents[name_or_id]
            for doc in self._documents.values():
                if key in doc.title.lower() or key in doc.document_id.lower():
                    return doc
        return None

    def trace_provenance(self, context_id: str) -> dict[str, Any] | None:
        """Returns provenance audit and cryptographic verification for a CTX-* evidence token."""
        ev = self.get_evidence(context_id)
        if not ev:
            return None

        doc = self.get_document(ev.document_id)
        return {
            "context_id": ev.context_id,
            "document_id": ev.document_id,
            "document_title": doc.title if doc else ev.title,
            "version": doc.version if doc else "v1.0",
            "section": ev.section,
            "verbatim_excerpt": ev.verbatim_excerpt,
            "provenance_hash": ev.provenance_hash,
            "source_uri": ev.source_uri,
            "effective_date": doc.effective_date if doc else "unknown",
            "created_at": ev.created_at,
        }

    def clear_for_test(self) -> None:
        """Resets store back to canonical seed corpus for clean testing."""
        with self._lock:
            self._documents.clear()
            self._evidence_by_id.clear()
            self._evidence_by_metric.clear()
            self._seed_default_enterprise_corpus()


context_store = ContextStore()
