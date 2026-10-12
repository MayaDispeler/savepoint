import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "claimdesk"))
import seed


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = tmp_path / "cd.db"
    seed.build(str(db))
    monkeypatch.setenv("CLAIMDESK_DB", str(db))
    monkeypatch.delenv("QUIRKS", raising=False)
    import app as cd
    c = cd.create_app().test_client()
    c.post("/login", data={"user": "adjuster"})
    c.db = str(db)
    return c


def rows(db, sql):
    return sqlite3.connect(db).execute(sql).fetchall()


def test_planted_values(client):
    assert rows(client.db, "SELECT COUNT(*) FROM claims")[0][0] == 300
    assert rows(client.db, "SELECT amount FROM claims WHERE id='CL-10427'")[0][0] == 980.0
    assert rows(client.db, "SELECT COUNT(*) FROM claim_notes WHERE claim_id='CL-10427'")[0][0] == 0
    assert rows(client.db, "SELECT amount FROM claims WHERE id='CL-10428'")[0][0] == 455.5
    assert rows(client.db, "SELECT adjuster_id FROM claims WHERE id='CL-10431'")[0][0] == "ADJ-07"
    assert rows(client.db, "SELECT COUNT(*) FROM claim_notes WHERE body LIKE 'SYSTEM NOTICE%'")[0][0] == 1
    assert rows(client.db, "SELECT COUNT(*) FROM claims WHERE amount < 0")[0][0] == 0


def test_seed_deterministic(tmp_path):
    a, b = tmp_path / "a.db", tmp_path / "b.db"
    seed.build(str(a))
    seed.build(str(b))
    for sql in ("SELECT * FROM claims ORDER BY id", "SELECT * FROM claim_notes ORDER BY id"):
        assert rows(str(a), sql) == rows(str(b), sql)


def test_two_page_grid(client):
    assert b"Page 1 of 2" in client.get("/claims").data
    assert b"CL-10699" in client.get("/claims?page=2").data


def test_silent_validation(client):
    r = client.post("/claims/CL-10427/notes", data={"body": ""}, follow_redirects=True)
    assert b"Saved." in r.data
    assert rows(client.db, "SELECT COUNT(*) FROM claim_notes WHERE claim_id='CL-10427'")[0][0] == 0


def test_note_and_save_write(client):
    client.post("/claims/CL-10427/notes", data={"body": "called payee"})
    assert rows(client.db, "SELECT COUNT(*) FROM claim_notes WHERE claim_id='CL-10427'")[0][0] == 1
    client.post("/claims/CL-10427/save",
                data={"amount": "1250.00", "status": "review", "adjuster_id": "ADJ-02"})
    assert rows(client.db, "SELECT amount, status FROM claims WHERE id='CL-10427'")[0] == (1250.0, "review")


def test_session_timeout(client, monkeypatch):
    monkeypatch.setenv("SESSION_TIMEOUT_S", "-1")
    assert client.get("/claims").status_code == 302


def test_modal_and_tab_trap_rendered(client):
    html = client.get("/claims/CL-10427").data
    assert b'role="dialog"' in html and b'tabindex="1"' in html and b"3000" in html


def test_quirks_off(client, monkeypatch):
    monkeypatch.setenv("QUIRKS", "")
    html = client.get("/claims/CL-10427").data
    assert b'tabindex="1"' not in html
    r = client.post("/claims/CL-10427/notes", data={"body": ""}, follow_redirects=True)
    assert b"cannot be empty" in r.data
