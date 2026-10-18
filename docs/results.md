# Savepoint results

Agent: **scripted fault-injecting agent (not a language model)**. Faults are injected on a fixed schedule (trials 7 to 10 of each workflow), paired across arms. These numbers show what the runtime does with a known failure mix. They are not a measurement of any model's reliability.

## Outcomes by arm

| Arm | N | Valid success | Atomicity (Wilson 95%) | Invalid success | Unsafe side effect | VS | VF | IS | IF |
|---|---|---|---|---|---|---|---|---|---|
| B baseline (no Savepoint) | 200 | 63.0% | 68.0% (61.2% to 74.1%) | 30.5% | 1.5% | 126 | 10 | 61 | 3 |
| R savepoint_retry | 200 | 86.0% | 100.0% (98.1% to 100.0%) | 0.0% | 0.0% | 172 | 28 | 0 | 0 |
| S atomic | 200 | 63.0% | 100.0% (98.1% to 100.0%) | 0.0% | 0.0% | 126 | 74 | 0 | 0 |

Atomicity = (VS + VF) / N: the run either fully succeeded or left the state untouched. IS = said done, state wrong. IF = said not done, state partly changed.

## pass^k (mean over workflows)

| Arm | k=1 | k=2 | k=3 | k=4 | k=5 | k=6 | k=7 | k=8 | k=9 | k=10 |
|---|---|---|---|---|---|---|---|---|---|---|
| B | 0.607 | 0.363 | 0.232 | 0.174 | 0.152 | nan | nan | nan | nan | nan |
| R | 0.823 | 0.720 | 0.667 | 0.640 | 0.617 | nan | nan | nan | nan | nan |
| S | 0.607 | 0.363 | 0.232 | 0.174 | 0.152 | nan | nan | nan | nan | nan |

## By app: claimdesk

| Arm | N | Valid success | Atomicity (Wilson 95%) | VS | VF | IS | IF | pass^1 | pass^5 |
|---|---|---|---|---|---|---|---|---|---|
| B baseline (no Savepoint) | 100 | 70.0% | 70.0% (60.4% to 78.1%) | 70 | 0 | 27 | 3 | 0.700 | 0.157 |
| R savepoint_retry | 100 | 97.0% | 100.0% (96.3% to 100.0%) | 97 | 3 | 0 | 0 | 0.970 | 0.850 |
| S atomic | 100 | 70.0% | 100.0% (96.3% to 100.0%) | 70 | 30 | 0 | 0 | 0.700 | 0.157 |

Arm S catch rate 100.0% (25 of 25); false alarms 0.0% (0 of 70); restores exact 60 of 60.

## By app: idempiere

| Arm | N | Valid success | Atomicity (Wilson 95%) | VS | VF | IS | IF | pass^1 | pass^5 |
|---|---|---|---|---|---|---|---|---|---|
| B baseline (no Savepoint) | 50 | 52.0% | 68.0% (54.2% to 79.2%) | 26 | 8 | 16 | 0 | 0.520 | 0.200 |
| R savepoint_retry | 50 | 54.0% | 100.0% (92.9% to 100.0%) | 27 | 23 | 0 | 0 | 0.540 | 0.200 |
| S atomic | 50 | 52.0% | 100.0% (92.9% to 100.0%) | 26 | 24 | 0 | 0 | 0.520 | 0.200 |

Arm S catch rate 100.0% (16 of 16); false alarms 0.0% (0 of 26); restores exact 63 of 63.

## By app: openmrs

| Arm | N | Valid success | Atomicity (Wilson 95%) | VS | VF | IS | IF | pass^1 | pass^5 |
|---|---|---|---|---|---|---|---|---|---|
| B baseline (no Savepoint) | 50 | 60.0% | 64.0% (50.1% to 75.9%) | 30 | 2 | 18 | 0 | 0.600 | 0.100 |
| R savepoint_retry | 50 | 96.0% | 100.0% (92.9% to 100.0%) | 48 | 2 | 0 | 0 | 0.960 | 0.800 |
| S atomic | 50 | 60.0% | 100.0% (92.9% to 100.0%) | 30 | 20 | 0 | 0 | 0.600 | 0.100 |

Arm S catch rate 100.0% (18 of 18); false alarms 0.0% (0 of 30); restores exact 40 of 40.

## False completions (arm S, single attempt, all apps)

- Catch rate: 100.0% (59 of 59 false `done` claims caught)
- False-alarm rate: 0.0% (0 of 126 true claims flagged)

## Restore fidelity and cost

- Restores: 163; exact: 163 (100.0%)
- Quarantined runs: 0
- Checkpoint p95: 114 ms over 769 checkpoints; restore p95: 568 ms
- Checkpoint + restore share of wall time (arms S and R): 3.6%

Sample sizes: arm B N=200 (30 workflows x 5 trials), arm R N=200 (30 workflows x 5 trials), arm S N=200 (30 workflows x 5 trials)
