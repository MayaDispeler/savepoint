# Validation status (PRD acceptance V01 to V34)

Pass = verified by a test or a measured run in this repository. Adapted = verified with a documented change to the
PRD wording. Simulated = no real model call, by the owner's choice. Real apps ran in Docker on a free GitHub
Codespace (OpenMRS 2.12, iDempiere); the third app, ClaimDesk 98, is the synthetic clone built here.

| ID | Status | Evidence or note |
|---|---|---|
| V01 | Pass | ClaimDesk starts in under 2 s. OpenMRS and iDempiere start from `docker compose` / `docker start` in about 2 to 3 minutes (limit 5). |
| V02 | Pass | `test_adapter.py::test_two_resets_same_digest` (SQLite). On the real apps every run begins with a reset and the digest compare after each restore was exact (below). |
| V03 | Pass | `test_claimdesk.py`: modal, tab trap, spinner delay, silent validation, session timeout, two-page grid |
| V04 | Pass | `test_runtime.py::test_arm_b_golden_is_valid_success`; every golden path also passes goal and frame on OpenMRS (10 of 10) and iDempiere (10 of 10) |
| V05 | Pass | `test_stop_midway_rolls_back` (arm S: rolled back, VF, exact; arm B: IF) |
| V06 | Pass | recorded-response test of the Claude loop, no network |
| V07 | Simulated | No real model call and no spend. `agent/simulated.py` replays a recorded 5-step computer-tool transcript through the real `ClaudeAgent` loop on a live ClaimDesk. A real run needs `ANTHROPIC_API_KEY`, and the toolset type name is unverified against the live API. |
| V08 | Pass | budget guard test and API 402 test; zero model calls |
| V09 | Pass | S0 checkpoint at step 0 before step 1 |
| V10 | Pass | `test_risky_checkpoint_dedupe` |
| V11 | Pass | 100 scripted restores exact on SQLite; broken restore caught and quarantined. In the benchmark 60 (ClaimDesk), 40 (OpenMRS, MySQL) and 63 (iDempiere, PostgreSQL) digest-compared restores, all exact, 0 quarantined. |
| V12 | Pass | 8 broken contracts return 8 codes with paths |
| V13 | Pass | 10 operators x pass and fail = 20 of 20 |
| V14 | Adapted | The ClaimDesk UI rejects negative amounts, so the invariant fault is a slipped decimal (125000.00 against a cap of 100000). |
| V15 | Pass | skipped save in arm S: rolled back, false completion recorded, oracle VF, `claim_true` false |
| V16 | Pass | frame check names the unexpected change while the goal checks still pass |
| V17 | Pass | advisory "no" stays committed; required "no" rolls back (recorded vision answers) |
| V18 | Pass | arm R `retried_committed`, oracle VS |
| V19 | Adapted | runner "killed" after 4 of 10 runs, resumed to 10 rows, no duplicates (PRD: 7 of 20). The iDempiere benchmark also crashed once (see below) and resumed without duplicates. |
| V20 | Pass | four oracle examples VS, IS, VF, IF |
| V21 | Pass | pass^k 0.767, 0.615, 0.409, 0.333; Wilson 0.931 to 0.977; 92.5% and 2.5% |
| V22 | Pass | import-lint test |
| V23 | Pass (adapted) | An own-words contract for the OpenMRS "onboard patient" task shape ran in arms B, S, R, 5 trials each: `docs/legacyworld-port.md`. Nothing copied from the benchmark (licence OD07 open). |
| V24 | Adapted | Bundle 1.4 MB (limit 20 MB). Screenshots are blurred at capture; the pixel-variance check on blurred regions was not written (the real apps show only synthetic data, so no redaction regions were needed). |
| V25 | Pass | all 600 tiles measure the same size at both viewports; each has an icon and a word |
| V26 | Pass | featured rollbacks show checkpoint diamonds, failing checks in red and the before/after slider with the diff percentage, for all three apps |
| V27 | Pass | adapter test and API 403 |
| V28 | Pass | write-guard test: `redact.py` is the only image writer |
| V29 | Pass | chart data equals `results.json` for every app, arm and k (checked in `scripts/check_console.py`) |
| V30 | Pass | hosted page makes requests to its own origin only; no inner scroll areas at 1920x911 and 1366x768; Tab reaches only buttons. `app.js` is 5.8 KB and the stylesheet 1.7 KB gzipped. |
| V31 | Partial | 263 digest-compared restores (163 in the benchmark plus 100 in the test), all exact; the PRD asks for at least 300, which was not reached. Checkpoint p95 47 / 71 / 131 ms and restore p95 94 / 529 / 610 ms (ClaimDesk / OpenMRS / iDempiere) against limits of 5 s and 60 s. |
| V32 | Pass | `traces.jsonl` has run, step, checkpoint and restore spans |
| V33 | Pass | coverage 91% on runtime, contracts and snapshot (limit 85%); a test fixture fails any real Anthropic client construction |
| V34 | Pass | the 300-run ClaimDesk suite ran twice into two ledgers; the outcome-table hash was identical |

## What the real apps taught us (kept, not hidden)

- **Restores bypass the app's own cache.** After a database-level restore OpenMRS still showed old data from its Hibernate cache, so patients looked voided. We turned the caches off; restores are only trusted with that setting.
- **Generated values must be excluded from the state comparison.** OpenMRS patient identifiers and iDempiere ids come from sequences. iDempiere's restore rewinds only the partner and product counters; rewinding all of them made the app reuse ids its log tables already held and broke login.
- **A UI failure while retrying crashed the benchmark runner.** Found on iDempiere run 96 of 150: a Playwright timeout in the retry path propagated instead of being recorded. Fixed (an error outcome and a rollback) with a regression test; the run resumed from where it stopped.
- **iDempiere's screens are slow and flaky.** 15 of its 150 runs ended with agent status `error` (a UI timeout) and were rolled back cleanly. That is why arm R adds only one valid success over arm S there (54% against 52%), where on OpenMRS it adds 18 (96% against 60%).
- **Contract gaps show up on real data.** The first OpenMRS frame check missed a column Hibernate also writes (`allergy_status`), and iDempiere creates one accounting row per accounting schema. Contracts were widened only for changes the real app is documented to make.

## Known deviations from the PRD

- The ledger is SQLite (owner decision: local first). The schema runs on Postgres, including Supabase, by setting `LEDGER_URL`. No Alembic migration; tables come from the SQLAlchemy metadata.
- The console is plain HTML, CSS and JavaScript (no React or Vite build). It has no network dependency and no build step.
- Snapshots cover the monitored tables, not whole database dumps (`pg_dump` / `mysqldump`): rows are read in one consistent read and re-inserted on restore, then proven exact by the digest compare. Changes outside the monitored tables are neither digested nor restored.
- 30 workflows (10 per app), with 10 trials on ClaimDesk and 5 on each real app because those apps are slow. The agent is scripted; no model results exist.
- Hosted at `savepoint-demo.ksvhari007.workers.dev` and as a Hugging Face static Space. The custom route on iamsrihari.com is not set up.
