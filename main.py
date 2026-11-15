import signal
import threading
import time
from datetime import datetime

from AppKit import NSRunLoop, NSDate

from monitor.detector import get_current_activity, get_idle_seconds
from rules.allowlist import classify
from rules.focus_tracker import FocusTracker
from alerts.messages import pick_message
from alerts.actions import notify, force_back
from rules.config_editor import load_config
from data.db import init_db, log_event

import state
from dashboard.server import run as run_dashboard


CONFIG = load_config()
POLL_SECONDS = 1.0
RELOAD_SECONDS = 5
# Events are only logged on change, so re-log the current status this often;
# stats then treat any gap longer than MAX_GAP_SECONDS as sleep/crash and skip it.
HEARTBEAT_SECONDS = 30
MAX_GAP_SECONDS = HEARTBEAT_SECONDS + 2 * POLL_SECONDS + 10


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


def current_status(activity):
    status = classify(activity, CONFIG)
    # Idle only overrides allowed/neutral: a video left playing on YouTube still counts as distracting
    if status != "distracting" and get_idle_seconds() > CONFIG["idle_seconds"]:
        return "idle"
    return status


def handle(event, activity, tracker):
    where = label(activity)
    if event == "drifting":
        log(f"   drifting... {CONFIG['grace_seconds']}s grace period started")
        return
    log_event(activity["app"], activity["domain"], event)
    if event in ("distracted", "still_distracted"):
        text = pick_message(CONFIG["persona"], event, where)
        log(f"   ⚠️  {text}")
        notify("Study Monitor", text)
        #added "event == distracted" so no new tab every repeat_seconds
        if CONFIG["mode"] == "force" and event == "distracted":
            target = tracker.last_allowed
            force_back(target)
            if target:
                log_event(target["app"], target["domain"], "forced")
    elif event == "refocused":
        log(f"   ✅ {pick_message(CONFIG['persona'], 'refocused', where)}")


def stop_on_signal(signum, frame):
    # SIGTERM (kill) and SIGHUP (terminal window closed) would otherwise skip the "stopped" log
    raise SystemExit(0)


def main():
    global CONFIG
    init_db()
    threading.Thread(target=run_dashboard, daemon=True).start()
    tracker = FocusTracker(CONFIG["grace_seconds"], CONFIG["repeat_seconds"])
    log(f"Study Monitor on: mode={CONFIG['mode']}, persona={CONFIG['persona']}, "
        f"grace={CONFIG['grace_seconds']}s (Ctrl+C to stop)")
    log_event(None, None, "started")
    last_logged = None      # (label, status) of the last activity row
    last_write = 0.0        # wall-clock time of the last activity/heartbeat row
    was_paused = False
    last_reload = time.monotonic()

    while True:
        # Pick up edits from the config menu (or a future settings page)
        if time.monotonic() - last_reload >= RELOAD_SECONDS:
            try:
                CONFIG = load_config()
                tracker.grace = CONFIG["grace_seconds"]
                tracker.repeat = CONFIG["repeat_seconds"]
            except SystemExit:   # load_config exits on invalid JSON
                log("   config.json has an error, keeping the previous settings")
            last_reload = time.monotonic()

        activity = get_current_activity()
        status = current_status(activity)

        # Publish to the dashboard's shared board (see state.py)
        state.update(status=status, app=activity["app"], domain=activity["domain"])

        # Paused from the dashboard: keep showing live activity, but skip warnings
        paused = state.snapshot()["paused"]
        if paused and not was_paused:
            log_event(None, None, "paused")   # marks when the pause began
        elif was_paused and not paused:
            log_event(None, None, "resumed")
            tracker.reset()      # clear old drift timers so they can't fire instantly (keeps last_allowed)
            last_logged = None   # forces the current activity to be logged again
        was_paused = paused

        current = (label(activity), "paused" if paused else status)
        if not paused and current != last_logged:
            log(f"{current[0]}  [{status}]")
            log_event(activity["app"], activity["domain"], status)
            last_logged, last_write = current, time.time()
        elif time.time() - last_write >= HEARTBEAT_SECONDS:
            log_event(activity["app"], activity["domain"], current[1], heartbeat=True)
            last_write = time.time()

        if not paused:
            event = tracker.update(activity, status, time.monotonic())
            if event:
                handle(event, activity, tracker)

        wait(POLL_SECONDS)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, stop_on_signal)
    signal.signal(signal.SIGHUP, stop_on_signal)
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        log_event(None, None, "stopped")
        try:
            print("\nStopped.")
        except OSError:   # terminal already closed (SIGHUP)
            pass
