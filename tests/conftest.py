import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "claimdesk"))


@pytest.fixture(scope="session")
def live(tmp_path_factory):
    """One live ClaimDesk server + Chromium for integration tests."""
    from playwright.sync_api import sync_playwright

    from savepoint.adapters.claimdesk import ClaimDeskAdapter
    from savepoint.adapters.server import ClaimDeskServer
    from savepoint.runtime.runtime import RunContext

    d = tmp_path_factory.mktemp("live")
    db = str(d / "cd.db")
    server = ClaimDeskServer(db, port=5077, save_delay_ms=200)
    adapter = ClaimDeskAdapter(server.url, db)
    adapter.reset("seed_a")
    server.start()
    pw = sync_playwright().start()
    browser = pw.chromium.launch()

    def make(artifacts=None):
        return RunContext(adapter, browser, server.url, artifacts or str(d / "art"))

    make.adapter, make.url = adapter, server.url
    yield make
    browser.close()
    pw.stop()
    server.stop()


@pytest.fixture(autouse=True)
def no_model_calls(monkeypatch):
    """NFR07 / V33: constructing a real Anthropic client in a test fails the test."""
    import anthropic

    def boom(*a, **k):
        raise AssertionError("a test tried to construct a real Anthropic client")

    monkeypatch.setattr(anthropic, "Anthropic", boom)
    monkeypatch.setattr(anthropic, "AsyncAnthropic", boom)
