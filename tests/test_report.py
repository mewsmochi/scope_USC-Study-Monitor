from datetime import datetime

from data.stats import distractions, longest_focus, report


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


def test_distractions_time_visits_warnings():
    yt = dict(app="Safari", domain="youtube.com")
    events = [ev(0, "distracting", **yt), ev(15, "distracted", "alert", **yt),
              ev(20, "distracting", app="Discord"),
              ev(25, "distracting", **yt), ev(28, "distracting", "heartbeat", **yt),   # heartbeat isn't a visit
              ev(30, "stopped", "lifecycle")]
    assert distractions(events, max_gap=42) == {
        "youtube.com": {"kind": "site", "seconds": 25, "visits": 2, "warnings": 1},
        "Discord": {"kind": "app", "seconds": 5, "visits": 1, "warnings": 0},
    }


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
    discord = {"name": "Discord", "kind": "app", "seconds": 10, "visits": 1, "warnings": 0, "share": 100}
    assert r["top_distractions"] == [discord]
    assert r["top_distractions_week"] == [discord]
    assert [s["id"] for s in r["recent_sessions"]] == [1, 2]          # newest first
    assert len(r["deadlines"]) == 1                                   # past deadline hidden
    d = r["deadlines"][0]
    assert (d["days_left"], d["low"]) == (5, True)


def test_top_distractions_week_vs_all_time():
    now = datetime(2026, 11, 15, 12).timestamp()
    old = now - 10 * 86400
    sessions = [{"id": 1, "class_id": 1, "start": now - 100, "mode": "regular"},
                {"id": 2, "class_id": 1, "start": old, "mode": "regular"}]
    events = [ev(now - 100, "distracting", app="Safari", domain="reddit.com"),
              ev(now - 70, "stopped", "lifecycle"),
              ev(old, "distracting", app="Safari", domain="youtube.com", session_id=2),
              ev(old + 40, "distracted", "alert", app="Safari", domain="youtube.com", session_id=2),
              ev(old + 40, "distracting", "heartbeat", app="Safari", domain="youtube.com", session_id=2),
              ev(old + 70, "stopped", "lifecycle", session_id=2)]
    r = report([{"id": 1, "name": "CSCI 104"}], sessions, events, [], now, low_study_hours=3)

    assert [(d["name"], d["seconds"], round(d["share"])) for d in r["top_distractions"]] == \
        [("youtube.com", 70, 70), ("reddit.com", 30, 30)]
    assert r["top_distractions"][0]["warnings"] == 1
    assert [d["name"] for d in r["top_distractions_week"]] == ["reddit.com"]   # youtube was 10 days ago
