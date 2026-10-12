"""Online SQLite snapshot and in-place restore using the backup API (no app stop needed)."""
import sqlite3
from pathlib import Path


def backup(db_path: str, dest: str) -> int:
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    Path(dest).unlink(missing_ok=True)
    src = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    dst = sqlite3.connect(dest)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return Path(dest).stat().st_size


def restore(snapshot: str, db_path: str) -> None:
    """Overwrite the live database with the snapshot. Idempotent."""
    src = sqlite3.connect(f"file:{snapshot}?mode=ro", uri=True)
    dst = sqlite3.connect(db_path, timeout=10)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
