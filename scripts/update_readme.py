"""Rewrite the README results section from docs/results.json. Run after `bench report`."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPS = {"claimdesk": "ClaimDesk 98 (synthetic claims app, built here)",
        "openmrs": "OpenMRS 2.12 (real hospital record system, Docker)",
        "idempiere": "iDempiere (real ERP, Docker)"}
START, END = "<!-- RESULTS:START -->", "<!-- RESULTS:END -->"


def pct(x):
    return "n/a" if x is None else f"{x * 100:.1f}%"


def block(m: dict) -> str:
    L = ["## Results (scripted agent, not a language model)", "",
         "A **scripted fault-injecting agent** drives each app: it follows a golden click path and, on a fixed schedule,",
         "stops midway, types a wrong value, skips the final save or claims done early. The same fault hits every arm.",
         "Arm B is the baseline with no Savepoint, S is Savepoint with atomic rollback, R adds retry from the last good",
         "checkpoint. These numbers show what the runtime does with a known failure mix. **They say nothing about how",
         "reliable any model is.**", ""]
    total = 0
    for app, am in m["by_app"].items():
        n = sum(x["n"] for x in am["arms"].values())
        total += n
        L += [f"### {APPS.get(app, app)}: {n} runs", "",
              "| Arm | N | Valid success | Atomicity (Wilson 95%) | False done (IS) | Dirty fail (IF) |", "|---|---|---|---|---|---|"]
        for a, x in am["arms"].items():
            lo, hi = x["atomicity_ci95"]
            L.append(f"| {a} | {x['n']} | {pct(x['valid_success'])} | {pct(x['atomicity'])} ({pct(lo)} to {pct(hi)}) "
                     f"| {x['IS']} | {x['IF']} |")
        c, f = am["catch"], am["fidelity"]
        L += ["", f"False `done` claims caught in arm S: {c['caught']} of {c['false_claims']} "
                  f"({pct(c['catch_rate'])}); true claims flagged: {c['false_alarms']} of {c['true_claims']}. "
                  f"Restores exact: {f['exact']} of {f['restores']}. Checkpoint p95 {am['timings']['checkpoint_p95_ms']} ms, "
                  f"restore p95 {am['timings']['restore_p95_ms']} ms.", ""]
    L += [f"{total} runs in total. Full tables, pass^k and sample sizes: [docs/results.md](docs/results.md). "
          "Acceptance status per check: [docs/validation.md](docs/validation.md).", ""]
    return "\n".join(L)


def main():
    m = json.loads((ROOT / "docs" / "results.json").read_text(encoding="utf-8"))
    p = ROOT / "README.md"
    s = p.read_text(encoding="utf-8")
    new = f"{START}\n{block(m)}\n{END}"
    if START in s:
        a, b = s.index(START), s.index(END) + len(END)
        s = s[:a] + new + s[b:]
    else:
        a = s.index("## Results so far")
        b = s.index("## Quick start")
        s = s[:a] + new + "\n\n" + s[b:]
    p.write_text(s, encoding="utf-8")
    print("README updated")


if __name__ == "__main__":
    main()
