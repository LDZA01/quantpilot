# Data model

| Table | Key | Contents |
| --- | --- | --- |
| `assets` | symbol | Display name, optional sector, USD currency, earliest successfully requested history start |
| `market_bars` | integer id; unique symbol/session/provider | UTC-aware session timestamp, OHLC, nullable adjusted close, 64-bit volume, provider, dividends and splits |
| `pipeline_runs` | UUID string | UTC creation time, job kind/status and JSON counts/error/duration |
| `research_runs` | UUID string | Kind, symbol/watchlist label, input SHA-256, result JSON with parameters, metrics, trades, warnings and provenance |
| `data_snapshots` | SHA-256 | Gzip-compressed canonical JSON inputs, deduplicated across repeated identical research requests |
| `alembic_version` | revision | Deployed schema version |

Bars reference assets. Timestamps use PostgreSQL `TIMESTAMP WITH TIME ZONE`. Yahoo's daily date is normalized to UTC midnight **as a session label**, not an actual midnight execution. Trade entry/exit fields also label sessions; `reason` and execution metadata identify open/intraday semantics. The provider uses the New York date to exclude current sessions, avoiding UTC date rollover mistakes.

Start is inclusive, end exclusive. Normal updates request the most recent stored date minus ten calendar days; earlier coverage is extended only when the requested start predates the successful coverage request. Storing the requested boundary rather than the first returned candle avoids repeated downloads for holidays or pre-listing dates. Historical-range requests are allowed without creating reversed fetch ranges.

All normalized prices must be finite and positive; volume must be a nonnegative integer; OHLC must form a valid envelope. Duplicate/non-session Yahoo rows fail. Provider history retains missing values so they cannot disappear before validation. Missing interior exchange sessions fail provider ingestion rather than pretending multiple days are a single daily return. Leading/trailing availability remains provider-dependent (e.g. listing/delisting); requested and actual research coverage must be reviewed.

Overlap price or adjustment-factor changes and new corporate actions trigger a complete refresh of existing coverage. A refresh that omits an existing stored session fails atomically. The revision detector cannot discover arbitrary corrections outside the overlap. Raw provider payloads are not archived; immutable normalized research inputs are.

Features are not stored as a huge derived table. Scanner/backtest results are versioned run artifacts; trade history is inside each backtest artifact. Portfolio, positions, ML experiments and model-metric tables arrive when their respective features are implemented rather than appearing as unused scaffolding.

Migrations are explicit and reversible: `uv run alembic upgrade head`, `uv run alembic downgrade -1`. Back up the database before downgrading: reversing a schema migration removes that migration's data.
