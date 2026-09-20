"""Single-asset long-only, fractional-share, next-open research simulator."""

from typing import Literal, Protocol

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from packages.market_data.validation import validate_frame
from packages.quant.features import features


class Config(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    strategy: Literal["sma_crossover", "rsi_mean_reversion", "momentum", "breakout"] = (
        "sma_crossover"
    )
    initial_capital: float = Field(default=10000, gt=0, le=1e12)
    position_size: float = Field(default=0.95, gt=0, le=1)
    max_position_size: float = Field(default=1, gt=0, le=1)
    commission_bps: float = Field(default=5, ge=0, le=1000)
    slippage_bps: float = Field(default=5, ge=0, le=1000)
    stop_loss: float | None = Field(default=None, gt=0, lt=1)
    take_profit: float | None = Field(default=None, gt=0, le=10)


class Strategy(Protocol):
    def signals(self, frame: pd.DataFrame) -> pd.Series: ...


class RuleStrategy:
    def __init__(self, name: str):
        self.name = name

    def signals(self, frame: pd.DataFrame) -> pd.Series:
        f = features(frame)
        if self.name == "sma_crossover":
            return (f.sma20 > f.sma50).astype(int)
        if self.name == "momentum":
            return (f.momentum20 > 0).astype(int)
        state = 0
        result = []
        for _, row in f.iterrows():
            if self.name == "rsi_mean_reversion":
                if row.rsi < 30:
                    state = 1
                elif row.rsi > 55:
                    state = 0
            elif self.name == "breakout":
                if row.close > row.prior_high20:
                    state = 1
                elif row.close < row.sma20:
                    state = 0
            else:
                raise ValueError("Unknown strategy")
            result.append(state)
        return pd.Series(result, index=f.index)


def metrics(equity: pd.Series, trades: list[dict], initial: float) -> dict:
    returns = equity.pct_change().dropna()
    years = (equity.index[-1] - equity.index[0]).total_seconds() / (365.25 * 86400)
    total = float(equity.iloc[-1] / initial - 1)
    exponent = np.log1p(total) / years if years > 0 and total > -1 else None
    cagr = float(np.expm1(exponent)) if exponent is not None and exponent < 700 else None
    std = float(returns.std(ddof=1)) if len(returns) > 1 else 0
    downside = float(np.sqrt(np.mean(np.minimum(returns, 0) ** 2))) if len(returns) else 0
    pnls = [t["net_pnl"] for t in trades]
    wins, losses = [x for x in pnls if x > 0], [x for x in pnls if x < 0]
    return {
        "total_return": total,
        "annualized_return": cagr,
        "cagr": cagr,
        "sharpe": float(returns.mean() / std * np.sqrt(252)) if std > 1e-12 else None,
        "sortino": float(returns.mean() / downside * np.sqrt(252)) if downside > 1e-12 else None,
        "max_drawdown": float((equity / equity.cummax() - 1).min()),
        "volatility": std * float(np.sqrt(252)),
        "number_of_trades": len(pnls),
        "win_rate": len(wins) / len(pnls) if pnls else None,
        "loss_rate": len(losses) / len(pnls) if pnls else None,
        "average_win": float(np.mean(wins)) if wins else None,
        "average_loss": float(np.mean(losses)) if losses else None,
        "profit_factor": sum(wins) / abs(sum(losses)) if losses else None,
        "expectancy": float(np.mean(pnls)) if pnls else None,
    }


def run(frame: pd.DataFrame, config: Config, strategy: Strategy | None = None) -> dict:
    if len(frame) < 2:
        raise ValueError("At least two completed daily bars required")
    validate_frame(frame)
    frame = frame.reset_index(drop=True)
    timestamps = pd.to_datetime(frame.timestamp, utc=True)
    if timestamps.duplicated().any() or not timestamps.is_monotonic_increasing:
        raise ValueError("Bars must be unique and chronologically ordered")
    # Yahoo historic OHLC is split-adjusted; dividend cash is excluded consistently.
    signals = (strategy or RuleStrategy(config.strategy)).signals(frame)
    if len(signals) != len(frame) or not signals.isin([0, 1]).all():
        raise ValueError("Strategy must return one binary target per bar")
    cash, qty = config.initial_capital, 0.0
    fee, slip = config.commission_bps / 10000, config.slippage_bps / 10000
    entry_price, entry_fee, entry_date = 0.0, 0.0, ""
    trades, curve = [], []

    def sell(raw_price: float, stamp: str, reason: str):
        nonlocal cash, qty
        price = raw_price * (1 - slip)
        exit_fee = qty * price * fee
        pnl = qty * (price - entry_price) - entry_fee - exit_fee
        cash += qty * price - exit_fee
        trades.append(
            {
                "entry_timestamp": entry_date,
                "exit_timestamp": stamp,
                "quantity": qty,
                "entry_price": entry_price,
                "exit_price": price,
                "fees": entry_fee + exit_fee,
                "net_pnl": pnl,
                "return": pnl / (qty * entry_price + entry_fee),
                "reason": reason,
            }
        )
        qty = 0

    for i, (_, row) in enumerate(frame.iterrows()):
        stamp = timestamps.iloc[i].isoformat()
        target = int(signals.iloc[i - 1]) if i > 0 else 0
        exited = False
        if qty and target == 0:
            sell(row.open, stamp, "signal_next_open")
            exited = True
        if not qty and target == 1 and not exited:
            entry_price = row.open * (1 + slip)
            budget = cash * min(config.position_size, config.max_position_size)
            qty = budget / (entry_price * (1 + fee))
            entry_fee, entry_date = qty * entry_price * fee, stamp
            cash -= qty * entry_price + entry_fee
        if qty:
            stop = entry_price * (1 - config.stop_loss) if config.stop_loss else None
            take = entry_price * (1 + config.take_profit) if config.take_profit else None
            # Gap prices first; if both intrabar barriers touch, pessimistically stop first.
            if stop and row.open <= stop:
                sell(row.open, stamp, "stop_gap")
            elif take and row.open >= take:
                sell(row.open, stamp, "target_gap")
            elif stop and row.low <= stop:
                sell(stop, stamp, "stop")
            elif take and row.high >= take:
                sell(take, stamp, "target")
        curve.append({"timestamp": stamp, "equity": cash + qty * row.close})
    series = pd.Series([x["equity"] for x in curve], index=pd.DatetimeIndex(timestamps))
    dd = series / series.cummax() - 1
    for point, drawdown in zip(curve, dd, strict=True):
        point["drawdown"] = float(drawdown)
    warnings = [
        "Historical research, not a prediction or trade recommendation",
        "Price returns only; dividends excluded; Yahoo OHLC is split-adjusted",
        "Current symbol selection is subject to survivorship bias",
        "Daily bars cannot resolve intrabar execution paths",
    ]
    if len(trades) < 30:
        warnings.append("Small sample: fewer than 30 completed trades")
    if len(frame) < 252:
        warnings.append("Less than one trading year; annualized metrics may be unstable")
    return {
        "metrics": metrics(series, trades, config.initial_capital),
        "equity_curve": curve,
        "trades": trades,
        "open_position": {"quantity": qty, "cash": cash},
        "warnings": warnings,
        "config": config.model_dump(),
        "execution": "close[t] targets execute open[t+1]; terminal position marked, not sold",
    }


class BuyAndHold:
    def signals(self, frame: pd.DataFrame) -> pd.Series:
        return pd.Series(1, index=frame.index)
