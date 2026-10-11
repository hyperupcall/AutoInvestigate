"""SQLite store for the ideation collective.

One file (`ideation.db`) holds everything the daemon needs to survive a restart:
the tagged watchlist of topics, the raw signals it has seen (deduplicated), the
ideas it has generated, the refinement sessions (with their streamed events) and
the curated memory.

SQLite is used (rather than a JSON document store) because the signal firehose is
append-heavy and needs cheap dedup/retention queries, and because the daemon is
long-running and multi-threaded (the HTTP server and the scheduler both touch it).
A single connection with `check_same_thread=False` and a re-entrant lock keeps it
simple and safe; WAL mode lets readers and the writer proceed together.
"""
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS topics (
    id             TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    description    TEXT DEFAULT '',
    tags           TEXT DEFAULT '[]',
    keywords       TEXT DEFAULT '[]',
    sources        TEXT DEFAULT '[]',
    priority       INTEGER DEFAULT 1,
    enabled        INTEGER DEFAULT 1,
    last_polled_at TEXT,
    created_at     TEXT
);

CREATE TABLE IF NOT EXISTS signals (
    id           TEXT PRIMARY KEY,
    topic_id     TEXT,
    source       TEXT,
    title        TEXT,
    url          TEXT,
    text         TEXT,
    published_at TEXT,
    fetched_at   TEXT,
    hash         TEXT UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_signals_topic ON signals(topic_id);
CREATE INDEX IF NOT EXISTS idx_signals_hash  ON signals(hash);

CREATE TABLE IF NOT EXISTS ideas (
    id              TEXT PRIMARY KEY,
    topic_id        TEXT,
    session_id      TEXT,
    kind            TEXT,            -- abstract | concrete
    text            TEXT,            -- the idea itself: ONE sentence
    justification   TEXT DEFAULT '[]',
    context         TEXT DEFAULT '',
    sources         TEXT DEFAULT '[]',
    tags            TEXT DEFAULT '[]',
    parent_idea_ids TEXT DEFAULT '[]',
    artifact_type   TEXT DEFAULT '',
    score           TEXT DEFAULT '{}',
    created_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_ideas_topic ON ideas(topic_id);

CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    topic_id    TEXT,
    topic_name  TEXT,
    status      TEXT,                -- running | done | failed
    model       TEXT,
    cost        REAL DEFAULT 0,
    trigger     TEXT DEFAULT 'manual',
    started_at  TEXT,
    finished_at TEXT,
    report      TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_sessions_topic ON sessions(topic_id);

CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    seq        INTEGER,
    ts         TEXT,
    kind       TEXT,
    data       TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id, seq);

CREATE TABLE IF NOT EXISTS memory (
    id                TEXT PRIMARY KEY,
    kind              TEXT,          -- fact | constraint | preference | decision | entity
    text              TEXT,
    importance        INTEGER DEFAULT 5,
    tags              TEXT DEFAULT '[]',
    topic_id          TEXT,
    source_signal_ids TEXT DEFAULT '[]',
    created_at        TEXT,
    last_used_at      TEXT,
    pinned            INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_memory_topic ON memory(topic_id);
"""

JSON_COLUMNS = {
    "topics": ("tags", "keywords", "sources"),
    "ideas": ("justification", "sources", "tags", "parent_idea_ids", "score"),
    "sessions": ("report",),
    "memory": ("tags", "source_signal_ids"),
    "events": ("data",),
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    """Thread-safe SQLite document store. Rows are plain dicts; JSON columns are decoded."""

    def __init__(self, path: str):
        self.path = path
        directory = os.path.dirname(os.path.abspath(path))
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._lock = threading.RLock()
        try:
            self._conn = sqlite3.connect(path, check_same_thread=False)
        except sqlite3.OperationalError as exc:
            raise RuntimeError(
                f"cannot open the ideation database at {path!r}: {exc}. "
                f"The data directory must exist and be writable by the user running the daemon "
                f"(in Docker the entrypoint chowns it to HOST_UID:HOST_GID)."
            ) from exc
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(SCHEMA)
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        """Add columns introduced after the first release, so an existing database keeps working."""
        cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(topics)")}
        for name, ddl in (("origin", "TEXT DEFAULT 'user'"), ("rationale", "TEXT DEFAULT ''")):
            if name not in cols:
                self._conn.execute(f"ALTER TABLE topics ADD COLUMN {name} {ddl}")

    # ------------------------------------------------------------- internals
    def _decode(self, table: str, row: sqlite3.Row) -> Dict[str, Any]:
        obj = dict(row)
        for col in JSON_COLUMNS.get(table, ()):
            if col in obj and isinstance(obj[col], str):
                try:
                    obj[col] = json.loads(obj[col])
                except (ValueError, TypeError):
                    obj[col] = None
        return obj

    def _rows(self, table: str, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute(sql, params)
            return [self._decode(table, r) for r in cur.fetchall()]

    def _row(self, table: str, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        rows = self._rows(table, sql, params)
        return rows[0] if rows else None

    def _insert(self, table: str, obj: Dict[str, Any]) -> None:
        cols = list(obj.keys())
        placeholders = ", ".join("?" for _ in cols)
        sql = f"INSERT OR REPLACE INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
        values = [json.dumps(obj[c]) if c in JSON_COLUMNS.get(table, ()) and not isinstance(obj[c], str)
                  else obj[c] for c in cols]
        with self._lock:
            self._conn.execute(sql, values)
            self._conn.commit()

    # --------------------------------------------------------------- topics
    def add_topic(self, topic: Dict[str, Any]) -> Dict[str, Any]:
        topic.setdefault("created_at", now_iso())
        topic.setdefault("tags", [])
        topic.setdefault("keywords", [])
        topic.setdefault("sources", [])
        topic.setdefault("priority", 1)
        topic.setdefault("enabled", 1)
        topic.setdefault("description", "")
        topic.setdefault("origin", "user")
        topic.setdefault("rationale", "")
        topic.setdefault("last_polled_at", None)
        self._insert("topics", topic)
        return topic

    def list_topics(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM topics"
        if enabled_only:
            sql += " WHERE enabled = 1"
        sql += " ORDER BY priority DESC, name ASC"
        return self._rows("topics", sql)

    def get_topic(self, id: str) -> Optional[Dict[str, Any]]:
        return self._row("topics", "SELECT * FROM topics WHERE id = ?", (id,))

    def update_topic(self, id: str, **fields: Any) -> Optional[Dict[str, Any]]:
        topic = self.get_topic(id)
        if topic is None:
            return None
        topic.update(fields)
        self._insert("topics", topic)
        return topic

    def delete_topic(self, id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM topics WHERE id = ?", (id,))
            self._conn.commit()
            return cur.rowcount > 0

    # -------------------------------------------------------------- signals
    def add_signal(self, signal: Dict[str, Any]) -> bool:
        """Insert a signal unless its hash was already seen. Returns True when new."""
        signal.setdefault("fetched_at", now_iso())
        signal.setdefault("published_at", None)
        signal.setdefault("text", "")
        cols = ["id", "topic_id", "source", "title", "url", "text",
                "published_at", "fetched_at", "hash"]
        values = [signal.get(c) for c in cols]
        with self._lock:
            cur = self._conn.execute(
                f"INSERT OR IGNORE INTO signals ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
                values)
            self._conn.commit()
            return cur.rowcount > 0

    def list_signals(self, topic_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        if topic_id:
            return self._rows("signals", "SELECT * FROM signals WHERE topic_id = ? ORDER BY fetched_at DESC LIMIT ?",
                              (topic_id, limit))
        return self._rows("signals", "SELECT * FROM signals ORDER BY fetched_at DESC LIMIT ?", (limit,))

    def count_signals(self, topic_id: Optional[str] = None) -> int:
        with self._lock:
            if topic_id:
                cur = self._conn.execute("SELECT COUNT(*) FROM signals WHERE topic_id = ?", (topic_id,))
            else:
                cur = self._conn.execute("SELECT COUNT(*) FROM signals")
            return int(cur.fetchone()[0])

    # ---------------------------------------------------------------- ideas
    def add_idea(self, idea: Dict[str, Any]) -> Dict[str, Any]:
        idea.setdefault("created_at", now_iso())
        for col in ("justification", "sources", "tags", "parent_idea_ids"):
            idea.setdefault(col, [])
        idea.setdefault("score", {})
        idea.setdefault("context", "")
        idea.setdefault("artifact_type", "")
        idea.setdefault("kind", "abstract")
        self._insert("ideas", idea)
        return idea

    def list_ideas(self, topic_id: Optional[str] = None, kind: Optional[str] = None,
                   session_id: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        clauses, params = [], []
        if topic_id:
            clauses.append("topic_id = ?")
            params.append(topic_id)
        if kind:
            clauses.append("kind = ?")
            params.append(kind)
        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)
        return self._rows("ideas", f"SELECT * FROM ideas{where} ORDER BY created_at DESC LIMIT ?", tuple(params))

    def get_idea(self, id: str) -> Optional[Dict[str, Any]]:
        return self._row("ideas", "SELECT * FROM ideas WHERE id = ?", (id,))

    # ------------------------------------------------------------- sessions
    def create_session(self, session: Dict[str, Any]) -> Dict[str, Any]:
        session.setdefault("started_at", now_iso())
        session.setdefault("status", "running")
        session.setdefault("cost", 0.0)
        session.setdefault("report", {})
        session.setdefault("trigger", "manual")
        session.setdefault("finished_at", None)
        self._insert("sessions", session)
        return session

    def update_session(self, id: str, **fields: Any) -> Optional[Dict[str, Any]]:
        session = self.get_session(id)
        if session is None:
            return None
        session.update(fields)
        self._insert("sessions", session)
        return session

    def get_session(self, id: str) -> Optional[Dict[str, Any]]:
        return self._row("sessions", "SELECT * FROM sessions WHERE id = ?", (id,))

    def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._rows("sessions", "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?", (limit,))

    def list_sessions_by_status(self, status: str) -> List[Dict[str, Any]]:
        return self._rows("sessions", "SELECT * FROM sessions WHERE status = ? ORDER BY started_at DESC", (status,))

    # --------------------------------------------------------------- events
    def add_event(self, session_id: str, kind: str, data: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            cur = self._conn.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM events WHERE session_id = ?", (session_id,))
            seq = int(cur.fetchone()[0])
            self._conn.execute(
                "INSERT INTO events (session_id, seq, ts, kind, data) VALUES (?, ?, ?, ?, ?)",
                (session_id, seq, now_iso(), kind, json.dumps(data)))
            self._conn.commit()
        return {"seq": seq, "kind": kind, "data": data}

    def list_events(self, session_id: str, since: int = 0) -> List[Dict[str, Any]]:
        rows = self._rows("events",
                          "SELECT * FROM events WHERE session_id = ? AND seq > ? ORDER BY seq ASC",
                          (session_id, since))
        out = []
        for r in rows:
            data = r.get("data") or {}
            out.append({"seq": r["seq"], "ts": r["ts"], "kind": r["kind"], **data})
        return out

    # --------------------------------------------------------------- memory
    def add_memory(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        entry.setdefault("created_at", now_iso())
        entry.setdefault("importance", 5)
        entry.setdefault("tags", [])
        entry.setdefault("source_signal_ids", [])
        entry.setdefault("pinned", 0)
        entry.setdefault("last_used_at", None)
        entry.setdefault("kind", "fact")
        self._insert("memory", entry)
        return entry

    def list_memory(self, topic_id: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        if topic_id:
            return self._rows("memory",
                              "SELECT * FROM memory WHERE topic_id = ? ORDER BY importance DESC, created_at DESC LIMIT ?",
                              (topic_id, limit))
        return self._rows("memory", "SELECT * FROM memory ORDER BY importance DESC, created_at DESC LIMIT ?", (limit,))

    def get_memory(self, id: str) -> Optional[Dict[str, Any]]:
        return self._row("memory", "SELECT * FROM memory WHERE id = ?", (id,))

    def touch_memory(self, id: str) -> None:
        with self._lock:
            self._conn.execute("UPDATE memory SET last_used_at = ? WHERE id = ?", (now_iso(), id))
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()
