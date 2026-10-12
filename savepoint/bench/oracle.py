"""Oracle classification (A5), independent of Savepoint validators (INV04).

This module imports nothing from savepoint.contracts or savepoint.runtime.
"""
import hashlib
import json

from savepoint.snapshot.digest import Digest, diff


def normalize(s0: Digest, final: Digest) -> dict:
    """Canonical state diff. Inserted rows match on their non-key, non-volatile columns."""
    d = diff(s0, final)
    added = {t: sorted(hashlib.blake2b(json.dumps(final[t][pk], sort_keys=True).encode(),
                                       digest_size=8).hexdigest() for pk in pks)
             for t, pks in d.added.items()}
    removed = {t: sorted(pks) for t, pks in d.removed.items()}
    changed = {t: {pk: {c: final[t][pk][c] for c in cols} for pk, cols in rows.items()}
               for t, rows in d.changed.items()}
    return {"added": added, "removed": removed, "changed": changed}


def is_empty(n: dict) -> bool:
    return not (n["added"] or n["removed"] or n["changed"])


def classify(reported_done: bool, final: Digest, s0: Digest, golden: dict) -> str:
    """VS / VF / IS / IF. `reported_done` is the system's report: the agent for arm B, Savepoint for S and R."""
    observed = normalize(s0, final)
    if reported_done:
        return "VS" if observed == golden else "IS"
    return "VF" if is_empty(observed) else "IF"


def claim_true(verify: Digest, s0: Digest, golden: dict) -> bool:
    """Is the agent's `done` claim true, judged on the digest taken just before goal checks?"""
    return normalize(s0, verify) == golden
