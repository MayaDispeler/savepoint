from fastapi.testclient import TestClient

from savepoint.api import main


def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "_ledger", None)
    monkeypatch.setenv("LEDGER_URL", f"sqlite:///{tmp_path / 'l.db'}")
    return TestClient(main.app)


def test_healthz_and_empty_runs(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    assert c.get("/healthz").json()["sandbox_only"] is True
    assert c.get("/runs").json() == []
    r = c.get("/runs/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


def test_sandbox_violation_403(tmp_path, monkeypatch):  # V27
    r = client(tmp_path, monkeypatch).post("/runs", json={"base_url": "https://example.com"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "SANDBOX_VIOLATION"


def test_budget_exceeded_402_before_any_model_call(tmp_path, monkeypatch):  # V08
    r = client(tmp_path, monkeypatch).post("/runs", json={"cap_usd": 0.01, "model": "claude-haiku-5-5"})
    assert r.status_code == 402 and r.json()["error"]["code"] == "BUDGET_EXCEEDED"


def test_invalid_contract_422(tmp_path, monkeypatch):
    r = client(tmp_path, monkeypatch).post("/runs", json={"contract_yaml": "id: [bad"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "CONTRACT_INVALID"


def test_app_not_running_409(tmp_path, monkeypatch):
    r = client(tmp_path, monkeypatch).post("/runs", json={})
    assert r.status_code == 409 and r.json()["error"]["code"] == "APP_NOT_RUNNING"
