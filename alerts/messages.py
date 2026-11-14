import random

PERSONAS = {
    "base": {
        "distracted":       ["You're on {where}. Back to studying."],
        "still_distracted": ["Still on {where}."],
        "refocused":        ["Back on track."],
    },
    "kind": {
        "distracted":       ["Hey, looks like you wandered to {where}. Want to head back? 🙂",
                             "Little detour to {where}! Let's get back to it."],
        "still_distracted": ["Still on {where}. You've got this, let's refocus."],
        "refocused":        ["Nice, welcome back! 🎉"],
    },
    "stern": {
        "distracted":       ["{where}? Really? Close it.",
                             "That is not studying. Back to work."],
        "still_distracted": ["Still on {where}. Your exam won't study for itself."],
        "refocused":        ["Good. Keep it that way."],
    },
}


def pick_message(persona, event, where):
    options = PERSONAS.get(persona, PERSONAS["base"])[event]
    return random.choice(options).format(where=where)