import copy

import pytest

import state
from data import db
from dashboard import server
from rules.config_editor import DEFAULTS


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(server, "load_config", lambda: copy.deepcopy(DEFAULTS))
    db.init_db()
    state.update(session_id=None, class_name=None, session_start=None, mode=None,
                 pomodoro=None, timer=None, paused=False, last_summary=None)
    yield server.app.test_client()
    state.update(session_id=None)


def add_class(client, name="CSCI 104"):
    return client.post("/api/classes", json={"name": name}).get_json()["id"]


# --- other websites can't control or read the dashboard ---

def test_rejects_form_post(client):
    # a plain <form> on another site can only send form data, never JSON
    assert client.post("/api/session/stop", data={"x": "1"}).status_code == 415
    assert client.post("/api/pause").status_code == 415


def test_rejects_foreign_origin(client):
    r = client.post("/api/pause", json={}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    r = client.delete("/api/deadlines/1", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


def test_rejects_foreign_host(client):
    # DNS rebinding: evil.example resolves to 127.0.0.1 but the Host header gives it away
    assert client.get("/api/stats", headers={"Host": "evil.example"}).status_code == 403


def test_allows_dashboard_origin(client):
    r = client.post("/api/pause", json={}, headers={"Origin": "http://127.0.0.1:5050"})
    assert r.status_code == 409   # got past the checks; just no session running


# --- classes and sessions ---

def test_add_class(client):
    assert client.post("/api/classes", json={"name": "  "}).status_code == 400
    cid = add_class(client)
    assert add_class(client) == cid   # duplicate reuses the row
    assert client.get("/api/classes").get_json() == [{"id": cid, "name": "CSCI 104"}]


def test_session_start_and_stop(client):
    cid = add_class(client)
    assert client.post("/api/session/start", json={"class_id": 999}).status_code == 400
    assert client.post("/api/session/start", json={"class_id": cid, "mode": "x"}).status_code == 400

    s = client.post("/api/session/start", json={"class_id": cid, "mode": "pomodoro"}).get_json()
    assert (s["class_name"], s["mode"]) == ("CSCI 104", "pomodoro")
    assert client.post("/api/session/start", json={"class_id": cid}).status_code == 409

    assert client.post("/api/pause", json={}).get_json()["paused"] is True
    assert client.post("/api/session/stop", json={}).get_json()["session_id"] is None
    assert client.post("/api/session/stop", json={}).status_code == 409

    statuses = [e["status"] for e in db.session_events(s["session_id"])]
    assert statuses == ["started", "stopped"]


# --- deadlines and stats ---

def test_deadlines(client):
    cid = add_class(client)
    for bad in ({"class_id": cid, "title": "", "due_date": "2099-01-01"},
                {"class_id": 999, "title": "x", "due_date": "2099-01-01"},
                {"class_id": cid, "title": "x", "due_date": "soon"},
                {}):
        assert client.post("/api/deadlines", json=bad).status_code == 400

    r = client.post("/api/deadlines", json={"class_id": cid, "title": "Final", "due_date": "2099-01-01"})
    assert r.status_code == 201
    deadlines = client.get("/api/stats").get_json()["deadlines"]
    assert [d["title"] for d in deadlines] == ["Final"]

    did = r.get_json()["id"]
    assert client.delete(f"/api/deadlines/{did}").status_code == 204
    assert client.delete(f"/api/deadlines/{did}").status_code == 404


def test_stats_shape(client):
    add_class(client)
    r = client.get("/api/stats").get_json()
    assert set(r) == {"classes", "recent_sessions", "personal_best", "top_distractions", "top_distractions_week", "week", "deadlines"}
