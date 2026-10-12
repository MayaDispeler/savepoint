"""Budget guard (FR08, INV07, A8). Prices are the PRD A8 assumptions; check them before any live run."""
from dataclasses import dataclass

from savepoint import config

# USD per million tokens: input, output, cache read, cache write
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),
    "claude-opus-5-5": (4.00, 20.00, 0.20, 5.00),
}
EST_PREFIX, EST_PER_STEP_IN, EST_PER_STEP_OUT, EST_STEPS = 3000, 1600, 250, 12


class BudgetExceeded(Exception):
    code = "BUDGET_EXCEEDED"


def cost_usd(model: str, input_tokens: int, output_tokens: int, cache_read: int = 0, cache_write: int = 0) -> float:
    pi, po, pr, pw = PRICES[model]
    return (input_tokens * pi + output_tokens * po + cache_read * pr + cache_write * pw) / 1e6


def estimate_run_usd(model: str, steps: int = EST_STEPS) -> float:
    uncached = sum(EST_PREFIX + EST_PER_STEP_IN * i for i in range(1, steps + 1))
    return cost_usd(model, uncached, EST_PER_STEP_OUT * steps)


@dataclass
class BudgetGuard:
    ledger: object | None = None
    cap_usd: float = config.MODEL_BUDGET_USD
    spent: float = 0.0

    def current_spend(self) -> float:
        return self.ledger.spent_usd() if self.ledger is not None else self.spent

    def check_start(self, model: str):
        """Refuse a run when spent + 2 x estimate > cap, before any model call."""
        if self.current_spend() + 2 * estimate_run_usd(model) > self.cap_usd:
            raise BudgetExceeded(f"cap {self.cap_usd} would be exceeded")

    def record(self, run_id, model, usage) -> float:
        c = cost_usd(model, getattr(usage, "input_tokens", 0), getattr(usage, "output_tokens", 0),
                     getattr(usage, "cache_read_input_tokens", 0) or 0,
                     getattr(usage, "cache_creation_input_tokens", 0) or 0)
        if self.current_spend() + c > self.cap_usd:
            raise BudgetExceeded("recorded call would exceed the cap")
        self.spent += c
        if self.ledger is not None:
            self.ledger.add_spend(run_id, model, getattr(usage, "input_tokens", 0),
                                  getattr(usage, "output_tokens", 0),
                                  getattr(usage, "cache_read_input_tokens", 0) or 0, c)
        return c
