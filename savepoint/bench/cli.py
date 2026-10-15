"""CLI: `python -m savepoint.bench.cli run|report [--app claimdesk|openmrs|idempiere]`."""
import argparse
import os
import tempfile

from playwright.sync_api import sync_playwright

from savepoint.bench import report
from savepoint.bench.runner import load_contracts, run_benchmark
from savepoint.ledger.db import Ledger
from savepoint.runtime.runtime import RunContext

DEFAULT_TRIALS = {"claimdesk": 10, "openmrs": 5, "idempiere": 5}


def _claimdesk(port):
    from savepoint.adapters.claimdesk import ClaimDeskAdapter
    from savepoint.adapters.server import ClaimDeskServer
    db = os.path.join(tempfile.mkdtemp(prefix="savepoint-"), "claimdesk.db")
    server = ClaimDeskServer(db, port, save_delay_ms=300)
    adapter = ClaimDeskAdapter(server.url, db)
    adapter.reset("seed_a")
    server.start()
    return adapter, server.url, server.stop


def _external(app):
    """OpenMRS and iDempiere run in Docker (started separately); the adapter reads their database directly."""
    if app == "openmrs":
        from savepoint.adapters.openmrs import OpenMrsAdapter
        return OpenMrsAdapter(), "http://localhost:8080", lambda: None
    from savepoint.adapters.idempiere import IdempiereAdapter
    return IdempiereAdapter(), "http://localhost:8081", lambda: None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "report"])
    ap.add_argument("--app", default="claimdesk", choices=list(DEFAULT_TRIALS))
    ap.add_argument("--ledger", default="sqlite:///ledger.db")
    ap.add_argument("--trials", type=int)
    ap.add_argument("--max-runs", type=int)
    ap.add_argument("--port", type=int, default=5001)
    a = ap.parse_args()
    ledger = Ledger(a.ledger)
    if a.cmd == "report":
        report.write(ledger)
        print("wrote docs/results.md and docs/results.json")
        return
    trials = a.trials or DEFAULT_TRIALS[a.app]
    contracts = load_contracts(os.path.join("workflows", a.app))
    adapter, url, stop = _claimdesk(a.port) if a.app == "claimdesk" else _external(a.app)
    pw = sync_playwright().start()
    browser = pw.chromium.launch()
    try:
        n = run_benchmark(ledger, lambda: RunContext(adapter, browser, url, "artifacts"), contracts, trials=trials,
                          max_runs=a.max_runs,
                          progress=lambda i, wf, arm, t, r: print(i, wf, arm, t, r["sp_outcome"], r["oracle"],
                                                                  flush=True))
        print("executed", n)
    finally:
        browser.close()
        pw.stop()
        stop()


if __name__ == "__main__":
    main()
