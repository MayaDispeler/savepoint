"""Benchmark metrics (FR22): atomicity, valid success, pass^k, catch rate, fidelity, overhead."""
from collections import defaultdict

from savepoint.bench.passk import mean_pass_hat_k, wilson


def _p95(xs):
    if not xs:
        return None
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(0.95 * len(xs) + 0.9999) - 1)]


def arm_metrics(runs: list[dict], max_k: int = 10) -> dict:
    n = len(runs)
    if not n:
        return {"n": 0}
    count = defaultdict(int)
    for r in runs:
        count[r["oracle"]] += 1
    lo, hi = wilson(count["VS"] + count["VF"], n)
    per_wf: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in runs:
        per_wf[r["workflow_id"]][1] += 1
        per_wf[r["workflow_id"]][0] += r["oracle"] == "VS"
    cn = [(c, t) for c, t in per_wf.values()]
    ks = range(1, min(max_k, min(t for _, t in cn)) + 1)
    return {
        "n": n, "VS": count["VS"], "VF": count["VF"], "IS": count["IS"], "IF": count["IF"],
        "atomicity": (count["VS"] + count["VF"]) / n, "atomicity_ci95": [lo, hi],
        "valid_success": count["VS"] / n, "invalid_success_rate": count["IS"] / n,
        "unsafe_side_effect_rate": count["IF"] / n,
        "pass_hat_k": {str(k): mean_pass_hat_k(cn, k) for k in ks},
        "workflows": len(cn), "trials_per_workflow": min(t for _, t in cn),
    }


def catch_rates(s_runs: list[dict]) -> dict:
    """Arm S only (single attempt). claim_true is judged by the oracle on the pre-validation digest."""
    judged = [r for r in s_runs if r.get("claim_true") is not None]
    false_claims = [r for r in judged if not r["claim_true"]]
    true_claims = [r for r in judged if r["claim_true"]]
    caught = sum(1 for r in false_claims if r["false_completion"])
    alarms = sum(1 for r in true_claims if r["false_completion"])
    return {"false_claims": len(false_claims), "caught": caught,
            "catch_rate": caught / len(false_claims) if false_claims else None,
            "true_claims": len(true_claims), "false_alarms": alarms,
            "false_alarm_rate": alarms / len(true_claims) if true_claims else None}


def compute(runs: list[dict], rollbacks: list[dict], checkpoints: list[dict]) -> dict:
    by_arm = defaultdict(list)
    for r in runs:
        by_arm[r["arm"]].append(r)
    out = {"arms": {a: arm_metrics(rs) for a, rs in sorted(by_arm.items())}}
    out["catch"] = catch_rates(by_arm.get("S", []))
    out["fidelity"] = {"restores": len(rollbacks), "exact": sum(1 for r in rollbacks if r["exact"]),
                       "exact_rate": (sum(1 for r in rollbacks if r["exact"]) / len(rollbacks))
                       if rollbacks else None}
    sr = [r for r in runs if r["arm"] in ("S", "R")]
    walls = sum(r["wall_ms"] for r in sr) or 1
    b_wall = [r["wall_ms"] for r in by_arm.get("B", [])]
    s_wall = [r["wall_ms"] for r in by_arm.get("S", [])]
    out["overhead"] = {
        "checkpoint_restore_share_of_wall": sum(r["checkpoint_ms"] for r in sr) / walls,
        "mean_wall_ms_B": sum(b_wall) / len(b_wall) if b_wall else None,
        "mean_wall_ms_S": sum(s_wall) / len(s_wall) if s_wall else None}
    out["timings"] = {"checkpoint_p95_ms": _p95([c["took_ms"] for c in checkpoints]),
                      "restore_p95_ms": _p95([r["restore_ms"] for r in rollbacks]),
                      "checkpoints": len(checkpoints)}
    out["quarantined"] = sum(1 for r in runs if r.get("quarantined"))
    return out
