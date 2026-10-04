"""Persistent SQLite Storage for System Analytical Function & Jargon Library.

Stores self-describing analytical functions, token-optimized compact representations,
layman definitions, and business impact rules in an isolated system database.
This database is completely decoupled from dataset/sheet lifecycles and is NEVER
wiped during sheet deletions or data purges.
"""

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any

from ...core import config
from .base import (
    AnalyticalFunctionMetadata,
    FunctionCategory,
    ImpactType,
    ImpactSeverity,
    JargonMapping,
    BusinessImpactRule,
    FunctionPreconditions,
    VisualGrammarRecommendation,
)

logger = logging.getLogger(__name__)

_storage_lock = threading.RLock()


class FunctionLibraryStorage:
    """Manages permanent storage and querying of analytical functions and jargon mappings."""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else config.SYSTEM_FUNCTION_LIBRARY_DB_PATH
        self._ensure_initialized()

    def _get_connection(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_initialized(self) -> None:
        """Initializes system_function_catalog table if not already present."""
        with _storage_lock, self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS system_function_catalog (
                    function_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    version TEXT NOT NULL,
                    mathematical_formula TEXT NOT NULL,
                    compact_token_repr TEXT NOT NULL,
                    token_cost INTEGER NOT NULL,
                    layman_definition TEXT NOT NULL,
                    hr_perspective TEXT NOT NULL,
                    finance_perspective TEXT NOT NULL,
                    pm_perspective TEXT NOT NULL,
                    jargon_map_json TEXT NOT NULL,
                    impact_rule_json TEXT NOT NULL,
                    preconditions_json TEXT NOT NULL,
                    visual_rec_json TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def upsert_function(self, meta: AnalyticalFunctionMetadata) -> None:
        """Persists or updates an analytical function definition."""
        meta.compile_compact_token_repr()

        with _storage_lock, self._get_connection() as conn:
            conn.execute("""
                INSERT INTO system_function_catalog (
                    function_id, name, category, version, mathematical_formula,
                    compact_token_repr, token_cost, layman_definition,
                    hr_perspective, finance_perspective, pm_perspective,
                    jargon_map_json, impact_rule_json, preconditions_json,
                    visual_rec_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(function_id) DO UPDATE SET
                    name=excluded.name,
                    category=excluded.category,
                    version=excluded.version,
                    mathematical_formula=excluded.mathematical_formula,
                    compact_token_repr=excluded.compact_token_repr,
                    token_cost=excluded.token_cost,
                    layman_definition=excluded.layman_definition,
                    hr_perspective=excluded.hr_perspective,
                    finance_perspective=excluded.finance_perspective,
                    pm_perspective=excluded.pm_perspective,
                    jargon_map_json=excluded.jargon_map_json,
                    impact_rule_json=excluded.impact_rule_json,
                    preconditions_json=excluded.preconditions_json,
                    visual_rec_json=excluded.visual_rec_json,
                    updated_at=CURRENT_TIMESTAMP
            """, (
                meta.function_id,
                meta.name,
                meta.category.value if hasattr(meta.category, "value") else str(meta.category),
                meta.version,
                meta.mathematical_formula,
                meta.compact_token_repr,
                meta.token_cost,
                meta.jargon_mapping.layman_definition,
                meta.jargon_mapping.hr_perspective,
                meta.jargon_mapping.finance_perspective,
                meta.jargon_mapping.pm_perspective,
                json.dumps(meta.jargon_mapping.term_translations),
                json.dumps(meta.impact_rule.model_dump()),
                json.dumps(meta.preconditions.model_dump(mode="json")),
                json.dumps(meta.visual_recommendation.model_dump()),
            ))
            conn.commit()

    def get_function(self, function_id: str) -> AnalyticalFunctionMetadata | None:
        """Retrieves a single analytical function metadata by ID."""
        with _storage_lock, self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM system_function_catalog WHERE function_id = ?",
                (function_id,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_metadata(row)

    def get_all_functions(self) -> list[AnalyticalFunctionMetadata]:
        """Retrieves all registered analytical functions."""
        with _storage_lock, self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM system_function_catalog ORDER BY category ASC, function_id ASC"
            ).fetchall()
            return [self._row_to_metadata(r) for r in rows]

    def get_compact_token_block(self) -> str:
        """Returns the pre-compiled, token-optimized DSL block for prompt injection (<400 tokens total)."""
        with _storage_lock, self._get_connection() as conn:
            rows = conn.execute(
                "SELECT compact_token_repr FROM system_function_catalog ORDER BY category ASC, function_id ASC"
            ).fetchall()
            lines = [r["compact_token_repr"] for r in rows if r["compact_token_repr"]]
            if not lines:
                return ""
            return "[ANALYTICAL_FUNCTION_LIBRARY]\n" + "\n".join(lines)

    def total_token_cost(self) -> int:
        """Returns the total token budget consumed by the entire compact function library."""
        with _storage_lock, self._get_connection() as conn:
            row = conn.execute(
                "SELECT SUM(token_cost) as total_tokens FROM system_function_catalog"
            ).fetchone()
            return int(row["total_tokens"] or 0) if row else 0

    def _row_to_metadata(self, row: sqlite3.Row) -> AnalyticalFunctionMetadata:
        impact_data = json.loads(row["impact_rule_json"])
        precond_data = json.loads(row["preconditions_json"])
        visual_data = json.loads(row["visual_rec_json"])
        term_map = json.loads(row["jargon_map_json"])

        jargon = JargonMapping(
            layman_definition=row["layman_definition"],
            hr_perspective=row["hr_perspective"],
            finance_perspective=row["finance_perspective"],
            pm_perspective=row["pm_perspective"],
            term_translations=term_map
        )

        return AnalyticalFunctionMetadata(
            function_id=row["function_id"],
            name=row["name"],
            category=FunctionCategory(row["category"]),
            version=row["version"],
            mathematical_formula=row["mathematical_formula"],
            preconditions=FunctionPreconditions(**precond_data),
            jargon_mapping=jargon,
            impact_rule=BusinessImpactRule(**impact_data),
            visual_recommendation=VisualGrammarRecommendation(**visual_data),
            compact_token_repr=row["compact_token_repr"],
            token_cost=row["token_cost"]
        )
