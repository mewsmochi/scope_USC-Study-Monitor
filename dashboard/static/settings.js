// Settings and allowlist. Uses post() from app.js. Loaded once and after each change
// (not on a timer, so a refresh can't wipe what you're typing).

const modeSel = document.getElementById("set-mode");
const personaSel = document.getElementById("set-persona");
const numbersEl = document.getElementById("set-numbers");
const settingsMsg = document.getElementById("settings-msg");
const allowMsg = document.getElementById("allow-current-msg");
const focusBox = document.getElementById("set-focus");

function flash(el, text) {
  el.textContent = text;
  setTimeout(() => (el.textContent = ""), 3000);
}

// Show "Force" / "Kind" in the dropdown, but keep the saved value lowercase ("force" / "kind")
const cap = s => s.charAt(0).toUpperCase() + s.slice(1);

function fillSelect(sel, options, current) {
  sel.replaceChildren(...options.map(o => new Option(cap(o), o)));
  sel.value = current;
}

// One <li> per entry, each with a Remove button
function fillAllowList(id, kind, items) {
  const ul = document.getElementById(id);
  ul.replaceChildren();
  if (!items.length) {
    const li = document.createElement("li");
    li.textContent = "Nothing yet";
    ul.append(li);
  }
  for (const item of items) {
    const li = document.createElement("li");
    const name = document.createElement("span");
    name.textContent = item;   // textContent: a name can never run as HTML
    const btn = document.createElement("button");
    btn.className = "remove";
    btn.textContent = "Remove";
    btn.addEventListener("click", async () => {
      showConfig(await post("/api/allowlist/remove", { kind, value: item }));
    });
    li.append(name, btn);
    ul.append(li);
  }
}

// Draw a config payload from the server onto the page
function showConfig(c) {
  if (!c || c.error) return;
  fillSelect(modeSel, c.modes, c.mode);
  fillSelect(personaSel, c.personas, c.persona);
  focusBox.checked = c.focus_mode;
  numbersEl.replaceChildren(...c.numbers.map(n => {
    const p = document.createElement("p");
    const label = document.createElement("label");
    label.append(`${n.label} (${n.unit}) `);
    const input = document.createElement("input");
    input.type = "number";
    input.min = n.min;
    input.max = n.max;
    input.value = n.value;
    input.dataset.key = n.key;
    label.append(input);
    p.append(label);
    return p;
  }));
  fillAllowList("list-apps", "apps", c.apps);
  fillAllowList("list-sites", "sites", c.sites);
}

async function loadConfig() {
  try {
    showConfig(await (await fetch("/api/config", { cache: "no-store" })).json());
  } catch (err) { /* server offline: app.js already shows it */ }
}

document.getElementById("save-settings").addEventListener("click", async () => {
  const body = { mode: modeSel.value, persona: personaSel.value, focus_mode: focusBox.checked };
  numbersEl.querySelectorAll("input").forEach(i => (body[i.dataset.key] = i.value));
  const c = await post("/api/config", body);
  if (!c.error) {
    showConfig(c);
    flash(settingsMsg, " Saved (applies within 5 seconds)");
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

// The dashboard is in front when you click, so give the user 5 seconds to switch away
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
    allowMsg.textContent = "";
    if (!c.error) { showConfig(c); flash(allowMsg, " Added!"); }
  }, 1000);
});

loadConfig();