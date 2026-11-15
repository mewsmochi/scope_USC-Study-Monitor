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
const timerBox = document.getElementById("timer-box");
const timerPhase = document.getElementById("timer-phase");
const timerDisplay = document.getElementById("timer-display");
const timerSub = document.getElementById("timer-sub");
const timerModeSel = document.getElementById("timer-mode");
const pomoFields = document.getElementById("pomo-fields");
const pomoWork = document.getElementById("pomo-work");
const pomoBreak = document.getElementById("pomo-break");

//Helpers
// POST a JSON body; show the server's error message if it refuses
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
  if (selectId) classSelect.value = selectId;
}

addClassButton.addEventListener("click", async () => {
  const c = await post("/api/classes", { name: newClassInput.value });
  if (c.id) {
    newClassInput.value = "";
    await loadClasses(c.id);
    refresh();
  }
});

// refresh(): ask the server what's happening and update every part of the page.
// Runs once at load, after each button click, and every second.
async function refresh() {
  try {
    // Get the shared state from Flask (no-store = never use a cached answer)
    const res = await fetch("/api/status", { cache: "no-store" });
    const s = await res.json();
    lastStatus = s;
    // session_id is null when no session is running
    const inSession = s.session_id !== null;

    // Live activity: status text depends on whether a session is running or paused
    statusEl.textContent = !inSession ? "No session running" : s.paused ? "Paused" : s.status;
    appEl.textContent = s.app || "—";          // "—" if no app detected
    domainEl.textContent = s.domain || "—";    // "—" if not on a website

    // Session info: class name plus elapsed time (now minus start, in seconds)
    sessionInfoEl.textContent = inSession ? s.class_name : "Not started";
    // One button does both jobs: its label follows the session state
    sessionButton.textContent = inSession ? "Stop session" : "Start session";
    // Can't start without a class selected
    sessionButton.disabled = !inSession && !classSelect.value;
    // Lock the dropdown mid-session so the class can't change
    classSelect.disabled = inSession;
    timerModeSel.disabled = inSession;   // timer type is fixed once a session starts
    pomoWork.disabled = inSession;
    pomoBreak.disabled = inSession;

    // Pause only makes sense during a session; the label flips between pause and resume
    pauseButton.disabled = !inSession;
    pauseButton.textContent = s.paused ? "Resume monitoring" : "Pause monitoring";
  } catch (err) {
    // Server unreachable (e.g. main.py was stopped): show it and disable the buttons
    statusEl.textContent = "Not connected";
    sessionButton.disabled = true;
    pauseButton.disabled = true;
    lastStatus = null;
  }
}

// Buttons 
sessionButton.addEventListener("click", async () => {
  const inSession = sessionButton.textContent === "Stop session";
  if (inSession) {
    await post("/api/session/stop");
    loadStats();
  } else {
      await post("/api/session/start", {
      class_id: Number(classSelect.value),
      mode: timerModeSel.value,
      work_minutes: Number(pomoWork.value),
      break_minutes: Number(pomoBreak.value),
    });
  }
  refresh();
});

pauseButton.addEventListener("click", async () => {
  await post("/api/pause");
  refresh();
});

