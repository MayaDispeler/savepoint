"""Contract YAML loading and validation (FR13). Errors carry code, path and message."""
import re
from dataclasses import dataclass, field

import yaml

OPERATORS = {"equals", "not_equals", "gte", "lte", "between", "in", "matches", "empty", "not_empty",
             "row_count"}
ID_RE = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")
FORBIDDEN_SQL = re.compile(r"\b(insert|update|delete|drop|alter|create|replace|attach|pragma|vacuum)\b",
                           re.IGNORECASE)


@dataclass
class ContractError:
    code: str
    path: str
    message: str


class ContractInvalid(Exception):
    def __init__(self, errors: list[ContractError]):
        super().__init__("; ".join(f"{e.code} at {e.path}: {e.message}" for e in errors))
        self.errors = errors


@dataclass
class Check:
    id: str
    sql: str
    expect: dict


@dataclass
class Contract:
    id: str
    app: str
    title: str
    fixture: str
    params: dict
    instruction: str
    invariants: list[Check]
    goal: list[Check]
    unchanged: list[str]
    allowed: list[dict]
    screen: list[dict] = field(default_factory=list)
    lookup_only: bool = False
    sha256: str = ""

    def text(self) -> str:
        return self.instruction.format(**self.params).strip()


def _check_sql(sql, path, errs):
    if not isinstance(sql, str) or not sql.strip():
        errs.append(ContractError("SQL_MISSING", path, "sql must be a non-empty string"))
        return
    body = sql.strip().rstrip(";")
    if ";" in body or not body.lower().startswith("select") or FORBIDDEN_SQL.search(body):
        errs.append(ContractError("SQL_NOT_READONLY", path, "sql must be exactly one read-only SELECT"))


def _check_expect(exp, path, errs):
    if not isinstance(exp, dict) or len(exp) != 1:
        errs.append(ContractError("EXPECT_OPERATOR", path, "expect needs exactly one operator"))
    elif next(iter(exp)) not in OPERATORS:
        errs.append(ContractError("EXPECT_UNKNOWN_OPERATOR", path, f"unknown operator {next(iter(exp))!r}"))


def _checks(items, path, errs) -> list[Check]:
    out = []
    for i, it in enumerate(items or []):
        p = f"{path}[{i}]"
        if not isinstance(it, dict) or "id" not in it:
            errs.append(ContractError("CHECK_MALFORMED", p, "check needs id, sql, expect"))
            continue
        _check_sql(it.get("sql"), f"{p}.sql", errs)
        _check_expect(it.get("expect"), f"{p}.expect", errs)
        out.append(Check(str(it["id"]), str(it.get("sql", "")), it.get("expect") or {}))
    return out


def parse(text: str, known_tables: set[str] | None = None) -> Contract:
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ContractInvalid([ContractError("YAML_ERROR", "$", str(e).splitlines()[0])]) from e
    errs: list[ContractError] = []
    if not isinstance(raw, dict):
        raise ContractInvalid([ContractError("YAML_ERROR", "$", "document must be a mapping")])
    for key in ("id", "app", "title", "fixture", "instruction"):
        if not isinstance(raw.get(key), str) or not raw[key].strip():
            errs.append(ContractError("MISSING_FIELD", key, f"{key} is required"))
    if isinstance(raw.get("id"), str) and not ID_RE.match(raw["id"]):
        errs.append(ContractError("ID_FORMAT", "id", "id must match ^[a-z0-9_]+\\.[a-z0-9_]+$"))
    params = raw.get("params") or {}
    if not isinstance(params, dict):
        errs.append(ContractError("PARAMS_INVALID", "params", "params must be a mapping"))
        params = {}
    instruction = raw.get("instruction") or ""
    for name in re.findall(r"{(\w+)(?::[^}]*)?}", instruction):
        if name not in params:
            errs.append(ContractError("PARAM_UNDEFINED", "instruction", f"parameter {{{name}}} not in params"))
    invariants = _checks(raw.get("invariants"), "invariants", errs)
    goal = _checks(raw.get("goal"), "goal", errs)
    if not goal:
        errs.append(ContractError("MISSING_GOAL", "goal", "at least one goal check is required"))
    frame = raw.get("frame") or {}
    unchanged = list(frame.get("unchanged") or [])
    allowed = list(frame.get("allowed") or [])
    for i, rule in enumerate(allowed):
        t = rule.get("table") if isinstance(rule, dict) else None
        if t not in unchanged:
            errs.append(ContractError("FRAME_TABLE_NOT_UNCHANGED", f"frame.allowed[{i}].table",
                                      f"table {t!r} is not listed in frame.unchanged"))
    if known_tables is not None:
        for i, t in enumerate(unchanged):
            if t not in known_tables:
                errs.append(ContractError("UNKNOWN_TABLE", f"frame.unchanged[{i}]", f"unknown table {t!r}"))
    screen = raw.get("screen") or []
    if len(screen) > 3:
        errs.append(ContractError("SCREEN_TOO_MANY", "screen", "at most 3 screen checks"))
    if errs:
        raise ContractInvalid(errs)
    import hashlib
    return Contract(raw["id"], raw["app"], raw["title"], raw["fixture"], params, instruction, invariants,
                    goal, unchanged, allowed, screen, bool(raw.get("lookup_only")),
                    hashlib.sha256(text.encode()).hexdigest())


def load(path: str, known_tables: set[str] | None = None) -> Contract:
    with open(path, encoding="utf-8") as f:
        return parse(f.read(), known_tables)
