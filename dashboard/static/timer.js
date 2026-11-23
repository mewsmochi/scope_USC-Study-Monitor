// Big timer + Pomodoro inputs. Reads window.lastStatus, which app.js refreshes every second.
const timerBox = document.getElementById("timer-box");
const timerPhase = document.getElementById("timer-phase");
const timerDisplay = document.getElementById("timer-display");
const pomoFields = document.getElementById("pomo-fields");
const pomoInputs = ["pomo-work", "pomo-break", "pomo-rounds"].map(id => document.getElementById(id));

// 125 -> "2:05", 3725 -> "1:02:05"
function clock(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  const sec = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${sec}` : `${m}:${sec}`;
}

function renderTimer() {
  const s = window.lastStatus;
  const inSession = !!s && s.session_id !== null;
  timerBox.classList.remove("break");
  pomoFields.hidden = timerSelect.value !== "pomodoro";
  pomoInputs.forEach(i => (i.disabled = inSession));

  if (!inSession) {
    timerPhase.textContent = "Ready";
    timerDisplay.textContent = timerSelect.value === "pomodoro"
      ? clock((Number(pomoInputs[0].value) || 25) * 60) : "0:00";
    return;
  }
  const t = s.timer;
  if (s.mode === "pomodoro" && t) {
    timerPhase.textContent = t.phase === "done" ? "Done"
      : `${t.phase === "break" ? "Break" : "Focus"} · round ${t.round}/${t.rounds}`;
    timerDisplay.textContent = clock(t.remaining);
    if (t.phase === "break") timerBox.classList.add("break");
  } else {
    timerPhase.textContent = s.paused ? "Paused" : "Studying";
    timerDisplay.textContent = clock((s.paused_at || Date.now() / 1000) - s.session_start);
  }
}

// Prefill the Pomodoro boxes from the saved defaults in Settings
async function loadPomoDefaults() {
  try {
    const c = await (await fetch("/api/config", { cache: "no-store" })).json();
    for (const n of c.numbers) {
      if (n.key === "pomodoro_work_minutes") pomoInputs[0].value = n.value;
      if (n.key === "pomodoro_break_minutes") pomoInputs[1].value = n.value;
      if (n.key === "pomodoro_rounds") pomoInputs[2].value = n.value;
    }
  } catch (err) { /* server offline */ }
}

timerSelect.addEventListener("change", renderTimer);
pomoInputs[0].addEventListener("input", renderTimer);
loadPomoDefaults();
setInterval(renderTimer, 250);