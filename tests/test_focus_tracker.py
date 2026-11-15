from rules.focus_tracker import FocusTracker

CODE = {"app": "Code", "domain": None}
YT = {"app": "Google Chrome", "domain": "youtube.com"}


def test_grace_period_then_warning():
    t = FocusTracker(grace_seconds=10, repeat_seconds=30)
    assert t.update(YT, "distracting", 0) == "drifting"
    assert t.update(YT, "distracting", 9) is None
    assert t.update(YT, "distracting", 10) == "distracted"


def test_repeat_warnings():
    t = FocusTracker(10, 30)
    t.update(YT, "distracting", 0)
    t.update(YT, "distracting", 10)
    assert t.update(YT, "distracting", 39) is None
    assert t.update(YT, "distracting", 40) == "still_distracted"
    assert t.update(YT, "distracting", 70) == "still_distracted"


def test_refocus_only_after_distracted():
    t = FocusTracker(10, 30)
    t.update(YT, "distracting", 0)
    assert t.update(CODE, "allowed", 5) is None          # back during grace: no refocus message
    t.update(YT, "distracting", 6)
    t.update(YT, "distracting", 16)
    assert t.update(CODE, "allowed", 17) == "refocused"
    assert t.state == "FOCUSED" and t.last_allowed == CODE


def test_neutral_and_idle_dont_change_state():
    t = FocusTracker(10, 30)
    t.update(YT, "distracting", 0)
    for status in ("neutral", "idle"):
        assert t.update({"app": None, "domain": None}, status, 5) is None
    assert t.state == "DRIFTING"
    assert t.update(YT, "distracting", 10) == "distracted"   # timer kept running


def test_reset_keeps_last_allowed():
    t = FocusTracker(10, 30)
    t.update(CODE, "allowed", 0)
    t.update(YT, "distracting", 1)
    t.reset()
    assert t.state == "FOCUSED" and t.off_since is None
    assert t.last_allowed == CODE
