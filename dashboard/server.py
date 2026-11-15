# in server.py
from flask import Flask, jsonify, render_template
import state
import logging

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

def run():
    app.run(host="127.0.0.1", port=5050, debug=False, use_reloader=False)

if __name__ == "__main__":
    run()