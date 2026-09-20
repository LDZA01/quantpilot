"""Content-addressed, compressed research inputs preserve data across provider revisions."""

import gzip
import hashlib
import json

import pandas as pd
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from apps.api.db import DataSnapshot


def save_snapshot(db: Session, frame: pd.DataFrame) -> str:
    serial = frame.copy()
    if "timestamp" in serial:
        serial["timestamp"] = pd.to_datetime(serial.timestamp, utc=True).map(
            lambda x: x.isoformat()
        )
    serial = serial.astype(object).where(pd.notna(serial), None)
    payload = json.dumps(
        serial.to_dict(orient="records"), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    digest = hashlib.sha256(payload).hexdigest()
    insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    db.execute(
        insert(DataSnapshot)
        .values(data_hash=digest, compressed_json=gzip.compress(payload, mtime=0))
        .on_conflict_do_nothing(index_elements=["data_hash"])
    )
    return digest


def restore_snapshot(db: Session, digest: str) -> pd.DataFrame:
    snapshot = db.get(DataSnapshot, digest)
    if snapshot is None:
        raise ValueError("Research input snapshot not found")
    raw = gzip.decompress(snapshot.compressed_json)
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("Research input snapshot integrity check failed")
    frame = pd.DataFrame(json.loads(raw))
    if "timestamp" in frame:
        frame["timestamp"] = pd.to_datetime(frame.timestamp, utc=True)
    return frame
