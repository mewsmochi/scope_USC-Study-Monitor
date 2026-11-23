import random

PERSONAS = {
    "base": {
        "drifting":          ["You're on {where}. Back to studying within {seconds}s."],
        "distracted":        ["You're on {where}. Back to studying."],
        "distracted_forced": ["You were on {where}, so I sent you back. Stay focused."],
        "still_distracted":  ["Still on {where}."],
        "refocused":         ["Back on track."],
        "away_distracted":       ["You're looking away from your screen. Back to studying."],
        "away_still_distracted": ["Still looking away."],
        "away_refocused":        ["Welcome back to your screen."],
    },
    "kind": {
        "drifting":          ["Looks like you wandered to {where}. You have {seconds}s to head back 🙂"],
        "distracted":        ["Hey, looks like you wandered to {where}. Want to head back? 🙂",
                              "Little detour to {where}! Let's get back to it."],
        "distracted_forced": ["I gently moved you back from {where}. You've got this! 🙂",
                              "Detour over! I brought you back from {where}. Let's keep going."],
        "still_distracted":  ["Still on {where}. You've got this, let's refocus."],
        "refocused":         ["Nice, welcome back! 🎉"],
        "away_distracted":       ["Hey, looks like you drifted away from the screen. Want to come back? 🙂",
                                  "Little break from the screen! Let's get back to it."],
        "away_still_distracted": ["Still away from the screen. You've got this, let's refocus."],
        "away_refocused":        ["Welcome back! Eyes back on the screen 🎉"],
    },
    "stern": {
        "drifting":          ["What do you think you're doing? You have {seconds}s to close it."],
        "distracted":        ["{where}? Really? Close it.",
                              "That is not studying. Back to work."],
        "distracted_forced": ["I warned you. {where} is gone, back to work.",
                              "Sent you back from {where}. Don't make me do it again."],
        "still_distracted":  ["Still on {where}. Your exam won't study for itself."],
        "refocused":         ["Good. Now, back to work."],
        "away_distracted":       ["Eyes up. That is not studying.",
                                  "Looking away? Back to work."],
        "away_still_distracted": ["Still not looking at your screen. Your exam won't study for itself."],
        "away_refocused":        ["Your eyes are back on the screen. Good. Keep them there."],
    },
}


def pick_message(persona, event, where, **extra):
    base = PERSONAS["base"]
    options = (PERSONAS.get(persona, base).get(event)
               or base.get(event)
               or base[event.removeprefix("away_")])   # look-away wording falls back to the generic message
    return random.choice(options).format(where=where, **extra)