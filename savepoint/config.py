import os


def _flag(name: str, default: str) -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes"}


SANDBOX_ONLY = _flag("SANDBOX_ONLY", "true")
MODEL_BUDGET_USD = float(os.environ.get("MODEL_BUDGET_USD", "25"))
BENCH_MODEL = os.environ.get("BENCH_MODEL", "claude-haiku-5-5")
