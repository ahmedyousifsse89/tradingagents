"""Tests for the control API: auth, reads, mutations, and the run trigger."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.execution_fakes import FakeBroker, position
from tests.test_runner import FakeGraph
from tradingagents.execution import ExecutionEngine
from tradingagents.runner import TradingRunner
from tradingagents.server.app import create_app
from tradingagents.server.auth import MissingAPIToken, load_token, token_matches

TOKEN = "test-token-that-is-long-enough-1234"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture()
def runner(tmp_path):
    config = {
        "data_cache_dir": str(tmp_path / "cache"),
        "execution_enabled": True,
        "execution_dry_run": True,
    }
    broker = FakeBroker(positions=[position("NVDA", 10, 100.0)])
    return TradingRunner(
        config,
        broker=broker,
        engine=ExecutionEngine(config, broker=broker),
        graph=FakeGraph({"NVDA": "Buy"}),
    )


@pytest.fixture()
def client(runner):
    app = create_app(runner.config, runner=runner, api_token=TOKEN)
    with TestClient(app) as test_client:
        yield test_client


# ---- auth ------------------------------------------------------------


def test_token_must_be_configured(monkeypatch):
    monkeypatch.delenv("TRADINGAGENTS_API_TOKEN", raising=False)
    with pytest.raises(MissingAPIToken, match="not set"):
        load_token({})


def test_short_token_is_rejected():
    with pytest.raises(MissingAPIToken, match="at least"):
        load_token({"TRADINGAGENTS_API_TOKEN": "short"})


@pytest.mark.parametrize(
    "header", [None, "", "Bearer", "Bearer ", "Basic " + TOKEN, "Bearer wrong-token"]
)
def test_bad_authorization_headers_are_rejected(header):
    assert token_matches(TOKEN, header) is False


def test_correct_token_matches():
    assert token_matches(TOKEN, f"Bearer {TOKEN}") is True


def test_unauthenticated_requests_are_refused(client):
    assert client.get("/api/status").status_code == 401
    assert client.get("/api/positions").status_code == 401
    assert client.post("/api/runs", json={}).status_code == 401


def test_health_needs_no_token(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---- status ----------------------------------------------------------


def test_status_reports_account_and_mode(client):
    body = client.get("/api/status", headers=AUTH).json()
    assert body["account"]["equity"] == 100_000.0
    assert body["account"]["market_open"] is True
    assert body["runner"]["execution_dry_run"] is True
    assert body["risk"]["halted"] is False
    assert body["broker_error"] is None


def test_status_survives_a_broker_outage(runner):
    class DeadBroker(FakeBroker):
        def get_account(self):
            raise RuntimeError("alpaca unreachable")

    runner._broker = DeadBroker()
    app = create_app(runner.config, runner=runner, api_token=TOKEN)
    with TestClient(app) as client:
        body = client.get("/api/status", headers=AUTH).json()
    assert body["account"] is None
    assert "alpaca unreachable" in body["broker_error"]
    assert body["runner"]["running"] is False


def test_positions_are_listed_with_unrealised_pl(client):
    body = client.get("/api/positions", headers=AUTH).json()
    (pos,) = body["positions"]
    assert pos["symbol"] == "NVDA"
    assert pos["qty"] == 10
    assert pos["unrealized_pl"] == 0.0


# ---- watchlist -------------------------------------------------------


def test_watchlist_crud(client):
    assert client.get("/api/watchlist", headers=AUTH).json() == {"tickers": []}

    put = client.put("/api/watchlist", headers=AUTH, json={"tickers": ["nvda", "amd"]})
    assert put.json() == {"tickers": ["NVDA", "AMD"]}

    delete = client.delete("/api/watchlist/nvda", headers=AUTH)
    assert delete.json() == {"tickers": ["AMD"]}


def test_watchlist_rejects_an_unsafe_ticker(client):
    response = client.put(
        "/api/watchlist", headers=AUTH, json={"tickers": ["../../etc/passwd"]}
    )
    assert response.status_code == 400


# ---- runs ------------------------------------------------------------


def test_trigger_run_executes_in_the_background(client, runner):
    response = client.post("/api/runs", headers=AUTH, json={"tickers": ["NVDA"]})
    assert response.status_code == 202

    # The worker is a single thread; shutting the executor down waits for it.
    client.app.state.executor.shutdown(wait=True)

    runs = client.get("/api/runs", headers=AUTH).json()["runs"]
    assert runs[0]["ratings"] == {"NVDA": "Buy"}
    assert runs[0]["status"] == "completed"


def test_trigger_run_conflicts_when_one_is_in_flight(client, runner, monkeypatch):
    monkeypatch.setattr(
        type(runner), "is_running", property(lambda self: True), raising=False
    )
    response = client.post("/api/runs", headers=AUTH, json={})
    assert response.status_code == 409


def test_unknown_run_id_is_404(client):
    assert client.get("/api/runs/run-nope", headers=AUTH).status_code == 404


# ---- orders ----------------------------------------------------------


def test_orders_come_back_newest_first(client, runner):
    runner.engine.execute_ratings({"AMD": "Buy"}, trade_date="2026-08-07")
    orders = client.get("/api/orders", headers=AUTH).json()["orders"]
    assert orders[0]["symbol"] == "AMD"
    assert orders[0]["status"] == "dry_run"


# ---- risk ------------------------------------------------------------


def test_halt_and_resume_round_trip(client):
    halted = client.post("/api/risk/halt", headers=AUTH, json={"detail": "stop"}).json()
    assert halted["halted"] is True
    assert client.get("/api/risk", headers=AUTH).json()["halted"] is True

    resumed = client.post("/api/risk/resume", headers=AUTH).json()
    assert resumed["halted"] is False


def test_halt_blocks_a_subsequent_run(client, runner):
    client.post("/api/risk/halt", headers=AUTH, json={"detail": "stop"})
    client.post("/api/runs", headers=AUTH, json={"tickers": ["NVDA"]})
    client.app.state.executor.shutdown(wait=True)

    runs = client.get("/api/runs", headers=AUTH).json()["runs"]
    assert runs[0]["status"] == "halted"


def test_flatten_requires_the_literal_confirmation(client):
    assert client.post("/api/flatten", headers=AUTH, json={"confirm": "yes"}).status_code == 400
    assert client.post("/api/flatten", headers=AUTH, json={"confirm": "flatten"}).status_code == 400


def test_flatten_closes_positions_when_confirmed(client):
    body = client.post("/api/flatten", headers=AUTH, json={"confirm": "FLATTEN"}).json()
    assert [o["symbol"] for o in body["orders"]] == ["NVDA"]
    assert body["orders"][0]["side"] == "sell"
