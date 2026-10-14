"""Savepoint runtime: run one workflow in arm B (baseline), S (atomic) or R (savepoint_retry).

Implements A1 (risky step checkpoints), A3 (run policy), INV01 (S0 before step 1) and INV02 (one outcome).
"""
import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from savepoint import telemetry
from savepoint.agent.actuator import VIEWPORT, Actuator
from savepoint.agent.scripted import Terminal
from savepoint.bench import oracle
from savepoint.contracts import evaluator
from savepoint.contracts.schema import Contract
from savepoint.export import diffimg, redact
from savepoint.snapshot import checkpoint as cpmod

STEP_BUDGET = 40
WALL_LIMIT_S = 900
MAX_RETRIES = 2
POLICY = {"B": "none", "S": "atomic", "R": "savepoint_retry"}


@dataclass
class RunContext:
    adapter: object
    browser: object
    base_url: str
    artifacts: str
    model: str = "scripted"
    vision: object | None = None  # optional object with ask(png: bytes, question: str) -> bool
    step_budget: int = STEP_BUDGET
    wall_limit_s: float = WALL_LIMIT_S
    _contexts: list = field(default_factory=list)

    def new_page(self, storage_state: str | None = None):
        ctx = self.browser.new_context(viewport=VIEWPORT, storage_state=storage_state)
        self._contexts.append(ctx)
        page = ctx.new_page()
        if storage_state is None:
            self.adapter.login(page)
        return page

    def close(self):
        for c in self._contexts:
            c.close()
        self._contexts.clear()


def _sha(d) -> str:
    return hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()


