"""Contract evaluation: invariants, goal and frame checks (FR14-FR16, A4). Never imports bench/oracle."""
import re
import sqlite3
import time
from dataclasses import dataclass

from savepoint.contracts.schema import Contract
from savepoint.snapshot.digest import Digest, diff

QUERY_TIMEOUT_S = 2.0


@dataclass
class CheckResult:
    phase: str
    check_id: str
    passed: bool
    observed: object
    expected: object
    took_ms: int = 0


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


def apply_operator(op: str, arg, rows: list[tuple]) -> tuple[bool, object]:
    """Apply one operator to a result set. Scalar operators read the first cell of the first row."""
    first = rows[0][0] if rows and rows[0] else None
    if op == "row_count":
        return len(rows) == arg, len(rows)
    if op == "empty":
        ok = (not rows) or first in (None, "")
        return ok == bool(arg), first
    if op == "not_empty":
        ok = bool(rows) and first not in (None, "")
        return ok == bool(arg), first
    if op == "equals":
        a, b = _num(first), _num(arg)
        return (abs(a - b) < 1e-9 if isinstance(a, float) and isinstance(b, float) else a == b), first
    if op == "not_equals":
        a, b = _num(first), _num(arg)
        return (not abs(a - b) < 1e-9 if isinstance(a, float) and isinstance(b, float) else a != b), first
    if op == "gte":
        return first is not None and _num(first) >= _num(arg), first
    if op == "lte":
        return first is not None and _num(first) <= _num(arg), first
    if op == "between":
        lo, hi = arg
        return first is not None and _num(lo) <= _num(first) <= _num(hi), first
    if op == "in":
        return first in arg, first
    if op == "matches":
        return first is not None and re.search(str(arg), str(first)) is not None, first
    raise ValueError(f"unknown operator {op}")


def run_sql(db_path: str, sql: str, params: dict) -> list[tuple]:
    """Run one SELECT in a read-only connection with a 2 s timeout."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    deadline = time.monotonic() + QUERY_TIMEOUT_S
    con.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10000)
    try:
        names = set(re.findall(r":(\w+)", sql))
        return con.execute(sql, {k: v for k, v in params.items() if k in names}).fetchall()
    finally:
        con.close()


def _eval_checks(phase, checks, adapter, params) -> list[CheckResult]:
    out = []
    for c in checks:
        t0 = time.monotonic()
        op, arg = next(iter(c.expect.items()))
        try:
            ok, observed = apply_operator(op, arg, adapter.select(c.sql, params))
        except Exception as e:  # noqa: BLE001 - a failing check query is a failed check, not a crash
            ok, observed = False, f"error: {e}"
        out.append(CheckResult(phase, c.id, bool(ok), observed, c.expect, int((time.monotonic() - t0) * 1000)))
    return out


def frame_violations(contract: Contract, s0: Digest, now: Digest, adapter, s0_db: str | None) -> list[str]:
    """A4: remove every change the contract allows; anything left is an unexpected change."""
    d = diff({t: s0.get(t, {}) for t in contract.unchanged}, {t: now.get(t, {}) for t in contract.unchanged})
    violations = []
    for table in contract.unchanged:
        rules = [r for r in contract.allowed if r["table"] == table]

        def selected(rule, snapshot, table=table):
            where = rule.get("where")
            if not where:
                return set()
            pk = adapter.pk_sql(table)
            rows = adapter.select(f"SELECT {pk} FROM {table} WHERE {where}", contract.params, snapshot=snapshot)
            return {str(r[0]) for r in rows}

        for pk, cols in sorted(d.changed.get(table, {}).items()):
            ok = False
            for r in rules:
                if (pk in selected(r, s0_db) | selected(r, None)) and set(cols) <= set(r.get("columns", [])):
                    ok = True
            if not ok:
                violations.append(f"unexpected change {table}[{pk}].{','.join(cols)}")
        n_added = len(d.added.get(table, []))
        if n_added > sum(r.get("insert", 0) for r in rules):
            violations.append(f"unexpected insert {table}: {n_added}")
        n_removed = len(d.removed.get(table, []))
        if n_removed > sum(r.get("delete", 0) for r in rules):
            violations.append(f"unexpected delete {table}: {n_removed}")
    return violations


def check(contract: Contract, phase: str, adapter, s0: Digest | None = None,
          s0_db: str | None = None) -> list[CheckResult]:
    if phase == "invariant":
        return _eval_checks("invariant", contract.invariants, adapter, contract.params)
    if phase == "goal":
        return _eval_checks("goal", contract.goal, adapter, contract.params)
    if phase == "frame":
        t0 = time.monotonic()
        v = frame_violations(contract, s0, adapter.digest(), adapter, s0_db)
        return [CheckResult("frame", "frame", not v, v, "no unexpected change",
                            int((time.monotonic() - t0) * 1000))]
    raise ValueError(phase)
