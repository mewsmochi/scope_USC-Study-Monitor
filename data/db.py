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
    status     TEXT NOT NULL
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


def log_event(app, domain, status, session_id=None):
    """Record one change of activity. Never lets a database problem crash the monitor."""
    try:
        # Fresh connection per call, so the monitor and Flask threads never share one
        with closing(connect()) as conn, conn:
            # The ? placeholders keep values separate from the SQL (prevents SQL injection)
            conn.execute(
                "INSERT INTO events (session_id, ts, app, domain, status) VALUES (?, ?, ?, ?, ?)",
                # ts = the current time in seconds since 1970
                (session_id, time.time(), app, domain, status),
            )
    except sqlite3.Error as e:
        # Logging problems should never stop the monitor, so just print and carry on
        print(f"   [db] couldn't log event: {e}")
# Add, list, and retrieve classes

def add_class(name):
    """Add a class (ignored if it exists) and return {'id', 'name'}, or None if the name is blank."""
    name = name.strip()
    if not name:
        return None
    with closing(connect()) as conn, conn:
        # OR IGNORE + UNIQUE name: adding a duplicate just reuses the existing row
        conn.execute("INSERT OR IGNORE INTO classes (name) VALUES (?)", (name,))
        row = conn.execute("SELECT id, name FROM classes WHERE name = ?", (name,)).fetchone()
    return dict(row)


def list_classes():
    # All classes, alphabetical, for the dropdown
    with closing(connect()) as conn:
        return [dict(r) for r in conn.execute("SELECT id, name FROM classes ORDER BY name")]


def get_class(class_id):
    # One class by id, or None if it doesn't exist
    with closing(connect()) as conn:
        row = conn.execute("SELECT id, name FROM classes WHERE id = ?", (class_id,)).fetchone()
    return dict(row) if row else None


# Start, end, and close abandoned sessions
def start_session(class_id, mode="regular"):
    """Create a session row and return its id."""
    with closing(connect()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO sessions (class_id, start, mode) VALUES (?, ?, ?)",
            (class_id, time.time(), mode),
        )
        return cur.lastrowid   # the id SQLite just assigned


def end_session(session_id):
    # Stamp the end time; "end" is quoted because it's also an SQL keyword.
    # AND "end" IS NULL means an already-ended session is never overwritten.
    with closing(connect()) as conn, conn:
        conn.execute('UPDATE sessions SET "end" = ? WHERE id = ? AND "end" IS NULL',
                     (time.time(), session_id))


def close_orphan_sessions():
    """If the program crashed mid-session, close that session at its last logged event."""
    with closing(connect()) as conn, conn:
        # For every session with no end: use its newest event's time (or its start if it has none)
        conn.execute('''
            UPDATE sessions
            SET "end" = COALESCE((SELECT MAX(ts) FROM events WHERE session_id = sessions.id), start)
            WHERE "end" IS NULL''')