"""Validation at the research boundary, including direct package callers."""

import numpy as np
import pandas as pd


def validate_frame(frame: pd.DataFrame) -> None:
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    if not required.issubset(frame.columns) or frame.empty:
        raise ValueError("Nonempty OHLCV data with timestamps required")
    times = pd.to_datetime(frame.timestamp)
    if times.dt.tz is None or times.isna().any():
        raise ValueError("Explicit timezone-aware timestamps required")
    if times.duplicated().any() or not times.is_monotonic_increasing:
        raise ValueError("Bars must be unique and chronologically ordered")
    prices = frame[["open", "high", "low", "close"]]
    if not np.isfinite(prices.to_numpy()).all() or (prices <= 0).any().any():
        raise ValueError("OHLC must be finite and positive")
    if (frame.low > prices[["open", "close"]].min(axis=1)).any() or (
        frame.high < prices[["open", "close"]].max(axis=1)
    ).any():
        raise ValueError("Invalid OHLC envelope")
    if not np.isfinite(frame.volume).all() or (frame.volume < 0).any():
        raise ValueError("Volume must be finite and nonnegative")