def run_workflow(contract: Contract, arm: str, agent, trial: int, ctx: RunContext, golden: dict | None,
                 fault: str = "none") -> dict:
    """Execute one run. Returns {"run": row, "steps": [...], "checkpoints": [...], "validations": [...],
    "rollbacks": [...]} ready for Ledger.record_run."""
    adapter, run_id = ctx.adapter, str(uuid.uuid4())
    t_start, started = time.monotonic(), datetime.now(UTC)
    steps_rows: list[dict] = []
    cps_rows: list[dict] = []
    vals: list[dict] = []
    rbs: list[dict] = []
    cps: list[cpmod.Checkpoint] = []
    stats = {"retries": 0, "false_completion": False, "quarantined": False, "cp_ms": 0}

    with telemetry.span("run", run_id=run_id, workflow=contract.id, arm=arm, trial=trial):
        s0 = adapter.reset(contract.fixture)
        page = ctx.new_page()
        act = Actuator(page)
        s0_db = None
        if arm in ("S", "R"):
            cp0 = _take(ctx, run_id, 0, "initial", page, cps, cps_rows, stats)  # INV01
            s0_db = cp0.db_path
        prev_marker = _sha(adapter.digest())
        last_cp_step, changed_since_cp = 0, False
        i, total = 0, 0
        agent_status, sp_outcome, reason, summary = "done", "none", None, ""

        def fail(why: str, failing_step: int, message: str):
            """Apply the run policy for a failure. Returns True when the run continues (retry)."""
            nonlocal page, act, prev_marker, last_cp_step, changed_since_cp, i, sp_outcome
            retry = (arm == "R" and stats["retries"] < MAX_RETRIES and why in ("invariant", "false_completion"))
            if retry:
                target = cps[0]
                if why == "invariant":
                    eligible = [c for c in cps if c.step_idx <= failing_step]
                    target = eligible[-1] if eligible else cps[0]
            else:
                target = cps[0]
            new_page, rb = _restore(ctx, run_id, target, page, act, why, failing_step, rbs)
            page, act = new_page, Actuator(new_page)
            if not rb.exact:
                stats["quarantined"] = True
                sp_outcome = "rollback_failed"
                return False
            del cps[cps.index(target) + 1:]
            prev_marker, last_cp_step, changed_since_cp = _sha(adapter.digest()), target.step_idx, False
            if retry:
                stats["retries"] += 1
                restored = max(target.step_idx - 1, 0)
                if hasattr(agent, "notify"):
                    agent.notify(f"State restored to checkpoint {target.step_idx} because {message}", restored)
                i = restored
                return True
            sp_outcome = "rolled_back"
            return False

        terminal = None
        while True:
            if total >= ctx.step_budget:
                agent_status, reason = "step_budget", "step_budget"
                break
            if time.monotonic() - t_start > ctx.wall_limit_s:
                agent_status, reason = "timeout", "timeout"
                break
            try:
                obs = (act.screenshot_bytes(adapter.redaction_selectors)
                       if getattr(agent, "wants_screenshot", False) else None)
                action = agent.next_action(obs)
            except Exception as e:  # noqa: BLE001 - model/agent error ends the run
                agent_status, reason, summary = "error", "error", str(e)
                break
            if isinstance(action, Terminal):
                terminal = action
                agent_status = action.status
                summary = action.summary
                break
            i += 1
            total += 1
            t0 = time.monotonic()
            risky = False
            if arm in ("S", "R"):
                risky = act.is_risky(action, adapter.risky_patterns)
                if risky and not (i - last_cp_step <= 2 and not changed_since_cp):
                    _take(ctx, run_id, i, "risky", page, cps, cps_rows, stats)
                    last_cp_step, changed_since_cp = i, False
            try:
                with telemetry.span("step", run_id=run_id, idx=i, action=action["type"]):
                    act.execute(action)
            except Exception as e:  # noqa: BLE001 - actuator failure ends the run as an error
                agent_status, reason, summary = "error", "error", str(e)[:200]
                break
            marker = _sha(adapter.digest())
            changed = marker != prev_marker
            prev_marker = marker
            steps_rows.append({"idx": total, "action": action, "element": {"name": act.target_name(action)}
                               if risky else None, "risky": risky, "state_changed": changed,
                               "screenshot": None, "t_ms": int((time.monotonic() - t0) * 1000)})
            if changed:
                changed_since_cp = True
                if arm in ("S", "R"):
                    results = evaluator.check(contract, "invariant", adapter)
                    _record_vals(vals, total, results)
                    bad = [r for r in results if not r.passed]
                    if bad:
                        msg = f"check {bad[0].check_id} failed: observed {bad[0].observed}"
                        if fail("invariant", i, msg):
                            continue
                        agent_status, reason, terminal = "halted", "invariant", None
                        summary = "halted by an invariant failure"
                        break

        verify = None
        claim = None
        if sp_outcome not in ("rolled_back", "rollback_failed") and arm in ("S", "R"):
            while True:
                if agent_status == "done" and terminal is not None:
                    verify = adapter.digest()
                    claim = oracle.claim_true(verify, s0, golden) if golden is not None else None
                    results = (evaluator.check(contract, "goal", adapter)
                               + evaluator.check(contract, "frame", adapter, s0, s0_db))
                    if ctx.vision is not None and contract.screen:
                        results += _screen_checks(ctx, contract, act, adapter)
                    _record_vals(vals, None, results)
                    req_screen = {s["id"] for s in contract.screen if s.get("required")}
                    bad = [r for r in results if not r.passed and (r.phase != "screen" or r.check_id in req_screen)]
                    if not bad:
                        sp_outcome = "retried_committed" if stats["retries"] else "committed"
                        break
                    stats["false_completion"] = True
                    msg = f"check {bad[0].check_id} failed: observed {bad[0].observed}"
                    if fail("false_completion", total, msg):
                        # retry: run the agent again until it reports a terminal state
                        agent_status, terminal = _drive(ctx, agent, act, total, steps_rows)
                        if agent_status == "done":
                            continue
                        fail(agent_status, total, f"agent ended with {agent_status}")
                    break
                else:
                    fail(reason or "agent_failed", total, f"agent ended with {agent_status}")
                    break
            # fail() already restored when the run did not commit
        if arm == "B":
            sp_outcome = "none"
        elif sp_outcome == "none":
            sp_outcome = "rolled_back"

        final = adapter.digest()
        reported_done = (agent_status == "done") if arm == "B" else sp_outcome in ("committed", "retried_committed")
        oracle_class = oracle.classify(reported_done, final, s0, golden) if golden is not None else "VS"
        cp_ms = stats["cp_ms"] + sum(r["restore_ms"] for r in rbs)
        row = {
            "id": run_id, "workflow_id": contract.id, "arm": arm, "model": ctx.model, "trial": trial,
            "policy": POLICY[arm], "fault": fault, "started_at": started, "ended_at": datetime.now(UTC),
            "agent_status": agent_status,
            "sp_outcome": sp_outcome, "oracle": oracle_class,
            "claim_true": claim, "false_completion": stats["false_completion"],
            "verify_digest": oracle.normalize(s0, verify) if verify is not None else None,
            "steps": total, "wall_ms": int((time.monotonic() - t_start) * 1000), "checkpoint_ms": cp_ms,
            "featured": False, "quarantined": stats["quarantined"], "retries": stats["retries"]}
        ctx.close()
        return {"run": row, "steps": steps_rows, "checkpoints": cps_rows, "validations": vals,
                "rollbacks": rbs, "summary": summary}


