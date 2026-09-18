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
