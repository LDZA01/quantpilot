import numpy as np
import pandas as pd

from packages.market_data.validation import validate_frame


def wilder(values: pd.Series, period: int) -> pd.Series:
    """Wilder smoothing seeded with the first complete simple average."""
    result = pd.Series(np.nan, index=values.index)
    seed = values.rolling(period).mean().first_valid_index()
    if seed is None:
        return result
    offset = int(np.flatnonzero(values.index == seed)[0])
    result.iloc[offset] = values.iloc[offset - period + 1 : offset + 1].mean()
    for i in range(offset + 1, len(values)):
        result.iloc[i] = (result.iloc[i - 1] * (period - 1) + values.iloc[i]) / period
    return result


def features(frame: pd.DataFrame) -> pd.DataFrame:
    """Causal features on Yahoo split-adjusted OHLC; dividends excluded."""
    validate_frame(frame)
    f = frame.copy().reset_index(drop=True)
    c, v = f.close, f.volume
    f["returns"] = c.pct_change(fill_method=None)
    f["log_returns"] = np.log(c / c.shift(1))
    for n in (20, 50):
        f[f"sma{n}"] = c.rolling(n).mean()
        f[f"distance_sma{n}"] = c / f[f"sma{n}"] - 1
    f["ema20"] = c.ewm(span=20, adjust=False, min_periods=20).mean()
    delta = c.diff()
    gain, loss = wilder(delta.clip(lower=0), 14), wilder(-delta.clip(upper=0), 14)
    f["rsi"] = 100 - 100 / (1 + gain / loss)
    f.loc[(loss == 0) & (gain > 0), "rsi"] = 100
    f.loc[(loss == 0) & (gain == 0), "rsi"] = 50
    f["macd"] = (
        c.ewm(span=12, adjust=False, min_periods=12).mean()
        - c.ewm(span=26, adjust=False, min_periods=26).mean()
    )
    f["macd_signal"] = f.macd.ewm(span=9, adjust=False, min_periods=9).mean()
    f["macd_histogram"] = f.macd - f.macd_signal
    tr = pd.concat(
        [f.high - f.low, (f.high - c.shift()).abs(), (f.low - c.shift()).abs()], axis=1
    ).max(axis=1)
    f["atr"] = wilder(tr, 14)
    f["bollinger_upper"] = f.sma20 + 2 * c.rolling(20).std(ddof=0)
    f["bollinger_lower"] = f.sma20 - 2 * c.rolling(20).std(ddof=0)
    f["volatility"] = f.returns.rolling(20).std(ddof=1) * np.sqrt(252)
    f["volume_sma20"] = v.rolling(20).mean()
    f["relative_volume"] = v / v.shift().rolling(20).mean().replace(0, np.nan)
    f["rolling_high20"] = f.high.rolling(20).max()
    f["rolling_low20"] = f.low.rolling(20).min()
    f["prior_high20"] = f.high.shift().rolling(20).max()
    f["drawdown"] = c / c.cummax() - 1
    f["momentum20"] = c.pct_change(20, fill_method=None)
    # Daily approximation, explicitly not intraday execution VWAP.
    typical = (f.high + f.low + c) / 3
    f["daily_vwap_proxy20"] = (typical * v).rolling(20).sum() / v.rolling(20).sum()
    return f.replace([np.inf, -np.inf], np.nan)
