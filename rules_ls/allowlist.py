import difflib
import json
from pathlib import Path
from urllib.parse import urlparse

from AppKit import NSWorkspace, NSRunLoop, NSDate
from monitor.detector import BROWSER_SCRIPTS, current_active

# Always find the file next to this script, no matter where you run from
ALLOWLIST_PATH = Path(__file__).parent / "allowlist.json"


# helper functions

def normalize(name):
    return name.strip().lower()

def url_to_domain(url):
    """'https://www.piazza.com:443/class' -> 'piazza.com'"""
    host = urlparse(url).hostname or ""
    return host[4:] if host.startswith("www.") else host

def clean_site(text):
    """Accepts 'piazza.com', 'www.piazza.com/x', or a full URL. Returns the bare domain."""
    text = text.strip().lower()
    if "//" in text:
        return url_to_domain(text)
    text = text.split("/")[0]
    return text[4:] if text.startswith("www.") else text


# loading/saving allowlist

def load_allowlist():
    data = {}
    if ALLOWLIST_PATH.exists():
        try:
            with open(ALLOWLIST_PATH) as f:
                data = json.load(f)
        except json.JSONDecodeError:
            data = {}
    data.setdefault("apps", [])
    data.setdefault("websites", [])
    return data

def save_allowlist(allowlist):
    with open(ALLOWLIST_PATH, "w") as f:
        json.dump(allowlist, f, indent=2)

def add_to_allowlist(kind, value):
    """kind is 'apps' or 'websites'. Returns True if newly added."""
    allowlist = load_allowlist()
    if any(normalize(item) == normalize(value) for item in allowlist[kind]):
        return False
    allowlist[kind].append(value)
    save_allowlist(allowlist)
    return True

def remove_from_allowlist(kind, value):
    """Returns True if found and removed."""
    allowlist = load_allowlist()
    for item in allowlist[kind]:
        if normalize(item) == normalize(value):
            allowlist[kind].remove(item)
            save_allowlist(allowlist)
            return True
    return False


# checking allowlist

def app_is_allowed(app_name, allowlist):
    app = normalize(app_name)
    for allowed in allowlist["apps"]:
        allowed = normalize(allowed)
        # startswith handles versioned names: "matlab" matches "MATLAB_R2024b"
        if app == allowed or app.startswith(allowed):
            return True
    return False

def domain_is_allowed(domain, allowlist):
    """'www.piazza.com' and 'piazza.com' both match an allowed 'piazza.com'."""
    d = domain.lower()
    return any(d == a.lower() or d.endswith("." + a.lower()) for a in allowlist["websites"])

def is_allowed(app, url, allowlist):
    """The one function the grace-period logic will call."""
    if url:
        return domain_is_allowed(url_to_domain(url), allowlist)
    if app in BROWSER_SCRIPTS:
        return False   # browser with no readable URL: not allowed (we can revisit this)
    return app_is_allowed(app, allowlist)


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


# menu actions

def show(allowlist):
    for kind in ("apps", "websites"):
        print(f"\n{kind.upper()}:")
        for i, item in enumerate(allowlist[kind], start=1):
            print(f"  {i}. {item}")
        if not allowlist[kind]:
            print("  (empty)")

def show_allowlist():
    allowlist = load_allowlist()
    if not any(allowlist.values()):
        print("Allowlist is empty")
        return
    print("Current allowlist:")
    show(allowlist)

def allow_current(seconds=5):
    """Give the user a few seconds to switch somewhere, then allow whatever they're on."""
    print(f"Switch to the app or website you want to allow. Capturing in {seconds} seconds...")
    NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(seconds))
    app, url = current_active()
    if url:
        domain = url_to_domain(url)
        print(f"Added website: {domain}" if add_to_allowlist("websites", domain) else f"{domain} is already allowed")
    elif app in BROWSER_SCRIPTS:
        print(f"Couldn't read a URL from {app}. Open a page and try again.")
    else:
        print(f"Added app: {app}" if add_to_allowlist("apps", app) else f"{app} is already allowed")

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
        elif add_to_allowlist("apps", name):
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
        print("  Added." if add_to_allowlist("apps", name) else "  Already in the list.")

def add_websites_loop():
    print("\nAdding websites. Press Enter on an empty line when you're done.")
    while True:
        site = clean_site(input("Website (e.g. piazza.com): "))
        if not site:
            break
        print("  Added." if add_to_allowlist("websites", site) else "  Already in the list.")

def menu():
    while True:
        print("\n1) Show list   2) Add app   3) Add website")
        print("4) Remove app  5) Remove website")
        print("6) Allow what I'm on now   (recommended)")
        print("7) Pick from running apps  (recommended)")
        print("8) Quit")
        choice = input("> ").strip()

        if choice == "1":
            show_allowlist()
        elif choice == "2":
            add_apps_loop()
        elif choice == "3":
            add_websites_loop()
        elif choice == "4":
            name = input("App to remove: ").strip()
            print("Removed." if remove_from_allowlist("apps", name) else "Not found.")
        elif choice == "5":
            site = clean_site(input("Website to remove: "))
            print("Removed." if remove_from_allowlist("websites", site) else "Not found.")
        elif choice == "6":
            allow_current()
        elif choice == "7":
            pick_running_app()
        elif choice == "8":
            break


if __name__ == "__main__":
    menu()