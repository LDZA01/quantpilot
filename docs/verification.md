# Milestone 1 verification

Verification date: 2026-09-20. This records executed checks separately from planned features.

## Executed successfully

- **41 tests passed** on Homebrew Python 3.13 with SQLite: financial calculations, causal indicators, next-open execution, position sizing, costs, stops/targets, drawdowns, normalization, retries, revision refresh, atomic failures, snapshots and API persistence.
- **41 tests passed** against PostgreSQL 17 in isolated, automatically removed schemas (`TEST_DATABASE_URL`). The PostgreSQL run found a failed-readiness transaction cleanup issue; the API now rolls back before returning 503.
- Ruff lint/format and mypy for backend/shared modules; ESLint, TypeScript and Prettier for the web app.
- Next.js 16.3.5 production build with Webpack, both locally and in the Node 22 Alpine Docker build.
- Docker Compose configuration, API/web image builds and `docker compose up -d --build --wait`.
- PostgreSQL schema migrations and `alembic check` (no ungenerated schema changes).
- SQLite migration upgrade, schema check, downgrade to base and fresh upgrade, using a disposable `/tmp` database.
- API `/health`, `/ready`, `/assets`, `/jobs`: HTTP 200 through the running Compose service.
- Web service HTTP 200 with the server-rendered overview present. This is an HTTP/render check, not interactive browser QA.
- Real Yahoo provider ingestion, **2023-01-01 inclusive to 2024-01-01 exclusive**: 250 AAPL bars and 250 SPY bars, no rejected rows. These are genuine historical provider responses, not synthetic dashboard seed data.
- Repeated live ingestion inserted zero duplicate rows. Yahoo returned revised adjusted-close values; the SPY overlap triggered a full adjustment refresh, and both symbols retained 250 unique sessions.
- Scanner run and AAPL SMA crossover backtest with an exactly aligned SPY benchmark; saved-input replay returned `matches: true`. No inference about future strategy profitability follows from this smoke test.

## Reproduce

```sh
make install
make check

docker compose up -d --build --wait
docker compose exec -T api alembic check
uv run python scripts/smoke.py
# Explicitly ingest real historical data and run scanner/backtest/replay:
uv run python scripts/smoke.py --live
# Uses temporary, isolated schemas in the supplied PostgreSQL database:
TEST_DATABASE_URL=postgresql+psycopg://quantpilot:quantpilot@localhost:5432/quantpilot uv run pytest -q
```

The live smoke check requires provider/network availability and intentionally fails if external data is unavailable. Unit/integration tests do not require Yahoo. Tests never put synthetic bars into the application's public schema.

## Environment issues and remaining verification

- Docker was initially stopped/inaccessible; after it became available, full container/PostgreSQL verification was completed.
- The initially selected Anaconda Python 3.12 crashed while pytest imported readline. Switching the project virtual environment to installed Homebrew Python 3.13 resolved the runner crash.
- Turbopack could not bind its worker port in this managed environment. The project uses the supported Webpack production build instead, which passed.
- The Browser skill reported no available browser and an empty connection list. Interactive browser behavior, responsive visual appearance and screenshot QA therefore remain **unverified**. README screenshot entries are placeholders.
- Two upstream deprecation warnings appear in FastAPI/Starlette's httpx/AnyIO test-client integration; tests pass. ESLint 9 is pinned through the lockfile and emitted an upstream maintenance/deprecation notice; npm installation reported zero known vulnerabilities at verification time.
- This milestone does not verify out-of-sample statistical validity, portfolio accounting, ML, AI explanations or trading; those are not implemented yet.
