"""Detects which app is in front, and which website if it's a browser."""
import subprocess
from urllib.parse import urlparse

from AppKit import NSWorkspace

# Browser name (as macOS reports it) -> AppleScript that returns the active tab's URL
BROWSER_SCRIPTS = {
    "Google Chrome":  'tell application "Google Chrome" to get URL of active tab of front window',
    "Brave Browser":  'tell application "Brave Browser" to get URL of active tab of front window',
    "Microsoft Edge": 'tell application "Microsoft Edge" to get URL of active tab of front window',
    "Arc":            'tell application "Arc" to get URL of active tab of front window',
    "Safari":         'tell application "Safari" to get URL of current tab of front window',
}


def get_front_app():
    """Name of the app currently in front, e.g. 'Visual Studio Code'."""
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    return app.localizedName() if app else None


def get_browser_url(app_name):
    """Active tab's URL if app_name is a supported browser, else None."""
    script = BROWSER_SCRIPTS.get(app_name)
    if script is None:
        return None
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=2,
        )
    except subprocess.TimeoutExpired:
        return None
    if result.returncode != 0:  # e.g. browser has no open windows, or permission denied
        return None
    return result.stdout.strip() or None


def get_domain(url):
    """'https://www.youtube.com/watch?v=x' -> 'youtube.com'"""
    if not url:
        return None
    return urlparse(url).netloc.lower().removeprefix("www.") or None


def get_current_activity():
    """Snapshot of what the user is looking at right now."""
    app = get_front_app()
    url = get_browser_url(app)
    return {"app": app, "url": url, "domain": get_domain(url)}