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
from data.db import init_db, log_event, start_session, end_session, session_events
from data.stats import summarize
from sessions.picker import pick_class, pick_timer
from sessions.timer import pomodoro_phase

import state
from dashboard.server import run as run_dashboard


CONFIG = load_config()
POLL_SECONDS = 1.0
RELOAD_SECONDS = 5
# Events are only logged on change, so re-log the current status this often;
# stats then treat any gap longer than MAX_GAP_SECONDS as sleep/crash and skip it.
HEARTBEAT_SECONDS = 30
MAX_GAP_SECONDS = HEARTBEAT_SECONDS + 2 * POLL_SECONDS + 10

SESSION = None   # {"id", "class", "mode", "start", "pomodoro": (work, break, rounds) in seconds}


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


def record(status, activity=None, heartbeat=False):
    """log_event, tagged with the current session."""
    a = activity or {}
    log_event(a.get("app"), a.get("domain"), status, SESSION and SESSION["id"], heartbeat)


def fmt(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m {s:02d}s"


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
    record(event, activity)
    if event in ("distracted", "still_distracted"):
        text = pick_message(CONFIG["persona"], event, where)
        log(f"   ⚠️  {text}")
        notify("Study Monitor", text)
        #added "event == distracted" so no new tab every repeat_seconds
        if CONFIG["mode"] == "force" and event == "distracted":
            target = tracker.last_allowed
            force_back(target)
            if target:
                record("forced", target)
    elif event == "refocused":
        log(f"   ✅ {pick_message(CONFIG['persona'], 'refocused', where)}")


def start():
    """Ask for class and timer, then create the session row."""
    global SESSION
    class_id, class_name = pick_class()
    mode = pick_timer(CONFIG)
    # Pomodoro lengths are fixed for the session, even if config.json changes mid-way
    pomodoro = (CONFIG["pomodoro_work_minutes"] * 60, CONFIG["pomodoro_break_minutes"] * 60,
                CONFIG["pomodoro_rounds"])
    SESSION = {"id": start_session(class_id, mode), "class": class_name, "mode": mode,
               "start": time.time(), "pomodoro": pomodoro}
    record("started")


def timer_tick(last_phase):
    """Returns the pomodoro phase ("work"/"break"/"done") and publishes the timer to the dashboard."""
    elapsed = time.time() - SESSION["start"]   # ponytail: wall clock, pausing doesn't freeze the pomodoro
    info = {"class": SESSION["class"], "mode": SESSION["mode"], "elapsed": elapsed}
    phase = "work"
    if SESSION["mode"] == "pomodoro":
        work, brk, rounds = SESSION["pomodoro"]
        phase, rnd, left = pomodoro_phase(elapsed, work, brk, rounds)
        info.update(phase=phase, round=rnd, rounds=rounds, remaining=left)
        if last_phase and phase != last_phase:
            if phase == "break":
                record("break_start")
                text = f"Round {rnd} of {rounds} done. Take a {brk // 60}-minute break."
            elif phase == "work":
                record("break_end")
                text = f"Break's over. Round {rnd} of {rounds}, let's go."
            else:
                text = f"Session complete: {rounds} rounds done!"
            log(f"⏱  {text}")
            notify("Study Monitor", text)
    state.update(session=info)
    return phase


def main():
    global CONFIG
    init_db()
    start()
    threading.Thread(target=run_dashboard, daemon=True).start()
    tracker = FocusTracker(CONFIG["grace_seconds"], CONFIG["repeat_seconds"])
    log(f"Studying {SESSION['class']} ({SESSION['mode']}): mode={CONFIG['mode']}, "
        f"persona={CONFIG['persona']}, grace={CONFIG['grace_seconds']}s (Ctrl+C to stop)")
    log("Dashboard: http://127.0.0.1:5050")
    last_logged = None      # (label, status) of the last activity row
    last_write = 0.0        # wall-clock time of the last activity/heartbeat row
    was_paused = False
    was_held = False        # paused or on a break: no warnings
    phase = None
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

        new_phase = timer_tick(phase)
        if new_phase == "done":
            return
        if new_phase != phase:
            last_write = 0.0   # log the new state right away
        phase = new_phase

        activity = get_current_activity()
        status = current_status(activity)

        # Paused from the dashboard: keep showing live activity, but skip warnings
        paused = state.snapshot()["paused"]
        if paused != was_paused:
            record("paused" if paused else "resumed")
            last_write = 0.0
        was_paused = paused

        held = "paused" if paused else ("break" if phase == "break" else None)
        if was_held and not held:
            tracker.reset()      # clear old drift timers so they can't fire instantly (keeps last_allowed)
            last_logged = None   # forces the current activity to be logged again
        was_held = bool(held)

        # Publish to the dashboard's shared board (see state.py)
        state.update(status=held or status, app=activity["app"], domain=activity["domain"])

        current = (label(activity), status)
        if not held and current != last_logged:
            log(f"{current[0]}  [{status}]")
            record(status, activity)
            last_logged, last_write = current, time.time()
        elif time.time() - last_write >= HEARTBEAT_SECONDS:
            record(held or status, activity, heartbeat=True)
            last_write = time.time()

        if not held:
            event = tracker.update(activity, status, time.monotonic())
            if event:
                handle(event, activity, tracker)

        wait(POLL_SECONDS)


def finish():
    """Close the session and print a summary. Runs on timer done, Ctrl+C, SIGTERM, or SIGHUP."""
    if SESSION is None:   # quit during the class/timer prompts
        return
    record("stopped")
    end_session(SESSION["id"])
    s = summarize(session_events(SESSION["id"]), MAX_GAP_SECONDS)
    productivity = f"{s['productivity']:.0f}%" if s["productivity"] is not None else "—"
    try:
        print(f"\nSession summary: {SESSION['class']} ({SESSION['mode']})\n"
              f"  Total time:    {fmt(s['total'])}\n"
              f"  Focused:       {fmt(s['focused'])}\n"
              f"  Productivity:  {productivity}  (focused ÷ (focused + distracted))\n"
              f"  Warnings:      {s['warnings']}")
    except OSError:   # terminal already closed (SIGHUP)
        pass


def stop_on_signal(signum, frame):
    # SIGTERM (kill) and SIGHUP (terminal window closed) would otherwise skip the "stopped" log
    raise SystemExit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, stop_on_signal)
    signal.signal(signal.SIGHUP, stop_on_signal)
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        finish()
