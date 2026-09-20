# QuantPilot

**AI-Assisted Quantitative Research & Portfolio Analytics Platform** — a locally runnable personal research workspace. This first milestone implements **Phases 1–5**: daily market data, explainable features, deterministic scanners and cost-aware backtests, with a Next.js dashboard and FastAPI API.

It does not make BUY/SELL recommendations, promise returns, fabricate prices or use an LLM to produce confidence scores. Portfolio accounting, statistical validation, ML, AI explanations and paper trading are subsequent milestones, not enabled features.

## Run

Prerequisites: Docker Engine/Desktop with Compose and internet access for image/dependency downloads. No paid API key is needed.

```sh
cp .env.example .env
make dev
# Equivalent: docker compose up --build
```

- Dashboard: http://localhost:3000
- API / interactive documentation: http://localhost:8000/docs
- Liveness: http://localhost:8000/health
- Database/migration readiness: http://localhost:8000/ready

The API applies Alembic migrations before starting. PostgreSQL persists in the `postgres_data` Compose volume. Services bind to **127.0.0.1**. `docker compose down` preserves data. Local default credentials are development credentials, not a public deployment configuration. Do not expose this unauthenticated personal workspace to the internet.

## First research workflow

Use **Overview → Ingest data**, or the CLI after installing Python dependencies:

```sh
uv sync --frozen
uv run python -m pipelines.cli ingest AAPL NVDA SPY QQQ --start 2020-01-01
uv run python -m pipelines.cli scan AAPL NVDA
uv run python -m pipelines.cli backtest AAPL --strategy sma_crossover
```

Without local Python, call the API:

```sh
curl -f http://localhost:8000/ingest -H 'Content-Type: application/json' \
  -d '{"symbol":"AAPL","start":"2020-01-01"}'
curl -f http://localhost:8000/ingest -H 'Content-Type: application/json' \
  -d '{"symbol":"SPY","start":"2020-01-01"}'
curl -f http://localhost:8000/scanner -H 'Content-Type: application/json' \
  -d '{"symbols":["AAPL","SPY"]}'
curl -f http://localhost:8000/backtests -H 'Content-Type: application/json' \
  -d '{"symbol":"AAPL","strategy":"sma_crossover","initial_capital":10000,"commission_bps":5,"slippage_bps":5,"position_size":0.95,"max_position_size":1,"stop_loss":0.08,"take_profit":0.2}'
```

Supported strategies: `sma_crossover`, `rsi_mean_reversion`, `momentum`, `breakout`. Omit stop/target or set them to `null` to disable. `start` is inclusive and `end` exclusive. The first test bar starts in cash; indicators warm up inside the selected period. SPY comparison is included only when stored data covers exactly the same sessions.

Saved runs: `GET /runs`, `GET /runs/{id}`. Replay immutable inputs with `POST /runs/{id}/reproduce`; `matches` compares the recalculated results to the saved run. Historical Yahoo revisions do not overwrite these research inputs.

An empty dashboard is intentional until ingestion succeeds. Provider errors return HTTP 502 and appear in **Settings → Ingestion activity** (`GET /jobs`). There is no generated-data fallback.

## Local development

Python 3.12+ (3.13 selected in `.python-version`), uv, Node 22+, npm and PostgreSQL 17:

```sh
make install
cp .env.example .env
# Start only PostgreSQL:
docker compose up -d db
make migrate
# In separate terminals:
make api
make web
```

For isolated API experimentation without PostgreSQL, SQLite is supported as a **development/test adapter**:

```sh
DATABASE_URL=sqlite:///./quantpilot.db uv run alembic upgrade head
DATABASE_URL=sqlite:///./quantpilot.db uv run uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
```

Use a single API worker with SQLite. PostgreSQL is the intended persistent deployment database and supplies advisory locks for same-symbol ingestion. If an Anaconda interpreter crashes on this machine, use `uv sync --python /opt/homebrew/bin/python3.13` to select Homebrew Python explicitly.

## Environment variables