// Stats 
// 3725 seconds -> "1h 02m", 125 -> "2m 05s"
function formatDuration(seconds) {
  const s = Math.max(0, Math.round(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (h) return `${h}h ${String(m).padStart(2, "0")}m`;
  return `${m}m ${String(s % 60).padStart(2, "0")}s`;
}

// Replace a <ul>'s contents with one <li> per string (textContent: never run as HTML)
function fillList(id, lines) {
  const ul = document.getElementById(id);
  ul.innerHTML = "";
  for (const line of lines.length ? lines : ["Nothing yet"]) {
    const li = document.createElement("li");
    li.textContent = line;
    ul.appendChild(li);
  }
}

// One table row per class: name, focused time, distracted time, and a focus bar
function fillClassTable(rows) {
  const body = document.getElementById("stat-classes");
  body.innerHTML = "";
  if (!rows.length) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 4;
    td.textContent = "Nothing yet";
    tr.appendChild(td);
    body.appendChild(tr);
    return;
  }
  for (const c of rows) {
    const total = c.focused + c.distracted;
    const pct = total ? Math.round((100 * c.focused) / total) : 0;
    const tr = document.createElement("tr");

    for (const text of [c.name, formatDuration(c.focused), formatDuration(c.distracted)]) {
      const td = document.createElement("td");
      td.textContent = text;
      tr.appendChild(td);
    }

    const barCell = document.createElement("td");
    const bar = document.createElement("div");
    bar.className = "bar";
    const fill = document.createElement("div");
    fill.className = "bar-fill";
    fill.style.width = pct + "%";
    bar.appendChild(fill);
    const label = document.createElement("span");
    label.className = "bar-label";
    label.textContent = pct + "%";
    barCell.appendChild(bar);
    barCell.appendChild(label);
    tr.appendChild(barCell);

    body.appendChild(tr);
  }
}

async function loadStats() {
  try {
    const res = await fetch("/api/stats", { cache: "no-store" });
    const s = await res.json();

    document.getElementById("stat-productivity").textContent =
      s.productivity === null ? "—" : `${s.productivity}%`;
    document.getElementById("stat-totals").textContent =
      `${formatDuration(s.focused_seconds)} / ${formatDuration(s.distracted_seconds)}`;
    document.getElementById("stat-best").textContent = formatDuration(s.personal_best_seconds);
    document.getElementById("stat-prev-best").textContent =
      s.previous_best_seconds === null ? "—" : formatDuration(s.previous_best_seconds);

    fillClassTable(s.by_class);
    fillList("stat-distractions", s.top_distractions.map(
      d => `${d.name}: ${formatDuration(d.seconds)}`));
    fillList("stat-sessions", s.recent_sessions.map(r =>
      `${r.class} — ${new Date(r.start * 1000).toLocaleString()} — ${r.minutes} min` +
      (r.productivity === null ? "" : ` — ${r.productivity}% focused`)));
  } catch (err) {
    // Stats are a bonus: if they fail, leave the rest of the page working
  }
}



// ---------- Settings and allowlist ----------
const modeSel = document.getElementById("set-mode");
const personaSel = document.getElementById("set-persona");
const graceInput = document.getElementById("set-grace");
const repeatInput = document.getElementById("set-repeat");
const settingsMsg = document.getElementById("settings-msg");
const allowMsg = document.getElementById("allow-current-msg");

function fillSelect(sel, options, current) {
  sel.innerHTML = "";
  for (const o of options) {
    const opt = document.createElement("option");
    opt.value = o;
    opt.textContent = o;
    sel.appendChild(opt);
  }
  sel.value = current;
}

// One <li> per entry, each with a Remove button
function fillAllowList(id, kind, items) {
  const ul = document.getElementById(id);
  ul.innerHTML = "";
  if (!items.length) {
    const li = document.createElement("li");
    li.textContent = "Nothing yet";
    ul.appendChild(li);
  }
  for (const item of items) {
    const li = document.createElement("li");
    li.textContent = item + " ";
    const btn = document.createElement("button");
    btn.textContent = "Remove";
    btn.addEventListener("click", async () => {
      showConfig(await post("/api/allowlist/remove", { kind, value: item }));
    });
    li.appendChild(btn);
    ul.appendChild(li);
  }
}

// Draw a config payload from the server onto the page
function showConfig(c) {
  if (!c || c.error) return;
  fillSelect(modeSel, c.modes, c.mode);
  fillSelect(personaSel, c.personas, c.persona);
  graceInput.value = c.grace_seconds;
  repeatInput.value = c.repeat_seconds;
  fillAllowList("list-apps", "apps", c.apps);
  fillAllowList("list-sites", "sites", c.sites);
}

async function loadConfig() {
  const res = await fetch("/api/config", { cache: "no-store" });
  showConfig(await res.json());
}

document.getElementById("save-settings").addEventListener("click", async () => {
  const c = await post("/api/config", {
    mode: modeSel.value, persona: personaSel.value,
    grace_seconds: graceInput.value, repeat_seconds: repeatInput.value,
  });
  if (!c.error) {
    showConfig(c);
    settingsMsg.textContent = " Saved (applies within 5 seconds)";
    setTimeout(() => (settingsMsg.textContent = ""), 3000);
  }
});

function wireAdd(kind, inputId, buttonId) {
  const input = document.getElementById(inputId);
  document.getElementById(buttonId).addEventListener("click", async () => {
    const c = await post("/api/allowlist/add", { kind, value: input.value });
    if (!c.error) { input.value = ""; showConfig(c); }
  });
}
wireAdd("apps", "add-app-input", "add-app-button");
wireAdd("sites", "add-site-input", "add-site-button");

// The dashboard itself is in front when you click, so give the user 5 seconds to switch away
document.getElementById("allow-current-button").addEventListener("click", () => {
  let left = 5;
  allowMsg.textContent = ` Switch to the app or site now... ${left}`;
  const timer = setInterval(async () => {
    left -= 1;
    if (left > 0) {
      allowMsg.textContent = ` Switch to the app or site now... ${left}`;
      return;
    }
    clearInterval(timer);
    const c = await post("/api/allowlist/allow-current");
    allowMsg.textContent = c.error ? "" : " Added!";
    if (!c.error) showConfig(c);
    setTimeout(() => (allowMsg.textContent = ""), 3000);
  }, 1000);
});

// Separate Tabs: Moniter, Stats, Settings
const tabButtons = document.querySelectorAll(".tab-button");
const panels = document.querySelectorAll(".panel");

function showTab(name) {
  if (!document.getElementById("tab-" + name)) name = "session";   // unknown hash: fall back
  tabButtons.forEach(b => b.classList.toggle("active", b.dataset.tab === name));
  panels.forEach(p => (p.hidden = p.id !== "tab-" + name));
  history.replaceState(null, "", "#" + name);   // so a refresh stays on the same tab
}

tabButtons.forEach(b => b.addEventListener("click", () => showTab(b.dataset.tab)));
showTab(location.hash.slice(1) || "session");

// ---------- Timer ----------
let lastStatus = null;   // newest /api/status reply; the timer redraws from it 4x a second

// 125 -> "2:05", 3725 -> "1:02:05"
function formatClock(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${sec}` : `${m}:${sec}`;
}

function renderTimer() {
  const s = lastStatus;
  timerBox.classList.remove("break");

  // No session: show what the timer will start at
  if (!s || s.session_id === null) {
    timerPhase.textContent = "Ready";
    timerDisplay.textContent =
      timerModeSel.value === "pomodoro" ? formatClock((Number(pomoWork.value) || 25) * 60) : "0:00";
    timerSub.textContent = "";
    return;
  }

  // Focused time so far: stop the clock while paused, and skip earlier pauses
  const now = Date.now() / 1000;
  const elapsed = Math.max(0, (s.paused_at ?? now) - s.session_start - s.paused_total);

  if (s.mode === "pomodoro") {
    const cycle = s.work_seconds + s.break_seconds;
    const pos = elapsed % cycle;                 // where we are inside this round
    const onBreak = pos >= s.work_seconds;
    const left = onBreak ? cycle - pos : s.work_seconds - pos;
    timerPhase.textContent = s.paused ? "Paused" : onBreak ? "Break" : "Focus";
    timerDisplay.textContent = formatClock(Math.ceil(left));
    timerSub.textContent = `Round ${Math.floor(elapsed / cycle) + 1} · ${formatClock(elapsed)} total`;
    if (onBreak && !s.paused) timerBox.classList.add("break");
  } else {
    timerPhase.textContent = s.paused ? "Paused" : "Studying";
    timerDisplay.textContent = formatClock(elapsed);
    timerSub.textContent = "";
  }
}

// Show the focus/break length boxes only for Pomodoro
timerModeSel.addEventListener("change", () => {
  pomoFields.hidden = timerModeSel.value !== "pomodoro";
  renderTimer();
});
pomoWork.addEventListener("input", renderTimer);
setInterval(renderTimer, 250);

// Start up 
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) refresh();
});

loadClasses().then(refresh);
loadConfig();
setInterval(refresh, 1000);
loadStats();                       
setInterval(loadStats, 10000);     