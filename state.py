# used as a communication whiteboard between the two threads in one process: the monitor loop (main.py) and the Flask server (server.py)
# the monitor and server run at the same time --> safe way to pass information to each other

import threading

_lock = threading.Lock()
_state = {"status": "Not connected", "app": None, "domain": None, "paused": False, "session": None}

def update(**fields):
    with _lock:
        _state.update(fields)

def snapshot():
    with _lock:
        return dict(_state)