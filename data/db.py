"""SQLite storage for sessions and activity events."""
import sqlite3
import time
from contextlib import closing
from pathlib import Path

DB_PATH = Path(__file__).parent / "study.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS classes (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS sessions (
    id       INTEGER PRIMARY KEY,
    class_id INTEGER REFERENCES classes(id),
    start    REAL NOT NULL,
    end      REAL,
    mode     TEXT NOT NULL DEFAULT 'regular'
);

CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY,
    session_id INTEGER REFERENCES sessions(id),
    ts         REAL NOT NULL,
    app        TEXT,
    domain     TEXT,
    status     TEXT NOT NULL,
    kind       TEXT NOT NULL DEFAULT 'activity'
);

CREATE TABLE IF NOT EXISTS deadlines (
    id       INTEGER PRIMARY KEY,
    class_id INTEGER NOT NULL REFERENCES classes(id),
    title    TEXT NOT NULL,
    due_date TEXT NOT NULL,
    weight   REAL NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
"""

# Every status belongs to one kind, so queries can say WHERE kind = 'alert'.
#   activity:  what you were doing (allowed, distracting, neutral, idle, paused, break)
#   heartbeat: same status re-logged every HEARTBEAT_SECONDS so durations survive long stretches
#   lifecycle: the monitor starting/stopping/pausing, pomodoro breaks
#   alert:     what the focus tracker did about it
KINDS = {
    "started": "lifecycle", "stopped": "lifecycle", "paused": "lifecycle",
    "resumed": "lifecycle", "break_start": "lifecycle", "break_end": "lifecycle",
    "distracted": "alert", "still_distracted": "alert", "refocused": "alert", "forced": "alert",
}

def connect():
    # Open (or create) data/study.db; wait up to 5s if another thread is writing
    conn = sqlite3.connect(DB_PATH, timeout=5)
    # Let us read columns by name (row["app"]) instead of by position
    conn.row_factory = sqlite3.Row
    # SQLite ignores REFERENCES links unless this is switched on for every connection
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create the database and tables if they don't exist yet. Safe to call every start."""
    # closing(...) closes the connection afterward; the second "conn" commits on success
    # or rolls back on error
    with closing(connect()) as conn, conn:
        # Run every CREATE TABLE IF NOT EXISTS in SCHEMA (won't erase existing data)
        conn.executescript(SCHEMA)
        # Databases made before the kind column existed: add it instead of losing data
        cols = [row["name"] for row in conn.execute("PRAGMA table_info(events)")]
        if "kind" not in cols:
            conn.execute("ALTER TABLE events ADD COLUMN kind TEXT NOT NULL DEFAULT 'activity'")
            for status, kind in KINDS.items():
                conn.execute("UPDATE events SET kind = ? WHERE status = ?", (kind, status))


def log_event(app, domain, status, session_id=None, heartbeat=False):
    """Record one event. Never lets a database problem crash the monitor."""
    kind = "heartbeat" if heartbeat else KINDS.get(status, "activity")
    try:
        # Fresh connection per call, so the monitor and Flask threads never share one
        with closing(connect()) as conn, conn:
            # The ? placeholders keep values separate from the SQL (prevents SQL injection)
            conn.execute(
                "INSERT INTO events (session_id, ts, app, domain, status, kind) VALUES (?, ?, ?, ?, ?, ?)",
                # ts = the current time in seconds since 1970
                (session_id, time.time(), app, domain, status, kind),
            )
    except sqlite3.Error as e:
        # Logging problems should never stop the monitor, so just print and carry on
        print(f"   [db] couldn't log event: {e}")