| Variable | Default / purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL SQLAlchemy URL; overridden to the internal `db` hostname by Compose |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Local Compose PostgreSQL credentials/database, all `quantpilot` by default |
| `CORS_ORIGIN` | `http://localhost:3000`; exact permitted web origin |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000`; browser-visible API address, embedded at web build time |
| `INGESTION_ATTEMPTS` | 3; bounded exponential retry for provider history requests |
| `LOG_LEVEL` | `INFO`; JSON application/request/job logs |

Never commit `.env` or provider/broker credentials. Passwords containing URL-reserved characters must be URL-encoded in manually configured connection URLs. No broker or LLM secret is required or consumed by this milestone.

## Architecture and technology

```text
apps/api                FastAPI, Pydantic settings, SQLAlchemy, research snapshots
apps/web                Next.js 16, TypeScript, Tailwind 4, Recharts
packages/market_data    Provider protocol, yfinance, OHLCV validation
packages/quant          Causal indicators and deterministic scanner
packages/backtest       Strategy interface, simulator, metrics
packages/{portfolio,ml,ai}  Reserved namespaces; later milestones
pipelines               Ingestion and HTTP CLI
infra                   Dockerfiles and Alembic migrations
scripts                 Integration verification helpers
tests                   Synthetic test fixtures only; no production seed data
docs                    Architecture, methodology, assumptions, verification
```

NumPy/Pandas provide transparent numerical operations and direct yfinance interoperability. PostgreSQL stores bars and research artifacts. Features are computed on demand. Deduplicated gzip JSON snapshots preserve backtest inputs. No TA-Lib, paid data feed, Redis, background-worker cluster or deep learning is required. Polars, DuckDB, scipy, statsmodels and scikit-learn will be introduced when the associated analytical/validation/ML workloads require them.

See [architecture](docs/architecture.md), [data model](docs/data-model.md), [feature formulas and scanner rules](docs/features.md), [backtesting](docs/backtesting.md), and [ML methodology](docs/ml-methodology.md).

## Tests and quality checks

```sh
make test
make lint
make check  # tests, Ruff, mypy, ESLint, TypeScript, Prettier and production build
```

Python tests cover returns, indicator warm-up/causality, RSI/ATR seeding, scanner determinism, position sizing, costs, next-bar fills, stops/targets, drawdowns, provider normalization, retries, revisions, incremental upserts, transactional failure reporting, API persistence and snapshot replay. Financial fixtures are explicitly synthetic and confined to tests.

Frontend production builds use Webpack because this managed macOS environment blocks Turbopack's local worker port. This changes the bundler, not the application behavior. API tests use SQLite by default; [verification](docs/verification.md) records deployment checks separately.

## Screenshots

Placeholder: add `docs/screenshots/overview.png`, `scanner.png` and `backtest.png` after browser-based visual QA with successfully ingested data. Do not substitute mock financial numbers or claim screenshots are live results.

## Limitations

- Daily US-listed USD instruments only. Yahoo is a development provider without an availability SLA; its terms and personal-use restrictions apply. Data is revised, not point-in-time.
- OHLC is split-adjusted; `adjusted_close` is retained separately. Features and backtests use **price returns excluding dividends**, consistently for the asset and SPY. They are not total-return simulations.
- Corporate-action overlap detection triggers a full refresh. Arbitrary corrections outside the overlap may not be detected; ingestion is not a point-in-time institutional data warehouse.
- Current-session candles are excluded even after the close. Scanner results show their data timestamp and may be stale. Earnings dates are explicitly unavailable.
- Long-only, one symbol per backtest, fractional shares, no borrowing or leverage. Position caps apply at entry; weights can drift. No liquidity/market-impact model, taxes, cash interest, limit-order queue or partial fills.
- Daily stop/target ordering is unknowable; stop-first is the conservative default when both are touched. Risk statistics assume 252 sessions/year and zero risk-free rate.
- Survivorship bias remains when users choose today's symbols. Baseline results are in-sample historical research, not statistically validated investment strategies.
- Ingestion is synchronous and intended for a small personal watchlist. An interrupted process can leave a job marked `running`; see operational notes.
- No authentication, multi-user authorization, portfolio engine, ML, AI analyst or broker is included in this first milestone.

## Exact next milestone

**Phase 6 — Strategy validation:** explicit chronological train/validation/final-test ranges; purged boundaries where targets overlap; walk-forward evaluation; a locked final-test evaluation record; in-sample/validation/out-of-sample comparison reports; small-sample, instability and degradation warnings; tests proving no tuning reads final-test observations.

Following that: portfolio accounting/risk (Phase 8 priority), probability-based ML with baseline/calibration comparisons (Phase 7), expanded dashboard, optional evidence-bound AI, then guarded simulated paper brokerage. No live automatic trading is planned for V1.

PostgreSQL-specific regression checks can use isolated test schemas:

```sh
TEST_DATABASE_URL=postgresql+psycopg://quantpilot:quantpilot@localhost:5432/quantpilot uv run pytest -q
```

For runtime verification, `uv run python scripts/smoke.py` checks health and read endpoints. Add `--live` to ingest real AAPL/SPY history for 2023, scan it, run an aligned backtest and verify snapshot replay. See [executed verification and blockers](docs/verification.md).
