import pandas as pd
import pytest

from packages.backtest.engine import Config, RuleStrategy, metrics, run


class Fixed:
    def __init__(self, values):
        self.values = values

    def signals(self, frame):
        return pd.Series(self.values)


def candles(prices):
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-02", periods=len(prices), tz="UTC"),
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "volume": 1000,
        }
    )


def test_next_open_execution_and_pnl():
    r = run(
        candles([10, 20, 30, 40]),
        Config(initial_capital=1000, position_size=1, commission_bps=0, slippage_bps=0),
        Fixed([1, 0, 0, 0]),
    )
    t = r["trades"][0]
    assert t["entry_price"] == 20
    assert t["exit_price"] == 30
    assert t["quantity"] == 50
    assert t["net_pnl"] == 500
    assert r["metrics"]["total_return"] == 0.5
    assert r["equity_curve"][0]["equity"] == 1000


def test_commission_and_slippage_accounting():
    r = run(
        candles([100, 100, 100]),
        Config(initial_capital=1000, position_size=1, commission_bps=100, slippage_bps=100),
        Fixed([1, 0, 0]),
    )
    qty = 1000 / (101 * 1.01)
    expected = qty * 99 * 0.99
    assert r["equity_curve"][-1]["equity"] == pytest.approx(expected)
    assert r["trades"][0]["net_pnl"] == pytest.approx(expected - 1000)
    assert r["trades"][0]["fees"] == pytest.approx(qty * (101 + 99) * 0.01)
    assert r["open_position"]["cash"] >= 0


def test_max_position_and_terminal_mark():
    r = run(
        candles([100, 100, 110]),
        Config(
            initial_capital=1000,
            position_size=1,
            max_position_size=0.25,
            commission_bps=0,
            slippage_bps=0,
        ),
        Fixed([1, 1, 1]),
    )
    assert r["open_position"]["quantity"] == 2.5
    assert r["open_position"]["cash"] == 750
    assert r["metrics"]["number_of_trades"] == 0
    assert r["metrics"]["total_return"] == pytest.approx(0.025)


def test_stop_target_ambiguity_and_gap():
    f = candles([100, 100, 80])
    f.loc[1, "high"], f.loc[1, "low"] = 120, 80
    cfg = Config(
        initial_capital=1000,
        position_size=1,
        commission_bps=0,
        slippage_bps=0,
        stop_loss=0.1,
        take_profit=0.1,
    )
    r = run(f, cfg, Fixed([1, 0, 0]))
    assert r["trades"][0]["exit_price"] == 90
    assert r["trades"][0]["reason"] == "stop"
    f.loc[1, "high"], f.loc[1, "low"] = 100, 100
    r = run(f, cfg, Fixed([1, 1, 1]))
    assert r["trades"][0]["exit_price"] == 80
    assert r["trades"][0]["reason"] == "stop_gap"


@pytest.mark.parametrize("name", ["sma_crossover", "rsi_mean_reversion", "momentum", "breakout"])
def test_strategy_causality(frame, name):
    rule = RuleStrategy(name)
    before = rule.signals(frame)
    changed = frame.copy()
    changed.loc[75:, ["open", "high", "low", "close"]] = 1
    pd.testing.assert_series_equal(before.iloc[:75], rule.signals(changed).iloc[:75])
    config = Config(strategy=name)
    a, b = run(frame, config), run(changed, config)
    assert a["equity_curve"][:75] == b["equity_curve"][:75]


def test_drawdown_and_trade_statistics():
    eq = pd.Series(
        [100.0, 120.0, 90.0, 110.0], index=pd.date_range("2024-01-01", periods=4, tz="UTC")
    )
    m = metrics(eq, [{"net_pnl": 20}, {"net_pnl": -10}, {"net_pnl": 0}], 100)
    assert m["max_drawdown"] == -0.25
    assert m["win_rate"] == pytest.approx(1 / 3)
    assert m["loss_rate"] == pytest.approx(1 / 3)
    assert m["profit_factor"] == 2
    assert m["expectancy"] == pytest.approx(10 / 3)


def test_empty_undefined_statistics():
    r = run(candles([100, 100, 100]), Config(), Fixed([0, 0, 0]))
    assert r["metrics"]["sharpe"] is None
    assert r["metrics"]["sortino"] is None
    assert r["metrics"]["profit_factor"] is None


def test_reject_unordered_bars():
    with pytest.raises(ValueError, match="chronologically"):
        run(candles([100, 101, 102]).iloc[::-1], Config())
