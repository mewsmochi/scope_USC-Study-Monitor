# in server.py
from flask import Flask, jsonify, render_template, request
import state
import logging

import time
from data import db


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
    name = (request.get_json(silent=True) or {}).get("name", "")
    c = db.add_class(name)
    if not c:
        return jsonify(error="Class name can't be empty"), 400   # 400 = bad request
    return jsonify(c)

# sessions
@app.post("/api/session/start")
def session_start():
    # Only one session at a time
    if state.snapshot()["session_id"] is not None:
        return jsonify(error="A session is already running"), 409   # 409 = conflict
    # The chosen class must exist
    c = db.get_class((request.get_json(silent=True) or {}).get("class_id"))
    if not c:
        return jsonify(error="Pick a class first"), 400
    # Create the row, then put the session on the board so the monitor sees it
    sid = db.start_session(c["id"])
    state.update(session_id=sid, class_name=c["name"], session_start=time.time(), paused=False)
    return jsonify(state.snapshot())


@app.post("/api/session/stop")
def session_stop():
    sid = state.snapshot()["session_id"]
    if sid is None:
        return jsonify(error="No session running"), 409
    # Close out the session in the database, then clear it from the board
    db.log_event(None, None, "stopped", sid)
    db.end_session(sid)
    state.update(session_id=None, class_name=None, session_start=None, paused=False)
    return jsonify(state.snapshot())

def run():
    app.run(host="127.0.0.1", port=5050, debug=False, use_reloader=False)


if __name__ == "__main__":
    run()