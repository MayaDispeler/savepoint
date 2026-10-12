import json
from pathlib import Path

from savepoint.bench.runner import load_contracts, run_benchmark
from savepoint.ledger.db import Ledger, runs
from savepoint.runtime.runtime import run_workflow

WF = Path(__file__).resolve().parents[2] / "workflows" / "claimdesk"


def test_runner_resumes_after_kill_without_duplicates(live, tmp_path):  # V19
    contracts = [c for c in load_contracts(str(WF)) if c[0].id.endswith("add_note_only")]
    ledger = Ledger(f"sqlite:///{tmp_path / 'l.db'}")
    assert run_benchmark(ledger, live, contracts, arms=("B", "S"), trials=5, max_runs=4) == 4  # "killed" at 4
    assert run_benchmark(ledger, live, contracts, arms=("B", "S"), trials=5) == 6
    rows = ledger.all_runs()
    assert len(rows) == 10
    assert len({(r["workflow_id"], r["arm"], r["trial"], r["model"]) for r in rows}) == 10
    assert run_benchmark(ledger, live, contracts, arms=("B", "S"), trials=5) == 0  # nothing left to run
    assert ledger.run_exists("claimdesk.add_note_only", "S", 5, "scripted")
    assert runs.c.workflow_id is not None


def test_traces_emitted_for_one_workflow(live, tmp_path, monkeypatch):  # V32
    from savepoint.agent.scripted import ScriptedAgent
    from savepoint.bench.golden import compute_golden
    trace = tmp_path / "traces.jsonl"
    monkeypatch.setenv("SAVEPOINT_TRACES", str(trace))
    c = load_contracts(str(WF))[0][0]
    g = compute_golden(c, live())
    run_workflow(c, "S", ScriptedAgent(c.id, c.params, "stop_at", 3, base_url=live.url), 1, live(), g, "stop_at")
    names = {json.loads(line)["name"] for line in trace.read_text().splitlines()}
    assert {"run", "step", "checkpoint", "restore"} <= names


def test_required_screen_check_rolls_back_but_advisory_does_not(live, tmp_path):  # V17
    from savepoint.agent.scripted import ScriptedAgent
    from savepoint.bench.golden import compute_golden
    from savepoint.contracts import schema

    class Vision:
        def __init__(self, answer):
            self.answer = answer

        def ask(self, png, question):
            return self.answer

    base = (WF / "add_note_only.yaml").read_text(encoding="utf-8")

    def go(required, answer):
        text = base + f"screen:\n- id: saved_banner\n  ask: Does the page say Saved?\n  required: {str(required).lower()}\n"
        c = schema.parse(text)
        g = compute_golden(c, live())
        ctx = live()
        ctx.vision = Vision(answer)
        agent = ScriptedAgent(c.id, c.params, "none", base_url=live.url)
        return run_workflow(c, "S", agent, 1, ctx, g)["run"]["sp_outcome"]

    assert go(False, False) == "committed"   # advisory "no" leaves the run committed
    assert go(True, False) == "rolled_back"  # required "no" triggers rollback
    assert go(True, True) == "committed"
