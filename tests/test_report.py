from datetime import datetime

from data.stats import distraction_time, longest_focus, report


def ev(ts, status, kind="activity", app="Code", domain=None, session_id=1):
    return {"session_id": session_id, "ts": ts, "status": status, "kind": kind, "app": app, "domain": domain}


def test_longest_focus_continues_through_heartbeats_and_alerts():
    events = [ev(0, "allowed"), ev(30, "allowed", "heartbeat"), ev(40, "refocused", "alert"),
              ev(60, "distracting"), ev(70, "allowed"), ev(80, "stopped", "lifecycle")]
    assert longest_focus(events, max_gap=42) == 60


def test_longest_focus_breaks_on_gap():
    events = [ev(0, "allowed"), ev(30, "allowed", "heartbeat"), ev(3630, "allowed", "heartbeat"),
              ev(3650, "stopped", "lifecycle")]
    assert longest_focus(events, max_gap=42) == 30


def test_distraction_time_by_site_or_app():
    events = [ev(0, "distracting", app="Safari", domain="youtube.com"), ev(20, "distracting", app="Discord"),
              ev(25, "distracting", app="Safari", domain="youtube.com"), ev(30, "stopped", "lifecycle")]
    assert distraction_time(events, max_gap=42) == {"youtube.com": 25, "Discord": 5}


def test_report():
    now = datetime(2026, 11, 15, 12).timestamp()
    day = 86400
    classes = [{"id": 1, "name": "CSCI 104"}, {"id": 2, "name": "MATH 225"}]
    sessions = [{"id": 1, "class_id": 1, "start": now - 1000, "mode": "regular"},
                {"id": 2, "class_id": 1, "start": now - 10 * day, "mode": "pomodoro"}]
    events = [ev(now - 1000, "allowed"), ev(now - 990, "distracting", app="Discord"),
              ev(now - 980, "stopped", "lifecycle"),
              ev(now - 10 * day, "allowed", session_id=2), ev(now - 10 * day + 30, "stopped", "lifecycle", session_id=2)]
    deadlines = [{"id": 1, "class_id": 2, "title": "Midterm", "due_date": "2026-11-20"},
                 {"id": 2, "class_id": 1, "title": "Old", "due_date": "2026-11-01"}]
    r = report(classes, sessions, events, deadlines, now, low_study_hours=3)

    assert [(c["name"], c["focused"], c["week_focused"]) for c in r["classes"]] == \
        [("CSCI 104", 40, 10), ("MATH 225", 0, 0)]
    assert r["week"] == {"focused": 10, "distracted": 10, "productivity": 50}
    assert r["personal_best"] == 30
    assert r["top_distractions"] == [{"name": "Discord", "seconds": 10}]
    assert [s["id"] for s in r["recent_sessions"]] == [1, 2]          # newest first
    assert len(r["deadlines"]) == 1                                   # past deadline hidden
    d = r["deadlines"][0]
    assert (d["days_left"], d["low"]) == (5, True)
