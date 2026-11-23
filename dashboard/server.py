# in server.py
import logging
import time
from datetime import date
from urllib.parse import urlparse

from flask import Flask, jsonify, render_template, request

import state
from data import db
from data.stats import report
from alerts.messages import PERSONAS
from monitor.detector import BROWSER_SCRIPTS
from rules.config_editor import (load_config, save_config, add_to_allowlist, remove_from_allowlist,
                                 clean_site, APPS, SITES, MODES, NUMBER_SETTINGS)
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
    now = time.time()
    if s["paused"]:
        # Resume: push the start time forward by the pause length so the timer skips it
        state.update(paused=False, paused_at=None,
                     session_start=s["session_start"] + (now - s["paused_at"]))
    else:
        state.update(paused=True, paused_at=now, monitoring_paused=False)
    return jsonify(state.snapshot())

@app.post("/api/pause-monitoring")
def pause_monitoring():
    """Stop warnings and tracking, but leave the timer running."""
    s = state.snapshot()
    if s["session_id"] is None:
        return jsonify(error="No session running"), 409
    if s["paused"]:
        return jsonify(error="Session is paused"), 409
    state.update(monitoring_paused=not s["monitoring_paused"])
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
    cfg = load_config()   # a copy for this session only; config.json isn't changed
    if mode == "pomodoro":
        for key, field in (("pomodoro_work_minutes", "work_minutes"),
                           ("pomodoro_break_minutes", "break_minutes"),
                           ("pomodoro_rounds", "rounds")):
            if body.get(field) in (None, ""):
                continue
            try:
                n = int(body[field])
            except (TypeError, ValueError):
                return jsonify(error=f"{field} must be a whole number"), 400
            lo, hi = LIMITS[key]
            if not lo <= n <= hi:
                return jsonify(error=f"{field} must be between {lo} and {hi}"), 400
            cfg[key] = n
    control.start(c, mode, cfg)
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

# settings and allowlist
LIMITS = {   # config key -> (min, max)
    "grace_seconds": (1, 3600), "repeat_seconds": (1, 3600), "idle_seconds": (1, 3600),
    "pomodoro_work_minutes": (1, 180), "pomodoro_break_minutes": (1, 60),
    "pomodoro_rounds": (1, 12), "low_study_hours": (1, 100),
    "look_away_seconds": (3, 300),
}
KINDS = {"apps": APPS, "sites": SITES}


def config_payload():
    c = load_config()
    return {
        "mode": c["mode"], "persona": c["persona"], "focus_mode": c["focus_mode"],
        "modes": list(MODES), "personas": list(PERSONAS),
        "numbers": [{"key": k, "label": label, "unit": unit, "value": c[k],
                     "min": LIMITS[k][0], "max": LIMITS[k][1]}
                    for label, k, unit in NUMBER_SETTINGS],
        "apps": c[APPS], "sites": c[SITES],
    }


@app.get("/api/config")
def get_config():
    return jsonify(config_payload())


@app.post("/api/config")
def set_config():
    body = request.get_json(silent=True) or {}
    if body.get("mode") not in MODES:
        return jsonify(error="Invalid mode"), 400
    if body.get("persona") not in PERSONAS:
        return jsonify(error="Invalid persona"), 400
    if not isinstance(body.get("focus_mode"), bool):
        return jsonify(error="Invalid focus mode setting"), 400
    updates = {"mode": body["mode"], "persona": body["persona"], "focus_mode": body["focus_mode"]}
    for key, (lo, hi) in LIMITS.items():
        try:
            n = int(body[key])
        except (KeyError, TypeError, ValueError):
            return jsonify(error=f"{key} must be a whole number"), 400
        if not lo <= n <= hi:
            return jsonify(error=f"{key} must be between {lo} and {hi}"), 400
        updates[key] = n
    config = load_config()
    config.update(updates)
    save_config(config)   # main.py reloads this within ~5 seconds
    return jsonify(config_payload())


@app.post("/api/allowlist/add")
def allowlist_add():
    body = request.get_json(silent=True) or {}
    kind = KINDS.get(body.get("kind"))
    value = str(body.get("value") or "").strip()[:200]
    if not kind or not value:
        return jsonify(error="Enter a name first"), 400
    if kind == SITES:
        value = clean_site(value)
    elif value in BROWSER_SCRIPTS:
        return jsonify(error=f"Allowing {value} would allow every website. Add websites instead."), 400
    if not value:
        return jsonify(error="Enter a name first"), 400
    add_to_allowlist(kind, value)
    return jsonify(config_payload())


@app.post("/api/allowlist/remove")
def allowlist_remove():
    body = request.get_json(silent=True) or {}
    kind = KINDS.get(body.get("kind"))
    if not kind:
        return jsonify(error="Bad request"), 400
    remove_from_allowlist(kind, str(body.get("value") or ""))
    return jsonify(config_payload())


@app.post("/api/allowlist/allow-current")
def allowlist_allow_current():
    # Allows whatever the monitor currently sees (the page waits a few seconds so you can switch first)
    s = state.snapshot()
    app_name, domain = s.get("app"), s.get("domain")
    if not app_name or domain in LOCAL_HOSTS:
        return jsonify(error="Switch to the app or site you want to allow first"), 400
    if domain:
        add_to_allowlist(SITES, domain)
    elif app_name in BROWSER_SCRIPTS:
        return jsonify(error="Couldn't read a page from the browser. Open a site and try again."), 400
    else:
        add_to_allowlist(APPS, app_name)
    return jsonify(config_payload())

def run():
    app.run(host="127.0.0.1", port=5050, debug=False, use_reloader=False)


if __name__ == "__main__":
    run()
