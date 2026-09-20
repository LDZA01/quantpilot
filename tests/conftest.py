import os
from uuid import uuid4

os.environ["DATABASE_URL"] = "sqlite://"

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from apps.api.db import Base


@pytest.fixture
def db():
    postgres_url = os.environ.get("TEST_DATABASE_URL")
    if postgres_url:
        schema = "quantpilot_test_" + uuid4().hex
        admin = create_engine(postgres_url)
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(postgres_url, connect_args={"options": f"-csearch_path={schema}"})
    else:
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()
        if postgres_url:
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin.dispose()


@pytest.fixture
def frame():
    """Synthetic TEST-ONLY series, never served as market data."""
    close = np.arange(100.0, 200.0)
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2023-01-03", periods=100, freq="B", tz="UTC"),
            "open": close,
            "high": close + 2,
            "low": close - 2,
            "close": close,
            "volume": 1000,
        }
    )
