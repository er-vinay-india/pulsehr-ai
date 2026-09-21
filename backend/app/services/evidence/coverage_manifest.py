"""Transparent evidence coverage manifest generator."""

from typing import Any


def generate_coverage_manifest(
    all_candidate_findings: list[dict[str, Any]],
    main_deck_slides: list[dict[str, Any]],
    appendix_slides: list[dict[str, Any]],
    excluded_reasons: dict[str, str] | None = None
) -> dict[str, Any]:
    """Builds an explicit, defensible coverage manifest showing which candidate findings appear
    in the main deck, which appear in the appendix, and which were excluded with reasons."""
    reasons = excluded_reasons or {}
    items: list[dict[str, Any]] = []

    # Map finding IDs from slides
    main_finding_map = {}
    for s in main_deck_slides:
        fid = s.get("finding_id") or s.get("evidence_id")
        if fid:
            main_finding_map[fid] = s

    appendix_finding_map = {}
    for s in appendix_slides:
        fid = s.get("finding_id") or s.get("evidence_id")
        if fid:
            appendix_finding_map[fid] = s

    main_count = 0
    appendix_count = 0
    excluded_count = 0

    for cand in all_candidate_findings:
        fid = cand["finding_id"]
        evid = cand.get("evidence_id")

        if fid in main_finding_map or (evid and evid in main_finding_map):
            slide = main_finding_map.get(fid) or main_finding_map.get(evid)
            items.append({
                "finding_id": fid,
                "evidence_id": evid,
                "title": cand["title"],
                "category": cand["category"],
                "importance": cand["importance"],
                "disposition": "main_deck",
                "slide_index": slide.get("order"),
                "slide_title": slide.get("title"),
                "reason": "Prioritized in primary analytical narrative flow."
            })
            main_count += 1
        elif fid in appendix_finding_map or (evid and evid in appendix_finding_map):
            slide = appendix_finding_map.get(fid) or appendix_finding_map.get(evid)
            items.append({
                "finding_id": fid,
                "evidence_id": evid,
                "title": cand["title"],
                "category": cand["category"],
                "importance": cand["importance"],
                "disposition": "appendix",
                "slide_index": slide.get("order"),
                "slide_title": slide.get("title"),
                "reason": "Routed to appendix to preserve main deck legibility and focus."
            })
            appendix_count += 1
        else:
            default_reason = reasons.get(
                fid,
                "Subsumed into aggregate executive metrics or reserved for deep-dive investigation."
            )
            items.append({
                "finding_id": fid,
                "evidence_id": evid,
                "title": cand["title"],
                "category": cand["category"],
                "importance": cand["importance"],
                "disposition": "excluded",
                "slide_index": None,
                "slide_title": None,
                "reason": default_reason
            })
            excluded_count += 1

    return {
        "total_candidate_findings": len(all_candidate_findings),
        "main_deck_count": main_count,
        "appendix_count": appendix_count,
        "excluded_count": excluded_count,
        "coverage_pct": round(((main_count + appendix_count) / max(1, len(all_candidate_findings))) * 100, 1),
        "items": items
    }
