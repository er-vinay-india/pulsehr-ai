from __future__ import annotations

import datetime
import hashlib
import json
import logging
from typing import Any

from ....core import config
from ....db.database import get_connection
from .memory_models import MemoryRecord, MemoryType, EvidenceStatus
from .embedding_service import embedding_service
from .memory_store import memory_store
from .memory_provenance import (
    build_deck_provenance,
    build_slide_provenance,
    build_dataset_provenance,
)

logger = logging.getLogger(__name__)


class PresentationMemoryIndexer:
    """Extracts, chunks, hashes, and indexes presentation decks, datasets, and brand guidelines."""

    def __init__(self, store=None, embedder=None):
        self.store = store or memory_store
        self.embedder = embedder or embedding_service

    @staticmethod
    def _compute_hash(text: str) -> str:
        return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()

    def index_presentation_deck(self, deck_spec: dict[str, Any], force: bool = False) -> int:
        """Indexes a full presentation deck into semantic memories (deck summary + slide chunks + evidence)."""
        deck_id = deck_spec.get("id")
        if not deck_id:
            logger.warning("Cannot index deck without id.")
            return 0

        meta = deck_spec.get("metadata", {})
        title = meta.get("title") or deck_spec.get("title", "Executive Presentation")
        domain = meta.get("domain", "General Analytics")
        audience = meta.get("audience", "C-Suite & Operations Leadership")
        theme_id = meta.get("theme_id") or deck_spec.get("theme", {}).get("id", "executive_dark")
        file_label = meta.get("file_label") or meta.get("source_file", "Workspace Data")
        dataset_id = meta.get("dataset_id")
        sheet_id = meta.get("sheet_id")
        workspace_id = meta.get("workspace_id")
        slides = deck_spec.get("slides", [])
        evidence_ledger = deck_spec.get("evidence_ledger", [])
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        candidate_records: list[dict[str, Any]] = []

        # 1. Deck-Level Summary Chunk
        slide_titles_summary = " · ".join([s.get("title", "") for s in slides[:6] if s.get("title")])
        deck_text = (
            f"Presentation: {title}\n"
            f"Domain: {domain}\n"
            f"Audience: {audience}\n"
            f"Dataset Source: {file_label}\n"
            f"Theme: {theme_id}\n"
            f"Total Slides: {len(slides)}\n"
            f"Slide Trajectory: {slide_titles_summary}\n"
            f"Executive Focus: {meta.get('objective', 'Leadership review and operational analysis')}."
        )

        deck_mem_id = f"mem_deck_{deck_id}"
        deck_hash = self._compute_hash(deck_text)
        candidate_records.append({
            "memory_id": deck_mem_id,
            "memory_type": MemoryType.PRESENTATION_DECK,
            "text": deck_text,
            "source_id": deck_id,
            "source_type": "presentation_deck",
            "deck_id": deck_id,
            "slide_id": None,
            "dataset_id": dataset_id,
            "sheet_id": sheet_id,
            "workspace_id": workspace_id,
            "domain": domain,
            "audience": audience,
            "theme": theme_id,
            "evidence_status": EvidenceStatus.HISTORICAL,
            "content_hash": deck_hash,
            "provenance": build_deck_provenance(deck_spec),
            "metadata": {
                "slide_count": len(slides),
                "snapshot_hash": meta.get("snapshot_hash"),
                "deck_title": title
            },
            "created_at": deck_spec.get("created_at") or now_iso,
            "updated_at": now_iso
        })

        # 2. Slide-Level Semantic Chunks
        for idx, slide in enumerate(slides):
            order = slide.get("order", idx + 1)
            s_id = slide.get("id") or f"{deck_id}_s{order}"
            s_title = slide.get("title", f"Slide {order}")
            s_sub = slide.get("subtitle", "")
            s_narrative = slide.get("narrative", "")
            s_layout = slide.get("layout", "chart_narrative")
            s_cat = slide.get("category", "EXECUTIVE REVIEW")
            s_ev_id = slide.get("evidence_id")

            # Metrics and chart synthesis
            metrics_parts = []
            for m in (slide.get("metrics") or []):
                if isinstance(m, dict):
                    m_label = m.get("label", "")
                    m_val = m.get("value", "")
                    m_sub = m.get("subtext") or m.get("context", "")
                    metrics_parts.append(f"{m_label}: {m_val}" + (f" ({m_sub})" if m_sub else ""))
            metrics_str = " · ".join(metrics_parts) if metrics_parts else "None specified"

            chart_str = "No chart"
            if slide.get("chart"):
                c = slide["chart"]
                c_type = c.get("chart_type") or c.get("type", "chart")
                c_metric = c.get("metric_col") or c.get("title", "")
                chart_str = f"{c_type.title()} chart ({c_metric})"
            elif slide.get("talent_9box_data"):
                chart_str = "McKinsey 9-Box Talent Matrix"
            elif slide.get("burnout_strain_data"):
                chart_str = "Department Strain Diagnostic"

            bullets_str = " ".join([f"• {b}" for b in (slide.get("bullets") or [])[:3]])

            slide_text = (
                f"Presentation: {title} | Slide {order} ({s_cat}): {s_title}\n"
                f"Subtitle: {s_sub}\n"
                f"Narrative: {s_narrative}\n"
                f"Key Findings: {bullets_str}\n"
                f"Empirical Metrics: {metrics_str}\n"
                f"Visual Component: {s_layout} ({chart_str})"
                + (f"\nEvidence Reference: {s_ev_id}" if s_ev_id else "")
            )

            s_mem_id = f"mem_slide_{deck_id}_{order}"
            s_hash = self._compute_hash(slide_text)
            candidate_records.append({
                "memory_id": s_mem_id,
                "memory_type": MemoryType.SLIDE,
                "text": slide_text,
                "source_id": s_id,
                "source_type": "presentation_slide",
                "deck_id": deck_id,
                "slide_id": s_id,
                "dataset_id": dataset_id,
                "sheet_id": sheet_id,
                "workspace_id": workspace_id,
                "domain": domain,
                "audience": audience,
                "theme": theme_id,
                "evidence_status": EvidenceStatus.HISTORICAL,
                "content_hash": s_hash,
                "provenance": build_slide_provenance(deck_spec, slide, order),
                "metadata": {
                    "slide_order": order,
                    "layout": s_layout,
                    "category": s_cat,
                    "evidence_id": s_ev_id,
                    "has_chart": bool(slide.get("chart"))
                },
                "created_at": deck_spec.get("created_at") or now_iso,
                "updated_at": now_iso
            })

        # 3. Evidence Ledger Chunks (Sample top 4 material evidence items)
        for ev in (evidence_ledger or [])[:4]:
            ev_id = ev.get("evidence_id")
            if not ev_id:
                continue
            ev_meth = str(ev.get('calculation_methodology', 'Empirical aggregate.'))[:250]
            ev_estab = str(ev.get('what_it_establishes', ''))[:250]
            ev_not_estab = str(ev.get('what_it_does_not_establish', 'See source records.'))[:250]
            ev_text = (
                f"Evidence Item {ev_id}: {ev.get('metric_name', 'Metric')}\n"
                f"Established Value: {ev.get('metric_value', 'N/A')}\n"
                f"What It Establishes: {ev_estab}\n"
                f"Limitations: {ev_not_estab}\n"
                f"Methodology: {ev_meth}"
            )[:1800]
            ev_mem_id = f"mem_evid_{deck_id}_{ev_id}"
            ev_hash = self._compute_hash(ev_text)
            candidate_records.append({
                "memory_id": ev_mem_id,
                "memory_type": MemoryType.EVIDENCE,
                "text": ev_text,
                "source_id": ev_id,
                "source_type": "evidence_ledger",
                "deck_id": deck_id,
                "slide_id": None,
                "dataset_id": dataset_id,
                "sheet_id": sheet_id,
                "workspace_id": workspace_id,
                "domain": domain,
                "audience": audience,
                "theme": theme_id,
                "evidence_status": EvidenceStatus.HISTORICAL,
                "content_hash": ev_hash,
                "provenance": {
                    **build_deck_provenance(deck_spec),
                    "source_type": "evidence_ledger",
                    "evidence_id": ev_id
                },
                "metadata": {
                    "evidence_id": ev_id,
                    "metric_name": ev.get("metric_name")
                },
                "created_at": deck_spec.get("created_at") or now_iso,
                "updated_at": now_iso
            })

        # Filter out records that are already up to date by content hash
        records_to_embed: list[dict[str, Any]] = []
        final_records: list[MemoryRecord] = []

        for cand in candidate_records:
            if not force:
                existing = self.store.get_by_id(cand["memory_id"])
                if existing and existing.content_hash == cand["content_hash"] and existing.embedding:
                    # Reuse existing record without touching Ollama
                    continue
            records_to_embed.append(cand)

        if not records_to_embed:
            logger.debug(f"Deck '{deck_id}' memories are already up to date with identical content hash.")
            return 0

        # Batch embed all new or changed texts
        texts_to_embed = [r["text"] for r in records_to_embed]
        embeddings = self.embedder.embed_batch(texts_to_embed)

        for cand, emb in zip(records_to_embed, embeddings):
            rec = MemoryRecord(
                memory_id=cand["memory_id"],
                memory_type=cand["memory_type"],
                text=cand["text"],
                embedding=emb,
                source_id=cand["source_id"],
                source_type=cand["source_type"],
                deck_id=cand["deck_id"],
                slide_id=cand["slide_id"],
                dataset_id=cand["dataset_id"],
                sheet_id=cand["sheet_id"],
                workspace_id=cand["workspace_id"],
                domain=cand["domain"],
                audience=cand["audience"],
                theme=cand["theme"],
                evidence_status=cand["evidence_status"],
                content_hash=cand["content_hash"],
                provenance=cand["provenance"],
                metadata=cand["metadata"],
                created_at=cand["created_at"],
                updated_at=cand["updated_at"]
            )
            final_records.append(rec)

        upserted_count = self.store.upsert_batch(final_records)
        logger.info(f"Successfully indexed {upserted_count} memory chunks for deck '{deck_id}'.")
        return upserted_count

    def index_dataset_sheet(self, sheet_id: int, force: bool = False) -> int:
        """Indexes dataset metadata and profile into DATASET_PROFILE memory chunk."""
        with get_connection() as conn:
            sheet_row = conn.execute("""
                SELECT s.id, s.name, s.display_name, s.columns_json, s.profile_json, s.row_count,
                       d.original_name, d.filename, d.id as dataset_id
                FROM sheets s
                JOIN dataset_uploads d ON s.dataset_id = d.id
                WHERE s.id = ?
            """, (sheet_id,)).fetchone()

        if not sheet_row:
            logger.warning(f"Sheet {sheet_id} not found to index.")
            return 0

        cols = json.loads(sheet_row["columns_json"] or "[]")
        prof = json.loads(sheet_row["profile_json"] or "{}")
        row_count = sheet_row["row_count"] or 0
        disp_name = sheet_row["display_name"] or sheet_row["name"]
        orig_name = sheet_row["original_name"] or sheet_row["filename"]

        # Infer domain from columns or profile
        col_names = [c.get("name", "") if isinstance(c, dict) else str(c) for c in cols]
        col_text = " ".join(col_names).lower()
        if any(k in col_text for k in ("sales", "revenue", "price", "profit", "order")):
            domain = "Commercial Sales & Retail"
        elif any(k in col_text for k in ("attendance", "employee", "clock", "leave", "shift", "rating")):
            domain = "Workforce Attendance & HR Operations"
        else:
            domain = "General Operations"

        # Summarize dimensions & key measures
        dim_summary = ", ".join(col_names[:8])
        measures_parts = []
        if isinstance(prof, dict):
            for k, v in list(prof.items())[:5]:
                if isinstance(v, dict) and "mean" in v:
                    measures_parts.append(f"{k} (mean: {v['mean']})")

        measures_str = "; ".join(measures_parts) if measures_parts else "Descriptive indicators"

        dataset_text = (
            f"Dataset: {disp_name} ({orig_name})\n"
            f"Domain: {domain}\n"
            f"Audited Population: {row_count:,} records\n"
            f"Observed Dimensions: {dim_summary}\n"
            f"Baseline Measures: {measures_str}\n"
            f"Context: Verified source sheet in active workspace."
        )

        mem_id = f"mem_sheet_{sheet_id}"
        c_hash = self._compute_hash(dataset_text)

        if not force:
            existing = self.store.get_by_id(mem_id)
            if existing and existing.content_hash == c_hash and existing.embedding:
                return 0

        emb = self.embedder.embed_text(dataset_text)
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        rec = MemoryRecord(
            memory_id=mem_id,
            memory_type=MemoryType.DATASET_PROFILE,
            text=dataset_text,
            embedding=emb,
            source_id=str(sheet_id),
            source_type="dataset_sheet",
            deck_id=None,
            slide_id=None,
            dataset_id=sheet_row["dataset_id"],
            sheet_id=sheet_id,
            workspace_id=None,
            domain=domain,
            audience="Operations Leadership",
            theme=None,
            evidence_status=EvidenceStatus.CONTEXTUAL,
            content_hash=c_hash,
            provenance=build_dataset_provenance(dict(sheet_row)),
            metadata={
                "sheet_name": sheet_row["name"],
                "row_count": row_count,
                "column_count": len(cols)
            },
            created_at=now_iso,
            updated_at=now_iso
        )

        self.store.upsert_record(rec)
        logger.info(f"Indexed dataset profile memory for sheet {sheet_id} ('{disp_name}').")
        return 1

    def delete_presentation_deck(self, deck_id: str) -> int:
        """Removes all semantic memories associated with a deleted presentation deck."""
        count = self.store.delete_by_deck_id(deck_id)
        logger.info(f"Deleted {count} semantic memories for deck '{deck_id}'.")
        return count


# Global singleton
memory_indexer = PresentationMemoryIndexer()
