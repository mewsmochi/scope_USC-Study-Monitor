"""Starting and stopping a session. Used by the dashboard (Start/Stop), the Pomodoro timer
(when the last round ends), and main.py (Ctrl+C / signals), so they all close it the same way."""
import time

import state
from data import db

MODES = ("regular", "pomodoro")


def start(class_row, mode, config):
    """Create the session row and put it on the shared board. Returns the session id."""
    sid = db.start_session(class_row["id"], mode)
    db.log_event(None, None, "started", sid)
    # Pomodoro lengths are fixed for the session, even if config.json changes mid-way
    pomodoro = (config["pomodoro_work_minutes"] * 60, config["pomodoro_break_minutes"] * 60,
                config["pomodoro_rounds"])
    state.update(session_id=sid, class_name=class_row["name"], session_start=time.time(),
                 mode=mode, pomodoro=pomodoro, timer=None, paused=False, last_summary=None)
    return sid


def stop():
    """End the running session, if any. Returns its id (None if nothing was running).
    The monitor loop notices the session is gone and prints/publishes the summary."""
    sid = state.take("session_id")   # atomic: a double stop can't log "stopped" twice
    if sid is None:
        return None
    db.log_event(None, None, "stopped", sid)
    db.end_session(sid)
    state.update(class_name=None, session_start=None, mode=None, timer=None, paused=False)
    return sid
