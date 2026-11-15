// Stats section: fetched from /api/stats every 30s (it's history, not live status)

let classChart = null;

// 3725 -> "1h 02m", 125 -> "2m 05s"
function duration(seconds) {
    const s = Math.floor(seconds);
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
    return h ? `${h}h ${String(m).padStart(2, "0")}m` : `${m}m ${String(s % 60).padStart(2, "0")}s`;
}

function percent(p) {
    return p === null ? "—" : `${Math.round(p)}%`;
}

// Build a table row from plain values (textContent, so titles can't inject HTML)
function row(cells) {
    const tr = document.createElement("tr");
    for (const c of cells) {
        const td = document.createElement("td");
        if (c instanceof Node) td.append(c); else td.textContent = c;
        tr.append(td);
    }
    return tr;
}

function renderDeadlines(deadlines) {
    const body = document.getElementById("deadlines");
    body.replaceChildren(...deadlines.map(d => {
        const del = document.createElement("button");
        del.textContent = "Delete";
        del.addEventListener("click", async () => {
            await fetch(`/api/deadlines/${d.id}`, { method: "DELETE" });
            refreshStats();
        });
        const tr = row([
            `${d.due_date} (${d.days_left === 0 ? "today" : d.days_left + "d"})`,
            d.class, d.title,
            `${d.week_hours.toFixed(1)}h${d.low ? "  ⚠️ low" : ""}`,
            del,
        ]);
        if (d.low) tr.classList.add("low");
        return tr;
    }));
    if (!deadlines.length) body.append(row(["No upcoming deadlines", "", "", "", ""]));
}

function renderClassChart(classes) {
    const labels = classes.map(c => c.name);
    const hours = classes.map(c => +(c.focused / 3600).toFixed(2));
    if (!classChart) {
        classChart = new Chart(document.getElementById("class-chart"), {
            type: "bar",
            data: { labels, datasets: [{ label: "Focused hours", data: hours }] },
            options: { indexAxis: "y", plugins: { legend: { display: false } } },
        });
    } else {
        classChart.data.labels = labels;
        classChart.data.datasets[0].data = hours;
        classChart.update();
    }

    // The add-deadline form needs the class list too; keep the current choice
    const select = document.getElementById("deadline-class");
    const chosen = select.value;
    select.replaceChildren(...classes.map(c => new Option(c.name, c.id)));
    if (chosen) select.value = chosen;
}

// --- Top distractions: ranked by time, with visits, warnings, and share of distracted time ---

let lastReport = null;
let distractionRange = "week";   // "week" or "all"
try { distractionRange = localStorage.getItem("distractionRange") || "week"; } catch (e) {}

function plural(n, word) {
    return `${n} ${word}${n === 1 ? "" : "s"}`;
}

// "This week | All time" switch, added above the list once (keeps index.html untouched)
function distractionToggle(list) {
    let bar = document.getElementById("distraction-range");
    if (bar) return bar;
    bar = document.createElement("div");
    bar.id = "distraction-range";
    bar.setAttribute("role", "group");
    bar.setAttribute("aria-label", "Time range");
    for (const [value, text] of [["week", "This week"], ["all", "All time"]]) {
        const b = document.createElement("button");
        b.type = "button";
        b.dataset.range = value;
        b.textContent = text;
        b.addEventListener("click", () => {
            distractionRange = value;
            try { localStorage.setItem("distractionRange", value); } catch (e) {}
            renderDistractions();
        });
        bar.append(b);
    }
    list.before(bar);
    return bar;
}

function renderDistractions() {
    const list = document.getElementById("distractions");
    if (!list || !lastReport) return;
    for (const b of distractionToggle(list).children) {
        b.setAttribute("aria-pressed", String(b.dataset.range === distractionRange));
    }
    const items = distractionRange === "week" ? lastReport.top_distractions_week : lastReport.top_distractions;
    const top = items.length ? items[0].seconds : 0;

    list.replaceChildren(...items.map(d => {
        const li = document.createElement("li");
        li.className = "distraction";

        const head = document.createElement("div");
        head.className = "distraction-head";
        const name = document.createElement("span");
        name.className = "distraction-name";
        name.textContent = d.name;
        const kind = document.createElement("span");
        kind.className = "distraction-kind";
        kind.textContent = d.kind === "site" ? "website" : "app";
        const time = document.createElement("span");
        time.className = "distraction-time";
        time.textContent = duration(d.seconds);
        head.append(name, kind, time);

        // Bar length is relative to the #1 distraction, so the ranking reads at a glance
        const track = document.createElement("div");
        track.className = "distraction-bar";
        const fill = document.createElement("span");
        fill.style.width = `${top ? Math.max(2, 100 * d.seconds / top) : 0}%`;
        track.append(fill);

        const meta = document.createElement("div");
        meta.className = "distraction-meta";
        meta.textContent = `${Math.round(d.share)}% of distracted time · ${plural(d.visits, "visit")} · ` +
                           plural(d.warnings, "warning");

        li.append(head, track, meta);
        return li;
    }));
    if (!items.length) {
        list.textContent = distractionRange === "week" ? "No distractions this week 🎉" : "None yet 🎉";
    }
}

async function refreshStats() {
    try {
        const r = await (await fetch("/api/stats")).json();
        document.getElementById("week-focused").textContent = duration(r.week.focused);
        document.getElementById("week-productivity").textContent = percent(r.week.productivity);
        document.getElementById("personal-best").textContent = duration(r.personal_best);
        renderDeadlines(r.deadlines);
        if (window.Chart) renderClassChart(r.classes);

        lastReport = r;
        renderDistractions();

        document.getElementById("sessions").replaceChildren(...r.recent_sessions.map(s => row([
            new Date(s.start * 1000).toLocaleString(), s.class, s.mode,
            duration(s.focused), percent(s.productivity), s.warnings,
        ])));
    } catch (err) {
        // Server offline: app.js already shows "Error" in the status line
    }
}

document.getElementById("deadline-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const res = await fetch("/api/deadlines", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            class_id: document.getElementById("deadline-class").value,
            title: document.getElementById("deadline-title").value,
            due_date: document.getElementById("deadline-date").value,
        }),
    });
    const err = document.getElementById("deadline-error");
    err.textContent = res.ok ? "" : (await res.json()).error;
    if (res.ok) {
        e.target.reset();
        refreshStats();
    }
});

refreshStats();
setInterval(refreshStats, 30000);
