from datetime import UTC, date, datetime

import pandas as pd
import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from apps.api.db import Job, MarketBar
from packages.market_data.provider import Bar, DataUnavailable, normalize
from pipelines.ingest import ingest


def bar(day=2, price=100, **kwargs):
    return Bar(
        symbol="TEST",
        timestamp=datetime(2024, 1, day, tzinfo=UTC),
        open=price,
        high=price + 1,
        low=price - 1,
        close=price,
        adjusted_close=price,
        volume=100,
        **kwargs,
    )


class Provider:
    name = "yfinance"

    def __init__(self, bars):
        self.bars = bars
        self.calls = []

    def get_history(self, symbol, start, end):
        self.calls.append(start)
        return [b for b in self.bars if start <= b.timestamp.date() < end]

    def get_asset(self, symbol):
        return {"symbol": symbol, "name": "Test fixture", "sector": None, "currency": "USD"}


def test_validation():
    b = bar().model_dump()
    for key, value in [
        ("close", float("nan")),
        ("volume", -1),
        ("high", 10),
        ("open", 0),
        ("timestamp", datetime(2024, 1, 2)),
        ("volume", 1.5),
    ]:
        with pytest.raises(ValidationError):
            Bar(**{**b, key: value})


def test_normalization_preserves_session_date():
    frame = pd.DataFrame(
        {
            "Open": [100.0],
            "High": [102.0],
            "Low": [99.0],
            "Close": [101.0],
            "Adj Close": [100.5],
            "Volume": [1000],
        },
        index=pd.DatetimeIndex(["2024-03-11"], tz="America/New_York"),
    )
    normalized = normalize("TEST", frame)[0]
    assert normalized.timestamp == datetime(2024, 3, 11, tzinfo=UTC)
    assert normalized.adjusted_close == 100.5
    with pytest.raises(DataUnavailable, match="Duplicate"):
        normalize("TEST", pd.concat([frame, frame]))


def test_idempotent_upsert_and_incremental_overlap(db):
    provider = Provider([bar(), bar(3), bar(25)])
    first = ingest(db, provider, "TEST", date(2024, 1, 1), date(2024, 2, 1))
    second = ingest(db, provider, "TEST", date(2024, 1, 1), date(2024, 2, 1))
    assert first["rows_inserted"] == 3
    assert second["rows_inserted"] == 0
    assert second["rows_unchanged"] == 1
    assert provider.calls[-1] == date(2024, 1, 15)
    assert db.scalar(select(func.count()).select_from(MarketBar)) == 3


def test_adjustment_refresh(db):
    provider = Provider([bar(), bar(3), bar(25)])
    ingest(db, provider, "TEST", date(2024, 1, 1), date(2024, 2, 1))
    provider.bars = [b.model_copy(update={"adjusted_close": 99.0}) for b in provider.bars]
    result = ingest(db, provider, "TEST", date(2024, 1, 1), date(2024, 2, 1))
    assert result["adjustment_refresh"]
    assert provider.calls[-1] == date(2024, 1, 1)
    assert result["rows_updated"] == 3


def test_failed_job_rolls_back(db):
    class Broken(Provider):
        def get_asset(self, symbol):
            raise DataUnavailable("offline")

    with pytest.raises(DataUnavailable, match="offline"):
        ingest(db, Broken([bar()]), "TEST", date(2024, 1, 1), date(2024, 2, 1), attempts=1)
    assert db.scalar(select(func.count()).select_from(MarketBar)) == 0
    job = db.scalars(select(Job)).one()
    assert job.status == "failed"
    assert job.detail["rows_inserted"] == 0
