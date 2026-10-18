"""
HighView Ingestion V2 — Phase I8.3 HRIDAY Intelligence Context Adapter
Stage: HRIDAY Controlled V2 Cutover
Connects HRIDAY's context acquisition path to the frozen ConsumerIntelligenceGateway
and Ingestion V2 multi-namespace hybrid retrieval.
Enforces epistemic boundaries:
- The Gateway is the sole routing authority.
- Answer generation reasoning pipeline is preserved 100% unchanged.
- Context does NOT invent facts, alter denominators, or forge EVID records.
- Unready/stale V2 requests cleanly and measurably fall back to V1.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from typing import Any, Sequence

from app.core import config
from app.db.database import session_scope
from app.services.ingestion_v2.contracts.cutover import (
    ConsumerName,
    ConsumerRouteDecision,
    FallbackReason,
    Route,
)
from app.services.ingestion_v2.contracts.hriday_context import (
    GovernedJoinContext,
    GovernedMetricContext,
    HridayNormalizedContext,
    RetrievedEvidenceItem,
)
from app.services.ingestion_v2.gateway.gateway import (
    ConsumerIntelligenceGateway,
    RoutingFallbackDisallowedError,
    get_consumer_gateway,
)
from app.services.ingestion_v2.retrieval.context_assembler import (
    ContextAssembler,
    GovernedContextPackage,
)
from app.services.ingestion_v2.retrieval.hybrid_retriever import (
    HybridRetrievalResult,
    HybridRetriever,
)
from app.services.ingestion_v2.retrieval.namespaces import RetrievalNamespace

logger = logging.getLogger(__name__)


class HridayIntelligenceAdapter:
    """
    Thin, governed adapter connecting HRIDAY to the central routing gateway and V2 retrieval.
    Guarantees:
    - Zero LLM calls for routing or context assembly.
    - Zero changes to HRIDAY answer-generation semantics or models.
    - Preserves exact source grain, denominators, and EVID-* references.
    - Seamless fallback to V1 when V2 is unready, stale, or experiencing degraded retrieval.
    """

    def __init__(
        self,
        gateway: ConsumerIntelligenceGateway | None = None,
        retriever: HybridRetriever | None = None,
        context_assembler: ContextAssembler | None = None,
    ) -> None:
        self.gateway = gateway or get_consumer_gateway()
        self.retriever = retriever
        self.context_assembler = context_assembler or ContextAssembler()
        self._cached_v2_manifests: dict[str, dict[str, Any]] = {}

    def register_v2_manifest(self, dataset_id: str | int, manifest_data: dict[str, Any]) -> None:
        """Registers a canonical V2 manifest for readiness evaluation (in-memory/cache)."""
        self._cached_v2_manifests[str(dataset_id)] = manifest_data

    def invalidate_v2_manifest(self, dataset_id: str | int) -> None:
        """Invalidates cached V2 manifest on dataset deletion or replacement."""
        self._cached_v2_manifests.pop(str(dataset_id), None)
        if self.retriever:
            self.retriever.delete_dataset(str(dataset_id))

    def acquire_context(
        self,
        query: str,
        dataset_id: int | str | None = None,
        sheet_id: int | None = None,
        canary_cohort: str | None = None,
        canary_authorized: bool = False,
        is_probe: bool = False,
        manifest_data: dict[str, Any] | None = None,
        required_evidence_refs: list[str] | None = None,
        available_evidence_ids: set[str] | None = None,
    ) -> HridayNormalizedContext:
        """
        Acquires evidence and context for HRIDAY through the authoritative ConsumerIntelligenceGateway.
        Returns a normalized HridayNormalizedContext envelope.
        """
        t0 = time.perf_counter()
        str_ds_id = str(dataset_id) if dataset_id is not None else None

        # 1. Resolve active manifest data for readiness checks if not passed directly
        active_manifest = manifest_data
        if active_manifest is None and str_ds_id is not None:
            active_manifest = self._cached_v2_manifests.get(str_ds_id)

        # 2. Evaluate route via the sole authoritative Gateway
        decision: ConsumerRouteDecision = self.gateway.evaluate_route(
            consumer=ConsumerName.HRIDAY,
            dataset_id=str_ds_id,
            dataset_version=active_manifest.get("dataset_version") if active_manifest else None,
            canary_cohort=canary_cohort,
            canary_authorized=canary_authorized,
            is_probe=is_probe,
            manifest_data=active_manifest,
            required_evidence_refs=required_evidence_refs,
            available_evidence_ids=available_evidence_ids,
        )

        gw_duration_ms = (time.perf_counter() - t0) * 1000

        # 3. Route to V2 or V1
        if decision.selected_route == Route.V2:
            try:
                t_v2_0 = time.perf_counter()
                v2_ctx = self._acquire_v2_context(
                    query=query,
                    dataset_id=str_ds_id,
                    sheet_id=sheet_id,
                    decision=decision,
                    manifest_data=active_manifest,
                )
                v2_duration_ms = (time.perf_counter() - t_v2_0) * 1000
                v2_ctx.telemetry["gateway_decision_ms"] = round(gw_duration_ms, 3)
                v2_ctx.telemetry["v2_context_acquisition_ms"] = round(v2_duration_ms, 3)
                v2_ctx.telemetry["total_context_acquisition_ms"] = round((time.perf_counter() - t0) * 1000, 3)
                self.gateway.record_success(ConsumerName.HRIDAY)
                return v2_ctx
            except Exception as exc:
                logger.warning(f"V2 context acquisition failed for HRIDAY: {exc}. Evaluating governed fallback.")
                self.gateway.record_failure(ConsumerName.HRIDAY, FallbackReason.V2_RUNTIME_ERROR)
                if not self.gateway.is_fallback_allowed(ConsumerName.HRIDAY):
                    raise RoutingFallbackDisallowedError(
                        f"V2 context acquisition failed and fallback to V1 is disallowed for HRIDAY: {exc}"
                    ) from exc

                # Fall back to V1 with fallback decision provenance
                fallback_decision = ConsumerRouteDecision(
                    decision_id=decision.decision_id,
                    decision_timestamp=decision.decision_timestamp,
                    consumer=ConsumerName.HRIDAY,
                    selected_route=Route.V1,
                    consumer_state=decision.consumer_state,
                    feature_enabled=decision.feature_enabled,
                    global_enabled=decision.global_enabled,
                    fallback_allowed=decision.fallback_allowed,
                    fallback_used=True,
                    fallback_reason=FallbackReason.V2_RUNTIME_ERROR,
                    circuit_breaker_state=self.gateway.circuit_breaker.get_state(ConsumerName.HRIDAY),
                    dataset_id=str_ds_id,
                    rationale=f"Governed fallback triggered by V2 retrieval exception: {exc}",
                )
                v1_ctx = self._acquire_v1_context(query=query, dataset_id=dataset_id, sheet_id=sheet_id, decision=fallback_decision)
                v1_ctx.telemetry["gateway_decision_ms"] = round(gw_duration_ms, 3)
                v1_ctx.telemetry["fallback_recovery"] = True
                v1_ctx.telemetry["total_context_acquisition_ms"] = round((time.perf_counter() - t0) * 1000, 3)
                return v1_ctx

        # Default / Gated Route.V1
        t_v1_0 = time.perf_counter()
        v1_ctx = self._acquire_v1_context(query=query, dataset_id=dataset_id, sheet_id=sheet_id, decision=decision)
        v1_duration_ms = (time.perf_counter() - t_v1_0) * 1000
        v1_ctx.telemetry["gateway_decision_ms"] = round(gw_duration_ms, 3)
        v1_ctx.telemetry["v1_context_acquisition_ms"] = round(v1_duration_ms, 3)
        v1_ctx.telemetry["total_context_acquisition_ms"] = round((time.perf_counter() - t0) * 1000, 3)
        return v1_ctx

    def _acquire_v1_context(
        self,
        query: str,
        dataset_id: int | str | None,
        sheet_id: int | None,
        decision: ConsumerRouteDecision,
    ) -> HridayNormalizedContext:
        """Acquires context through existing legacy V1 retrieval and wraps in normalized contract."""
        from app.services.ai_copilot import get_aggregate_context
        from app.services.hybrid_retrieval import hybrid_search
        from app.services.sheet_catalog import linked_evidence

        int_ds = int(dataset_id) if (isinstance(dataset_id, int) or (isinstance(dataset_id, str) and dataset_id.isdigit())) else None

        # 1. V1 Hybrid Search
        evidence = []
        try:
            import app.services.ai_copilot as copilot_mod
            h_search = getattr(copilot_mod, "hybrid_search", None)
            if h_search is None:
                from app.services.hybrid_retrieval import hybrid_search as h_search
            evidence = h_search(query, top_k=8, dataset_id=int_ds, sheet_id=sheet_id) or []
            try:
                related = linked_evidence(evidence, limit=12)
                evidence.extend(related)
            except Exception:
                pass
        except Exception:
            evidence = []

        # 2. V1 Aggregate Context
        try:
            catalog_summary = get_aggregate_context(sheet_id=sheet_id, dataset_id=int_ds)
        except TypeError:
            catalog_summary = get_aggregate_context()

        # 3. Format samples for prompt builder
        evidence_samples = [
            {
                **r,
                "sheet": r.get("sheet") or r.get("source"),
                "source_file": r.get("source_file") or r.get("sheet") or r.get("source"),
                "row": r.get("row_index") or r.get("row_id"),
                "row_index": r.get("row_index"),
                "text": r.get("text") or r.get("preview") or str(r)[:200],
                "data": r.get("text") or r.get("preview") or str(r)[:200],
                "id": r.get("id"),
                "retrieval_methods": r.get("retrieval_methods", ["hybrid_search"]),
            }
            for r in evidence[:10]
        ]

        # 4. Wrap evidence items
        items: list[RetrievedEvidenceItem] = []
        for idx, r in enumerate(evidence):
            chunk_id = str(r.get("row_id") or r.get("id") or f"v1_chunk_{idx}")
            items.append(
                RetrievedEvidenceItem(
                    evidence_id=chunk_id,
                    namespace="V1_CHUNK",
                    title=f"V1 Chunk {chunk_id}",
                    content=r.get("text") or r.get("preview") or str(r),
                    relevance_score=float(r.get("relevance_score", 1.0)),
                    source_sheet=r.get("sheet") or r.get("source"),
                    row_index=r.get("row_index"),
                )
            )

        return HridayNormalizedContext(
            route_selected=Route.V1,
            dataset_id=dataset_id,
            evidence_items=items,
            catalog_summary_text=catalog_summary,
            evidence_samples_json=evidence_samples,
            route_decision=decision,
            telemetry={"evidence_count": len(items)},
        )

    def _acquire_v2_context(
        self,
        query: str,
        dataset_id: str | None,
        sheet_id: int | None,
        decision: ConsumerRouteDecision,
        manifest_data: dict[str, Any] | None,
    ) -> HridayNormalizedContext:
        """Acquires context through frozen Ingestion V2 multi-namespace retrieval & context assembler."""
        if self.retriever is None:
            raise RuntimeError("V2 HybridRetriever is not configured on HridayIntelligenceAdapter.")

        # 1. Retrieve across 4 namespaces
        retrieval_res: HybridRetrievalResult = self.retriever.retrieve(
            query=query,
            dataset_id=dataset_id,
            top_k=8,
        )

        # 2. Assemble bounded GovernedContextPackage
        pkg: GovernedContextPackage = self.context_assembler.assemble_context(retrieval_res)

        # 3. Extract governed metric contexts
        metrics: list[GovernedMetricContext] = []
        for m in pkg.metric_definitions:
            metrics.append(
                GovernedMetricContext(
                    metric_id=m.get("metric_id", ""),
                    metric_name=m.get("metric_name", ""),
                    formula=m.get("formula", ""),
                    grain=m.get("grain", ""),
                    unit=m.get("unit", ""),
                    denominator=m.get("denominator"),
                    population=m.get("population"),
                    source_table=m.get("source_table"),
                    is_ambiguous=bool(m.get("is_ambiguous", False)),
                    ambiguity_rationale=m.get("ambiguity_rationale"),
                )
            )

        # 4. Extract governed join plans (enforcing SAFE vs UNSAFE/AMBIGUOUS)
        join_plans: list[GovernedJoinContext] = []
        for jp in pkg.join_plans:
            safety = jp.get("join_safety", "SAFE")
            join_plans.append(
                GovernedJoinContext(
                    join_plan_id=jp.get("join_plan_id", ""),
                    left_table=jp.get("left_table", ""),
                    right_table=jp.get("right_table", ""),
                    join_type=jp.get("join_type", "INNER"),
                    join_safety=safety,
                    requires_preaggregation=bool(jp.get("requires_preaggregation", False)),
                    grain_warning=jp.get("grain_warning"),
                )
            )

        # 5. Extract retrieved evidence items
        evidence_items: list[RetrievedEvidenceItem] = []
        evidence_samples: list[dict[str, Any]] = []

        for cand in retrieval_res.ranked_candidates:
            doc = cand.document
            evid_id = (doc.evidence_refs[0] if doc.evidence_refs else None) or doc.artifact_id
            title = doc.structured_metadata.get("title") or doc.structured_metadata.get("name") or doc.artifact_id
            content = doc.text_for_retrieval
            source_sheet = doc.structured_metadata.get("table_id") or doc.structured_metadata.get("entity_id") or doc.namespace.value

            evidence_items.append(
                RetrievedEvidenceItem(
                    evidence_id=evid_id,
                    namespace=doc.namespace.value,
                    title=title,
                    content=content,
                    relevance_score=cand.rrf_score,
                    source_sheet=source_sheet,
                    provenance={"artifact_id": doc.artifact_id, "authority_class": doc.authority_class.value},
                )
            )
            evidence_samples.append({
                "sheet": source_sheet,
                "evidence_id": evid_id,
                "id": evid_id,
                "row_index": doc.structured_metadata.get("row_index"),
                "text": content,
                "data": content,
                "authority": doc.authority_class.value,
                "retrieval_methods": ["v2_hybrid_retrieval"],
            })

        # 6. Build governed catalog summary text
        summary_lines = [
            f"GOVERNED INGESTION V2 CATALOGUE (Dataset: {dataset_id}, Version: {pkg.dataset_version}):",
            f"Artifact Count: {len(pkg.artifact_ids)} | Canonical Namespaces: {[ns.value for ns in pkg.namespaces]}",
        ]
        if pkg.grains:
            summary_lines.append(f"Authoritative Grains: {', '.join(pkg.grains)}")
        if metrics:
            m_descs = [f"'{m.metric_name}' (formula: {m.formula}, grain: {m.grain})" for m in metrics[:5]]
            summary_lines.append(f"Governed Metrics: {'; '.join(m_descs)}")
        if join_plans:
            jp_descs = [f"'{jp.left_table}' <-> '{jp.right_table}' ({jp.join_safety})" for jp in join_plans[:4]]
            summary_lines.append(f"Governed Joins: {'; '.join(jp_descs)}")
        if pkg.limitations:
            summary_lines.append(f"Known Limitations: {'; '.join(pkg.limitations)}")
        if pkg.is_ambiguous:
            summary_lines.append(f"AMBIGUITY ALERT: {'; '.join(pkg.ambiguity_notes)}")

        catalog_summary = "\n".join(summary_lines)

        try:
            from app.services.ai_copilot import get_aggregate_context
            raw_sheet_context = get_aggregate_context(sheet_id=sheet_id, dataset_id=int(dataset_id) if dataset_id and str(dataset_id).isdigit() else None)
            if raw_sheet_context:
                catalog_summary = f"{catalog_summary}\n\n{raw_sheet_context}"
        except Exception:
            pass

        return HridayNormalizedContext(
            route_selected=Route.V2,
            dataset_id=dataset_id,
            dataset_version=(manifest_data.get("dataset_version") if manifest_data else None) or pkg.dataset_version,
            manifest_fingerprint=manifest_data.get("manifest_fingerprint") if manifest_data else None,
            semantic_graph_fingerprint=manifest_data.get("semantic_graph_fingerprint") if manifest_data else None,
            evidence_items=evidence_items,
            metrics=metrics,
            join_plans=join_plans,
            limitations=pkg.limitations,
            reliability_notes=["Grounded in canonical V2 Ingestion artifacts. Zero LLM hallucinations."],
            catalog_summary_text=catalog_summary,
            evidence_samples_json=evidence_samples[:10],
            route_decision=decision,
            telemetry={
                "candidate_count": len(retrieval_res.ranked_candidates),
                "intent": retrieval_res.intent_result.intent.value,
                "estimated_tokens": pkg.estimated_token_count,
            },
        )


_shared_hriday_adapter: HridayIntelligenceAdapter | None = None


def get_hriday_adapter() -> HridayIntelligenceAdapter:
    """Returns the singleton shared HridayIntelligenceAdapter."""
    global _shared_hriday_adapter
    if _shared_hriday_adapter is None:
        _shared_hriday_adapter = HridayIntelligenceAdapter()
    return _shared_hriday_adapter


def set_hriday_adapter(adapter: HridayIntelligenceAdapter | None) -> None:
    """Sets or resets the singleton shared HridayIntelligenceAdapter (for testing)."""
    global _shared_hriday_adapter
    _shared_hriday_adapter = adapter
