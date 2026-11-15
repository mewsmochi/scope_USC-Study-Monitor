import copy
import difflib
import json
import shutil
from pathlib import Path

from AppKit import NSWorkspace, NSRunLoop, NSDate
from monitor.detector import BROWSER_SCRIPTS, get_current_activity, get_domain
from alerts.messages import PERSONAS

# config.json lives in the project root, no matter where you run from
CONFIG_PATH = Path(__file__).parent.parent / "config.json"
# config.json is git-ignored (each person has their own allowlist); this is the shared template
EXAMPLE_PATH = CONFIG_PATH.with_name("config.example.json")

# The two list keys the menu edits
APPS = "allowed_apps"
SITES = "allowed_domains"

DEFAULTS = {
    "mode": "warn",
    "persona": "kind",
    "grace_seconds": 10,
    "repeat_seconds": 30,
    APPS: [],
    SITES: [],
    "neutral_apps": ["loginwindow", "ScreenSaverEngine", "Notification Center", "Spotlight", "Dock"],
    "idle_seconds": 120,
    "pomodoro_work_minutes": 25,
    "pomodoro_break_minutes": 5,
    "pomodoro_rounds": 4,
    "low_study_hours": 3,
}


# helper functions

def normalize(name):
    return name.strip().lower()

def url_to_domain(url):
    """'https://www.piazza.com:443/class' -> 'piazza.com' (one shared copy of the logic)"""
    return get_domain(url) or ""

def clean_site(text):
    """Accepts 'piazza.com', 'www.piazza.com/x', or a full URL. Returns the bare domain."""
    text = text.strip().lower()
    if "//" in text:
        return url_to_domain(text)
    text = text.split("/")[0]
    return text[4:] if text.startswith("www.") else text


# loading and saving config.json

def load_config():
    """Read the whole config, filling in anything missing with defaults."""
    data = {}
    if not CONFIG_PATH.exists() and EXAMPLE_PATH.exists():
        shutil.copy(EXAMPLE_PATH, CONFIG_PATH)   # first run: start from the shared template
    if CONFIG_PATH.exists():
        text = CONFIG_PATH.read_text().strip()
        if text:
            try:
                data = json.loads(text)
            except json.JSONDecodeError as e:
                raise SystemExit(f"config.json isn't valid JSON ({e}). Fix it, then run again.")
    for key, default in DEFAULTS.items():
        data.setdefault(key, copy.deepcopy(default))
    return data

def save_config(config):
    """Write the WHOLE config back, so settings like mode and persona are never lost."""
    tmp = CONFIG_PATH.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(config, f, indent=2)
    tmp.replace(CONFIG_PATH)   
    # atomic swap: readers see the old file or the new one, never half


def add_to_allowlist(kind, value):
    """kind is APPS or SITES. Returns True if newly added."""
    config = load_config()
    if any(normalize(item) == normalize(value) for item in config[kind]):
        return False
    config[kind].append(value)
    save_config(config)
    return True

def remove_from_allowlist(kind, value):
    """Returns True if found and removed."""
    config = load_config()
    for item in config[kind]:
        if normalize(item) == normalize(value):
            config[kind].remove(item)
            save_config(config)
            return True
    return False


# finding app names

def known_app_names():
    """Names of running apps plus everything installed."""
    names = set()
    for a in NSWorkspace.sharedWorkspace().runningApplications():
        if a.activationPolicy() == 0 and a.localizedName():
            names.add(a.localizedName())
    folders = (
        Path("/Applications"),
        Path("/Applications/Utilities"),
        Path("/System/Applications"),
        Path("/System/Applications/Utilities"),
        Path.home() / "Applications",
    )
    for folder in folders:
        if folder.exists():
            names.update(p.stem for p in folder.glob("*.app"))
    return sorted(names)

def resolve_app_name(typed):
    """Return the best-matching real app name, or what the user typed if they decline."""
    known = known_app_names()
    lookup = {n.lower(): n for n in known}

    if typed.lower() in lookup:
        return lookup[typed.lower()]

    matches = [n for n in known if n.lower().startswith(typed.lower())]
    matches += difflib.get_close_matches(typed, known, n=3, cutoff=0.6)
    matches = list(dict.fromkeys(matches))

    if matches:
        print(f"'{typed}' isn't an exact app name. Did you mean:")
        for i, m in enumerate(matches, start=1):
            print(f"  {i}. {m}")
        pick = input("Number to choose, or Enter to keep what you typed: ").strip()
        if pick.isdigit() and 1 <= int(pick) <= len(matches):
            return matches[int(pick) - 1]
    return typed

def running_app_names():
    """Names of apps currently open, with background helpers filtered out."""
    names = set()
    for a in NSWorkspace.sharedWorkspace().runningApplications():
        if a.activationPolicy() == 0 and a.localizedName():
            names.add(a.localizedName())
    return sorted(names, key=str.lower)

# settings helpers

MODES = ("warn", "force")

def choose(title, options, current):
    """Show numbered options, return the chosen one (or None if cancelled)."""
    print(f"\n{title} (current: {current})")
    for i, opt in enumerate(options, start=1):
        print(f"  {i}. {opt}")
    pick = input("Number (Enter to cancel): ").strip()
    if pick.isdigit() and 1 <= int(pick) <= len(options):
        return options[int(pick) - 1]
    return None

