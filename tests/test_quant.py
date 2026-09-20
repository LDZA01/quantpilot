import numpy as np
import pandas as pd
import pytest

from packages.quant.features import features, wilder
from packages.quant.scanner import scan


def test_returns_and_indicators(frame):
    f = features(frame)
    assert np.isnan(f.returns.iloc[0])
    assert f.returns.iloc[1] == pytest.approx(0.01)
    assert f.log_returns.iloc[1] == pytest.approx(np.log(1.01))
    assert np.isnan(f.sma20.iloc[18])
    assert f.sma20.iloc[19] == pytest.approx(109.5)
    assert f.sma50.iloc[49] == pytest.approx(124.5)
    assert f.rsi.iloc[14] == 100
    assert f.atr.iloc[13] == 4
    assert f.relative_volume.iloc[20] == 1
    assert f.momentum20.iloc[20] == pytest.approx(0.2)
    assert f.bollinger_upper.iloc[19] == pytest.approx(109.5 + 2 * np.std(range(100, 120)))
    assert f.daily_vwap_proxy20.iloc[19] == pytest.approx(109.5)
    assert f.drawdown.iloc[-1] == 0


def test_wilder_seed_and_recurrence():
    result = wilder(pd.Series([1.0, 2.0, 3.0, 4.0]), 3)
    assert np.isnan(result.iloc[1])
    assert result.iloc[2] == 2
    assert result.iloc[3] == pytest.approx(8 / 3)


def test_flat_rsi_and_zero_volume(frame):
    frame[["open", "high", "low", "close"]] = 100.0
    frame.volume = 0
    f = features(frame)
    assert f.rsi.iloc[-1] == 50
    assert np.isnan(f.relative_volume.iloc[-1])
    assert np.isnan(f.daily_vwap_proxy20.iloc[-1])


def test_no_future_feature_leakage(frame):
    expected = features(frame).iloc[:75]
    altered = frame.copy()
    altered.loc[75:, ["open", "high", "low", "close"]] *= 10
    pd.testing.assert_frame_equal(expected, features(altered).iloc[:75])


def test_scanner_is_deterministic_and_explainable(frame):
    result = scan("TEST", frame)
    assert result == scan("TEST", frame)
    assert any(r["setup"] == "momentum" for r in result)
    assert all(r["signal_strength"] in (66.67, 100) for r in result)
    assert all(r["supporting_factors"] and r["risk_factors"] for r in result)
    assert scan("TEST", frame.iloc[:20]) == []
