import sqlite3

import pytest

from savepoint import config
from savepoint.adapters.base import SandboxViolation
from savepoint.adapters.claimdesk import ClaimDeskAdapter
from savepoint.snapshot.digest import diff


@pytest.fixture
def adapter(tmp_path):
    return ClaimDeskAdapter("http://127.0.0.1:5001", str(tmp_path / "cd.db"))


def test_sandbox_allowlist_blocks_external_host(tmp_path):  # V27
    with pytest.raises(SandboxViolation):
        ClaimDeskAdapter("https://example.com", str(tmp_path / "x.db"))
    assert config.SANDBOX_ONLY


def test_two_resets_same_digest(adapter):  # V02
    d1 = adapter.reset("seed_a")
    d2 = adapter.reset("seed_a")
    assert diff(d1, d2).exact
    assert len(d1["claims"]) == 300


def test_volatile_ignored_but_amount_detected(adapter):  # PRD A2 worked example
    d0 = adapter.reset("seed_a")
    con = sqlite3.connect(adapter.db_path)
    con.execute("UPDATE claims SET updated_at='2026-10-11T09:21:00Z' WHERE id='CL-10427'")
    con.commit()
    assert diff(d0, adapter.digest()).exact
    con.execute("UPDATE claims SET amount=1250.00 WHERE id='CL-10427'")
    con.commit()
    d = diff(d0, adapter.digest())
    assert d.changed == {"claims": {"CL-10427": ["amount"]}}
    assert d.rows_differ == 1 and not d.exact
