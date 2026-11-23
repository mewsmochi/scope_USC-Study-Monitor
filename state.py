# used as a communication whiteboard between the two threads in one process: the monitor loop (main.py) and the Flask server (server.py)
# the monitor and server run at the same time --> safe way to pass information to each other

import threading

_lock = threading.Lock()
_state = {
    # live activity
    "status": "Not connected", "app": None, "domain": None, "paused": False,
    "paused_at": None,      # time.time() when the current pause began (None if not paused)
    # current session (None when no session is running)
    "session_id": None, "class_name": None, "session_start": None, "mode": None,
    "pomodoro": None,       # (work_seconds, break_seconds, rounds) for this session
    "timer": None,          # pomodoro phase/round/remaining, published by the monitor
    "last_summary": None,   # summary of the session that just ended
}

def update(**fields):
    with _lock:
        _state.update(fields)

def snapshot():
    with _lock:
        return dict(_state)

def take(field, value=None):
    """Atomically read a field and replace it (so two threads can't both 'stop' a session)."""
    with _lock:
        old = _state[field]
        _state[field] = value
        return old
