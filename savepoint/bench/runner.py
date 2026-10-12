"""Resumable benchmark runner (FR20): workflows x arms x trials, never the same key twice (INV08)."""
from pathlib import Path

from savepoint.agent.scripted import ScriptedAgent, fault_for
from savepoint.bench.golden import compute_golden
from savepoint.contracts import schema
from savepoint.ledger.db import Ledger
from savepoint.runtime.runtime import run_workflow


def load_contracts(directory: str) -> list[tuple[schema.Contract, str]]:
    out = []
    for p in sorted(Path(directory).glob("*.yaml")):
        text = p.read_text(encoding="utf-8")
        out.append((schema.parse(text), text))
    return out


def run_benchmark(ledger: Ledger, make_ctx, contracts, arms=("B", "S", "R"), trials=10, model="scripted",
                  max_runs: int | None = None, progress=None) -> int:
    """Run every missing (workflow, arm, trial, model). Returns the number of runs executed now."""
    goldens = {}
    for c, text in contracts:
        ctx = make_ctx()
        goldens[c.id] = compute_golden(c, ctx)
        ledger.upsert_workflow(c, text, goldens[c.id])
    executed = 0
    for trial in range(1, trials + 1):
        for c, _ in contracts:
            for arm in arms:
                if ledger.run_exists(c.id, arm, trial, model):
                    continue
                if max_runs is not None and executed >= max_runs:
                    return executed
                ctx = make_ctx()
                fault = fault_for(trial, c.id)
                agent = ScriptedAgent(c.id, c.params, fault, base_url=ctx.base_url)
                res = run_workflow(c, arm, agent, trial, ctx, goldens[c.id], fault)
                ledger.record_run(res["run"], res["steps"], res["checkpoints"], res["validations"],
                                  res["rollbacks"])
                executed += 1
                if progress:
                    progress(executed, c.id, arm, trial, res["run"])
    return executed
