# in server.py
import logging
import time
from datetime import date
from urllib.parse import urlparse

from flask import Flask, jsonify, render_template, request

import state
from data import db
from data.stats import report
from rules.config_editor import load_config
from sessions import control

logging.getLogger("werkzeug").setLevel(logging.ERROR)

app = Flask(__name__)

LOCAL_HOSTS = {"127.0.0.1", "localhost"}


@app.before_request
def only_this_dashboard():
    """Block other websites from controlling or reading the dashboard.

    - Host check: stops DNS rebinding (evil.com re-pointed at 127.0.0.1 to read /api/stats).
    - Origin check: a page on another site can't send POST/DELETE here.
    - JSON-only POSTs: a plain HTML form can't send JSON, and a cross-site fetch with JSON needs
      a CORS preflight, which this server never approves.
    """
    if request.host.split(":")[0] not in LOCAL_HOSTS:
        return jsonify(error="Forbidden host"), 403
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return None
    origin = request.headers.get("Origin")
    if origin and urlparse(origin).hostname not in LOCAL_HOSTS:
        return jsonify(error="Forbidden origin"), 403
    if request.method == "POST" and not request.is_json:
        return jsonify(error="Send JSON (Content-Type: application/json)"), 415
    return None


@app.get("/")
def home():
    return render_template("index.html")

@app.get("/api/status")
def status():
    s = state.snapshot()
    s.pop("pomodoro", None)   # internal; the dashboard uses "timer"
    return jsonify(s)

@app.post("/api/pause")
def pause():
    s = state.snapshot()
    if s["session_id"] is None:
        return jsonify(error="No session running"), 409
    state.update(paused=not s["paused"])
    return jsonify(state.snapshot())

# Classes
@app.get("/api/classes")
def classes():
    # List of classes for the dropdown
    return jsonify(db.list_classes())


@app.post("/api/classes")
def new_class():
    # Read the name from the JSON body; silent=True returns None instead of erroring on bad JSON
    name = str((request.get_json(silent=True) or {}).get("name", ""))
    c = db.add_class(name)
    if not c:
        return jsonify(error="Class name can't be empty"), 400   # 400 = bad request
    return jsonify(c)

# sessions
@app.post("/api/session/start")
def session_start():
    body = request.get_json(silent=True) or {}
    # Only one session at a time
    if state.snapshot()["session_id"] is not None:
        return jsonify(error="A session is already running"), 409   # 409 = conflict
    # The chosen class must exist
    c = db.get_class(body.get("class_id"))
    if not c:
        return jsonify(error="Pick a class first"), 400
    mode = body.get("mode", "regular")
    if mode not in control.MODES:
        return jsonify(error="Pick a timer: regular or pomodoro"), 400
    control.start(c, mode, load_config())
    return jsonify(state.snapshot())


@app.post("/api/session/stop")
def session_stop():
    if control.stop() is None:
        return jsonify(error="No session running"), 409
    return jsonify(state.snapshot())

# stats
@app.get("/api/stats")
def stats():
    # Recomputed from the raw events on every request: fine for a single user's history
    r = report(db.list_classes(), db.all_sessions(), db.all_events(), db.list_deadlines(),
               time.time(), load_config()["low_study_hours"])
    return jsonify(r)

# deadlines
@app.post("/api/deadlines")
def add_deadline():
    body = request.get_json(silent=True) or {}
    title = str(body.get("title", "")).strip()
    try:
        class_id = int(body.get("class_id"))
        due = date.fromisoformat(str(body.get("due_date"))).isoformat()
    except (TypeError, ValueError):
        return jsonify(error="Pick a class and a valid date."), 400
    if not title or len(title) > 200:
        return jsonify(error="Give the deadline a title (up to 200 characters)."), 400
    if not db.get_class(class_id):
        return jsonify(error="Unknown class."), 400
    return jsonify(id=db.add_deadline(class_id, title, due)), 201

@app.delete("/api/deadlines/<int:deadline_id>")
def delete_deadline(deadline_id):
    if not db.delete_deadline(deadline_id):
        return jsonify(error="Not found."), 404
    return "", 204

def run():
    app.run(host="127.0.0.1", port=5050, debug=False, use_reloader=False)


if __name__ == "__main__":
    run()