def ask_seconds(label, current):
    """Ask for a whole number of seconds (at least 1). Returns None if cancelled or invalid."""
    text = input(f"{label} in seconds (current: {current}, Enter to cancel): ").strip()
    if text.isdigit() and int(text) >= 1:
        return int(text)
    if text:
        print("  Please enter a whole number of 1 or more.")
    return None

# menu actions

def show_allowlist():
    config = load_config()
    print(f"\nMode: {config['mode']}   Persona: {config['persona']}   "
          f"Grace: {config['grace_seconds']}s   Repeat: {config['repeat_seconds']}s")
    for title, key in (("APPS", APPS), ("WEBSITES", SITES)):
        print(f"\n{title}:")
        for i, item in enumerate(config[key], start=1):
            print(f"  {i}. {item}")
        if not config[key]:
            print("  (empty)")

def allow_current(seconds=5):
    """Give the user a few seconds to switch somewhere, then allow whatever they're on."""
    print(f"Switch to the app or website you want to allow. Capturing in {seconds} seconds...")
    NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(seconds))
    activity = get_current_activity()
    app, domain = activity["app"], activity["domain"]

    if not app:
        print("Couldn't detect the front app. Try again.")
    elif domain:
        print(f"Added website: {domain}" if add_to_allowlist(SITES, domain) else f"{domain} is already allowed")
    elif app in BROWSER_SCRIPTS:
        print(f"Couldn't read a URL from {app}. Open a page and try again.")
    else:
        print(f"Added app: {app}" if add_to_allowlist(APPS, app) else f"{app} is already allowed")

def pick_running_app():
    apps = running_app_names()
    if not apps:
        print("No running apps found.")
        return

    print("\nRunning apps:")
    for i, name in enumerate(apps, start=1):
        print(f"  {i}. {name}")

    picks = input("Numbers to add, separated by spaces (Enter to cancel): ").split()
    for p in picks:
        if not (p.isdigit() and 1 <= int(p) <= len(apps)):
            print(f"Skipping '{p}' (not a valid number)")
            continue
        name = apps[int(p) - 1]
        if name in BROWSER_SCRIPTS:
            print(f"Skipping {name}: allowing a whole browser would allow every website. Use 'Add website' instead.")
        elif add_to_allowlist(APPS, name):
            print(f"Added {name}")
        else:
            print(f"{name} is already allowed")

def add_apps_loop():
    print("\nAdding apps. Press Enter on an empty line when you're done.")
    print("Tip: if an app doesn't get recognized later, use option 6 or 7 instead.")
    while True:
        typed = input("App name: ").strip()
        if not typed:
            break
        name = resolve_app_name(typed)
        if name in BROWSER_SCRIPTS:
            print(f"  Skipped: allowing {name} would allow every website. Add websites instead.")
            continue
        if name not in running_app_names():
            print("  Note: this app isn't open right now, so I can't confirm the name matches.")
            print("  If it gets flagged as a distraction, open it and use option 6.")
        print("  Added." if add_to_allowlist(APPS, name) else "  Already in the list.")

def add_websites_loop():
    print("\nAdding websites. Press Enter on an empty line when you're done.")
    while True:
        site = clean_site(input("Website (e.g. piazza.com): "))
        if not site:
            break
        print("  Added." if add_to_allowlist(SITES, site) else "  Already in the list.")

def settings_menu():
    while True:
        config = load_config()
        print(f"\nSettings:  mode={config['mode']}  persona={config['persona']}  "
              f"grace={config['grace_seconds']}s  repeat={config['repeat_seconds']}s")
        print("1) Change mode   2) Change persona   3) Grace period   4) Repeat interval   5) Back")
        choice = input("> ").strip()

        if choice == "1":
            new = choose("Mode  (warn = notification only, force = also switches you back)",
                         MODES, config["mode"])
            key = "mode"
        elif choice == "2":
            new = choose("Persona", list(PERSONAS), config["persona"])
            key = "persona"
        elif choice == "3":
            new = ask_seconds("Grace period", config["grace_seconds"])
            key = "grace_seconds"
        elif choice == "4":
            new = ask_seconds("Repeat interval", config["repeat_seconds"])
            key = "repeat_seconds"
        elif choice == "5":
            break
        else:
            continue

        if new is not None:
            config = load_config()
            config[key] = new
            save_config(config)
            print(f"  Saved: {key} = {new}")

def menu():
    while True:
        print("\n1) Show list   2) Add app   3) Add website")
        print("4) Remove app  5) Remove website")
        print("6) Allow what I'm on now   (recommended)")
        print("7) Pick from running apps  (recommended)")
        print("8) Settings (mode, persona, timers)")
        print("9) Quit")
        choice = input("> ").strip()

        if choice == "1":
            show_allowlist()
        elif choice == "2":
            add_apps_loop()
        elif choice == "3":
            add_websites_loop()
        elif choice == "4":
            name = input("App to remove: ").strip()
            print("Removed." if remove_from_allowlist(APPS, name) else "Not found.")
        elif choice == "5":
            site = clean_site(input("Website to remove: "))
            print("Removed." if remove_from_allowlist(SITES, site) else "Not found.")
        elif choice == "6":
            allow_current()
        elif choice == "7":
            pick_running_app()
        elif choice == "8":
            settings_menu()
        elif choice == "9":
            break


if __name__ == "__main__":
    menu()