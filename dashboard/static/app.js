// page elements that will be updated
const statusEl = document.getElementById("status");                  // <strong id="status">
const appEl = document.getElementById("current-app");               // <span id="current-app">
const domainEl = document.getElementById("current-domain");         // <span id="current-domain">
const pauseButton = document.getElementById("pause-button");        // <button id="pause-button">
const sessionButton = document.getElementById("session-button");    // <button id="session-button">
const sessionInfoEl = document.getElementById("session-info");      // <span id="session-info">
const classSelect = document.getElementById("class-select");        // <select id="class-select">
const newClassInput = document.getElementById("new-class");         // <input id="new-class">
const addClassButton = document.getElementById("add-class-button"); // <button id="add-class-button">
const timerSelect = document.getElementById("timer-select");        // <select id="timer-select">
const summaryEl = document.getElementById("last-summary");          // <p id="last-summary">
const cameraEl = document.getElementById("camera-status");          // <span id="camera-status">
const noClassesEl = document.getElementById("no-classes");
const monitorButton = document.getElementById("monitor-button");   

//Helpers
// POST a JSON body; show the server's error message if it refuses
// Focus-mode camera state (from main.py's LookAwayWatcher) -> friendly text
const CAMERA_TEXT = {
  off: "Off (turn on Focus Mode in Settings)",
  idle: "Not watching right now (no session or paused, or on a break)",
  calibrating: "Calibrating... look at your screen",
  watching: "Watching for look-aways",
};

// Show text in the camera line, with "Focus Mode" in bold italics
function setCamera(text) {
  cameraEl.replaceChildren();
  text.split("Focus Mode").forEach((part, i) => {
    if (i > 0) {
      const b = document.createElement("b");
      const em = document.createElement("i");
      em.textContent = "Focus Mode";
      b.append(em);
      cameraEl.append(b);
    }
    cameraEl.append(part);   // plain text node, never parsed as HTML
  });
}

async function post(url, body) {
    const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {}),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) alert(data.error || "Something went wrong");
    return data;
}

// 725 seconds -> "12:05"
function formatElapsed(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, "0")}`;
}

// "CSCI 104 — 12:05" (regular) or "CSCI 104 — Pomodoro round 2/4, work, 12:34 left"
function sessionText(s) {
  const t = s.timer;
  if (s.mode === "pomodoro" && t) {
    return `${s.class_name} — Pomodoro round ${t.round}/${t.rounds}, ${t.phase}, ${formatElapsed(t.remaining)} left`;
  }
  return `${s.class_name} — ${formatElapsed((s.paused_at || Date.now() / 1000) - s.session_start)}`;
}

// "Last session (CSCI 104): 48:10 focused, 87% productive, 3 warnings"
function summaryText(sum) {
  const pct = sum.productivity === null ? "—" : `${Math.round(sum.productivity)}%`;
  return `Last session (${sum.class}): ${formatElapsed(sum.focused)} focused of ${formatElapsed(sum.total)}, ` +
         `${pct} productive, ${sum.warnings} warning${sum.warnings === 1 ? "" : "s"}`;
}

// Class dropdown 
// Loaded at start and after adding a class (not every second, which would reset your choice)
async function loadClasses(selectId) {
  const res = await fetch("/api/classes", { cache: "no-store" });
  const classes = await res.json();
  classSelect.innerHTML = "";
  for (const c of classes) {
    const option = document.createElement("option");
    option.value = c.id;
    option.textContent = c.name;
    classSelect.appendChild(option);
  }
  if (!classes.length) classSelect.appendChild(new Option("No classes yet", ""));
  noClassesEl.hidden = classes.length > 0;   // show the hint only when the list is empty
  if (selectId) classSelect.value = selectId;
}

addClassButton.addEventListener("click", async () => {
  const c = await post("/api/classes", { name: newClassInput.value });
  if (c.id) {
    newClassInput.value = "";
    await loadClasses(c.id);
    refresh();
    if (window.refreshStats) refreshStats();   // the deadline form's class list too
  }
});

// refresh(): ask the server what's happening and update every part of the page.
// Runs once at load, after each button click, and every second.
async function refresh() {
  try {
    // Get the shared state from Flask (no-store = never use a cached answer)
    const res = await fetch("/api/status", { cache: "no-store" });
    const s = await res.json();
    window.lastStatus = s;   // timer.js reads this
    // session_id is null when no session is running
    const inSession = s.session_id !== null;

    // Live activity: status text depends on whether a session is running or paused
    s.paused ? "Paused" : s.monitoring_paused ? "Monitoring paused" : s.status;
    appEl.textContent = s.app || "—";          // "—" if no app detected
    domainEl.textContent = s.domain || "—";    // "—" if not on a website
    const cam = s.focus_cam || "off";
    setCamera(CAMERA_TEXT[cam] || cam);   // an error shows its own text

    // Session info: class name plus elapsed time (now minus start, in seconds)
    sessionInfoEl.textContent = inSession ? sessionText(s) : "Not started";
    // After a session ends, show its summary until the next one starts
    summaryEl.hidden = inSession || !s.last_summary;
    if (s.last_summary) summaryEl.textContent = summaryText(s.last_summary);
    // One button does both jobs: its label follows the session state
    sessionButton.textContent = inSession ? "Stop session" : "Start session";
    // Can't start without a class selected
    sessionButton.disabled = !inSession && !classSelect.value;
    // Lock the dropdown mid-session so the class can't change
    classSelect.disabled = inSession;
    timerSelect.disabled = inSession;

    // Pause only makes sense during a session; the label flips between pause and resume
    pauseButton.disabled = !inSession;
    pauseButton.textContent = s.paused ? "Resume session" : "Pause session";
    monitorButton.disabled = !inSession || s.paused;   // a paused session already stops monitoring
    monitorButton.textContent = s.monitoring_paused ? "Resume monitoring" : "Pause monitoring";
  } catch (err) {
    // Server unreachable (e.g. main.py was stopped): show it and disable the buttons
    statusEl.textContent = "Not connected";
    sessionButton.disabled = true;
    pauseButton.disabled = true;
    monitorButton.disabled = true;
    cameraEl.textContent = "—";
  }
}

// Buttons 
sessionButton.addEventListener("click", async () => {
  const inSession = sessionButton.textContent === "Stop session";
  if (inSession) {
    await post("/api/session/stop");
    setTimeout(() => window.refreshStats && refreshStats(), 1500);   // summary + stats once the monitor has caught up
  } else {
    await post("/api/session/start", {
      class_id: Number(classSelect.value),
      mode: timerSelect.value,
      work_minutes: document.getElementById("pomo-work").value,
      break_minutes: document.getElementById("pomo-break").value,
      rounds: document.getElementById("pomo-rounds").value,
    });  
  }
  refresh();
});

pauseButton.addEventListener("click", async () => {
  await post("/api/pause");
  refresh();
});

monitorButton.addEventListener("click", async () => {
  await post("/api/pause-monitoring");
  refresh();
});

// Start up 
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) refresh();
});

loadClasses().then(refresh);
setInterval(refresh, 1000);