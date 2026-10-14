# Validation status (PRD acceptance V01 to V34)

Pass = verified by a test or a measured run in this repository. Partial = verified on ClaimDesk 98 only or with a
documented adaptation. Blocked = cannot run on the build machine yet; the reason is given.

| ID | Status | Evidence or reason |
|---|---|---|
| V01 | Partial | ClaimDesk starts in under 2 s. OpenMRS and iDempiere blocked: Docker is not installed. |
| V02 | Pass | `test_adapter.py::test_two_resets_same_digest` |
| V03 | Pass | `test_claimdesk.py`: modal, tab trap, spinner delay, silent validation, session timeout, two-page grid |
| V04 | Pass | `test_runtime.py::test_arm_b_golden_is_valid_success` |
| V05 | Pass | `test_stop_midway_rolls_back` (arm S: rolled back, VF, exact; arm B: IF) |
| V06 | Pass | `test_bench.py::test_claude_loop_recorded_responses` (no network) |
| V07 | Simulated (by choice) | No real model call and no spend. `agent/simulated.py` replays a recorded 5-step computer-tool transcript through the real `ClaudeAgent` loop on a live ClaimDesk (`test_simulated_live.py`: click by pixel, type, Save note detected as risky, committed, oracle VS, A8 cost accounted). A real run still needs `ANTHROPIC_API_KEY`, and the toolset type name is unverified against the live API. |
| V08 | Pass | budget guard test and API 402 test; zero model calls |
| V09 | Pass | S0 checkpoint at step 0 before step 1 |
| V10 | Pass | `test_risky_checkpoint_dedupe`: S0 plus one checkpoint per committing click |
| V11 | Partial | 100 scripted restores exact, broken restore caught and quarantined, on SQLite only. Postgres and MySQL blocked (Docker). |
| V12 | Pass | 8 broken contracts return 8 codes with paths |
| V13 | Pass | 10 operators x pass and fail = 20 of 20 |
| V14 | Pass (adapted) | The UI rejects negative amounts, so the invariant fault is a slipped decimal (125000.00 against a cap of 100000). Arm S restores S0. Arm R restores the checkpoint, appends the reason and retries. |
| V15 | Pass | skipped save in arm S: rolled back, false completion recorded, oracle VF, `claim_true` false |
| V16 | Pass | frame check names `claims[CL-10431].adjuster_id` while the goal checks still pass |
| V17 | Pass | advisory "no" stays committed; required "no" rolls back (recorded vision answers) |
| V18 | Pass | arm R `retried_committed`, oracle VS |
| V19 | Pass (adapted) | runner "killed" after 4 of 10 runs, resumed to 10 rows, no duplicates (the PRD uses 7 of 20) |
| V20 | Pass | four oracle examples VS, IS, VF, IF |
| V21 | Pass | pass^k 0.767, 0.615, 0.409, 0.333; Wilson 0.931 to 0.977; 92.5% and 2.5% |
| V22 | Pass | import-lint test |
| V23 | Blocked | OpenMRS needs Docker. Contract drafted in `workflows/openmrs/`; see `legacyworld-port.md`. |
| V24 | Partial | Bundle 0.63 MB (limit 20 MB). Screenshots are blurred at capture; the pixel-variance check on blurred regions was not written. |
| V25 | Pass | all 300 tiles measure the same size at both viewports; each has an icon and a word. Contrast not measured by tool. |
| V26 | Pass | featured rollback shows checkpoint diamonds, the failing check in red and the before/after slider with the diff percentage |
| V27 | Pass | adapter test and API 403 |
| V28 | Pass | write-guard test: `redact.py` is the only image writer |
| V29 | Pass | chart data equals `results.json` (checked in `scripts/check_console.py`) |
| V30 | Pass | hosted page makes requests to its own origin only; no inner scroll areas at 1920x911 and 1366x768; 40 Tab presses reach only buttons. `app.js` is 5 KB gzipped. |
| V31 | Partial | 60 restores in the benchmark plus 100 in the test, all exact. Checkpoint p95 47 ms, restore p95 94 ms. The PRD asks for at least 300 restores over three apps. |
| V32 | Pass | `traces.jsonl` has run, step, checkpoint and restore spans |
| V33 | Pass | coverage 89% on runtime, contracts and snapshot (limit 85%); a test fixture fails any real Anthropic client construction |
| V34 | Pass | the 300-run suite ran twice into two ledgers; the outcome-table hash was identical (`042b29468902d227`) |

## Known deviations from the PRD

- Ledger is SQLite (user decision: local first). The schema runs on Postgres, including Supabase, by setting `LEDGER_URL`. No Alembic migration; tables are created from the SQLAlchemy metadata.
- The console is plain HTML, CSS and JavaScript (no React or Vite build). It has no network dependency and no build step.
- Ten ClaimDesk workflows, not thirty. The agent is scripted; no model results exist.
- Hosted at `savepoint-demo.ksvhari007.workers.dev` and as a Hugging Face static Space. The custom route on iamsrihari.com is not set up.
