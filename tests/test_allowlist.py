import pytest

from rules.allowlist import app_matches, classify, domain_matches

CONFIG = {
    "allowed_apps": ["Code", "MATLAB"],
    "allowed_domains": ["usc.edu", "github.com"],
    "neutral_apps": ["Dock"],
}


def act(app, url=None, domain=None):
    return {"app": app, "url": url, "domain": domain}


@pytest.mark.parametrize("domain,ok", [
    ("usc.edu", True), ("brightspace.usc.edu", True), ("notusc.edu", False), ("usc.edu.evil.com", False),
])
def test_domain_matches(domain, ok):
    assert domain_matches(domain, ["usc.edu"]) is ok


@pytest.mark.parametrize("app,ok", [
    ("Code", True), ("code", True), ("Code - Insiders", True),
    ("MATLAB_R2024b", True), ("MATLAB2024", True), ("MATLAB-beta", True),
    ("Codex", False), ("Codecademy", False), ("MATLABish", False),
])
def test_app_prefix_rule(app, ok):
    assert app_matches(app, CONFIG["allowed_apps"]) is ok


def test_classify_apps():
    assert classify(act("Code"), CONFIG) == "allowed"
    assert classify(act("Discord"), CONFIG) == "distracting"
    assert classify(act("dock"), CONFIG) == "neutral"
    assert classify(act(None), CONFIG) == "neutral"


def test_classify_browser():
    assert classify(act("Safari", "https://github.com/x", "github.com"), CONFIG) == "allowed"
    assert classify(act("Safari", "https://www.youtube.com/", "youtube.com"), CONFIG) == "distracting"
    assert classify(act("Safari", "http://127.0.0.1:5050/", "127.0.0.1"), CONFIG) == "neutral"
    assert classify(act("Safari", "chrome://newtab", None), CONFIG) == "neutral"
    assert classify(act("Safari"), CONFIG) == "neutral"
