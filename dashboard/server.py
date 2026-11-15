# in server.py
from flask import Flask, jsonify, render_template, request
import state
import logging

import time
from data import db
from rules.config_editor import (load_config, save_config, add_to_allowlist,
                                 remove_from_allowlist, clean_site, APPS, SITES, MODES)
from alerts.messages import PERSONAS
from monitor.detector import BROWSER_SCRIPTS


logging.getLogger("werkzeug").setLevel(logging.ERROR)

app = Flask(__name__)

@app.get("/")
def home():
    return render_template("index.html")

@app.get("/api/status")
def status():
    return jsonify(state.snapshot())

@app.post("/api/pause")
def pause():
    s = state.snapshot()
    if s["session_id"] is None:
        return jsonify(error="No session running"), 409
    now = time.time()
    if s["paused"]:   # resuming: add the paused gap to the total so the timer skips it
        gap = now - s["paused_at"] if s["paused_at"] else 0
        state.update(paused=False, paused_at=None, paused_total=s["paused_total"] + gap)
    else:
        state.update(paused=True, paused_at=now)
    return jsonify(state.snapshot())

# Classes
@app.get("/api/classes")
def classes():
    # List of classes for the dropdown
    return jsonify(db.list_classes())


@app.post("/api/classes")
def new_class():
    # Read the name from the JSON body; silent=True returns None instead of erroring on bad JSON
    name = (request.get_json(silent=True) or {}).get("name", "")
    c = db.add_class(name)
    if not c:
        return jsonify(error="Class name can't be empty"), 400   # 400 = bad request
    return jsonify(c)

# sessions
@app.post("/api/session/start")
def session_start():
    if state.snapshot()["session_id"] is not None:
        return jsonify(error="A session is already running"), 409
    data = request.get_json(silent=True) or {}
    c = db.get_class(data.get("class_id"))
    if not c:
        return jsonify(error="Pick a class first"), 400
    mode = data.get("mode", "regular")
    if mode not in ("regular", "pomodoro"):
        return jsonify(error="Invalid timer mode"), 400
    try:
        work = int(data.get("work_minutes") or 25)
        brk = int(data.get("break_minutes") or 5)
    except (TypeError, ValueError):
        return jsonify(error="Work and break must be whole numbers of minutes"), 400
    if not (1 <= work <= 180 and 1 <= brk <= 60):
        return jsonify(error="Work must be 1-180 minutes and break 1-60"), 400
    sid = db.start_session(c["id"], mode)   # sessions.mode already exists in the schema
    state.update(session_id=sid, class_name=c["name"], session_start=time.time(), paused=False,
                 mode=mode, work_seconds=work * 60, break_seconds=brk * 60,
                 paused_at=None, paused_total=0.0)
    return jsonify(state.snapshot())


@app.post("/api/session/stop")
def session_stop():
    sid = state.snapshot()["session_id"]
    if sid is None:
        return jsonify(error="No session running"), 409
    # Close out the session in the database, then clear it from the board
    db.log_event(None, None, "stopped", sid)
    db.end_session(sid)
    state.update(session_id=None, class_name=None, session_start=None, paused=False,
        mode="regular", paused_at=None, paused_total=0.0)
    return jsonify(state.snapshot())

@app.get("/api/stats")
def stats():
    return jsonify(db.get_stats())

# ----- Settings and allowlist -----

KINDS = {"apps": APPS, "sites": SITES}


def config_payload():
    c = load_config()
    return {"mode": c["mode"], "persona": c["persona"],
            "grace_seconds": c["grace_seconds"], "repeat_seconds": c["repeat_seconds"],
            "apps": c[APPS], "sites": c[SITES],
            "modes": list(MODES), "personas": list(PERSONAS)}


@app.get("/api/config")
def get_config():
    return jsonify(config_payload())


@app.post("/api/config")
def set_config():
    data = request.get_json(silent=True) or {}
    config = load_config()
    if data.get("mode") not in MODES:
        return jsonify(error="Invalid mode"), 400
    if data.get("persona") not in PERSONAS:
        return jsonify(error="Invalid persona"), 400
    try:
        grace, repeat = int(data["grace_seconds"]), int(data["repeat_seconds"])
    except (KeyError, TypeError, ValueError):
        return jsonify(error="Timers must be whole numbers"), 400
    if not (1 <= grace <= 3600 and 1 <= repeat <= 3600):
        return jsonify(error="Timers must be between 1 and 3600 seconds"), 400
    config.update(mode=data["mode"], persona=data["persona"],
                  grace_seconds=grace, repeat_seconds=repeat)
    save_config(config)   # main.py reloads this within ~5 seconds
    return jsonify(config_payload())


@app.post("/api/allowlist/add")
def allowlist_add():
    data = request.get_json(silent=True) or {}
    kind = KINDS.get(data.get("kind"))
    value = (data.get("value") or "").strip()
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
    data = request.get_json(silent=True) or {}
    kind = KINDS.get(data.get("kind"))
    if not kind:
        return jsonify(error="Bad request"), 400
    remove_from_allowlist(kind, data.get("value") or "")
    return jsonify(config_payload())


@app.post("/api/allowlist/allow-current")
def allowlist_allow_current():
    # Allows whatever the monitor currently sees (the page waits a few seconds so you can switch first)
    s = state.snapshot()
    app_name, domain = s["app"], s["domain"]
    if domain in ("127.0.0.1", "localhost") or not app_name:
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