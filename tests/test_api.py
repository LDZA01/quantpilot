from fastapi.testclient import TestClient

from apps.api.db import session
from apps.api.main import app
from pipelines.ingest import ingest
from tests.test_data import Provider, bar


def client(db):
    app.dependency_overrides[session] = lambda: db
    return TestClient(app)


def test_health_readiness_and_missing_data(db):
    with client(db) as api:
        assert api.get("/health").status_code == 200
        assert api.get("/ready").status_code == 503
        assert api.get("/bars/TEST").status_code == 404
        assert api.post("/ingest", json={"symbol": "bad;symbol"}).status_code == 422
    app.dependency_overrides.clear()


def test_ingest_features_scanner_backtest_persistence(db):
    from datetime import date

    ingest(db, Provider([bar(), bar(3), bar(4)]), "TEST", date(2024, 1, 1), date(2024, 2, 1))
    with client(db) as api:
        assert len(api.get("/assets").json()) == 1
        assert len(api.get("/bars/TEST").json()) == 3
        assert api.get("/features/TEST").json()["latest"]["rsi"] is None
        scan = api.post("/scanner", json={"symbols": ["TEST", "MISSING"]}).json()
        assert len(scan["failures"]) == 2
        response = api.post("/backtests", json={"symbol": "TEST"})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["benchmark"] is None
        assert len(result["data_hash"]) == 64
        assert api.get("/runs/" + result["id"]).json() == result
        assert len(api.get("/runs").json()) == 1
        assert api.get("/jobs").json()[0]["status"] == "completed"
    app.dependency_overrides.clear()


def test_provider_error_is_visible_and_audited(db, monkeypatch):
    from apps.api.main import settings
    from packages.market_data.provider import DataUnavailable

    def fail(*args):
        raise DataUnavailable("provider offline")

    monkeypatch.setattr("apps.api.main.YahooProvider.get_history", fail)
    monkeypatch.setattr(settings(), "ingestion_attempts", 1)
    with client(db) as api:
        result = api.post("/ingest", json={"symbol": "AAPL"})
        assert result.status_code == 502
        assert "provider offline" in result.json()["detail"]
        job = api.get("/jobs").json()[0]
        assert job["status"] == "failed"
        assert job["detail"]["rows_inserted"] == 0
        assert job["created_at"].endswith(("Z", "+00:00"))
    app.dependency_overrides.clear()
