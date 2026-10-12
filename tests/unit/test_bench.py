import re
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from savepoint.agent import budget as bud
from savepoint.agent.claude_agent import ClaudeAgent, to_action
from savepoint.agent.scripted import ScriptedAgent, Terminal
from savepoint.bench import metrics, oracle
from savepoint.bench.passk import mean_pass_hat_k, pass_hat_k, wilson
from savepoint.contracts.vision import VisionChecker

SRC = Path(__file__).resolve().parents[2] / "savepoint"


def dg(**rows):
    return {t: {pk: dict(cols) for pk, cols in r.items()} for t, r in rows.items()}


S0 = dg(claims={"CL-1": {"amount": "a1", "status": "s1"}}, notes={})
GOLD = oracle.normalize(S0, dg(claims={"CL-1": {"amount": "a2", "status": "s1"}}, notes={"1": {"body": "b"}}))


def test_oracle_four_examples():  # V20 / A5
    ok = dg(claims={"CL-1": {"amount": "a2", "status": "s1"}}, notes={"9": {"body": "b"}})  # new key, same content
    assert oracle.classify(True, ok, S0, GOLD) == "VS"
    no_note = dg(claims={"CL-1": {"amount": "a2", "status": "s1"}}, notes={})
    assert oracle.classify(True, no_note, S0, GOLD) == "IS"
    assert oracle.classify(False, S0, S0, GOLD) == "VF"
    assert oracle.classify(False, no_note, S0, GOLD) == "IF"
    assert oracle.claim_true(ok, S0, GOLD) and not oracle.claim_true(no_note, S0, GOLD)


def test_pass_k_worked_example():  # V21 / A6
    cn = [(10, 10), (8, 10), (5, 10)]
    got = [round(mean_pass_hat_k(cn, k), 3) for k in (1, 2, 5, 10)]
    assert got == [0.767, 0.615, 0.409, 0.333]
    assert round(pass_hat_k(8, 10, 2), 3) == round(28 / 45, 3)


def test_wilson_and_catch_rates_worked_example():  # A7
    lo, hi = wilson(288, 300)
    assert (round(lo, 3), round(hi, 3)) == (0.931, 0.977)
    runs = ([{"claim_true": False, "false_completion": i < 37} for i in range(40)]
            + [{"claim_true": True, "false_completion": i < 4} for i in range(160)])
    c = metrics.catch_rates(runs)
    assert c["catch_rate"] == 0.925 and c["false_alarm_rate"] == 0.025


def test_import_lint_oracle_and_validators_separate():  # V22 / INV04
    oracle_src = (SRC / "bench" / "oracle.py").read_text()
    assert not re.search(r"^\s*(from|import)\s+savepoint\.(contracts|runtime)", oracle_src, re.MULTILINE)
    for f in (SRC / "contracts").glob("*.py"):
        assert "savepoint.bench" not in f.read_text(), f.name


def test_only_redact_writes_images():  # V28 / INV06
    for f in SRC.rglob("*.py"):
        if f.name == "redact.py":
            continue
        text = f.read_text()
        assert not re.search(r"screenshot\(\s*path", text), f
        assert not re.search(r"\.save\(\s*(?!buf)", text), f
        assert ".write_bytes(" not in text or "png" not in text.lower(), f


def test_budget_guard_refuses_before_any_call():  # V08
    class Boom:
        class messages:
            @staticmethod
            def create(**kw):
                raise AssertionError("model call made")

    guard = bud.BudgetGuard(cap_usd=0.01)
    with pytest.raises(bud.BudgetExceeded):
        ClaudeAgent(Boom, "claude-haiku-5-5", "task", guard)


def test_cost_matches_prd_a8_estimate():
    assert round(bud.estimate_run_usd("claude-haiku-5-5"), 4) == 0.0176


def usage(i=1000, o=100):
    return NS(input_tokens=i, output_tokens=o, cache_read_input_tokens=0, cache_creation_input_tokens=0)


class Recorded:
    """Replays recorded responses; no network."""

    def __init__(self, responses):
        self.responses, self.calls = list(responses), 0
        self.messages = self

    def create(self, **kw):
        self.calls += 1
        return self.responses.pop(0)


def tool(name, **inp):
    return NS(type="tool_use", id=f"t{name}", name=name, input=inp)


def test_claude_loop_recorded_responses():  # V06
    client = Recorded([
        NS(content=[tool("computer", action="left_click", coordinate=[10, 20])], usage=usage()),
        NS(content=[tool("computer", action="type", text="1250.00")], usage=usage()),
        NS(content=[tool("report_outcome", status="done", summary="finished")], usage=usage()),
    ])
    guard = bud.BudgetGuard(cap_usd=25)
    agent = ClaudeAgent(client, "claude-haiku-5-5", "do it", guard, "run1")
    assert agent.next_action(b"png") == {"type": "click", "x": 10, "y": 20}
    assert agent.next_action(b"png") == {"type": "type", "text": "1250.00"}
    t = agent.next_action(b"png")
    assert isinstance(t, Terminal) and t.status == "done" and client.calls == 3 and guard.spent > 0
    assert any(m["content"][0].get("type") == "tool_result" for m in agent.messages if isinstance(m["content"], list))


def test_to_action_mapping():
    assert to_action({"action": "key", "text": "Return"}) == {"type": "key", "key": "Enter"}
    assert to_action({"action": "wait", "duration": 2})["ms"] == 2000
    with pytest.raises(ValueError):
        to_action({"action": "zoom"})


def test_vision_recorded_answers():  # V17 (checker half)
    yes = VisionChecker(Recorded([NS(content=[NS(type="text", text="Yes.")], usage=usage())]))
    no = VisionChecker(Recorded([NS(content=[NS(type="text", text="No")], usage=usage())]))
    assert yes.ask(b"x", "q?") is True and no.ask(b"x", "q?") is False


def test_scripted_faults_shape():
    base = ScriptedAgent("claimdesk.adjust_amount", {"claim_id": "c", "new_amount": 1.0})
    n = 0
    while not isinstance(base.next_action(), Terminal):
        n += 1
    stop = ScriptedAgent("claimdesk.adjust_amount", {"claim_id": "c", "new_amount": 1.0}, "stop_at", 6)
    m = 0
    while not isinstance(t := stop.next_action(), Terminal):
        m += 1
    assert m == 6 and t.status == "cannot_complete" and n > 6
    skip = ScriptedAgent("claimdesk.add_note_only", {"claim_id": "c"}, "skip_save")
    sel = []
    while not isinstance(a := skip.next_action(), Terminal):
        sel.append(a.get("selector"))
    assert "#save-note" not in sel
