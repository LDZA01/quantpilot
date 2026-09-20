import json
import logging
import time
from datetime import UTC, date, datetime
from typing import Annotated
from uuid import uuid4

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from apps.api.config import settings
from apps.api.db import Asset, Job, MarketBar, ResearchRun, session
from apps.api.snapshots import restore_snapshot, save_snapshot
from packages.backtest.engine import BuyAndHold, Config, run
from packages.market_data.provider import DataUnavailable, YahooProvider
from packages.quant.features import features
from packages.quant.scanner import scan
from pipelines.ingest import ingest


class JsonLog(logging.Formatter):
    def format(self, record):
        value = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "detail": getattr(record, "detail", None),
        }
        if record.exc_info:
            value["exception"] = self.formatException(record.exc_info)
        return json.dumps(value)


handler = logging.StreamHandler()
handler.setFormatter(JsonLog())
logging.basicConfig(handlers=[handler], level=settings().log_level, force=True)
app = FastAPI(title="QuantPilot", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings().cors_origin],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
DB = Annotated[Session, Depends(session)]
Symbol = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9.\-]{0,14}$")]


@app.middleware("http")
async def request_log(request: Request, call_next):
    started = time.monotonic()
    response = await call_next(request)
    logging.getLogger("http").info(
        "request",
        extra={
            "detail": {
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_seconds": time.monotonic() - started,
            }
        },
    )
    return response


@app.exception_handler(DataUnavailable)
async def unavailable(request, exc):
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now(UTC)}


@app.get("/ready")
def ready(db: DB):
    try:
        revision = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
        if revision != "0002":
            raise RuntimeError("Migration mismatch")
        return {"status": "ready", "revision": revision}
    except Exception:
        db.rollback()
        raise HTTPException(503, "Database unavailable or migrations required") from None


class IngestRequest(BaseModel):
    symbol: Symbol
    start: date = date(2020, 1, 1)
    end: date = Field(default_factory=lambda: datetime.now(UTC).date())

    @model_validator(mode="after")
    def dates(self):
        if self.start >= self.end or self.start < date(1990, 1, 1):
            raise ValueError("Require 1990-01-01 <= start < end")
        return self


@app.post("/ingest")
def ingest_data(body: IngestRequest, db: DB):
    return ingest(
        db, YahooProvider(), body.symbol, body.start, body.end, settings().ingestion_attempts
    )


@app.get("/assets")
def assets(db: DB):
    return [
        {"symbol": a.symbol, "name": a.name, "sector": a.sector, "currency": a.currency}
        for a in db.scalars(select(Asset).order_by(Asset.symbol))
    ]


def load(db: Session, symbol: str, start: date | None = None, end: date | None = None):
    query = select(MarketBar).where(MarketBar.symbol == symbol, MarketBar.provider == "yfinance")
    if start:
        query = query.where(
            MarketBar.timestamp >= datetime.combine(start, datetime.min.time(), UTC)
        )
    if end:
        query = query.where(MarketBar.timestamp < datetime.combine(end, datetime.min.time(), UTC))
    records = list(db.scalars(query.order_by(MarketBar.timestamp)))
    if not records:
        raise HTTPException(404, f"No stored bars for {symbol}; ingest completed sessions first")
    rows = [
        {c.name: getattr(r, c.name) for c in MarketBar.__table__.columns if c.name != "id"}
        for r in records
    ]
    frame = pd.DataFrame(rows)
    frame["timestamp"] = pd.to_datetime(frame.timestamp, utc=True)
    return frame


def records(frame: pd.DataFrame):
    return json.loads(frame.to_json(orient="records", date_format="iso"))


@app.get("/bars/{symbol}")
def bars(symbol: Symbol, db: DB, limit: int = Query(500, ge=1, le=10000)):
    return records(load(db, symbol).tail(limit))


@app.get("/features/{symbol}")
def get_features(symbol: Symbol, db: DB):
    frame = features(load(db, symbol))
    return {
        "symbol": symbol,
        "latest": records(frame.tail(1))[0],
        "basis": "split-adjusted OHLC, price returns; dividends excluded",
    }


def persist(db: Session, kind: str, symbol: str, frame: pd.DataFrame, result: dict):
    digest = save_snapshot(db, frame)
    ident = str(uuid4())
    result.update(
        {
            "id": ident,
            "data_hash": digest,
            "engine_version": "0.1.0",
            "created_at": datetime.now(UTC).isoformat(),
        }
    )
    db.add(
        ResearchRun(
            id=ident,
            created_at=datetime.now(UTC),
            kind=kind,
            symbol=symbol,
            data_hash=digest,
            result=result,
        )
    )
    db.commit()
    return result


