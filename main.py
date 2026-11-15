# site url: http://127.0.0.1:5050

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
from data.db import init_db, log_event, session_events, close_orphan_sessions
from data.stats import summarize, HEARTBEAT_SECONDS, MAX_GAP_SECONDS
from sessions import control
from sessions.timer import pomodoro_phase

import state
from dashboard.server import run as run_dashboard


CONFIG = load_config()
POLL_SECONDS = 1.0
RELOAD_SECONDS = 5


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


def handle(event, activity, tracker, sid):
    where = label(activity)
    if event == "drifting":
        log(f"   drifting... {CONFIG['grace_seconds']}s grace period started")
        # Heads-up right as you leave the allowed list, before anything is forced
        text = pick_message(CONFIG["persona"], "drifting", where, seconds=CONFIG["grace_seconds"])
        log(f"   ⏳ {text}")
        notify("Study Monitor", text)
        return
    log_event(activity["app"], activity["domain"], event, sid)
    if event in ("distracted", "still_distracted"):
        # Force first (once per episode), so this notification arrives after you're pulled back
        forced = CONFIG["mode"] == "force" and event == "distracted"
        target = tracker.last_allowed
        if forced:
            force_back(target)
            if target:
                log_event(target["app"], target["domain"], "forced", sid)
        # In force mode the message says you were sent back; in warn mode it just nudges you
        key = "distracted_forced" if forced else event
        text = pick_message(CONFIG["persona"], key, where)
        log(f"   ⚠️  {text}")
        notify("Study Monitor", text)
    elif event == "refocused":
        log(f"   ✅ {pick_message(CONFIG['persona'], 'refocused', where)}")

def timer_tick(snap, last_phase):
    """Returns the pomodoro phase ("work"/"break"/"done") and publishes it to the dashboard."""
    if snap["mode"] != "pomodoro":
        return "work"
    sid = snap["session_id"]
    work, brk, rounds = snap["pomodoro"]
    # ponytail: wall clock, pausing doesn't freeze the pomodoro
    phase, rnd, left = pomodoro_phase(time.time() - snap["session_start"], work, brk, rounds)
    state.update(timer={"phase": phase, "round": rnd, "rounds": rounds, "remaining": left})
    if last_phase and phase != last_phase:
        if phase == "break":
            log_event(None, None, "break_start", sid)
            text = f"Round {rnd} of {rounds} done. Take a {brk // 60}-minute break."
        elif phase == "work":
            log_event(None, None, "break_end", sid)
            text = f"Break's over. Round {rnd} of {rounds}, let's go."
        else:
            text = f"Session complete: {rounds} rounds done!"
        log(f"⏱  {text}")
        notify("Study Monitor", text)
    return phase


def summarize_session(sid, class_name, mode):
    """Print the summary of a finished session and put it on the dashboard."""
    s = summarize(session_events(sid), MAX_GAP_SECONDS)
    state.update(last_summary={"class": class_name, "mode": mode, **s})
    productivity = f"{s['productivity']:.0f}%" if s["productivity"] is not None else "—"
    try:
        print(f"\nSession summary: {class_name} ({mode})\n"
              f"  Total time:    {fmt(s['total'])}\n"
              f"  Focused:       {fmt(s['focused'])}\n"
              f"  Productivity:  {productivity}  (focused ÷ (focused + distracted))\n"
              f"  Warnings:      {s['warnings']}\n")
    except OSError:   # terminal already closed (SIGHUP)
        pass


def main():
    global CONFIG
    init_db()
    close_orphan_sessions()   # tidy up any session left open by a crash
    threading.Thread(target=run_dashboard, daemon=True).start()   # dashboard runs in the background
    tracker = FocusTracker(CONFIG["grace_seconds"], CONFIG["repeat_seconds"])
    log(f"Study Monitor on: mode={CONFIG['mode']}, persona={CONFIG['persona']}, "
        f"grace={CONFIG['grace_seconds']}s (Ctrl+C to quit)")
    log("Open http://127.0.0.1:5050 to pick a class and start a session")
    active = None           # (session_id, class_name, mode) the loop is tracking
    last_logged = None      # (label, status) of the last activity row
    last_write = 0.0        # wall-clock time of the last activity/heartbeat row
    was_paused = was_held = False
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

        activity = get_current_activity()
        status = current_status(activity)
        snap = state.snapshot()
        sid = snap["session_id"]

        # Session started or stopped from the dashboard (or by the pomodoro timer)
        if active and active[0] != sid:
            log("Session ended")
            summarize_session(*active)
            active = None
        if sid is not None and active is None:
            active = (sid, snap["class_name"], snap["mode"])
            tracker.reset()   # fresh timers for the new session (keeps last_allowed)
            last_logged, last_write, was_paused, was_held, phase = None, 0.0, False, False, None
            log(f"Session started: {snap['class_name']} ({snap['mode']})")

        # No session running: show live activity but track nothing
        if sid is None:
            state.update(status=status, app=activity["app"], domain=activity["domain"])
            wait(POLL_SECONDS)
            continue

        new_phase = timer_tick(snap, phase)
        if new_phase == "done":
            control.stop()   # next loop prints the summary
            continue
        if new_phase != phase:
            last_write = 0.0   # log the new state right away
        phase = new_phase

        # Paused from the dashboard: keep showing live activity, but skip warnings
        paused = snap["paused"]
        if paused != was_paused:
            log_event(None, None, "paused" if paused else "resumed", sid)
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
            log_event(activity["app"], activity["domain"], status, sid)
            last_logged, last_write = current, time.time()
        elif time.time() - last_write >= HEARTBEAT_SECONDS:
            log_event(activity["app"], activity["domain"], held or status, sid, heartbeat=True)
            last_write = time.time()

        if not held:
            event = tracker.update(activity, status, time.monotonic())
            if event:
                handle(event, activity, tracker, sid)

        wait(POLL_SECONDS)


def finish():
    """Ctrl+C, SIGTERM, or SIGHUP: close a running session properly and print its summary."""
    snap = state.snapshot()
    if control.stop() is not None:
        summarize_session(snap["session_id"], snap["class_name"], snap["mode"])
    try:
        print("Stopped.")
    except OSError:
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
