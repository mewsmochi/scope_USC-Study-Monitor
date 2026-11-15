"""Turns logged events into time spent per status, plus the dashboard report."""
from collections import defaultdict
from datetime import date

# Events are only logged on change, so main.py re-logs the current status this often.
# Any gap longer than MAX_GAP_SECONDS (2x the 1s poll + 10s buffer on top) is sleep/crash.
HEARTBEAT_SECONDS = 30
MAX_GAP_SECONDS = HEARTBEAT_SECONDS + 2 * 1 + 10

# Lifecycle events that start a stretch of non-study time; every other lifecycle event
# (started, stopped, resumed, break_end) ends the current stretch.
_LIFECYCLE_STATUS = {"paused": "paused", "break_start": "break"}


def intervals(events, max_gap):
    """Yields (row, start, end) for every counted stretch, oldest first.

    events: rows with ts, kind, status (and app/domain for activity rows), oldest first.
    Each activity/heartbeat row means "this status until the next row". Gaps longer than
    max_gap (laptop asleep, crash, killed process) are skipped.
    """
    current = None
    for row, nxt in zip(events, events[1:]):
        if row["kind"] in ("activity", "heartbeat"):
            current = row
        elif row["kind"] == "lifecycle":
            s = _LIFECYCLE_STATUS.get(row["status"])
            current = {"status": s, "app": None, "domain": None} if s else None
        # alerts don't change what you're doing; they just split the interval
        if current and 0 <= nxt["ts"] - row["ts"] <= max_gap:
            yield current, row["ts"], nxt["ts"]


def durations(events, max_gap):
    """{status: seconds}"""
    totals = defaultdict(float)
    for row, start, end in intervals(events, max_gap):
        totals[row["status"]] += end - start
    return dict(totals)


def longest_focus(events, max_gap):
    """Longest unbroken stretch of "allowed" time, in seconds."""
    best = run = 0.0
    run_end = None
    for row, start, end in intervals(events, max_gap):
        if row["status"] != "allowed":
            run_end = None
            continue
        run = run + (end - start) if start == run_end else end - start
        run_end = end
        best = max(best, run)
    return best


def distraction_time(events, max_gap):
    """{website or app: seconds spent on it while it counted as distracting}"""
    totals = defaultdict(float)
    for row, start, end in intervals(events, max_gap):
        if row["status"] == "distracting":
            totals[row["domain"] or row["app"] or "Unknown"] += end - start
    return dict(totals)


def productivity(focused, distracted):
    # Breaks, idle, pauses, and neutral apps don't count for or against you
    judged = focused + distracted
    return 100 * focused / judged if judged else None


def summarize(events, max_gap):
    """Numbers for the end-of-session summary."""
    t = durations(events, max_gap)
    focused, distracted = t.get("allowed", 0.0), t.get("distracting", 0.0)
    return {
        "total": sum(t.values()),
        "focused": focused,
        "distracted": distracted,
        "productivity": productivity(focused, distracted),
        "warnings": sum(1 for e in events if e["status"] in ("distracted", "still_distracted")),
    }


def report(classes, sessions, events, deadlines, now, low_study_hours, max_gap=MAX_GAP_SECONDS):
    """Everything the stats dashboard shows. Pure: takes rows, returns plain dicts.

    classes: id, name.  sessions: id, class_id, start, mode.  events: session_id, ts, kind,
    status, app, domain (oldest first).  deadlines: id, class_id, title, due_date (YYYY-MM-DD).
    """
    by_session = defaultdict(list)
    for e in events:
        by_session[e["session_id"]].append(e)

    names = {c["id"]: c["name"] for c in classes}
    week_ago = now - 7 * 86400
    per_class = {c["id"]: {"id": c["id"], "name": c["name"], "focused": 0.0, "week_focused": 0.0}
                 for c in classes}
    distractions = defaultdict(float)
    week = {"focused": 0.0, "distracted": 0.0}
    recent, best = [], 0.0

    # Each session on its own, so one session's last row never runs into the next one's first
    for s in sorted(sessions, key=lambda s: s["start"]):
        evs = by_session.get(s["id"], [])
        summary = summarize(evs, max_gap)
        best = max(best, longest_focus(evs, max_gap))
        for name, secs in distraction_time(evs, max_gap).items():
            distractions[name] += secs
        c = per_class.get(s["class_id"])
        if c:
            c["focused"] += summary["focused"]
        if s["start"] >= week_ago:
            week["focused"] += summary["focused"]
            week["distracted"] += summary["distracted"]
            if c:
                c["week_focused"] += summary["focused"]
        recent.append({"id": s["id"], "class": names.get(s["class_id"], "—"), "mode": s["mode"],
                       "start": s["start"], **summary})

    today = date.fromtimestamp(now)
    upcoming = []
    for d in deadlines:
        days_left = (date.fromisoformat(d["due_date"]) - today).days
        if days_left < 0:
            continue
        week_hours = per_class[d["class_id"]]["week_focused"] / 3600 if d["class_id"] in per_class else 0
        upcoming.append({
            "id": d["id"], "class": names.get(d["class_id"], "—"), "title": d["title"],
            "due_date": d["due_date"], "days_left": days_left, "week_hours": week_hours,
            # ponytail: fixed rule (due within 2 weeks and < low_study_hours focused this week);
            # scale by deadline weight / days left if it flags the wrong things
            "low": days_left <= 14 and week_hours < low_study_hours,
        })

    return {
        "classes": sorted(per_class.values(), key=lambda c: -c["focused"]),
        "recent_sessions": recent[::-1][:10],
        "personal_best": best,
        "top_distractions": [{"name": n, "seconds": s} for n, s in
                             sorted(distractions.items(), key=lambda kv: -kv[1])[:10]],
        "week": {**week, "productivity": productivity(week["focused"], week["distracted"])},
        "deadlines": sorted(upcoming, key=lambda d: d["due_date"]),
    }
