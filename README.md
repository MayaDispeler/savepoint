# Savepoint

Checkpoint, verify and roll back AI agents working on legacy GUI applications.

Computer-use agents drive apps that have no API. When they fail halfway, or say "done" when the state is wrong,
nothing undoes the damage. Savepoint adds a transaction layer around the agent: it checkpoints before risky
steps, checks a goal contract when the agent says "done", rolls back on failure or false completion, and proves
each restore exact with a state diff.

![runs matrix](docs/screens/console-runs-1920.png)

## Results so far (scripted agent, not a language model)

The benchmark uses a **scripted fault-injecting agent** on a synthetic claims app (ClaimDesk 98): 10 workflows x
10 trials x 3 arms = 300 runs. Trials 7 to 10 of each workflow inject a known fault (stop midway, wrong value,
skipped save, claim done early), identically in every arm. These numbers show what the runtime does with a known
failure mix. **They say nothing about how reliable any model is.**

| Arm | Valid success | Atomicity (Wilson 95%) | False done | Dirty fail |
|---|---|---|---|---|
| B baseline | 70.0% | 70.0% (60.4 to 78.1) | 27 | 3 |
| S atomic | 70.0% | 100.0% (96.3 to 100.0) | 0 | 0 |
| R savepoint_retry | 97.0% | 100.0% (96.3 to 100.0) | 0 | 0 |

- 25 of 25 false `done` claims caught in arm S; 0 of 70 true claims flagged.
- 60 of 60 restores exact (database, files, browser session, URL). Checkpoint p95 47 ms, restore p95 94 ms.
- Full tables, pass^k and sample sizes: [docs/results.md](docs/results.md).

Not yet measured: a live Claude agent (no real model call was made; a simulated run through the real agent loop
is in `tests/integration/test_simulated_live.py`, and a real run needs `ANTHROPIC_API_KEY`), and the OpenMRS and iDempiere apps (need Docker). See [docs/validation.md](docs/validation.md).

## Quick start

```bash
uv sync && uv run playwright install chromium
uv run pytest -q                                   # 58 tests, no model calls
uv run python -m savepoint.bench.cli run           # 300 runs, resumable, ~10 min
uv run python -m savepoint.bench.cli report        # docs/results.md + results.json
make export && make console                        # open http://localhost:8080
```

## How rollback works

1. S0 is checkpointed before step 1: SQLite online backup, file-volume tar, browser storage state, URL.
2. Before any click on a risky control (Save, Delete, OK...) another checkpoint is taken, unless nothing changed since the last one.
3. After each state-changing step the contract invariants run.
4. When the agent reports `done`, goal and frame checks run. The frame check removes every change the contract allows; anything left is an unexpected change.
5. On failure the checkpoint is restored and the digest compared column by column. Any difference means `rollback_failed` and quarantine.

## Contract language

YAML with `invariants`, `goal` (SQL plus one of ten operators), `frame` (`unchanged` tables and an allowed-change
list) and up to three `screen` checks. See [docs/contracts.md](docs/contracts.md) and `workflows/claimdesk/`.

## Limits

Sandbox apps only (`SANDBOX_ONLY=true` refuses any other host). Snapshots work at the database and file level,
so apps with external side effects (email, payments) are out of scope. Data is synthetic (Faker seed 42).
The oracle and the validators are separate modules (an import-lint test enforces it).

## Prior work

Outcome classes and atomicity follow LegacyWorld (arXiv 2608.14131). Related: legacy-use, TClone, DART, AgentRewind.
Atomicity, rollback and pass^k are not novel here; the contribution is the combination and the exactness proof.

## Security

No real credentials or data. Screenshots are redacted before any write (`export/redact.py` is the only image
writer). No model call runs in tests or CI.

MIT licence.
