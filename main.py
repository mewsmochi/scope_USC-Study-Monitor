import json
import time
from datetime import datetime
from pathlib import Path

from AppKit import NSRunLoop, NSDate

from monitor.detector import get_current_activity
from rules.allowlist import classify
from rules.focus_tracker import FocusTracker
from alerts.messages import pick_message
from alerts.actions import notify, force_back

CONFIG = json.loads((Path(__file__).parent / "config.json").read_text())
POLL_SECONDS = 1.0


def wait(seconds):
    NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(seconds))


def label(activity):
    if activity["domain"]:
        return f'{activity["app"]} — {activity["domain"]}'
    return activity["app"]


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
        if CONFIG["mode"] == "force":
            force_back(tracker.last_allowed)
    elif event == "refocused":
        log(f"   ✅ {pick_message(CONFIG['persona'], 'refocused', where)}")


def main():
    tracker = FocusTracker(CONFIG["grace_seconds"], CONFIG["repeat_seconds"])
    log(f"Study Monitor on: mode={CONFIG['mode']}, persona={CONFIG['persona']}, "
        f"grace={CONFIG['grace_seconds']}s (Ctrl+C to stop)")
    last_label = None

    while True:
        activity = get_current_activity()
        status = classify(activity, CONFIG)

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