# in server.py
import logging
import time
from datetime import date

from flask import Flask, jsonify, render_template, request

import state
from data import db
from data.stats import report
from rules.config_editor import load_config

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
    state.update(paused=not s["paused"])
    return jsonify(state.snapshot())

@app.get("/api/stats")
def stats():
    # Recomputed from the raw events on every request: fine for a single user's history
    r = report(db.list_classes(), db.all_sessions(), db.all_events(), db.list_deadlines(),
               time.time(), load_config()["low_study_hours"])
    return jsonify(r)

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
    if class_id not in {c["id"] for c in db.list_classes()}:
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
