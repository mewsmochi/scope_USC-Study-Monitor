// Two tabs. The page keeps updating in the background, so nothing is lost when you switch.
const tabButtons = document.querySelectorAll(".tab-button");
const panels = document.querySelectorAll(".panel");

function showTab(name) {
  if (!document.getElementById("tab-" + name)) name = "dashboard";
  tabButtons.forEach(b => b.classList.toggle("active", b.dataset.tab === name));
  panels.forEach(p => (p.hidden = p.id !== "tab-" + name));
  history.replaceState(null, "", "#" + name);
}

tabButtons.forEach(b => b.addEventListener("click", () => showTab(b.dataset.tab)));
showTab(location.hash.slice(1) || "dashboard");