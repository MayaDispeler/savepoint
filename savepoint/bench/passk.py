"""pass^k (A6) and Wilson interval (A7)."""
from math import comb, sqrt


def pass_hat_k(successes: int, n: int, k: int) -> float:
    if successes < k:
        return 0.0
    return comb(successes, k) / comb(n, k)


def mean_pass_hat_k(per_workflow: list[tuple[int, int]], k: int) -> float:
    return sum(pass_hat_k(c, n, k) for c, n in per_workflow) / len(per_workflow)


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return center - half, center + half
