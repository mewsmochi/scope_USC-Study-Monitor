# Tunnl 📚
 
A study monitor that keeps you focused, tracks your progress, and tells you what to study next.
 
Tunnl watches which app or website you're on during a study session. If you drift off your allowed list, it warns you and (optionally) pulls you back. With the optional **Focus Mode**, it can also warn you when you look away from the screen. It records every session so you can see your focus, your biggest distractions, and which deadline needs attention first.
 
**Platform:** macOS
**Stack:** Python + PyObjC, SQLite, Flask, Chart.js
 
## Features
 
- **Focus monitoring:** detects the frontmost app and the active browser tab (Chrome, Safari, Brave, Edge, Arc).
- **Allowlist:** apps and websites that count as studying. Everything else starts a grace-period timer.
- **Two warning modes:**
  - **Warn:** one notification once the grace period runs out, then reminders while you stay off task.
  - **Force:** a heads-up when you drift, then, once the grace period runs out, Tunnl switches you back to your last study app or page (reusing the existing tab instead of opening a new one).
- **Welcome-back message:** when you return to an allowed app after a warning, you get a short message.
- **Focus Mode (optional):** uses your webcam during sessions to notice when you look away from the screen. See [Focus Mode](#focus-mode-optional).
- **Personas:** *Base*, *Kind* and *Stern* change the tone of the messages. Add your own in `alerts/messages.py`.
- **Sessions:** pick a class (or add your first one if the list is empty), then run a Regular (counts up) or Pomodoro timer. Pomodoro focus, break and round counts can be set per session.
- **Pause button** for breaks, plus idle detection.
- **Stats:** productivity %, last 7 days, personal best, per-class focused hours, top distractions, recent sessions.
- **Deadlines:** add midterms and finals, see the next one coming up and what to study first. A deadline is flagged ⚠️ when it's due within 2 weeks and you've studied that class less than your weekly target.
- **Settings tab:** change mode, persona, Focus Mode and timers, and edit the allowlist from the dashboard. "Allow what I'm on now" saves exactly what the monitor sees, so names always match.
## Setup
 
Requires macOS and Python 3.12.
 
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-webcam.txt   # optional: only needed for Focus Mode
```
 
On first run, `config.json` is created from `config.example.json`. It's git-ignored, so your allowlist stays yours. The database (`data/study.db`) is created on first run and is also git-ignored, so a fresh install starts with no classes.
 
### macOS permissions
 
macOS asks for these the first time they're needed. If you missed a prompt, turn them on in **System Settings → Privacy & Security** (or **Notifications**):
 
- **Automation:** allow the app you run Python from (VS Code or Terminal) to control each browser you use. Tunnl needs this to read the current tab's URL and to switch back to a study tab in Force mode. Without it, websites can't be detected and browser tabs show up as neutral.
- **Notifications:** allow **Script Editor**. macOS sends `osascript` notifications under Script Editor's name, so warnings won't appear without it. Also check that no Focus mode (Do Not Disturb) is on.
- **Camera (Focus Mode only):** allow the app you run Python from (VS Code or Terminal) to use the camera. If the prompt hangs when launched from VS Code, run `python main.py` from Terminal once to grant it.
## Run
 
```bash
python main.py                  # starts the monitor and the dashboard
python -m rules.config_editor   # optional terminal menu for the same settings
```
 
Open http://127.0.0.1:5050 (the dashboard only listens on your own computer).
 
1. **Settings tab → Allowed apps and websites:** click **Allow what I'm on now** (recommended), then within 5 seconds switch to the app or site you want to allow. The dashboard can't see other apps, so it saves whatever is in front when the countdown ends. Do this for each study app and site.
2. **Dashboard tab:** pick or add a class, choose Regular or Pomodoro, and press **Start session**.
3. Study. In Warn mode, leave your allowed list and stay away past the grace period and you'll get a warning. In Force mode you get a heads-up when you leave, then you're sent back once the grace period runs out.
4. Press **Stop session** (a Pomodoro session also ends after its last round). You get a summary of total time, focused time, productivity % and warnings, in the terminal and on the dashboard. Ctrl+C quits Tunnl and closes any running session first.
Warnings and logging only happen while a session is running.
 
## Focus Mode (optional)
 
Focus Mode watches your head position through the webcam and warns you when you look away from the screen for too long: turned to the side, tilted down, or out of the frame. A look-away counts as a distraction, so the grace period, warning, repeat reminders and stats all work the same way as for apps. In Force mode there's nothing to switch back to, so you just get the warning.
 
**Turn it on:** tick **Focus Mode** in the Settings tab and save (or set `"focus_mode": true` in `config.json`). The dashboard's Focus Mode line shows whether the camera is calibrating, watching or off.
 
**How it works:**
 
- The camera only runs during a session, and is released when you pause, take a Pomodoro break, or stop.
- Look at your screen for the first few seconds of each session. Tunnl learns your resting head position then, and measures everything relative to it.
- It flags you when your head is about 10° below that position or turned about 30° to the side (or your face leaves the frame) for the **look away for** time, and then the normal grace period applies on top. You can adjust the angles at the top of `webcam/look_away.py`.
**Privacy:** face detection uses Apple's on-device Vision framework. Video frames are processed in memory and never saved or sent anywhere. Focus Mode is off by default.
 
**Not recommended** if you expect to look down for long stretches, like handwriting notes or reading a book. That counts as looking away.
 
## Settings
 
Change these in the Settings tab (applied within about 5 seconds), or edit `config.json`:
 
| Setting | Meaning |
|---|---|
| `mode` | `warn` or `force` |
| `persona` | `base`, `kind` or `stern` |
| `focus_mode` | `true` or `false` (default `false`): webcam look-away alerts |
| `look_away_seconds` | how long you can look away before it counts (the grace period then applies on top) |
| `grace_seconds` | time off the allowlist before the warning |
| `repeat_seconds` | how often the "still distracted" reminder repeats |
| `idle_seconds` | no input for this long counts as idle |
| `pomodoro_work_minutes`, `pomodoro_break_minutes`, `pomodoro_rounds` | defaults for Pomodoro sessions |
| `low_study_hours` | weekly hours below which a deadline is flagged |
 
Pomodoro changes apply to the next session.
 
### Customizing messages
 
Each persona in `alerts/messages.py` maps an event to a list of messages, and Tunnl picks one at random. Add as many variants as you like.
 
- Events: `drifting` (the Force-mode heads-up), `distracted`, `distracted_forced`, `still_distracted`, `refocused`.
- Focus Mode has its own wording, since there's no app name to mention: `away_distracted`, `away_still_distracted`, `away_refocused`.
- `{where}` is the app or site, and `{seconds}` is available in `drifting` only.
- A new persona appears in the dashboard and the terminal menu automatically. A persona missing an event falls back to `base`.
## Project layout
 
```
main.py         # monitor loop: detect, classify, warn, log
monitor/        # frontmost app and browser URL detection
rules/          # allowlist rules, focus tracker, config editor
alerts/         # notifications, force-back, persona messages
sessions/       # session control and Pomodoro timer
webcam/         # Focus Mode: head-angle detection (optional)
data/           # SQLite database and stats
dashboard/      # Flask server, page, scripts and styles
tests/          # pytest suite
```
 
## Tests
 
```bash
python -m pytest
```
 
The tests cover the focus tracker, allowlist rules, duration stats, the dashboard report, the Pomodoro timer, and the dashboard API (including blocking requests from other websites). None of them call macOS APIs, so they also run without PyObjC. GitHub Actions runs them on Linux for every PR and every push to `main`. Focus Mode needs a camera and isn't covered by the automated tests.
 
## Known limitations
 
- Only the frontmost window is checked. A distracting video in a second window or on another monitor goes unnoticed.
- Only the active tab of the front browser window is read.
- Productivity = focused ÷ (focused + distracted). Idle, neutral, pause and break time count neither for nor against you.
- Typed app names must match the name macOS reports for the running app (for example VS Code is `Code`). Use **Allow what I'm on now** to avoid mismatches.
- The dashboard needs internet once to load Chart.js and the title font. Without it the chart is skipped and the title uses a system font; everything else still works.
- Up to ~40 seconds before a sleep or crash may be left out of the stats (time is tracked with a 30s heartbeat).
- Focus Mode follows your head, not your eyes. Moving only your eyes isn't detected, and looking down to write or read counts as looking away. A small head tilt may be missed, and results depend on lighting and camera position.
- Focus Mode can't see a phone or tablet. It only notices that you've turned away from the screen.
## Roadmap
 
**Done**
- [x] Core detector: frontmost app and browser tab URL
- [x] Allowlist, grace-period state machine, Warn and Force modes, personas
- [x] Sessions, class picker, Regular and Pomodoro timers
- [x] SQLite event logging
- [x] Stats, deadlines, and the web dashboard
- [x] Settings and allowlist editor on the dashboard
- [x] Pause button
- [x] Focus Mode: webcam look-away alerts
**Next**
- [ ] Menu bar app (`rumps`)
- [ ] Package as a `.app` with `py2app`, with start at login

## Future ideas
 
- **Phone and iPad usage reports:** a laptop webcam can't reliably see a phone or tablet on the desk (we tried object detection, and Focus Mode looks at head position instead). A better route is for the device to report itself. An iPad Shortcuts automation (or Tasker/MacroDroid on Android) could send a request to Tunnl whenever a distracting app opens, and Tunnl would log it as a distraction. This needs a network-reachable endpoint protected by a secret token, and some campus Wi-Fi networks stop devices from reaching each other, so a hotspot or a private network tool like Tailscale may be needed.
- **iPad companion app (Swift/SwiftUI):** iPadOS doesn't let apps see which other apps you use, so the iPad app could only *block* distracting apps during a session through Apple's Screen Time API (FamilyControls / DeviceActivity), not track them. Needs a paid Apple Developer account, plus a way to sync sessions with the Mac.
 
