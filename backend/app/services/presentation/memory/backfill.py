"""Presentation Memory Backfill Utility.

Scans existing SQLite presentation decks and dataset profiles, skips unchanged items via
content-hash check, and indexes them into the local presentation memory store.

Run via:
    python -m app.services.presentation.memory.backfill [--force] [--limit N]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from ....db.database import get_connection
from .memory_indexer import memory_indexer
from .memory_store import memory_store

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_backfill(limit: int | None = None, force: bool = False) -> dict[str, int]:
    """Indexes historical presentation decks and sheets into presentation memory."""
    stats = {
        "total_decks_scanned": 0,
        "decks_indexed": 0,
        "decks_skipped": 0,
        "deck_chunks_created": 0,
        "total_sheets_scanned": 0,
        "sheets_indexed": 0,
        "sheets_skipped": 0,
        "failures": 0,
    }

    # 1. Backfill Presentation Decks
    with get_connection() as conn:
        query = "SELECT id, title, spec_json, created_at FROM presentation_decks ORDER BY created_at DESC"
        if limit:
            query += f" LIMIT {int(limit)}"
        deck_rows = conn.execute(query).fetchall()

    stats["total_decks_scanned"] = len(deck_rows)
    logger.info(f"Starting memory backfill for {len(deck_rows)} historical presentation decks...")

    for row in deck_rows:
        deck_id = row["id"]
        try:
            raw_spec = row["spec_json"]
            if not raw_spec:
                stats["decks_skipped"] += 1
                continue
            deck_spec = json.loads(raw_spec)
            chunks = memory_indexer.index_presentation_deck(deck_spec, force=force)
            if chunks > 0:
                stats["decks_indexed"] += 1
                stats["deck_chunks_created"] += chunks
            else:
                stats["decks_skipped"] += 1
        except Exception as exc:
            logger.warning(f"Failed to backfill deck '{deck_id}': {exc}")
            stats["failures"] += 1

    # 2. Backfill Dataset Sheet Profiles
    with get_connection() as conn:
        sheet_rows = conn.execute("SELECT id, name FROM sheets ORDER BY id ASC").fetchall()

    stats["total_sheets_scanned"] = len(sheet_rows)
    logger.info(f"Starting memory backfill for {len(sheet_rows)} dataset sheets...")

    for s_row in sheet_rows:
        s_id = s_row["id"]
        try:
            chunks = memory_indexer.index_dataset_sheet(s_id, force=force)
            if chunks > 0:
                stats["sheets_indexed"] += 1
            else:
                stats["sheets_skipped"] += 1
        except Exception as exc:
            logger.warning(f"Failed to backfill sheet {s_id}: {exc}")
            stats["failures"] += 1

    total_memories = memory_store.count()
    logger.info(f"Backfill complete! Total active presentation memories: {total_memories}.")
    logger.info(f"Summary: {stats}")
    return stats


def main():
    parser = argparse.ArgumentParser(description="Backfill presentation memory from existing SQLite tables.")
    parser.add_argument("--force", action="store_true", help="Force re-embedding even if content hash matches.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of decks to index.")
    args = parser.parse_args()

    run_backfill(limit=args.limit, force=args.force)


if __name__ == "__main__":
    main()
