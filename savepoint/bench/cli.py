"""CLI: `python -m savepoint.bench.cli run|report`."""
import argparse
import os
import tempfile

from playwright.sync_api import sync_playwright

from savepoint.adapters.claimdesk import ClaimDeskAdapter
from savepoint.adapters.server import ClaimDeskServer
from savepoint.bench import report
from savepoint.bench.runner import load_contracts, run_benchmark
from savepoint.ledger.db import Ledger
from savepoint.runtime.runtime import RunContext


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "report"])
    ap.add_argument("--ledger", default="sqlite:///ledger.db")
    ap.add_argument("--trials", type=int, default=10)
    ap.add_argument("--max-runs", type=int)
    ap.add_argument("--port", type=int, default=5001)
    a = ap.parse_args()
    ledger = Ledger(a.ledger)
    if a.cmd == "report":
        report.write(ledger)
        print("wrote docs/results.md and docs/results.json")
        return
    contracts = load_contracts("workflows/claimdesk")
    work = tempfile.mkdtemp(prefix="savepoint-")
    db = os.path.join(work, "claimdesk.db")
    server = ClaimDeskServer(db, a.port, save_delay_ms=300)
    adapter = ClaimDeskAdapter(server.url, db)
    adapter.reset("seed_a")
    server.start()
    pw = sync_playwright().start()
    browser = pw.chromium.launch()
    try:
        n = run_benchmark(ledger, lambda: RunContext(adapter, browser, server.url, os.path.join("artifacts")),
                          contracts, trials=a.trials, max_runs=a.max_runs,
                          progress=lambda i, wf, arm, t, r: print(i, wf, arm, t, r["sp_outcome"], r["oracle"], flush=True))
        print("executed", n)
    finally:
        browser.close()
        pw.stop()
        server.stop()


if __name__ == "__main__":
    main()
