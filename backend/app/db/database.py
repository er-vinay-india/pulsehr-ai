import sqlite3
from contextlib import contextmanager
from pathlib import Path
import sqlite_vec

from ..core import config


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    target_path = db_path or config.DB_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target_path, timeout=60.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 60000")
    conn.execute("PRAGMA synchronous = NORMAL")

    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)

    return conn


def init_db(conn: sqlite3.Connection | None = None) -> None:
    close_after = False
    if conn is None:
        conn = get_connection()
        close_after = True

    try:
        conn.executescript(config.SCHEMA_PATH.read_text())

        # Ensure display_name and analysis_context_json columns exist in dataset_uploads and sheets
        du_cols = [r[1] for r in conn.execute("PRAGMA table_info(dataset_uploads)").fetchall()]
        if "display_name" not in du_cols:
            conn.execute("ALTER TABLE dataset_uploads ADD COLUMN display_name TEXT")
        if "analysis_context_json" not in du_cols:
            conn.execute("ALTER TABLE dataset_uploads ADD COLUMN analysis_context_json TEXT")

        s_cols = [r[1] for r in conn.execute("PRAGMA table_info(sheets)").fetchall()]
        if "display_name" not in s_cols:
            conn.execute("ALTER TABLE sheets ADD COLUMN display_name TEXT")
        if "analysis_context_json" not in s_cols:
            conn.execute("ALTER TABLE sheets ADD COLUMN analysis_context_json TEXT")

        # Backfill display names for existing datasets
        try:
            import json
            from ..services.sheet_naming_pipeline import generate_sheet_display_name

            unnamed = conn.execute(
                "SELECT id, filename, original_name, columns_json, sample_preview_json FROM dataset_uploads WHERE display_name IS NULL OR display_name = ''"
            ).fetchall()
            for row in unnamed:
                cols = json.loads(row["columns_json"] or "[]")
                sample = json.loads(row["sample_preview_json"] or "[]")
                naming = generate_sheet_display_name(row["original_name"] or row["filename"], cols, sample)
                disp = naming["display_name"]
                conn.execute("UPDATE dataset_uploads SET display_name = ? WHERE id = ?", (disp, row["id"]))
                conn.execute("UPDATE sheets SET display_name = ? WHERE dataset_id = ? AND (display_name IS NULL OR display_name = '')", (disp, row["id"]))
        except Exception:
            pass

        # Initialize vector virtual table if not exists
        has_vec = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tabular_vectors'"
        ).fetchone()
        if not has_vec:
            conn.execute(
                f"""
                CREATE VIRTUAL TABLE tabular_vectors USING vec0(
                    id INTEGER PRIMARY KEY,
                    embedding FLOAT[{config.EMBEDDING_DIM}] distance_metric=cosine
                )
                """
            )

        # EDA & Curated / Derived Data Tables
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sheet_curated_rows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sheet_id INTEGER NOT NULL REFERENCES sheets(id) ON DELETE CASCADE,
                row_index INTEGER NOT NULL,
                data_json TEXT NOT NULL,
                anomalies_json TEXT DEFAULT '[]',
                UNIQUE(sheet_id, row_index)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS derived_tables (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                display_name TEXT NOT NULL,
                description TEXT,
                source_sheets_json TEXT NOT NULL,
                join_keys_json TEXT NOT NULL,
                columns_json TEXT NOT NULL,
                row_count INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS derived_table_rows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                derived_table_id INTEGER NOT NULL REFERENCES derived_tables(id) ON DELETE CASCADE,
                row_index INTEGER NOT NULL,
                data_json TEXT NOT NULL,
                UNIQUE(derived_table_id, row_index)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS eda_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sheet_id INTEGER REFERENCES sheets(id) ON DELETE CASCADE,
                dataset_id INTEGER REFERENCES dataset_uploads(id) ON DELETE CASCADE,
                health_score INTEGER NOT NULL,
                report_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        eda_cols = [r[1] for r in conn.execute("PRAGMA table_info(eda_reports)").fetchall()]
        if "snapshot" not in eda_cols:
            try:
                conn.execute("ALTER TABLE eda_reports ADD COLUMN snapshot TEXT")
            except Exception:
                pass
        conn.commit()

    finally:
        if close_after:
            conn.close()


@contextmanager
def session_scope(db_path: Path | None = None):
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
