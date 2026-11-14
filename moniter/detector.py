import subprocess
from AppKit import NSWorkspace, NSRunLoop, NSDate

BROWSER_SCRIPTS = {
    "Google Chrome": "tell application \"Google Chrome\" to get URL of active tab of first window",
    "Safari": "tell application \"Safari\" to get URL of current tab of window 1"
}

def front_app():
    """Name of app in front"""
    return NSWorkspace.sharedWorkspace().frontmostApplication().localizedName()

def browser_url(browser):
    """URL of the active tab in the specified browser"""
    script = BROWSER_SCRIPTS.get(browser)
    if not script:
        return None
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True
    )
    return result.stdout.strip()

def current_active():
    """current active app name and browser URL"""
    app = front_app()
    return app, browser_url(app)

if __name__ == "__main__":
    while True:
        app, url = current_active()
        if url:
            print(f"Active app: {app}, URL: {url}")
        else:
            print(f"Active app: {app}")
        NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(1.0))
        

