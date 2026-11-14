import time
from datetime import datetime

from AppKit import NSRunLoop, NSDate

from monitor.detector import get_current_activity

POLL_SECONDS = 1.0


def wait(seconds):
    # Lets macOS process events while we wait. With time.sleep() instead,
    # get_front_app() keeps returning the same stale app.
    NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(seconds))


def label(activity):
    if activity["domain"]:
        return f'{activity["app"]} — {activity["domain"]}'
    return activity["app"]


def main():
    print("Study Monitor watching... (Ctrl+C to stop)")
    last, since = None, time.monotonic()

    while True:
        current = label(get_current_activity())
        if current != last:
            now = time.monotonic()
            note = f"   (left {last} after {now - since:.0f}s)" if last else ""
            print(f"[{datetime.now():%H:%M:%S}] {current}{note}")
            last, since = current, now
        wait(POLL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")