class ScanRequest(BaseModel):
    symbols: list[Symbol] = Field(min_length=1, max_length=50)


@app.post("/scanner")
def scanner(body: ScanRequest, db: DB):
    outputs, failures, frames = [], [], []
    for symbol in dict.fromkeys(body.symbols):
        try:
            frame = load(db, symbol)
            frames.append(frame)
            if len(frame) < 50:
                failures.append({"symbol": symbol, "detail": "At least 50 bars needed"})
            outputs.extend(scan(symbol, frame))
        except HTTPException as exc:
            failures.append({"symbol": symbol, "detail": exc.detail})
    combined = pd.concat(frames) if frames else pd.DataFrame()
    return persist(
        db,
        "scanner",
        "WATCHLIST",
        combined,
        {"results": outputs, "failures": failures, "symbols": body.symbols},
    )


class BacktestRequest(Config):
    symbol: Symbol
    start: date | None = None
    end: date | None = None

    @model_validator(mode="after")
    def dates(self):
        if self.start and self.end and self.start >= self.end:
            raise ValueError("start must precede exclusive end")
        return self


@app.post("/backtests")
def backtest(body: BacktestRequest, db: DB):
    frame = load(db, body.symbol, body.start, body.end)
    cfg = Config(**body.model_dump())
    try:
        result = run(frame, cfg)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    result["symbol"] = body.symbol
    result["requested_range"] = {"start": str(body.start), "end": str(body.end)}
    result["benchmark"] = None
    try:
        spy = load(db, "SPY")
        spy = spy[spy.timestamp.isin(frame.timestamp)].reset_index(drop=True)
        if list(spy.timestamp) != list(frame.timestamp):
            result["warnings"].append("SPY benchmark unavailable: session coverage mismatch")
        else:
            benchmark_cfg = cfg.model_copy(
                update={
                    "stop_loss": None,
                    "take_profit": None,
                    "position_size": 1,
                    "max_position_size": 1,
                }
            )
            result["benchmark"] = run(spy, benchmark_cfg, BuyAndHold())
            result["benchmark"]["data_hash"] = save_snapshot(db, spy)
    except HTTPException:
        result["warnings"].append("SPY benchmark unavailable: ingest SPY first")
    return persist(db, "backtest", body.symbol, frame, result)


@app.get("/runs")
def runs(db: DB, kind: str = "backtest"):
    return [
        {
            "id": r.id,
            "symbol": r.symbol,
            "created_at": r.created_at.replace(tzinfo=UTC)
            if r.created_at.tzinfo is None
            else r.created_at,
            "kind": r.kind,
        }
        for r in db.scalars(
            select(ResearchRun)
            .where(ResearchRun.kind == kind)
            .order_by(ResearchRun.created_at.desc())
            .limit(50)
        )
    ]


@app.get("/runs/{ident}")
def get_run(ident: str, db: DB):
    obj = db.get(ResearchRun, ident)
    if not obj:
        raise HTTPException(404, "Research run not found")
    return obj.result


@app.get("/jobs")
def jobs(db: DB):
    return [
        {
            "id": j.id,
            "created_at": j.created_at.replace(tzinfo=UTC)
            if j.created_at.tzinfo is None
            else j.created_at,
            "status": j.status,
            "detail": j.detail,
        }
        for j in db.scalars(select(Job).order_by(Job.created_at.desc()).limit(50))
    ]


@app.post("/runs/{ident}/reproduce")
def reproduce(ident: str, db: DB):
    saved = db.get(ResearchRun, ident)
    if saved is None or saved.kind != "backtest":
        raise HTTPException(404, "Backtest run not found")
    if saved.result.get("engine_version") != "0.1.0":
        raise HTTPException(409, "Run requires a different engine version")
    try:
        result = run(restore_snapshot(db, saved.data_hash), Config(**saved.result["config"]))
        benchmark = saved.result.get("benchmark")
        if benchmark:
            result["benchmark"] = run(
                restore_snapshot(db, benchmark["data_hash"]),
                Config(**benchmark["config"]),
                BuyAndHold(),
            )
        matches = all(
            result[key] == saved.result[key]
            for key in ("metrics", "equity_curve", "trades", "open_position")
        )
        if benchmark:
            matches = matches and result["benchmark"]["metrics"] == benchmark["metrics"]
        return {"original_id": ident, "matches": matches, "result": result}
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
