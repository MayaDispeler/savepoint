# Savepoint results

Agent: **scripted fault-injecting agent (not a language model)**. Faults are injected on a fixed schedule (trials 7 to 10 of each workflow), paired across arms. These numbers show what the runtime does with a known failure mix. They are not a measurement of any model's reliability.

## Outcomes by arm

| Arm | N | Valid success | Atomicity (Wilson 95%) | Invalid success | Unsafe side effect | VS | VF | IS | IF |
|---|---|---|---|---|---|---|---|---|---|
| B baseline (no Savepoint) | 150 | 66.7% | 68.0% (60.2% to 74.9%) | 30.0% | 2.0% | 100 | 2 | 45 | 3 |
| R savepoint_retry | 150 | 96.7% | 100.0% (97.5% to 100.0%) | 0.0% | 0.0% | 145 | 5 | 0 | 0 |
| S atomic | 150 | 66.7% | 100.0% (97.5% to 100.0%) | 0.0% | 0.0% | 100 | 50 | 0 | 0 |

Atomicity = (VS + VF) / N: the run either fully succeeded or left the state untouched. IS = said done, state wrong. IF = said not done, state partly changed.

## pass^k (mean over workflows)

| Arm | k=1 | k=2 | k=3 | k=4 | k=5 | k=6 | k=7 | k=8 | k=9 | k=10 |
|---|---|---|---|---|---|---|---|---|---|---|
| B | 0.650 | 0.405 | 0.247 | 0.161 | 0.129 | nan | nan | nan | nan | nan |
| R | 0.965 | 0.930 | 0.895 | 0.860 | 0.825 | nan | nan | nan | nan | nan |
| S | 0.650 | 0.405 | 0.247 | 0.161 | 0.129 | nan | nan | nan | nan | nan |

## By app: claimdesk

| Arm | N | Valid success | Atomicity (Wilson 95%) | VS | VF | IS | IF | pass^1 | pass^5 |
|---|---|---|---|---|---|---|---|---|---|
| B baseline (no Savepoint) | 100 | 70.0% | 70.0% (60.4% to 78.1%) | 70 | 0 | 27 | 3 | 0.700 | 0.157 |
| R savepoint_retry | 100 | 97.0% | 100.0% (96.3% to 100.0%) | 97 | 3 | 0 | 0 | 0.970 | 0.850 |
| S atomic | 100 | 70.0% | 100.0% (96.3% to 100.0%) | 70 | 30 | 0 | 0 | 0.700 | 0.157 |

Arm S catch rate 100.0% (25 of 25); false alarms 0.0% (0 of 70); restores exact 60 of 60.

## By app: openmrs

| Arm | N | Valid success | Atomicity (Wilson 95%) | VS | VF | IS | IF | pass^1 | pass^5 |
|---|---|---|---|---|---|---|---|---|---|
| B baseline (no Savepoint) | 50 | 60.0% | 64.0% (50.1% to 75.9%) | 30 | 2 | 18 | 0 | 0.600 | 0.100 |
| R savepoint_retry | 50 | 96.0% | 100.0% (92.9% to 100.0%) | 48 | 2 | 0 | 0 | 0.960 | 0.800 |
| S atomic | 50 | 60.0% | 100.0% (92.9% to 100.0%) | 30 | 20 | 0 | 0 | 0.600 | 0.100 |

Arm S catch rate 100.0% (18 of 18); false alarms 0.0% (0 of 30); restores exact 40 of 40.

## False completions (arm S, single attempt, all apps)

- Catch rate: 100.0% (43 of 43 false `done` claims caught)
- False-alarm rate: 0.0% (0 of 100 true claims flagged)

## Restore fidelity and cost

- Restores: 100; exact: 100 (100.0%)
- Quarantined runs: 0
- Checkpoint p95: 64 ms over 541 checkpoints; restore p95: 525 ms
- Checkpoint + restore share of wall time (arms S and R): 5.1%

Sample sizes: arm B N=150 (20 workflows x 5 trials), arm R N=150 (20 workflows x 5 trials), arm S N=150 (20 workflows x 5 trials)
