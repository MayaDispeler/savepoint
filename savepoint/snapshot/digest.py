"""State digest and fidelity compare (PRD Algorithm 2)."""
import hashlib
import unicodedata
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

Digest = dict[str, dict[str, dict[str, str]]]


def canonical(v) -> str:
    if v is None:
        return "\0"
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, float):
        return f"{v:.6f}"
    if isinstance(v, datetime):
        if v.tzinfo is None:
            v = v.replace(tzinfo=UTC)
        return v.astimezone(UTC).isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, str):
        return unicodedata.normalize("NFC", v)
    return str(v)


def h(v) -> str:
    return hashlib.blake2b(canonical(v).encode(), digest_size=8).hexdigest()


def row_digest(row: dict, volatile: list[str]) -> dict[str, str]:
    return {c: h(v) for c, v in row.items() if c not in volatile}


@dataclass
class DigestDiff:
    added: dict[str, list[str]]
    removed: dict[str, list[str]]
    changed: dict[str, dict[str, list[str]]]

    @property
    def rows_differ(self) -> int:
        return (
            sum(len(v) for v in self.added.values())
            + sum(len(v) for v in self.removed.values())
            + sum(len(v) for v in self.changed.values())
        )

    @property
    def exact(self) -> bool:
        return self.rows_differ == 0


def diff(a: Digest, b: Digest) -> DigestDiff:
    added: dict[str, list[str]] = {}
    removed: dict[str, list[str]] = {}
    changed: dict[str, dict[str, list[str]]] = {}
    for table in set(a) | set(b):
        ta, tb = a.get(table, {}), b.get(table, {})
        if x := sorted(set(tb) - set(ta)):
            added[table] = x
        if x := sorted(set(ta) - set(tb)):
            removed[table] = x
        for pk in set(ta) & set(tb):
            cols = sorted(c for c in set(ta[pk]) | set(tb[pk]) if ta[pk].get(c) != tb[pk].get(c))
            if cols:
                changed.setdefault(table, {})[pk] = cols
    return DigestDiff(added, removed, changed)
