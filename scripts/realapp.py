"""Real-app helper (OpenMRS / iDempiere). Usage:
  realapp.py openmrs seed          register the patient cast through the UI and freeze baseline
  realapp.py openmrs test [slug]   run each golden path, check goal + frame against its contract
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from savepoint.agent.actuator import Actuator
from savepoint.agent.scripted import ScriptedAgent, Terminal
from savepoint.bench.runner import load_contracts
from savepoint.contracts import evaluator
from savepoint.runtime.runtime import RunContext

ROOT = Path(__file__).resolve().parents[1]


def make(app):
    if app == "openmrs":
        from savepoint.adapters.openmrs import OpenMrsAdapter
        return OpenMrsAdapter(), "http://localhost:8080"
    from savepoint.adapters.idempiere import IdempiereAdapter
    return IdempiereAdapter(), "http://localhost:8080"


def run_steps(ctx, steps_agent):
    page = ctx.new_page()
    act = Actuator(page)
    while True:
        a = steps_agent.next_action(None)
        if isinstance(a, Terminal):
            return page
        try:
            act.execute(a)
        except Exception as e:
            page.screenshot(path="/tmp/fail.png")
            raise RuntimeError(f"step failed {a}: {str(e)[:120]}") from e


def seed(app):
    adapter, base = make(app)
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = RunContext(adapter, b, base, "artifacts")
        page = ctx.new_page()
        act = Actuator(page)
        if app == "openmrs":
            from savepoint.agent import openmrs_paths as op
            cast = [("Ravi", "Menon", False), ("Meera", "Iyer", True), ("Dev", "Patel", False), ("Kiran", "Shah", False)]
            steps = []
            for given, family, visit in cast:
                steps += op.register(given, family)
                if visit:
                    steps += op.start_visit(adapter.query("SELECT MAX(patient_id) AS m FROM patient")[0]["m"] + 1)
        else:
            from savepoint.agent import idempiere_paths as ip
            steps = ip.steps("create_business_partner", {"value": "BP-DELME", "name": "Delete Me Partner"})
        for s in steps:
            s = dict(s)
            s.pop("commit", None)
            s.pop("wrong", None)
            if s["type"] == "goto":
                s["url"] = base + s.pop("path")
            act.execute(s)
        ctx.close()
        b.close()
    print("baseline bytes", adapter.make_baseline())


def test(app, only=None):
    adapter, base = make(app)
    contracts = load_contracts(str(ROOT / "workflows" / app))
    with sync_playwright() as p:
        b = p.chromium.launch()
        for c, _ in contracts:
            if only and not c.id.endswith(only):
                continue
            ctx = RunContext(adapter, b, base, "artifacts")
            s0 = adapter.reset(c.fixture)
            snap = str(ROOT / "artifacts" / "t.snapshot")
            adapter.snapshot_db(snap)
            agent = ScriptedAgent(c.id, c.params, "none", base_url=base)
            try:
                pg = run_steps(ctx, agent)
                pg.screenshot(path='/tmp/end.png')
                g = evaluator.check(c, "goal", adapter)
                f = evaluator.check(c, "frame", adapter, s0, snap)
                bad = [x for x in g + f if not x.passed]
                print(c.id, "OK" if not bad else "FAIL", [(x.check_id, x.observed) for x in bad])
            except Exception as e:  # noqa: BLE001
                print(c.id, "ERROR", str(e)[:300])
            ctx.close()
        b.close()


if __name__ == "__main__":
    app, cmd = sys.argv[1], sys.argv[2]
    (seed(app) if cmd == "seed" else test(app, sys.argv[3] if len(sys.argv) > 3 else None))
