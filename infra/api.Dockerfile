FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.9.18 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY apps/api apps/api
COPY apps/__init__.py apps/__init__.py
COPY packages packages
COPY pipelines pipelines
COPY infra/migrations infra/migrations
COPY alembic.ini ./
RUN useradd --create-home researcher && chown -R researcher:researcher /app
USER researcher
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn apps.api.main:app --host 0.0.0.0 --port 8000"]
