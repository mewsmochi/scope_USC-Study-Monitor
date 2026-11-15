import random

PERSONAS = {
    "base": {
        "drifting":         ["You're on {where}. Back to studying within {seconds}s."],
        "distracted":       ["You're on {where}. Back to studying."],
        "distracted_forced": ["You were on {where}, so I sent you back. Stay focused."],
        "still_distracted": ["Still on {where}."],
        "refocused":        ["Back on track."],
    },
    "kind": {
        "drifting":         ["Looks like you wandered to {where}. You have {seconds}s to head back 🙂"],
        "distracted":       ["Hey, looks like you wandered to {where}. Want to head back? 🙂",
                             "Little detour to {where}! Let's get back to it."],
        "distracted_forced": ["I gently moved you back from {where}. You've got this! 🙂",
                              "Detour over! I brought you back from {where}. Let's keep going."],                    
        "still_distracted": ["Still on {where}. You've got this, let's refocus."],
        "refocused":        ["Nice, welcome back! 🎉"],
    },
    "stern": {
        "drifting":         ["{where}? You have {seconds}s to close it."],
        "distracted":       ["{where}? Really? Close it.",
                             "That is not studying. Back to work."],
        "distracted_forced": ["I warned you. {where} is gone, back to work.",
                              "Sent you back from {where}. Don't make me do it again."],
        "still_distracted": ["Still on {where}. Your exam won't study for itself."],
        "refocused":        ["Good. Keep it that way."],
    },
}


def pick_message(persona, event, where, **extra):
    options = PERSONAS.get(persona, PERSONAS["base"])[event]
    return random.choice(options).format(where=where, **extra)