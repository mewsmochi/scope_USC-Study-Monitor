// "Next deadline" card + study order. Uses the same /api/stats data as the Deadlines table.
// Urgency: deadlines flagged "low" (under your weekly study-hours target) come first,
// then by soonest due date, so the top item is "what to study right now".

function urgencyOrder(deadlines) {
  return [...deadlines].sort((a, b) =>
    (b.low - a.low) || (a.days_left - b.days_left) || (a.week_hours - b.week_hours));
}

function whenText(d) {
  return d.days_left === 0 ? "today" : d.days_left === 1 ? "tomorrow" : `in ${d.days_left} days`;
}

function renderNextDeadline(deadlines) {
  const card = document.getElementById("next-deadline");
  const list = document.getElementById("study-order");
  card.className = "next-card";
  card.replaceChildren();
  list.replaceChildren();

  if (!deadlines.length) {
    card.textContent = "No upcoming deadlines. Add one in the Deadlines section below.";
    return;
  }

  // Card: the soonest deadline, regardless of study hours
  const next = [...deadlines].sort((a, b) => a.days_left - b.days_left)[0];
  const big = document.createElement("div");
  big.className = "next-days";
  big.textContent = next.days_left === 0 ? "Today" : `${next.days_left}d`;
  const info = document.createElement("div");
  const title = document.createElement("strong");
  title.textContent = `${next.class}: ${next.title}`;
  const sub = document.createElement("div");
  sub.className = "hint";
  sub.textContent = `Due ${next.due_date} · studied ${next.week_hours.toFixed(1)}h this week` +
                    (next.low ? " · ⚠️ needs more study time" : "");
  info.append(title, sub);
  card.append(big, info);
  if (next.low) card.classList.add("low");

  // Ranked list of what to study first (top 3)
  urgencyOrder(deadlines).slice(0, 3).forEach(d => {
    const li = document.createElement("li");
    li.textContent = `${d.class}: ${d.title} (${whenText(d)}, ${d.week_hours.toFixed(1)}h this week)` +
                     (d.low ? " ⚠️" : "");
    list.append(li);
  });
}

async function loadNextDeadline() {
  try {
    const r = await (await fetch("/api/stats", { cache: "no-store" })).json();
    renderNextDeadline(r.deadlines || []);
  } catch (err) { /* server offline: app.js already shows it */ }
}

loadNextDeadline();
setInterval(loadNextDeadline, 30000);
// Refresh right after a deadline is added or deleted
document.addEventListener("click", e => {
  if (e.target.closest("#deadline-form button, #deadlines button")) setTimeout(loadNextDeadline, 600);
});