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
    // session_id is null when no session is running
    const inSession = s.session_id !== null;

    // Live activity: status text depends on whether a session is running or paused
    statusEl.textContent = !inSession ? "No session running" : s.paused ? "Paused" : s.status;
    appEl.textContent = s.app || "—";          // "—" if no app detected
    domainEl.textContent = s.domain || "—";    // "—" if not on a website

    // Session info: class name plus elapsed time (now minus start, in seconds)
    sessionInfoEl.textContent = inSession
      ? `${s.class_name} — ${formatElapsed(Date.now() / 1000 - s.session_start)}`
      : "Not started";
    // One button does both jobs: its label follows the session state
    sessionButton.textContent = inSession ? "Stop session" : "Start session";
    // Can't start without a class selected
    sessionButton.disabled = !inSession && !classSelect.value;
    // Lock the dropdown mid-session so the class can't change
    classSelect.disabled = inSession;

    // Pause only makes sense during a session; the label flips between pause and resume
    pauseButton.disabled = !inSession;
    pauseButton.textContent = s.paused ? "Resume monitoring" : "Pause monitoring";
  } catch (err) {
    // Server unreachable (e.g. main.py was stopped): show it and disable the buttons
    statusEl.textContent = "Not connected";
    sessionButton.disabled = true;
    pauseButton.disabled = true;
  }
}

// Buttons 
sessionButton.addEventListener("click", async () => {
  const inSession = sessionButton.textContent === "Stop session";
  if (inSession) {
    await post("/api/session/stop");
  } else {
    await post("/api/session/start", { class_id: Number(classSelect.value) });
  }
  refresh();
});

pauseButton.addEventListener("click", async () => {
  await post("/api/pause");
  refresh();
});

// Start up 
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) refresh();
});

loadClasses().then(refresh);
setInterval(refresh, 1000);