"""Decides if the current activity is allowed, distracting, or neutral."""
from monitor.detector import BROWSER_SCRIPTS


def domain_matches(domain, allowed_domains):
    # "brightspace.usc.edu" matches "usc.edu"; "notusc.edu" does not
    return any(domain == d or domain.endswith("." + d) for d in allowed_domains)

def _norm(text):
    return text.strip().lower()

def app_matches(app, allowed_apps):
    # Case-insensitive; "matlab" also matches "MATLAB_R2024b"
    a = _norm(app)
    return any(a == _norm(x) or a.startswith(_norm(x)) for x in allowed_apps)

def classify(activity, config):
    app, url, domain = activity["app"], activity["url"], activity["domain"]

    if app is None or _norm(app) in [_norm(n) for n in config["neutral_apps"]]:
        return "neutral"

    if app in BROWSER_SCRIPTS:
        # New tab, settings page, no window, or URL unreadable: don't judge it
        if not url or not url.startswith(("http://", "https://")):
            return "neutral"
        if domain in ("127.0.0.1", "localhost"):
            return "neutral"   # the dashboard itself: not studying, not distracting
        
        if domain in ("127.0.0.1", "localhost"):
            return "neutral"   # the dashboard itself: not studying, not distracting
        
        return "allowed" if domain_matches(domain, config["allowed_domains"]) else "distracting"
    return "allowed" if app_matches(app, config["allowed_apps"]) else "distracting"
