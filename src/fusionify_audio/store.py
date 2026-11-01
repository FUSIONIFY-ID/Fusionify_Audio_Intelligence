"""Transactional local records for one owner workspace."""
import json
import re
import sqlite3
import time
from pathlib import Path


def identifier(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{32}", value):
        raise ValueError("Invalid record ID.")
    return value


class Store:
    def __init__(self, root: Path):
        self.path = root / "workspace.sqlite3"
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("CREATE TABLE IF NOT EXISTS records (bucket TEXT, id TEXT, payload TEXT NOT NULL, updated REAL NOT NULL, PRIMARY KEY(bucket,id))")

    def connect(self):
        return sqlite3.connect(self.path, timeout=15)

    def get(self, bucket: str, key: str) -> dict:
        identifier(key)
        with self.connect() as conn:
            row = conn.execute("SELECT payload FROM records WHERE bucket=? AND id=?", (bucket,key)).fetchone()
        if row is None:
            raise ValueError(f"Unknown {bucket} ID.")
        return json.loads(row[0])

    def put(self, bucket: str, key: str, value: dict):
        identifier(key)
        data = json.dumps(value, ensure_ascii=False, allow_nan=False)
        with self.connect() as conn:
            conn.execute("INSERT INTO records VALUES (?,?,?,?) ON CONFLICT(bucket,id) DO UPDATE SET payload=excluded.payload,updated=excluded.updated", (bucket,key,data,time.time()))

    def list(self, bucket: str, limit: int=50) -> list[dict]:
        if not isinstance(limit,int) or isinstance(limit,bool) or not 1 <= limit <= 100:
            raise ValueError("Limit must be an integer from 1 to 100.")
        with self.connect() as conn:
            rows = conn.execute("SELECT payload FROM records WHERE bucket=? ORDER BY updated DESC LIMIT ?", (bucket,limit)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def revise(self, key: str, expected_revision: int, updates: dict) -> dict:
        identifier(key)
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT payload FROM records WHERE bucket='project' AND id=?", (key,)).fetchone()
            if row is None: raise ValueError("Unknown project ID.")
            current = json.loads(row[0])
            if current['revision'] != expected_revision:
                raise ValueError("Project revision conflict. Read the project and retry with its current revision.")
            value = {**current, **updates, 'revision':expected_revision+1}
            conn.execute("UPDATE records SET payload=?,updated=? WHERE bucket='project' AND id=?", (json.dumps(value,ensure_ascii=False,allow_nan=False),time.time(),key))
        return value
