"""Transactional local storage. Every operation uses its own connection."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .models import canonical, now


class Store:
    def __init__(self, path=None):
        self.path = Path(path or os.environ.get("AVB_DB", Path.home() / ".local/share/agent-visual-bridge/reviews.sqlite3"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > 1:
                raise ValueError("Database created by a newer version")
            db.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS reviews (
                  id TEXT PRIMARY KEY, document TEXT NOT NULL, state TEXT NOT NULL,
                  decisions TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS revisions (
                  review_id TEXT NOT NULL, revision INTEGER NOT NULL, document TEXT NOT NULL,
                  PRIMARY KEY(review_id, revision));
                CREATE TABLE IF NOT EXISTS receipts (
                  id TEXT PRIMARY KEY, review_id TEXT NOT NULL, request_key TEXT NOT NULL,
                  request_hash TEXT NOT NULL, document TEXT NOT NULL,
                  UNIQUE(review_id, request_key));
                CREATE TABLE IF NOT EXISTS events (
                  seq INTEGER PRIMARY KEY AUTOINCREMENT, review_id TEXT NOT NULL,
                  kind TEXT NOT NULL, document TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS settings (
                  project_id TEXT PRIMARY KEY, document TEXT NOT NULL);
                PRAGMA user_version=1;
            """)
        if os.name == "posix":
            self.path.chmod(0o600)

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(str(self.path), timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def event(db, review_id, kind, document):
        cursor = db.execute("INSERT INTO events(review_id,kind,document,created_at) VALUES(?,?,?,?)",
                            (review_id, kind, canonical(document), now()))
        return cursor.lastrowid

    def events(self, review_id, after=0):
        with self.transaction() as db:
            return [{"seq": r["seq"], "kind": r["kind"], "created_at": r["created_at"],
                     **json.loads(r["document"])} for r in db.execute(
                         "SELECT * FROM events WHERE review_id=? AND seq>? ORDER BY seq",
                         (review_id, after))]
