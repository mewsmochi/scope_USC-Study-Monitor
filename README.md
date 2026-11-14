# [NAME] 📚

A study monitor that keeps you focused, tracks your progress, and tells you what to study next.

**Platform:** macOS first, iPad later
**Stack:** Python + PyObjC, SQLite, Flask + Chart.js

## Roadmap

### Phase 0: Decisions & Setup
- [ ] Choose the stack (Python + PyObjC for Mac)
- [ ] Set up the repo, virtual environment, and project folders
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
- [ ] Detect the frontmost app (`NSWorkspace`)
- [ ] Detect the active browser tab URL (Chrome and Safari via AppleScript)
- [ ] Handle macOS Automation and Accessibility permissions

### Phase 2: Rules, Warnings & Enforcement
- [ ] Allowlist of apps and website domains (`allowlist.json`)
- [ ] Grace-period state machine: `FOCUSED` → `DRIFTING` → `DISTRACTED` (configurable, e.g. 5 vs. 10 sec)
- [ ] **Gentle mode:** notification or popup reminding you to get back to studying
- [ ] **Strict mode:** bring the last allowed app back to the front
- [ ] Character personas that change the tone of warnings (*kind*, *stern*, *drill sergeant*, ...)

### Phase 3: Sessions, Timers & Class Picker
- [ ] SQLite database (`classes`, `sessions`, `events`, `deadlines`)
- [ ] Pick a class before starting a session
- [ ] Regular timer and Pomodoro timer (e.g. 25/5)
- [ ] Log every app/site switch during a session

### Phase 4: Stats & Dashboard
- [ ] Productivity %: time on allowed apps ÷ total session time
- [ ] Personal Best: longest unbroken focused stretch
- [ ] Top distracting websites/apps, ranked
- [ ] Per-class totals: see which classes you've studied most and which need more attention
- [ ] Deadline dashboard: upcoming midterms/finals sorted by date, flagged when study hours are low
- [ ] Menu bar app (`rumps`) and local web dashboard (Flask + Chart.js)

### Phase 5: Package as a Real App
- [ ] Package as a `.app` with `py2app`
- [ ] Start at login
- [ ] Settings screen: allowlist, grace period, persona
- [ ] Pause button
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
