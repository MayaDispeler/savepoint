from pathlib import Path

from savepoint.agent import simulated
from savepoint.agent.budget import BudgetGuard
from savepoint.agent.claude_agent import ClaudeAgent
from savepoint.bench.golden import compute_golden
from savepoint.contracts import schema
from savepoint.runtime.runtime import run_workflow

WF = Path(__file__).resolve().parents[2] / "workflows" / "claimdesk"


def test_simulated_haiku_run_through_real_agent_loop(live):  # V07 stand-in: no real model call
    c = schema.load(str(WF / "add_note_only.yaml"))
    golden = compute_golden(c, live())
    ctx = live()
    client = simulated.SimulatedClient(simulated.load("add_note_only"),
                                       page_provider=lambda: ctx._contexts[-1].pages[0])
    guard = BudgetGuard(cap_usd=25)
    agent = ClaudeAgent(client, "claude-haiku-5-5", c.text(), guard, "sim-run")
    res = run_workflow(c, "S", agent, 1, ctx, golden)
    run = res["run"]
    assert (run["agent_status"], run["sp_outcome"], run["oracle"]) == ("done", "committed", "VS")
    assert client.calls == 5 and not client.transcript            # model "called" 5 times, all replayed
    assert 0 < guard.spent < 0.01                                 # cost accounted by the A8 price model
    assert [s["action"]["type"] for s in res["steps"]] == ["click", "click", "type", "click"]
    assert any(cp["kind"] == "risky" for cp in res["checkpoints"])  # Save note clicked by pixel, still detected
