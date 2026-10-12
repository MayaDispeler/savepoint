import sqlite3
from pathlib import Path

import pytest

from savepoint.adapters.claimdesk import ClaimDeskAdapter
from savepoint.snapshot import checkpoint


@pytest.fixture
def adapter(tmp_path):
    files = tmp_path / "attachments"
    files.mkdir()
    (files / "a.txt").write_text("original")
    a = ClaimDeskAdapter("http://127.0.0.1:5001", str(tmp_path / "cd.db"), str(files))
    a.reset("seed_a")
    return a


def mutate(adapter):
    con = sqlite3.connect(adapter.db_path)
    con.execute("UPDATE claims SET amount=1250.00 WHERE id='CL-10427'")
    con.execute("DELETE FROM claim_notes WHERE claim_id='CL-10431'")
    con.execute("INSERT INTO claim_notes (claim_id, body, created_at) VALUES ('CL-10428','x','t')")
    con.commit()
    con.close()
    (Path(adapter.files_dir) / "a.txt").write_text("changed")
    (Path(adapter.files_dir) / "new.txt").write_text("new")


def test_restore_exact(adapter, tmp_path):
    cp = checkpoint.take(adapter, "run1", 0, "initial", str(tmp_path / "art"))
    mutate(adapter)
    assert adapter.digest() != cp.digest
    r = checkpoint.restore(adapter, cp)
    assert r.exact and r.rows_differ == 0 and r.outcome == "rolled_back"
    assert (Path(adapter.files_dir) / "a.txt").read_text() == "original"
    assert not (Path(adapter.files_dir) / "new.txt").exists()


def test_restore_is_idempotent_and_repeatable(adapter, tmp_path):
    cp = checkpoint.take(adapter, "run1", 0, "initial", str(tmp_path / "art"))
    for _ in range(20):
        mutate(adapter)
        assert checkpoint.restore(adapter, cp).exact
    assert checkpoint.restore(adapter, cp).exact


def test_missing_files_step_is_caught(adapter, tmp_path):  # V11 broken restore
    cp = checkpoint.take(adapter, "run1", 0, "initial", str(tmp_path / "art"))
    mutate(adapter)
    r = checkpoint.restore(adapter, cp, skip_files=True)
    assert not r.exact and r.rows_differ == 2 and r.quarantined and r.outcome == "rollback_failed"


def test_volatile_updated_at_does_not_fail_restore(adapter, tmp_path):
    cp = checkpoint.take(adapter, "run1", 0, "initial", str(tmp_path / "art"))
    con = sqlite3.connect(adapter.db_path)
    con.execute("UPDATE claims SET updated_at='later' WHERE id='CL-10427'")
    con.commit()
    con.close()
    assert checkpoint.restore(adapter, cp).exact


def test_browser_session_and_url_restored(adapter, tmp_path, live):
    b = live().browser  # shares the session Chromium; a second sync_playwright() cannot start in one thread
    ctx = b.new_context()
    ctx.add_cookies([{"name": "sid", "value": "abc", "url": "http://127.0.0.1:5001/"}])
    page = ctx.new_page()
    page.route("**/*", lambda route: route.fulfill(body="<p>ok</p>", content_type="text/html"))
    page.goto("http://127.0.0.1:5001/claims/CL-10427")
    cp = checkpoint.take(adapter, "run2", 3, "risky", str(tmp_path / "art"), page)
    ctx.close()

    def factory(state):
        c = b.new_context(storage_state=state)
        pg = c.new_page()
        pg.route("**/*", lambda route: route.fulfill(body="<p>ok</p>", content_type="text/html"))
        return pg

    r = checkpoint.restore(adapter, cp, factory)
    assert r.exact and r.page.url.endswith("/claims/CL-10427")
    assert {c["name"]: c["value"] for c in r.page.context.cookies()} == {"sid": "abc"}
