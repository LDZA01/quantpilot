from datetime import UTC, date, datetime

import numpy as np
import pytest
from sqlalchemy import func, select

from apps.api.db import DataSnapshot, MarketBar
from apps.api.snapshots import restore_snapshot, save_snapshot
from packages.backtest.engine import Config, run
from packages.market_data.provider import DataUnavailable
from packages.quant.features import features
from pipelines.ingest import ingest
from tests.test_api import client
from tests.test_backtest import Fixed, candles
from tests.test_data import Provider, bar


def test_snapshot_reuses_content_and_roundtrips(db, frame):
    frame.loc[0, "close"] = 100.12345678901234
    first = save_snapshot(db, frame)
    second = save_snapshot(db, frame)
    assert first == second
    assert db.scalar(select(func.count()).select_from(DataSnapshot)) == 1
    restored = restore_snapshot(db, first)
    assert restored.close.iloc[0] == frame.close.iloc[0]
    assert str(restored.timestamp.dt.tz) == "UTC"


def test_replay_survives_market_data_revision(db):
    ingest(db, Provider([bar(), bar(3), bar(4)]), "TEST", date(2024, 1, 1), date(2024, 2, 1))
    with client(db) as api:
        result = api.post("/backtests", json={"symbol": "TEST"}).json()
        for b in db.scalars(select(MarketBar)):
            b.close = 999
        db.commit()
        replay = api.post(f"/runs/{result['id']}/reproduce")
        assert replay.status_code == 200
        assert replay.json()["matches"] is True
    from apps.api.main import app

    app.dependency_overrides.clear()


def test_request_historical_subset_does_not_reverse_range(db):
    provider = Provider([bar(), bar(3), bar(25)])
    ingest(db, provider, "TEST", date(2024, 1, 1), date(2024, 2, 1))
    result = ingest(db, provider, "TEST", date(2024, 1, 1), date(2024, 1, 5))
    assert result["rows_unchanged"] == 2
    assert provider.calls[-1] == date(2024, 1, 1)


def test_empty_provider_fails_explicitly(db):
    with pytest.raises(DataUnavailable, match="empty"):
        ingest(db, Provider([]), "TEST", date(2024, 1, 1), date(2024, 2, 1), attempts=1)


def test_retry_after_rate_limit(db, monkeypatch):
    sleeps = []
    monkeypatch.setattr("pipelines.ingest.time.sleep", sleeps.append)

    class Throttled(Provider):
        failures = 0

        def get_history(self, symbol, start, end):
            if not self.failures:
                self.failures += 1
                raise DataUnavailable("429 rate limited")
            return super().get_history(symbol, start, end)

    result = ingest(db, Throttled([bar()]), "TEST", date(2024, 1, 1), date(2024, 2, 1))
    assert result["rows_inserted"] == 1
    assert sleeps == [1]


def test_partial_action_refresh_is_atomic(db):
    provider = Provider([bar(), bar(3), bar(25)])
    ingest(db, provider, "TEST", date(2024, 1, 1), date(2024, 2, 1))
    provider.bars = [bar(25, price=50)]
    with pytest.raises(DataUnavailable, match="did not cover"):
        ingest(db, provider, "TEST", date(2024, 1, 1), date(2024, 2, 1), attempts=1)
    assert all(b.close == 100 for b in db.scalars(select(MarketBar)))


@pytest.mark.parametrize("bad", [float("inf"), float("nan"), 0, -1])
def test_bad_price_cannot_enter_features_or_engine(frame, bad):
    frame.loc[10, "close"] = bad
    with pytest.raises(ValueError):
        features(frame)
    with pytest.raises(ValueError):
        run(frame, Config())


def test_naive_timestamps_rejected(frame):
    frame.timestamp = frame.timestamp.dt.tz_localize(None)
    with pytest.raises(ValueError, match="timezone"):
        run(frame, Config())


def test_sell_signal_uses_open_even_when_stop_touched_later():
    f = candles([100, 100, 100])
    f.loc[2, "low"] = 50
    r = run(f, Config(commission_bps=0, slippage_bps=0, stop_loss=0.1), Fixed([1, 0, 0]))
    assert r["trades"][0]["exit_price"] == 100
    assert r["trades"][0]["reason"] == "signal_next_open"


def test_entry_day_target_and_no_same_bar_reentry():
    f = candles([100, 100, 100])
    f.loc[1, "high"] = 120
    r = run(f, Config(commission_bps=0, slippage_bps=0, take_profit=0.1), Fixed([1, 0, 0]))
    assert len(r["trades"]) == 1
    assert r["trades"][0]["exit_price"] == pytest.approx(110)
    assert r["open_position"]["quantity"] == 0


def test_provider_excludes_current_session_and_preserves_missing(monkeypatch):
    from packages.market_data.provider import YahooProvider

    class FakeTicker:
        def history(self, **kwargs):
            assert kwargs["auto_adjust"] is False
            assert kwargs["keepna"] is True
            assert date.fromisoformat(kwargs["end"]) <= datetime.now(UTC).date()
            return __import__("pandas").DataFrame()

    monkeypatch.setattr("packages.market_data.provider.yf.Ticker", lambda _: FakeTicker())
    with pytest.raises(DataUnavailable, match="No data"):
        YahooProvider().get_history("AAPL", date(2024, 1, 1), date(2099, 1, 1))


def test_ema_macd_and_volatility_reference(frame):
    f = features(frame)
    expected = frame.close.ewm(span=20, adjust=False, min_periods=20).mean()
    assert f.ema20.iloc[-1] == pytest.approx(expected.iloc[-1])
    expected_vol = np.std(frame.close.pct_change().iloc[-20:], ddof=1) * np.sqrt(252)
    assert f.volatility.iloc[-1] == pytest.approx(expected_vol)


def test_later_start_still_bridges_existing_coverage(db):
    provider = Provider([bar(), bar(3), bar(25)])
    ingest(db, provider, "TEST", date(2024, 1, 1), date(2024, 1, 4))
    ingest(db, provider, "TEST", date(2024, 1, 25), date(2024, 2, 1))
    assert provider.calls[-1] <= date(2024, 1, 3)
    assert db.scalar(select(func.count()).select_from(MarketBar)) == 3


def test_aligned_benchmark_and_replay(db):
    provider = Provider([bar(), bar(3), bar(4)])
    ingest(db, provider, "TEST", date(2024, 1, 1), date(2024, 2, 1))
    provider.bars = [b.model_copy(update={"symbol": "SPY"}) for b in provider.bars]
    ingest(db, provider, "SPY", date(2024, 1, 1), date(2024, 2, 1))
    with client(db) as api:
        result = api.post("/backtests", json={"symbol": "TEST"}).json()
        assert result["benchmark"] is not None
        assert result["benchmark"]["config"]["position_size"] == 1
        replay = api.post(f"/runs/{result['id']}/reproduce").json()
        assert replay["matches"]
    from apps.api.main import app

    app.dependency_overrides.clear()
