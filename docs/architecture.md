# Architecture and decisions

## Vertical slice

Browser → FastAPI → SQLAlchemy/PostgreSQL. The API runs the same provider, feature, scanner and backtest Python modules used by tests. The HTTP CLI avoids duplicating persistence or research logic. Ingestion is synchronous in FastAPI's worker thread pool; no fake progress or background success is returned. JSON logs record request durations and ingestion counts/failures.

## Decisions

1. **Monorepo and ordinary modules.** Shared Python namespaces avoid six independently versioned distributions. Python dependencies are fixed by `uv.lock`; npm dependencies by `apps/web/package-lock.json`. Python 3.13/Node 22 are the tested runtime choices; the backend's declared minimum is Python 3.12.
2. **Pandas for V1.** Rolling financial calculations are transparent and the provider already returns Pandas. A second frame engine and DuckDB would not improve correctness at personal daily-data scale; add them with measured need. SciPy/statsmodels belong with Phase 6 validation; scikit-learn with Phase 7.
3. **Provider protocol.** `MarketDataProvider` describes history, asset, last completed quote and calendar status. Yahoo is the sole implemented adapter. Polygon/Alpaca/IB adapters must normalize currency, session timestamps and price basis before reuse. Broker execution is a separate later interface.
4. **PostgreSQL as source of stored market history.** `(symbol, timestamp, provider)` is unique. An ingestion transaction holds a PostgreSQL per-provider/symbol advisory lock. Upserts and audit completion commit together. Failure rolls back bars and records a failed job in a fresh transaction. SQLite is for isolated development/tests and not concurrent ingestion.
5. **Corporate actions and price basis.** Yahoo's split-adjusted OHLC is used consistently; adjusted close is retained but not substituted into OHLC. Overlap revisions/new corporate actions request complete existing history atomically. Partial refreshes fail. Dividends are excluded from backtest P&L and benchmark alike. Consult [Yahoo's adjustment definition](https://help.yahoo.com/kb/SLN28256.html) and [yfinance history implementation](https://github.com/ranaroussi/yfinance/blob/main/yfinance/scrapers/history.py).
6. **No fake availability.** Live provider failure is an error. Empty and invalid histories fail. Indicator warm-up values are JSON null. Missing benchmark means null plus a reason. Readiness verifies the database migration head; liveness is independent.
7. **Reproducible research.** Every run includes its parameters, engine version, UTC creation time and SHA-256 input identity. Input JSON preserves float precision, is compressed and deduplicated by hash. Replay reads snapshots rather than mutable market bars. Input hash integrity is checked before replay. Pinning the engine/dependencies and retaining repository revisions is still necessary for bit-for-bit reproducibility across future releases.
8. **Derived data on demand.** Indicators and raw strategy signals are not materialized. Run results, curves and trades live in an auditable JSON artifact for this single-user MVP; relational trade/model tables can be introduced when cross-run querying warrants them.
9. **Local security boundary.** Loopback-only Compose host ports, unprivileged application containers, narrow CORS, validated symbol/range/cost inputs and no secrets committed. This is not an authenticated hosted service. Future live broker credentials/order handling require separate design and risk controls; no live adapter exists.
10. **Frontend.** Responsive research workspace with real empty/loading/error states, symbol library, price/volume charts, feature inspection, rule explanations, backtest equity/drawdown/metrics/trades and job audit. Portfolio/ML screens are deliberately deferred to their functional milestones. Recharts renders data returned by the API; there are no seeded dashboard values.

## Operations

`docker compose up --build` orders PostgreSQL health → migrations/API readiness → web. `docker compose logs -f api` emits JSON request/job diagnostics. `GET /jobs` reports ingestion rows downloaded/inserted/updated/rejected/unchanged and duration. Retries back off 1 then 2 seconds with the default three attempts; provider rate-limit errors use the same bounded retry. A failed batch never reports committed inserts. Invalid provider rows reject the whole batch rather than silently repair prices.

A process crash may leave an ingestion job `running`; inspect container logs, verify no ingestion process is active, and retry the idempotent request. Automatic crash recovery, scheduling and progress events are later operational work. Large histories/watchlists can block an HTTP request for minutes; do not use many concurrent requests as a work queue.

## Future boundaries

Portfolio positions/transactions must use explicit currency and corporate-action semantics independent of split-adjusted research share units. ML consumes immutable feature/label snapshots, uses chronological partitions and emits calibrated probabilities only. AI receives structured evidence and must state unavailable fields. A future Broker protocol must enforce position/order/daily-loss limits, idempotency and a kill switch before any live integration. No placeholder live-order endpoint is exposed.
