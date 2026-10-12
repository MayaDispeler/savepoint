from pathlib import Path

import pytest

from savepoint.agent.scripted import ScriptedAgent
from savepoint.bench.golden import compute_golden
from savepoint.contracts import schema
from savepoint.runtime.runtime import run_workflow

WF = Path(__file__).resolve().parents[2] / "workflows" / "claimdesk"


def contract(slug):
    return schema.load(str(WF / f"{slug}.yaml"))


@pytest.fixture(scope="module")
def golden(live):
    return {s: compute_golden(contract(s), live()) for s in ("adjust_amount", "add_note_only")}


def run(live, golden, slug, arm, fault, k=6):
    c = contract(slug)
    agent = ScriptedAgent(c.id, c.params, fault, k, base_url=live.url)
    return run_workflow(c, arm, agent, 1, live(), golden[slug], fault)


def test_golden_diff_shape(golden):
    g = golden["adjust_amount"]
    assert list(g["changed"]["claims"]) == ["CL-10427"] and list(g["changed"]["claims"]["CL-10427"]) == ["amount"]
    assert len(g["added"]["claim_notes"]) == 1


def test_arm_b_golden_is_valid_success(live, golden):  # V04
    r = run(live, golden, "adjust_amount", "B", "none")["run"]
    assert (r["sp_outcome"], r["oracle"], r["agent_status"]) == ("none", "VS", "done")


def test_arm_s_clean_commits(live, golden):
    r = run(live, golden, "adjust_amount", "S", "none")
    assert r["run"]["sp_outcome"] == "committed" and r["run"]["oracle"] == "VS"
    assert r["checkpoints"][0]["kind"] == "initial" and r["checkpoints"][0]["step_idx"] == 0  # V09


def test_stop_midway_rolls_back(live, golden):  # V05
    b = run(live, golden, "adjust_amount", "B", "stop_at", 6)["run"]
    s = run(live, golden, "adjust_amount", "S", "stop_at", 6)
    assert b["oracle"] == "IF"  # the baseline leaves the claim half-edited
    assert s["run"]["sp_outcome"] == "rolled_back" and s["run"]["oracle"] == "VF"
    assert s["rollbacks"][0]["exact"] is True


def test_false_completion_is_caught(live, golden):  # V15
    b = run(live, golden, "add_note_only", "B", "skip_save")["run"]
    s = run(live, golden, "add_note_only", "S", "skip_save")
    assert b["oracle"] == "IS"
    assert s["run"]["sp_outcome"] == "rolled_back" and s["run"]["false_completion"]
    assert s["run"]["oracle"] == "VF" and s["run"]["claim_true"] is False


def test_invariant_failure_s_vs_r(live, golden):  # V14 / V18
    s = run(live, golden, "adjust_amount", "S", "wrong_value")
    assert s["run"]["sp_outcome"] == "rolled_back" and s["run"]["oracle"] == "VF"
    assert any(not v["passed"] and v["phase"] == "invariant" for v in s["validations"])
    r = run(live, golden, "adjust_amount", "R", "wrong_value")
    assert r["run"]["sp_outcome"] == "retried_committed" and r["run"]["oracle"] == "VS"
    assert r["run"]["retries"] == 1


def test_risky_checkpoint_dedupe(live, golden):  # V10
    r = run(live, golden, "adjust_amount", "S", "none")
    kinds = [(c["kind"], c["step_idx"]) for c in r["checkpoints"]]
    assert kinds[0] == ("initial", 0) and len(kinds) == 3  # S0, save click, save-note click
