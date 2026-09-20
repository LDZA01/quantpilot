import logging
import time
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from apps.api.db import Asset, Job, MarketBar
from packages.market_data.provider import DataUnavailable, MarketDataProvider

logger = logging.getLogger(__name__)


def ingest(
    db: Session,
    provider: MarketDataProvider,
    symbol: str,
    start: date,
    end: date,
    attempts: int = 3,
) -> dict:
    if start >= end:
        raise ValueError("start must precede exclusive end")
    began = time.monotonic()
    job_id = str(uuid4())
    counts = {
        "rows_downloaded": 0,
        "rows_inserted": 0,
        "rows_updated": 0,
        "rows_rejected": 0,
        "rows_unchanged": 0,
    }
    db.add(
        Job(
            id=job_id,
            created_at=datetime.now(UTC),
            kind="ingestion",
            status="running",
            detail={"symbol": symbol},
        )
    )
    db.commit()
    try:
        if db.get_bind().dialect.name == "postgresql":
            db.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
                {"key": f"{provider.name}:{symbol}"},
            )
        stored = list(
            db.scalars(
                select(MarketBar)
                .where(MarketBar.symbol == symbol, MarketBar.provider == provider.name)
                .order_by(MarketBar.timestamp)
            )
        )
        by_date = {r.timestamp.date(): r for r in stored}
        # Extend earlier coverage on demand; normal updates overlap 10 calendar days.
        begin = stored[-1].timestamp.date() - timedelta(days=10) if stored else start
        asset = db.get(Asset, symbol)
        coverage_start = asset.history_start if asset else None
        if stored and (coverage_start is None or start < coverage_start):
            begin = start

        request_end = end
        if stored and (coverage_start is None or start < coverage_start):
            request_end = max(end, stored[0].timestamp.date() + timedelta(days=1))
        if begin >= request_end:
            begin = start

        def fetch(first: date):
            for attempt in range(attempts):
                try:
                    values = provider.get_history(symbol, first, request_end)
                    counts["rows_downloaded"] += len(values)
                    if not values:
                        raise DataUnavailable("Provider returned an empty dataset")
                    return values
                except DataUnavailable as exc:
                    counts["rows_downloaded"] += exc.rows_downloaded
                    counts["rows_rejected"] += exc.rows_rejected
                    if attempt + 1 == attempts:
                        raise
                    time.sleep(min(2**attempt, 8))
            raise DataUnavailable("Provider retry exhausted")

        bars = fetch(begin)
        refresh = False
        for bar in bars:
            previous = by_date.get(bar.timestamp.date())
            if previous:
                old_factor = (
                    previous.adjusted_close / previous.close if previous.adjusted_close else 1
                )
                new_factor = bar.adjusted_close / bar.close if bar.adjusted_close else 1
                if abs(old_factor - new_factor) > 1e-7 or abs(previous.close - bar.close) > 1e-7:
                    refresh = True
            elif bar.splits > 0 or bar.dividends > 0:
                refresh = bool(stored)
        if refresh and stored:
            request_end = max(end, stored[-1].timestamp.date() + timedelta(days=1))
            begin = min(start, stored[0].timestamp.date())
            bars = fetch(begin)
            # Never leave old pre-action history alongside freshly adjusted candles.
            if not set(by_date).issubset({b.timestamp.date() for b in bars}):
                raise DataUnavailable("Corporate-action refresh did not cover stored history")
        keys = set()
        for bar in bars:
            key = bar.timestamp.date()
            if bar.symbol != symbol or bar.provider != provider.name or key in keys:
                counts["rows_rejected"] += 1
                raise DataUnavailable("Duplicate or mismatched normalized candle")
            if not min(start, begin) <= key < request_end:
                counts["rows_rejected"] += 1
                raise DataUnavailable("Provider returned an out-of-range candle")
            keys.add(key)
        metadata = provider.get_asset(symbol)
        metadata["history_start"] = min(start, coverage_start) if coverage_start else start
        db.merge(Asset(**metadata))
        db.flush()
        insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
        for bar in bars:
            values = bar.model_dump()
            previous = by_date.get(bar.timestamp.date())
            if previous is None:
                counts["rows_inserted"] += 1
            elif any(
                getattr(previous, k) != v
                for k, v in values.items()
                if k not in {"timestamp", "symbol", "provider"}
            ):
                counts["rows_updated"] += 1
            else:
                counts["rows_unchanged"] += 1
            stmt = insert(MarketBar).values(**values)
            db.execute(
                stmt.on_conflict_do_update(
                    index_elements=["symbol", "timestamp", "provider"],
                    set_={
                        k: v
                        for k, v in values.items()
                        if k not in {"symbol", "timestamp", "provider"}
                    },
                )
            )
        detail = {
            **counts,
            "symbol": symbol,
            "job_id": job_id,
            "duration_seconds": time.monotonic() - began,
            "start": begin.isoformat(),
            "end_exclusive": request_end.isoformat(),
            "adjustment_refresh": refresh,
        }
        job = db.get(Job, job_id)
        assert job is not None
        job.status, job.detail = "completed", detail
        db.commit()
        logger.info("ingestion_completed", extra={"detail": detail})
        return detail
    except Exception as exc:
        db.rollback()
        job = db.get(Job, job_id)
        assert job is not None
        job.status = "failed"
        job.detail = {
            **counts,
            "rows_inserted": 0,
            "rows_updated": 0,
            "symbol": symbol,
            "error": str(exc),
            "duration_seconds": time.monotonic() - began,
        }
        db.commit()
        logger.exception("ingestion_failed", extra={"detail": job.detail})
        raise DataUnavailable(str(exc)) from exc
