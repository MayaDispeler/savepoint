"""SQL-server adapters (MySQL for OpenMRS, PostgreSQL for iDempiere) over SQLAlchemy.

Snapshots cover the monitored tables only: rows are read with one consistent read and pickled; a restore clears
the monitored tables with foreign-key checks off and re-inserts the rows. Exactness is then proven by the digest
compare, as for SQLite. Scope note: changes to tables outside `monitored_tables` are neither digested nor restored.
"""
import pickle
import re
from pathlib import Path
from typing import ClassVar

from sqlalchemy import create_engine, text

from savepoint.adapters.base import AppAdapter
from savepoint.snapshot.digest import Digest, row_digest

QUERY_TIMEOUT_MS = 2000


class SqlAdapter(AppAdapter):
    dialect = "mysql"  # or "postgresql"
    url: str = ""
    baseline_path: str = "baseline.pkl"
    connect_args: ClassVar[dict] = {}
    row_filters: ClassVar[dict[str, str]] = {}  # table -> WHERE clause limiting the rows we snapshot and restore

    def __init__(self, base_url: str, url: str, baseline_path: str | None = None):
        super().__init__(base_url)
        self.url = url
        self.engine = create_engine(url, pool_pre_ping=True, pool_size=2, max_overflow=2, connect_args=self.connect_args)
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

    def _writable(self, conn):
        if self.dialect == "mysql":
            conn.execute(text("SET SESSION TRANSACTION READ WRITE"))
            conn.execute(text("SET SESSION MAX_EXECUTION_TIME=0"))
        else:
            conn.execute(text("SET default_transaction_read_only = off"))
            conn.execute(text("SET statement_timeout = 0"))

    def select(self, sql: str, params: dict | None = None, snapshot: str | None = None) -> list[tuple]:
        if snapshot:  # server adapters keep no queryable copy of a checkpoint
            return []
        names = set(re.findall(r":(\w+)", sql))
        with self.engine.connect() as conn:
            self._readonly(conn)
            try:
                rows = conn.execute(text(sql), {k: v for k, v in (params or {}).items() if k in names}).fetchall()
                return [tuple(r) for r in rows]
            finally:
                conn.rollback()
                self._writable(conn)
                conn.commit()

    def query(self, sql: str, params: dict | None = None) -> list[dict]:
        with self.engine.connect() as conn:
            self._readonly(conn)
            try:
                return [dict(r) for r in conn.execute(text(sql), params or {}).mappings().all()]
            finally:
                conn.rollback()
                self._writable(conn)
                conn.commit()

    # -- table access ----------------------------------------------------------------------------------------
    def _pg_columns(self, conn, table: str) -> list[tuple[str, str]]:
        cache = self.__dict__.setdefault("_col_cache", {})
        if table not in cache:
            rows = conn.execute(text(
                "SELECT a.attname, format_type(a.atttypid, a.atttypmod) FROM pg_attribute a "
                "WHERE a.attrelid = CAST(:t AS regclass) AND a.attnum > 0 AND NOT a.attisdropped ORDER BY a.attnum"),
                {"t": table}).fetchall()
            cache[table] = [(r[0], r[1]) for r in rows]
        return cache[table]

    def _table_rows(self, conn, table: str, order_by: str | None = None) -> list[dict]:
        """All rows of a table. PostgreSQL columns are read as text so out-of-range dates (iDempiere has some
        BC timestamps) never fail in the driver; restore casts them back."""
        order = f" ORDER BY {order_by}" if order_by else ""
        where = f" WHERE {self.row_filters[table]}" if table in self.row_filters else ""
        if self.dialect == "mysql":
            return [dict(r) for r in conn.execute(text(f"SELECT * FROM {table}{where}{order}")).mappings().all()]
        cols = ", ".join(f'"{c}"::text AS "{c}"' for c, _ in self._pg_columns(conn, table))
        return [dict(r) for r in conn.execute(text(f"SELECT {cols} FROM {table}{where}{order}")).mappings().all()]

    def pk_sql(self, table: str) -> str:
        cols = [c.strip() for c in self.monitored_tables[table].split(",")]
        if len(cols) == 1:
            return cols[0]
        if self.dialect == "mysql":
            return "CONCAT_WS('|', " + ", ".join(cols) + ")"
        return " || '|' || ".join(f"CAST({c} AS text)" for c in cols)

    def digest(self) -> Digest:
        out: Digest = {}
        with self.engine.connect() as conn:
            for table, pk in self.monitored_tables.items():
                volatile = self.volatile_columns.get(table, [])
                cols = [c.strip() for c in pk.split(",")]
                rows = self._table_rows(conn, table, pk)
                out[table] = {"|".join(str(r[c]) for c in cols): row_digest(r, volatile) for r in rows}
            conn.rollback()
        return out

    # -- snapshot and restore --------------------------------------------------------------------------------
    def _read_all(self) -> dict[str, list[dict]]:
        out = {}
        with self.engine.connect() as conn:
            if self.dialect == "mysql":
                conn.execute(text("SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
                conn.execute(text("START TRANSACTION WITH CONSISTENT SNAPSHOT"))
            for table in self.monitored_tables:
                out[table] = self._table_rows(conn, table)
            conn.rollback()
        return out

    def snapshot_db(self, dest: str) -> int:
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(pickle.dumps(self._read_all(), protocol=pickle.HIGHEST_PROTOCOL))
        return Path(dest).stat().st_size

    def restore_db(self, src: str) -> None:
        data = pickle.loads(Path(src).read_bytes())
        with self.engine.begin() as conn:
            if self.dialect == "mysql":
                conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
                conn.execute(text("SET UNIQUE_CHECKS=0"))
            else:
                conn.execute(text("SET session_replication_role = replica"))
            for table in self.monitored_tables:
                where = f" WHERE {self.row_filters[table]}" if table in self.row_filters else ""
                conn.execute(text(f"DELETE FROM {table}{where}"))
            for table, rows in data.items():
                if rows:
                    cols = list(rows[0])
                    if self.dialect == "mysql":
                        q = ", ".join(f"`{c}`" for c in cols)
                        ph = ", ".join(f":{c}" for c in cols)
                    else:
                        types = dict(self._pg_columns(conn, table))
                        q = ", ".join(f'"{c}"' for c in cols)
                        ph = ", ".join(f"CAST(:{c} AS {types[c]})" for c in cols)
                    conn.execute(text(f"INSERT INTO {table} ({q}) VALUES ({ph})"), rows)
            if self.dialect == "mysql":
                for table, pk in self.monitored_tables.items():
                    nxt = conn.execute(text(f"SELECT COALESCE(MAX({pk}), 0) + 1 FROM {table}")).scalar()
                    conn.execute(text(f"ALTER TABLE {table} AUTO_INCREMENT = {int(nxt)}"))
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