def _drive(ctx, agent, act, total, steps_rows):
    """After a retry from the false-completion path, keep driving the agent until it is terminal."""
    adapter = ctx.adapter
    prev = _sha(adapter.digest())
    n = 0
    while n < ctx.step_budget:
        action = agent.next_action(None)
        if isinstance(action, Terminal):
            return action.status, action
        n += 1
        t0 = time.monotonic()
        act.execute(action)
        cur = _sha(adapter.digest())
        steps_rows.append({"idx": total + n, "action": action, "element": None, "risky": False,
                           "state_changed": cur != prev, "screenshot": None,
                           "t_ms": int((time.monotonic() - t0) * 1000)})
        prev = cur
    return "step_budget", None


def _take(ctx, run_id, step, kind, page, cps, cps_rows, stats):
    with telemetry.span("checkpoint", run_id=run_id, step=step, kind=kind):
        cp = cpmod.take(ctx.adapter, run_id, step, kind, ctx.artifacts, page)
    cps.append(cp)
    stats["cp_ms"] += cp.took_ms
    cps_rows.append({"id": cp.id, "step_idx": step, "kind": kind, "db_path": cp.db_path,
                     "files_path": cp.files_path, "browser_state_path": cp.browser_state_path, "url": cp.url,
                     "digest_sha256": cp.digest_sha256, "bytes": cp.bytes, "took_ms": cp.took_ms})
    return cp


def _restore(ctx, run_id, cp, page, act, why, failing_step, rbs):
    """Restore a checkpoint, with before/after redacted screenshots and the pixel diff (A9)."""
    reason = {"invariant": "invariant", "false_completion": "false_completion"}.get(why, why)
    if reason not in ("invariant", "false_completion", "agent_failed", "timeout", "step_budget", "error"):
        reason = "agent_failed"
    base = Path(ctx.artifacts) / run_id / f"rb-{len(rbs)}"
    before = act.screenshot_bytes(ctx.adapter.redaction_selectors)
    shot_before = redact.write_png(before, str(base) + "-before.png")
    holder = {}

    def factory(state):
        holder["page"] = ctx.new_page(state)
        return holder["page"]

    with telemetry.span("restore", run_id=run_id, checkpoint=cp.id, reason=reason):
        res = cpmod.restore(ctx.adapter, cp, factory)
    new_page = res.page or ctx.new_page()
    after = Actuator(new_page).screenshot_bytes(ctx.adapter.redaction_selectors)
    shot_after = redact.write_png(after, str(base) + "-after.png")
    rbs.append({"id": str(uuid.uuid4()), "from_step": failing_step, "checkpoint_id": cp.id, "reason": reason,
                "restore_ms": res.restore_ms, "rows_differ": res.rows_differ, "exact": res.exact,
                "shot_before": shot_before, "shot_after": shot_after,
                "pixel_diff_pct": diffimg.pixel_diff_pct(before, after)})
    return new_page, res


def _record_vals(vals, step_idx, results):
    for r in results:
        vals.append({"step_idx": step_idx, "phase": r.phase, "check_id": r.check_id, "passed": r.passed,
                     "observed": r.observed, "expected": r.expected, "took_ms": r.took_ms})


def _screen_checks(ctx, contract, act, adapter):
    out = []
    png = act.screenshot_bytes(adapter.redaction_selectors)
    for s in contract.screen:
        ok = bool(ctx.vision.ask(png, s["ask"]))
        out.append(evaluator.CheckResult("screen", s["id"], ok, ok, "yes"))
    return out
