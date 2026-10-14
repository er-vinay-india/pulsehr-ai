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
        from .migration_runner import run_migrations
        run_migrations(conn)

        # Backfill display names for existing datasets if missing
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

        conn.commit()

    finally:
        if close_after:
            conn.close()


@contextmanager
def session_scope(db_path: Path | None = None):
    conn = get_connection(db_path) if db_path is not None else get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
