"""Record the data behind the console's "Try it" tab: one real run of claimdesk.adjust_amount for every
(fault x protection) pair, with the record state after every event. Nothing is hand-written: the events come from the
real runtime (instrumented), the app is the real ClaimDesk 98 and the agent is the scripted one.

Run: uv run python scripts/make_experience_data.py   (needs Chromium; takes about 3 minutes)
Writes console/public/data/experience.js and console/public/experience/*.png
"""
import json
import shutil
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from savepoint.adapters.claimdesk import ClaimDeskAdapter
from savepoint.adapters.server import ClaimDeskServer
from savepoint.agent import actuator as actuator_mod
from savepoint.agent import scripted
from savepoint.bench.golden import compute_golden
from savepoint.contracts import evaluator, schema
from savepoint.runtime import runtime
from savepoint.runtime.runtime import RunContext, run_workflow

ROOT = Path(__file__).resolve().parents[1]
OUT_JS = ROOT / "console" / "public" / "data" / "experience.js"
OUT_IMG = ROOT / "console" / "public" / "experience"
CLAIM = "CL-10427"
FAULTS = ["none", "stop_at", "wrong_value", "skip_save", "done_early"]
ARMS = {"B": "off", "S": "savepoint", "R": "retry"}


def friendly(a: dict) -> str:
    t, sel = a["type"], a.get("selector", "")
    if t == "goto":
        return f"Open claim {CLAIM}"
    if t == "fill" and sel == "#amount":
        return f"Type {a['value']} in the Amount box"
    if t == "fill":
        return f"Type the note: “{a['value']}”"
    if t == "click" and sel == "#save":
        return "Click Save"
    if t == "click" and sel == "#ok":
        return "Click OK on the confirmation"
    if t == "click" and sel == "#save-note":
        return "Click Save note"
    if t == "wait":
        return "Wait for the screen to finish saving"
    return f"{t} {sel}".strip()


def main():
    contract = schema.load(str(ROOT / "workflows" / "claimdesk" / "adjust_amount.yaml"))
    work = Path(tempfile.mkdtemp(prefix="savepoint-exp-"))
    db = str(work / "claimdesk.db")
    adapter = ClaimDeskAdapter("http://127.0.0.1:5021", db)
    adapter.reset("seed_a")
    OUT_IMG.mkdir(parents=True, exist_ok=True)
    for old in OUT_IMG.glob("*.png"):
        old.unlink()

    def state():
        r = adapter.query("SELECT amount, status FROM claims WHERE id = :i", {"i": CLAIM})[0]
        notes = [x["body"] for x in adapter.query("SELECT body FROM claim_notes WHERE claim_id = :i ORDER BY id", {"i": CLAIM})]
        return {"amount": round(float(r["amount"]), 2), "status": r["status"], "notes": notes}

    timeline: list[dict] = []

    real_execute = actuator_mod.Actuator.execute
    real_take, real_restore, real_check = runtime._take, runtime._restore, evaluator.check
    real_next = scripted.ScriptedAgent.next_action

    def execute(self, action):
        out = real_execute(self, action)
        timeline.append({"t": "step", "text": friendly(action), "state": state()})
        return out

    def take(ctx, run_id, step, kind, page, cps, cps_rows, stats):
        cp = real_take(ctx, run_id, step, kind, page, cps, cps_rows, stats)
        timeline.append({"t": "checkpoint", "kind": kind, "step": step, "state": state()})
        return cp

    def restore(ctx, run_id, cp, page, act, why, failing_step, rbs):
        page2, res = real_restore(ctx, run_id, cp, page, act, why, failing_step, rbs)
        rb = rbs[-1]
        timeline.append({"t": "restore", "reason": rb["reason"], "exact": bool(rb["exact"]),
                         "rows_differ": rb["rows_differ"], "restore_ms": rb["restore_ms"],
                         "to": "the start" if cp.step_idx == 0 else f"before step {cp.step_idx}",
                         "state": state(), "_shots": [rb["shot_before"], rb["shot_after"]]})
        return page2, res

    def check(c, phase, ad, s0=None, s0_db=None):
        res = real_check(c, phase, ad, s0, s0_db)
        timeline.append({"t": "check", "phase": phase, "results": [
            {"id": r.check_id, "passed": bool(r.passed),
             "observed": r.observed if isinstance(r.observed, (str, int, float, list, type(None))) else str(r.observed),
             "expected": r.expected} for r in res]})
        return res

    def next_action(self, obs=None):
        a = real_next(self, obs)
        if isinstance(a, scripted.Terminal):
            timeline.append({"t": "agent", "status": a.status, "text": a.summary})
        return a

    actuator_mod.Actuator.execute = execute
    runtime._take, runtime._restore, evaluator.check = take, restore, check
    scripted.ScriptedAgent.next_action = next_action

    data = {"claim": CLAIM, "title": "Change a claim amount and add an adjustment note",
            "instruction": contract.text(), "initial": None, "runs": {}}
    try:
        with ClaimDeskServer(db, 5021, save_delay_ms=300) as server, sync_playwright() as p:
            browser = p.chromium.launch()

            def make_ctx():
                return RunContext(adapter, browser, server.url, str(work / "art"))

            golden = compute_golden(contract, make_ctx())
            adapter.reset("seed_a")
            data["initial"] = state()
            for fault in FAULTS:
                for arm, label in ARMS.items():
                    timeline.clear()
                    timeline.append({"t": "start", "state": None})
                    agent = scripted.ScriptedAgent(contract.id, contract.params, fault, base_url=server.url)
                    res = run_workflow(contract, arm, agent, 1, make_ctx(), golden, fault)
                    row = res["run"]
                    events = [dict(e) for e in timeline]
                    events[0]["state"] = data["initial"]
                    shots = []
                    for e in events:
                        for s in e.pop("_shots", []):
                            if s:
                                name = f"{fault}-{arm}-{len(shots)}.png"
                                shutil.copyfile(s, OUT_IMG / name)
                                shots.append(name)
                    events.append({"t": "end", "state": state()})
                    data["runs"][f"{fault}|{label}"] = {
                        "fault": fault, "protection": label, "arm": arm, "events": events, "shots": shots,
                        "agent_status": row["agent_status"], "savepoint": row["sp_outcome"], "oracle": row["oracle"],
                        "false_completion": bool(row["false_completion"]), "retries": row["retries"],
                        "steps": row["steps"], "wall_ms": row["wall_ms"]}
                    print(fault, arm, row["sp_outcome"], row["oracle"], flush=True)
            browser.close()
    finally:
        actuator_mod.Actuator.execute = real_execute
        runtime._take, runtime._restore, evaluator.check = real_take, real_restore, real_check
        scripted.ScriptedAgent.next_action = real_next

    OUT_JS.write_text("window.EXPERIENCE=" + json.dumps(data, separators=(",", ":")) + ";", encoding="utf-8")
    print("wrote", OUT_JS, OUT_JS.stat().st_size, "bytes;", len(list(OUT_IMG.glob('*.png'))), "images")


if __name__ == "__main__":
    main()
