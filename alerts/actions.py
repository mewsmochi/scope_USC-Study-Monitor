import subprocess


def notify(title, text):
    """macOS notification with a sound. Text is passed as arguments, so quotes can't break it."""
    subprocess.run(
        ["osascript",
         "-e", "on run argv",
         "-e", 'display notification (item 1 of argv) with title (item 2 of argv) sound name "Funk"',
         "-e", "end run",
         text, title],
        capture_output=True,
    )


def force_back(target):
    """Bring the last allowed app (and page, for browsers) back to the front."""
    if not target or not target.get("app_path"):
        return  # nothing allowed seen yet this run
    cmd = ["open", "-a", target["app_path"]]
    if target.get("url"):
        cmd.append(target["url"])   # browser: reopens the allowed page
    subprocess.run(cmd, capture_output=True)