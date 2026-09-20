# First milestone: phases 1–5
1. Foundation: locked Python/Node dependencies, FastAPI settings/logs/health, SQLAlchemy/Alembic, Compose and Next.js.
2. Data: validated daily US bars, provider protocol/yfinance, incremental transactional upserts, adjustment-revision refresh and job audit.
3. Features: transparent causal calculations with warm-up nulls and regression tests.
4. Scanner: deterministic rule evidence and documented score, persisted runs.
5. Backtest: long-only single-asset strategies, next-open fills, costs, conservative stop/target rules, metrics and aligned SPY comparison.
6. Integrate dashboard and CLI; run financial, API, migration and frontend checks.

Risks: Yahoo data has no availability SLA, may revise history and is not point-in-time; daily prices cannot resolve intrabar paths; current watchlists are survivorship biased. Docker daemon unavailable at initial inspection. SQLite tests do not replace PostgreSQL validation.

Dependency policy: Python >=3.12; resolve bounded stable major versions to uv.lock; Next.js 16 / React 19 via npm lock. Pandas used for explicit rolling calculations and yfinance interoperability. Polars/DuckDB deferred until analytical volume justifies two additional execution engines.

## Milestone outcome

Implemented the six steps above, including the API/dashboard vertical slices and reproducible snapshot replay. Docker later became available and both application images, migrations, PostgreSQL integration tests and a real AAPL/SPY ingestion/backtest workflow were exercised. See `verification.md` for exact checks and remaining browser QA. The next implementation milestone is Phase 6 strategy validation, not expansion into unvalidated ML signals.
