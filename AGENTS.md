# QuantPilot engineering rules
Scope: personal quantitative research; no trade recommendations or return guarantees.
Use timezone-aware UTC timestamps; daily bars identify the US exchange session by its date.
Never silently synthesize provider data. Synthetic fixtures belong only in tests.
Keep feature calculations causal; execute close-derived signals at the following open.
Record costs, assumptions, data hashes and strategy parameters in persisted research runs.
Never tune on final test data. Do not introduce live trading.
Run pytest, Ruff, mypy, frontend lint/typecheck/build after relevant changes.
PostgreSQL is the deployment database; SQLite is a local test adapter only.
Use exact dependency lockfiles. No secrets or generated datasets in git.
