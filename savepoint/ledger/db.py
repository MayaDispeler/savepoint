"""Ledger (PRD section 6 tables) on SQLAlchemy Core. SQLite locally; the same schema runs on Postgres
(Supabase) by setting LEDGER_URL."""
import json
import os
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    func,
    insert,
    select,
)
from sqlalchemy.exc import IntegrityError

DEFAULT_URL = "sqlite:///ledger.db"
md = MetaData()


def _enum(name, *values):
    return CheckConstraint(f"{name} IN ({', '.join(repr(v) for v in values)})", name=f"ck_{name}")


workflows = Table(
    "workflows", md,
    Column("id", String, primary_key=True), Column("app", String, nullable=False),
    Column("title", String, nullable=False), Column("source", String, nullable=False, default="own"),
    Column("contract_yaml", Text, nullable=False), Column("contract_sha256", String(64), nullable=False),
    Column("golden_diff", JSON), _enum("source", "own", "legacyworld"))

runs = Table(
    "runs", md,
    Column("id", String, primary_key=True), Column("workflow_id", String, ForeignKey("workflows.id")),
    Column("arm", String, nullable=False), Column("model", String, nullable=False),
    Column("trial", Integer, nullable=False), Column("policy", String, nullable=False),
    Column("fault", String), Column("started_at", DateTime(timezone=True)),
    Column("ended_at", DateTime(timezone=True)), Column("agent_status", String, nullable=False),
    Column("sp_outcome", String, nullable=False), Column("oracle", String, nullable=False),
    Column("claim_true", Boolean), Column("false_completion", Boolean, default=False),
    Column("verify_digest", JSON), Column("steps", Integer, default=0),
    Column("input_tokens", Integer, default=0), Column("output_tokens", Integer, default=0),
    Column("cache_read_tokens", Integer, default=0), Column("cost_usd", Float, default=0.0),
    Column("wall_ms", Integer, default=0), Column("checkpoint_ms", Integer, default=0),
    Column("featured", Boolean, default=False), Column("quarantined", Boolean, default=False),
    Column("retries", Integer, default=0),
    UniqueConstraint("workflow_id", "arm", "trial", "model", name="uq_run"),
    _enum("arm", "B", "S", "R"),
    _enum("agent_status", "done", "cannot_complete", "timeout", "step_budget", "error", "halted"),
    _enum("sp_outcome", "committed", "rolled_back", "retried_committed", "rollback_failed", "none"),
    _enum("oracle", "VS", "VF", "IS", "IF"))

steps = Table(
    "steps", md,
    Column("run_id", String, ForeignKey("runs.id"), primary_key=True),
    Column("idx", Integer, primary_key=True), Column("action", JSON), Column("element", JSON),
    Column("risky", Boolean), Column("state_changed", Boolean), Column("screenshot", String),
    Column("t_ms", Integer))

checkpoints = Table(
    "checkpoints", md,
    Column("id", String, primary_key=True), Column("run_id", String, ForeignKey("runs.id")),
    Column("step_idx", Integer), Column("kind", String), Column("db_path", String),
    Column("files_path", String), Column("browser_state_path", String), Column("url", String),
    Column("digest_sha256", String(64)), Column("bytes", BigInteger), Column("took_ms", Integer),
    _enum("kind", "initial", "risky", "retry"))

validations = Table(
    "validations", md,
    Column("pk", Integer, primary_key=True, autoincrement=True),
    Column("run_id", String, ForeignKey("runs.id")), Column("step_idx", Integer),
    Column("phase", String), Column("check_id", String), Column("passed", Boolean),
    Column("observed", JSON), Column("expected", JSON), Column("took_ms", Integer),
    _enum("phase", "invariant", "goal", "frame", "screen"))

