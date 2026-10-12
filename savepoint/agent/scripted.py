"""Scripted agent and golden paths for the ten ClaimDesk 98 workflows (FR05).

Four injected faults: stop at step k, type a wrong value, skip the final Save, claim done early.
The agent speaks the same interface the Claude agent does: next_action(obs) -> action | terminal.
"""
from dataclasses import dataclass

FAULTS = ("none", "stop_at", "wrong_value", "skip_save", "done_early")
SAVE_WAIT_MS = 700  # must exceed SAVE_DELAY_MS used by the benchmark server


@dataclass
class Terminal:
    status: str  # done | cannot_complete
    summary: str = ""
    value: str | None = None


def _save(button="#save"):
    return [{"type": "click", "selector": button, "commit": True}, {"type": "click", "selector": "#ok"},
            {"type": "wait", "ms": SAVE_WAIT_MS}]


def _note(text, wrong=None):
    s = [{"type": "fill", "selector": "textarea[name=body]", "value": text}]
    if wrong:
        s[0]["wrong"] = wrong
    return s + [{"type": "click", "selector": "#save-note", "commit": True}]


def _claim(cid):
    return [{"type": "goto", "path": f"/claims/{cid}"}]


def golden_steps(workflow_id: str, p: dict) -> list[dict]:
    slug = workflow_id.split(".")[1]
    c = p.get("claim_id")
    if slug == "adjust_amount":
        return (_claim(c) + [{"type": "fill", "selector": "#amount", "value": f"{p['new_amount']:.2f}",
                              "wrong": "125000.00"}] + _save() + _note("amount adjusted per call"))
    if slug == "add_note_only":
        return _claim(c) + _note("reviewed by supervisor", wrong="see you soon")
    if slug == "reassign_adjuster":
        return _claim(c) + [{"type": "select", "selector": "#adjuster_id", "value": p["adjuster"],
                             "wrong": "ADJ-09"}] + _save()
    if slug == "close_claim":
        return (_claim(c) + [{"type": "select", "selector": "#status", "value": p["status"],
                              "wrong": "review"}] + _save() + _note("closed: settled in full"))
    if slug in ("reopen_claim", "approve_claim"):
        return _claim(c) + [{"type": "select", "selector": "#status", "value": p["status"],
                             "wrong": "review"}] + _save()
    if slug == "void_duplicate":
        return _claim(c) + [{"type": "click", "selector": "#delete", "commit": True}, {"type": "click", "selector": "#ok"},
                            {"type": "wait", "ms": 300}]
    if slug == "correct_payee_bank":
        sel = f"form[action$='/payees/{p['payee_id']}']"
        return [{"type": "goto", "path": "/payees"},
                {"type": "fill", "selector": f"{sel} input", "value": p["bank_account"], "wrong": "GB00WRONG"},
                {"type": "click", "selector": f"{sel} button", "commit": True}]
    if slug == "lookup_total":
        return _claim(c) + [{"type": "wait", "ms": 200}]
    if slug == "set_amount_and_reassign":
        return (_claim(c) + [{"type": "fill", "selector": "#amount", "value": f"{p['new_amount']:.2f}",
                              "wrong": "65000000.00"},
                             {"type": "select", "selector": "#adjuster_id", "value": p["adjuster"]}] + _save())
    raise KeyError(workflow_id)


def fault_for(trial: int, workflow_id: str) -> str:
    """Deterministic, paired across arms: trials 1-6 clean, 7 stop_at, 8 wrong_value, 9 skip_save, 10 done_early."""
    return {7: "stop_at", 8: "wrong_value", 9: "skip_save", 10: "done_early"}.get(trial, "none")


class ScriptedAgent:
    """Replays a step list. Faults apply to the first attempt only; notify() rewinds and clears the fault."""

    def __init__(self, workflow_id: str, params: dict, fault: str = "none", k: int = 6,
                 base_url: str = "http://127.0.0.1:5001"):
        if fault not in FAULTS:
            raise ValueError(fault)
        self.base_url = base_url.rstrip("/")
        self.fault = fault
        self.k = k
        self.full = golden_steps(workflow_id, params)
        self.steps = list(self.full)
        if fault == "wrong_value" and not any("wrong" in s for s in self.steps):
            self.fault = "done_early"  # lookup-only workflows have nothing to mistype
        if self.fault == "skip_save":
            self.steps = self._drop_final_save(self.steps)
        self.i = 0
        self.emitted = 0
        self.notes: list[str] = []

    @staticmethod
    def _drop_final_save(steps):
        """Skip the final committing click (and the confirm click and wait that follow it)."""
        j = max((i for i, st in enumerate(steps) if st.get("commit")), default=None)
        if j is None:
            return steps
        end = j + 1
        if end < len(steps) and steps[end].get("selector") == "#ok":
            end += 1
            if end < len(steps) and steps[end]["type"] == "wait":
                end += 1
        return steps[:j] + steps[end:]

    def next_action(self, obs=None):
        if self.fault == "stop_at" and self.emitted >= self.k:
            return Terminal("cannot_complete", "gave up")
        if self.fault == "done_early" and self.emitted >= max(1, len(self.steps) // 2):
            return Terminal("done", "all finished")
        if self.i >= len(self.steps):
            return Terminal("done", "completed the task")
        s = dict(self.steps[self.i])
        if self.fault == "wrong_value" and "wrong" in s:
            s["value"] = s["wrong"]
        s.pop("wrong", None)
        s.pop("commit", None)
        if s["type"] == "goto":
            s["url"] = self.base_url + s.pop("path")
        self.i += 1
        self.emitted += 1
        return s

    def notify(self, message: str, restored_step: int = 0):
        """Retry hook (policy savepoint_retry): record the message, rewind to the restored step, drop the fault."""
        self.notes.append(message)
        self.fault = "none"
        self.steps = list(self.full)
        # A restore reloads the page, so unsaved form input is gone: resume from the last navigation.
        j = max((k for k in range(min(restored_step, len(self.steps))) if self.steps[k]["type"] == "goto"),
                default=0)
        self.i = self.emitted = j
