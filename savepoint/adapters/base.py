import sqlite3
from typing import ClassVar
from urllib.parse import urlparse

from savepoint import config
from savepoint.snapshot.digest import Digest, row_digest
from savepoint.snapshot.files import files_digest


class SandboxViolation(Exception):
    def __init__(self, host: str):
        super().__init__(f"host not in sandbox allowlist: {host}")
        self.host = host


class AppAdapter:
    ALLOWED_HOSTS: ClassVar[set[str]] = {"localhost", "127.0.0.1", "claimdesk", "openmrs", "idempiere"}

    app_id: str = ""
    monitored_tables: ClassVar[dict[str, str]] = {}  # table -> primary key column
    volatile_columns: ClassVar[dict[str, list[str]]] = {}
    risky_patterns: ClassVar[list[str]] = []
    redaction_selectors: ClassVar[list[str]] = []
    files_dir: str | None = None

    def __init__(self, base_url: str):
        host = urlparse(base_url).hostname
        if config.SANDBOX_ONLY and host not in self.ALLOWED_HOSTS:
            raise SandboxViolation(str(host))
        self.base_url = base_url

    def query(self, sql: str, params: dict | None = None) -> list[dict]:
        raise NotImplementedError

    def reset(self, fixture: str) -> Digest:
        raise NotImplementedError

    def digest(self) -> Digest:
        out: Digest = {}
        for table, pk in self.monitored_tables.items():
            volatile = self.volatile_columns.get(table, [])
            rows = self.query(f"SELECT * FROM {table} ORDER BY {pk}")
            out[table] = {str(r[pk]): row_digest(r, volatile) for r in rows}
        if self.files_dir:
            out["_files"] = files_digest(self.files_dir)
        return out


class SqliteMixin:
    db_path: str

    def query(self, sql: str, params: dict | None = None) -> list[dict]:
        con = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in con.execute(sql, params or {})]
        finally:
            con.close()