rollbacks = Table(
    "rollbacks", md,
    Column("id", String, primary_key=True), Column("run_id", String, ForeignKey("runs.id")),
    Column("from_step", Integer), Column("checkpoint_id", String), Column("reason", String),
    Column("restore_ms", Integer), Column("rows_differ", Integer), Column("exact", Boolean),
    Column("shot_before", String), Column("shot_after", String), Column("pixel_diff_pct", Float),
    _enum("reason", "invariant", "false_completion", "agent_failed", "timeout", "step_budget", "error"))

budget_ledger = Table(
    "budget_ledger", md,
    Column("id", Integer, primary_key=True, autoincrement=True), Column("at", DateTime(timezone=True)),
    Column("run_id", String), Column("model", String), Column("input_tokens", Integer),
    Column("output_tokens", Integer), Column("cache_read_tokens", Integer), Column("cost_usd", Float))


def _jsonable(v):
    return json.loads(json.dumps(v, default=str))


class Ledger:
    def __init__(self, url: str | None = None):
        self.engine = create_engine(url or os.environ.get("LEDGER_URL", DEFAULT_URL))
        md.create_all(self.engine)

    def upsert_workflow(self, contract, yaml_text: str, golden_diff=None):
        with self.engine.begin() as c:
            exists = c.execute(select(workflows.c.id).where(workflows.c.id == contract.id)).first()
            if not exists:
                c.execute(insert(workflows).values(
                    id=contract.id, app=contract.app, title=contract.title, source="own",
                    contract_yaml=yaml_text, contract_sha256=contract.sha256,
                    golden_diff=_jsonable(golden_diff)))
            elif golden_diff is not None:
                c.execute(workflows.update().where(workflows.c.id == contract.id)
                          .values(golden_diff=_jsonable(golden_diff)))

    def run_exists(self, workflow_id: str, arm: str, trial: int, model: str) -> bool:
        with self.engine.connect() as c:
            return c.execute(select(runs.c.id).where(
                (runs.c.workflow_id == workflow_id) & (runs.c.arm == arm) & (runs.c.trial == trial)
                & (runs.c.model == model))).first() is not None

    def record_run(self, rec: dict, step_rows=(), cps=(), vals=(), rbs=()) -> str | None:
        """Insert one run and children in a single transaction. Returns None on a duplicate (INV08)."""
        rid = rec.setdefault("id", str(uuid.uuid4()))
        try:
            with self.engine.begin() as c:
                c.execute(insert(runs).values(**_jsonable_run(rec)))
                for table, rows in ((steps, step_rows), (checkpoints, cps), (validations, vals),
                                    (rollbacks, rbs)):
                    for r in rows:
                        c.execute(insert(table).values(run_id=rid, **{k: _jsonable(v) for k, v in r.items()}))
        except IntegrityError:
            if self.run_exists(rec["workflow_id"], rec["arm"], rec["trial"], rec["model"]):
                return None
            raise
        return rid

    def spent_usd(self) -> float:
        with self.engine.connect() as c:
            return float(c.execute(select(func.coalesce(func.sum(budget_ledger.c.cost_usd), 0.0))).scalar())

    def add_spend(self, run_id, model, in_tok, out_tok, cache_tok, cost):
        with self.engine.begin() as c:
            c.execute(insert(budget_ledger).values(at=datetime.now(UTC), run_id=run_id, model=model,
                                                   input_tokens=in_tok, output_tokens=out_tok,
                                                   cache_read_tokens=cache_tok, cost_usd=cost))

    def all_runs(self) -> list[dict]:
        with self.engine.connect() as c:
            return [dict(r._mapping) for r in c.execute(select(runs).order_by(runs.c.workflow_id, runs.c.arm,
                                                                               runs.c.trial))]

    def rows(self, table) -> list[dict]:
        with self.engine.connect() as c:
            return [dict(r._mapping) for r in c.execute(select(table))]


def _jsonable_run(rec):
    out = dict(rec)
    if "verify_digest" in out:
        out["verify_digest"] = _jsonable(out["verify_digest"])
    return out
