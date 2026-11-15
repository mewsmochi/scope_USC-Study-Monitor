import time
from datetime import datetime

from AppKit import NSRunLoop, NSDate

from monitor.detector import get_current_activity
from rules.allowlist import classify
from rules.focus_tracker import FocusTracker
from alerts.messages import pick_message
from alerts.actions import notify, force_back
from rules.config_editor import load_config

import threading
import state
from dashboard.server import run as run_dashboard


CONFIG = load_config()
POLL_SECONDS = 1.0


def wait(seconds):
    NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(seconds))


def label(activity):
    # Use "Unknown" if front app can't be detected (i.e app is None)
    # so the log never prints "None"
    app = activity["app"] or "Unknown"
    if activity["domain"]:
        return f'{app} — {activity["domain"]}'
    return app


def log(text):
    print(f"[{datetime.now():%H:%M:%S}] {text}")


def handle(event, activity, tracker):
    where = label(activity)
    if event == "drifting":
        log(f"   drifting... {CONFIG['grace_seconds']}s grace period started")
    elif event in ("distracted", "still_distracted"):
        text = pick_message(CONFIG["persona"], event, where)
        log(f"   ⚠️  {text}")
        notify("Study Monitor", text)
        #added "event == distracted" so no new tab every repeat_seconds
        if CONFIG["mode"] == "force" and event == "distracted": 
            force_back(tracker.last_allowed)
    elif event == "refocused":
        log(f"   ✅ {pick_message(CONFIG['persona'], 'refocused', where)}")


def main():
    threading.Thread(target=run_dashboard, daemon=True).start()
    tracker = FocusTracker(CONFIG["grace_seconds"], CONFIG["repeat_seconds"])
    log(f"Study Monitor on: mode={CONFIG['mode']}, persona={CONFIG['persona']}, "
        f"grace={CONFIG['grace_seconds']}s (Ctrl+C to stop)")
    last_label = None
    was_paused = False

    while True:
        activity = get_current_activity()
        status = classify(activity, CONFIG)

        # Publish to the dashboard's shared board (see state.py)
        state.update(status=status, app=activity["app"], domain=activity["domain"])

        # Paused from the dashboard: keep showing live activity, but skip warnings
        paused = state.snapshot()["paused"]
        if paused:
            was_paused = True
            wait(POLL_SECONDS)
            continue
        if was_paused:
            # Resuming: start with a fresh tracker so an old drift timer can't fire instantly
            tracker = FocusTracker(CONFIG["grace_seconds"], CONFIG["repeat_seconds"])
            was_paused = False

        current = label(activity)
        if current != last_label:
            log(f"{current}  [{status}]")
            last_label = current

        event = tracker.update(activity, status, time.monotonic())
        if event:
            handle(event, activity, tracker)

        wait(POLL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")