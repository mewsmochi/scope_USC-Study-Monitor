// page elements that will be updated
const statusEl = document.getElementById("status");          // <strong id="status">
const appEl = document.getElementById("current-app");        // <span id="current-app">
const domainEl = document.getElementById("current-domain");  // <span id="current-domain">
const button = document.getElementById("pause-button");      // <button id="pause-button">
const sessionEl = document.getElementById("session");        // <span id="session">

// 125 -> "2:05"
function clock(seconds) {
    const s = Math.floor(seconds);
    const m = Math.floor(s / 60);
    return `${m}:${String(s % 60).padStart(2, "0")}`;
}

// "CSCI 104 · Pomodoro round 2/4 · work · 12:34 left" or "CSCI 104 · Regular · 45:10 elapsed"
function sessionText(se) {
    if (!se) return "—";
    if (se.mode === "pomodoro") {
        return `${se.class} · Pomodoro round ${se.round}/${se.rounds} · ${se.phase} · ${clock(se.remaining)} left`;
    }
    return `${se.class} · Regular · ${clock(se.elapsed)} elapsed`;
}

// refresh(): fetch the latest status from the server and update the page elements
async function refresh() {
    try {
    //current state
    const res = await fetch("/api/status");
    //current state in json --> javascript
    const s = await res.json();
    //if monitering paused --> show paused, otherwise show monitors status
    statusEl.textContent = s.paused ? "Paused" : s.status;
    sessionEl.textContent = sessionText(s.session);
    //show app and website
    //use "-" if app or domain is empty
    appEl.textContent = s.app || "—";
    domainEl.textContent = s.domain || "—";
    //if we get response, enable pause button
    button.disabled = false;
    button.textContent = s.paused ? "Resume monitoring" : "Pause monitoring";
} catch (err) {
    //if fetch fails (server is offline) reflect that on the page
    statusEl.textContent = "Error";
    button.disabled = true;
}


}


// PAUSE / RESUME BUTTON

// When the button is clicked, send a POST request to /api/pause.
// The server flips the "paused" flag on the shared state board.
button.addEventListener('click', async () => {
    await fetch("/api/pause", { method: "POST" });
    // Refresh right away so the button label changes immediately
    refresh();
});

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) refresh();
});

// initial refresh to populate the page with current status
refresh();
setInterval(refresh, 1000);