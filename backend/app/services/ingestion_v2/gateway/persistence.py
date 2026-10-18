"""
HighView Ingestion V2 — Phase I8.2 Cutover State Persistence & Restart Recovery
Stage: Governed Consumer Gateway & Safety Guards
Implements durable, transactional SQLite storage for consumer cutover state and
the transition decision ledger. Enforces fail-closed restart semantics and
strict schema version gating. Zero network/external dependencies.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any

from app.core import config
from app.services.ingestion_v2.contracts.cutover import (
    CURRENT_CUTOVER_STATE_SCHEMA_VERSION,
    CircuitBreakerState,
    ConfigurationSource,
    ConsumerCutoverRecord,
    ConsumerName,
    CutoverState,
    CutoverTransitionLedgerEntry,
    FallbackReason,
)

logger = logging.getLogger(__name__)


class CutoverStateCorruptionError(Exception):
    """Raised when persisted cutover state is corrupted or unreadable."""
    pass


class UnknownCutoverSchemaVersionError(Exception):
    """Raised when persisted cutover state schema version is higher than supported."""
    pass


class CutoverPersistenceStore:
    """
    Durable, isolated SQLite storage for consumer cutover state and transition history.
    Guarantees:
    - Never mutates production database (pulsehr.sqlite3).
    - ACID transactions for state updates and transition ledger writes.
    - Fails safe to SHADOW on missing, corrupt, or unknown schema state.
    - Preserves transition history across service/process restarts.
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._lock = threading.RLock()
        if db_path is not None:
            self.db_path = Path(db_path) if db_path != ":memory:" else ":memory:"
        else:
            env_path = os.getenv("HIGHVIEW_CUTOVER_DB_PATH")
            if env_path:
                self.db_path = Path(env_path)
            else:
                data_dir = getattr(config, "DATA_DIR", Path("data"))
                self.db_path = data_dir / "cutover_state.sqlite3"

        if isinstance(self.db_path, Path) and self.db_path != Path(":memory:"):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Creates a managed SQLite connection."""
        if self.db_path == ":memory:":
            if not hasattr(self, "_mem_conn") or self._mem_conn is None:
                self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
                self._mem_conn.row_factory = sqlite3.Row
            return self._mem_conn
        conn = sqlite3.connect(str(self.db_path), timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initializes tables and metadata if they do not exist."""
        self._is_corrupt = False
        with self._lock:
            try:
                conn = self._get_connection()
                try:
                    with conn:
                        conn.execute("""
                            CREATE TABLE IF NOT EXISTS cutover_metadata (
                                key TEXT PRIMARY KEY,
                                value TEXT NOT NULL
                            )
                        """)
                        conn.execute("""
                            CREATE TABLE IF NOT EXISTS consumer_cutover_state (
                                consumer_name TEXT PRIMARY KEY,
                                current_state TEXT NOT NULL,
                                previous_state TEXT,
                                feature_enabled INTEGER NOT NULL DEFAULT 0,
                                fallback_allowed INTEGER NOT NULL DEFAULT 1,
                                circuit_breaker_state TEXT NOT NULL DEFAULT 'CLOSED',
                                certification_run_id TEXT,
                                v2_manifest_fingerprint TEXT,
                                semantic_graph_fingerprint TEXT,
                                dataset_version TEXT,
                                transition_version INTEGER NOT NULL DEFAULT 1,
                                configuration_source TEXT NOT NULL DEFAULT 'CONTROL_PLANE',
                                cutover_state_schema_version INTEGER NOT NULL DEFAULT 1,
                                activated_at TEXT,
                                last_success_at TEXT,
                                last_failure_at TEXT,
                                fallback_count INTEGER NOT NULL DEFAULT 0,
                                last_fallback_reason TEXT,
                                last_transition_timestamp TEXT,
                                metadata_json TEXT
                            )
                        """)
                        conn.execute("""
                            CREATE TABLE IF NOT EXISTS cutover_transition_ledger (
                                transition_id TEXT PRIMARY KEY,
                                consumer TEXT NOT NULL,
                                from_state TEXT NOT NULL,
                                to_state TEXT NOT NULL,
                                reason TEXT NOT NULL,
                                certification_evidence TEXT,
                                commit_hash TEXT NOT NULL,
                                artifact_fingerprints TEXT NOT NULL,
                                authorized_configuration_source TEXT NOT NULL,
                                cutover_state_schema_version INTEGER NOT NULL DEFAULT 1,
                                timestamp TEXT NOT NULL
                            )
                        """)
                        conn.execute("""
                            INSERT OR IGNORE INTO cutover_metadata (key, value)
                            VALUES ('schema_version', ?)
                        """, (str(CURRENT_CUTOVER_STATE_SCHEMA_VERSION),))
                finally:
                    if self.db_path != ":memory:":
                        conn.close()
            except sqlite3.DatabaseError as e:
                logger.error("Corrupted database file encountered during init: %s. Failing safe.", e)
                self._is_corrupt = True

    def get_schema_version(self) -> int:
        """Reads the cutover state schema version."""
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM cutover_metadata WHERE key = 'schema_version'")
                row = cursor.fetchone()
                if row:
                    return int(row[0])
                return CURRENT_CUTOVER_STATE_SCHEMA_VERSION
            except Exception as e:
                logger.warning("Failed to read cutover schema version: %s", e)
                return CURRENT_CUTOVER_STATE_SCHEMA_VERSION
            finally:
                if self.db_path != ":memory:":
                    conn.close()

    def save_consumer_state(self, record: ConsumerCutoverRecord) -> None:
        """Persists or updates a consumer cutover record."""
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO consumer_cutover_state (
                            consumer_name, current_state, previous_state, feature_enabled,
                            fallback_allowed, circuit_breaker_state, certification_run_id,
                            v2_manifest_fingerprint, semantic_graph_fingerprint, dataset_version,
                            transition_version, configuration_source, cutover_state_schema_version,
                            activated_at, last_success_at, last_failure_at, fallback_count,
                            last_fallback_reason, last_transition_timestamp, metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        record.consumer_name.value,
                        record.current_state.value,
                        record.previous_state.value if record.previous_state else None,
                        1 if record.feature_enabled else 0,
                        1 if record.fallback_allowed else 0,
                        record.circuit_breaker_state.value,
                        record.certification_run_id,
                        record.v2_manifest_fingerprint,
                        record.semantic_graph_fingerprint,
                        record.dataset_version,
                        record.transition_version,
                        record.configuration_source.value,
                        record.cutover_state_schema_version,
                        record.activated_at,
                        record.last_success_at,
                        record.last_failure_at,
                        record.fallback_count,
                        record.last_fallback_reason.value if record.last_fallback_reason else None,
                        record.last_transition_timestamp,
                        json.dumps({}),
                    ))
            finally:
                if self.db_path != ":memory:":
                    conn.close()

    def append_transition_entry(self, entry: CutoverTransitionLedgerEntry) -> None:
        """Appends an immutable entry to the durable transition ledger."""
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO cutover_transition_ledger (
                            transition_id, consumer, from_state, to_state, reason,
                            certification_evidence, commit_hash, artifact_fingerprints,
                            authorized_configuration_source, cutover_state_schema_version, timestamp
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        entry.transition_id,
                        entry.consumer.value,
                        entry.from_state.value,
                        entry.to_state.value,
                        entry.reason,
                        entry.certification_evidence,
                        entry.commit,
                        json.dumps(entry.artifact_fingerprints),
                        entry.authorized_configuration_source.value,
                        entry.cutover_state_schema_version,
                        entry.timestamp,
                    ))
            finally:
                if self.db_path != ":memory:":
                    conn.close()

    def load_all_consumer_states(self) -> dict[ConsumerName, ConsumerCutoverRecord]:
        """
        Loads all persisted consumer cutover records.
        Fails safe on corruption, missing state, or unknown future schema versions.
        """
        # Default safe baseline: all consumers in SHADOW
        default_baseline = {
            c: ConsumerCutoverRecord(
                consumer_name=c,
                current_state=CutoverState.SHADOW,
                feature_enabled=False,
                fallback_allowed=True,
                configuration_source=ConfigurationSource.CONTROL_PLANE,
            )
            for c in ConsumerName
        }

        if getattr(self, "_is_corrupt", False):
            return default_baseline

        with self._lock:
            try:
                conn = self._get_connection()
            except Exception as e:
                logger.error("Failed to connect to cutover database, failing safe to SHADOW: %s", e)
                return default_baseline

            try:
                # 1. Inspect schema version
                schema_ver = self.get_schema_version()
                if schema_ver > CURRENT_CUTOVER_STATE_SCHEMA_VERSION:
                    logger.critical(
                        "Unknown future cutover state schema version %d > %d. Gating to safe SHADOW baseline.",
                        schema_ver, CURRENT_CUTOVER_STATE_SCHEMA_VERSION,
                    )
                    return default_baseline

                cursor = conn.cursor()
                cursor.execute("""
                    SELECT
                        consumer_name, current_state, previous_state, feature_enabled,
                        fallback_allowed, circuit_breaker_state, certification_run_id,
                        v2_manifest_fingerprint, semantic_graph_fingerprint, dataset_version,
                        transition_version, configuration_source, cutover_state_schema_version,
                        activated_at, last_success_at, last_failure_at, fallback_count,
                        last_fallback_reason, last_transition_timestamp
                    FROM consumer_cutover_state
                """)
                rows = cursor.fetchall()
                if not rows:
                    return default_baseline

                loaded: dict[ConsumerName, ConsumerCutoverRecord] = dict(default_baseline)

                for row in rows:
                    try:
                        c_name = ConsumerName(row[0])
                        c_state = CutoverState(row[1])
                        prev_state = CutoverState(row[2]) if row[2] else None
                        feat_enabled = bool(row[3])
                        fb_allowed = bool(row[4])
                        cb_state = CircuitBreakerState(row[5]) if row[5] else CircuitBreakerState.CLOSED
                        cert_id = row[6]
                        v2_mfp = row[7]
                        sg_fp = row[8]
                        ds_ver = row[9]
                        tr_ver = int(row[10])
                        cfg_src = ConfigurationSource(row[11]) if row[11] else ConfigurationSource.CONTROL_PLANE
                        rec_schema_ver = int(row[12])
                        act_at = row[13]
                        succ_at = row[14]
                        fail_at = row[15]
                        fb_count = int(row[16])
                        fb_reason = FallbackReason(row[17]) if row[17] else None
                        last_tr = row[18]

                        # Schema version check per record
                        if rec_schema_ver > CURRENT_CUTOVER_STATE_SCHEMA_VERSION:
                            logger.warning(
                                "Record for %s has future schema version %d; resetting to SHADOW",
                                c_name.value, rec_schema_ver
                            )
                            c_state = CutoverState.SHADOW
                            feat_enabled = False

                        loaded[c_name] = ConsumerCutoverRecord(
                            consumer_name=c_name,
                            current_state=c_state,
                            previous_state=prev_state,
                            feature_enabled=feat_enabled,
                            fallback_allowed=fb_allowed,
                            circuit_breaker_state=cb_state,
                            certification_run_id=cert_id,
                            v2_manifest_fingerprint=v2_mfp,
                            semantic_graph_fingerprint=sg_fp,
                            dataset_version=ds_ver,
                            transition_version=tr_ver,
                            configuration_source=cfg_src,
                            cutover_state_schema_version=rec_schema_ver,
                            activated_at=act_at,
                            last_success_at=succ_at,
                            last_failure_at=fail_at,
                            fallback_count=fb_count,
                            last_fallback_reason=fb_reason,
                            last_transition_timestamp=last_tr,
                        )
                    except Exception as parse_err:
                        logger.error("Corrupt consumer state row encountered (%s): %s. Reverting to SHADOW.", row, parse_err)
                        # Fail-closed for that consumer
                        continue

                return loaded
            except Exception as e:
                logger.error("Error reading consumer cutover state (%s). Failing safe to SHADOW.", e)
                return default_baseline
            finally:
                if self.db_path != ":memory:":
                    conn.close()

    def load_transition_history(self) -> list[CutoverTransitionLedgerEntry]:
        """Loads all historical cutover transition ledger entries in chronological order."""
        with self._lock:
            try:
                conn = self._get_connection()
            except Exception as e:
                logger.error("Failed to connect to cutover database for ledger: %s", e)
                return []

            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT
                        transition_id, consumer, from_state, to_state, reason,
                        certification_evidence, commit_hash, artifact_fingerprints,
                        authorized_configuration_source, cutover_state_schema_version, timestamp
                    FROM cutover_transition_ledger
                    ORDER BY rowid ASC
                """)
                entries: list[CutoverTransitionLedgerEntry] = []
                for row in cursor.fetchall():
                    try:
                        fps = json.loads(row[7]) if row[7] else {}
                        entry = CutoverTransitionLedgerEntry(
                            transition_id=row[0],
                            consumer=ConsumerName(row[1]),
                            from_state=CutoverState(row[2]),
                            to_state=CutoverState(row[3]),
                            reason=row[4],
                            certification_evidence=row[5] or "",
                            commit=row[6],
                            artifact_fingerprints=fps,
                            authorized_configuration_source=ConfigurationSource(row[8]),
                            cutover_state_schema_version=int(row[9]),
                            timestamp=row[10],
                        )
                        entries.append(entry)
                    except Exception as err:
                        logger.warning("Corrupt transition ledger row skipped (%s): %s", row, err)
                        continue
                return entries
            except Exception as e:
                logger.error("Error reading transition history (%s). Returning empty ledger.", e)
                return []
            finally:
                if self.db_path != ":memory:":
                    conn.close()
