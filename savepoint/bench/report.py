"""`make report`: results.json and docs/results.md with sample sizes (FR22)."""
import json
from pathlib import Path

from savepoint.bench import metrics
from savepoint.ledger.db import Ledger, checkpoints, rollbacks

ARM_NAMES = {"B": "B baseline (no Savepoint)", "S": "S atomic", "R": "R savepoint_retry"}


def build(ledger: Ledger, scripted: bool = True) -> dict:
    m = metrics.compute(ledger.all_runs(), ledger.rows(rollbacks), ledger.rows(checkpoints))
    m["agent"] = "scripted fault-injecting agent (not a language model)" if scripted else "language model"
    return m


def write(ledger: Ledger, out_dir: str = "docs") -> dict:
    m = build(ledger)
    Path(out_dir).mkdir(exist_ok=True)
    Path(out_dir, "results.json").write_text(json.dumps(m, indent=2), encoding="utf-8")
    Path(out_dir, "results.md").write_text(render(m), encoding="utf-8")
    return m


def pct(x):
    return "n/a" if x is None else f"{x * 100:.1f}%"


def render(m: dict) -> str:
    L = ["# Savepoint results", "",
         f"Agent: **{m['agent']}**. Faults are injected on a fixed schedule (trials 7 to 10 of each workflow), "
         "paired across arms. These numbers show what the runtime does with a known failure mix. "
         "They are not a measurement of any model's reliability.", "",
         "## Outcomes by arm", "",
         "| Arm | N | Valid success | Atomicity (Wilson 95%) | Invalid success | Unsafe side effect | VS | VF | IS | IF |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for a, x in m["arms"].items():
        lo, hi = x["atomicity_ci95"]
        L.append(f"| {ARM_NAMES.get(a, a)} | {x['n']} | {pct(x['valid_success'])} | {pct(x['atomicity'])} "
                 f"({pct(lo)} to {pct(hi)}) | {pct(x['invalid_success_rate'])} | "
                 f"{pct(x['unsafe_side_effect_rate'])} | {x['VS']} | {x['VF']} | {x['IS']} | {x['IF']} |")
    L += ["", "Atomicity = (VS + VF) / N: the run either fully succeeded or left the state untouched. "
          "IS = said done, state wrong. IF = said not done, state partly changed.", "",
          "## pass^k (mean over workflows)", "", "| Arm | " + " | ".join(f"k={k}" for k in range(1, 11)) + " |",
          "|---|" + "---|" * 10]
    for a, x in m["arms"].items():
        L.append(f"| {a} | " + " | ".join(f"{x['pass_hat_k'].get(str(k), float('nan')):.3f}" for k in range(1, 11)) + " |")
    c = m["catch"]
    L += ["", "## False completions (arm S, single attempt)", "",
          f"- Catch rate: {pct(c['catch_rate'])} ({c['caught']} of {c['false_claims']} false `done` claims caught)",
          f"- False-alarm rate: {pct(c['false_alarm_rate'])} ({c['false_alarms']} of {c['true_claims']} true claims flagged)",
          "", "## Restore fidelity and cost", "",
          f"- Restores: {m['fidelity']['restores']}; exact: {m['fidelity']['exact']} ({pct(m['fidelity']['exact_rate'])})",
          f"- Quarantined runs: {m['quarantined']}",
          f"- Checkpoint p95: {m['timings']['checkpoint_p95_ms']} ms over {m['timings']['checkpoints']} checkpoints; "
          f"restore p95: {m['timings']['restore_p95_ms']} ms",
          f"- Checkpoint + restore share of wall time (arms S and R): {pct(m['overhead']['checkpoint_restore_share_of_wall'])}",
          "", "Sample sizes: " + ", ".join(f"arm {a} N={x['n']} ({x['workflows']} workflows x "
                                            f"{x['trials_per_workflow']} trials)" for a, x in m["arms"].items()), ""]
    return "\n".join(L)
