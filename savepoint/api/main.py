"""Local FastAPI (port 8787): /healthz /runs /runs/{id} /runs/{id}/steps /workflows and a budget-guarded POST /runs."""
import os
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from savepoint import config
from savepoint.adapters.base import AppAdapter, SandboxViolation
from savepoint.agent.budget import BudgetExceeded, BudgetGuard
from savepoint.contracts import schema
from savepoint.ledger.db import Ledger, runs, steps, workflows

app = FastAPI(title="Savepoint")
_ledger: Ledger | None = None


def ledger() -> Ledger:
    global _ledger
    if _ledger is None:
        _ledger = Ledger(os.environ.get("LEDGER_URL", "sqlite:///ledger.db"))
    return _ledger


def err(status: int, code: str, message: str):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@app.exception_handler(SandboxViolation)
async def _sandbox(_: Request, e: SandboxViolation):
    return err(403, "SANDBOX_VIOLATION", str(e))


@app.exception_handler(BudgetExceeded)
async def _budget(_: Request, e: BudgetExceeded):
    return err(402, "BUDGET_EXCEEDED", str(e))


@app.get("/healthz")
def healthz():
    return {"ok": True, "sandbox_only": config.SANDBOX_ONLY}


@app.get("/runs")
def list_runs():
    return [{k: (str(v) if k.endswith("_at") else v) for k, v in r.items() if k != "verify_digest"}
            for r in ledger().all_runs()]


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    with ledger().engine.connect() as c:
        row = c.execute(select(runs).where(runs.c.id == run_id)).first()
    if row is None:
        return err(404, "NOT_FOUND", f"run {run_id} not found")
    return {k: (str(v) if k.endswith("_at") else v) for k, v in row._mapping.items()}


@app.get("/runs/{run_id}/steps")
def get_steps(run_id: str):
    with ledger().engine.connect() as c:
        return [dict(r._mapping) for r in c.execute(select(steps).where(steps.c.run_id == run_id)
                                                     .order_by(steps.c.idx))]


@app.get("/workflows")
def list_workflows():
    return [{"id": w["id"], "app": w["app"], "title": w["title"]} for w in ledger().rows(workflows)]


@app.post("/runs")
async def start_run(request: Request):
    """Validate the request, then refuse before any model call if the budget or sandbox would be violated."""
    body = await request.json()
    if "contract_yaml" in body:
        try:
            schema.parse(body["contract_yaml"])
        except schema.ContractInvalid as e:
            return err(422, "CONTRACT_INVALID", str(e))
    AppAdapter(body.get("base_url", "http://127.0.0.1:5001"))  # raises SandboxViolation
    BudgetGuard(ledger(), body.get("cap_usd", config.MODEL_BUDGET_USD)).check_start(
        body.get("model", config.BENCH_MODEL))
    host = urlparse(body.get("base_url", "http://127.0.0.1:5001")).hostname
    return err(409, "APP_NOT_RUNNING", f"no sandbox app is listening for host {host}; start it with make up")
