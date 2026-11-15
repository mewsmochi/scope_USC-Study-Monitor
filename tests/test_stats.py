from data.stats import durations, summarize


def ev(ts, status, kind="activity"):
    return {"ts": ts, "status": status, "kind": kind}


def test_durations_split_by_status():
    events = [ev(0, "started", "lifecycle"), ev(0, "allowed"), ev(30, "allowed", "heartbeat"),
              ev(40, "distracting"), ev(50, "distracted", "alert"), ev(60, "allowed"),
              ev(70, "stopped", "lifecycle")]
    assert durations(events, max_gap=42) == {"allowed": 50, "distracting": 20}


def test_long_gap_is_ignored():
    # laptop slept for an hour between the two rows
    events = [ev(0, "allowed"), ev(10, "allowed", "heartbeat"), ev(3610, "allowed", "heartbeat"),
              ev(3620, "stopped", "lifecycle")]
    assert durations(events, max_gap=42) == {"allowed": 20}


def test_pause_and_break_count_separately():
    events = [ev(0, "allowed"), ev(10, "paused", "lifecycle"), ev(20, "resumed", "lifecycle"),
              ev(20, "allowed"), ev(30, "break_start", "lifecycle"), ev(40, "break_end", "lifecycle"),
              ev(40, "stopped", "lifecycle")]
    assert durations(events, max_gap=42) == {"allowed": 20, "paused": 10, "break": 10}


def test_summary():
    events = [ev(0, "allowed"), ev(30, "distracting"), ev(35, "distracted", "alert"),
              ev(40, "allowed"), ev(70, "idle"), ev(80, "stopped", "lifecycle")]
    s = summarize(events, max_gap=42)
    assert (s["total"], s["focused"], s["distracted"], s["warnings"]) == (80, 60, 10, 1)
    assert round(s["productivity"]) == 86
