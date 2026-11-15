import subprocess
from pathlib import Path
from monitor.detector import BROWSER_SCRIPTS

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

def _focus_existing_tab(app_name, url):
    """Switch to an already-open tab with this exact URL. Returns True if found."""
    if app_name == "Safari":
        body = '''
            repeat with w in windows
                repeat with t in tabs of w
                    if URL of t is theURL then
                        set current tab of w to t
                        set index of w to 1
                        return "found"
                    end if
                end repeat
            end repeat'''
    else:  # Chrome, Brave, Edge, Arc
        body = '''
            repeat with w in windows
                set i to 0
                repeat with t in tabs of w
                    set i to i + 1
                    if URL of t is theURL then
                        set active tab index of w to i
                        set index of w to 1
                        return "found"
                    end if
                end repeat
            end repeat'''
    script = (f'on run argv\n set theURL to item 1 of argv\n'
              f' tell application "{app_name}"\n activate\n{body}\n'
              f' return "missing"\n end tell\nend run')
    try:
        result = subprocess.run(["osascript", "-e", script, url],
                                capture_output=True, text=True, timeout=5)
    except subprocess.TimeoutExpired:
        return False
    return result.stdout.strip() == "found"

def force_back(target):
    """Bring the last allowed app (and page, for browsers) back to the front."""
    if not target or not target.get("app_path"):
        print("   [force] no allowed app seen yet, nothing to go back to")
        return
    #new: integrate with focus_existing_tab function
    app_name = Path(target["app_path"]).stem   # "Google Chrome.app" -> "Google Chrome"
    url = target.get("url")

    # Browsers: reuse the existing tab instead of opening a new one
    if url and app_name in BROWSER_SCRIPTS:
        if _focus_existing_tab(app_name, url):
            print(f"   [force] switched to existing tab: {url}")
            return
        print("   [force] tab not found, opening it")

    cmd = ["open", "-a", target["app_path"]]
    if url:
        cmd.append(url)
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"   [force] failed: {result.stderr.strip()}")