from pathlib import Path

import pytest
import yaml

from savepoint.contracts import evaluator, schema

WF = Path(__file__).resolve().parents[2] / "workflows" / "claimdesk"
BASE = (WF / "adjust_amount.yaml").read_text(encoding="utf-8")


def mutate(fn):
    doc = yaml.safe_load(BASE)
    fn(doc)
    return yaml.safe_dump(doc)


def codes(text, tables=None):
    with pytest.raises(schema.ContractInvalid) as e:
        schema.parse(text, tables)
    return {(x.code, x.path) for x in e.value.errors}


def test_all_ten_claimdesk_contracts_valid():
    files = sorted(WF.glob("*.yaml"))
    assert len(files) == 10
    for f in files:
        c = schema.load(str(f), {"claims", "claim_notes", "policies", "payees", "adjusters"})
        assert c.text()


def test_eight_broken_contracts_give_codes_with_paths():  # V12
    cases = {
        "bad id": (mutate(lambda d: d.update(id="Bad Id")), ("ID_FORMAT", "id")),
        "two operators": (mutate(lambda d: d["goal"][0].update(expect={"equals": 1, "gte": 1})),
                          ("EXPECT_OPERATOR", "goal[0].expect")),
        "update in sql": (mutate(lambda d: d["goal"][0].update(sql="UPDATE claims SET amount=0")),
                          ("SQL_NOT_READONLY", "goal[0].sql")),
        "unknown table in allowed": (mutate(lambda d: d["frame"]["allowed"].append({"table": "nope", "insert": 1})),
                                     ("FRAME_TABLE_NOT_UNCHANGED", "frame.allowed[2].table")),
        "four screen checks": (mutate(lambda d: d.update(screen=[{"id": str(i), "ask": "?"} for i in range(4)])),
                               ("SCREEN_TOO_MANY", "screen")),
        "missing goal": (mutate(lambda d: d.update(goal=[])), ("MISSING_GOAL", "goal")),
        "bad param": (mutate(lambda d: d["params"].pop("new_amount")), ("PARAM_UNDEFINED", "instruction")),
        "yaml error": ("id: [unclosed", ("YAML_ERROR", "$")),
    }
    assert len(cases) == 8
    for name, (text, expected) in cases.items():
        assert expected in codes(text), name


def test_unknown_table_in_unchanged():
    assert ("UNKNOWN_TABLE", "frame.unchanged[0]") in codes(
        mutate(lambda d: d["frame"].update(unchanged=["ghost"], allowed=[])), {"claims"})


OPS = [
    ("equals", 5, [(5,)], [(6,)]), ("not_equals", 5, [(6,)], [(5,)]), ("gte", 5, [(5,)], [(4,)]),
    ("lte", 5, [(5,)], [(6,)]), ("between", [1, 3], [(2,)], [(4,)]), ("in", [1, 2], [(2,)], [(3,)]),
    ("matches", "^ab", [("abc",)], [("xab",)]), ("empty", True, [(None,)], [(1,)]),
    ("not_empty", True, [(1,)], [(None,)]), ("row_count", 2, [(1,), (2,)], [(1,)]),
]


@pytest.mark.parametrize("op,arg,good,bad", OPS)
def test_each_operator_pass_and_fail(op, arg, good, bad):  # V13: 20 of 20
    assert evaluator.apply_operator(op, arg, good)[0] is True
    assert evaluator.apply_operator(op, arg, bad)[0] is False


def test_sql_runs_read_only(tmp_path):
    import sqlite3
    db = str(tmp_path / "x.db")
    sqlite3.connect(db).executescript("create table t(a); insert into t values (1);")
    assert evaluator.run_sql(db, "SELECT a FROM t WHERE a = :a", {"a": 1}) == [(1,)]
    with pytest.raises(sqlite3.OperationalError):
        evaluator.run_sql(db, "INSERT INTO t VALUES (2)", {})


def test_frame_check_a4_worked_example(tmp_path):  # V16
    from savepoint.adapters.claimdesk import ClaimDeskAdapter
    from savepoint.snapshot import checkpoint
    a = ClaimDeskAdapter("http://127.0.0.1:5001", str(tmp_path / "cd.db"))
    s0 = a.reset("seed_a")
    cp = checkpoint.take(a, "r", 0, "initial", str(tmp_path / "art"))
    import sqlite3
    con = sqlite3.connect(a.db_path)
    con.execute("UPDATE claims SET amount=1250.00 WHERE id='CL-10427'")
    con.execute("INSERT INTO claim_notes (claim_id, body, created_at) VALUES ('CL-10427','adjusted','t')")
    con.commit()
    c = schema.load(str(WF / "adjust_amount.yaml"))
    assert evaluator.check(c, "frame", a, s0, cp.db_path)[0].passed
    con.execute("UPDATE claims SET adjuster_id='ADJ-09' WHERE id='CL-10431'")
    con.commit()
    res = evaluator.check(c, "frame", a, s0, cp.db_path)[0]
    assert not res.passed and any("claims[CL-10431]" in v or "CL-10431" in v for v in res.observed)
    goal = evaluator.check(c, "goal", a)
    assert all(g.passed for g in goal)  # without the frame check this would count as a success
