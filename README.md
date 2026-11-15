# [NAME] 📚

A study monitor that keeps you focused, tracks your progress, and tells you what to study next.

**Platform:** macOS first, iPad later
**Stack:** Python + PyObjC, SQLite, Flask + Chart.js

## Setup

Requires macOS and Python 3.12.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On first run, `config.json` is created from `config.example.json`. It's git-ignored, so your allowlist stays yours.

### macOS permissions

macOS asks for these the first time they're needed. If you missed a prompt, turn them on in **System Settings → Privacy & Security**:

- **Automation:** allow the app you run Python from (VS Code or Terminal) to control each browser you use (Google Chrome, Safari, Brave, Edge, Arc). Without this, websites can't be detected and browser tabs show up as neutral.
- **Notifications:** allow **Script Editor**. macOS sends `osascript` notifications under Script Editor's name, so warnings won't appear without it.

## Run

```bash
python main.py                  # pick a class and timer, then start monitoring
python -m rules.config_editor   # edit allowed apps/sites, mode, persona, grace period
```

- Dashboard: http://127.0.0.1:5050. It shows live status, the session timer and a pause button, plus
  stats (last 7 days, personal best, per-class hours, top distractions, recent sessions) and deadlines.
  Add deadlines there. One is flagged ⚠️ when it's due within 2 weeks and you've studied that class less than
  `low_study_hours` (default 3) this week.
- Stop with Ctrl+C. You get a session summary (total time, focused time, productivity %, warnings).
- Pomodoro lengths and round count, the idle cutoff, and the deadline flag are in `config.json`
  (`pomodoro_*`, `idle_seconds`, `low_study_hours`).

## Tests

```bash
python -m pytest
```

The tests cover the focus tracker, allowlist rules, duration stats, the dashboard report, and the Pomodoro timer. None of them call macOS APIs, so they also run without PyObjC.

## Known limitations

- Only the frontmost window is checked. A distracting video in a second window or on another monitor goes unnoticed.
- Only the active tab of the front browser window is read.
- Pausing doesn't freeze the Pomodoro clock: it keeps running on wall-clock time.
- Productivity = focused ÷ (focused + distracted). Idle, neutral, pause, and break time count neither for nor against you.
- The dashboard needs internet once to load Chart.js from a CDN. Without it the chart is skipped and everything else still works.
- Up to ~40 seconds before a sleep or crash may be left out of the stats (time is tracked with a 30s heartbeat).

## Roadmap

### Phase 0: Decisions & Setup
- [x] Choose the stack (Python + PyObjC for Mac)
- [x] Set up the repo, virtual environment, and project folders
  ```
  study-monitor/
    monitor/      # active app/URL detection
    rules/        # allowlist + grace-period logic
    sessions/     # timer, class picker, logging
    data/         # SQLite database
    dashboard/    # stats + deadlines UI
  ```

### Phase 1: Core Detector
Print what you're looking at once per second.
- [x] Detect the frontmost app (`NSWorkspace`)
- [x] Detect the active browser tab URL (Chrome, Safari, Brave, Edge, Arc via AppleScript)
- [x] Handle macOS Automation and Accessibility permissions

### Phase 2: Rules, Warnings & Enforcement
- [x] Allowlist of apps and website domains (`config.json`)
- [x] Grace-period state machine: `FOCUSED` → `DRIFTING` → `DISTRACTED` (configurable, e.g. 5 vs. 10 sec)
- [x] **Gentle mode:** notification or popup reminding you to get back to studying
- [x] **Strict mode:** bring the last allowed app back to the front
- [x] Character personas that change the tone of warnings (*kind*, *stern*, *drill sergeant*, ...)

### Phase 3: Sessions, Timers & Class Picker
- [x] SQLite database (`classes`, `sessions`, `events`, `deadlines`)
- [x] Pick a class before starting a session
- [x] Regular timer and Pomodoro timer (e.g. 25/5)
- [x] Log every app/site switch during a session

### Phase 4: Stats & Dashboard
- [x] Productivity %: focused time ÷ (focused + distracted time)
- [x] Personal Best: longest unbroken focused stretch
- [x] Top distracting websites/apps, ranked
- [x] Per-class totals: see which classes you've studied most and which need more attention
- [x] Deadline dashboard: upcoming midterms/finals sorted by date, flagged when study hours are low
- [x] Local web dashboard (Flask + Chart.js)
- [ ] Menu bar app (`rumps`)

### Phase 5: Package as a Real App
- [ ] Package as a `.app` with `py2app`
- [ ] Start at login
- [ ] Settings screen: allowlist, grace period, persona (terminal version done: `python -m rules.config_editor`)
- [x] Pause button (on the dashboard)
- [ ] Dogfood it for a week and fix what annoys you

### Phase 6: Webcam Phone Detection (Stretch)
- [ ] Grab a webcam frame every 3–5 seconds with OpenCV
- [ ] Detect "cell phone" with YOLOv8n (pretrained on COCO)
- [ ] Count a distraction only after a few consecutive detections
- [ ] Opt-in, processed locally, frames never saved

### Phase 7: iPad Integration (Stretch)
- [ ] Swift/SwiftUI companion app
- [ ] Use Apple's Screen Time API (FamilyControls / DeviceActivity) to block distracting apps during a session
- [ ] Sync sessions between Mac and iPad (iCloud or a small backend)
- [ ] Note: iPadOS doesn't let apps read other apps' usage, so the iPad can block distractions but not track them. This also needs a paid Apple Developer account.
