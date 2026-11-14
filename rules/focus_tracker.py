"""Tracks focus over time and decides WHEN to warn."""


class FocusTracker:
    def __init__(self, grace_seconds, repeat_seconds):
        self.grace = grace_seconds
        self.repeat = repeat_seconds
        self.state = "FOCUSED"
        self.off_since = None      # when you left the allowed list
        self.last_alert = None     # when we last warned you
        self.last_allowed = None   # where to send you back in force mode

    def update(self, activity, status, now):
        """Feed in the latest status; returns an event name or None."""
        if status == "neutral":
            return None

        if status == "allowed":
            self.last_allowed = activity
            was_distracted = self.state == "DISTRACTED"
            self.state, self.off_since, self.last_alert = "FOCUSED", None, None
            return "refocused" if was_distracted else None

        # status == "distracting"
        if self.state == "FOCUSED":
            self.state, self.off_since = "DRIFTING", now
            return "drifting"

        if self.state == "DRIFTING" and now - self.off_since >= self.grace:
            self.state, self.last_alert = "DISTRACTED", now
            return "distracted"

        if self.state == "DISTRACTED" and now - self.last_alert >= self.repeat:
            self.last_alert = now
            return "still_distracted"

        return None