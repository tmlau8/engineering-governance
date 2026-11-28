"""Local deduplicated observation history and rebuildable current projections."""
import datetime as dt
import json
import os
from pathlib import Path
import sqlite3
from common import UTC, canonical, fingerprint, now


class Store:
    def __init__(self, path, readonly=False):
        self.path = Path(path)
        if self.path.is_symlink() or self.path.parent.is_symlink():
            raise ValueError("UNSAFE_STORE_PATH")
        if readonly:
            self.db = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True, timeout=10, check_same_thread=False)
            self.db.row_factory = sqlite3.Row
            return
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.path.parent, 0o700)
        self.db = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        os.chmod(self.path, 0o600)
        self.db.executescript("""
          PRAGMA journal_mode=DELETE;
          CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY, source TEXT, entity TEXT, observed_at TEXT,
            fingerprint TEXT, payload TEXT);
          CREATE TABLE IF NOT EXISTS current (
            source TEXT, entity TEXT, observed_at TEXT, last_seen TEXT, payload TEXT,
            PRIMARY KEY(source,entity));
          CREATE TABLE IF NOT EXISTS health (
            source TEXT PRIMARY KEY, attempted_at TEXT, succeeded_at TEXT,
            status TEXT, error_code TEXT, row_count INTEGER);
          CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY, source TEXT, attempted_at TEXT,
            status TEXT, error_code TEXT, row_count INTEGER);
        """)

    def close(self):
        self.db.close()

    def snapshot(self, source, records, at=None):
        at = at or now()
        with self.db:
            for entity, payload in records.items():
                encoded = canonical(payload)
                previous = self.db.execute("SELECT observed_at,payload FROM current WHERE source=? AND entity=?", (source, entity)).fetchone()
                if not previous or previous["payload"] != encoded:
                    self.db.execute("INSERT INTO events(source,entity,observed_at,fingerprint,payload) VALUES(?,?,?,?,?)", (source, entity, at, fingerprint(payload), encoded))
                observed = at if not previous or previous["payload"] != encoded else previous["observed_at"]
                self.db.execute("INSERT OR REPLACE INTO current VALUES(?,?,?,?,?)", (source, entity, observed, at, encoded))
            # A successful complete snapshot may retire absent rows. Errors never call this.
            existing = [r[0] for r in self.db.execute("SELECT entity FROM current WHERE source=?", (source,))]
            for entity in set(existing) - set(records):
                tombstone = canonical({"record_state": "absent_from_complete_snapshot"})
                self.db.execute("INSERT INTO events(source,entity,observed_at,fingerprint,payload) VALUES(?,?,?,?,?)", (source, entity, at, fingerprint(tombstone), tombstone))
                self.db.execute("DELETE FROM current WHERE source=? AND entity=?", (source, entity))
            self.db.execute("INSERT OR REPLACE INTO health VALUES(?,?,?,?,?,?)", (source, at, at, "success", None, len(records)))
            self.db.execute("INSERT INTO attempts(source,attempted_at,status,error_code,row_count) VALUES(?,?,?,?,?)", (source, at, "success", None, len(records)))

    def failure(self, source, code, at=None):
        at = at or now()
        if not isinstance(code, str) or not code.replace("_", "").isalnum() or len(code) > 60:
            code = "COLLECTION_ERROR"
        with self.db:
            previous = self.db.execute("SELECT succeeded_at,row_count FROM health WHERE source=?", (source,)).fetchone()
            self.db.execute("INSERT OR REPLACE INTO health VALUES(?,?,?,?,?,?)", (source, at, previous[0] if previous else None, "error", code, previous[1] if previous else None))
            self.db.execute("INSERT INTO attempts(source,attempted_at,status,error_code,row_count) VALUES(?,?,?,?,?)", (source, at, "error", code, None))

    def records(self, prefix=None):
        if prefix is None:
            rows = self.db.execute("SELECT * FROM current ORDER BY source,entity")
        else:
            rows = self.db.execute("SELECT * FROM current WHERE source LIKE ? ORDER BY source,entity", (prefix + "%",))
        return [{"source": r["source"], "entity": r["entity"], "observed_at": r["observed_at"], "last_seen": r["last_seen"], "data": json.loads(r["payload"])} for r in rows]

    def health(self):
        return [dict(r) for r in self.db.execute("SELECT * FROM health ORDER BY source")]

    def history(self, limit=150):
        return [{k: r[k] for k in ["id", "source", "entity", "observed_at", "fingerprint"]} for r in self.db.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (min(limit, 500),))]

    def attempts(self):
        return [dict(r) for r in self.db.execute("SELECT * FROM attempts ORDER BY id DESC LIMIT 100")]

    def prune(self, days=30):
        cutoff = (dt.datetime.now(UTC) - dt.timedelta(days=days)).isoformat().replace("+00:00", "Z")
        with self.db:
            self.db.execute("DELETE FROM events WHERE observed_at < ?", (cutoff,))
            self.db.execute("DELETE FROM current WHERE last_seen < ?", (cutoff,))
            self.db.execute("DELETE FROM attempts WHERE attempted_at < ?", (cutoff,))
        self.db.execute("VACUUM")
