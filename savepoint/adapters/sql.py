"""SQL-server adapters (MySQL for OpenMRS, PostgreSQL for iDempiere) over SQLAlchemy.

Snapshots cover the monitored tables only: rows are read with one consistent read and pickled; a restore clears
the monitored tables with foreign-key checks off and re-inserts the rows. Exactness is then proven by the digest
compare, as for SQLite. Scope note: changes to tables outside `monitored_tables` are neither digested nor restored.
"""
import pickle
import re
from pathlib import Path

from sqlalchemy import create_engine, text

from savepoint.adapters.base import AppAdapter

QUERY_TIMEOUT_MS = 2000


class SqlAdapter(AppAdapter):
    dialect = "mysql"  # or "postgresql"
    url: str = ""
    baseline_path: str = "baseline.pkl"

    def __init__(self, base_url: str, url: str, baseline_path: str | None = None):
        super().__init__(base_url)
        self.url = url
        self.engine = create_engine(url, pool_pre_ping=True, pool_size=2, max_overflow=2)
        if baseline_path:
            self.baseline_path = baseline_path

    # -- session setup ---------------------------------------------------------------------------------------
    def _readonly(self, conn):
        if self.dialect == "mysql":
            conn.execute(text("SET SESSION TRANSACTION READ ONLY"))
            conn.execute(text(f"SET SESSION MAX_EXECUTION_TIME={QUERY_TIMEOUT_MS}"))
        else:
            conn.execute(text("SET default_transaction_read_only = on"))
            conn.execute(text(f"SET statement_timeout = {QUERY_TIMEOUT_MS}"))

    def select(self, sql: str, params: dict | None = None, snapshot: str | None = None) -> list[tuple]:
        if snapshot:  # server adapters keep no queryable copy of a checkpoint
            return []
        names = set(re.findall(r":(\w+)", sql))
        with self.engine.connect() as conn:
            self._readonly(conn)
            rows = conn.execute(text(sql), {k: v for k, v in (params or {}).items() if k in names}).fetchall()
            conn.rollback()
            return [tuple(r) for r in rows]

    def query(self, sql: str, params: dict | None = None) -> list[dict]:
        with self.engine.connect() as conn:
            self._readonly(conn)
            rows = [dict(r) for r in conn.execute(text(sql), params or {}).mappings().all()]
            conn.rollback()
            return rows

    # -- snapshot and restore --------------------------------------------------------------------------------
    def _read_all(self) -> dict[str, list[dict]]:
        out = {}
        with self.engine.connect() as conn:
            if self.dialect == "mysql":
                conn.execute(text("SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
                conn.execute(text("START TRANSACTION WITH CONSISTENT SNAPSHOT"))
            for table in self.monitored_tables:
                out[table] = [dict(r) for r in conn.execute(text(f"SELECT * FROM {table}")).mappings().all()]
            conn.rollback()
        return out

    def snapshot_db(self, dest: str) -> int:
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(pickle.dumps(self._read_all(), protocol=pickle.HIGHEST_PROTOCOL))
        return Path(dest).stat().st_size

    def restore_db(self, src: str) -> None:
        data = pickle.loads(Path(src).read_bytes())  # noqa: S301 - our own snapshot file
        with self.engine.begin() as conn:
            if self.dialect == "mysql":
                conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
                conn.execute(text("SET UNIQUE_CHECKS=0"))
            else:
                conn.execute(text("SET session_replication_role = replica"))
            for table in self.monitored_tables:
                conn.execute(text(f"DELETE FROM {table}"))
            for table, rows in data.items():
                if rows:
                    cols = list(rows[0])
                    q = ", ".join(f'"{c}"' if self.dialect != "mysql" else f"`{c}`" for c in cols)
                    ph = ", ".join(f":{c}" for c in cols)
                    conn.execute(text(f"INSERT INTO {table} ({q}) VALUES ({ph})"), rows)
            if self.dialect == "mysql":
                conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
            else:
                conn.execute(text("SET session_replication_role = DEFAULT"))

    # -- fixtures --------------------------------------------------------------------------------------------
    def make_baseline(self) -> int:
        """Freeze the current (seeded) state as fixture `seed_a`."""
        return self.snapshot_db(self.baseline_path)

    def reset(self, fixture: str = "seed_a"):
        if fixture != "seed_a":
            raise ValueError(f"unknown fixture: {fixture}")
        if not Path(self.baseline_path).exists():
            raise FileNotFoundError(f"no baseline at {self.baseline_path}; seed the app and call make_baseline()")
        self.restore_db(self.baseline_path)
        return self.digest()
