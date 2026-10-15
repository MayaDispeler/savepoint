"""Merge one app's ledger into the main ledger. Usage: merge_ledgers.py <source-url> [<target-url>]"""
import sys

from sqlalchemy import insert, select

from savepoint.ledger.db import (
    Ledger,
    checkpoints,
    rollbacks,
    runs,
    steps,
    validations,
    workflows,
)


def merge(src_url: str, dst_url: str = "sqlite:///ledger.db") -> dict:
    src, dst = Ledger(src_url), Ledger(dst_url)
    counts = {}
    with dst.engine.begin() as c:
        have = {r[0] for r in c.execute(select(workflows.c.id))}
        have_runs = {r[0] for r in c.execute(select(runs.c.id))}
        for table in (workflows, runs, steps, checkpoints, validations, rollbacks):
            rows = src.rows(table)
            if table is workflows:
                rows = [r for r in rows if r["id"] not in have]
            elif table is runs:
                rows = [r for r in rows if r["id"] not in have_runs]
            else:
                rows = [r for r in rows if r["run_id"] not in have_runs]
            if table is validations:
                rows = [{k: v for k, v in r.items() if k != "pk"} for r in rows]
            if rows:
                c.execute(insert(table), rows)
            counts[table.name] = len(rows)
    return counts


if __name__ == "__main__":
    print(merge(*sys.argv[1:3]))
