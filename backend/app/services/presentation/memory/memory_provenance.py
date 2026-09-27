from __future__ import annotations

from typing import Any


def build_deck_provenance(deck_spec: dict[str, Any]) -> dict[str, Any]:
    """Extracts immutable provenance metadata for an entire presentation deck."""
    meta = deck_spec.get("metadata", {})
    return {
        "source_type": "presentation_deck",
        "deck_id": deck_spec.get("id"),
        "deck_title": meta.get("title") or deck_spec.get("title", "Presentation Deck"),
        "dataset_id": meta.get("dataset_id"),
        "sheet_id": meta.get("sheet_id"),
        "source_file": meta.get("file_label") or meta.get("source_file"),
        "snapshot_hash": meta.get("snapshot_hash") or meta.get("data_snapshot_hash"),
        "domain": meta.get("domain"),
        "audience": meta.get("audience"),
        "theme_id": meta.get("theme_id") or deck_spec.get("theme", {}).get("id"),
        "workspace_id": meta.get("workspace_id"),
        "created_at": meta.get("created_at") or deck_spec.get("created_at"),
        "total_slides": len(deck_spec.get("slides", [])),
    }


def build_slide_provenance(deck_spec: dict[str, Any], slide: dict[str, Any], slide_order: int | None = None) -> dict[str, Any]:
    """Extracts immutable provenance metadata for a specific slide within a deck."""
    deck_prov = build_deck_provenance(deck_spec)
    order = slide.get("order") or slide_order or 1
    return {
        **deck_prov,
        "source_type": "presentation_slide",
        "slide_id": slide.get("id", f"slide_{order}"),
        "slide_order": order,
        "slide_title": slide.get("title", ""),
        "layout": slide.get("layout", "chart_narrative"),
        "category": slide.get("category", "EXECUTIVE REVIEW"),
        "evidence_id": slide.get("evidence_id"),
        "evidence_sources": slide.get("evidence_sources", []),
    }


def build_dataset_provenance(sheet_info: dict[str, Any]) -> dict[str, Any]:
    """Extracts provenance metadata for a dataset/sheet profile."""
    return {
        "source_type": "dataset_profile",
        "sheet_id": sheet_info.get("id"),
        "dataset_id": sheet_info.get("dataset_id"),
        "sheet_name": sheet_info.get("name"),
        "display_name": sheet_info.get("display_name"),
        "original_name": sheet_info.get("original_name") or sheet_info.get("filename"),
        "row_count": sheet_info.get("row_count", 0),
        "domain": sheet_info.get("domain"),
    }


def format_provenance_citation(provenance: dict[str, Any]) -> str:
    """Renders a concise, human-readable citation label for a retrieved memory."""
    s_type = provenance.get("source_type", "")
    if s_type == "presentation_slide":
        title = provenance.get("deck_title", "Deck")
        order = provenance.get("slide_order", "?")
        s_title = provenance.get("slide_title", "Slide")
        ev_id = provenance.get("evidence_id")
        ev_part = f" [{ev_id}]" if ev_id else ""
        return f"Historical Deck '{title}' → Slide {order}: {s_title}{ev_part}"
    elif s_type == "presentation_deck":
        title = provenance.get("deck_title", "Deck")
        created = (provenance.get("created_at") or "")[:10]
        return f"Historical Deck '{title}' ({created})"
    elif s_type == "dataset_profile":
        name = provenance.get("display_name") or provenance.get("sheet_name", "Dataset")
        rows = provenance.get("row_count", 0)
        return f"Dataset Profile '{name}' ({rows:,} rows)"
    return f"Source: {provenance.get('deck_id') or provenance.get('source_id') or 'Workspace'}"
