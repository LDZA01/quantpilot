"""Daily bars use UTC midnight session labels, not fictional execution timestamps."""

from datetime import UTC, date, datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import pandas as pd
import yfinance as yf
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator


class DataUnavailable(RuntimeError):
    def __init__(self, message: str, rows_downloaded: int = 0, rows_rejected: int = 0):
        super().__init__(message)
        self.rows_downloaded = rows_downloaded
        self.rows_rejected = rows_rejected


class Bar(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    adjusted_close: float | None = None
    volume: int
    provider: str = "yfinance"
    dividends: float = 0
    splits: float = 0

    @field_validator("timestamp")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamp must have a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def valid_prices(self) -> "Bar":
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise ValueError("OHLC must be positive")
        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close):
            raise ValueError("invalid OHLC envelope")
        if self.volume < 0 or self.dividends < 0 or self.splits < 0:
            raise ValueError("invalid volume or corporate action")
        if self.adjusted_close is not None and self.adjusted_close <= 0:
            raise ValueError("adjusted close must be positive")
        return self


class MarketDataProvider(Protocol):
    name: str

    def get_history(self, symbol: str, start: date, end: date) -> list[Bar]: ...
    def get_asset(self, symbol: str) -> dict: ...
    def get_quote(self, symbol: str) -> dict: ...
    def get_market_status(self) -> dict: ...


def normalize(symbol: str, frame: pd.DataFrame) -> list[Bar]:
    bars = []
    if frame.empty:
        raise DataUnavailable("Provider returned an empty dataset")
    calendar = xcals.get_calendar("XNYS", start="1990-01-01")
    for index, row in frame.iterrows():
        session = pd.Timestamp(str(index)).date()
        if not calendar.is_session(pd.Timestamp(session)):
            raise DataUnavailable(f"Non-session candle: {session}")
        bars.append(
            Bar(
                symbol=symbol,
                timestamp=datetime.combine(session, datetime.min.time(), UTC),
                open=row["Open"],
                high=row["High"],
                low=row["Low"],
                close=row["Close"],
                adjusted_close=row.get("Adj Close"),
                volume=row["Volume"],
                dividends=row.get("Dividends", 0),
                splits=row.get("Stock Splits", 0),
            )
        )
    if len({b.timestamp for b in bars}) != len(bars):
        raise DataUnavailable("Duplicate provider candles")
    return sorted(bars, key=lambda bar: bar.timestamp)


class YahooProvider:
    name = "yfinance"

    def get_history(self, symbol: str, start: date, end: date) -> list[Bar]:
        # Exclude the current exchange date, even after close, to avoid provisional bars.
        end = min(end, datetime.now(ZoneInfo("America/New_York")).date())
        try:
            frame = yf.Ticker(symbol).history(
                start=start.isoformat(),
                end=end.isoformat(),
                interval="1d",
                auto_adjust=False,
                actions=True,
                raise_errors=True,
                timeout=20,
                keepna=True,
            )
            if frame.empty:
                raise DataUnavailable(f"No data returned for {symbol}")
            try:
                bars = normalize(symbol, frame)
            except (ValidationError, DataUnavailable, KeyError) as exc:
                raise DataUnavailable(str(exc), len(frame), 1) from exc
            expected = xcals.get_calendar("XNYS", start="1990-01-01").sessions_in_range(
                pd.Timestamp(bars[0].timestamp.date()), pd.Timestamp(bars[-1].timestamp.date())
            )
            missing = set(expected.date) - {b.timestamp.date() for b in bars}
            if missing:
                raise DataUnavailable(f"Missing market sessions: {sorted(missing)[:5]}", len(frame))
            return bars
        except DataUnavailable:
            raise
        except Exception as exc:
            raise DataUnavailable(f"Provider history unavailable for {symbol}: {exc}") from exc

    def get_asset(self, symbol: str) -> dict:
        try:
            data = yf.Ticker(symbol).get_info()
            if data.get("currency") != "USD" or data.get("exchange") not in {
                "NMS",
                "NYQ",
                "NGM",
                "NCM",
                "ASE",
                "PCX",
                "BTS",
            }:
                raise DataUnavailable("Only USD US-listed instruments supported")
            return {
                "symbol": symbol,
                "name": data.get("shortName", symbol),
                "sector": data.get("sector"),
                "currency": "USD",
            }
        except Exception as exc:
            raise DataUnavailable(f"Asset metadata unavailable: {exc}") from exc

    def get_quote(self, symbol: str) -> dict:
        today = datetime.now(UTC).date()
        bar = self.get_history(symbol, today - timedelta(days=14), today)[-1]
        return {
            "symbol": symbol,
            "price": bar.close,
            "timestamp": bar.timestamp,
            "kind": "last completed daily close, not live",
        }

    def get_market_status(self) -> dict:
        now = pd.Timestamp.now(tz="UTC").floor("min")
        return {
            "open": bool(xcals.get_calendar("XNYS").is_open_on_minute(now)),
            "timestamp": now.isoformat(),
            "calendar": "XNYS",
        }
