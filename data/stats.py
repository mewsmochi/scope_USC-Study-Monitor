"""Turns logged events into time spent per status."""
from collections import defaultdict

# Lifecycle events that start a stretch of non-study time; every other lifecycle event
# (started, stopped, resumed, break_end) ends the current stretch.
_LIFECYCLE_STATUS = {"paused": "paused", "break_start": "break"}


def durations(events, max_gap):
    """events: rows with ts, kind, status (oldest first). Returns {status: seconds}.

    Each activity/heartbeat row means "this status until the next row". Gaps longer than
    max_gap (laptop asleep, crash, killed process) are not counted at all.
    """
    totals = defaultdict(float)
    current = None
    for row, nxt in zip(events, events[1:]):
        if row["kind"] in ("activity", "heartbeat"):
            current = row["status"]
        elif row["kind"] == "lifecycle":
            current = _LIFECYCLE_STATUS.get(row["status"])
        # alerts don't change what you're doing; they just split the interval
        gap = nxt["ts"] - row["ts"]
        if current and 0 <= gap <= max_gap:
            totals[current] += gap
    return dict(totals)


def summarize(events, max_gap):
    """Numbers for the end-of-session summary."""
    t = durations(events, max_gap)
    focused, distracted = t.get("allowed", 0.0), t.get("distracting", 0.0)
    judged = focused + distracted
    return {
        "total": sum(t.values()),
        "focused": focused,
        "distracted": distracted,
        # Breaks, idle, pauses, and neutral apps don't count for or against you
        "productivity": 100 * focused / judged if judged else None,
        "warnings": sum(1 for e in events if e["status"] in ("distracted", "still_distracted")),
    }
