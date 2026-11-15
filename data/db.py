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


# ----- Stats -----

# One row per stretch of time. How long each event lasted = next event's time minus its own;
# the last event of a session runs until the session's end.
SEGMENTS_SQL = '''
SELECT e.session_id, c.name AS class_name, e.app, e.domain, e.status,
       COALESCE(LEAD(e.ts) OVER (PARTITION BY e.session_id ORDER BY e.ts), s."end", e.ts) - e.ts AS secs
FROM events e
JOIN sessions s ON s.id = e.session_id
JOIN classes c ON c.id = s.class_id
ORDER BY e.session_id, e.ts
'''


def get_stats():
    """Everything the dashboard's stats section shows, as one dictionary."""
    with closing(connect()) as conn:
        segs = conn.execute(SEGMENTS_SQL).fetchall()
        recent = conn.execute('''
            SELECT s.id, c.name AS class_name, s.start, s."end"
            FROM sessions s JOIN classes c ON c.id = s.class_id
            WHERE s."end" IS NOT NULL ORDER BY s.start DESC LIMIT 8''').fetchall()

    allowed = distracting = 0.0
    by_class = {}       # class name -> [focused secs, distracted secs]
    distractions = {}   # site or app -> secs
    per_session = {}    # session id -> [focused secs, distracted secs]
    session_best = {}   # session id -> longest unbroken focus streak in that session
    best = run = 0.0    # personal best = longest unbroken stretch on allowed things
    current = None

    for r in segs:
        if r["session_id"] != current:       # new session: start a fresh streak
            current, run = r["session_id"], 0.0
            session_best.setdefault(current, 0.0)
        secs = r["secs"] or 0
        cls = by_class.setdefault(r["class_name"], [0.0, 0.0])
        ses = per_session.setdefault(r["session_id"], [0.0, 0.0])
        if r["status"] == "allowed":
            allowed += secs
            cls[0] += secs
            ses[0] += secs
            run += secs
            best = max(best, run)
            session_best[current] = max(session_best[current], run)
        elif r["status"] == "distracting":
            distracting += secs
            cls[1] += secs
            ses[1] += secs
            run = 0.0                          # a distraction breaks the streak
            key = r["domain"] or r["app"] or "Unknown"
            distractions[key] = distractions.get(key, 0.0) + secs

            # neutral, paused and stopped rows neither count nor break a streak

    # Previous best = best streak from every session except the most recent one
    ids = sorted(session_best)
    prev_best = max((session_best[i] for i in ids[:-1]), default=None)

    def pct(focused, distracted):
        total = focused + distracted
        return round(100 * focused / total) if total else None

    return {
        "productivity": pct(allowed, distracting),
        "focused_seconds": round(allowed),
        "distracted_seconds": round(distracting),
        "personal_best_seconds": round(best),
        "previous_best_seconds": round(prev_best) if prev_best is not None else None,
        "by_class": sorted(
            ({"name": n, "focused": round(f), "distracted": round(d)} for n, (f, d) in by_class.items()),
            key=lambda x: -x["focused"]),
        "top_distractions": sorted(
            ({"name": n, "seconds": round(s)} for n, s in distractions.items()),
            key=lambda x: -x["seconds"])[:5],
        "recent_sessions": [
            {"class": r["class_name"], "start": r["start"],
             "minutes": round((r["end"] - r["start"]) / 60, 1),
             "productivity": pct(*per_session.get(r["id"], [0, 0]))}
            for r in recent],
    }