"""Checkpoint and restore orchestration (FR11, FR12, INV03)."""
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from time import monotonic, time_ns

from savepoint.snapshot import browser, files, sqlite
from savepoint.snapshot.digest import Digest, diff


@dataclass
class Checkpoint:
    id: str
    run_id: str
    step_idx: int
    kind: str  # initial | risky | retry
    db_path: str
    files_path: str | None
    browser_state_path: str | None
    url: str | None
    digest: Digest
    digest_sha256: str
    bytes: int
    took_ms: int


@dataclass
class RestoreResult:
    restore_ms: int
    rows_differ: int
    exact: bool
    page: object | None = None
    quarantined: bool = False

    @property
    def outcome(self) -> str:
        return "rolled_back" if self.exact else "rollback_failed"


def digest_sha256(d: Digest) -> str:
    return hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()


def take(adapter, run_id: str, step: int, kind: str, root: str, page=None) -> Checkpoint:
    t0 = monotonic()
    cp_dir = Path(root) / run_id / f"cp-{step}"
    db_snap = str(cp_dir / "db.sqlite")
    size = sqlite.backup(adapter.db_path, db_snap)
    files_snap = None
    if adapter.files_dir:
        files_snap = str(cp_dir / "files.tar.gz")
        size += files.tar_dir(adapter.files_dir, files_snap)
    state = url = None
    if page is not None:
        state, url = browser.capture(page, str(cp_dir))
    d = adapter.digest()
    return Checkpoint(f"{run_id}:{step}:{time_ns()}", run_id, step, kind, db_snap, files_snap, state, url, d,
                      digest_sha256(d), size, int((monotonic() - t0) * 1000))


def restore(adapter, cp: Checkpoint, page_factory=None, *, skip_files: bool = False) -> RestoreResult:
    """Restore database, file volume, browser session and URL, then verify by digest compare."""
    t0 = monotonic()
    sqlite.restore(cp.db_path, adapter.db_path)
    if cp.files_path and not skip_files:  # skip_files exists only to prove the compare catches it (V11)
        files.untar_dir(cp.files_path, adapter.files_dir)
    page = None
    if page_factory is not None and cp.browser_state_path:
        page = page_factory(cp.browser_state_path)
        if cp.url:
            page.goto(cp.url)
    d = diff(cp.digest, adapter.digest())
    return RestoreResult(int((monotonic() - t0) * 1000), d.rows_differ, d.exact, page,
                         quarantined=not d.exact)
