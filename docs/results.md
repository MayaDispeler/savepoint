# Savepoint results

Agent: **scripted fault-injecting agent (not a language model)**. Faults are injected on a fixed schedule (trials 7 to 10 of each workflow), paired across arms. These numbers show what the runtime does with a known failure mix. They are not a measurement of any model's reliability.

## Outcomes by arm

| Arm | N | Valid success | Atomicity (Wilson 95%) | Invalid success | Unsafe side effect | VS | VF | IS | IF |
|---|---|---|---|---|---|---|---|---|---|
| B baseline (no Savepoint) | 100 | 70.0% | 70.0% (60.4% to 78.1%) | 27.0% | 3.0% | 70 | 0 | 27 | 3 |
| R savepoint_retry | 100 | 97.0% | 100.0% (96.3% to 100.0%) | 0.0% | 0.0% | 97 | 3 | 0 | 0 |
| S atomic | 100 | 70.0% | 100.0% (96.3% to 100.0%) | 0.0% | 0.0% | 70 | 30 | 0 | 0 |

Atomicity = (VS + VF) / N: the run either fully succeeded or left the state untouched. IS = said done, state wrong. IF = said not done, state partly changed.

## pass^k (mean over workflows)

| Arm | k=1 | k=2 | k=3 | k=4 | k=5 | k=6 | k=7 | k=8 | k=9 | k=10 |
|---|---|---|---|---|---|---|---|---|---|---|
| B | 0.700 | 0.480 | 0.325 | 0.221 | 0.157 | 0.121 | 0.105 | 0.100 | 0.100 | 0.100 |
| R | 0.970 | 0.940 | 0.910 | 0.880 | 0.850 | 0.820 | 0.790 | 0.760 | 0.730 | 0.700 |
| S | 0.700 | 0.480 | 0.325 | 0.221 | 0.157 | 0.121 | 0.105 | 0.100 | 0.100 | 0.100 |

## False completions (arm S, single attempt)

- Catch rate: 100.0% (25 of 25 false `done` claims caught)
- False-alarm rate: 0.0% (0 of 70 true claims flagged)

## Restore fidelity and cost

- Restores: 60; exact: 60 (100.0%)
- Quarantined runs: 0
- Checkpoint p95: 47 ms over 379 checkpoints; restore p95: 94 ms
- Checkpoint + restore share of wall time (arms S and R): 7.7%

Sample sizes: arm B N=100 (10 workflows x 10 trials), arm R N=100 (10 workflows x 10 trials), arm S N=100 (10 workflows x 10 trials)
