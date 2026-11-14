import subprocess
from AppKit import NSWorkspace, NSRunLoop, NSDate
import time

def format_duration(seconds):
    """Turn 125 into '2m 5s'."""
    seconds = int(seconds)
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"

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

def describe(app, url):
    """'Safari - https://...' for browsers, just 'Messages' for other apps."""
    return f"{app} - {url}" if url else app

if __name__ == "__main__":
    last = None                  # the (app, url) we were on before
    started = time.monotonic()   # when we arrived there
    try:
        while True:
            app, url = current_active()
            current = (app, url or "")   # turn None into "" so the comparison is consistent

            if current != last:
                now = time.monotonic()
                if last is not None:
                    print(f" Now: {describe(*current)} (spent {format_duration(now - started)} on {describe(*last)})")
                else:
                    print(f"Now: {describe(*current)}")
                last = current
                started = now

            NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(1.0))
    except KeyboardInterrupt:
        if last is not None:
            print(f"\n  spent {format_duration(time.monotonic() - started)} on {describe(*last)}")
        

