# Tunnl 📚

A study monitor that keeps you focused, tracks your progress, and tells you what to study next.

Tunnl watches which app or website you're on during a study session. If you drift off your allowed list, it gives you a heads-up, then (optionally) pulls you back. It records every session so you can see your focus, your biggest distractions, and which deadline needs attention first.

**Platform:** macOS
**Stack:** Python + PyObjC, SQLite, Flask, Chart.js

## Features

- **Focus monitoring:** detects the frontmost app and the active browser tab (Chrome, Safari, Brave, Edge, Arc).
- **Allowlist:** apps and websites that count as studying. Everything else starts a grace-period timer.
- **Two warning modes:**
  - **Warn:** a notification as soon as you drift, and another once the grace period runs out.
  - **Force:** the same heads-up, then Tunnl switches you back to your last study app or page (reusing the existing tab instead of opening a new one).
- **Personas:** *Base*, *Kind* and *Stern* change the tone of the warnings.
- **Sessions:** pick a class, then run a Regular (counts up) or Pomodoro timer. Pomodoro focus, break and round counts can be set per session.
- **Pause button** for breaks, plus idle detection.
- **Stats:** productivity %, last 7 days, personal best, per-class focused hours, top distractions, recent sessions.
- **Deadlines:** add midterms and finals, see the next one coming up and what to study first. A deadline is flagged ⚠️ when it's due within 2 weeks and you've studied that class less than your weekly target.
- **Settings tab:** change mode, persona and timers, and edit the allowlist from the dashboard. "Allow what I'm on now" saves exactly what the monitor sees, so names always match.

## Setup

Requires macOS and Python 3.12.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On first run, `config.json` is created from `config.example.json`. It's git-ignored, so your allowlist stays yours.

### macOS permissions

macOS asks for these the first time they're needed. If you missed a prompt, turn them on in **System Settings → Privacy & Security** (or **Notifications**):

- **Automation:** allow the app you run Python from (VS Code or Terminal) to control each browser you use. Tunnl needs this to read the current tab's URL and to switch back to a study tab in Force mode. Without it, websites can't be detected and browser tabs show up as neutral.
- **Notifications:** allow **Script Editor**. macOS sends `osascript` notifications under Script Editor's name, so warnings won't appear without it. Also check that no Focus mode (Do Not Disturb) is on.

## Run

```bash
python main.py                  # starts the monitor and the dashboard
python -m rules.config_editor   # optional terminal menu for the same settings
```

Open http://127.0.0.1:5050 (the dashboard only listens on your own computer).

1. **Settings tab → Allowed apps and websites:** click **Allow what I'm on now** (recommended), then within 5 seconds switch to the app or site you want to allow. The dashboard can't see other apps, so it saves whatever is in front when the countdown ends. Do this for each study app and site.
2. **Dashboard tab:** pick or add a class, choose Regular or Pomodoro, and press **Start session**.
3. Study. Leave your allowed list and you'll get a heads-up; stay away past the grace period and you'll get a second message (and be sent back in Force mode).
4. Press **Stop session** (a Pomodoro session also ends after its last round). You get a summary of total time, focused time, productivity % and warnings, in the terminal and on the dashboard. Ctrl+C quits Tunnl and closes any running session first.

Warnings and logging only happen while a session is running.

## Settings

Change these in the Settings tab (applied within about 5 seconds), or edit `config.json`:

| Setting | Meaning |
|---|---|
| `mode` | `warn` or `force` |
| `persona` | `base`, `kind` or `stern` |
| `grace_seconds` | time off the allowlist before the second warning |
| `repeat_seconds` | how often the "still distracted" reminder repeats |
| `idle_seconds` | no input for this long counts as idle |
| `pomodoro_work_minutes`, `pomodoro_break_minutes`, `pomodoro_rounds` | defaults for Pomodoro sessions |
| `low_study_hours` | weekly hours below which a deadline is flagged |

Pomodoro changes apply to the next session.

## Project layout

```
main.py         # monitor loop: detect, classify, warn, log
monitor/        # frontmost app and browser URL detection
rules/          # allowlist rules, focus tracker, config editor
alerts/         # notifications, force-back, persona messages
sessions/       # session control and Pomodoro timer
data/           # SQLite database and stats
dashboard/      # Flask server, page, scripts and styles
tests/          # pytest suite
```

## Tests

```bash
python -m pytest
```

The tests cover the focus tracker, allowlist rules, duration stats, the dashboard report, the Pomodoro timer, and the dashboard API (including blocking requests from other websites). None of them call macOS APIs, so they also run without PyObjC. GitHub Actions runs them on Linux for every PR and every push to `main`.

## Known limitations

- Only the frontmost window is checked. A distracting video in a second window or on another monitor goes unnoticed.
- Only the active tab of the front browser window is read.
- Pausing doesn't freeze the timer display or the Pomodoro clock: they keep running on wall-clock time.
- Productivity = focused ÷ (focused + distracted). Idle, neutral, pause and break time count neither for nor against you.
- Typed app names must match the name macOS reports for the running app (for example VS Code is `Code`). Use **Allow what I'm on now** to avoid mismatches.
- The dashboard needs internet once to load Chart.js and the title font. Without it the chart is skipped and the title uses a system font; everything else still works.
- Up to ~40 seconds before a sleep or crash may be left out of the stats (time is tracked with a 30s heartbeat).

## Roadmap

**Done**
- [x] Core detector: frontmost app and browser tab URL
- [x] Allowlist, grace-period state machine, Warn and Force modes, personas
- [x] Sessions, class picker, Regular and Pomodoro timers
- [x] SQLite event logging
- [x] Stats, deadlines, and the web dashboard
- [x] Settings and allowlist editor on the dashboard
- [x] Pause button

**Next**
- [ ] Freeze the timer while paused
- [ ] Menu bar app (`rumps`)
- [ ] Package as a `.app` with `py2app`, with start at login

## Future ideas

These were part of the original plan but aren't built yet.

- **Webcam phone detection:** grab a webcam frame every few seconds with OpenCV, detect "cell phone" with YOLOv8n (pretrained on COCO), and count a distraction only after several consecutive detections. It would be opt-in, processed locally, with frames never saved.
- **iPad companion app (Swift/SwiftUI):** iPadOS doesn't let apps see which other apps you use, so the iPad app could only *block* distracting apps during a session through Apple's Screen Time API (FamilyControls / DeviceActivity), not track them. Needs a paid Apple Developer account, plus a way to sync sessions with the Mac.
